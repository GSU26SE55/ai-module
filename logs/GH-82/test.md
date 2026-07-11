## TEST REPORT — GH-82 — 2026-07-11
### Scope: AI
### Môi trường: local

### TÓM TẮT
Full suite 443/443 PASS (0 fail — `test_kb_manifest` đã hết fail pre-existing), coverage toàn `src` 92% (target ≥85%). Đã start server thật (`uvicorn main:app`) và gọi `/prescribe/` sống với 5 kịch bản (baseline, agentic không key, agentic+enrich=false, invalid schema, missing field) — tất cả đúng expected, không crash.

| Test case | Input | Expected | Actual | Status |
|-----------|-------|----------|--------|--------|
| Full pytest suite | `pytest tests/ --cov=src` | all pass, ≥85% cov | 443 passed, 0 failed, 92% cov | ✅ PASS |
| `test_kb_manifest` (pre-existing fail) | manifest vs embeddings | pass sau re-ingest | 4 passed | ✅ PASS |
| Diagnosis determinism | `build_diagnosis_statement()` x2, cùng input | output giống hệt | `test_deterministic` PASS | ✅ PASS |
| Rule-path latency (regression) | enrich=false, dummy model | <100ms | `test_rule_path_under_100ms` PASS | ✅ PASS |
| `/health` live | GET | model/scaler loaded | `{"status":"ok","model_version":"1.6","scaler_loaded":true,"mamba_loaded":true,"isolation_forest_loaded":true}` | ✅ PASS |
| `/prescribe/` enrich=false live | valid 30-step readings | `enriched:false`, `query_gen_ms:0.0`, `generated_queries:[]` | đúng như expected | ✅ PASS |
| `/prescribe/` enrich=true, agentic=true, **không có LLM key** live | valid readings | fallback graceful — `enriched:false`, `retrieved_via:"template"` mọi doc, `query_gen_ms:0.0`, `generated_queries:[]`, không crash | đúng như expected (rag_ms=30.61ms, retrieval thật từ ChromaDB đã re-ingest chạy tốt) | ✅ PASS |
| `/prescribe/` agentic=true + enrich=false live | valid readings | agentic bị ignore hoàn toàn | `enriched:false`, `query_gen_ms:0.0`, `generated_queries:[]` | ✅ PASS |
| `/prescribe/` invalid schema (`agentic:"not-a-bool"`) | string thay vì bool | 422 | HTTP 422 | ✅ PASS |
| `/prescribe/` missing `readings` | thiếu field bắt buộc | 422 | HTTP 422 | ✅ PASS |

### Coverage
- Line coverage toàn `src`: **92%** (target AI ≥ 85%) — `pytest tests/ --cov=src --cov-report=term-missing`, 443 passed
- File GH-82 touch trực tiếp: `diagnosis.py` 100%, `anthropic/deepseek/gemini_provider.py` 100%, `chain.py` 95%, `orchestrator.py` 99%, `rag_retriever.py` 91%

### Latency
- Rule-path (enrich=false): PASS test quy định <100ms (dùng dummy model nhỏ trong fixture — đây là regression guard có sẵn từ trước GH-82, không phải benchmark production mới; GH-82 không đổi code đường rule-path nên không cần benchmark lại với real weights)
- Agentic path không đo được latency LLM thật trong môi trường này vì **không có `DEEPSEEK_API_KEY`/`GEMINI_API_KEY`/`ANTHROPIC_API_KEY`** set — chain tự fallback về template ngay từ đầu (`chain.is_available()==False`), đúng thiết kế, nhưng nghĩa là 2-LLM-call path (query-gen + summarize) chỉ được verify qua unit test mock, chưa verify latency thật <30s worst-case ngoài đời

### Bugs tìm được
Không có.

### RỦI RO & LƯU Ý
- Agentic path thật (có LLM call thật) chưa được exercise end-to-end trong môi trường test này do thiếu API key — hành vi fallback khi thiếu key đã verify sống, nhưng **hành vi khi có key thật** (latency thực tế, chất lượng query sinh ra, recall) vẫn phụ thuộc vào việc user tự chạy `scripts/eval_query_gen.py` như đã note ở review.md.
- Coverage 92% là coverage toàn `src` (bao gồm cả model/training code không đổi trong GH-82) — không phải coverage riêng của diff, nhưng vẫn vượt xa target 85%.

### KẾT LUẬN
PASS — Độ tự tin: Cao
