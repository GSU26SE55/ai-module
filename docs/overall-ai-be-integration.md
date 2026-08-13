# AI Module — Overall & BE Integration (gRPC primary, REST fallback)

> **Dự án:** Solar Lithium-ion Battery Maintenance Management System — GSU26SE55
> **Phạm vi file này:** toàn bộ chức năng AI, cách hoạt động, và **cách BE (.NET) connect tới AI qua gRPC** (REST/FastAPI là fallback).
> **Nguồn:** verify trực tiếp từ code (`src/`, `protos/ai_service.proto`) + smoke test thật (model v1.6, gRPC :50051). Mọi JSON dưới đây là response THẬT, không bịa.
> **Model đang chạy:** `MODEL_VERSION = "1.6"` (`src/core/config.py`).

---

## Mục lục

1. [AI làm gì — 3 năng lực](#1-ai-làm-gì--3-năng-lực)
2. [Cách hoạt động — luồng chuẩn](#2-cách-hoạt-động--luồng-chuẩn)
3. [Hai transport: gRPC (chính) + REST (fallback)](#3-hai-transport-grpc-chính--rest-fallback)
4. [Cách chạy AI service](#4-cách-chạy-ai-service)
5. [BE connect tới AI qua gRPC (.NET)](#5-be-connect-tới-ai-qua-grpc-net)
6. [Contract & JSON Request/Response](#6-contract--json-requestresponse)
7. [Semantics BẮT BUỘC BE phải biết](#7-semantics-bắt-buộc-be-phải-biết)
8. [BE dùng output thế nào (ticket ITIL)](#8-be-dùng-output-thế-nào-ticket-itil)

---

## 1. AI làm gì — 3 năng lực

| Năng lực | Model | Vào → Ra |
|----------|-------|----------|
| **SOH** (State of Health) | Mamba SSM (pure-PyTorch, không CUDA) | 30 timestep cảm biến → % sức khỏe pin |
| **Anomaly** (bất thường) | IsolationForest (sklearn) | 57 đặc trưng phổ → `Normal` / `Degrading` / `Failed` |
| **Prescription** (kê đơn bảo trì) | Rule-based + (RAG + LLM tùy chọn) | Kết quả dự đoán → các bước sửa + PPE + escalation |

- **Predict** không gọi mạng, không cần API key — chạy hoàn toàn bằng model local.
- **Prescribe** mặc định là rule-based (`enrich=false`, <100ms). Chỉ khi `enrich=true` mới gọi LLM (DeepSeek→Gemini→Anthropic, tự fallback về rule nếu LLM lỗi/không có key).

---

## 2. Cách hoạt động — luồng chuẩn

### 2.1 Luồng phát triển (offline → online)

```
[1] DỮ LIỆU     scripts/preprocess.py  — NASA raw CSV → cắt window=30, tính SOH, chia theo battery ID
[2] TRAIN       scripts/train.py (Kaggle GPU) — Mamba (SOH) + IsolationForest (anomaly)
                → xuất: soh_mamba_v1.6.pth, isolation_forest_v1.6.pkl, scaler.pkl, feature_scaler.pkl
                → commit CẢ 4 artifacts vào Git cùng lúc
[3] SERVE       load_models() nạp 4 artifacts 1 lần lúc khởi động → REST + gRPC dùng chung pipeline
```

**Nguyên tắc vàng:** train và inference phải khớp tuyệt đối — cùng `window=30`, cùng scaler (KHÔNG fit lại trên production), cùng version. Sai version → service **raise lỗi rõ ràng lúc startup** (`model_loader.py`), không predict sai âm thầm.

### 2.2 Luồng runtime 1 request `/predict`

```
readings (30 × 4) [voltage, current, temperature, time]
   │
   ├─ schema validate (chặn NaN/Inf, giá trị ngoài range per-cell)      src/schemas/predict.py
   ├─ pack→cell normalize (chia điện áp / n_series, C-rate current)     src/services/inference.py
   ├─ scaler.transform + thêm 2 cột phái sinh (cycle_count, soc) → (30,6)
   ├─ extractor: 57-dim spectral + kurtosis từ 3 kênh đầu               src/features/extractor.py
   ├─ Mamba chạy 10 lần (MC Dropout) → SOH trung bình + confidence      src/models/soh_predictor.py
   ├─ IsolationForest.decision_function → anomaly score                 src/models/anomaly_detector.py
   ├─ so với lịch sử chính pin đó (causal rate) → classification        src/services/battery_history.py
   └─ sinh warnings + risk (P1/P2/P3) + degradation + RUL
   │
   └→ JSON: soh_percent, classification, confidence, warnings, priority, recommended_action, ...
```

### 2.3 Luồng 1 request `/prescribe`

```
run_inference()  ← chạy step 1 (LUÔN chạy, bất kể enrich)
   → rule-based prescription (deterministic, baseline)
   → nếu enrich=true: RAG (ChromaDB tìm SOP) + LLM sinh đơn chi tiết
   → safety gate: chặn output nguy hiểm, inject LOTO/thermal, enforce PPE
   → nếu bị block → fallback rule-based + human_verification_required=true
   → JSON: prescription, action_steps, ppe_required, escalation, + nested prediction/anomaly/risk
```

---

## 3. Hai transport: gRPC (chính) + REST (fallback)

Cùng một pipeline (`run_inference()` / `run_prescription()`), **không nhân đôi logic**. Đã có parity test field-by-field (`tests/test_grpc_server.py`).

| Transport | Port | Entrypoint | Dùng cho |
|-----------|------|-----------|----------|
| **gRPC** `aimodule.v1.AiService` | **50051** (env `GRPC_PORT`) | `python -m src.grpc_server` | **BE connect chính** — latency thấp, streaming |
| REST (FastAPI) | 8000 | `uvicorn main:app --port 8000` | **fallback** — Swagger UI, debug, tích hợp cũ |

**gRPC RPCs:** `Predict`, `Prescribe`, `Health` (unary, mirror REST) + `PredictStream` (bidirectional streaming — N window vào → N response ra, đúng thứ tự).

> ✅ **Đã smoke test thật:** `HEALTH: ok | model 1.6 | scaler True | mamba True | iso True` · `PREDICT: latency 33.6ms < 100ms SLA`.

---

## 4. Cách chạy AI service

### 4.1 Yêu cầu môi trường

- **Python 3.11** + `torch==2.6.0` (ghim cứng). Production và CI dùng Python 3.11 để giữ cùng một runtime đã được kiểm thử; dùng venv 3.11 hoặc Docker `python:3.11`.
- Artifacts `models/weights/soh_mamba_v1.6.pth`, `scaler.pkl`, `feature_scaler.pkl`, `isolation_forest_v1.6.pkl` — **đã có sẵn trong repo**, không cần train lại.

### 4.2 Chạy bằng venv (local)

```bash
cd ai-module
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# gRPC (BE gọi cái này) — port 50051
python -m src.grpc_server

# REST fallback (Swagger) — port 8000, chạy song song tùy chọn
uvicorn main:app --port 8000
```

### 4.3 Chạy bằng Docker (nếu máy không có Python 3.11)

```bash
cd ai-module
docker run --rm -p 50051:50051 -v "$PWD":/app -w /app python:3.11-slim bash -c '
  pip install -r requirements.txt && python -m src.grpc_server'
```

> Chỉ test core Predict/Health (không cần LLM) thì cài gọn:
> `pip install torch==2.6.0 numpy==1.26.4 scikit-learn==1.6.1 scipy==1.13.1 pydantic==2.13.4 joblib==1.4.2 grpcio==1.81.1 protobuf==6.33.6`

### 4.4 Kiểm tra sống

```bash
# REST
curl http://localhost:8000/health
# → {"status":"ok","model_version":"1.6","scaler_loaded":true,"mamba_loaded":true,"isolation_forest_loaded":true}

# gRPC — demo đủ 4 RPC (thay Swagger)
python scripts/grpc_client_demo.py

# Benchmark latency (enforce SLA <100ms với weights thật)
python scripts/benchmark_grpc.py --real-weights
```

### 4.5 API key (chỉ cần cho `/prescribe?enrich=true`)

Không key nào bắt buộc để chạy Predict + Prescribe rule-based. Muốn bật LLM enrichment thì cần **ít nhất 1 key**:

```bash
cp .env.example .env      # điền DEEPSEEK_API_KEY hoặc GEMINI_API_KEY
uvicorn main:app --env-file .env --port 8000
```

---

## 5. BE connect tới AI qua gRPC (.NET)

### 5.1 Lấy proto & gen C# client

Copy `protos/ai_service.proto` từ repo `ai-module` vào BE (giữ nguyên — mọi thay đổi contract phải qua repo ai-module trước).

```xml
<!-- ServiceName.Infrastructure.csproj -->
<ItemGroup>
  <PackageReference Include="Google.Protobuf" Version="3.27.*" />
  <PackageReference Include="Grpc.Net.Client" Version="2.63.*" />
  <PackageReference Include="Grpc.Tools" Version="2.63.*" PrivateAssets="All" />
</ItemGroup>
<ItemGroup>
  <Protobuf Include="Protos\ai_service.proto" GrpcServices="Client" />
</ItemGroup>
```

Build xong có namespace **`AiModule.V1`**: `AiService.AiServiceClient`, `PredictRequest`, `PredictResponse`, ...

### 5.2 Gọi unary (khuyến nghị: chỉ gọi `Prescribe`)

> **GH-87:** cho use-case tạo/enrich ticket, gọi **`Prescribe` DUY NHẤT** — `Predict` chạy nội bộ nên response `Prescribe` đã có đủ block `prediction`/`anomaly`/`risk`. **KHÔNG** gọi cả `Predict` lẫn `Prescribe` trên cùng window (mỗi lần chạy MC Dropout riêng → có thể lệch nhau ở ngưỡng). `Predict`/`PredictStream` chỉ dành cho dashboard real-time.

```csharp
using AiModule.V1;
using Grpc.Net.Client;

// Channel tạo 1 lần, tái dùng (DI singleton) — KHÔNG tạo per-request
var channel = GrpcChannel.ForAddress("http://ai-module:50051");   // insecure, nội bộ docker network
var client  = new AiService.AiServiceClient(channel);

// Health
var health = await client.HealthAsync(new HealthRequest());

// Prescribe — 30 timesteps × 4 features [voltage, current, temperature, time]
var req = new PrescribeRequest { BatteryId = "B0005", Enrich = false };
foreach (var row in windowRows)          // 30 hàng, mỗi hàng 4 double
{
    var reading = new Reading();
    reading.Values.AddRange(row);        // [3.72, -1.5, 25.3, 120.0]
    req.Readings.Add(reading);
}
var resp = await client.PrescribeAsync(req);
// resp.Prediction.SohPercent, resp.Risk.Priority ("P1".."P3"|"None"),
// resp.ActionCode, resp.ActionSteps, resp.HumanVerificationRequired ...
```

### 5.3 Streaming (dashboard real-time)

```csharp
using var call = client.PredictStream();
foreach (var window in windows)                  // mỗi request = 1 window 30×4 ĐẦY ĐỦ
    await call.RequestStream.WriteAsync(window);
await call.RequestStream.CompleteAsync();
await foreach (var r in call.ResponseStream.ReadAllAsync())   // N responses, đúng thứ tự request
    Console.WriteLine($"{r.BatteryId}: {r.SohPercent}%");
```

---

## 6. Contract & JSON Request/Response

> gRPC dùng proto (`ai_service.proto`) nhưng payload **1:1 với JSON REST**. JSON dưới đây là **response THẬT** dump từ pipeline (model v1.6). Dùng để BE map field và viết test.

### 6.1 `Predict` / `POST /predict/`

**Request:**
```json
{
  "battery_id": "B0005",
  "readings": [
    [3.70, -1.2, 30.0, 0.0],
    [3.698, -1.2, 30.05, 13.0],
    "... đủ 30 dòng [voltage, current, temperature, time]"
  ],
  "pack_config": {
    "n_series": 1,
    "chemistry": null,
    "capacity_ah": null
  }
}
```
> `pack_config` **tùy chọn** (bỏ = pin đơn cell). Multi-cell pack: gửi `n_series` (vd 12V/3S → `n_series:3`), `chemistry` (`"LFP"`/`"NMC"`), `capacity_ah`.
> Readings chấp nhận **4 features** (chuẩn sau ablation GH-25), hoặc 6 (BE tự tính `cycle_count`+`soc_percent`), hoặc 3 (legacy).

**Response (rút gọn — các field chính, nested + flat compat):**
```json
{
  "battery_id": "B0005",
  "prediction": {
    "soh_percent": 53.57,
    "soh_confidence": 0.367,
    "soh_std": 1.392,
    "rul_cycles_estimate": 0,
    "degradation_rate_per_cycle": 2.0,
    "soh_trend": "stable",
    "cycles_to_maintenance": 0,
    "soh_trajectory": [51.6, 49.6, 47.6, 45.6, 43.6],
    "health_stage": "End Of Life",
    "stage_probabilities": {"End Of Life": 1.0, "Maintenance Required": 0.0, "Degrading": 0.0, "Healthy": 0.0},
    "stage_confidence": 1.0,
    "is_borderline": false
  },
  "anomaly": {
    "anomaly_score": 0.2192,
    "anomaly_status": "Normal",
    "anomaly_confidence": 0.219
  },
  "risk": {
    "risk_level": "Critical",
    "priority": "P1",
    "action_code": "REPLACE_IMMEDIATELY",
    "reasons": ["SOH 53.6% is below 80% end-of-life threshold", "..."]
  },
  "evidence": {
    "warnings": [
      {"code": "BATTERY_EOL", "severity": "critical", "message": "SOH 53.6% is below end-of-life threshold (80%) — battery should be replaced."},
      {"code": "TEMP_OOD", "severity": "warning", "message": "Temperature 7.5°C from nearest training cluster (4/24/44°C) — prediction may be extrapolated."}
    ],
    "feature_summary": {
      "voltage": {"mean": 3.671, "min": 3.642, "max": 3.7},
      "current": {"mean": -1.2, "min": -1.2, "max": -1.2},
      "temperature": {"mean": 30.725, "min": 30.0, "max": 31.45},
      "time": {"mean": 188.5, "min": 0.0, "max": 377.0}
    }
  },
  "metadata": {
    "model_version": "1.6",
    "window_size": 30,
    "input_features": 6,
    "inference_ms": 13.12,
    "n_series": 1,
    "chemistry": null,
    "capacity_ah": null,
    "temperature_domain_distance": 7.45,
    "is_temperature_ood": true
  },

  "soh_percent": 53.57,
  "classification": "Failed",
  "confidence": 0.367,
  "inference_ms": 13.12,
  "rul_cycles_estimate": 0,
  "degradation_rate_per_cycle": 2.0,
  "soh_trend": "stable",
  "cycles_to_maintenance": 0,
  "soh_trajectory": [51.6, 49.6, 47.6, 45.6, 43.6],
  "anomaly_score": 0.2192,
  "recommended_action": "REPLACE_IMMEDIATELY",
  "warnings": [ /* = evidence.warnings */ ],
  "feature_summary": { /* = evidence.feature_summary */ }
}
```

> **Flat fields** (`soh_percent`, `classification`, `confidence`, ...) là bản backward-compat, dẫn xuất từ nested block (single source). Giữ đến khi BE migrate xong sang nested. BE mới nên đọc **nested** (`prediction.*`, `risk.*`).
> `classification` (flat) = 3 tier `Normal/Degrading/Failed`. `health_stage` (nested) = 4 tier chi tiết hơn `Healthy/Degrading/Maintenance Required/End Of Life`.

### 6.2 `Prescribe` / `POST /prescribe/`

**Request:**
```json
{
  "battery_id": "B0005",
  "readings": [ "... 30 dòng [voltage, current, temperature, time]" ],
  "enrich": false,
  "agentic": false,
  "pack_config": { "n_series": 1 },
  "age_cycles": null,
  "last_maintenance_date": null,
  "ticket_history": []
}
```
> `enrich=false` (mặc định) → rule-based, <100ms, không gọi LLM. `enrich=true` → thêm RAG+LLM (chậm, vài giây). `agentic=true` chỉ có tác dụng khi `enrich=true`.

**Response THẬT (rule-based, `enrich=false`):**
```json
{
  "battery_id": "B0005",
  "soh_percent": 50.48,
  "risk_level": "Critical",
  "priority": "P1",
  "action_code": "REPLACE_IMMEDIATELY",

  "prediction": { "soh_percent": 50.48, "soh_confidence": 0.722, "health_stage": "End Of Life",
                  "stage_confidence": 1.0, "is_borderline": false, "rul_cycles_estimate": 0, "...": "..." },
  "anomaly":    { "anomaly_score": 0.2192, "anomaly_status": "Normal", "anomaly_confidence": 0.219 },
  "risk":       { "risk_level": "Critical", "priority": "P1", "action_code": "REPLACE_IMMEDIATELY", "reasons": ["..."] },

  "prescription": "Battery has reached end-of-life — immediate replacement required. Current SOH 50.5%, risk Critical, priority P1. Active warnings: BATTERY_EOL, TEMP_OOD.",
  "action_steps": [
    "Isolate the battery from the system using the Lockout/Tagout procedure.",
    "Measure open-circuit voltage and surface temperature before removal.",
    "Replace with a unit of identical specification per the maintenance SOP §3.",
    "Record final SOH, anomaly status, and replacement reason in the ticket."
  ],
  "escalation_conditions": ["Immediate replacement required — notify manager within 1 hour"],
  "ppe_required": ["Insulated gloves (>=500V)", "Safety glasses (ANSI Z87.1)", "Steel-toed footwear"],
  "sop_references": ["battery_maintenance_sop §3 (Replacement Criteria)", "electrical_safety_sop (LOTO + isolation)"],

  "enriched": false,
  "llm_provider": "none",
  "prescription_id": "",
  "maintenance_docs": [],
  "safety_docs": [],

  "human_verification_required": true,
  "safety_warnings": ["Mandatory PPE missing from generated output — enforced per PPE matrix: Steel-toed footwear"],
  "blocked": false,

  "inference_ms": 9.86,
  "rag_ms": 0.0,
  "llm_ms": 0.0,
  "query_gen_ms": 0.0,
  "generated_queries": []
}
```

> Khi `enrich=true` và LLM chạy được: `enriched=true`, `llm_provider` = `"deepseek"`/`"gemini"`, `maintenance_docs`/`safety_docs` có SOP retrieve, `prescription_id` là uuid4 (dùng cho `POST /prescribe/feedback` — **REST-only**).

### 6.3 `Health` / `GET /health`

```json
{ "status": "ok", "model_version": "1.6", "scaler_loaded": true, "mamba_loaded": true, "isolation_forest_loaded": true }
```

---

## 7. Semantics BẮT BUỘC BE phải biết

| # | Quy tắc | Chi tiết |
|---|---------|----------|
| 1 | **Payload 4 features** | `[voltage, current, temperature, time]` (sau ablation GH-25, bỏ current_load/voltage_load). Gửi 5 hoặc số cột lạ → `INVALID_ARGUMENT`. |
| 2 | **Window = 30 timesteps** | Khác 30 → `INVALID_ARGUMENT` (cùng rule REST 422). |
| 3 | **Range guard per-cell** | Voltage/cell ngoài `[2.0, 4.5]V`, current-equiv ngoài `[-5,5]A`, temp ngoài `[-10,60]°C`, hoặc NaN/Inf → reject. 12V pack chưa quy đổi → gửi `pack_config.n_series` kèm hint. |
| 4 | **Error codes gRPC** | Input sai → `INVALID_ARGUMENT`; lỗi pipeline → `INTERNAL`; server chưa chạy → `UNAVAILABLE`. **Không** có kiểu "200 with error" như REST wrapper. |
| 5 | **Insecure channel** | Port 50051 không TLS/auth (scope capstone) — chỉ nội bộ docker network, dùng `http://` (không `https://`). KHÔNG expose ra ngoài. |
| 6 | **Stream chết theo message lỗi** | gRPC bidi không có per-message error: window lỗi ở vị trí k → client nhận k−1 responses rồi stream kết thúc bằng `RpcException`. Client catch → reconnect → gửi tiếp từ k+1. |
| 7 | **In-order + backpressure** | Responses đúng thứ tự requests; HTTP/2 flow control tự điều tiết. |
| 8 | **Channel tái dùng** | Tạo `GrpcChannel` 1 lần (DI singleton), KHÔNG tạo per-request. |
| 9 | **priority ≠ ticket Priority** | Xem §8. |

---

## 8. BE dùng output thế nào (ticket ITIL)

**QUAN TRỌNG (GH-23):** `risk.priority` (`P1`/`P2`/`P3`/`None`) mà AI trả về **KHÔNG phải Priority cuối của ticket**. Nó chỉ là **tín hiệu Urgency** tính thuần từ mức độ nghiêm trọng của pin (health_stage, anomaly, critical warnings) — AI **không biết** `ImpactScope` (Site / SingleAsset / MultiSite).

BE phải:
1. Lấy `risk.priority` từ AI làm **Urgency**.
2. Kết hợp với **ImpactScope** của BE qua **Priority Matrix (Impact × Urgency)** → ra Priority ticket thật.
3. Priority cố định suốt vòng đời ticket; breach SLA → escalate thêm nhân lực, không đổi deadline.

Ngoài ra:
- `action_code` (`MONITOR` / `SCHEDULE_MAINTENANCE` / `SCHEDULE_REPLACEMENT` / `REPLACE_IMMEDIATELY`) → gợi ý loại công việc.
- `human_verification_required=true` (luôn true khi P1 hoặc bị safety-block) → ticket phải có người duyệt trước khi thực thi.
- `warnings[]` + `prescription` + `action_steps[]` → nội dung mô tả + checklist cho technician.
- `evidence.feature_summary` + `metadata.is_temperature_ood` → audit/độ tin cậy (pin đang extrapolate ngoài vùng train).

---

### Phụ lục — file & lệnh tham chiếu

| Việc | File / Lệnh |
|------|-------------|
| Contract gRPC | `protos/ai_service.proto` → gen: `python scripts/gen_proto.py` |
| Server gRPC | `python -m src.grpc_server` (:50051) |
| REST fallback | `uvicorn main:app --port 8000` (Swagger `/docs`) |
| Demo 4 RPC | `python scripts/grpc_client_demo.py` |
| Benchmark SLA | `python scripts/benchmark_grpc.py --real-weights` |
| Pipeline inference | `src/services/inference.py :: run_inference()` |
| Pipeline prescribe | `src/services/prescription/orchestrator.py :: run_prescription()` |
| Guide gốc (BE) | `docs/grpc-integration-be.md` |
