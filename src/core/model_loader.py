import os

import joblib
import torch

from src.core.config import (
    ISO_FOREST_PATH,
    MAMBA_PATH,
    MODEL_VERSION,
    SCALER_PATH,
    SCALER_VERSION,
)
from src.models.soh_predictor import MambaSOHPredictor

scaler = None
soh_model = None
iso_model = None


def load_models() -> None:
    global scaler, soh_model, iso_model

    for path, label in [
        (SCALER_PATH, "MinMaxScaler"),
        (MAMBA_PATH, "Mamba model"),
        (ISO_FOREST_PATH, "Isolation Forest"),
    ]:
        if not os.path.exists(path):
            raise RuntimeError(
                f"[STARTUP] {label} artifact not found at '{path}'. "
                f"Run scripts/create_dummy_artifacts.py and commit models/weights/ before starting."
            )

    scaler_artifact = joblib.load(SCALER_PATH)
    if scaler_artifact["version"] != SCALER_VERSION:
        raise RuntimeError(
            f"Scaler version mismatch: expected {SCALER_VERSION}, got {scaler_artifact['version']}"
        )
    scaler = scaler_artifact["scaler"]

    checkpoint = torch.load(MAMBA_PATH, map_location="cpu", weights_only=False)
    if checkpoint["version"] != MODEL_VERSION:
        raise RuntimeError(
            f"Model version mismatch: expected {MODEL_VERSION}, got {checkpoint['version']}"
        )
    input_features = checkpoint.get("input_features", 3)
    soh_model = MambaSOHPredictor(input_features=input_features)
    soh_model.load_state_dict(checkpoint["model_state_dict"])
    soh_model.eval()

    iso_model = joblib.load(ISO_FOREST_PATH)
