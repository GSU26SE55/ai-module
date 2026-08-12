# Tech — AI Module

## Stack

| Quyết định | Lựa chọn | Ghi chú |
|------------|----------|---------|
| Language | Python 3.11 | — |
| ML Framework | PyTorch | **Mamba (SSM) thuần PyTorch** — không dùng lib `mamba-ssm` CUDA |
| Anomaly | scikit-learn Isolation Forest | Đủ cho scope capstone |
| Serving | FastAPI (REST :8000) + gRPC (:50051) | gRPC là transport production BE gọi |
| Dataset | NASA Ames (mặc định) | Severson + SNL (nhánh LFP) · CALCE backup |

## Model Spec (bắt buộc thống nhất giữa train và inference)

| Tham số | Giá trị | Ghi chú |
|---------|---------|---------|
| Window size | 30 timestep | 30 chu kỳ đo liên tiếp |
| Input features | **6** (`INPUT_FEATURES`) | 4 base (`BASE_FEATURES` = voltage, current, temperature, **time**) + 2 dẫn xuất tính phía server: `cycle_count/CYCLE_COUNT_NORM`, `soc_percent/100` |
| Feature phụ (FiLM) | **57** (`SPECTRAL_FEAT_DIM`) | 10 spectral + 9 statistical × 3 kênh V/I/T — `extract_window_features()` |
| Normalization | 2 scaler riêng | `scaler.pkl` (MinMax [0,1] trên 4 cột base) + `feature_scaler.pkl` (trên vector 57). 2 cột dẫn xuất **KHÔNG** qua scaler — đã normalize sẵn |
| SOH target | capacity_current / capacity_nominal × 100 | NASA = 2.0 Ah · LFP/Severson = 1.1 Ah (`NOMINAL_CAPACITY_AH_BY_CHEMISTRY`) |
| Train / Val / Test | 24 / 1 / 1 | Chia theo battery ID, không theo timestep — xem bảng bên dưới |
| Random seed | 42 | Bắt buộc mọi script (train, preprocess) |

**Train/Val/Test split — NASA Ames (chia theo battery ID, KHÔNG theo timestep):**

| Split | Battery IDs | Số pin |
|-------|-------------|--------|
| Train | B0005/06/07/18, B0025–B0032, B0033, B0034, B0042–B0044, B0041, B0045, B0053, B0054, B0055, B0056, **B0047** | 24 |
| Val   | B0046 (4°C) | 1 |
| Test  | B0048 (4°C) — held out hoàn toàn | 1 |

> **GH-88 (2026-07-08):** B0047 chuyển từ Val sang Train — train 4°C cũ (B0041/45/53–56) chỉ phủ SOH 0–67.2%, thiếu hẳn vùng 67–86% mà val/test cần → model ngoại suy lệch xuống đúng ngưỡng EOL 80%. Chi tiết: `docs/adr/0002-split-rebalance-b0047.md`.
> **Phạm vi:** split 24/1/1 này áp dụng cho pipeline production window=30 (`soh_mamba_v1.6.pth` trở đi). Model headline bài báo NCKH (`soh_mamba_long_v2.2.pth`, LOBO) train **trước** khi đổi split (commit split-rebalance `899aa45` ngày 2026-07-05, checkpoint v2.2 đã có từ 2026-07-03) nên vẫn dùng split cũ 23/2/1 (B0047 ở val) — số liệu đó không đổi, xem `docs/nckh-paper-plan.md` §3.1.
> Chia HẲN theo battery ID (1 pin chỉ thuộc 1 split) — đo đúng cross-battery generalization, không phải chia timestep trong 1 pin.
> **Bắt buộc có pin 4°C trong train** (B0041/45/53/54/55/56/B0047): val/test đều 4°C, nếu train thiếu domain 4°C model phải extrapolate → generalization gap lớn.
> Nguồn duy nhất của split: `scripts/preprocess.py` (`TRAIN_IDS`/`VAL_IDS`/`TEST_IDS`). Sửa ở đó, không hardcode nơi khác.
> Bỏ qua: B0036 (SOH spike 122% — nhiễu), B0049–B0052 (quá ngắn/corrupt), B0038–B0040 (dự phòng).

**Metric đánh giá:**
- SOH regression: MAE < 2%, RMSE < 3%
- Anomaly classification: F1-score > 0.80

## Model Architecture (bắt buộc nhất quán train & inference)

### 1. MambaSOHPredictor — SOH Prediction

> ⚠️ Dự án **KHÔNG còn dùng CNN-LSTM**. Kiến trúc production là Mamba (SSM) thuần PyTorch.
> Nguồn sự thật: `src/models/soh_predictor.py`. Đoạn dưới là tóm tắt, không phải bản sao đầy đủ.

