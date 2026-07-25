 # AI Module — Tài liệu tổng quan (gRPC-first, cho BE tích hợp)

> **Dự án:** Solar Lithium-ion Battery Maintenance Management System — GSU26SE55
> **Cập nhật:** 2026-07-22 (thay bản cũ 2026-06-21 — đã lệch nhiều version/field)
> **Đối tượng đọc:** BE dev (.NET) cần dựng gateway gọi sang AI module.
> **Phạm vi:** Tài liệu này tập trung vào **gRPC (`aimodule.v1.AiService`, port 50051)** —
> đây là transport BE dùng thật trong production (xem [[grpc-is-production-transport]]).
> REST (`FastAPI`, port 8000) vẫn tồn tại và trả **cùng payload** (parity test field-by-field),
> nhưng chỉ dùng cho dev/Swagger/local testing — **không phải đường tích hợp BE nên đi**,
> ngoại trừ 1 endpoint chưa có ở gRPC (`POST /prescribe/feedback` — xem §11.4).

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
| Mamba SOH (production, L=30) | **v1.6** (GH-88 split rebalance) | `models/weights/soh_mamba_v1.6.pth` |
| MinMaxScaler (6-feature) | v1.3 | `models/weights/scaler.pkl` |
| Feature StandardScaler (57-dim) | v1.5 | `models/weights/feature_scaler.pkl` |
| IsolationForest | v1.6 (theo Mamba) | `models/weights/isolation_forest_v1.6.pkl` |
| Mamba SOH Long (L=4096) | v2.2 (feature ablation 6→4 base) | `models/weights/soh_mamba_long_v2.2.pth` |
| RUL Predictor (cycle-axis) | v1.0 | `models/weights/soh_mamba_rul_v1.0.pth` |
| gRPC contract | `protos/ai_service.proto` (GH-39, đang ở field 91 = GH-91) | `src/grpc_gen/` (generated, committed) |
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

NASA Ames Battery Dataset (18650 Li-ion, 34 cells, nominal capacity 2.0 Ah).

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

---

## 5. Model Artifacts

