import time

import numpy as np
import torch

from src.core import model_loader
from src.models.anomaly_detector import (
    classify_anomaly,
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

    with torch.no_grad():
        soh = float(max(0.0, min(100.0, model_loader.soh_model(x_tensor).item() * 100)))

    score = float(model_loader.iso_model.decision_function([x_scaled.flatten()])[0])
    classification = classify_anomaly(score, soh)
    confidence = round(min(1.0, max(0.0, abs(score))), 3)

    elapsed_ms = (time.perf_counter() - start) * 1000

    return {
        "soh_percent":          round(soh, 2),
        "classification":       classification,
        "confidence":           confidence,
        "inference_ms":         round(elapsed_ms, 2),
        "rul_cycles_estimate":  estimate_rul(soh),
        "anomaly_score":        round(score, 4),
        "recommended_action":   get_recommended_action(classification, soh),
        "warnings":             generate_warnings(raw, soh, classification),
        "feature_summary":      _compute_feature_summary(raw),
    }
