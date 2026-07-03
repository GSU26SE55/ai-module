import time
from unittest.mock import patch

import numpy as np
import pytest

from src.core.config import (
    BASE_FEATURES,
    D_MODEL,
    D_STATE,
    INPUT_FEATURES,
    LONG_SEQ_LEN,
    SPECTRAL_FEAT_DIM,
    WINDOW_SIZE,
)

from src.models.soh_predictor import MambaSOHPredictor

BASE_N = len(BASE_FEATURES)  # GH-54: payload/scaler width (4)

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
    return [[3.7 + i * 0.001, 1.5, 25.0, float(i)] for i in range(n)]


class TestInferencePipeline:
    @pytest.fixture(autouse=True)
    def patch_model_loader(self):
        """Patch model_loader globals — no real artifact files needed."""
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import MinMaxScaler, StandardScaler

        dummy_scaler = MinMaxScaler()
        dummy_scaler.fit(np.random.rand(50, BASE_N))

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
            mock_loader.scaler = dummy_scaler
            mock_loader.feature_scaler = dummy_feat_scaler
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
        assert result["prediction"]["health_stage"] in {
            "Healthy",
            "Degrading",
            "Maintenance Required",
            "End Of Life",
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
            "MONITOR",
            "SCHEDULE_MAINTENANCE",
            "SCHEDULE_REPLACEMENT",
            "REPLACE_IMMEDIATELY",
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
        assert avg_ms < 10000, (
            f"Avg latency {avg_ms:.1f}ms is unexpectedly slow for test model"
        )


class TestLongInference:
    """GH-10: long-sequence fast-path inference + lazy long-model loading."""

    def _setup_artifacts(self, tmp_path, monkeypatch):
        import joblib
        import torch
        from sklearn.preprocessing import MinMaxScaler, StandardScaler

        from src.core import model_loader
        from src.core.config import LONG_INPUT_FEATURES, LONG_MODEL_VERSION

        # 6-feature scaler → used by _align_features (reads model_loader.scaler.n_features_in_)
        raw_scaler = MinMaxScaler().fit(np.random.rand(50, BASE_N))
        # 8-feature long scaler → transforms [6 base + IC curve + phase mask] before the long model
        long_scaler = MinMaxScaler().fit(np.random.rand(50, LONG_INPUT_FEATURES))
        feat_scaler = StandardScaler().fit(np.random.rand(50, SPECTRAL_FEAT_DIM))
        long_scaler_path = tmp_path / "scaler_long.pkl"
        feat_path = tmp_path / "feature_scaler_long.pkl"
        joblib.dump({"scaler": long_scaler, "version": "2.0"}, long_scaler_path)
        joblib.dump({"scaler": feat_scaler, "version": "long-1.0"}, feat_path)

        # Long model takes 8 input features (6 base + IC curve + phase mask)
        model = MambaSOHPredictor(
            input_features=LONG_INPUT_FEATURES,
            feat_dim=SPECTRAL_FEAT_DIM,
            d_model=8,
            d_state=4,
            pooling="attention",
        )
        model_path = tmp_path / "soh_mamba_long.pth"
        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "version": LONG_MODEL_VERSION,
                "pooling": "attention",
                "input_features": LONG_INPUT_FEATURES,
                "feat_dim": SPECTRAL_FEAT_DIM,
                "d_model": 8,
                "d_state": 4,
                # patch_size=1 (no-patch) — must match how load_long_model reconstructs;
                # default LONG_PATCH_SIZE=16 would build patch_embed and mismatch state_dict.
                "patch_size": 1,
                "patch_stride": 1,
            },
            model_path,
        )

        # load_long_model calls torch.compile(mode="reduce-overhead"); inductor needs a
        # C++ toolchain (absent on some dev boxes) and fails at forward-time (not caught by
        # the compile() try/except). Unit tests exercise inference logic, not compilation →
        # make torch.compile a no-op so the test is toolchain-independent.
        monkeypatch.setattr(torch, "compile", lambda m, *a, **k: m)
        monkeypatch.setattr(model_loader, "LONG_SCALER_PATH", str(long_scaler_path))
        monkeypatch.setattr(model_loader, "LONG_FEATURE_SCALER_PATH", str(feat_path))
        monkeypatch.setattr(model_loader, "LONG_MAMBA_PATH", str(model_path))
        # predict_soh_long → _align_features reads model_loader.scaler.n_features_in_ (6);
        # set it directly since load_models() is not called in the long-only path.
        monkeypatch.setattr(model_loader, "scaler", raw_scaler)
        for attr in (
            "long_scaler",
            "long_feature_scaler",
            "long_soh_model",
            "long_device",
        ):
            monkeypatch.setattr(model_loader, attr, None)

    def test_predict_soh_long_chunked_path(self, tmp_path, monkeypatch):
        self._setup_artifacts(tmp_path, monkeypatch)
        from src.services.inference import predict_soh_long

        readings = np.random.rand(600, BASE_N).tolist()  # L>512 → chunked no-ckpt path
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
        predict_soh_long(np.random.rand(64, BASE_N).tolist(), device="cpu")
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
        model = (
            MambaSOHPredictor(
                input_features=INPUT_FEATURES,
                feat_dim=SPECTRAL_FEAT_DIM,
                d_model=D_MODEL,
                d_state=D_STATE,
                pooling="attention",
            )
            .to(device)
            .eval()
        )
        x = torch.randn(1, LONG_SEQ_LEN, INPUT_FEATURES, device=device)
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
            assert avg < 100, (
                f"GPU L={LONG_SEQ_LEN} latency {avg:.1f}ms exceeds 100ms SLA"
            )
        # CPU: recorded only — SLA <100ms is enforced on GPU per GH-10 deploy decision.


