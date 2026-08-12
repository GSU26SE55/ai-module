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

    def test_causal_rate_escalates_classification(self):
        """GH-95: seeding a much-higher historical SOH forces causal_rate above
        RATE_THRESHOLD, which must escalate Normal -> Degrading. Uses a
        constant-output stub for soh_model/iso_model instead of the random
        untrained dummy_model — that one's output can land anywhere (e.g.
        clipped to 0.0 -> already "Failed", no room to demonstrate escalation)."""
        import torch

        from src.services import battery_history
        from src.services.inference import run_inference

        class ConstantSOHModel(torch.nn.Module):
            """Ignores input, always predicts soh=92% (comfortably 'Normal')."""

            def __init__(self):
                super().__init__()
                self.input_features = INPUT_FEATURES

            def forward(self, x, x_feat):
                return torch.full((x.shape[0],), 0.92)

        class ConstantIso:
            """Always reports a healthy score — classification driven by soh/rate only."""

            def decision_function(self, X):
                return np.full(len(X), 0.5)

        battery_id = "TEST-GH95-ESCALATE"
        battery_history._history.clear()

        from sklearn.preprocessing import MinMaxScaler, StandardScaler

        scaler = MinMaxScaler()
        scaler.fit(np.random.rand(50, BASE_N))
        feat_scaler = StandardScaler()
        feat_scaler.fit(np.random.rand(50, SPECTRAL_FEAT_DIM))

        with patch("src.services.inference.model_loader") as mock_loader:
            mock_loader.scaler = scaler
            mock_loader.feature_scaler = feat_scaler
            mock_loader.soh_model = ConstantSOHModel()
            mock_loader.iso_model = ConstantIso()

            baseline = run_inference(
                make_dummy_readings(), cycle_idx=5, battery_id=None
            )
            assert baseline["classification"] == "Normal"

            # Seed history far above the constant 92% prediction — guarantees
            # causal_rate > RATE_THRESHOLD.
            battery_history.record(battery_id, 0.0, 100.0)
            escalated = run_inference(
                make_dummy_readings(), cycle_idx=5, battery_id=battery_id
            )
            assert escalated["classification"] == "Degrading"

    def test_no_battery_id_behaves_as_before_gh95(self):
        from src.services.inference import run_inference

        result = run_inference(make_dummy_readings(), battery_id=None)
        assert result["classification"] in {"Normal", "Degrading", "Failed"}

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

    def test_stage_probabilities_consistent(self):
        """GH-86 — health_stage must be the argmax of stage_probabilities,
        stage_confidence its probability, and is_borderline the <0.7 flag."""
        from src.services.inference import run_inference

        result = run_inference(make_dummy_readings())
        prediction = result["prediction"]
        probs = prediction["stage_probabilities"]
        assert set(probs) == {"End Of Life", "Healthy"}
        assert abs(sum(probs.values()) - 1.0) < 1e-6
        assert probs[prediction["health_stage"]] == max(probs.values())
        assert prediction["stage_confidence"] == probs[prediction["health_stage"]]
        assert prediction["is_borderline"] == (prediction["stage_confidence"] < 0.7)

    def test_confidence_in_range(self):
        from src.services.inference import run_inference

        result = run_inference(make_dummy_readings())
        assert 0.0 <= result["confidence"] <= 1.0
        # confidence = soh_confidence (MC Dropout), anomaly_confidence = IF-based — different values
        assert 0.0 <= result["anomaly"]["anomaly_confidence"] <= 1.0

    def test_mc_dropout_batched_still_stochastic(self):
        """GH-62 — batching the 20 MC Dropout samples into one forward call must
        NOT collapse them to identical values (i.e. dropout masks still differ
        per row in the batch) — soh_std should be > 0, same as the old
        sequential-loop behaviour."""
        from src.services.inference import run_inference

        result = run_inference(make_dummy_readings())
        assert result["prediction"]["soh_std"] > 0.0

    def test_mc_dropout_batched_faster_than_naive_loop(self):
        """GH-62 — sanity-check the batched call is meaningfully faster than the
        old sequential python loop over the same model (not a hard SLA — that's
        scripts/benchmark_grpc.py's job — just confirms the optimization holds)."""
        import time

        import torch

        from src.services.inference import model_loader

        model = model_loader.soh_model
        x_tensor = torch.rand(1, 30, INPUT_FEATURES)
        x_feat_tensor = torch.rand(1, SPECTRAL_FEAT_DIM)
        model.train()
        try:
            with torch.no_grad():
                t0 = time.perf_counter()
                for _ in range(20):
                    model(x_tensor, x_feat_tensor)
                sequential_ms = (time.perf_counter() - t0) * 1000

                xb, xfb = x_tensor.repeat(20, 1, 1), x_feat_tensor.repeat(20, 1)
                t0 = time.perf_counter()
                model(xb, xfb)
                batched_ms = (time.perf_counter() - t0) * 1000
        finally:
            model.eval()
        assert batched_ms < sequential_ms

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

    def test_temperature_ood_flag_false_at_training_cluster(self):
        from src.services.inference import run_inference

        readings = [[3.7 + i * 0.001, 1.5, 24.0, float(i)] for i in range(WINDOW_SIZE)]
        result = run_inference(readings)
        assert result["metadata"]["is_temperature_ood"] is False
        assert result["metadata"]["temperature_domain_distance"] == 0.0
        assert "TEMP_OOD" not in [w["code"] for w in result["evidence"]["warnings"]]

    def test_temperature_ood_flag_true_between_clusters(self):
        from src.services.inference import run_inference

        # 15°C: motivating example from issue #91 — 9°C from nearest cluster (24°C)
        readings = [[3.7 + i * 0.001, 1.5, 15.0, float(i)] for i in range(WINDOW_SIZE)]
        result = run_inference(readings)
        assert result["metadata"]["is_temperature_ood"] is True
        assert result["metadata"]["temperature_domain_distance"] == 9.0
        assert "TEMP_OOD" in [w["code"] for w in result["evidence"]["warnings"]]

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

    @staticmethod
    def _art():
        """GH-67: _append_derived_features now takes the resolved artifact bundle so
        the model and its cycle_count divisor can't come from different sets. These
        tests exercise the DEFAULT (NASA) set — chemistry=None resolves to it."""
        from src.services.inference import _resolve_artifacts

        return _resolve_artifacts(None)

    def test_appends_two_columns_with_defaults(self):
        from src.services.inference import _append_derived_features

        raw = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)
        raw[:, 3] = np.arange(WINDOW_SIZE) * 10.0
        x_scaled = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)

        out = _append_derived_features(x_scaled, raw, cycle_idx=None, art=self._art())
        assert out.shape == (WINDOW_SIZE, INPUT_FEATURES)
        np.testing.assert_allclose(out[:, 4], 0.0)  # BE chua gui cycle_idx -> 0
        assert out[0, 5] == 1.0  # SOC window-local bat dau 100%

    def test_cycle_idx_normalized(self):
        from src.core.config import CYCLE_COUNT_NORM
        from src.services.inference import _append_derived_features

        raw = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)
        raw[:, 3] = np.arange(WINDOW_SIZE) * 10.0
        x_scaled = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)

        out = _append_derived_features(x_scaled, raw, cycle_idx=100, art=self._art())
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
            out = inf._append_derived_features(x_scaled, raw, cycle_idx=None, art=self._art())
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

        out = _append_derived_features(x_scaled, raw6, cycle_idx=None, art=self._art())
        assert out.shape == (WINDOW_SIZE, INPUT_FEATURES)
        np.testing.assert_allclose(out[:, 4], 42.0 / CYCLE_COUNT_NORM)
        np.testing.assert_allclose(out[:, 5], raw_soc_percent / 100.0)
        # cycle_idx param is ignored once the payload already carries 6 columns
        out_ignored_param = _append_derived_features(x_scaled, raw6, cycle_idx=999, art=self._art())
        np.testing.assert_allclose(out_ignored_param[:, 4], 42.0 / CYCLE_COUNT_NORM)

    def test_cycle_count_norm_clipped_when_exceeding_norm(self, caplog):
        """GH-59 — cycle_count > CYCLE_COUNT_NORM must clip to 1.0, not extrapolate,
        and must log a warning (production-observability for future tuning)."""
        from src.services.inference import _append_derived_features

        raw = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)
        raw[:, 3] = np.arange(WINDOW_SIZE) * 10.0
        x_scaled = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)

        with caplog.at_level("WARNING"):
            out = _append_derived_features(x_scaled, raw, cycle_idx=5000, art=self._art())
        np.testing.assert_allclose(out[:, 4], 1.0)
        assert "cycle_count=5000" in caplog.text

    def test_cycle_count_norm_clipped_negative(self):
        """GH-59 — negative cycle_count (bad input) must clip to 0.0, not go negative."""
        from src.services.inference import _append_derived_features

        raw = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)
        raw[:, 3] = np.arange(WINDOW_SIZE) * 10.0
        x_scaled = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)

        out = _append_derived_features(x_scaled, raw, cycle_idx=-1, art=self._art())
        np.testing.assert_allclose(out[:, 4], 0.0)

    def test_cycle_count_norm_at_boundary_no_warning(self, caplog):
        """GH-59 — cycle_count exactly == CYCLE_COUNT_NORM is in-range: 1.0, no warning."""
        from src.core.config import CYCLE_COUNT_NORM
        from src.services.inference import _append_derived_features

        raw = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)
        raw[:, 3] = np.arange(WINDOW_SIZE) * 10.0
        x_scaled = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)

        with caplog.at_level("WARNING"):
            out = _append_derived_features(x_scaled, raw, cycle_idx=int(CYCLE_COUNT_NORM), art=self._art())
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
            out = _append_derived_features(x_scaled, raw6, cycle_idx=None, art=self._art())
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

        out_6col = _append_derived_features(x_scaled, raw6, cycle_idx=None, art=self._art())
        out_4col = _append_derived_features(x_scaled, raw4, cycle_idx=cycle_idx, art=self._art())
        np.testing.assert_allclose(out_6col, out_4col, rtol=1e-5)


