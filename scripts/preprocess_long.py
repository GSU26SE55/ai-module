"""
Preprocessing (long-sequence, GH-10 v2): NASA cleaned_dataset → concatenated long
sequences (LONG_SEQ_LEN, 8) for L=4096 Mamba training.

v2 adds two derived features per timestep (computed on raw values within each cycle,
BEFORE any scaling):
  Feature 6 — IC curve (dQ/dV, A·s/V): incremental capacity per timestep.
    IC peaks shift monotonically with degradation (Dubarry et al. 2012, Weng et al. 2013).
    Clipped to [0, 20] A·s/V to remove numerical spikes during voltage plateaux.
  Feature 7 — discharge progress ([0, 1]): fraction of total cycle capacity discharged.
    Used by the model as a "phase channel" for discharge-weighted attention bias;
    goes from 0 (start of discharge) to 1 (end-of-discharge).

Both features are computed per cycle (no cross-cycle discontinuity from the time reset),
then concatenated across cycles before windowing.

v2 fits a SEPARATE 8-feature MinMaxScaler (scaler_long.pkl) on TRAIN timelines.
The window=30 scaler.pkl (6 features) is NOT used — the two scalers are independent.

Strategy:
  - Each battery: concatenate discharge cycles → timeline (T, 6)
  - Fit 8-feature MinMaxScaler on all TRAIN timelines → scaler_long.pkl
  - Slide LONG_SEQ_LEN window (stride LONG_SEQ_STRIDE) over scaled timeline
  - Label = SOH of last timestep in window
  - 54-dim spectral features on first 3 channels (voltage, current, temp) of scaled window

Usage:
    python scripts/preprocess_long.py --data-dir data/raw/nasa/cleaned_dataset \\
        --output-dir data/processed_long

Output:
    data/processed_long/{train,val,test}.pt
    Each: {"X": (N, LONG_SEQ_LEN, 8), "X_feat": (N, 54), "y": (N,),
           "seq_len": LONG_SEQ_LEN, "n_features": 8, "feature_scaler_version": "long-2.0"}
    models/weights/scaler_long.pkl  — 8-feature MinMaxScaler (train fit only)
    models/weights/feature_scaler_long.pkl  — 54-dim StandardScaler for spectral feats
"""

import argparse
import os
import random
import sys

import joblib
import numpy as np
import torch
from joblib import Parallel, delayed
from sklearn.preprocessing import MinMaxScaler, StandardScaler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.preprocess import TEST_IDS, TRAIN_IDS, VAL_IDS, load_cycles  # noqa: E402
from src.core.config import (  # noqa: E402
    FEATURE_SCALER_VERSION_LONG,
    BASE_FEATURES,
    LONG_FEATURE_SCALER_PATH,
    LONG_INPUT_FEATURES,
    LONG_SCALER_PATH,
    LONG_SEQ_LEN,
    LONG_SEQ_STRIDE,
)
from src.features.extractor import (  # noqa: E402
    compute_ic_curve_and_discharge_progress,
    extract_window_features,
)

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

LONG_SCALER_VERSION = "2.1"  # v2.1: feature ablation — 4 base + ic + progress (6 total)

assert LONG_INPUT_FEATURES == len(BASE_FEATURES) + 2, (
    f"preprocess_long.py produces {len(BASE_FEATURES) + 2} features (base {len(BASE_FEATURES)} + ic + progress)"
    f" but config.LONG_INPUT_FEATURES={LONG_INPUT_FEATURES}. Update config.py."
)


# ---------------------------------------------------------------------------
# Derived-feature helpers (per-cycle, raw values before scaling)
# ---------------------------------------------------------------------------


def _add_derived_features(cycle: np.ndarray) -> np.ndarray:
    """Add IC curve + discharge progress to one raw discharge cycle.

    Args:
        cycle: (T, 4) — [voltage, current, temperature, time] (config.BASE_FEATURES)
                         all RAW (unscaled) values.
    Returns:
        (T, 6) — appends [ic_curve, discharge_progress].

    Both features are computed on raw values WITHIN this single cycle so there
    are no discontinuities from the time-column reset at cycle boundaries.
    They are scaled later via scaler_long.pkl (MinMaxScaler fit on train).

    IC curve (dQ/dV):
        dQ = |I| * dt  — charge increment (A·s)
        dV = |ΔV|      — voltage change magnitude
        IC = dQ / dV   → large on voltage plateaux where chemistry transitions occur.
        Physical range [0, 20] A·s/V — clips numerical spikes at near-zero dV.

    Discharge progress:
        Fraction of total cycle capacity delivered: q_cumsum / q_total ∈ [0, 1].
        = 0 at start of discharge, = 1 at end-of-discharge.
        Serves as the 'phase channel' used by MambaSOHPredictor's discharge-weighted
        attention bias (model reads x[..., -1] for this purpose).
    """
    voltage = cycle[:, 0]
    current = cycle[:, 1]
    time_col = cycle[:, BASE_FEATURES.index("time")]

    ic, discharge_progress = compute_ic_curve_and_discharge_progress(
        voltage, current, time_col
    )
    return np.column_stack([cycle, ic, discharge_progress]).astype(np.float32)


