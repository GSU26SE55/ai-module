import numpy as np
import torch

from src.core.config import INPUT_FEATURES, SPECTRAL_FEAT_DIM, WINDOW_SIZE
from src.models.anomaly_detector import (
    classify_anomaly,
    classify_anomaly_status,
    classify_health_stage,
    classify_health_stage_probabilistic,
    compute_degradation_metrics,
    compute_risk_profile,
    estimate_rul,
    generate_warnings,
    get_recommended_action,
    temperature_domain_distance,
)
from src.models.soh_predictor import MambaBlock, MambaSOHPredictor


def _make_inputs(batch: int = 1):
    x      = torch.randn(batch, WINDOW_SIZE, INPUT_FEATURES)
    x_feat = torch.randn(batch, SPECTRAL_FEAT_DIM)
    return x, x_feat


def _make_model() -> MambaSOHPredictor:
    return MambaSOHPredictor(
        input_features=INPUT_FEATURES,
        feat_dim=SPECTRAL_FEAT_DIM,
        d_model=8,
        d_state=4,
    )


class TestAttentionPooling:
    """GH-10 P3: attention pooling for long sequences (default 'last' unchanged)."""

    def _attn_model(self):
        return MambaSOHPredictor(
            input_features=INPUT_FEATURES, feat_dim=SPECTRAL_FEAT_DIM,
            d_model=8, d_state=4, pooling="attention",
        )

    def test_invalid_pooling_raises(self):
        import pytest
        with pytest.raises(ValueError, match="pooling must be"):
            MambaSOHPredictor(pooling="mean")

    def test_attention_output_shape_long_seq(self):
        model = self._attn_model()
        model.eval()
        x      = torch.randn(4, 64, INPUT_FEATURES)   # L=64 > window, exercises pooling
        x_feat = torch.randn(4, SPECTRAL_FEAT_DIM)
        with torch.no_grad():
            out = model(x, x_feat)
        assert out.shape == (4,)

    def test_attention_weights_grad_flows(self):
        model = self._attn_model()
        x      = torch.randn(2, 48, INPUT_FEATURES)
        x_feat = torch.randn(2, SPECTRAL_FEAT_DIM)
        model(x, x_feat).sum().backward()
        assert model.attn_score.weight.grad is not None

    def test_attention_differs_from_last_token(self):
        """Attention pool should generally not equal the last-token output."""
        torch.manual_seed(0)
        attn = self._attn_model()
        attn.eval()
        last = MambaSOHPredictor(
            input_features=INPUT_FEATURES, feat_dim=SPECTRAL_FEAT_DIM,
            d_model=8, d_state=4, pooling="last",
        )
        last.load_state_dict(attn.state_dict(), strict=False)  # share shared weights
        last.eval()
        x      = torch.randn(1, 64, INPUT_FEATURES)
        x_feat = torch.randn(1, SPECTRAL_FEAT_DIM)
        with torch.no_grad():
            assert not torch.allclose(attn(x, x_feat), last(x, x_feat), atol=1e-4)


class TestMambaSOHPredictor:
    def test_output_shape_single(self):
        model = _make_model()
        model.eval()
        x, x_feat = _make_inputs(1)
        with torch.no_grad():
            out = model(x, x_feat)
        assert out.shape == (1,), f"Expected (1,), got {out.shape}"

    def test_output_shape_batch(self):
        model = _make_model()
        model.eval()
        x, x_feat = _make_inputs(8)
        with torch.no_grad():
            out = model(x, x_feat)
        assert out.shape == (8,), f"Expected (8,), got {out.shape}"

    def test_output_is_float(self):
        model = _make_model()
        model.eval()
        x, x_feat = _make_inputs(2)
        with torch.no_grad():
            out = model(x, x_feat)
        assert out.dtype == torch.float32

    def test_gradients_flow(self):
        model = _make_model()
        x, x_feat = _make_inputs(2)
        out = model(x, x_feat)
        loss = out.sum()
        loss.backward()
        grads = [p.grad for p in model.parameters() if p.grad is not None]
        assert len(grads) > 0, "No gradients computed"

    def test_film_modulation_changes_output(self):
        """Different x_feat should produce different SOH predictions."""
        model = _make_model()
        model.eval()
        x = torch.randn(1, WINDOW_SIZE, INPUT_FEATURES)
        feat_a = torch.zeros(1, SPECTRAL_FEAT_DIM)
        feat_b = torch.ones(1, SPECTRAL_FEAT_DIM)
        with torch.no_grad():
            out_a = model(x, feat_a)
            out_b = model(x, feat_b)
        assert not torch.allclose(out_a, out_b), "FiLM conditioning has no effect"


