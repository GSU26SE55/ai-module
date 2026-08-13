# Diagram — AI Module (GSU26SE55)

> Nguồn sự thật: code trong repo này. Mỗi diagram ghi rõ file gốc để đối chiếu khi code đổi.
> Render: GitHub tự render Mermaid. Export ảnh chèn Word: dán code vào https://mermaid.live → Export PNG/SVG.

**Trạng thái:** 3/10 diagram. Còn lại: Data pipeline, Training, Sequence, Decision logic, Artifact map, RAG, Feedback loop.

---

## 1. Component Diagram — AI module trong hệ thống

Nguồn: [main.py](../main.py) · [src/grpc_server.py](../src/grpc_server.py) · [src/routers/](../src/routers/) · [protos/ai_service.proto](../protos/ai_service.proto)

```mermaid
flowchart LR
    subgraph BE["Backend — ASP.NET Core"]
        BS["BatteryService"]
        TS["TicketService"]
    end

    subgraph AI["AI Module — Python 3.11"]
        direction TB

        subgraph TRANS["Transport Layer"]
            GRPC["gRPC Server :50051<br/>AiService — 10 RPC<br/><b>production</b>"]
            REST["FastAPI REST :8000<br/>routers/<br/><i>backup & dev</i>"]
        end

        SCHEMA["Pydantic Schemas<br/>src/schemas/<br/><i>dùng chung 2 transport</i>"]

        subgraph SVC["Service Layer"]
            INF["inference.py<br/>run_inference()"]
            PRE["prescription/<br/>orchestrator.py"]
            SUG["suggest_staff.py<br/>suggest_kb.py"]
            VER["verify.py"]
            HIST["battery_history.py<br/><i>SOH history in-memory</i>"]
        end

        subgraph ART["Artifacts — models/weights/"]
            NASA["Bộ NASA/NMC<br/>soh_mamba_v1.6.pth<br/>scaler.pkl<br/>isolation_forest_v1.6.pkl"]
            LFP["Bộ LFP<br/>soh_mamba_v2.1-lfp.pth<br/>scaler_lfp.pkl<br/>isolation_forest_v2.1-lfp.pkl"]
        end

        KB["knowledge/<br/>maintenance + safety<br/><i>vector store RAG</i>"]
    end

    LLM["LLM Provider Chain<br/><i>external — ADR 0003</i>"]

    BS -->|"Predict / PredictStream<br/>PredictLong"| GRPC
    TS -->|"Prescribe / VerifyTicket<br/>SuggestStaff / SuggestKb<br/>SubmitFeedback"| GRPC
    BS -.->|dev/test| REST

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

    classDef ext fill:#eee,stroke:#888,stroke-dasharray:4 3
    class LLM,BE ext
```

**Điểm cần nói trong báo cáo:**
- AI module **stateless** — không có database quan hệ, chỉ có in-memory SOH history
- Một pipeline, hai transport — gRPC và REST gọi chung `run_inference()`, không duplicate logic
- Validate input bằng **cùng một** Pydantic schema → hai transport reject giống hệt nhau
- Port 50051 **không** expose ra ngoài Docker network

---

## 2. Inference Pipeline — chi tiết box `run_inference()`

