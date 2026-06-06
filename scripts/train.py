"""
Training script: train MambaSOHPredictor + IsolationForest on preprocessed data.

Usage:
    python scripts/train.py --data-dir data/processed --epochs 50

Requires data/processed/{train,val,test}.pt from scripts/preprocess.py.
Log file: logs/training/train_YYYYMMDD_HHMMSS.log
"""

import argparse
import logging
import os
import random
import sys
from datetime import datetime

import joblib
import numpy as np
import torch
import torch.nn as nn
from sklearn.ensemble import IsolationForest
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import D_MODEL, D_STATE, INPUT_FEATURES, ISO_FOREST_PATH, MAMBA_PATH, MODEL_VERSION, SPECTRAL_FEAT_DIM, WINDOW_SIZE  # noqa: E402
from src.models.soh_predictor import MambaSOHPredictor  # noqa: E402

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

BATCH_SIZE = 8      # L=256: tensor (8,256,128,16)=134MB, fit RAM
LR         = 5e-4
PATIENCE   = 15


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logger(log_dir: str) -> logging.Logger:
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path  = os.path.join(log_dir, f"train_{timestamp}.log")

    logger = logging.getLogger("train")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    # File handler — full detail
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler — INFO+
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    logger.info(f"Log file: {log_path}")
    return logger


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_split(path: str) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    data = torch.load(path, weights_only=False)
    if "X_feat" not in data:
        raise KeyError(
            f"'X_feat' not found in {path}. "
            "Run scripts/preprocess.py again to regenerate processed data with spectral features."
        )
    return data["X"], data["X_feat"], data["y"]