def test_streaming_scan_matches_full_sequential_scan():
    """Chunked scan (L>256 path, used for warmup L=512 up to L=4096) must equal a
    naive fp32 sequential recurrence. L=512 covers the GH-10 threshold change
    (256) so warmup L=512 takes the chunked path; L=600 covers a non-multiple of
    CHUNK."""
    torch.manual_seed(0)
    block = MambaBlock(d_model=4, d_state=3, expand=2)
    block.eval()

    for seq_len in (512, 600):   # both > 256 → chunked path
        x = torch.randn(2, seq_len, block.d_inner)
        with torch.no_grad():
            actual = block._selective_scan(x)    # chunked scan

            # Manual fp32 sequential reference — same recurrence the L<=256 branch runs
            xf = x.float()
            x_dbl = block.x_proj(xf)
            dt_raw, b_proj, c_proj = x_dbl.split([1, block.d_state, block.d_state], dim=-1)
            dt = torch.nn.functional.softplus(block.dt_proj(dt_raw))
            a  = -torch.exp(block.A_log.float())
            dA  = torch.exp(dt.unsqueeze(-1) * a)
            dBx = dt.unsqueeze(-1) * b_proj.unsqueeze(2) * xf.unsqueeze(-1)
            B, L, d_inner = xf.shape
            h = torch.zeros(B, d_inner, block.d_state)
            ys = []
            for t in range(L):
                h = dA[:, t] * h + dBx[:, t]
                ys.append((h * c_proj[:, t].unsqueeze(1)).sum(-1))
            expected = torch.stack(ys, dim=1) + xf * block.D

        assert torch.allclose(actual, expected, atol=1e-5, rtol=1e-4), f"mismatch at L={seq_len}"


def test_selective_scan_preserves_input_dtype():
    """GH-9: scan returns output in the input dtype (fp32 internally, cast back)."""
    torch.manual_seed(0)
    block = MambaBlock(d_model=4, d_state=3, expand=2)
    block.eval()
    x = torch.randn(2, 30, block.d_inner)
    with torch.no_grad():
        out = block._selective_scan(x)
    assert out.dtype == x.dtype


def test_selective_scan_runs_fp32_under_autocast():
    """GH-9: the recurrence is shielded from AMP — output under autocast must
    match the plain fp32 output, proving the scan never runs in reduced precision.
    This is the root-cause fix for MAE inflating on GPU (AMP) vs CPU (fp32)."""
    torch.manual_seed(0)
    block = MambaBlock(d_model=4, d_state=3, expand=2)
    block.eval()
    x = torch.randn(2, 30, block.d_inner)   # fp32 input
    with torch.no_grad():
        out_plain = block._selective_scan(x)
        with torch.autocast(device_type="cpu", dtype=torch.bfloat16):
            out_autocast = block._selective_scan(x)
    assert torch.allclose(out_plain, out_autocast, atol=1e-6)


def test_model_forward_reproducible_same_seed():
    """GH-9: two models built under the same seed produce identical forward output
    — unit-level guard for the train-script reproducibility fix."""
    def build():
        torch.manual_seed(123)
        return MambaSOHPredictor(
            input_features=INPUT_FEATURES, feat_dim=SPECTRAL_FEAT_DIM,
            d_model=8, d_state=4,
        ).eval()

    x      = torch.randn(4, WINDOW_SIZE, INPUT_FEATURES)
    x_feat = torch.randn(4, SPECTRAL_FEAT_DIM)
    with torch.no_grad():
        out_a = build()(x, x_feat)
        out_b = build()(x, x_feat)
    assert torch.equal(out_a, out_b)


class TestClassifyAnomaly:
    """SOH is the primary driver; IsolationForest score only affects SOH>=90 case."""

    def test_normal_high_soh_good_score(self):
        assert classify_anomaly(0.1, 95.0) == "Normal"
        assert classify_anomaly(-0.05, 92.0) == "Normal"

    def test_normal_boundary_soh_90(self):
        assert classify_anomaly(0.0, 90.0) == "Normal"

    def test_degrading_soh_range(self):
        assert classify_anomaly(0.5, 89.9) == "Degrading"
        assert classify_anomaly(0.5, 85.0) == "Degrading"
        assert classify_anomaly(0.5, 80.0) == "Degrading"

    def test_failed_soh_below_80(self):
        assert classify_anomaly(0.5, 79.9) == "Failed"
        assert classify_anomaly(0.5, 67.0) == "Failed"
        assert classify_anomaly(-0.5, 60.0) == "Failed"

    def test_sensor_anomaly_downgrades_normal(self):
        assert classify_anomaly(-0.2, 95.0) == "Degrading"
        assert classify_anomaly(-0.15, 90.5) == "Degrading"

    def test_sensor_anomaly_does_not_affect_failed(self):
        assert classify_anomaly(0.9, 70.0) == "Failed"