| File | Dùng cho | Commit vào Git |
|---|---|---|
| `scaler.pkl` | MinMaxScaler 6-feat | ✅ |
| `feature_scaler.pkl` | StandardScaler 57-dim | ✅ |
| `soh_mamba_v1.6.pth` | Production Mamba (L=30) | ✅ |
| `isolation_forest_v1.6.pkl` | IsolationForest | ✅ |
| `scaler_long.pkl`, `feature_scaler_long.pkl`, `soh_mamba_long_v2.2.pth` | Long model (L=4096, ngoài scope gRPC) | ✅ |
| `feature_scaler_rul.pkl`, `soh_mamba_rul_v1.0.pth` | RUL Predictor (ngoài scope gRPC) | ✅ |

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
}
```

Cả 4 RPC chạy trong **cùng process** với REST (`src/grpc_server.py`, `python -m src.grpc_server`,
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

Toàn bộ field + comment gốc: xem `protos/ai_service.proto` trực tiếp (đã inline giải thích từng
GH ticket ngay trong file — đọc file đó khi cần chi tiết field-level thay vì tài liệu này).

### 6.2. Ví dụ JSON request/response

Xem file **`docs/examples/grpc-payloads.json`** — 3 kịch bản đầy đủ (Healthy/Normal,
Maintenance-Required/Warning, Critical-EOL trên pack LFP 4S) cho cả `Predict` và `Prescribe`,
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

### 7.2. `PackConfig` — pin nhiều cell (GH-65/67)

```
voltage_cell = voltage_pack / n_series        (áp dụng TRƯỚC scaler + TRƯỚC warning threshold)
current_equiv = current_pack × (2.0 / capacity_ah)   (chỉ khi capacity_ah được set)
```

- `n_series` (mặc định 1 = single cell, legacy behavior). Ví dụ 12V ≈ 3S NMC, 12.8V ≈ 4S LFP.
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

`temperature_domain_distance` + `is_temperature_ood`: model chỉ từng train ở đúng 3 mốc nhiệt độ
buồng NASA (4°C, 24°C, 44°C). Một giá trị PHÙ HỢP khoảng hợp lệ `[-10,60]` nhưng xa cả 3 mốc này
(vd 15°C) **vẫn qua được range-guard §7.3** nhưng là extrapolation ngầm — field này bật cờ
riêng để BE biết SOH lúc đó kém tin cậy hơn dù không có lỗi nào được raise.

---

## 9. ⚠️ Giới hạn phải biết trước khi tích hợp

### 9.1. `rul_cycles_estimate` / `degradation_rate_per_cycle` / `cycles_to_maintenance` / `soh_trajectory` — KHÔNG đáng tin ở window=30 (phát hiện khi viết tài liệu này, verify bằng code thật)

`compute_degradation_metrics()` chia window thành `n_seg = max(2, min(10, L // 285))` đoạn
(`285` = độ dài trung bình 1 chu kỳ NASA thật). Với **window=30 (chuẩn production)**, `30 // 285
= 0` → **luôn luôn đúng 2 đoạn**, bất kể window có thật sự trải dài nhiều chu kỳ hay không. Slope
điện áp giữa 2 đoạn 15-bước này bị nhân với hệ số `285/15 = 19` rồi đổi sang `%SOH/cycle` (×37.5)
để suy ra "tốc độ suy giảm mỗi chu kỳ" — chỉ cần độ dốc điện áp trong window **lớn hơn ~0.003V**
(rất dễ xảy ra ngay cả ở pin khỏe mạnh, discharge bình thường) là kết quả bị **clip trần ở giá
trị tối đa 2.0 %SOH/cycle**.

Hệ quả verify thực tế trên 1 kịch bản pin **93.3% SOH, `health_stage="Healthy"`, không cảnh báo
nào**: response vẫn trả `rul_cycles_estimate: 6`, `cycles_to_maintenance: 4`,
`degradation_rate_per_cycle: 2.0` — đọc qua tưởng pin sắp hỏng trong 6 chu kỳ, dù thực tế
`soh_percent` + `health_stage` + `risk` đều nói pin khỏe bình thường.

**BE PHẢI:**
- Coi `soh_percent`, `health_stage`, `risk.*` là nguồn authoritative.
- Coi `rul_cycles_estimate`/`degradation_rate_per_cycle`/`cycles_to_maintenance`/
  `soh_trajectory` là **thử nghiệm/không đáng tin cho window=30** — không hiển thị trực tiếp cho
  Customer như 1 con số dự báo chính xác (vd "pin sẽ hỏng sau N chu kỳ") nếu chưa có cải thiện
  từ phía AI team cho trường hợp 1-window request. Các field này chỉ có ý nghĩa khi window thật
  sự trải dài ≥ nhiều trăm timestep (nhiều chu kỳ thật) — không phải trường hợp chuẩn 30-timestep
  mà production đang gửi.

### 9.2. Escalation/safety text có thể lặp gần-giống nhau

`escalation_conditions` gộp từ `rule_prescription` (v1) và `safety_gate` (v2) bằng dedup **so
khớp string tuyệt đối** — 2 tầng đôi khi tạo câu nói cùng ý nhưng khác dấu câu (vd "escalate to
P1 immediately." vs "escalate to P1 immediately" không dấu chấm) nên **không bị dedup**, xuất
hiện gần-trùng lặp trong list. Nếu BE hiển thị trực tiếp lên UI ticket, cân nhắc dedup thêm theo
similarity ở phía BE, hoặc chỉ hiển thị `n` item đầu.

### 9.3. `prescription_id` / feedback loop — REST-only, chưa có ở gRPC

`PrescribeResponse.prescription_id` (GH-83, uuid4, chỉ set khi `enrich=true` và ghi history
thành công) dùng để gọi **`POST /prescribe/feedback`** — endpoint này **CHỈ có ở REST**, `.proto`
hiện KHÔNG có RPC tương ứng. Nếu BE cần vòng feedback (accepted/edited/rejected) mà muốn tránh
hoàn toàn FastAPI, đây là khoảng trống cần 1 ticket bên AI team bổ sung RPC `SubmitFeedback` —
hiện tại buộc phải gọi REST cho riêng bước này.

### 9.4. Idempotency — chưa có (GH-84)

Gọi `Prescribe` nhiều lần với cùng input (event trùng/burst, retry MassTransit) sẽ chạy MC
Dropout + rule/LLM lại từ đầu mỗi lần — không có cache/dedup phía AI. BE nên tự dedup phía
consumer (theo event ID của chính BE) trong lúc chờ GH-84.

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
// Đa cell: request.PackConfig = new PackConfig { NSeries = 4, Chemistry = "LFP", CapacityAh = 2.5 };

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
python scripts/grpc_client_demo.py     # demo đủ 4 RPC (thay Swagger)
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
