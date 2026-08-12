"""Tests for MC Dropout confidence (GH-13)."""

import torch

from src.core.config import INPUT_FEATURES
from src.models.soh_predictor import MambaSOHPredictor
from src.services.confidence import predict_with_confidence


def _model():
    torch.manual_seed(42)
    return MambaSOHPredictor(input_features=INPUT_FEATURES, feat_dim=57, d_model=64, d_state=16)


def test_confidence_shapes_and_range():
    m = _model()
    x = torch.randn(4, 30, INPUT_FEATURES)
    f = torch.randn(4, 57)
    out = predict_with_confidence(m, x, f, n_samples=10)
    for k in ("soh", "std", "confidence", "lower", "upper"):
        assert out[k].shape == (4,)
    assert torch.all(out["confidence"] >= 0) and torch.all(out["confidence"] <= 1)
    assert torch.all(out["std"] >= 0)
    assert torch.all(out["upper"] >= out["lower"])


def test_mc_dropout_produces_variance():
    # With dropout active across passes, std should be > 0 (stochastic).
    m = _model()
    x = torch.randn(2, 30, INPUT_FEATURES)
    f = torch.randn(2, 57)
    out = predict_with_confidence(m, x, f, n_samples=20)
    assert torch.any(out["std"] > 0)


def test_restores_eval_mode():
    m = _model()
    predict_with_confidence(m, torch.randn(1, 30, INPUT_FEATURES), torch.randn(1, 57), n_samples=5)
    assert not m.dropout.training  # dropout turned back off


def test_requires_min_samples():
    import pytest

    m = _model()
    with pytest.raises(ValueError):
        predict_with_confidence(
            m, torch.randn(1, 30, INPUT_FEATURES), torch.randn(1, 57), n_samples=1
        )
