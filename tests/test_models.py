import torch

from src.models.anomaly_detector import classify_anomaly
from src.models.soh_predictor import SOHPredictor


class TestSOHPredictor:
    def test_output_shape_single(self):
        model = SOHPredictor()
        model.eval()
        x = torch.randn(1, 30, 3)
        with torch.no_grad():
            out = model(x)
        assert out.shape == (1,), f"Expected (1,), got {out.shape}"

    def test_output_shape_batch(self):
        model = SOHPredictor()
        model.eval()
        x = torch.randn(8, 30, 3)
        with torch.no_grad():
            out = model(x)
        assert out.shape == (8,), f"Expected (8,), got {out.shape}"

    def test_output_is_float(self):
        model = SOHPredictor()
        model.eval()
        x = torch.randn(2, 30, 3)
        with torch.no_grad():
            out = model(x)
        assert out.dtype == torch.float32


class TestClassifyAnomaly:
    def test_normal(self):
        assert classify_anomaly(0.0, 95.0) == "Normal"
        assert classify_anomaly(-0.05, 90.0) == "Normal"

    def test_degrading_by_score(self):
        assert classify_anomaly(-0.2, 75.0) == "Degrading"

    def test_degrading_by_soh(self):
        # SOH >= 80 → Degrading even if score is bad
        assert classify_anomaly(-0.5, 85.0) == "Degrading"

    def test_failed(self):
        assert classify_anomaly(-0.5, 60.0) == "Failed"

    def test_boundary_score(self):
        # Exactly -0.1 → not > -0.1, so Degrading or Failed depending on SOH
        assert classify_anomaly(-0.1, 70.0) == "Degrading"