Model nhận **2 đầu vào** — `forward(x, x_feat)`:

```text
x (B, 30, 6) ──> Linear(6 → 64)
             ──> MambaBlock × 2  (d_model=64, d_state=16, d_conv=4, expand=2)
             ──> LayerNorm(64)
             ──> lấy token cuối  h = h[:, -1, :]        (B, 64)
                                                          │
x_feat (B, 57) ──> film_proj: Linear(57→57) → SiLU → Linear(57→128) → chunk → γ, β
                                                          │
             h = (sigmoid(γ) + 0.5) · h + β              (B, 64)   ← FiLM conditioning
             ──> Linear(64 → 32) → GELU → Dropout(0.2) → Linear(32 → 1)
             ──> SOH ∈ [0, 1]  (× 100 khi trả về)
```

**Bắt buộc nhớ:**
- **FiLM conditioning không được bỏ** — đặc trưng phổ cấp chu kỳ (57 chiều) điều biến trạng thái ẩn, KHÔNG nối vào input. Bỏ đi thì checkpoint không load được.
- Pure PyTorch mặc định (Windows-native). Cờ opt-in `use_official_mamba=True` dùng kernel CUDA `mamba_ssm` trên Kaggle/Colab — cùng công thức toán, chỉ nhanh hơn, tự fallback nếu thiếu lib.
- `d_state=16` cho window=30 (production) và RUL. Model **long-seq L=4096** là kiến trúc KHÁC: Conv1d patch (k=16, s=16) + `PatchDegradationEncoder` + `d_state=32` (`LONG_D_STATE`) + multi-head attention pooling. Đừng gộp 2 cái làm một.

```python
# Training config window=30 — nguồn: scripts/train.py:82-85, 315-320
OPTIMIZER  = "Adam"      # + weight_decay=1e-5
LR         = 5e-4
LOSS       = "weighted MSE"   # == nn.MSELoss() khi tắt --balance-bands
EPOCHS     = 100         # CLI --epochs, mặc định 100
PATIENCE   = 15          # early stopping
BATCH_SIZE = 32
SCHEDULER  = "ReduceLROnPlateau(factor=0.5, patience=5, min_lr=1e-6)"
```

> Đường long-seq dùng bộ hyperparameter khác: `AdamW` + `CosineAnnealingWarmRestarts` + SmoothL1 upweight near-EOL + progressive length warmup (`WARMUP_STAGES`).

### 2. Isolation Forest — Anomaly Detection

```python
from sklearn.ensemble import IsolationForest

# Hyperparameters (BẮT BUỘC) — justification: xem .claude/docs/ai-research-references.md §2
# - CONTAMINATION 0.1: Liu et al. ICDM 2008 đề xuất 0.05–0.15; NASA dataset ~12-15% near-EOL → 0.1 safe
# - N_ESTIMATORS 100: Liu et al. 2008 — variance hội tụ ≥ 100 trees; thêm chỉ tăng latency
# - RANDOM_STATE 42: reproducibility theo .claude/rules/tech/ai.md
CONTAMINATION = 0.1     # ước tính 10% data là bất thường (NASA dataset)
N_ESTIMATORS  = 100
RANDOM_STATE  = 42      # BẮT BUỘC — seed cố định

iso_forest = IsolationForest(
    contamination=CONTAMINATION,
    n_estimators=N_ESTIMATORS,
    random_state=RANDOM_STATE,
)
# ⚠️ fit trên VECTOR 57 CHIỀU (feature_scaler đã transform), KHÔNG phải chuỗi thô (30,6)
iso_forest.fit(X_train_features)  # fit trên train set, KHÔNG fit lại trên production

# Lưu model sau khi train
import joblib
joblib.dump(iso_forest, "models/weights/isolation_forest.pkl")
# isolation_forest.pkl PHẢI commit vào Git (như scaler.pkl)
```

**3 hàm phân loại ĐỘC LẬP** — nguồn: `src/models/anomaly_detector.py`. Đừng gộp làm một:

