"""
Training script: train MambaSOHPredictor + IsolationForest on preprocessed data.

Usage:
    python scripts/train.py --data-dir data/processed --epochs 100

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
try:
    from torch.amp import GradScaler, autocast  # PyTorch 2.x unified API
    _AMP_DEVICE = "cuda"
except ImportError:
    from torch.cuda.amp import GradScaler, autocast  # type: ignore[assignment]
    _AMP_DEVICE = None
from sklearn.ensemble import IsolationForest
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import D_MODEL, D_STATE, INPUT_FEATURES, ISO_FOREST_PATH, LONG_MAMBA_PATH, LONG_MODEL_VERSION, MAMBA_PATH, MODEL_VERSION, SPECTRAL_FEAT_DIM, WARMUP_STAGES, WINDOW_SIZE  # noqa: E402
from src.models.soh_predictor import MambaSOHPredictor  # noqa: E402

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)  # seed all GPUs — no-op on CPU; needed for GPU reproducibility


def _seed_worker(worker_id: int) -> None:
    """Seed each DataLoader worker so shuffle order is reproducible across runs."""
    worker_seed = SEED + worker_id
    np.random.seed(worker_seed)
    random.seed(worker_seed)

BATCH_SIZE     = 32
VAL_BATCH_SIZE = 256
LR             = 5e-4
PATIENCE       = 15


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

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

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
        raise KeyError(f"'X_feat' not found in {path}. Run scripts/preprocess.py first.")
    return data["X"], data["X_feat"], data["y"]


def evaluate(model: nn.Module, X: torch.Tensor, X_feat: torch.Tensor, y: torch.Tensor,
             device: torch.device, batch_size: int = VAL_BATCH_SIZE) -> dict:
    model.eval()
    preds = []
    loader = DataLoader(TensorDataset(X, X_feat), batch_size=batch_size)
    with torch.no_grad():
        for X_b, Xf_b in loader:
            preds.append(model(X_b.to(device), Xf_b.to(device)).cpu())
    pred = torch.cat(preds) * 100.0
    mae  = torch.mean(torch.abs(pred - y)).item()
    rmse = torch.sqrt(torch.mean((pred - y) ** 2)).item()
    loss = torch.mean(((pred / 100.0) - (y / 100.0)) ** 2).item()
    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "loss": loss}


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def _setup_device_amp(logger: logging.Logger):
    """Resolve device, enable deterministic cuDNN, build AMP scaler + autocast ctx."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Device: {device}")
    if device.type == "cuda":
        # Reproducibility over autotuning: benchmark=True picks different conv
        # algorithms run-to-run, making results non-reproducible across runs.
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    use_amp = device.type == "cuda"
    if _AMP_DEVICE:
        amp_scaler = GradScaler(_AMP_DEVICE, enabled=use_amp)
        def _amp_ctx(): return autocast(_AMP_DEVICE, enabled=use_amp)
    else:
        amp_scaler = GradScaler(enabled=use_amp)
        def _amp_ctx(): return autocast(enabled=use_amp)
    logger.info(f"AMP: {'enabled (fp16)' if use_amp else 'disabled'}")
    return device, use_amp, amp_scaler, _amp_ctx