class TestClassifyAnomalyCausalRate:
    """GH-95: causal_rate escalates the base tier by one step when it exceeds
    RATE_THRESHOLD; None (cold start / missing battery_id) preserves pre-GH-95
    behavior exactly."""

    def test_none_preserves_prior_behavior(self):
        assert classify_anomaly(0.1, 95.0, causal_rate=None) == "Normal"
        assert classify_anomaly(0.5, 85.0, causal_rate=None) == "Degrading"
        assert classify_anomaly(0.5, 70.0, causal_rate=None) == "Failed"

    def test_below_threshold_does_not_escalate(self):
        from src.core.config import RATE_THRESHOLD

        assert classify_anomaly(0.1, 95.0, causal_rate=RATE_THRESHOLD - 0.01) == "Normal"

    def test_above_threshold_escalates_normal_to_degrading(self):
        from src.core.config import RATE_THRESHOLD

        assert (
            classify_anomaly(0.1, 95.0, causal_rate=RATE_THRESHOLD + 0.5) == "Degrading"
        )

    def test_above_threshold_escalates_degrading_to_failed(self):
        from src.core.config import RATE_THRESHOLD

        assert (
            classify_anomaly(0.5, 85.0, causal_rate=RATE_THRESHOLD + 0.5) == "Failed"
        )

    def test_above_threshold_failed_stays_failed(self):
        from src.core.config import RATE_THRESHOLD

        assert (
            classify_anomaly(0.5, 70.0, causal_rate=RATE_THRESHOLD + 0.5) == "Failed"
        )

    def test_exactly_at_threshold_does_not_escalate(self):
        from src.core.config import RATE_THRESHOLD

        # strict '>' — boundary itself is not anomalous
        assert classify_anomaly(0.1, 95.0, causal_rate=RATE_THRESHOLD) == "Normal"


class TestClassifyHealthStageProbabilistic:
    """GH-86: stage from the MC Dropout sample distribution, not the mean."""

    def test_clear_majority_healthy(self):
        result = classify_health_stage_probabilistic([94.0, 95.0, 96.0, 93.5, 95.5])
        assert result["health_stage"] == "Healthy"
        assert result["stage_probabilities"]["Healthy"] == 1.0
        assert result["stage_confidence"] == 1.0
        assert result["is_borderline"] is False

    def test_borderline_near_eol_threshold(self):
        # GH-60-like case: samples straddle the 80% EOL threshold
        samples = [78.5, 79.2, 79.8, 80.3, 80.9, 81.4, 79.5, 80.1, 81.0, 78.9]
        result = classify_health_stage_probabilistic(samples)
        assert result["is_borderline"] is True
        assert result["stage_confidence"] < 0.7
        probs = result["stage_probabilities"]
        assert probs["End Of Life"] == 0.5
        assert probs["Healthy"] == 0.5

    def test_tie_breaks_toward_more_severe_stage(self):
        # 50/50 split → safety-first: report the more severe stage
        samples = [79.0, 79.5, 81.0, 81.5]
        result = classify_health_stage_probabilistic(samples)
        assert result["health_stage"] == "End Of Life"

    def test_majority_wins_over_mean(self):
        # Mean is 79.96 (< 80 → point-estimate would say End Of Life), but
        # 7/10 samples are above the threshold → distribution says Healthy
        samples = [70.0, 79.0, 79.6, 80.2, 80.4, 80.6, 80.8, 81.0, 83.0, 85.0]
        result = classify_health_stage_probabilistic(samples)
        assert result["health_stage"] == "Healthy"
        assert result["stage_probabilities"]["End Of Life"] == 0.3

    def test_probabilities_sum_to_one(self):
        result = classify_health_stage_probabilistic([79.0, 84.0, 88.0, 95.0])
        assert abs(sum(result["stage_probabilities"].values()) - 1.0) < 1e-9

    def test_samples_clipped_to_valid_range(self):
        result = classify_health_stage_probabilistic([-5.0, 120.0])
        probs = result["stage_probabilities"]
        assert probs["End Of Life"] == 0.5
        assert probs["Healthy"] == 0.5

    def test_empty_samples_raise(self):
        import pytest

        with pytest.raises(ValueError):
            classify_health_stage_probabilistic([])


