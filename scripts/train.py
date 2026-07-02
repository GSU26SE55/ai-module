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

from src.core.config import COSINE_T0, D_MODEL, D_STATE, EOL_SOH, FEATURE_SCALER_VERSION, FEATURE_SCALER_VERSION_LONG, INPUT_FEATURES, ISO_FOREST_PATH, LONG_INPUT_FEATURES, LONG_MAMBA_PATH, LONG_MODEL_VERSION, LONG_PATCH_SIZE, LONG_PATCH_STRIDE, MAMBA_PATH, MODEL_VERSION, RUL_FEAT_DIM, RUL_LOOKBACK, RUL_MAMBA_PATH, RUL_MODEL_VERSION, RUL_SCALE, SPECTRAL_FEAT_DIM, WARMUP_STAGES, WINDOW_SIZE  # noqa: E402
from src.models.rul_predictor import RULPredictor  # noqa: E402
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

def load_split(
    path: str, expected_version: str = FEATURE_SCALER_VERSION
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    data = torch.load(path, weights_only=False)
    if "X_feat" not in data:
        raise KeyError(f"'X_feat' not found in {path}. Run scripts/preprocess.py first.")
    saved_ver = data.get("feature_scaler_version")
    if expected_version is not None and saved_ver is not None and saved_ver != expected_version:
        raise ValueError(
            f"feature version mismatch in {path}: file has {saved_ver}, "
            f"config expects {expected_version}. Re-run the matching preprocess script."
        )
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
    X_train, X_feat_train, y_train = load_split(os.path.join(data_dir, "train.pt"), FEATURE_SCALER_VERSION)
    X_val,   X_feat_val,   y_val   = load_split(os.path.join(data_dir, "val.pt"),   FEATURE_SCALER_VERSION)
    X_test,  X_feat_test,  y_test  = load_split(os.path.join(data_dir, "test.pt"),  FEATURE_SCALER_VERSION)
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
                       device, grad_clip, n_samples, accum_steps, jitter: float = 0.0) -> float:
    """One epoch with gradient accumulation: step optimizer every `accum_steps`
    micro-batches (and once at the end to flush the remainder), so effective
    batch = micro_batch * accum_steps while peak memory stays at micro_batch.

    jitter>0 adds train-time Gaussian noise to the scaled input sequence (Tikhonov
    regularization, Bishop 1995) — improves cell-to-cell robustness on the held-out
    battery. Applied to X only (NOT x_feat); RNG is globally seeded so it stays
    reproducible across deterministic runs."""
    model.train()
    total = 0.0
    n_batches = len(loader)
    optimizer.zero_grad(set_to_none=True)
    for i, (X_b, X_feat_b, y_b) in enumerate(loader):
        # Signal CUDA Graphs that a new step begins — prevents tensor overwrite errors
        # when reduce-overhead mode replays the same graph across accum_steps iterations.
        torch.compiler.cudagraph_mark_step_begin()
        X_b = X_b.to(device)
        if jitter > 0.0:
            X_b = X_b + jitter * torch.randn_like(X_b)
        with amp_ctx():
            pred = model(X_b, X_feat_b.to(device))
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


def _soh_weighted_smooth_l1(
    pred: torch.Tensor, target: torch.Tensor,
    beta: float = 0.02, eol_threshold: float = 0.80, weight_scale: float = 2.0,
) -> torch.Tensor:
    """SmoothL1 loss with upweighting for near-EOL samples (SOH approaching 80%).

    target is SOH/100 in [0,1]. Samples with target close to eol_threshold (0.80)
    receive weight up to `weight_scale`× the base loss — encouraging the model to
    learn the critical degradation region more accurately.
    """
    base    = torch.nn.functional.smooth_l1_loss(pred, target, reduction="none", beta=beta)
    dist    = (target - eol_threshold).clamp(min=0)             # 0 at EOL, positive above
    weights = 1.0 + (weight_scale - 1.0) * torch.exp(-5.0 * dist)
    return (weights * base).mean()


