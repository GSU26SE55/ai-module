<div align="center">

# AI Module — Solar Battery Maintenance

**State of Health prediction, anomaly detection and LLM-grounded maintenance prescriptions for lithium-ion batteries — Mamba state space models in pure PyTorch, served over gRPC and REST, on CPU.**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.6%20CPU-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-REST%20%3A8000-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![gRPC](https://img.shields.io/badge/gRPC-%3A50051%20primary-244C5A?logo=grpc&logoColor=white)](protos/ai_service.proto)
[![Mamba](https://img.shields.io/badge/Mamba%20SSM-pure%20PyTorch%20·%20no%20CUDA-6E44FF)](#model-architecture)
[![Latency](https://img.shields.io/badge/inference-%3C%20100%20ms%20CPU-success)](#target-metrics)

</div>

---

The AI service of the **Solar Lithium-ion Battery Maintenance Management System** (capstone GSU26SE55). BatteryService calls it with a window of sensor readings; it returns an SOH estimate with a confidence interval, a health classification, an anomaly score and — when asked — a step-by-step maintenance prescription grounded in the SOP knowledge base. That result is what turns into a P1/P2/P3 ITIL ticket upstream.

No GPU, no `mamba-ssm` CUDA extension. Everything runs on a CPU container.

## Table of contents

- [What it does](#what-it-does)
- [Quick start](#quick-start)
- [Serving — gRPC + REST](#serving--grpc--rest)
- [API surface](#api-surface)
- [Model architecture](#model-architecture)
- [Features — 57 dimensions](#features--57-dimensions)
- [Two chemistries](#two-chemistries)
- [Dataset & split](#dataset--split)
- [Target metrics](#target-metrics)
- [Prescription layer](#prescription-layer)
- [Project structure](#project-structure)
- [Model artifacts & versioning](#model-artifacts--versioning)
- [Development](#development)
- [Deployment](#deployment)
- [Team](#team)
- [References](#references)

---

## What it does

| Capability | How | Status |
| --- | --- | --- |
| **SOH regression** | `MambaSOHPredictor` — selective SSM + FiLM conditioning | Production (`v1.6`) |
| **Confidence** | Monte Carlo Dropout, 20 stochastic passes | Production |
| **Anomaly detection** | IsolationForest over the same 57-dim feature space | Production (`v1.6`) |
| **LFP chemistry** | Separate artifacts trained on Severson, per-chemistry voltage guards | Production (`v2.2-lfp`) |
| **Long-sequence SOH** | Patch-embedded Mamba over `L = 4096` full discharge cycles | Research (`long v2.2`) |
| **RUL estimation** | `RULPredictor` — cycle-axis Mamba, 1 token = 1 discharge cycle | Research (`rul v1.0`) |
| **SOH forecasting** | Same cycle-axis tokens, predict SOH *h* cycles ahead | Research |
| **Prescription** | LLM + RAG over the SOP knowledge base (ChromaDB) | Production |
| **Staff / KB suggestion** | Retrieval over knowledge base + staff skill matching | Production |
| **Ticket verification** | LLM check of a resolution against the reported fault | Production |

---

## Quick start

Everything routine is a Make target — `make help` lists them all.

```bash
make setup            # .venv on Python 3.11 + runtime deps           (once)
make setup-dev        # + pytest, ruff                                (once)
make dummy            # generate placeholder weights — no dataset needed
make serve            # REST on :8000, Swagger at /docs
```

With real weights instead of dummies:

```bash
# 1. Put the NASA Ames cleaned dataset in data/raw/nasa/cleaned_dataset/
python scripts/preprocess.py          # raw CSV → tensors
python scripts/train.py --epochs 50   # Mamba + IsolationForest (~10 min, CPU)
make serve
```

Other useful targets:

```bash
make grpc         # standalone gRPC server (development only)
make demo         # exercise all 4 gRPC RPCs — the demo path, instead of Swagger
make smoke        # gRPC Health + Predict smoke test
make benchmark    # latency benchmark (--real-weights enforces the <100 ms SLA)
make test         # pytest + coverage (quality gate: ≥ 85 %)
make lint format  # ruff
make proto        # regenerate gRPC stubs from protos/ai_service.proto
make docker-build docker-run
```

---

## Serving — gRPC + REST

One inference pipeline, two transports running side by side:

| Transport | Internal port | Public endpoint | Role |
| --- | --- | --- | --- |
| gRPC (`aimodule.v1.AiService`) | `50051` (`GRPC_PORT`) | `https://ai.solaris.io.vn:443` | **Primary** backend transport, incl. streaming |
| REST (FastAPI) | `8000` | `https://ai.solaris.io.vn` | HTTPS fallback, health, metrics, Swagger |

In production **FastAPI owns the lifecycle of both**: model and RAG artifacts are verified and loaded once at startup, then the gRPC server starts inside the FastAPI lifespan. `python -m src.grpc_server` exists only as a development convenience. Caddy is the sole public ingress and multiplexes both transports on TLS 443 — the internal ports are never published.

gRPC RPCs: `Predict`, `Prescribe`, `Health` (unary, field-by-field parity-tested against REST) and `PredictStream` (bidirectional — N windows in, N predictions out, in order, over one connection).

- Contract: [`protos/ai_service.proto`](protos/ai_service.proto)
- Demo client: `python scripts/grpc_client_demo.py`
- .NET integration guide: [`docs/grpc-integration-be.md`](docs/grpc-integration-be.md)
- Deployment contract: [`docs/production-deployment.md`](docs/production-deployment.md)

---

## API surface

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/predict/` | SOH + classification + anomaly score from a 30-step window |
| `POST` | `/predict/long` | Long-sequence variant (`L = 4096`, full discharge cycles) |
| `POST` | `/predict/feedback` | Record a human correction of a classification |
| `POST` | `/prescribe/` | Prediction → grounded maintenance prescription (LLM + RAG) |
| `POST` | `/prescribe/feedback` | Record usefulness feedback on a prescription |
| `POST` | `/suggest/staff` | Suggest technicians by skill match |
| `POST` | `/suggest/kb` | Retrieve relevant knowledge-base articles |
| `POST` | `/verify-ticket/` | Check a resolution against the reported fault |
| `GET` | `/health` | Full readiness: which artifacts are loaded |
| `GET` | `/live` · `/ready` | Kubernetes-style liveness / readiness probes |

### `POST /predict/`

```json
{
  "battery_id": "B0005",
  "readings": [
    [3.92, -0.99, 25.3, 0.0],
    [3.87, -0.99, 25.5, 13.0],
    "… 30 rows of [voltage, current, temperature, time]"
  ]
}
```

Four features is the preferred input — the service derives the rest. A full six-feature row and the legacy three-feature form are also accepted; an optional `chemistry` field selects the per-chemistry voltage range and temperature guards (see [Two chemistries](#two-chemistries)).

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
  "warnings": [{ "code": "SOH_LOW", "severity": "warning", "message": "SOH below 90%" }],
  "inference_ms": 87.4
}
```

Classification — SOH is the primary driver, the anomaly score only breaks ties in the healthy band:

| Condition | Result |
| --- | --- |
| `SOH < 80 %` | **Failed** |
| `80 % ≤ SOH < 90 %` | **Degrading** |
| `SOH ≥ 90 %` and anomaly score `< -0.1` | **Degrading** |
| `SOH ≥ 90 %` and anomaly score `≥ -0.1` | **Normal** |

---

## Model architecture

### MambaSOHPredictor — production

Pure-PyTorch Mamba selective state space model. No `mamba-ssm`, no CUDA, runs natively on Windows and in a slim Linux container.

```
Input (batch, 30, 6)      ← 4 base features [voltage, current, temperature, time]
                            + 2 server-derived [cycle_count, soc_percent] (pre-normalised)
  → Linear(6 → 64)
  → MambaBlock × 2        ← selective SSM, ZOH discretisation
  → LayerNorm
  → last-token hidden state
  → FiLM conditioning     ← 2-layer MLP: 57-dim spectral features → γ, β
  → Linear(64 → 32) + GELU + Dropout(0.2)
  → Linear(32 → 1)
Output (batch,)             SOH %
```

Confidence comes from **MC Dropout**: 20 stochastic forward passes, mean → SOH, standard deviation → confidence.

### Long-sequence model — research, `L = 4096`

```
Input (batch, 4096, 8)    ← 6 base + dQ/dV (incremental capacity) + phase mask
  → Conv1d patch embed (P16S16) → 256 tokens
  → PatchDegradationEncoder     ← RMS / peak-to-peak / std / kurtosis per patch
  → MambaBlock × 2
  → attention pooling
  → FiLM conditioning + head
Output (batch,)             SOH %
```

Kaggle GPU run, 2026-06-20: **MAE 1.6293 %**, **RMSE 2.0871 %**.

### IsolationForest — anomaly detection

```python
IsolationForest(contamination=0.1, n_estimators=100, random_state=42)
# input: the same 57-dim spectral + statistical vector, StandardScaler'd
```

---

## Features — 57 dimensions

Each window is enriched with physics-informed features, used both for **FiLM conditioning** of the Mamba model and as the **IsolationForest** input. `SPECTRAL_FEAT_DIM = 57` in `src/core/config.py` is the single source of truth:

**(10 spectral + 9 statistical) × 3 channels** — voltage, current, temperature.

- **Spectral (FFT)** — centroid, entropy, peak frequency, flatness, rolloff, band-energy distribution, and a **spectral Gini coefficient**. Gini measures how concentrated the spectral energy is: as a cell ages, broadband noise rises and the Gini coefficient falls, which complements flatness.
- **Statistical (time domain)** — kurtosis, crest factor, waveform factor, skewness, peak-to-peak amplitude.

> [!WARNING]
> The feature dimension is baked into the first FiLM layer (`57 × 64`). Any checkpoint trained against an older 54-dim extractor is unloadable — `src/core/model_loader.py` rejects it rather than silently mis-predicting. Re-extract and retrain if you change the feature set.

---

## Two chemistries

The service handles both NASA-style **NMC** cells and **LFP** packs, because they fail differently and share nothing but the interface:

| | NMC (default) | LFP |
| --- | --- | --- |
| Artifacts | `soh_mamba_v1.6`, `isolation_forest_v1.6` | `*_v2.2-lfp` |
| Trained on | NASA Ames | Severson |
| Per-cell voltage range | 2.0 – 4.5 V | 2.0 – 3.8 V |
| Temperature domain | 4 / 24 / 43 °C clusters | single 30 °C chamber |

Declaring `chemistry` on the request matters: a real 8S LFP pack reading 26.4 V is a genuine overvoltage, but the shared NMC range is loose enough to miss it. Requests are also checked against the training temperature clusters, and flagged when they fall more than 5 °C outside any of them — an out-of-domain prediction is reported as such instead of being quietly returned.

---

## Dataset & split

**NASA Ames Battery Dataset** — 18650 cells, `cleaned_dataset` release. Split **by battery, never by timestep**, so no cell appears on both sides.

| Split | Cells | Notes |
| --- | --- | --- |
| Train | 24 cells | B0005–B0007, B0018 (24 °C) · B0025–B0032 (24 / 43 °C) · B0042–B0044 (22 °C) · B0033, B0034 (~197 cycles, deepest curves) · B0041, B0045, B0047, B0053–B0056 (4 °C) |
| Val | **B0046** | 4 °C, 72 cycles, SOH 0–86.4 % — held out |
| Test | **B0048** | 4 °C, 72 cycles — held out entirely |

The 4 °C cells exist for a reason: the original 15-cell train set had none, so the model had to extrapolate into a temperature domain it had never seen — the main cross-battery generalisation gap. B0047 was later moved val → train (`GH-88`) because the 4 °C train cells only spanned SOH 0–67.2 % while val/test demand predictions up to ~86 %, which caused systematic underprediction right at the 80 % EOL threshold. B0048 stayed fully held out, so the test protocol is still honest.

Excluded: B0036 (capacity spikes to 122 %), B0049–B0052 (too short or corrupt). SOH target: `capacity_current / 2.0 Ah × 100`. Seed `42` everywhere.

---

## Target metrics

| Metric | Target | Measured on |
| --- | --- | --- |
| MAE | **< 2.0 %** SOH | held-out test cell |
| RMSE | **< 3.0 %** SOH | held-out test cell |
| Anomaly F1 | **> 0.80** | — |
| Inference latency | **< 100 ms** | CPU, batch size 1 — the P1 ticket requirement |

`make benchmark --real-weights` enforces the latency SLA against production artifacts.

---

## Prescription layer

Based on Deng et al., *From Prediction to Prescription: LLM Agent for Context-Aware Maintenance Decision Support* (PHM Society, 2024).

```
POST /predict → { soh_percent, classification, confidence }
      │
      ▼ 1 — LLM: fault statement        "B0005 SOH 68.3 % — significant capacity fade…"
      ▼ 2 — LLM: search query generation
      ▼ 3 — RAG: ChromaDB over the SOP knowledge base   → top-3 procedures
      ▼ 4 — LLM: prescription report
        { action, steps, urgency, priority, sop_reference, safety_warnings }
```

The knowledge base lives in [`knowledge/`](knowledge) (`maintenance/`, `safety/`) and is ingested with `python scripts/ingest_rag.py`. Prescription quality is evaluated by [`eval/evaluate_prescription.py`](eval); usefulness feedback comes back through `POST /prescribe/feedback`.

| Component | Choice |
| --- | --- |
| LLM | Claude API |
| Vector DB | ChromaDB |
| Embeddings | sentence-transformers (baked into the image at build time) |

---

## Project structure

```
ai-module/
├── main.py                       # FastAPI entry point — loads artifacts, starts gRPC in the lifespan
├── src/
│   ├── core/
│   │   ├── config.py             # single source of truth: versions, dims, thresholds, paths
│   │   ├── model_loader.py       # artifact loading + version/dimension guards
│   │   ├── artifact_manifest.py  # what must be present for the service to be "ready"
│   │   ├── runtime.py · metrics.py
│   ├── models/                   # soh_predictor · rul_predictor · anomaly_detector
│   ├── features/extractor.py     # the 57-dim spectral + statistical extractor
│   ├── routers/                  # predict · prescribe · suggest · verify · health
│   ├── schemas/                  # pydantic request/response contracts
│   ├── services/                 # inference · confidence · prescription/ · suggest_* · verify
│   │                             # battery_history · classification_feedback · text_utils
│   ├── grpc_server.py · grpc_gen/
├── protos/ai_service.proto       # gRPC contract
├── scripts/                      # preprocess* · train · eval_* · experiment_* · benchmark_* ·
│                                 # gen_proto · ingest_rag · create_dummy_artifacts · grpc_client_demo
├── tests/                        # ~36 test modules incl. gRPC contract + production runtime
├── models/weights/               # committed artifacts (see below)
├── knowledge/                    # SOP knowledge base for RAG (maintenance/, safety/)
├── eval/ · demo/ · notebooks/    # evaluation harness, demo payloads, exploration
├── deploy/                       # Caddy config, host env template, deployment scripts
├── docs/                         # ADRs, integration guides, production runbook
└── Makefile · Dockerfile · Jenkinsfile · pyproject.toml
```

---

## Model artifacts & versioning

Committed under `models/weights/` — inference must use exactly the artifacts training produced.

| Artifact | Current | Notes |
| --- | --- | --- |
| `soh_mamba_v{MODEL_VERSION}.pth` | `1.6` | Production SOH model |
| `isolation_forest_v{MODEL_VERSION}.pkl` | `1.6` | Must match the model version |
| `scaler.pkl` | `1.3` | 6-feature MinMaxScaler |
| `feature_scaler.pkl` | `1.5` | 57-dim StandardScaler |
| `*_v2.2-lfp.*` | `2.2` | LFP chemistry set |
| `soh_mamba_long_v2.2.pth`, `feature_scaler_long.pkl` | `long-2.0` | `L = 4096` research pipeline |
| `soh_mamba_rul_v1.0.pth`, `feature_scaler_rul.pkl` | `1.0` | RUL predictor |

| Version bump | When |
| --- | --- |
| `v1.0 → v1.1` | Retrain, same architecture, new data or hyperparameters |
| `v1.x → v2.0` | Architecture change |

All artifacts of a set land in **one commit**, and scalers are **never refit on production data** — the model would then be reading a distribution it was not trained on.

---

## Development

```bash
make test          # pytest + coverage — gate is ≥ 85 %
make lint format   # ruff
```

Tests cover the pure pieces (extractor, preprocessing, confidence, schemas), the routers, the gRPC contract and server, the model loader's version guards, and the production runtime wiring — plus the RAG and prescription services.

**CI** — [`Jenkinsfile`](Jenkinsfile) runs: checkout → Python CI (lint, tests, coverage) → contract and deployment-config checks → filesystem security scan → immutable image build → container verification → image security scan + SBOM → a gated request for a trusted production release.

---

## Deployment

A multi-stage [`Dockerfile`](Dockerfile) pins the Python base image **by digest**, installs CPU-only Torch, and installs the runtime from a hash-locked requirements file (`requirements-runtime.lock`, `--require-hashes`) so a build is reproducible and cannot silently drift. The embedding model is downloaded at build time, so the container needs no model download at runtime.

Production runs on a VPS behind **Caddy**, which terminates TLS on 443 and multiplexes gRPC (HTTP/2) and REST to the same container. DNS, firewall, VPS and Jenkins contract: [`docs/production-deployment.md`](docs/production-deployment.md).

---

## Team

Capstone project **GSU26SE55** — supervisor: Trương Long.

| Name | Student ID | Role |
| --- | --- | --- |
| Nguyễn Phúc Duy | SE184821 | Backend + AI |
| Bùi Phước Thắng | SE180445 | Backend + AI |
| Mai Hồng Thái | SE183923 | Backend + AI |
| Trần Minh Trí | SE183109 | Frontend (team lead) |
| Nguyễn Nhật Minh | SE170310 | Frontend + AI |

---

## References

- Gu, A. & Dao, T. (2024). *Mamba: Linear-Time Sequence Modeling with Selective State Spaces.* COLM 2024 (arXiv:2312.00752).
- Liu, F. T., Ting, K. M. & Zhou, Z. H. (2008). *Isolation Forest.* ICDM 2008.
- Deng et al. (2024). *From Prediction to Prescription: LLM Agent for Context-Aware Maintenance Decision Support.* PHM Society.
- Severson, K. A. et al. (2019). *Data-driven prediction of battery cycle life before capacity degradation.* Nature Energy.
- Dubarry, M. & Liaw, B. Y. (2009). *Identify capacity fading mechanism in a commercial LiFePO4 cell.* Journal of Power Sources.
- [NASA Ames PCoE Battery Data Set](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/)
