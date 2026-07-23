# Plan — GH-84: Prescription — Event-driven hardening: idempotency cache, rate-limit guard, observability (bổ trợ GH-23)

## Metadata
- **Status:** PLANNING | **Role:** AI | **Ngày:** 2026-07-22
- **Issue:** #84 — https://github.com/GSU26SE55/ai-module/issues/84
- **Sprint:** không có milestone gán trên issue

## Mục tiêu

GH-23 định nghĩa contract `BatteryAnomalyDetectedEvent → /prescribe → auto ticket`. Ở chế độ event-driven, cùng 1 bất thường có thể bắn event trùng/burst (retry MassTransit, nhiều reading liên tiếp cùng cảnh báo) → mỗi call `enrich=true` tốn 1 lượt LLM (quota DeepSeek/Gemini) + vài giây latency, ticket có thể nhận prescription khác nhau cho cùng 1 trạng thái pin. Thêm 3 lớp hardening cho `/prescribe`: (1) idempotency cache theo TTL, (2) rate-limit/budget guard cho LLM call, (3) observability (structured log + counters qua `/health`).

## Scope

**Trong scope:**
- Idempotency cache in-process (dict + TTL + LRU bound), key = hash(battery_id, readings, enrich, agentic), response thêm field `cached: bool`, không cache khi `blocked=True`.
- Rate-limit: giới hạn concurrent enrich (semaphore, 2) + budget/giờ (env `LLM_HOURLY_BUDGET`, default 60) — vượt budget → degrade rule-based, tái dùng nhánh "no provider key" sẵn có trong `_enrich()`, không tạo path lỗi mới.
- Structured log 1 dòng/request + counters JSON qua `/health` mở rộng (không thêm dependency — không Prometheus client).
- Field `cached` thêm vào proto (field mới `= 27`, không đổi field cũ) + REST schema + gRPC mapping.
- Test cache hit/miss/expire/LRU, budget exhausted, concurrent semaphore, counters snapshot.
- Benchmark xác nhận batch path (rule-only) vẫn <500ms — hot-path không đổi.

**Ngoài scope:**
- Redis/distributed cache (single-instance đủ cho scope capstone).
- Queue/async worker cho enrich.
- Đổi contract GH-23 hay code .NET phía BE.
- Per-provider budget cap (chỉ có 1 budget tổng, không tách theo provider) — xem giả định bên dưới.

## Approach

**1. Idempotency cache** — module mới `src/services/prescription/observability.py`:
- Key: `hashlib.sha256(json.dumps([battery_id, readings, enrich, agentic], sort_keys=True).encode()).hexdigest()`.
- Store: `OrderedDict[key] -> (expires_at, response_dict)`, TTL = 600s (10 phút, đúng đề xuất issue — cùng window 30 reading thì trạng thái pin không đổi), maxsize = 256 (LRU evict khi đầy) — hằng số module, không cần env (issue không yêu cầu configurable).
- `run_prescription()` (orchestrator.py) đổi thành wrapper: logic hiện tại giữ nguyên dưới tên `_run_prescription_uncached(...)`; hàm `run_prescription()` mới: build key → cache hit (chưa hết TTL) → trả `{**cached, "cached": True}`; miss → gọi `_run_prescription_uncached` → **chỉ lưu cache nếu `result["blocked"] is False`** (đúng yêu cầu "KHÔNG cache khi blocked") → gắn `"cached": False` → trả kết quả.
- Thread-safe bằng 1 `threading.Lock` bọc quanh get/set (dict thao tác không atomic, REST + gRPC có thể gọi đồng thời cùng 1 process).
- Tests cần reset cache giữa các case → `observability.py` expose thêm hàm `reset()` (clear cache + counters), dùng trong test fixture — không phá lazy-singleton pattern hiện có (giống `_get_retriever()`/`_get_history_store()`).

**2. Rate-limit / budget guard** — **giả định quan trọng (xin xác nhận ở mục Câu hỏi):** guard đặt ở **mức 1 lần `_enrich()` invocation** (orchestrator.py), KHÔNG đặt sâu trong từng provider call của `chain.py`. Một lượt `enrich=true` (dù nội bộ có 1-2 network round-trip: query-gen GH-82 + generate) tính là 1 "LLM call" tiêu 1 slot semaphore + 1 đơn vị budget. Lý do chọn cách này thay vì bọc từng provider attempt trong `chain.py`:
  - Giữ blast radius nhỏ — không sửa `chain.py` (không đụng 3 hàm `generate_prescription`/`generate_queries`/`judge_safety`), chỉ sửa 1 điểm ở `_enrich()`.
  - Khớp với business intent của issue: mục tiêu là chặn *burst request trùng* tốn quota, không phải giới hạn nội bộ số lần retry trong 1 request.
