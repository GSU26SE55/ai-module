"""Per-temperature / per-cell SOH error breakdown for the LFP artifact set.

Why this exists: a single aggregate `test_mae` hides the failure mode that matters
here. Measured on v2.1-lfp, holding one discharge window fixed and only changing
ambient temperature moved SOH by 7.6 points (10 °C -> 95.05%, 40 °C -> 87.47%) and
flipped the label Normal -> Degrading at 35 °C — a temperature that is well inside
the training distribution. An aggregate number cannot show that, because the test
split is dominated by one temperature group.

Reads the provenance columns written by scripts/preprocess_snl.py (cell_idx /
temp_mean_c / cycle_idx) and cuts MAE/RMSE by (temperature bin x SOH band) and by
cell. Bins holding fewer than --min-count windows are printed but marked as too
thin to conclude from — with the current split most of the grid IS too thin, and
seeing that is the point.

Usage (Kaggle, after training):
    python scripts/eval_soh_by_temp.py --data-dir data/processed_lfp --split test

Does not run on a local checkout: data/raw/ holds NASA only, SNL/Severson live on
Kaggle.
"""

import argparse
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.train import evaluate  # noqa: E402
from src.models.soh_predictor import MambaSOHPredictor  # noqa: E402

SOH_BANDS = [
    ("<80", -np.inf, 80.0),
    ("80-85", 80.0, 85.0),
    ("85-90", 85.0, 90.0),
    ("90-95", 90.0, 95.0),
    (">=95", 95.0, np.inf),
]

META_KEYS = ("cell_idx", "cell_ids", "temp_mean_c")


def load_split_with_meta(path: str) -> dict:
    """Load a .pt split and fail loudly if it predates the provenance columns."""
    data = torch.load(path, weights_only=False)
    missing = [k for k in META_KEYS if k not in data]
    if missing:
        raise SystemExit(
            f"{path} is missing {missing} — it was written before the provenance\n"
            f"columns existed, so error cannot be cut by temperature or cell.\n"
            f"Re-run scripts/preprocess_snl.py to regenerate the splits (no retrain\n"
            f"needed: this script scores an existing checkpoint)."
        )
    return data


def load_model(weights: str, device: torch.device) -> MambaSOHPredictor:
    ck = torch.load(weights, map_location="cpu", weights_only=False)
    model = MambaSOHPredictor(
        input_features=ck.get("input_features", 6),
        feat_dim=ck.get("feat_dim", 57),
        d_model=ck.get("d_model", 64),
        d_state=ck.get("d_state", 16),
    )
    model.load_state_dict(ck["model_state_dict"])
    print(f"Model {weights} | version={ck.get('version')} "
          f"| reported test_mae={ck.get('test_mae')} rmse={ck.get('test_rmse')}")
    return model.to(device).eval()


def _stats(err: np.ndarray) -> tuple[float, float]:
    return float(np.mean(np.abs(err))), float(np.sqrt(np.mean(err**2)))


