"""Tests for the cycle-level RUL pipeline (GH-13)."""

import numpy as np
import torch

from scripts.preprocess_rul import find_eol, make_rul_windows
from src.models.rul_predictor import RULPredictor

# --- find_eol -------------------------------------------------------------

def test_find_eol_first_crossing():
    sohs = np.array([95.0, 90.0, 85.0, 80.0, 78.0, 70.0], dtype=np.float32)
    assert find_eol(sohs, 80.0) == 3  # first cycle SOH <= 80


def test_find_eol_fallback_last_when_never_crosses():
    sohs = np.array([95.0, 92.0, 90.0], dtype=np.float32)
    assert find_eol(sohs, 80.0) == 2  # never crosses -> last index


# --- make_rul_windows -----------------------------------------------------

def test_rul_window_labels_and_shape():
    n, feat_dim, lookback = 10, 57, 3
    feats = np.random.rand(n, feat_dim).astype(np.float32)
    # SOH crosses 80 at index 6
    sohs = np.linspace(95, 75, n).astype(np.float32)
    eol = find_eol(sohs, 80.0)
    X, y, last_idx, eol_ret = make_rul_windows(feats, sohs, lookback, stride=1, eol_soh=80.0)

    assert eol_ret == eol
    assert X.shape[1:] == (lookback, feat_dim)
    # No window's last cycle is past EOL
    assert (last_idx <= eol).all()
    # RUL = eol - last_idx, and the window ending exactly at EOL has RUL 0
    assert np.allclose(y, eol - last_idx)
    assert y.min() == 0.0


def test_rul_window_empty_when_too_short():
    feats = np.random.rand(2, 57).astype(np.float32)
    sohs = np.array([90.0, 70.0], dtype=np.float32)
    X, y, last_idx, _ = make_rul_windows(feats, sohs, lookback=5, stride=1, eol_soh=80.0)
    assert X.shape == (0, 5, 57)
    assert len(y) == 0


# --- RULPredictor ---------------------------------------------------------

def test_rul_predictor_output_shape():
    model = RULPredictor(feat_dim=57, d_model=64, d_state=16)
    x = torch.randn(4, 30, 57)
    out = model(x)
    assert out.shape == (4,)


def test_rul_predictor_attention_pooling():
    model = RULPredictor(feat_dim=57, pooling="attention")
    x = torch.randn(2, 30, 57)
    out = model(x)
    assert out.shape == (2,)


def test_rul_predictor_invalid_pooling_raises():
    import pytest
    with pytest.raises(ValueError):
        RULPredictor(pooling="mean")


def test_rul_predictor_grad_flows():
    model = RULPredictor(feat_dim=57)
    x = torch.randn(3, 30, 57)
    out = model(x).sum()
    out.backward()
    assert model.input_proj.weight.grad is not None
