# gRPC Integration Guide — BE (.NET) gọi AI Module

> GH-42 · Contract: `protos/ai_service.proto` (single source of truth, repo `ai-module`)
> Chuỗi liên quan: #39 (contract) → #40 (server unary) → #41 (streaming) → #42 (doc này)

AI module expose **2 transport song song** trên cùng pipeline:

| Transport | Port | Dùng khi |
|-----------|------|----------|
| REST (FastAPI) | 8000 | tích hợp hiện tại, Swagger, đơn giản |
| gRPC (`AiService`) | 50051 (env `GRPC_PORT`) | latency thấp hơn, streaming sensor real-time |

Cả hai trả **cùng payload** (đã có parity test field-by-field) — BE migrate dần không cần remap.

**Flow khuyến nghị (GH-87):** gọi **`Prescribe` duy nhất** cho use-case tạo/enrich ticket — `Predict`
chạy nội bộ trong `Prescribe` nên response đã có đủ block `prediction`/`anomaly`/`risk` (bao gồm
uncertainty GH-86: `health_stage`, `stage_probabilities`, `stage_confidence`, `is_borderline`,
`soh_confidence`, `soh_std`). Gọi riêng `Predict`/`PredictStream` chỉ dành cho dashboard giám sát
real-time (không cần prescription text/RAG). **Không** gọi cả `Predict` lẫn `Prescribe` trên cùng
một windows readings để lấy context — mỗi lần gọi chạy MC Dropout riêng nên 2 response có thể lệch
nhau (stage flip gần ngưỡng); dùng nested block trong `Prescribe` làm nguồn duy nhất.

---

## 1. Lấy proto & gen C# client

Copy `protos/ai_service.proto` từ repo `ai-module` vào project BE (giữ nguyên file — mọi thay đổi contract phải qua repo ai-module trước).

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

Build xong sẽ có sẵn namespace **`AiModule.V1`** (khai báo `csharp_namespace` trong proto): `AiService.AiServiceClient`, `PredictRequest`, `PredictResponse`, …

## 2. Gọi unary (Predict / Prescribe / Health)

```csharp
using AiModule.V1;
using Grpc.Net.Client;

// Channel tạo 1 lần, tái dùng (DI singleton) — KHÔNG tạo per-request
var channel = GrpcChannel.ForAddress("http://ai-module:50051");   // insecure, nội bộ docker network
var client  = new AiService.AiServiceClient(channel);

// Health
var health = await client.HealthAsync(new HealthRequest());

// Predict — 30 timesteps × 4 features [voltage, current, temperature, time]
var request = new PredictRequest { BatteryId = "B0005" };
foreach (var row in windowRows)   // 30 hàng, mỗi hàng 4 double
{
    var reading = new Reading();
    reading.Values.AddRange(row); // [3.72, 1.5, 25.3, 120.0]
    request.Readings.Add(reading);
}
var prediction = await client.PredictAsync(request);
// prediction.SohPercent, prediction.Classification ("Normal"|"Degrading"|"Failed"),
// prediction.Confidence, prediction.Risk.Priority ("P1".."P3"|"None"), ...
```

## 3. Streaming (PredictStream — sensor real-time)

```csharp
using var call = client.PredictStream();

// Gửi N windows — mỗi request là 1 window 30×4 ĐẦY ĐỦ (server không tự tích lũy)
foreach (var window in windows)
    await call.RequestStream.WriteAsync(window);
await call.RequestStream.CompleteAsync();

// Nhận N responses, ĐÚNG THỨ TỰ request (match bằng BatteryId nếu cần)
await foreach (var response in call.ResponseStream.ReadAllAsync())
    Console.WriteLine($"{response.BatteryId}: {response.SohPercent}%");
```

## 4. Semantics BẮT BUỘC phải biết

