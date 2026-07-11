## BÁO CÁO CODE REVIEW — feat/GH-82-agentic-query-gen-chain — 2026-07-11
### Scope: AI
### Effort: Standard

### TÓM TẮT
Agentic prescription chain (diagnosis statement → LLM query-gen → multi-query retrieval + dedup) implement đúng plan.md, contract additive/wire-compatible, mọi failure path fallback về template — không có Critical. 198/198 test liên quan PASS (local, độc lập với báo cáo trong plan.md), `test_kb_manifest` 4/4 PASS, ruff sạch, coverage 95–100% trên các file mới/sửa.

### PHÂN TÍCH

🟡 Warning: `src/services/prescription/diagnosis.py:9` — import `_ACTION_TEMPLATES`, `_DEFAULT_ACTION` (tên có prefix `_`, quy ước module-private) trực tiếp từ `rule_prescription.py` sang module khác. Không có precedent tương tự ở nơi khác trong codebase (`grep` cross-module private import chỉ ra đúng 1 chỗ — chính chỗ này). Coupling ẩn: nếu `rule_prescription.py` refactor nội bộ 2 tên này, `diagnosis.py` vỡ mà không có contract công khai nào báo trước.
→ Gợi ý (không chặn ship): bỏ prefix `_` cho 2 hằng số này nếu định dùng cross-module, hoặc thêm 1 hàm public accessor trong `rule_prescription.py`. Có thể để lại làm follow-up nếu không muốn touch thêm file ngoài plan.

✅ Pass: `agentic=false` giữ nguyên hành vi cũ — template query, `top_k=3/2`, không gọi `chain.generate_queries` (`test_agentic_false_never_calls_query_gen`, `test_agentic_ignored_without_enrich`)
✅ Pass: Query-gen fail/timeout/rỗng → fallback template, pipeline không chết, `generated_queries=[]` (`test_query_gen_failure_falls_back_to_template`, `test_empty_queries_fall_back_to_template`)
✅ Pass: Multi-query retrieval đúng top_k=2/query, dedup theo `chunk_id` giữ relevance cao nhất, cap 5 maintenance + 3 safety, `retrieved_via` gắn đúng (`test_agentic_dedup_and_retrieved_via`, `test_agentic_caps_maintenance_docs_at_5`)
✅ Pass: `chunk_id` chỉ là internal key — không leak ra REST/gRPC response (không có trong `RetrievedDoc` schema/proto, xác nhận qua `grpc_server._to_retrieved_docs` và test parity)
✅ Pass: Contract 4 field mới (`agentic`=8, `retrieved_via`=5, `query_gen_ms`=21, `generated_queries`=22) toàn số mới, wire-compatible, không đụng field cũ (`blocked`=20 GH-81 giữ nguyên)
✅ Pass: REST/gRPC parity test mở rộng đủ 4 field mới (`test_prescribe_parity_with_rest`, `test_prescribe_forwards_agentic_flag`)
✅ Pass: 3 provider (DeepSeek/Gemini/Anthropic) implement `generate_queries` theo đúng pattern structured-output đã có của `judge_safety`/`generate_prescription` — reuse `TIMEOUT_S`, `MAX_RETRIES`, retry logic nhất quán
✅ Pass: `chain.generate_queries` dùng `budget_s` riêng (`QUERYGEN_BUDGET_S=8.0`) tách khỏi `TOTAL_BUDGET_S=25.0` của summarize — không chiếm budget bước sau; test `test_budget_param_skips_remaining_tiers` xác nhận budget âm bị skip đúng
✅ Pass: Latency rule-path (enrich=false) không đổi — `_enrich` không được gọi khi `enrich=false`, chỉ thêm 2 key default vào dict trả về (`TestPrescriptionLatency` PASS)
✅ Pass: Ruff sạch trên toàn bộ file touched
✅ Pass: Coverage độc lập verify — `diagnosis.py` 100%, `anthropic/deepseek/gemini_provider.py` 100%, `chain.py` 95%, `orchestrator.py` 97%, tổng package `prescription` 98%
✅ Pass: `test_kb_manifest` (re-ingest KB, commit `b698cdc`) PASS — không còn regression tồn đọng

### RỦI RO & LƯU Ý
- AC "Recall agentic vs template trên golden set" (plan.md dòng 76) **chưa có số agentic** — cần user tự chạy `scripts/eval_query_gen.py` với `DEEPSEEK_API_KEY`/`GEMINI_API_KEY` thật rồi post vào issue #82. Baseline template hiện tại: **0.488** (14 scenario).
- Working tree hiện có thay đổi **không thuộc scope GH-82** chưa commit: `notebooks/kaggle_train_ablation.ipynb`, `scripts/grpc_client_demo.py` (modified), `docs/nckh/section5-discussion-vi.md`, `logs/nckh/ablation/` (untracked) — cần tách khỏi branch này trước khi ship (không phải part của diff `dev...HEAD` nên không ảnh hưởng review, nhưng cần dọn trước khi tạo PR để tránh lẫn vào commit history của GH-82).
- Chưa có PR / chưa chạy `/kltn-ship` — GitHub issue #82 vẫn label `status: implementing`.

### KẾT LUẬN
PASS — Độ tự tin: Cao
