## TEST REPORT — GH-20 — 2026-06-23
### Scope: AI
### Môi trường: local (pytest + FastAPI TestClient, model thật mock bằng dummy do artifact dev lệch version)
### Effort: Deep (API + service + RAG + LLM)

### TÓM TẮT
Hybrid Prescription Layer đạt tất cả acceptance criteria của GH-20: rule-path default <100ms không network, enrich fallback an toàn (không crash), safety_gate đúng, schema validation 422, coverage 86%. RAG retrieval hoạt động ở main-thread (serving path thật). Phát hiện 1 fragility môi trường (chromadb+onnxruntime trong worker thread) và 1 blocker pre-existing chặn app khởi động — cả hai ghi ở RISK, không thuộc lỗi logic GH-20.

| Test case | Input | Expected | Actual | Status |
|-----------|-------|----------|--------|--------|
| Rule-path enrich=false | readings hợp lệ | rule-based, no network | 200, enriched=False, rag_ms/llm_ms=0 | ✅ PASS |
| Default (enrich omitted) | không có field enrich | enriched=False | enriched=False | ✅ PASS |
| Latency rule-path (HTTP, dummy model) | 20 runs | < 100ms | 59.8 ms | ✅ PASS |
| Safety gate — P1/REPLACE_IMMEDIATELY | action_code P1 | human_verify=True | True | ✅ PASS |
| Safety gate — thermal | TEMP_CRITICAL | human=True + escalation | True | ✅ PASS |
| Safety gate — electrical | OVERVOLTAGE_CRITICAL | LOTO + arc-flash PPE | True (bug đã fix) | ✅ PASS |
| Enrich=true + LLM error (mock) | generate raise | fallback rule, no crash | enriched=False, 200 | ✅ PASS |
| Enrich=true + thiếu API key (e2e) | no ANTHROPIC_API_KEY | fallback rule | enriched=False, 200 | ✅ PASS |
| RAG retrieval — main thread | query | trả docs | 2 docs, score 0.32 | ✅ PASS |
| RAG retrieval — TestClient worker thread | query | trả docs | onnx import fail → fallback | ⚠️ ENV (fallback ok) |
| Invalid schema | readings=[[1,2,3]] | 422 | 422 | ✅ PASS |
| Reproducibility rule-path | same input | deterministic | giống nhau (rule + decision table) | ✅ PASS |

### Coverage
- Prescription scope (test_prescription + test_llm_client + test_rag_services): **29/29 PASS**.
- Per-file (file mới): rule_prescription **100%**, prescription **94%**, safety_gate **100%**, _llm_client **100%**, schema **100%**, rag_retriever **88%**, router prescribe **86%** (phủ qua TestClient e2e).
- Full-suite line coverage: **86% ≥ 85%** (target AI).

### Latency
- Rule-path (P1 hot-path), HTTP qua TestClient, dummy model (d_model=8): **59.8 ms < 100ms** ✅.
- ⚠️ Dùng dummy model do artifact thật lệch version (xem RISK). Cần re-benchmark real model trước demo — phần lớn latency là MC Dropout ×20 trong `run_inference`.

### Bugs tìm được
- 🟢 (đã fix trong review) `safety_gate.ELECTRICAL_KEYWORDS` thiếu `overvoltage_critical` → `OVERVOLTAGE_CRITICAL` lọt gate. Đã thêm + test phủ.
- Không có bug Critical mới trong phạm vi GH-20.

### RỦI RO & LƯU Ý
- 🟠 **RAG + onnxruntime trong worker thread (môi trường):** chromadb 0.5.3 tái dựng default ONNX embedder khi mở collection đã persist; `import onnxruntime` fail trong asyncio worker thread của TestClient trên Windows (import OK ở main thread). Route `async def` của uvicorn chạy sync inline trên main thread → RAG hoạt động (đã verify standalone main-thread trả docs). **Enrich fallback bao trọn case này** (200, enriched=False, không crash). **Cần smoke test dưới uvicorn thật + `ANTHROPIC_API_KEY`** trước demo; nếu tái diễn trong threadpool → cân nhắc pre-import onnxruntime lúc startup hoặc thay vector store không phụ thuộc ONNX.
- 🔴 **Pre-existing blocker (KHÔNG do GH-20):** `model_loader.load_models()` raise `Scaler version mismatch: expected 1.1, got 1.0` → **app không khởi động được với artifact đang commit trên `dev`** (kể cả `/predict`). Cần đồng bộ `scaler.pkl`/version (việc #13) trước khi deploy/demo. Vì lỗi này test endpoint phải mock model bằng dummy.
- 🟡 **4 test fail full-suite (pre-existing #13):** `test_long_model_lazy_loaded`, `predict_soh_long_chunked_path` (thiếu `scaler_long.pkl`), `test_spectral_features_ignore_dc_offset` (extractor), `test_load_split_rejects_stale_feature_version` (logic `train.py`). Không thuộc GH-20. Đã fix `train.py` IndentationError để pytest collect được.
- `models/embeddings/` (chroma.sqlite3 + UUID dirs) sẽ commit ở `/kltn-ship` (như `scaler.pkl`).

### KẾT LUẬN
**PASS** (phạm vi GH-20) — Độ tự tin: **Trung bình**
- PASS vững cho: rule-path hot-path, fallback an toàn, safety_gate, schema validation, coverage.
- Hạ xuống Trung bình vì: enrich-RAG dưới uvicorn thật chưa verify được (blocker scaler version chặn app start) + latency real-model chưa đo. Khuyến nghị: sửa scaler version (#13) → smoke test uvicorn + API key cho enrich trước khi demo.
