import time
from unittest.mock import patch

import numpy as np
import pytest

from src.models.soh_predictor import MambaSOHPredictor

REQUIRED_KEYS = {
    "soh_percent",
    "classification",
    "confidence",
    "inference_ms",
    "rul_cycles_estimate",
    "anomaly_score",
    "recommended_action",
    "warnings",
    "feature_summary",
}


def make_dummy_readings(n: int = 30) -> list[list[float]]:
    return [[3.7 + i * 0.001, 1.5, 25.0] for i in range(n)]


class TestInferencePipeline:
    @pytest.fixture(autouse=True)
    def patch_model_loader(self):
        """Patch model_loader globals so tests don't need real artifact files."""
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import MinMaxScaler

        dummy_scaler = MinMaxScaler()
        dummy_scaler.fit(np.random.rand(50, 3))

        dummy_model = MambaSOHPredictor()
        dummy_model.eval()

        dummy_iso = IsolationForest(n_estimators=10, random_state=42)
        dummy_iso.fit(np.random.rand(50, 90))

        with patch("src.services.inference.model_loader") as mock_loader:
            mock_loader.scaler = dummy_scaler
            mock_loader.soh_model = dummy_model
            mock_loader.iso_model = dummy_iso
            yield

    def test_returns_expected_keys(self):
        from src.services.inference import run_inference

        result = run_inference(make_dummy_readings())
        assert REQUIRED_KEYS.issubset(result.keys()), (
            f"Missing keys: {REQUIRED_KEYS - result.keys()}"
        )

    def test_classification_is_valid(self):
        from src.services.inference import run_inference

        result = run_inference(make_dummy_readings())
        assert result["classification"] in {"Normal", "Degrading", "Failed"}

    def test_soh_is_float(self):
        from src.services.inference import run_inference

        result = run_inference(make_dummy_readings())
        assert isinstance(result["soh_percent"], float)

    def test_confidence_in_range(self):
        from src.services.inference import run_inference

        result = run_inference(make_dummy_readings())
        assert 0.0 <= result["confidence"] <= 1.0

    def test_rul_is_non_negative_int(self):
        from src.services.inference import run_inference

        result = run_inference(make_dummy_readings())
        assert isinstance(result["rul_cycles_estimate"], int)
        assert result["rul_cycles_estimate"] >= 0

    def test_recommended_action_is_valid(self):
        from src.services.inference import run_inference

        valid_actions = {
            "MONITOR",
            "SCHEDULE_MAINTENANCE",
            "SCHEDULE_REPLACEMENT",
            "REPLACE_IMMEDIATELY",
        }
        result = run_inference(make_dummy_readings())
        assert result["recommended_action"] in valid_actions

    def test_warnings_is_list(self):
        from src.services.inference import run_inference

        result = run_inference(make_dummy_readings())
        assert isinstance(result["warnings"], list)

    def test_warnings_have_required_fields(self):
        from src.services.inference import run_inference

        result = run_inference(make_dummy_readings())
        for w in result["warnings"]:
            assert "code" in w
            assert "severity" in w
            assert "message" in w

    def test_feature_summary_has_voltage(self):
        from src.services.inference import run_inference

        result = run_inference(make_dummy_readings())
        assert "voltage" in result["feature_summary"]
        stat = result["feature_summary"]["voltage"]
        assert "mean" in stat and "min" in stat and "max" in stat

    def test_latency_under_100ms(self):
        """Inference must complete within 100ms (P1 SLA requirement)."""
        from src.services.inference import run_inference

        readings = make_dummy_readings()
        latencies = []
        for _ in range(20):
            start = time.perf_counter()
            run_inference(readings)
            latencies.append((time.perf_counter() - start) * 1000)

        avg_ms = sum(latencies) / len(latencies)
        assert avg_ms < 100, f"Avg inference latency {avg_ms:.1f}ms exceeds 100ms SLA"
