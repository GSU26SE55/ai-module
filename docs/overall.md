# AI Module - Overall Guide

> Project: Solar Lithium-ion Battery Maintenance Management System
>
> Team: GSU26SE55
>
> Updated: 2026-06-09
>
> Current model branch: `feat/spectral_kurtosis`

Tai lieu nay mo ta luong hien tai cua AI Module. Neu code va tai lieu cu mau thuan, uu tien `src/core/config.py`, schema Pydantic va test trong repo.

## 1. Muc tieu

AI Module nhan du lieu sensor pin va tra ve:

- SOH hien tai.
- Uoc luong RUL va xu huong suy giam.
- Trang thai bat thuong sensor.
- Health stage, risk level, ticket priority va action code.
- Evidence co cau truc cho Backend va RAG/LLM.

Luong tong:

```text
Battery telemetry
    -> BatteryService
    -> POST /predict
    -> AI Module
       -> preprocess + feature extraction
       -> Mamba SOH prediction
       -> IsolationForest anomaly score
       -> degradation/RUL estimation
       -> risk mapping
    -> structured prediction response
    -> TicketService / future RAG prescription
```

AI inference latency va maintenance SLA la hai khai niem khac nhau:

- `inference_ms`: thoi gian AI xu ly request.
- P1/P2/P3 SLA: thoi gian xu ly ticket cua he thong bao tri.

## 2. Trang thai hien tai

Da co:

- FastAPI app va model loading tai startup.
- Mamba SOH model voi sequence length 4096.
- 6 raw input features.
- 54 spectral/statistical features.
- IsolationForest anomaly detection.
- RUL/degradation heuristic.
- Structured `/predict` response cho Backend/RAG.
- AMP, gradient accumulation, checkpoint va resume training.
- Unit/integration tests.

Chua co:

- Full RAG implementation.
- `POST /prescribe`.
- Maintenance RAG va Safety RAG.
- LLM report generator va safety gate.
- True SOH prediction uncertainty.

## 3. Stack

| Thanh phan | Cong nghe |
| --- | --- |
| Language | Python 3.11+ |
| ML | PyTorch 2.3.1 |
| Data | NumPy, pandas, SciPy |
| Preprocessing | scikit-learn |
| API | FastAPI, Pydantic |
| Serving | Uvicorn |
| Dataset | NASA Ames Battery Dataset subset |
| Future RAG | ChromaDB + sentence-transformers + LLM API |

Dependencies duoc pin trong `requirements.txt`.

## 4. Cau hinh model hien tai

Nguon cau hinh: `src/core/config.py`.

```text
MODEL_VERSION = 1.3
WINDOW_SIZE = 4096
INPUT_FEATURES = 6
SPECTRAL_FEAT_DIM = 54
D_MODEL = 64
D_STATE = 16
SEED = 42
```

Raw feature order:

```text
0. voltage
1. current
2. temperature
3. current_load
4. voltage_load
5. time
```

Model co 73,729 trainable parameters.

### 4.1 Mamba path

```text
X: (batch, 4096, 6)
    -> Linear(6 -> 64)
    -> MambaBlock x 2
    -> LayerNorm
    -> last token representation
```

Mamba selective scan duoc xu ly theo chunk 256 timestep. Carry state duoc truyen qua cac chunk, vi vay model van doc du 4096 timestep; chunking chi giam peak activation memory.

### 4.2 Spectral/statistical path

Ba kenh dau:

```text
voltage, current, temperature
```

duoc dung de tinh:

```text
9 FFT features x 3 channels
9 statistical features x 3 channels
= 54 features
```

Feature vector duoc StandardScaler transform, sau do dua vao FiLM conditioning:

```text
X_feat: (batch, 54)
    -> Linear(54 -> 128)
    -> gamma + beta
    -> modulate Mamba hidden state
```

### 4.3 Output head

```text
FiLM-modulated hidden
    -> Linear(64 -> 32)
    -> GELU
    -> Dropout(0.2)
    -> Linear(32 -> 1)
    -> normalized SOH
```

Inference nhan output model va nhan `100` de doi sang SOH percent.

## 5. Dataset va preprocessing

Dataset path mac dinh:

