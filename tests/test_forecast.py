"""Tests for the SOH-forecasting windowing (GH-13)."""

import numpy as np

from scripts.preprocess_forecast import make_forecast_windows


def test_forecast_window_target_is_future_soh():
    n, feat_dim, lookback, horizon = 12, 54, 3, 2
    feats = np.random.rand(n, feat_dim).astype(np.float32)
    sohs = np.arange(n, dtype=np.float32)  # soh[i] = i, easy to check
    X, y, anchor = make_forecast_windows(feats, sohs, lookback, horizon, stride=1)

    assert X.shape[1:] == (lookback, feat_dim)
    # First window: cycles [0,1,2], last=2, target = soh[2+2] = soh[4] = 4.0
    assert y[0] == 4.0
    # anchor = last known SOH = soh[2] = 2.0
    assert anchor[0] == 2.0
    # Count = n - lookback - horizon + 1 = 12 - 3 - 2 + 1 = 8
    assert len(X) == n - lookback - horizon + 1


def test_forecast_window_empty_when_too_short():
    feats = np.random.rand(4, 54).astype(np.float32)
    sohs = np.arange(4, dtype=np.float32)
    X, y, anchor = make_forecast_windows(feats, sohs, lookback=3, horizon=3, stride=1)
    assert X.shape == (0, 3, 54)
    assert len(y) == 0
    assert len(anchor) == 0
