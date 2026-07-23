# Plan — GH-105: Prescription — Wire ticket_history + battery-scoped past-case retrieval

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-07-23
- **Issue:** #105 — https://github.com/GSU26SE55/ai-module/issues/105
- **Sprint:** Sprint 6 (due 2026-08-08)

## Mục tiêu

`ticket_history` đã tồn tại full-stack trong contract (`proto` field 5, `schemas/prescribe.py`, `grpc_server.py`, `routers/prescribe.py`) nhưng chưa từng được dùng — dừng lại ở `**context_kwargs` của `_run_prescription_uncached()` với docstring "(reserved)". Việc này nối nốt phần còn thiếu: đưa `ticket_history` vào diagnosis statement (context cho LLM), và ưu tiên case tương tự của **chính battery đó** khi lấy few-shot context (`retrieve_similar_accepted`), thay vì chỉ tìm toàn cục.

## Scope

**Trong scope:**
- `build_diagnosis_statement()` (`diagnosis.py`) nhận thêm `ticket_history`, render 1 dòng thứ 4 khi non-empty.
- `_enrich()` / `_run_prescription_uncached()` (`orchestrator.py`) forward `battery_id` + `ticket_history` xuống đúng chỗ.
- `retrieve_similar_accepted()` (`history_store.py`) nhận `battery_id`, ưu tiên case cùng battery, fallback toàn cục nếu battery đó chưa có case accepted nào.
- `observability.cache_key()` (GH-84) thêm `ticket_history` vào hash — tránh cache-hit sai khi ticket_history đổi nhưng battery_id/readings/enrich/agentic giữ nguyên.
- Note ngắn format `ticket_history` trong `docs/ai-be-integration.md` (không cần ADR riêng — đã xác nhận với user, vì không đổi wire contract).
- Test cho cả 2 luồng + tương tác cache.