class TestRiskProfile:
    def test_health_stage_from_soh(self):
        # Two stages split at the 80% EOL threshold — anything above it still
        # has its rated life left and is Healthy, including the old
        # "Degrading" (85-90%) and "Maintenance Required" (80-85%) bands.
        assert classify_health_stage(95.0) == "Healthy"
        assert classify_health_stage(87.0) == "Healthy"
        assert classify_health_stage(82.0) == "Healthy"
        assert classify_health_stage(80.0) == "Healthy"
        assert classify_health_stage(79.9) == "End Of Life"
        assert classify_health_stage(79.0) == "End Of Life"

    def test_anomaly_status_from_score(self):
        assert classify_anomaly_status(0.1) == "Normal"
        assert classify_anomaly_status(-0.2) == "Warning"
        assert classify_anomaly_status(-0.4) == "Anomaly"

    def test_critical_warning_maps_to_p1(self):
        risk = compute_risk_profile(
            health_stage="Healthy",
            anomaly_status="Normal",
            warnings=[{"severity": "critical", "message": "Temperature critical"}],
            soh=95.0,
            cycles_to_maintenance=20,
        )
        assert risk["risk_level"] == "Critical"
        assert risk["priority"] == "P1"


class TestEstimateRul:
    def test_healthy_battery(self):
        assert estimate_rul(100.0) == 133

    def test_degrading_battery(self):
        assert estimate_rul(90.0) == 66
        assert estimate_rul(85.0) == 33

    def test_at_eol(self):
        assert estimate_rul(80.0) == 0

    def test_below_eol(self):
        assert estimate_rul(70.0) == 0
        assert estimate_rul(0.0) == 0


class TestComputeDegradationMetrics:
    """Regression test for the window=30 RUL bug: a sub-cycle window (L <
    _STEPS_PER_CYCLE=285) used to extrapolate voltage noise by ~19x (285/15),
    saturating the 2%/cycle clip ceiling and collapsing rul_cycles_estimate
    toward 0 even for a healthy battery (verified real case: SOH 93.3% -> 6
    cycles instead of ~88). Must fall back to the population-average rate."""

    def test_short_window_falls_back_to_population_average(self):
        raw = np.tile([3.85, 1.0, 25.0], (30, 1)).astype(float)
        result = compute_degradation_metrics(raw, soh_current=93.3)
        assert result["degradation_rate_per_cycle"] == 0.15
        assert result["rul_cycles_estimate"] == int((93.3 - 80.0) / 0.15)
        assert result["soh_trend"] == "stable"

    def test_short_window_healthy_battery_not_reported_as_near_eol(self):
        raw = np.tile([3.85, 1.0, 25.0], (30, 1)).astype(float)
        raw[:, 0] += np.linspace(-0.02, 0.02, 30)  # small sensor-noise slope
        result = compute_degradation_metrics(raw, soh_current=93.3)
        assert result["rul_cycles_estimate"] > 50  # far from the buggy value of 6

    def test_long_window_still_uses_segment_regression(self):
        L = 285 * 3
        raw = np.tile([3.85, 1.0, 25.0], (L, 1)).astype(float)
        raw[:, 0] -= np.linspace(0, 0.05, L)  # real fade across the window
        result = compute_degradation_metrics(raw, soh_current=88.0)
        assert result["degradation_rate_per_cycle"] != 0.15


class TestGetRecommendedAction:
    def test_normal(self):
        assert get_recommended_action("Normal", 95.0) == "MONITOR"

    def test_degrading_high_soh(self):
        assert get_recommended_action("Degrading", 88.0) == "SCHEDULE_MAINTENANCE"

    def test_degrading_low_soh_stops_at_inspection(self):
        # Above the 80% EOL threshold the pack is Healthy, so even the bottom
        # of the old "Maintenance Required" band only warrants an inspection —
        # SCHEDULE_REPLACEMENT is no longer produced anywhere.
        assert get_recommended_action("Degrading", 84.9) == "SCHEDULE_MAINTENANCE"
        assert get_recommended_action("Degrading", 80.1) == "SCHEDULE_MAINTENANCE"

    def test_failed(self):
        assert get_recommended_action("Failed", 75.0) == "REPLACE_IMMEDIATELY"


