# TEST REPORT — GH-41 — 2026-07-02

## Scope: AI (gRPC bidirectional streaming PredictStream)
## Môi trường: local (Windows 11, Python 3.11.9, venv)

## TÓM TẮT
gRPC suites 34/34 PASS (17 server + 17 contract); full suite **175 pass**, coverage tổng **87%** (≥85%), `src/grpc_server.py` 91%. Fail duy nhất là flaky pre-existing `test_rule_path_under_100ms` (không liên quan diff — test_prescription không import grpc_server). Throughput sanity: stream ≈ unary per-window (ratio 1.05) — đúng kỳ vọng vì inference bị `_MC_LOCK` serialize; lợi ích stream là connection reuse + in-order, không phải tốc độ inference.

| Test case | Input | Expected | Actual | Status |
|-----------|-------|----------|--------|--------|
| 5 windows in-order | battery_id B0000–B0004, qua server thật | 5 responses, đúng thứ tự request | đúng cả 5, map đúng vị trí | ✅ PASS |
| Parity stream vs unary | cùng window, patch `run_inference` dict cố định | message bằng nhau tuyệt đối | `streamed[0] == unary` | ✅ PASS |
| Window sai shape ở vị trí 3/4 | 2 valid + 1 bad (5 timesteps) + 1 valid | 2 responses rồi `INVALID_ARGUMENT` | nhận đúng ["B0000","B0001"] rồi error | ✅ PASS |
| Stream rỗng | client đóng ngay | 0 responses, status OK | 0 responses, không lỗi | ✅ PASS |
| Client cancel giữa stream | stream vô hạn, cancel sau response đầu | server không crash, vẫn phục vụ | Health sau cancel = ok | ✅ PASS |
| Lỗi pipeline giữa stream | patch `run_inference` raise | `INTERNAL` | đúng | ✅ PASS |
| Unary regression (GH-40) | toàn bộ 11 test cũ | không đổi hành vi | 11/11 PASS | ✅ PASS |
| Contract regression (GH-39) | 17 test contract | xanh | 17/17 PASS | ✅ PASS |
| Full suite | `pytest tests/ --cov=src` | xanh, ≥85% | 175 pass / 87% | ✅ PASS |
| Throughput sanity | 20 windows: stream 1 connection vs 20 unary calls | stream không tệ hơn đáng kể | 116.5 vs 111.1 ms/window (ratio 1.05) | ✅ PASS |

## Coverage
- Tổng: **87%** (target ≥85%) — 1171 stmts, 151 miss.
- `src/grpc_server.py`: **91%** — chỉ còn `serve()` entrypoint (blocking loop, cần weights thật — như GH-40).

## Latency / Throughput
- Per-window stream ≈ unary (ratio 1.05, đo 20 windows qua server thật với dummy models trên máy dev đang tải ~111ms/window do MC Dropout ×20).
- Ý nghĩa: streaming không thêm chi phí đáng kể; giá trị của nó là 1 HTTP/2 connection cho cả phiên sensor + in-order + backpressure, không phải tăng tốc inference (bị `_MC_LOCK` serialize by design).

## Bugs tìm được
- Không có bug mới từ diff GH-41.
- ⚠️ Flaky pre-existing `test_rule_path_under_100ms` (105–119ms trên máy dev, fail cả isolate lúc máy tải) — không liên quan GH-41; **đề xuất mở ticket riêng** mark `@pytest.mark.flaky` hoặc nới threshold cho CPU dev trước khi nó chặn PR khác.

## Checklist bắt buộc (train/preprocess N/A — ticket serving-only)
- [x] Unit test streaming: in-order + parity + 4 edge cases — qua server thật, 6/6 PASS
- [x] Input validation: cùng Pydantic validator với unary/REST — test sai shape giữa stream
- [x] Output format: parity tuyệt đối với unary (cùng code path `_predict_one`)
- [x] Latency/throughput: đo thật, ratio 1.05 vs unary
- [x] Startup load: không đổi (dùng server GH-40)
- [x] REST/unary không regression: 175 pass

## RỦI RO & LƯU Ý
- BE tích hợp: window lỗi giữa stream → stream abort sau k−1 responses (bidi không có per-message error) — client cần reconnect; ghi vào handoff + demo #42.
- Stream dài giữ 1 worker thread (pool 10) — theo dõi ở benchmark #42.
- Smoke weights thật vẫn chờ artifacts v1.3/v2.2 (retrain #25).

## KẾT LUẬN
**PASS** — Độ tự tin: **Cao**
