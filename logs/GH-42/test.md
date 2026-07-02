# TEST REPORT — GH-42 — 2026-07-02

## Scope: AI (QA + handoff gRPC: tests, benchmark, demo client, docs)
## Môi trường: local (Windows 11, Python 3.11.9, venv)

## TÓM TẮT
Full suite **177 pass**, coverage **87%** (`grpc_server.py` 91%). Cả 2 script tooling verify end-to-end (benchmark PASS overhead 27.3ms; demo chạy đủ 4 RPC + friendly error khi không có server). Fail duy nhất là flaky pre-existing quen thuộc. `src/` không đụng.

| Test case | Input | Expected | Actual | Status |
|-----------|-------|----------|--------|--------|
| Concurrent streams | 2 stream đan xen (A-0..2, B-0..2) qua server thật | mỗi client nhận đúng ids của mình, đúng thứ tự | đúng cả 2 | ✅ PASS |
| Prescribe qua channel | PrescribeRequest enrich=false, dummy pipeline | risk/priority hợp lệ, prescription + action_steps không rỗng | đúng toàn bộ | ✅ PASS |
| Suite gRPC server | 19 tests (GH-40/41/42) | xanh | 19/19 PASS | ✅ PASS |
| Full suite + coverage | `pytest tests/ --cov=src` | xanh, ≥85% | 177 pass / **87%** | ✅ PASS |
| Benchmark dummy mode | `benchmark_grpc.py -n 30` | bảng 4 dòng + overhead <50ms, exit 0 | overhead **27.3ms**, RESULT PASS | ✅ PASS |
| Benchmark `--real-weights` | artifacts v1.3 chưa có | fail sớm, message rõ | RuntimeError artifact-not-found đúng path | ✅ PASS |
| Demo — không có server | port 50051 trống | message thân thiện, exit 1, không traceback | đúng (3 dòng hướng dẫn tiếng Việt) | ✅ PASS |
| Demo — có server (dummy) | server 50051 + dummy weights | đủ 4 RPC, exit 0 | Health/Predict/Stream×3/Prescribe OK | ✅ PASS |
| `src/` không đụng | `git status` | chỉ tests/docs/README/rules thay đổi | đúng | ✅ PASS |

## Coverage
- Tổng: **87%** (target ≥85%) — không giảm so với GH-41.
- `src/grpc_server.py`: 91% (chỉ còn `serve()` blocking loop).

## Latency (dummy weights, máy dev CPU — tham khảo)
- Transport overhead: **27.3ms** (<50ms budget) — ổn định với lần đo trước (1.4–28ms tùy tải máy).
- Stream per-window ~117ms ≈ unary ~113ms — không chi phí ẩn.
- Absolute <100ms: enforce khi `--real-weights` trên deploy env (artifacts v1.3/v2.2 chờ retrain #25) — số hiện tại bị MC Dropout ×20 trên CPU tải chiếm ~86–110ms từ trước GH-39.

## Bugs tìm được
- Không có bug mới từ diff GH-42. (Bug UTF-8 console của demo đã bắt & fix trong lúc implement.)
- ⚠️ Flaky pre-existing `test_rule_path_under_100ms` — lần này 1 fail trong full-suite; đề xuất ticket riêng (đã nhắc ở GH-41).

## Checklist bắt buộc (train/preprocess/inference N/A — ticket QA/docs)
- [x] Tests mới chạy thật qua channel — 3/3 PASS
- [x] Tooling verify end-to-end cả happy path lẫn error path
- [x] Docs khớp thực tế đo được (số benchmark trong doc = số chạy thật)
- [x] REST/gRPC server không regression — 177 pass, `src/` nguyên vẹn

## RỦI RO & LƯU Ý
- Khi artifacts v1.3/v2.2 về (retrain #25): chạy `python scripts/benchmark_grpc.py --real-weights` + smoke `python -m src.grpc_server` / `uvicorn main:app` — sẽ ghi vào handoff.
- Leader cần đưa mục Serving trong `.claude/rules/tech/ai.md` vào nguồn sync workflow-ai (note đã có trên issue #42).

## KẾT LUẬN
**PASS** — Độ tự tin: **Cao**
