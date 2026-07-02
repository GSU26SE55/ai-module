# BÁO CÁO CODE REVIEW — feat/GH-39-grpc-contract-ai-service-proto — 2026-07-02

## Scope: AI
## Effort: Standard

## TÓM TẮT
Ticket foundation: contract gRPC (`ai_service.proto`) + codegen pipeline + stub đã sinh + test contract. Không có server, không đụng REST/FastAPI, không đụng model/training. Toàn bộ acceptance criteria đạt; không có Critical.

## PHÂN TÍCH

### Files trong diff (working tree — chưa commit, đúng quy trình /kltn-ship mới commit)
| File | Action |
|------|--------|
| `protos/ai_service.proto` | create |
| `scripts/gen_proto.py` | create |
| `src/grpc_gen/__init__.py` + `ai_service_pb2.py` + `ai_service_pb2_grpc.py` + `ai_service_pb2.pyi` | generate |
| `requirements.txt` | modify (+3 pins) |
| `tests/test_grpc_contract.py` | create |
| `logs/GH-39/plan.md` | tracking |

### Kết quả checklist

✅ Pass: **Contract đúng scope** — service `AiService` chỉ có 4 RPC theo plan (`Predict`, `Prescribe`, `Health` unary + `PredictStream` bidi). Không có servicer implementation nào ngoài code generated (server là GH-40/41).

✅ Pass: **Field parity proto ↔ Pydantic** — test đối chiếu field names cho 11 message (WarningItem, FeatureStat, PredictionInfo, AnomalyInfo, RiskInfo, ResponseMetadata, RetrievedDoc, PrescribeRequest/Response, PredictRequest/Response) đều khớp `model_fields`, gồm cả flat compat fields của PredictResponse.

✅ Pass: **Kiểu số dùng `double`** — Python float là 64-bit; proto `float` sẽ truncate khi round-trip (3.7 → 3.6999998). Lệch có chủ đích so với sketch trong plan (`repeated float values`), có comment giải thích trong proto.

✅ Pass: **Import fix trong stub** — `ai_service_pb2_grpc.py:6` là `from src.grpc_gen import ai_service_pb2 as ...` (script tự rewrite sau codegen); import được từ repo root.

✅ Pass: **Version pins nhất quán** — `grpcio==1.81.1` / `grpcio-tools==1.81.1` / `protobuf==6.33.6` pin cùng nhau. Stub generated yêu cầu grpcio ≥ 1.81.1 (guard trong `_pb2_grpc.py`) và protobuf runtime ≥ 6.33.5 (gencode validate) — cả hai thỏa. Có note exception rule "chỉ PyTorch+sklearn" (grpcio là serving lib, tiền lệ chromadb/anthropic GH-20).

✅ Pass: **Codegen cross-platform** — dùng `grpc_tools.protoc` module (không cần protoc hệ thống), `pathlib`, ghi file explicit `encoding="utf-8"` (đã fix bug cp1252 trên Windows trong lúc implement).

✅ Pass: **REST không đụng** — `git status` xác nhận không có thay đổi nào trong `src/routers/`, `src/main.py`, `src/schemas/`. Tracked file thay đổi duy nhất: `requirements.txt`.

✅ Pass: **Reproducibility** — versions pinned; ticket không có training/preprocess nên random seed N/A. Scaler/data-leakage checklist N/A (không đụng data/model code).

✅ Pass: **Tests** — `tests/test_grpc_contract.py` 17/17 PASS (import stub, service surface, round-trip 4 cặp message, optional field semantics `HasField`, field parity). Ruff sạch trên toàn bộ file mới.

🟡 Warning: `src/grpc_gen/*_pb2*.py` là generated code commit vào Git — reviewer PR không cần đọc từng dòng, chỉ cần verify chạy lại `python scripts/gen_proto.py` cho ra kết quả giống hệt. Đề xuất ghi chú trong PR body (xử lý ở /kltn-ship).

🟡 Warning: proto có `option csharp_namespace = "AiModule.V1"` phục vụ BE .NET — BE cần copy đúng file này (single source of truth là repo ai-module). Nếu sau này contract đổi, cần quy trình sync 2 repo (ngoài scope ticket).

## RỦI RO & LƯU Ý
- Full suite: 158 pass; `test_prescription.py::TestPrescriptionLatency::test_rule_path_under_100ms` flaky khi chạy full suite dưới tải (115ms), PASS khi chạy riêng — pre-existing (tiền lệ commit `9b41269`), không liên quan diff này.
- Ruff báo lỗi ở `scripts/train.py`, `scripts/experiment_*.py` — pre-existing, ngoài scope (Surgical Changes), không sửa.
- Khi BE bắt đầu dùng contract (GH-40), nếu cần đổi/thêm field: chỉ **thêm** field number mới, không reuse/đổi số field cũ (wire compatibility).

## KẾT LUẬN
**PASS** — Độ tự tin: **Cao**
