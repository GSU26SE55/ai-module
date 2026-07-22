# Plan — GH-23: Phase 3 — Tích hợp Prescription vào BE/ITIL (BatteryAnomalyDetectedEvent → /prescribe → auto ticket)

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-07-21
- **Issue:** #23 — https://github.com/GSU26SE55/ai-module/issues/23
- **Sprint:** Sprint 4 (due 2026-07-11 — đã qua hạn, vẫn triển khai theo yêu cầu hiện tại)
- **Branch:** KHÔNG tạo branch riêng — theo quyết định của user (2026-07-21), làm chung trên `feat/GH-24-ai-phase-4-evaluation` (đang có phiên khác implement GH-24 dở trên cùng working directory). Khi ship, cần tách rõ file của GH-23 vs GH-24 khi `git add`.

## Mục tiêu

Định nghĩa và verify hợp đồng tích hợp AI ↔ BE cho luồng: **IoT → BE → AI (gRPC Predict) → nếu bất thường → BE gọi AI (gRPC Prescribe) → BE map response thành ticket ở TicketService → trả kết quả về BE**. Deliverable chính là tài liệu hợp đồng `docs/ai-be-integration.md` cho BE dev implement consumer, cộng với test + benchmark xác nhận `/Prescribe` phục vụ tốt call pattern này. Không code phía .NET (thuộc role BE, ticket riêng).

## Scope

**Trong scope:**
- `docs/ai-be-integration.md`: event schema `BatteryAnomalyDetectedEvent` → gRPC `PrescribeRequest` mapping → `PrescribeResponse` field reference → gợi ý map field sang ticket (priority, action_steps, human_verification_required, ppe_required, safety_warnings, escalation_conditions) + ví dụ payload request/response đầy đủ.
- Xác nhận **gRPC `Prescribe` (unary, đã có từ GH-40)** là contract chính cho luồng này — REST `/prescribe` chỉ ghi chú là dev/backup, theo `grpc-is-production-transport`.
- Xác nhận **`enrich=false`** (rule-based, <100ms) là chế độ đúng cho auto-ticket path — `enrich=true` (LLM/RAG, off hot-path) là path tương tác/thủ công riêng, KHÔNG nằm trong contract event-driven này.
- Làm rõ semantics field `priority` (P1/P2/P3): đây là **tín hiệu urgency AI đề xuất** dựa trên severity (health_stage/anomaly_status/warning) — KHÔNG phải Priority cuối cùng của ticket. BE tự kết hợp với `ImpactScope` đã biết qua Priority Matrix (Impact × Urgency, `design.md`) để chốt Priority thật; Manager triage vẫn là nơi quyết định cuối, giữ đúng Priority Policy hiện có.
- Docstring update (comment-only) ở `RiskInfo.priority` / `PrescribeResponse.priority` / proto để phản ánh đúng semantics trên.
- Test contract integration: giả lập input dạng payload xuất phát từ anomaly event → gọi gRPC `Prescribe(enrich=false)` → assert response có đủ field BE cần để map ticket.
- Verify benchmark batch path (`enrich=false`) < 500ms theo SLA `ai.md` — dùng `scripts/benchmark_grpc.py` đã có sẵn (đã benchmark "Prescribe (rule path)"), không viết script mới.

**Ngoài scope:**
- Code .NET phía TicketService/BatteryService (role BE, issue riêng ở repo BE).
- Idempotency cache / rate-limit / observability cho `/prescribe` — thuộc **GH-84** (companion issue, dedup bằng `hash(battery_id, readings, enrich, agentic)`, không liên quan `anomaly_event_id`).
- LLM/RAG enrichment (`enrich=true`) trong auto-ticket flow.
- Tạo issue mới ở repo BE (theo quyết định của bạn — chỉ để lại note nhắc thủ công).
- Thêm field mới vào proto / đổi field number.
- Logic ma trận Impact × Urgency (thuộc BE).

## Approach

- **Data flow (sửa sau khi đọc `docs/grpc-integration-be.md`, khuyến nghị GH-87):** `BatteryService` (BE) phát `BatteryAnomalyDetectedEvent` → BE gọi AI **`Prescribe(battery_id, readings, pack_config, enrich=false)`** (gRPC) **một lần duy nhất** — KHÔNG gọi `Predict` riêng trước, vì gọi 2 lần trên cùng window sẽ chạy MC Dropout 2 lần độc lập → `health_stage`/`anomaly_status` có thể lệch nhau giữa 2 response. `Prescribe` đã chạy `Predict` nội bộ (nested `prediction`/`anomaly`/`risk` — GH-87) nên luôn đủ dữ liệu. BE check `anomaly.anomaly_status` trong response: `"Normal"` → không tạo ticket (bỏ qua); `"Warning"`/`"Anomaly"` → tạo ticket, map:
  - `risk.priority` → input Urgency gợi ý cho Priority Matrix phía BE (không phải Priority cuối)
  - `action_steps` → nội dung maintenance log ban đầu của ticket
  - `human_verification_required` → cờ ticket cần kỹ thuật viên xác nhận
  - `ppe_required` / `safety_warnings` → hiển thị cảnh báo an toàn trên ticket
  - `escalation_conditions` → điều kiện escalate tham khảo
