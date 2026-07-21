## BÁO CÁO CODE REVIEW — feat/GH-87-ai-prescription-embed-nested — 2026-07-21
### Scope: AI
### Effort: Standard

### TÓM TẮT
Diff đúng scope plan (8 file nguồn + 2 file generated stub), không đụng file ngoài plan. Đã đọc toàn bộ diff (`git diff dev` — lưu ý local `dev` bị stale thiếu merge GH-67 nên đã fast-forward về `origin/dev` trước khi diff để loại nhiễu). 20 test liên quan trực tiếp GH-87 PASS, full suite 493 passed, coverage 92% (≥85% AC), ruff sạch.

### PHÂN TÍCH

✅ Pass: Proto field 24-26 không trùng với field 1-23 đã dùng (đã grep toàn bộ `PrescribeResponse` xác nhận) — append-only đúng như plan, không đổi số field cũ.

✅ Pass: `_to_prescribe_response()` (grpc_server.py) dùng hard-subscript `result["prediction"]`/`["anomaly"]`/`["risk"]` (không `.get()`) — nhất quán với pattern đã có sẵn của `_to_predict_response()` cho cùng 3 field, không phải inconsistency mới.

✅ Pass: `orchestrator.run_prescription()` — biến `prediction`/`anomaly`/`risk` đã tồn tại sẵn từ đầu hàm (`prediction_result.get(...)`), chỉ forward vào dict trả về, không có tính toán/forward-pass thêm → khớp AC latency. `test_rule_path_under_100ms` PASS xác nhận thực nghiệm.

✅ Pass: `PrescribeResponse.prediction`/`anomaly`/`risk` là required field (không optional) — an toàn vì chỉ có 1 call site duy nhất (`run_prescription()`) sinh ra dict cho schema này (REST router + gRPC servicer đều gọi qua nó), và `run_inference()` luôn chạy ở bước 1 bất kể `enrich` nên 3 key này luôn có mặt.

✅ Pass: Comment `confidence` đã sửa đúng bản chất (MC Dropout `soh_confidence`, không phải IsolationForest score) ở cả `protos/ai_service.proto` và `src/schemas/predict.py`, khớp với `src/services/inference.py:336` (`"confidence": prediction["soh_confidence"]`).

✅ Pass: Test parity (`test_prescribe_parity_with_rest`) mở rộng đúng field cần cho AC "is_borderline/stage_confidence xuất hiện trong response Prescribe" — bao gồm cả `stage_probabilities` (map field) và `risk.reasons` (repeated field). Test mới `test_response_nests_prediction_anomaly_risk_verbatim` xác nhận forward nguyên vẹn, không transform.

✅ Pass: Coverage per-file liên quan — `schemas/prescribe.py` 100%, `services/prescription/orchestrator.py` 100%, `grpc_server.py` 92% (2 dòng thiếu là `serve()`/`__main__` entrypoint, pre-existing không liên quan diff).

🟡 Warning: `models/embeddings/095c5d6b-.../length.bin` đang bị modify trong working tree (binary, không nằm trong diff của bất kỳ step nào trong plan) — có vẻ là artifact ChromaDB bị touch cục bộ khi chạy test/server ở phiên làm việc trước, không liên quan GH-87. **Không add file này khi `/kltn-ship`** — kiểm tra lại bằng `git status` trước khi `git add`, chỉ stage đúng 9 file trong Files table của plan (không tính stub generated).

🟡 Warning: local branch `dev` trước khi review bị stale (thiếu merge PR #102 GH-67) khiến `git diff dev...HEAD` ban đầu lẫn ~340 dòng thay đổi không liên quan (đã tự fix bằng `git branch -f dev origin/dev` trong lúc review này). Trước khi `/kltn-ship`, nên `git fetch origin && git branch -f dev origin/dev` (hoặc `git pull`) một lần nữa để chắc chắn base PR đúng, tránh PR diff bị lẫn nội dung thừa.

### RỦI RO & LƯU Ý
- Thay đổi mang tính additive/backward-compatible ở tầng wire (proto3 message field luôn implicit-optional) — BE cũ chưa đọc field mới vẫn hoạt động bình thường, không breaking.
- 3 field mới là required ở tầng Pydantic/REST — nếu tương lai có thêm 1 call site khác tạo `PrescribeResponse` mà không qua `run_prescription()`, sẽ lỗi validation ngay lập tức (fail-fast, đây là hành vi mong muốn chứ không phải rủi ro).
- Chưa chạy `scripts/benchmark_grpc.py --real-weights` (benchmark thật với model weights) — chỉ có unit-test latency check (`test_rule_path_under_100ms`, dummy path). Đủ để pass AC "không thêm forward pass" vì thay đổi thuần forward dict, nhưng nên nhắc nếu `/kltn-test` cần benchmark số thật.

### KẾT LUẬN
**PASS** — Độ tự tin: **Cao**
