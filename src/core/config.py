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
# GH-67: dải chung 2.0–4.5 phải đủ rộng cho NMC (sạc đầy 4.2 V), nên với LFP nó quá
# lỏng — cell LFP tối đa vật lý chỉ 3.65 V. Hệ quả đo được trên pack 8S/24V ở 26.4 V:
# gửi nhầm n_series=6 ra 4.40 V/cell vẫn LỌT vì 4.40 < 4.5, dù giá trị đó bất khả thi
# với LFP. Khai chemistry="LFP" thì dùng dải riêng bên dưới để chặn được ca đó.
# LƯU Ý: chỉ chặn được chiều "chia thiếu" (n_series quá nhỏ → điện áp ảo cao). Chiều
# "chia thừa" (n_series quá lớn → 2.6-2.9 V) KHÔNG chặn được vì đó là điện áp xả sâu
# hợp lệ. Cách chắc chắn duy nhất là đối chiếu evidence.feature_summary.voltage.mean
# một lần lúc tích hợp: LFP phải ra ~3.2-3.3 V.
# GH-67: trần độ dài 1 cửa sổ (giây) — lỗ hổng còn lại của range guard GH-66.
# Mọi cột đều bị chặn dải, RIÊNG cột `time` thì không, mà đó đúng là cột làm vỡ
# dự đoán: MinMaxScaler của bộ LFP fit trên time ∈ [0, 1453.9]s, nên cửa sổ dài
# hơn thế bị đẩy ra ngoài [0,1] y hệt ca mà GH-66 sinh ra để chặn.
#
# Đo trên dữ liệu IoT thật (pin LFP 8S, 2026-08-06), giãn đều khoảng lấy mẫu:
#     17s/dòng ->   8 phút -> SOH 100.00%   (bình thường)
#     30s/dòng ->  14 phút -> SOH 100.00%
#     60s/dòng ->  29 phút -> SOH  95.50%   <- bắt đầu vỡ
#    120s/dòng ->  58 phút -> SOH  82.85%
# Và ca thật đã gặp: IoT mất kết nối 76 phút giữa cửa sổ -> cửa sổ dài 94 phút
# -> SOH 81.84% + SCHEDULE_REPLACEMENT cho một quả pin hoàn toàn khoẻ, kèm
# confidence 0.799 (CAO NHẤT cả file). Model tự tin nhất đúng lúc sai nhất, nên
# BE không có cách nào lọc ra bằng confidence — buộc phải chặn ở đây.
#
# 1500 nằm giữa 14 phút (còn đúng) và 29 phút (đã vỡ), và sát trần train 1453.9s.
# Khoảng trống ĐƠN LẺ không cần luật riêng: đã đo 15 mẫu + trống 1400s + 15 mẫu
# (dài 1429s) vẫn ra SOH 100.00% — độ dài cửa sổ mới là yếu tố quyết định.
MAX_WINDOW_SPAN_S = 1500.0

VOLTAGE_CELL_RANGE_BY_CHEMISTRY = {
    "LFP": (2.0, 3.8),   # 2.5 cutoff .. 3.65 sạc đầy, cộng margin
}
CURRENT_RANGE = (-5.0, 5.0)  # A
TEMPERATURE_RANGE = (-10.0, 60.0)  # °C
SOC_RANGE = (0.0, 100.0)  # %

# GH-91: model was only ever trained at 3 discrete NASA chamber setpoints —
# a value inside TEMPERATURE_RANGE but far from all 3 (e.g. 15°C) still passes
# the range guard above yet is silent extrapolation. Flag it instead of letting
# it look in-distribution.
TEMPERATURE_TRAIN_CLUSTERS = (4.0, 24.0, 44.0)  # °C — NASA chamber setpoints
# GH-67: bộ LFP train trên Severson — TOÀN BỘ dataset chạy trong buồng 30 °C, nên
# cụm nhiệt độ của nó khác hẳn 3 mốc NASA. Dùng nhầm cụm NASA cho request LFP làm
# mọi giá trị 26–39 °C bị gắn cờ OOD sai (đo được: 30 °C → khoảng cách 6.0 > ngưỡng
# 5.0), tức gần như MỌI request từ pin solar ngoài trời đều bị báo "ngoài phân bố".
# v2.1-lfp: thêm 18 cell SNL ở 15/25/35 °C vào train, nên phủ nhiệt độ rộng hẳn ra —
# giá trị dưới lấy từ khoá `temperature_clusters` của scaler_lfp.pkl, KHÔNG tự đặt.
LFP_TEMPERATURE_TRAIN_CLUSTERS = (15.0, 25.0, 30.0, 35.0, 40.0)  # °C — SNL + Severson
# Tra cứu theo chemistry — dùng chung cho CẢ HAI đường sinh cờ OOD nhiệt độ:
# risk profile (_Artifacts.temp_clusters) và warning TEMP_OOD (generate_warnings).
# Sửa một chỗ này là đủ; đừng hardcode cụm ở nơi khác nữa.
TEMPERATURE_TRAIN_CLUSTERS_BY_CHEMISTRY = {
    "LFP": LFP_TEMPERATURE_TRAIN_CLUSTERS,
}
TEMPERATURE_OOD_THRESHOLD = 5.0  # °C — max allowed distance to nearest cluster
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

