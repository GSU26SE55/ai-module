"""Compare 2 Mambas on identical NASA SOH data (fair, parameter-aware).

  Mamba A = MambaSOHPredictor (current: Mamba + FiLM stats)
  Mamba B = HybridMambaSOH    (paper-style: Decomp + Patch + CNN + Mamba + stats)

Both trained on the SAME split (train B0005/06/07, test B0018), same (x, x_feat)
inputs, same optimizer/epochs. Reports MAE/RMSE/#params/latency side by side.
Pure-PyTorch (Windows + Kaggle GPU). Run on Kaggle for speed.

Usage:
    python scripts/compare_models.py --epochs 80
"""

import argparse, os, random, sys, time
import numpy as np, torch, torch.nn as nn
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.preprocess import load_cycles, cycles_to_windows, TRAIN_IDS, VAL_IDS  # noqa: E402
from scripts.train import setup_logger  # noqa: E402
from src.core.config import D_MODEL, D_STATE, SPECTRAL_FEAT_DIM  # noqa: E402
from src.models.soh_predictor import MambaSOHPredictor  # noqa: E402
from src.models.hybrid_mamba_soh import HybridMambaSOH  # noqa: E402

SEED = 42
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED); torch.cuda.manual_seed_all(SEED)


def build_data(data_dir):
    tr = [c for b in TRAIN_IDS for c in load_cycles(data_dir, b)]
    te = [c for b in VAL_IDS for c in load_cycles(data_dir, b)]
    mm = MinMaxScaler().fit(np.concatenate([c for c, _ in tr], axis=0))
    Xtr, Ftr_raw, ytr = cycles_to_windows(tr, mm)
    Xte, Fte_raw, yte = cycles_to_windows(te, mm)
    fs = StandardScaler().fit(Ftr_raw)
    Ftr = fs.transform(Ftr_raw).astype(np.float32)
    Fte = fs.transform(Fte_raw).astype(np.float32)
    t = lambda a: torch.tensor(a)
    return (t(Xtr), t(Ftr), t(ytr)), (t(Xte), t(Fte), t(yte))


def train_eval(model, train, test, epochs, device, logger, name):
    Xtr, Ftr, ytr = train; Xte, Fte, yte = test
    rng = np.random.RandomState(SEED); idx = rng.permutation(len(Xtr)); nv = int(len(Xtr) * 0.15)
    vi, ti = idx[:nv], idx[nv:]
    gen = torch.Generator(); gen.manual_seed(SEED)
    loader = DataLoader(TensorDataset(Xtr[ti], Ftr[ti], ytr[ti]), batch_size=32, shuffle=True, generator=gen)
    model = model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=5e-4, weight_decay=1e-5)
    crit = nn.MSELoss()

    def ev(X, F, y):
        model.eval()
        with torch.no_grad():
            p = model(X.to(device), F.to(device)).cpu() * 100.0
        return float(torch.mean(torch.abs(p - y))), float(torch.sqrt(torch.mean((p - y) ** 2)))

    best, best_state, pc = float("inf"), None, 0
    for ep in range(1, epochs + 1):
        model.train()
        for Xb, Fb, yb in loader:
            opt.zero_grad(set_to_none=True)
            loss = crit(model(Xb.to(device), Fb.to(device)), (yb / 100.0).to(device))
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        vmae, _ = ev(Xtr[vi], Ftr[vi], ytr[vi])
        if vmae < best: best, best_state, pc = vmae, {k: v.clone() for k, v in model.state_dict().items()}, 0
        else: pc += 1
        if pc >= 15: break
    model.load_state_dict(best_state)
    mae, rmse = ev(Xte, Fte, yte)

    # latency: single-sample inference, avg of 100 runs
    model.eval(); xs = Xte[:1].to(device); fs = Fte[:1].to(device)
    with torch.no_grad():
        for _ in range(10): model(xs, fs)  # warmup
        if device.type == "cuda": torch.cuda.synchronize()
        t0 = time.perf_counter()
        for _ in range(100): model(xs, fs)
        if device.type == "cuda": torch.cuda.synchronize()
        lat = (time.perf_counter() - t0) / 100 * 1000  # ms
    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"[{name}] params={n_params:,} | Test MAE={mae:.4f}% RMSE={rmse:.4f}% | latency={lat:.3f} ms")
    return {"name": name, "params": n_params, "mae": mae, "rmse": rmse, "latency_ms": lat}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/raw/nasa/cleaned_dataset")
    ap.add_argument("--epochs", type=int, default=80)
    args = ap.parse_args()
    logger = setup_logger("logs/training")
    logger.info("=== COMPARE: Mamba A (current) vs Mamba B (paper HybridMamba) ===")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Device: {device}")

    train, test = build_data(args.data_dir)
    logger.info(f"Train windows: {len(train[0])} | Test windows (B0018): {len(test[0])}")

    torch.manual_seed(SEED)
    A = MambaSOHPredictor(input_features=train[0].shape[-1], feat_dim=SPECTRAL_FEAT_DIM, d_model=D_MODEL, d_state=D_STATE)
    torch.manual_seed(SEED)
    B = HybridMambaSOH(input_features=train[0].shape[-1], feat_dim=SPECTRAL_FEAT_DIM, d_model=D_MODEL, d_state=D_STATE)

    rA = train_eval(A, train, test, args.epochs, device, logger, "Mamba-A (current)")
    rB = train_eval(B, train, test, args.epochs, device, logger, "Mamba-B (paper-style)")

    logger.info("=" * 64)
    logger.info(f"{'Model':<22}{'Params':>10}{'MAE%':>9}{'RMSE%':>9}{'Latency(ms)':>13}")
    for r in (rA, rB):
        logger.info(f"{r['name']:<22}{r['params']:>10,}{r['mae']:>9.4f}{r['rmse']:>9.4f}{r['latency_ms']:>13.3f}")
    logger.info("=" * 64)


if __name__ == "__main__":
    main()
