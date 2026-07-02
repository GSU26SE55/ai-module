# AI Module — Solar Battery Maintenance System

> **GSU26SE55 Capstone Project** | FPT University | GVHD: Trương Long
> Timeline: 11/05/2026 → 06/09/2026

AI service for real-time **State of Health (SOH) prediction**, **Remaining Useful Life (RUL) estimation**, and **anomaly detection** of lithium-ion batteries in solar energy systems. Built with FastAPI + pure-PyTorch Mamba SSM — no CUDA required.

---

## Overview

```
┌───────────────────────────────────────────────────────┐
│           Solar Battery Maintenance System            │
├─────────────────┬──────────────────┬──────────────────┤
│  Mobile App     │    Web App       │   AI Module      │
│  React Native   │    ReactJS       │  FastAPI+PyTorch  │
│  Customer       │  Admin/Manager/  │  SOH · RUL ·     │
│  real-time view │  Staff tickets   │  Anomaly detect  │
└─────────────────┴──────────────────┴──────────────────┘
```

The AI module sits behind the ASP.NET Core backend. When BatteryService detects a reading anomaly, it calls `POST /predict` to get an AI-powered assessment, then fires a `BatteryAnomalyDetectedEvent` to auto-create a P1/P2/P3 ITIL ticket.

---

## Features

| Capability | Model | Status |
|-----------|-------|--------|
| SOH Regression | MambaSOHPredictor (pure-PyTorch SSM) | Production |
| Anomaly Classification | IsolationForest (sklearn) | Production |
| Spectral + Kurtosis Features | 54-dim FFT + time-domain stats | Production |
| RUL Estimation | RULPredictor (cycle-axis Mamba) | Research |
| Prescription Layer | LLM + RAG over SOP knowledge base | Sprint 3 |

---

## Quick Start

### Prerequisites

- Python 3.11
- No GPU required — CPU-only inference

### Install

```bash
git clone https://github.com/GSU26SE55/ai-module.git
cd ai-module
pip install -r requirements.txt
```

### Run with dummy artifacts (dev mode)

```bash
# Generate placeholder model weights (no real data needed)
python -X utf8 scripts/create_dummy_artifacts.py

# Start the server
uvicorn main:app --reload --port 8000
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive Swagger UI.

### Run with real trained weights

```bash
# 1. Download NASA Ames dataset → data/raw/nasa/cleaned_dataset/
# 2. Preprocess
python -X utf8 scripts/preprocess.py

# 3. Train (50 epochs, ~10 min on CPU)
python -X utf8 scripts/train.py --epochs 50

