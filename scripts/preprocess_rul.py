"""
Preprocessing (RUL, GH-13): NASA cleaned_dataset → cycle-level sequences for
Remaining Useful Life estimation.

Strategy:
  - Reuse the trained MinMaxScaler (models/weights/scaler.pkl) on raw timesteps —
    do NOT refit (scaling is windowing-independent, consistent with window=30).
  - Each discharge cycle → ONE 54-dim spectral+kurtosis vector (reuse
    extract_window_features on the cycle's voltage/current/temperature). This is
    the key difference vs the failed L=4096 raw approach: features are computed
    PER CYCLE (clean), not over ~13 concatenated cycles (diluted).
  - Slide a RUL_LOOKBACK-cycle window along the cycle axis (stride RUL_STRIDE).
    Label = remaining cycles until End-of-Life (first cycle with SOH <= EOL_SOH),
    measured at the LAST cycle of the window.
  - Split by battery ID (train B0005/06/07; B0018 split 70/30 along the cycle
    axis by the window's last-cycle index) — no random shuffle.
  - Refit a StandardScaler on TRAIN cycle-features only; saved separately.

Usage:
    python scripts/preprocess_rul.py --data-dir data/raw/nasa/cleaned_dataset \
        --output-dir data/processed_rul

Output:
    data/processed_rul/{train,val,test}.pt
    Each: {"X": (N, RUL_LOOKBACK, 54), "y": (N,) RUL in cycles,
           "lookback": int, "eol_soh": float, "feature_scaler_version": "rul-1.0"}
"""

import argparse
import os
import random
import sys

import joblib
import numpy as np
import torch
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.preprocess import TRAIN_IDS, VAL_IDS, load_cycles  # noqa: E402
from src.core.config import (  # noqa: E402
    EOL_SOH,
    RUL_FEATURE_SCALER_PATH,
    RUL_LOOKBACK,
    RUL_STRIDE,
    SCALER_PATH,
)
from src.features.extractor import extract_window_features  # noqa: E402

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

FEATURE_SCALER_VERSION_RUL = "rul-1.0"


def cycle_feature_series(data_dir: str, battery_id: str, scaler) -> tuple[np.ndarray, np.ndarray]:
    """One battery → (feats (n_cycles, 54), sohs (n_cycles,)) in chronological order."""
    cycles = load_cycles(data_dir, battery_id)
    if not cycles:
        raise ValueError(f"No usable discharge cycles for '{battery_id}'")
    feats, sohs = [], []
    for cyc, soh in cycles:
        cyc_scaled = scaler.transform(cyc).astype(np.float32)
        feats.append(extract_window_features(cyc_scaled[:, :3]))  # voltage, current, temp
        sohs.append(soh)
    return np.array(feats, dtype=np.float32), np.array(sohs, dtype=np.float32)


def find_eol(sohs: np.ndarray, eol_soh: float) -> int:
    """Index of the first cycle whose SOH drops to/below eol_soh (End-of-Life).
    Falls back to the last cycle if the battery never crosses the threshold."""
    below = np.where(sohs <= eol_soh)[0]
    return int(below[0]) if len(below) else len(sohs) - 1


