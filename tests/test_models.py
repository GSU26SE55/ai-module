import torch

from src.core.config import INPUT_FEATURES
from src.models.anomaly_detector import classify_anomaly
from src.models.soh_predictor import MambaSOHPredictor


class TestMambaSOHPredictor:
    def test_output_shape_single(self):
        model = MambaSOHPredictor(input_features=INPUT_FEATURES)
        model.eval()
        x = torch.randn(1, 30, INPUT_FEATURES)
        with torch.no_grad():
            out = model(x)
        assert out.shape == (1,), f"Expected (1,), got {out.shape}"

    def test_output_shape_batch(self):
        model = MambaSOHPredictor(input_features=INPUT_FEATURES)
        model.eval()
        x = torch.randn(8, 30, INPUT_FEATURES)
        with torch.no_grad():
            out = model(x)
        assert out.shape == (8,), f"Expected (8,), got {out.shape}"

    def test_output_is_float(self):
        model = MambaSOHPredictor(input_features=INPUT_FEATURES)
        model.eval()
        x = torch.randn(2, 30, INPUT_FEATURES)
        with torch.no_grad():
            out = model(x)
        assert out.dtype == torch.float32

    def test_gradients_flow(self):
        model = MambaSOHPredictor(input_features=INPUT_FEATURES)
        x = torch.randn(2, 30, INPUT_FEATURES)
        out = model(x)
        loss = out.sum()
        loss.backward()
        grads = [p.grad for p in model.parameters() if p.grad is not None]
        assert len(grads) > 0, "No gradients computed"


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
