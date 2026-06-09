import time

import numpy as np
import torch

from src.core import model_loader
from src.core.config import INPUT_FEATURES, MODEL_VERSION, WINDOW_SIZE
from src.features.extractor import extract_window_features
from src.models.anomaly_detector import (
    classify_anomaly,
    classify_anomaly_status,
    classify_health_stage,
    compute_risk_profile,
    compute_degradation_metrics,
    estimate_rul,
    generate_warnings,
    get_recommended_action,
)

_FEATURE_NAMES = ["voltage", "current", "temperature", "current_load", "voltage_load", "time"]


def _expected_feature_count() -> int:
    if hasattr(model_loader.scaler, "n_features_in_"):
        return int(model_loader.scaler.n_features_in_)
    if hasattr(model_loader.soh_model, "input_features"):
        return int(model_loader.soh_model.input_features)
    return 3


def _align_features(x: np.ndarray) -> np.ndarray:
    expected = _expected_feature_count()
    actual = x.shape[1]
    if actual == expected:
        return x
    if actual > expected:
        return x[:, :expected]
    raise ValueError(
        f"readings provide {actual} features, but loaded artifacts expect {expected}. "
        "Run preprocessing/training for the expanded feature set or send the legacy feature set."
    )


def _compute_feature_summary(raw: np.ndarray) -> dict:
    """Mean/min/max for each sensor column in raw (unscaled) readings."""
    summary = {}
    n = min(raw.shape[1], len(_FEATURE_NAMES))
    for i in range(n):
        col = raw[:, i].astype(float)
        summary[_FEATURE_NAMES[i]] = {
            "mean": round(float(col.mean()), 4),
            "min":  round(float(col.min()),  4),
            "max":  round(float(col.max()),  4),
        }
    return summary


def run_inference(readings: list[list[float]]) -> dict:
    """
    Full inference pipeline: scale → Mamba SOH → IsolationForest → classify.

    Args:
        readings: (30, 6) preferred or legacy (30, 3) raw sensor values

    Returns:
        dict with soh_percent, classification, confidence, inference_ms,
        rul_cycles_estimate, anomaly_score, recommended_action,
        warnings, feature_summary
    """
    start = time.perf_counter()

    raw = np.array(readings, dtype=np.float32)          # (30, F) — keep for warnings + summary
    x = _align_features(raw)                             # (30, F_model)
    x_scaled = model_loader.scaler.transform(x)
    x_tensor = torch.tensor(x_scaled, dtype=torch.float32).unsqueeze(0)

    # Cycle-level features: compute from scaled window (first 3 channels: voltage, current, temp)
    # Matches SPECTRAL_FEAT_DIM=54 config. FiLM conditioning is soft — degrades
    # gracefully from cycle-level to window-level features at inference time.
    raw_feat = extract_window_features(x_scaled[:, :3])         # (54,)
    feat_scaled = model_loader.feature_scaler.transform(raw_feat.reshape(1, -1))
    x_feat_tensor = torch.tensor(feat_scaled, dtype=torch.float32)  # (1, 54)

    with torch.no_grad():
        soh = float(max(0.0, min(100.0, model_loader.soh_model(x_tensor, x_feat_tensor).item() * 100)))

    score = float(model_loader.iso_model.decision_function([x_scaled.flatten()])[0])
    classification = classify_anomaly(score, soh)
    anomaly_confidence = round(min(1.0, max(0.0, abs(score))), 3)
    health_stage = classify_health_stage(soh)
    anomaly_status = classify_anomaly_status(score)

    # Degradation metrics — battery-specific rate from multi-cycle window
    # More accurate when L >= 500 (spans multiple cycles); falls back to
    # population average (0.15%/cycle) for shorter windows.
    degradation = compute_degradation_metrics(raw, soh)
    warnings = generate_warnings(raw, soh, classification)
    feature_summary = _compute_feature_summary(raw)
    risk = compute_risk_profile(
        health_stage=health_stage,
        anomaly_status=anomaly_status,
        warnings=warnings,
        soh=soh,
        cycles_to_maintenance=degradation["cycles_to_maintenance"],
    )

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

    return {
        "prediction": {
            "soh_percent":                round(soh, 2),
            "rul_cycles_estimate":        degradation["rul_cycles_estimate"],
            "degradation_rate_per_cycle": degradation["degradation_rate_per_cycle"],
            "soh_trend":                  degradation["soh_trend"],
            "cycles_to_maintenance":      degradation["cycles_to_maintenance"],
            "soh_trajectory":             degradation["soh_trajectory"],
            "health_stage":               health_stage,
        },
        "anomaly": {
            "anomaly_score":              round(score, 4),
            "anomaly_status":             anomaly_status,
            "anomaly_confidence":         anomaly_confidence,
        },
        "risk": risk,
        "evidence": {
            "warnings":                   warnings,
            "feature_summary":            feature_summary,
        },
        "metadata": {
            "model_version":              MODEL_VERSION,
            "window_size":                WINDOW_SIZE,
            "input_features":             INPUT_FEATURES,
            "inference_ms":               elapsed_ms,
        },
        "soh_percent":                round(soh, 2),
        "classification":             classification,
        "confidence":                 anomaly_confidence,
        "inference_ms":               elapsed_ms,

        # RUL — battery-specific (from observed trend) when window is long enough
        "rul_cycles_estimate":        degradation["rul_cycles_estimate"],
        "degradation_rate_per_cycle": degradation["degradation_rate_per_cycle"],
        "soh_trend":                  degradation["soh_trend"],
        "cycles_to_maintenance":      degradation["cycles_to_maintenance"],
        "soh_trajectory":             degradation["soh_trajectory"],

        "anomaly_score":              round(score, 4),
        "recommended_action":         risk["action_code"],
        "warnings":                   warnings,
        "feature_summary":            feature_summary,
    }