# ---------------------------------------------------------------------------
# Timeline builder
# ---------------------------------------------------------------------------


def battery_timeline(data_dir: str, battery_id: str) -> tuple[np.ndarray, np.ndarray]:
    """Concatenate all discharge cycles of one battery into a single timeline (T, 6).

    Derived features (IC curve, discharge progress) are computed per-cycle on RAW
    values before concatenation, so the cycle-boundary time-reset never corrupts dQ/dV.

    Returns:
        X_raw:  (sum_T, 8) raw (unscaled) timesteps in cycle order.
        soh_ts: (sum_T,)   per-timestep SOH (= owning cycle's SOH).
    """
    cycles = load_cycles(data_dir, battery_id)
    if not cycles:
        raise ValueError(f"No usable discharge cycles for '{battery_id}'")
    X_parts = []
    for c, _, _ in cycles:
        X_parts.append(_add_derived_features(c))  # (T, 6) per cycle — raw
    X_raw = np.concatenate(X_parts, axis=0).astype(np.float32)
    soh_ts = np.concatenate(
        [np.full(len(c), soh, dtype=np.float32) for c, soh, _ in cycles]
    )
    return X_raw, soh_ts


# ---------------------------------------------------------------------------
# Window builder
# ---------------------------------------------------------------------------


