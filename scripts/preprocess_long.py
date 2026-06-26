"""
Preprocessing (long-sequence, GH-10): NASA cleaned_dataset → concatenated long
sequences (LONG_SEQ_LEN, 6) for L=4096 Mamba training.

Strategy:
  - Reuse the trained MinMaxScaler (models/weights/scaler.pkl). Raw-timestep
    scaling is windowing-independent → do NOT refit (consistency with window=30).
  - Concatenate consecutive discharge cycles of each battery into ONE timeline;
    each timestep carries its own cycle's SOH.
  - Slide a LONG_SEQ_LEN window (stride LONG_SEQ_STRIDE); label = SOH of the LAST
    timestep in the window (estimate current state from long history).
  - 54-dim spectral+kurtosis features computed on the FULL long window (not per
    cycle) → refit a dedicated feature_scaler (StandardScaler) on TRAIN windows
    only, saved separately from the window=30 feature_scaler.
  - Split by battery ID (train B0005/06/07; B0018 split 70/30 by timeline) — no
    cross-battery mixing inside a window, no random shuffle.

Usage:
    python scripts/preprocess_long.py --data-dir data/raw/nasa/cleaned_dataset \
        --output-dir data/processed_long

Output:
    data/processed_long/{train,val,test}.pt
    Each: {"X": (N, LONG_SEQ_LEN, 6), "X_feat": (N, 54), "y": (N,),
           "seq_len": LONG_SEQ_LEN, "feature_scaler_version": "long-1.0"}
"""

import argparse
import os
import random
import sys

import joblib
import numpy as np
import torch
from joblib import Parallel, delayed
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.preprocess import TEST_IDS, TRAIN_IDS, VAL_IDS, load_cycles  # noqa: E402
from src.core.config import (  # noqa: E402
    FEATURE_SCALER_VERSION_LONG,
    LONG_FEATURE_SCALER_PATH,
    LONG_SEQ_LEN,
    LONG_SEQ_STRIDE,
    SCALER_PATH,
)
from src.features.extractor import extract_window_features  # noqa: E402

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)


def battery_timeline(data_dir: str, battery_id: str) -> tuple[np.ndarray, np.ndarray]:
    """Concatenate all discharge cycles of one battery into a single timeline.

    Returns:
        X_raw:  (sum_T, 6) raw (unscaled) timesteps in cycle order.
        soh_ts: (sum_T,)   per-timestep SOH (= owning cycle's SOH).
    """
    cycles = load_cycles(data_dir, battery_id)  # [(cycle (T,6), soh), ...] in test_id order
    if not cycles:
        raise ValueError(f"No usable discharge cycles for '{battery_id}'")
    X_raw  = np.concatenate([c for c, _ in cycles], axis=0).astype(np.float32)
    soh_ts = np.concatenate(
        [np.full(len(c), soh, dtype=np.float32) for c, soh in cycles]
    )
    return X_raw, soh_ts