| # | Semantics | Chi tiết |
|---|-----------|----------|
| 1 | **Payload 4 features** | Sau GH-25 ablation: `[voltage, current, temperature, time]` (bỏ current_load/voltage_load). Gửi 6 features → `INVALID_ARGUMENT`. Legacy 3 features chỉ dùng được với artifacts cũ. |
| 2 | **Window = 30 timesteps** | Khác 30 → `INVALID_ARGUMENT` kèm message từ validator (cùng rule với REST 422). |
| 3 | **Stream chết theo message lỗi** | gRPC bidi không có per-message error: window lỗi ở vị trí k → client đã nhận k−1 responses, rồi stream kết thúc bằng `RpcException(INVALID_ARGUMENT)`. Client nên catch → reconnect → gửi tiếp từ window k+1. |
| 4 | **Error codes** | Input sai → `INVALID_ARGUMENT`; lỗi pipeline → `INTERNAL`; server chưa chạy → `UNAVAILABLE`. Không có 200-with-error như REST wrapper. |
| 5 | **Insecure channel — nội bộ only** | Port 50051 không TLS/auth (scope capstone). KHÔNG expose ra ngoài docker network; dùng `http://` (không phải `https://`) trong `GrpcChannel.ForAddress`. |
| 6 | **In-order, backpressure sẵn** | Responses đúng thứ tự requests; HTTP/2 flow control tự điều tiết — BE không cần rate-limit thủ công ở mức thấp. |
| 8 | **`VerifyTicket` — xem §7** | RPC thứ 5 (GH-693). Rule-based, deterministic, không gọi mạng. AI chỉ gắn nhãn, KHÔNG tự chặn ticket. |
| 7 | **Prescribe `enrich=false` mặc định** | Rule-based, hot-path (<100ms SLA). `enrich=true` chạy RAG+LLM (chậm, có thể vài giây) — chỉ dùng ngoài P1 hot-path. |

## 5. Chạy local để test

```bash
# Trong repo ai-module (cần artifacts trong models/weights/ — xem lưu ý bên dưới)
python -m src.grpc_server              # gRPC :50051
uvicorn main:app --port 8000           # REST :8000 (song song, tùy chọn)

# Demo các RPC (thay Swagger)
python scripts/grpc_client_demo.py

# Benchmark
python scripts/benchmark_grpc.py                 # dummy weights
python scripts/benchmark_grpc.py --real-weights  # artifacts thật + enforce SLA <100ms
```

