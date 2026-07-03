"""
Preprocessing script: NASA cleaned_dataset CSV → windowed tensors (30, 6) + window-level features.

Strategy:
  - MinMaxScaler fit/applied on raw timesteps
  - Spectral+Kurtosis features computed PER 30-STEP WINDOW, matching
    src/services/inference.py exactly (run_inference() only ever receives a
    single 30-step window per request — it has no access to the full cycle,
    so training must use the same window-scoped features or the model sees
    an out-of-distribution input at serving time). A prior version computed
    these on the full cycle (200-800 pts, richer FFT resolution) and shared
    one feature vector across all windows of a cycle — this caused severe
    train/serve skew (StandardScaler outliers up to -20 vs the expected
    ~[-3, 3] range) and unusable predictions in production.

Usage:
    python scripts/preprocess.py --data-dir data/raw/nasa/cleaned_dataset --output-dir data/processed

Output:
    data/processed/{train,val,test}.pt
    Each: {"X": Tensor(N,30,6), "X_feat": Tensor(N,54), "y": Tensor(N,)}
"""

import argparse
import os
import random
import sys

import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import MinMaxScaler, StandardScaler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import (
    CYCLE_COUNT_NORM,
    FEATURE_SCALER_PATH,
    FEATURE_SCALER_VERSION,
    FEATURE_SCALER_VERSION_LONG,
    BASE_FEATURES,
    LONG_FEATURE_SCALER_PATH,
    LONG_INPUT_FEATURES,
    LONG_SCALER_PATH,
    RAW_FEATURES,
    SCALER_VERSION,
    WINDOW_SIZE,
    WINDOW_STRIDE,
)
from src.features.extractor import (
    compute_ic_feature,
    compute_phase_mask,
    compute_soc_percent,
    extract_window_features,
)

SEED = 42
NOMINAL_CAPACITY = 2.0
MIN_SOH = 10.0  # filter failed/incomplete cycles (capacity ≈ 0 at extreme temps)

# 23 train / 2 val / 1 test — NASA cleaned_dataset
# Val/Test are 4°C (B0046/47/48). The original 15-battery train set had NO 4°C
# cells, so the model had to extrapolate across a temperature domain it never saw
# — the main cross-battery generalization gap. The 4°C additions below (B0041/45/53
# /54/55/56) close that gap; B0033/B0034 add the longest degradation curves in the
# dataset (~197 cycles → highest L=4096 window yield). Different battery ID = different
# physical cell, so 4°C siblings of the val/test cells are valid train data (no leakage).
# B0025-B0032: 24°C / 43°C, 28-40 cycles, limited degradation but adds temperature diversity
# B0042-B0044: 22°C, ~65 good cycles after filter, full degradation curve
# Skipped: B0036 (SOH spikes to 122% — noisy capacity), B0049-B0052 (too short/corrupt)
TRAIN_IDS = [
    "B0005",
    "B0006",
    "B0007",
    "B0018",  # original group — 24°C, 132-168 cycles
    "B0025",
    "B0026",
    "B0027",
    "B0028",  # 24°C, 28 cycles
    "B0029",
    "B0030",
    "B0031",
    "B0032",  # 43°C (high-temp), 40 cycles
    "B0042",
    "B0043",
    "B0044",  # 22°C, full degradation curve
    "B0033",
    "B0034",  # 24°C, 196-197 cycles — full curve to SOH~10%
    "B0041",
    "B0045",
    "B0053",  # 4°C, 25-70 cycles (SOH 30-61) — NEW temp domain
    "B0054",
    "B0055",
    "B0056",  # 4°C, 102 cycles each (SOH 37-67) — matches B0048 band
]
VAL_IDS = ["B0046", "B0047"]  # 4°C, 72 cycles each — held out
TEST_IDS = ["B0048"]  # 4°C, 72 cycles — held out entirely

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)


def load_cycles(data_dir: str, battery_id: str) -> list[tuple[np.ndarray, float, int]]:
    """Load each discharge cycle as (array, soh, cycle_idx) — not yet sliced.

    cycle_idx (GH-54): 0-based position of the cycle within this battery's
    kept discharge cycles (after test_id sort + filtering) — the model's
    aging-progress signal, normalized later by CYCLE_COUNT_NORM."""
    meta_path = os.path.join(data_dir, "metadata.csv")
    cycles_dir = os.path.join(data_dir, "data")
    meta = pd.read_csv(meta_path)

    discharge = (
        meta[
            (meta["battery_id"] == battery_id)
            & (meta["type"] == "discharge")
            & (meta["Capacity"].notna())
        ]
        .sort_values("test_id")
        .reset_index(drop=True)
    )

    if len(discharge) == 0:
        raise ValueError(f"No discharge cycles for '{battery_id}'")

    cycles = []
    for _, row in discharge.iterrows():
        csv_path = os.path.join(cycles_dir, row["filename"])
        if not os.path.exists(csv_path):
            continue
        df = pd.read_csv(csv_path)
        if not all(col in df.columns for col in RAW_FEATURES):
            continue
        n = min(len(df[col]) for col in RAW_FEATURES)
        cycle = np.stack(
            [df[col].values[:n].astype(np.float32) for col in RAW_FEATURES], axis=1
        )
        soh = float(row["Capacity"]) / NOMINAL_CAPACITY * 100
        if n >= WINDOW_SIZE and soh >= MIN_SOH:
            cycles.append((cycle, soh, len(cycles)))

    return cycles


