# Tech — AI Module

## Stack

| Quyết định | Lựa chọn | Ghi chú |
|------------|----------|---------|
| Language | Python 3.11 | — |
| ML Framework | PyTorch | LSTM/CNN-LSTM |
| Anomaly | scikit-learn Isolation Forest | Đủ cho scope capstone |
| Serving | FastAPI | REST endpoint cho BE gọi |
| Dataset | NASA Ames (ưu tiên) | CALCE backup |

## Model Spec (bắt buộc thống nhất giữa train và inference)

| Tham số | Giá trị | Ghi chú |
|---------|---------|---------|
| Window size | 30 timestep | 30 chu kỳ đo liên tiếp |
| Input features | 3 | voltage, current, temperature |
| Normalization | MinMaxScaler [0, 1] | Fit trên train set, lưu scaler.pkl để dùng lại |
| SOH target | capacity_current / capacity_nominal × 100 | NASA: nominal = 2.0 Ah |
| Train / Val / Test | 70 / 15 / 15 | Chia theo battery ID, không theo timestep — xem bảng bên dưới |
| Random seed | 42 | Bắt buộc mọi script (train, preprocess) |

**Train/Val/Test split — NASA Ames (cố định, không thay đổi):**

| Split | Battery IDs | Ghi chú |
|-------|-------------|---------|
| Train | B0005, B0006, B0007 | ~70% data |
| Val   | B0018 (70% đầu timestep) | ~15% data |
| Test  | B0018 (30% cuối timestep) | ~15% data |

> Chia theo battery ID trước, sau đó chia timestep cho B0018 (val/test). KHÔNG được xáo trộn ngẫu nhiên.

**Metric đánh giá:**
- SOH regression: MAE < 2%, RMSE < 3%
- Anomaly classification: F1-score > 0.80

## Model Architecture (bắt buộc nhất quán train & inference)

### 1. LSTM/CNN-LSTM — SOH Prediction

```python
import torch.nn as nn

class SOHPredictor(nn.Module):
    """
    Input:  (batch, 30, 3)  — 30 timestep, 3 features [voltage, current, temp]
    Output: (batch, 1)      — SOH% trong khoảng [0, 100]
    """
    def __init__(self):
        super().__init__()
        # CNN block — trích xuất local pattern
        self.conv1 = nn.Conv1d(in_channels=3, out_channels=32, kernel_size=3, padding=1)
        self.relu  = nn.ReLU()
        self.pool  = nn.MaxPool1d(kernel_size=2)          # (batch, 32, 15)

        # LSTM block — học temporal dependency
        self.lstm  = nn.LSTM(input_size=32, hidden_size=64,
                             num_layers=2, batch_first=True,
                             dropout=0.2)                 # dropout giữa layers

        # FC head
        self.fc1   = nn.Linear(64, 32)
        self.fc2   = nn.Linear(32, 1)
        self.dropout = nn.Dropout(0.2)

    def forward(self, x):                                 # x: (batch, 30, 3)
        x = x.permute(0, 2, 1)                           # → (batch, 3, 30) cho Conv1d
        x = self.pool(self.relu(self.conv1(x)))           # → (batch, 32, 15)
        x = x.permute(0, 2, 1)                           # → (batch, 15, 32) cho LSTM
        _, (h_n, _) = self.lstm(x)
        x = h_n[-1]                                       # hidden state lớp cuối
        x = self.dropout(self.relu(self.fc1(x)))
        return self.fc2(x).squeeze(-1)                    # → (batch,)

# Training config (BẮT BUỘC)
OPTIMIZER  = "Adam"
LR         = 1e-3
LOSS       = "MSELoss"
EPOCHS     = 50
PATIENCE   = 10          # early stopping
BATCH_SIZE = 32
```

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
iso_forest.fit(X_train_features)  # fit trên train set, KHÔNG fit lại trên production

# Mapping score → classification
def classify_anomaly(score: float, soh: float) -> str:
    """
    score: IsolationForest decision_function (âm = bất thường hơn)
    soh:   SOH% từ LSTM
    """
    if score > -0.1:            # ngưỡng bình thường
        return "Normal"
    elif score > -0.3 or soh >= 80:
        return "Degrading"
    else:
        return "Failed"

# Lưu model sau khi train
import joblib
joblib.dump(iso_forest, "models/weights/isolation_forest.pkl")
# isolation_forest.pkl PHẢI commit vào Git (như scaler.pkl)
```

> **Cơ sở khoa học (B2):** Mọi anomaly type và hyperparameter trong file này PHẢI cite paper hoặc industry standard. Xem `.claude/docs/ai-research-references.md`:
> - Phụ lục B2 §1 — paper cho 15 AnomalyType (Overheat, Overvoltage, SOH EOL 80%, …)
> - Phụ lục B2 §2 — IsolationForest hyperparameter justification
> - Phụ lục B2 §3 — CNN-LSTM architecture justification (kernel_size, dropout, optimizer)
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

def benchmark_inference(model, scaler, sample_input, n_runs=100):
    latencies = []
    for _ in range(n_runs):
        start = time.perf_counter()
        # inference pipeline
        x = scaler.transform(sample_input)
        x_tensor = torch.tensor(x, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            soh = model(x_tensor).item()
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
        "model_version": "1.0.0",
        "scaler_loaded": scaler is not None,
        "lstm_loaded": soh_model is not None,
        "isolation_forest_loaded": iso_model is not None,
    }
```

