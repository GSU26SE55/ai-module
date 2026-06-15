import time
from unittest.mock import patch

import numpy as np
import pytest

from src.core.config import D_MODEL, D_STATE, INPUT_FEATURES, LONG_SEQ_LEN, SPECTRAL_FEAT_DIM, WINDOW_SIZE
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


class TestLongInference:
    """GH-10: long-sequence fast-path inference + lazy long-model loading."""

    def _setup_artifacts(self, tmp_path, monkeypatch):
        import joblib
        import torch
        from sklearn.preprocessing import MinMaxScaler, StandardScaler

        from src.core import model_loader
        from src.core.config import LONG_MODEL_VERSION

        raw_scaler  = MinMaxScaler().fit(np.random.rand(50, INPUT_FEATURES))
        feat_scaler = StandardScaler().fit(np.random.rand(50, SPECTRAL_FEAT_DIM))
        scaler_path = tmp_path / "scaler.pkl"
        feat_path   = tmp_path / "feature_scaler_long.pkl"
        joblib.dump({"scaler": raw_scaler,  "version": "1.0"},      scaler_path)
        joblib.dump({"scaler": feat_scaler, "version": "long-1.0"}, feat_path)

        model = MambaSOHPredictor(
            input_features=INPUT_FEATURES, feat_dim=SPECTRAL_FEAT_DIM,
            d_model=8, d_state=4, pooling="attention",
        )
        model_path = tmp_path / "soh_mamba_long.pth"
        torch.save(
            {
                "model_state_dict": model.state_dict(), "version": LONG_MODEL_VERSION,
                "pooling": "attention", "input_features": INPUT_FEATURES,
                "feat_dim": SPECTRAL_FEAT_DIM, "d_model": 8, "d_state": 4,
            },
            model_path,
        )

        monkeypatch.setattr(model_loader, "SCALER_PATH", str(scaler_path))
        monkeypatch.setattr(model_loader, "LONG_FEATURE_SCALER_PATH", str(feat_path))
        monkeypatch.setattr(model_loader, "LONG_MAMBA_PATH", str(model_path))
        for attr in ("scaler", "long_feature_scaler", "long_soh_model", "long_device"):
            monkeypatch.setattr(model_loader, attr, None)

    def test_predict_soh_long_chunked_path(self, tmp_path, monkeypatch):
        self._setup_artifacts(tmp_path, monkeypatch)
        from src.services.inference import predict_soh_long

        readings = np.random.rand(600, INPUT_FEATURES).tolist()  # L>512 → chunked no-ckpt path
        out = predict_soh_long(readings, device="cpu")
        assert 0.0 <= out["soh_percent"] <= 100.0
        assert out["seq_len"] == 600
        assert out["device"] == "cpu"
        assert out["inference_ms"] >= 0

    def test_long_model_lazy_loaded(self, tmp_path, monkeypatch):
        self._setup_artifacts(tmp_path, monkeypatch)
        from src.core import model_loader
        from src.services.inference import predict_soh_long

        assert model_loader.long_soh_model is None
        predict_soh_long(np.random.rand(64, INPUT_FEATURES).tolist(), device="cpu")
        assert model_loader.long_soh_model is not None
        assert model_loader.long_feature_scaler is not None

    def test_long_latency_benchmark(self):
        """L=4096 fast-path latency. SLA <100ms enforced on GPU only; CPU recorded.

        Latency is config-driven (not weight-driven), so a randomly-initialised
        production-config model gives a representative number even without trained
        weights — the real number is re-confirmed on Kaggle GPU before /kltn-ship.
        """
        import time

        import torch

        torch.manual_seed(42)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = MambaSOHPredictor(
            input_features=INPUT_FEATURES, feat_dim=SPECTRAL_FEAT_DIM,
            d_model=D_MODEL, d_state=D_STATE, pooling="attention",
        ).to(device).eval()
        x  = torch.randn(1, LONG_SEQ_LEN, INPUT_FEATURES, device=device)
        xf = torch.randn(1, SPECTRAL_FEAT_DIM, device=device)

        with torch.no_grad():
            model(x, xf)  # warmup
            if device.type == "cuda":
                torch.cuda.synchronize()
            lat = []
            for _ in range(3):
                s = time.perf_counter()
                model(x, xf)
                if device.type == "cuda":
                    torch.cuda.synchronize()
                lat.append((time.perf_counter() - s) * 1000)
        avg = sum(lat) / len(lat)
        print(f"[GH-10] L={LONG_SEQ_LEN} latency on {device}: avg {avg:.1f}ms")

        if device.type == "cuda":
            assert avg < 100, f"GPU L={LONG_SEQ_LEN} latency {avg:.1f}ms exceeds 100ms SLA"
        # CPU: recorded only — SLA <100ms is enforced on GPU per GH-10 deploy decision.