```text
data/raw/nasa/cleaned_dataset/
├── metadata.csv
└── data/
    └── *.csv
```

Battery split hien tai:

| Split | Battery |
| --- | --- |
| Train | B0005, B0006, B0007 |
| Validation | 70% discharge cycles dau cua B0018 |
| Test | 30% discharge cycles cuoi cua B0018 |

### 5.1 Preprocessing flow

```text
metadata.csv
    -> filter discharge cycles co Capacity
    -> load 6 raw features
    -> fit MinMaxScaler tren train timesteps
    -> resample moi full discharge cycle thanh 4096 timestep
    -> extract 54 spectral/statistical features
    -> fit StandardScaler tren train spectral features
    -> save train.pt, val.pt, test.pt
```

SOH label:

```text
SOH = Capacity / 2.0 Ah * 100
```

Processed tensors hien tai:

```text
train.pt:
  X      (504, 4096, 6)
  X_feat (504, 54)
  y      (504,)

val.pt:
  X      (92, 4096, 6)
  X_feat (92, 54)
  y      (92,)

test.pt:
  X      (40, 4096, 6)
  X_feat (40, 54)
  y      (40,)
```

Moi processed file con co:

```text
feature_scaler_version = 1.2
```

`train.py` tu choi processed data cu/missing version de tranh train v1.3 bang
feature semantics v1.2.

Chay preprocess:

```bash
python scripts/preprocess.py \
  --data-dir data/raw/nasa/cleaned_dataset \
  --output-dir data/processed
```

Preprocess tao/cap nhat:

```text
data/processed/train.pt
data/processed/val.pt
data/processed/test.pt
models/weights/scaler.pkl
models/weights/feature_scaler.pkl
```

Raw va processed data khong commit vao Git.

## 6. Training flow

Training config mac dinh:

```text
optimizer = Adam
learning rate = 5e-4
weight decay = 1e-5
loss = MSELoss
physical batch = 1
accumulation steps = 8
effective batch = 8
early stopping patience = 15
gradient clipping = 1.0
AMP = enabled on CUDA
```

Full training:

```bash
python scripts/train.py \
  --data-dir data/processed \
  --epochs 100 \
  --batch-size 1 \
  --accumulation-steps 8 \
  --checkpoint-dir models/checkpoints \
  --log-dir logs/training
```

Checkpoint duoc ghi sau moi epoch:

```text
models/checkpoints/latest.pt
```

Checkpoint gom:

- Model state.
- Optimizer state.
- Scheduler state.
- AMP scaler state.
- Epoch.
- Best validation loss/state.
- Early stopping counter.

Resume:

```bash
python scripts/train.py \
  --data-dir data/processed \
  --epochs 100 \
  --batch-size 1 \
  --accumulation-steps 8 \
  --checkpoint-dir models/checkpoints \
  --resume models/checkpoints/latest.pt \
  --log-dir logs/training
```

### 6.1 Smoke test

Smoke test chi xac nhan forward/backward, CUDA, AMP va checkpoint:

```bash
python scripts/train.py \
  --data-dir data/processed \
  --epochs 1 \
  --batch-size 1 \
  --accumulation-steps 2 \
  --checkpoint-dir models/checkpoints_smoke \
  --log-dir logs/training_smoke \
  --max-train-batches 2 \
  --max-eval-batches 2 \
  --skip-final-artifacts
```

MAE/RMSE smoke test rat cao la binh thuong. Khong dung smoke metric de danh gia model.

### 6.2 CPU va GPU

- CPU: dung de test/debug/smoke; full training se cham.
- CUDA GPU: dung cho full training.
- Colab config an toan: batch 1, accumulation 8.
- AMP tu bat khi `Device: cuda`.

Huong dan Colab chi tiet:

```text
docs/colab-4096-training.md
```

### 6.3 Target metrics

Project targets:

```text
Test MAE < 2.0% SOH
Test RMSE < 3.0% SOH
```

Day la target, khong phai ket qua duoc dam bao. Chi report metric tu full training/test, khong report smoke metric.

## 7. Model artifacts

Production startup can:

```text
models/weights/scaler.pkl
models/weights/feature_scaler.pkl
models/weights/soh_mamba_v1.3.pth
models/weights/isolation_forest_v1.3.pkl
```

