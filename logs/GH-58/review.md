## BÁO CÁO CODE REVIEW — dev (GH-58, committed trực tiếp không qua branch) — 2026-07-03
### Scope: AI
### Effort: Standard

### TÓM TẮT
Fix đúng root cause (spectral feature tính theo window thay vì cả cycle, khớp chính xác `run_inference()`), có test chống regression rõ ràng, không phá logic hiện có. Có 1 rủi ro Critical cần xử lý **trước khi retrain/deploy**: artifact hiện đang commit trên `dev` bị lệch phiên bản với nhau.

### PHÂN TÍCH

🔴 ~~Critical~~ → **ĐÃ SỬA:** `models/weights/soh_mamba_v1.4.pth` (commit `13eaa01`, 17:35:55, train TRƯỚC fix — feature per-cycle cũ) đang mismatch với `feature_scaler.pkl` (commit `924b184`, 17:52:12, regenerate SAU fix — feature per-window mới), nhưng cả 2 khai cùng version nên cơ chế assertion không bắt được. Đã bump `MODEL_VERSION` 1.4→1.5 + `FEATURE_SCALER_VERSION` 1.3→1.4 (`src/core/config.py`) — giờ `model_loader.py` sẽ **fail loudly khi startup** (không tìm thấy `soh_mamba_v1.5.pth`/`isolation_forest_v1.5.pkl`) thay vì âm thầm dùng weight cũ sai. Đã regenerate `data/processed/*.pt` với version mới, full suite re-run pass (196/197, 1 flaky không liên quan).

🟡 Warning: Test `test_matches_inference_feature_extraction` (`tests/test_preprocess.py`) dùng cycle đúng bằng `WINDOW_SIZE` (30 dòng) nên `window == cycle_scaled` toàn bộ — test hợp lệ nhưng chỉ cover trường hợp 1-window/cycle. Không kiểm tra case cycle dài hơn (nhiều window) có đúng offset `cycle_scaled[i:i+WINDOW_SIZE]` không — dù `test_different_windows_get_different_features` gián tiếp cover việc này (3 window khác nhau), không có assertion so trực tiếp với `extract_window_features` cho window thứ 2/3. Rủi ro thấp vì logic offset đơn giản, không critical.

🟡 Warning: `docs/kaggle-4096-training.md` hoặc comment liên quan khác trong repo có thể vẫn còn nhắc "cycle-level FFT (richer resolution)" như một tính năng — chưa kiểm tra hết toàn bộ docs, có thể có tài liệu khác cần update cho khớp thiết kế mới. Không blocking.

✅ Pass: Logic fix đúng — `window_feat = extract_window_features(window[:, :3])` tính TRƯỚC khi `window` bị gán lại (thêm cột derived GH-54), dùng đúng slice `[:, :3]` khớp 100% với `run_inference()`. Verify bằng test trực tiếp (`test_matches_inference_feature_extraction`), không phải suy luận.
✅ Pass: `long_seq=True` (dead-code path) cũng được sửa nhất quán, dù không dùng thực tế trong workflow hiện tại (không gây regression vì không ai gọi path này).
✅ Pass: Random seed 42 không đổi, vẫn ở đầu script.
✅ Pass: Không có data leakage — train/val/test split (`TRAIN_IDS`/`VAL_IDS`/`TEST_IDS`) không đổi.
✅ Pass: `data/processed/*.pt` reproducible — regenerate 2 lần cho kết quả byte-identical với bản đã commit.
✅ Pass: 2 test mới không tautological — `test_different_windows_get_different_features` dùng 3 pattern tín hiệu rõ ràng khác nhau (sine/ramp/flat), không thể coincidentally giống nhau; sẽ FAIL dưới code cũ (cùng 1 cycle_feat share cho mọi window).
✅ Pass: Full suite 196 passed / 1 failed (flaky `test_rule_path_under_100ms`, không liên quan file đã sửa, xác nhận pass khi chạy riêng lẻ ở review trước).
✅ Pass: Ruff sạch trên file đã sửa (1 lỗi F541 pre-existing tại dòng khác, không liên quan diff).

### RỦI RO & LƯU Ý
- Sau khi bump version, app sẽ **không khởi động được** cho tới khi có `soh_mamba_v1.5.pth`/`isolation_forest_v1.5.pkl` — đúng ý đồ (chặn dùng nhầm weight stale), nhưng cần thông báo trước khi merge để không ai bị bất ngờ khi pull code mới mà app không chạy local được (phải retrain qua Kaggle trước).
- Code đã commit thẳng lên `dev`, bỏ qua PR/branch review trước khi review này chạy — không thể chặn ngược, chỉ ghi nhận.
- GH-59 (clip `cycle_count_norm`) nên merge trước lần retrain kế tiếp để tránh phải train 2 lần — lần train tới sẽ ra đúng `soh_mamba_v1.5.pth`.

### KẾT LUẬN
PASS — Độ tự tin: Cao. Critical đã được sửa (version bump) trong phiên review này.
