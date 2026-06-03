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
from sklearn.preprocessing import MinMaxScaler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import (
    FEATURES,
    INPUT_FEATURES,
    ISO_FOREST_PATH,
    MAMBA_PATH,
    SCALER_PATH,
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
        "version": "1.0",
        "trained_on": ["dummy"],
        "features": FEATURES,
    },
    SCALER_PATH,
)
print(f"✓ Saved dummy scaler → {SCALER_PATH}")

# Dummy Mamba — random weights, correct architecture
model = MambaSOHPredictor(input_features=INPUT_FEATURES)
torch.save(
    {
        "model_state_dict": model.state_dict(),
        "version": "1.0",
        "window_size": WINDOW_SIZE,
        "input_features": INPUT_FEATURES,
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
