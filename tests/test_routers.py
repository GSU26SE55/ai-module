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
    with patch("src.core.model_loader.load_models"):
        from main import app

        with patch("src.services.inference.model_loader") as mock_loader:
            mock_loader.scaler = scaler
            mock_loader.feature_scaler = feat_scaler
            mock_loader.soh_model = model
            mock_loader.iso_model = iso
            with TestClient(app) as c:
                yield c


class TestHealthRouter:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "model_version" in data

    def test_health_model_loaded_flags(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert "scaler_loaded" in data
        assert "mamba_loaded" in data
        assert "isolation_forest_loaded" in data


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