---

## Model Artifact Management

### Đường dẫn chuẩn (bắt buộc nhất quán giữa training và inference)

```
ai-module/
└── models/
    └── weights/
        ├── scaler.pkl                    # MinMaxScaler — fit trên train set
        ├── soh_lstm_v{major}.{minor}.pth # LSTM/CNN-LSTM weights
        └── isolation_forest_v{major}.{minor}.pkl  # Isolation Forest
```

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
- Cả 3 artifacts **phải commit vào Git** cùng 1 commit khi update

### Lưu artifacts sau khi train (bắt buộc kèm metadata)

```python
import joblib

# Lưu scaler kèm metadata — giúp phát hiện version mismatch lúc inference
joblib.dump({
    "scaler": scaler,
    "version": "1.0",
    "trained_on": ["B0005", "B0006", "B0007"],  # battery IDs dùng để fit
    "features": ["voltage", "current", "temperature"],
}, "models/weights/scaler.pkl")

# Lưu LSTM model
torch.save({
    "model_state_dict": soh_model.state_dict(),
    "version": "1.0",
    "window_size": 30,
    "input_features": 3,
}, "models/weights/soh_lstm_v1.0.pth")
```

### Load artifacts khi inference (FastAPI startup)

```python
# main.py — load 1 lần khi khởi động, không load lại per-request
import os
import joblib
import torch

SCALER_VERSION = "1.0"
MODEL_VERSION  = "1.0"

SCALER_PATH      = "models/weights/scaler.pkl"
LSTM_PATH        = f"models/weights/soh_lstm_v{MODEL_VERSION}.pth"
ISO_FOREST_PATH  = f"models/weights/isolation_forest_v{MODEL_VERSION}.pkl"

# ⚠️ Kiểm tra file tồn tại TRƯỚC khi load — cho phép báo lỗi rõ ràng thay vì traceback cryptic
for path, label in [
    (SCALER_PATH,     "MinMaxScaler"),
    (LSTM_PATH,       "LSTM model"),
    (ISO_FOREST_PATH, "Isolation Forest"),
]:
    assert os.path.exists(path), (
        f"[STARTUP] {label} artifact not found at '{path}'. "
        f"Run training script and commit all artifacts in models/weights/ before starting."
    )

scaler_artifact = joblib.load(SCALER_PATH)
assert scaler_artifact["version"] == SCALER_VERSION, (
    f"Scaler version mismatch: expected {SCALER_VERSION}, got {scaler_artifact['version']}"
)
scaler = scaler_artifact["scaler"]

checkpoint = torch.load(LSTM_PATH, map_location="cpu")
assert checkpoint["version"] == MODEL_VERSION, (
    f"Model version mismatch: expected {MODEL_VERSION}, got {checkpoint['version']}"
)
soh_model = SOHPredictor()
soh_model.load_state_dict(checkpoint["model_state_dict"])
soh_model.eval()

iso_model = joblib.load(ISO_FOREST_PATH)
```

> **Tại sao cần metadata?** Nếu `scaler.pkl` được refit (v1.1) nhưng `soh_lstm_v1.0.pth` không được update, inference sẽ ra kết quả sai mà không có error. Version assertion bắt lỗi này ngay khi startup thay vì âm thầm predict sai.

### Git LFS (nếu model file > 100MB)

```bash
# Cài Git LFS nếu weights vượt 100MB
git lfs install
git lfs track "models/weights/*.pth"
git lfs track "models/weights/*.pkl"
git add .gitattributes
```

> Với PyTorch LSTM nhỏ (< 50MB) và Isolation Forest (< 5MB): commit trực tiếp vào Git — không cần LFS cho scope capstone.

---

## Nguyên tắc

- Không thêm ML framework mới — chỉ PyTorch + scikit-learn
- Target metric: MAE < 2% SOH / RMSE < 3% / F1 > 0.80 anomaly — không dùng "accuracy 85–90%" chung chung
- Output bắt buộc: Classification (Normal / Degrading / Failed) + SOH % + confidence score
- IoT data pipeline chỉ thêm Sprint 8 nếu core model xong
- Scaler (MinMaxScaler) phải được lưu tại `models/weights/scaler.pkl` sau khi train — load lại khi inference, không fit lại trên production data
- `scaler.pkl` và `isolation_forest.pkl` phải được commit vào Git — inference cần cùng artifacts với training
- Inference latency **PHẢI** benchmark và đạt < 100ms trước khi merge

**Simplicity First:** Chỉ implement model/endpoint mà issue yêu cầu — không thêm hyperparameter tuning, architecture variant, hoặc preprocessing step chưa được approve.

**Surgical Changes:** Chỉ sửa files trong plan.md. Không refactor training script, không đổi hyperparameter, không thay đổi data split ngoài scope task.
