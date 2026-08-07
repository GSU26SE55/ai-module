import numpy as np
import pytest

from src.features.extractor import (
    _spectral_features,
    extract_batch_features,
    extract_window_features,
)


class TestExtractWindowFeatures:
    def test_output_shape(self):
        window = np.random.rand(30, 3).astype(np.float32)
        feats = extract_window_features(window)
        assert feats.shape == (57,), f"Expected (57,), got {feats.shape}"

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
        healthy = np.random.rand(30, 3).astype(np.float32) * 0.1 + 0.9
        degraded = np.random.rand(30, 3).astype(np.float32) * 0.5 + 0.3
        f_healthy = extract_window_features(healthy)
        f_degraded = extract_window_features(degraded)
        assert not np.allclose(f_healthy, f_degraded)

    def test_long_sequence_shape(self):
        window = np.random.rand(4096, 3).astype(np.float32)
        assert extract_window_features(window).shape == (57,)

    def test_spectral_kurtosis_responds_to_transient(self):
        smooth = np.sin(np.linspace(0, 16 * np.pi, 4096)).astype(np.float32)
        transient = smooth.copy()
        transient[2048] += 20.0
        smooth_kurtosis = _spectral_features(smooth)[3]
        transient_kurtosis = _spectral_features(transient)[3]
        assert transient_kurtosis != pytest.approx(smooth_kurtosis)

    def test_spectral_slope_responds_to_frequency_content(self):
        t = np.arange(4096, dtype=np.float32)
        low_frequency = np.sin(2 * np.pi * 8 * t / len(t))
        high_frequency = np.sin(2 * np.pi * 256 * t / len(t))
        low_slope = _spectral_features(low_frequency)[2]
        high_slope = _spectral_features(high_frequency)[2]
        assert high_slope != pytest.approx(low_slope)


class TestExtractBatchFeatures:
    def test_output_shape(self):
        windows = np.random.rand(16, 30, 3).astype(np.float32)
        feats = extract_batch_features(windows)
        assert feats.shape == (16, 57), f"Expected (16,57), got {feats.shape}"

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


class TestComputeSocPercent:
    """GH-54 — window-local Coulomb-counting SOC."""

    def test_zero_current_stays_100(self):
        from src.features.extractor import compute_soc_percent

        current = np.zeros(30, dtype=np.float32)
        time = np.arange(30, dtype=np.float32) * 10.0
        soc = compute_soc_percent(current, time)
        np.testing.assert_allclose(soc, 100.0)

    def test_constant_current_matches_hand_calc(self):
        from src.features.extractor import compute_soc_percent

        # |I| = 1 A constant, 1 gio (3600s) -> 1 Ah drawn / 2 Ah nominal = 50%
        current = np.full(31, -1.0, dtype=np.float32)  # discharge (am) — dung |I|
        time = np.linspace(0.0, 3600.0, 31).astype(np.float32)
        soc = compute_soc_percent(current, time, nominal_capacity_ah=2.0)
        assert soc[0] == 100.0
        np.testing.assert_allclose(soc[-1], 50.0, atol=1e-3)
        # nua duong (0.5h) -> 25% da xa -> SOC 75%
        np.testing.assert_allclose(soc[15], 75.0, atol=1e-3)

    def test_clipped_at_zero_and_shape_dtype(self):
        from src.features.extractor import compute_soc_percent

        # 10 A trong 1h = 10 Ah >> 2 Ah nominal -> clip 0, khong am
        current = np.full(30, 10.0, dtype=np.float32)
        time = np.linspace(0.0, 3600.0, 30).astype(np.float32)
        soc = compute_soc_percent(current, time, nominal_capacity_ah=2.0)
        assert soc.shape == (30,)
        assert soc.dtype == np.float32
        assert soc.min() == 0.0 and soc.max() == 100.0


def test_spectral_feat_dim_matches_the_real_extractor_width():
    """Mắt xích giữa `SPECTRAL_FEAT_DIM` và chiều THẬT của extractor.

    `TestExtractWindowFeatures.test_output_shape` chốt số 57 cứng, nhưng nó
    không ràng buộc gì với config — sửa extractor rồi sửa luôn số 57 trong test
    đó là suite vẫn xanh, trong khi `SPECTRAL_FEAT_DIM` đứng im và mọi checkpoint
    cũ chết âm thầm.

    Đó chính là chuyện đã xảy ra: commit e3f93da (2026-06-27) thêm Gini vào
    `_spectral_features`, đẩy 9 → 10 đặc trưng/kênh, tức 3 × 18 = 54 → 3 × 19 = 57.
    Checkpoint RUL lưu 2026-06-17 với `feat_dim=54` chết hẳn (ma trận lớp đầu
    54 × 64, đưa vào 57 số là lỗi shape) và không ai biết trong hơn một tháng.

    Test này đỏ NGAY khoảnh khắc extractor đổi chiều — trước khi kịp lưu
    checkpoint nào. Nếu nó đỏ: cập nhật `SPECTRAL_FEAT_DIM` VÀ train lại toàn bộ
    artifact, đừng chỉ sửa một trong hai.

    3 kênh vì inference chấm trên (voltage, current, temperature):
    xem `src/services/inference.py` — `extract_window_features(x_scaled[:, :3])`.
    """
    from src.core.config import SPECTRAL_FEAT_DIM

    window = np.zeros((30, 3), dtype=np.float32)
    assert extract_window_features(window).shape[0] == SPECTRAL_FEAT_DIM
