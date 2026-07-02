## BÁO CÁO CODE REVIEW — feat/GH-34-long-dstate-32 — 2026-07-02
### Scope: AI
### Effort: Standard

### TÓM TẮT
Tăng d_state 16→32 CHỈ cho long-seq (config `LONG_D_STATE` + wiring `train_long`). Khu trú, đúng scope, không đụng production/RUL. Không có Critical. PASS về code; kiểm chứng "32 có cải thiện + không overfit" phụ thuộc Kaggle ablation.

### PHÂN TÍCH
✅ Pass: Scope — `LONG_D_STATE=32` độc lập global `D_STATE=16`. `train()` window=30 + RUL (ctor line 642/775/883) GIỮ `D_STATE=16`; chỉ `train_long` model ctor + checkpoint dùng param `d_state`.
✅ Pass: Correctness — `train_long(..., d_state=LONG_D_STATE)`; ctor `d_state=d_state`; checkpoint lưu `d_state` thực tế → `model_loader.load_long_model` (`checkpoint.get("d_state",16)`) dựng đúng 32. MambaBlock đã tham số hoá `d_state` → không sửa `soh_predictor.py`.
✅ Pass: Ablation — `--long-d-state` default `LONG_D_STATE` (32); `--long-d-state 16` chạy được để so sánh.
✅ Pass: Không đổi `d_model=64` → không đụng FiLM/attention/head dims; không xung đột MHA (#37) hay CAWR warmup (#38).
✅ Pass: Reproducibility (seed 42), scaler, data split, latency production — không đụng (window=30 nguyên vẹn).
✅ Pass: Smoke — long d_state=32 (101,997 params) forward finite + checkpoint roundtrip OK; production d_state=16 (79,467 params) không đổi; `pytest tests/test_train_long.py` 3 passed; ruff sạch vùng sửa.
🟡 Warning: `scripts/train.py` (argparse `--long-d-state`) — không validate ≥1; `--long-d-state 0` → MambaBlock shape error. Minor (user-controlled), plan đã ghi.
🟡 Warning: `config.py` — `LONG_MODEL_VERSION` giữ "2.1" dù d_state đổi (thay đổi kiến trúc long). Có chủ đích trong giai đoạn ablation (checkpoint load đúng vì đọc d_state từ file); **bump version khi finalize/commit model long thắng**.

### RỦI RO & LƯU Ý
- **Acceptance cuối chưa verify:** tăng capacity có thể overfit khi bottleneck là generalization (test 1 pin B0048). Phải chạy **Kaggle ablation d_state 16 vs 32** (cùng config khác) — chỉ giữ 32 nếu MAE/RMSE trên B0048 cải thiện.
- Doc: cập nhật `CLAUDE.md` (nơi chứa spec Mamba) thay vì `ai.md` như plan ghi — đúng chỗ hơn.
- Khi ship: chỉ stage `config.py`, `scripts/train.py`, `CLAUDE.md`, `logs/GH-34/` — KHÔNG `models/embeddings/*.bin`, `test_prediction_local.py`.

### KẾT LUẬN
PASS — Độ tự tin: Cao (code correctness). Empirical (32 có giúp / không overfit) để dành Kaggle ablation ở bước train/ship.
