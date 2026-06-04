import numpy as np
import pytest

from src.features.extractor import extract_batch_features, extract_window_features


class TestExtractWindowFeatures:
    def test_output_shape(self):
        window = np.random.rand(30, 3).astype(np.float32)
        feats = extract_window_features(window)
        assert feats.shape == (54,), f"Expected (54,), got {feats.shape}"

    def test_output_dtype(self):
        window = np.random.rand(30, 3).astype(np.float32)
        assert extract_window_features(window).dtype == np.float32

    def test_no_nan_or_inf(self):
        window = np.random.rand(30, 3).astype(np.float32)
        feats = extract_window_features(window)
        assert not np.isnan(feats).any(), "NaN in features"
        assert not np.isinf(feats).any(), "Inf in features"

    def test_constant_signal_no_error(self):
        """Near-constant signals (std ≈ 0) must not raise or produce NaN."""
        window = np.ones((30, 3), dtype=np.float32) * 3.7
        feats = extract_window_features(window)
        assert not np.isnan(feats).any()
        assert not np.isinf(feats).any()

    def test_wrong_ndim_raises(self):
        with pytest.raises(ValueError):
            extract_window_features(np.random.rand(30))

    def test_different_signals_differ(self):
        """Healthy vs degraded signals should produce different feature vectors."""
        healthy   = np.random.rand(30, 3).astype(np.float32) * 0.1 + 0.9
        degraded  = np.random.rand(30, 3).astype(np.float32) * 0.5 + 0.3
        f_healthy  = extract_window_features(healthy)
        f_degraded = extract_window_features(degraded)
        assert not np.allclose(f_healthy, f_degraded)


class TestExtractBatchFeatures:
    def test_output_shape(self):
        windows = np.random.rand(16, 30, 3).astype(np.float32)
        feats = extract_batch_features(windows)
        assert feats.shape == (16, 54), f"Expected (16,54), got {feats.shape}"

    def test_no_nan_or_inf(self):
        windows = np.random.rand(8, 30, 3).astype(np.float32)
        feats = extract_batch_features(windows)
        assert not np.isnan(feats).any()
        assert not np.isinf(feats).any()

    def test_consistent_with_single(self):
        """batch[i] must equal extract_window_features(windows[i])."""
        windows = np.random.rand(4, 30, 3).astype(np.float32)
        batch_feats = extract_batch_features(windows)
        for i in range(4):
            single = extract_window_features(windows[i])
            np.testing.assert_array_almost_equal(batch_feats[i], single)
