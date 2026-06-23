# HANDOFF — GH-20: Prescription Layer (Hybrid)

## Thông tin
- **Người thực hiện:** Nguyễn Phúc Duy (SE184821)
- **Ngày ship:** 2026-06-23
- **Status:** SHIPPED ⏳ (chờ reviewer approve)
- **Issue:** #20
- **PR:** #21 — https://github.com/GSU26SE55/ai-module/pull/21
- **Branch:** feat/GH-20-prescription-hybrid

## Tiến độ Steps
- [x] KB/branch: branch sạch, migrate Python + knowledge/, gỡ node_modules, citation KB — 2026-06-23
- [x] Rule layer: rule_prescription.py (decision table, <100ms) — 2026-06-23
- [x] LLM/inference: _llm_client.py (Anthropic Haiku) + prescription.py hybrid + fallback; fix safety_gate overvoltage_critical — 2026-06-23
- [x] RAG build: ingest_rag.py → models/embeddings/ (16 chunks, cosine) — 2026-06-23
- [x] FastAPI endpoint: enrich flag + router + main.py — 2026-06-23
- [x] Unit test + latency: test_prescription.py + test_llm_client.py; coverage 86% — 2026-06-23

## Những gì đã làm
- `POST /prescribe` hybrid: rule-based default (<100ms, off P1) + RAG/LLM enrich tùy chọn có fallback.
- Files mới: `rule_prescription.py`, `_llm_client.py`, `rag_retriever.py`, `prescription.py`, `safety_gate.py`, `schemas/prescribe.py`, `routers/prescribe.py`, `scripts/ingest_rag.py`, `knowledge/**` (4 SOP + citation), `models/embeddings/**`, tests.
- Sửa: `main.py` (router), `requirements.txt` (+chromadb/sentence-transformers/anthropic), `.gitignore`, `.env.example`.
- Chore: dedent `scripts/train.py` (unblock pytest collection — bug #13 pre-existing).

## Kết quả
- reviewcode: PASS (logs/GH-20/review.md)
- test: PASS — 29/29 prescription tests, coverage 86% ≥ 85%, rule-path <100ms (logs/GH-20/test.md)
- PR #21: tạo thành công — chờ reviewer approve

## Ghi chú (QUAN TRỌNG cho reviewer + người làm #13)
- **CI có thể đỏ vì #13 pre-existing, KHÔNG do PR này:** 4 test fail (2 long-model thiếu artifact Kaggle, extractor DC-offset, load_split).
- **App chưa start E2E được** do `soh_mamba_v1.2.pth` lệch kiến trúc với `soh_predictor.py` (việc #13 — cần commit weights Kaggle khớp code). Vì vậy test endpoint dùng dummy model.
- **Enrich path:** cần `ANTHROPIC_API_KEY` trong `.env` để chạy LLM thật; RAG chromadb có thể vướng onnxruntime trong worker thread (Windows) → fallback rule-based bao trọn. Cần smoke test uvicorn thật trước demo.
- `models/embeddings/` đã commit (rebuild bằng `python scripts/ingest_rag.py`).
- Exception package (chromadb/sentence-transformers/anthropic) so với `ai.md` — nên viết ADR.

## Việc tiếp theo (ngoài scope GH-20)
- Đồng bộ artifact model #13 (kiến trúc + scaler version + long weights) — ticket riêng.
- BE/ITIL integration + eval harness đầy đủ (Phase 3/4).
