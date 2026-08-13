"""Experiment (GH-13 follow-up): credible NOWCASTING via leave-one-battery-out.

Addresses the valid concern that MAE on a single test battery (B0018) is not a
trustworthy estimate. Trains window=30 SOH nowcasting on ALL batteries except
one, tests on the whole held-out battery, rotates over every battery, and
reports MAE/RMSE as **mean ± std across folds** — a defensible robustness number.

Per fold: refit MinMax (raw) + StandardScaler (features) on the train batteries
only (no leakage). Saves nothing to production paths.

Designed for GPU (Kaggle/Colab) — on CPU it is slow. Logs to logs/training/.

Usage:
    python scripts/experiment_nowcast_lobo.py --epochs 60 [--min-cycles 60] [--folds B0005,B0018]
"""

import argparse
import os
import random
import sys

import numpy as np
import torch
import torch.nn as nn
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.preprocess import cycles_to_windows, load_cycles  # noqa: E402
from scripts.preprocess_forecast import available_batteries, batteries_at_temp  # noqa: E402
from scripts.train import setup_logger  # noqa: E402
from src.core.config import D_MODEL, D_STATE, SPECTRAL_FEAT_DIM  # noqa: E402
from src.models.soh_predictor import MambaSOHPredictor  # noqa: E402

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)


def resolve_device(logger):
    """cuda nếu GPU được PyTorch build hiện tại hỗ trợ; ngược lại cảnh báo rõ + CPU.

    Kaggle image PyTorch mới chỉ build kernel sm_70+ — chọn accelerator P100 (sm_60)
    thì is_available() vẫn True nhưng kernel đầu tiên sẽ crash. Đổi sang GPU T4 x2.
    """
    if not torch.cuda.is_available():
        return torch.device("cpu")
    major, minor = torch.cuda.get_device_capability(0)
    archs = [int(a.split("_")[1]) for a in torch.cuda.get_arch_list() if a.startswith("sm_")]
    if archs and major * 10 + minor < min(archs):
        logger.warning(
            f"GPU {torch.cuda.get_device_name(0)} (sm_{major}{minor}) khong duoc PyTorch build nay ho tro "
            f"(min sm_{min(archs)}) — fallback CPU. Tren Kaggle: Settings -> Accelerator -> GPU T4 x2."
        )
        return torch.device("cpu")
    return torch.device("cuda")


def load_cycles_safe(data_dir, bid, min_cycles):
    try:
        cyc = load_cycles(data_dir, bid)
    except Exception:
        return None
    return cyc if len(cyc) >= min_cycles else None