```python
def classify_anomaly(score, soh, causal_rate=None) -> str:
    """SOH là yếu tố CHÍNH. IsolationForest chỉ hạ bậc được khi SOH đã khoẻ."""
    if soh < EOL_SOH:        # 80.0
        base = "Failed"
    elif soh < 90.0:
        base = "Degrading"
    else:
        base = "Degrading" if score < -0.1 else "Normal"

    # GH-95: tốc độ suy giảm so với lịch sử CỦA CHÍNH pin đó → nâng 1 bậc
    if causal_rate is not None and causal_rate > RATE_THRESHOLD:   # 0.5016 %SOH/cycle
        return _ANOMALY_TIERS[min(_ANOMALY_TIERS.index(base) + 1, 2)]
    return base


def classify_anomaly_status(score) -> str:
    """Trạng thái CẢM BIẾN — tách khỏi sức khoẻ pin."""
    if score <= -0.3: return "Anomaly"
    if score <= -0.1: return "Warning"
    return "Normal"


def classify_health_stage(soh) -> str:
    """2 TẦNG. Trên 80% vẫn còn tuổi thọ danh định ⇒ Healthy."""
    return "End Of Life" if soh < EOL_SOH else "Healthy"
```

> **health_stage quyết định bằng phân phối MC Dropout**, không phải điểm ước lượng: `classify_health_stage_probabilistic(mc_preds)` lấy argmax trên tỉ lệ mẫu rơi vào từng tầng, trả thêm `stage_probabilities` / `stage_confidence` / `is_borderline` (ngưỡng `BORDERLINE_CONFIDENCE=0.7`). Hoà phiếu → chọn tầng nặng hơn (safety-first).
>
> **`MAINTENANCE_SOH` (85%) KHÔNG còn là ranh giới tầng** — chỉ là tín hiệu lookahead cho `cycles_to_maintenance`, không sinh ticket. `SCHEDULE_REPLACEMENT` đã bị khai tử cùng lúc, chỉ còn 3 `action_code`: `REPLACE_IMMEDIATELY` / `SCHEDULE_MAINTENANCE` / `MONITOR`.

> **Cơ sở khoa học (B2):** Mọi anomaly type và hyperparameter trong file này PHẢI cite paper hoặc industry standard. Xem `.claude/docs/ai-research-references.md`:
> - Phụ lục B2 §1 — paper cho 15 AnomalyType (Overheat, Overvoltage, SOH EOL 80%, …)
> - Phụ lục B2 §2 — IsolationForest hyperparameter justification
> - Phụ lục B2 §3 — **CHƯA CẬP NHẬT**: vẫn justify CNN-LSTM, chưa có citation nào cho Mamba/SSM (kiểm tra 2026-08-12: file đó 0 lần nhắc "Mamba"). Cần bổ sung Gu & Dao 2023 (Mamba), Nie et al. ICLR 2023 (PatchTST), Perez et al. AAAI 2018 (FiLM), Gal & Ghahramani ICML 2016 (MC Dropout) trước khi bảo vệ.
>
> Hội đồng KLTN sẽ hỏi "tại sao ngưỡng X?" — đừng tự đặt mà không cite.

---

## Inference Latency SLA

| Priority ticket | Yêu cầu inference | Lý do |
|-----------------|------------------|-------|
| P1 Critical (4h SLA) | **< 100ms** | Alert phải real-time |
| P2/P3 batch | < 500ms | Acceptable cho batch check |

**Benchmark bắt buộc trước khi merge AI module:**
```python
import time

def benchmark_inference(sample_readings, n_runs=100):
    """Benchmark TOÀN BỘ run_inference(), không chỉ forward pass —
    scaler + trích 57 feature + MC Dropout 10 mẫu + IsolationForest đều tính vào SLA."""
    latencies = []
    for _ in range(n_runs):
        start = time.perf_counter()
        run_inference(sample_readings)   # src/services/inference.py
        latencies.append((time.perf_counter() - start) * 1000)  # ms

    avg_ms = sum(latencies) / len(latencies)
    assert avg_ms < 100, f"Inference quá chậm: {avg_ms:.1f}ms > 100ms threshold"
    print(f"Avg inference latency: {avg_ms:.1f}ms ✅")

# Chạy trong tests/test_inference.py trước khi /kltn-ship
```

**FastAPI health endpoint** — trả latency metrics để monitor:
```python
@router.get("/health")
async def health():
    return {
        "status": "ok",
        "model_version": MODEL_VERSION,
        "scaler_loaded": scaler is not None,
        "feature_scaler_loaded": feature_scaler is not None,
        "mamba_loaded": soh_model is not None,
        "isolation_forest_loaded": iso_model is not None,
    }
```

> Shape thật của response `/health` (và `rpc Health`) nằm ở `src/routers/health.py` + `protos/ai_service.proto` — nó báo trạng thái của **cả 2 bộ artifact** (NASA + LFP) và cờ nạp lười của model long-seq. Đoạn trên chỉ minh hoạ nguyên tắc.

---

## Serving — Hybrid REST + gRPC (GH-39→42)