def train_long(data_dir: str, log_dir: str, accum_steps: int = 4, micro_batch: int = 8,
               stage_epochs: int = 5, final_epochs: int = 50, stages: list[int] | None = None,
               num_workers: int = 2, eval_batch: int = 16,
               compile_model: bool = False, benchmark: bool = False,
               official_mamba: bool = False,
               patch_size: int = LONG_PATCH_SIZE, patch_stride: int = LONG_PATCH_STRIDE,
               weighted_loss: bool = False, eol_weight_scale: float = 2.0,
               cosine_t0: int = 25, weight_decay: float = 1e-5, dropout: float = 0.2,
               jitter: float = 0.0, swa: bool = False, swa_start_frac: float = 0.75,
               attention_heads: int = 1, warmup_cosine_t0: int = 0) -> None:
    """Train the long-sequence model (L up to 4096) with progressive length warmup.

    Each stage truncates sequences to a shorter length (cheap epochs), carrying
    weights forward — Mamba params are length-independent so transfer is valid.
    The final (full-length) stage uses early stopping. Uses attention pooling.
    """
    logger = setup_logger(log_dir)
    logger.info("=== Long-sequence training (GH-10) ===")
    X_train, X_feat_train, y_train = load_split(os.path.join(data_dir, "train.pt"), FEATURE_SCALER_VERSION_LONG)
    X_val,   X_feat_val,   y_val   = load_split(os.path.join(data_dir, "val.pt"),   FEATURE_SCALER_VERSION_LONG)
    X_test,  X_feat_test,  y_test  = load_split(os.path.join(data_dir, "test.pt"),  FEATURE_SCALER_VERSION_LONG)
    seq_len = X_train.shape[1]
    logger.info(f"  Train {len(X_train)} | Val {len(X_val)} | Test {len(X_test)} | seq_len={seq_len}")

    device, use_amp, amp_scaler, _amp_ctx = _setup_device_amp(logger)
    if benchmark and device.type == "cuda":
        torch.backends.cudnn.benchmark     = True
        torch.backends.cudnn.deterministic = False
        logger.info("cuDNN benchmark: ON (non-deterministic — reproducibility disabled)")

    loader_gen = torch.Generator()
    loader_gen.manual_seed(SEED)
    torch.manual_seed(SEED)
    num_tokens = (seq_len - patch_size) // patch_stride + 1 if patch_size > 1 else seq_len
    logger.info(
        f"Patch: size={patch_size} stride={patch_stride} → {num_tokens} tokens "
        f"(from {seq_len} raw timesteps, {seq_len // patch_size if patch_size > 1 else 1}× compression)"
        if patch_size > 1 else f"Patch: disabled (patch_size=1, {seq_len} tokens)"
    )
    # Long-seq model uses 8 input features (6 base + IC curve + phase mask).
    # Verify preprocessed data matches before wasting training time.
    if X_train.shape[-1] != LONG_INPUT_FEATURES:
        raise ValueError(
            f"Long-seq data has {X_train.shape[-1]} features but LONG_INPUT_FEATURES="
            f"{LONG_INPUT_FEATURES}. Re-run preprocess.py with WINDOW_SIZE>30 first."
        )
    model = MambaSOHPredictor(
        input_features=LONG_INPUT_FEATURES, feat_dim=SPECTRAL_FEAT_DIM,
        d_model=D_MODEL, d_state=D_STATE, pooling="attention",
        use_official_mamba=official_mamba,
        patch_size=patch_size, patch_stride=patch_stride,
        dropout=dropout, attention_heads=attention_heads,
    ).to(device)
    if compile_model:
        try:
            model = torch.compile(model, mode="default", dynamic=True)
            logger.info("torch.compile: ON (default, dynamic=True) — handles variable L across warmup stages without recompilation")
        except Exception as e:
            logger.warning(f"torch.compile unavailable ({e}) — falling back to eager")
    # AdamW (decoupled weight decay, Loshchilov & Hutter ICLR 2019) — correct form
    # for the L2 regularization that targets the cross-battery generalization gap.
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=weight_decay)
    # GH-38: warmup stages now use CosineAnnealingWarmRestarts too (was ReduceLROnPlateau).
    # One continuous CAWR across the warmup loop with T_0 = warmup restart period; with
    # T_0 = stage_epochs the LR anneals fully within a stage then restarts to full LR at
    # each new (longer) stage — letting the SSM escape local minima instead of the
    # monotonic LR decay that capped v1.x. Final stage still builds its own CAWR (with
    # --cosine-t0) after resetting LR. Ref: SGDR, Loshchilov & Hutter, ICLR 2017.
    warmup_t0 = max(1, warmup_cosine_t0 if warmup_cosine_t0 > 0 else stage_epochs)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
        optimizer, T_0=warmup_t0, T_mult=1, eta_min=1e-6,
    )
    logger.info(f"Warmup scheduler: CosineAnnealingWarmRestarts(T_0={warmup_t0}, T_mult=1, eta_min=1e-6)")
    # SmoothL1Loss(beta=0.02): clips gradient for residuals > 2% SOH, stabilising
    # training against noisy SOH labels (vs MSELoss which amplifies outliers).
    # Weighted variant upweights near-EOL samples (SOH approaching 80%).
    if weighted_loss:
        def criterion(pred, target):  # type: ignore[assignment]
            return _soh_weighted_smooth_l1(pred, target, beta=0.02,
                                           weight_scale=eol_weight_scale)
        logger.info(f"Loss: SmoothL1(beta=0.02) + EOL upweight (scale={eol_weight_scale})")
    else:
        criterion = nn.SmoothL1Loss(beta=0.02)
        logger.info("Loss: SmoothL1(beta=0.02)")
    GRAD_CLIP = 1.0
    logger.info(f"Optim: AdamW(lr={LR}, weight_decay={weight_decay}) | dropout={dropout} | jitter={jitter}")

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
    swa_state = None   # running weight average over the final stage's tail (SWA, Izmailov 2018)
    swa_n = 0
    swa_start = 0
    for si, stage_len in enumerate(stages):
        is_final = (si == len(stages) - 1)
        if is_final:
            # Reset LR to initial value — warmup-stage transitions accumulate
            # ReduceLROnPlateau reductions that would starve the final stage.
            # Adam momentum is preserved (warm from warmup) — only LR resets.
            for pg in optimizer.param_groups:
                pg["lr"] = LR
            # CosineAnnealingWarmRestarts: T_0-epoch cycles with period doubling.
            # Periodic LR restarts let the optimiser escape sharp minima that
            # ReduceLROnPlateau cannot recover from once LR is reduced. This
            # directly addresses the MAE ceiling observed in v1.x runs.
            # T_mult=2 → cycles: T_0, 2*T_0, 4*T_0 … (first restart at epoch T_0+1)
            scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
                optimizer, T_0=cosine_t0, T_mult=2, eta_min=1e-5,
            )
            patience_counter = 0
            best_val_loss = float("inf")
            # Patience must cover at least one full CAWR cycle so early-stopping
            # doesn't fire on the temporary val_loss increase after an LR restart.
            final_patience = max(PATIENCE, cosine_t0 + 5)
            # SWA: from this epoch on, average weights every epoch (low-LR tail of the
            # cosine anneal). Averaging points along the trajectory finds a wider, flatter
            # optimum that generalises better than any single checkpoint (Izmailov et al.,
            # UAI 2018). No BatchNorm in this model → averaged weights need no recalibration.
            swa_start = max(1, int(round(final_epochs * swa_start_frac))) if swa else 0
            logger.info(
                f"Final stage: reset LR={LR}, CosineAnnealingWarmRestarts "
                f"T_0={cosine_t0} T_mult=2 eta_min=1e-5 (patience={final_patience})"
                + (f" | SWA from epoch {swa_start}" if swa else "")
            )
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
                device, GRAD_CLIP, len(Xtr_s), accum_steps, jitter=jitter,
            )
            val_metrics = evaluate(model, Xval_s, X_feat_val, y_val, device, batch_size=eval_batch)
            val_loss    = val_metrics["loss"]
            # GH-38: both warmup and final stage now use CosineAnnealingWarmRestarts,
            # which steps purely by epoch count (no val_loss argument).
            scheduler.step()
            current_lr = optimizer.param_groups[0]["lr"]
            logger.debug(
                f"  L={stage_len} ep{epoch}  train={train_loss:.6f} "
                f"val={val_loss:.6f} mae={val_metrics['mae']:.4f} lr={current_lr:.2e}"
            )
            if is_final:
                if val_loss < best_val_loss:
                    best_val_loss    = val_loss
                    best_state       = {k: v.clone() for k, v in model.state_dict().items()}
                    patience_counter = 0
                else:
                    patience_counter += 1
                # SWA: fold this epoch's weights into the running average (tail only)
                if swa and epoch >= swa_start:
                    cur = model.state_dict()
                    if swa_state is None:
                        swa_state = {k: v.detach().float().clone() for k, v in cur.items()}
                        swa_n = 1
                    else:
                        for k, v in cur.items():
                            if torch.is_floating_point(v):
                                swa_state[k].mul_(swa_n / (swa_n + 1)).add_(v.detach().float() / (swa_n + 1))
                        swa_n += 1
                if patience_counter >= final_patience:
                    logger.info(f"Early stopping at epoch {epoch} (patience={final_patience})")
                    break

    if best_state is not None:
        model.load_state_dict(best_state)
    final_weights = "best-val-checkpoint"

    # SWA selection: compare the averaged weights vs the best single checkpoint on the
    # VALIDATION set (never the test set — that would leak). Keep whichever wins on val.
    if swa and swa_state is not None and swa_n > 0:
        model.load_state_dict(swa_state)
        swa_val = evaluate(model, X_val, X_feat_val, y_val, device, batch_size=eval_batch)
        logger.info(
            f"SWA: averaged {swa_n} epochs | SWA val_loss={swa_val['loss']:.6f} "
            f"vs best-ckpt val_loss={best_val_loss:.6f}"
        )
        if swa_val["loss"] <= best_val_loss:
            final_weights = f"SWA(avg={swa_n})"
        elif best_state is not None:
            model.load_state_dict(best_state)   # SWA worse on val → revert
    logger.info(f"Final weights: {final_weights}")

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
            "model_state_dict":  model.state_dict(),
            "version":           LONG_MODEL_VERSION,
            "seq_len":           seq_len,
            "pooling":           "attention",
            "input_features":    LONG_INPUT_FEATURES,
            "feat_dim":          SPECTRAL_FEAT_DIM,
            "d_model":           D_MODEL,
            "d_state":           D_STATE,
            "patch_size":        patch_size,
            "patch_stride":      patch_stride,
            "attention_heads":   attention_heads,   # GH-37: multi-head attn pooling (1 = single-head)
            # v2.0 additions
            "patch_deg_enc":     patch_size > 1,   # PatchDegradationEncoder active
            "film_depth":        2,                 # 2-layer FiLM MLP
            "loss":              "smooth_l1_beta0.02",
            "weighted_loss":     weighted_loss,
            "scheduler":         "cosine_warmrestarts",
            "cosine_t0":         cosine_t0,
            "scheduler_warmup":  "cosine_warmrestarts",   # GH-38 (was reduce_lr_on_plateau)
            "warmup_cosine_t0":  warmup_cosine_t0 if warmup_cosine_t0 > 0 else stage_epochs,
            "optimizer":         "adamw",
            "weight_decay":      weight_decay,
            "dropout":           dropout,
            "jitter":            jitter,
            "swa":               final_weights.startswith("SWA"),
            "final_weights":     final_weights,
            "test_mae":          test_metrics["mae"],
            "test_rmse":         test_metrics["rmse"],
        },
        LONG_MAMBA_PATH,
    )
    logger.info(f"Saved long Mamba model -> {LONG_MAMBA_PATH}")
    logger.info("Long-sequence training complete.")


