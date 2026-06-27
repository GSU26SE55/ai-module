import numpy as np
import pytest
import torch

from scripts.train import load_split
from src.core.config import FEATURE_SCALER_VERSION, WINDOW_SIZE


class TestWindowUtils:
    def test_window_size(self):
        """A valid reading sequence must have exactly WINDOW_SIZE timesteps."""
        readings = [[3.7, 1.5, 25.0, 1.0, 3.5, 12.0]] * WINDOW_SIZE
        assert len(readings) == WINDOW_SIZE
        assert all(len(r) == 6 for r in readings)

    def test_invalid_window_size_raises(self):
        """PredictRequest validator must reject sequences != WINDOW_SIZE timesteps."""
        from pydantic import ValidationError

        from src.schemas.predict import PredictRequest

        with pytest.raises(ValidationError, match=f"{WINDOW_SIZE} timesteps"):
            PredictRequest(battery_id="B0005", readings=[[3.7, 1.5, 25.0, 1.0, 3.5, 12.0]] * (WINDOW_SIZE - 1))

    def test_invalid_feature_count_raises(self):
        """PredictRequest validator must reject rows with unsupported feature count."""
        from pydantic import ValidationError

        from src.schemas.predict import PredictRequest

        with pytest.raises(ValidationError, match="feature counts"):
            PredictRequest(battery_id="B0005", readings=[[3.7, 1.5]] * WINDOW_SIZE)

    def test_valid_request_passes(self):
        from src.schemas.predict import PredictRequest

        req = PredictRequest(
            battery_id="B0005",
            readings=[[3.7, 1.5, 25.0, 1.0, 3.5, 12.0]] * WINDOW_SIZE,
        )
        assert req.battery_id == "B0005"
        assert len(req.readings) == WINDOW_SIZE

    def test_legacy_three_feature_request_passes(self):
        from src.schemas.predict import PredictRequest

        req = PredictRequest(battery_id="B0005", readings=[[3.7, 1.5, 25.0]] * WINDOW_SIZE)
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


class TestProcessedFeatureVersion:
    def test_load_split_accepts_current_feature_version(self, tmp_path):
        path = tmp_path / "train.pt"
        torch.save(
            {
                "X": torch.zeros(1, WINDOW_SIZE, 6),
                "X_feat": torch.zeros(1, 57),
                "y": torch.zeros(1),
                "feature_scaler_version": FEATURE_SCALER_VERSION,
            },
            path,
        )
        X, X_feat, y = load_split(str(path))
        assert X.shape == (1, WINDOW_SIZE, 6)
        assert X_feat.shape == (1, 57)
        assert y.shape == (1,)

    def test_load_split_rejects_stale_feature_version(self, tmp_path):
        path = tmp_path / "train.pt"
        torch.save(
            {
                "X": torch.zeros(1, WINDOW_SIZE, 6),
                "X_feat": torch.zeros(1, 57),
                "y": torch.zeros(1),
                "feature_scaler_version": "0.9",  # outdated — should trigger mismatch
            },
            path,
        )
        with pytest.raises(ValueError, match="feature version mismatch"):
            load_split(str(path))


class _IdentityScaler:
    """Stub MinMaxScaler — transform is identity (raw scaling tested elsewhere)."""

    def transform(self, x):
        return np.asarray(x, dtype=np.float32)


class TestLongWindows:
    """GH-10: concatenated long-sequence windowing (scripts/preprocess_long.py)."""

    def test_window_count_and_shape(self):
        from scripts.preprocess_long import make_long_windows

        T, seq_len, stride = 40, 8, 4
        X_raw  = np.random.RandomState(42).rand(T, 6).astype(np.float32)
        soh_ts = np.arange(T, dtype=np.float32)  # distinct per timestep

        X, F, y = make_long_windows(X_raw, soh_ts, _IdentityScaler(), seq_len, stride)

        expected_n = (T - seq_len) // stride + 1
        assert X.shape == (expected_n, seq_len, 6)
        assert F.shape == (expected_n, 57)
        assert y.shape == (expected_n,)

    def test_label_is_last_timestep_soh(self):
        from scripts.preprocess_long import make_long_windows

        T, seq_len, stride = 40, 8, 4
        X_raw  = np.random.RandomState(0).rand(T, 6).astype(np.float32)
        soh_ts = np.arange(T, dtype=np.float32)

        _, _, y = make_long_windows(X_raw, soh_ts, _IdentityScaler(), seq_len, stride)

        # First window ends at index seq_len-1; each subsequent shifts by stride.
        expected = [float(seq_len - 1 + i * stride) for i in range(len(y))]
        assert y.tolist() == expected

    def test_short_timeline_returns_empty(self):
        from scripts.preprocess_long import make_long_windows

        X_raw  = np.random.RandomState(1).rand(5, 6).astype(np.float32)
        soh_ts = np.zeros(5, dtype=np.float32)

        X, F, y = make_long_windows(X_raw, soh_ts, _IdentityScaler(), seq_len=8, stride=4)
        assert len(X) == 0 and len(F) == 0 and len(y) == 0
        assert X.shape == (0, 8, 6)