def collect_cycles(
    data_dir: str, battery_ids: list[str]
) -> list[tuple[np.ndarray, float, int]]:
    all_cycles = []
    for bid in battery_ids:
        cycles = load_cycles(data_dir, bid)
        print(f"  {bid}: {len(cycles)} cycles")
        all_cycles.extend(cycles)
    return all_cycles


def cycles_to_windows(
    cycles: list[tuple[np.ndarray, float, int]],
    scaler: MinMaxScaler,
    feat_scaler: StandardScaler | None = None,
    long_seq: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Scale cycles, then slice windows and compute a per-window feature vector
    for each — matching src/services/inference.py's run_inference() exactly.

    long_seq=True: extends each cycle to LONG_INPUT_FEATURES (6) by appending
    IC curve (dQ/dV) and phase mask columns before scaling. The supplied scaler
    must have been fit on 6-feature data (scaler_long.pkl).

    long_seq=False (GH-54): appends 2 derived columns AFTER scaling the 4 base
    columns — cycle_count_norm (cycle_idx / CYCLE_COUNT_NORM, constant per
    cycle) and soc_percent/100 (window-local Coulomb counting, recomputed per
    window). Both are already in ~[0,1] by construction, so scaler.pkl stays
    a 4-feature scaler. Model input becomes (WINDOW_SIZE, 6).
    """
    all_X, all_feat, all_y = [], [], []

    for cycle_raw, soh, cycle_idx in cycles:
        T = len(cycle_raw)

        if long_seq:
            # Extend raw cycle: append IC curve + phase mask before scaling
            ic = compute_ic_feature(cycle_raw[:, 0], cycle_raw[:, 1])  # (T,)
            phase = compute_phase_mask(cycle_raw[:, 1])  # (T,)
            cycle_ext = np.column_stack([cycle_raw, ic, phase])  # (T, 6)
            cycle_scaled = scaler.transform(cycle_ext).astype(np.float32)
        else:
            cycle_scaled = scaler.transform(cycle_raw).astype(np.float32)

        # GH-59: clip to [0,1] — defensive symmetry with inference.py's
        # _append_derived_features(); a no-op for NASA data (max cycle_idx ~197).
        cycle_count_norm = np.float32(np.clip(cycle_idx / CYCLE_COUNT_NORM, 0.0, 1.0))

        # Non-overlapping sliding windows
        for i in range(0, T - WINDOW_SIZE + 1, WINDOW_STRIDE):
            window = cycle_scaled[i : i + WINDOW_SIZE]
            # Per-window features (voltage/current/temperature only) — matches
            # run_inference()'s extract_window_features(x_scaled[:, :3]) exactly,
            # since inference only ever sees this same WINDOW_SIZE slice.
            window_feat = extract_window_features(window[:, :3])  # (54,)
            if not long_seq:
                # GH-54: derived columns from the RAW window (current=col1, time=col3)
                raw_win = cycle_raw[i : i + WINDOW_SIZE]
                soc_norm = compute_soc_percent(raw_win[:, 1], raw_win[:, 3]) / 100.0
                window = np.column_stack(
                    [
                        window,
                        np.full(WINDOW_SIZE, cycle_count_norm, dtype=np.float32),
                        soc_norm,
                    ]
                )
            all_X.append(window)
            all_feat.append(window_feat)
            all_y.append(soh)

    X = np.array(all_X, dtype=np.float32)
    X_feat = np.array(all_feat, dtype=np.float32)
    y = np.array(all_y, dtype=np.float32)

    if feat_scaler is not None:
        X_feat = feat_scaler.transform(X_feat).astype(np.float32)

    return X, X_feat, y


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/raw/nasa/cleaned_dataset")
    parser.add_argument("--output-dir", default="data/processed")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    print(f"Window size: {WINDOW_SIZE} | Stride: {WINDOW_STRIDE}")

    print("\nLoading train cycles...")
    train_cycles = collect_cycles(args.data_dir, TRAIN_IDS)

    print("Loading val cycles...")
    val_cycles = collect_cycles(args.data_dir, VAL_IDS)

    print("Loading test cycles...")
    test_cycles = collect_cycles(args.data_dir, TEST_IDS)

    long_seq = WINDOW_SIZE > 30
    os.makedirs(os.path.dirname("models/weights/scaler.pkl"), exist_ok=True)

    if long_seq:
        # Long-seq mode (WINDOW_SIZE=4096): add IC curve + phase mask → 6 features.
        # Fit a separate MinMaxScaler on 8-feature train data → scaler_long.pkl.
        # The 6-feature scaler.pkl (for the production window=30 model) is unchanged.
        print(
            f"\nLong-seq mode (WINDOW_SIZE={WINDOW_SIZE}): adding IC curve + phase mask (features 7-8)..."
        )
        train_raw_ext = []
        for cycle_raw, _, _ in train_cycles:
            ic = compute_ic_feature(cycle_raw[:, 0], cycle_raw[:, 1])
            phase = compute_phase_mask(cycle_raw[:, 1])
            train_raw_ext.append(np.column_stack([cycle_raw, ic, phase]))
        train_raw_ext = np.concatenate(train_raw_ext, axis=0)

        scaler = MinMaxScaler()
        scaler.fit(train_raw_ext)
        joblib.dump(
            {
                "scaler": scaler,
                "version": "1.0",
                "trained_on": TRAIN_IDS,
                "features": BASE_FEATURES + ["ic_dqdv", "phase_mask"],
                "n_features": LONG_INPUT_FEATURES,
            },
            LONG_SCALER_PATH,
        )
        print(
            f"Saved scaler_long ({LONG_INPUT_FEATURES} features) -> {LONG_SCALER_PATH}"
        )
    else:
        # Standard window=30 mode: 4-feature (BASE_FEATURES) MinMaxScaler — 2 cột derived GH-54 KHÔNG qua scaler
        print("\nFitting MinMaxScaler...")
        train_raw = np.concatenate([c for c, _, _ in train_cycles], axis=0)
        scaler = MinMaxScaler()
        scaler.fit(train_raw)
        joblib.dump(
            {
                "scaler": scaler,
                "version": SCALER_VERSION,
                "trained_on": TRAIN_IDS,
                "features": BASE_FEATURES,
            },
            "models/weights/scaler.pkl",
        )
        print("Saved scaler -> models/weights/scaler.pkl")

    # Extract cycle-level features for train
    print("\nExtracting cycle-level Spectral+Kurtosis features...")
    X_train_raw, X_feat_train_raw, y_train = cycles_to_windows(
        train_cycles, scaler, long_seq=long_seq
    )
    print(f"  Train: {len(X_train_raw)} windows, feat shape: {X_feat_train_raw.shape}")

    feat_scaler = StandardScaler()
    X_feat_train = feat_scaler.fit_transform(X_feat_train_raw).astype(np.float32)

    feat_scaler_out = LONG_FEATURE_SCALER_PATH if long_seq else FEATURE_SCALER_PATH
    feat_scaler_ver = (
        FEATURE_SCALER_VERSION_LONG if long_seq else FEATURE_SCALER_VERSION
    )
    os.makedirs(os.path.dirname(feat_scaler_out), exist_ok=True)
    joblib.dump(
        {
            "scaler": feat_scaler,
            "version": feat_scaler_ver,
            "n_features": X_feat_train.shape[1],
        },
        feat_scaler_out,
    )
    print(f"Saved feature_scaler -> {feat_scaler_out}")

    X_val, X_feat_val, y_val = cycles_to_windows(
        val_cycles, scaler, feat_scaler, long_seq=long_seq
    )
    X_test, X_feat_test, y_test = cycles_to_windows(
        test_cycles, scaler, feat_scaler, long_seq=long_seq
    )

    print(f"\nSplit summary:")
    print(
        f"  Train: {len(X_train_raw):>5} windows from {len(train_cycles)} cycles  ({len(TRAIN_IDS)} batteries)"
    )
    print(
        f"  Val  : {len(X_val):>5} windows from {len(val_cycles)} cycles  ({len(VAL_IDS)} batteries: {VAL_IDS})"
    )
    print(
        f"  Test : {len(X_test):>5} windows from {len(test_cycles)} cycles  ({len(TEST_IDS)} batteries: {TEST_IDS})"
    )

    for name, X, X_feat, y in [
        ("train", X_train_raw, X_feat_train, y_train),
        ("val", X_val, X_feat_val, y_val),
        ("test", X_test, X_feat_test, y_test),
    ]:
        path = os.path.join(args.output_dir, f"{name}.pt")
        torch.save(
            {
                "X": torch.tensor(X, dtype=torch.float32),
                "X_feat": torch.tensor(X_feat, dtype=torch.float32),
                "y": torch.tensor(y, dtype=torch.float32),
                "feature_scaler_version": FEATURE_SCALER_VERSION,
            },
            path,
        )
        print(f"Saved {name}.pt  ({len(X)} samples)")

    print("\nPreprocessing complete.")


if __name__ == "__main__":
    main()
