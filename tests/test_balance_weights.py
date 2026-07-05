"""GH-88 — unit tests for _balance_band_weights (inverse temp x SOH-band frequency)."""

import torch

from src.core.config import BASE_FEATURES, INPUT_FEATURES, WINDOW_SIZE
from scripts.train import _balance_band_weights

TEMP_IDX = BASE_FEATURES.index("temperature")


def _make_x(temps: list[float]) -> torch.Tensor:
    """Windows whose scaled temperature channel is constant per sample."""
    x = torch.zeros(len(temps), WINDOW_SIZE, INPUT_FEATURES)
    for i, t in enumerate(temps):
        x[i, :, TEMP_IDX] = t
    return x


def test_uniform_data_gives_unit_weights():
    # single occupied bin → every weight exactly 1.0
    x = _make_x([0.5] * 8)
    y = torch.full((8,), 75.0)
    w = _balance_band_weights(x, y)
    assert torch.allclose(w, torch.ones(8))


def test_mean_weight_is_one_without_clipping():
    # 2 bins, mildly imbalanced (6 vs 2) — no clipping at default max 5.0
    x = _make_x([0.1] * 6 + [0.9] * 2)
    y = torch.cat([torch.full((6,), 55.0), torch.full((2,), 85.0)])
    w = _balance_band_weights(x, y)
    assert abs(w.mean().item() - 1.0) < 1e-6


def test_rare_bin_weighted_higher_than_common_bin():
    # mimic the real imbalance: dense mid-SOH warm mass vs rare cold high-SOH
    x = _make_x([0.6] * 90 + [0.05] * 10)
    y = torch.cat([torch.full((90,), 70.0), torch.full((10,), 82.0)])
    w = _balance_band_weights(x, y)
    assert w[-1] > w[0]
    # each occupied bin contributes equally: n_common * w_common == n_rare * w_rare
    assert abs(90 * w[0].item() - 10 * w[-1].item()) < 1e-4


def test_weights_clipped_at_max_weight():
    # 1 sample vs 99 → raw rare weight = 100/(2*1) = 50 → clipped to 5.0
    x = _make_x([0.6] * 99 + [0.05])
    y = torch.cat([torch.full((99,), 70.0), torch.full((1,), 82.0)])
    w = _balance_band_weights(x, y, max_weight=5.0)
    assert w.max().item() == 5.0


def test_weights_positive_and_finite():
    x = _make_x([0.0, 0.3, 0.5, 0.7, 1.0])
    y = torch.tensor([5.0, 40.0, 75.0, 82.0, 100.0])  # includes both clamp edges
    w = _balance_band_weights(x, y)
    assert torch.isfinite(w).all()
    assert (w > 0).all()
