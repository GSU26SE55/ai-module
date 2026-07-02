# Plan — GH-39: gRPC contract ai_service.proto + codegen (foundation)

## Metadata
- **Status:** TESTING | **Role:** AI | **Ngày:** 2026-07-02
- **Issue:** #39 — https://github.com/GSU26SE55/ai-module/issues/39
- **Sprint:** Sprint 4

## Mục tiêu
Định nghĩa contract gRPC (`ai_service.proto`) dùng chung AI module ↔ BE .NET + pipeline codegen sinh Python stub. Đây là **foundation** cho #40 (server unary) + #41 (streaming) — issue này CHỈ giao contract + stub compile được, **chưa có server**.

## Scope
**Trong scope:**
- `protos/ai_service.proto` — service `AiService`: `Predict`, `Prescribe`, `Health` (unary) + `PredictStream` (bidirectional stream). Messages mirror Pydantic schema hiện tại (`src/schemas/predict.py`, `prescribe.py`) gồm cả flat compat fields.
- `scripts/gen_proto.py` — codegen script (Python, chạy được Windows + Kaggle/Linux; không dùng .sh vì máy dev là Windows) → sinh stub vào `src/grpc_gen/` + sửa import tương đối.
- Commit stub đã sinh (`src/grpc_gen/*_pb2*.py`) để CI/teammate không cần chạy protoc.
- `requirements.txt` +`grpcio`, `grpcio-tools`, `protobuf` (pin version).
- Unit test: stub import được + build message round-trip.

**Ngoài scope:**
- KHÔNG viết gRPC server/servicer (đó là #40).
- KHÔNG streaming logic (đó là #41).
- KHÔNG đụng FastAPI/routers/main.py — REST giữ nguyên 100%.
- KHÔNG đổi Pydantic schemas.

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `protos/ai_service.proto` | create | contract v1 (package `aimodule.v1`) |
| `scripts/gen_proto.py` | create | chạy `grpc_tools.protoc`, fix import `import ai_service_pb2` → `from src.grpc_gen import` |
| `src/grpc_gen/__init__.py` | create | package marker |
| `src/grpc_gen/ai_service_pb2.py` + `_pb2_grpc.py` + `.pyi` | generate | commit stub sinh ra |
| `requirements.txt` | modify | +grpcio==1.81.1, grpcio-tools (khớp), protobuf (pin theo venv) |
| `tests/test_grpc_contract.py` | create | import stub, dựng PredictRequest/Response round-trip, verify field names khớp schema |

## Approach
- Proto3, package `aimodule.v1`. `Reading { repeated float values }`; `PredictRequest { battery_id, repeated Reading readings }`.
- `PredictResponse` mirror `PredictResponse` Pydantic: nested (`PredictionInfo`, `AnomalyInfo`, `RiskInfo`, `WarningItem`, `map<string,FeatureStat> feature_summary`, `ResponseMetadata`) + flat compat fields (soh_percent, classification, confidence, ...) để BE migrate dần.
- `PrescribeRequest/Response` mirror schema prescribe (docs, safety gate, timings). `HealthResponse` mirror `/health`.
- Codegen bằng Python script (cross-platform): `python -m grpc_tools.protoc -I protos --python_out=src/grpc_gen --grpc_python_out=src/grpc_gen --pyi_out=src/grpc_gen protos/ai_service.proto` + post-fix import.
- Ghi chú deps: grpcio là **serving lib** (ngang hàng FastAPI), không phải ML framework — không vi phạm rule "chỉ PyTorch+sklearn"; thêm 1 dòng note trong requirements.txt (tiền lệ: chromadb/anthropic có exception ADR).

## Edge Cases
- Windows path/protoc: dùng `grpc_tools.protoc` module (không cần cài protoc hệ thống).
- Import lỗi trong stub sinh ra (`import ai_service_pb2` tuyệt đối) → script tự sửa thành import từ `src.grpc_gen`.
- Version mismatch protobuf runtime vs codegen → pin cả 3 package cùng nhau trong requirements.
- `map<string,FeatureStat>` và `optional` fields (age_cycles...) — proto3 optional cần bật (mặc định OK từ protoc ≥3.15).

## Acceptance Criteria
- [x] `protos/ai_service.proto` compile sạch qua `grpc_tools.protoc`.
- [x] Stub sinh vào `src/grpc_gen/`, import được: `from src.grpc_gen import ai_service_pb2, ai_service_pb2_grpc`.
- [x] Message round-trip test PASS (serialize → parse → so field).
- [x] Field names proto khớp Pydantic schema (test đối chiếu các field chính).
- [x] FastAPI/routers/main.py không đổi (diff không đụng).
- [x] `pytest tests/test_grpc_contract.py` PASS (17/17) + suite hiện tại vẫn xanh (158 pass; test latency prescribe flaky khi full-suite, pass khi chạy riêng — tiền lệ commit 9b41269).

## Steps
- [x] Bước 1: Viết `protos/ai_service.proto` (mirror schemas) — 2026-07-02
- [x] Bước 2: `scripts/gen_proto.py` + chạy sinh stub vào `src/grpc_gen/` — 2026-07-02
- [x] Bước 3: `requirements.txt` pin grpcio/grpcio-tools/protobuf + note exception — 2026-07-02
- [x] Bước 4: `tests/test_grpc_contract.py` (import + round-trip + field parity) — 2026-07-02
- [x] Bước 5: Verify: ruff + pytest full suite + xác nhận REST không đụng — 2026-07-02

## Câu hỏi đã giải đáp
- **Hybrid đã chốt (conversation trước):** gRPC chạy song song FastAPI, KHÔNG xóa REST.
- **Streaming đã chốt:** có `PredictStream` (bidi) trong contract ngay từ v1 để #41 không phải đổi proto.
- **Codegen script:** dùng Python thay .sh (máy dev Windows + Kaggle Linux đều chạy).
- **Deps:** grpcio 1.81.1 đã có sẵn trong venv (dependency của chromadb) → pin đúng version đó, ít rủi ro conflict.