**Ngoài scope:**
- Đổi proto/schema (field đã tồn tại sẵn, không cần field mới).
- BE gửi ticket_history thế nào (TicketService phía .NET) — chỉ viết docs contract.
- Top-up past_cases cho đủ `top_k` khi battery-scoped có kết quả nhưng ít hơn `top_k` (dùng fallback nhị phân đơn giản — xem Approach #4).
- age_cycles / last_maintenance_date (vẫn "reserved", không thuộc issue này).

## Approach

1. **Diagnosis statement — dòng thứ 4:** `build_diagnosis_statement(prediction, anomaly, risk, warnings, ticket_history: list[str] | None = None)`. Nếu `ticket_history` non-empty: lấy **5 phần tử cuối** (giả định BE gửi theo thứ tự chronological oldest→newest — ghi rõ giả định này trong docstring + docs contract, vì chưa xác nhận được với BE), nối bằng `"; "`, thêm dòng `f"Past repairs on this battery: {joined}."`. Rỗng/None → không render dòng này (nhất quán với cách `past_cases` xử lý rỗng ở GH-83) — hằng số `TICKET_HISTORY_MAX_LINES = 5` module-level trong `diagnosis.py`.
2. **Threading qua orchestrator:** `_enrich()` thêm 2 param trailing `battery_id: str = ""`, `ticket_history: list[str] | None = None` (không phá vị trí positional args hiện có — các test gọi `_enrich(pred, risk, warnings, rule_out)` positional vẫn chạy nguyên). `_run_prescription_uncached()` gọi `_enrich(..., battery_id=battery_id, ticket_history=context_kwargs.get("ticket_history"))`.
3. **battery_id-scoped past cases:** `retrieve_similar_accepted(self, context, battery_id: str | None = None, top_k: int = 2)`. Nếu có `battery_id`: query 1 lần với `where={"$and": [{"feedback_status": "accepted"}, {"battery_id": battery_id}]}` (dùng lại embedding đã encode, không encode 2 lần); nếu kết quả rỗng → query lại như cũ (`where={"feedback_status": "accepted"}`, không lọc battery). Không `battery_id` (None) → giữ nguyên hành vi cũ hệt (test cũ không cần sửa). **Fallback nhị phân, không top-up** — nếu battery-scoped trả về ít nhất 1 kết quả thì dùng luôn, dù ít hơn `top_k` (đúng theo yêu cầu gốc, đơn giản nhất, tránh merge/dedup phức tạp không cần thiết).
4. **Cache key (phát hiện khi audit code, ngoài 2 việc gốc nhưng ảnh hưởng đúng-sai trực tiếp):** `observability.cache_key()` thêm param `ticket_history: list | None = None` vào payload hash. Call site trong `run_prescription()` đổi thành `observability.cache_key(battery_id, readings, enrich, agentic, context_kwargs.get("ticket_history"))`. Không đổi `age_cycles`/`last_maintenance_date` vào key vì 2 field đó vẫn chưa được dùng ở downstream (không ảnh hưởng response).
5. **Docs:** `docs/ai-be-integration.md` thêm đoạn ngắn: field `ticket_history` đã có sẵn từ trước, nay AI module bắt đầu sử dụng — mỗi string nên là 1 dòng tóm tắt ngắn (vd `"2026-06-10: Replaced BMS fuse after overvoltage alert, resolved"`), thứ tự **oldest→newest**, AI chỉ dùng tối đa 5 dòng cuối — BE gửi nhiều hơn cũng không sao (bị cắt phía AI).

## Edge Cases

- `ticket_history=None` hoặc `[]` → không render dòng "Past repairs", không lỗi (giữ nguyên diagnosis 3 dòng như hiện tại — không phá test cũ).
- `ticket_history` dài hơn 5 → chỉ lấy 5 phần tử cuối, không lỗi.
- `battery_id` chưa có case accepted nào → fallback query toàn cục, không lỗi, không rỗng oan nếu toàn cục có case.
- `battery_id=None`/`""` truyền vào `retrieve_similar_accepted` → bỏ qua tier battery-scoped, y hệt hành vi cũ.
- ChromaDB lỗi ở tier battery-scoped (network/query lỗi) → toàn bộ method vẫn nằm trong try/except hiện có, trả `[]`, không raise (không đổi nguyên tắc best-effort của GH-83).
- Cache: 2 request khác `ticket_history` → `cache_key` khác nhau → cache miss đúng như kỳ vọng, không cần đổi TTL/maxsize.

## Acceptance Criteria

- [ ] `build_diagnosis_statement(..., ticket_history=[...])` trả statement có dòng `"Past repairs on this battery: ..."`; `ticket_history=None`/`[]` → không có dòng này (3 dòng như cũ).
- [ ] `ticket_history` > 5 phần tử → chỉ 5 phần tử cuối xuất hiện trong statement.
- [ ] `retrieve_similar_accepted(ctx, battery_id="B0001")` ưu tiên trả case của B0001 nếu có ≥1 case accepted của B0001; battery đó chưa có case accepted nào → fallback trả case toàn cục (nếu có).
- [ ] `retrieve_similar_accepted(ctx)` (không truyền `battery_id`) hành vi y hệt trước khi sửa — toàn bộ test cũ trong `test_prescription_history.py` PASS không sửa.
- [ ] 2 lần gọi `run_prescription()`/`/prescribe` cùng `battery_id`/`readings`/`enrich`/`agentic` nhưng khác `ticket_history` → `cache_key` khác nhau → không cache-hit lẫn nhau.
- [ ] `enrich=false` (rule-path) không đổi latency — `ticket_history`/`battery_id` chỉ chạm nhánh `enrich=true`.
- [ ] Toàn bộ test cũ liên quan prescription (diagnosis, hybrid, history, observability, grpc parity) PASS không sửa đổi hành vi cũ.
- [ ] `docs/ai-be-integration.md` có note format `ticket_history` (ví dụ cụ thể + giả định thứ tự chronological + cap 5).
- [ ] `pytest --cov=src` toàn repo PASS, coverage ≥ 85%.

## Files

| File | Action | Ghi chú |
|------|--------|---------|
| `src/services/prescription/diagnosis.py` | modify | `build_diagnosis_statement()` thêm param `ticket_history`, hằng số `TICKET_HISTORY_MAX_LINES = 5`, render dòng 4 |
| `src/services/prescription/orchestrator.py` | modify | `_enrich()` thêm `battery_id`/`ticket_history`; `_run_prescription_uncached()` forward xuống `_enrich()`; `run_prescription()` cache key thêm `ticket_history` |
| `src/services/prescription/history_store.py` | modify | `retrieve_similar_accepted()` thêm `battery_id`, 2-tier query (battery-scoped → fallback global) |
| `src/services/prescription/observability.py` | modify | `cache_key()` thêm param `ticket_history` vào hash payload |
| `docs/ai-be-integration.md` | modify | Note format `ticket_history` cho BE |
| `tests/test_rag_services.py` | modify | Test `build_diagnosis_statement(ticket_history=...)` — có/rỗng/vượt N=5 |
| `tests/test_hybrid_prescription.py` | modify | Test `_enrich()` forward `battery_id`/`ticket_history` đúng chỗ |
| `tests/test_prescription_history.py` | modify | Test `retrieve_similar_accepted(battery_id=...)` — hit battery-scoped, fallback global, backward-compat khi không truyền |
| `tests/test_observability.py` | modify | Test `cache_key()` đổi khi `ticket_history` khác nhau |

## Steps

- [x] Bước 1: `diagnosis.py` — thêm `ticket_history` param + render dòng 4 + hằng số cap N=5 — 2026-07-23
- [x] Bước 2: `history_store.py` — `retrieve_similar_accepted()` thêm `battery_id`, 2-tier query nhị phân (không top-up) — 2026-07-23
- [x] Bước 3: `observability.py` — `cache_key()` thêm `ticket_history` vào hash — 2026-07-23
- [x] Bước 4: `orchestrator.py` — thread `battery_id`/`ticket_history` qua `_enrich()` → `build_diagnosis_statement()` + `retrieve_similar_accepted()`; sửa call site `cache_key()` trong `run_prescription()` — 2026-07-23
- [x] Bước 5: `docs/ai-be-integration.md` — note format ticket_history — 2026-07-23
- [x] Bước 6: Viết/sửa test cho cả 4 file trên (diagnosis, history_store, observability, orchestrator/hybrid) — 2026-07-23
- [x] Bước 7: `pytest --cov=src` toàn repo + `ruff check` — PASS, coverage 92% (≥85%) — 2026-07-23
- [x] Bước 8: Benchmark nhanh xác nhận `enrich=false` không đổi latency — `tests/test_prescription.py::TestPrescriptionLatency::test_rule_path_under_100ms` PASS (rule-path không chạm `_enrich()`) — 2026-07-23

## Câu hỏi đã giải đáp

User chọn **"đi theo hướng tối ưu nhất"** cho tất cả 5 điểm nêu ra — quyết định cụ thể:
1. Format/data thật từ BE: chưa xác nhận được — thiết kế hoạt động đúng cả khi rỗng (hiện tại) lẫn khi có data thật sau này; ghi giả định thứ tự chronological vào docs cho BE xác nhận sau.
2. Cap N=5 dòng gần nhất.
3. Chèn dòng 4 sau `Description:`, bỏ qua khi rỗng.
4. Cache key: chọn hướng (A) — thêm `ticket_history` vào hash, ưu tiên đúng hơn stale cache (phát hiện thêm khi audit code, ngoài 2 việc gốc trong issue).
5. Fallback nhị phân (không top-up) cho `retrieve_similar_accepted` — giữ đơn giản, đúng theo yêu cầu gốc.
