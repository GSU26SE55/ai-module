# Plan — GH-40: gRPC server unary (Predict/Prescribe/Health) song song FastAPI

## Metadata
- **Status:** TESTING | **Role:** AI | **Ngày:** 2026-07-02
- **Issue:** #40 — https://github.com/GSU26SE55/ai-module/issues/40
- **Sprint:** Sprint 4 (chuỗi gRPC: #39 → **#40** → #41 → #42)

## Mục tiêu
gRPC server implement 3 RPC unary (`Predict`, `Prescribe`, `Health`) từ contract GH-39, **tái dùng nguyên** `run_inference()` / `run_prescription()` — không duplicate logic. Chạy **song song uvicorn** (hybrid): entrypoint riêng port 50051, FastAPI giữ nguyên 100%.

## Scope
**Trong scope:**
- `src/grpc_server.py` — `AiServiceServicer(ai_service_pb2_grpc.AiServiceServicer)`:
  - `Predict` → validate bằng Pydantic `PredictRequest` → `run_inference()` → `_to_predict_response()`
  - `Prescribe` → validate bằng Pydantic `PrescribeRequest` → `run_prescription()` → `_to_prescribe_response()`
  - `Health` → mirror logic `/health` (đọc `model_loader.*`)
  - `PredictStream` — KHÔNG implement (kế thừa default `UNIMPLEMENTED` từ base class, đó là #41)
- Helper `_to_predict_response(battery_id, result: dict)` / `_to_prescribe_response(result: dict)` — map dict (đã là PredictResponse/PrescribeResponse-compatible) → proto message
- Entrypoint `serve()` + `if __name__ == "__main__"`: `load_models()` → sync `grpc.server(ThreadPoolExecutor)` → bind `0.0.0.0:{GRPC_PORT}` (env, default 50051) → `wait_for_termination()`
- Unit tests `tests/test_grpc_server.py` — dùng dummy loader pattern của `test_routers.py`, gọi servicer trực tiếp (không cần chạy server thật) + 1 test end-to-end qua channel local
- Parity test: patch `run_inference` trả dict cố định → gRPC response == REST response field-by-field

**Ngoài scope:**
- KHÔNG streaming (`PredictStream` → #41)
- KHÔNG benchmark/client demo/share proto cho BE (→ #42)
- KHÔNG đụng FastAPI (`main.py`, routers, schemas) — REST giữ nguyên
- KHÔNG đổi contract proto (nếu phát hiện thiếu field → dừng, hỏi trước)
- KHÔNG TLS/auth (nội bộ docker network, scope capstone)

## Endpoints
| RPC | Proto | Mục đích |
|-----|-------|----------|
| `AiService.Predict` | `PredictRequest → PredictResponse` | Mirror `POST /predict` |
| `AiService.Prescribe` | `PrescribeRequest → PrescribeResponse` | Mirror `POST /prescribe` |
| `AiService.Health` | `HealthRequest → HealthResponse` | Mirror `GET /health` |

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/grpc_server.py` | create | Servicer + 2 helper mapping + `serve()` entrypoint |
| `tests/test_grpc_server.py` | create | unit (servicer trực tiếp) + parity REST + error cases |
| `logs/GH-40/plan.md` | create | file này |

## Approach
- **Sync server** (`grpc.server` + `ThreadPoolExecutor(max_workers=10)`) — `run_inference` là sync (có `_MC_LOCK` nội bộ), không cần grpc.aio.
- **Validate qua Pydantic có sẵn**: proto `PredictRequest` → dựng `src.schemas.predict.PredictRequest(battery_id=..., readings=[[...]])` — tái dùng validator shape (30 timesteps, 3|6 features). `ValidationError` → `context.abort(INVALID_ARGUMENT, str(e))`. Lỗi bất ngờ → `abort(INTERNAL)`.
- **Mapping dict → proto** trong 2 helper: dùng `ParseDict`-free manual mapping (rõ ràng, type-safe qua .pyi) — nested (`prediction`, `anomaly`, `risk`, `evidence`, `metadata`) + flat compat fields, `feature_summary` map, `warnings` repeated.
- **Model load 1 lần** khi start (`load_models()` trong `serve()`), servicer không load per-request — giống lifespan FastAPI.
- **Port qua env** `GRPC_PORT` (default 50051) — không hardcode; chạy: `python -m src.grpc_server` (process riêng, song song `uvicorn main:app`).

## Edge Cases
- Readings sai shape (≠30 timesteps, ≠3|6 features) → `INVALID_ARGUMENT` kèm message từ Pydantic validator.
- `battery_id` rỗng: **chấp nhận** — Pydantic schema REST không có `min_length`, gRPC dùng cùng schema nên hành vi giống hệt (parity là mục tiêu; nếu muốn siết thì siết ở schema chung, ticket riêng).
- `PredictStream` gọi khi chưa có #41 → gRPC trả `UNIMPLEMENTED` (behavior mặc định của base servicer).
- Model chưa load (gọi servicer trước `load_models()`) → `INTERNAL` với message rõ ràng, không crash server.
- `Prescribe` với `enrich=true` nhưng LLM lỗi → `run_prescription` đã tự fallback rule-based (không cần xử lý thêm ở gRPC layer).

## Acceptance Criteria
- [x] `Predict`/`Prescribe`/`Health` qua gRPC trả kết quả **khớp REST**: patch `run_inference`/`run_prescription` trả dict cố định → so sánh từng field gRPC response vs REST response (TestClient) — bằng nhau.
- [x] Server start được: bind port thật + client stub thật qua channel (fixture `grpc_stub`, OS-assigned port). ⚠️ Smoke `python -m src.grpc_server` với weights thật **blocked bởi repo state ngoài scope**: config đòi v1.3 nhưng `models/weights/` chỉ có v1.2, và checkpoint v1.2 không load được vào arch hiện hành (FiLM 2-layer, dt_proj 128×4 — đổi bởi GH-34/37/38). REST cũng bị y hệt. Smoke lại khi artifacts v1.3 được commit (chuỗi #25).
- [x] Input sai shape → `INVALID_ARGUMENT` (không phải crash/UNKNOWN).
- [x] `PredictStream` trả `UNIMPLEMENTED`.
- [x] FastAPI không đổi — diff chỉ gồm 2 file mới + logs, không đụng tracked file nào.
- [x] `pytest tests/test_grpc_server.py` 9/9 PASS + suite 167 pass (1 flaky pre-existing 9b41269); ruff sạch trên file mới.
- [x] Latency: **điều chỉnh cách đo** — pipeline `run_inference` (MC Dropout ×20) vốn đã 85–110ms trên máy dev (chính là flaky 9b41269), assert tuyệt đối <100ms cho gRPC sẽ flaky vì đo lại pipeline. Test đo **transport overhead gRPC = 1.4ms (<50ms)** + sanity bound end-to-end <500ms (tier P2/P3 rules/tech/ai.md). SLA <100ms của pipeline vẫn do test hiện có enforce.

## Steps
- [x] Bước 1: `src/grpc_server.py` — servicer `Health` + entrypoint `serve()` (skeleton chạy được) — 2026-07-02
- [x] Bước 2: Helper `_to_predict_response` + RPC `Predict` (validate Pydantic → run_inference → map proto) — 2026-07-02
- [x] Bước 3: Helper `_to_prescribe_response` + RPC `Prescribe` — 2026-07-02
- [x] Bước 4: `tests/test_grpc_server.py` — unit + parity REST + error cases (INVALID_ARGUMENT, UNIMPLEMENTED) + latency — 2026-07-02
- [x] Bước 5: Verify: ruff + pytest full suite (167 pass) + xác nhận REST không đụng; smoke weights thật blocked (xem Acceptance Criteria) — 2026-07-02

## Câu hỏi đã giải đáp
- **Branch base (hỏi 2026-07-02):** ban đầu chốt stack lên `feat/GH-39-*`; nhưng PR #50 (GH-39) đã merge vào dev trước khi implement → **`feat/GH-40-grpc-server-unary` tạo thẳng từ dev** (đơn giản hơn, không cần đổi base PR).
- **Server style:** sync `grpc.server` process riêng (không nhét vào lifespan FastAPI) — đúng chữ "song song uvicorn" trong issue; đơn giản, cô lập failure domain.
- **"Khớp REST" đo thế nào:** MC Dropout làm output stochastic giữa 2 lần gọi thật → parity test phải patch `run_inference` trả dict cố định rồi so sánh field-by-field giữa 2 transport.
