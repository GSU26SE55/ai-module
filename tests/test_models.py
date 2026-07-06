import numpy as np
import torch

from src.core.config import INPUT_FEATURES, SPECTRAL_FEAT_DIM, WINDOW_SIZE
from src.models.anomaly_detector import (
    classify_anomaly,
    classify_anomaly_status,
    classify_health_stage,
    classify_health_stage_probabilistic,
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
        assert probs["Maintenance Required"] == 0.5

    def test_tie_breaks_toward_more_severe_stage(self):
        # 50/50 split → safety-first: report the more severe stage
        samples = [79.0, 79.5, 81.0, 81.5]
        result = classify_health_stage_probabilistic(samples)
        assert result["health_stage"] == "End Of Life"

    def test_majority_wins_over_mean(self):
        # Mean is 79.96 (< 80 → point-estimate would say End Of Life), but
        # 6/10 samples are above the threshold → distribution says Maintenance
        samples = [70.0, 79.0, 79.6, 80.2, 80.4, 80.6, 80.8, 81.0, 83.0, 85.0]
        result = classify_health_stage_probabilistic(samples)
        assert result["health_stage"] == "Maintenance Required"
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
        assert classify_health_stage(95.0) == "Healthy"
        assert classify_health_stage(87.0) == "Degrading"
        assert classify_health_stage(82.0) == "Maintenance Required"
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


class TestGetRecommendedAction:
    def test_normal(self):
        assert get_recommended_action("Normal", 95.0) == "MONITOR"

    def test_degrading_high_soh(self):
        assert get_recommended_action("Degrading", 88.0) == "SCHEDULE_MAINTENANCE"

    def test_degrading_low_soh(self):
        assert get_recommended_action("Degrading", 84.9) == "SCHEDULE_REPLACEMENT"

    def test_failed(self):
        assert get_recommended_action("Failed", 75.0) == "REPLACE_IMMEDIATELY"


class TestGenerateWarnings:
    def _raw(self, voltage=3.8, current=-1.5, temperature=25.0, n=30):
        return np.full((n, 3), [voltage, current, temperature], dtype=np.float32)

    def test_no_warnings_healthy(self):
        assert generate_warnings(self._raw(), soh=95.0, classification="Normal") == []

    def test_soh_low_warning(self):
        codes = [w["code"] for w in generate_warnings(self._raw(), soh=87.0, classification="Degrading")]
        assert "SOH_LOW" in codes

    def test_soh_critical_warning(self):
        codes = [w["code"] for w in generate_warnings(self._raw(), soh=83.0, classification="Degrading")]
        assert "SOH_CRITICAL" in codes

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