def train(data_dir: str, epochs: int, log_dir: str) -> None:
    logger = setup_logger(log_dir)

    logger.info("Loading data...")
    X_train, X_feat_train, y_train = load_split(os.path.join(data_dir, "train.pt"))
    X_val,   X_feat_val,   y_val   = load_split(os.path.join(data_dir, "val.pt"))
    X_test,  X_feat_test,  y_test  = load_split(os.path.join(data_dir, "test.pt"))
    logger.info(f"  Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")

    if X_train.shape[-1] != INPUT_FEATURES:
        raise ValueError(f"Data has {X_train.shape[-1]} features, config expects {INPUT_FEATURES}.")
    if X_feat_train.shape[-1] != SPECTRAL_FEAT_DIM:
        raise ValueError(f"Feature dim {X_feat_train.shape[-1]}, config expects {SPECTRAL_FEAT_DIM}.")

    # Re-seed right before model init — JIT compilation at module import
    # may consume PyTorch random state, causing different weight initialization
    device, use_amp, amp_scaler, _amp_ctx = _setup_device_amp(logger)

    loader_gen = torch.Generator()
    loader_gen.manual_seed(SEED)
    train_loader = DataLoader(
        TensorDataset(X_train, X_feat_train, y_train),
        batch_size=BATCH_SIZE, shuffle=True,
        pin_memory=use_amp, num_workers=2, persistent_workers=True,
        generator=loader_gen, worker_init_fn=_seed_worker,
    )

    torch.manual_seed(SEED)
    model     = MambaSOHPredictor(input_features=INPUT_FEATURES, feat_dim=SPECTRAL_FEAT_DIM, d_model=D_MODEL, d_state=D_STATE).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5, min_lr=1e-6
    )
    criterion = nn.MSELoss()
    GRAD_CLIP = 1.0
    n_params  = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"MambaSOHPredictor — {n_params:,} trainable params")
    logger.info(f"Config: lr={LR}, batch={BATCH_SIZE}, epochs={epochs}, patience={PATIENCE}")


    best_val_loss    = float("inf")
    patience_counter = 0
    best_state       = None

    logger.info("Starting training...")
    logger.info(f"{'Epoch':>6}  {'TrainLoss':>10}  {'ValLoss':>10}  {'ValMAE%':>8}  {'ValRMSE%':>9}")
    logger.info("-" * 55)

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        for X_batch, X_feat_batch, y_batch in train_loader:
            optimizer.zero_grad(set_to_none=True)
            with _amp_ctx():
                pred  = model(X_batch.to(device), X_feat_batch.to(device))
                loss  = criterion(pred, (y_batch / 100.0).to(device))
            amp_scaler.scale(loss).backward()
            amp_scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            amp_scaler.step(optimizer)
            amp_scaler.update()
            train_loss += loss.item() * len(X_batch)
        train_loss /= len(X_train)

        val_metrics = evaluate(model, X_val, X_feat_val, y_val, device)
        val_loss    = val_metrics["loss"]
        current_lr  = optimizer.param_groups[0]["lr"]

        logger.debug(
            f"{epoch:>6}  {train_loss:>10.6f}  {val_loss:>10.6f}"
            f"  {val_metrics['mae']:>8.4f}  {val_metrics['rmse']:>9.4f}"
        )

        if epoch % 10 == 0:
            logger.info(
                f"{epoch:>6}  {train_loss:>10.6f}  {val_loss:>10.6f}"
                f"  {val_metrics['mae']:>8.4f}  {val_metrics['rmse']:>9.4f}"
                f"  lr={current_lr:.2e}"
            )

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

    model.load_state_dict(best_state)
    test_metrics = evaluate(model, X_test, X_feat_test, y_test, device)
    logger.info("-" * 55)
    logger.info(f"Test MAE : {test_metrics['mae']:.4f}%  (target < 2.0%)")
    logger.info(f"Test RMSE: {test_metrics['rmse']:.4f}%  (target < 3.0%)")

    if test_metrics["mae"] < 2.0 and test_metrics["rmse"] < 3.0:
        logger.info("Target metrics ACHIEVED (MAE < 2%, RMSE < 3%)")
    else:
        if test_metrics["mae"] >= 2.0:
            logger.warning(f"MAE {test_metrics['mae']:.4f}% >= 2.0% target")
        if test_metrics["rmse"] >= 3.0:
            logger.warning(f"RMSE {test_metrics['rmse']:.4f}% >= 3.0% target")

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

    logger.info("Training IsolationForest on spectral features (54 dims)...")
    iso = IsolationForest(contamination=0.1, n_estimators=100, random_state=SEED)
    iso.fit(X_feat_train.numpy())
    joblib.dump(iso, ISO_FOREST_PATH)
    logger.info(f"Saved IsolationForest -> {ISO_FOREST_PATH}")

    logger.info("Training complete.")


