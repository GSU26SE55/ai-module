"""
Preprocessing (SOH-forecasting, GH-13): NASA cleaned_dataset → cycle-level
sequences for forecasting SOH `horizon` cycles ahead.

Same cycle-axis representation as the RUL pipeline (1 token = 1 cycle's 54-dim
spectral+kurtosis vector), but the target is the FUTURE SOH instead of remaining
life. Far more data-efficient than RUL: every cycle is a valid target, not only
those before End-of-Life.

Builds per-battery UNSCALED windows → by_battery_forecast.pt; the LOBO trainer
fits a feature StandardScaler per fold (train batteries only).

Usage:
    python scripts/preprocess_forecast.py --data-dir data/raw/nasa/cleaned_dataset \
        --output-dir data/processed_forecast
"""

import argparse
import os
import random
import sys

import joblib
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.preprocess import TRAIN_IDS, VAL_IDS  # noqa: E402
from scripts.preprocess_rul import cycle_feature_series  # noqa: E402  (reused)


def available_batteries(data_dir: str) -> list[str]:
    """All battery IDs present in metadata.csv (full NASA set, not just the 4
    spec-locked ones). Used to expand the forecast experiment's training pool."""
    meta = pd.read_csv(os.path.join(data_dir, "metadata.csv"))
    return sorted(meta["battery_id"].unique())


def batteries_at_temp(data_dir: str, temp: float) -> list[str]:
    """Battery IDs whose discharge cycles run ONLY at the given ambient temperature.

    Lets us add SAME-condition data (no temperature domain shift) — the clean way
    to expand beyond the 4 spec batteries. NASA has ~11 batteries purely at 24°C
    (B0005/06/07/18, B0025-28, B0033/34/36), so adding them avoids the cross-temp
    shift that wrecked naive multi-battery training (5.46% MAE)."""
    meta = pd.read_csv(os.path.join(data_dir, "metadata.csv"))
    dis = meta[meta["type"] == "discharge"]
    ids = []
    for bid, sub in dis.groupby("battery_id"):
        temps = sub["ambient_temperature"].unique()
        if len(temps) == 1 and float(temps[0]) == float(temp):
            ids.append(bid)
    return sorted(ids)
from src.core.config import (  # noqa: E402
    FORECAST_HORIZON,
    FORECAST_LOOKBACK,
    FORECAST_STRIDE,
    SCALER_PATH,
)

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)


def make_forecast_windows(
    feats: np.ndarray,
    sohs: np.ndarray,
    lookback: int,
    horizon: int,
    stride: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Slide a lookback-cycle window; target = SOH `horizon` cycles after the last.

    X[i]      = feats[start : start+lookback]              (lookback, 54)
    y[i]      = sohs[start + lookback - 1 + horizon]       (future SOH %)
    anchor[i] = sohs[start + lookback - 1]                 (last known SOH %)

    The anchor enables DELTA prediction (target = y - anchor): deltas are small
    and on a common scale across batteries, so mixing batteries of different SOH
    regimes no longer poisons the model (raw absolute SOH does — see 42% result).
    Returns empty arrays if the series is shorter than lookback + horizon.
    """
    n = len(feats)
    Xs, ys, anchors = [], [], []
    for start in range(0, n - lookback - horizon + 1, stride):
        last = start + lookback - 1
        Xs.append(feats[start : start + lookback])
        ys.append(float(sohs[last + horizon]))
        anchors.append(float(sohs[last]))
    if not Xs:
        empty = np.empty((0,), dtype=np.float32)
        return np.empty((0, lookback, feats.shape[1]), dtype=np.float32), empty, empty
    return (
        np.array(Xs, dtype=np.float32),
        np.array(ys, dtype=np.float32),
        np.array(anchors, dtype=np.float32),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir",   default="data/raw/nasa/cleaned_dataset")
    parser.add_argument("--output-dir", default="data/processed_forecast")
    parser.add_argument("--lookback",   type=int, default=FORECAST_LOOKBACK)
    parser.add_argument("--horizon",    type=int, default=FORECAST_HORIZON)
    parser.add_argument("--stride",     type=int, default=FORECAST_STRIDE)
    parser.add_argument("--batteries",  default="spec",
                        help="'spec' = B0005/06/07/18 only | 'all' = full NASA set | comma list")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    print(f"Forecast lookback: {args.lookback} cycles | horizon: +{args.horizon} cycles | stride: {args.stride}")

    if not os.path.exists(SCALER_PATH):
        raise FileNotFoundError(f"MinMaxScaler not found at '{SCALER_PATH}'. Run scripts/preprocess.py first.")
    scaler = joblib.load(SCALER_PATH)["scaler"]
    print(f"Loaded MinMaxScaler <- {SCALER_PATH}")

    if args.batteries == "spec":
        bids = TRAIN_IDS + VAL_IDS
    elif args.batteries == "all":
        bids = available_batteries(args.data_dir)
    else:
        bids = args.batteries.split(",")
    print(f"Batteries ({args.batteries}): {len(bids)}")

    print("\nBuilding per-battery forecast windows...")
    by_bat = {}
    for bid in bids:
        try:
            feats, sohs = cycle_feature_series(args.data_dir, bid, scaler)
        except Exception as e:
            print(f"  {bid}: skipped ({e})")
            continue
        X, y, anchor = make_forecast_windows(feats, sohs, args.lookback, args.horizon, args.stride)
        if len(X) == 0:
            print(f"  {bid}: {len(feats)} cycles -> 0 windows (too short for lookback+horizon)")
            continue
        by_bat[bid] = {
            "X":      torch.tensor(X, dtype=torch.float32),
            "y":      torch.tensor(y, dtype=torch.float32),
            "anchor": torch.tensor(anchor, dtype=torch.float32),
        }
        print(f"  {bid}: {len(feats)} cycles -> {len(X)} windows | future SOH {y.min():.1f}..{y.max():.1f}%")

    torch.save(
        {"batteries": by_bat, "lookback": args.lookback, "horizon": args.horizon},
        os.path.join(args.output_dir, "by_battery_forecast.pt"),
    )
    print(f"\nSaved by_battery_forecast.pt  ({len(by_bat)} batteries)")
    print("Forecast preprocessing complete.")


if __name__ == "__main__":
    main()