- `enrich=false` là default và ĐÚNG cho auto-ticket path; `enrich=true` là tính năng tương tác riêng (vd nút "AI gợi ý chi tiết" trên UI kỹ thuật viên), không thuộc contract event-driven này — vì latency vài giây (LLM call) không hợp với path đồng bộ ngay sau khi nhận event.
- Idempotency/dedup **không** thuộc GH-23 — doc chỉ trỏ sang GH-84, không thêm field hay logic dedup ở đây.

## Edge Cases

- `Prescribe` trả `anomaly.anomaly_status = "Normal"` → BE không tạo ticket, chỉ bỏ qua response (ghi rõ trong doc — hành vi phía BE, không phải code AI).
- `Prescribe` lỗi nội bộ → gRPC `INTERNAL` abort (đã có sẵn trong `grpc_server.py`) — doc hướng dẫn BE nên retry/log/alert thế nào, không tự tạo ticket rỗng.
- `pack_config` không gửi (pin 1 cell) → vẫn chạy bình thường, `n_series=1` mặc định (đã có từ GH-65/67).
- `battery_id` rỗng/không hợp lệ → validation đã có sẵn ở `PredictRequest`/proto, không cần thêm.

## Acceptance Criteria

- [x] `docs/ai-be-integration.md` mô tả đủ: event schema, gRPC `Prescribe` request/response field reference, ví dụ payload đầy đủ, bảng field → ticket mapping, và ghi rõ `priority` = tín hiệu urgency gợi ý (không phải Priority cuối)
- [x] Docstring `RiskInfo.priority` (predict.py) + `PrescribeResponse.priority` (prescribe.py) + proto comment cập nhật đúng semantics
- [x] Test contract integration mới PASS: input dạng anomaly-event-shaped → `Prescribe(enrich=false)` qua gRPC → response có đủ field cần cho ticket mapping
- [x] Benchmark xác nhận batch path (`enrich=false`) < 500ms — 54.1ms avg / 72.4ms p95 (real weights v1.6) — số liệu ghi vào doc
- [x] `pytest --cov=src` toàn bộ suite PASS, coverage ≥ 85% — 512 passed, 92%

## Files

| File | Action | Ghi chú |
|------|--------|---------|
| `docs/ai-be-integration.md` | create | Hợp đồng chính — event schema, gRPC contract, field mapping, ví dụ, priority semantics |
| `src/schemas/predict.py` | modify | Docstring `RiskInfo.priority` — nêu rõ đây là urgency signal, không phải Priority cuối |
| `src/schemas/prescribe.py` | modify | Docstring `PrescribeResponse.priority` — cùng nội dung |
| `protos/ai_service.proto` | modify | Comment cho field `priority` trong `PrescribeResponse` (chỉ sửa comment, không đổi field number) |
| `tests/test_grpc_server.py` | modify | Thêm test contract: payload dạng anomaly-event → `Prescribe(enrich=false)` → assert field mapping + response shape |

## Steps

- [x] Bước 1: Viết `docs/ai-be-integration.md` (event schema, gRPC contract, field mapping, ví dụ payload, priority semantics) — 2026-07-21
- [x] Bước 2: Cập nhật docstring `RiskInfo.priority` (predict.py) + `PrescribeResponse.priority` (prescribe.py) + proto comment (`ai_service.proto`, cả RiskInfo message và flat field) — 2026-07-21 (comment-only, không cần regen stub — .pyi hiện không mang theo proto comment)
- [x] Bước 3: Viết test contract integration mới trong `test_grpc_server.py` (tái dùng fixture `grpc_stub`, `_LFP_PACK_READINGS` có sẵn) — 2026-07-21, PASS
- [x] Bước 4: Chạy `scripts/benchmark_grpc.py --real-weights` (v1.6) — Prescribe rule-path avg 54.1ms / p95 72.4ms, PASS <500ms, ghi vào doc — 2026-07-21
- [x] Bước 5: Full test suite `pytest --cov=src` PASS — 512 passed, coverage 92% (≥85%) — 2026-07-21 (bao gồm cả test của GH-24 đang dở trong cùng working directory, không xung đột)

## Câu hỏi đã giải đáp

1. **Transport:** gRPC `Prescribe` là contract chính cho luồng auto-ticket (REST là dev/backup) — khớp với thực tế BE dùng gRPC production.
2. **Enrich mode:** auto-ticket path dùng `enrich=false` (rule-based, <100ms); `enrich=true` (LLM/RAG) là path tương tác/thủ công riêng, không nằm trong contract event-driven.
3. **Priority semantics:** field `priority` (P1/P2/P3) do AI trả về là tín hiệu urgency gợi ý — BE tự áp Priority Matrix (Impact × Urgency) để ra Priority cuối, giữ nguyên Priority Policy (`design.md`): chỉ Manager triage mới chốt Priority.
4. **BE-side issue:** không tạo issue ở repo BE trong lúc thực hiện GH-23 — chỉ để lại note nhắc thủ công cho bạn tự phối hợp sau.
