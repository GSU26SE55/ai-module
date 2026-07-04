"""Unit tests for scripts/eval_anomaly.py labeling + threshold selection (GH-70)."""

import numpy as np

from scripts.eval_anomaly import (
    EOL_SOH,
    eol_labels,
    evaluate,
    expand_to_windows,
    local_fade_rate,
    pick_threshold,
    rate_labels,
    smooth_soh,
)


def test_smooth_soh_removes_single_spike() -> None:
    soh = np.array([100.0, 99.0, 60.0, 97.0, 96.0])  # one-cycle sensor spike
    smoothed = smooth_soh(soh)
    assert smoothed[2] > 90.0  # median filter suppresses the spike
    assert len(smoothed) == len(soh)


def test_local_fade_rate_linear_degradation() -> None:
    soh = 100.0 - 0.5 * np.arange(20)  # constant 0.5 %SOH/cycle fade
    rates = local_fade_rate(soh)
    assert np.allclose(rates, 0.5, atol=1e-6)


def test_rate_labels_flag_only_rapid_regime() -> None:
    # 10 flat cycles (rate 0) then 10 steep cycles (rate 2.0 %SOH/cycle)
    soh = np.concatenate([np.full(10, 100.0), 100.0 - 2.0 * np.arange(1, 11)])
    labels = rate_labels(soh, threshold=1.0)
    assert not labels[:8].any()  # flat regime stays normal
    # Last cycle excluded: the shrinking median window at the series edge
    # attenuates the measured rate to exactly threshold (1.0, not > 1.0).
    assert labels[12:-1].all()  # steep regime is anomalous


def test_eol_labels_threshold() -> None:
    soh = np.array([EOL_SOH + 0.1, EOL_SOH, EOL_SOH - 0.1])
    assert eol_labels(soh).tolist() == [False, False, True]


def test_expand_to_windows_repeats_per_cycle() -> None:
    per_cycle = np.array([True, False])
    n_win = np.array([2, 3])
    assert expand_to_windows(per_cycle, n_win).tolist() == [
        True,
        True,
        False,
        False,
        False,
    ]


def test_pick_threshold_finds_perfect_separation() -> None:
    # Anomalous windows score below -0.5, normal ones above 0 — separable
    scores = np.concatenate([np.linspace(-1.0, -0.5, 20), np.linspace(0.0, 0.5, 80)])
    y = np.concatenate([np.ones(20, dtype=bool), np.zeros(80, dtype=bool)])
    thr, f1 = pick_threshold(scores, y)
    assert -0.5 <= thr < 0.0
    assert f1 == 1.0


def test_evaluate_handles_empty_predictions() -> None:
    y_true = np.array([True, False, True])
    y_pred = np.zeros(3, dtype=bool)
    metrics = evaluate(y_true, y_pred)
    assert metrics == {"precision": 0.0, "recall": 0.0, "f1": 0.0}
