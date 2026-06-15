import os

MODEL_VERSION = "1.1"
SCALER_VERSION = "1.0"
FEATURE_SCALER_VERSION = "1.1"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEIGHTS_DIR = os.path.join(BASE_DIR, "models", "weights")

SCALER_PATH         = os.path.join(WEIGHTS_DIR, "scaler.pkl")
FEATURE_SCALER_PATH = os.path.join(WEIGHTS_DIR, "feature_scaler.pkl")
MAMBA_PATH          = os.path.join(WEIGHTS_DIR, f"soh_mamba_v{MODEL_VERSION}.pth")
ISO_FOREST_PATH     = os.path.join(WEIGHTS_DIR, f"isolation_forest_v{MODEL_VERSION}.pkl")

WINDOW_SIZE   = 30
WINDOW_STRIDE = 30
INPUT_FEATURES    = 6
SPECTRAL_FEAT_DIM = 54  # 9 spectral + 9 statistical × 3 channels (voltage, current, temperature)
D_MODEL = 64
D_STATE = 16

# --- Long-sequence (GH-10) — extend to L=4096 via concatenated discharge cycles ---
# Window=30 (above) stays the production/inference default; the long-seq pipeline is
# a separate artifact for the L=4096 experiment, not a replacement.
LONG_SEQ_LEN    = 4096
LONG_SEQ_STRIDE = 128                       # slide stride over the concatenated timeline (smaller = more windows)
WARMUP_STAGES   = [256, 512, 1024, 2048, 4096]  # progressive length warmup (GH-10 P1)
LONG_MODEL_VERSION       = "1.0"
LONG_MAMBA_PATH          = os.path.join(WEIGHTS_DIR, f"soh_mamba_long_v{LONG_MODEL_VERSION}.pth")
LONG_FEATURE_SCALER_PATH = os.path.join(WEIGHTS_DIR, "feature_scaler_long.pkl")

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
