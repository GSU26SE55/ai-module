"""
Preprocessing script: NASA Ames .mat files → windowed tensors (30, 3).

Usage:
    python scripts/preprocess.py --data-dir data/raw/nasa --output-dir data/processed

Output files:
    data/processed/train.pt  — {"X": Tensor(N,30,3), "y": Tensor(N,)}
    data/processed/val.pt
    data/processed/test.pt
"""

import argparse
import os
import random

import joblib
import numpy as np
import torch
from sklearn.preprocessing import MinMaxScaler

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

# Battery ID split — fixed, do NOT shuffle
TRAIN_IDS = ["B0005", "B0006", "B0007"]
VAL_IDS = ["B0018"]  # first 70% of timesteps
TEST_IDS = ["B0018"]  # last 30% of timesteps

WINDOW_SIZE = 30
FEATURES = ["voltage_measured", "current_measured", "temperature_measured"]
NOMINAL_CAPACITY = 2.0


def load_battery(mat_path: str) -> tuple[np.ndarray, np.ndarray]:
    """Load a NASA .mat file and return (features, soh) arrays."""
    import scipy.io

    battery_name = os.path.splitext(os.path.basename(mat_path))[0]
    data = scipy.io.loadmat(mat_path)
    battery = data[battery_name][0][0]
    cycles = battery["cycle"][0]

    all_features, all_soh = [], []
    for cycle in cycles:
        cycle_type = str(cycle["type"][0])
        if cycle_type != "discharge":
            continue
        capacity = float(cycle["data"][0][0]["Capacity"][0][0])
        soh = capacity / NOMINAL_CAPACITY * 100

        voltage = cycle["data"][0][0]["Voltage_measured"][0]
        current = cycle["data"][0][0]["Current_measured"][0]
        temp = cycle["data"][0][0]["Temperature_measured"][0]

        min_len = min(len(voltage), len(current), len(temp))
        for i in range(0, min_len - WINDOW_SIZE + 1, WINDOW_SIZE):
            window = np.stack(
                [
                    voltage[i : i + WINDOW_SIZE],
                    current[i : i + WINDOW_SIZE],
                    temp[i : i + WINDOW_SIZE],
                ],
                axis=1,
            )
            all_features.append(window)
            all_soh.append(soh)

    return np.array(all_features, dtype=np.float32), np.array(all_soh, dtype=np.float32)


def make_windows(
    data_dir: str, battery_ids: list[str]
) -> tuple[np.ndarray, np.ndarray]:
    X_list, y_list = [], []
    for bid in battery_ids:
        mat_path = os.path.join(data_dir, f"{bid}.mat")
        if not os.path.exists(mat_path):
            raise FileNotFoundError(f"Battery file not found: {mat_path}")
        X, y = load_battery(mat_path)
        X_list.append(X)
        y_list.append(y)
    return np.concatenate(X_list), np.concatenate(y_list)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/raw/nasa")
    parser.add_argument("--output-dir", default="data/processed")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    X_train, y_train = make_windows(args.data_dir, TRAIN_IDS)
    X_val_all, y_val_all = make_windows(args.data_dir, VAL_IDS)

    # B0018 split: first 70% → val, last 30% → test
    split = int(len(X_val_all) * 0.7)
    X_val, y_val = X_val_all[:split], y_val_all[:split]
    X_test, y_test = X_val_all[split:], y_val_all[split:]

    # Fit scaler on train only
    N_train, W, F = X_train.shape
    scaler = MinMaxScaler()
    X_train_2d = X_train.reshape(-1, F)
    X_train_scaled = scaler.fit_transform(X_train_2d).reshape(N_train, W, F)
    X_val_scaled = scaler.transform(X_val.reshape(-1, F)).reshape(len(X_val), W, F)
    X_test_scaled = scaler.transform(X_test.reshape(-1, F)).reshape(len(X_test), W, F)

    joblib.dump(
        {
            "scaler": scaler,
            "version": "1.0",
            "trained_on": TRAIN_IDS,
            "features": FEATURES,
        },
        "models/weights/scaler.pkl",
    )

    for name, X, y in [
        ("train", X_train_scaled, y_train),
        ("val", X_val_scaled, y_val),
        ("test", X_test_scaled, y_test),
    ]:
        torch.save(
            {"X": torch.tensor(X), "y": torch.tensor(y)},
            os.path.join(args.output_dir, f"{name}.pt"),
        )
        print(f"✓ Saved {name}.pt — {len(X)} samples")

    print("\n✅ Preprocessing complete.")


if __name__ == "__main__":
    main()
