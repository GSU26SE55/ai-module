## TEST REPORT — GH-10 — 2026-06-15
### Scope: AI
### Môi trường: local (CPU, Windows 11, Python 3.11.9)

### TÓM TẮT
Toàn bộ test trong scope GH-10 PASS: 88 passed / 2 failed (2 fail là pre-existing, ngoài scope —
đã ghi trong GH-9 test.md). Coverage tổng 92% (≥85%). Benchmark L=4096 chạy được; CPU 170ms (SLA
<100ms enforce trên GPU theo quyết định deploy, CPU chỉ ghi nhận). Số MAE/RMSE thật + latency GPU
chờ verify trên Kaggle GPU (ngoài phạm vi unit test, giống posture GH-9).

| Test case | Input | Expected | Actual | Status |
|-----------|-------|----------|--------|--------|
| make_long_windows count+shape | T=40,seq=8,stride=4 | 9 windows (8,6)+(54) | đúng | ✅ PASS |
| long window label = last timestep SOH | soh_ts=arange | last-step value | đúng | ✅ PASS |
| short timeline → empty | T=5 < seq=8 | shape (0,8,6) | đúng | ✅ PASS |
| attention pooling output shape | (4,64,6) | (4,) | (4,) | ✅ PASS |
| invalid pooling raises | pooling="mean" | ValueError | raised | ✅ PASS |
| attention grad flows | backward | attn_score.grad≠None | đúng | ✅ PASS |
| attention ≠ last-token | shared weights | not allclose | đúng | ✅ PASS |
| chunked==sequential scan (P0-lite) | L=600 random | allclose fp32 | allclose | ✅ PASS |
| truncate_seq keeps last N | (2,10,3),N=4 | X[:,-4:] | đúng | ✅ PASS |
| truncate_seq noop when shorter | N>len | unchanged ref | đúng | ✅ PASS |
| train_long smoke (warmup+accum) | synthetic, stages[4,8] | save ckpt attention | saved | ✅ PASS |
| predict_soh_long chunked path | L=600, cpu | soh∈[0,100] | đúng | ✅ PASS |
| long model lazy loaded | first call | model+scaler loaded | đúng | ✅ PASS |
| latency benchmark L=4096 | (1,4096,6) cpu | recorded | 170.1ms (CPU) | ✅ PASS |
| test_models suite (regression) | window=30 | 36/36 pass | 36/36 | ✅ PASS |
| test_inference pipeline (regression) | window=30 | pass | pass | ✅ PASS |

### Coverage
- Line coverage tổng: **92%** (target ≥ 85% ✅)
- `src/models/soh_predictor.py`: 99% · `src/services/inference.py`: 92% · `src/core/config.py`: 100%
- `src/core/model_loader.py`: 53% — phần miss là `load_models()` + `load_long_model()` (cần file artifact thật để cover; test long-loader cover qua monkeypatch path khác). Không phải logic GH-10 mới chưa test.

### Latency
- L=4096 (CPU, d_model=64 attention): **avg 170.1ms** — > 100ms → SLA chỉ enforce GPU (đúng quyết định deploy). GPU benchmark assert <100ms sẽ chạy trên Kaggle.
- L=30 (window cũ, CPU): không đổi so với GH-9 (~4.8ms).

### Bugs tìm được
- Không có bug trong scope GH-10.
- 🟡 (ngoài scope) 2 test pre-existing fail — verified hỏng từ baseline (đã ghi GH-9 test.md), KHÔNG phải regression GH-10:
  - `test_extractor::TestExtractWindowFeatures::test_spectral_features_ignore_dc_offset`
  - `test_preprocess::TestProcessedFeatureVersion::test_load_split_rejects_stale_feature_version`
  - → nên tạo issue `type: fix` riêng.

### RỦI RO & LƯU Ý
- **Chưa verify số thật:** MAE<2%/RMSE<3% + latency GPU <100ms phải chạy `preprocess_long.py` (NASA data) → `train.py --long` trên Kaggle GPU. Unit test chỉ verify logic/shape/correctness scan, KHÔNG verify hội tụ.
- **Data-scarcity:** ghép cycle tới 4096 → ít sample độc lập → nguy cơ overfit; nếu MAE val không đạt, hạ L=2048 (phương án trong plan).
- W1 (eval batch OOM ở L=4096) đã fix trong review → `eval_batch=16`.
- `docs/overall.md` ngoài scope — phải loại khi `/kltn-ship`.

### KẾT LUẬN
**PASS** — Độ tự tin: **Trung bình–Cao**
(Mọi test GH-10 xanh, coverage 92%, regression window=30 nguyên vẹn, benchmark chạy được.
Confidence chưa tuyệt đối vì MAE + latency GPU còn chờ verify Kaggle — bước ngoài unit test.)
