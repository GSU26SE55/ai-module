# BÁO CÁO CODE REVIEW — feat/GH-40-grpc-server-unary — 2026-07-02

## Scope: AI
## Effort: Standard

## TÓM TẮT
gRPC server unary tái dùng nguyên pipeline REST (`run_inference`/`run_prescription`) — không duplicate logic, không đụng FastAPI. Diff chỉ gồm 2 file mới (`src/grpc_server.py`, `tests/test_grpc_server.py`) + logs. Không có Critical.

## PHÂN TÍCH

### Files trong diff (working tree — chưa commit, /kltn-ship mới commit)
| File | Action |
|------|--------|
| `src/grpc_server.py` | create — servicer + 2 helper mapping + entrypoint |
| `tests/test_grpc_server.py` | create — 9 tests |
| `logs/GH-40/plan.md` | tracking |

### Kết quả checklist

✅ Pass: **Không duplicate logic** — `Predict`/`Prescribe` gọi thẳng `run_inference()`/`run_prescription()` (src/grpc_server.py:174,194); servicer chỉ làm transport + mapping. Sửa model/pipeline sau này tự ảnh hưởng cả 2 transport.

✅ Pass: **Validation parity** — `_validate()` (src/grpc_server.py:217) dựng chính Pydantic schema REST (`PredictRequest`/`PrescribeRequest`) → cùng validator window 30 × 3|6 features, cùng reject; `ValidationError` → `INVALID_ARGUMENT` kèm message gốc. Verify bằng 2 error-case test qua server thật.

✅ Pass: **Mapping đúng và đủ** — 2 helper map dict → proto phủ toàn bộ field (nested `prediction`/`anomaly`/`risk`/`evidence`/`metadata` + flat compat + map `feature_summary` cả 2 chỗ + `RetrievedDoc`). Parity test field-by-field gRPC vs REST (patch pipeline trả dict cố định) PASS cho cả Predict lẫn Prescribe.

✅ Pass: **proto3 optional đúng ngữ nghĩa** — `HasField` guard (src/grpc_server.py:188-191): `age_cycles`/`last_maintenance_date` chỉ forward khi client set, không nhầm 0/"" thành giá trị thật. Có test riêng verify kwargs tới `run_prescription`.

✅ Pass: **Model load 1 lần** — `load_models()` trong `serve()` (src/grpc_server.py:243), servicer không load per-request — giống lifespan FastAPI. Thread-safe: `run_inference` đã có `_MC_LOCK` nội bộ cho MC Dropout.

✅ Pass: **Error handling** — lỗi pipeline bất ngờ → `INTERNAL` + `logger.exception` (không crash server, không leak UNKNOWN); `PredictStream` không override → base class trả `UNIMPLEMENTED` (đúng scope, dành cho #41). Có test.

✅ Pass: **Config qua env** — `GRPC_PORT` (default 50051), không hardcode; entrypoint `python -m src.grpc_server` chạy process riêng song song uvicorn.

✅ Pass: **REST không đụng** — không có tracked file nào thay đổi; `main.py`/routers/schemas/proto nguyên vẹn.

✅ Pass: **Reproducibility/checklist ML** — không có training/preprocess code trong diff → seed/scaler/data-leakage N/A; không thêm ML framework (grpcio đã vào từ GH-39).

✅ Pass: **Tests + lint** — `tests/test_grpc_server.py` 9/9 PASS (unit + parity + error + latency, có server thật bind port thật); full suite 167 pass; ruff sạch.

🟡 Warning: `_validate`/`abort` giả định `context` không None — các test happy-path gọi servicer trực tiếp với `context=None` là chấp nhận được (error-path test đi qua channel thật), nhưng dev sau này viết test error-path trực tiếp sẽ gặp `AttributeError` thay vì abort. Gợi ý (không blocking): dùng channel thật cho mọi error-path test (như hiện tại đang làm).

🟡 Warning: `battery_id` rỗng được chấp nhận — **giống hệt REST** (schema không có `min_length`). Đây là parity đúng mục tiêu; nếu muốn siết thì siết ở schema chung (ticket riêng, ảnh hưởng cả 2 transport). Plan đã cập nhật edge case này cho khớp thực tế.

🟡 Warning: bind `0.0.0.0` không TLS/auth — đã khai báo ngoài scope trong plan (nội bộ docker network, scope capstone); cần nhắc lại trong PR body để BE biết không expose port 50051 ra ngoài.

## RỦI RO & LƯU Ý
- **Blocker chung của repo (ngoài scope GH-40, đã comment lên issue #40):** config đòi artifacts v1.3 chưa commit; checkpoint v1.2 không tương thích arch hiện hành (GH-34/37/38) → cả REST lẫn gRPC đều không start được với weights thật cho tới khi v1.3 được commit (chuỗi #25). Smoke weights thật dời sang lúc đó / GH-42.
- Latency: acceptance đổi sang đo transport overhead (**1.4ms** < 50ms) + sanity 500ms — pipeline <100ms vẫn do test hiện có enforce; lý do chi tiết trong plan + issue comment.
- Full suite còn 1 flaky pre-existing (`test_rule_path_under_100ms`, commit 9b41269) — không liên quan diff.

## KẾT LUẬN
**PASS** — Độ tự tin: **Cao**