class TestGenerateWarnings:
    def _raw(self, voltage=3.8, current=-1.5, temperature=25.0, n=30):
        return np.full((n, 3), [voltage, current, temperature], dtype=np.float32)

    def test_no_warnings_healthy(self):
        assert generate_warnings(self._raw(), soh=95.0, classification="Normal") == []

    def test_no_soh_warning_above_eol(self):
        # A pack above the 80% EOL threshold is Healthy: no SOH warning is
        # raised, so has_warning stays False and no maintenance ticket is
        # forced. SOH_LOW (<90%) and SOH_CRITICAL (<85%) used to fire here and
        # opened a P3 ticket for a perfectly serviceable mid-life pack.
        for soh in (87.0, 83.0, 80.0):
            codes = [
                w["code"]
                for w in generate_warnings(self._raw(), soh=soh, classification="Degrading")
            ]
            assert "SOH_LOW" not in codes, soh
            assert "SOH_CRITICAL" not in codes, soh
            assert "BATTERY_EOL" not in codes, soh

    def test_battery_eol_warning(self):
        codes = [w["code"] for w in generate_warnings(self._raw(), soh=75.0, classification="Failed")]
        assert "BATTERY_EOL" in codes

    def test_voltage_low_warning(self):
        codes = [w["code"] for w in generate_warnings(self._raw(voltage=3.1), soh=95.0, classification="Normal")]
        assert "VOLTAGE_LOW" in codes

    def test_voltage_critical_warning(self):
        codes = [w["code"] for w in generate_warnings(self._raw(voltage=2.9), soh=95.0, classification="Normal")]
        assert "VOLTAGE_CRITICAL" in codes

    def test_temp_elevated_warning(self):
        codes = [w["code"] for w in generate_warnings(self._raw(temperature=38.0), soh=95.0, classification="Normal")]
        assert "TEMP_ELEVATED" in codes

    def test_temp_critical_warning(self):
        codes = [w["code"] for w in generate_warnings(self._raw(temperature=50.0), soh=95.0, classification="Normal")]
        assert "TEMP_CRITICAL" in codes

    def test_overcurrent_warning(self):
        codes = [w["code"] for w in generate_warnings(self._raw(current=-2.5), soh=95.0, classification="Normal")]
        assert "OVERCURRENT" in codes

    def test_warnings_sorted_critical_first(self):
        raw = self._raw(voltage=2.8, temperature=40.0)
        warnings = generate_warnings(raw, soh=75.0, classification="Failed")
        severities = [w["severity"] for w in warnings]
        critical_idx = [i for i, s in enumerate(severities) if s == "critical"]
        warning_idx  = [i for i, s in enumerate(severities) if s == "warning"]
        if critical_idx and warning_idx:
            assert max(critical_idx) < min(warning_idx)


class TestGenerateWarningsChemistry:
    """GH-67: per-cell voltage warning profile selected by pack chemistry."""

    def _raw(self, voltage, current=-1.5, temperature=25.0, n=30):
        return np.full((n, 3), [voltage, current, temperature], dtype=np.float32)

    def test_lfp_discharge_plateau_not_flagged(self):
        # 2.95 V/cell is a normal loaded LFP voltage: the NMC profile fires
        # VOLTAGE_CRITICAL (<3.0), the LFP profile stays silent (knee at 2.8)
        raw = self._raw(voltage=2.95)
        nmc = [w["code"] for w in generate_warnings(raw, 95.0, "Normal")]
        lfp = [w["code"] for w in generate_warnings(raw, 95.0, "Normal", chemistry="LFP")]
        assert "VOLTAGE_CRITICAL" in nmc
        assert lfp == []

    def test_lfp_overcharge_detected_where_nmc_is_blind(self):
        # 3.7 V/cell = real overcharge on LFP (charge cutoff 3.65 V) but far
        # below the NMC 4.15 V threshold — the NMC profile would miss it
        raw = self._raw(voltage=3.7)
        nmc = [w["code"] for w in generate_warnings(raw, 95.0, "Normal")]
        lfp = [w["code"] for w in generate_warnings(raw, 95.0, "Normal", chemistry="LFP")]
        assert nmc == []
        assert "OVERVOLTAGE" in lfp

    def test_lfp_critical_overcharge(self):
        raw = self._raw(voltage=3.85)
        lfp = [w["code"] for w in generate_warnings(raw, 95.0, "Normal", chemistry="LFP")]
        assert "OVERVOLTAGE_CRITICAL" in lfp

    def test_unknown_chemistry_falls_back_to_nmc_profile(self):
        raw = self._raw(voltage=2.95)
        codes = [
            w["code"]
            for w in generate_warnings(raw, 95.0, "Normal", chemistry="lead-acid")
        ]
        assert "VOLTAGE_CRITICAL" in codes