# ---------------------------------------------------------------------------
# RUL training (GH-13): cycle-level Mamba, target = remaining cycles to EOL
# ---------------------------------------------------------------------------

def load_rul_split(path: str) -> tuple[torch.Tensor, torch.Tensor]:
    data = torch.load(path, weights_only=False)
    if "y" not in data or "X" not in data:
        raise KeyError(f"'X'/'y' not found in {path}. Run scripts/preprocess_rul.py first.")
    return data["X"], data["y"]


def evaluate_seq(model: nn.Module, X: torch.Tensor, y: torch.Tensor, device: torch.device,
                 scale: float = RUL_SCALE, batch_size: int = VAL_BATCH_SIZE) -> dict:
    """Metrics for a cycle-sequence regressor whose output is normalised by `scale`
    (RUL_SCALE → cycles; 100 → SOH%). mae/rmse are in the target's native unit."""
    model.eval()
    preds = []
    loader = DataLoader(TensorDataset(X), batch_size=batch_size)
    with torch.no_grad():
        for (X_b,) in loader:
            preds.append(model(X_b.to(device)).cpu())
    pred = torch.cat(preds) * scale
    mae  = torch.mean(torch.abs(pred - y)).item()
    rmse = torch.sqrt(torch.mean((pred - y) ** 2)).item()
    loss = torch.mean(((pred / scale) - (y / scale)) ** 2).item()
    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "loss": loss}


