## BÁO CÁO CODE REVIEW — feat/GH-24-ai-phase-4-evaluation — 2026-07-22
### Scope: AI
### Effort: Deep (schema/proto contract change GH-23 + new eval module GH-24, cùng working tree)

> Lưu ý: branch chứa công việc của **2 issue** (GH-23 + GH-24) chưa commit — theo đúng ghi chú trong `logs/GH-23/plan.md`. Review này bao trùm toàn bộ diff working-tree hiện tại (`git diff` + untracked), không chỉ riêng GH-24, vì cả hai sẽ cần tách file khi ship.

### TÓM TẮT
Code chất lượng tốt, logic đúng, test mới đều PASS (18/18 `test_evaluate_prescription.py`, 7/7 test liên quan trong `test_grpc_server.py`), ruff sạch. Có 2 vấn đề cần xử lý trước khi ship: (1) diff nhị phân ngoài ý muốn trên KB embeddings production do harness/test chạm vào ChromaDB thật, và (2) 2 test "unit" bị coi là offline nhưng thực chất vẫn mở kết nối tới vector store thật trên đĩa.

### PHÂN TÍCH

🟡 **Warning: `models/embeddings/{095c5d6b,5d6594ba}/length.bin` bị modify ngoài scope cả 2 plan** — `git diff --stat` cho thấy 2 file nhị phân này đổi (size giữ nguyên 4000 bytes, nội dung khác) dù không file nào trong `logs/GH-23/plan.md` hay `logs/GH-24/plan.md` liệt kê chúng. Nguyên nhân: `RagRetriever.__init__` (`src/services/prescription/rag_retriever.py:36`) mở `chromadb.PersistentClient(path=EMBEDDINGS_DIR)` trỏ thẳng vào `models/embeddings/` (KB production, đã commit) — `eval/evaluate_prescription.py:235` (`main()`) và 2 test dưới đây khởi tạo `RagRetriever()` thật nên chạm vào store này mỗi lần chạy.
   - **Cách fix:** trước khi `git add`, kiểm tra `git diff models/embeddings/` — nếu xác nhận đây chỉ là ChromaDB ghi lại metadata nội bộ (không đổi nội dung/số lượng doc, kiểm bằng `python scripts/ingest_rag.py --verify` hoặc so `results.json` coverage trước/sau) thì `git checkout -- models/embeddings/` để loại khỏi commit; nếu không chắc, KHÔNG `git add -A` mù mà add từng file theo đúng bảng Files của từng plan.

🟡 **Warning: `tests/test_evaluate_prescription.py::TestRunScenarioAndEvaluate` — 2 test không thực sự offline** — `test_evaluate_reports_sop_overlap_once_per_scenario` (dòng 140) và `test_hybrid_arms_have_none_faithfulness_without_llm_key` (dòng 152) gọi `evaluate([...], encoder=FakeEncoder())` cho cả 3 nhánh kể cả `hybrid_template`/`hybrid_agentic`, nhưng chỉ mock `llm.chain.is_available` — không mock `orchestrator._get_retriever` như `test_rule_arm_never_touches_retriever` (dòng 113-120) đã làm cho nhánh rule. Kết quả: 2 nhánh hybrid trong 2 test này gọi `RagRetriever()` thật → mở `PersistentClient` vào `models/embeddings/` thật mỗi lần `pytest` chạy — đúng là nguồn gây ra Warning phía trên, và mâu thuẫn với docstring module (dòng 1: "Tests for eval/evaluate_prescription.py") ngụ ý test thuần công thức không cần I/O ngoài.
   - **Cách fix:** thêm `patch.object(orchestrator, "_get_retriever", return_value=<fake retriever không retrieve gì>)` (hoặc mock ở tầng thấp hơn) cho 2 test này, cùng pattern với `test_rule_arm_never_touches_retriever`, để test thật sự hermetic và không ghi vào KB production mỗi lần CI chạy.

✅ Pass: `random.seed(42)` + `np.random.seed(42)` set đầu `eval/evaluate_prescription.py` (dòng 60-61) — đúng rule bắt buộc seed.
✅ Pass: history store được patch sang tempdir (`run_scenario` dòng 125) — không ghi vào `models/prescription_history/` thật, đúng như plan đã lường trước.
✅ Pass: `run_inference` được mock trả dict cố định từ golden set (dòng 124) — tách khỏi model SOH/anomaly thật, kết quả coverage/sop_overlap reproducible.
✅ Pass: công thức `compute_recall`/`compute_sop_overlap`/`compute_faithfulness` đúng theo README, xử lý đúng edge case `expected` rỗng → `0.0`, không docs/text rỗng → `None` (không nhầm với `0.0`).
✅ Pass: `run_scenario()` gọi `orchestrator.run_prescription(readings, battery_id, enrich=..., agentic=...)` đúng signature (`orchestrator.py:271-278`).
✅ Pass: test contract GH-23 (`test_prescribe_anomaly_event_contract_for_ticket_mapping`) assert đủ field BE cần map ticket, action_code set khớp đúng 4 giá trị thật trong `rule_prescription.py` (MONITOR/SCHEDULE_MAINTENANCE/SCHEDULE_REPLACEMENT/REPLACE_IMMEDIATELY) — không thiếu case.
✅ Pass: proto/docstring update (GH-23) chỉ sửa comment, không đổi field number — đúng contract rule `ai.md`.
✅ Pass: `docs/ai-be-integration.md` semantics `priority` (urgency signal, không phải Priority cuối) khớp đúng `Priority Policy` trong `design.md` — không lấn quyền Manager triage.
✅ Pass: `pytest tests/test_evaluate_prescription.py` (18 passed) + `pytest tests/test_grpc_server.py -k "prescribe or anomaly_event or contract"` (7 passed) + `ruff check` trên toàn bộ file mới/sửa — sạch.

### RỦI RO & LƯU Ý
- `logs/GH-24/plan.md` — Bước 6 (chạy harness thật với LLM key) và Bước 7 (`pytest --cov=src` full suite + `ruff check` toàn repo) vẫn `[ ]` chưa làm; toàn bộ 6 Acceptance Criteria cũng còn `[ ]`. Report hiện có ở `logs/eval/report.md` là chạy **không có LLM key** (0/14 enriched, faithfulness toàn N/A) — chưa đạt AC "số liệu thật (không phải placeholder)". Đây không phải lỗi code, chỉ là việc chưa hoàn tất — không tự ý tick AC.
- `logs/GH-23/plan.md` tự đánh dấu `Status: REVIEWING` và mọi Step/AC đã tick từ trước, nhưng chưa từng qua `/kltn-reviewcode` thật (không có `review.md` cũ) và issue #23 trên GitHub vẫn label `status: init`. Review lần này áp dụng cho cả 2 issue.
- Không có commit nào trên branch — toàn bộ thay đổi ở working tree. Khi ship, nhớ tách `git add` theo đúng bảng Files của từng plan (GH-23: proto/schemas/test_grpc_server.py/docs; GH-24: eval/ + tests/test_evaluate_prescription.py + logs/eval) — không `git add -A`.

### KẾT LUẬN
**PASS** (với 2 Warning cần xử lý trước khi `git add`/ship, không có Critical) — Độ tự tin: Cao