def make_rul_windows(
    feats: np.ndarray,
    sohs: np.ndarray,
    lookback: int,
    stride: int,
    eol_soh: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """Slide a lookback-cycle window; label = cycles remaining to EOL at last cycle.

    Returns (X (N, lookback, 54), y (N,) cycles, last_idx (N,), eol_idx).
    Windows whose last cycle is past EOL are dropped (RUL would be undefined).
    """
    n = len(feats)
    eol = find_eol(sohs, eol_soh)
    Xs, ys, last_idxs = [], [], []
    for start in range(0, n - lookback + 1, stride):
        last = start + lookback - 1
        if last > eol:               # past End-of-Life — skip
            continue
        Xs.append(feats[start : start + lookback])
        ys.append(float(eol - last))  # remaining cycles
        last_idxs.append(last)
    if not Xs:
        return (
            np.empty((0, lookback, feats.shape[1]), dtype=np.float32),
            np.empty((0,), dtype=np.float32),
            np.empty((0,), dtype=np.int64),
            eol,
        )
    return (
        np.array(Xs, dtype=np.float32),
        np.array(ys, dtype=np.float32),
        np.array(last_idxs, dtype=np.int64),
        eol,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir",   default="data/raw/nasa/cleaned_dataset")
    parser.add_argument("--output-dir", default="data/processed_rul")
    parser.add_argument("--lookback",   type=int,   default=RUL_LOOKBACK)
    parser.add_argument("--stride",     type=int,   default=RUL_STRIDE)
    parser.add_argument("--eol-soh",    type=float, default=EOL_SOH)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    print(f"RUL lookback: {args.lookback} cycles | stride: {args.stride} | EOL: SOH<={args.eol_soh}%")

    if not os.path.exists(SCALER_PATH):
        raise FileNotFoundError(
            f"MinMaxScaler not found at '{SCALER_PATH}'. Run scripts/preprocess.py first."
        )
    scaler = joblib.load(SCALER_PATH)["scaler"]
    print(f"Loaded MinMaxScaler <- {SCALER_PATH}")

    # --- Train: B0005/06/07, windowed per battery then combined ---
    print("\nBuilding train RUL windows...")
    Xtr, ytr = [], []
    for bid in TRAIN_IDS:
        feats, sohs = cycle_feature_series(args.data_dir, bid, scaler)
        X, y, _, eol = make_rul_windows(feats, sohs, args.lookback, args.stride, args.eol_soh)
        print(f"  {bid}: {len(feats)} cycles | EOL@cycle {eol} (SOH {sohs[eol]:.1f}%) -> {len(X)} windows | RUL {y.min():.0f}..{y.max():.0f}")
        Xtr.append(X); ytr.append(y)
    X_train = np.concatenate(Xtr, axis=0)
    y_train = np.concatenate(ytr, axis=0)
    if len(X_train) == 0:
        raise RuntimeError(f"No train windows — timelines shorter than lookback={args.lookback}.")

    # --- Val/Test: B0018, split the valid RUL windows 70/30 in chronological order ---
    # (Split by window order, NOT cycle position: B0018 reaches EOL early, so a
    #  cycle-position split would leave all valid windows on one side.)
    print("\nBuilding val/test RUL windows (B0018, 70/30 by window order)...")
    feats, sohs = cycle_feature_series(args.data_dir, VAL_IDS[0], scaler)
    X_b, y_b, last_b, eol = make_rul_windows(feats, sohs, args.lookback, args.stride, args.eol_soh)
    split = int(len(X_b) * 0.7)
    X_val,  y_val  = X_b[:split], y_b[:split]   # earlier cycles (higher RUL)
    X_test, y_test = X_b[split:], y_b[split:]   # later cycles (lower RUL, near EOL)
    print(f"  B0018: {len(feats)} cycles | EOL@cycle {eol} (SOH {sohs[eol]:.1f}%) | {len(X_b)} valid windows")
    print(f"  -> val {len(X_val)} windows | test {len(X_test)} windows")

    # --- Refit feature_scaler on TRAIN cycle-features only ---
    print("\nRefitting feature_scaler on train cycle-features...")
    feat_scaler = StandardScaler()
    n_feat = X_train.shape[-1]
    feat_scaler.fit(X_train.reshape(-1, n_feat))

    def _scale(X):
        if len(X) == 0:
            return X
        return feat_scaler.transform(X.reshape(-1, n_feat)).reshape(X.shape).astype(np.float32)

    X_train, X_val, X_test = _scale(X_train), _scale(X_val), _scale(X_test)

    os.makedirs(os.path.dirname(RUL_FEATURE_SCALER_PATH), exist_ok=True)
    joblib.dump(
        {"scaler": feat_scaler, "version": FEATURE_SCALER_VERSION_RUL, "n_features": n_feat},
        RUL_FEATURE_SCALER_PATH,
    )
    print(f"Saved RUL feature_scaler -> {RUL_FEATURE_SCALER_PATH}")

    print("\nSplit summary:")
    print(f"  Train: {len(X_train):>4} windows  RUL {y_train.min():.0f}..{y_train.max():.0f}")
    print(f"  Val  : {len(X_val):>4} windows")
    print(f"  Test : {len(X_test):>4} windows")

    for name, X, y in [("train", X_train, y_train), ("val", X_val, y_val), ("test", X_test, y_test)]:
        path = os.path.join(args.output_dir, f"{name}.pt")
        torch.save(
            {
                "X":                      torch.tensor(X, dtype=torch.float32),
                "y":                      torch.tensor(y, dtype=torch.float32),
                "lookback":               args.lookback,
                "eol_soh":                args.eol_soh,
                "feature_scaler_version": FEATURE_SCALER_VERSION_RUL,
            },
            path,
        )
        print(f"Saved {name}.pt  ({len(X)} samples)")

    print("\nRUL preprocessing complete.")


if __name__ == "__main__":
    main()
