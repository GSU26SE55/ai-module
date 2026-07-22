# Plan — GH-24: Phase 4 — Evaluation harness cho RAG prescription

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-07-21
- **Issue:** #24 — https://github.com/GSU26SE55/ai-module/issues/24
- **Sprint:** Sprint 5 (due 2026-07-25)

## Mục tiêu
Xây dựng evaluation harness đo chất lượng lớp RAG/LLM của Prescription Layer (Phase 4, GH-20's đã ghi "ngoài scope — ticket riêng") — phục vụ hồ sơ bảo vệ KLTN khi hội đồng hỏi "RAG có ích không, dựa trên đâu?". Output: script chạy được (CI/offline cho phần không cần LLM key), báo cáo số liệu (coverage/faithfulness/ablation 3 nhánh) lưu vào `logs/eval/`.

## Scope
**Trong scope:**
- Golden set: **tái dùng nguyên** `tests/fixtures/rag_golden_set.json` (14 kịch bản, đã tạo từ GH-82 — comment gốc ghi "Seed set for GH-24 to extend"). Đã ≥10, phủ đủ 4 action_code chính (MONITOR/SCHEDULE_MAINTENANCE/SCHEDULE_REPLACEMENT/REPLACE_IMMEDIATELY) + có sẵn kịch bản LFP 12V (GH-67). **Không tạo `eval/golden_set.json` mới** như issue đề xuất ban đầu — tránh 2 nguồn golden set trùng lặp.
- `eval/evaluate_prescription.py` — harness chạy 3 nhánh trên cùng golden set qua `run_prescription()` thật (mock `run_inference`, không mock RAG/LLM):
  1. **rule** (`enrich=False`)
  2. **hybrid-template** (`enrich=True, agentic=False`)
  3. **hybrid-agentic** (`enrich=True, agentic=True`)
- Metric:
  - **Coverage** (retrieval recall@k) — `|expected_sources ∩ retrieved_sources| / |expected_sources|`, tính cho hybrid-template/hybrid-agentic (rule không retrieve).
  - **SOP overlap** — `|rule sop_references ∩ expected_sources| / |expected_sources|` — tính được cho **cả 3 nhánh** (rule dùng `sop_references` tĩnh, không cần LLM/key) → cho nhánh rule 1 con số so sánh được thay vì N/A hoàn toàn.
  - **Faithfulness** — semantic overlap (cosine similarity, `all-MiniLM-L6-v2` — tái dùng đúng model `RagRetriever` đang dùng) giữa text prescription sinh ra và nội dung docs đã retrieve; chỉ tính khi `enriched=True` (có LLM key thật, generation thành công) — nhánh rule không có (không có free-text LLM output để so).
  - **Ablation** — bảng 3 cột rule/hybrid-template/hybrid-agentic: SOP-overlap, coverage, faithfulness, latency (`rag_ms`/`llm_ms`/`query_gen_ms` — đã có sẵn trong `run_prescription()` output).
- Báo cáo: `logs/eval/results.json` (raw per-scenario) + `logs/eval/report.md` (bảng summary) — theo đúng convention `--output-dir` đã có ở `scripts/eval_anomaly.py`.
- `eval/README.md` — giải thích từng metric + công thức + cách diễn giải cho hồ sơ KLTN + giới hạn đã biết (faithfulness cần LLM key, LLM text không seed-control được).
- Unit test `tests/test_evaluate_prescription.py` — test công thức metric bằng mock (không cần key thật), theo đúng convention `tests/test_eval_anomaly.py` (test `scripts/eval_anomaly.py`).
- Chạy harness thật 1 lần (cần API key user set trong `.env`) — lưu số liệu thật vào `logs/eval/`.

**Ngoài scope:**
- Fine-tune embedding model
- Sửa rule engine / LLM prompt (nếu eval lộ vấn đề → issue fix riêng)
- Mở rộng golden set thêm kịch bản mới (đã quyết định dùng nguyên 14 kịch bản có sẵn)
- LLM-as-judge cho faithfulness (đã chọn semantic overlap, không dùng judge)

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `eval/evaluate_prescription.py` | create | Harness: load golden set → 3 nhánh qua `run_prescription()` (mock `run_inference` + mock `_get_history_store` để không ghi vào history store thật) → tính coverage/SOP-overlap/faithfulness → xuất báo cáo |
| `eval/README.md` | create | Giải thích metric, công thức, cách chạy, giới hạn |
| `tests/test_evaluate_prescription.py` | create | Unit test công thức metric (recall, SOP-overlap, faithfulness) bằng dữ liệu giả — không cần LLM key |
| `logs/eval/results.json`, `logs/eval/report.md` | output (chạy harness sinh ra) | Không phải file code — kết quả 1 lần chạy thật |

## Approach
- **Golden set format đã có sẵn** (`tests/fixtures/rag_golden_set.json`): mỗi scenario có `prediction`/`anomaly`/`risk`/`warnings` (dict, đúng shape `run_inference()` trả về) + `expected_sources` (list source file). Harness patch `orchestrator.run_inference` trả thẳng dict này — bỏ qua model SOH/anomaly thật (đó là việc của GH-70, không phải GH-24) → tránh nhiễu do MC-Dropout không reproducible, giữ đúng AC "reproducible (seed 42)".
- **Vì sao gọi `run_prescription()` thật thay vì gọi thẳng RAG/LLM** (khác với `scripts/eval_query_gen.py` gọi retrieval trực tiếp): để số liệu phản ánh đúng pipeline production (bao gồm safety gate, SOP reference union, rule fallback khi LLM lỗi) — không tái tạo logic riêng, không lệch với hành vi thật.
- **Patch `_get_history_store()`** trỏ về `PrescriptionHistoryStore(path=<tempdir>)` khi chạy harness (giống pattern `tests/test_hybrid_prescription.py::TestHistoryFewShotIntegration._patch_common`) — 14 scenario × 2 nhánh enrich=True = 28 lần gọi `run_prescription(enrich=True)`, nếu không patch sẽ ghi thẳng vào `models/prescription_history/` thật (production-adjacent), làm bẩn dữ liệu.
- **Faithfulness không cần request thêm LLM call** — dùng lại `_encoder` (SentenceTransformer) mà `RagRetriever` đã tải, encode text prescription + nội dung từng doc đã retrieve, lấy `max` cosine similarity qua các doc (đo "có ít nhất 1 doc support câu này không"). Chỉ tính khi `result["enriched"] is True`; nếu không có key → giá trị `None`, báo cáo ghi rõ "N/A (no LLM key)" thay vì số sai lệch.
- **Coverage/SOP-overlap luôn chạy được offline/CI** (không cần LLM key) — chỉ faithfulness + phần "hybrid" của ablation cần key thật. README ghi rõ ranh giới này.

## Edge Cases
- Không có LLM key khi chạy: `enrich=True` vẫn chạy retrieval (coverage đo được) nhưng `enriched=False` → faithfulness = `None` cho tất cả scenario, báo cáo in rõ "0/14 scenarios enriched — set an LLM key to measure faithfulness" thay vì âm thầm báo cáo số 0/sai.
- 1 provider trong chain lỗi/timeout giữa chừng (mạng, rate limit): `run_prescription()` đã tự fallback về rule-based (`enriched=False`) — harness không cần xử lý thêm, chỉ đọc `result["enriched"]` để quyết định có tính faithfulness hay không.
- `expected_sources` rỗng (không có trong golden set hiện tại nhưng phòng hờ): recall chia 0 → trả `0.0` (giữ nguyên convention `_recall()` của `eval_query_gen.py`: `len(expected & retrieved) / len(expected) if expected else 0.0`).
- Golden set 14 scenario × 3 nhánh × (1-2 LLM call/nhánh hybrid) ≈ 40+ LLM call thật — có tốn API cost + vài phút runtime khi chạy Bước 6, đã được user xác nhận chấp nhận.

## Acceptance Criteria
- [ ] Golden set ≥10 kịch bản, phủ đủ action_code chính (đã thỏa sẵn — tái dùng 14 kịch bản GH-82)
- [ ] Harness xuất faithfulness + retrieval recall@k + bảng ablation 3 cột (rule/hybrid-template/hybrid-agentic)
- [ ] Báo cáo reproducible (seed 42) — coverage/SOP-overlap luôn reproducible offline; faithfulness/hybrid ghi rõ giới hạn (cần key, text LLM không seed-control được, nhưng công thức tính similarity từ text đó là deterministic)
- [ ] `eval/README.md` giải thích rõ từng metric + cách diễn giải kết quả
- [ ] Unit test coverage cho công thức metric (không phụ thuộc LLM key)
- [ ] Đã chạy harness thật ít nhất 1 lần, có `logs/eval/results.json` + `logs/eval/report.md` với số liệu thật (không phải placeholder)

## Steps
- [x] Bước 1: Viết `eval/evaluate_prescription.py` phần core — load golden set, chạy 3 nhánh qua `run_prescription()` (mock `run_inference` + `_get_history_store`), tính coverage + SOP-overlap (không cần key) — 2026-07-21
- [x] Bước 2: Thêm faithfulness — semantic overlap qua `SentenceTransformer("all-MiniLM-L6-v2")` (tái dùng model của `RagRetriever`), chỉ tính khi `enriched=True` — 2026-07-21 (viết cùng lúc Bước 1 do cùng 1 file/1 lần thiết kế)
- [x] Bước 3: Xuất báo cáo `logs/eval/results.json` + `logs/eval/report.md` (`--output-dir` flag, default `logs/eval`, theo convention `scripts/eval_anomaly.py`) — 2026-07-21 (viết cùng Bước 1)
- [x] Bước 4: Viết `eval/README.md` — 2026-07-21
- [x] Bước 5: Viết `tests/test_evaluate_prescription.py` — test công thức recall/SOP-overlap/faithfulness bằng mock, không cần key — 2026-07-21 (18 test PASS)
- [ ] Bước 6: Chạy harness thật (`python eval/evaluate_prescription.py`) — **cần user đã set LLM API key trong `.env`** — lưu báo cáo thật
- [ ] Bước 7: `pytest tests/ --cov=src` — xác nhận không phá test hiện có + `ruff check` sạch

## Câu hỏi đã giải đáp
- **Faithfulness — semantic overlap hay LLM-as-judge:** chọn **semantic overlap** (embedding cosine similarity, tái dùng model RAG retriever sẵn có) — deterministic, không tốn thêm API call, chạy được ngay không cần key. LLM-as-judge bị loại vì tốn API call thêm + không reproducible (provider hiện tại không có tham số seed/temperature=0) — mâu thuẫn với AC "reproducible (seed 42)".
- **API key phiên này:** user xác nhận sẽ set trong `.env` trước khi chạy `/kltn-implement` — Bước 6 (chạy harness thật) phụ thuộc việc này; nếu chưa set khi tới Bước 6, dừng lại hỏi thay vì âm thầm báo cáo số liệu rỗng/giả.
- **Ablation — so sánh cái gì:** bảng 3 cột rule/hybrid-template/hybrid-agentic (không phải 2 cột rule/hybrid như approach gốc của issue) — trả lời luôn câu "agentic có tốt hơn template không" mà GH-82 chưa có số liệu chính thức. Thêm SOP-overlap để nhánh rule có 1 con số so sánh được (không toàn N/A).
- **Golden set — tái dùng hay mở rộng:** dùng nguyên 14 kịch bản có sẵn từ GH-82 (`tests/fixtures/rag_golden_set.json`) — đã đủ AC, tiết kiệm thời gian cho deadline Sprint 5 (25/07, còn 4 ngày). Không tạo `eval/golden_set.json` mới (khác đề xuất ban đầu của issue) để tránh 2 nguồn golden set trùng lặp — 1 nguồn duy nhất giữ nhất quán với GH-82.
- **Vì sao không tái dùng logic của `scripts/eval_query_gen.py` (import trực tiếp):** thay vì import chéo `scripts/` ↔ `eval/` (2 thư mục không phải package chính thức, phải hack `sys.path`), harness mới gọi thẳng `run_prescription()` — vừa đơn giản hơn, vừa phản ánh đúng full pipeline production (bao gồm safety gate, SOP union) thay vì chỉ retrieval đơn lẻ như `eval_query_gen.py`.