`src/core/model_loader.py` validate:

- File ton tai.
- Scaler version.
- Feature scaler version.
- Model version.
- Model architecture metadata.

App fail startup neu thieu hoac sai version artifact.

Khi retrain, commit cung luc scaler, feature scaler, Mamba weight va IsolationForest artifact.

## 8. Inference flow

Request:

```text
4096 timesteps x 6 features (preferred)
4096 timesteps x 3 features (legacy only when loaded artifacts expect 3)
```

Flow:

```text
readings
    -> validate shape
    -> align feature count with loaded artifacts
    -> MinMaxScaler
    -> extract 54 features from first 3 channels
    -> feature StandardScaler
    -> Mamba SOH prediction
    -> IsolationForest score
    -> degradation/RUL heuristic
    -> threshold warnings
    -> health/anomaly/risk mapping
    -> structured response
```

Important:

- Mamba SOH la model prediction.
- RUL va degradation rate hien tai la heuristic tu voltage trend.
- `anomaly_confidence` hien tai duoc tinh tu magnitude cua IsolationForest score; no chua phai calibrated probability.
- Flat fields duoc giu de backward compatibility.

## 9. API

Base URL:

```text
http://localhost:8000
```

Swagger:

```text
http://localhost:8000/docs
```

### 9.1 GET /health

```json
{
  "status": "ok",
  "model_version": "1.3",
  "scaler_loaded": true,
  "mamba_loaded": true,
  "isolation_forest_loaded": true
}
```

### 9.2 POST /predict/

Request shape:

```json
{
  "battery_id": "B0005",
  "readings": [
    [3.92, -0.99, 25.3, -1.0, 3.7, 0.0]
  ]
}
```

`readings` trong vi du duoc rut gon; request that phai co dung 4096 rows.

Structured response:

```json
{
  "battery_id": "B0005",
  "prediction": {
    "soh_percent": 82.4,
    "rul_cycles_estimate": 16,
    "degradation_rate_per_cycle": 0.15,
    "soh_trend": "stable",
    "cycles_to_maintenance": 0,
    "soh_trajectory": [82.3, 82.1, 82.0, 81.8, 81.7],
    "health_stage": "Maintenance Required"
  },
  "anomaly": {
    "anomaly_score": -0.18,
    "anomaly_status": "Warning",
    "anomaly_confidence": 0.18
  },
  "risk": {
    "risk_level": "High",
    "priority": "P2",
    "action_code": "SCHEDULE_REPLACEMENT",
    "reasons": [
      "SOH 82.4% is below 85% maintenance threshold"
    ]
  },
  "evidence": {
    "warnings": [],
    "feature_summary": {
      "voltage": {
        "mean": 3.61,
        "min": 3.05,
        "max": 4.18
      }
    }
  },
  "metadata": {
    "model_version": "1.3",
    "window_size": 4096,
    "input_features": 6,
    "inference_ms": 120.5
  }
}
```

Response hien tai con tra flat fields cu:

```text
soh_percent
classification
confidence
inference_ms
rul_cycles_estimate
degradation_rate_per_cycle
soh_trend
cycles_to_maintenance
soh_trajectory
anomaly_score
recommended_action
warnings
feature_summary
```

Dev moi nen dung nested fields. Flat fields se duoc loai bo sau khi Backend migration xong.

### 9.3 Health, anomaly va risk mapping

Health stage:

| SOH | Stage |
| --- | --- |
| `>= 90` | Healthy |
| `85 - <90` | Degrading |
| `80 - <85` | Maintenance Required |
| `< 80` | End Of Life |

Anomaly status:

| IsolationForest score | Status |
| --- | --- |
| `> -0.1` | Normal |
| `-0.3 < score <= -0.1` | Warning |
| `<= -0.3` | Anomaly |

Risk mapping:

| Condition | Risk | Priority |
| --- | --- | --- |
| EOL or critical warning | Critical | P1 |
| Maintenance Required or Anomaly | High | P2 |
| Degrading, Warning or sensor warning | Medium | P3 |
| Healthy and normal | Low | None |

Known issue before final BE/RAG contract:

