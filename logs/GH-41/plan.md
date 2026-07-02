# Plan — GH-41: gRPC bidirectional streaming PredictStream (sensor real-time)

## Metadata
- **Status:** TESTING | **Role:** AI | **Ngày:** 2026-07-02
- **Issue:** #41 — https://github.com/GSU26SE55/ai-module/issues/41
- **Sprint:** Sprint 4 (chuỗi gRPC: #39 → #40 → **#41** → #42)

## Mục tiêu
Implement RPC `PredictStream (stream PredictRequest) returns (stream PredictResponse)` trên server gRPC hiện có (GH-40): client stream nhiều window sensor liên tục, server trả prediction tương ứng **đúng thứ tự** trên cùng HTTP/2 connection — phục vụ luồng sensor real-time, không phải mở connection mới mỗi window.

## Scope
**Trong scope:**
- Override `PredictStream` trong `AiServiceServicer` (`src/grpc_server.py`) — **sync generator** (đã chốt với user): `for request in request_iterator: yield response`
- Tái dùng nguyên đường xử lý unary: validate Pydantic → `run_inference()` → `_to_predict_response()` — 1 request trong stream ≡ 1 call `Predict` unary
- Error semantics giữa stream: window sai shape → abort `INVALID_ARGUMENT` (kết thúc stream, gRPC bidi không có per-message error channel); lỗi pipeline → `INTERNAL`
- Tests: in-order N windows, mixed-shape abort, stream rỗng, client cancel, parity với unary, throughput sanity

**Ngoài scope:**
- KHÔNG migrate grpc.aio (đã chốt: sync generator — backpressure có sẵn từ gRPC/HTTP/2 flow control; `_MC_LOCK` serialize inference nên aio không tăng throughput)
- KHÔNG đổi contract proto (RPC đã khai báo từ GH-39)
- KHÔNG đụng `Predict`/`Prescribe`/`Health` unary, FastAPI, model code
- KHÔNG windowing/buffering phía server (client tự gửi đủ window 30 — giữ semantics giống unary; sliding-window tích lũy từng reading là scope khác, cần bàn với BE trước)
- KHÔNG benchmark/client demo hoàn chỉnh (→ #42)

## Endpoints
| RPC | Proto | Mục đích |
|-----|-------|----------|
| `AiService.PredictStream` | `stream PredictRequest → stream PredictResponse` | Real-time: N windows → N predictions in-order trên 1 connection |

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/grpc_server.py` | modify | thêm method `PredictStream` (~15 dòng, tái dùng `_validate` + `_to_predict_response`) |
| `tests/test_grpc_server.py` | modify | thêm class test streaming |
| `logs/GH-41/plan.md` | create | file này |

## Approach
- Sync generator trong servicer: gRPC sync server hỗ trợ bidi streaming native — mỗi `yield` đẩy 1 response; in-order được bảo đảm vì xử lý tuần tự trong 1 handler thread.
- Backpressure: gRPC flow control (HTTP/2 window) tự chặn `request_iterator` khi server xử lý chậm — không cần code thêm; ghi chú rõ trong docstring.
- Mỗi message qua đúng đường unary (validate → infer → map) — parity tuyệt đối với `Predict`, không duplicate logic.
- Client cancel giữa stream: `request_iterator` raise → generator kết thúc sạch, server không crash (có test).
- Thread-safety sẵn có: nhiều stream đồng thời chia sẻ `_MC_LOCK` trong `run_inference` (như unary).

## Edge Cases
- Window sai shape ở message thứ k: abort `INVALID_ARGUMENT` — client nhận k-1 responses rồi error status (bidi gRPC không có per-message error; BE cần biết semantics này, ghi vào handoff/#42).
- Stream rỗng (client đóng ngay): server trả 0 responses, status OK, không crash.
- Client cancel giữa chừng: server dừng xử lý message còn lại, không leak.
- Lỗi pipeline bất ngờ giữa stream → `INTERNAL` (giống unary).

## Acceptance Criteria
- [x] Client gửi N windows (khác nhau) → nhận đúng N predictions, **đúng thứ tự** (test 5 windows, map battery_id request↔response).
- [x] Response thứ i của stream == response của `Predict` unary với cùng input (parity test, patch `run_inference` dict cố định — message bằng nhau tuyệt đối).
- [x] Window sai shape giữa stream → `INVALID_ARGUMENT`, các window trước đó vẫn nhận response (test: nhận đúng 2 responses rồi error).
- [x] Stream rỗng → 0 responses, không lỗi; client cancel → server vẫn healthy (Health sau cancel OK).
- [x] Unary `Predict`/`Prescribe`/`Health` không đổi hành vi — suite GH-40 17/17 xanh (11 test cũ + 6 streaming).
- [x] Full suite 175 pass + ruff sạch; FastAPI không đụng (diff: `src/grpc_server.py` + `tests/test_grpc_server.py`).

## Steps
- [x] Bước 1: Implement `PredictStream` generator trong `src/grpc_server.py` — 2026-07-02
- [x] Bước 2: Tests streaming — in-order N windows + parity với unary — 2026-07-02
- [x] Bước 3: Tests edge cases — sai shape giữa stream, stream rỗng, client cancel + pipeline INTERNAL — 2026-07-02
- [x] Bước 4: Thay test `test_predict_stream_unimplemented` (GH-40) bằng class `TestPredictStream` (6 tests) — 2026-07-02
- [x] Bước 5: Verify: ruff sạch + full suite 175 pass + REST/unary không đụng (diff chỉ 2 file gRPC). Flaky pre-existing `test_rule_path_under_100ms` dao động 95–119ms trên máy dev tải nặng (fail cả isolate 2/3 lần) — không liên quan GH-41 (test_prescription không import grpc_server); đề xuất ticket riêng mark flaky/threshold — 2026-07-02

## Câu hỏi đã giải đáp
- **Sync generator vs grpc.aio (hỏi 2026-07-02):** issue body ghi grpc.aio nhưng đã chốt **sync generator** — server GH-40 là sync, `run_inference` blocking + `_MC_LOCK` serialize nên aio không tăng throughput inference; sync generator cho in-order + backpressure sẵn có (HTTP/2 flow control), diff nhỏ, không refactor code vừa merge.
- **Semantics per-message:** 1 `PredictRequest` trong stream = 1 window 30 đầy đủ = 1 `PredictResponse` (mirror unary) — server không tích lũy sliding window từng reading (ngoài scope, cần bàn BE).
