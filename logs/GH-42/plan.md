# Plan — GH-42: Test + benchmark gRPC + client demo + share proto cho BE

## Metadata
- **Status:** TESTING | **Role:** AI | **Ngày:** 2026-07-02
- **Issue:** #42 — https://github.com/GSU26SE55/ai-module/issues/42
- **Sprint:** Sprint 4 (chuỗi gRPC: #39 → #40 → #41 → **#42** — bước QA + handoff cuối)

## Mục tiêu
Đóng gói chuỗi gRPC để BE tích hợp được: bổ sung test còn thiếu, benchmark script tái dùng được (chạy dummy weights ngay, re-run khi có weights thật), client demo thay Swagger, docs (README + rules + hướng dẫn BE gen C# client).

## Scope
**Trong scope:**
- **Tests bổ sung** (`tests/test_grpc_server.py`): GH-40/41 đã có 17 test qua channel thật — chỉ thêm phần thiếu: concurrent streams (2 stream song song không lẫn response), Prescribe qua channel thật với dummy models (hiện chỉ có direct-servicer + parity).
- **`scripts/benchmark_grpc.py`** — benchmark tái dùng: unary Predict/Prescribe, stream N windows, transport overhead vs direct pipeline; in bảng kết quả + exit code theo threshold; flag `--real-weights` (mặc định dummy — weights v1.3/v2.2 chưa có, retrain #25 đang chạy).
- **`scripts/grpc_client_demo.py`** — demo client cho bảo vệ/BE tham khảo: Health → Predict 1 window → PredictStream 3 windows → Prescribe; đọc `GRPC_HOST`/`GRPC_PORT` từ env; in kết quả dễ đọc.
- **`docs/grpc-integration-be.md`** — hướng dẫn BE (.NET): copy `protos/ai_service.proto`, `Grpc.Tools` trong `.csproj` (snippet), `csharp_namespace AiModule.V1`, ví dụ C# client unary + stream, semantics cần biết (stream abort sau k−1 responses, insecure port 50051 nội bộ docker, payload 4 features sau ablation GH-25).
- **`README.md`** — thêm section Serving: FastAPI (REST, port 8000) + gRPC (port 50051), cách chạy từng cái, link docs.
- **`.claude/rules/tech/ai.md`** — thêm mục Serving gRPC ngắn (đã chốt: sửa ở đây + note cho leader đưa vào workflow-ai khi sync).
- Comment lên issue #42 tag BE về doc integration.

**Ngoài scope:**
- KHÔNG benchmark số thật với weights v1.3/v2.2 (chưa có — retrain #25; script có sẵn flag để re-run, ghi rõ trong docs)
- KHÔNG sửa server/proto/pipeline — ticket test+docs; nếu benchmark lộ bug thì dừng, báo, mở ticket
- KHÔNG TLS/auth setup (nội bộ docker, đã khai báo từ GH-40)
- KHÔNG viết C# code vào BE repo (chỉ doc + snippet; BE tự gen client)

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `tests/test_grpc_server.py` | modify | +2 test: concurrent streams, Prescribe qua channel |
| `scripts/benchmark_grpc.py` | create | benchmark tái dùng, threshold-aware, `--real-weights` flag |
| `scripts/grpc_client_demo.py` | create | demo 4 RPC, env-config, output dễ đọc |
| `docs/grpc-integration-be.md` | create | hướng dẫn BE gen C# client + semantics |
| `README.md` | modify | section Serving (REST + gRPC) |
| `.claude/rules/tech/ai.md` | modify | mục Serving gRPC ngắn + note leader sync |
| `logs/GH-42/plan.md` | create | file này |

## Approach
- Benchmark script dựng in-process server (port 0) với dummy loader (pattern test) hoặc `load_models()` thật khi `--real-weights`; đo p50/p95/avg cho unary + stream + transport overhead; threshold: overhead <50ms luôn enforce, absolute <100ms chỉ enforce khi `--real-weights` (nhất quán tiền lệ GH-10: SLA enforce trên môi trường deploy).
- Demo client là file standalone chỉ dùng stub + grpcio — BE đọc là hiểu cách gọi; chạy được ngay khi server GH-40 chạy (`python -m src.grpc_server` — cần weights thật) hoặc trỏ vào server test.
- Doc BE viết theo góc nhìn consumer: những gì BE cần biết mà không phải đọc code Python.
- Test concurrent streams: 2 client stream đan xen trên cùng server (ThreadPool) → responses không lẫn battery_id giữa 2 stream.

## Edge Cases
- Benchmark trên máy chậm/tải: threshold absolute chỉ enforce với `--real-weights` (deploy env) — dummy mode chỉ báo cáo, không fail.
- Demo client khi server chưa chạy → message lỗi rõ ràng (connect timeout), không traceback thô.
- Concurrent streams: xác nhận không race/lẫn response (\_MC_LOCK chỉ serialize inference, không giữ thread).

## Acceptance Criteria
- [x] 2 test mới PASS (19 test gRPC server) + suite 177 pass (ruff sạch).
- [x] Benchmark dummy mode PASS: overhead 27.7ms <50ms, bảng p50/p95/avg đủ 4 dòng; `--real-weights` fail đúng với message artifact-not-found rõ ràng.
- [x] Demo 4 RPC chạy OK với dummy server; không server → message thân thiện tiếng Việt (đã fix UTF-8 console Windows), exit 1.
- [x] Doc BE: csproj snippet + ví dụ unary/stream C# + 7 semantics + hướng dẫn chạy local + benchmark tham khảo.
- [x] README section Serving; rules mục Hybrid + marker leader; comment issue #42 (BE handoff + leader note).
- [x] Không đụng `src/` — diff: 2 script mới + doc mới + README + rules + tests.

## Steps
- [x] Bước 1: 2 test bổ sung (concurrent streams, Prescribe qua channel) — suite xanh — 2026-07-02
- [x] Bước 2: `scripts/benchmark_grpc.py` + chạy dummy mode (overhead 27.7ms PASS), ghi số vào docs — 2026-07-02
- [x] Bước 3: `scripts/grpc_client_demo.py` + verify 2 path (no-server friendly error + full demo vs dummy server) — 2026-07-02
- [x] Bước 4: `docs/grpc-integration-be.md` (csproj snippet, ví dụ C#, 7 semantics, benchmark tham khảo) — 2026-07-02
- [x] Bước 5: README section Serving + rules mục Hybrid REST+gRPC (marker cho leader) + comment issue #42 — 2026-07-02
- [x] Bước 6: Verify: ruff sạch + full suite 177 pass (1 flaky pre-existing) + src/ không đụng — 2026-07-02

## Câu hỏi đã giải đáp
- **Benchmark khi chưa có weights thật (hỏi 2026-07-02):** không block — viết benchmark script tái dùng, chạy dummy weights ngay (transport overhead đã đo 1.4ms ở GH-40), threshold absolute <100ms chỉ enforce khi `--real-weights`; re-run khi retrain #25 xong, ghi rõ trong docs.
- **Hình thức share proto:** doc `docs/grpc-integration-be.md` + comment issue — không tạo PR sang BE repo.
- **`.claude/rules/tech/ai.md` sync:** sửa ở repo này theo issue + note trên issue cho leader đưa thay đổi vào workflow-ai (nguồn sync) để không bị ghi đè.
