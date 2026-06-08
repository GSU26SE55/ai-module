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

BATCH_SIZE = 1      # physical batch; accumulation keeps the effective batch larger
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


def evaluate(
    model: nn.Module,
    X: torch.Tensor,
    X_feat: torch.Tensor,
    y: torch.Tensor,
    batch_size: int,
    device: torch.device,
    amp_enabled: bool,
    max_batches: int | None = None,
) -> dict:
    model.eval()
    preds = []
    targets = []
    with torch.no_grad():
        loader = DataLoader(TensorDataset(X, X_feat, y), batch_size=batch_size, shuffle=False)
        for step, (X_batch, X_feat_batch, y_batch) in enumerate(loader, start=1):
            if max_batches is not None and step > max_batches:
                break
            X_batch = X_batch.to(device, non_blocking=True)
            X_feat_batch = X_feat_batch.to(device, non_blocking=True)
            with torch.autocast(
                device_type=device.type,
                dtype=torch.float16,
                enabled=amp_enabled,
            ):
                pred = model(X_batch, X_feat_batch) * 100.0
            preds.append(pred.cpu())
            targets.append(y_batch)
    pred_all = torch.cat(preds)
    target_all = torch.cat(targets)
    mae  = torch.mean(torch.abs(pred_all - target_all)).item()
    rmse = torch.sqrt(torch.mean((pred_all - target_all) ** 2)).item()
    mse  = torch.mean(((pred_all / 100.0) - (target_all / 100.0)) ** 2).item()
    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "mse": mse}


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(
    data_dir: str,
    epochs: int,
    log_dir: str,
    batch_size: int,
    accumulation_steps: int,
    checkpoint_dir: str,
    resume: str | None,
    use_amp: bool,
    max_train_batches: int | None,
    max_eval_batches: int | None,
    skip_final_artifacts: bool,
) -> None:
    logger = setup_logger(log_dir)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Device: {device}")

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
        TensorDataset(X_train, X_feat_train, y_train),
        batch_size=batch_size,
        shuffle=True,
        pin_memory=device.type == "cuda",
    )

    # ── Model ──────────────────────────────────────────────────────────────
    model     = MambaSOHPredictor(input_features=INPUT_FEATURES, feat_dim=SPECTRAL_FEAT_DIM, d_model=D_MODEL, d_state=D_STATE).to(device)
    # torch.compile disabled: crashes on Windows with non-ASCII source files (cp1252 codec issue)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5, min_lr=1e-6
    )
    criterion = nn.MSELoss()
    amp_enabled = use_amp and device.type == "cuda"
    scaler = torch.cuda.amp.GradScaler(enabled=amp_enabled)
    GRAD_CLIP = 1.0  # gradient clipping — tránh exploding gradients trong SSM
    n_params  = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"MambaSOHPredictor — {n_params:,} trainable params")
    logger.info(
        f"Config: lr={LR}, batch={batch_size}, accumulation={accumulation_steps}, "
        f"effective_batch={batch_size * accumulation_steps}, epochs={epochs}, "
        f"patience={PATIENCE}, amp={amp_enabled}"
    )

    # ── Training loop ──────────────────────────────────────────────────────
    best_val_loss    = float("inf")
    patience_counter = 0
    best_state       = None
    start_epoch      = 1

    if resume:
        checkpoint = torch.load(resume, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint["model_state_dict"])
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        scheduler.load_state_dict(checkpoint["scheduler_state_dict"])
        scaler.load_state_dict(checkpoint["scaler_state_dict"])
        start_epoch = checkpoint["epoch"] + 1
        best_val_loss = checkpoint["best_val_loss"]
        patience_counter = checkpoint["patience_counter"]
        best_state = checkpoint.get("best_state")
        logger.info(f"Resumed from {resume} at epoch {start_epoch}")

    os.makedirs(checkpoint_dir, exist_ok=True)

    logger.info("Starting training...")
    logger.info(f"{'Epoch':>6}  {'TrainLoss':>10}  {'ValLoss':>10}  {'ValMAE%':>8}  {'ValRMSE%':>9}")
    logger.info("-" * 55)

    for epoch in range(start_epoch, epochs + 1):
        # Train
        model.train()
        train_loss = 0.0
        train_seen = 0
        optimizer.zero_grad(set_to_none=True)
        for step, (X_batch, X_feat_batch, y_batch) in enumerate(train_loader, start=1):
            if max_train_batches is not None and step > max_train_batches:
                break
            X_batch = X_batch.to(device, non_blocking=True)
            X_feat_batch = X_feat_batch.to(device, non_blocking=True)
            y_batch = y_batch.to(device, non_blocking=True)
            with torch.autocast(
                device_type=device.type,
                dtype=torch.float16,
                enabled=amp_enabled,
            ):
                pred = model(X_batch, X_feat_batch)
                raw_loss = criterion(pred, y_batch / 100.0)
                loss = raw_loss / accumulation_steps
            scaler.scale(loss).backward()

            should_step = (
                step % accumulation_steps == 0
                or step == len(train_loader)
                or (
                    max_train_batches is not None
                    and step == max_train_batches
                )
            )
            if should_step:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)

            train_loss += raw_loss.item() * len(X_batch)
            train_seen += len(X_batch)
        train_loss /= max(train_seen, 1)

        # Val
        model.eval()
        val_metrics = evaluate(
            model,
            X_val,
            X_feat_val,
            y_val,
            batch_size,
            device,
            amp_enabled,
            max_eval_batches,
        )
        val_loss = val_metrics["mse"]
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
            best_state       = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1

        torch.save(
            {
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "scheduler_state_dict": scheduler.state_dict(),
                "scaler_state_dict": scaler.state_dict(),
                "best_val_loss": best_val_loss,
                "patience_counter": patience_counter,
                "best_state": best_state,
            },
            os.path.join(checkpoint_dir, "latest.pt"),
        )

        if patience_counter >= PATIENCE:
            logger.info(f"Early stopping at epoch {epoch} (patience={PATIENCE})")
            break

    # ── Eval on test set ───────────────────────────────────────────────────
    model.load_state_dict(best_state)
    test_metrics = evaluate(
        model,
        X_test,
        X_feat_test,
        y_test,
        batch_size,
        device,
        amp_enabled,
        max_eval_batches,
    )
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
    if skip_final_artifacts:
        logger.info("Skipping final model/IsolationForest artifacts (--skip-final-artifacts).")
        return

    os.makedirs(os.path.dirname(MAMBA_PATH), exist_ok=True)
    torch.save(
        {
            "model_state_dict": {k: v.detach().cpu() for k, v in model.state_dict().items()},
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
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--accumulation-steps", type=int, default=8)
    parser.add_argument("--checkpoint-dir", default="models/checkpoints")
    parser.add_argument("--resume", default=None)
    parser.add_argument("--no-amp", action="store_true")
    parser.add_argument("--max-train-batches", type=int, default=None)
    parser.add_argument("--max-eval-batches", type=int, default=None)
    parser.add_argument("--skip-final-artifacts", action="store_true")
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1")
    if args.accumulation_steps < 1:
        parser.error("--accumulation-steps must be at least 1")
    train(
        args.data_dir,
        args.epochs,
        args.log_dir,
        args.batch_size,
        args.accumulation_steps,
        args.checkpoint_dir,
        args.resume,
        not args.no_amp,
        args.max_train_batches,
        args.max_eval_batches,
        args.skip_final_artifacts,
    )


if __name__ == "__main__":
    main()