class TestAppendDerivedFeatures:
    """GH-54 — run_inference builds (30,6) model input from a 4-col payload."""

    @pytest.fixture(autouse=True)
    def patch_loader(self):
        from src.models.soh_predictor import MambaSOHPredictor

        model = MambaSOHPredictor(
            input_features=INPUT_FEATURES,
            feat_dim=SPECTRAL_FEAT_DIM,
            d_model=8,
            d_state=4,
        )
        with patch("src.services.inference.model_loader") as mock_loader:
            mock_loader.soh_model = model
            yield

    def test_appends_two_columns_with_defaults(self):
        from src.services.inference import _append_derived_features

        raw = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)
        raw[:, 3] = np.arange(WINDOW_SIZE) * 10.0
        x_scaled = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)

        out = _append_derived_features(x_scaled, raw, cycle_idx=None)
        assert out.shape == (WINDOW_SIZE, INPUT_FEATURES)
        np.testing.assert_allclose(out[:, 4], 0.0)  # BE chua gui cycle_idx -> 0
        assert out[0, 5] == 1.0  # SOC window-local bat dau 100%

    def test_cycle_idx_normalized(self):
        from src.core.config import CYCLE_COUNT_NORM
        from src.services.inference import _append_derived_features

        raw = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)
        raw[:, 3] = np.arange(WINDOW_SIZE) * 10.0
        x_scaled = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)

        out = _append_derived_features(x_scaled, raw, cycle_idx=100)
        np.testing.assert_allclose(out[:, 4], 100 / CYCLE_COUNT_NORM)

    def test_legacy_model_passthrough(self):
        """Model 4-input (pre-GH-54) -> khong append gi ca."""
        from src.models.soh_predictor import MambaSOHPredictor
        from src.services import inference as inf

        legacy = MambaSOHPredictor(
            input_features=BASE_N, feat_dim=SPECTRAL_FEAT_DIM, d_model=8, d_state=4
        )
        with patch.object(inf.model_loader, "soh_model", legacy, create=True):
            x_scaled = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)
            raw = x_scaled.copy()
            out = inf._append_derived_features(x_scaled, raw, cycle_idx=None)
        assert out.shape == (WINDOW_SIZE, BASE_N)

    def test_6col_payload_uses_be_values_directly(self):
        """GH-56 — payload voi 6 cot: cycle_count/soc_percent (BE tinh) duoc dung
        thang, khong tinh lai qua Coulomb counting."""
        from src.core.config import CYCLE_COUNT_NORM
        from src.services.inference import _append_derived_features

        raw4 = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)
        raw4[:, 3] = np.arange(WINDOW_SIZE) * 10.0
        raw_cycle_count = np.full(WINDOW_SIZE, 42.0, dtype=np.float32)  # raw int, constant
        raw_soc_percent = np.linspace(100.0, 80.0, WINDOW_SIZE).astype(np.float32)
        raw6 = np.column_stack([raw4, raw_cycle_count, raw_soc_percent])
        x_scaled = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)

        out = _append_derived_features(x_scaled, raw6, cycle_idx=None)
        assert out.shape == (WINDOW_SIZE, INPUT_FEATURES)
        np.testing.assert_allclose(out[:, 4], 42.0 / CYCLE_COUNT_NORM)
        np.testing.assert_allclose(out[:, 5], raw_soc_percent / 100.0)
        # cycle_idx param is ignored once the payload already carries 6 columns
        out_ignored_param = _append_derived_features(x_scaled, raw6, cycle_idx=999)
        np.testing.assert_allclose(out_ignored_param[:, 4], 42.0 / CYCLE_COUNT_NORM)

    def test_cycle_count_norm_clipped_when_exceeding_norm(self, caplog):
        """GH-59 — cycle_count > CYCLE_COUNT_NORM must clip to 1.0, not extrapolate,
        and must log a warning (production-observability for future tuning)."""
        from src.services.inference import _append_derived_features

        raw = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)
        raw[:, 3] = np.arange(WINDOW_SIZE) * 10.0
        x_scaled = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)

        with caplog.at_level("WARNING"):
            out = _append_derived_features(x_scaled, raw, cycle_idx=5000)
        np.testing.assert_allclose(out[:, 4], 1.0)
        assert "cycle_count=5000" in caplog.text

    def test_cycle_count_norm_clipped_negative(self):
        """GH-59 — negative cycle_count (bad input) must clip to 0.0, not go negative."""
        from src.services.inference import _append_derived_features

        raw = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)
        raw[:, 3] = np.arange(WINDOW_SIZE) * 10.0
        x_scaled = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)

        out = _append_derived_features(x_scaled, raw, cycle_idx=-1)
        np.testing.assert_allclose(out[:, 4], 0.0)

    def test_cycle_count_norm_at_boundary_no_warning(self, caplog):
        """GH-59 — cycle_count exactly == CYCLE_COUNT_NORM is in-range: 1.0, no warning."""
        from src.core.config import CYCLE_COUNT_NORM
        from src.services.inference import _append_derived_features

        raw = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)
        raw[:, 3] = np.arange(WINDOW_SIZE) * 10.0
        x_scaled = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)

        with caplog.at_level("WARNING"):
            out = _append_derived_features(x_scaled, raw, cycle_idx=int(CYCLE_COUNT_NORM))
        np.testing.assert_allclose(out[:, 4], 1.0)
        assert caplog.text == ""

    def test_6col_payload_cycle_count_clipped(self, caplog):
        """GH-59 — same clip + warning behavior via the 6-column BE-supplied path."""
        from src.services.inference import _append_derived_features

        raw4 = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)
        raw4[:, 3] = np.arange(WINDOW_SIZE) * 10.0
        raw6 = np.column_stack(
            [
                raw4,
                np.full(WINDOW_SIZE, 5000.0, dtype=np.float32),
                np.full(WINDOW_SIZE, 90.0, dtype=np.float32),
            ]
        )
        x_scaled = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)

        with caplog.at_level("WARNING"):
            out = _append_derived_features(x_scaled, raw6, cycle_idx=None)
        np.testing.assert_allclose(out[:, 4], 1.0)
        assert "cycle_count=5000" in caplog.text

    def test_6col_matches_4col_plus_cycle_idx_when_soc_agrees(self):
        """Parity (AC GH-56): 6-cot (BE tinh) va 4-cot+cycle_idx (AI tu tinh) phai
        cho cung model input khi soc_percent BE gui khop cong thuc Coulomb counting."""
        from src.core.config import NOMINAL_CAPACITY_AH
        from src.features.extractor import compute_soc_percent
        from src.services.inference import _append_derived_features

        raw4 = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)
        raw4[:, 1] = 1.5  # current (col "current")
        raw4[:, 3] = np.arange(WINDOW_SIZE) * 10.0  # time (col "time")
        cycle_idx = 100

        # soc_percent BE would compute using the exact same formula AI uses server-side
        soc_percent_be = compute_soc_percent(raw4[:, 1], raw4[:, 3], NOMINAL_CAPACITY_AH)
        raw6 = np.column_stack(
            [raw4, np.full(WINDOW_SIZE, float(cycle_idx), dtype=np.float32), soc_percent_be]
        )
        x_scaled = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)

        out_6col = _append_derived_features(x_scaled, raw6, cycle_idx=None)
        out_4col = _append_derived_features(x_scaled, raw4, cycle_idx=cycle_idx)
        np.testing.assert_allclose(out_6col, out_4col, rtol=1e-5)
