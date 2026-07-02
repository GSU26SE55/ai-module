## TEST REPORT — GH-34 — 2026-07-02
### Scope: AI
### Môi trường: local (CPU, Windows) · Effort: Standard

### TÓM TẮT
`pytest tests/ --cov=src` → coverage **88% ≥ 85% target**. Các test liên quan #34 (train_long, models, extractor) PASS. 2 test FAIL trong `TestLongInference` do **thiếu monkeypatch `LONG_SCALER_PATH` + `scaler_long.pkl` chưa commit** — lỗi test-setup CÓ SẴN, KHÔNG do #34.

| Test case | Input | Expected | Actual | Status |
|-----------|-------|----------|--------|--------|
| `tests/test_train_long.py` (3) | train_long smoke | pass | pass | ✅ |
| `tests/test_models.py` | MambaSOHPredictor/MambaBlock | pass | pass | ✅ |
| smoke #34 (thủ công) | long d_state=32 build+forward+roundtrip; prod d_state=16 | 32≠16, finite | 101,997 vs 79,467 params, OK | ✅ |
| CLI `--long-d-state` | 16 / omit | 16 / 32 | 16 / 32 | ✅ |
| `test_long_latency_benchmark` | L=4096 random model | chạy (SLA <100ms GPU-only) | pass | ✅ |
| `test_predict_soh_long_chunked_path` | predict_soh_long L=600 | soh∈[0,100] | RuntimeError: scaler_long.pkl not found | ❌ pre-existing |
| `test_long_model_lazy_loaded` | lazy load long | model loaded | RuntimeError: scaler_long.pkl not found | ❌ pre-existing |

### Coverage
- Line coverage: **88%** (target AI ≥ 85%) ✅ — `config.py` 100%, `soh_predictor.py` 86%, `train.py` không nằm trong `--cov=src` (script).

### Bugs tìm được
- 🟡 [Pre-existing, KHÔNG do #34] `tests/test_inference.py::TestLongInference._setup_artifacts` — monkeypatch thiếu `LONG_SCALER_PATH` (chỉ patch SCALER_PATH/LONG_FEATURE_SCALER_PATH/LONG_MAMBA_PATH). `load_long_model` require `LONG_SCALER_PATH` (`scaler_long.pkl`) → check file thật (chưa commit) → RuntimeError. Fail y hệt trên dev. → nên fix ở issue riêng (thêm patch `LONG_SCALER_PATH` + dump scaler_long giả trong fixture).

### RỦI RO & LƯU Ý
- 2 fail **độc lập #34** (chứng minh: diff #34 chỉ chạm train.py/config.py/CLAUDE.md; test chỉ chạy model_loader/inference; load d_state từ checkpoint=4, không dùng LONG_D_STATE).
- Latency production window=30 **không đổi** (#34 không đụng train()/window=30 path).
- Acceptance empirical (d_state=32 có giảm MAE/RMSE trên B0048 + không overfit) → **Kaggle ablation** ở bước sau, ngoài local test.

### KẾT LUẬN
PASS (cho GH-34) — Độ tự tin: Cao. Coverage đạt; không có regression do #34. 2 test fail là lỗi test-setup có sẵn (thiếu monkeypatch LONG_SCALER_PATH) — khuyến nghị fix ở issue riêng, không block #34.