<!-- ⚠️ LEADER: section này thêm ở repo ai-module (GH-42) — cần đưa vào nguồn sync workflow-ai để không bị ghi đè -->

Cùng pipeline inference/prescription expose qua 2 transport song song — **KHÔNG duplicate logic**, servicer gRPC gọi chung `run_inference()`/`run_prescription()` với FastAPI:

| Transport | Port | Entrypoint |
|-----------|------|-----------|
| REST (FastAPI) | 8000 | `uvicorn main:app` |
| gRPC `aimodule.v1.AiService` | 50051 (env `GRPC_PORT`) | `python -m src.grpc_server` |

**Quy tắc:**
- Contract duy nhất: `protos/ai_service.proto` — sửa contract PHẢI qua repo ai-module, chỉ **thêm** field number mới, không reuse/đổi số cũ (wire compatibility). Stub sinh bằng `python scripts/gen_proto.py`, commit vào `src/grpc_gen/`.
- Validate input gRPC bằng **chính Pydantic schema của REST** — 2 transport reject giống nhau (`ValidationError` → `INVALID_ARGUMENT`).
- Response 2 transport phải **parity field-by-field** — có test enforce (`tests/test_grpc_server.py`).
- `PredictStream` (bidi): 1 request = 1 window 30 đầy đủ = 1 response, in-order; window lỗi giữa stream → stream abort sau k−1 responses (bidi không có per-message error).
- gRPC insecure — chỉ nội bộ docker network, KHÔNG expose port 50051 ra ngoài.
- Benchmark trước khi ship thay đổi serving: `python scripts/benchmark_grpc.py` (transport overhead <50ms luôn enforce; SLA <100ms enforce với `--real-weights` trên môi trường deploy).
- BE integration: `docs/grpc-integration-be.md`.

---

## Model Artifact Management

### Đường dẫn chuẩn (bắt buộc nhất quán giữa training và inference)

**2 bộ artifact tách theo chemistry** — chọn lúc inference ở `_resolve_artifacts(chemistry)`:

```text
ai-module/models/weights/
├── [bộ mặc định — NASA/NMC]
│   ├── scaler.pkl                     # MinMax trên 4 cột base
│   ├── feature_scaler.pkl             # scaler cho vector 57 chiều
│   ├── soh_mamba_v1.6.pth             # MODEL_VERSION
│   └── isolation_forest_v1.6.pkl
├── [bộ LFP — chemistry="LFP", Severson + SNL]
│   ├── scaler_lfp.pkl
│   ├── feature_scaler_lfp.pkl
│   ├── soh_mamba_v2.1-lfp.pth         # LFP_MODEL_VERSION
│   └── isolation_forest_v2.1-lfp.pkl
└── [long-seq / RUL — không phải đường production]
    ├── soh_mamba_long_v2.2.pth · scaler_long.pkl · feature_scaler_long.pkl
    └── soh_mamba_rul_v1.0.pth · feature_scaler_rul.pkl
```

> ⚠️ **Đổi artifact LFP phải sync 3 hằng trong `src/core/config.py`**: `LFP_MODEL_VERSION`,
> `LFP_CYCLE_COUNT_NORM`, `LFP_TEMPERATURE_TRAIN_CLUSTERS` — lấy đúng từ khoá trong
> `scaler_lfp.pkl`, đừng tự đặt. Lệch là hỏng **im lặng**, không có exception.

### Versioning strategy

| Sprint | Phiên bản | Ghi chú |
|--------|-----------|---------|
| Sprint 4 | v1.0 | Model baseline — NASA dataset |
| Sprint 5 | v1.1 | Tuning hyperparameter / thêm data |
| Sprint 6+ | v1.x | Cải thiện metric |

**Quy tắc:**
- Tăng minor version (`v1.0 → v1.1`) khi retrain cùng architecture nhưng khác data/hyperparameter
- Tăng major version (`v1.x → v2.0`) khi thay đổi architecture (e.g., thêm attention layer)
- `scaler.pkl` lưu kèm metadata version để phát hiện mismatch với model
- Cả **4 artifact của một bộ** (model + scaler + feature_scaler + iforest) **phải commit vào Git** cùng 1 commit khi update — thiếu `feature_scaler` là inference sai im lặng

### Lưu artifacts sau khi train (bắt buộc kèm metadata)

