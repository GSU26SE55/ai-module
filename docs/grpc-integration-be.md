# gRPC Integration Guide — BE (.NET) gọi AI Module

> GH-42 · Contract: `protos/ai_service.proto` (single source of truth, repo `ai-module`)
> Chuỗi liên quan: #39 (contract) → #40 (server unary) → #41 (streaming) → #42 (doc này)

AI module expose **2 transport song song** trên cùng pipeline:

| Transport | Port | Dùng khi |
|-----------|------|----------|
| REST (FastAPI) | 8000 | tích hợp hiện tại, Swagger, đơn giản |
| gRPC (`AiService`) | 50051 (env `GRPC_PORT`) | latency thấp hơn, streaming sensor real-time |

Cả hai trả **cùng payload** (đã có parity test field-by-field) — BE migrate dần không cần remap.

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
| 7 | **Prescribe `enrich=false` mặc định** | Rule-based, hot-path (<100ms SLA). `enrich=true` chạy RAG+LLM (chậm, có thể vài giây) — chỉ dùng ngoài P1 hot-path. |

## 5. Chạy local để test

```bash
# Trong repo ai-module (cần artifacts trong models/weights/ — xem lưu ý bên dưới)
python -m src.grpc_server              # gRPC :50051
uvicorn main:app --port 8000           # REST :8000 (song song, tùy chọn)

# Demo đủ 4 RPC (thay Swagger)
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