# 4. Start server
uvicorn main:app --reload --port 8000
```

---

## Serving — REST + gRPC (hybrid)

The same inference/prescription pipeline is exposed over two transports running side by side:

| Transport | Port | Start | Use for |
|-----------|------|-------|---------|
| REST (FastAPI) | 8000 | `uvicorn main:app --port 8000` | current integrations, Swagger UI |
| gRPC (`aimodule.v1.AiService`) | 50051 (env `GRPC_PORT`) | `python -m src.grpc_server` | lower latency, real-time sensor streaming |

gRPC RPCs: `Predict`, `Prescribe`, `Health` (unary — mirror the REST endpoints, parity-tested field-by-field) and `PredictStream` (bidirectional streaming: N windows in → N predictions out, in order, over one connection).

- Contract: [`protos/ai_service.proto`](protos/ai_service.proto) — regenerate Python stubs with `python scripts/gen_proto.py`
- Demo client (all 4 RPCs, replaces Swagger for demos): `python scripts/grpc_client_demo.py`
- Benchmark: `python scripts/benchmark_grpc.py` (add `--real-weights` to enforce the <100ms SLA with production artifacts)
- BE (.NET) integration guide: [`docs/grpc-integration-be.md`](docs/grpc-integration-be.md)

---

## API

### `POST /predict`

Predict SOH and battery health classification from 30 timesteps of sensor data.

**Request**
```json
{
  "battery_id": "B0005",
  "readings": [
    [3.92, -0.99, 25.3, -1.00, 3.90, 0.0],
    [3.87, -0.99, 25.5, -1.00, 3.85, 13.0],
    "... 30 rows of [voltage, current, temperature, current_load, voltage_load, time]"
  ]
}
```

> Legacy 3-feature `[voltage, current, temperature]` is also accepted — auto-aligned.

**Response**
```json
{
  "battery_id": "B0005",
  "soh_percent": 84.5,
  "classification": "Degrading",
  "confidence": 0.82,
  "rul_cycles_estimate": 30,
  "degradation_rate_per_cycle": 0.15,
  "anomaly_score": -0.12,
  "recommended_action": "SCHEDULE_MAINTENANCE",
  "warnings": [{"code": "SOH_LOW", "severity": "warning", "message": "SOH below 90%"}],
  "inference_ms": 87.4
}
```

Classifications: `Normal` | `Degrading` | `Failed`

Classification logic:
- `SOH < 80%` → **Failed**
- `SOH 80–90%` → **Degrading**
- `SOH ≥ 90%` + anomaly score `< -0.1` → **Degrading**
- `SOH ≥ 90%` + anomaly score `≥ -0.1` → **Normal**

Latency SLA: **< 100ms** (P1 Critical ticket requirement)

### `GET /health`

```json
{
  "status": "ok",
  "model_version": "1.2",
  "scaler_loaded": true,
  "lstm_loaded": true,
  "isolation_forest_loaded": true
}
```

### `POST /prescribe` *(Sprint 3 — planned)*

Turn a prediction result into a step-by-step maintenance prescription, grounded in the SOP knowledge base via RAG.

**Request**
```json
{
  "battery_id": "B0005",
  "prediction": {
    "soh_percent": 68.3,
    "classification": "Degrading",
    "confidence": 0.87
  }
}
```

**Response**
```json
{
  "battery_id": "B0005",
  "fault_statement": "Battery B0005 shows significant SOH degradation to 68.3%...",
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

---

## Prescription Layer *(Sprint 3)*

Based on: *"From Prediction to Prescription: LLM Agent for Context-Aware Maintenance Decision Support"* — Deng et al., PHM Society 2024.

```
POST /predict → {soh_percent, classification, confidence, risk}
      │
      ▼ Step 1 — LLM: Fault Statement
        "Battery B0005 SOH 68.3% — significant capacity fade..."
      │
      ▼ Step 2 — LLM: Search Query Generation
        ["battery degradation maintenance SOH 68%", ...]
      │
      ▼ Step 3 — RAG: ChromaDB SOP Knowledge Base
        Top-3 relevant standard operating procedures
      │
      ▼ Step 4 — LLM: Prescription Report
        {action, steps, urgency, sop_reference, safety_warnings}
```

Additional dependencies for Sprint 3:

| Component | Library |
|-----------|---------|
| LLM | Claude API (`claude-sonnet-4-6`) |
| Vector DB | ChromaDB |
| Embeddings | sentence-transformers |
| SOP docs | Markdown files in `data/sop/` |

---

## Model Architecture

### MambaSOHPredictor (Production)

Pure-PyTorch implementation of the Mamba Selective State Space Model — no `mamba-ssm` CUDA dependency, runs natively on Windows 11.

```
Input (batch, 30, 6)        ← [voltage, current, temperature, current_load, voltage_load, time]
  → Linear(6→64)
  → MambaBlock × 2          ← Selective SSM with ZOH discretization
  → LayerNorm
  → Last token hidden state
  → FiLM conditioning       ← 2-layer MLP: 54-dim spectral features → γ + β
  → Linear(64→32) + GELU + Dropout(0.2)
  → Linear(32→1)
Output (batch,)              # SOH %
```

Confidence: **MC Dropout** — 20 stochastic forward passes → mean=SOH, std→confidence score.

### Long-Sequence Model (Research, L=4096)

```
Input (batch, L, 8)         ← 6 base features + dQ/dV (IC curve) + phase mask
  → Conv1d patch embed (P16S16) → 256 tokens
  → PatchDegradationEncoder    ← RMS / peak-to-peak / std / kurtosis per patch
  → MambaBlock × 2
  → Attention pooling
  → FiLM conditioning + head
Output (batch,)              # SOH %
```

Results (Kaggle GPU, 2026-06-20): **MAE 1.6293%** ✅ | **RMSE 2.0871%** ✅

### Spectral + Kurtosis Features (54-dim)

Each window is enriched with physics-informed features used for both **FiLM conditioning** (Mamba) and **IsolationForest** input:

- **9 spectral features × 3 channels** — FFT-based: centroid, entropy, peak frequency, spectral flatness, rolloff, band energy distribution
- **9 statistical features × 3 channels** — Time-domain: kurtosis, crest factor, waveform factor, skewness, peak-to-peak amplitude

### IsolationForest (Anomaly Detection)

```python
IsolationForest(contamination=0.1, n_estimators=100, random_state=42)
# Input: 54-dim spectral+kurtosis features (StandardScaler'd)

# Classification logic (SOH is the primary driver):
# SOH < 80%                    → Failed
# SOH 80–90%                   → Degrading
# SOH ≥ 90% AND score < -0.1   → Degrading
# SOH ≥ 90% AND score ≥ -0.1   → Normal
```

---

## Dataset

**NASA Ames Battery Dataset** — 34 lithium-ion 18650 cells (B0005–B0056)

| Split | Batteries | Windows | SOH Range |
|-------|-----------|---------|-----------|
| Train | B0005, B0006, B0007 | 4,812 | 57.7–101.8% |
| Val | B0018 (first 70%) | 767 | 72.0–92.8% |
| Test | B0018 (last 30%) | 329 | 67.1–73.5% |

Split by battery ID (not by timestep) to prevent data leakage across cells.

SOH formula: `capacity_current / 2.0 Ah × 100`

---

## Target Metrics

| Metric | Target | Notes |
|--------|--------|-------|
| MAE | **< 2.0%** SOH | Test set |
| RMSE | **< 3.0%** SOH | Test set |
| Anomaly F1 | **> 0.80** | — |
| Inference latency | **< 100ms** | CPU, batch_size=1 |

---

## Project Structure

```
ai-module/
├── main.py                    # FastAPI entry point
├── src/
│   ├── models/
│   │   ├── soh_predictor.py   # MambaBlock + MambaSOHPredictor
│   │   ├── rul_predictor.py   # RULPredictor (research)
│   │   └── anomaly_detector.py
│   ├── features/
│   │   └── extractor.py       # 54-dim spectral + kurtosis features
│   ├── routers/
│   │   ├── predict.py         # POST /predict
│   │   └── health.py          # GET /health
│   ├── services/
│   │   ├── inference.py       # Full prediction pipeline
│   │   └── confidence.py
│   └── core/
│       ├── config.py
│       └── model_loader.py    # Load artifacts at startup
├── scripts/
│   ├── preprocess.py          # Raw NASA CSV → tensors
│   ├── preprocess_long.py     # 8-feature long-context preprocessing
│   ├── train.py               # Train Mamba + IsolationForest
│   └── create_dummy_artifacts.py
├── tests/
│   ├── test_models.py
│   ├── test_inference.py      # Includes latency benchmark
│   ├── test_preprocess.py
│   └── test_routers.py
├── models/weights/            # Committed model artifacts
│   ├── scaler.pkl                    # 6-feat MinMaxScaler
│   ├── feature_scaler.pkl            # 54-dim StandardScaler
│   ├── soh_mamba_v1.2.pth            # Production Mamba
│   ├── isolation_forest_v1.2.pkl     # IsolationForest
│   ├── feature_scaler_long.pkl       # 54-dim StandardScaler (long)
│   ├── soh_mamba_long_v2.0.pth       # Long Mamba (L=4096)
│   ├── feature_scaler_rul.pkl
│   └── soh_mamba_rul_v1.0.pth        # RUL Predictor
└── data/                      # .gitignored — download separately
    └── raw/nasa/cleaned_dataset/
```

---

## Development

### Run tests

```bash
pytest tests/ -v --cov=src
# Target: >= 85% coverage
```

### Lint & format

```bash
ruff check src/ scripts/ tests/
ruff format src/ scripts/ tests/
```

### Model versioning

| Version bump | When |
|--------------|------|
| `v1.0 → v1.1` | Retrain same architecture with new data or hyperparameters |
| `v1.x → v2.0` | Architecture change (new layers, new model class) |

All artifacts (`scaler.pkl`, `feature_scaler.pkl`, `soh_mamba_vX.Y.pth`, `isolation_forest_vX.Y.pkl`) must be committed together in a single commit. **Do not refit scalers on production data.**

---

## Roadmap

| Sprint | Period | Goal |
|--------|--------|------|
| Sprint 1 | May 11 – Jun 1 | Base architecture, preprocessing, FastAPI skeleton |
| Sprint 2 | Jun 2 – Jun 21 | Production training (v1.2), FiLM + spectral features, long-seq L=4096 (GH-10), RULPredictor (GH-13) |
| Sprint 3 | Jun 22 – Jul 6 | Prescription Layer (LLM + RAG + ChromaDB) |
| Sprint 4 | Jul 7 – Jul 20 | Integration with BatteryService event bus |
| Sprint 5 | Jul 21 – Aug 3 | Load testing, performance hardening |
| Sprint 6+ | Aug 4 – Sep 6 | System test, IoT pipeline (optional) |

---

## Tech Stack

| Layer | Choice | Version |
|-------|--------|---------|
| Language | Python | 3.11 |
| ML | PyTorch | 2.3.1 |
| Anomaly | scikit-learn | 1.5.0 |
| Signal processing | scipy | 1.13.1 |
| API | FastAPI | 0.111.1 |
| Server | uvicorn | 0.30.1 |
| Data | numpy, pandas | 1.26.4 / 2.2.2 |

No GPU. No `mamba-ssm`. Runs on any CPU.

---

## Team

| Name | ID | Role |
|------|----|------|
| Nguyen Phuc Duy | SE184821 | BE + AI |
| Bui Phuoc Thang | SE180445 | BE + AI |
| Mai Hong Thai | SE183923 | BE + AI |
| Tran Minh Tri | SE183109 | FE / Leader |
| Nguyen Nhat Minh | SE170310 | FE + AI |

---

## References

- Gu, A., & Dao, T. (2024). *Mamba: Linear-Time Sequence Modeling with Selective State Spaces*. COLM 2024 (arXiv:2312.00752, 2023).
- Liu, F. T., Ting, K. M., & Zhou, Z. H. (2008). *Isolation Forest*. ICDM 2008.
- Deng et al. (2024). *From Prediction to Prescription: LLM Agent for Context-Aware Maintenance Decision Support*. PHM Society.
- Dubarry, M., & Liaw, B. Y. (2009). *Identify capacity fading mechanism in a commercial LiFePO4 cell*. Journal of Power Sources.
- NASA Ames Battery Dataset: [PCoE Data Set Repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/)
