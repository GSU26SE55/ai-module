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
    FEATURES,
    RAW_FEATURES,
    WINDOW_SIZE,
)
from src.features.extractor import extract_window_features

SEED             = 42
NOMINAL_CAPACITY = 2.0
TRAIN_IDS        = ["B0005", "B0006", "B0007"]
VAL_IDS          = ["B0018"]

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
        if n >= 2:
            cycles.append((cycle, soh))

    return cycles


def collect_cycles(data_dir: str, battery_ids: list[str]) -> list[tuple[np.ndarray, float]]:
    all_cycles = []
    for bid in battery_ids:
        cycles = load_cycles(data_dir, bid)
        print(f"  {bid}: {len(cycles)} cycles")
        all_cycles.extend(cycles)
    return all_cycles


def resample_cycle(cycle: np.ndarray, target_len: int = WINDOW_SIZE) -> np.ndarray:
    """Linearly resample one variable-length cycle to a fixed sequence length."""
    old_x = np.linspace(0.0, 1.0, num=len(cycle), dtype=np.float32)
    new_x = np.linspace(0.0, 1.0, num=target_len, dtype=np.float32)
    resampled = np.empty((target_len, cycle.shape[1]), dtype=np.float32)
    for col in range(cycle.shape[1]):
        resampled[:, col] = np.interp(new_x, old_x, cycle[:, col]).astype(np.float32)
    return resampled


def cycles_to_sequences(
    cycles: list[tuple[np.ndarray, float]],
    scaler: MinMaxScaler,
    feat_scaler: StandardScaler | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Scale cycles, resample each full cycle to WINDOW_SIZE, and compute
    spectral+kurtosis features on the resampled sequence.
    """
    all_X, all_feat, all_y = [], [], []

    for cycle_raw, soh in cycles:
        cycle_scaled = scaler.transform(cycle_raw).astype(np.float32)
        seq = resample_cycle(cycle_scaled, WINDOW_SIZE)

        # Sequence-level features: FFT + kurtosis on voltage/current/temperature.
        cycle_feat = extract_window_features(seq[:, :3])  # (54,)

        all_X.append(seq)
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
    print(f"Resampled sequence length: {WINDOW_SIZE}")

    print("\nLoading train cycles...")
    train_cycles = collect_cycles(args.data_dir, TRAIN_IDS)

    print("Loading val/test cycles (B0018)...")
    b0018_cycles = collect_cycles(args.data_dir, VAL_IDS)

    split      = int(len(b0018_cycles) * 0.7)
    val_cycles  = b0018_cycles[:split]
    test_cycles = b0018_cycles[split:]

    # Fit MinMaxScaler on all train timesteps
    print("\nFitting MinMaxScaler...")
    train_raw = np.concatenate([c for c, _ in train_cycles], axis=0)
    scaler    = MinMaxScaler()
    scaler.fit(train_raw)

    os.makedirs(os.path.dirname("models/weights/scaler.pkl"), exist_ok=True)
    joblib.dump(
        {"scaler": scaler, "version": "1.0", "trained_on": TRAIN_IDS, "features": FEATURES},
        "models/weights/scaler.pkl",
    )
    print("Saved scaler -> models/weights/scaler.pkl")

    # Extract cycle-level features
    print("\nExtracting cycle-level Spectral+Kurtosis features...")
    X_train_raw, X_feat_train_raw, y_train = cycles_to_sequences(train_cycles, scaler)
    print(f"  Train: {len(X_train_raw)} sequences, feat shape: {X_feat_train_raw.shape}")

    feat_scaler  = StandardScaler()
    X_feat_train = feat_scaler.fit_transform(X_feat_train_raw).astype(np.float32)

    os.makedirs(os.path.dirname(FEATURE_SCALER_PATH), exist_ok=True)
    joblib.dump(
        {"scaler": feat_scaler, "version": "1.1", "n_features": X_feat_train.shape[1]},
        FEATURE_SCALER_PATH,
    )
    print(f"Saved feature_scaler -> {FEATURE_SCALER_PATH}")

    X_val,  X_feat_val,  y_val  = cycles_to_sequences(val_cycles,  scaler, feat_scaler)
    X_test, X_feat_test, y_test = cycles_to_sequences(test_cycles, scaler, feat_scaler)

    print(f"\nSplit summary:")
    print(f"  Train: {len(X_train_raw):>5} sequences from {len(train_cycles)} cycles")
    print(f"  Val  : {len(X_val):>5} sequences from {len(val_cycles)} cycles")
    print(f"  Test : {len(X_test):>5} sequences from {len(test_cycles)} cycles")

    for name, X, X_feat, y in [
        ("train", X_train_raw,  X_feat_train, y_train),
        ("val",   X_val,        X_feat_val,   y_val),
        ("test",  X_test,       X_feat_test,  y_test),
    ]:
        path = os.path.join(args.output_dir, f"{name}.pt")
        torch.save(
            {
                "X":      torch.tensor(X,      dtype=torch.float32),
                "X_feat": torch.tensor(X_feat, dtype=torch.float32),
                "y":      torch.tensor(y,      dtype=torch.float32),
            },
            path,
        )
        print(f"Saved {name}.pt  ({len(X)} samples)")

    print("\nPreprocessing complete.")


if __name__ == "__main__":
    main()
