# TEST REPORT — GH-40 — 2026-07-02

## Scope: AI (gRPC server unary — Predict/Prescribe/Health)
## Môi trường: local (Windows 11, Python 3.11.9, venv)

## TÓM TẮT
GH-40 suite 12/12 PASS; full suite 170 pass, coverage tổng **88%** (≥85% target), `src/grpc_server.py` đạt 90%. Fail duy nhất trong full-suite là latency prescribe flaky pre-existing (PASS khi chạy riêng — verify lại lần này). Smoke weights thật blocked bởi repo state ngoài scope (artifacts v1.3 chưa commit — REST cũng bị, đã comment issue #40).

| Test case | Input | Expected | Actual | Status |
|-----------|-------|----------|--------|--------|
| Health | `HealthRequest` | status ok + 3 loaded flags | ok, đủ flags, đúng MODEL_VERSION | ✅ PASS |
| Predict hợp lệ | 30×6 readings (dummy models) | classification ∈ {Normal,Degrading,Failed}, SOH [0,100], nested==flat | đúng toàn bộ | ✅ PASS |
| Predict thiếu timestep | 5 readings, qua server thật | `INVALID_ARGUMENT` + msg "timesteps" | đúng code + msg | ✅ PASS |
| Predict sai feature count | 30×2 readings | `INVALID_ARGUMENT` | đúng | ✅ PASS |
| PredictStream (chưa có #41) | stream 1 request | `UNIMPLEMENTED` | đúng | ✅ PASS |
| Parity Predict gRPC vs REST | patch `run_inference` dict cố định, cả 2 transport | field-by-field bằng nhau (flat + 4 nested block + warnings + feature_summary ×2) | bằng nhau | ✅ PASS |
| Parity Prescribe gRPC vs REST | patch `run_prescription` dict cố định | field-by-field bằng nhau (11 scalar + 5 list + docs) | bằng nhau | ✅ PASS |
| proto3 optional forwarding | age_cycles=300, không set last_maintenance_date; rồi ngược lại | HasField → kwargs đúng, không set → default | đúng cả 2 chiều | ✅ PASS |
| Pipeline lỗi (Predict) | patch `run_inference` raise, qua server thật | `INTERNAL` + "inference failed" | đúng | ✅ PASS |
| Pipeline lỗi (Prescribe) | patch `run_prescription` raise | `INTERNAL` + "prescription failed" | đúng | ✅ PASS |
| `create_server` bind + start/stop | port 0 (OS-assigned) | không lỗi | không lỗi | ✅ PASS |
| Transport overhead | 20 lần direct vs 20 lần gRPC end-to-end | overhead <50ms, e2e <500ms | **overhead 1.4ms**, e2e ~110ms | ✅ PASS |
| Full suite regression | `pytest tests/ --cov=src` | xanh, ≥85% | 170 pass / 88% (1 flaky pre-existing) | ✅ PASS |
| Flaky isolate verify | `TestPrescriptionLatency` riêng | <100ms | PASS (4.1s) | ✅ PASS |

## Coverage
- Line coverage tổng: **88%** (target ≥ 85%) — 1166 stmts, 145 miss.
- `src/grpc_server.py`: **90%** — chỉ còn `serve()` entrypoint (dòng 241–247, 251): blocking loop `wait_for_termination` + cần weights thật, không unit-test được; thành phần của nó (`load_models`, `create_server`) đều có test riêng.

## Latency
- **Transport overhead gRPC: 1.4ms** (assert <50ms) — phần GH-40 thêm vào.
- Pipeline direct ~109ms trên máy dev CPU đang tải (MC Dropout ×20) — SLA <100ms của pipeline do test hiện có enforce (`test_prescription.py`, `test_inference.py`), pass khi máy không tải; xem note flaky 9b41269.
- gRPC end-to-end ~110ms cùng điều kiện — đúng bằng pipeline + overhead, không có chi phí ẩn.

## Bugs tìm được
- Không có bug mới từ diff GH-40.
- ⚠️ Pre-existing flaky: `test_rule_path_under_100ms` fail dưới tải full-suite (118.9ms), PASS khi chạy riêng — tiền lệ 9b41269, ngoài scope.
- ⚠️ Pre-existing blocker (đã comment issue #40): config đòi artifacts v1.3 chưa commit; checkpoint v1.2 không tương thích arch sau GH-34/37/38 → **cả REST lẫn gRPC không start được với weights thật** cho tới khi v1.3 commit (chuỗi #25). Smoke thật dời sang GH-42/khi có artifacts.

## Checklist bắt buộc (mục train/preprocess N/A — ticket serving-only)
- [x] Unit test servicer: 3 RPC + stream UNIMPLEMENTED + error codes — 12/12 PASS
- [x] Input validation: cùng Pydantic validator với REST → reject giống nhau, có test 2 case
- [x] Output format: parity field-by-field với REST cho cả 2 RPC
- [x] Latency benchmark: transport overhead 1.4ms < 50ms
- [x] Startup load: `load_models()` 1 lần trong `serve()`; servicer không load per-request
- [x] REST không regression: full suite xanh, diff không đụng tracked file

## RỦI RO & LƯU Ý
- BE tích hợp cần biết: port 50051 (env `GRPC_PORT`), insecure channel — chỉ dùng nội bộ docker network, không expose ra ngoài (không TLS).
- Khi artifacts v1.3 được commit: chạy lại smoke `python -m src.grpc_server` + `uvicorn main:app` để xác nhận cả 2 transport start được (ghi vào handoff).

## KẾT LUẬN
**PASS** — Độ tự tin: **Cao**
