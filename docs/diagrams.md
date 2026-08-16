# Diagrams — AI Module (GSU26SE55)

> Source of truth: the code in this repository. Each diagram lists its source files so it can be re-verified when the code changes.
> Rendering: GitHub renders Mermaid natively. To export an image for the report, paste a block into [mermaid.live](https://mermaid.live) → Export PNG/SVG.

**Status:** 3 of 10 complete. Remaining: Data pipeline, Training, Sequence, Decision logic, Artifact map, RAG, Feedback loop.

---

## 1. Component Diagram — AI Module in the system

Source: [main.py](../main.py) · [src/grpc_server.py](../src/grpc_server.py) · [src/routers/](../src/routers/) · [protos/ai_service.proto](../protos/ai_service.proto)

```mermaid
%%{init: {'flowchart': {'curve': 'linear'}}}%%
flowchart LR
    subgraph BE["Backend — ASP.NET Core"]
        BS["BatteryService"]
        TS["TicketService"]
    end

    subgraph AI["AI Module — Python 3.11"]
        direction TB

        subgraph TRANS["Transport Layer"]
            GRPC["gRPC Server :50051<br/>AiService — 10 RPCs<br/><b>production</b>"]
            REST["FastAPI REST :8000<br/>routers/<br/><i>backup &amp; dev</i>"]
        end

        SCHEMA["Pydantic Schemas<br/>src/schemas/<br/><i>shared by both transports</i>"]

        subgraph SVC["Service Layer"]
            INF["inference.py<br/>run_inference()"]
            PRE["prescription/<br/>orchestrator.py"]
            SUG["suggest_staff.py<br/>suggest_kb.py"]
            VER["verify.py"]
            HIST["battery_history.py<br/><i>in-memory SOH history</i>"]
        end

        subgraph ART["Artifacts — models/weights/"]
            NASA["NASA / NMC set<br/>soh_mamba_v1.6.pth<br/>scaler.pkl<br/>isolation_forest_v1.6.pkl"]
            LFP["LFP set<br/>soh_mamba_v2.2-lfp.pth<br/>scaler_lfp.pkl<br/>isolation_forest_v2.2-lfp.pkl"]
        end

        KB["knowledge/<br/>maintenance + safety<br/><i>RAG vector store</i>"]
    end

    LLM["LLM Provider Chain<br/><i>external — ADR 0003</i>"]

    BS -->|"Predict / PredictStream<br/>PredictLong"| GRPC
    TS -->|"Prescribe / VerifyTicket<br/>SuggestStaff / SuggestKb<br/>SubmitFeedback"| GRPC
    BS -.->|dev / test| REST

    GRPC --> SCHEMA
    REST --> SCHEMA
    SCHEMA --> INF
    SCHEMA --> PRE
    SCHEMA --> SUG
    SCHEMA --> VER

    INF --> HIST
    INF -->|"chemistry = null"| NASA
    INF -->|"chemistry = LFP"| LFP
    PRE --> INF
    PRE --> KB
    PRE --> LLM
```

**Points to make in the report:**

- The AI module is **stateless** — no relational database, only an in-memory SOH history keyed by battery.
- One pipeline, two transports — gRPC and REST both call `run_inference()`; the logic is never duplicated.
- Input is validated by the **same** Pydantic schema on both paths, so both transports reject identical payloads.
- Port 50051 is **not** exposed outside the Docker network.

---

## 2. Inference Pipeline — inside `run_inference()`

Source: [src/services/inference.py:278-460](../src/services/inference.py#L278) · [src/features/extractor.py](../src/features/extractor.py)

```mermaid
%%{init: {'flowchart': {'curve': 'linear'}}}%%
flowchart TD
    IN["Request<br/>readings (30 × 6)<br/>pack_config: chemistry, n_series, capacity_ah<br/>battery_id, cycle_idx"]

    VAL{"Validate<br/>Pydantic"}
    REJ["422 / INVALID_ARGUMENT"]

    ART["<b>Select artifact set</b><br/>_resolve_artifacts(chemistry)<br/>LFP → LFP set · otherwise → NASA set"]

    NORM["<b>Pack → cell normalisation</b><br/>voltage ÷ n_series<br/>current × nominal_Ah / capacity_Ah"]

    SCALE["MinMaxScaler [0,1]<br/>4 base columns:<br/>voltage, current, temperature, time"]

    DER["<b>Append 2 derived columns</b><br/>cycle_count / cycle_count_norm<br/>soc_percent / 100<br/>→ (30, 6)"]

    FEAT["<b>Cycle-level feature extraction</b><br/>extract_window_features()<br/>10 spectral + 9 statistical<br/>× 3 channels = 57 dims"]
    FSCALE["feature_scaler<br/>→ x_feat (1, 57)"]

    MC["<b>Mamba + MC Dropout</b><br/>10 stochastic samples, 1 batched forward<br/>Dropout ON"]

    STAT["mean → soh_percent<br/>std → soh_confidence = exp(−std / 5)<br/>median → drives every threshold"]

    ISO["<b>IsolationForest</b><br/>decision_function(x_feat)<br/>→ anomaly_score"]

    RATE["<b>Causal degradation rate</b><br/>battery_history.causal_rate()<br/>vs. this battery's own last 2 cycles"]

    CLS["<b>Classification</b><br/>classify_anomaly(score, soh, rate)<br/>classify_health_stage_probabilistic(mc_preds)<br/>classify_anomaly_status(score)"]

    WARN["<b>Warning generation</b><br/>generate_warnings()<br/>V / I / T thresholds per chemistry<br/>+ TEMP_OOD"]

    DEG["<b>Degradation metrics</b><br/>degradation_rate, rul_cycles<br/>soh_trend, cycles_to_maintenance"]

    RISK["<b>Risk profile</b><br/>compute_risk_profile()<br/>health_stage + anomaly + warnings"]

    OUT["Response<br/>prediction · anomaly · risk<br/>evidence · metadata<br/><b>inference_ms &lt; 100</b>"]

    IN --> VAL
    VAL -->|fail| REJ
    VAL -->|pass| ART
    ART --> NORM --> SCALE --> DER --> MC
    SCALE --> FEAT --> FSCALE
    FSCALE --> MC
    FSCALE --> ISO
    MC --> STAT
    STAT --> RATE --> CLS
    ISO --> CLS
    STAT --> CLS
    CLS --> RISK
    NORM --> WARN --> RISK
    NORM --> DEG --> RISK
    RISK --> OUT
    STAT --> OUT
```

**Points to make in the report:**

- The artifact set is chosen **first**, so the scaler, the model, the Isolation Forest and the normalisation constants can never come from different sets.
- Pack-to-cell conversion happens **before** the scaler, so an 8S / 24 V pack is scored against the per-cell distribution the model was trained on.
- MC Dropout draws 10 samples in **a single batched forward pass**, not a Python loop — this is what keeps the pipeline under 100 ms.
- Threshold decisions use the **median**; the reported figure is the **mean**. The median resists outliers when n = 10.
- The Isolation Forest scores the **57-dimensional feature vector**, not the raw sequence.

---

## 3. Model Architecture — MambaSOHPredictor

Source: [src/models/soh_predictor.py:342-500](../src/models/soh_predictor.py#L342)

```mermaid
%%{init: {'flowchart': {'curve': 'linear'}}}%%
flowchart TD
    X["<b>x</b> (B, 30, 6)<br/>voltage, current, temperature, time,<br/>cycle_count, soc_percent"]
    XF["<b>x_feat</b> (B, 57)<br/>spectral + statistical<br/>features of the window"]

    PROJ["Linear(6 → 64)"]
    M1["MambaBlock #1<br/>d_model=64, d_state=16<br/>d_conv=4, expand=2"]
    M2["MambaBlock #2<br/>d_model=64, d_state=16"]
    NORM["LayerNorm(64)"]
    POOL["Take last token<br/>h = h[:, −1, :]<br/>→ (B, 64)"]

    FILM["<b>FiLM conditioning</b><br/>film_proj: Linear(57→57) → SiLU → Linear(57→128)<br/>chunk → γ, β"]
    MOD["h = (sigmoid(γ) + 0.5) · h + β<br/>→ (B, 64)"]

    FC1["Linear(64 → 32)"]
    ACT["GELU + Dropout(0.2)"]
    FC2["Linear(32 → 1)"]
    OUT["<b>SOH</b> (B,) ∈ [0, 1] → × 100"]

    X --> PROJ --> M1 --> M2 --> NORM --> POOL --> MOD
    XF --> FILM --> MOD
    MOD --> FC1 --> ACT --> FC2 --> OUT
```

**Long-sequence variant (L = 4096)** — used by `PredictLong`, not by the production path:

```mermaid
%%{init: {'flowchart': {'curve': 'linear'}}}%%
flowchart LR
    A["x (B, 4096, 6)"] --> B["Conv1d patch embedding<br/>k=16, s=16<br/>→ 256 tokens"]
    B --> C["+ PatchDegradationEncoder<br/>RMS · P2P · std · kurtosis<br/>per patch, per channel"]
    C --> D["MambaBlock × 2<br/><b>d_state=32</b>"]
    D --> E["Multi-head<br/>attention pooling<br/>+ discharge bias"]
    E --> F["FiLM + head<br/>as above"]
```

**Points to make in the report:**

- **Pure PyTorch** — the `mamba-ssm` CUDA library is not required, so the model runs natively on Windows. An opt-in flag switches to the CUDA kernel on Kaggle/Colab: identical mathematics, only faster.
- **FiLM conditioning** is the departure from vanilla Mamba: the 57-dimensional cycle-level spectral features modulate the hidden state rather than being concatenated to the input.
- The production path (L = 30) uses `d_state=16` with last-token pooling; the long-sequence path uses `d_state=32` with attention pooling. These are **two distinct configurations and must not be drawn as one figure**.

---

## Remaining diagrams

| # | Diagram | Source |
|---|---------|--------|
| 4 | Data pipeline / preprocessing | `scripts/preprocess.py`, `preprocess_lfp.py`, `preprocess_snl.py` |
| 5 | Training pipeline | `scripts/train.py` |
| 6 | Sequence — BE ↔ AI (Predict, Prescribe, VerifyTicket) | `src/grpc_server.py`, `protos/ai_service.proto` |
| 7 | Decision logic flowchart | `src/models/anomaly_detector.py` |
| 8 | Model artifact / versioning map | `src/core/config.py`, `src/core/model_loader.py` |
| 9 | RAG pipeline | `src/services/prescription/`, `scripts/ingest_rag.py` |
| 10 | Feedback loop | `src/services/classification_feedback.py`, `prescription/history_store.py` |
