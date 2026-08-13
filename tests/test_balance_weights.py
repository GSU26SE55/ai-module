"""GH-88 — unit tests for _balance_band_weights (inverse temp x SOH-band frequency)."""

import pytest
import torch

from scripts.train import _balance_band_weights
from src.core.config import BASE_FEATURES, INPUT_FEATURES, WINDOW_SIZE

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


# --------------------------------------------------------------------------
# LFP v2.1: four chamber temperatures instead of NASA's three
# --------------------------------------------------------------------------
# The merged Severson+SNL train set has clusters at 15/25/30/35 °C (plus
# Severson self-heating up to ~40 °C), and the MinMaxScaler fits temperature
# over roughly [0, 44.6] °C. n_temp_bins is applied to the SCALED channel, so
# the bin width in °C is range/n. With the default 3 bins that is ~14.9 °C —
# wider than the 5 °C spacing between clusters — so 30 °C (140 Severson cells)
# and 35 °C (6 SNL cells) land in ONE bin and the rare group is never
# up-weighted, which is the entire purpose of passing --balance-bands here.

_T_RANGE_C = 44.56  # measured scaler range on the real merged set (2026-08-11)


def _scaled(celsius: float) -> float:
    return celsius / _T_RANGE_C


def _temp_bin(celsius: float, n_bins: int) -> int:
    return min(int(_scaled(celsius) * n_bins), n_bins - 1)


def test_default_three_bins_merge_the_30C_and_35C_clusters():
    assert _temp_bin(30.0, 3) == _temp_bin(35.0, 3)


def test_twelve_bins_separate_every_real_cluster():
    clusters = [15.0, 25.0, 30.0, 35.0, 40.0]
    bins = [_temp_bin(c, 12) for c in clusters]
    assert len(set(bins)) == len(clusters), f"clusters collided: {list(zip(clusters, bins))}"


def test_rare_warm_cluster_is_upweighted_only_with_enough_bins():
    """End-to-end on the weights, not just the bin arithmetic.

    Dense 30 °C mass vs a rare 35 °C group at the same SOH. With 3 bins they
    share a bin and get identical weights; with 12 bins the rare one is lifted.
    """
    dense, rare = 200, 10
    x = _make_x([_scaled(30.0)] * dense + [_scaled(35.0)] * rare)
    y = torch.full((dense + rare,), 88.0)

    w3 = _balance_band_weights(x, y, n_temp_bins=3)
    assert w3[-1].item() == pytest.approx(w3[0].item()), "3 bins must NOT separate them"

    w12 = _balance_band_weights(x, y, n_temp_bins=12)
    assert w12[-1] > w12[0] * 5, "12 bins must lift the rare 35 °C group"


def test_more_bins_still_respect_the_weight_cap():
    """Finer bins mean sparser bins; the cap is what stops one cell dominating."""
    x = _make_x([_scaled(30.0)] * 500 + [_scaled(15.0)])
    y = torch.cat([torch.full((500,), 88.0), torch.full((1,), 88.0)])
    w = _balance_band_weights(x, y, n_temp_bins=12, max_weight=5.0)
    assert w.max().item() == 5.0
    assert torch.isfinite(w).all()