class TestPackToCell:
    """GH-65: n_series divides ONLY the voltage column, before scaler + warnings."""

    @pytest.fixture(autouse=True)
    def patch_model_loader(self):
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
        dummy_iso = IsolationForest(n_estimators=10, random_state=42)
        dummy_iso.fit(np.random.rand(50, SPECTRAL_FEAT_DIM))
        with patch("src.services.inference.model_loader") as mock_loader:
            mock_loader.scaler = dummy_scaler
            mock_loader.feature_scaler = dummy_feat_scaler
            mock_loader.soh_model = dummy_model
            mock_loader.iso_model = dummy_iso
            yield

    def test_voltage_divided_per_cell_in_feature_summary(self):
        from src.services.inference import run_inference

        cell_readings = make_dummy_readings()
        pack_readings = [[r[0] * 3, r[1], r[2], r[3]] for r in cell_readings]
        pack = run_inference(pack_readings, n_series=3)
        cell = run_inference(cell_readings)
        # voltage back to per-cell values; current/temperature untouched
        assert pack["feature_summary"]["voltage"]["mean"] == pytest.approx(
            cell["feature_summary"]["voltage"]["mean"], abs=1e-3
        )
        assert pack["feature_summary"]["current"] == cell["feature_summary"]["current"]
        assert (
            pack["feature_summary"]["temperature"]
            == cell["feature_summary"]["temperature"]
        )

    def test_metadata_traces_n_series(self):
        from src.services.inference import run_inference

        assert run_inference(make_dummy_readings())["metadata"]["n_series"] == 1
        pack = [[r[0] * 3, r[1], r[2], r[3]] for r in make_dummy_readings()]
        assert run_inference(pack, n_series=3)["metadata"]["n_series"] == 3

    def test_no_overvoltage_false_alarm_for_pack(self):
        from src.services.inference import run_inference

        pack = [[r[0] * 3, r[1], r[2], r[3]] for r in make_dummy_readings()]
        result = run_inference(pack, n_series=3)
        codes = [w["code"] for w in result["warnings"]]
        assert not any("OVERVOLTAGE" in c for c in codes), codes


