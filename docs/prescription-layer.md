# Prescription Layer — Hybrid (Phương án C)

> Biến output prediction (SOH% + classification + risk + warnings) thành **khuyến nghị bảo trì hành động được** qua `POST /prescribe`.
> Issue gốc: GH-20 (PR #21, đã merge). Phase 2 (LLM thật + dọn dẹp): track tiếp theo.

## Mục tiêu thiết kế

| Yêu cầu | Cách đạt |
|---------|----------|
| P1 critical phải < 100ms, không phụ thuộc mạng | Rule-based engine chạy trước, P1 không bao giờ gọi LLM/RAG |
| Khuyến nghị phải an toàn, có thể kiểm chứng | `safety_gate` ép `human_verification_required` cho P1/thermal/electrical/REPLACE |
| LLM không được bịa | Prompt ràng buộc **chỉ dùng retrieved docs**, structured output |
| Hệ thống không sập khi LLM/RAG lỗi | Mọi lỗi → fallback rule baseline (graceful degradation) |

## Kiến trúc — 3 lớp

```
POST /prescribe
   │
   ├─ 1. run_inference()         → prediction (SOH, health_stage), risk (priority, action_code), warnings
   │
   ├─ 2. build_rule_prescription()   [rules_prescription.py]  ← LUÔN chạy (default + fallback), <100ms, 0 network
   │        action_code × warning_codes × hazard-class → prescription + action_steps + PPE
   │
   ├─ 3. _should_enrich(priority, detail)?
   │        P1            → KHÔNG enrich (rule-only, giữ SLA + an toàn)
   │        P2/P3/None    → enrich (off hot-path)
   │        detail=True   → ép enrich kể cả P1
   │
   ├─ 4. (nếu enrich) RagRetriever → ChromaDB semantic search (maintenance + safety docs)
   │        → call_structured_prescription()  [_llm_client.py]  ← Claude Haiku 4.5, structured output
   │        → _merge_llm_onto_rule()  ← LLM enrich prose + steps; rule steps/PPE giữ làm safety baseline
   │        → nếu LLM None (lỗi/timeout/thiếu key) → giữ rule baseline, source="rule (llm-unavailable)"
   │
   ├─ 5. apply_safety_gate()    [safety_gate.py]  ← chạy CHO CẢ 2 nhánh
   │
   └─ 6. PrescribeResponse (rule-based luôn có; RAG docs + LLM prose chỉ khi enrich)
```

## Lớp 1 — Rule engine (`rules_prescription.py`)

Deterministic, không network, < 100ms — an toàn trên P1 hot-path.

- `_ACTION_TABLE`: mỗi `action_code` (REPLACE_IMMEDIATELY / SCHEDULE_REPLACEMENT / SCHEDULE_MAINTENANCE / MONITOR) → prescription prose + action_steps + baseline PPE.
- `_WARNING_STEPS`: mỗi warning code (TEMP_CRITICAL, VOLTAGE_CRITICAL, ...) → bước hành động bổ sung.
- Hazard-class PPE escalation: thermal-critical → Face shield + fire extinguisher; electrical-critical → arc-flash gloves.
- Thresholds đồng bộ với `src/models/anomaly_detector.py`.

## Lớp 2 — LLM enrichment (`_llm_client.py`)

- Model: **`claude-haiku-4-5`** — tier latency/cost thấp, chỉ chạy off hot-path (P2/P3 hoặc `detail=True`).
- **Structured output** (`output_config.format` json_schema): API đảm bảo trả JSON `{prescription, action_steps, ppe_required}`.
- **Grounding**: system prompt cấm dùng thông tin ngoài retrieved docs; chỉ được *thêm*, không được làm yếu safety step.
- Timeout 8s, max_retries 1.
- **Graceful degradation**: thiếu `ANTHROPIC_API_KEY`, SDK chưa cài, API lỗi, output sai schema → trả `None` → caller fallback rule baseline.

> ⚠️ `anthropic` SDK phải đủ mới để hỗ trợ `output_config.format` + `claude-haiku-4-5` (xem `requirements.txt`). SDK cũ → call raise → bắt và fallback rule.

## Lớp 3 — Safety gate (`safety_gate.py`)

Chạy cuối cho cả 2 nhánh. Ép `human_verification_required=True` khi: priority P1, action_code REPLACE_IMMEDIATELY, hoặc có warning thermal/electrical critical. Thêm escalation conditions. Không block (human review xử lý).

## RAG (`rag_retriever.py` + `scripts/ingest_rag.py`)

- Knowledge base: `knowledge/maintenance/*.md` + `knowledge/safety/*.md` (mỗi doc có citation).
- `ingest_rag.py`: chunk (512 char, overlap 64) → embed (`all-MiniLM-L6-v2`) → ChromaDB tại `models/embeddings/`.
- `RagRetriever`: semantic search; nếu chromadb chưa cài → `_ready=False` → trả `[]` (vẫn ra rule-based).

## API contract

`POST /prescribe` — request = `PredictRequest` + `age_cycles?`/`last_maintenance_date?`/`ticket_history?` + **`detail: bool=false`**.
Response `PrescribeResponse`: rule-based luôn có; `maintenance_docs`/`safety_docs` + LLM prose chỉ khi enrich. `prescription_source` ∈ `"rule"` | `"llm"` | `"rule (llm-unavailable)"`.

> Lưu ý: param điều khiển enrich tên là **`detail`** trong code hiện tại (plan GH-20 ghi `enrich`). Đồng bộ 1 tên khi chốt contract với BE.
