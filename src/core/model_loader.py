import os

import joblib
import torch

from src.core.config import (
    FEATURE_SCALER_PATH,
    FEATURE_SCALER_VERSION,
    ISO_FOREST_PATH,
    LONG_FEATURE_SCALER_PATH,
    LONG_MAMBA_PATH,
    LONG_MODEL_VERSION,
    MAMBA_PATH,
    MODEL_VERSION,
    SCALER_PATH,
    SCALER_VERSION,
    SPECTRAL_FEAT_DIM,
)
from src.models.soh_predictor import MambaSOHPredictor

scaler = None
feature_scaler = None
soh_model = None
iso_model = None

# Long-sequence (GH-10) — loaded lazily on first long inference, not at startup
long_feature_scaler = None
long_soh_model = None
long_device = None


def load_models() -> None:
    global scaler, feature_scaler, soh_model, iso_model

    for path, label in [
        (SCALER_PATH,         "MinMaxScaler"),
        (FEATURE_SCALER_PATH, "Feature StandardScaler"),
        (MAMBA_PATH,          "Mamba model"),
        (ISO_FOREST_PATH,     "Isolation Forest"),
    ]:
        if not os.path.exists(path):
            raise RuntimeError(
                f"[STARTUP] {label} artifact not found at '{path}'. "
                "Run scripts/preprocess.py + scripts/train.py and commit models/weights/ before starting."
            )

    scaler_artifact = joblib.load(SCALER_PATH)
    if scaler_artifact["version"] != SCALER_VERSION:
        raise RuntimeError(
            f"Scaler version mismatch: expected {SCALER_VERSION}, got {scaler_artifact['version']}"
        )
    scaler = scaler_artifact["scaler"]

    feat_scaler_artifact = joblib.load(FEATURE_SCALER_PATH)
    if feat_scaler_artifact["version"] != FEATURE_SCALER_VERSION:
        raise RuntimeError(
            f"Feature scaler version mismatch: expected {FEATURE_SCALER_VERSION}, "
            f"got {feat_scaler_artifact['version']}"
        )
    feature_scaler = feat_scaler_artifact["scaler"]

    checkpoint = torch.load(MAMBA_PATH, map_location="cpu", weights_only=False)
    if checkpoint["version"] != MODEL_VERSION:
        raise RuntimeError(
            f"Model version mismatch: expected {MODEL_VERSION}, got {checkpoint['version']}"
        )
    input_features = checkpoint.get("input_features", 6)
    feat_dim       = checkpoint.get("feat_dim", SPECTRAL_FEAT_DIM)
    d_model        = checkpoint.get("d_model", 64)
    d_state        = checkpoint.get("d_state", 16)
    soh_model = MambaSOHPredictor(input_features=input_features, feat_dim=feat_dim, d_model=d_model, d_state=d_state)
    soh_model.load_state_dict(checkpoint["model_state_dict"])
    soh_model.eval()

    iso_model = joblib.load(ISO_FOREST_PATH)


def load_long_model(device: str | None = None) -> MambaSOHPredictor:
    """Load the long-sequence model (GH-10) and its artifacts onto the best device.

    Reuses the shared MinMaxScaler but the dedicated long feature_scaler (features
    are computed on full L=4096 windows, a different distribution than window=30).
    Picks CUDA when available so the L=4096 scan can meet the <100ms SLA.
    """
    global scaler, long_feature_scaler, long_soh_model, long_device

    for path, label in [
        (SCALER_PATH,              "MinMaxScaler"),
        (LONG_FEATURE_SCALER_PATH, "Long feature scaler"),
        (LONG_MAMBA_PATH,          "Long Mamba model"),
    ]:
        if not os.path.exists(path):
            raise RuntimeError(
                f"[STARTUP] {label} artifact not found at '{path}'. "
                "Run scripts/preprocess_long.py + scripts/train.py --long and commit models/weights/ first."
            )

    if scaler is None:
        scaler = joblib.load(SCALER_PATH)["scaler"]
    long_feature_scaler = joblib.load(LONG_FEATURE_SCALER_PATH)["scaler"]

    long_device = torch.device(device) if device else torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(LONG_MAMBA_PATH, map_location=long_device, weights_only=False)
    if checkpoint["version"] != LONG_MODEL_VERSION:
        raise RuntimeError(
            f"Long model version mismatch: expected {LONG_MODEL_VERSION}, got {checkpoint['version']}"
        )
    model = MambaSOHPredictor(
        input_features=checkpoint.get("input_features", 6),
        feat_dim=checkpoint.get("feat_dim", SPECTRAL_FEAT_DIM),
        d_model=checkpoint.get("d_model", 64),
        d_state=checkpoint.get("d_state", 16),
        pooling=checkpoint.get("pooling", "attention"),
    ).to(long_device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    long_soh_model = model
    return model