- Cơ chế: `threading.Semaphore(2)` + `deque` timestamp các lần enrich được phép trong 1 giờ gần nhất (rolling window, không phải fixed clock-hour) so với `LLM_HOURLY_BUDGET` (env, default 60).
- Vị trí check trong `_enrich()`: ngay sau nhánh `if not chain.is_available(): return result` hiện có (dòng ~242-244) — thêm 1 check tương tự: nếu budget hết → log warning + `return result` (giữ nguyên rule-based, y hệt nhánh "no provider key"), không tạo response lỗi mới. Nếu budget còn → acquire semaphore (non-blocking `acquire(blocking=False)`; nếu không lấy được slot ngay do đã đủ 2 concurrent → coi như hết slot, degrade rule-based luôn, KHÔNG xếp hàng chờ — đúng yêu cầu "không xếp hàng chờ vô hạn") → chạy tiếp query-gen + generate như cũ → `finally: release()`.
- Giới hạn phạm vi (single-instance, giống cache): semaphore/budget là in-memory per-process — nếu deploy nhiều worker process, cap không cộng dồn across process. Ghi chú này vào docstring, không cần ADR riêng (đã cùng caveat với cache, issue đã chấp nhận).

**3. Observability** (`observability.py` + `orchestrator.py` + `chain.py` nhỏ):
- `chain.py::generate_prescription()` — thêm 1 dòng: trả kèm `"chain_attempted": [tên provider đã thử, kể cả fail] `, để log/metric biết "fallback tier đã đi qua" (hiện tại chỉ trả `"provider"` của provider THÀNH CÔNG, không biết đã fail qua tier nào trước đó). Đây là thay đổi bổ sung (additive), không đổi field cũ, không breaking.
- Counters (`observability.py`, thread-safe dict + lock): `prescribe_total`, `enrich_success_total`, `cache_hit_total`, `cache_miss_total`, `blocked_total`, `budget_exhausted_total`, và `fallback_tier_counts` (Counter theo từng tên provider xuất hiện trong `chain_attempted`).
- Structured log 1 dòng/request trong `run_prescription()` (sau khi có kết quả cuối, trước return): `battery_id`, `enrich`, `llm_provider`, `chain_attempted`, `rag_ms`, `llm_ms`, `total_ms` (đo quanh toàn bộ `_run_prescription_uncached`), `cached`, `blocked`.
- `/health` (`src/routers/health.py`) mở rộng thêm field `prescription_metrics: dict` = snapshot từ `observability.py`: `{"prescribe_total", "enrich_success_rate", "cache_hit_rate", "fallback_tier_counts", "llm_budget_remaining"}` — tính tỉ lệ tại thời điểm gọi (không lưu sẵn rate, tránh chia 0 khi `prescribe_total == 0` → trả `0.0`).

## Edge Cases

- `prescribe_total == 0` khi gọi `/health` lần đầu (chưa có request nào) → mọi rate = `0.0`, không chia-cho-0.
- Cache key trùng nhưng request đến gần lúc TTL hết hạn đúng lúc 2 thread đọc/ghi đồng thời → Lock bọc toàn bộ get-check-set (không tách rời check và set).
- Budget hết đúng lúc nhiều request đến đồng thời (race đếm) → Lock chung cho budget deque, không dùng riêng lock cho semaphore và budget (2 lock riêng dễ deadlock nếu thứ tự acquire lộn xộn — dùng 1 lock bảo vệ cả đếm budget, semaphore riêng theo `threading.Semaphore` (đã atomic sẵn)).
- `readings` list-of-list float → `json.dumps` cần deterministic order (đã là list nên thứ tự giữ nguyên, không cần `sort_keys` cho phần readings — chỉ cần cho dict ngoài cùng nếu có).
- Response từ cache phải **giống hệt** response gốc trừ field `cached` — không tính lại `total_ms`/timestamp field nào (kiểm tra hiện tại response không có trường timestamp động ngoài `*_ms` — các field `*_ms` cũng nên giữ nguyên từ lần tính gốc, không tính lại lúc cache hit, để test "response bằng nhau" pass đúng nghĩa).

## Success Criteria

| Tiêu chí (map AC issue) | Cách verify |
|---|---|
| 2 call giống hệt trong TTL → 1 lần LLM thật, lần 2 `cached=true`, response bằng nhau | Test: mock `chain.generate_prescription` đếm call count == 1 sau 2 lần gọi `run_prescription` giống hệt tham số |
| Vượt LLM budget → rule-based + log, không 5xx | Test: set budget=0 (hoặc giả lập đã dùng hết), gọi enrich=true → response `enriched=False`, `llm_provider="none"`, không raise |
| `/health` trả counters đúng sau chuỗi call test | Test: gọi `run_prescription` vài lần theo kịch bản cố định → assert `/health` numbers khớp |
| Batch path (rule-only) benchmark <500ms; hot-path không đổi | Chạy lại `scripts/benchmark_grpc.py --real-weights`, so với số cũ (54.1ms/72.4ms) — cache/budget check thêm overhead nhỏ, phải vẫn <500ms |
| Test đủ: cache hit/miss/expire, budget exhausted, concurrent semaphore | `tests/test_observability.py` — từng case riêng, dùng `observability.reset()` giữa các test |
| `pytest --cov=src` toàn repo PASS, coverage ≥ 85% | Chạy full suite trước khi đóng issue |