def run_fold(held, train_cycles, test_cycles, epochs, device, logger, official_mamba=False):
    """Train on train_cycles, eval on held-out test_cycles. Returns (mae, rmse, n_test)."""
    raw = np.concatenate([c for c, _, _ in train_cycles], axis=0)
    minmax = MinMaxScaler().fit(raw)
    Xtr, Ftr_raw, ytr = cycles_to_windows(train_cycles, minmax)
    Xte, Fte_raw, yte = cycles_to_windows(test_cycles, minmax)
    if len(Xte) == 0 or len(Xtr) == 0:
        return None
    feat_scaler = StandardScaler().fit(Ftr_raw)
    Ftr = torch.tensor(feat_scaler.transform(Ftr_raw).astype(np.float32))
    Fte = torch.tensor(feat_scaler.transform(Fte_raw).astype(np.float32))
    Xtr, ytr = torch.tensor(Xtr), torch.tensor(ytr)
    Xte, yte = torch.tensor(Xte), torch.tensor(yte)

    rng = np.random.RandomState(SEED)
    idx = rng.permutation(len(Xtr))
    nv = max(1, int(len(Xtr) * 0.15))
    vi, ti = idx[:nv], idx[nv:]
    gen = torch.Generator()
    gen.manual_seed(SEED)
    loader = DataLoader(
        TensorDataset(Xtr[ti], Ftr[ti], ytr[ti]), batch_size=32, shuffle=True, generator=gen
    )

    torch.manual_seed(SEED)
    model = MambaSOHPredictor(
        input_features=Xtr.shape[-1],
        feat_dim=SPECTRAL_FEAT_DIM,
        d_model=D_MODEL,
        d_state=D_STATE,
        use_official_mamba=official_mamba,
    ).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=5e-4, weight_decay=1e-5)
    crit = nn.MSELoss()

    def ev(X, F, y):
        model.eval()
        with torch.no_grad():
            pred = model(X.to(device), F.to(device)).cpu() * 100.0
        return float(torch.mean(torch.abs(pred - y))), float(
            torch.sqrt(torch.mean((pred - y) ** 2))
        )

    best, best_state, pc = float("inf"), None, 0
    for _ in range(1, epochs + 1):
        model.train()
        for Xb, Fb, yb in loader:
            opt.zero_grad(set_to_none=True)
            loss = crit(model(Xb.to(device), Fb.to(device)), (yb / 100.0).to(device))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        vmae, _ = ev(Xtr[vi], Ftr[vi], ytr[vi])
        if vmae < best:
            best, best_state, pc = vmae, {k: v.clone() for k, v in model.state_dict().items()}, 0
        else:
            pc += 1
        if pc >= 15:
            break
    model.load_state_dict(best_state)
    mae, rmse = ev(Xte, Fte, yte)
    return mae, rmse, len(Xte)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/raw/nasa/cleaned_dataset")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--min-cycles", type=int, default=60, help="skip batteries with fewer cycles")
    ap.add_argument(
        "--temp",
        type=float,
        default=None,
        help="restrict to batteries at this ambient temperature (e.g. 24) — same-condition, no domain shift",
    )
    ap.add_argument(
        "--pool",
        default=None,
        help="comma list = EXACT battery pool (train+test). Use for clean same-campaign LOBO, e.g. B0005,B0006,B0007,B0018",
    )
    ap.add_argument(
        "--folds", default=None, help="comma list of held-out batteries (default: all eligible)"
    )
    ap.add_argument(
        "--official-mamba",
        action="store_true",
        help="Use official CUDA mamba_ssm (Kaggle/Colab GPU only; same accuracy)",
    )
    args = ap.parse_args()

    logger = setup_logger("logs/training")
    logger.info("=== NOWCASTING leave-one-battery-out (GH-13 follow-up) ===")
    device = resolve_device(logger)
    logger.info(f"Device: {device}")

    if args.pool is not None:
        all_ids = args.pool.split(",")
        logger.info(f"Exact pool: {all_ids}")
    elif args.temp is not None:
        all_ids = batteries_at_temp(args.data_dir, args.temp)
        logger.info(
            f"Same-condition filter: ambient_temperature = {args.temp}°C -> {len(all_ids)} batteries"
        )
    else:
        all_ids = available_batteries(args.data_dir)
    cycles_by = {}
    for bid in all_ids:
        cyc = load_cycles_safe(args.data_dir, bid, args.min_cycles)
        if cyc is not None:
            cycles_by[bid] = cyc
    eligible = list(cycles_by.keys())
    logger.info(f"Eligible batteries (>= {args.min_cycles} cycles): {len(eligible)} -> {eligible}")

    fold_ids = args.folds.split(",") if args.folds else eligible
    results = []
    for held in fold_ids:
        if held not in cycles_by:
            logger.warning(f"[hold {held}] not eligible — skipped")
            continue
        train_cycles = [c for b in cycles_by if b != held for c in cycles_by[b]]
        out = run_fold(
            held,
            train_cycles,
            cycles_by[held],
            args.epochs,
            device,
            logger,
            official_mamba=args.official_mamba,
        )
        if out is None:
            logger.warning(f"[hold {held}] empty fold — skipped")
            continue
        mae, rmse, ntest = out
        logger.info(f"[hold {held}] test {ntest} windows -> MAE {mae:.4f}% | RMSE {rmse:.4f}%")
        results.append((held, mae, rmse))

    if results:
        maes = np.array([r[1] for r in results])
        rmses = np.array([r[2] for r in results])
        logger.info("=" * 60)
        logger.info(f"LOBO over {len(results)} batteries:")
        logger.info(
            f"  MAE  = {maes.mean():.4f}% ± {maes.std():.4f}%  (min {maes.min():.3f}, max {maes.max():.3f})"
        )
        logger.info(f"  RMSE = {rmses.mean():.4f}% ± {rmses.std():.4f}%")
        logger.info("  (4-battery single-fold baseline: MAE 0.61%)")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()
