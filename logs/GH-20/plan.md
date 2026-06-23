# Plan — GH-20: Prescription Layer (Hybrid)

## Metadata
- **Status:** SHIPPED | **Role:** AI | **Ngày:** 2026-06-23
- **Issue:** #20 — https://github.com/GSU26SE55/ai-module/issues/20
- **PR:** #21 — https://github.com/GSU26SE55/ai-module/pull/21
- **Sprint:** Sprint 3 (due 2026-06-27)
- **Branch:** `feat/GH-20-prescription-hybrid` (tạo từ `dev`)

## Mục tiêu
Biến output prediction (SOH% + classification + risk) thành **khuyến nghị bảo trì hành động được** qua endpoint `POST /prescribe`, theo **Phương án C (Hybrid)** trong `docs/prescription-layer.md`:
- **Rule-based** = đường mặc định, luôn chạy, <100ms, 0 phụ thuộc ngoài (off P1 hot-path).
- **LLM + RAG** (ChromaDB + sentence-transformers + Claude Haiku) = lớp enrich **tùy chọn**, bật bằng `enrich=true`, có fallback về rule-based khi API lỗi.
- **safety_gate** = human-in-the-loop cho mọi hành động vật lý.

## Scope
**Trong scope (Core hybrid — Phase 1 + 2 của doc):**
- Dọn skeleton: branch sạch, gỡ `node_modules/headroom-ai` + `package*.json`.
- Rule-based decision table (`action_code` × `risk_level` × `warning_codes` → prescription template).
- Refactor `prescription.py` thành hybrid: rule-based default + nhánh enrich.
- Thay stub `_call_llm()` bằng gọi Anthropic (`claude-haiku-4-5`) thật, structured output, timeout/retry/fallback.
- Ingest `knowledge/*.md` → ChromaDB → commit `models/embeddings/`.
- `enrich: bool` trong schema; field LLM/RAG optional khi không enrich.
- Unit test (rule path không cần network) + latency benchmark.

**Ngoài scope (ticket riêng sau):**
- Phase 3 — BE/ITIL integration (`BatteryAnomalyDetectedEvent` → TicketService → enrich ticket).
- Phase 4 — Evaluation harness đầy đủ (faithfulness/coverage/safety-recall + ablation).
- Tối ưu lại model SOH (track song song, độc lập ticket này).

## Endpoints
| Method | Path | Mục đích / Request / Response |
|--------|------|-------------------------------|
| POST | `/prescribe/` | Sinh prescription. Request: `PredictRequest` + `age_cycles?`, `last_maintenance_date?`, `ticket_history?`, **`enrich?: bool = false`**. Response: `PrescribeResponse` (rule-based luôn có; `prescription`/RAG docs chỉ đầy đủ khi `enrich=true`). |

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `node_modules/`, `package.json`, `package-lock.json` | **delete** | Rác JS commit nhầm — gỡ khỏi branch |
| `.gitignore` | modify | Thêm `node_modules/`, `package*.json` |
| `src/services/rule_prescription.py` | **create** | Decision table → `prescription`, `action_steps`, `ppe_required`, `escalation_conditions`. Deterministic, <100ms. |
| `src/services/prescription.py` | modify | Refactor hybrid: luôn chạy rule-based; nếu `enrich=true` → RAG + `_call_llm`, merge kết quả; fallback rule-based khi LLM lỗi |
| `src/services/_llm_client.py` | **create** | Gọi Anthropic `claude-haiku-4-5`, structured output, timeout 10s, retry 1, raise → caller fallback |
| `src/services/rag_retriever.py` | modify (nhẹ) | Giữ nguyên logic; chỉ chỉnh nếu cần khi gọi từ nhánh enrich |
| `src/services/safety_gate.py` | keep | Đã đúng — chạy cho cả 2 nhánh |
| `src/schemas/prescribe.py` | modify | Thêm `enrich: bool = False`, `enriched: bool` (output), field RAG/LLM cho phép rỗng khi rule-only |
| `src/routers/prescribe.py` | modify | Truyền `enrich` xuống `run_prescription` |
| `main.py` | modify | Đảm bảo `prescribe.router` đã được include |
| `scripts/ingest_rag.py` | keep | Chạy build vector store (seed cố định) |
| `knowledge/maintenance/*.md`, `knowledge/safety/*.md` | modify | Bổ sung **citation** mỗi doc (yêu cầu B2 của `ai.md`) |
| `models/embeddings/` | **commit** | Vector store build sẵn (như `scaler.pkl`) |
| `requirements.txt` | keep | Đã pin `chromadb==0.5.3`, `sentence-transformers==3.0.1`, `anthropic==0.34.2` |
| `.env.example` | keep | Đã có `ANTHROPIC_API_KEY` |
| `tests/test_rag_services.py` | modify | Mở rộng test |
| `tests/test_prescription.py` | **create** | Test rule-path (no network), enrich-path (mock LLM), safety_gate, latency |
| `tests/test_llm_client.py` | **create** | Mock anthropic SDK — is_available, success, API-error, malformed, no-tool-use |
| `scripts/train.py` | **fix (out-of-scope, approved)** | Dedent toàn file — sửa `IndentationError` pre-existing từ commit `f815452` chặn pytest collection. Không đổi logic. |

