## TEST REPORT — GH-77 — 2026-07-04
### Scope: AI
### Môi trường: local (unit test + gRPC server thật với model weights thật `soh_mamba_v1.5.pth`/`feature_scaler.pkl`/`isolation_forest_v1.5.pkl`)

### TÓM TẮT
Toàn bộ unit test liên quan (51 test) pass, coverage 95% trên 2 file thay đổi chính. Verify thêm bằng gRPC server thật + demo payload named-field thật (B0048 degraded) — object-format và array-format cho kết quả nhất quán, `PredictStream` nhận đúng `reading_objects`, error path đúng, latency vẫn nằm trong SLA <100ms sau warm-up.

| Test case | Input | Expected | Actual | Status |
|-----------|-------|----------|--------|--------|
| Unit suite `test_grpc_server.py` + `test_grpc_contract.py` + `test_routers.py` | pytest | all pass | 51 passed | ✅ PASS |
| `reading_objects` (4-field) → normalize | gRPC named-field | khớp array tương đương | khớp | ✅ PASS |
| `reading_objects` (6-field, cycle_count+soc_percent) → normalize | gRPC named-field | khớp array tương đương | khớp | ✅ PASS |
| gRPC `reading_objects` vs REST object-format | cùng data | cùng normalized rows | khớp | ✅ PASS |
| Gửi cả `readings` + `reading_objects` | 2 field cùng lúc | ưu tiên `reading_objects` | đúng | ✅ PASS |
| `PredictStream` với `reading_objects` | stream 2 window (1 object-format, 1 array-format) | 2 response đúng thứ tự | `['B0048', 'B0048']` đúng thứ tự | ✅ PASS |
| **Live server** — demo `grpc_predict_degraded_object_format.json` (B0048, 30 dòng thật) qua `Predict` | reading_objects thật | 200/response hợp lệ, classification hợp lý (SOH thấp → Failed) | `soh=61.89%, classification=Failed` | ✅ PASS |
| **Live server** — cùng data qua `readings` (array) để so sánh | readings thật (khớp giá trị) | SOH gần bằng object-format (MC Dropout stochastic → chênh nhỏ) | `soh=61.74%` (chênh 0.15%, trong biên độ std MC Dropout) | ✅ PASS |
| **Live server** — gọi lại `reading_objects` lần 2 (cùng request) | reading_objects thật | classification ổn định (SOH dao động nhẹ do MC Dropout, không đổi hạng mục) | `soh=62.06%, classification=Failed` (ổn định) | ✅ PASS |
| **Live server** — window ngắn (5/30 dòng) qua `reading_objects` | 5 dòng | INVALID_ARGUMENT | `StatusCode.INVALID_ARGUMENT`, message "readings must have..." | ✅ PASS |
| **Live server** — latency warm-state (10 lần, sau 1 lần warm-up) | reading_objects vs readings | cả 2 < 100ms, chênh lệch nhỏ (overhead parse dict) | `reading_objects avg 75.3ms` / `readings avg 71.4ms` (overhead ~4ms) | ✅ PASS |
| `/health` qua live server | GET | status ok, model loaded | `status=ok, model_version=1.5, mamba_loaded=True` | ✅ PASS |

### Coverage
- `src/grpc_server.py`: 91% (8 dòng miss = `serve()`/`__main__` entrypoint có sẵn từ trước, không thuộc code GH-77)
- `src/schemas/predict.py`: 98% (2 dòng miss = nhánh lỗi validation `cycle_count`/`soc_percent` không nhất quán — thuộc scope GH-76, được cover bởi test suite của GH-76 khi merge, không phải gap của GH-77)
- Full suite project: 212 passed, 89% tổng thể (đã verify lại ở bước reviewcode) — vượt target ≥85%

### Latency
- Cold-start (chưa warm-up): 192.8ms (bình thường cho lần gọi đầu — model chưa warm, không phản ánh steady-state)
- Warm-state avg (10 lần, sau warm-up): `reading_objects` 75.3ms | `readings` (mảng) 71.4ms — cả 2 đạt SLA <100ms (`rules/tech/ai.md`), overhead của named-field parsing (~4ms) không đáng kể

### Bugs tìm được
- Không tìm thấy bug nào trong scope GH-77.

### RỦI RO & LƯU Ý
- Đã verify lại lưu ý từ `/kltn-reviewcode`: `src/schemas/predict.py` trên nhánh này chứa thay đổi của GH-76 (chưa merge) — bắt buộc merge GH-76 → dev trước, rebase GH-77, rồi mới ship GH-77.
- Server test thật đã dừng sạch sau khi test xong (verify qua `netstat` — không còn process nào LISTEN cổng 50051); không để lại process hoặc file scratch nào trong repo.
- SOH chênh lệch nhỏ (0.15-0.3%) giữa các lần gọi object-format/array-format là do MC Dropout (stochastic by design, `docs`/`ai.md` — không phải bug, đã biết từ trước).

### KẾT LUẬN
PASS — Độ tự tin: Cao
