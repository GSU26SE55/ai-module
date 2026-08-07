 # AI Module — Tài liệu tổng quan (gRPC-first, cho BE tích hợp)

> **Dự án:** Solar Lithium-ion Battery Maintenance Management System — GSU26SE55
> **Cập nhật:** 2026-08-07 (verify lại toàn bộ từ code — bản 2026-07-22 ghi 4 RPC, thực tế đã 8;
> chưa có bộ LFP, chưa có guard cửa sổ, chưa có `soc_mode`)
> **Đối tượng đọc:** BE dev (.NET) cần dựng gateway gọi sang AI module.
> **Phạm vi:** Tài liệu này tập trung vào **gRPC (`aimodule.v1.AiService`, port 50051)** —
> đây là transport BE dùng thật trong production (xem [[grpc-is-production-transport]]).
> REST (`FastAPI`, port 8000) vẫn tồn tại và trả **cùng payload** (parity test field-by-field),
> nhưng chỉ dùng cho dev/Swagger/local testing — **không phải đường tích hợp BE nên đi**.
> Từ 2026-08, gRPC đã phủ **đủ** mọi chức năng (kể cả feedback loop) — BE không còn lý do chạm REST.

---

## Mục lục

1. [Tổng quan & Kiến trúc](#1-tổng-quan--kiến-trúc)
2. [Stack & Version hiện tại](#2-stack--version-hiện-tại)
3. [Model Architecture (tóm tắt)](#3-model-architecture-tóm-tắt)
4. [Dataset & Split hiện tại](#4-dataset--split-hiện-tại)
5. [Model Artifacts](#5-model-artifacts)
6. [gRPC Service Contract — `AiService`](#6-grpc-service-contract--aiservice)
7. [Request Semantics — Predict / Prescribe](#7-request-semantics--predict--prescribe)
8. [Response Semantics — Prediction / Anomaly / Risk](#8-response-semantics--prediction--anomaly--risk)
9. [⚠️ Giới hạn phải biết trước khi tích hợp](#9-️-giới-hạn-phải-biết-trước-khi-tích-hợp)
10. [Prescription Pipeline (rule → enrich → agentic → safety gate)](#10-prescription-pipeline-rule--enrich--agentic--safety-gate)
11. [Error handling & mã lỗi](#11-error-handling--mã-lỗi)
12. [Latency benchmark hiện tại](#12-latency-benchmark-hiện-tại)
13. [Setup client .NET (C#)](#13-setup-client-net-c)
14. [File tham khảo](#14-file-tham-khảo)

---

## 1. Tổng quan & Kiến trúc

```
Pin lithium-ion (BMS / IoT sensor)
        │  voltage, current, temperature, time (+ cycle_count, soc_percent nếu BE có)
        ▼
[BatteryService / TicketService (BE, .NET)]
        │
        │  gRPC :50051  (production — KHÔNG dùng REST :8000 cho luồng này)
        ▼
[AiService — ai-module]
   Predict / Prescribe / Health / PredictStream
        │
        ▼  PrescribeResponse.anomaly.anomaly_status != "Normal"
[TicketService] → tạo/enrich ticket P1/P2/P3 (Priority thật vẫn do BE tính — xem §8.3)
```

**Vì sao gRPC, không phải REST, cho luồng production:** latency thấp hơn, có streaming
(`PredictStream` cho sensor real-time), cùng pipeline/cùng validation với REST (parity test),
nên migrate không cần remap field. REST giữ lại cho Swagger/dev vì dễ curl/test tay.

**Khuyến nghị gọi (GH-87):** BE chỉ cần gọi **`Prescribe`** cho mọi use-case tạo/enrich ticket.
`Predict` chạy **nội bộ** trong `Prescribe` (bước 1), nên `PrescribeResponse` đã có đủ
`prediction`/`anomaly`/`risk` (kể cả uncertainty GH-86). Gọi riêng `Predict` chỉ dành cho
dashboard giám sát real-time không cần prescription text.
**KHÔNG** gọi cả `Predict` lẫn `Prescribe` trên cùng 1 window để lấy 2 loại thông tin — mỗi
lần gọi chạy MC Dropout độc lập (10 mẫu ngẫu nhiên mỗi lần), 2 response **có thể lệch nhau**
gần ngưỡng 80/85/90 (`health_stage` bị flip). Dùng nested block trong `Prescribe` làm nguồn
duy nhất.

---

## 2. Stack & Version hiện tại

| Thành phần | Version | File |
|---|---|---|
| **Bộ mặc định — NASA / NMC** | | |
| Mamba SOH (production, L=30) | **v1.6** (GH-88 split rebalance) | `models/weights/soh_mamba_v1.6.pth` |
| MinMaxScaler (6-feature) | v1.3 | `models/weights/scaler.pkl` |
| Feature StandardScaler (57-dim) | v1.5 | `models/weights/feature_scaler.pkl` |
| IsolationForest | v1.6 (theo Mamba) | `models/weights/isolation_forest_v1.6.pkl` |
| **Bộ LFP — Severson** (chọn khi `pack_config.chemistry="LFP"`) | | |
| Mamba SOH LFP | **v2.0-lfp** | `models/weights/soh_mamba_v2.0-lfp.pth` |
| Scaler + feature scaler + IsolationForest LFP | v2.0-lfp | `scaler_lfp.pkl`, `feature_scaler_lfp.pkl`, `isolation_forest_v2.0-lfp.pkl` |
| **Ngoài luồng Predict** | | |
| Mamba SOH Long (L≤4096) | v2.2 — dùng bởi `rpc PredictLong`, nạp **lười** | `models/weights/soh_mamba_long_v2.2.pth` |
| RUL Predictor (cycle-axis) | v1.0 — ⚠️ **KHÔNG nạp bởi service**, không RPC/endpoint nào gọi | `models/weights/soh_mamba_rul_v1.0.pth` |
| gRPC contract | `protos/ai_service.proto` — **8 RPC** | `src/grpc_gen/` (generated, committed) |
| grpcio / grpcio-tools / protobuf | 1.81.1 / 1.81.1 / 6.33.6 | `requirements.txt` |

Version mismatch giữa `scaler.pkl`/`feature_scaler.pkl`/model checkpoint làm server **crash ngay
lúc startup** (assertion trong `model_loader.py`) — không silent-fail, nên nếu gRPC server chạy
được nghĩa là 3 artifact đang khớp nhau.

---

## 3. Model Architecture (tóm tắt)

- **MambaSOHPredictor (production, L=30):** `Linear(6→64) → MambaBlock×2(d_model=64, d_state=16) →
  LayerNorm → last-token pooling → FiLM(feat_57) → Linear(64→32)+GELU+Dropout(0.2) → Linear(32→1)`.
  Input 6 kênh = 4 base (`voltage, current, temperature, time`) + 2 derived server-side
  (`cycle_count`, `soc_percent` — xem §7.1). MC Dropout **10 runs** (giảm từ 20, GH-63) → SOH% (mean)
  + `soh_std` → `soh_confidence = 1 - soh_std/5.0`.
- **MambaSOHPredictor Long (L=4096, d_state=32):** patch embedding P16S16 → 256 token, attention
  pooling, single forward pass (không MC Dropout). Ngoài scope tài liệu này (không expose qua
  `AiService` — chỉ REST `/predict-long`, không có RPC tương ứng).
- **RULPredictor (cycle-axis):** input `(30, 57)` — 30 chu kỳ, mỗi token là feature 57-dim của
  1 discharge cycle. Không expose qua `AiService` hiện tại.
- **IsolationForest:** `contamination=0.1, n_estimators=100, random_state=42`, input = feature
  57-dim đã `StandardScaler`. Output `decision_function` (âm hơn = bất thường hơn).

> Pure PyTorch SSM — không cần CUDA, chạy Windows 11 native. `torch.compile()` được warm-up ở
> cả eval/train mode lúc startup (MC Dropout cần train-mode graph) để tránh crash-on-request-#1.

---

## 4. Dataset & Split hiện tại

Hai bộ dữ liệu độc lập, chọn theo `pack_config.chemistry`.

### 4.1. Bộ mặc định — NASA Ames (18650 NMC, nominal 2.0 Ah)

| Split | Battery IDs | Số pin |
|---|---|---|
| Train | B0005/06/07/18, B0025–B0032, B0033, B0034, B0042–B0044, B0041, B0045, B0053, B0054, B0055, B0056, **B0047** | 24 |
| Val | B0046 (4°C) | 1 |
| Test | B0048 (4°C) — held out hoàn toàn | 1 |

Chia **theo battery ID** (không theo timestep) — tránh data leakage. **B0047 chuyển từ Val
sang Train ở GH-88** (2026-07-08): train 4°C cũ chỉ phủ SOH 0–67.2%, thiếu vùng 67–86% mà
val/test cần → model ngoại suy lệch dưới ngưỡng EOL 80%. Chi tiết: `docs/adr/0002-split-rebalance-b0047.md`.

> Model headline bài báo NCKH (`soh_mamba_long_v2.2.pth`, LOBO) train **trước** đổi split này,
> vẫn dùng split cũ 23/2/1 — xem `docs/nckh-paper-plan.md` §3.1 nếu cần đối chiếu.

**Target metrics:** MAE < 2% SOH · RMSE < 3% · Anomaly F1 > 0.80.
v1.6 đạt MAE 1.34% / RMSE 1.84% (`docs/GH-88` ablation report). Anomaly F1 trên window-shape
đơn thuần **chưa đạt** 0.80 (GH-70/GH-95) — xem §9.6.

### 4.2. Bộ LFP — Severson et al. 2019 (A123 APR18650M1A, nominal **1.1 Ah**)

Dùng khi request khai `pack_config.chemistry="LFP"`. Cell nhỏ hơn NASA và tuổi thọ dài hơn hẳn,
nên **mọi hằng số hiệu chỉnh đều khác** — đây là nguồn của cả một lớp lỗi (xem §7.2):

| Hằng số | NASA / NMC | LFP / Severson |
|---|---|---|
| Cell danh định (quy dòng về C-rate) | 2.0 Ah | **1.1 Ah** |
| `cycle_count` chuẩn hoá chia cho | 200 | **2300** |
| Cụm nhiệt độ lúc train | 4 / 24 / 44 °C | **30 °C** (Severson chạy 1 buồng duy nhất) |
| Dải điện áp per-cell hợp lệ | [2.0, 4.5] V | **[2.0, 3.8] V** |
| Tốc độ suy giảm quần thể | 0.15 %/chu kỳ | **0.0087 %/chu kỳ** (~2300 chu kỳ tới EOL) |
| `soc_mode` | `"window"` | `"cycle"` |

---

## 5. Model Artifacts

| File | Dùng cho | Commit vào Git |
|---|---|---|
| `scaler.pkl` | MinMaxScaler 6-feat | ✅ |
| `feature_scaler.pkl` | StandardScaler 57-dim | ✅ |
| `soh_mamba_v1.6.pth` | Production Mamba (L=30) | ✅ |
| `isolation_forest_v1.6.pkl` | IsolationForest | ✅ |
| `scaler_long.pkl`, `feature_scaler_long.pkl`, `soh_mamba_long_v2.2.pth` | Long model (L=4096, ngoài scope gRPC) | ✅ |
| `scaler_lfp.pkl`, `feature_scaler_lfp.pkl`, `soh_mamba_v2.0-lfp.pth`, `isolation_forest_v2.0-lfp.pkl` | Bộ LFP — **tuỳ chọn**, thiếu thì service vẫn boot nhưng request `chemistry="LFP"` sẽ lỗi rõ ràng | ✅ |
| `feature_scaler_rul.pkl`, `soh_mamba_rul_v1.0.pth` | RUL Predictor — ⚠️ `feat_dim=54` trong khi extractor sinh **57**, checkpoint này **đã chết** (lưu trước commit thêm Gini). Không code nào nạp nó | ✅ |

`scaler.pkl`/`feature_scaler.pkl` KHÔNG được fit lại trên production data — load từ file lúc
startup, mismatch version → server refuse to start (fail-fast, không silent wrong prediction).

---

## 6. gRPC Service Contract — `AiService`

Contract nguồn: `protos/ai_service.proto` (package `aimodule.v1`, C# namespace `AiModule.V1`).
Copy nguyên file này vào project BE — **mọi thay đổi contract phải qua repo `ai-module` trước**,
chỉ **thêm** field number mới, không reuse/đổi số cũ (wire compatibility).

```protobuf
service AiService {
  rpc Predict(PredictRequest) returns (PredictResponse);
  rpc Prescribe(PrescribeRequest) returns (PrescribeResponse);
  rpc Health(HealthRequest) returns (HealthResponse);
  rpc PredictStream(stream PredictRequest) returns (stream PredictResponse);
  rpc VerifyTicket(VerifyTicketRequest) returns (VerifyTicketResponse);
  rpc SubmitFeedback(SubmitFeedbackRequest) returns (SubmitFeedbackResponse);
  rpc PredictLong(PredictLongRequest) returns (PredictLongResponse);
  rpc SubmitClassificationFeedback(ClassificationFeedbackRequest)
      returns (ClassificationFeedbackResponse);
}
```

| RPC | Dùng để làm gì |
|---|---|
| `Prescribe` | **Đường BE nên dùng cho mọi ticket** — chạy `Predict` bên trong rồi trả kèm prescription |
| `Predict` | Dashboard giám sát real-time, không cần prescription text |
| `PredictStream` | Bidi stream — chấm nhiều window / nhiều pin trong 1 kết nối |
| `Health` | Kiểm bộ artifact nào đã nạp + **`soc_mode`** (bắt buộc đọc, xem §7.1) |
| `VerifyTicket` | Chấm ticket khách tự tạo là thật/rác + dò trùng mô tả |
| `SubmitFeedback` | KTV phản hồi về một prescription (`accepted`/`edited`/`rejected`) |
| `PredictLong` | SOH từ chuỗi **31–4096** timestep — phân tích lịch sử, vẽ chart. Trả **chỉ SOH**, không confidence/anomaly/risk |
| `SubmitClassificationFeedback` | Staff chấm nhãn anomaly của AI đúng/sai → AI đo được precision/recall |

Cả 8 RPC chạy trong **cùng process** với REST (`src/grpc_server.py`, `python -m src.grpc_server`,
`GRPC_PORT` env, default 50051) — **cùng pipeline** `run_inference()` / `run_prescription()`,
insecure channel (không TLS/auth — chỉ dùng nội bộ docker network, KHÔNG expose port 50051 ra
ngoài).

### 6.1. Message shapes chính

```protobuf
message Reading { repeated double values = 1; }        // positional row — xem §7.1
message ReadingFields {                                  // named-field alternative (GH-77)
  double voltage = 1; double current = 2; double temperature = 3; double time = 4;
  optional double cycle_count = 5; optional double soc_percent = 6;
}
message PackConfig {                                      // GH-65/67 — multi-cell pack
  int32 n_series = 1; string chemistry = 2; double capacity_ah = 3;
}
message PredictRequest {
  string battery_id = 1;
  repeated Reading readings = 2;
  repeated ReadingFields reading_objects = 3;   // nếu non-empty, ưu tiên hơn readings
  PackConfig pack_config = 4;                   // omit = single-cell (legacy)
}
message PredictResponse {
  PredictionInfo prediction = 2; AnomalyInfo anomaly = 3; RiskInfo risk = 4;
  EvidenceInfo evidence = 5; ResponseMetadata metadata = 6;
  // + flat backward-compat fields 7-19 (soh_percent, classification, confidence, ...)
}
message PrescribeRequest {          // "extends" PredictRequest theo convention field number
  string battery_id = 1; repeated Reading readings = 2;
  optional int32 age_cycles = 3; optional string last_maintenance_date = 4;
  repeated string ticket_history = 5;
  bool enrich = 6;             // default false — rule-based, <100ms hot-path
  PackConfig pack_config = 7;
  bool agentic = 8;            // chỉ có ý nghĩa khi enrich=true
}
message PrescribeResponse {
  // fields 2-23: flat/legacy + prescription-specific (prescription, action_steps, ppe_required,
  // sop_references, enriched, maintenance_docs, safety_docs, human_verification_required,
  // safety_warnings, blocked, prescription_id, ...)
  PredictionInfo prediction = 24; AnomalyInfo anomaly = 25; RiskInfo risk = 26;  // GH-87 nested
}
```

```protobuf
message HealthResponse {
  string status = 1; string model_version = 2;
  bool scaler_loaded = 3; bool mamba_loaded = 4; bool isolation_forest_loaded = 5;
  bool lfp_loaded = 6; string lfp_model_version = 7;
  string soc_mode = 8;         // của bộ mặc định — "window"
  string lfp_soc_mode = 9;     // của bộ LFP — "cycle"; "" khi lfp_loaded=false
  bool long_loaded = 10;       // nạp LƯỜI: false = "chưa ai gọi", KHÔNG phải "thiếu file"
  string long_model_version = 11;
}
message SubmitFeedbackRequest {
  string prescription_id = 1;        // từ PrescribeResponse.prescription_id (chỉ có khi enrich=true)
  string status = 2;                 // "accepted" | "edited" | "rejected" — khác → INVALID_ARGUMENT
  repeated string edited_steps = 3;  // rỗng nếu status != "edited"
  string note = 4;
}
message PredictLongRequest {
  string battery_id = 1;
  repeated Reading readings = 2;   // 31..4096 hàng, mỗi hàng 4 cột (cycle_count/soc_percent bị bỏ qua)
  PackConfig pack_config = 3;      // chuẩn hoá pack→cell giống Predict
}
message PredictLongResponse {
  string battery_id = 1; double soh_percent = 2; int32 seq_len = 3;
  string device = 4; double inference_ms = 5;
  string model_version = 6;        // LONG_MODEL_VERSION — KHÁC model_version của Predict
}
message VerifyTicketResponse {
  string verdict = 1;              // "legitimate" | "suspicious"
  double score = 2; string reason = 3;
  string duplicate_of_ticket_id = 4; double duplicate_score = 5; string duplicate_reason = 6;
}
```

> `SubmitFeedbackResponse.success` không bao giờ là `false` — `prescription_id` sai thì trả
> **`NOT_FOUND`** (tương ứng `404` bên REST). Đừng viết nhánh xử lý `success=false`.

> `ClassificationFeedbackResponse` có `has_precision`/`has_recall` (bool) vì proto3 scalar
> **không phân biệt** được "chưa có mẫu nào" với "precision = 0.0" — hai chuyện khác hẳn.

Toàn bộ field + comment gốc: xem `protos/ai_service.proto` trực tiếp (đã inline giải thích từng
GH ticket ngay trong file — đọc file đó khi cần chi tiết field-level thay vì tài liệu này).

### 6.2. Ví dụ JSON request/response

Xem file **`docs/examples/grpc-payloads.json`** — 3 kịch bản đầy đủ (Healthy/Normal,
Maintenance-Required/Warning, Critical-EOL trên pack LFP) cho cả `Predict` và `Prescribe`,
đã verify bằng cách chạy trực tiếp `src/models/anomaly_detector.py` +
`src/services/prescription/rule_prescription.py` + `safety_gate.py` thật (không phải số bịa) —
BE có thể copy-paste field name (snake_case, khớp `.proto`) để test qua grpcurl/Postman gRPC.

---

## 7. Request Semantics — Predict / Prescribe

### 7.1. Shape của `readings` — 3 dạng được chấp nhận

| Số cột | Cột | Khi dùng |
|---|---|---|
| **6 (khuyến nghị, GH-56)** | `voltage, current, temperature, time, cycle_count, soc_percent` | BE tự tính `cycle_count`/`soc_percent` từ lịch sử đầy đủ của pin (chính xác hơn AI tự đoán) — gửi thẳng, AI dùng nguyên (không tự derive lại). **Đây là default BE nên dùng** ([[be-predict-payload-6column-default]]). |
| 4 | `voltage, current, temperature, time` | AI tự tính `cycle_count`/`soc_percent` phía server (window-local Coulomb counting; `cycle_count` mặc định 0 vì gRPC `PredictRequest` không có field `cycle_idx` riêng — chỉ REST có). |
| 3 (legacy) | `voltage, current, temperature` | Chỉ dùng được với artifact rất cũ — tránh dùng cho payload mới. |

- `reading_objects` (named-field, `ReadingFields`) là **alternative**, không phải bổ sung — nếu
  gửi cả `readings` lẫn `reading_objects`, **`reading_objects` thắng** (giống REST Union-type).
  Ưu điểm: tránh lỗi đảo cột (`[v, i, t, time]` vs `[i, v, t, time]`) vì named field không thể
  đảo nhầm như positional array.
- `cycle_count`/`soc_percent` trong `ReadingFields` dùng `optional` — phải set **cả 2 cùng lúc
  hoặc không set cái nào** trên **toàn bộ** window (validator reject nếu window có readings vừa
  có vừa thiếu 2 field này).
- Window **PHẢI đúng 30 timestep** — khác 30 → `INVALID_ARGUMENT` (gRPC) / `422` (REST).

> ### ⚠️ `soc_percent` — PHẢI đọc `soc_mode` từ `Health`, đừng suy theo chemistry
>
> Ý nghĩa cột `soc_percent` là **thuộc tính của bộ artifact**, không phải của request:
>
> | Bộ | `soc_mode` | Định nghĩa |
> |---|---|---|
> | NASA / NMC | `"window"` | SOC **cục bộ trong window** — ~100% ở hàng đầu, giảm dần qua 30 hàng |
> | LFP | `"cycle"` | SOC theo **cả chu kỳ xả** — SOC thật của pin |
>
> Gửi sai định nghĩa **không bao giờ bị từ chối**. AI vẫn trả kết quả, chỉ là SOH lệch đi.
> Đo trên một pin thật: thiếu `chemistry` → SOH **38.25%** *"End Of Life"*; có `chemistry` →
> **98.29%** *"Healthy"*. **Lệch 60 điểm, không một dòng lỗi nào.**
>
> Không chắc thì **gửi 4 cột** — AI tự suy, an toàn hơn gửi 6 cột sai nghĩa.

### 7.2. `PackConfig` — pin nhiều cell (GH-65/67)

```
voltage_cell  = voltage_pack / n_series                      (TRƯỚC scaler + TRƯỚC threshold)
current_equiv = current_pack × (nominal_cell / capacity_ah)  (chỉ khi capacity_ah được set)

nominal_cell = 1.1 Ah nếu chemistry="LFP"  ·  2.0 Ah nếu không khai
```

**`nominal_cell` phụ thuộc chemistry** — bộ LFP train trên cell Severson 1.1 Ah, không phải cell
NASA 2.0 Ah. Hệ quả trực tiếp lên **trần dòng** của pack:

| Pack | Khai `chemistry="LFP"` | Không khai |
|---|---|---|
| 30 Ah | trần **136 A** (`5 × 30/1.1`) | trần **75 A** (`5 × 30/2.0`) |

Tải 100 A trên pack 30 Ah: khai chemistry thì **qua**, không khai thì **bị từ chối thẳng**.

- `n_series` (mặc định 1 = single cell, legacy behavior). Ví dụ 12V ≈ 3S NMC, **25.6V ≈ 8S LFP** (pin thật của dự án).
- `chemistry`: `"LFP"` chọn voltage warning profile riêng (LiFePO4 plateau phẳng 3.2-3.3V —
  profile NMC mặc định sẽ spam `VOLTAGE_LOW` sai và bỏ sót overcharge thật). Unset/unknown =
  NMC/NASA default. Tự động normalize `"lfp"/"lifepo4"` → `"LFP"`, `"nmc"` → `"NMC"`.
- `capacity_ah`: rescale current về C-rate tương đương cell NASA 2Ah **trước** scaler/range-guard/
  threshold. Không set = không rescale.
- **Quan trọng:** `raw` (dùng cho `warnings` + `feature_summary` trong response) là giá trị
  **SAU KHI** đã chia `n_series` / rescale `capacity_ah` — tức `evidence.feature_summary.voltage`
  BE nhận về là **per-cell**, KHÔNG phải pack voltage BE gửi lên. Đừng hiểu nhầm đây là echo lại
  giá trị gốc.
- **Chưa validate độ chính xác dự đoán trên đường cong LFP thật** (GH-67 chỉ chỉnh threshold
  cảnh báo, không phải retrain model cho LFP) — SOH% trên pin LFP vẫn suy ra từ model train trên
  NASA NMC/18650.

### 7.3. Value-range validation (GH-66) — reject trước khi vào scaler

| Field | Khoảng hợp lệ | Kiểm tra SAU khi áp dụng `pack_config` |
|---|---|---|
| Voltage (per-cell) | `[2.0, 4.5]` V | |
| Current (NASA-equivalent) | `[-5.0, 5.0]` A | |
| Temperature | `[-10.0, 60.0]` °C | không chia n_series |
| SOC percent | `[0.0, 100.0]` | chỉ check nếu gửi đủ 6 cột |

**Dải điện áp per-cell phụ thuộc chemistry:** `chemistry="LFP"` dùng **`[2.0, 3.8]`** V thay vì
dải chung `[2.0, 4.5]` V. Dải chung phải đủ rộng cho NMC sạc đầy 4.2 V nên quá lỏng với LFP —
cell LFP tối đa vật lý chỉ 3.65 V. Siết lại bắt được ca khai thiếu `n_series` (pack 8S/26.4 V mà
gửi `n_series=6` ra 4.40 V/cell — bất khả thi với LFP, dải chung vẫn cho lọt).

> Chiều ngược lại (`n_series` quá **lớn**) không chặn được: 26.4/10 = 2.64 V/cell trùng dải xả sâu
> hợp lệ. Cách chắc chắn duy nhất là đối chiếu `evidence.feature_summary.voltage.mean` **một lần**
> lúc tích hợp — LFP đúng `n_series` phải ra **≈ 3.2–3.3 V**.

### 7.4. Cửa sổ phải liền mạch về thời gian (GH-67)

Window trải quá **1500 giây (25 phút)** → `INVALID_ARGUMENT` / `422`. Cột `time` cũng phải
**không giảm**.

30 bản ghi liên tiếp trong DB **không** đảm bảo liên tiếp về thời gian. Ca thật đo trên pin LFP
8S: IoT mất kết nối 76 phút giữa window → 30 hàng trải **94 phút** thay vì ~8 phút → AI trả
SOH **81.84%** + `SCHEDULE_REPLACEMENT` cho một quả pin hoàn toàn khoẻ (111 window còn lại đều
`Healthy`).

**Vì sao từ chối hẳn thay vì trả kèm cảnh báo:** window hỏng kiểu này lại cho `soh_confidence`
**cao nhất cả file — 0.799** (trung vị 0.425). BE **không thể lọc bằng confidence**.

Độ nhạy đo được (giãn đều nhịp lấy mẫu):

| Nhịp/hàng | Độ dài window | SOH |
|---|---|---|
| 17 s | 8 phút | 100.00% ✅ |
| 30 s | 14 phút | 100.00% ✅ |
| 60 s | 29 phút | 95.50% ❌ |
| 120 s | 58 phút | 82.85% ❌ |

⇒ Ràng buộc suy ra cho BE: **nhịp lấy mẫu ≤ 50 s/hàng** (30 × 50 = 1500 s). Vượt trần là tình
huống **bình thường** sau khi IoT mất kết nối — bỏ qua window, đợi dữ liệu liền mạch, **không
tạo ticket**.

Ngoài khoảng → `INVALID_ARGUMENT` kèm message gợi ý (vd "gửi thêm `pack_config.n_series`") —
chặn silent garbage (12V pack chưa quy đổi bị coi là voltage-per-cell 12V → out of range ngay,
thay vì lọt qua scaler và ra SOH vô nghĩa với confidence bình thường). `NaN`/`Inf` cũng bị reject
tại đây (Pydantic `float` không tự chặn NaN).

---

## 8. Response Semantics — Prediction / Anomaly / Risk

### 8.1. `PredictionInfo` — uncertainty staging (GH-86)

`health_stage` không còn chỉ là 1 threshold trên `soh_percent` (mean) — được quyết định bằng
**argmax trên phân phối 10 mẫu MC Dropout** (mỗi mẫu rơi vào 1 trong 4 bin:
`End Of Life`(<80) / `Maintenance Required`(80-85) / `Degrading`(85-90) / `Healthy`(≥90)):

```
stage_probabilities: {"End Of Life": 0.1, "Maintenance Required": 0.9, ...}  // sums to 1.0
stage_confidence:    0.9     // probability của stage được chọn (argmax)
is_borderline:       false   // true khi stage_confidence < 0.7 — không stage nào áp đảo
```

BE nên hiển thị cảnh báo "kết quả chưa chắc chắn" khi `is_borderline=true`, thay vì chỉ tin
`health_stage` như một nhãn chắc chắn.

### 8.2. `AnomalyInfo` — 2 tầng phân loại độc lập

- `anomaly.anomaly_status` (`Normal`/`Warning`/`Anomaly`) — thuần từ `IsolationForest score`.
- `classification` (flat field, legacy 3-tier `Normal`/`Degrading`/`Failed`) — thuần từ `soh_percent`,
  chỉ hạ cấp `Normal→Degrading` nếu score bất thường VÀ SOH khỏe (≥90%).
- 2 field này **không phải cùng 1 taxonomy** — đừng map 1-1 giữa `anomaly_status` và `classification`.
- `anomaly.anomaly_confidence` = `|score|` clip `[0,1]` — **không phải xác suất calibrated**, chỉ
  là độ lớn tương đối của decision_function.

### 8.3. `RiskInfo.priority` — tín hiệu Urgency, KHÔNG phải Priority ticket cuối cùng

`risk.priority` (`P1`/`P2`/`P3`/`None`) tính **thuần từ severity kỹ thuật của pin**
(`health_stage`, `anomaly_status`, cảnh báo critical) — AI **không biết** `ImpactScope`
(Site/SingleAsset/MultiSite), chỉ BE có. Theo Priority Policy (`.claude/rules/design.md`):
Priority ticket thật = **ma trận Impact × Urgency**, chốt lúc Manager triage, không role nào đổi
sau đó.

```
risk.priority (AI, chỉ severity pin)  +  ImpactScope (BE)  →  Priority Matrix (BE)  →  Priority ticket thật
```

**⚠️ Gotcha đã verify bằng code thật — `priority` không tỉ lệ thuận với mức độ hành động:**
Bất kỳ `soh_percent` nào rơi vào khoảng **80–85%** (`health_stage = "Maintenance Required"`)
LUÔN kèm cảnh báo `SOH_CRITICAL` với `severity: "critical"` (ngưỡng trong
`generate_warnings()`). `compute_risk_profile()` đọc thấy `has_critical_warning=True` nên gán
`risk_level="Critical"`, `priority="P1"` — **NGAY CẢ KHI** `action_code` vẫn chỉ là
`"SCHEDULE_REPLACEMENT"` (không phải `REPLACE_IMMEDIATELY`). Nói cách khác: SOH 82% → `priority
P1` + `action_code SCHEDULE_REPLACEMENT` cùng lúc — nếu BE lỡ suy luận "P1 thì phải
REPLACE_IMMEDIATELY" sẽ sai. Luôn đọc `action_code` để biết hành động cụ thể, đọc `priority` chỉ
để biết mức urgency gợi ý cho Priority Matrix — 2 field độc lập, không suy ra field kia từ field này.

### 8.4. `ResponseMetadata` — nhãn "extrapolation" (GH-91)

`temperature_domain_distance` + `is_temperature_ood`: khoảng cách tới cụm nhiệt độ train **gần
nhất của đúng bộ artifact đang chấm**. Giá trị hợp lệ `[-10,60]` nhưng xa cụm train **vẫn qua
range-guard §7.3** — cờ này báo cho BE biết đó là ngoại suy ngầm.

| Bộ | Cụm train |
|---|---|
| NASA / NMC | 4 / 24 / 44 °C |
| **LFP** | **30 °C** (Severson chạy 1 buồng duy nhất) |

> Dùng nhầm cụm NASA cho LFP thì 30 °C ra khoảng cách 6 °C và 35 °C ra 9 °C — vượt ngưỡng OOD,
> tức **gần như mọi đọc số ngoài trời của pin mặt trời đều bị gắn cờ sai**. Đã sửa (GH-67), và có
> **hai** đường sinh cờ này (risk profile + warning `TEMP_OOD`) — cả hai đọc chung một bảng.

### 8.5. Cờ `INSUFFICIENT_DISCHARGE` — `severity: "info"`, KHÔNG phải lỗi

Xuất hiện khi window **không có mẫu xả nào** (dòng chưa bao giờ dưới −0.1 A).

SOH nghĩa là *"xả ra được bao nhiêu Ah so với danh định"*, nên window không có mẫu xả thì con số
SOH chỉ là nội suy từ điện áp nghỉ. Đo trên dump IoT thật (pin đứng im 17 giờ, 0 mẫu xả): **mọi
window đều ra đúng 100.00%**, kể cả khi ép điện áp xuống 23.9 V / SOC 8%.

`severity="info"` là **cố ý** — `compute_risk_profile()` chỉ leo thang với `warning`/`critical`,
nên cờ này **không đổi** `health_stage` / `anomaly_status` / `recommended_action` / `risk_level`.
Pin vẫn được báo bình thường, **không sinh ticket**. Chỉ dùng nó để:
1. Đừng vẽ đồ thị suy giảm SOH từ các window có cờ này — chúng luôn ~100%
2. Đừng hoảng khi pin bắt đầu có tải thật rồi SOH tụt từ 100% xuống ~94% — đó là lần đầu **đo
   được thật**, không phải pin đột ngột hỏng

---

## 9. ⚠️ Giới hạn phải biết trước khi tích hợp

### 9.1. `rul_cycles_estimate` / `degradation_rate_per_cycle` / `cycles_to_maintenance` là **công thức**, không phải dự đoán

`compute_degradation_metrics()` chỉ tính được tốc độ suy giảm riêng cho từng pin khi window trải
`L >= 285` bước (~1 chu kỳ NASA). Production dùng **window=30** nên **luôn** rơi vào hằng số quần
thể. Nói cách khác, các field này là **hàm của `soh_percent`**, không phải dự đoán:

```
rul_cycles_estimate   = (soh_percent - 80) / degradation_rate
cycles_to_maintenance = (soh_percent - 85) / degradation_rate
```

Hằng số theo chemistry (GH-67 — trước đó dùng chung số của NASA cho cả LFP):

| | NASA / NMC | LFP |
|---|---|---|
| `degradation_rate_per_cycle` | 0.15 | **0.0087** |
| Pin mới (SOH 100%) → `rul_cycles_estimate` | 133 | **2298** |
| Pin mới → `cycles_to_maintenance` | 100 | **1724** |

> Trước khi sửa, một pack LFP 30 Ah **mới tinh** nhận `rul=133` / `cycles_to_maintenance=100` —
> BE dùng để lên lịch bảo trì sẽ gọi thợ sớm gấp **~17 lần**.

**BE PHẢI:**
- Coi `soh_percent`, `health_stage`, `risk.*` là nguồn authoritative.
- Hiểu 3 field trên là **ước lượng tuyến tính theo tốc độ trung bình quần thể** — chúng **không**
  bắt được "quả pin này đang xuống nhanh hơn bình thường". Hiển thị được cho khách, nhưng đừng
  gọi nó là "dự báo".
- ⚠️ Với LFP, `rul` ~2298 chu kỳ ≈ **6.3 năm** ở nhịp 1 chu kỳ/ngày. Đừng hiển thị độ chính xác
  cấp chu kỳ cho một con số có chân trời 6 năm.

### 9.2. Escalation/safety text có thể lặp gần-giống nhau

`escalation_conditions` gộp từ `rule_prescription` (v1) và `safety_gate` (v2) bằng dedup **so
khớp string tuyệt đối** — 2 tầng đôi khi tạo câu nói cùng ý nhưng khác dấu câu (vd "escalate to
P1 immediately." vs "escalate to P1 immediately" không dấu chấm) nên **không bị dedup**, xuất
hiện gần-trùng lặp trong list. Nếu BE hiển thị trực tiếp lên UI ticket, cân nhắc dedup thêm theo
similarity ở phía BE, hoặc chỉ hiển thị `n` item đầu.

### 9.3. ~~feedback loop REST-only~~ — ĐÃ CÓ `rpc SubmitFeedback`

Bản trước ghi là khoảng trống. Nay `.proto` **đã có** `rpc SubmitFeedback`, dùng chung hàm với
`POST /prescribe/feedback`, parity đã có test: id sai → `NOT_FOUND` (REST `404`), status sai →
`INVALID_ARGUMENT` (REST `422`). BE **không cần chạm FastAPI** cho bước này nữa.

> `prescription_id` **rỗng** khi `enrich=false` — đường rule-only không ghi history. Đánh đổi có
> chủ ý để giữ SLA hot-path.

### 9.4. Idempotency — ĐÃ CÓ

`Prescribe` gọi lại với **cùng input** trả kết quả đã cache (`cached=true`), không chạy lại MC
Dropout + LLM. Khoá cache gồm cả `n_series` / `chemistry` / `capacity_ah` — nếu không, một request
pack 8S LFP có thể bị trả về response đã cache của pin 1 cell NMC.

### 9.5. Causal degradation rate (GH-95) cần cùng `battery_id` xuyên suốt

`classify_anomaly()` có thể escalate 1 bậc severity (`Normal→Degrading→Failed`) dựa trên xu
hướng SOH của **chính pin đó qua các lần gọi trước** (`src/services/battery_history.py`, in-
memory, key theo `battery_id`, giữ tối đa 8 điểm gần nhất). Điều này **CHỈ hoạt động nếu BE luôn
gửi cùng `battery_id`** cho cùng 1 pin vật lý qua các lần gọi, và **cùng gửi `cycle_count`** (4
hoặc 6-cột đều được, miễn có). History **mất khi restart server** và **không share giữa nhiều
replica** (single-process, in-memory) — nếu deploy nhiều instance sau load balancer, causal-rate
escalation sẽ không nhất quán giữa các request của cùng 1 pin tùy request rơi vào replica nào.

### 9.6. Anomaly F1 trên window-shape đơn thuần chưa đạt target 0.80

`IsolationForest` trên feature 57-dim của 1 window đơn lẻ có AUC ~0.5 cho early/gradual
degradation (GH-70/GH-95) — đây là lý do GH-95 thêm causal rate (§9.5) làm tín hiệu bổ sung.
Đừng kỳ vọng `anomaly_score`/`anomaly_status` một mình phát hiện tốt degradation từ từ; chúng
mạnh hơn ở phát hiện **bất thường đột ngột trong 1 window** (sensor spike, nhiễu) hơn là trend
dài hạn.

### 9.7. ⚠️ Với pin LFP, SOH bão hoà 100% ở đoạn phẳng OCV — giới hạn VẬT LÝ

Đây là giới hạn quan trọng nhất khi chấm pin LFP, và **không phải lỗi model**.

LFP có đường OCV cực phẳng: điện áp gần như không đổi từ 20% đến 90% SOC. Ở vùng đó **không tồn
tại thông tin dung lượng** để bất kỳ model nào đọc. Đo trên `soh_mamba_v2.0-lfp.pth`:

| Điện áp pack (8S) | V/cell | SOH trả về (cycle 100 → 2300) |
|---|---|---|
| 26.6 V | 3.33 V | 100.0% → 100.0% |
| 25.0 V | 3.12 V | 100.0% → 100.0% |
| 24.0 V | 3.00 V | 100.0% → 98.6% |
| 23.2 V | 2.90 V | 100.0% → 90.3% |
| 22.8 V | 2.85 V | 95.3% → 85.1% |

Model **có** phân biệt — nhưng chỉ dưới ~**3.05 V/cell**, tức "đầu gối" cuối đoạn xả. Ở 26.4 V,
ép sụt 0.96 V trong 87 giây (dốc bất thường) vẫn ra **100.0%**.

**Hệ quả cho BE:** pin đang ở dải nghỉ/sạc bình thường (3.2–3.3 V/cell) sẽ **luôn** ra ~100% SOH.
Đó là câu trả lời trung thực nhất có thể ở điểm vận hành đó, **không phải** bằng chứng pin hoàn
hảo. Muốn có số SOH thật thì cần window rơi vào đoạn xả sâu.

---

## 10. Prescription Pipeline (rule → enrich → agentic → safety gate)

```
run_prescription(readings, battery_id, enrich, agentic, pack_config, ...)
  1. run_inference()                     → prediction/anomaly/risk/warnings (LUÔN chạy, kể cả enrich=false)
  2. build_rule_prescription()           → baseline rule-based (<100ms, không mạng, LUÔN chạy)
  3. NẾU enrich=true:
       agentic=false → RAG template query (2 query cố định) → LLM sinh prescription
       agentic=true  → LLM sinh 3-5 query từ diagnosis statement → multi-query RAG (dedup theo relevance)
     LLM fail bất kỳ bước nào → fallback về rule-based, KHÔNG lỗi ra ngoài
  4. apply_safety_gate()                 → LUÔN chạy (cả 2 path):
       - P1/REPLACE_IMMEDIATELY luôn set human_verification_required=true
       - Cảnh báo thermal/electrical critical → inject LOTO/thermal step nếu thiếu trong action_steps
       - PPE bắt buộc theo hazard (union vào ppe_required, kể cả path rule-based)
       - Blocklist forbidden-action CHỈ áp dụng cho text LLM sinh (llm_generated=true) — rule text luôn an toàn
  4b. LLM-as-judge (optional, env SAFETY_LLM_JUDGE=1) — chỉ chạy khi enrich=true và chưa bị block
  4c. Nếu blocked → discard LLM output, fallback rule-based, re-run gate 1 lần, ghi audit log
  5. NẾU enrich=true → lưu history (best-effort) → prescription_id (uuid4) cho feedback loop
  6. return PrescribeResponse dict
```

**`enrich=false` là default và là path BE nên dùng cho luồng auto-ticket event-driven**
(`BatteryAnomalyDetectedEvent` → `Prescribe`) — rule-based, cùng hot-path budget với `Predict`
(benchmark thật `enrich=false`: avg 54.1ms, p95 72.4ms — artifacts v1.6, `n=50`). `enrich=true`
(RAG+LLM, có thể mất vài giây) chỉ dùng cho tương tác thủ công (vd nút "AI gợi ý chi tiết" trên
UI kỹ thuật viên), KHÔNG thuộc luồng event-driven.

**LLM provider chain:** `deepseek` → `gemini` → `anthropic` (fallback tuần tự nếu key trước lỗi/thiếu),
`llm_provider: "none"` khi không có key nào hoặc path rule-based. Xem `docs/adr/0003-llm-provider-chain.md`.

---

## 11. Error handling & mã lỗi

| Tình huống | gRPC | REST (tham khảo, không phải path BE nên dùng) |
|---|---|---|
| Input sai (window≠30, feature count sai, out-of-range, NaN) | `INVALID_ARGUMENT` (message = Pydantic validation error, dùng chung validator với REST) | `422` |
| Lỗi pipeline nội bộ (exception trong `run_inference`/`run_prescription`) | `INTERNAL` | `500` |
| Server chưa sẵn sàng | `UNAVAILABLE` | connection refused |
| Stream lỗi giữa chừng (`PredictStream`) | Không có per-message error — window lỗi thứ k → client đã nhận đủ k-1 response trước đó, rồi cả stream abort bằng `RpcException(INVALID_ARGUMENT)`. Client nên catch → reconnect → gửi tiếp từ window k+1. | N/A |
| Có kết quả nhưng "mềm" (chưa reject) | Không có — validate chỉ reject range/shape/NaN; giá trị hợp lệ nhưng bất thường (vd nhiệt độ OOD) trả về BÌNH THƯỜNG kèm cờ cảnh báo trong response (§8.4), không phải lỗi | (giống) |

Không có khái niệm "200 OK kèm lỗi trong body" ở gRPC (khác REST's `CommonResponse.isSuccess=false`)
— input sai luôn là `INVALID_ARGUMENT`, BE nên catch theo status code chuẩn gRPC, không parse message
để suy lỗi.

---

## 12. Latency benchmark hiện tại

Máy dev CPU, dummy weights trừ khi ghi chú khác (`scripts/benchmark_grpc.py`):

| RPC | avg | p95 | Ghi chú |
|---|---|---|---|
| `Predict` unary | ~114ms | — | dummy weights |
| `PredictStream` (per window) | ~116ms | — | không tốn thêm so với unary |
| `Prescribe` (`enrich=false`) | ~116ms (dummy) / **54.1ms (real weights v1.6, n=50)** | 72.4ms (real) | Đạt cả SLA batch <500ms lẫn P1 hot-path <100ms |
| `Predict` — bộ **LFP** (real weights, n=30) | 75.5ms | **80.0ms** | in-process, có tranh GIL |
| `Prescribe` — bộ **LFP** (`enrich=false`, n=30) | 77.2ms | **82.4ms** | như trên |
| Transport overhead (gRPC thêm so với gọi hàm trực tiếp) | ~1–28ms | — | budget <50ms — PASS |

SLA `<100ms` (P1) enforce trên môi trường deploy với weights thật; số dev CPU chỉ tham khảo
tương đối. Chạy lại: `python scripts/benchmark_grpc.py --real-weights`.

---

## 13. Setup client .NET (C#)

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

```csharp
using AiModule.V1;
using Grpc.Net.Client;

// Channel tạo 1 lần, tái dùng (DI singleton) — KHÔNG tạo per-request
var channel = GrpcChannel.ForAddress("http://ai-module:50051");   // insecure, nội bộ docker network
var client  = new AiService.AiServiceClient(channel);

var request = new PrescribeRequest { BatteryId = "B0005", Enrich = false };
foreach (var row in windowRows)              // 30 hàng, mỗi hàng 4 hoặc 6 double
{
    var reading = new Reading();
    reading.Values.AddRange(row);
    request.Readings.Add(reading);
}
// Pack LFP 8S 24V 30Ah (pin thật của dự án):
request.PackConfig = new PackConfig { NSeries = 8, Chemistry = "LFP", CapacityAh = 30.0 };
// Bỏ Chemistry => rơi về bộ NASA: SOH lệch tới 60 điểm, trần dòng tụt 136A -> 75A

var response = await client.PrescribeAsync(request);
// response.Prediction.SohPercent, response.Prediction.HealthStage,
// response.Risk.Priority ("P1".."P3"|"None"), response.ActionCode(?) -- xem §6.1 cho field đúng
// response.ActionSteps, response.PpeRequired, response.HumanVerificationRequired
```

Streaming (`PredictStream`):

```csharp
using var call = client.PredictStream();
foreach (var window in windows)
    await call.RequestStream.WriteAsync(window);
await call.RequestStream.CompleteAsync();

await foreach (var response in call.ResponseStream.ReadAllAsync())
    Console.WriteLine($"{response.BatteryId}: {response.SohPercent}%");
```

Chạy server local để test:

```bash
python -m src.grpc_server              # gRPC :50051 (cần artifacts thật trong models/weights/)
python scripts/grpc_client_demo.py     # demo các RPC (thay Swagger)
python scripts/e2e_full_test.py        # test đầy đủ cả 2 bộ artifact + đo latency
python scripts/benchmark_grpc.py --real-weights
```

---

## 14. File tham khảo

| File | Nội dung |
|---|---|
| `protos/ai_service.proto` | Contract nguồn — đọc trực tiếp khi cần field-level detail |
| `docs/examples/grpc-payloads.json` | Ví dụ request/response đầy đủ, đã verify bằng code thật |
| `docs/grpc-integration-be.md` | Hướng dẫn client .NET gốc (một phần đã gộp vào §13 tài liệu này) |
| `docs/ai-be-integration.md` | Chi tiết luồng `BatteryAnomalyDetectedEvent` → `Prescribe` → auto-ticket |
| `docs/adr/0002-split-rebalance-b0047.md` | Lý do đổi split GH-88 |
| `docs/adr/0003-llm-provider-chain.md` | Thứ tự fallback LLM provider |
| `.claude/rules/tech/ai.md` | Rule bắt buộc cho AI dev (model spec, versioning) |
| `.claude/rules/design.md` | Priority Matrix (Impact × Urgency) — nơi BE tính Priority ticket thật |

---

> **Repo:** https://github.com/GSU26SE55/ai-module