class TestTemperatureDomainDistance:
    """GH-91: distance to nearest NASA training chamber setpoint (4/24/44°C)."""

    def test_at_cluster_is_zero(self):
        temps = np.full(30, 24.0, dtype=np.float32)
        assert temperature_domain_distance(temps) == 0.0

    def test_at_threshold_boundary(self):
        # 9°C: min(|9-4|, |9-24|, |9-44|) = 5 — exactly at TEMPERATURE_OOD_THRESHOLD
        temps = np.full(30, 9.0, dtype=np.float32)
        assert temperature_domain_distance(temps) == 5.0

    def test_between_clusters_matches_issue_example(self):
        # 15°C: min(11, 9, 29) = 9 — the motivating example from issue #91
        temps = np.full(30, 15.0, dtype=np.float32)
        assert temperature_domain_distance(temps) == 9.0

    def test_beyond_outer_cluster(self):
        # 60°C (TEMPERATURE_RANGE upper bound): min(56, 36, 16) = 16
        temps = np.full(30, 60.0, dtype=np.float32)
        assert temperature_domain_distance(temps) == 16.0

    def test_uses_max_not_mean_across_window(self):
        # One reading far from any cluster (60°C, distance 16) among readings
        # at a cluster (24°C, distance 0) — max must catch the outlier.
        temps = np.full(30, 24.0, dtype=np.float32)
        temps[0] = 60.0
        assert temperature_domain_distance(temps) == 16.0


class TestTempOodWarning:
    def _raw(self, temperature, n=30):
        return np.full((n, 3), [3.8, -1.5, temperature], dtype=np.float32)

    def test_no_flag_at_cluster(self):
        codes = [w["code"] for w in generate_warnings(self._raw(24.0), soh=95.0, classification="Normal")]
        assert "TEMP_OOD" not in codes

    def test_flag_between_clusters(self):
        codes = [w["code"] for w in generate_warnings(self._raw(15.0), soh=95.0, classification="Normal")]
        assert "TEMP_OOD" in codes

    def test_no_flag_at_threshold_boundary(self):
        # 9°C: distance == 5.0 == threshold, uses `>` so NOT flagged
        codes = [w["code"] for w in generate_warnings(self._raw(9.0), soh=95.0, classification="Normal")]
        assert "TEMP_OOD" not in codes


class TestTemperatureDomainClusters:
    """GH-67 — cụm nhiệt độ train khác nhau giữa 2 bộ artifact.

    NASA chạy trong buồng 4/24/44 °C; Severson (bộ LFP) chạy TOÀN BỘ ở 30 °C.
    Dùng nhầm cụm NASA cho LFP thì 30 °C ra khoảng cách 6 °C — vượt ngưỡng OOD,
    nên gần như mọi đọc số ngoài trời của pin mặt trời đều bị gắn cờ sai.
    """

    def test_lfp_30c_is_in_domain(self):
        from src.core.config import LFP_TEMPERATURE_TRAIN_CLUSTERS
        from src.models.anomaly_detector import temperature_domain_distance

        temps = np.full(30, 30.0)
        assert temperature_domain_distance(temps, LFP_TEMPERATURE_TRAIN_CLUSTERS) == 0.0

    def test_lfp_35c_closer_than_nasa_clusters(self):
        """35 °C: v2.1-lfp có hẳn cell SNL ở 35 °C ⇒ lệch 0; cụm NASA lệch 9 °C."""
        from src.core.config import LFP_TEMPERATURE_TRAIN_CLUSTERS
        from src.models.anomaly_detector import temperature_domain_distance

        temps = np.full(30, 35.0)
        assert temperature_domain_distance(temps, LFP_TEMPERATURE_TRAIN_CLUSTERS) == 0.0
        assert temperature_domain_distance(temps) == 9.0

    def test_default_stays_nasa_clusters(self):
        """Không truyền clusters ⇒ giữ nguyên hành vi cũ (không hồi quy)."""
        from src.models.anomaly_detector import temperature_domain_distance

        assert temperature_domain_distance(np.full(30, 24.0)) == 0.0
        assert temperature_domain_distance(np.full(30, 44.0)) == 0.0

    def test_distance_is_worst_timestep(self):
        """Lấy max — 1 timestep lệch xa đủ để cả cửa sổ bị coi là ngoài miền."""
        from src.core.config import LFP_TEMPERATURE_TRAIN_CLUSTERS
        from src.models.anomaly_detector import temperature_domain_distance

        temps = np.full(30, 30.0)
        temps[7] = 55.0  # cụm gần nhất là 40 °C ⇒ lệch 15
        assert temperature_domain_distance(temps, LFP_TEMPERATURE_TRAIN_CLUSTERS) == 15.0

    def test_warning_path_is_chemistry_aware_too(self):
        """GH-67: có HAI đường sinh cờ OOD nhiệt độ — risk profile và warning
        TEMP_OOD. Sửa mỗi đường risk thì LFP ở 30 °C vẫn nhận cảnh báo sai kèm
        chuỗi cụm NASA '(4/24/44°C)'. Test này khoá cả đường warning."""
        from src.models.anomaly_detector import generate_warnings

        raw = np.column_stack([
            np.full(30, 3.3),    # voltage per-cell
            np.zeros(30),        # current
            np.full(30, 30.0),   # temperature — đúng buồng Severson
        ]).astype(np.float32)

        lfp = generate_warnings(raw, 95.0, "Normal", chemistry="LFP")
        assert "TEMP_OOD" not in {w["code"] for w in lfp}

        # không khai chemistry ⇒ vẫn cụm NASA, 30 °C cách 6 °C nên có cảnh báo
        nasa = [w for w in generate_warnings(raw, 95.0, "Normal") if w["code"] == "TEMP_OOD"]
        assert nasa and "4/24/44" in nasa[0]["message"]

    def test_lfp_warning_message_names_the_lfp_cluster(self):
        """Khi LFP thật sự ngoài miền, thông điệp phải in cụm của bộ LFP — in
        nhầm cụm NASA làm người đọc log kết luận sai nguyên nhân.

        50 °C mới là ngoài miền với v2.1-lfp: cụm cao nhất là 40 °C nên 45 °C chỉ
        cách 5.0, vừa đúng ngưỡng và KHÔNG cảnh báo nữa (v2.0 chỉ có cụm 30 °C)."""
        from src.models.anomaly_detector import generate_warnings

        raw = np.column_stack([
            np.full(30, 3.3), np.zeros(30), np.full(30, 50.0)
        ]).astype(np.float32)
        w = [x for x in generate_warnings(raw, 95.0, "Normal", chemistry="LFP")
             if x["code"] == "TEMP_OOD"]
        assert w and "(15/25/30/35/40°C)" in w[0]["message"]


