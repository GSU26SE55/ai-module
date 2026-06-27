"""
Feature extraction: Spectral + Statistical (Kurtosis) features from a sliding window.

Each window (T, C) yields 57 scalar features:
  - 10 spectral features × C channels  (FFT-based, incl. spectral Gini)
  - 9  statistical features × C channels (kurtosis, crest factor, …)
"""

import numpy as np
from scipy.stats import kurtosis as scipy_kurtosis
from scipy.stats import skew as scipy_skew


# ---------------------------------------------------------------------------
# Per-channel feature extraction
# ---------------------------------------------------------------------------

def _spectral_gini(power: np.ndarray) -> float:
    """Gini coefficient of the FFT power spectrum.

    Measures spectral energy concentration. As Li-ion batteries age, increasing
    internal resistance redistributes energy across a broader frequency range,
    lowering the Gini coefficient. Complements spectral flatness (which uses a
    geometric/arithmetic mean ratio) by capturing the full distribution inequality.
    """
    x = np.sort(power.astype(np.float64))
    n = len(x)
    total = x.sum()
    if total < 1e-12:
        return 0.0
    ranks = np.arange(1, n + 1, dtype=np.float64)
    return float(np.clip((2.0 * (ranks * x).sum()) / (n * total) - (n + 1) / n, 0.0, 1.0))


def _spectral_features(x: np.ndarray) -> np.ndarray:
    """
    10 FFT-based features from a 1-D signal.

    Returns ndarray of shape (10,):
      [centroid, entropy, peak_freq, peak_power_db,
       flatness, rolloff, band_low, band_mid, band_high, gini]
    """
    n = len(x)
    fft_vals = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(n, d=1.0)
    power = np.abs(fft_vals) ** 2

    total = power.sum()
    if total < 1e-12:
        power = power + 1e-12
        total = power.sum()

    p_norm = power / total

    centroid = float(np.dot(freqs, p_norm))

    log_len = np.log(len(p_norm) + 1e-12)
    entropy = float(-np.sum(p_norm * np.log(p_norm + 1e-12)) / log_len)

    peak_idx = int(np.argmax(power))
    peak_freq = float(freqs[peak_idx])
    peak_power_db = float(10.0 * np.log10(power[peak_idx] + 1e-12))

    log_mean = np.mean(np.log(power + 1e-12))
    arith_mean = np.mean(power)
    flatness = float(np.exp(log_mean) / (arith_mean + 1e-12))

    cumsum = np.cumsum(power)
    rolloff_idx = int(np.searchsorted(cumsum, 0.85 * total))
    rolloff_idx = min(rolloff_idx, len(freqs) - 1)
    rolloff = float(freqs[rolloff_idx])

    bs = len(power) // 3
    band_low  = float(power[:bs].sum() / total)
    band_mid  = float(power[bs : 2 * bs].sum() / total)
    band_high = float(power[2 * bs :].sum() / total)

    gini = _spectral_gini(power)

    return np.array(
        [centroid, entropy, peak_freq, peak_power_db,
         flatness, rolloff, band_low, band_mid, band_high, gini],
        dtype=np.float32,
    )


def _statistical_features(x: np.ndarray) -> np.ndarray:
    """
    9 time-domain statistical features from a 1-D signal.

    Returns ndarray of shape (9,):
      [mean, std, skewness, kurtosis, crest_factor,
       waveform_factor, pulse_factor, margin_factor, peak_to_peak]
    """
    x = x.astype(np.float64)

    mean_val = float(np.mean(x))
    std_val  = float(np.std(x, ddof=0))

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
    Extract 57 scalar features from a scaled window.

    Args:
        window: np.ndarray of shape (T, C) — MinMaxScaler already applied.

    Returns:
        np.ndarray of shape (57,) — [spectral×C, statistical×C], float32.
        Layout: [spec_ch0…spec_ch2, stat_ch0…stat_ch2] (10×3 + 9×3).
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
        windows: np.ndarray of shape (N, T, C).

    Returns:
        np.ndarray of shape (N, 57), float32.
    """
    return np.stack([extract_window_features(w) for w in windows], axis=0)


# ---------------------------------------------------------------------------
# Long-sequence feature engineering (IC curve + phase mask)
# ---------------------------------------------------------------------------

def compute_ic_feature(voltage: np.ndarray, current: np.ndarray) -> np.ndarray:
    """Incremental Capacity dQ/dV per timestep — strongest Li-ion aging indicator.

    IC peak at ~3.7 V shifts predictably left with cycle aging, directly encoding
    SOH fade. Used as channel 7 in long-seq (L=4096) preprocessing.

    References: Dubarry et al. (2020), Weng et al. (2013).

    Args:
        voltage: (L,) raw unscaled voltage signal.
        current: (L,) raw unscaled current signal (negative = discharge).

    Returns:
        np.ndarray of shape (L,), float32, clipped to [-50, 50].
    """
    dV = np.diff(voltage, prepend=voltage[0])
    # Avoid division by near-zero dV while preserving sign
    dV = np.where(np.abs(dV) < 1e-4, np.sign(dV + 1e-9) * 1e-4, dV)
    return np.clip(current / dV, -50.0, 50.0).astype(np.float32)


def compute_phase_mask(current: np.ndarray, threshold: float = 0.1) -> np.ndarray:
    """Discharge / charge / rest phase indicator per timestep.

    Values: 0 = rest, 1 = charge (positive current), 2 = discharge (negative current).
    Used as channel 8 in long-seq preprocessing and for discharge-weighted
    attention pooling in MambaSOHPredictor.

    Args:
        current:   (L,) raw unscaled current signal.
        threshold: absolute current threshold (A) separating active from rest.

    Returns:
        np.ndarray of shape (L,), float32 with values in {0, 1, 2}.
    """
    mask = np.zeros(len(current), dtype=np.float32)
    mask[current >  threshold] = 1.0   # charging
    mask[current < -threshold] = 2.0   # discharging
    return mask