# --- LFP chemistry variant (GH-67 Mức 2) — Severson et al. 2019 dataset ---
# Separate artifact set (own scaler/model/iso-forest), same window=30/6-feature
# architecture as the default NASA/NMC model. Selected at inference time when
# pack_config.chemistry == "LFP" — chemistry-aware artifact selection in
# model_loader.py/inference.py is a separate follow-up step, NOT part of this.
LFP_MODEL_VERSION = "2.2-lfp"  # v2.2: bỏ 5 cell tiếp nối batch1→batch2 của Severson
# (b2c7/8/9/15/16 — cycle_count đếm lại từ 1 nên mâu thuẫn với nhãn SOH) + lọc cảm biến
# phi vật lý. MAE 1.5421 → 1.2697 %. v2.1: +18 cell SNL đa nhiệt độ (15/25/35 °C).
LFP_NOMINAL_CAPACITY_AH = 1.1  # A123 APR18650M1A (Severson et al. 2019) — vs NASA's 2.0 Ah
# GH-67: dung lượng cell danh định dùng để quy dòng pack về C-rate lúc INFERENCE.
# Trước đây LFP_NOMINAL_CAPACITY_AH chỉ được dùng lúc train (preprocess_lfp.py),
# còn inference quy đổi bằng 2.0 (cell NASA) cho CẢ HAI đường. Bằng chứng từ
# chính 2 scaler — hai bộ có thang dòng khác hẳn nhau:
#     NASA: current fit trên [-4.039,  0.030] A / 2.0 Ah -> C-rate [-2.02, 0.02]
#     LFP : current fit trên [-4.708, -0.100] A / 1.1 Ah -> C-rate [-4.28,-0.09]
# Hệ quả trên pack LFP 30 Ah: xả 1C (30 A) bị quy thành 2.00 A, model đọc thành
# 1.82C — sai hệ số 1.82x trên toàn bộ cột dòng.
# Sửa cũng nới trần dòng cho pack 30 Ah từ 75 A lên 136 A (BMS JK rated 100-200 A).
NOMINAL_CAPACITY_AH_BY_CHEMISTRY = {
    "LFP": LFP_NOMINAL_CAPACITY_AH,
}
# Severson cells cycle up to ~2300 times (vs NASA's ~197) — reusing the NASA
# CYCLE_COUNT_NORM=200 clips almost every Severson window's cycle_count_norm to
# 1.0, destroying the feature. Whoever wires chemistry-aware artifact selection
# in model_loader.py/inference.py MUST use THIS constant (not CYCLE_COUNT_NORM)
# when normalizing cycle_count for chemistry=="LFP" requests, or train/inference
# will mismatch on this feature.
# v2.1-lfp: cell SNL chạy dài hơn Severson nên preprocess nâng norm 2300 → 4600.
# Giá trị phải khớp khoá `cycle_count_norm` trong scaler_lfp.pkl — lệch là cả cột
# cycle_count vào model sai đúng bằng tỉ số hai hằng số (2× nếu quên sửa dòng này).
LFP_CYCLE_COUNT_NORM = 4600.0
LFP_SCALER_PATH = os.path.join(WEIGHTS_DIR, "scaler_lfp.pkl")
LFP_FEATURE_SCALER_PATH = os.path.join(WEIGHTS_DIR, "feature_scaler_lfp.pkl")
LFP_MAMBA_PATH = os.path.join(WEIGHTS_DIR, f"soh_mamba_v{LFP_MODEL_VERSION}.pth")
LFP_ISO_FOREST_PATH = os.path.join(WEIGHTS_DIR, f"isolation_forest_v{LFP_MODEL_VERSION}.pkl")

# GH-95: causal degradation-rate anomaly rule (src/services/battery_history.py).
# RATE_THRESHOLD = train p90 of the locally smoothed per-cycle SOH fade rate —
# SAME methodology/percentile as GH-70's GVHD-approved rate-based label
# (scripts/eval_anomaly.py), recomputed on the current split (post GH-88) via
# scripts/compute_rate_threshold.py: RATE_THRESHOLD = 0.5016 %SOH/cycle, seed 42.
RATE_THRESHOLD = 0.5016  # %SOH/cycle
CAUSAL_RATE_K = 2  # cycles back to compare against — best AUC (0.80-0.84) in GH-95 sweep {2,3,5,8}