class TestDegradationRateByChemistry:
    """GH-67 — tốc độ suy giảm 0.15%/chu kỳ là của cell NASA 18650 NMC (chết sau
    ~150 chu kỳ). Dùng cho LFP thì RUL sai ~17 lần: đo trên dump IoT thật ra
    rul_cycles_estimate=133 cho một quả pin LFP 30Ah MỚI TINH.
    """

    def _resting_window(self):
        return np.column_stack([
            np.full(30, 3.3), np.zeros(30), np.full(30, 30.0),
            np.arange(30, dtype=np.float32) * 17.0,
        ]).astype(np.float32)

    def test_lfp_rul_matches_severson_cycle_life(self):
        from src.models.anomaly_detector import compute_degradation_metrics

        d = compute_degradation_metrics(self._resting_window(), 100.0, chemistry="LFP")
        assert d["degradation_rate_per_cycle"] == 0.0087
        # (100 - 80) / 0.0087 ≈ 2299 — khớp ~2300 chu kỳ của bộ Severson
        assert 2200 <= d["rul_cycles_estimate"] <= 2400

    def test_nasa_path_unchanged(self):
        """Không khai chemistry ⇒ giữ nguyên hằng số NASA, không hồi quy."""
        from src.models.anomaly_detector import DEGRADATION_RATE, compute_degradation_metrics

        d = compute_degradation_metrics(self._resting_window(), 100.0)
        assert d["degradation_rate_per_cycle"] == DEGRADATION_RATE
        assert d["rul_cycles_estimate"] == 133

    def test_production_window_always_uses_the_fallback_rate(self):
        """window=30 < _STEPS_PER_CYCLE nên LUÔN đi nhánh hằng số — đó là lý do
        hằng số này chính là RUL mà BE nhận được, không phải giá trị dự phòng
        hiếm khi dùng."""
        from src.models.anomaly_detector import _STEPS_PER_CYCLE

        assert 30 < _STEPS_PER_CYCLE


