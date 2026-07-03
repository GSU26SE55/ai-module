## BÁO CÁO CODE REVIEW — feat/GH-62-ai-optimize-mc-dropout — 2026-07-04
### TÓM TẮT
Fix đúng, đơn giản, hiệu quả rõ rệt (494.8ms → 119.3ms, 4.15x). Đã verify kỹ điểm quan trọng nhất (không có BatchNorm/layer phụ thuộc cross-sample) nên batching không đổi ý nghĩa toán học so với vòng lặp tuần tự cũ — chỉ đổi cách gọi, không đổi công thức.

### PHÂN TÍCH

✅ Pass: `xb = x_tensor.repeat(MC_RUNS,1,1)` / `xfb = x_feat_tensor.repeat(MC_RUNS,1)` đúng shape `(20,30,6)`/`(20,57)`, khớp input mà `MambaSOHPredictor.forward()` đã hỗ trợ sẵn (kiến trúc generic theo batch dimension, train.py vốn dùng batch=32).
✅ Pass: **Đã kiểm tra không có `BatchNorm`** trong `MambaSOHPredictor`/`MambaBlock` (chỉ có `LayerNorm` + `Dropout`, cả 2 đều xử lý độc lập theo từng sample, không phụ thuộc thống kê giữa các sample trong batch) — xác nhận batching cho **kết quả tương đương toán học** với vòng lặp tuần tự cũ (20 lần dropout mask độc lập), không phải chỉ nhanh hơn mà còn đúng hơn về mặt thống kê MC-Dropout (không bị coupling giữa các sample).
✅ Pass: `mc_preds = (model(xb, xfb) * 100).tolist()` — output shape `(20,)` (do `forward()` có `.squeeze(-1)`), `.tolist()` cho list 20 float, tương thích 100% với code phía sau (`np.mean`/`np.std` không đổi).
✅ Pass: `_MC_LOCK` + `try/finally` (train→eval) giữ nguyên, không có regression về thread-safety.
✅ Pass: Test `test_mc_dropout_batched_still_stochastic` verify đúng thứ cần verify (dropout mask không bị collapse, `soh_std>0`) — không tautological.
✅ Pass: Full suite 205 passed / 0 failed (kể cả flaky test trước đây lần này cũng pass), coverage 87%, ruff chỉ 4 lỗi E402 pre-existing (không liên quan diff này).
✅ Pass: Benchmark thật xác nhận cải thiện đúng như dự đoán trong plan (494.8ms→119.3ms, gần khớp số đo thử 295ms→120ms lúc viết issue).
✅ Pass: Demo payload accuracy không regression (MAE 2.127% vs 2.19% trước đó — chênh trong dao động MC Dropout tự nhiên).

🟡 Warning: `tests/test_inference.py::test_mc_dropout_batched_faster_than_naive_loop` — so sánh thời gian trực tiếp (`assert batched_ms < sequential_ms`) là test dựa trên timing, về nguyên tắc có rủi ro flaky nhỏ trên máy CI tải nặng/không ổn định (dù chênh lệch lý thuyết đủ lớn — batch giảm overhead gọi Python 19 lần — nên rủi ro thực tế thấp). Có thể chấp nhận được vì đây là sanity-check phụ (không phải nguồn xác nhận SLA chính thức, đó là việc của `scripts/benchmark_grpc.py`), nhưng nên biết trước nếu sau này CI báo flaky ở đúng test này.

### RỦI RO & LƯU Ý
- Latency benchmark vẫn **FAIL** (119.3ms > 100ms) dù cải thiện lớn — ticket này KHÔNG tự động làm SLA pass, cần quyết định thêm ở tầng deploy/leader (đã ghi trong `benchmark_result.md`, không phải việc của code review chặn PR này).
- Code đang ở branch riêng `feat/GH-62-ai-optimize-mc-dropout`, đúng lần này (khác GH-58/59 đã lỡ commit thẳng `dev`).

### KẾT LUẬN
PASS — Độ tự tin: Cao
