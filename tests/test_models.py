import numpy as np
import torch

from src.core.config import INPUT_FEATURES, SPECTRAL_FEAT_DIM
from src.models.anomaly_detector import (
    classify_anomaly,
    estimate_rul,
    generate_warnings,
    get_recommended_action,
)
from src.models.soh_predictor import MambaSOHPredictor


def _make_inputs(batch: int = 1):
    x      = torch.randn(batch, 30, INPUT_FEATURES)
    x_feat = torch.randn(batch, SPECTRAL_FEAT_DIM)
    return x, x_feat


class TestMambaSOHPredictor:
    def test_output_shape_single(self):
        model = MambaSOHPredictor(input_features=INPUT_FEATURES, feat_dim=SPECTRAL_FEAT_DIM)
        model.eval()
        x, x_feat = _make_inputs(1)
        with torch.no_grad():
            out = model(x, x_feat)
        assert out.shape == (1,), f"Expected (1,), got {out.shape}"

    def test_output_shape_batch(self):
        model = MambaSOHPredictor(input_features=INPUT_FEATURES, feat_dim=SPECTRAL_FEAT_DIM)
        model.eval()
        x, x_feat = _make_inputs(8)
        with torch.no_grad():
            out = model(x, x_feat)
        assert out.shape == (8,), f"Expected (8,), got {out.shape}"

    def test_output_is_float(self):
        model = MambaSOHPredictor(input_features=INPUT_FEATURES, feat_dim=SPECTRAL_FEAT_DIM)
        model.eval()
        x, x_feat = _make_inputs(2)
        with torch.no_grad():
            out = model(x, x_feat)
        assert out.dtype == torch.float32

    def test_gradients_flow(self):
        model = MambaSOHPredictor(input_features=INPUT_FEATURES, feat_dim=SPECTRAL_FEAT_DIM)
        x, x_feat = _make_inputs(2)
        out = model(x, x_feat)
        loss = out.sum()
        loss.backward()
        grads = [p.grad for p in model.parameters() if p.grad is not None]
        assert len(grads) > 0, "No gradients computed"

    def test_film_modulation_changes_output(self):
        """Different x_feat should produce different SOH predictions."""
        model = MambaSOHPredictor(input_features=INPUT_FEATURES, feat_dim=SPECTRAL_FEAT_DIM)
        model.eval()
        x = torch.randn(1, 30, INPUT_FEATURES)
        feat_a = torch.zeros(1, SPECTRAL_FEAT_DIM)
        feat_b = torch.ones(1, SPECTRAL_FEAT_DIM)
        with torch.no_grad():
            out_a = model(x, feat_a)
            out_b = model(x, feat_b)
        assert not torch.allclose(out_a, out_b), "FiLM conditioning has no effect"


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
