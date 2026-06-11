import time
from unittest.mock import patch

import numpy as np
import pytest

from src.core.config import INPUT_FEATURES, SPECTRAL_FEAT_DIM, WINDOW_SIZE
from src.models.soh_predictor import MambaSOHPredictor

REQUIRED_KEYS = {
    "prediction",
    "anomaly",
    "risk",
    "evidence",
    "metadata",
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


def make_dummy_readings(n: int = WINDOW_SIZE) -> list[list[float]]:
    return [[3.7 + i * 0.001, 1.5, 25.0, 1.5, 3.7, float(i)] for i in range(n)]


class TestInferencePipeline:
    @pytest.fixture(autouse=True)
    def patch_model_loader(self):
        """Patch model_loader globals — no real artifact files needed."""
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import MinMaxScaler, StandardScaler

        dummy_scaler = MinMaxScaler()
        dummy_scaler.fit(np.random.rand(50, INPUT_FEATURES))

        dummy_feat_scaler = StandardScaler()
        dummy_feat_scaler.fit(np.random.rand(50, SPECTRAL_FEAT_DIM))

        dummy_model = MambaSOHPredictor(
            input_features=INPUT_FEATURES,
            feat_dim=SPECTRAL_FEAT_DIM,
            d_model=8,
            d_state=4,
        )
        dummy_model.eval()

        # IF now trained on spectral features (SPECTRAL_FEAT_DIM), not raw flatten
        dummy_iso = IsolationForest(n_estimators=10, random_state=42)
        dummy_iso.fit(np.random.rand(50, SPECTRAL_FEAT_DIM))

        with patch("src.services.inference.model_loader") as mock_loader:
            mock_loader.scaler         = dummy_scaler
            mock_loader.feature_scaler = dummy_feat_scaler
            mock_loader.soh_model      = dummy_model
            mock_loader.iso_model      = dummy_iso
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
        assert result["prediction"]["health_stage"] in {
            "Healthy", "Degrading", "Maintenance Required", "End Of Life",
        }

    def test_soh_is_float(self):
        from src.services.inference import run_inference
        result = run_inference(make_dummy_readings())
        assert isinstance(result["soh_percent"], float)

    def test_confidence_in_range(self):
        from src.services.inference import run_inference
        result = run_inference(make_dummy_readings())
        assert 0.0 <= result["confidence"] <= 1.0
        # confidence = soh_confidence (MC Dropout), anomaly_confidence = IF-based — different values
        assert 0.0 <= result["anomaly"]["anomaly_confidence"] <= 1.0

    def test_nested_rag_fields_are_present(self):
        from src.services.inference import run_inference
        result = run_inference(make_dummy_readings())
        assert "soh_percent" in result["prediction"]
        assert "anomaly_status" in result["anomaly"]
        assert "risk_level" in result["risk"]
        assert "priority" in result["risk"]
        assert "reasons" in result["risk"]
        assert "warnings" in result["evidence"]
        assert "model_version" in result["metadata"]

    def test_rul_is_non_negative_int(self):
        from src.services.inference import run_inference
        result = run_inference(make_dummy_readings())
        assert isinstance(result["rul_cycles_estimate"], int)
        assert result["rul_cycles_estimate"] >= 0

    def test_recommended_action_is_valid(self):
        from src.services.inference import run_inference
        valid_actions = {
            "MONITOR", "SCHEDULE_MAINTENANCE",
            "SCHEDULE_REPLACEMENT", "REPLACE_IMMEDIATELY",
        }
        result = run_inference(make_dummy_readings())
        assert result["recommended_action"] in valid_actions
        assert result["recommended_action"] == result["risk"]["action_code"]

    def test_warnings_is_list(self):
        from src.services.inference import run_inference
        result = run_inference(make_dummy_readings())
        assert isinstance(result["warnings"], list)
        assert result["warnings"] == result["evidence"]["warnings"]

    def test_warnings_have_required_fields(self):
        from src.services.inference import run_inference
        for w in run_inference(make_dummy_readings())["warnings"]:
            assert "code" in w and "severity" in w and "message" in w

    def test_feature_summary_has_voltage(self):
        from src.services.inference import run_inference
        stat = run_inference(make_dummy_readings())["feature_summary"]["voltage"]
        assert "mean" in stat and "min" in stat and "max" in stat

    def test_long_sequence_inference_completes(self):
        """Long-sequence health inference is a batch/background path, not a 100ms realtime path."""
        from src.services.inference import run_inference
        readings = make_dummy_readings()
        latencies = []
        for _ in range(2):
            start = time.perf_counter()
            run_inference(readings)
            latencies.append((time.perf_counter() - start) * 1000)
        avg_ms = sum(latencies) / len(latencies)
        assert avg_ms < 10000, f"Avg latency {avg_ms:.1f}ms is unexpectedly slow for test model"
