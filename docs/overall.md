# AI Module — Tài liệu tổng quan

> **Dự án:** Solar Lithium-ion Battery Maintenance Management System
> **Nhóm:** GSU26SE55 | **GVHD:** Trương Long
> **Cập nhật:** 2026-06-21

---

## Mục lục

1. [Tổng quan dự án](#1-tổng-quan-dự-án)
2. [Kiến trúc hệ thống](#2-kiến-trúc-hệ-thống)
3. [AI Module — Chi tiết](#3-ai-module--chi-tiết)
4. [Model Architecture](#4-model-architecture)
5. [Feature Engineering](#5-feature-engineering)
6. [Dataset & Training Pipeline](#6-dataset--training-pipeline)
7. [API Endpoints](#7-api-endpoints)
8. [Cấu trúc thư mục](#8-cấu-trúc-thư-mục)
9. [Hướng dẫn chạy local](#9-hướng-dẫn-chạy-local)
10. [Kế hoạch Sprint](#10-kế-hoạch-sprint)
11. [Prescription Layer (Sắp triển khai)](#11-prescription-layer-sắp-triển-khai)
12. [Quy ước phát triển](#12-quy-ước-phát-triển)

---

## 1. Tổng quan dự án

### Mục tiêu

Xây dựng nền tảng **giám sát và bảo trì pin lithium-ion** cho hệ thống năng lượng mặt trời, bao gồm:

- Dự đoán **State of Health (SOH)** của pin theo thời gian thực
- Ước tính **Remaining Useful Life (RUL)** — số chu kỳ còn lại đến End-of-Life
- Phát hiện **bất thường** (anomaly) trước khi pin hỏng
- Tự động tạo **ticket bảo trì** theo chuẩn ITIL với SLA P1/P2/P3
- Cung cấp **prescription** — kế hoạch bảo trì từng bước có căn cứ khoa học

### Hệ thống 3 lớp

```
┌──────────────────────────────────────────────┐
│  Mobile App (React Native / Expo)             │
│  Customer xem trạng thái pin real-time        │
├──────────────────────────────────────────────┤
│  Web App (ReactJS)                            │
│  Admin / Manager / Staff quản lý ticket       │
├──────────────────────────────────────────────┤
│  AI Module (FastAPI + PyTorch)                │  ← File này mô tả phần này
│  SOH prediction · RUL · Anomaly detection    │
└──────────────────────────────────────────────┘
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
     │  (voltage, current, temperature, ... — mỗi ~13s/reading)
     ▼
[IoT Sensor] ──────────────────────────────────────────────────┐
                                                               │
                                              POST /predict    │
[BatteryService (BE)] ────────────────────► [AI Module]       │
                                              ◄────────────────┘
                                              {soh_percent,
                                               classification,
                                               confidence,
                                               rul_cycles_estimate,
                                               recommended_action,
                                               warnings, ...}
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
| **P1 Critical** | SOH < 80% / nguy cơ an toàn / scope Site-MultiSite | **4h** | Reassign Senior + notify Admin |
| **P2 High** | SOH 80–85% / anomaly score ≤ -0.3 | **24h** | Manager reassign |
| **P3 Standard** | SOH 85–90% / anomaly warning | **72h** | Manager review |

---

## 3. AI Module — Chi tiết

### Stack công nghệ

| Quyết định | Lựa chọn | Ghi chú |
|-----------|----------|---------|
| Language | Python 3.11 | — |
| ML Framework | PyTorch 2.3.1 | Pure-PyTorch SSM — không cần CUDA |
| Anomaly Detection | scikit-learn 1.5.0 | Isolation Forest |
| Signal Processing | scipy 1.13.1 | FFT-based spectral features |
| Serving | FastAPI 0.111.1 | REST API cho BE gọi |
| Dataset | NASA Ames Battery Dataset | 34 batteries, format CSV |

### Pipeline inference — Production (window=30)

```
Sensor readings (30 timesteps × 6 features)
  [voltage, current, temperature, current_load, voltage_load, time]
  (legacy: 30 × 3 cũng được nhận, tự động align)
         │
         ▼
[MinMaxScaler] — scale 6-feature về [0, 1]
         │
         ├──────────────────────────────────────────────────┐
         ▼                                                  │
[extract_window_features]                                   │
  → 54-dim spectral + kurtosis (từ 3 channels đầu)         │
         │                                                  │
         ▼                                                  │
[StandardScaler (feature_scaler)]                           │
  → scale 54-dim về zero-mean unit-variance                 │
         │                                                  ▼
         ├────────────────────► [MambaSOHPredictor v1.2]
         │  x_feat (FiLM)        × MC Dropout 20 runs
         │                       → SOH% (mean) + soh_std
         │                       → confidence = 1 - soh_std/5.0
         │
         ▼
[IsolationForest v1.2] ← input: 54-dim (đã scale)
  → anomaly_score (decision_function)
  → anomaly_status: Normal / Warning / Anomaly
         │
         ▼
[classify_anomaly(score, soh)]
  SOH < 80%            → "Failed"
  SOH 80–90%           → "Degrading"
  SOH ≥ 90% & score < -0.1 → "Degrading"
  SOH ≥ 90% & score ≥ -0.1 → "Normal"
         │
         ▼
[compute_degradation_metrics] — RUL, trend, trajectory
[compute_risk_profile]        — priority P1/P2/P3, action_code
[generate_warnings]           — threshold-based sensor warnings
         │
         ▼
Response: {soh_percent, classification, confidence,
           rul_cycles_estimate, cycles_to_maintenance,
           anomaly_score, recommended_action, warnings,
           feature_summary, risk, ...}
Latency : < 100ms (P1 SLA requirement)
```

### Pipeline inference — Long (L=4096, GH-10)

```
Sensor readings (L timesteps × 6 features), L ≤ 4096
         │
         ▼
[compute_ic_feature + compute_phase_mask]
  → 8 features: [V, I, T, I_load, V_load, time, dQ/dV, phase]
         │
         ▼
[MinMaxScaler (scaler_long)] — 8-feature
         │
         ▼
[extract_window_features] — 54-dim từ 3 channels đầu
  → StandardScaler (long_feature_scaler)
         │
         ▼
[MambaSOHPredictor v2.0 — long]
  patch_size=16, stride=16 → 256 tokens từ 4096 raw
  PatchDegradationEncoder: RMS/P2P/std/kurtosis per patch
  Attention pooling
  FiLM conditioning (x_feat)
  → SOH% (single forward pass, không MC Dropout)
         │
         ▼
Response: {soh_percent, seq_len, device, inference_ms}
(Anomaly + RUL out of scope cho long pipeline)
```

---

## 4. Model Architecture

### 4.1. MambaSOHPredictor — Production (L=30)

> **Pure PyTorch SSM** — không dùng `mamba-ssm` CUDA library, chạy Windows 11 native.
> Artifact: `models/weights/soh_mamba_v1.2.pth`

```
Input: (batch, 30, 6)   ← 30 timestep × [V, I, T, I_load, V_load, time]
  │
  ▼ Linear(6 → 64)                # Input projection
  │
  ▼ MambaBlock #1                 # Selective SSM layer 1
  │   ├─ Pre-norm (LayerNorm)
  │   ├─ in_proj: Linear(64 → 256, bias=True) → split (x_branch, z_gate)
  │   ├─ Causal depthwise Conv1d(kernel=4, groups=d_inner)
  │   ├─ Selective SSM scan (ZOH discretization, fp32 internal)
  │   │   ├─ dt_rank = ceil(d_model/16) = 4
  │   │   ├─ A: log-initialized, learnable (d_inner × d_state)
  │   │   ├─ B, C, dt: input-dependent (selective)
  │   │   └─ Sequential scan for L=30 (vectorized chunked scan for L>32)
  │   ├─ Gate: output × SiLU(z_gate)
  │   └─ out_proj + residual
  │
  ▼ MambaBlock #2                 # Selective SSM layer 2
  │
  ▼ LayerNorm(64)
  │
  ▼ h[:, -1, :]                   # Last timestep hidden state (pooling="last")
  │
  ▼ FiLM conditioning             # 2-layer MLP: feat_54 → γ + β
  │   film_proj: Linear(54→54) → SiLU → Linear(54→128)
  │   h = (sigmoid(γ)+0.5) × h + β
  │
  ▼ Linear(64 → 32) + GELU + Dropout(0.2)
  │
  ▼ Linear(32 → 1)
  │
Output: (batch,)                  # SOH raw → ×100 = SOH%
```

**Tham số:**
- Trainable params: **~66K–305K** (phụ thuộc version)
- Inference: MC Dropout 20 runs → confidence từ std
- Không cần CUDA — chạy Windows 11 native

### 4.2. MambaSOHPredictor — Long Sequence (L=4096, GH-10)

> Artifact: `models/weights/soh_mamba_long_v2.0.pth`
> Loaded lazily — không load khi startup, chỉ load khi gọi `/predict-long`

```
Input: (batch, L, 8)   ← L ≤ 4096, 8 features (6 base + IC + phase)
  │
  ▼ Conv1d(8, 64, kernel=16, stride=16)   # Patch embedding
    → (batch, 256, 64)                    # 4096 raw → 256 tokens (16× nén)
  │
  ▼ PatchDegradationEncoder              # Per-patch local degradation stats
  │   RMS, peak-to-peak, std, kurtosis × 8 channels per patch
  │   → Linear(32→64) → LayerNorm
  │   → added vào patch token embeddings
  │
  ▼ MambaBlock × 2
  │
  ▼ LayerNorm(64)
  │
  ▼ Attention Pooling                    # pooling="attention"
  │   score = Linear(64→1)
  │   Discharge-bias: patch có phase=discharge được ưu tiên
  │   h = Σ(softmax(score) × token)
  │
  ▼ FiLM conditioning (54-dim)           # same as production
  │
  ▼ Linear(64→32) + GELU + Dropout → Linear(32→1)
  │
Output: (batch,)   # SOH%
```

**Kết quả training (Kaggle GPU, 2026-06-20):**

| Metric | Kết quả | Target |
|--------|---------|--------|
| Test MAE | **1.6293%** | < 2.0% ✅ |
| Test RMSE | **2.0871%** | < 3.0% ✅ |
| Early stop | epoch 41/50 | — |

**Config:**
```
seq_len=4096 | patch P16S16 → 256 tokens
Warmup stages: [256, 512, 1024, 2048, 4096] × 3 epochs/stage
Final stage: LR=5e-4, CosineAnnealingWarmRestarts T_0=25 T_mult=2
Loss: SmoothL1(beta=0.02) | AMP fp16 | micro_batch=8 × accum=4 = eff_batch=32
```

### 4.3. RULPredictor — Cycle-axis Mamba (GH-13)

> Artifact: `models/weights/soh_mamba_rul_v1.0.pth`

```
Input: (batch, 30, 54)   ← 30 chu kỳ × 54-dim per-cycle feature vector
  │
  ▼ Linear(54 → 64)
  │
  ▼ MambaBlock × 2
  │
  ▼ LayerNorm → pooling (last | attention)
  │
  ▼ Linear(64→32) + GELU + Dropout → Linear(32→1)
  │
Output: (batch,)   # normalized RUL × 200 = số chu kỳ còn lại
```

> Token hóa theo **chu kỳ** thay vì raw timestep. Mỗi token = 54-dim spectral+kurtosis của 1 discharge cycle. EOL threshold = 80% SOH.

### 4.4. IsolationForest (Anomaly Detection)

```python
IsolationForest(
    contamination = 0.1,    # 10% data ước tính bất thường (Liu et al. ICDM 2008)
    n_estimators  = 100,    # variance hội tụ ≥ 100 trees
    random_state  = 42,
)

# Input : 54-dim spectral+kurtosis features (StandardScaler'd)
# Output: decision_function score (âm hơn = bất thường hơn)
```

**Mapping score → anomaly_status:**

| Score | anomaly_status |
|-------|---------------|
| `score > -0.1` | **Normal** |
| `-0.3 < score ≤ -0.1` | **Warning** |
| `score ≤ -0.3` | **Anomaly** |

**Mapping (score + SOH) → classification:**

| Điều kiện | classification |
|-----------|---------------|
| `SOH < 80%` | **Failed** |
| `SOH 80–90%` | **Degrading** |
| `SOH ≥ 90%` AND `score < -0.1` | **Degrading** |
| `SOH ≥ 90%` AND `score ≥ -0.1` | **Normal** |

**Health stage → Risk → Priority:**

| Health Stage | Risk | Priority | Action |
|---|---|---|---|
| End Of Life (SOH < 80%) | Critical | **P1** | REPLACE_IMMEDIATELY |
| Maintenance Required (SOH 80–85%) | High | **P2** | SCHEDULE_REPLACEMENT |
| Degrading (SOH 85–90%) | Medium | **P3** | SCHEDULE_MAINTENANCE |
| Healthy (SOH ≥ 90%) | Low | None | MONITOR |

> Critical sensor warning (voltage/temp) override: luôn đẩy lên P1 bất kể SOH.

### 4.5. Training Configuration

| Tham số | Production (L=30) | Long (L=4096) |
|---------|-------------------|---------------|
| Optimizer | Adam | Adam |
| Learning rate | 1e-3 | 5e-4 (final stage) |
| Loss | SmoothL1(beta=0.02) | SmoothL1(beta=0.02) |
| Batch size (eff.) | 32 | 32 (micro=8 × accum=4) |
| Max epochs | 50 | 50 (final stage) |
| Early stopping patience | 30 | 30 |
| LR scheduler | CosineAnnealingWarmRestarts T_0=25 T_mult=2 | CosineAnnealingWarmRestarts T_0=25 T_mult=2 |
| Random seed | **42** | **42** |
| Warmup | — | stages [256, 512, 1024, 2048, 4096] × 3 epochs |
| AMP | — | fp16 (GPU) |

### 4.6. Target Metrics

| Metric | Target | Đạt được |
|--------|--------|---------|
| MAE (production L=30) | **< 2.0%** SOH | 1.87% ✅ |
| RMSE (production L=30) | **< 3.0%** SOH | 2.31% ✅ |
| MAE (long L=4096) | **< 2.0%** SOH | **1.6293%** ✅ |
| RMSE (long L=4096) | **< 3.0%** SOH | **2.0871%** ✅ |
| Anomaly F1 | **> 0.80** | — |
| Inference latency | **< 100ms** | CPU, batch_size=1 |

---

## 5. Feature Engineering

### 5.1. Spectral + Kurtosis Features (54-dim)

Module `src/features/extractor.py` — trích xuất từ window sau khi scale, dùng cho **FiLM conditioning** (MambaSOHPredictor) và **IsolationForest** (anomaly detection).

Input: chuỗi đã scale, lấy 3 channels đầu (voltage, current, temperature).

**Spectral features (9 per channel — FFT-based):**

| Feature | Mô tả |
|---------|-------|
| `centroid` | Trung tâm năng lượng phổ tần số |
| `entropy` | Entropy phổ — đo độ phân tán tần số |
| `peak_freq` | Tần số có năng lượng cao nhất |
| `peak_power_db` | Công suất đỉnh (dB) |
| `flatness` | Spectral flatness (nhiễu trắng ≈ 1) |
| `rolloff` | Tần số chứa 85% tổng năng lượng |
| `band_low/mid/high` | Phân bổ năng lượng 3 dải tần |

**Statistical features (9 per channel — time-domain):**

| Feature | Mô tả |
|---------|-------|
| `mean`, `std` | Trung bình, độ lệch chuẩn |
| `skewness` | Độ lệch phân phối |
| `kurtosis` | "Đuôi nặng" — nhạy với spike dị thường |
| `crest_factor` | Peak / RMS — đo xung đột |
| `waveform_factor` | RMS / mean |
| `pulse_factor` | Peak / mean |
| `margin_factor` | Peak / RMS² |
| `peak_to_peak` | Biên độ dao động |

**Tổng:** `(9 spectral + 9 statistical) × 3 channels = 54 features`

### 5.2. Per-patch Degradation Stats — PatchDegradationEncoder (Long model)

Trong long model (L=4096), mỗi patch 16-step được bổ sung local stats:

| Stat | Ý nghĩa |
|------|---------|
| RMS | Năng lượng trung bình trong patch |
| Peak-to-peak | Biên độ dao động trong patch |
| Std | Độ biến động tín hiệu |
| Excess kurtosis | Chỉ số xung — cao khi gần EOL / fault |

`4 stats × input_features channels = 32-dim` → project to d_model, add vào patch token.

> Overcomes bottleneck của global FiLM averaging khi L=4096 spans 100+ discharge cycles. Inspired by DualMamba (Frontiers CS 2026) và BatteryML (arXiv 2310.14714).

### 5.3. IC Curve + Phase Mask (Long model only)

`src/features/extractor.py`: `compute_ic_feature` + `compute_phase_mask`

| Feature | Ý nghĩa vật lý |
|---------|----------------|
| `dQ/dV` (IC curve) | Incremental Capacity — phát hiện phase transition pin |
| `phase_mask` | 0=rest, 1=charge, 2=discharge — giúp attention focus vào discharge |

> IC curve nhạy cảm với degradation cơ học (lithium plating, particle cracking). Dubarry & Liaw, 2009.

---

## 6. Dataset & Training Pipeline

### 6.1. NASA Ames Battery Dataset

| Thông tin | Chi tiết |
|-----------|---------|
| Cell type | 18650 Lithium-ion |
| Tổng batteries | 34 cells (B0005 → B0056) |
| Format gốc | `.mat` (MATLAB) — đã convert sang CSV |
| Nominal capacity | **2.0 Ah** |
| Features | Voltage_measured, Current_measured, Temperature_measured, Current_load, Voltage_load, Time |
| SOH formula | `capacity_current / 2.0 × 100` |

**Train/Val/Test split (cố định, không thay đổi):**

| Split | Battery IDs | Windows (L=30) | SOH Range |
|-------|-------------|----------------|-----------|
| **Train** | B0005, B0006, B0007 | 4,812 | 57.7% – 101.8% |
| **Val** | B0018 (70% đầu) | 767 | 72.0% – 92.8% |
| **Test** | B0018 (30% cuối) | 329 | 67.1% – 73.5% |

**Long model split (L=4096):**

| Split | Samples | Ghi chú |
|-------|---------|---------|
| Train | 4,411 | stride=64 trên B0005/06/07 |
| Val | 622 | B0018 (70% đầu) |
| Test | 311 | B0018 (30% cuối) |

> **Tại sao chia theo battery ID?** Chia theo timestep gây **data leakage** — model thấy cùng 1 pin trong cả train và test → accuracy ảo. Chia theo battery ID đảm bảo generalization thực sự.

### 6.2. Preprocessing Pipeline

```
data/raw/nasa/cleaned_dataset/
├── metadata.csv          ← battery_id, type, filename, Capacity
└── data/
    ├── 00001.csv         ← 1 cycle/file: V, I, T, I_load, V_load, Time
    └── ...

─── scripts/preprocess.py ───────────────────────────────── (L=30, production)
1. Đọc metadata.csv → filter discharge cycles có Capacity
2. Mỗi cycle: đọc CSV → lấy 6 features
3. Sliding windows: window=30, stride=30 (non-overlapping)
4. SOH = Capacity / 2.0 × 100
5. Fit MinMaxScaler(6-feat) trên TRAIN → transform val/test
6. Fit StandardScaler(54-feat) trên TRAIN spectral features
7. Lưu scaler.pkl + feature_scaler.pkl + {train,val,test}.pt

─── scripts/preprocess_long.py ──────────────────────────── (L=4096, GH-10)
v2: 8-feature data: [V, I, T, I_load, V_load, time, dQ/dV, phase]
Sliding windows: window=4096, stride=64
→ scaler_long.pkl + feature_scaler_long.pkl + long_{train,val,test}.pt
```

### 6.3. Training Pipeline

```bash
# Production model (L=30)
python scripts/preprocess.py --data-dir data/raw/nasa/cleaned_dataset
python scripts/train.py --data-dir data/processed --epochs 50

# Output:
# models/weights/scaler.pkl                    ← 6-feat MinMaxScaler
# models/weights/feature_scaler.pkl            ← 54-dim StandardScaler
# models/weights/soh_mamba_v1.2.pth            ← Mamba weights
# models/weights/isolation_forest_v1.2.pkl     ← IsolationForest

# Long model (L=4096) — chạy trên Kaggle GPU
python scripts/preprocess_long.py
python scripts/train.py --long --epochs 50

# Output:
# models/weights/scaler_long.pkl               ← 8-feat MinMaxScaler
# models/weights/feature_scaler_long.pkl       ← 54-dim StandardScaler
# models/weights/soh_mamba_long_v2.0.pth       ← Long Mamba weights
```

**Log format — Long model (Kaggle 2026-06-20):**
```
INFO  Train 4411 | Val 622 | Test 311 | seq_len=4096
INFO  Patch: size=16 stride=16 → 256 tokens (16× compression)
INFO  Warmup stages: [256, 512, 1024, 2048, 4096] | micro_batch=8 accum=4
INFO  [stage 1/5] L=256  epochs=3
...
INFO  Final stage: LR=0.0005, CAWR T_0=25 T_mult=2 eta_min=1e-5
INFO  Early stopping at epoch 41 (patience=30)
INFO  Test MAE : 1.6293%  ✅
INFO  Test RMSE: 2.0871%  ✅
```

### 6.4. Scripts tổng quan

| Script | Mục đích |
|--------|---------|
| `preprocess.py` | NASA CSV → `data/processed/*.pt` (6-feature, L=30) |
| `preprocess_long.py` | NASA CSV → long-context data (8-feature, L=4096) |
| `preprocess_rul.py` | NASA CSV → RUL dataset (per-cycle 54-dim features) |
| `preprocess_forecast.py` | NASA CSV → multi-step SOH forecast dataset |
| `train.py` | Train MambaSOHPredictor + IsolationForest (cả short lẫn long) |
| `experiment_nowcast_lobo.py` | LOBO cross-validation cho multi-battery |
| `experiment_nowcast_multi.py` | Multi-battery nowcast experiment |
| `create_dummy_artifacts.py` | Gen dummy weights cho dev (không cần real data) |
| `benchmark_tokens.py` | Benchmark inference latency |

### 6.5. Model Artifacts

| File | Size | Dùng cho | Phải commit |
|------|------|---------|-------------|
| `scaler.pkl` | ~1 KB | MinMaxScaler 6-feat (production) | ✅ |
| `feature_scaler.pkl` | ~2 KB | StandardScaler 54-dim (production) | ✅ |
| `soh_mamba_v1.2.pth` | ~306 KB | Production Mamba (L=30) | ✅ |
| `isolation_forest_v1.2.pkl` | ~1.75 MB | IsolationForest (production) | ✅ |
| `scaler_long.pkl` | ~1 KB | MinMaxScaler 8-feat (long model) | ✅ |
| `feature_scaler_long.pkl` | ~2 KB | StandardScaler 54-dim (long model) | ✅ |
| `soh_mamba_long_v2.0.pth` | ~306 KB | Long Mamba (L=4096) | ✅ |
| `feature_scaler_rul.pkl` | ~2 KB | StandardScaler 54-dim (RUL model) | ✅ |
| `soh_mamba_rul_v1.0.pth` | ~290 KB | RUL Predictor | ✅ |

> **QUAN TRỌNG:** Tất cả artifacts phải **commit vào Git** cùng 1 commit khi update. Không fit lại scaler/IF trên production data.

---

## 7. API Endpoints

### Base URL
```
http://localhost:8000
```

### GET /health

```json
{
  "status": "ok",
  "model_version": "1.2",
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
    [3.92, -0.99, 25.3, -1.00, 3.90, 0.0],
    "... (30 rows: [voltage, current, temperature, current_load, voltage_load, time])"
  ]
}
```

> Legacy 3-feature `[voltage, current, temperature]` vẫn được nhận — tự động align.

**Response (đầy đủ):**
```json
{
  "battery_id": "B0005",

  "prediction": {
    "soh_percent": 84.5,
    "health_stage": "Degrading",
    "rul_cycles_estimate": 30,
    "cycles_to_maintenance": 0
  },

  "anomaly": {
    "anomaly_score": -0.12,
    "anomaly_status": "Warning",
    "anomaly_confidence": 0.12
  },

  "risk": {
    "risk_level": "Medium",
    "priority": "P3",
    "action_code": "SCHEDULE_MAINTENANCE",
    "reasons": ["SOH 84.5% indicates degradation below 90%"]
  },

  "evidence": {
    "warnings": [
      {"code": "SOH_LOW", "severity": "warning", "message": "SOH 84.5% is below 90%..."}
    ],
    "feature_summary": {
      "voltage": {"mean": 3.52, "min": 3.05, "max": 3.92},
      "current": {"mean": -0.99, "min": -1.00, "max": -0.99},
      "temperature": {"mean": 27.1, "min": 25.3, "max": 29.1}
    }
  },

  "metadata": {
    "model_version": "1.2",
    "window_size": 30,
    "input_features": 6,
    "inference_ms": 87.4
  },

  "soh_percent": 84.5,
  "classification": "Degrading",
  "confidence": 0.82,
  "inference_ms": 87.4,

  "rul_cycles_estimate": 30,
  "cycles_to_maintenance": 0,
  "anomaly_score": -0.12,
  "recommended_action": "SCHEDULE_MAINTENANCE",
  "warnings": [...],
  "feature_summary": {...}
}
```

> Flat fields (`soh_percent`, `classification`, ...) là backward-compatible — giữ đến khi BE migrate sang nested response.

**Error cases:**
```json
// readings không phải 30 timestep
HTTP 422: {"detail": "readings must have 30 timesteps, got 25"}

// features không phải 3 hoặc 6
HTTP 422: {"detail": "readings[0] must have one of {3, 6} feature counts"}
```

---

## 8. Cấu trúc thư mục

```
ai-module/
│
├── main.py                          ← FastAPI app entry point
│
├── src/
│   ├── models/
│   │   ├── soh_predictor.py         ← MambaBlock + MambaSOHPredictor (production + long)
│   │   ├── rul_predictor.py         ← RULPredictor — cycle-level Mamba
│   │   └── anomaly_detector.py      ← classify_anomaly, compute_risk_profile, generate_warnings
│   │
│   ├── features/
│   │   └── extractor.py             ← 54-dim spectral+kurtosis, IC curve, phase mask
│   │
│   ├── schemas/
│   │   └── predict.py               ← PredictRequest, PredictResponse (Pydantic)
│   │
│   ├── routers/
│   │   ├── predict.py               ← POST /predict
│   │   └── health.py                ← GET /health
│   │
│   ├── services/
│   │   ├── inference.py             ← run_inference() + predict_soh_long()
│   │   └── confidence.py            ← MC Dropout confidence
│   │
│   └── core/
│       ├── config.py                ← Paths, versions, hyperparameters
│       └── model_loader.py          ← load_models() (startup) + load_long_model() (lazy)
│
├── scripts/
│   ├── preprocess.py                ← NASA CSV → *.pt (6-feat, L=30)
│   ├── preprocess_long.py           ← NASA CSV → *.pt (8-feat, L=4096)
│   ├── preprocess_rul.py            ← RUL dataset (per-cycle features)
│   ├── preprocess_forecast.py       ← Multi-step forecast dataset
│   ├── train.py                     ← Train Mamba + IsolationForest (short + long)
│   ├── experiment_nowcast_lobo.py   ← LOBO cross-validation
│   ├── experiment_nowcast_multi.py  ← Multi-battery experiment
│   ├── benchmark_tokens.py          ← Latency benchmark
│   └── create_dummy_artifacts.py    ← Dummy artifacts cho dev
│
├── tests/
│   ├── test_models.py               ← MambaSOHPredictor forward pass
│   ├── test_inference.py            ← Pipeline + latency benchmark
│   ├── test_preprocess.py           ← Preprocessing utils
│   ├── test_routers.py              ← FastAPI endpoint tests
│   └── test_rul.py                  ← RULPredictor tests
│
├── models/
│   └── weights/
│       ├── scaler.pkl               ← MinMaxScaler 6-feat (PHẢI commit)
│       ├── feature_scaler.pkl       ← StandardScaler 54-dim (PHẢI commit)
│       ├── soh_mamba_v1.2.pth       ← Production Mamba (PHẢI commit)
│       ├── isolation_forest_v1.2.pkl ← IsolationForest (PHẢI commit)
│       ├── scaler_long.pkl          ← MinMaxScaler 8-feat long (PHẢI commit)
│       ├── feature_scaler_long.pkl  ← StandardScaler 54-dim long (PHẢI commit)
│       ├── soh_mamba_long_v2.0.pth  ← Long Mamba (PHẢI commit)
│       ├── feature_scaler_rul.pkl   ← StandardScaler 54-dim RUL (PHẢI commit)
│       └── soh_mamba_rul_v1.0.pth   ← RUL Predictor (PHẢI commit)
│
├── data/
│   ├── raw/nasa/cleaned_dataset/    ← NASA CSV (KHÔNG commit — .gitignore)
│   └── processed/                   ← Output preprocess.py (KHÔNG commit)
│
├── logs/
│   ├── training/                    ← Training logs
│   └── GH-{number}/                 ← plan.md, review.md, test.md
│
├── docs/
│   └── overall.md                   ← File này
│
├── requirements.txt
├── requirements-dev.txt
└── CLAUDE.md
```

---

## 9. Hướng dẫn chạy local

### Yêu cầu

- Python 3.11
- Không cần GPU — CPU-only inference

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

> App boot được với dummy artifacts. Prediction sai nhưng endpoint trả đúng format.

### Bước 3: Chạy FastAPI server

```bash
uvicorn main:app --reload --port 8000
```

Mở `http://localhost:8000/docs` để xem Swagger UI.

### Bước 4: Test endpoint

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "battery_id": "B0005",
    "readings": [
      [3.92, -0.99, 25.3, -1.00, 3.90, 0.0],
      [3.87, -0.99, 25.5, -1.00, 3.85, 13.0],
      "... (30 rows total)"
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
python -X utf8 scripts/preprocess.py
python -X utf8 scripts/train.py --epochs 50
```

---

## 10. Kế hoạch Sprint

### Timeline tổng thể: 11/05/2026 → 06/09/2026

| Sprint | Thời gian | AI Tasks | Deliverable |
|--------|-----------|----------|-------------|
| **Sprint 1** ✅ | 11/5 – 1/6 | Setup base, Mamba architecture, preprocessing pipeline, FastAPI skeleton | Code + dummy artifacts, test coverage ≥ 90% |
| **Sprint 2** ✅ | 2/6 – 21/6 | Train production model, FiLM conditioning, spectral features, long-seq L=4096 (GH-10), RULPredictor | `soh_mamba_v1.2.pth` + `soh_mamba_long_v2.0.pth` — MAE < 2% ✅ |
| **Sprint 3** 🔥 | 22/6 – 6/7 | SOP Knowledge Base, ChromaDB, POST /prescribe (Prescription Layer) | Prescription endpoint live |
| **Sprint 4** | 7/7 – 20/7 | Tích hợp BatteryAnomalyDetectedEvent, integration test với BE | End-to-end flow |
| **Sprint 5** | 21/7 – 3/8 | Load test, safety gate, performance optimization | < 100ms P1 confirmed |
| **Sprint 6** | 4/8 – 17/8 | Monitor dashboard, refinement | Realtime metrics |
| **Sprint 7** | 18/8 – 31/8 | System test toàn diện | Final test report |
| **Sprint 8** | (optional) | IoT pipeline nếu core xong | — |

---

## 11. Prescription Layer (Sprint 3)

> **Cơ sở khoa học:** *"From Prediction to Prescription: LLM Agent for Context-Aware Maintenance Decision Support"*
> Deng et al., PHM Society 2024, Cranfield University — [github.com/BlueAsuka/Rocket-RAG](https://github.com/BlueAsuka/Rocket-RAG)

### 11.1. Lý do thiết kế

ML model (Mamba + Isolation Forest) chỉ trả **prediction** — một con số và nhãn phân loại. Đó là **notification**, không phải **hành động**. Staff nhận alert nhưng không biết làm gì tiếp theo trong hệ thống pin mặt trời.

**Prescription Layer** biến output của prediction thành **kế hoạch bảo trì từng bước**, tự động điền nội dung ticket cho TicketService, giảm tải quyết định cho Staff.

```
Không có Prescription:
  SOH 68% → "Failed" → Staff tự viết ticket → sai SOP → P1 breach

Có Prescription:
  SOH 68% → "Failed" → LLM+RAG → "Thay thế ngay, SOP-BAT-001 §3.2,
             kiểm tra voltage trước khi tháo, báo Admin" → ticket tự điền
```

---

### 11.2. Kiến trúc pipeline đầy đủ

```
┌────────────────────────────────────────────────────────────────┐
│                    POST /prescribe                              │
│  {battery_id, prediction: {soh%, classification, confidence,  │
│   anomaly_score, risk.priority, warnings[]}}                   │
└────────────────────────┬───────────────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │  Step 1             │
              │  Fault Statement    │  ← LLM (Claude Haiku)
              │  Generation         │
              │                     │
              │  Input:             │
              │  · prediction JSON  │
              │  · battery context  │  ← system prompt cố định
              │    (SOP domain,     │
              │     solar context)  │
              │                     │
              │  Output:            │
              │  Fault statement    │  → "Pin B0005 SOH 68.3%,
              │  (structured text)  │     Failed, anomaly Anomaly,
              └──────────┬──────────┘     cần thay thế khẩn cấp..."
                         │
              ┌──────────▼──────────┐
              │  Step 2             │
              │  Search Query       │  ← LLM (Claude Haiku)
              │  Generation         │
              │                     │
              │  Input:             │
              │  · fault statement  │
              │                     │
              │  Output: 3–5 queries│  → ["lithium battery SOH below 80
              │  (JSON array)       │      replacement procedure",
              │                     │     "solar battery failed safety
              └──────────┬──────────┘      checklist", ...]
                         │
              ┌──────────▼──────────┐
              │  Step 3             │
              │  RAG — ChromaDB     │  ← Vector similarity search
              │  Knowledge Base     │
              │                     │
              │  Input:             │
              │  · 3–5 queries      │
              │                     │
              │  Process:           │
              │  · embed queries    │  ← sentence-transformers
              │    (all-MiniLM-L6)  │    (local, không cần API)
              │  · cosine search    │
              │    top-3 per query  │
              │  · dedup + rank     │  → max 5 unique SOP chunks
              │                     │
              │  Output:            │
              │  · SOP chunks       │  → [SOP-BAT-001 §3, SOP-BAT-002 §1,
              │  · source refs      │     SAFETY-LI-003 §2]
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  Step 4             │
              │  Prescription       │  ← LLM (Claude Haiku)
              │  Report Generation  │
              │                     │
              │  Input:             │
              │  · fault statement  │
              │  · SOP chunks       │
              │  · priority (P1/2/3)│
              │                     │
              │  Output (JSON):     │
              │  · action_title     │
              │  · urgency          │
              │  · steps[]          │  → bước bảo trì cụ thể
              │  · sop_references[] │  → [SOP-BAT-001, ...]
              │  · safety_warnings[]│
              │  · ticket_description│ → text điền thẳng vào ticket
              └─────────────────────┘
```

---

### 11.3. Knowledge Base — SOP Documents

**Cấu trúc thư mục:**

```
data/sop/
├── SOP-BAT-001.md    ← Thay thế pin (Failed — SOH < 80%)
├── SOP-BAT-002.md    ← Bảo trì định kỳ (Degrading — SOH 80–90%)
├── SOP-BAT-003.md    ← Giám sát pin bình thường (Normal)
├── SOP-BAT-004.md    ← Xử lý pin nhiệt độ cao (temperature > 45°C)
├── SOP-BAT-005.md    ← Xử lý pin điện áp bất thường
├── SAFETY-LI-001.md  ← An toàn khi tháo lắp pin lithium-ion
├── SAFETY-LI-002.md  ← PPE và phòng cháy pin
└── SAFETY-LI-003.md  ← Quy trình khẩn cấp khi pin phồng/smoke
```

**Format mỗi SOP file:**

```markdown
---
id: SOP-BAT-001
title: Quy trình thay thế pin lithium-ion (Failed)
trigger: SOH < 80% hoặc classification = Failed
priority: P1
last_updated: 2026-06-22
---

## Mục đích
...

## Điều kiện áp dụng
- SOH < 80% (End of Life)
- Anomaly score ≤ -0.3

## Bước thực hiện
### Bước 1: Kiểm tra an toàn trước tháo lắp
...

## Cảnh báo an toàn
- Không charge pin đã Failed
- Kiểm tra nhiệt độ < 60°C trước khi tháo
```

**Chunking strategy:**

```
Mỗi SOP file → split theo heading (##) → chunk ~200–400 tokens
Mỗi chunk giữ nguyên metadata: {id, title, section, priority}
→ embed → store ChromaDB collection "sop_chunks"
```

---

### 11.4. ChromaDB Vector Store

```python
# src/services/knowledge_base.py

import chromadb
from sentence_transformers import SentenceTransformer

EMBED_MODEL = "all-MiniLM-L6-v2"   # 22MB, CPU-friendly, 384-dim
COLLECTION  = "sop_chunks"
TOP_K       = 3                      # top-3 per query
MAX_CHUNKS  = 5                      # max sau dedup

client     = chromadb.PersistentClient(path="data/chroma")
collection = client.get_or_create_collection(COLLECTION)
embedder   = SentenceTransformer(EMBED_MODEL)

def retrieve(queries: list[str]) -> list[dict]:
    """Embed queries → cosine search → dedup → top MAX_CHUNKS."""
    seen, results = set(), []
    for q in queries:
        vec = embedder.encode(q).tolist()
        hits = collection.query(query_embeddings=[vec], n_results=TOP_K)
        for doc, meta in zip(hits["documents"][0], hits["metadatas"][0]):
            key = meta["id"] + meta["section"]
            if key not in seen:
                seen.add(key)
                results.append({"content": doc, "source": meta})
                if len(results) >= MAX_CHUNKS:
                    return results
    return results
```

**Khởi tạo ChromaDB (1 lần, khi setup):**

```bash
python scripts/build_knowledge_base.py   # đọc data/sop/ → chunk → embed → insert
```

---

### 11.5. LLM Prompting Design

**Model:** `claude-haiku-4-5-20251001` — nhanh (~1–2s/call), rẻ, đủ cho structured output.

**Step 1 — Fault Statement:**

```python
SYSTEM_FAULT = """
You are a battery health expert for solar energy systems.
Given a prediction JSON, write a concise 2-3 sentence fault statement in Vietnamese.
Include: battery ID, SOH value, classification, anomaly status, and immediate implication.
Do NOT add recommendations here — only describe the fault.
"""

USER_FAULT = """
Prediction:
{prediction_json}

Write the fault statement:
"""
```

**Step 2 — Query Generation:**

```python
SYSTEM_QUERY = """
You are a maintenance knowledge retrieval specialist.
Given a fault statement, generate 3-5 search queries in English
that would find relevant SOP procedures and safety guidelines.
Return as JSON array: ["query1", "query2", ...]
"""
```

**Step 4 — Prescription Report:**

```python
SYSTEM_PRESCRIBE = """
You are a senior maintenance engineer for solar lithium-ion battery systems.
Given the fault statement, relevant SOP excerpts, and ticket priority,
generate a structured maintenance prescription in Vietnamese.

Return ONLY valid JSON with this schema:
{
  "action_title": "string — tên hành động chính (< 60 chars)",
  "urgency": "string — thời hạn thực hiện",
  "steps": ["step 1", "step 2", ...],      // tối đa 6 bước
  "sop_references": ["SOP-BAT-001", ...],
  "safety_warnings": ["warning 1", ...],    // tối đa 3
  "ticket_description": "string — nội dung điền vào ticket (< 300 chars)"
}
"""
```

---

### 11.6. API: POST /prescribe

**Request:**

```json
{
  "battery_id": "B0005",
  "prediction": {
    "soh_percent": 68.3,
    "classification": "Failed",
    "confidence": 0.87,
    "anomaly_score": -0.41,
    "anomaly_status": "Anomaly",
    "risk": {
      "priority": "P1",
      "action_code": "REPLACE_IMMEDIATELY"
    },
    "warnings": [
      {"code": "SOH_CRITICAL", "severity": "critical", "message": "SOH below 80% EOL threshold"}
    ]
  }
}
```

**Response:**

```json
{
  "battery_id": "B0005",

  "fault_statement": "Pin B0005 đang ở trạng thái Failed với SOH 68.3% — dưới ngưỡng EOL 80%. Điểm bất thường -0.41 cho thấy suy giảm nghiêm trọng về mặt vật lý. Cần can thiệp ngay lập tức để tránh nguy cơ an toàn.",

  "sop_chunks_used": ["SOP-BAT-001 §3", "SAFETY-LI-001 §1", "SAFETY-LI-003 §2"],

  "prescription": {
    "action_title": "Thay thế pin khẩn cấp — P1",
    "urgency": "Trong vòng 4 giờ (SLA P1)",
    "steps": [
      "1. Cô lập pin khỏi hệ thống điện mặt trời",
      "2. Kiểm tra nhiệt độ bề mặt — dừng nếu > 60°C",
      "3. Đo điện áp từng cell bằng multimeter",
      "4. Tháo pin theo SOP-BAT-001 §3.2 (2 người)",
      "5. Thay thế bằng pin cùng model và dung lượng",
      "6. Chạy charge cycle đầu tiên và ghi SOH baseline"
    ],
    "sop_references": ["SOP-BAT-001", "SAFETY-LI-001"],
    "safety_warnings": [
      "Không charge pin đã Failed — nguy cơ nhiệt",
      "Mang PPE: găng cách điện + kính bảo hộ",
      "Báo Admin ngay nếu pin có dấu hiệu phồng"
    ],
    "ticket_description": "Pin B0005 SOH 68.3% — Failed (P1). Cần thay thế trong 4h. Anomaly score: -0.41. Thực hiện theo SOP-BAT-001."
  },

  "metadata": {
    "llm_model": "claude-haiku-4-5-20251001",
    "embed_model": "all-MiniLM-L6-v2",
    "chunks_retrieved": 3,
    "prescription_ms": 2150
  }
}
```

**Error cases:**

```json
// ANTHROPIC_API_KEY chưa set
HTTP 503: {"detail": "Prescription service unavailable — LLM not configured"}

// ChromaDB chưa khởi tạo
HTTP 503: {"detail": "Knowledge base not initialized — run build_knowledge_base.py"}
```

---

### 11.7. Latency Budget

| Bước | Thời gian ước tính | Ghi chú |
|------|--------------------|---------|
| Step 1 (Fault Statement) | ~600ms | Claude Haiku, ~100 token output |
| Step 2 (Query Gen) | ~400ms | Claude Haiku, JSON 5 queries |
| Step 3 (ChromaDB search) | ~50ms | CPU embedding × 5 queries |
| Step 4 (Prescription) | ~1000ms | Claude Haiku, JSON output ~200 tokens |
| **Tổng** | **~2.0–2.5s** | Async — không block `/predict` |

> `/prescribe` là **async endpoint riêng** — không ảnh hưởng latency < 100ms của `/predict` (P1 SLA).
> BE gọi `/predict` trước để tạo alert, sau đó gọi `/prescribe` để điền nội dung ticket.

---

### 11.8. Cấu trúc code

```
src/
├── services/
│   ├── inference.py         ← (hiện có)
│   ├── confidence.py        ← (hiện có)
│   ├── knowledge_base.py    ← ChromaDB client + retrieve()
│   └── prescriber.py        ← LLM chain (4 steps) + PrescriptionService
│
├── routers/
│   ├── predict.py           ← (hiện có)
│   ├── health.py            ← (hiện có)
│   └── prescribe.py         ← POST /prescribe
│
└── schemas/
    ├── predict.py           ← (hiện có)
    └── prescribe.py         ← PrescribeRequest, PrescribeResponse

scripts/
└── build_knowledge_base.py  ← đọc data/sop/ → chunk → embed → ChromaDB

data/
└── sop/                     ← SOP Markdown files (commit vào Git)
    ├── SOP-BAT-001.md
    └── ...
```

---

### 11.9. Tech Stack bổ sung

| Thành phần | Thư viện | Phiên bản | Ghi chú |
|-----------|----------|-----------|---------|
| LLM | `anthropic` | ≥ 0.28 | Claude Haiku 4.5 |
| Vector DB | `chromadb` | ≥ 0.5 | Persistent local store |
| Embedding | `sentence-transformers` | ≥ 3.0 | `all-MiniLM-L6-v2`, CPU-only |
| SOP Docs | Markdown → `data/sop/` | — | Commit vào Git |

**Environment variable bắt buộc (Sprint 3):**

```bash
ANTHROPIC_API_KEY=sk-ant-...   # Claude API key
```

> Khi `ANTHROPIC_API_KEY` không set → `/prescribe` trả 503. `/predict` không bị ảnh hưởng.

---

## 12. Quy ước phát triển

### Git workflow

```
Branch naming : feat/GH-{number}-slug-ngan
                fix/GH-{number}-slug-ngan
Commit message: type(#number): mô tả
                feat(#10): long-seq L=4096 patch P16S16
                fix(#6):   fix scaler version mismatch

PR requirement: Có "Closes #{number}" trong body
```

### Model versioning

| Phiên bản | Khi nào tăng |
|-----------|-------------|
| `v1.2 → v1.3` | Retrain cùng architecture, khác data/hyperparameter |
| `v1.x → v2.0` | Thay đổi architecture (thêm layer, đổi model class) |

> **Bắt buộc:** Commit cả scaler + feature_scaler + model + IF cùng 1 commit.

### Các lệnh hay dùng

```bash
# Chạy server
uvicorn main:app --reload

# Chạy toàn bộ test
pytest tests/ -v --cov=src

# Preprocess (production)
python -X utf8 scripts/preprocess.py

# Train (production)
python -X utf8 scripts/train.py --epochs 50

# Benchmark latency
python -X utf8 scripts/benchmark_tokens.py

# Tạo dummy artifacts (dev)
python -X utf8 scripts/create_dummy_artifacts.py

# Lint & format
ruff check src/ scripts/ tests/
ruff format src/ scripts/ tests/
```

### Environment variables

Prediction layer: không cần biến môi trường.
Prescription layer (Sprint 3):
```
ANTHROPIC_API_KEY=sk-ant-...   # Claude API
```

---

> **Repo:** https://github.com/GSU26SE55/ai-module