def train_rul(data_dir: str, epochs: int, log_dir: str, pooling: str = "last") -> None:
    """Train the cycle-level RUL predictor. Target normalised by RUL_SCALE; metrics
    reported in CYCLES. Split by battery (train B0005/06/07; B0018 val/test)."""
    logger = setup_logger(log_dir)
    logger.info("=== RUL training (GH-13, cycle-level) ===")

    X_train, y_train = load_rul_split(os.path.join(data_dir, "train.pt"))
    X_val,   y_val   = load_rul_split(os.path.join(data_dir, "val.pt"))
    X_test,  y_test  = load_rul_split(os.path.join(data_dir, "test.pt"))
    logger.info(f"  Train {len(X_train)} | Val {len(X_val)} | Test {len(X_test)} | lookback={X_train.shape[1]} cycles")
    logger.info(f"  EOL=SOH<={EOL_SOH}% | RUL range train {y_train.min():.0f}..{y_train.max():.0f} cycles | scale={RUL_SCALE}")

    if X_train.shape[-1] != RUL_FEAT_DIM:
        raise ValueError(f"Feature dim {X_train.shape[-1]}, config expects {RUL_FEAT_DIM}.")

    device, use_amp, amp_scaler, _amp_ctx = _setup_device_amp(logger)

    loader_gen = torch.Generator()
    loader_gen.manual_seed(SEED)
    train_loader = DataLoader(
        TensorDataset(X_train, y_train),
        batch_size=BATCH_SIZE, shuffle=True,
        pin_memory=use_amp, num_workers=2, persistent_workers=True,
        generator=loader_gen, worker_init_fn=_seed_worker,
    )

    torch.manual_seed(SEED)
    model     = RULPredictor(feat_dim=RUL_FEAT_DIM, d_model=D_MODEL, d_state=D_STATE, pooling=pooling).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=5, min_lr=1e-6)
    criterion = nn.MSELoss()
    GRAD_CLIP = 1.0
    n_params  = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"RULPredictor — {n_params:,} trainable params | pooling={pooling}")
    logger.info(f"Config: lr={LR}, batch={BATCH_SIZE}, epochs={epochs}, patience={PATIENCE}")

    best_val_loss = float("inf")
    patience_counter = 0
    best_state = None

    logger.info(f"{'Epoch':>6}  {'TrainLoss':>10}  {'ValLoss':>10}  {'ValMAE(cyc)':>11}  {'ValRMSE(cyc)':>12}")
    logger.info("-" * 60)
    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        for X_batch, y_batch in train_loader:
            optimizer.zero_grad(set_to_none=True)
            with _amp_ctx():
                pred = model(X_batch.to(device))
                loss = criterion(pred, (y_batch / RUL_SCALE).to(device))
            amp_scaler.scale(loss).backward()
            amp_scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            amp_scaler.step(optimizer)
            amp_scaler.update()
            train_loss += loss.item() * len(X_batch)
        train_loss /= len(X_train)

        val_metrics = evaluate_seq(model, X_val, y_val, device)
        val_loss    = val_metrics["loss"]
        logger.debug(f"{epoch:>6}  {train_loss:>10.6f}  {val_loss:>10.6f}  {val_metrics['mae']:>11.4f}  {val_metrics['rmse']:>12.4f}")
        if epoch % 10 == 0:
            logger.info(f"{epoch:>6}  {train_loss:>10.6f}  {val_loss:>10.6f}  {val_metrics['mae']:>11.4f}  {val_metrics['rmse']:>12.4f}")
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

    if best_state is not None:
        model.load_state_dict(best_state)
    test_metrics = evaluate_seq(model, X_test, y_test, device)
    logger.info("-" * 60)
    logger.info(f"Test MAE : {test_metrics['mae']:.4f} cycles")
    logger.info(f"Test RMSE: {test_metrics['rmse']:.4f} cycles")

    os.makedirs(os.path.dirname(RUL_MAMBA_PATH), exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "version":          RUL_MODEL_VERSION,
            "lookback":         X_train.shape[1],
            "feat_dim":         RUL_FEAT_DIM,
            "rul_scale":        RUL_SCALE,
            "eol_soh":          EOL_SOH,
            "pooling":          pooling,
            "d_model":          D_MODEL,
            "d_state":          D_STATE,
            "test_mae_cycles":  test_metrics["mae"],
            "test_rmse_cycles": test_metrics["rmse"],
        },
        RUL_MAMBA_PATH,
    )
    logger.info(f"Saved RUL model -> {RUL_MAMBA_PATH}")
    logger.info("RUL training complete.")


