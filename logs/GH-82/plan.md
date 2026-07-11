# Plan — GH-82: Prescription — Agentic multi-step chain theo paper: diagnosis statement + LLM tự sinh search queries

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-07-11
- **Branch:** `feat/GH-82-agentic-query-gen-chain`
- **Issue:** #82 — https://github.com/GSU26SE55/ai-module/issues/82
- **Sprint:** (chưa gán milestone) | **Priority:** P3 Standard | **Dev:** Nguyễn Phúc Duy (DuyNguyen-3006)

## Mục tiêu
Nâng enrich path thành agentic chain theo Deng et al. 2024 §3.2: (1) diagnosis statement deterministic từ kết quả `/predict` → (2) LLM sinh 3–5 search queries → (3) multi-query retrieval có dedup + `retrieved_via` → (4) summarize như cũ. Bật per-request qua `agentic: bool` (default off); agentic=false giữ behavior byte-for-byte.

## Scope
**Trong scope:**
- `diagnosis.py` — build diagnosis statement (Diagnosis / Inference evidence / Description) từ prediction_result có sẵn, không tính thêm
- Query generation qua provider chain GH-79 (pattern structured-output như GH-81 judge), fallback template query khi fail
- Multi-query retrieval: top-k=2/query, dedup theo chunk id, cap 5 maintenance + 3 safety theo relevance_score, gắn `retrieved_via`
- Contract: `agentic` (request, proto 8) + `retrieved_via` (RetrievedDoc, proto 5) + `query_gen_ms` (proto 21) + `generated_queries` (proto 22) — REST/gRPC parity
- Mini golden set + `scripts/eval_query_gen.py` đo recall agentic vs template (user chạy với API key, post số vào issue)

**Ngoài scope:**
- Long-term memory / feedback, tool-use tự do (web search) — KB nội bộ only, đúng ADR
- Không đổi summarize (`generate_prescription`) và safety gate GH-81
- Không refactor gộp 3 method structured-output của providers (giữ pattern song song như GH-81 — refactor là quyết định riêng của user)
- GH-24 eval harness đầy đủ (golden set mini ở đây là seed cho GH-24 mở rộng)

