# Plan — GH-13: RUL prediction (cycle-level Mamba)

## Metadata
- **Status:** PLANNING | **Role:** AI | **Ngày:** 2026-06-16
- **Issue:** #13 — https://github.com/GSU26SE55/ai-module/issues/13
- **Sprint:** Sprint 3 (deadline 2026-06-27)
- **Branch:** `feat/GH-13-rul-cycle-level`

## Mục tiêu
Dự đoán **RUL (Remaining Useful Life)** cho pin NASA bằng cách chuyển từ trục
timestep (L=4096 raw — fail MAE 3.81%) sang **trục chu kỳ**: mỗi token = 1 chu kỳ,
biểu diễn bằng vector feature spectral/kurtosis tính *per-cycle*. Đây là baseline
sạch, mở rộng sau (observability-index, thêm baselines) qua các issue tiếp theo.

## Scope
**Trong scope (baseline):**
- Preprocessing cycle-level → dataset RUL.
- Model `RULPredictor` (tái dùng `MambaBlock`), dự đoán RUL scalar.
- Train + eval (MAE/RMSE theo đơn vị *chu kỳ*), split theo battery ID.
- Unit test preprocessing + model shape.

**NGOÀI scope (issue sau, đã chừa cờ/param sẵn):**
- Observability-index auxiliary loss (`use_obs_loss=False` mặc định).
- So sánh parameter-parity với LSTM/PatchTST/SimpleMamba (Table IV/V).
- Confidence/uncertainty head.
- KHÔNG đụng model SOH production (window=30) — giữ nguyên spec.

## Quyết định thiết kế (đã chốt với user)
| # | Quyết định | Giá trị | Config? |
|---|-----------|---------|---------|
| 1 | Nhãn RUL | số chu kỳ còn lại tới **EOL = SOH ≤ 80%** (lần chạm đầu tiên) | `EOL_SOH=80.0` |
| 2 | Lookback | **30 chu kỳ**/mẫu | `RUL_LOOKBACK=30` |
| 3 | Observability-index | **tắt** ở baseline, bật sau qua flag | `use_obs_loss` |
| 4 | Token = 1 chu kỳ | vector **54-dim** (spectral+kurtosis per-cycle, tái dùng `extract_window_features`) | — |
| 5 | Split | train B0005/06/07 · val/test B0018 (70/30 theo chu kỳ) | giống SOH |
| 6 | Loss | MSE (Huber để mở rộng sau) | — |

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/core/config.py` | modify | thêm `RUL_LOOKBACK=30`, `EOL_SOH=80.0`, `RUL_*_PATH`, `RUL_FEAT_DIM=54` |
| `scripts/preprocess_rul.py` | create | dựng dataset cycle-level → `data/processed_rul/{train,val,test}.pt` |
| `src/models/rul_predictor.py` | create | `RULPredictor` tái dùng `MambaBlock`; cờ `use_obs_loss` (no-op baseline) |
| `scripts/train.py` | modify | thêm hàm `train_rul()` + arg `--rul` (không đụng `train`/`train_long`) |
| `tests/test_rul.py` | create | test windowing/nhãn RUL + output shape model |

## Approach

**Data flow (preprocess_rul.py):**
```
load_cycles(battery) → [(cycle(T,6), soh), ...]  # đã có sẵn
  → mỗi cycle: feat = extract_window_features(cycle[:, :3])   # 54-dim
  → chuỗi feat theo cycle: (n_cycles, 54)
  → EOL_idx = chu kỳ đầu tiên có soh ≤ 80
  → trượt cửa sổ 30 cycle (stride 1):
        X[i]   = feats[i : i+30]          # (30, 54)
        y[i]   = max(EOL_idx - (i+29), 0) # RUL tại cycle cuối window
     (chỉ lấy window có cycle cuối < EOL để nhãn có ý nghĩa)
  → refit StandardScaler cho feat trên TRAIN only (lưu kèm)
  → split: B0005/06/07 train; B0018 chia 70/30 val/test
```

**Model (rul_predictor.py):**
```
x (B, 30, 54) → Linear(54→64) → MambaBlock×2(d_model=64) → LayerNorm
  → pooling (last|attention) → Linear(64→32) → GELU+Dropout → Linear(32→1) → RUL
# use_obs_loss=False: forward thuần; chừa hook để issue sau cộng auxiliary loss
```

**Train (train_rul):** Adam(lr=1e-3), MSELoss, seed=42, early stopping; báo
MAE/RMSE theo **đơn vị chu kỳ**. Lưu `models/weights/soh_mamba_rul_v1.0.pth`.

## Steps
- [ ] B1: thêm config RUL (`src/core/config.py`)
- [ ] B2: `scripts/preprocess_rul.py` + chạy sinh dataset, in summary (số mẫu/pin, dải RUL)
- [ ] B3: `src/models/rul_predictor.py`
- [ ] B4: `train_rul()` trong `train.py` + chạy train baseline, ghi log
- [ ] B5: `tests/test_rul.py` + `pytest` PASS
- [ ] B6: báo cáo MAE/RMSE (cycle) so với mục tiêu, quyết định bước enhance

## Mở rộng dự kiến (không làm ở #13)
- #14: observability-index auxiliary loss (bật `use_obs_loss`)
- #15: bảng so sánh parameter-parity với baselines (Table IV/V)
- Series decomposition trên chuỗi RUL/feature theo cycle