def _row(label: str, err: np.ndarray, min_count: int, width: int) -> str:
    if len(err) == 0:
        return f"{label:>{width}} {'-':>9} {'-':>9} {0:>8}"
    mae, rmse = _stats(err)
    thin = "  <- qua it mau" if len(err) < min_count else ""
    return f"{label:>{width}} {mae:>9.3f} {rmse:>9.3f} {len(err):>8,}{thin}"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", default="data/processed_lfp")
    p.add_argument("--split", default="test", choices=["train", "val", "test"])
    p.add_argument("--weights", default="models/weights/soh_mamba_v2.1-lfp.pth")
    p.add_argument("--temp-bin", type=float, default=5.0, help="Width of a temperature bin, °C")
    p.add_argument("--min-count", type=int, default=100,
                   help="Below this many windows a bin is flagged as too thin to conclude from")
    args = p.parse_args()

    data = load_split_with_meta(os.path.join(args.data_dir, f"{args.split}.pt"))
    X, X_feat, y = data["X"], data["X_feat"], data["y"]
    temp = np.asarray(data["temp_mean_c"], dtype=np.float64)
    cell_idx = np.asarray(data["cell_idx"], dtype=np.int64)
    cell_ids = list(data["cell_ids"])

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_model(args.weights, device)

    res = evaluate(model, X, X_feat, y, device)
    pred = res["pred"].numpy().astype(np.float64)
    truth = y.numpy().astype(np.float64)
    err = pred - truth

    print(f"\nSplit '{args.split}': {len(err):,} windows | "
          f"nhiet do {temp.min():.1f}-{temp.max():.1f} °C | SOH {truth.min():.1f}-{truth.max():.1f}%")
    print(f"TONG: MAE {res['mae']:.4f}%  RMSE {res['rmse']:.4f}%")

    # --- per cell -----------------------------------------------------------
    # Truncate from the RIGHT: SNL ids carry the chamber temperature up front
    # ("SNL_18650_LFP_35C_..."), so cutting the head makes every cell look alike.
    w = min(38, max(12, max(len(c) for c in cell_ids)))
    print("\n== Theo cell (xep theo MAE giam dan) ==")
    print(f"{'cell':>{w}} {'MAE':>9} {'RMSE':>9} {'N':>8}")
    order = sorted(
        range(len(cell_ids)),
        key=lambda i: -_stats(err[cell_idx == i])[0] if (cell_idx == i).any() else 0.0,
    )
    for i in order:
        m = cell_idx == i
        name = cell_ids[i] if len(cell_ids[i]) <= w else cell_ids[i][: w - 1] + "…"
        print(_row(name, err[m], args.min_count, w),
              f"  ({temp[m].mean():.1f} °C)" if m.any() else "")

    # --- temperature x SOH grid --------------------------------------------
    lo = np.floor(temp.min() / args.temp_bin) * args.temp_bin
    hi = np.ceil(temp.max() / args.temp_bin) * args.temp_bin
    edges = np.arange(lo, hi + args.temp_bin, args.temp_bin)

    print(f"\n== Luoi (nhiet do x dai SOH) — bin {args.temp_bin:g} °C ==")
    header = f"{'temp °C':>14}" + "".join(f"{b[0]:>16}" for b in SOH_BANDS)
    print(header)
    for a, b in zip(edges[:-1], edges[1:]):
        tm = (temp >= a) & (temp < b)
        if not tm.any():
            continue
        cells = []
        for _, s_lo, s_hi in SOH_BANDS:
            m = tm & (truth >= s_lo) & (truth < s_hi)
            if not m.any():
                cells.append(f"{'-':>16}")
            else:
                mae, _ = _stats(err[m])
                mark = "!" if int(m.sum()) < args.min_count else " "
                cells.append(f"{mae:>10.2f}/{int(m.sum()):<4d}{mark}"[:16].rjust(16))
        print(f"{f'{a:.0f}-{b:.0f}':>14}" + "".join(cells))
    print("\n  o = MAE% / so cua so.  '!' = duoi --min-count, khong du mau de ket luan.")

    # --- bias by temperature ------------------------------------------------
    # Signed mean error, not MAE: a model that reads ambient temperature as a proxy
    # for age shows up as bias drifting with temperature, which |error| hides.
    print("\n== Bias co dau theo nhiet do (duong = doan CAO hon thuc te) ==")
    print(f"{'temp °C':>14} {'bias':>9} {'MAE':>9} {'N':>8}")
    for a, b in zip(edges[:-1], edges[1:]):
        m = (temp >= a) & (temp < b)
        if not m.any():
            continue
        mae, _ = _stats(err[m])
        thin = "  <- qua it mau" if int(m.sum()) < args.min_count else ""
        print(f"{f'{a:.0f}-{b:.0f}':>14} {err[m].mean():>+9.3f} {mae:>9.3f} {int(m.sum()):>8,}{thin}")


if __name__ == "__main__":
    main()