class TestChemistryCapacity:
    """GH-67: capacity_ah rescales ONLY the current column to the NASA-2Ah
    C-rate equivalent; chemistry selects the voltage warning profile."""

    @pytest.fixture(autouse=True)
    def patch_model_loader(self):
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
        dummy_iso = IsolationForest(n_estimators=10, random_state=42)
        dummy_iso.fit(np.random.rand(50, SPECTRAL_FEAT_DIM))
        with patch("src.services.inference.model_loader") as mock_loader:
            mock_loader.scaler = dummy_scaler
            mock_loader.feature_scaler = dummy_feat_scaler
            mock_loader.soh_model = dummy_model
            mock_loader.iso_model = dummy_iso
            # GH-67: chemistry now ALSO selects the artifact set. These tests are
            # about the voltage-warning profile and the C-rate rescale, so point
            # the LFP set at the same dummies — artifact SELECTION is covered by
            # TestChemistryArtifactSelection below. Without this the MagicMock's
            # auto-created lfp_* attributes would be used as real scalers.
            mock_loader.lfp_scaler = dummy_scaler
            mock_loader.lfp_feature_scaler = dummy_feat_scaler
            mock_loader.lfp_soh_model = dummy_model
            mock_loader.lfp_iso_model = dummy_iso
            yield

    def test_current_rescaled_by_c_rate_in_feature_summary(self):
        from src.services.inference import run_inference

        cell_readings = make_dummy_readings()
        # same C-rate on a 50 Ah pack: current × 25, capacity 2 → 50
        pack_readings = [[r[0], r[1] * 25, r[2], r[3]] for r in cell_readings]
        pack = run_inference(pack_readings, capacity_ah=50.0)
        cell = run_inference(cell_readings)
        assert pack["feature_summary"]["current"]["mean"] == pytest.approx(
            cell["feature_summary"]["current"]["mean"], abs=1e-3
        )
        # voltage/temperature untouched by capacity_ah
        assert pack["feature_summary"]["voltage"] == cell["feature_summary"]["voltage"]
        assert (
            pack["feature_summary"]["temperature"]
            == cell["feature_summary"]["temperature"]
        )

    def test_metadata_traces_chemistry_and_capacity(self):
        from src.services.inference import run_inference

        base = run_inference(make_dummy_readings())["metadata"]
        assert base["chemistry"] is None
        assert base["capacity_ah"] is None
        lfp = run_inference(
            [[r[0] * 4, r[1], r[2], r[3]] for r in make_dummy_readings()],
            n_series=4,
            chemistry="LFP",
            capacity_ah=50.0,
        )["metadata"]
        assert lfp["chemistry"] == "LFP"
        assert lfp["capacity_ah"] == 50.0

    def test_no_overcurrent_false_alarm_for_high_capacity_pack(self):
        from src.services.inference import run_inference

        # 10 A discharge = 0.2C on a 50 Ah pack (NASA equivalent 0.4 A)
        readings = [[r[0], -10.0, r[2], r[3]] for r in make_dummy_readings()]
        with_capacity = run_inference(readings, capacity_ah=50.0)
        without = run_inference(readings)
        codes_with = [w["code"] for w in with_capacity["warnings"]]
        codes_without = [w["code"] for w in without["warnings"]]
        assert not any("OVERCURRENT" in c for c in codes_with), codes_with
        assert "OVERCURRENT_CRITICAL" in codes_without

    def test_lfp_4s_pack_no_false_voltage_warning(self):
        from src.services.inference import run_inference

        # 12.0 V pack / 4S = 3.00 V/cell — normal loaded LFP, but the NMC
        # profile flags it as VOLTAGE_LOW (approaching the 3.2 V NMC cutoff)
        readings = [[12.0, r[1], r[2], r[3]] for r in make_dummy_readings()]
        nmc = run_inference(readings, n_series=4)
        lfp = run_inference(readings, n_series=4, chemistry="LFP")
        assert "VOLTAGE_LOW" in [w["code"] for w in nmc["warnings"]]
        assert not any(
            "VOLTAGE" in w["code"] for w in lfp["warnings"]
        ), lfp["warnings"]


