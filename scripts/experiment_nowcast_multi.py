"""Experiment (GH-13 follow-up): does adding batteries help NOWCASTING?

The "add batteries -> 42%" failure was for FORECASTING (future prediction).
Nowcasting (feature -> current SOH) is physics-based and may transfer across
batteries, so adding data could HELP. This script tests exactly that:

  Train window=30 SOH model on ALL usable batteries EXCEPT B0018, test on B0018,
  compare MAE to the 4-battery baseline (0.61%). Scalers are refit on the bigger
  train pool (off-condition batteries have different voltage/current ranges).

Saves NOTHING to production paths — pure measurement. Does not touch the
spec-locked production pipeline (scripts/preprocess.py).

Usage:
    python scripts/experiment_nowcast_multi.py [--epochs 80]
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

from scripts.preprocess import load_cycles, cycles_to_windows  # noqa: E402
from scripts.preprocess_forecast import available_batteries, batteries_at_temp  # noqa: E402
from scripts.train import setup_logger  # noqa: E402  (logs to logs/training/)
from src.core.config import D_MODEL, D_STATE, SPECTRAL_FEAT_DIM  # noqa: E402
from src.models.soh_predictor import MambaSOHPredictor  # noqa: E402

SEED = 42
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)


def collect(data_dir, bids):
    cycles = []
    for bid in bids:
        try:
            cycles.extend(load_cycles(data_dir, bid))
        except Exception as e:
            print(f"  {bid}: skipped ({e})")
    return cycles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/raw/nasa/cleaned_dataset")
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--test-id", default="B0018")
    ap.add_argument("--official-mamba", action="store_true",
                    help="Use official CUDA mamba_ssm (Kaggle/Colab GPU only; same accuracy)")
    ap.add_argument("--temp", type=float, default=None,
                    help="restrict pool to batteries at this ambient temperature (e.g. 24) — same-condition, no domain shift")
    args = ap.parse_args()
    logger = setup_logger("logs/training")
    logger.info("=== Multi-battery NOWCASTING experiment (GH-13 follow-up) ===")

    if args.temp is not None:
        all_ids = batteries_at_temp(args.data_dir, args.temp)
        logger.info(f"Same-condition filter: ambient_temperature = {args.temp}°C -> {len(all_ids)} batteries")
    else:
        all_ids = available_batteries(args.data_dir)
    train_ids = [b for b in all_ids if b != args.test_id]
    logger.info(f"Train pool: {len(train_ids)} batteries (all except {args.test_id})")

    train_cycles = collect(args.data_dir, train_ids)
    test_cycles  = collect(args.data_dir, [args.test_id])
    logger.info(f"Train cycles: {len(train_cycles)} | Test cycles: {len(test_cycles)}")

    # Refit MinMax on the bigger train pool (raw timesteps)
    raw = np.concatenate([c for c, _ in train_cycles], axis=0)
    minmax = MinMaxScaler().fit(raw)

    # Windows (window=30) + cycle-level 54-dim features
    Xtr, Ftr_raw, ytr = cycles_to_windows(train_cycles, minmax)
    Xte, Fte_raw, yte = cycles_to_windows(test_cycles, minmax)
    feat_scaler = StandardScaler().fit(Ftr_raw)
    Ftr = feat_scaler.transform(Ftr_raw).astype(np.float32)
    Fte = feat_scaler.transform(Fte_raw).astype(np.float32)
    logger.info(f"Train windows: {len(Xtr)} | Test windows: {len(Xte)}")

    Xtr = torch.tensor(Xtr); Ftr = torch.tensor(Ftr); ytr = torch.tensor(ytr)
    Xte = torch.tensor(Xte); Fte = torch.tensor(Fte); yte = torch.tensor(yte)

    # Carve 15% val for early stopping
    rng = np.random.RandomState(SEED)
    idx = rng.permutation(len(Xtr)); nv = int(len(Xtr) * 0.15)
    vi, ti = idx[:nv], idx[nv:]

    loader = DataLoader(TensorDataset(Xtr[ti], Ftr[ti], ytr[ti]), batch_size=32, shuffle=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(SEED)
    model = MambaSOHPredictor(input_features=Xtr.shape[-1], feat_dim=SPECTRAL_FEAT_DIM,
                              d_model=D_MODEL, d_state=D_STATE,
                              use_official_mamba=args.official_mamba).to(device)
    logger.info(f"Mamba backend: {'official CUDA mamba_ssm' if args.official_mamba else 'pure-PyTorch'}")
    opt = torch.optim.Adam(model.parameters(), lr=5e-4, weight_decay=1e-5)
    crit = nn.MSELoss()

    def evaluate(X, F, y):
        model.eval()
        with torch.no_grad():
            pred = model(X.to(device), F.to(device)).cpu() * 100.0
        return float(torch.mean(torch.abs(pred - y))), float(torch.sqrt(torch.mean((pred - y) ** 2)))

    logger.info(f"Device: {device} | model params: {sum(p.numel() for p in model.parameters()):,}")
    logger.info(f"{'Epoch':>6}  {'ValMAE%':>8}")
    best, best_state, pc = float("inf"), None, 0
    for ep in range(1, args.epochs + 1):
        model.train()
        for Xb, Fb, yb in loader:
            opt.zero_grad(set_to_none=True)
            loss = crit(model(Xb.to(device), Fb.to(device)), (yb / 100.0).to(device))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        vmae, _ = evaluate(Xtr[vi], Ftr[vi], ytr[vi])
        logger.info(f"{ep:>6}  {vmae:>8.4f}")
        if vmae < best:
            best, best_state, pc = vmae, {k: v.clone() for k, v in model.state_dict().items()}, 0
        else:
            pc += 1
        if pc >= 15:
            logger.info(f"Early stop at epoch {ep}"); break

    model.load_state_dict(best_state)
    mae, rmse = evaluate(Xte, Fte, yte)
    logger.info("=" * 55)
    logger.info(f"MULTI-BATTERY NOWCASTING — test {args.test_id}")
    logger.info(f"  Train pool: {len(train_ids)} batteries, {len(Xtr)} windows")
    logger.info(f"  Test MAE : {mae:.4f}%   (4-battery baseline: 0.61%)")
    logger.info(f"  Test RMSE: {rmse:.4f}%   (4-battery baseline: 0.73%)")
    verdict = "HELPS (<=0.61)" if mae <= 0.61 else ("comparable" if mae <= 1.0 else "HURTS (>1.0)")
    logger.info(f"  Verdict: adding data {verdict}")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()
