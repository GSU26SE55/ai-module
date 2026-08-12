from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.core.config import WINDOW_SIZE
from src.models.soh_predictor import MambaSOHPredictor


def make_dummy_loader():
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import MinMaxScaler, StandardScaler

    from src.core.config import BASE_FEATURES, INPUT_FEATURES, SPECTRAL_FEAT_DIM

    scaler = MinMaxScaler()
    scaler.fit(np.random.rand(50, len(BASE_FEATURES)))  # GH-54: scaler = 4 base cols

    feat_scaler = StandardScaler()
    feat_scaler.fit(np.random.rand(50, SPECTRAL_FEAT_DIM))

    model = MambaSOHPredictor(
        input_features=INPUT_FEATURES,
        feat_dim=SPECTRAL_FEAT_DIM,
        d_model=8,
        d_state=4,
    )
    model.eval()

    iso = IsolationForest(n_estimators=10, random_state=42)
    iso.fit(np.random.rand(50, SPECTRAL_FEAT_DIM))

    return scaler, feat_scaler, model, iso


@pytest.fixture()
def client():
    scaler, feat_scaler, model, iso = make_dummy_loader()
    from src.core import model_loader

    with (
        patch("src.core.model_loader.load_models"),
        patch.object(model_loader, "scaler", scaler),
        patch.object(model_loader, "feature_scaler", feat_scaler),
        patch.object(model_loader, "soh_model", model),
        patch.object(model_loader, "iso_model", iso),
        patch.object(model_loader, "lfp_scaler", scaler),
        patch.object(model_loader, "lfp_feature_scaler", feat_scaler),
        patch.object(model_loader, "lfp_soh_model", model),
        patch.object(model_loader, "lfp_iso_model", iso),
    ):
        from main import app

        with patch("src.services.inference.model_loader") as mock_loader:
            mock_loader.scaler = scaler
            mock_loader.feature_scaler = feat_scaler
            mock_loader.soh_model = model
            mock_loader.iso_model = iso
            with TestClient(app) as c:
                yield c


