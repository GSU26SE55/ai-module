import numpy as np
import pytest
import torch

from scripts.train import load_split
from src.core.config import (
    BASE_FEATURES,
    FEATURE_SCALER_VERSION,
    SPECTRAL_FEAT_DIM,
    WINDOW_SIZE,
)


class TestWindowUtils:
    def test_window_size(self):
        """A valid reading sequence must have exactly WINDOW_SIZE timesteps."""
        readings = [[3.7, 1.5, 25.0, 12.0]] * WINDOW_SIZE
        assert len(readings) == WINDOW_SIZE
        assert all(len(r) == len(BASE_FEATURES) for r in readings)

    def test_invalid_window_size_raises(self):
        """PredictRequest validator must reject sequences != WINDOW_SIZE timesteps."""
        from pydantic import ValidationError

        from src.schemas.predict import PredictRequest

        with pytest.raises(ValidationError, match=f"{WINDOW_SIZE} timesteps"):
            PredictRequest(
                battery_id="B0005",
                readings=[[3.7, 1.5, 25.0, 12.0]] * (WINDOW_SIZE - 1),
            )

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
            readings=[[3.7, 1.5, 25.0, 12.0]] * WINDOW_SIZE,
        )
        assert req.battery_id == "B0005"
        assert len(req.readings) == WINDOW_SIZE

    def test_legacy_three_feature_request_passes(self):
        from src.schemas.predict import PredictRequest

        req = PredictRequest(
            battery_id="B0005", readings=[[3.7, 1.5, 25.0]] * WINDOW_SIZE
        )
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
        X_raw = np.random.RandomState(42).rand(T, 6).astype(np.float32)
        soh_ts = np.arange(T, dtype=np.float32)  # distinct per timestep

        X, F, y = make_long_windows(X_raw, soh_ts, _IdentityScaler(), seq_len, stride)

        expected_n = (T - seq_len) // stride + 1
        assert X.shape == (expected_n, seq_len, 6)
        assert F.shape == (expected_n, 57)
        assert y.shape == (expected_n,)

    def test_label_is_last_timestep_soh(self):
        from scripts.preprocess_long import make_long_windows

        T, seq_len, stride = 40, 8, 4
        X_raw = np.random.RandomState(0).rand(T, 6).astype(np.float32)
        soh_ts = np.arange(T, dtype=np.float32)

        _, _, y = make_long_windows(X_raw, soh_ts, _IdentityScaler(), seq_len, stride)

        # First window ends at index seq_len-1; each subsequent shifts by stride.
        expected = [float(seq_len - 1 + i * stride) for i in range(len(y))]
        assert y.tolist() == expected

    def test_short_timeline_returns_empty(self):
        from scripts.preprocess_long import make_long_windows

        X_raw = np.random.RandomState(1).rand(5, 6).astype(np.float32)
        soh_ts = np.zeros(5, dtype=np.float32)

        X, F, y = make_long_windows(
            X_raw, soh_ts, _IdentityScaler(), seq_len=8, stride=4
        )
        assert len(X) == 0 and len(F) == 0 and len(y) == 0
        assert X.shape == (0, 8, 6)


