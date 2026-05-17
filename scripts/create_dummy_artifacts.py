"""
Creates dummy model artifacts for development so the FastAPI app can boot.
Run once after cloning the repo if models/weights/ is empty.

Real artifacts (trained on NASA dataset) will replace these in Sprint 3-4.
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

from src.core.config import ISO_FOREST_PATH, LSTM_PATH, SCALER_PATH, WEIGHTS_DIR
from src.models.soh_predictor import SOHPredictor

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

os.makedirs(WEIGHTS_DIR, exist_ok=True)

# Dummy scaler — fit on random data with correct feature count (3)
scaler = MinMaxScaler()
scaler.fit(np.random.rand(200, 3))
joblib.dump(
    {
        "scaler": scaler,
        "version": "1.0",
        "trained_on": ["dummy"],
        "features": ["voltage", "current", "temperature"],
    },
    SCALER_PATH,
)
print(f"✓ Saved dummy scaler → {SCALER_PATH}")

# Dummy LSTM — random weights, correct architecture
model = SOHPredictor()
torch.save(
    {
        "model_state_dict": model.state_dict(),
        "version": "1.0",
        "window_size": 30,
        "input_features": 3,
    },
    LSTM_PATH,
)
print(f"✓ Saved dummy LSTM → {LSTM_PATH}")

# Dummy IsolationForest — fit on random flattened windows (30*3=90 features)
iso = IsolationForest(contamination=0.1, n_estimators=100, random_state=SEED)
iso.fit(np.random.rand(200, 90))
joblib.dump(iso, ISO_FOREST_PATH)
print(f"✓ Saved dummy IsolationForest → {ISO_FOREST_PATH}")

print("\n✅ Dummy artifacts created. App can now boot.")
print("   Replace with real trained artifacts in Sprint 3-4.")