## Endpoints
| Method | Path | Thay đổi |
|--------|------|----------|
| POST | `/prescribe/` | Request thêm `agentic: bool = false` (chỉ hiệu lực khi `enrich=true`). Response thêm `query_gen_ms: float`, `generated_queries: list[str]`; mỗi doc thêm `retrieved_via: str` |
| gRPC | `Prescribe` | `PrescribeRequest.agentic = 8` · `RetrievedDoc.retrieved_via = 5` · `PrescribeResponse.query_gen_ms = 21`, `generated_queries = 22` (toàn field number mới) |

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/services/prescription/diagnosis.py` | create | `build_diagnosis_statement(prediction, anomaly, risk, warnings)` — pure function, format 3 phần theo paper; Description reuse `_ACTION_TEMPLATES` summary |
| `src/services/prescription/llm/base.py` | modify | `QUERYGEN_SYSTEM_PROMPT` + `QUERYGEN_SCHEMA` (`{maintenance_queries: [str], safety_queries: [str]}`) + `build_querygen_content` + abstract `generate_queries` |
| `src/services/prescription/llm/deepseek_provider.py` | modify | Impl `generate_queries` (mirror plumbing hiện có) |
| `src/services/prescription/llm/gemini_provider.py` | modify | Impl `generate_queries` |
| `src/services/prescription/llm/anthropic_provider.py` | modify | Impl `generate_queries` |
| `src/services/prescription/llm/chain.py` | modify | `generate_queries()` + param `budget_s` cho loop (default `TOTAL_BUDGET_S`) — query-gen gọi với budget 8s |
| `src/services/prescription/rag_retriever.py` | modify | `_format` thêm `chunk_id` từ `results["ids"]` (internal key, phục vụ dedup) |
| `src/services/prescription/orchestrator.py` | modify | Agentic path trong `_enrich`: diagnosis → query-gen (timed) → multi-query retrieve + dedup/cap + `retrieved_via` → summarize; fallback template; `query_gen_ms`, `generated_queries` vào result |
| `src/schemas/prescribe.py` | modify | `PrescribeRequest.agentic`; `RetrievedDoc.retrieved_via: str = ""`; `PrescribeResponse.query_gen_ms: float = 0.0`, `generated_queries: list[str] = []` |
| `protos/ai_service.proto` | modify | 4 field mới như bảng Endpoints |
| `src/grpc_gen/*` | regen | `python scripts/gen_proto.py` |
| `src/grpc_server.py` | modify | Forward `request.agentic`; map `retrieved_via`/`query_gen_ms`/`generated_queries` |
| `src/routers/prescribe.py` | modify | Pass `agentic` vào `run_prescription` |
| `tests/fixtures/rag_golden_set.json` | create | 10–15 scenario: diagnosis input stub + `expected_sources` (file-level, gán tay từ KB) |
| `scripts/eval_query_gen.py` | create | Recall@k template vs agentic trên golden set; agentic cần `DEEPSEEK_API_KEY`; in bảng per-scenario + mean |
| `tests/test_prescription.py` | modify | Agentic pipeline mocked: 2 LLM call, dedup, caps, retrieved_via, fallback, agentic=false regression |
| `tests/test_llm_providers.py` | modify | `generate_queries` per provider (fake SDK) + chain fallback + budget |
| `tests/test_rag_services.py` | modify | Diagnosis builder unit + `chunk_id` trong `_format` |
| `tests/test_grpc_server.py` | modify | Parity 3 field response + forward `agentic` |
| `.env.example` | modify | (Bổ sung sau approve, yêu cầu user 2026-07-11) Sync với code: thêm `SAFETY_LLM_JUDGE` (GH-81), `GRPC_PORT/GRPC_HOST`; xóa dòng `MODEL_VERSION` sai (code không đọc env này); sửa path comment cũ |

## Approach
1. **Diagnosis statement (deterministic):** format cố định — `Diagnosis:` (classification + health_stage) / `Inference evidence:` (soh ± soh_std, anomaly_score + status + confidence, warning codes) / `Description:` (summary template theo action_code + risk/priority). Chỉ đọc `prediction_result` hiện có (thêm block `anomaly` vào tham số `_enrich`).
2. **Query-gen:** `chain.generate_queries(diagnosis)` — schema tagged 2 list (maintenance 2–4 + safety 1–2, tổng 3–5), prompt ràng buộc EN/<15 từ/lithium battery. Đo `query_gen_ms`. Fail/timeout/rỗng → fallback template query hiện tại (`generated_queries=[]`), pipeline tiếp tục — không được chết.
3. **Multi-query retrieval:** mỗi maintenance query → `retrieve_maintenance(top_k=2)`, safety query → `retrieve_safety(top_k=2)`; gắn `retrieved_via=query` từng doc; dedup theo `chunk_id` giữ bản relevance cao nhất; sort desc → cap 5 maintenance + 3 safety. Template path (agentic=false hoặc fallback): docs gắn `retrieved_via="template"`.
4. **Latency bound:** query-gen dùng chain budget 8s (param `budget_s`, chỉ thêm param — không đổi behavior call hiện có); mỗi provider call sẵn `TIMEOUT_S=10` + 1 retry; summarize giữ budget 25s hiện tại. Typical agentic ≈ 2 LLM call <15s; worst-case ghi nhận trong eval script.
5. **Contract:** 4 field mới toàn số MỚI (8/5/21/22), chỉ thêm — wire compatible; parity test mở rộng; `agentic` chỉ hiệu lực khi `enrich=true` (agentic một mình → bỏ qua, document trong schema).

## Edge Cases
- `agentic=true, enrich=false` → agentic bỏ qua (docstring + test) — enrich vẫn là công tắc tổng của path LLM
- Query-gen trả ≥1 nhưng <3 queries → vẫn dùng (AC ≥3 chỉ áp khi LLM trả đủ); trả rỗng/fail → fallback template
- Query không đạt constraint (dài/không EN) → dùng nguyên, không hard-validate (constraint là prompt-level)
- ChromaDB unavailable → retrieve trả `[]` như hiện tại → summarize ít/không docs, không crash
- Dedup: cùng chunk từ 2 query → giữ relevance cao nhất, `retrieved_via` theo bản giữ lại
- LLM không có key → `chain.is_available()` false → skip enrich như hiện tại (agentic không đổi gì)
- Safety gate GH-81 chạy sau summarize như cũ — agentic không đi vòng qua gate

## Acceptance Criteria
- [ ] `agentic=true` (enrich=true, mock) → đúng 2 LLM call (query-gen + summarize), retrieval gọi per-query, dedup đúng, caps 5/3, `retrieved_via` đúng query nguồn
- [ ] Query-gen fail (mock raise/timeout) → pipeline hoàn thành bằng template query, `generated_queries=[]`, `query_gen_ms` vẫn đo
- [ ] `agentic=false` → output byte-for-byte như hiện tại (regression test so sánh dict, trừ field mới có default)
- [ ] Recall agentic vs template trên golden set — script chạy được, số post vào issue (user chạy với DEEPSEEK key)
- [ ] Parity REST/gRPC 4 field mới; `agentic` forward đúng qua gRPC
- [ ] Coverage ≥ 85% file sửa; `ruff check` sạch; latency rule-path (enrich=false) không đổi <100ms

## Steps
- [x] Bước 1 — Diagnosis builder (`diagnosis.py`) + unit tests — 2026-07-11
- [x] Bước 2 — Query-gen: base schema/prompt → 3 provider impl → `chain.generate_queries(budget_s)` + fake-SDK tests — 2026-07-11
- [x] Bước 3 — Retriever: `chunk_id` trong `_format` + test — 2026-07-11
- [x] Bước 4 — Orchestrator: agentic path (multi-query retrieve, dedup/cap, retrieved_via, query_gen_ms, generated_queries, fallback) + tests mock đủ AC — 2026-07-11
- [x] Bước 5 — Contract: schemas + proto 4 field (8/5/21/22, verify runtime) + regen stub + grpc_server + router + parity tests — 2026-07-11
- [x] Bước 6 — Golden set 14 scenario + `scripts/eval_query_gen.py` — smoke test template mode chạy được, **mean template recall baseline = 0.488** — 2026-07-11
- [x] Bước 7 — Verify: ruff sạch + 442 passed (1 fail duy nhất `test_kb_manifest` pre-existing từ 32d0200) + coverage diagnosis 100%/providers 100%/chain 95%/orchestrator 99% + latency rule-path PASS — 2026-07-11

## Việc còn lại cho user
- Chạy `python scripts/eval_query_gen.py` với `DEEPSEEK_API_KEY` (~14 LLM calls) → post bảng recall agentic vs template (baseline 0.488) vào issue #82 theo AC.

## Fix ngoài scope đi kèm branch (yêu cầu user 2026-07-11)
- Re-ingest KB (`python scripts/ingest_rag.py`) — sửa `test_kb_manifest` FAIL pre-existing từ 32d0200 (KB sửa mà manifest chưa update). 39 maintenance + 25 safety chunks; artifacts thay đổi: `models/embeddings/*` + `manifest.json`. Full suite sau fix: **443 passed, 0 failed**. Baseline recall đo lại không đổi (0.488).

## Câu hỏi đã giải đáp
1. **Toggle `agentic` ở đâu?** → Request field `PrescribeRequest.agentic` + proto field 8 (mirror pattern `enrich`) — BE bật per-request, không cần restart.
2. **Expose metadata mức nào?** → Đầy đủ: `retrieved_via` (RetrievedDoc proto 5) + `query_gen_ms` (proto 21) + `generated_queries` (proto 22) — minh bạch toàn chain cho FE/eval.
3. **AC recall khi GH-24 chưa có golden set?** → Mini golden set (~10–15 scenario) + `scripts/eval_query_gen.py` ngay trong GH-82; user chạy 1 lần với DEEPSEEK key, post số vào issue; GH-24 kế thừa mở rộng.
4. **Path trong issue** (`prescription.py`) thực tế là `src/services/prescription/orchestrator.py` sau tái cấu trúc GH-20.