def evaluate(model: nn.Module, X: torch.Tensor, X_feat: torch.Tensor, y: torch.Tensor) -> dict:
    model.eval()
    with torch.no_grad():
        pred = model(X, X_feat) * 100.0
        mae  = torch.mean(torch.abs(pred - y)).item()
        rmse = torch.sqrt(torch.mean((pred - y) ** 2)).item()
    return {"mae": round(mae, 4), "rmse": round(rmse, 4)}


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(data_dir: str, epochs: int, log_dir: str) -> None:
    logger = setup_logger(log_dir)

    # ── Load data ──────────────────────────────────────────────────────────
    logger.info("Loading data...")
    X_train, X_feat_train, y_train = load_split(os.path.join(data_dir, "train.pt"))
    X_val,   X_feat_val,   y_val   = load_split(os.path.join(data_dir, "val.pt"))
    X_test,  X_feat_test,  y_test  = load_split(os.path.join(data_dir, "test.pt"))
    logger.info(f"  Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")
    if X_train.shape[-1] != INPUT_FEATURES:
        raise ValueError(
            f"Processed data has {X_train.shape[-1]} features, but config expects {INPUT_FEATURES}. "
            "Run scripts/preprocess.py again before training."
        )
    if X_feat_train.shape[-1] != SPECTRAL_FEAT_DIM:
        raise ValueError(
            f"Feature tensor has {X_feat_train.shape[-1]} dims, expected {SPECTRAL_FEAT_DIM}. "
            "Run scripts/preprocess.py again before training."
        )

    train_loader = DataLoader(
        TensorDataset(X_train, X_feat_train, y_train), batch_size=BATCH_SIZE, shuffle=True
    )

    # ── Model ──────────────────────────────────────────────────────────────
    model     = MambaSOHPredictor(input_features=INPUT_FEATURES, feat_dim=SPECTRAL_FEAT_DIM, d_model=D_MODEL, d_state=D_STATE)
    # torch.compile disabled: crashes on Windows with non-ASCII source files (cp1252 codec issue)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5, min_lr=1e-6
    )
    criterion = nn.MSELoss()
    GRAD_CLIP = 1.0  # gradient clipping — tránh exploding gradients trong SSM
    n_params  = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"MambaSOHPredictor — {n_params:,} trainable params")
    logger.info(f"Config: lr={LR}, batch={BATCH_SIZE}, epochs={epochs}, patience={PATIENCE}")

    # ── Training loop ──────────────────────────────────────────────────────
    best_val_loss    = float("inf")
    patience_counter = 0
    best_state       = None

    logger.info("Starting training...")
    logger.info(f"{'Epoch':>6}  {'TrainLoss':>10}  {'ValLoss':>10}  {'ValMAE%':>8}  {'ValRMSE%':>9}")
    logger.info("-" * 55)

    for epoch in range(1, epochs + 1):
        # Train
        model.train()
        train_loss = 0.0
        for X_batch, X_feat_batch, y_batch in train_loader:
            optimizer.zero_grad()
            pred  = model(X_batch, X_feat_batch)
            loss  = criterion(pred, y_batch / 100.0)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            optimizer.step()
            train_loss += loss.item() * len(X_batch)
        train_loss /= len(X_train)

        # Val
        model.eval()
        with torch.no_grad():
            val_pred = model(X_val, X_feat_val)
            val_loss = criterion(val_pred, y_val / 100.0).item()
        val_metrics = evaluate(model, X_val, X_feat_val, y_val)
        current_lr = optimizer.param_groups[0]["lr"]

        logger.debug(
            f"{epoch:>6}  {train_loss:>10.6f}  {val_loss:>10.6f}"
            f"  {val_metrics['mae']:>8.4f}  {val_metrics['rmse']:>9.4f}"
        )

        # Log every 10 epochs to console/file INFO
        if epoch % 10 == 0:
            logger.info(
                f"{epoch:>6}  {train_loss:>10.6f}  {val_loss:>10.6f}"
                f"  {val_metrics['mae']:>8.4f}  {val_metrics['rmse']:>9.4f}"
                f"  lr={current_lr:.2e}"
            )

        # Early stopping
        scheduler.step(val_loss)

        if val_loss < best_val_loss:
            best_val_loss    = val_loss
            best_state       = {k: v.clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1

        if patience_counter >= PATIENCE:
            logger.info(f"Early stopping at epoch {epoch} (patience={PATIENCE})")
            break

    # ── Eval on test set ───────────────────────────────────────────────────
    model.load_state_dict(best_state)
    test_metrics = evaluate(model, X_test, X_feat_test, y_test)
    logger.info("-" * 55)
    logger.info(f"Test MAE : {test_metrics['mae']:.4f}%  (target < 2.0%)")
    logger.info(f"Test RMSE: {test_metrics['rmse']:.4f}%  (target < 3.0%)")

    mae_ok  = test_metrics["mae"]  < 2.0
    rmse_ok = test_metrics["rmse"] < 3.0
    if mae_ok and rmse_ok:
        logger.info("Target metrics ACHIEVED (MAE < 2%, RMSE < 3%)")
    else:
        if not mae_ok:
            logger.warning(f"MAE {test_metrics['mae']:.4f}% >= 2.0% target — consider more epochs or d_model=128")
        if not rmse_ok:
            logger.warning(f"RMSE {test_metrics['rmse']:.4f}% >= 3.0% target — consider more epochs or d_model=128")

    # ── Save Mamba model ───────────────────────────────────────────────────
    os.makedirs(os.path.dirname(MAMBA_PATH), exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "version":          MODEL_VERSION,
            "window_size":      WINDOW_SIZE,
            "input_features":   INPUT_FEATURES,
            "feat_dim":         SPECTRAL_FEAT_DIM,
            "d_model":          D_MODEL,
            "d_state":          D_STATE,
            "test_mae":         test_metrics["mae"],
            "test_rmse":        test_metrics["rmse"],
        },
        MAMBA_PATH,
    )
    logger.info(f"Saved Mamba model -> {MAMBA_PATH}")

    # ── Train + save Isolation Forest ─────────────────────────────────────
    logger.info("Training IsolationForest...")
    X_flat = X_train.numpy().reshape(len(X_train), -1)  # (N, 30×6=180) — unchanged
    iso     = IsolationForest(contamination=0.1, n_estimators=100, random_state=SEED)
    iso.fit(X_flat)
    joblib.dump(iso, ISO_FOREST_PATH)
    logger.info(f"Saved IsolationForest -> {ISO_FOREST_PATH}")

    logger.info("Training complete.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/processed")
    parser.add_argument("--epochs",   type=int, default=50)
    parser.add_argument("--log-dir",  default="logs/training")
    args = parser.parse_args()
    train(args.data_dir, args.epochs, args.log_dir)


if __name__ == "__main__":
    main()
