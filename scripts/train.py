"""
Training script: train SOHPredictor (CNN-LSTM) + IsolationForest on preprocessed data.

Usage:
    python scripts/train.py --data-dir data/processed --epochs 50

Requires data/processed/{train,val,test}.pt from scripts/preprocess.py.
"""

import argparse
import os
import random
import sys

import joblib
import numpy as np
import torch
import torch.nn as nn
from sklearn.ensemble import IsolationForest
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import ISO_FOREST_PATH, LSTM_PATH, MODEL_VERSION  # noqa: E402
from src.models.soh_predictor import SOHPredictor  # noqa: E402

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

BATCH_SIZE = 32
LR = 1e-3
PATIENCE = 10


def load_split(path: str) -> tuple[torch.Tensor, torch.Tensor]:
    data = torch.load(path, weights_only=False)
    return data["X"], data["y"]


def train(data_dir: str, epochs: int) -> None:
    X_train, y_train = load_split(os.path.join(data_dir, "train.pt"))
    X_val, y_val = load_split(os.path.join(data_dir, "val.pt"))

    train_loader = DataLoader(
        TensorDataset(X_train, y_train), batch_size=BATCH_SIZE, shuffle=True
    )

    model = SOHPredictor()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    criterion = nn.MSELoss()

    best_val_loss = float("inf")
    patience_counter = 0
    best_state = None

    for epoch in range(1, epochs + 1):
        model.train()
        for X_batch, y_batch in train_loader:
            optimizer.zero_grad()
            pred = model(X_batch)
            loss = criterion(pred, y_batch / 100.0)
            loss.backward()
            optimizer.step()

        model.eval()
        with torch.no_grad():
            val_pred = model(X_val)
            val_loss = criterion(val_pred, y_val / 100.0).item()

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1

        if epoch % 10 == 0:
            print(f"Epoch {epoch}/{epochs} — val_loss: {val_loss:.6f}")

        if patience_counter >= PATIENCE:
            print(f"Early stopping at epoch {epoch}")
            break

    model.load_state_dict(best_state)
    os.makedirs(os.path.dirname(LSTM_PATH), exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "version": MODEL_VERSION,
            "window_size": 30,
            "input_features": 3,
        },
        LSTM_PATH,
    )
    print(f"✓ Saved LSTM model → {LSTM_PATH}")

    X_flat = X_train.numpy().reshape(len(X_train), -1)
    iso = IsolationForest(contamination=0.1, n_estimators=100, random_state=SEED)
    iso.fit(X_flat)
    joblib.dump(iso, ISO_FOREST_PATH)
    print(f"✓ Saved IsolationForest → {ISO_FOREST_PATH}")

    print("\n✅ Training complete.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/processed")
    parser.add_argument("--epochs", type=int, default=50)
    args = parser.parse_args()
    train(args.data_dir, args.epochs)


if __name__ == "__main__":
    main()