class TestChemistryArtifactSelection:
    """GH-67 — chemistry picks WHICH trained artifact set scores the request.

    Before this, chemistry only chose the voltage warning profile (Mức 1) while
    LFP telemetry was still scored with the NASA/NMC weights.
    """

    @staticmethod
    def _distinct_sets():
        """Two artifact sets whose models are distinguishable by their output."""
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import MinMaxScaler, StandardScaler

        def make(seed):
            import torch

            torch.manual_seed(seed)
            sc = MinMaxScaler().fit(np.random.RandomState(seed).rand(50, BASE_N))
            fs = StandardScaler().fit(np.random.RandomState(seed).rand(50, SPECTRAL_FEAT_DIM))
            m = MambaSOHPredictor(
                input_features=INPUT_FEATURES, feat_dim=SPECTRAL_FEAT_DIM,
                d_model=8, d_state=4,
            )
            m.eval()
            iso = IsolationForest(n_estimators=10, random_state=seed).fit(
                np.random.RandomState(seed).rand(50, SPECTRAL_FEAT_DIM)
            )
            return sc, fs, m, iso

        return make(1), make(99)

    def test_lfp_chemistry_resolves_lfp_bundle_and_divisor(self):
        from src.core.config import CYCLE_COUNT_NORM, LFP_CYCLE_COUNT_NORM
        from src.services.inference import _resolve_artifacts

        (nsc, nfs, nm, niso), (lsc, lfs, lm, liso) = self._distinct_sets()
        with patch("src.services.inference.model_loader") as ml:
            ml.scaler, ml.feature_scaler, ml.soh_model, ml.iso_model = nsc, nfs, nm, niso
            ml.lfp_scaler, ml.lfp_feature_scaler = lsc, lfs
            ml.lfp_soh_model, ml.lfp_iso_model = lm, liso

            lfp = _resolve_artifacts("LFP")
            assert lfp.soh_model is lm and lfp.scaler is lsc
            assert lfp.iso_model is liso and lfp.feature_scaler is lfs
            assert lfp.artifact_set == "LFP"
            # The divisor MUST travel with the weights: LFP cells (Severson + SNL)
            # run to ~4600 cycles, NASA to ~197. Mixing them silently shifts an
            # input channel. Value = `cycle_count_norm` in scaler_lfp.pkl.
            assert lfp.cycle_count_norm == LFP_CYCLE_COUNT_NORM == 4600.0

            for chem in (None, "NMC", "unknown"):
                nasa = _resolve_artifacts(chem)
                assert nasa.soh_model is nm, f"chemistry={chem!r} must keep NASA weights"
                assert nasa.cycle_count_norm == CYCLE_COUNT_NORM == 200.0
                assert nasa.artifact_set == "NASA"

    def test_lfp_requested_but_not_loaded_raises_instead_of_silent_fallback(self):
        from src.services.inference import _resolve_artifacts

        (nsc, nfs, nm, niso), _ = self._distinct_sets()
        with patch("src.services.inference.model_loader") as ml:
            ml.scaler, ml.feature_scaler, ml.soh_model, ml.iso_model = nsc, nfs, nm, niso
            ml.lfp_soh_model = None  # artifacts absent (NASA-only deploy)

            with pytest.raises(RuntimeError, match="chemistry='LFP'"):
                _resolve_artifacts("LFP")
            # and the default path still works — a missing LFP set must not break
            # batteries that never asked for it
            assert _resolve_artifacts(None).soh_model is nm

    def test_metadata_reports_which_artifact_set_ran(self):
        from src.core.config import LFP_MODEL_VERSION, MODEL_VERSION
        from src.services.inference import run_inference

        (nsc, nfs, nm, niso), (lsc, lfs, lm, liso) = self._distinct_sets()
        readings = np.random.rand(WINDOW_SIZE, BASE_N).astype(np.float32)
        readings[:, 0] = np.linspace(3.35, 2.95, WINDOW_SIZE)  # per-cell LFP volts
        readings[:, 1] = -1.0
        readings[:, 2] = 30.0
        readings[:, 3] = np.arange(WINDOW_SIZE) * 10.0

        with patch("src.services.inference.model_loader") as ml:
            ml.scaler, ml.feature_scaler, ml.soh_model, ml.iso_model = nsc, nfs, nm, niso
            ml.lfp_scaler, ml.lfp_feature_scaler = lsc, lfs
            ml.lfp_soh_model, ml.lfp_iso_model = lm, liso

            nasa = run_inference(readings.tolist())
            lfp = run_inference(readings.tolist(), chemistry="LFP")

        assert nasa["metadata"]["artifact_set"] == "NASA"
        assert nasa["metadata"]["model_version"] == MODEL_VERSION
        assert lfp["metadata"]["artifact_set"] == "LFP"
        assert lfp["metadata"]["model_version"] == LFP_MODEL_VERSION


