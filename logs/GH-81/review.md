## BÁO CÁO CODE REVIEW — feat/GH-81-safety-gate-v2-output-validation — 2026-07-10
### Scope: AI
### Effort: Deep (serving pipeline + LLM chain + contract change REST/gRPC)

### TÓM TẮT
Safety gate v2 (GH-81): output validation deterministic (LOTO/thermal inject, PPE union theo ppe_matrix.md, blocklist negation-aware), blocked path trả rule-based + audit log, LLM-as-judge behind env flag (default off), expose `blocked` qua REST + proto field 20. Diff ~1114 dòng/18 file, 403 tests pass, không phát hiện Critical.

### PHÂN TÍCH

🔴 Critical: (không có)

🟡 Warning: `safety_gate.py:66` — `_NEGATION_RE` (`not|don't|never|avoid|prevent`) không bắt các phrasing hiếm như "cannot", "refrain from" → có thể block oan step an toàn. Chấp nhận được vì fail-safe: block oan → vẫn trả rule-based prescription hợp lệ, không mất dịch vụ. Gợi ý: bổ sung pattern khi gặp thực tế.

🟡 Warning: `safety_gate.py:71-99` — blocklist là finite regex list (4 nhóm hành động cấm); LLM có thể diễn đạt hành động nguy hiểm theo cách khác ("pry the cover off") → miss. Lớp phòng thủ còn lại: SYSTEM_PROMPT ràng buộc retrieved-docs-only + judge (khi bật). Giới hạn này inherent với rule-based — đã ghi rõ trong docstring.

🟡 Warning: `safety_gate.py:41` — v1 `ELECTRICAL_KEYWORDS` chứa `electrocution` nhưng LOTO injection trigger dùng `_ELECTRICAL_CRITICAL` (không có electrocution) → warning code ELECTROCUTION (nếu có) sẽ set human_required mà không inject LOTO. BMS hiện không emit code này — inconsistency lý thuyết, không sửa trong scope GH-81.

🟡 Warning: `orchestrator.py` (PPE union) — PPE string từ LLM có thể trùng ngữ nghĩa khác chữ với constant KB ("Insulated gloves" vs "Insulated gloves (>=500V)") → duplicate ngữ nghĩa trong `ppe_required`. Union không bao giờ drop PPE nên an toàn; chỉ là noise hiển thị.

🟡 Warning: `chain.py:89-131` — `judge_safety()` lặp lại vòng loop provider của `generate_prescription` (~25 dòng). Chủ ý giữ song song để không refactor code đã test (Surgical Changes); có thể extract helper chung ở ticket refactor sau.

✅ Pass: Kiến trúc nhất quán 2 transport — gRPC `Prescribe` và REST `/prescribe/` cùng gọi `run_prescription()`, không duplicate logic; parity test có field `blocked`.
✅ Pass: Contract — proto field 20 là số MỚI (không reuse), stub regen bằng `scripts/gen_proto.py`, runtime verified (`fields_by_name['blocked'].number == 20`, serialize round-trip OK); Pydantic `blocked: bool = False` backward-compatible.
✅ Pass: Gate là pure function (không log/network) — orchestrator giữ side-effects (audit log `safety_gate.audit`, JSON đủ: input, output bị block, pattern khớp, source blocklist/llm_judge) — test được qua caplog.
✅ Pass: Blocked path đúng spec — `blocked=True` không bao giờ leak LLM output (test mock chain trả banned steps → response là rule-based, HTTP 200); re-run gate 1 lần trên rule output với blocklist tắt → không thể loop.
✅ Pass: Blocklist CHỈ chạy với LLM output (`llm_generated=True`) — rule text chứa "do NOT use water" hợp lệ không bị block (test riêng); negation guard giới hạn trong cùng câu.
✅ Pass: PPE enforcement grounded `knowledge/safety/ppe_matrix.md` — electrical critical → +arc-flash +steel-toed; TEMP_ELEVATED → +IR thermometer; thermal critical → KHÔNG thêm PPE (matrix: no PPE substitutes for evacuation) mà inject evacuate step.
✅ Pass: Judge — env `SAFETY_LLM_JUDGE` default off; flag off → chain không được gọi (mock assert); unsafe → blocked path; judge raise/timeout → pass (không block oan); dùng chung LLM_PROVIDER_CHAIN + budget GH-79.
✅ Pass: Edge cases đủ theo issue — empty action_steps từ LLM → fallback ở `_enrich`; v1 call sites (4 positional args) chạy nguyên nhờ default params (test cũ giữ nguyên pass).
✅ Pass: Test matrix AC 3×3 đủ 9 ô (electrical/thermal/none × thiếu-LOTO/banned/sạch) + 7 banned + 4 negated parametrized.
✅ Pass: Coverage file sửa — safety_gate 100%, orchestrator 99%, llm/* 97–100%, schemas/prescribe 100% (AC ≥85%).
✅ Pass: Latency — `test_rule_path_under_100ms` PASS; gate chỉ regex/string matching, không network trên hot-path.
✅ Pass: Reproducibility/Data/Model checklist — KHÔNG đụng train/preprocess/scaler/window/seed; không thêm dependency mới (judge dùng SDK sẵn có); requirements.txt nguyên.
✅ Pass: `ruff check` sạch trên toàn bộ file GH-81.

### RỦI RO & LƯU Ý
- `tests/test_kb_manifest.py` FAIL pre-existing từ commit 32d0200 (KB thêm file, manifest chưa update) — fail cả trên tree sạch, KHÔNG do GH-81; cần fix ở commit riêng.
- 8 lỗi ruff toàn repo là pre-existing ở file ngoài scope (`grpc_gen` stub generated, `inference.py`, `test_confidence.py`).
- BE cần được thông báo field mới `blocked = 20` (chỉ THÊM field — wire compatible, client cũ bỏ qua an toàn).
- Judge bật qua env sẽ thêm 1 LLM call/enrich request — chỉ bật khi có budget (đúng thiết kế issue).
- `docs/nckh/section4-experiments-vi.md` đang modified trong working tree là WIP của user, KHÔNG thuộc GH-81 — không được stage khi ship.

### KẾT LUẬN
**PASS** — Độ tự tin: **Cao** (diff đọc trực tiếp từng hunk, field proto verify runtime, 403 tests pass, 5 warning đều mức chấp nhận được có ghi lý do)
