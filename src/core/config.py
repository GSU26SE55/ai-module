import os

MODEL_VERSION = "1.2"
SCALER_VERSION = "1.1"
FEATURE_SCALER_VERSION = "1.2"
FEATURE_SCALER_VERSION_LONG = "long-2.0"   # long-sequence (8-feature) pipeline — independent of standard

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
LONG_SEQ_STRIDE = 64                        # slide stride over the concatenated timeline (halved 128→64 doubles windows ~2206→4400)
LONG_PATCH_SIZE   = 16                      # compresses L=4096 → 256 tokens (16× reduction, ~5-6× VRAM/speed)
LONG_PATCH_STRIDE = 16                      # non-overlapping (fastest); use 8 for P16S8 as in PatchTST/MambaDecomp
WARMUP_STAGES   = [256, 512, 1024, 2048, 4096]  # progressive length warmup (GH-10 P1)
LONG_MODEL_VERSION       = "2.0"   # v2.0: PatchDegradationEncoder + 2-layer FiLM + SmoothL1 + CAWR
LONG_MAMBA_PATH          = os.path.join(WEIGHTS_DIR, f"soh_mamba_long_v{LONG_MODEL_VERSION}.pth")
COSINE_T0                = 25     # CosineAnnealingWarmRestarts T_0 for final training stage
LONG_FEATURE_SCALER_PATH = os.path.join(WEIGHTS_DIR, "feature_scaler_long.pkl")
LONG_INPUT_FEATURES      = 8     # 6 base + IC curve (dQ/dV) + phase mask
LONG_SCALER_PATH         = os.path.join(WEIGHTS_DIR, "scaler_long.pkl")  # 8-feature MinMaxScaler

# --- RUL (GH-13) — cycle-level Mamba: 1 token = 1 discharge cycle ---
# Re-frames the long-context problem onto the CYCLE axis (NASA ~168 cycles/battery)
# instead of raw timesteps. Each token = one cycle's 54-dim spectral+kurtosis vector.
# Target = remaining cycles until End-of-Life (SOH first crosses EOL_SOH).
RUL_LOOKBACK = 30        # number of historical cycles per sample
RUL_STRIDE   = 1         # slide stride along the cycle axis
EOL_SOH      = 80.0      # End-of-Life threshold (%) — first cycle SOH <= this
RUL_SCALE    = 200.0     # normalise RUL (cycles) to ~[0,1] for training stability
RUL_FEAT_DIM = 54        # per-cycle feature dim (reuses extract_window_features)
RUL_MODEL_VERSION       = "1.0"
RUL_MAMBA_PATH          = os.path.join(WEIGHTS_DIR, f"soh_mamba_rul_v{RUL_MODEL_VERSION}.pth")
RUL_FEATURE_SCALER_PATH = os.path.join(WEIGHTS_DIR, "feature_scaler_rul.pkl")

# --- SOH-forecasting (GH-13) — cycle-level: predict SOH h cycles ahead ---
# More data-efficient than RUL on NASA: every cycle is a valid forecast target
# (not just pre-EOL), and SOH is bounded so there is no extrapolation-beyond-range
# problem. Same cycle-axis tokens (54-dim per-cycle features) + same model.
FORECAST_LOOKBACK = 30      # historical cycles per sample
FORECAST_HORIZON  = 10      # forecast SOH this many cycles ahead of the last
FORECAST_STRIDE   = 1
FORECAST_MODEL_VERSION = "1.0"
FORECAST_MAMBA_PATH    = os.path.join(WEIGHTS_DIR, f"soh_mamba_forecast_v{FORECAST_MODEL_VERSION}.pth")

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
