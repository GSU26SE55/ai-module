# HANDOFF — GH-10: Mở rộng MambaSOHPredictor chạy chuỗi dài L=4096

## Thông tin
- **Người thực hiện:** Nguyễn Phúc Duy (SE184821)
- **Ngày ship:** 2026-06-16
- **Status:** SHIPPED ⏳ (chờ reviewer approve)
- **Issue:** #10
- **PR:** #11 — https://github.com/GSU26SE55/ai-module/pull/11
- **Branch:** `feat/GH-10-mamba-long-seq-4096` (base PR = `feat/spectral_kurtosis`, stacked trên fix #9)

## Tiến độ Steps
- [x] B1 Preprocess: `scripts/preprocess_long.py` ghép cycle → 4096 + test — 2026-06-15
- [x] B2 Model P0-lite: tối ưu chunked prefix-scan + gỡ dead `_parallel_scan` + test (chunked==sequential L=512/600) — 2026-06-15
- [x] B3 Model P3: attention pooling (mặc định `"last"` giữ window=30) + 4 test — 2026-06-15
- [x] B4 Train P1+P2: `train_long()` warmup 256→4096 + gradient accumulation + `--long` CLI + 3 test — 2026-06-15
- [x] B5 Inference P4: `predict_soh_long` fast-path + `load_long_model` + 2 test — 2026-06-15
- [x] B6 Test + latency: unit test + benchmark L=4096 — coverage 92% — 2026-06-15

## Những gì đã làm
- `scripts/preprocess_long.py` (mới) — ghép discharge cycle NASA → chuỗi 4096, label=SOH cycle cuối, stride 128 (1083/159/50 windows), refit `feature_scaler_long.pkl`
- `src/models/soh_predictor.py` — P0-lite scan (slicing, gỡ `_parallel_scan`), ngưỡng scan 512→256, attention pooling option, no-checkpoint khi inference
- `scripts/train.py` — `train_long()` warmup + grad accumulation + eval-batch nhỏ + `--long`/`--eval-batch` CLI
- `src/services/inference.py` — `predict_soh_long` fast-path
- `src/core/model_loader.py` — `load_long_model()`
- `src/core/config.py` — `LONG_SEQ_LEN/STRIDE`, `WARMUP_STAGES`, `LONG_MAMBA_PATH`, `LONG_FEATURE_SCALER_PATH`
- tests: `test_train_long.py` (mới) + bổ sung `test_preprocess/test_models/test_inference`

## Kết quả
- reviewcode: ✅ PASS (W1 eval-batch OOM đã fix)
- test: ✅ PASS — 88 passed / 2 pre-existing fail / coverage 92%
- PR: ✅ tạo thành công (#11) — chờ reviewer approve

## Ghi chú (QUAN TRỌNG cho reviewer + bước sau)
- ⏳ **MAE/RMSE thật + latency GPU <100ms CHƯA verify** — phải chạy `preprocess_long.py` + `train.py --long` trên **Kaggle GPU** (local không đủ data/GPU, giống posture #9). PR chưa có số metric.
- ⚠️ **Data-scarcity:** chỉ 1083/159/50 windows (overlap ~97%, 3 pin) → nguy cơ overfit; nếu MAE không đạt <2% → hạ `LONG_SEQ_LEN=2048` (phương án trong plan).
- ⚠️ **CPU latency L=4096 = 170ms > 100ms** → SLA <100ms chỉ enforce GPU.
- 🔸 `models/weights/feature_scaler_long.pkl` để **untracked** — commit cùng `soh_mamba_long_v1.0.pth` sau khi train Kaggle (giữ cặp artifact đồng bộ).
- 🔸 P0→P0-lite: SSD/matmul không khả thi với A theo (d_inner,d_state) — đã sync comment lên issue.
- 🔸 2 test pre-existing fail (`test_spectral_features_ignore_dc_offset`, `test_load_split_rejects_stale_feature_version`) nên tạo issue `type: fix` riêng.
- 🔸 `predict_soh_long` chưa wire vào FastAPI router — cần task endpoint riêng nếu BE cần gọi long inference.
- Base PR là `feat/spectral_kurtosis` (đã merge fix #9), KHÔNG phải dev/main.