def make_long_windows(
    X_raw: np.ndarray,
    soh_ts: np.ndarray,
    scaler,
    seq_len: int = LONG_SEQ_LEN,
    stride: int = LONG_SEQ_STRIDE,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Slide a seq_len window over a scaled timeline.

    Label = SOH of the last timestep (current-state estimate).
    Spectral features extracted on first 3 channels (voltage, current, temp) of
    the scaled window — same feature extractor as window=30 pipeline.
    Returns empty arrays if the timeline is shorter than seq_len.
    """
    T = len(X_raw)
    if T < seq_len:
        return (
            np.empty((0, seq_len, X_raw.shape[1]), dtype=np.float32),
            np.empty((0, 54), dtype=np.float32),
            np.empty((0,), dtype=np.float32),
        )

    X_scaled = scaler.transform(X_raw).astype(np.float32)
    starts = list(range(0, T - seq_len + 1, stride))

    def _one(s: int):
        win = X_scaled[s : s + seq_len]
        feat = extract_window_features(win[:, :3])  # voltage/current/temp only
        return win, feat, float(soh_ts[s + seq_len - 1])

    results = Parallel(n_jobs=-1, prefer="threads")(delayed(_one)(s) for s in starts)
    if not results:
        return (
            np.empty((0, seq_len, X_raw.shape[1]), dtype=np.float32),
            np.empty((0, 54), dtype=np.float32),
            np.empty((0,), dtype=np.float32),
        )
    Xs, feats, ys = zip(*results)
    return (
        np.array(Xs, dtype=np.float32),
        np.array(feats, dtype=np.float32),
        np.array(ys, dtype=np.float32),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/raw/nasa/cleaned_dataset")
    parser.add_argument("--output-dir", default="data/processed_long")
    parser.add_argument("--seq-len", type=int, default=LONG_SEQ_LEN)
    parser.add_argument("--stride", type=int, default=LONG_SEQ_STRIDE)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    print(
        f"Long seq len: {args.seq_len} | stride: {args.stride} | features: {LONG_INPUT_FEATURES}"
    )

    # --- Fit 8-feature MinMaxScaler on ALL train timelines (raw values) ---
    # Done BEFORE windowing so the scaler sees the full range of each feature.
    # IC curve (feature 6) and discharge_progress (feature 7) are included.
    # scaler.pkl (6-feature, window=30) is NOT used — completely independent.
    print("\nFitting scaler_long.pkl on TRAIN timelines (8 features)...")
    train_timelines: list[tuple[np.ndarray, np.ndarray]] = []
    for bid in TRAIN_IDS:
        X_raw, soh_ts = battery_timeline(args.data_dir, bid)
        print(f"  {bid}: {len(X_raw)} raw timesteps")
        train_timelines.append((X_raw, soh_ts))
    raw_all = np.concatenate([t[0] for t in train_timelines], axis=0)

    long_scaler = MinMaxScaler()
    long_scaler.fit(raw_all)
    os.makedirs(os.path.dirname(LONG_SCALER_PATH), exist_ok=True)
    joblib.dump(
        {
            "scaler": long_scaler,
            "version": LONG_SCALER_VERSION,
            "features": BASE_FEATURES + ["ic_curve", "discharge_progress"],
            "trained_on": TRAIN_IDS,
        },
        LONG_SCALER_PATH,
    )
    print(
        f"Saved scaler_long.pkl -> {LONG_SCALER_PATH}  (v{LONG_SCALER_VERSION}, {LONG_INPUT_FEATURES} features)"
    )

    # --- Build windows for each split ---
    print("\nBuilding train long-windows...")
    Xtr, Ftr, ytr = [], [], []
    for bid, (X_raw, soh_ts) in zip(
        TRAIN_IDS, train_timelines
    ):  # reuse, no extra disk read
        X, F, y = make_long_windows(
            X_raw, soh_ts, long_scaler, args.seq_len, args.stride
        )
        print(f"  {bid}: timeline {len(X_raw)} steps -> {len(X)} windows")
        Xtr.append(X)
        Ftr.append(F)
        ytr.append(y)
    X_train = np.concatenate(Xtr, axis=0)
    X_feat_train = np.concatenate(Ftr, axis=0)
    y_train = np.concatenate(ytr, axis=0)
    if len(X_train) == 0:
        raise RuntimeError(
            f"No train windows produced — battery timelines shorter than seq_len={args.seq_len}. "
            "Lower --seq-len or --stride."
        )

    print(f"\nBuilding val long-windows ({VAL_IDS})...")
    Xvl, Fvl, yvl = [], [], []
    for bid in VAL_IDS:
        X_raw, soh_ts = battery_timeline(args.data_dir, bid)
        X, F, y = make_long_windows(
            X_raw, soh_ts, long_scaler, args.seq_len, args.stride
        )
        print(f"  {bid}: timeline {len(X_raw)} steps -> {len(X)} windows")
        Xvl.append(X)
        Fvl.append(F)
        yvl.append(y)
    X_val = (
        np.concatenate(Xvl, axis=0)
        if Xvl and any(len(a) for a in Xvl)
        else np.empty((0, args.seq_len, LONG_INPUT_FEATURES), dtype=np.float32)
    )
    X_feat_val = (
        np.concatenate(Fvl, axis=0)
        if Fvl and any(len(a) for a in Fvl)
        else np.empty((0, 54), dtype=np.float32)
    )
    y_val = (
        np.concatenate(yvl, axis=0)
        if yvl and any(len(a) for a in yvl)
        else np.empty((0,), dtype=np.float32)
    )

    print(f"\nBuilding test long-windows ({TEST_IDS})...")
    Xts, Fts, yts = [], [], []
    for bid in TEST_IDS:
        X_raw, soh_ts = battery_timeline(args.data_dir, bid)
        X, F, y = make_long_windows(
            X_raw, soh_ts, long_scaler, args.seq_len, args.stride
        )
        print(f"  {bid}: timeline {len(X_raw)} steps -> {len(X)} windows")
        Xts.append(X)
        Fts.append(F)
        yts.append(y)
    X_test = (
        np.concatenate(Xts, axis=0)
        if Xts and any(len(a) for a in Xts)
        else np.empty((0, args.seq_len, LONG_INPUT_FEATURES), dtype=np.float32)
    )
    X_feat_test = (
        np.concatenate(Fts, axis=0)
        if Fts and any(len(a) for a in Fts)
        else np.empty((0, 54), dtype=np.float32)
    )
    y_test = (
        np.concatenate(yts, axis=0)
        if yts and any(len(a) for a in yts)
        else np.empty((0,), dtype=np.float32)
    )

    # --- Refit spectral feature_scaler on TRAIN windows only ---
    print(
        "\nRefitting feature_scaler_long on long-window spectral features (train only)..."
    )
    feat_scaler = StandardScaler()
    X_feat_train = feat_scaler.fit_transform(X_feat_train).astype(np.float32)
    if len(X_feat_val) > 0:
        X_feat_val = feat_scaler.transform(X_feat_val).astype(np.float32)
    if len(X_feat_test) > 0:
        X_feat_test = feat_scaler.transform(X_feat_test).astype(np.float32)

    os.makedirs(os.path.dirname(LONG_FEATURE_SCALER_PATH), exist_ok=True)
    joblib.dump(
        {
            "scaler": feat_scaler,
            "version": FEATURE_SCALER_VERSION_LONG,
            "n_features": X_feat_train.shape[1],
        },
        LONG_FEATURE_SCALER_PATH,
    )
    print(f"Saved feature_scaler_long.pkl -> {LONG_FEATURE_SCALER_PATH}")

    print("\nSplit summary:")
    print(f"  Train: {len(X_train):>4} windows  (features={X_train.shape[-1]})")
    print(f"  Val  : {len(X_val):>4} windows")
    print(f"  Test : {len(X_test):>4} windows")

    for name, X, X_feat, y in [
        ("train", X_train, X_feat_train, y_train),
        ("val", X_val, X_feat_val, y_val),
        ("test", X_test, X_feat_test, y_test),
    ]:
        path = os.path.join(args.output_dir, f"{name}.pt")
        torch.save(
            {
                "X": torch.tensor(X, dtype=torch.float32),
                "X_feat": torch.tensor(X_feat, dtype=torch.float32),
                "y": torch.tensor(y, dtype=torch.float32),
                "seq_len": args.seq_len,
                "n_features": LONG_INPUT_FEATURES,
                "feature_scaler_version": FEATURE_SCALER_VERSION_LONG,
            },
            path,
        )
        print(f"Saved {name}.pt  ({len(X)} samples, shape {X.shape})")

    print("\nLong-sequence preprocessing v2 complete.")


if __name__ == "__main__":
    main()
