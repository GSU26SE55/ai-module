## BÁO CÁO CODE REVIEW — feat/GH-105-prescription-ticket-history — 2026-07-23
### Scope: AI
### Effort: Standard

### TÓM TẮT
Wiring nội bộ, không đổi contract — nối `ticket_history` vào diagnosis statement + battery-scoped past-case retrieval + fix một bug tiềm ẩn ở cache key (GH-84). Diff nhỏ, surgical, có test cho từng nhánh mới, không phá test cũ.

### PHÂN TÍCH

🟡 Warning: `src/services/prescription/history_store.py:12-17` — module docstring (usage example ở đầu file) vẫn ghi `retrieve_similar_accepted(context, top_k=2)`, chưa cập nhật để thể hiện `battery_id` kwarg mới. Không ảnh hưởng hành vi (backward-compatible), chỉ là doc nit — có thể sửa hoặc để lại, không block ship.

🟡 Warning: `src/services/prescription/diagnosis.py:34` / `docs/ai-be-integration.md` §9 — giả định thứ tự `ticket_history` là oldest→newest **chưa được BE xác nhận chính thức** (đã ghi rõ trong docs + plan.md, là quyết định có chủ đích khi lập plan, không phải sót). Nếu BE gửi ngược (newest→oldest), `ticket_history[-N:]` sẽ lấy nhầm N phần tử cũ nhất thay vì gần nhất — không crash, chỉ sai ngữ nghĩa "gần đây nhất". Rủi ro chấp nhận được ở mức Standard vì đã document rõ, nhưng cần theo dõi khi BE thực sự bắt đầu gửi data thật.

✅ Pass: `diagnosis.py` — `ticket_history` None/[] không render dòng "Past repairs" (test `test_no_ticket_history_omits_past_repairs_line`, `test_empty_ticket_history_omits_past_repairs_line`), cap đúng 5 phần tử cuối (`test_ticket_history_capped_to_last_five`).

✅ Pass: `history_store.py:114-151` — 2-tier query (battery-scoped → fallback global) đúng syntax ChromaDB `$and`, verified bằng test dùng ChromaDB thật (không mock) — `TestBatteryScopedRetrieval` (3 case: hit, fallback, backward-compat không truyền `battery_id`). Coverage: nhánh mới (dòng 131-142) nằm trong 86% coverage của file, phần miss (107-109, 149-151, 181-183, 200-201, 211-212) đều là `except Exception` defensive path có sẵn từ trước, không liên quan thay đổi này.

✅ Pass: `observability.py:44-51` — phát hiện đúng: `cache_key()` cũ (GH-84, cùng ngày) không hash `ticket_history` → sẽ cache-hit sai khi ticket_history đổi trong TTL 600s. Đã fix + có test riêng (`test_cache_key_distinguishes_ticket_history`, `test_different_ticket_history_not_cached_together` — integration test qua `run_prescription()` thật, không chỉ unit test hàm hash).

✅ Pass: `orchestrator.py` — threading `battery_id`/`ticket_history` xuyên suốt `_enrich()` → `build_diagnosis_statement()` + `retrieve_similar_accepted()` + `cache_key()`. Cả 2 transport (REST `routers/prescribe.py`, gRPC `grpc_server.py:294`) đều đã forward `ticket_history` vào `run_prescription(**context_kwargs)` từ trước (GH-83 era) — không cần sửa gì ở 2 file này, chỉ orchestrator tiêu thụ đúng field đã có sẵn.

✅ Pass: Backward-compat — tham số mới đều là trailing keyword-only với default (`battery_id: str = ""`, `ticket_history: list[str] | None = None`, `battery_id: str | None = None` trong `retrieve_similar_accepted`) — không phá vị trí positional args ở các call site cũ trong test suite.

✅ Pass: `enrich=false` (rule-path, dùng bởi luồng auto-ticket GH-23) không đổi hành vi — `ticket_history` chỉ được forward vào `_enrich()` trong nhánh `if enrich:`. `tests/test_prescription.py::TestPrescriptionLatency::test_rule_path_under_100ms` PASS.

✅ Pass: `pytest --cov=src` toàn repo — 539 passed, coverage 92% (≥85% target). `ruff check` — clean trên toàn bộ file đã sửa.

✅ Pass: `docs/ai-be-integration.md` — mục 9 mới mô tả rõ format, thứ tự giả định, cap 5, và đường link tới file cần sửa nếu giả định sai; mục 5 (idempotency) đã cập nhật mô tả cache key.

### RỦI RO & LƯU Ý
- Giả định thứ tự `ticket_history` (oldest→newest) cần BE xác nhận thực tế khi họ implement gửi field này — hiện tại field khả năng vẫn đang rỗng ở production (BE có thể chưa gửi), nên rủi ro chỉ phát sinh khi BE bắt đầu gửi data thật.
- 2 file `models/embeddings/*/length.bin` đang modified trong working tree nhưng không thuộc diff của GH-105 (đã modified từ trước session này) — không đụng tới, nhắc để tránh nhầm khi review diff tổng.

### KẾT LUẬN
**PASS** — Độ tự tin: **Cao**
