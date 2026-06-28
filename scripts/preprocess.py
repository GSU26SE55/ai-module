"""
Preprocessing script: NASA cleaned_dataset CSV → windowed tensors (30, 6) + cycle-level features.

Strategy:
  - MinMaxScaler fit/applied on raw timesteps
  - Spectral+Kurtosis features computed on FULL discharge cycle (200-800 pts)
    not on 30-step windows — FFT has 100-400 bins vs 16 previously.
  - All 30-step windows from the same cycle share the same feature vector.

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
    FEATURE_SCALER_PATH,
    FEATURE_SCALER_VERSION,
    FEATURE_SCALER_VERSION_LONG,
    FEATURES,
    LONG_FEATURE_SCALER_PATH,
    LONG_INPUT_FEATURES,
    LONG_SCALER_PATH,
    RAW_FEATURES,
    WINDOW_SIZE,
    WINDOW_STRIDE,
)
from src.features.extractor import (
    compute_ic_feature,
    compute_phase_mask,
    extract_window_features,
)

SEED             = 42
NOMINAL_CAPACITY = 2.0
MIN_SOH          = 10.0   # filter failed/incomplete cycles (capacity ≈ 0 at extreme temps)

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
    "B0005", "B0006", "B0007", "B0018",          # original group — 24°C, 132-168 cycles
    "B0025", "B0026", "B0027", "B0028",           # 24°C, 28 cycles
    "B0029", "B0030", "B0031", "B0032",           # 43°C (high-temp), 40 cycles
    "B0042", "B0043", "B0044",                    # 22°C, full degradation curve
    "B0033", "B0034",                             # 24°C, 196-197 cycles — full curve to SOH~10%
    "B0041", "B0045", "B0053",                    # 4°C, 25-70 cycles (SOH 30-61) — NEW temp domain
    "B0054", "B0055", "B0056",                    # 4°C, 102 cycles each (SOH 37-67) — matches B0048 band
]
VAL_IDS  = ["B0046", "B0047"]                     # 4°C, 72 cycles each — held out
TEST_IDS = ["B0048"]                              # 4°C, 72 cycles — held out entirely

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)


def load_cycles(data_dir: str, battery_id: str) -> list[tuple[np.ndarray, float]]:
    """Load each discharge cycle as a full-length array (not yet sliced)."""
    meta_path  = os.path.join(data_dir, "metadata.csv")
    cycles_dir = os.path.join(data_dir, "data")
    meta       = pd.read_csv(meta_path)

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
        n     = min(len(df[col]) for col in RAW_FEATURES)
        cycle = np.stack([df[col].values[:n].astype(np.float32) for col in RAW_FEATURES], axis=1)
        soh   = float(row["Capacity"]) / NOMINAL_CAPACITY * 100
        if n >= WINDOW_SIZE and soh >= MIN_SOH:
            cycles.append((cycle, soh))

    return cycles


def collect_cycles(data_dir: str, battery_ids: list[str]) -> list[tuple[np.ndarray, float]]:
    all_cycles = []
    for bid in battery_ids:
        cycles = load_cycles(data_dir, bid)
        print(f"  {bid}: {len(cycles)} cycles")
        all_cycles.extend(cycles)
    return all_cycles


def cycles_to_windows(
    cycles: list[tuple[np.ndarray, float]],
    scaler: MinMaxScaler,
    feat_scaler: StandardScaler | None = None,
    long_seq: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Scale cycles, compute cycle-level features on full cycle, then slice windows.
    All WINDOW_SIZE-step windows of a cycle share the same feature vector.

    long_seq=True: extends each cycle to LONG_INPUT_FEATURES (8) by appending
    IC curve (dQ/dV) and phase mask columns before scaling. The supplied scaler
    must have been fit on 8-feature data (scaler_long.pkl).
    """
    all_X, all_feat, all_y = [], [], []

    for cycle_raw, soh in cycles:
        T = len(cycle_raw)

        if long_seq:
            # Extend raw cycle: append IC curve + phase mask before scaling
            ic    = compute_ic_feature(cycle_raw[:, 0], cycle_raw[:, 1])  # (T,)
            phase = compute_phase_mask(cycle_raw[:, 1])                    # (T,)
            cycle_ext    = np.column_stack([cycle_raw, ic, phase])         # (T, 8)
            cycle_scaled = scaler.transform(cycle_ext).astype(np.float32)
        else:
            cycle_scaled = scaler.transform(cycle_raw).astype(np.float32)

        # Cycle-level features: FFT on full cycle (voltage, current, temperature only)
        cycle_feat = extract_window_features(cycle_scaled[:, :3])  # (54,)

        # Non-overlapping sliding windows
        for i in range(0, T - WINDOW_SIZE + 1, WINDOW_STRIDE):
            all_X.append(cycle_scaled[i : i + WINDOW_SIZE])
            all_feat.append(cycle_feat)
            all_y.append(soh)

    X      = np.array(all_X,    dtype=np.float32)
    X_feat = np.array(all_feat, dtype=np.float32)
    y      = np.array(all_y,    dtype=np.float32)

    if feat_scaler is not None:
        X_feat = feat_scaler.transform(X_feat).astype(np.float32)

    return X, X_feat, y


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir",   default="data/raw/nasa/cleaned_dataset")
    parser.add_argument("--output-dir", default="data/processed")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    print(f"Window size: {WINDOW_SIZE} | Stride: {WINDOW_STRIDE}")

    print("\nLoading train cycles...")
    train_cycles = collect_cycles(args.data_dir, TRAIN_IDS)

    print("Loading val cycles...")
    val_cycles  = collect_cycles(args.data_dir, VAL_IDS)

    print("Loading test cycles...")
    test_cycles = collect_cycles(args.data_dir, TEST_IDS)

    long_seq = WINDOW_SIZE > 30
    os.makedirs(os.path.dirname("models/weights/scaler.pkl"), exist_ok=True)

    if long_seq:
        # Long-seq mode (WINDOW_SIZE=4096): add IC curve + phase mask → 8 features.
        # Fit a separate MinMaxScaler on 8-feature train data → scaler_long.pkl.
        # The 6-feature scaler.pkl (for the production window=30 model) is unchanged.
        print(f"\nLong-seq mode (WINDOW_SIZE={WINDOW_SIZE}): adding IC curve + phase mask (features 7-8)...")
        train_raw_ext = []
        for cycle_raw, _ in train_cycles:
            ic    = compute_ic_feature(cycle_raw[:, 0], cycle_raw[:, 1])
            phase = compute_phase_mask(cycle_raw[:, 1])
            train_raw_ext.append(np.column_stack([cycle_raw, ic, phase]))
        train_raw_ext = np.concatenate(train_raw_ext, axis=0)

        scaler = MinMaxScaler()
        scaler.fit(train_raw_ext)
        joblib.dump(
            {
                "scaler":      scaler,
                "version":     "1.0",
                "trained_on":  TRAIN_IDS,
                "features":    FEATURES + ["ic_dqdv", "phase_mask"],
                "n_features":  LONG_INPUT_FEATURES,
            },
            LONG_SCALER_PATH,
        )
        print(f"Saved scaler_long ({LONG_INPUT_FEATURES} features) -> {LONG_SCALER_PATH}")
    else:
        # Standard window=30 mode: 6-feature MinMaxScaler
        print("\nFitting MinMaxScaler...")
        train_raw = np.concatenate([c for c, _ in train_cycles], axis=0)
        scaler    = MinMaxScaler()
        scaler.fit(train_raw)
        joblib.dump(
            {"scaler": scaler, "version": "1.1", "trained_on": TRAIN_IDS, "features": FEATURES},
            "models/weights/scaler.pkl",
        )
        print("Saved scaler -> models/weights/scaler.pkl")

    # Extract cycle-level features for train
    print("\nExtracting cycle-level Spectral+Kurtosis features...")
    X_train_raw, X_feat_train_raw, y_train = cycles_to_windows(train_cycles, scaler, long_seq=long_seq)
    print(f"  Train: {len(X_train_raw)} windows, feat shape: {X_feat_train_raw.shape}")

    feat_scaler  = StandardScaler()
    X_feat_train = feat_scaler.fit_transform(X_feat_train_raw).astype(np.float32)

    feat_scaler_out = LONG_FEATURE_SCALER_PATH if long_seq else FEATURE_SCALER_PATH
    feat_scaler_ver = FEATURE_SCALER_VERSION_LONG if long_seq else FEATURE_SCALER_VERSION
    os.makedirs(os.path.dirname(feat_scaler_out), exist_ok=True)
    joblib.dump(
        {"scaler": feat_scaler, "version": feat_scaler_ver, "n_features": X_feat_train.shape[1]},
        feat_scaler_out,
    )
    print(f"Saved feature_scaler -> {feat_scaler_out}")

    X_val,  X_feat_val,  y_val  = cycles_to_windows(val_cycles,  scaler, feat_scaler, long_seq=long_seq)
    X_test, X_feat_test, y_test = cycles_to_windows(test_cycles, scaler, feat_scaler, long_seq=long_seq)

    print(f"\nSplit summary:")
    print(f"  Train: {len(X_train_raw):>5} windows from {len(train_cycles)} cycles  ({len(TRAIN_IDS)} batteries)")
    print(f"  Val  : {len(X_val):>5} windows from {len(val_cycles)} cycles  ({len(VAL_IDS)} batteries: {VAL_IDS})")
    print(f"  Test : {len(X_test):>5} windows from {len(test_cycles)} cycles  ({len(TEST_IDS)} batteries: {TEST_IDS})")

    for name, X, X_feat, y in [
        ("train", X_train_raw,  X_feat_train, y_train),
        ("val",   X_val,        X_feat_val,   y_val),
        ("test",  X_test,       X_feat_test,  y_test),
    ]:
        path = os.path.join(args.output_dir, f"{name}.pt")
        torch.save(
            {
                "X":                     torch.tensor(X,      dtype=torch.float32),
                "X_feat":                torch.tensor(X_feat, dtype=torch.float32),
                "y":                     torch.tensor(y,      dtype=torch.float32),
                "feature_scaler_version": FEATURE_SCALER_VERSION,
            },
            path,
        )
        print(f"Saved {name}.pt  ({len(X)} samples)")

    print("\nPreprocessing complete.")


if __name__ == "__main__":
    main()