## Approach
- **Hot-path tách triệt để:** `run_prescription` luôn tính rule-based trước (decision table) → trả về ngay nếu `enrich=false`. SLA P1 <100ms không bao giờ chạm LLM/RAG.
- **Nhánh enrich (off hot-path):** `enrich=true` → RAG retrieve (ChromaDB) → `_call_llm` (Haiku, structured output, prompt ràng buộc "chỉ dùng retrieved docs, thiếu thì nói cần chuyên gia" để chống hallucination) → merge vào kết quả rule-based.
- **Fallback chắc chắn:** `_call_llm` lỗi/timeout/thiếu API key → log + trả về kết quả rule-based (response vẫn hợp lệ, `enriched=false`).
- **safety_gate** chạy cuối cho cả 2 nhánh — `human_verification_required=True` cho P1/thermal/electrical/REPLACE_IMMEDIATELY.
- **Đo latency:** benchmark `inference_ms` + `rag_ms` + `llm_ms` riêng, assert rule-path <100ms; ghi rõ enrich-path nằm ngoài P1 SLA.

## Edge Cases
- `enrich=true` nhưng thiếu `ANTHROPIC_API_KEY` → fallback rule-based, `enriched=false`, không crash.
- ChromaDB chưa ingest (`_ready=False`) → retriever trả `[]`, LLM prompt báo thiếu evidence → vẫn ra prescription rule-based.
- `readings` sai shape/feature count → đã có `_align_features` raise rõ ràng (giữ nguyên hành vi `/predict`).
- Anomaly có thermal/electrical warning → safety_gate ép `human_verification_required=True` + escalation, kể cả khi rule-only.
- LLM trả output không đúng schema → coi như lỗi → fallback rule-based.

## Acceptance Criteria
- [ ] `POST /prescribe` với `enrich=false` trả prescription rule-based, **benchmark <100ms**, không gọi network.
- [ ] `POST /prescribe` với `enrich=true` trả kết quả enrich (RAG docs + LLM prescription); khi API lỗi/thiếu key → fallback rule-based, `enriched=false`, không crash.
- [ ] `scripts/ingest_rag.py` build được ChromaDB từ `knowledge/`; `models/embeddings/` được commit.
- [ ] `safety_gate`: P1 / thermal / electrical / REPLACE_IMMEDIATELY → `human_verification_required=True`.
- [ ] Prompt LLM ràng buộc chỉ dùng retrieved docs (chống hallucination).
- [ ] `node_modules/` + `package*.json` đã gỡ khỏi branch; `.gitignore` cập nhật.
- [ ] Mỗi `knowledge/*.md` có citation.
- [ ] `pytest tests/ -v --cov=src` PASS, coverage ≥ 85% trên file mới.

## Steps
- [x] **Preprocess/KB:** tạo branch sạch từ `dev`, migrate file Python + `knowledge/` từ `feat/RAG_struct`, gỡ `node_modules`/`package*`, thêm citation vào KB docs. — 2026-06-23
- [x] **Rule layer:** viết `rule_prescription.py` (decision table) — đường default <100ms. — 2026-06-23
- [x] **LLM/inference:** viết `_llm_client.py` (Anthropic Haiku, structured output, timeout/retry); refactor `prescription.py` thành hybrid + fallback; verify contract `run_inference` (prediction/risk/warnings/metadata); fix bug `safety_gate` thiếu `overvoltage_critical`. — 2026-06-23
- [x] **RAG build:** chạy `ingest_rag.py` → build `models/embeddings/` (16 chunks, cosine space). Commit ở `/kltn-ship`. — 2026-06-23
- [x] **FastAPI endpoint:** thêm `enrich` vào schema + router; `main.py` include router (verified `/prescribe/` route). — 2026-06-23
- [x] **Unit test + latency:** `test_prescription.py` + `test_llm_client.py` (rule no-network, enrich mock LLM, fallback, safety_gate) + benchmark rule-path <100ms; coverage tổng **86% ≥ 85%**. — 2026-06-23

## Known pre-existing failures (KHÔNG do GH-20 — cần ticket #13/debug riêng)
`pytest tests/` còn 4 fail không liên quan prescription, đều thuộc long-model (#13) hoặc môi trường:
- `test_long_model_lazy_loaded`, `test_predict_soh_long_chunked_path` — thiếu artifact `models/weights/scaler_long.pkl` (long model chưa build/commit ở checkout này).
- `test_spectral_features_ignore_dc_offset` — assertion số học trong `extractor.py`.
- `test_load_split_rejects_stale_feature_version` — `load_split` không raise như kỳ vọng (logic drift `train.py`, lộ ra sau khi fix collection).

Tests phần prescription (GH-20): **29/29 PASS**, coverage tổng **86% ≥ 85%**.

## Câu hỏi đã giải đáp
- **API shape:** 1 endpoint `/prescribe` + flag `enrich` (rule-based default <100ms; `enrich=true` mới gọi LLM+RAG đồng bộ, off P1 path).
- **Scope:** Core hybrid (Phase 1+2 + rule-based + wiring + test + benchmark). Phase 3 (BE/ITIL) và Phase 4 (eval) tách ticket riêng.
- **Branch:** mới `feat/GH-20-prescription-hybrid` từ `dev` (không reuse `feat/RAG_struct` vì lệch convention + dính rác node_modules).
- **LLM model:** `claude-haiku-4-5` (id: `claude-haiku-4-5-20251001`) cho enrich; rule-based là fallback. Không dùng Sonnet/Opus cho hot-path prescription.
- **Rule cứng:** thêm `chromadb`/`sentence-transformers`/`anthropic` vi phạm `ai.md` ("không thêm framework ngoài PyTorch+sklearn") — **exception có chủ đích**, đã bỏ qua governance hình thức theo yêu cầu. Nên ghi ADR sau (`docs/adr/`).