# ---------------------------------------------------------------------------
# Long-sequence training (GH-10): progressive length warmup + grad accumulation
# ---------------------------------------------------------------------------

def truncate_seq(X: torch.Tensor, stage_len: int) -> torch.Tensor:
    """Keep the LAST stage_len timesteps (label = current/last state, so the
    tail is the relevant context). Returns X unchanged if already shorter."""
    if X.shape[1] <= stage_len:
        return X
    return X[:, -stage_len:, :].contiguous()


def _train_epoch_accum(model, loader, optimizer, criterion, amp_scaler, amp_ctx,
                       device, grad_clip, n_samples, accum_steps) -> float:
    """One epoch with gradient accumulation: step optimizer every `accum_steps`
    micro-batches (and once at the end to flush the remainder), so effective
    batch = micro_batch * accum_steps while peak memory stays at micro_batch."""
    model.train()
    total = 0.0
    n_batches = len(loader)
    optimizer.zero_grad(set_to_none=True)
    for i, (X_b, X_feat_b, y_b) in enumerate(loader):
        with amp_ctx():
            pred = model(X_b.to(device), X_feat_b.to(device))
            loss = criterion(pred, (y_b / 100.0).to(device))
        amp_scaler.scale(loss / accum_steps).backward()
        if (i + 1) % accum_steps == 0 or (i + 1) == n_batches:
            amp_scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            amp_scaler.step(optimizer)
            amp_scaler.update()
            optimizer.zero_grad(set_to_none=True)
        total += loss.item() * len(X_b)
    return total / n_samples


