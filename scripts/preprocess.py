"""
Preprocessing script: NASA cleaned_dataset CSV → windowed tensors (30, 6).

Usage:
    python scripts/preprocess.py --data-dir data/raw/nasa/cleaned_dataset --output-dir data/processed

Output files:
    data/processed/train.pt  — {"X": Tensor(N,30,6), "y": Tensor(N,)}
    data/processed/val.pt
    data/processed/test.pt
"""

import argparse
import os
import random
import sys

import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import MinMaxScaler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import FEATURES, RAW_FEATURES

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

# Battery ID split — fixed, do NOT shuffle
TRAIN_IDS = ["B0005", "B0006", "B0007"]
VAL_IDS   = ["B0018"]  # first 70% of windows
TEST_IDS  = ["B0018"]  # last 30% of windows

WINDOW_SIZE       = 30
NOMINAL_CAPACITY  = 2.0  # NASA 18650 nominal capacity (Ah)


def load_battery(data_dir: str, battery_id: str) -> tuple[np.ndarray, np.ndarray]:
    """
    Load all discharge cycles for one battery from cleaned CSV dataset.

    Reads metadata.csv to find discharge cycles, then reads each cycle CSV
    and creates non-overlapping sliding windows of WINDOW_SIZE timesteps.

    Returns:
        X: (N_windows, 30, 6) float32 — configured RAW_FEATURES
        y: (N_windows,)       float32 — SOH % (capacity / 2.0 * 100)
    """
    meta_path = os.path.join(data_dir, "metadata.csv")
    cycles_dir = os.path.join(data_dir, "data")

    meta = pd.read_csv(meta_path)

    # Keep only discharge cycles for this battery that have a valid Capacity
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
        raise ValueError(f"No discharge cycles found for battery '{battery_id}' in {meta_path}")

    all_X, all_y = [], []

    for _, row in discharge.iterrows():
        csv_path = os.path.join(cycles_dir, row["filename"])
        if not os.path.exists(csv_path):
            print(f"  [WARN] Missing file: {row['filename']} — skipped")
            continue

        df = pd.read_csv(csv_path)

        if not all(col in df.columns for col in RAW_FEATURES):
            print(f"  [WARN] Missing columns in {row['filename']} — skipped")
            continue

        series = [df[col].values.astype(np.float32) for col in RAW_FEATURES]

        n = min(len(values) for values in series)
        if n < WINDOW_SIZE:
            continue

        soh = float(row["Capacity"]) / NOMINAL_CAPACITY * 100

        # Non-overlapping sliding windows across the discharge cycle
        for i in range(0, n - WINDOW_SIZE + 1, WINDOW_SIZE):
            window = np.stack(
                [values[i : i + WINDOW_SIZE] for values in series],
                axis=1,
            )  # (30, 6)
            all_X.append(window)
            all_y.append(soh)

    if len(all_X) == 0:
        raise RuntimeError(f"No windows created for battery '{battery_id}' — check data files.")

    return np.array(all_X, dtype=np.float32), np.array(all_y, dtype=np.float32)


def make_windows(data_dir: str, battery_ids: list[str]) -> tuple[np.ndarray, np.ndarray]:
    X_list, y_list = [], []
    for bid in battery_ids:
        X, y = load_battery(data_dir, bid)
        X_list.append(X)
        y_list.append(y)
        print(f"  {bid}: {len(X)} windows, SOH range [{y.min():.1f}%, {y.max():.1f}%]")
    return np.concatenate(X_list), np.concatenate(y_list)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir",   default="data/raw/nasa/cleaned_dataset")
    parser.add_argument("--output-dir", default="data/processed")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print("Loading train batteries...")
    X_train, y_train = make_windows(args.data_dir, TRAIN_IDS)

    print("Loading val/test battery (B0018)...")
    X_b0018, y_b0018 = make_windows(args.data_dir, VAL_IDS)

    # B0018 split: first 70% → val, last 30% → test
    split = int(len(X_b0018) * 0.7)
    X_val,  y_val  = X_b0018[:split],  y_b0018[:split]
    X_test, y_test = X_b0018[split:],  y_b0018[split:]

    print(f"\nSplit summary:")
    print(f"  Train : {len(X_train):>5} windows")
    print(f"  Val   : {len(X_val):>5} windows")
    print(f"  Test  : {len(X_test):>5} windows")

    # Fit scaler on train only — (N*30, F) → fit → reshape back
    N_train, W, F = X_train.shape
    scaler = MinMaxScaler()
    X_train_scaled = scaler.fit_transform(X_train.reshape(-1, F)).reshape(N_train, W, F)
    X_val_scaled   = scaler.transform(X_val.reshape(-1, F)).reshape(len(X_val),   W, F)
    X_test_scaled  = scaler.transform(X_test.reshape(-1, F)).reshape(len(X_test),  W, F)

    joblib.dump(
        {
            "scaler":     scaler,
            "version":    "1.0",
            "trained_on": TRAIN_IDS,
            "features":   FEATURES,
        },
        "models/weights/scaler.pkl",
    )
    print("\nSaved scaler -> models/weights/scaler.pkl")

    for name, X, y in [
        ("train", X_train_scaled, y_train),
        ("val",   X_val_scaled,   y_val),
        ("test",  X_test_scaled,  y_test),
    ]:
        path = os.path.join(args.output_dir, f"{name}.pt")
        torch.save({"X": torch.tensor(X), "y": torch.tensor(y)}, path)
        print(f"Saved {name}.pt  ({len(X)} samples)")

    print("\nPreprocessing complete.")


if __name__ == "__main__":
    main()
