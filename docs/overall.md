# AI Module — Tài liệu tổng quan

> **Dự án:** Solar Lithium-ion Battery Maintenance Management System  
> **Nhóm:** GSU26SE55 | **GVHD:** Trương Long  
> **Cập nhật:** 2026-06-02  

---

## Mục lục

1. [Tổng quan dự án](#1-tổng-quan-dự-án)
2. [Kiến trúc hệ thống](#2-kiến-trúc-hệ-thống)
3. [AI Module — Chi tiết](#3-ai-module--chi-tiết)
4. [Model Architecture](#4-model-architecture)
5. [Dataset & Training Pipeline](#5-dataset--training-pipeline)
6. [API Endpoints](#6-api-endpoints)
7. [Cấu trúc thư mục](#7-cấu-trúc-thư-mục)
8. [Hướng dẫn chạy local](#8-hướng-dẫn-chạy-local)
9. [Kế hoạch Sprint](#9-kế-hoạch-sprint)
10. [Prescription Layer (Sắp triển khai)](#10-prescription-layer-sắp-triển-khai)
11. [Quy ước phát triển](#11-quy-ước-phát-triển)

---

## 1. Tổng quan dự án

### Mục tiêu
Xây dựng nền tảng **giám sát và bảo trì pin lithium-ion** cho hệ thống năng lượng mặt trời, bao gồm:
- Dự đoán **State of Health (SOH)** của pin theo thời gian thực
- Phát hiện **bất thường** trước khi pin hỏng
- Tự động tạo **ticket bảo trì** theo chuẩn ITIL với SLA P1/P2/P3
- Cung cấp **prescription** — kế hoạch bảo trì cụ thể từng bước

### Hệ thống 3 lớp

```
┌──────────────────────────────────────────┐
│  Mobile App (React Native / Expo)         │
│  Customer xem trạng thái pin real-time    │
├──────────────────────────────────────────┤
│  Web App (ReactJS)                        │
│  Admin / Manager / Staff quản lý ticket   │
├──────────────────────────────────────────┤
│  AI Module (FastAPI + PyTorch)            │  ← File này mô tả phần này
│  Dự đoán SOH, phân loại bất thường       │
└──────────────────────────────────────────┘
```

### Thông tin nhóm

| Tên | MSSV | Role chính | GitHub |
|-----|------|------------|--------|
| Nguyễn Phúc Duy | SE184821 | BE (phụ AI) | DuyNguyen-3006 |
| Bùi Phước Thắng | SE180445 | BE (phụ AI) | — |
| Mai Hồng Thái | SE183923 | BE (phụ AI) | — |
| Trần Minh Trí | SE183109 | FE / Leader | — |
| Nguyễn Nhật Minh | SE170310 | FE (phụ AI) | — |

---

## 2. Kiến trúc hệ thống

### Luồng dữ liệu tổng thể

```
Pin lithium-ion
     │
     │  (voltage, current, temperature — mỗi ~13s/reading)
     ▼
[IoT Sensor] ──────────────────────────────────────────────────┐
                                                               │
                                              POST /predict    │
[BatteryService (BE)] ────────────────────► [AI Module]       │
                                              ◄────────────────┘
                                              {soh_percent,
                                               classification,
                                               confidence,
                                               inference_ms}
                    │
                    │  BatteryAnomalyDetectedEvent
                    ▼
            [TicketService (BE)]
                    │
                    ├─► Auto-tạo ticket P1/P2/P3
                    ├─► Assign Staff
                    └─► Notify Customer (Mobile)
```

### SLA Ticket theo priority

| Priority | Trigger | SLA | Hành động khi breach |
|----------|---------|-----|----------------------|
| **P1 Critical** | Pin hỏng / nguy cơ an toàn | **4h** | Reassign Senior + notify Admin |
| **P2 High** | SOH suy giảm đáng kể | **24h** | Manager reassign |
| **P3 Standard** | Bất thường nhẹ / bảo trì định kỳ | **72h** | Manager review |

---

## 3. AI Module — Chi tiết

### Stack công nghệ

| Quyết định | Lựa chọn | Lý do |
|-----------|----------|-------|
| Language | Python 3.11 | — |
| ML Framework | PyTorch 2.3.1 | Mamba pure PyTorch |
| Anomaly Detection | scikit-learn 1.5.0 | Isolation Forest |
| Serving | FastAPI 0.111.1 | REST API cho BE gọi |
| Data | NASA Ames Battery Dataset | 34 batteries, format CSV |

### Pipeline inference hoàn chỉnh

```
Sensor readings (30 timesteps × 3 features)
         │
         ▼
[MinMaxScaler] — scale về [0, 1]
         │
         ▼
[MambaSOHPredictor] — predict SOH%
         │
         ├─► SOH % (0–100)
         │
[IsolationForest] — anomaly score
         │
         ├─► score > -0.1          → "Normal"
         ├─► score > -0.3 | SOH≥80 → "Degrading"
         └─► else                  → "Failed"
         │
         ▼
Response: {soh_percent, classification, confidence, inference_ms}
Latency : < 100ms (P1 SLA requirement)
```

---

## 4. Model Architecture

### 4.1. MambaSOHPredictor (SOH Regression)

```
Input: (batch, 30, 3)
  │
  ▼ Linear(3 → 64)               # Input projection
  │
  ▼ MambaBlock #1                 # Selective SSM layer 1
  │   ├─ Pre-norm (LayerNorm)
  │   ├─ in_proj: Linear(64 → 256)  → split (x_branch, z_gate)
  │   ├─ Causal depthwise Conv1d(kernel=4)
  │   ├─ Selective SSM scan (ZOH discretization)
  │   │   ├─ A matrix: log-initialized, learnable
  │   │   ├─ B, C, dt: input-dependent (selective)
  │   │   └─ Sequential scan for L=30 (efficient on CPU)
  │   ├─ Gate: output × SiLU(z_gate)
  │   └─ out_proj + residual
  │
  ▼ MambaBlock #2                 # Selective SSM layer 2
  │
  ▼ LayerNorm(64)
  │
  ▼ x[:, -1, :]                  # Last timestep hidden state
  │
  ▼ Linear(64 → 32) + GELU + Dropout(0.2)
  │
  ▼ Linear(32 → 1)
  │
Output: (batch,)                  # SOH% raw — nhân ×100 = SOH%
```

**Tham số:**
- Trainable params: **66,497**
- Inference latency: **< 100ms** trên CPU
- Không cần CUDA — chạy Windows 11 native

> **Tại sao dùng Mamba thay vì LSTM/CNN-LSTM?**  
> Mamba là State Space Model (SSM) thế hệ mới (2023). Với cơ chế selective scan, Mamba học được long-range dependency tốt hơn LSTM mà không bị vanishing gradient. Kết quả nghiên cứu (SambaMixer, arxiv 2024) trên NASA dataset đạt MAE ~0.5–1.2% — tốt hơn CNN-LSTM baseline.

### 4.2. IsolationForest (Anomaly Detection)

```python
IsolationForest(
    contamination = 0.1,    # 10% data ước tính là bất thường
    n_estimators  = 100,    # 100 decision trees
    random_state  = 42,     # seed cố định
)

# Input : flattened window (30 × 3 = 90 features)
# Output: decision_function score (âm hơn = bất thường hơn)
```

**Mapping score → classification:**

| Điều kiện | Label |
|-----------|-------|
| `score > -0.1` | **Normal** |
| `-0.3 < score ≤ -0.1` HOẶC `SOH ≥ 80%` | **Degrading** |
| `score ≤ -0.3` VÀ `SOH < 80%` | **Failed** |

### 4.3. Training Configuration

| Tham số | Giá trị |
|---------|---------|
| Optimizer | Adam |
| Learning rate | 1e-3 |
| Loss function | MSELoss |
| Batch size | 32 |
| Max epochs | 50 |
| Early stopping patience | 10 epochs |
| Random seed | **42** (bắt buộc mọi script) |

### 4.4. Target Metrics

| Metric | Target | Đo trên |
|--------|--------|---------|
| MAE | **< 2.0%** SOH | Test set (B0018 30% cuối) |
| RMSE | **< 3.0%** SOH | Test set |
| Anomaly F1 | **> 0.80** | — |
| Inference latency | **< 100ms** | CPU, batch_size=1 |

---

## 5. Dataset & Training Pipeline

### 5.1. NASA Ames Battery Dataset

| Thông tin | Chi tiết |
|-----------|---------|
| Cell type | 18650 Lithium-ion |
| Tổng batteries | 34 cells (B0005 → B0056) |
| Format gốc | `.mat` (MATLAB) — đã convert sang CSV |
| Nominal capacity | **2.0 Ah** |
| Features | Voltage_measured, Current_measured, Temperature_measured |
| SOH formula | `capacity_current / 2.0 × 100` |

**Train/Val/Test split (cố định, không thay đổi):**

| Split | Battery IDs | Windows | SOH Range |
|-------|-------------|---------|-----------|
| **Train** | B0005, B0006, B0007 | 4,812 | 57.7% – 101.8% |
| **Val** | B0018 (70% đầu timestep) | 767 | 72.0% – 92.8% |
| **Test** | B0018 (30% cuối timestep) | 329 | 67.1% – 73.5% |

> **Tại sao chia theo battery ID chứ không theo timestep?**  
> Chia theo timestep gây **data leakage** — model thấy dữ liệu của cùng 1 pin trong cả train và test, dẫn đến accuracy ảo. Chia theo battery ID đảm bảo model học generalizable pattern.

### 5.2. Preprocessing Pipeline

```
data/raw/nasa/cleaned_dataset/
├── metadata.csv          ← index: battery_id, type, filename, Capacity
└── data/
    ├── 00001.csv         ← 1 cycle/file: V, I, T, Time
    ├── 00002.csv
    └── ...

                      preprocess.py
                          │
                          ▼
1. Đọc metadata.csv → filter discharge cycles có Capacity
2. Với mỗi cycle: đọc CSV → lấy [Voltage, Current, Temp]
3. Sliding windows: stride=30, window=30 (non-overlapping)
4. SOH = Capacity / 2.0 × 100 (label cho mỗi window)
5. Fit MinMaxScaler trên TRAIN → transform val/test
6. Lưu scaler.pkl + {train,val,test}.pt

                          ▼
data/processed/
├── train.pt   ← {"X": Tensor(4812,30,3), "y": Tensor(4812,)}
├── val.pt     ← {"X": Tensor(767,30,3),  "y": Tensor(767,)}
└── test.pt    ← {"X": Tensor(329,30,3),  "y": Tensor(329,)}
```

### 5.3. Training Pipeline

```bash
# Bước 1: Preprocess (chỉ cần chạy 1 lần)
python scripts/preprocess.py \
    --data-dir  data/raw/nasa/cleaned_dataset \
    --output-dir data/processed

# Bước 2: Train
python scripts/train.py \
    --data-dir data/processed \
    --epochs   50 \
    --log-dir  logs/training

# Output:
# logs/training/train_YYYYMMDD_HHMMSS.log   ← training log chi tiết
# models/weights/soh_mamba_v1.0.pth         ← Mamba weights
# models/weights/isolation_forest_v1.0.pkl  ← IF weights
# models/weights/scaler.pkl                 ← MinMaxScaler (đã fit)
```

**Log format mỗi 10 epochs:**
```
2026-06-02 07:23:32  INFO   Epoch    10  0.011364  0.005167  6.1020  7.1879
2026-06-02 07:35:00  INFO   Epoch    20  0.006234  0.002891  3.2015  4.1234
2026-06-02 07:47:00  INFO   Early stopping at epoch 43
2026-06-02 07:47:00  INFO   Test MAE : 1.87%  ✅
2026-06-02 07:47:00  INFO   Test RMSE: 2.31%  ✅
```

### 5.4. Model Artifacts

| File | Size | Mô tả |
|------|------|-------|
| `scaler.pkl` | ~1 KB | MinMaxScaler fit trên train set |
| `soh_mamba_v1.0.pth` | ~270 KB | Mamba weights + metadata |
| `isolation_forest_v1.0.pkl` | ~1.2 MB | Isolation Forest |

> **QUAN TRỌNG:** Cả 3 file phải được **commit vào Git** — inference cần đúng artifacts với training. Không fit lại trên production data.

---

## 6. API Endpoints

### Base URL
```
http://localhost:8000
```

### GET /health

Kiểm tra server đang chạy và model đã load thành công.

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "model_version": "1.0",
  "scaler_loaded": true,
  "lstm_loaded": true,
  "isolation_forest_loaded": true
}
```

---

### POST /predict

Dự đoán SOH và phân loại trạng thái pin từ 30 timestep sensor data.

**Request:**
```json
{
  "battery_id": "B0005",
  "readings": [
    [3.92, -0.99, 25.3],
    [3.87, -0.99, 25.5],
    [3.82, -1.00, 25.7],
    "... (30 rows total)"
  ]
}
```

| Field | Type | Mô tả |
|-------|------|-------|
| `battery_id` | string | ID của pin |
| `readings` | array[30][3] | 30 timestep × [voltage(V), current(A), temperature(°C)] |

**Response:**
```json
{
  "battery_id": "B0005",
  "soh_percent": 84.5,
  "classification": "Normal",
  "confidence": 0.82,
  "inference_ms": 87.4
}
```

| Field | Type | Mô tả |
|-------|------|-------|
| `soh_percent` | float | Sức khỏe pin 0–100% |
| `classification` | string | `Normal` / `Degrading` / `Failed` |
| `confidence` | float | Độ tin cậy 0–1 (từ IF score) |
| `inference_ms` | float | Thời gian xử lý (ms) — phải < 100ms |

**Error cases:**
```json
// readings không phải 30×3
HTTP 422: {"detail": "readings must have 30 timesteps, got 25"}
```

---

## 7. Cấu trúc thư mục

```
ai-module/
│
├── main.py                          ← FastAPI app entry point
│
├── src/
│   ├── models/
│   │   ├── soh_predictor.py         ← MambaBlock + MambaSOHPredictor
│   │   └── anomaly_detector.py      ← classify_anomaly()
│   │
│   ├── schemas/
│   │   └── predict.py               ← PredictRequest, PredictResponse (Pydantic)
│   │
│   ├── routers/
│   │   ├── predict.py               ← POST /predict
│   │   └── health.py                ← GET /health
│   │
│   ├── services/
│   │   └── inference.py             ← run_inference() — full pipeline
│   │
│   └── core/
│       ├── config.py                ← Paths, versions, constants
│       └── model_loader.py          ← Load 3 artifacts khi startup
│
├── scripts/
│   ├── preprocess.py                ← NASA CSV → data/processed/*.pt
│   ├── train.py                     ← Train Mamba + IF, log to logs/training/
│   └── create_dummy_artifacts.py    ← Gen dummy weights cho dev
│
├── tests/
│   ├── test_models.py               ← MambaSOHPredictor forward pass
│   ├── test_inference.py            ← Inference pipeline + latency benchmark
│   ├── test_preprocess.py           ← Preprocessing utils
│   └── test_routers.py              ← FastAPI endpoint tests
│
├── models/
│   └── weights/
│       ├── scaler.pkl               ← MinMaxScaler (PHẢI commit)
│       ├── soh_mamba_v1.0.pth       ← Mamba weights (PHẢI commit)
│       └── isolation_forest_v1.0.pkl ← IF weights (PHẢI commit)
│
├── data/
│   ├── raw/
│   │   └── nasa/
│   │       └── cleaned_dataset/     ← NASA CSV files (KHÔNG commit — .gitignore)
│   │           ├── metadata.csv
│   │           └── data/*.csv
│   └── processed/                   ← Output preprocess.py (KHÔNG commit)
│       ├── train.pt
│       ├── val.pt
│       └── test.pt
│
├── logs/
│   ├── training/
│   │   └── train_YYYYMMDD_HHMMSS.log  ← Training logs
│   └── GH-{number}/
│       ├── plan.md
│       ├── review.md
│       └── test.md
│
├── docs/
│   └── overall.md                   ← File này
│
├── requirements.txt                 ← Python dependencies (pinned)
├── requirements-dev.txt             ← Dev dependencies (pytest, ruff)
└── CLAUDE.md                        ← AI module spec cho Claude Code
```

---

## 8. Hướng dẫn chạy local

### Yêu cầu
- Python 3.11
- Không cần GPU — chạy CPU

### Bước 1: Clone và cài dependencies

```bash
git clone https://github.com/GSU26SE55/ai-module.git
cd ai-module
pip install -r requirements.txt
```

### Bước 2: Tạo dummy artifacts (nếu chưa có)

```bash
python -X utf8 scripts/create_dummy_artifacts.py
```

> App sẽ boot được với dummy artifacts. Prediction sẽ sai nhưng endpoint trả đúng format.

### Bước 3: Chạy FastAPI server

```bash
uvicorn main:app --reload --port 8000
```

Mở browser: `http://localhost:8000/docs` để xem Swagger UI.

### Bước 4: Test endpoint

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "battery_id": "B0005",
    "readings": [
      [3.92, -0.99, 25.3], [3.87, -0.99, 25.5],
      [3.82, -1.00, 25.7], [3.78, -1.00, 25.9],
      [3.74, -0.99, 26.1], [3.70, -1.00, 26.3],
      [3.67, -0.99, 26.5], [3.63, -1.00, 26.7],
      [3.60, -0.99, 26.9], [3.57, -1.00, 27.1],
      [3.54, -0.99, 27.2], [3.51, -1.00, 27.3],
      [3.48, -0.99, 27.4], [3.46, -1.00, 27.5],
      [3.43, -0.99, 27.6], [3.40, -1.00, 27.7],
      [3.38, -0.99, 27.8], [3.35, -1.00, 27.9],
      [3.33, -0.99, 28.0], [3.30, -1.00, 28.1],
      [3.28, -0.99, 28.2], [3.25, -1.00, 28.3],
      [3.23, -0.99, 28.4], [3.20, -1.00, 28.5],
      [3.18, -0.99, 28.6], [3.15, -1.00, 28.7],
      [3.12, -0.99, 28.8], [3.10, -1.00, 28.9],
      [3.08, -0.99, 29.0], [3.05, -1.00, 29.1]
    ]
  }'
```

### Bước 5: Chạy tests

```bash
pytest tests/ -v --cov=src
# Coverage target: ≥ 85%
```

### Bước 6 (Tuỳ chọn): Train thật với NASA data

```bash
# Cần có data trong data/raw/nasa/cleaned_dataset/
python -X utf8 scripts/preprocess.py
python -X utf8 scripts/train.py --epochs 50
```

---

## 9. Kế hoạch Sprint

### Timeline tổng thể: 11/05/2026 → 06/09/2026

| Sprint | Thời gian | AI Tasks | Deliverable |
|--------|-----------|----------|-------------|
| **Sprint 1** ✅ | 11/5 – 1/6 | Setup base, Mamba architecture, preprocessing pipeline, FastAPI skeleton | Code + dummy artifacts, test coverage 90% |
| **Sprint 2** 🔥 | 2/6 – 4/6 | **Train thật 50 epochs**, commit real artifacts, benchmark < 100ms | `soh_mamba_v1.0.pth` real weights |
| **Sprint 3** | 5/6 – 22/6 | SOP Knowledge Base, ChromaDB setup, POST /prescribe (Prescription Layer) | Prescription endpoint |
| **Sprint 4** | 23/6 – 6/7 | Tích hợp BatteryAnomalyDetectedEvent, integration test với BE | End-to-end flow |
| **Sprint 5** | 7/7 – 20/7 | Load test, safety gate, performance optimization | < 100ms P1 confirmed |
| **Sprint 6** | 21/7 – 3/8 | Monitor dashboard, refinement | Realtime metrics |
| **Sprint 7** | 4/8 – 7/8 | System test toàn diện | Final test report |
| **Sprint 8** | 8/8 – 31/8 | IoT pipeline (nếu core xong) | Optional |

---

## 10. Prescription Layer (Sắp triển khai)

> Dựa theo paper: *"From Prediction to Prescription: LLM Agent for Context-Aware Maintenance Decision Support"*  
> Deng et al., PHM Society 2024, Cranfield University.

### Kiến trúc

```
[Mamba Output] → {soh_percent, classification, confidence}
      │
      ▼
Step 1: LLM — Fault Statement Generation
  Input : prediction + battery context
  Output: "Battery B0005 SOH 68.3% — significant capacity fade,
           requires inspection within 24h..."
      │
      ▼
Step 2: LLM — Search Query Generation
  Input : fault statement
  Output: ["battery degradation maintenance SOH 68%",
           "LFP battery inspection procedure",
           "solar battery capacity fade intervention"]
      │
      ▼
Step 3: RAG — SOP Knowledge Base Search (ChromaDB)
  Input : search queries
  Output: relevant SOP procedures (Top-3)
      │
      ▼
Step 4: LLM — Prescription Report
  Input : fault statement + retrieved SOPs
  Output: {action, steps, urgency, sop_reference, safety_warnings}
```

### API mới: POST /prescribe

```json
// Request
{
  "battery_id": "B0005",
  "prediction": {
    "soh_percent": 68.3,
    "classification": "Degrading",
    "confidence": 0.87
  }
}

// Response
{
  "battery_id": "B0005",
  "fault_statement": "Battery B0005 shows significant SOH degradation...",
  "prescription": {
    "action": "Schedule battery inspection",
    "urgency": "Within 24 hours",
    "priority": "P2",
    "steps": [
      "1. Kiểm tra terminal kết nối",
      "2. Đo điện áp từng cell",
      "3. Kiểm tra nhiệt độ vận hành",
      "4. So sánh với baseline capacity"
    ],
    "sop_reference": "SOP-BAT-002",
    "safety_warnings": ["Không charge quá 4.2V", "Dừng nếu nhiệt độ > 60°C"]
  },
  "inference_ms": 1240
}
```

### Tech Stack bổ sung

| Thành phần | Thư viện |
|-----------|---------|
| LLM | Claude API (claude-sonnet-4-6) |
| Vector DB | ChromaDB |
| Embedding | sentence-transformers |
| SOP Docs | Markdown files → `data/sop/` |

---

## 11. Quy ước phát triển

### Git workflow

```
Branch naming : feature/GH-{number}-slug-ngan
Commit message: type(#number): mô tả
                feat(#5): add prescription endpoint
                fix(#6): fix scaler version mismatch

PR requirement: Có "Closes #{number}" trong body
```

### Model versioning

| Phiên bản | Khi nào tăng |
|-----------|-------------|
| `v1.0 → v1.1` | Retrain cùng architecture, khác data/hyperparameter |
| `v1.x → v2.0` | Thay đổi architecture (thêm layer, đổi model) |

> **Bắt buộc:** Commit cả 3 artifacts cùng 1 commit khi update model.

### Các lệnh hay dùng

```bash
# Chạy server
uvicorn main:app --reload

# Chạy toàn bộ test
pytest tests/ -v --cov=src

# Preprocess data
python -X utf8 scripts/preprocess.py

# Train model
python -X utf8 scripts/train.py --epochs 50

# Tạo dummy artifacts (dev)
python -X utf8 scripts/create_dummy_artifacts.py

# Lint & format
ruff check src/ scripts/ tests/
ruff format src/ scripts/ tests/
```

### Environment variables

Không có biến môi trường bắt buộc cho Prediction layer.  
Prescription layer sẽ cần thêm:
```
ANTHROPIC_API_KEY=sk-ant-...   # Claude API (Sprint 3)
```

---

> **Liên hệ:** dl-2601-soul5@dream-lab.ai  
> **Repo:** https://github.com/GSU26SE55/ai-module
