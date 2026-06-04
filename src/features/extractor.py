"""
Feature extraction: Spectral + Statistical (Kurtosis) features from a sliding window.

Each window (30, C) yields 54 scalar features:
  - 9 spectral features × C channels  (FFT-based)
  - 9 statistical features × C channels (kurtosis, crest factor, …)
"""

import numpy as np
from scipy.stats import kurtosis as scipy_kurtosis
from scipy.stats import skew as scipy_skew


# ---------------------------------------------------------------------------
# Per-channel feature extraction
# ---------------------------------------------------------------------------

def _spectral_features(x: np.ndarray) -> np.ndarray:
    """
    9 FFT-based features from a 1-D signal of length 30.

    Returns ndarray of shape (9,):
      [centroid, entropy, peak_freq, peak_power_db,
       flatness, rolloff, band_low, band_mid, band_high]
    """
    n = len(x)
    fft_vals = np.fft.rfft(x)                        # 16 complex bins for n=30
    freqs = np.fft.rfftfreq(n, d=1.0)               # normalized freq [0, 0.5]
    power = np.abs(fft_vals) ** 2

    total = power.sum()
    if total < 1e-12:
        power = power + 1e-12
        total = power.sum()

    p_norm = power / total

    # Spectral centroid
    centroid = float(np.dot(freqs, p_norm))

    # Spectral entropy (normalized to [0, 1])
    log_len = np.log(len(p_norm) + 1e-12)
    entropy = float(-np.sum(p_norm * np.log(p_norm + 1e-12)) / log_len)

    # Peak frequency and peak power (dB)
    peak_idx = int(np.argmax(power))
    peak_freq = float(freqs[peak_idx])
    peak_power_db = float(10.0 * np.log10(power[peak_idx] + 1e-12))

    # Spectral flatness (Wiener entropy)
    log_mean = np.mean(np.log(power + 1e-12))
    arith_mean = np.mean(power)
    flatness = float(np.exp(log_mean) / (arith_mean + 1e-12))

    # Spectral rolloff at 85%
    cumsum = np.cumsum(power)
    rolloff_idx = int(np.searchsorted(cumsum, 0.85 * total))
    rolloff_idx = min(rolloff_idx, len(freqs) - 1)
    rolloff = float(freqs[rolloff_idx])

    # Band power (split bins into thirds)
    bs = len(power) // 3  # 5 bins each for n=30
    band_low  = float(power[:bs].sum() / total)
    band_mid  = float(power[bs : 2 * bs].sum() / total)
    band_high = float(power[2 * bs :].sum() / total)

    return np.array(
        [centroid, entropy, peak_freq, peak_power_db,
         flatness, rolloff, band_low, band_mid, band_high],
        dtype=np.float32,
    )


def _statistical_features(x: np.ndarray) -> np.ndarray:
    """
    9 time-domain statistical features from a 1-D signal of length 30.

    Returns ndarray of shape (9,):
      [mean, std, skewness, kurtosis, crest_factor,
       waveform_factor, pulse_factor, margin_factor, peak_to_peak]
    """
    x = x.astype(np.float64)

    mean_val = float(np.mean(x))
    std_val  = float(np.std(x, ddof=0))

    # Bias-corrected skewness and kurtosis (important for small N=30).
    # Near-constant signals (std < 1e-8) cause precision loss in higher moments — return 0.
    if std_val < 1e-8:
        skew_val = 0.0
        kurt_val = 0.0
    else:
        skew_val = float(scipy_skew(x, bias=False))
        kurt_val = float(scipy_kurtosis(x, fisher=True, bias=False))

    rms      = float(np.sqrt(np.mean(x ** 2)))
    abs_max  = float(np.max(np.abs(x)))
    mean_abs = float(np.mean(np.abs(x))) + 1e-12

    crest_factor   = abs_max / (rms + 1e-12)
    waveform_factor = rms / mean_abs
    pulse_factor   = abs_max / mean_abs
    margin_factor  = abs_max / (float(np.mean(np.sqrt(np.abs(x)))) ** 2 + 1e-12)
    ptp            = float(np.ptp(x))

    return np.array(
        [mean_val, std_val, skew_val, kurt_val,
         crest_factor, waveform_factor, pulse_factor, margin_factor, ptp],
        dtype=np.float32,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_window_features(window: np.ndarray) -> np.ndarray:
    """
    Extract 54 scalar features from a scaled window.

    Args:
        window: np.ndarray of shape (30, C) — MinMaxScaler already applied.

    Returns:
        np.ndarray of shape (54,) — [spectral×C, statistical×C], float32.
        Layout: [spec_ch0…spec_ch2, stat_ch0…stat_ch2] (9×3 + 9×3).
    """
    if window.ndim != 2:
        raise ValueError(f"Expected window shape (T, C), got {window.shape}")

    n_channels = window.shape[1]
    spectral_parts   = [_spectral_features(window[:, c])   for c in range(n_channels)]
    statistical_parts = [_statistical_features(window[:, c]) for c in range(n_channels)]

    return np.concatenate(spectral_parts + statistical_parts, dtype=np.float32)


def extract_batch_features(windows: np.ndarray) -> np.ndarray:
    """
    Vectorised extraction for a batch of windows.

    Args:
        windows: np.ndarray of shape (N, 30, C).

    Returns:
        np.ndarray of shape (N, 54), float32.
    """
    return np.stack([extract_window_features(w) for w in windows], axis=0)
