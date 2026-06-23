## BÁO CÁO CODE REVIEW — feat/GH-20-prescription-hybrid — 2026-06-23
### Scope: AI
### Effort: Deep (API + service + RAG + LLM, không train)

### TÓM TẮT
Hybrid Prescription Layer (`POST /prescribe`): rule-based default <100ms + LLM/RAG enrich tùy chọn có fallback. Kiến trúc đúng, tách hot-path rõ ràng, an toàn (fallback + safety_gate). Không có lỗi Critical. Vài cleanup nhỏ đã xử lý ngay trong review.

### PHÂN TÍCH

✅ **Pass — Reproducibility**
- Deps pinned: `chromadb==0.5.3`, `sentence-transformers==3.0.1`, `anthropic==0.34.2`.
- Ticket không train → không cần `random_seed=42`. `ingest_rag.py` deterministic (embedding cố định theo model + cosine space).

✅ **Pass — Data / không leakage**
- Không fit scaler, không train, không đụng split. `run_prescription` chỉ tiêu thụ output `run_inference` (artifacts đã load lúc startup). Không có production refit.

✅ **Pass — Model scope**
- Không thêm core model thứ 3. RAG embedder (`all-MiniLM-L6-v2`) là retrieval, không phải predictor. Đúng exception đã duyệt (ghi trong `requirements.txt` + plan).

✅ **Pass — FastAPI endpoint**
- Pydantic `PrescribeRequest`/`PrescribeResponse` đầy đủ; `enrich` flag + `enriched`/`sop_references`/`llm_ms`.
- Input validation kế thừa `PredictRequest` (shape/feature → 422).
- Model load 1 lần ở `lifespan`; retriever lazy-singleton (rule-path không load sentence-transformers).
- Router include trong `main.py`; route `/prescribe/` verified.

✅ **Pass — Hybrid correctness & safety**
- Rule-based luôn tính trước; `enrich=true` mới gọi RAG+LLM; LLM lỗi/thiếu key → fallback rule-based, `enriched=false`, không crash (test phủ).
- `safety_gate` chạy cả 2 path; PPE = union(rule, LLM) → không mất PPE an toàn.
- **Bug fix:** `safety_gate.ELECTRICAL_KEYWORDS` bổ sung `overvoltage_critical` (trước đó `OVERVOLTAGE_CRITICAL` lọt gate).

🟡 **Warning — đã xử lý trong review**
- `rag_retriever.py`: gỡ comment `TODO install...` cũ; sửa docstring sai (`ingest()` không tồn tại); **clamp `relevance_score = max(0, 1 - cosine_dist)`** (cosine distance ∈ [0,2] có thể cho score âm).

🟡 **Warning — chấp nhận / theo dõi**
- Latency rule-path benchmark dùng dummy model (d_model=8) → PASS <100ms. Cần **re-benchmark với real artifact** ở `/kltn-test` (MC Dropout ×20 trong `run_inference`).
- `_llm_client` mới test qua mock SDK — call thật chưa chạy với live API (fallback bao lỗi). Cần đặt `ANTHROPIC_API_KEY` để smoke test enrich thật trước demo.
- `models/embeddings/` commit binary (chroma.sqlite3 + UUID dirs); re-ingest sinh UUID mới → churn. Chấp nhận cho scope (như `scaler.pkl`).
- `main.py` chưa có CORS middleware — pre-existing (cả `/predict`), BE↔AI là server-to-server.

### RỦI RO & LƯU Ý
- 4 test fail trong full suite là **pre-existing (#13 long-model + thiếu `scaler_long.pkl` + extractor DC-offset)** — không thuộc GH-20, ghi trong `plan.md`. Đã fix `train.py` IndentationError (dedent, không đổi logic) để pytest collect được.
- Coverage tổng **86% ≥ 85%**; file prescription: rule 100%, prescription 94%, safety_gate 100%, _llm_client 100%, schema 100%, router 86%.

### KẾT LUẬN
**PASS** — Độ tự tin: **Cao**