class TestInsufficientDischargeFlag:
    """GH-67 — pin nằm im thì SOH không dựa trên phép đo nào."""

    def _raw(self, currents):
        return np.column_stack([
            np.full(30, 3.3), np.asarray(currents, dtype=np.float32), np.full(30, 30.0),
        ]).astype(np.float32)

    def _flag(self, warnings):
        return next((w for w in warnings if w["code"] == "INSUFFICIENT_DISCHARGE"), None)

    def test_resting_window_raises_the_flag(self):
        from src.models.anomaly_detector import generate_warnings

        w = self._flag(generate_warnings(self._raw(np.zeros(30)), 100.0, "Normal",
                                         chemistry="LFP"))
        assert w is not None

    def test_flag_is_info_so_it_cannot_escalate_risk(self):
        """compute_risk_profile() chỉ leo thang với severity warning/critical.
        Đổi severity của cờ này thành 'warning' sẽ biến MỌI cửa sổ pin nằm im
        thành risk Medium/P3 — test này khoá lại."""
        from src.models.anomaly_detector import compute_risk_profile, generate_warnings

        ws = generate_warnings(self._raw(np.zeros(30)), 100.0, "Normal", chemistry="LFP")
        assert self._flag(ws)["severity"] == "info"
        risk = compute_risk_profile(
            health_stage="Healthy", anomaly_status="Normal", warnings=ws,
            soh=100.0, cycles_to_maintenance=1724,
        )
        assert risk["risk_level"] == "Low"

    def test_window_with_discharge_has_no_flag(self):
        from src.models.anomaly_detector import generate_warnings

        currents = np.full(30, -2.0)
        assert self._flag(generate_warnings(self._raw(currents), 95.0, "Normal",
                                            chemistry="LFP")) is None

    def test_charge_only_window_still_flagged(self):
        """Sạc cũng không đo được dung lượng xả — model train trên đoạn xả."""
        from src.models.anomaly_detector import generate_warnings

        assert self._flag(generate_warnings(self._raw(np.full(30, 2.4)), 100.0,
                                            "Normal", chemistry="LFP")) is not None


class TestTemperatureProfileByChemistry:
    """GH-67 — ngưỡng nhiệt độ theo chemistry.

    Trước đây dùng chung 35/45 cho MỌI loại pin, trong khi SOP của chính dự án
    (knowledge/safety/anomaly_thermal.md) ghi cell LFP chịu tới 60 °C, NMC 55 °C.
    Pin LFP 8S thật đặt ngoài trời đo được max 34.5 °C — cách ngưỡng cũ đúng
    0.5 °C, tức mỗi trưa nắng là sinh ticket giả.
    """

    def _warn(self, temp, chemistry):
        from src.models.anomaly_detector import generate_warnings

        raw = np.column_stack([
            np.full(30, 3.3), np.zeros(30), np.full(30, temp)
        ]).astype(np.float32)
        return {
            w["code"] for w in generate_warnings(raw, 95.0, "Normal", chemistry=chemistry)
        }

    def test_lfp_quiet_in_the_outdoor_range(self):
        """29–44 °C là dải vận hành ngoài trời bình thường của pin mặt trời."""
        for temp in (34.5, 38.0, 42.0, 44.0):
            assert "TEMP_ELEVATED" not in self._warn(temp, "LFP")
            assert "TEMP_CRITICAL" not in self._warn(temp, "LFP")

    def test_lfp_still_warns_above_its_own_limit(self):
        """Nới ngưỡng KHÔNG được biến thành tắt cảnh báo."""
        assert "TEMP_ELEVATED" in self._warn(46.0, "LFP")
        assert "TEMP_CRITICAL" in self._warn(56.0, "LFP")

    def test_lfp_critical_stays_below_thermal_runaway(self):
        """55 < 60 — phải còn đệm trước ngưỡng thoát nhiệt trong anomaly_thermal.md.
        Lấy thẳng 60 làm ngưỡng cảnh báo là cảnh báo lúc đã cháy."""
        from src.models.anomaly_detector import CHEMISTRY_TEMP_PROFILES

        _, crit = CHEMISTRY_TEMP_PROFILES["LFP"]
        assert crit < 60.0

    def test_default_path_unchanged(self):
        """NMC KHÔNG phải loại pin thứ hai — nó là đường mặc định khi request không
        khai chemistry, và BE hiện chưa gửi pack_config (issue #1005). Đổi nó là
        đổi hành vi của mọi request đang chạy."""
        from src.models.anomaly_detector import (
            CHEMISTRY_TEMP_PROFILES,
            TEMP_CRITICAL,
            TEMP_WARNING,
        )

        assert CHEMISTRY_TEMP_PROFILES["NMC"] == (TEMP_WARNING, TEMP_CRITICAL)
        assert "TEMP_ELEVATED" in self._warn(36.0, None)
        assert "TEMP_CRITICAL" in self._warn(46.0, None)
