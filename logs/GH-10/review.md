## BÁO CÁO CODE REVIEW — feat/GH-10-mamba-long-seq-4096 — 2026-06-15
### Scope: AI
### Effort: Deep (preprocess + model + train + inference)

### TÓM TẮT
Feature L=4096 (preprocess ghép cycle, P0-lite scan, attention pooling, warmup+grad-accum,
fast-path inference) implement đầy đủ 6 bước, đúng các rule cốt lõi AI (seed 42, không data
leakage, scaler workflow chuẩn). Không có lỗi Critical. Một số Warning về vận hành ở L=4096 cần
xử lý trước khi train thật trên Kaggle GPU.

### PHÂN TÍCH

✅ **Reproducibility**
- `preprocess_long.py`: SEED=42 + random/np/torch seed ở đầu script ✓
- `train_long()`: `torch.manual_seed(SEED)` trước khi init model, DataLoader có `generator` + `worker_init_fn` seeded ✓
- Kế thừa `cudnn.deterministic` của #9 ✓

✅ **Data / scaler workflow**
- Split theo battery ID (train B0005/06/07; B0018 70/30 timeline), KHÔNG cross-battery trong 1 chuỗi, không shuffle ✓
- MinMaxScaler **tái dùng** `scaler.pkl` (không refit) — đúng vì raw scaling độc lập windowing ✓
- `feature_scaler` long **chỉ fit trên train**, transform val/test → không leakage ✓
- Inference (`predict_soh_long`) load `scaler.pkl` + `feature_scaler_long.pkl` đã lưu — không tạo scaler mới ✓
- Label = SOH cycle cuối (nhất quán giữa preprocess `make_long_windows` và mục tiêu seq→scalar) ✓

✅ **Model**
- Vẫn chỉ 2 core model (Mamba + IsolationForest); attention pooling là layer trong Mamba, KHÔNG phải model thứ 3 ✓
- Mặc định `pooling="last"` → forward window=30 byte-for-byte không đổi (36 test cũ pass) ✓
- P0-lite scan: tối ưu prefix-scan bằng slicing, vẫn functional/autograd-safe; `test_streaming_scan_matches_full_sequential_scan` (L=600) pass → correctness giữ nguyên ✓
- Target MAE<2%/RMSE<3% giữ nguyên trong `train_long` (log + warning) ✓
- Inference fast-path bỏ checkpoint khi `torch.is_grad_enabled()=False` → đúng (no backward) ✓

🟡 **Warning**
- ~~`train_long` eval batch 256 OOM ở L=4096~~ → **ĐÃ FIX (2026-06-15):** thêm tham số `batch_size` cho `evaluate()`, `train_long` dùng `eval_batch=16` + CLI `--eval-batch`. `train()` window=30 giữ nguyên default 256.
- `train_long` warmup: `x_feat` tính trên cửa sổ 4096 đầy đủ nhưng các stage đầu model chỉ thấy chuỗi truncate (-stage_len). Bất nhất nhẹ ở stage warmup (stage cuối nhất quán). Chấp nhận được cho mục đích ổn định optimize, nhưng nên ghi rõ.
- `predict_soh_long` **chưa wire vào FastAPI router** — BE chưa gọi được long inference qua API. Đúng scope (B5 = service + loader), nhưng cần task endpoint riêng nếu BE cần.
- `docs/overall.md` đang modified trong working tree — **ngoài scope GH-10**, PHẢI loại khi `/kltn-ship` (giống cách đã làm với GH-9).
- Attention pooling thực chất là **global attention pool** (softmax toàn chuỗi), không phải "causal" theo nghĩa autoregressive — hợp lý cho seq→scalar; chỉ là vấn đề tên gọi.

### RỦI RO & LƯU Ý
- **Chưa verify số thật:** MAE/RMSE và latency GPU <100ms phải chạy trên Kaggle GPU + NASA data (local không có) — giống posture GH-9. Unit test chỉ verify logic/shape/correctness scan, không verify hội tụ.
- **Data-scarcity:** ghép tới 4096 → ít sample độc lập (sliding overlap cao) → nguy cơ overfit; chưa chắc đạt MAE<2% cho tới khi train thật. Plan đã nêu phương án hạ L=2048 nếu cần.
- **CPU latency L=4096 = 169ms > 100ms** (đo trong benchmark) → SLA chỉ enforce GPU (đúng quyết định deploy).
- 2 test fail toàn suite là **pre-existing** (đã ghi GH-9 test.md): `test_spectral_features_ignore_dc_offset`, `test_load_split_rejects_stale_feature_version` — không phải regression GH-10. Nên tạo issue `type: fix` riêng.
- P0 → P0-lite (SSD infeasible 172GB) đã sync comment lên issue #10.

### KẾT LUẬN
**PASS** — Độ tự tin: **Trung bình–Cao**
(Không có Critical; rule seed/leakage/scaler đều đạt; coverage 92% ≥85%; file GH-10 ruff sạch.
Confidence không tuyệt đối vì số liệu MAE + latency GPU còn chờ verify trên Kaggle — bước ngoài unit test.)
