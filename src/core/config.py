import os

MODEL_VERSION = "1.1"
SCALER_VERSION = "1.0"
FEATURE_SCALER_VERSION = "1.1"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEIGHTS_DIR = os.path.join(BASE_DIR, "models", "weights")

SCALER_PATH = os.path.join(WEIGHTS_DIR, "scaler.pkl")
FEATURE_SCALER_PATH = os.path.join(WEIGHTS_DIR, "feature_scaler.pkl")
MAMBA_PATH = os.path.join(WEIGHTS_DIR, f"soh_mamba_v{MODEL_VERSION}.pth")
ISO_FOREST_PATH = os.path.join(WEIGHTS_DIR, "isolation_forest_v1.0.pkl")

WINDOW_SIZE = 30
WINDOW_STRIDE = 30
INPUT_FEATURES = 6
SPECTRAL_FEAT_DIM = 54   # 9 spectral + 9 statistical × 3 channels (voltage, current, temperature)
D_MODEL = 64
D_STATE = 16

FEATURES = [
    "voltage",
    "current",
    "temperature",
    "current_load",
    "voltage_load",
    "time",
]
RAW_FEATURES = [
    "Voltage_measured",
    "Current_measured",
    "Temperature_measured",
    "Current_load",
    "Voltage_load",
    "Time",
]

SEED = 42