def _lobo(by_battery_path: str, epochs: int, log_dir: str, scale: float, unit: str,
          title: str, pooling: str = "last", val_frac: float = 0.15,
          holdouts: list[str] | None = None) -> None:
    """Generic leave-one-battery-out evaluation for a cycle-sequence regressor.

    For each held-out battery: train on the others, test on the WHOLE held-out
    battery. Feature StandardScaler is fit per fold on train batteries only (no
    leakage). `scale` normalises the target (RUL_SCALE→cycles, 100→SOH%); `unit`
    labels the metrics. Reports per-fold + macro-avg. Used by RUL and forecasting."""
    from sklearn.preprocessing import StandardScaler

    logger = setup_logger(log_dir)
    logger.info(f"=== {title} (GH-13, leave-one-battery-out) ===")
    blob = torch.load(by_battery_path, weights_only=False)
    batteries = blob["batteries"]
    ids = list(batteries.keys())
    fold_ids = ids if holdouts is None else [h for h in holdouts if h in batteries]
    logger.info(f"Pool: {len(ids)} batteries | held-out folds: {fold_ids} | lookback={blob.get('lookback')} | scale={scale} | unit={unit}")

    device, use_amp, amp_scaler, _amp_ctx = _setup_device_amp(logger)
    rng = np.random.RandomState(SEED)
    GRAD_CLIP = 1.0
    results = []

    for held in fold_ids:
        train_ids = [b for b in ids if b != held]
        Xtr = torch.cat([batteries[b]["X"] for b in train_ids], dim=0).numpy()
        ytr = torch.cat([batteries[b]["y"] for b in train_ids], dim=0).numpy()
        Xte = batteries[held]["X"].numpy()
        yte = batteries[held]["y"].numpy()
        if len(Xte) == 0 or len(Xtr) == 0:
            logger.warning(f"[hold {held}] empty fold (train {len(Xtr)} test {len(Xte)}) — skipped")
            continue

        # Per-fold feature scaler — fit on TRAIN batteries only
        nf = Xtr.shape[-1]
        sc = StandardScaler().fit(Xtr.reshape(-1, nf))
        def _scale(X):
            return sc.transform(X.reshape(-1, nf)).reshape(X.shape).astype(np.float32)
        Xtr_s, Xte_s = _scale(Xtr), _scale(Xte)

        # Carve val from train pool for early stopping
        n = len(Xtr_s)
        idx = rng.permutation(n)
        n_val = max(1, int(n * val_frac))
        val_idx, tr_idx = idx[:n_val], idx[n_val:]
        Xt = torch.tensor(Xtr_s[tr_idx]); yt = torch.tensor(ytr[tr_idx])
        Xv = torch.tensor(Xtr_s[val_idx]); yv = torch.tensor(ytr[val_idx])
        Xe = torch.tensor(Xte_s);          ye = torch.tensor(yte)

        gen = torch.Generator(); gen.manual_seed(SEED)
        loader = DataLoader(
            TensorDataset(Xt, yt), batch_size=BATCH_SIZE, shuffle=True,
            pin_memory=use_amp, num_workers=2, persistent_workers=True,
            generator=gen, worker_init_fn=_seed_worker,
        )
        torch.manual_seed(SEED)
        model = RULPredictor(feat_dim=nf, d_model=D_MODEL, d_state=D_STATE, pooling=pooling).to(device)
        opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-5)
        sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, mode="min", factor=0.5, patience=5, min_lr=1e-6)
        crit = nn.MSELoss()

        best, best_state, pc = float("inf"), None, 0
        for _ in range(1, epochs + 1):
            model.train()
            for Xb, yb in loader:
                opt.zero_grad(set_to_none=True)
                with _amp_ctx():
                    loss = crit(model(Xb.to(device)), (yb / scale).to(device))
                amp_scaler.scale(loss).backward()
                amp_scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
                amp_scaler.step(opt); amp_scaler.update()
            vm = evaluate_seq(model, Xv, yv, device, scale=scale)
            sched.step(vm["loss"])
            if vm["loss"] < best:
                best, best_state, pc = vm["loss"], {k: v.clone() for k, v in model.state_dict().items()}, 0
            else:
                pc += 1
            if pc >= PATIENCE:
                break
        if best_state is not None:
            model.load_state_dict(best_state)

        tm = evaluate_seq(model, Xe, ye, device, scale=scale)
        logger.info(
            f"[hold {held}] train {len(Xt)} val {len(Xv)} test {len(Xe)} "
            f"(target {yte.min():.1f}..{yte.max():.1f}) -> MAE {tm['mae']:.3f} | RMSE {tm['rmse']:.3f} {unit}"
        )
        results.append((held, tm["mae"], tm["rmse"]))

    if results:
        maes  = [r[1] for r in results]
        rmses = [r[2] for r in results]
        logger.info("-" * 60)
        logger.info(f"LOBO macro-avg over {len(results)} folds: "
                    f"MAE {np.mean(maes):.3f} ± {np.std(maes):.3f} | RMSE {np.mean(rmses):.3f} {unit}")
    logger.info("LOBO evaluation complete.")


