from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.models.soh_predictor import MambaSOHPredictor


def make_dummy_loader():
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import MinMaxScaler

    scaler = MinMaxScaler()
    scaler.fit(np.random.rand(50, 3))

    model = MambaSOHPredictor()
    model.eval()

    iso = IsolationForest(n_estimators=10, random_state=42)
    iso.fit(np.random.rand(50, 90))

    return scaler, model, iso


@pytest.fixture()
def client():
    scaler, model, iso = make_dummy_loader()
    with patch("src.core.model_loader.load_models"):
        from main import app

        with patch("src.services.inference.model_loader") as mock_loader:
            mock_loader.scaler = scaler
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
            "readings": [[3.7 + i * 0.001, 1.5, 25.0] for i in range(30)],
        }

    def test_predict_returns_200(self, client):
        resp = client.post("/predict/", json=self._valid_payload())
        assert resp.status_code == 200

    def test_predict_response_schema(self, client):
        resp = client.post("/predict/", json=self._valid_payload())
        data = resp.json()
        assert "battery_id" in data
        assert "soh_percent" in data
        assert "classification" in data
        assert "confidence" in data
        assert "inference_ms" in data

    def test_predict_battery_id_echoed(self, client):
        resp = client.post("/predict/", json=self._valid_payload())
        assert resp.json()["battery_id"] == "B0005"

    def test_predict_invalid_shape_returns_422(self, client):
        payload = {"battery_id": "B0005", "readings": [[3.7, 1.5, 25.0]] * 29}
        resp = client.post("/predict/", json=payload)
        assert resp.status_code == 422

    def test_predict_invalid_features_returns_422(self, client):
        payload = {"battery_id": "B0005", "readings": [[3.7, 1.5]] * 30}
        resp = client.post("/predict/", json=payload)
        assert resp.status_code == 422