Nguồn: [src/services/inference.py:278-460](../src/services/inference.py#L278) · [src/features/extractor.py](../src/features/extractor.py)

```mermaid
flowchart TD
    IN["Request<br/>readings (30 × 6)<br/>pack_config: chemistry, n_series, capacity_ah<br/>battery_id, cycle_idx"]

    VAL{"Validate<br/>Pydantic"}
    REJ["422 / INVALID_ARGUMENT"]

    ART["<b>Chọn bộ artifact</b><br/>_resolve_artifacts(chemistry)<br/>LFP → bộ LFP · else → bộ NASA"]

    NORM["<b>Chuẩn hoá pack → cell</b><br/>voltage ÷ n_series<br/>current × nominal_Ah / capacity_Ah"]

    SCALE["MinMaxScaler [0,1]<br/>4 cột base:<br/>voltage, current, temperature, time"]

    DER["<b>+2 cột dẫn xuất</b><br/>cycle_count / cycle_count_norm<br/>soc_percent / 100<br/>→ (30, 6)"]

    FEAT["<b>Trích đặc trưng chu kỳ</b><br/>extract_window_features()<br/>10 spectral + 9 statistical<br/>× 3 kênh = 57 dim"]
    FSCALE["feature_scaler<br/>→ x_feat (1, 57)"]

    MC["<b>Mamba + MC Dropout</b><br/>10 mẫu ngẫu nhiên, 1 batched forward<br/>Dropout BẬT"]

    STAT["mean → soh_percent<br/>std → soh_confidence = exp(−std/5)<br/>median → dùng cho mọi ngưỡng"]

    ISO["<b>IsolationForest</b><br/>decision_function(x_feat)<br/>→ anomaly_score"]

    RATE["<b>Tốc độ suy giảm nhân quả</b><br/>battery_history.causal_rate()<br/>so với 2 chu kỳ trước CỦA CHÍNH pin đó"]

    CLS["<b>Phân loại</b><br/>classify_anomaly(score, soh, rate)<br/>classify_health_stage_probabilistic(mc_preds)<br/>classify_anomaly_status(score)"]

    WARN["<b>Sinh cảnh báo</b><br/>generate_warnings()<br/>ngưỡng V/I/T theo chemistry<br/>+ TEMP_OOD"]

    DEG["<b>Chỉ số suy giảm</b><br/>degradation_rate, rul_cycles<br/>soh_trend, cycles_to_maintenance"]

    RISK["<b>Hồ sơ rủi ro</b><br/>compute_risk_profile()<br/>health_stage + anomaly + warnings"]

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

    classDef bad fill:#fdd,stroke:#c33
    class REJ bad
```

**Điểm cần nói trong báo cáo:**
- Chọn bộ artifact **trước tiên** — để scaler, model, iforest và hằng số chuẩn hoá không bao giờ lệch bộ
- Quy đổi pack → cell **trước** scaler — pack 8S/24V được chấm điểm trên phân phối cell mà model đã học
- MC Dropout 10 mẫu chạy **1 lần forward theo batch**, không phải vòng lặp — đây là lý do đạt được <100ms
- Ngưỡng quyết định dùng **median**, số báo cáo dùng **mean** — median chống nhiễu khi n=10
- IsolationForest chấm điểm trên **57 chiều đặc trưng**, không phải trên chuỗi thô

---

## 3. Model Architecture — MambaSOHPredictor

Nguồn: [src/models/soh_predictor.py:342-500](../src/models/soh_predictor.py#L342)

```mermaid
flowchart TD
    X["<b>x</b> (B, 30, 6)<br/>voltage, current, temperature, time,<br/>cycle_count, soc_percent"]
    XF["<b>x_feat</b> (B, 57)<br/>spectral + statistical<br/>của cửa sổ"]

    PROJ["Linear(6 → 64)"]
    M1["MambaBlock #1<br/>d_model=64, d_state=16<br/>d_conv=4, expand=2"]
    M2["MambaBlock #2<br/>d_model=64, d_state=16"]
    NORM["LayerNorm(64)"]
    POOL["Lấy token cuối<br/>h = h[:, −1, :]<br/>→ (B, 64)"]

    FILM["<b>FiLM conditioning</b><br/>film_proj: Linear(57→57) → SiLU → Linear(57→128)<br/>chunk → γ, β"]
    MOD["h = (sigmoid(γ) + 0.5) · h + β<br/>→ (B, 64)"]

    FC1["Linear(64 → 32)"]
    ACT["GELU + Dropout(0.2)"]
    FC2["Linear(32 → 1)"]
    OUT["<b>SOH</b> (B,) ∈ [0, 1] → × 100"]

    X --> PROJ --> M1 --> M2 --> NORM --> POOL --> MOD
    XF --> FILM --> MOD
    MOD --> FC1 --> ACT --> FC2 --> OUT

    classDef film fill:#e8f0ff,stroke:#37c
    class FILM,MOD film
```

**Biến thể long-sequence (L=4096)** — dùng cho `PredictLong`, không phải đường production:

```mermaid
flowchart LR
    A["x (B, 4096, 6)"] --> B["Conv1d patch embed<br/>k=16, s=16<br/>→ 256 token"]
    B --> C["+ PatchDegradationEncoder<br/>RMS · P2P · std · kurtosis<br/>mỗi patch, mỗi kênh"]
    C --> D["MambaBlock × 2<br/><b>d_state=32</b>"]
    D --> E["Multi-head<br/>Attention Pool<br/>+ discharge bias"]
    E --> F["FiLM + head<br/>giống trên"]
```

**Điểm cần nói trong báo cáo:**
- **Pure PyTorch** — không dùng thư viện CUDA `mamba-ssm`, chạy được Windows native. Có nhánh opt-in dùng kernel CUDA trên Kaggle/Colab, cùng công thức toán, chỉ nhanh hơn
- **FiLM conditioning** là điểm khác biệt so với Mamba gốc: đặc trưng phổ cấp chu kỳ (57 chiều) điều biến trạng thái ẩn thay vì nối vào input
- Đường production (L=30) dùng `d_state=16` + pooling "last"; đường long-seq dùng `d_state=32` + attention pooling — **hai cấu hình khác nhau, đừng vẽ chung một hình**

---

## Còn lại (chưa vẽ)

| # | Diagram | Nguồn |
|---|---------|-------|
| 4 | Data pipeline / Preprocessing | `scripts/preprocess.py`, `preprocess_lfp.py`, `preprocess_snl.py` |
| 5 | Training pipeline | `scripts/train.py` |
| 6 | Sequence — BE ↔ AI (Predict, Prescribe, VerifyTicket) | `src/grpc_server.py`, `protos/ai_service.proto` |
| 7 | Decision logic flowchart | `src/models/anomaly_detector.py` |
| 8 | Model artifact / versioning map | `src/core/config.py`, `src/core/model_loader.py` |
| 9 | RAG pipeline | `src/services/prescription/`, `scripts/ingest_rag.py` |
| 10 | Feedback loop | `src/services/classification_feedback.py`, `prescription/history_store.py` |
