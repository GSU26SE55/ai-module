import os

MODEL_VERSION = (
    "1.6"  # v1.6: GH-88 split rebalance (B0047 val→train, lấp vùng 4°C SOH 67-84%
    # gây bias tại ngưỡng EOL) + optional --balance-bands loss — retrain bắt buộc.
)
SCALER_VERSION = "1.3"  # v1.3: GH-88 refit trên train set mới (thêm B0047) — retrain bắt buộc
FEATURE_SCALER_VERSION = "1.5"  # v1.5: GH-88 refit trên train set mới (thêm B0047) — retrain bắt buộc
FEATURE_SCALER_VERSION_LONG = (
    "long-2.0"  # long-sequence (8-feature) pipeline — independent of standard
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEIGHTS_DIR = os.path.join(BASE_DIR, "models", "weights")

SCALER_PATH = os.path.join(WEIGHTS_DIR, "scaler.pkl")
FEATURE_SCALER_PATH = os.path.join(WEIGHTS_DIR, "feature_scaler.pkl")
MAMBA_PATH = os.path.join(WEIGHTS_DIR, f"soh_mamba_v{MODEL_VERSION}.pth")
ISO_FOREST_PATH = os.path.join(WEIGHTS_DIR, f"isolation_forest_v{MODEL_VERSION}.pkl")

WINDOW_SIZE = 30
WINDOW_STRIDE = 30

# GH-66: khoảng hợp lệ per-cell cho input validation (phân phối train NASA + margin).
# NASA 18650: discharge voltage ~2.5-4.2V, current ~±4A, ambient 4-44°C — khoảng dưới
# đã nới margin để không reject dữ liệu hợp lệ ở biên. Giá trị NGOÀI khoảng bị reject
# 422/INVALID_ARGUMENT (chặn silent garbage: 12V pack chưa quy đổi, cảm biến hỏng)
# thay vì scaler transform ra ngoài [0,1] → SOH vô nghĩa với confidence bình thường.
VOLTAGE_CELL_RANGE = (2.0, 4.5)  # V per-cell — check SAU khi chia pack_config.n_series (GH-65)
CURRENT_RANGE = (-5.0, 5.0)  # A
TEMPERATURE_RANGE = (-10.0, 60.0)  # °C
SOC_RANGE = (0.0, 100.0)  # %
INPUT_FEATURES = 6  # model input dim = 4 base (BASE_FEATURES, API payload) + 2 derived (GH-54: cycle_count, soc_percent)
CYCLE_COUNT_NORM = 200.0  # GH-54: chia cycle_idx cho hằng số này (cycle dài nhất quan sát ~197, B0033/34); KHÔNG clip >1
NOMINAL_CAPACITY_AH = (
    2.0  # NASA nominal capacity (Ah) — dùng cho SOH target và SOC Coulomb counting
)
SPECTRAL_FEAT_DIM = 57  # 10 spectral (incl. Gini) + 9 statistical × 3 channels (voltage, current, temperature)
D_MODEL = 64
D_STATE = 16

# --- Long-sequence (GH-10) — extend to L=4096 via concatenated discharge cycles ---
# Window=30 (above) stays the production/inference default; the long-seq pipeline is
# a separate artifact for the L=4096 experiment, not a replacement.
LONG_SEQ_LEN = 4096
LONG_SEQ_STRIDE = 64  # slide stride over the concatenated timeline (halved 128→64 doubles windows ~2206→4400)
LONG_PATCH_SIZE = 16  # compresses L=4096 → 256 tokens (16× reduction, ~5-6× VRAM/speed)
LONG_PATCH_STRIDE = (
    16  # non-overlapping (fastest); use 8 for P16S8 as in PatchTST/MambaDecomp
)
LONG_D_STATE = 32  # GH-34: SSM state dim for long-seq ONLY (global D_STATE=16 kept for window=30 + RUL)
WARMUP_STAGES = [256, 512, 1024, 2048, 4096]  # progressive length warmup (GH-10 P1)
LONG_MODEL_VERSION = "2.2"  # v2.2: feature ablation 6→4 base (bỏ current_load/voltage_load) → LONG_INPUT_FEATURES=6; v2.1: +8 train batteries (incl. 4°C domain)
LONG_MAMBA_PATH = os.path.join(WEIGHTS_DIR, f"soh_mamba_long_v{LONG_MODEL_VERSION}.pth")
COSINE_T0 = 25  # CosineAnnealingWarmRestarts T_0 for final training stage
LONG_FEATURE_SCALER_PATH = os.path.join(WEIGHTS_DIR, "feature_scaler_long.pkl")
LONG_INPUT_FEATURES = 6  # 4 base + IC curve (dQ/dV) + phase mask
LONG_SCALER_PATH = os.path.join(
    WEIGHTS_DIR, "scaler_long.pkl"
)  # 8-feature MinMaxScaler

# --- RUL (GH-13) — cycle-level Mamba: 1 token = 1 discharge cycle ---
# Re-frames the long-context problem onto the CYCLE axis (NASA ~168 cycles/battery)
# instead of raw timesteps. Each token = one cycle's 57-dim spectral+kurtosis vector.
# Target = remaining cycles until End-of-Life (SOH first crosses EOL_SOH).
RUL_LOOKBACK = 30  # number of historical cycles per sample
RUL_STRIDE = 1  # slide stride along the cycle axis
EOL_SOH = 80.0  # End-of-Life threshold (%) — first cycle SOH <= this
RUL_SCALE = 200.0  # normalise RUL (cycles) to ~[0,1] for training stability
RUL_FEAT_DIM = 57  # per-cycle feature dim (reuses extract_window_features)
RUL_MODEL_VERSION = "1.0"
RUL_MAMBA_PATH = os.path.join(WEIGHTS_DIR, f"soh_mamba_rul_v{RUL_MODEL_VERSION}.pth")
RUL_FEATURE_SCALER_PATH = os.path.join(WEIGHTS_DIR, "feature_scaler_rul.pkl")

# --- SOH-forecasting (GH-13) — cycle-level: predict SOH h cycles ahead ---
# More data-efficient than RUL on NASA: every cycle is a valid forecast target
# (not just pre-EOL), and SOH is bounded so there is no extrapolation-beyond-range
# problem. Same cycle-axis tokens (54-dim per-cycle features) + same model.
FORECAST_LOOKBACK = 30  # historical cycles per sample
FORECAST_HORIZON = 10  # forecast SOH this many cycles ahead of the last
FORECAST_STRIDE = 1
FORECAST_MODEL_VERSION = "1.0"
FORECAST_MAMBA_PATH = os.path.join(
    WEIGHTS_DIR, f"soh_mamba_forecast_v{FORECAST_MODEL_VERSION}.pth"
)

# Feature ablation (GH-25): bỏ current_load/voltage_load — 2 kênh load redundant/noisy.
# BASE_FEATURES = 4 cột đo trực tiếp: là API payload (BE gửi) và đầu vào của scaler.pkl.
# Thứ tự cột PHẢI khớp giữa preprocess và inference.
BASE_FEATURES = [
    "voltage",
    "current",
    "temperature",
    "time",
]
# FEATURES = tên đầy đủ 6 cột input model (GH-54): 4 base + 2 derived tính phía server
# (cycle_count/CYCLE_COUNT_NORM, soc_percent/100 — đã normalize sẵn [0,1], KHÔNG qua scaler).
FEATURES = BASE_FEATURES + [
    "cycle_count",
    "soc_percent",
]
RAW_FEATURES = [
    "Voltage_measured",
    "Current_measured",
    "Temperature_measured",
    "Time",
]

SEED = 42
