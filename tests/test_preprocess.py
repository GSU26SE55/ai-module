import pytest


class TestWindowUtils:
    def test_window_size_30(self):
        """A valid reading sequence must have exactly 30 timesteps."""
        readings = [[3.7, 1.5, 25.0, 1.0, 3.5, 12.0]] * 30
        assert len(readings) == 30
        assert all(len(r) == 6 for r in readings)

    def test_invalid_window_size_raises(self):
        """PredictRequest validator must reject sequences != 30 timesteps."""
        from pydantic import ValidationError

        from src.schemas.predict import PredictRequest

        with pytest.raises(ValidationError, match="30 timesteps"):
            PredictRequest(battery_id="B0005", readings=[[3.7, 1.5, 25.0, 1.0, 3.5, 12.0]] * 29)

    def test_invalid_feature_count_raises(self):
        """PredictRequest validator must reject rows with unsupported feature count."""
        from pydantic import ValidationError

        from src.schemas.predict import PredictRequest

        with pytest.raises(ValidationError, match="feature counts"):
            PredictRequest(battery_id="B0005", readings=[[3.7, 1.5]] * 30)

    def test_valid_request_passes(self):
        from src.schemas.predict import PredictRequest

        req = PredictRequest(
            battery_id="B0005",
            readings=[[3.7, 1.5, 25.0, 1.0, 3.5, 12.0]] * 30,
        )
        assert req.battery_id == "B0005"
        assert len(req.readings) == 30

    def test_legacy_three_feature_request_passes(self):
        from src.schemas.predict import PredictRequest

        req = PredictRequest(battery_id="B0005", readings=[[3.7, 1.5, 25.0]] * 30)
        assert len(req.readings[0]) == 3


class TestSOHFormula:
    def test_soh_100_at_nominal(self):
        nominal = 2.0
        current = 2.0
        soh = current / nominal * 100
        assert soh == pytest.approx(100.0)

    def test_soh_decreases_with_capacity(self):
        nominal = 2.0
        assert (1.8 / nominal * 100) < (2.0 / nominal * 100)

    def test_soh_80_threshold(self):
        nominal = 2.0
        capacity_at_80 = 1.6
        soh = capacity_at_80 / nominal * 100
        assert soh == pytest.approx(80.0)