def train_rul_lobo(data_dir: str, epochs: int, log_dir: str, pooling: str = "last") -> None:
    _lobo(os.path.join(data_dir, "by_battery.pt"), epochs, log_dir,
          scale=RUL_SCALE, unit="cycles", title="RUL", pooling=pooling)


def train_forecast_lobo(data_dir: str, epochs: int, log_dir: str, pooling: str = "last",
                        holdouts: list[str] | None = None) -> None:
    _lobo(os.path.join(data_dir, "by_battery_forecast.pt"), epochs, log_dir,
          scale=100.0, unit="%SOH", title="SOH-forecast", pooling=pooling, holdouts=holdouts)


def train_forecast_delta(data_dir: str, epochs: int, log_dir: str, pooling: str = "last",
                         holdouts: list[str] | None = None, val_frac: float = 0.15,
                         scale: float = 50.0) -> None:
    """SOH-forecasting via DELTA: predict (future SOH - last known SOH), anchored on
    the lookback's last SOH. Deltas are small + on a common scale across batteries,
    so adding batteries of different SOH regimes is safe (raw absolute → 42% disaster).
    Reports reconstructed absolute SOH MAE + the persistence baseline (predict no change)."""
    from sklearn.preprocessing import StandardScaler

    logger = setup_logger(log_dir)
    logger.info("=== SOH-forecast DELTA (GH-13, anchor=last SOH, multi-battery) ===")
    blob = torch.load(os.path.join(data_dir, "by_battery_forecast.pt"), weights_only=False)
    batteries = blob["batteries"]
    if "anchor" not in next(iter(batteries.values())):
        raise KeyError("by_battery_forecast.pt has no 'anchor' — rerun scripts/preprocess_forecast.py.")
    ids = list(batteries.keys())
    fold_ids = ids if holdouts is None else [h for h in holdouts if h in batteries]
    logger.info(f"Pool: {len(ids)} batteries | folds: {fold_ids} | lookback={blob.get('lookback')} | horizon=+{blob.get('horizon')} | delta-scale={scale}")

    device, use_amp, amp_scaler, _amp_ctx = _setup_device_amp(logger)
    rng = np.random.RandomState(SEED)
    GRAD_CLIP = 1.0
    results = []

    for held in fold_ids:
        train_ids = [b for b in ids if b != held]
        Xtr = torch.cat([batteries[b]["X"] for b in train_ids]).numpy()
        ytr = torch.cat([batteries[b]["y"] for b in train_ids]).numpy()
        atr = torch.cat([batteries[b]["anchor"] for b in train_ids]).numpy()
        Xte = batteries[held]["X"].numpy()
        yte = batteries[held]["y"].numpy()
        ate = batteries[held]["anchor"].numpy()
        if len(Xte) == 0 or len(Xtr) == 0:
            logger.warning(f"[hold {held}] empty fold — skipped"); continue

        dtr = ytr - atr  # delta target

        nf = Xtr.shape[-1]
        sc = StandardScaler().fit(Xtr.reshape(-1, nf))
        def _scale(X): return sc.transform(X.reshape(-1, nf)).reshape(X.shape).astype(np.float32)
        Xtr_s, Xte_s = _scale(Xtr), _scale(Xte)

        n = len(Xtr_s); idx = rng.permutation(n); nv = max(1, int(n * val_frac))
        vi, ti = idx[:nv], idx[nv:]
        Xt = torch.tensor(Xtr_s[ti]); dt = torch.tensor(dtr[ti])
        Xv = torch.tensor(Xtr_s[vi]); dv = torch.tensor(dtr[vi])

        gen = torch.Generator(); gen.manual_seed(SEED)
        loader = DataLoader(
            TensorDataset(Xt, dt), batch_size=BATCH_SIZE, shuffle=True,
            pin_memory=use_amp, num_workers=2, persistent_workers=True,
            generator=gen, worker_init_fn=_seed_worker,
        )
        torch.manual_seed(SEED)
        model = RULPredictor(feat_dim=nf, d_model=D_MODEL, d_state=D_STATE, pooling=pooling).to(device)
        opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-5)
        sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, mode="min", factor=0.5, patience=5, min_lr=1e-6)
        crit = nn.MSELoss()

        best, best_state, pc = float("inf"), None, 0
        for _ in range(1, epochs + 1):
            model.train()
            for Xb, db in loader:
                opt.zero_grad(set_to_none=True)
                with _amp_ctx():
                    loss = crit(model(Xb.to(device)), (db / scale).to(device))
                amp_scaler.scale(loss).backward()
                amp_scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
                amp_scaler.step(opt); amp_scaler.update()
            model.eval()
            with torch.no_grad():
                pv = (model(Xv.to(device)).cpu() * scale)
            vloss = torch.mean(((pv - dv) / scale) ** 2).item()
            sched.step(vloss)
            if vloss < best:
                best, best_state, pc = vloss, {k: v.clone() for k, v in model.state_dict().items()}, 0
            else:
                pc += 1
            if pc >= PATIENCE:
                break
        if best_state is not None:
            model.load_state_dict(best_state)

        model.eval()
        with torch.no_grad():
            pred_delta = (model(torch.tensor(Xte_s).to(device)).cpu() * scale).numpy()
        pred_abs = ate + pred_delta
        mae  = float(np.mean(np.abs(pred_abs - yte)))
        rmse = float(np.sqrt(np.mean((pred_abs - yte) ** 2)))
        pers = float(np.mean(np.abs(ate - yte)))  # persistence: predict no change
        verdict = "BEATS persistence" if mae < pers else "loses to persistence"
        logger.info(
            f"[hold {held}] train {len(Xt)} test {len(Xte_s)} -> "
            f"DELTA-model MAE {mae:.3f} RMSE {rmse:.3f} | persistence MAE {pers:.3f} %SOH  [{verdict}]"
        )
        results.append((held, mae, rmse, pers))

    if results:
        logger.info("-" * 60)
        logger.info(f"DELTA macro-avg: model MAE {np.mean([r[1] for r in results]):.3f} | "
                    f"persistence MAE {np.mean([r[3] for r in results]):.3f} %SOH")
    logger.info("DELTA forecast complete.")


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
    parser.add_argument("--rul", action="store_true",
                        help="Train cycle-level RUL predictor (GH-13)")
    parser.add_argument("--lobo", action="store_true",
                        help="RUL leave-one-battery-out evaluation (GH-13)")
    parser.add_argument("--forecast", action="store_true",
                        help="SOH-forecasting leave-one-battery-out (GH-13)")
    parser.add_argument("--holdout", default=None,
                        help="Comma list of held-out test batteries (default: all folds)")
    parser.add_argument("--delta", action="store_true",
                        help="Forecast via DELTA (anchor=last SOH) — safe multi-battery (GH-13)")
    parser.add_argument("--pooling", default="last", choices=["last", "attention"],
                        help="Pooling for RUL model")
    parser.add_argument("--accum-steps",  type=int, default=4)
    parser.add_argument("--micro-batch",  type=int, default=8)
    parser.add_argument("--stage-epochs", type=int, default=3)
    parser.add_argument("--final-epochs", type=int, default=50)
    parser.add_argument("--eval-batch",   type=int, default=16,
                        help="Eval batch for long-seq — small to avoid OOM at L=4096")
    parser.add_argument("--compile", action="store_true",
                        help="torch.compile the model (~30-50%% speedup on GPU, PyTorch 2.x)")
    parser.add_argument("--benchmark", action="store_true",
                        help="cuDNN benchmark mode — faster conv autotuning, non-deterministic")
    parser.add_argument("--num-workers", type=int, default=2,
                        help="DataLoader workers (default 2; use 4 on Kaggle P100/T4)")
    parser.add_argument("--official-mamba", action="store_true",
                        help="Use official mamba_ssm CUDA backend (3-5x faster, Kaggle/Colab GPU only). "
                             "Falls back to pure-PyTorch if mamba_ssm not installed.")
    parser.add_argument("--patch-size",   type=int, default=LONG_PATCH_SIZE,
                        help=f"Patch size for long-seq input compression (default {LONG_PATCH_SIZE}; "
                             "L=4096 → 256 tokens at P=16; use 1 to disable patching)")
    parser.add_argument("--patch-stride", type=int, default=LONG_PATCH_STRIDE,
                        help=f"Patch stride (default {LONG_PATCH_STRIDE} = non-overlapping; "
                             "use 8 for P16S8 overlapping as in PatchTST/MambaDecomp)")
    # v2.0 training improvements
    parser.add_argument("--weighted-loss", action="store_true",
                        help="Upweight near-EOL samples (SOH < 80%%) in SmoothL1 loss "
                             "(scale controlled by --eol-weight-scale)")
    parser.add_argument("--eol-weight-scale", type=float, default=2.0,
                        help="Near-EOL loss multiplier for --weighted-loss (default 2.0; "
                             "test stability before going above 3.0)")
    parser.add_argument("--cosine-t0", type=int, default=COSINE_T0,
                        help=f"T_0 for CosineAnnealingWarmRestarts in the final training stage "
                             f"(default {COSINE_T0}; must be < final_epochs for at least one restart. "
                             f"Set == final_epochs for a single long anneal with no restart race)")
    parser.add_argument("--weight-decay", type=float, default=1e-5,
                        help="AdamW weight decay for the --long path (default 1e-5; "
                             "try 3e-4 for stronger regularization against cross-battery overfit)")
    parser.add_argument("--dropout", type=float, default=0.2,
                        help="Dropout for the long-seq model (default 0.2; try 0.3 to reduce overfit)")
    parser.add_argument("--jitter", type=float, default=0.0,
                        help="Train-time Gaussian input-noise std on scaled sequences "
                             "(default 0.0=off; try 0.0075 ~0.75%% of [0,1] range for cell-to-cell robustness)")
    parser.add_argument("--swa", action="store_true",
                        help="Stochastic Weight Averaging: average weights over the final stage's "
                             "tail epochs (Izmailov 2018). Kept only if it beats the best checkpoint on val. "
                             "Needs the final stage to run long (use --cosine-t0 == --final-epochs so it doesn't early-stop).")
    parser.add_argument("--swa-start-frac", type=float, default=0.75,
                        help="Start SWA averaging at this fraction of --final-epochs (default 0.75 = last 25%%)")
    parser.add_argument("--attention-heads", type=int, default=1,
                        help="GH-37: multi-head attention pooling for long-seq (default 1 = single-head; "
                             "try 4 — d_model must be divisible by it). Only affects pooling='attention'.")
    parser.add_argument("--warmup-cosine-t0", type=int, default=0,
                        help="GH-38: T_0 for CosineAnnealingWarmRestarts in the WARMUP stages "
                             "(default 0 = use --stage-epochs so LR restarts at each stage boundary).")
    args = parser.parse_args()
    if args.forecast:
        holdouts = args.holdout.split(",") if args.holdout else None
        fc_dir = args.data_dir or "data/processed_forecast"
        if args.delta:
            train_forecast_delta(fc_dir, args.epochs, args.log_dir, pooling=args.pooling, holdouts=holdouts)
        else:
            train_forecast_lobo(fc_dir, args.epochs, args.log_dir, pooling=args.pooling, holdouts=holdouts)
    elif args.lobo:
        train_rul_lobo(args.data_dir or "data/processed_rul", args.epochs, args.log_dir, pooling=args.pooling)
    elif args.rul:
        train_rul(args.data_dir or "data/processed_rul", args.epochs, args.log_dir, pooling=args.pooling)
    elif args.long:
        data_dir = args.data_dir or "data/processed_long"
        train_long(
            data_dir, args.log_dir,
            accum_steps=args.accum_steps, micro_batch=args.micro_batch,
            stage_epochs=args.stage_epochs, final_epochs=args.final_epochs,
            eval_batch=args.eval_batch, num_workers=args.num_workers,
            compile_model=args.compile, benchmark=args.benchmark,
            official_mamba=args.official_mamba,
            patch_size=args.patch_size, patch_stride=args.patch_stride,
            weighted_loss=args.weighted_loss,
            eol_weight_scale=args.eol_weight_scale,
            cosine_t0=args.cosine_t0,
            weight_decay=args.weight_decay,
            dropout=args.dropout,
            jitter=args.jitter,
            swa=args.swa,
            swa_start_frac=args.swa_start_frac,
            attention_heads=args.attention_heads,
            warmup_cosine_t0=args.warmup_cosine_t0,
        )
    else:
        train(args.data_dir or "data/processed", args.epochs, args.log_dir)


if __name__ == "__main__":
    main()
