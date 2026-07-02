# TEST REPORT — GH-39 — 2026-07-02

## Scope: AI (gRPC contract + codegen — foundation, không có server)
## Môi trường: local (Windows 11, Python 3.11.9, venv)

## TÓM TẮT
Full suite 158/159 pass với coverage 86% (≥85% target). Test fail duy nhất là latency prescribe flaky khi chạy full-suite dưới tải — PASS khi chạy riêng, pre-existing (tiền lệ commit `9b41269`), không liên quan diff GH-39. Toàn bộ 17 test contract PASS; codegen deterministic; REST regression xanh.

| Test case | Input | Expected | Actual | Status |
|-----------|-------|----------|--------|--------|
| Contract suite (17 tests) | `pytest tests/test_grpc_contract.py` | 17 pass | 17 pass (0.14s) | ✅ PASS |
| Stub import | `from src.grpc_gen import ai_service_pb2, ai_service_pb2_grpc` | import OK | import OK | ✅ PASS |
| Service surface | descriptor `AiService` | 4 method: Predict/Prescribe/Health unary, PredictStream bidi | đúng 4, đúng streaming flags | ✅ PASS |
| PredictRequest round-trip | 30 readings × 3 features | serialize→parse bằng nhau | bằng nhau, giữ nguyên values | ✅ PASS |
| PredictResponse round-trip | full nested + flat compat + map FeatureStat | parse == gốc | == gốc, map/repeated giữ đúng | ✅ PASS |
| PrescribeRequest optional | `age_cycles=300`, bỏ `last_maintenance_date` | HasField đúng ngữ nghĩa optional | HasField(age_cycles)=True, (last_maintenance_date)=False | ✅ PASS |
| HealthResponse round-trip | 5 fields | parse == gốc | == gốc | ✅ PASS |
| Field parity 11 messages | proto DESCRIPTOR vs Pydantic model_fields | tên field khớp 100% | khớp 100% | ✅ PASS |
| Codegen deterministic | chạy `gen_proto.py` 2 lần, md5 toàn bộ output | hash giống hệt | giống hệt | ✅ PASS |
| REST regression | `pytest tests/test_routers.py` | pass (không đụng REST) | 24/24 pass (gộp contract) | ✅ PASS |
| Full suite | `pytest tests/ --cov=src` | xanh | 158 pass, 1 fail (flaky, xem dưới) | ⚠️ xem lưu ý |
| Latency prescribe (isolated) | `TestPrescriptionLatency` riêng | < 100ms | PASS | ✅ PASS |
| Latency inference benchmark | `tests/test_inference.py` | < 100ms | 15/15 PASS (gồm long-seq benchmark) | ✅ PASS |

## Coverage
- Line coverage: **86%** (target ≥ 85%) — TOTAL 1086 stmts, 152 miss.
- Lưu ý: stub generated (`ai_service_pb2.py` 22%, `_pb2_grpc.py` 50%) kéo tổng xuống nhưng vẫn đạt target; phần code generated không yêu cầu test từng dòng (Servicer/Stub classes dùng ở GH-40/41).

## Latency
- Inference benchmark: PASS < 100ms (tests/test_inference.py, gồm long-sequence path).
- Ticket này không đụng inference path — latency không đổi so với dev.

## Bugs tìm được
- Không có bug mới từ diff GH-39.
- ⚠️ Pre-existing flaky: `tests/test_prescription.py::TestPrescriptionLatency::test_rule_path_under_100ms` fail khi chạy full-suite (113.8–115ms > 100ms do máy tải), PASS khi chạy riêng (2 lần verify). Không thuộc scope ticket — đã có tiền lệ xử lý ở commit `9b41269 update latency flaky`.

## Checklist bắt buộc (mục N/A do ticket contract-only, không đụng train/inference/REST)
- [x] Unit test contract: import + round-trip + field parity — 17/17 PASS
- [x] Reproducibility: codegen deterministic (md5 identical 2 runs); không có training code trong diff → seed N/A
- [x] Latency benchmark < 100ms — PASS (không đổi, diff không đụng inference)
- [x] Input validation: proto3 optional semantics verify bằng HasField
- [x] REST endpoints không regression — test_routers 24/24 PASS
- [x] Startup load: không đổi (diff không đụng model_loader/main.py)

## RỦI RO & LƯU Ý
- Test flaky latency nên chạy riêng khi CI fail full-suite; cân nhắc tăng threshold hoặc mark `@pytest.mark.flaky` ở ticket riêng (ngoài scope GH-39).
- Stub commit vào Git: teammate sau khi pull chỉ cần `pip install -r requirements.txt`, không cần chạy codegen.

## KẾT LUẬN
**PASS** — Độ tự tin: **Cao**
