# Plan — GH-83: Prescription — Long-term memory + human feedback loop

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-07-14
- **Issue:** #83 — https://github.com/GSU26SE55/ai-module/issues/83
- **Sprint:** (không có milestone gán)

## Mục tiêu
Thêm "long-term memory" cho prescription layer (theo Future Work của Deng et al. 2024): mỗi lần `/prescribe` chạy với `enrich=true`, lưu context + kết quả cuối vào 1 vector store riêng; lần enrich sau, nếu tìm được case tương tự đã được technician xác nhận (`feedback_status=accepted`), đưa case đó vào prompt LLM như "Past resolved cases" (chỉ tham khảo, ưu tiên SOP docs). Thêm `POST /prescribe/feedback` để BE ghi nhận feedback (accepted/edited/rejected) sau khi ticket CLOSED.

## Scope
**Trong scope:**
- Store lịch sử prescription riêng biệt (ChromaDB collection mới, path riêng — xem Approach #1).
- Retrieve top-2 case `feedback_status=accepted` làm few-shot context khi `enrich=true` (áp dụng cả agentic lẫn non-agentic path).
- `POST /prescribe/feedback` (REST) — cập nhật `feedback_status` theo `prescription_id`.
- `prescription_id` (uuid) thêm vào `PrescribeResponse` (REST + proto field 23, cả 2 transport phải parity).
- FIFO evict khi vượt N=500 record.
- Docs contract cho BE (file riêng).

**Ngoài scope:**
- gRPC RPC riêng cho feedback endpoint (chỉ REST — xem Approach #4). Có thể làm ở issue sau nếu BE cần.
- BE/.NET code (TicketService gọi feedback khi CLOSED) — chỉ viết contract/docs, không code BE.
- Đổi cơ chế feedback thành flow ITIL thật (đó là GH-23).
- Dùng history data build golden set eval (đó là GH-24).

## Endpoints
| Method | Path | Request | Response |
|--------|------|---------|----------|
| POST | `/prescribe/feedback` | `{prescription_id: str, status: "accepted"\|"edited"\|"rejected", edited_steps?: list[str], note?: str}` | `{success: bool}` — 404 nếu `prescription_id` không tồn tại (hoặc store không sẵn sàng) |

`POST /prescribe/` (đã có) — thêm field `prescription_id` vào response, không đổi request.

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/services/prescription/history_store.py` | create | `PrescriptionHistoryStore`: `save()`, `retrieve_similar_accepted()`, `update_feedback()`, FIFO evict N=500. ChromaDB `PersistentClient` **riêng** tại `models/prescription_history/` (không phải `models/embeddings/`). Constructor nhận `path` override (seam cho test). Lazy import chromadb+sentence-transformers, `_ready=False` graceful nếu thiếu. |
| `.gitignore` | modify | Thêm `models/prescription_history/` — không commit (runtime data tích luỹ, khác bản chất KB tĩnh GH-80). |
| `src/services/prescription/llm/base.py` | modify | Thêm `format_past_cases()` (mirror `format_docs`); `build_user_content()` thêm param `past_cases: list[dict] \| None = None`, render section "Past resolved cases"; `SYSTEM_PROMPT` thêm rule disclaimer (past cases chỉ tham khảo, ưu tiên SOP docs khi mâu thuẫn). |
| `src/services/prescription/llm/anthropic_provider.py` | modify | `generate_prescription()` thêm param `past_cases`, forward vào `build_user_content()`. |
| `src/services/prescription/llm/deepseek_provider.py` | modify | Tương tự anthropic_provider. |
| `src/services/prescription/llm/gemini_provider.py` | modify | Tương tự anthropic_provider. |
| `src/services/prescription/llm/chain.py` | modify | `generate_prescription()` thêm param `past_cases`, forward xuống provider. |
| `src/services/prescription/orchestrator.py` | modify | `_get_history_store()` lazy singleton (mirror `_get_retriever()`); trong `_enrich()`: build `diagnosis` **unconditional** (không chỉ khi `agentic=True` như hiện tại) để dùng làm context cho cả query-gen (agentic) lẫn history retrieve; gọi `history_store.retrieve_similar_accepted(diagnosis, top_k=2)` trước khi gọi LLM, forward `past_cases` vào `chain.generate_prescription(...)`; trả `diagnosis` trong dict kết quả. Trong `run_prescription()`: sau khi block-path xử lý xong (để lưu đúng nội dung **cuối cùng** đã trả, không lưu bản LLM bị block), nếu `enrich=True` → gọi `history_store.save(...)` lấy `prescription_id`; thêm `prescription_id` (mặc định `""` khi `enrich=False`) vào response dict. |
| `src/schemas/prescribe.py` | modify | `PrescribeResponse` thêm `prescription_id: str = ""`. Thêm `PrescriptionFeedbackRequest` (`prescription_id: str`, `status: Literal["accepted","edited","rejected"]`, `edited_steps: list[str] \| None = None`, `note: str \| None = None`) và `PrescriptionFeedbackResponse` (`success: bool`). |
| `src/routers/prescribe.py` | modify | Thêm `POST /prescribe/feedback` → gọi `submit_prescription_feedback()`; `HTTPException(404)` khi không tìm thấy. |
| `src/services/prescription/__init__.py` | modify | Export thêm `submit_prescription_feedback`. |
| `protos/ai_service.proto` | modify | `PrescribeResponse` thêm `string prescription_id = 23;`. Không thêm RPC/message mới cho feedback (REST-only, xem Approach #4). |
| `src/grpc_gen/ai_service_pb2.py` / `.pyi` | regenerate | `python scripts/gen_proto.py` sau khi sửa proto — commit theo convention hiện tại. |
| `src/grpc_server.py` | modify | `Prescribe` handler: thêm `prescription_id=result.get("prescription_id", "")` vào construct `ai_service_pb2.PrescribeResponse(...)`. |
| `tests/test_grpc_server.py` | modify | Cập nhật assertion parity cho field `prescription_id` mới. |
| `tests/test_prescription_history.py` | create | Unit test `PrescriptionHistoryStore`: save/retrieve (chỉ accepted)/evict FIFO N=500/update_feedback (found/not-found)/graceful khi thiếu chromadb — dùng `path=tmp_path` để không đụng store thật. |
| `tests/test_llm_providers.py` | modify | Test `build_user_content` với `past_cases` → chứa "Past resolved cases"; test `SYSTEM_PROMPT` có disclaimer mới; test mỗi provider forward `past_cases` đúng xuống `build_user_content`. |
| `tests/test_hybrid_prescription.py` | modify | Test `_enrich()`: case `accepted` xuất hiện trong context gọi LLM, case `pending`/`rejected` không xuất hiện; test history KHÔNG ghi khi `enrich=False`; test `prescription_id` có giá trị khi `enrich=True`, rỗng khi `enrich=False`. |
| `tests/test_routers.py` | modify | Test `POST /prescribe/feedback`: accepted/edited/rejected 200, `prescription_id` lạ → 404. |
| `docs/prescription-feedback-contract.md` | create | Contract cho BE: `prescription_id` trả về từ `/prescribe/`, khi nào TicketService nên gọi `/prescribe/feedback` (ticket CLOSED, map maintenance log → status), request/response shape, lưu ý REST-only hiện tại. |
| `docs/adr/0004-prescription-long-term-memory.md` | create | ADR: tách store riêng khỏi KB tĩnh committed, chỉ ghi khi `enrich=true` (giữ latency rule-path), N=500 FIFO, REST-only feedback (gRPC parity sau nếu cần). |

## Approach
1. **Store tách biệt khỏi KB tĩnh** — `models/embeddings/chroma.sqlite3` đã commit vào Git và được `test_kb_manifest` kiểm tra (GH-80, static/reproducible). Ghi lịch sử prescription (runtime, tích luỹ liên tục) vào **cùng file** sẽ làm dirty artifact đã commit mỗi lần chạy server/test → phá bất biến "KB tĩnh, tái lập được". Dùng `PersistentClient` thứ 2 tại `models/prescription_history/`, thêm vào `.gitignore`.
2. **Chỉ ghi history khi `enrich=true`** — AC yêu cầu "rule-path /prescribe không đổi latency"; ghi ChromaDB (encode + `collection.add`) tốn thêm compute, không được phép trên hot-path P1 (`enrich=false`, hiện tại "never touches the network" theo docstring `orchestrator.py`). `enrich=false` → `prescription_id=""`, không có record.
3. **N=500, FIFO evict theo timestamp** — hằng số trong `history_store.py` (không qua `.env`, nhất quán với cách `CONTAMINATION`/`N_ESTIMATORS` hiện tại là hằng số code, không phải env).
4. **Feedback endpoint REST-only** — không thêm RPC gRPC mới trong issue này (AC hedge "nếu expose gRPC"); chỉ field `prescription_id` mới trong `PrescribeResponse` (đã có RPC `Prescribe`) mới cần proto + gRPC server + parity test.
5. **Tái dùng `build_diagnosis_statement()` (GH-82) làm "context"** — đã deterministic, không cần LLM, đã có sẵn; build unconditional trong `_enrich()` (hiện chỉ build khi `agentic=True`) để dùng chung cho query-gen VÀ history retrieve/save — tránh viết logic "context" thứ 2.
6. **Lưu sau khi block-path xử lý xong** (trong `run_prescription()`, không phải trong `_enrich()`) — đảm bảo record lưu đúng nội dung **cuối cùng** đã trả cho caller (nếu bị block thì lưu bản rule-based, không lưu bản LLM đã bị chặn).

## Edge Cases
- History rỗng (deploy mới) → `retrieve_similar_accepted` trả `[]`, `format_past_cases([])` không render section (giống `format_docs` hiện tại) → không lỗi.
- `feedback_status` khác `"accepted"` (pending/edited/rejected) → không được dùng làm context, lọc bằng `where={"feedback_status": "accepted"}` khi query.
- `prescription_id` không tồn tại (hoặc lịch sử store lỗi/không sẵn sàng) → `update_feedback()` trả `False` → router trả 404.
- Cùng `battery_id` gọi lặp nhiều lần → mỗi lần 1 uuid4 riêng, không dedup theo battery.
- `chromadb`/`sentence-transformers` chưa cài → `PrescriptionHistoryStore._ready=False`, `save()`/`retrieve_similar_accepted()` no-op (`None`/`[]`), không crash pipeline.
- Ghi history lỗi (disk, exception bất kỳ) → best-effort, log warning, không ảnh hưởng response đã build xong.

## Acceptance Criteria
- [x] Sau 1 lần `/prescribe` (`enrich=true`) + `/prescribe/feedback` `status=accepted`, lần `/prescribe` (`enrich=true`) sau cho case tương tự → prompt LLM chứa "Past resolved cases" (`test_accepted_case_surfaces_as_few_shot_on_next_call`).
- [x] Case `rejected` hoặc chưa feedback (`pending`) không xuất hiện trong context (`test_rejected_case_does_not_surface_as_few_shot`, `test_pending_case_excluded_from_retrieval`, `test_edited_case_excluded_from_retrieval`).
- [x] `POST /prescribe/feedback` đủ test: accepted/edited/rejected → 200; `prescription_id` không tồn tại → 404; status không hợp lệ → 422.
- [x] Hot-path `/predict` và rule-path `/prescribe` (`enrich=false`) không đổi latency — `test_history_not_touched_when_enrich_false` (raise nếu `_get_history_store` bị gọi) + benchmark tay ~8.3ms avg.
- [x] `prescription_id` xuất hiện trong `PrescribeResponse` khi `enrich=true` (uuid hợp lệ), rỗng khi `enrich=false`.
- [x] `test_grpc_server.py` parity xanh với field `prescription_id` mới (33 passed).
- [x] Docs contract BE tồn tại (`docs/prescription-feedback-contract.md`).
- [x] Toàn bộ test cũ (163 test hiện có của prescription layer) vẫn PASS — 243 test prescription-related PASS, 474 test toàn repo PASS, ruff clean.

## Steps
- [x] Bước 1: `history_store.py` — `PrescriptionHistoryStore` (save/retrieve/evict/update_feedback) + unit test `test_prescription_history.py`. — 2026-07-14
- [x] Bước 2: `llm/base.py` — `format_past_cases()` + `build_user_content(past_cases=...)` + `SYSTEM_PROMPT` disclaimer; cập nhật 3 provider + `chain.py` forward `past_cases`; test `test_llm_providers.py`. — 2026-07-14
- [x] Bước 3: `orchestrator.py` — build `diagnosis` unconditional, gọi `history_store.retrieve_similar_accepted()`, forward `past_cases`; `run_prescription()` gọi `history_store.save()` sau block-path, thêm `prescription_id` vào response; `submit_prescription_feedback()`; test `test_hybrid_prescription.py`. — 2026-07-14
- [x] Bước 4: `schemas/prescribe.py` — `prescription_id` field + `PrescriptionFeedbackRequest/Response`. — 2026-07-14
- [x] Bước 5: `routers/prescribe.py` + `services/prescription/__init__.py` — endpoint `POST /prescribe/feedback`; test `test_routers.py`. — 2026-07-14
- [x] Bước 6: `protos/ai_service.proto` (field 23) → `scripts/gen_proto.py` → `grpc_server.py` → `test_grpc_server.py` parity. — 2026-07-14
- [x] Bước 7: `.gitignore` (làm ở Bước 1) + `docs/prescription-feedback-contract.md` + `docs/adr/0004-prescription-long-term-memory.md`. — 2026-07-14
- [x] Bước 8: Chạy full suite prescription-related (163 test cũ + test mới) — PASS (243 test prescription-related, 474 toàn repo); benchmark nhanh xác nhận `enrich=false` không tăng latency (~8.3ms avg, không có write nào tới history store). — 2026-07-14

## Câu hỏi đã giải đáp
1. **Storage path** — tách riêng `models/prescription_history/` (gitignore), không dùng chung `models/embeddings/` (đang là KB tĩnh committed cho `test_kb_manifest`). User chọn theo đề xuất.
2. **Latency hot-path** — chỉ ghi history khi `enrich=true`; `enrich=false` không ghi gì (bảo toàn AC "rule-path không đổi latency"). User chọn theo đề xuất.
3. **FIFO cap** — N=500. User chọn theo đề xuất.
4. **gRPC** — feedback endpoint REST-only trong issue này; field `prescription_id` mới trên `PrescribeResponse` vẫn cần parity proto/gRPC vì đó là field của RPC `Prescribe` đã có sẵn. User chọn theo đề xuất.
