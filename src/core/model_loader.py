import os

import joblib
import torch

from src.core.config import (
    FEATURE_SCALER_PATH,
    FEATURE_SCALER_VERSION,
    ISO_FOREST_PATH,
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