## Files

| File | Action | Ghi chú |
|------|--------|---------|
| `src/services/prescription/observability.py` | create | Cache (TTL+LRU dict), budget/semaphore guard, counters — module-level lazy state, hàm `reset()` cho test |
| `src/services/prescription/orchestrator.py` | modify | `run_prescription()` → wrapper cache quanh `_run_prescription_uncached`; `_enrich()` → check budget/semaphore trước khi gọi `chain.*`; structured log 1 dòng cuối `run_prescription()` |
| `src/services/prescription/llm/chain.py` | modify | `generate_prescription()` trả thêm `"chain_attempted": [...]` (additive, không đổi field cũ) |
| `src/schemas/prescribe.py` | modify | `PrescribeResponse.cached: bool = False` |
| `protos/ai_service.proto` | modify | Thêm `bool cached = 27;` trong `PrescribeResponse` (field mới, field number tiếp theo sau 26) |
| `src/grpc_gen/` | regenerate | Chạy `python scripts/gen_proto.py` sau khi sửa proto — commit lại stub |
| `src/grpc_server.py` | modify | Map field `cached` từ dict response sang `PrescribeResponse` proto (giống pattern các field khác) |
| `src/routers/health.py` | modify | Thêm `prescription_metrics` vào response `/health`, đọc từ `observability.py` |
| `tests/test_observability.py` | create | Test cache hit/miss/expire/LRU, budget exhausted, concurrent semaphore, counters snapshot |
| `tests/test_grpc_server.py` | modify | Test contract: 2 call giống hệt qua gRPC → lần 2 `cached=true` |
| `docs/ai-be-integration.md` | modify | Cập nhật ghi chú GH-84 (hiện đang ghi "chưa có") → mô tả field `cached` mới cho BE biết |

## Steps

- [ ] Bước 1: Đọc kỹ `src/services/prescription/llm/chain.py` toàn bộ (đã đọc 100 dòng đầu, cần xác nhận `generate_queries`/`judge_safety` không bị ảnh hưởng bởi thay đổi `generate_prescription`) trước khi sửa
- [ ] Bước 2: Viết `src/services/prescription/observability.py` (cache + budget/semaphore + counters + `reset()`)
- [ ] Bước 3: Sửa `orchestrator.py` — wrapper cache cho `run_prescription()`, budget/semaphore check + structured log trong `_enrich()`/`run_prescription()`
- [ ] Bước 4: Sửa `chain.py::generate_prescription()` thêm `chain_attempted`
- [ ] Bước 5: Thêm field `cached` — proto, regenerate stub, `schemas/prescribe.py`, `grpc_server.py` mapping
- [ ] Bước 6: Mở rộng `/health` với `prescription_metrics`
- [ ] Bước 7: Viết `tests/test_observability.py` + test contract gRPC trong `test_grpc_server.py`
- [ ] Bước 8: Chạy `scripts/benchmark_grpc.py --real-weights` xác nhận rule-path vẫn <500ms, cập nhật `docs/ai-be-integration.md`
- [ ] Bước 9: `pytest --cov=src` toàn repo + `ruff check` — PASS, coverage ≥85%

## Câu hỏi đã giải đáp / giả định cần xác nhận

1. **Semaphore/budget ở mức nào?** — Giả định: 1 lần `_enrich()` = 1 slot/1 đơn vị budget (không tách theo từng provider attempt trong `chain.py`). Nếu bạn muốn giới hạn chính xác từng network call (kể cả query-gen riêng generate riêng), cần sửa sâu hơn vào `chain.py` (3 hàm) — approach ở trên sẽ đổi.
2. **"Budget đếm theo provider" (GH-79, mục Liên quan)** — hiểu là counter `fallback_tier_counts` (observability #3) chứ KHÔNG phải `LLM_HOURLY_BUDGET` tách riêng theo từng provider — chỉ có 1 budget tổng dùng chung. Nếu ý issue là budget riêng theo provider (vd DeepSeek 60/h, Gemini 60/h riêng), cần đổi thiết kế.
3. **Cache TTL/maxsize không qua env** — 600s/256 entries là hằng số cố định, vì issue chỉ yêu cầu `LLM_HOURLY_BUDGET` configurable qua env, không nói TTL cache. Nếu muốn cache TTL cũng qua env, thêm dễ dàng ở bước 2.
