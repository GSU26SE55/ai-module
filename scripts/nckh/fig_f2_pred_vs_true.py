"""NCKH Figure F2 — predicted vs true SOH on B0048 (held-out test), long
model v2.2, with MC Dropout uncertainty band (10 samples, same pattern as
production src/services/inference.py — dropout ON via train(), batched
forward, restore eval() after).

Data: data/processed_long/test.pt — X/X_feat already scaler-transformed by
scripts/preprocess_long.py (no re-scaling needed here). Windows appear in
chronological blocks sharing one SOH label per cycle (311 windows -> 60
unique cycles for B0048); grouped by first-appearance order for the x-axis.

Usage: python scripts/nckh/fig_f2_pred_vs_true.py
Output: logs/nckh/figures/f2_pred_vs_true_b0048.{pdf,svg}
"""

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.models.soh_predictor import MambaSOHPredictor  # noqa: E402

CKPT_PATH = "models/weights/soh_mamba_long_v2.2.pth"
TEST_PT = "data/processed_long/test.pt"
OUT_DIR = "logs/nckh/figures"
MC_RUNS = 10  # matches production src/services/inference.py (GH-63)
SEED = 42

FONT = "Arial"
COLOR_TRUE = "#0b0b0b"
COLOR_PRED = "#2a78d6"   # slot 1 blue
COLOR_BAND = "#2a78d6"
COLOR_GRID = "#e1e0d9"
COLOR_AXIS = "#c3c2b7"
COLOR_MUTED_TEXT = "#52514e"


def load_model():
    ckpt = torch.load(CKPT_PATH, map_location="cpu", weights_only=False)
    meta = {k: v for k, v in ckpt.items() if k != "model_state_dict"}
    model = MambaSOHPredictor(
        input_features=int(meta["input_features"]),
        d_model=int(meta["d_model"]),
        d_state=int(meta["d_state"]),
        dropout=0.3,  # must match training-time dropout for MC sampling to be meaningful
        feat_dim=int(meta["feat_dim"]),
        pooling=meta["pooling"],
        patch_size=int(meta["patch_size"]),
        patch_stride=int(meta["patch_stride"]),
        attention_heads=int(meta["attention_heads"]),
    )
    state_dict = {
        k.removeprefix("_orig_mod."): v for k, v in ckpt["model_state_dict"].items()
    }  # strip torch.compile wrapper prefix
    model.load_state_dict(state_dict)
    model.eval()
    return model, meta


def mc_predict(model, X, X_feat, mc_runs=MC_RUNS, window_batch=4):
    """MC Dropout, same pattern as src/services/inference.py, chunked over
    windows (window_batch at a time x mc_runs) to fit L=4096 selective-scan
    activations in CPU memory — full 311-window batch OOMs at this seq_len."""
    torch.manual_seed(SEED)
    model.train()
    n = X.shape[0]
    out = np.zeros((n, mc_runs), dtype=np.float32)
    try:
        with torch.no_grad():
            for start in range(0, n, window_batch):
                end = min(start + window_batch, n)
                Xc, Fc = X[start:end], X_feat[start:end]
                b = end - start
                xb = Xc.unsqueeze(1).repeat(1, mc_runs, 1, 1).reshape(-1, Xc.shape[1], Xc.shape[2])
                xfb = Fc.unsqueeze(1).repeat(1, mc_runs, 1).reshape(-1, Fc.shape[1])
                preds = (model(xb, xfb) * 100).reshape(b, mc_runs)
                out[start:end] = preds.numpy()
                print(f"  MC predict {end}/{n}", end="\r")
    finally:
        model.eval()
    print()
    return out  # (n_windows, mc_runs)