```python
import joblib

# Lưu scaler kèm metadata — giúp phát hiện version mismatch lúc inference
joblib.dump({
    "scaler": scaler,
    "version": "1.0",
    "trained_on": ["B0005", "B0006", "B0007"],  # battery IDs dùng để fit
    "features": BASE_FEATURES,   # ["voltage", "current", "temperature", "time"]
    # bộ LFP còn lưu thêm: "cycle_count_norm", "temperature_clusters"
}, "models/weights/scaler.pkl")

# Lưu Mamba model
torch.save({
    "model_state_dict": soh_model.state_dict(),
    "version": MODEL_VERSION,       # "1.6"
    "window_size": 30,
    "input_features": 6,
    "feat_dim": 57,
}, f"models/weights/soh_mamba_v{MODEL_VERSION}.pth")
```

### Load artifacts khi inference (FastAPI startup)

Thực tế nằm ở `src/core/model_loader.py` (load 1 lần khi khởi động, không load lại per-request). Nguyên tắc bắt buộc:

```python
# Đường dẫn + version lấy TỪ src/core/config.py, KHÔNG hardcode lại
from src.core.config import (
    MODEL_VERSION, SCALER_VERSION, FEATURE_SCALER_VERSION,
    MAMBA_PATH, SCALER_PATH, FEATURE_SCALER_PATH, ISO_FOREST_PATH,
    INPUT_FEATURES, SPECTRAL_FEAT_DIM, D_MODEL, D_STATE,
)

# ⚠️ Kiểm tra file tồn tại TRƯỚC khi load — báo lỗi rõ thay vì traceback cryptic
for path, label in [
    (SCALER_PATH,         "MinMaxScaler"),
    (FEATURE_SCALER_PATH, "Feature scaler (57-dim)"),
    (MAMBA_PATH,          "Mamba SOH model"),
    (ISO_FOREST_PATH,     "Isolation Forest"),
]:
    assert os.path.exists(path), (
        f"[STARTUP] {label} artifact not found at '{path}'. "
        f"Run training script and commit all artifacts in models/weights/ before starting."
    )

# Version assertion cho CẢ 3 artifact có metadata
scaler_artifact = joblib.load(SCALER_PATH)
assert scaler_artifact["version"] == SCALER_VERSION

checkpoint = torch.load(MAMBA_PATH, map_location="cpu")
assert checkpoint["version"] == MODEL_VERSION
soh_model = MambaSOHPredictor(
    input_features=INPUT_FEATURES,   # 6
    d_model=D_MODEL, d_state=D_STATE,
    feat_dim=SPECTRAL_FEAT_DIM,      # 57
)
soh_model.load_state_dict(checkpoint["model_state_dict"])
soh_model.eval()
```

> **Tại sao cần metadata?** Nếu `scaler.pkl` được refit nhưng `soh_mamba_v1.6.pth` không update, inference ra kết quả sai mà **không có error**. Version assertion bắt lỗi ngay lúc startup thay vì âm thầm predict sai.
>
> **Model long-seq nạp LƯỜI** (lần gọi `PredictLong` đầu tiên), không nạp lúc startup — nó nặng hơn nhiều và phần lớn deploy không dùng tới.

### Git LFS (nếu model file > 100MB)

```bash
# Cài Git LFS nếu weights vượt 100MB
git lfs install
git lfs track "models/weights/*.pth"
git lfs track "models/weights/*.pkl"
git add .gitattributes
```

> Với model Mamba nhỏ (< 50MB) và Isolation Forest (< 5MB): commit trực tiếp vào Git — không cần LFS cho scope capstone.

---

## Nguyên tắc

- Không thêm ML framework mới — chỉ PyTorch + scikit-learn
- Target metric: MAE < 2% SOH / RMSE < 3% / F1 > 0.80 anomaly — không dùng "accuracy 85–90%" chung chung
- Output bắt buộc: Classification (Normal / Degrading / Failed) + SOH % + confidence score
- IoT data pipeline chỉ thêm Sprint 8 nếu core model xong
- Scaler (MinMaxScaler) phải được lưu tại `models/weights/scaler.pkl` sau khi train — load lại khi inference, không fit lại trên production data
- Cả 4 artifact của mỗi bộ (model · scaler · feature_scaler · iforest) phải commit vào Git — inference cần cùng artifacts với training
- Hằng số model chỉ khai báo ở `src/core/config.py` — KHÔNG hardcode lại `window=30`, `input_features=6`, `feat_dim=57`, đường dẫn weights, hay cụm nhiệt độ ở nơi khác
- Inference latency **PHẢI** benchmark và đạt < 100ms trước khi merge

**Simplicity First:** Chỉ implement model/endpoint mà issue yêu cầu — không thêm hyperparameter tuning, architecture variant, hoặc preprocessing step chưa được approve.

**Surgical Changes:** Chỉ sửa files trong plan.md. Không refactor training script, không đổi hyperparameter, không thay đổi data split ngoài scope task.
