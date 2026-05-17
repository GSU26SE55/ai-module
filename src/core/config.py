import os

MODEL_VERSION = "1.0"
SCALER_VERSION = "1.0"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEIGHTS_DIR = os.path.join(BASE_DIR, "models", "weights")

SCALER_PATH = os.path.join(WEIGHTS_DIR, "scaler.pkl")
LSTM_PATH = os.path.join(WEIGHTS_DIR, f"soh_lstm_v{MODEL_VERSION}.pth")
ISO_FOREST_PATH = os.path.join(WEIGHTS_DIR, f"isolation_forest_v{MODEL_VERSION}.pkl")

WINDOW_SIZE = 30
INPUT_FEATURES = 3
FEATURES = ["voltage", "current", "temperature"]

SEED = 42