def group_by_cycle(y: np.ndarray, mean_pred: np.ndarray, std_pred: np.ndarray):
    """Windows appear in chronological blocks sharing one SOH label per cycle.
    Group consecutive identical-y windows -> one point per cycle, in order of
    first appearance (verified against load_cycles ordering)."""
    cycles = []
    i = 0
    n = len(y)
    while i < n:
        j = i
        while j < n and np.isclose(y[j], y[i]):
            j += 1
        cycles.append({
            "true": y[i],
            "pred_mean": mean_pred[i:j].mean(),
            "pred_std": std_pred[i:j].mean(),  # avg MC-std across sub-windows of this cycle
        })
        i = j
    return cycles


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    model, meta = load_model()
    print("Loaded checkpoint meta:", {k: meta[k] for k in ("version", "test_mae", "test_rmse")})

    d = torch.load(TEST_PT, weights_only=False)
    X, X_feat, y = d["X"], d["X_feat"], d["y"].numpy()

    mc_preds = mc_predict(model, X, X_feat)
    mean_pred = mc_preds.mean(axis=1)
    std_pred = mc_preds.std(axis=1)

    cycles = group_by_cycle(y, mean_pred, std_pred)
    xs = np.arange(len(cycles))
    true_soh = np.array([c["true"] for c in cycles])
    pred_soh = np.array([c["pred_mean"] for c in cycles])
    pred_std = np.array([c["pred_std"] for c in cycles])

    mae = float(np.mean(np.abs(pred_soh - true_soh)))
    rmse = float(np.sqrt(np.mean((pred_soh - true_soh) ** 2)))
    print(f"Recomputed on this script's grouping: MAE {mae:.4f}%  RMSE {rmse:.4f}%  "
          f"(checkpoint self-reported: {meta['test_mae']}/{meta['test_rmse']})")

    plt.rcParams.update({
        "font.family": FONT,
        "font.size": 9,
        "axes.edgecolor": COLOR_AXIS,
        "axes.labelcolor": "#0b0b0b",
        "text.color": "#0b0b0b",
        "xtick.color": COLOR_MUTED_TEXT,
        "ytick.color": COLOR_MUTED_TEXT,
        "axes.grid": True,
        "grid.color": COLOR_GRID,
        "grid.linewidth": 0.6,
        "svg.fonttype": "none",
    })

    fig, ax = plt.subplots(figsize=(7.0, 3.2), dpi=300)
    ax.set_axisbelow(True)

    ax.fill_between(xs, pred_soh - pred_std, pred_soh + pred_std,
                     color=COLOR_BAND, alpha=0.18, lw=0,
                     label="MC Dropout ±1 std (n=10)")
    ax.plot(xs, true_soh, color=COLOR_TRUE, lw=1.8, label="Ground-truth SOH")
    ax.plot(xs, pred_soh, color=COLOR_PRED, lw=1.6, ls="--", label="Predicted SOH")
    # No EOL=80% reference line here: this test-window range of B0048 stays
    # below ~71%, well clear of the threshold — the line would sit at/above
    # the top edge and add no information (unlike F5, which spans full
    # battery lifetimes and crosses 80% for several batteries).

    ax.set_xlabel("Discharge cycle (B0048)")
    ax.set_ylabel("SOH (%)")
    # Headline number (Table 1) = checkpoint's own deterministic eval; this
    # script's recomputed MAE/RMSE differ slightly (MC-dropout sampling +
    # per-cycle grouping) — title shows the official headline for
    # consistency with the rest of the paper, not the just-recomputed value.
    ax.set_title(
        f"Predicted vs. true SOH on held-out B0048 — long model "
        f"(MAE {meta['test_mae']:.2f}%, RMSE {meta['test_rmse']:.2f}%)",
        fontsize=10, loc="left",
    )
    ax.legend(frameon=False, fontsize=8, loc="upper right")

    fig.tight_layout()
    for ext in ("pdf", "svg", "png"):
        path = os.path.join(OUT_DIR, f"f2_pred_vs_true_b0048.{ext}")
        fig.savefig(path, bbox_inches="tight")
        print("Saved", path)


if __name__ == "__main__":
    main()
