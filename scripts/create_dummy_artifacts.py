"""
Creates dummy model artifacts for development so the FastAPI app can boot.
Run once after cloning the repo if models/weights/ is empty.

Real artifacts (trained on NASA dataset) will replace these after training.
"""

import os
import random
import sys

import joblib
import numpy as np
import torch
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler, StandardScaler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import (
    FEATURE_SCALER_PATH,
    FEATURE_SCALER_VERSION,
    FEATURES,
    INPUT_FEATURES,
    ISO_FOREST_PATH,
    MAMBA_PATH,
    MODEL_VERSION,
    SCALER_PATH,
    SCALER_VERSION,
    SPECTRAL_FEAT_DIM,
    WEIGHTS_DIR,
    WINDOW_SIZE,
)
from src.models.soh_predictor import MambaSOHPredictor

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

os.makedirs(WEIGHTS_DIR, exist_ok=True)

# Dummy scaler — fit on random data with configured feature count
scaler = MinMaxScaler()
scaler.fit(np.random.rand(200, INPUT_FEATURES))
joblib.dump(
    {
        "scaler": scaler,
        "version": SCALER_VERSION,
        "trained_on": ["dummy"],
        "features": FEATURES,
    },
    SCALER_PATH,
)
print(f"✓ Saved dummy scaler → {SCALER_PATH}")
feat_scaler = StandardScaler()
feat_scaler.fit(np.random.rand(200, SPECTRAL_FEAT_DIM))
joblib.dump(
    {
        "scaler": feat_scaler,
        "version": FEATURE_SCALER_VERSION,
        "n_features": SPECTRAL_FEAT_DIM,
    },
    FEATURE_SCALER_PATH,
)
print(f"Saved dummy feature scaler -> {FEATURE_SCALER_PATH}")


# Dummy Mamba — random weights, correct architecture
model = MambaSOHPredictor(input_features=INPUT_FEATURES, feat_dim=SPECTRAL_FEAT_DIM)
torch.save(
    {
        "model_state_dict": model.state_dict(),
        "version": MODEL_VERSION,
        "window_size": WINDOW_SIZE,
        "input_features": INPUT_FEATURES,
        "feat_dim": SPECTRAL_FEAT_DIM,
    },
    MAMBA_PATH,
)
print(f"✓ Saved dummy Mamba model → {MAMBA_PATH}")

# Dummy IsolationForest — fit on random flattened windows
iso = IsolationForest(contamination=0.1, n_estimators=100, random_state=SEED)
iso.fit(np.random.rand(200, WINDOW_SIZE * INPUT_FEATURES))
joblib.dump(iso, ISO_FOREST_PATH)
print(f"✓ Saved dummy IsolationForest → {ISO_FOREST_PATH}")

print("\n✅ Dummy artifacts created. App can now boot.")
print("   Replace with real trained artifacts by running scripts/train.py.")