def make_long_windows(
    X_raw: np.ndarray,
    soh_ts: np.ndarray,
    scaler,
    seq_len: int = LONG_SEQ_LEN,
    stride: int = LONG_SEQ_STRIDE,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Slide a seq_len window over a scaled timeline.

    Label = SOH of the last timestep (current-state estimate). Features computed
    on the full window's voltage/current/temperature channels (54-dim).
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
        return win, extract_window_features(win[:, :3]), float(soh_ts[s + seq_len - 1])

    # prefer="threads": NumPy/SciPy FFT releases the GIL → thread parallelism avoids
    # process-spawn overhead while still getting ~3-5x speedup on feature extraction
    results = Parallel(n_jobs=-1, prefer="threads")(delayed(_one)(s) for s in starts)
    if not results:
        return (
            np.empty((0, seq_len, X_raw.shape[1]), dtype=np.float32),
            np.empty((0, 54), dtype=np.float32),
            np.empty((0,), dtype=np.float32),
        )
    Xs, feats, ys = zip(*results)
    return (
        np.array(Xs,    dtype=np.float32),
        np.array(feats, dtype=np.float32),
        np.array(ys,    dtype=np.float32),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir",   default="data/raw/nasa/cleaned_dataset")
    parser.add_argument("--output-dir", default="data/processed_long")
    parser.add_argument("--seq-len",    type=int, default=LONG_SEQ_LEN)
    parser.add_argument("--stride",     type=int, default=LONG_SEQ_STRIDE)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    print(f"Long seq len: {args.seq_len} | stride: {args.stride}")

    # Reuse the trained MinMaxScaler — do NOT refit (raw scaling is window-independent)
    if not os.path.exists(SCALER_PATH):
        raise FileNotFoundError(
            f"MinMaxScaler not found at '{SCALER_PATH}'. Run scripts/preprocess.py first "
            f"to fit and commit it (long-seq pipeline reuses the same raw scaler)."
        )
    scaler = joblib.load(SCALER_PATH)["scaler"]
    print(f"Loaded MinMaxScaler <- {SCALER_PATH}")

    # --- Train: each battery timeline windowed separately, then combined ---
    print("\nBuilding train long-windows...")
    Xtr, Ftr, ytr = [], [], []
    for bid in TRAIN_IDS:
        X_raw, soh_ts = battery_timeline(args.data_dir, bid)
        X, F, y = make_long_windows(X_raw, soh_ts, scaler, args.seq_len, args.stride)
        print(f"  {bid}: timeline {len(X_raw)} steps -> {len(X)} windows")
        Xtr.append(X)
        Ftr.append(F)
        ytr.append(y)
    X_train      = np.concatenate(Xtr, axis=0)
    X_feat_train = np.concatenate(Ftr, axis=0)
    y_train      = np.concatenate(ytr, axis=0)
    if len(X_train) == 0:
        raise RuntimeError(
            f"No train windows produced — battery timelines shorter than seq_len={args.seq_len}. "
            f"Lower --seq-len or --stride."
        )

    # --- Val: each VAL_IDS battery as its own timeline ---
    print(f"\nBuilding val long-windows ({VAL_IDS})...")
    Xvl, Fvl, yvl = [], [], []
    for bid in VAL_IDS:
        X_raw, soh_ts = battery_timeline(args.data_dir, bid)
        X, F, y = make_long_windows(X_raw, soh_ts, scaler, args.seq_len, args.stride)
        print(f"  {bid}: timeline {len(X_raw)} steps -> {len(X)} windows")
        Xvl.append(X); Fvl.append(F); yvl.append(y)
    X_val      = np.concatenate(Xvl, axis=0) if any(len(a) for a in Xvl) else np.empty((0, args.seq_len, X_train.shape[-1]), dtype=np.float32)
    X_feat_val = np.concatenate(Fvl, axis=0) if any(len(a) for a in Fvl) else np.empty((0, 54), dtype=np.float32)
    y_val      = np.concatenate(yvl, axis=0) if any(len(a) for a in yvl) else np.empty((0,), dtype=np.float32)

    # --- Test: TEST_IDS batteries (held out entirely) ---
    print(f"\nBuilding test long-windows ({TEST_IDS})...")
    Xts, Fts, yts = [], [], []
    for bid in TEST_IDS:
        X_raw, soh_ts = battery_timeline(args.data_dir, bid)
        X, F, y = make_long_windows(X_raw, soh_ts, scaler, args.seq_len, args.stride)
        print(f"  {bid}: timeline {len(X_raw)} steps -> {len(X)} windows")
        Xts.append(X); Fts.append(F); yts.append(y)
    X_test      = np.concatenate(Xts, axis=0) if any(len(a) for a in Xts) else np.empty((0, args.seq_len, X_train.shape[-1]), dtype=np.float32)
    X_feat_test = np.concatenate(Fts, axis=0) if any(len(a) for a in Fts) else np.empty((0, 54), dtype=np.float32)
    y_test      = np.concatenate(yts, axis=0) if any(len(a) for a in yts) else np.empty((0,), dtype=np.float32)

    # --- Refit feature_scaler on TRAIN long-window features only ---
    print("\nRefitting feature_scaler on long-window features (train only)...")
    feat_scaler  = StandardScaler()
    X_feat_train = feat_scaler.fit_transform(X_feat_train).astype(np.float32)
    if len(X_feat_val) > 0:
        X_feat_val = feat_scaler.transform(X_feat_val).astype(np.float32)
    if len(X_feat_test) > 0:
        X_feat_test = feat_scaler.transform(X_feat_test).astype(np.float32)

    os.makedirs(os.path.dirname(LONG_FEATURE_SCALER_PATH), exist_ok=True)
    joblib.dump(
        {"scaler": feat_scaler, "version": FEATURE_SCALER_VERSION_LONG, "n_features": X_feat_train.shape[1]},
        LONG_FEATURE_SCALER_PATH,
    )
    print(f"Saved long feature_scaler -> {LONG_FEATURE_SCALER_PATH}")

    print("\nSplit summary:")
    print(f"  Train: {len(X_train):>4} windows")
    print(f"  Val  : {len(X_val):>4} windows")
    print(f"  Test : {len(X_test):>4} windows")

    for name, X, X_feat, y in [
        ("train", X_train, X_feat_train, y_train),
        ("val",   X_val,   X_feat_val,   y_val),
        ("test",  X_test,  X_feat_test,  y_test),
    ]:
        path = os.path.join(args.output_dir, f"{name}.pt")
        torch.save(
            {
                "X":                      torch.tensor(X,      dtype=torch.float32),
                "X_feat":                 torch.tensor(X_feat, dtype=torch.float32),
                "y":                      torch.tensor(y,      dtype=torch.float32),
                "seq_len":                args.seq_len,
                "feature_scaler_version": FEATURE_SCALER_VERSION_LONG,
            },
            path,
        )
        print(f"Saved {name}.pt  ({len(X)} samples)")

    print("\nLong-sequence preprocessing complete.")


if __name__ == "__main__":
    main()