class TestSocModeGuard:
    """GH-67: artifacts trained with soc_mode='cycle' need the 6-column payload.

    The window-local fallback defines SOC relative to the window, so it always
    starts at 100% and spans ~[0.91, 1.0]; the LFP artifacts were trained on soc
    spanning the whole discharge (~[0.09, 1.0]). A stateless 30-row window cannot
    reconstruct the real value, so this must fail loudly instead of silently
    shifting that input channel.
    """

    def _art(self, soc_mode, model_dim=6):
        from src.services import inference

        class _M:
            input_features = model_dim

        return inference._Artifacts(
            scaler=None, feature_scaler=None, soh_model=_M(), iso_model=None,
            cycle_count_norm=4600.0, artifact_set="LFP",
            model_version="2.1-lfp", soc_mode=soc_mode,
        )

    def _payload(self, n_cols):
        return np.array(
            [[3.3, -4.0, 30.0, float(i), 900.0, 80.0][:n_cols] for i in range(30)],
            dtype=np.float32,
        )

    def test_cycle_mode_rejects_4_column_payload(self):
        from src.services import inference
        raw = self._payload(4)
        x_scaled = raw[:, :4]
        with pytest.raises(ValueError, match="soc_mode='cycle'"):
            inference._append_derived_features(x_scaled, raw, None, self._art("cycle"))

    def test_cycle_mode_accepts_6_column_payload(self):
        from src.services import inference
        raw = self._payload(6)
        x_scaled = raw[:, :4]
        out = inference._append_derived_features(x_scaled, raw, None, self._art("cycle"))
        assert out.shape == (30, 6)
        # soc comes straight from BE's column 6 (80%), not the window-local estimate
        assert np.allclose(out[:, 5], 0.8)

    def test_window_mode_still_accepts_4_column_payload(self):
        """Back-compat: NASA artifacts (soc_mode='window') are unaffected."""
        from src.services import inference
        raw = self._payload(4)
        x_scaled = raw[:, :4]
        out = inference._append_derived_features(x_scaled, raw, None, self._art("window"))
        assert out.shape == (30, 6)
        assert out[0, 5] == pytest.approx(1.0)  # window-local SOC starts at 100%