- Critical sensor warning can currently produce P1 while action code remains `MONITOR` in one edge case. Fix risk/action consistency before ticket automation.
- `anomaly_confidence` is not calibrated probability.

## 10. Local development

Install:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Run tests:

```bash
python -m pytest -q
```

Run API:

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

The app loads all artifacts during startup. Dummy artifacts are only for endpoint development:

```bash
python scripts/create_dummy_artifacts.py
```

Dummy output is not valid model evaluation.

## 11. Repo structure

```text
ai-module/
├── main.py
├── src/
│   ├── core/
│   │   ├── config.py
│   │   └── model_loader.py
│   ├── features/
│   │   └── extractor.py
│   ├── models/
│   │   ├── soh_predictor.py
│   │   └── anomaly_detector.py
│   ├── routers/
│   │   ├── health.py
│   │   └── predict.py
│   ├── schemas/
│   │   └── predict.py
│   └── services/
│       └── inference.py
├── scripts/
│   ├── preprocess.py
│   ├── train.py
│   ├── benchmark_tokens.py
│   └── create_dummy_artifacts.py
├── models/
│   ├── weights/
│   └── checkpoints/          # ignored, local/Drive only
├── data/
│   ├── raw/                  # ignored
│   └── processed/            # ignored
├── tests/
└── docs/
    ├── overall.md
    ├── colab-4096-training.md
    ├── agent-review-brief.md
    └── ai-prediction-research.md
```

## 12. Backend integration contract

Backend nen:

1. Gui du 4096 readings theo dung feature order.
2. Dung nested `prediction`, `anomaly`, `risk`, `evidence`, `metadata`.
3. Khong coi `confidence` cu la SOH prediction confidence.
4. Dung `risk.priority` de tham khao ticket mapping sau khi known action inconsistency duoc fix.
5. Persist model version va evidence de audit.
6. Khong tu dong thuc hien physical maintenance action chi dua tren LLM output.

Ticket SLA de xuat:

| Priority | SLA |
| --- | --- |
| P1 | 4 hours |
| P2 | 24 hours |
| P3 | 72 hours |

## 13. RAG/Prescription roadmap

RAG chua duoc implement. Kien truc du kien:

```text
structured /predict output
    -> fault statement builder
    -> maintenance query builder
    -> safety query builder
    -> Maintenance RAG
    -> Safety RAG
    -> LLM prescription generator
    -> safety gate
    -> human verification
    -> ticket workflow
```

Maintenance knowledge:

- Battery maintenance manuals.
- BMS warning code guides.
- Inverter/manual references.
- Replacement criteria.
- Preventive maintenance SOP.
- Historical maintenance cases.

Safety knowledge:

- Electrical safety SOP.
- Lockout/Tagout.
- Battery isolation.
- PPE checklist.
- Thermal runaway/fire response.
- Human verification checklist.

Planned modules:

```text
knowledge/maintenance/
knowledge/safety/
scripts/ingest_rag.py
src/services/rag_retriever.py
src/services/prescription.py
src/services/safety_gate.py
src/schemas/prescribe.py
src/routers/prescribe.py
```

Planned endpoint:

```text
POST /prescribe
```

Prescription output must include:

- Retrieved maintenance evidence.
- Retrieved safety evidence.
- Priority and action steps.
- PPE/isolation warnings.
- Escalation conditions.
- `human_verification_required = true`.

## 14. Development sequence

Current recommended order:

1. Full-train and validate Mamba v1.3 artifacts.
2. Fix reviewed risk/action inconsistency.
3. Finalize nested `/predict` contract with Backend.
4. Update Backend event/ticket mapping.
5. Build Maintenance RAG.
6. Build Safety RAG separately.
7. Add `/prescribe` and safety gate.
8. Add RAG evaluation and human verification.

## 15. Git and artifact rules

- Khong push truc tiep vao `main`.
- Mot issue nen co mot branch.
- Khong commit raw/processed dataset.
- Khong commit training checkpoints.
- Commit production weight artifacts cung version.
- Seed training la 42.
- Khong overwrite user changes/logs khong lien quan.

Before PR:

```bash
python -m pytest -q
git diff --check
git status --short
```