class TestHealthRouter:
    def test_live(self, client):
        assert client.get("/live").json() == {"status": "live"}

    def test_ready(self, client):
        resp = client.get("/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"

    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "model_version" in data

    def test_ready_returns_503_when_required_model_is_missing(self, client):
        from src.core import model_loader

        with patch.object(model_loader, "soh_model", None):
            resp = client.get("/ready")
        assert resp.status_code == 503
        assert resp.json()["status"] == "not_ready"

    def test_health_model_loaded_flags(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert "scaler_loaded" in data
        assert "mamba_loaded" in data
        assert "isolation_forest_loaded" in data

    def test_health_exposes_soc_mode_per_artifact_set(self, client):
        """BE must read soc_mode from the server, not hardcode it by chemistry.

        Asserts the STRING type too: a wrong soc_percent is never rejected by
        /predict, it silently shifts SOH — so if this ever leaked a non-string
        (a mock, None) BE's branch would fall through to the wrong payload shape
        with no error anywhere.
        """
        data = client.get("/health").json()
        assert isinstance(data["soc_mode"], str)
        assert data["soc_mode"] in ("window", "cycle")
        # "" = LFP artifacts not loaded; "unknown" = artifact declared something
        # this build does not recognise. Both are strings the caller can branch on.
        assert isinstance(data["lfp_soc_mode"], str)
        assert data["lfp_soc_mode"] in ("", "window", "cycle", "unknown")

    def test_health_exposes_long_model_readiness(self, client):
        data = client.get("/health").json()
        assert isinstance(data["long_loaded"], bool)
        assert isinstance(data["long_model_version"], str)


class TestClassificationFeedbackRouter:
    """POST /predict/feedback — F4, khép vòng học nhánh anomaly."""

    @pytest.fixture(autouse=True)
    def _isolated_store(self, tmp_path, monkeypatch):
        # Mỗi test một file riêng: store là append-only toàn cục, dùng chung sẽ khiến
        # bộ đếm rò từ test này sang test khác và khẳng định về precision thành vô nghĩa.
        import src.services.classification_feedback as cf

        monkeypatch.setattr(cf, "FEEDBACK_DIR", str(tmp_path))
        monkeypatch.setattr(cf, "FEEDBACK_PATH", str(tmp_path / "feedback.jsonl"))

    def _payload(self, **over):
        base = {
            "battery_id": "B0005",
            "classification": "Degrading",
            "verdict": "correct",
        }
        base.update(over)
        return base

    def test_records_and_returns_counts(self, client):
        resp = client.post("/predict/feedback", json=self._payload())
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["total"] == 1
        assert data["correct"] == 1

    def test_precision_is_null_before_any_feedback_not_zero(self, client):
        """Chưa ai chấm ⇒ precision phải là null, KHÔNG phải 0.0.

        0.0 đọc thành "model sai hết" — kết luận ngược hẳn với sự thật "chưa có dữ liệu".
        Đây là chỗ một con số mặc định vô hại lại nói dối đúng lúc quan trọng nhất.
        """
        resp = client.post("/predict/feedback", json=self._payload(verdict="false_negative"))
        data = resp.json()
        # false_negative không vào mẫu số của precision ⇒ vẫn chưa tính được.
        assert data["precision"] is None
        assert data["recall"] == 0.0   # recall CÓ mẫu (tp=0, fn=1) ⇒ tính được, bằng 0

    def test_counts_accumulate_across_calls(self, client):
        client.post("/predict/feedback", json=self._payload(verdict="correct"))
        client.post("/predict/feedback", json=self._payload(verdict="correct"))
        resp = client.post("/predict/feedback", json=self._payload(verdict="false_positive"))
        data = resp.json()
        assert (data["total"], data["correct"], data["false_positive"]) == (3, 2, 1)
        assert data["precision"] == round(2 / 3, 3)

    def test_invalid_verdict_returns_422(self, client):
        resp = client.post("/predict/feedback", json=self._payload(verdict="maybe"))
        assert resp.status_code == 422

    def test_invalid_classification_returns_422(self, client):
        """Nhãn lạ phải bị TỪ CHỐI — file retrain lẫn nhãn rác tệ hơn file thiếu dòng."""
        resp = client.post("/predict/feedback", json=self._payload(classification="Broken"))
        assert resp.status_code == 422


class TestPredictLongRouter:
    """POST /predict/long — GH-10 long-sequence path."""

    def _rows(self, n):
        return [[3.7 + i * 0.0001, 1.5, 25.0, float(i)] for i in range(n)]

    def test_long_happy_path(self, client):
        fake = {
            "soh_percent": 88.5,
            "seq_len": 100,
            "device": "cpu",
            "inference_ms": 12.3,
            "model_version": "2.2",
        }
        with patch("src.routers.predict.predict_soh_long", return_value=fake):
            resp = client.post(
                "/predict/long",
                json={"battery_id": "B0005", "readings": self._rows(100)},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["battery_id"] == "B0005"
        assert data["soh_percent"] == 88.5
        assert data["model_version"] == "2.2"
        # The long path must NOT pretend to have the window=30 extras.
        for absent in ("confidence", "anomaly_score", "risk", "warnings"):
            assert absent not in data

    def test_long_rejects_exactly_window_size(self, client):
        """30 rows belongs to /predict — which also returns anomaly/risk.

        Accepting it here would hand back a bare SOH from a model that never saw
        sequences that short, and the caller would never know it took a worse path.
        """
        resp = client.post(
            "/predict/long",
            json={"battery_id": "B0005", "readings": self._rows(WINDOW_SIZE)},
        )
        assert resp.status_code == 422

    def test_long_rejects_over_max_seq_len(self, client):
        from src.core.config import LONG_SEQ_LEN

        resp = client.post(
            "/predict/long",
            json={"battery_id": "B0005", "readings": self._rows(LONG_SEQ_LEN + 1)},
        )
        assert resp.status_code == 422

    def test_long_applies_same_range_guard_as_predict(self, client):
        """A 12V pack without n_series must be rejected on BOTH paths.

        Same physical limits, one shared implementation — otherwise one transport
        accepts what the other rejects and the bug only shows up in production.
        """
        rows = self._rows(100)
        rows[0][0] = 12.0  # pack voltage, no pack_config
        resp = client.post(
            "/predict/long", json={"battery_id": "B0005", "readings": rows}
        )
        assert resp.status_code == 422
        assert "n_series" in resp.text

    def test_long_forwards_pack_config(self, client):
        rows = [[12.0, 1.5, 25.0, float(i)] for i in range(100)]
        fake = {
            "soh_percent": 90.0,
            "seq_len": 100,
            "device": "cpu",
            "inference_ms": 5.0,
            "model_version": "2.2",
        }
        with patch(
            "src.routers.predict.predict_soh_long", return_value=fake
        ) as mock_long:
            resp = client.post(
                "/predict/long",
                json={
                    "battery_id": "B0005",
                    "readings": rows,
                    "pack_config": {"n_series": 3, "capacity_ah": 50.0},
                },
            )
        assert resp.status_code == 200
        _, kwargs = mock_long.call_args
        assert kwargs["n_series"] == 3
        assert kwargs["capacity_ah"] == 50.0


class TestPredictRouter:
    def _valid_payload(self):
        return {
            "battery_id": "B0005",
            "readings": [
                [3.7 + i * 0.001, 1.5, 25.0, float(i)] for i in range(WINDOW_SIZE)
            ],
        }

    def test_predict_returns_200(self, client):
        resp = client.post("/predict/", json=self._valid_payload())
        assert resp.status_code == 200

    def test_predict_response_schema(self, client):
        resp = client.post("/predict/", json=self._valid_payload())
        data = resp.json()
        required = {
            "battery_id",
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
        for key in required:
            assert key in data, f"Missing key: {key}"
        assert "health_stage" in data["prediction"]
        assert "anomaly_status" in data["anomaly"]
        assert "risk_level" in data["risk"]
        assert "model_version" in data["metadata"]

    def test_predict_battery_id_echoed(self, client):
        resp = client.post("/predict/", json=self._valid_payload())
        assert resp.json()["battery_id"] == "B0005"

    def test_predict_invalid_shape_returns_422(self, client):
        payload = {
            "battery_id": "B0005",
            "readings": [[3.7, 1.5, 25.0]] * (WINDOW_SIZE - 1),
        }
        resp = client.post("/predict/", json=payload)
        assert resp.status_code == 422

    def test_predict_invalid_features_returns_422(self, client):
        payload = {"battery_id": "B0005", "readings": [[3.7, 1.5]] * WINDOW_SIZE}
        resp = client.post("/predict/", json=payload)
        assert resp.status_code == 422

    def test_predict_accepts_6col_payload(self, client):
        """GH-56 — BE gui cycle_count + soc_percent truc tiep (6 cot)."""
        payload = {
            "battery_id": "B0005",
            "readings": [
                [3.7 + i * 0.001, 1.5, 25.0, float(i), 42.0, 100.0 - i]
                for i in range(WINDOW_SIZE)
            ],
        }
        resp = client.post("/predict/", json=payload)
        assert resp.status_code == 200

    def test_predict_invalid_5col_returns_422(self, client):
        payload = {
            "battery_id": "B0005",
            "readings": [[3.7, 1.5, 25.0, float(i), 42.0] for i in range(WINDOW_SIZE)],
        }
        resp = client.post("/predict/", json=payload)
        assert resp.status_code == 422


class TestPackConfigRouter:
    """GH-65 pack→cell + GH-66 range guard through the REST endpoint."""

    def _pack_12v_payload(self):
        return {
            "battery_id": "PACK-12V",
            "readings": [
                [11.1 + i * 0.003, 1.5, 25.0, float(i)] for i in range(WINDOW_SIZE)
            ],
        }

    def test_12v_without_pack_config_rejected_with_hint(self, client):
        resp = client.post("/predict/", json=self._pack_12v_payload())
        assert resp.status_code == 422
        assert "pack_config" in resp.text

    def test_12v_with_n_series_3_ok_and_traced(self, client):
        payload = self._pack_12v_payload() | {"pack_config": {"n_series": 3}}
        resp = client.post("/predict/", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["metadata"]["n_series"] == 3
        # feature_summary reflects per-cell voltage (~3.7V), not pack voltage
        assert body["feature_summary"]["voltage"]["mean"] < 4.5

    def test_out_of_range_temperature_rejected(self, client):
        payload = self._pack_12v_payload() | {"pack_config": {"n_series": 3}}
        payload["readings"][5][2] = 75.0
        resp = client.post("/predict/", json=payload)
        assert resp.status_code == 422
        assert "temperature" in resp.text

    def test_nan_rejected(self, client):
        payload = self._pack_12v_payload() | {"pack_config": {"n_series": 3}}
        payload["readings"][0][1] = None  # JSON null → not a float → 422
        resp = client.post("/predict/", json=payload)
        assert resp.status_code == 422

    def test_prescribe_accepts_pack_config(self, client):
        payload = self._pack_12v_payload() | {"pack_config": {"n_series": 3}}
        resp = client.post("/prescribe/", json=payload)
        assert resp.status_code == 200

    def test_prescribe_blocked_llm_returns_200_rule_based(self, client):
        """GH-81: blocked LLM output → HTTP 200, blocked=true, rule-based fallback."""

        class FakeRetriever:
            def retrieve_maintenance(self, q, top_k=3):
                return []

            def retrieve_safety(self, q, top_k=2):
                return []

        banned = {
            "prescription": "Inspect the pack internals.",
            "action_steps": ["Open the battery casing to inspect the cells."],
            "ppe_required": [],
            "provider": "deepseek",
        }
        payload = self._pack_12v_payload() | {
            "pack_config": {"n_series": 3},
            "enrich": True,
        }
        with (
            patch(
                "src.services.prescription.orchestrator._get_retriever",
                return_value=FakeRetriever(),
            ),
            patch("src.services.prescription.llm.chain.is_available", return_value=True),
            patch(
                "src.services.prescription.llm.chain.generate_prescription",
                return_value=banned,
            ),
        ):
            resp = client.post("/prescribe/", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["blocked"] is True
        assert body["human_verification_required"] is True
        assert body["enriched"] is False
        assert "open the battery casing" not in " ".join(body["action_steps"]).lower()

    def test_prescribe_agentic_ignored_without_enrich(self, client):
        """GH-82: agentic=true without enrich → rule path, new fields defaulted."""
        payload = self._pack_12v_payload() | {
            "pack_config": {"n_series": 3},
            "agentic": True,
        }
        resp = client.post("/prescribe/", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["enriched"] is False
        assert body["query_gen_ms"] == 0.0
        assert body["generated_queries"] == []

    def test_prescribe_id_empty_on_rule_only_path(self, client):
        """GH-83: enrich=false never writes history — prescription_id stays ''."""
        payload = self._pack_12v_payload() | {"pack_config": {"n_series": 3}}
        resp = client.post("/prescribe/", json=payload)
        assert resp.status_code == 200
        assert resp.json()["prescription_id"] == ""

    def _get_prescription_id(self, client, tmp_path):
        """GH-83 test helper: run one enrich=true /prescribe/ call against a
        tmp_path-isolated history store and return the resulting prescription_id."""
        from src.services.prescription.history_store import PrescriptionHistoryStore

        class FakeRetriever:
            def retrieve_maintenance(self, q, top_k=3):
                return []

            def retrieve_safety(self, q, top_k=2):
                return []

        llm_out = {
            "prescription": "Schedule inspection.",
            "action_steps": ["Inspect terminals."],
            "ppe_required": [],
            "provider": "deepseek",
        }
        payload = self._pack_12v_payload() | {"pack_config": {"n_series": 3}, "enrich": True}
        store = PrescriptionHistoryStore(path=str(tmp_path))
        with (
            patch("src.services.prescription.orchestrator._get_retriever", return_value=FakeRetriever()),
            patch("src.services.prescription.orchestrator._get_history_store", return_value=store),
            patch("src.services.prescription.llm.chain.is_available", return_value=True),
            patch("src.services.prescription.llm.chain.generate_prescription", return_value=llm_out),
        ):
            resp = client.post("/prescribe/", json=payload)
            assert resp.status_code == 200
            prescription_id = resp.json()["prescription_id"]
            assert prescription_id
            return prescription_id, store

    def test_prescribe_feedback_accepted_returns_200(self, client, tmp_path):
        prescription_id, store = self._get_prescription_id(client, tmp_path)
        with patch("src.services.prescription.orchestrator._get_history_store", return_value=store):
            resp = client.post("/prescribe/feedback", json={
                "prescription_id": prescription_id, "status": "accepted",
            })
        assert resp.status_code == 200
        assert resp.json() == {"success": True}

    def test_prescribe_feedback_edited_with_steps_and_note(self, client, tmp_path):
        prescription_id, store = self._get_prescription_id(client, tmp_path)
        with patch("src.services.prescription.orchestrator._get_history_store", return_value=store):
            resp = client.post("/prescribe/feedback", json={
                "prescription_id": prescription_id,
                "status": "edited",
                "edited_steps": ["Corrected step."],
                "note": "Technician correction",
            })
        assert resp.status_code == 200
        assert resp.json() == {"success": True}

    def test_prescribe_feedback_rejected_returns_200(self, client, tmp_path):
        prescription_id, store = self._get_prescription_id(client, tmp_path)
        with patch("src.services.prescription.orchestrator._get_history_store", return_value=store):
            resp = client.post("/prescribe/feedback", json={
                "prescription_id": prescription_id, "status": "rejected",
            })
        assert resp.status_code == 200
        assert resp.json() == {"success": True}

    def test_prescribe_feedback_unknown_id_returns_404(self, client):
        resp = client.post("/prescribe/feedback", json={
            "prescription_id": "00000000-0000-0000-0000-000000000000",
            "status": "accepted",
        })
        assert resp.status_code == 404

    def test_prescribe_feedback_invalid_status_returns_422(self, client):
        resp = client.post("/prescribe/feedback", json={
            "prescription_id": "00000000-0000-0000-0000-000000000000",
            "status": "not-a-real-status",
        })
        assert resp.status_code == 422