def train_long(data_dir: str, log_dir: str, accum_steps: int = 4, micro_batch: int = 8,
               stage_epochs: int = 3, final_epochs: int = 50, stages: list[int] | None = None,
               num_workers: int = 2, eval_batch: int = 16) -> None:
    """Train the long-sequence model (L up to 4096) with progressive length warmup.

    Each stage truncates sequences to a shorter length (cheap epochs), carrying
    weights forward — Mamba params are length-independent so transfer is valid.
    The final (full-length) stage uses early stopping. Uses attention pooling.
    """
    logger = setup_logger(log_dir)
    logger.info("=== Long-sequence training (GH-10) ===")
    X_train, X_feat_train, y_train = load_split(os.path.join(data_dir, "train.pt"))
    X_val,   X_feat_val,   y_val   = load_split(os.path.join(data_dir, "val.pt"))
    X_test,  X_feat_test,  y_test  = load_split(os.path.join(data_dir, "test.pt"))
    seq_len = X_train.shape[1]
    logger.info(f"  Train {len(X_train)} | Val {len(X_val)} | Test {len(X_test)} | seq_len={seq_len}")

    device, use_amp, amp_scaler, _amp_ctx = _setup_device_amp(logger)

    loader_gen = torch.Generator()
    loader_gen.manual_seed(SEED)
    torch.manual_seed(SEED)
    model = MambaSOHPredictor(
        input_features=INPUT_FEATURES, feat_dim=SPECTRAL_FEAT_DIM,
        d_model=D_MODEL, d_state=D_STATE, pooling="attention",
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5, min_lr=1e-6
    )
    criterion = nn.MSELoss()
    GRAD_CLIP = 1.0

    # Warmup stages ≤ seq_len, always ending exactly at seq_len
    base    = stages if stages is not None else WARMUP_STAGES
    stages  = [s for s in base if s <= seq_len]
    if not stages or stages[-1] != seq_len:
        stages.append(seq_len)
    logger.info(
        f"Warmup stages: {stages} | micro_batch={micro_batch} accum={accum_steps} "
        f"(eff batch={micro_batch * accum_steps})"
    )

    best_val_loss = float("inf")
    best_state = None
    patience_counter = 0
    for si, stage_len in enumerate(stages):
        is_final = (si == len(stages) - 1)
        Xtr_s  = truncate_seq(X_train, stage_len)
        Xval_s = truncate_seq(X_val,   stage_len)
        loader = DataLoader(
            TensorDataset(Xtr_s, X_feat_train, y_train),
            batch_size=micro_batch, shuffle=True, pin_memory=use_amp,
            num_workers=num_workers, persistent_workers=num_workers > 0,
            generator=loader_gen, worker_init_fn=_seed_worker,
        )
        n_epochs = final_epochs if is_final else stage_epochs
        logger.info(f"[stage {si + 1}/{len(stages)}] L={stage_len} epochs={n_epochs}{'  (final)' if is_final else ''}")
        for epoch in range(1, n_epochs + 1):
            train_loss  = _train_epoch_accum(
                model, loader, optimizer, criterion, amp_scaler, _amp_ctx,
                device, GRAD_CLIP, len(Xtr_s), accum_steps,
            )
            val_metrics = evaluate(model, Xval_s, X_feat_val, y_val, device, batch_size=eval_batch)
            val_loss    = val_metrics["loss"]
            scheduler.step(val_loss)
            logger.debug(f"  L={stage_len} ep{epoch}  train={train_loss:.6f} val={val_loss:.6f} mae={val_metrics['mae']:.4f}")
            if is_final:
                if val_loss < best_val_loss:
                    best_val_loss    = val_loss
                    best_state       = {k: v.clone() for k, v in model.state_dict().items()}
                    patience_counter = 0
                else:
                    patience_counter += 1
                if patience_counter >= PATIENCE:
                    logger.info(f"Early stopping at epoch {epoch} (final stage)")
                    break

    if best_state is not None:
        model.load_state_dict(best_state)

    test_metrics = evaluate(model, X_test, X_feat_test, y_test, device, batch_size=eval_batch)
    logger.info("-" * 55)
    logger.info(f"Test MAE : {test_metrics['mae']:.4f}%  (target < 2.0%)")
    logger.info(f"Test RMSE: {test_metrics['rmse']:.4f}%  (target < 3.0%)")
    if test_metrics["mae"] >= 2.0:
        logger.warning(f"MAE {test_metrics['mae']:.4f}% >= 2.0% target")
    if test_metrics["rmse"] >= 3.0:
        logger.warning(f"RMSE {test_metrics['rmse']:.4f}% >= 3.0% target")

    os.makedirs(os.path.dirname(LONG_MAMBA_PATH), exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "version":          LONG_MODEL_VERSION,
            "seq_len":          seq_len,
            "pooling":          "attention",
            "input_features":   INPUT_FEATURES,
            "feat_dim":         SPECTRAL_FEAT_DIM,
            "d_model":          D_MODEL,
            "d_state":          D_STATE,
            "test_mae":         test_metrics["mae"],
            "test_rmse":        test_metrics["rmse"],
        },
        LONG_MAMBA_PATH,
    )
    logger.info(f"Saved long Mamba model -> {LONG_MAMBA_PATH}")
    logger.info("Long-sequence training complete.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--epochs",   type=int, default=100)
    parser.add_argument("--log-dir",  default="logs/training")
    parser.add_argument("--long", action="store_true",
                        help="Train long-sequence model (L up to 4096) with warmup + grad accumulation")
    parser.add_argument("--accum-steps",  type=int, default=4)
    parser.add_argument("--micro-batch",  type=int, default=8)
    parser.add_argument("--stage-epochs", type=int, default=3)
    parser.add_argument("--final-epochs", type=int, default=50)
    parser.add_argument("--eval-batch",   type=int, default=16,
                        help="Eval batch for long-seq — small to avoid OOM at L=4096")
    args = parser.parse_args()
    if args.long:
        data_dir = args.data_dir or "data/processed_long"
        train_long(
            data_dir, args.log_dir,
            accum_steps=args.accum_steps, micro_batch=args.micro_batch,
            stage_epochs=args.stage_epochs, final_epochs=args.final_epochs,
            eval_batch=args.eval_batch,
        )
    else:
        train(args.data_dir or "data/processed", args.epochs, args.log_dir)


if __name__ == "__main__":
    main()
