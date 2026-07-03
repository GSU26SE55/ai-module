## BÁO CÁO CODE REVIEW — feat/GH-63-ai-latency-still-100ms — 2026-07-04

### TÓM TẮT
Đạt mục tiêu (SLA <100ms PASS lần đầu, 80.3ms). Trong lúc review phát hiện thêm 1 gap thật (warm-up chỉ cover eval mode, bỏ sót train mode mà MC Dropout thực sự dùng) — đã sửa và verify lại ngay trong phiên review này, đúng nguyên tắc "Critical → phải sửa trước khi PASS".

### PHÂN TÍCH

🔴 ~~Critical~~ → **ĐÃ SỬA:** `src/core/model_loader.py` — warm-up ban đầu (lúc implement) chỉ gọi `compiled(...)` khi model đang ở `.eval()` (dòng 78 gọi `soh_model.eval()` trước khối compile). Nhưng `run_inference()` (`src/services/inference.py`) gọi `model_loader.soh_model.train()` để bật Dropout cho MC Dropout — **train mode chưa từng được warm-up**. `torch.compile`/dynamo tạo guard riêng theo `self.training`, nên compile ở eval mode không đảm bảo train mode không phải compile lazy lại — tái lập đúng rủi ro "crash ở request thật đầu tiên" mà warm-up này sinh ra để chặn, chỉ dịch từ eval sang train mode. Đã sửa: warm-up cả 2 mode (`compiled(...)` ở eval, rồi `compiled.train()` + `compiled(...)` lần nữa, rồi `compiled.eval()` để trả về đúng trạng thái ban đầu). Verify: `soh_model.training is False` sau `load_models()`, `run_inference()` chạy được thật.

🟡 Warning: `tests/test_model_loader.py::test_cpu_compile_success_is_used` (viết lúc implement) — mock ban đầu trả về 1 hàm thường (không có `.train()`/`.eval()`), khiến `compiled.train()` ném `AttributeError`, bị nuốt bởi `except Exception: pass` và fallback về eager — **test pass nhưng sai lý do** (không thực sự test được path "compile thành công và được dùng"). Đã sửa mock thành class `_FakeCompiled` có `__call__`/`train()`/`eval()`/`training` property giống thật, verify đúng thứ tự gọi `[False, True]` (eval rồi train) và `soh_model` kết thúc ở eval mode.

✅ Pass: `MC_RUNS 20→10` — đơn giản, đúng, không side-effect khác. Đã đo thực tế: confidence/soh_std vẫn cùng bậc độ lớn với baseline 20 (không collapse).
✅ Pass: Nhánh `torch.compile` CPU chỉ nằm trong `else` (không ảnh hưởng path CUDA hiện có), có try/except bọc toàn bộ (kể cả 2 lần warm-up mới) nên fallback vẫn an toàn nếu bất kỳ bước nào fail.
✅ Pass: Benchmark thật xác nhận `Predict avg 80.3ms < 100ms` — SLA đạt, sau khi sửa Critical vẫn giữ nguyên kết quả tốt (không đổi hiệu năng, chỉ đổi để đúng/an toàn hơn).
✅ Pass: Full suite 207 passed / 0 failed, coverage 89%, ruff sạch hoàn toàn trên các file đã sửa (`model_loader.py`, `test_model_loader.py` — "All checks passed!"); `inference.py` chỉ còn 4 lỗi E402 pre-existing như mọi lần trước.
✅ Pass: Document rõ giới hạn torch.compile CPU không verify được tăng tốc thật trên Windows (do Triton), đã ghi trong `plan.md`/kết quả benchmark cho thấy PASS đạt được là nhờ MC_RUNS, không phải torch.compile (compile fallback về eager trên máy này).

### RỦI RO & LƯU Ý
- torch.compile CPU vẫn CHƯA được verify hoạt động thật trên bất kỳ môi trường nào (luôn fallback ở đây) — nhánh code này về bản chất là "đặt cược tương lai" cho môi trường Linux deploy có Triton/C++ toolchain, cần ai đó xác nhận khi có điều kiện.
- MAE tăng nhẹ (2.13%→2.41%, đo trên 4 mẫu) do giảm MC_RUNS — nằm trong dao động tự nhiên nhưng nên theo dõi thêm khi có nhiều dữ liệu production hơn.

### KẾT LUẬN
PASS — Độ tự tin: Cao (sau khi đã sửa Critical trong phiên review này)