> ⚠️ **Trạng thái artifacts (2026-07-02):** config đang trỏ model v1.3 / long v2.2 (sau feature ablation GH-25) nhưng artifacts chưa được commit — retrain trên Kaggle đang chạy (#25). Trước khi artifacts về, server chỉ chạy được ở test mode (dummy weights). Benchmark số thật + smoke 2 transport sẽ chạy lại khi retrain xong.

## 6. Benchmark tham khảo (máy dev CPU, dummy weights, 2026-07-02)

| RPC | avg | ghi chú |
|-----|-----|---------|
| `run_inference` (direct, không gRPC) | ~86–110ms | MC Dropout ×20 chiếm gần hết |
| Predict unary | ~114ms | |
| PredictStream (per window) | ~116ms | ratio 1.05 vs unary — stream không thêm chi phí |
| Prescribe (rule path) | ~116ms | |
| **Transport overhead (phần gRPC thêm)** | **~1–28ms** | budget <50ms, PASS |

SLA <100ms enforce trên môi trường deploy với weights thật (tiền lệ GH-10) — số dev CPU chỉ để tham khảo tương đối.

---

## 7. `VerifyTicket` — chấm điểm ticket do khách tự tạo (GH-693)

> RPC thứ **5**, gộp vào `dev` ngày 2026-08-05. TicketService đang gọi thật.
> Tương đương REST: `POST /verify-ticket/`.

### 7.1. Mục đích và giới hạn

AI **gắn nhãn** ticket khách tự khai là hợp lệ hay đáng nghi, và dò xem có trùng ticket
đang mở nào không. **AI KHÔNG tự chặn ticket** — quyết định cuối cùng là của Manager
(human-in-the-loop). Nhãn chỉ để xếp thứ tự xử lý và cảnh báo trùng lặp.

Toàn bộ chấm điểm là **rule-based, deterministic, không gọi mạng** — cùng input luôn ra
cùng output, không phụ thuộc LLM và không tốn chi phí API.

### 7.2. Signature

```protobuf
rpc VerifyTicket(VerifyTicketRequest) returns (VerifyTicketResponse);
```

**Request**

| Field | Kiểu | Bắt buộc | Ghi chú |
|-------|------|:---:|---------|
| `title` | string | ✅ | Tiêu đề khách nhập |
| `description` | string | ✅ | Mô tả khách nhập — nguồn tín hiệu chính |
| `detected_at` | string | — | ISO UTC. `""` nếu không có |
| `category` | int32 | ✅ | **`TicketCategoryEnum` của BE** — xem §7.5 |
| `sensor_snapshot` | `TicketSensorSnapshot` | — | Số đo pin tại thời điểm tạo ticket |
| `has_sensor_snapshot` | bool | ✅ | `false` → bỏ qua hoàn toàn phần đối chiếu sensor |
| `candidates[]` | `DuplicateCandidate` | — | Ticket đang mở **cùng pin** để so trùng |

```protobuf
message TicketSensorSnapshot {
  double soh_percent = 1;  double voltage = 2;  double current = 3;
  double temperature = 4;  double soc_percent = 5;
  bool has_active_alert = 6;   // pin có alert đang mở tại thời điểm đó
}
message DuplicateCandidate {
  string ticket_id = 1;  string description = 2;
  int32 category = 3;          // cùng category → nghi trùng cao hơn
}
```

**Response**

| Field | Kiểu | Ghi chú |
|-------|------|---------|
| `verdict` | string | `"legitimate"` \| `"suspicious"` |
| `score` | double | `[0..1]` — độ hợp lệ, `1` = chắc chắn thật |
| `reason` | string | **Tiếng Việt**, viết cho Manager đọc trực tiếp |
| `duplicate_of_ticket_id` | string | `""` nếu không nghi trùng |
| `duplicate_score` | double | `[0..1]` — độ tương đồng cao nhất với `candidates` |
| `duplicate_reason` | string | Lý do nghi trùng |

### 7.3. Cách tính điểm (để BE giải thích được cho Manager)

Điểm khởi đầu **0.5** (trung tính), rồi cộng/trừ:

| Tín hiệu | Ảnh hưởng |
|---|---|
| Mô tả quá ngắn | **−0.30** |
| Mô tả đủ chi tiết | **+0.15** |
| Tiêu đề rỗng hoặc trùng y hệt mô tả | **−0.10** |
| Có từ khoá bất thường (nóng, phồng, khói…) | **+0.20** |
| Spam rõ rệt (1 ký tự lặp, toàn số) | **−0.40** |
| **Sensor xác nhận có bất thường thật** | **+0.30** |
| Sensor bình thường, không có gì bất thường | **−0.10** |

Kết quả clip về `[0, 1]`. **`score >= 0.5` → `legitimate`, ngược lại `suspicious`.**
Dò trùng dùng Jaccard trên token đã bỏ dấu; **`duplicate_score >= 0.45`** thì báo trùng,
cùng `category` được cộng thêm trọng số.

> Trọng số lớn nhất là **sensor** (±0.30/0.40 cả cụm). Gửi `has_sensor_snapshot=true` kèm
> số đo thật làm kết quả tin cậy hơn hẳn so với chỉ chấm chữ.

### 7.4. Mapping sang `TicketVerifyStatusEnum`

| Kết quả AI | `ai_verify_status` |
|---|---|
| `verdict = "legitimate"` | `2` — Legitimate |
| `verdict = "suspicious"` | `3` — Suspicious |
| RPC lỗi bất kỳ (`UNAVAILABLE`, `UNIMPLEMENTED`, timeout…) | `4` — Skipped |

BE **không được** để lỗi verify chặn việc tạo ticket — bắt lỗi, set `Skipped`, ghi log, ticket
vẫn tạo bình thường.

### 7.5. ⚠️ `category` phải đồng bộ hai phía

`category` là `int32` thô, **không** có enum trong proto. AI dùng nó để so trùng
(cùng category → nghi trùng cao hơn). Nếu BE đổi thứ tự/giá trị `TicketCategoryEnum` mà
AI không đổi theo, **không có lỗi nào được raise** — chỉ là kết quả dò trùng kém đi âm thầm.

**Quy tắc:** đổi `TicketCategoryEnum` phải báo AI team và cập nhật cùng lúc.

### 7.6. Ticket tồn đọng không tự verify lại

`TicketVerifyRunner` bỏ qua ticket có `AiVerifyStatus != Pending`, và consumer chỉ chạy trên
`TicketCreatedEvent`. Muốn xử lý số tồn phải gọi tay:

```
POST /api/admin/tickets/{id:guid}/re-verify     [Authorize(Roles = "Manager")]
```

Chỉ nhận ticket `Origin == ManualByCustomer` **và** status hiện tại là `Skipped`/`Pending`.
→ **Ticket auto-tạo từ alert KHÔNG re-verify được.**

---

## 8. `SubmitFeedback` — KTV phản hồi về prescription (GH-83)

```protobuf
rpc SubmitFeedback(SubmitFeedbackRequest) returns (SubmitFeedbackResponse);
```

Mirror của `POST /prescribe/feedback`. Gọi **sau khi kỹ thuật viên xử lý xong** một
prescription mà AI đã trả.

### Request

| Field | Bắt buộc | Ghi chú |
|---|---|---|
| `prescription_id` | ✅ | lấy từ `PrescribeResponse.prescription_id` — chỉ có khi gọi `Prescribe` với `enrich = true` |
| `status` | ✅ | đúng 1 trong 3: `"accepted"` / `"edited"` / `"rejected"`. Giá trị khác → `INVALID_ARGUMENT` |
| `edited_steps` | — | các bước sau khi KTV sửa; để rỗng nếu `status != "edited"` |
| `note` | — | ghi chú tự do, để `""` nếu không có |

### Response

`success = true`. Không có nhánh trả `false` — `prescription_id` không tồn tại thì RPC
trả **`NOT_FOUND`** (tương ứng 404 bên REST), không phải `success = false`.

### Vì sao nên gửi

Prescription được đánh `"accepted"` sẽ thành **few-shot context** cho các ca tương tự
sau này. Không gửi feedback thì AI không có đường học từ thực tế hiện trường — chất
lượng prescription đứng yên ở mức rule + RAG ban đầu.

### Lưu ý

- `prescription_id` **rỗng** khi `enrich = false` (đường rule-only). Không có id thì
  không gửi feedback được — đây là đánh đổi có chủ ý: đường rule-only tối ưu cho SLA
  auto-ticket, không ghi lịch sử.
- Idempotent theo `prescription_id`: gọi lại sẽ **ghi đè** feedback cũ, không cộng dồn.

---

## 9. `PredictLong` — SOH từ chuỗi dài (GH-10)

```protobuf
rpc PredictLong(PredictLongRequest) returns (PredictLongResponse);
```

Mirror của `POST /predict/long`. Nhận **31..4096** timestep thay vì đúng 30, chạy bằng
model long-sequence (attention pooling) — **một artifact khác hẳn** model window=30.

### Khác `Predict` ở ba điểm — đọc trước khi dùng

| | `Predict` | `PredictLong` |
|---|---|---|
| Độ dài `readings` | đúng 30 | 31..4096 |
| MC-dropout | có → `soh_confidence`, `soh_std`, `health_stage` | **không có** |
| IsolationForest | có → `anomaly`, `risk`, `warnings` | **không có** |
| Artifact | `model_version` | `model_version` = `long_model_version` (khác hẳn, **đừng so sánh 2 giá trị này**) |

Bỏ anomaly là **có chủ ý**: IsolationForest được fit trên phân bố feature của window=30;
chấm một chuỗi 4096 bước bằng nó là ngoài phân bố — ra con số trông hợp lệ nhưng vô nghĩa.

### Request

| Field | Bắt buộc | Ghi chú |
|---|---|---|
| `battery_id` | ✅ | |
| `readings` | ✅ | 31..4096 hàng. Mỗi hàng 4 cột `[voltage, current, temperature, time]` hoặc legacy 3 cột. `cycle_count`/`soc_percent` **không dùng** ở đường này (model tự sinh IC-curve + discharge-progress) — gửi thừa cũng bị bỏ, nên **không có bẫy `soc_mode`** ở đây |
| `pack_config` | — | `n_series` chia voltage, `capacity_ah` quy đổi C-rate — **giống hệt `Predict`**. `chemistry` KHÔNG chọn artifact ở đường này: model long chỉ có một bộ (NASA), gửi `"LFP"` vẫn dùng bộ đó |

### Response

| Field | Ghi chú |
|---|---|
| `soh_percent` | [0, 100] |
| `seq_len` | số timestep thực nhận |
| `device` | `"cpu"` / `"cuda"` — đường long dùng GPU nếu có |
| `inference_ms` | |
| `model_version` | `LONG_MODEL_VERSION` |

### Lưu ý

- **KHÔNG thay `Prescribe` ở hot-path tạo ticket.** Luồng đó vẫn phải dùng `Prescribe`
  (xem đầu file) — `PredictLong` không trả risk/anomaly nên không đủ để sinh ticket.
  Dùng cho phân tích/biểu đồ lịch sử dài.
- Gửi ≤ 30 hàng → **`INVALID_ARGUMENT`** kèm gợi ý dùng `Predict`. Cố tình không im lặng
  nhận, vì model long chưa từng thấy chuỗi ngắn như vậy.
- Range guard giống hệt `Predict` (voltage per-cell, current theo C-rate, temperature,
  soc) — cùng payload sai thì hai đường từ chối như nhau.
- Model nạp **lười** ở lần gọi đầu, không phải lúc boot ⇒ `Health.long_loaded = false`
  chỉ nghĩa là "chưa ai gọi", KHÔNG phải "thiếu artifact". Request đầu tiên vì vậy chậm
  hơn hẳn các request sau.

---

## 10. `SubmitClassificationFeedback` — KTV chấm lại phân loại của AI (F4)

```protobuf
rpc SubmitClassificationFeedback(ClassificationFeedbackRequest)
    returns (ClassificationFeedbackResponse);
```

Mirror của `POST /predict/feedback`. Khác `SubmitFeedback` ở §8: cái kia phản hồi về
**prescription** (nội dung hướng dẫn), cái này phản hồi về **nhãn phân loại**
(Normal/Degrading/Failed) mà nhánh anomaly đã đưa ra.

BE đã lưu `staff_feedback` vào `anomaly_classifications` từ lâu nhưng chưa có đường gửi
ngược về AI ⇒ vòng học đóng lại ở phía BE, AI không bao giờ biết mình phân loại sai.

### Request

| Field | Bắt buộc | Ghi chú |
|---|---|---|
| `battery_id` | ✅ | |
| `classification` | ✅ | nhãn AI **đã** đưa ra: `"Normal"` / `"Degrading"` / `"Failed"`. **Không phải nhãn đúng** — `verdict` mới nói AI đúng hay sai. Giá trị lạ → `INVALID_ARGUMENT` |
| `verdict` | ✅ | `"correct"` / `"false_positive"` / `"false_negative"` — khớp `StaffFeedbackEnum` của BE (1/2/3). **BE map số sang chuỗi trước khi gửi**, để hợp đồng không phụ thuộc thứ tự enum của riêng bên nào |
| `model_version` | — | version đã sinh ra nhãn đó; `""` nếu không rõ |
| `classified_at` | — | ISO UTC lúc phân loại; `""` nếu không có |
| `note` | — | |

### Response

Trả bộ đếm chạy hiện tại để BE thấy đã ghi nhận và theo dõi được precision/recall thô:
`total`, `correct`, `false_positive`, `false_negative`, `precision`, `recall`.

⚠️ **Phải đọc `has_precision` / `has_recall` trước khi đọc `precision` / `recall`.**
proto3 scalar không nullable nên `0.0` một mình là mơ hồ đúng ở chỗ nguy hiểm nhất:
không phân biệt được "chưa ai chấm" với "đã chấm và sai hết". `has_* = false` ⇒ bỏ qua
giá trị, đừng hiển thị 0%.

### Lưu ý

- `success = false` không bao giờ xảy ra — thất bại luôn đi bằng status code.
- Bản ghi append vào `models/classification_feedback/feedback.jsonl` (không dùng ChromaDB
  như prescription history: ở đây chỉ cần đếm đúng/sai và giữ dữ liệu cho lần retrain).
- Hai container AI (REST + gRPC) phải **mount chung** thư mục này, nếu không bộ đếm trả
  về sẽ khác nhau tuỳ transport.

---

## 11. `Health` — 4 field mới, BE **phải** đọc

| Field | Ghi chú |
|---|---|
| `soc_mode` | định nghĩa `soc_percent` mà **bộ artifact mặc định (NASA/NMC)** được train |
| `lfp_soc_mode` | như trên cho bộ LFP; `""` khi `lfp_loaded = false` |
| `long_loaded` | model long đã nạp chưa — nạp **lười**, `false` = "chưa ai gọi", không phải "thiếu artifact" |
| `long_model_version` | version của model long |

**Vì sao bắt buộc đọc `soc_mode` thay vì hardcode theo chemistry:** `soc_mode` là thuộc
tính của **bộ artifact**, không phải của request. Gửi sai `soc_percent` **không bao giờ bị
từ chối** — nó chỉ lặng lẽ làm lệch SOH. Hardcode theo chemistry sẽ hỏng âm thầm đúng vào
ngày một bộ được retrain với định nghĩa còn lại.

| Giá trị | BE phải gửi `soc_percent` kiểu nào |
|---|---|
| `"window"` | **window-local**: ~100% ở **hàng đầu của window này**, giảm dần qua 30 hàng. Không chắc thì gửi 4 cột |
| `"cycle"` | scope theo **cả chu kỳ xả**: ~100% đầu chu kỳ, giảm tới ~9% cuối chu kỳ (đúng SOC thật của pin) |
| `"unknown"` | artifact khai báo giá trị lạ — **đừng đoán**, gửi 4 cột và báo cho AI team |