class TestGh54DerivedColumns:
    """GH-54 — cycles_to_windows appends cycle_count + soc as columns 5-6."""

    def _make_cycle(self, n=60):
        rng = np.random.RandomState(42)
        cycle = rng.rand(n, 4).astype(np.float32)
        cycle[:, 3] = np.arange(n, dtype=np.float32) * 10.0  # time (s)
        return cycle

    def test_windows_have_six_columns(self):
        from sklearn.preprocessing import MinMaxScaler

        from scripts.preprocess import cycles_to_windows
        from src.core.config import CYCLE_COUNT_NORM

        cycle = self._make_cycle(60)
        scaler = MinMaxScaler().fit(cycle)
        X, X_feat, y = cycles_to_windows([(cycle, 95.0, 4)], scaler)

        assert X.shape == (2, WINDOW_SIZE, 6)  # 60 steps / stride 30 = 2 windows
        # column 5: cycle_count_norm = 4/200, constant across the window
        np.testing.assert_allclose(X[:, :, 4], 4 / CYCLE_COUNT_NORM, atol=1e-6)
        # column 6: soc_norm starts at exactly 1.0 in EVERY window (window-local)
        np.testing.assert_allclose(X[:, 0, 5], 1.0)
        assert (X[:, :, 5] <= 1.0).all() and (X[:, :, 5] >= 0.0).all()

    def test_soc_recomputed_per_window(self):
        """Window 2 must restart at SOC=1.0, not continue from window 1."""
        from sklearn.preprocessing import MinMaxScaler

        from scripts.preprocess import cycles_to_windows

        cycle = self._make_cycle(60)
        cycle[:, 1] = 2.0  # constant discharge current
        scaler = MinMaxScaler().fit(cycle)
        X, _, _ = cycles_to_windows([(cycle, 95.0, 0)], scaler)
        assert X[0, 0, 5] == 1.0 and X[1, 0, 5] == 1.0
        assert X[0, -1, 5] < 1.0  # drained within the window


class TestGh58PerWindowSpectralFeatures:
    """GH-58 — X_feat must be computed PER WINDOW, matching run_inference()'s
    extract_window_features(x_scaled[:, :3]) call on just the received window.
    A prior version computed X_feat once on the FULL cycle and shared it across
    every window sliced from that cycle — causing severe train/serve skew
    (StandardScaler outliers up to -20 at inference vs the ~[-3, 3] range seen
    in training). This test would have FAILED under that prior behaviour, since
    all windows of a cycle used to share an identical X_feat row."""

    def test_different_windows_get_different_features(self):
        from sklearn.preprocessing import MinMaxScaler

        from scripts.preprocess import cycles_to_windows

        n = 90  # 3 windows of 30
        rng = np.random.RandomState(42)
        cycle = rng.rand(n, 4).astype(np.float32)
        cycle[:, 3] = np.arange(n, dtype=np.float32) * 10.0  # time
        # Give each window a distinctly different voltage pattern so their
        # spectral/statistical features cannot coincidentally match.
        t = np.arange(30, dtype=np.float32)
        cycle[0:30, 0] = 3.7 + 0.05 * np.sin(t)  # oscillating
        cycle[30:60, 0] = np.linspace(3.7, 3.2, 30)  # linear ramp
        cycle[60:90, 0] = 3.5  # flat

        scaler = MinMaxScaler().fit(cycle)
        X, X_feat, y = cycles_to_windows([(cycle, 90.0, 0)], scaler)

        assert X_feat.shape == (3, SPECTRAL_FEAT_DIM)
        assert not np.allclose(X_feat[0], X_feat[1])
        assert not np.allclose(X_feat[1], X_feat[2])
        assert not np.allclose(X_feat[0], X_feat[2])

    def test_matches_inference_feature_extraction(self):
        """Same scaled window fed to preprocess's per-window path and to
        run_inference()'s extractor must produce identical features."""
        from sklearn.preprocessing import MinMaxScaler

        from scripts.preprocess import cycles_to_windows
        from src.features.extractor import extract_window_features

        rng = np.random.RandomState(42)
        cycle = rng.rand(WINDOW_SIZE, 4).astype(np.float32)  # exactly 1 window
        cycle[:, 3] = np.arange(WINDOW_SIZE, dtype=np.float32) * 10.0  # time
        scaler = MinMaxScaler().fit(cycle)
        _, X_feat, _ = cycles_to_windows([(cycle, 95.0, 0)], scaler)

        x_scaled = scaler.transform(cycle)
        expected = extract_window_features(x_scaled[:, :3])
        np.testing.assert_allclose(X_feat[0], expected)
