# Plan — GH-7: Add Spectral & Kurtosis feature

## Metadata
- **Status:** SHIPPED | **Role:** AI | **Ngày:** 2026-06-04
- **Issue:** #7 — https://github.com/GSU26SE55/ai-module/issues/7
- **Sprint:** Sprint 2 (due: 2026-06-13)

## Mục tiêu
Mở rộng feature extraction từ **3 channels (54 features) → 6 channels (108 features)**.
Extractor đã implement đúng; chỉ cần bỏ hard-code `[:, :3]` thành full 6 channels
(`voltage, current, temperature, current_load, voltage_load, time`) ở preprocess + inference,
cập nhật config, retrain và commit artifacts v1.2.

## Scope
**Trong scope:**
- Tạo `src/features/extractor.py` — hàm extract 9 spectral + 9 statistical features per channel × 3 channels = 54 scalars
- Update `preprocess.py` — fit StandardScaler cho 54 features, lưu `feature_scaler.pkl`, thêm `X_feat` vào .pt files
- Update `soh_predictor.py` — `forward(x, x_global)`, head `Linear(64→32)` → `Linear(118→32)`
- Update `train.py` — DataLoader nhận thêm X_feat, truyền vào model
- Update `model_loader.py` — load `feature_scaler.pkl`, export `feature_scaler` global
- Update `config.py` — thêm `SPECTRAL_FEAT_DIM`, `FEATURE_SCALER_PATH`, bump version lên `v1.1`
- Commit 4 artifacts: `scaler.pkl`, `feature_scaler.pkl`, `soh_mamba_v1.1.pth`, `isolation_forest_v1.0.pkl`

**Ngoài scope:**
- IsolationForest không thay đổi (giữ nguyên train trên X_flat 180 dims)
- Không thêm detrending trước FFT (đơn giản hóa, scope future)
- Không thêm Spectral Kurtosis (SK per frequency bin) — chỉ time-domain kurtosis
- Không thay đổi window_size, input_features của Mamba backbone

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/features/__init__.py` | create | empty package init |
| `src/features/extractor.py` | create | spectral_features(), stat_features(), extract_window_features() |
| `src/core/config.py` | modify | thêm SPECTRAL_FEAT_DIM=54, FEATURE_SCALER_PATH, MODEL_VERSION="1.1" |
| `scripts/preprocess.py` | modify | extract + scale 54 features, lưu feature_scaler.pkl, thêm X_feat vào .pt |
| `src/models/soh_predictor.py` | modify | forward(x, x_global), head Linear(118→32) |
| `scripts/train.py` | modify | TensorDataset(X, X_feat, y), evaluate() nhận X_feat, truyền vào model |
| `src/core/model_loader.py` | modify | load feature_scaler.pkl, export feature_scaler global |

## Approach

**Feature extraction (per window (30,6) đã scaled):**
- Spectral (9 per channel): centroid, entropy, peak_freq, peak_power_db, flatness, rolloff, band_power_low/mid/high
- Statistical (9 per channel): mean, std, skewness, kurtosis, crest_factor, waveform_factor, pulse_factor, margin_factor, peak_to_peak
- Tổng: 9×3 + 9×3 = **54 scalars** per window

**Normalization:**
- `feature_scaler.pkl` — StandardScaler fit trên 54 features của train set
- Lưu kèm metadata: version, feature_names

**Model forward pass:**
```
x_seq  (B,30,6) → input_proj → MambaBlock×2 → LayerNorm → last token (B,64)
x_feat (B,54)   ─────────────────────────────────────────────────────────────┐
                                                                    cat → (B,118)
                                                         Linear(118→32) → GELU → Dropout → Linear(32→1)
```

**Artifacts sau khi train:**
- `models/weights/scaler.pkl` — unchanged (v1.0)
- `models/weights/feature_scaler.pkl` — NEW (v1.1)
- `models/weights/soh_mamba_v1.1.pth` — NEW
- `models/weights/isolation_forest_v1.0.pkl` — unchanged

## Edge Cases
- Window có signal phẳng (voltage constant): power=0 → guard `+ 1e-12` tránh log(0), division by zero
- Kurtosis từ N=30 samples có variance cao — dùng `bias=False` (bias-corrected)
- Feature scaler version mismatch: assert version tại startup như scaler.pkl
- `.pt` files cũ (chỉ có X, y, không có X_feat) → train.py báo lỗi rõ ràng

## Success Criteria
| Tiêu chí | Cách verify |
|----------|------------|
| MAE < 2%, RMSE < 3% trên test set | Log output của `scripts/train.py` |
| Inference latency < 100ms (P95) | `tests/test_inference.py` benchmark 100 runs |
| 4 artifacts tồn tại và có version đúng | `model_loader.load_models()` không raise |
| `pytest tests/ -v` PASS | CI / local run |

## Steps
- [x] Bước 1: Update `config.py` — thêm `SPECTRAL_FEAT_DIM`, `FEATURE_SCALER_PATH`, `MODEL_VERSION="1.1"` — 2026-06-04
- [x] Bước 2: Tạo `src/features/__init__.py` + `src/features/extractor.py` — 2026-06-04
- [x] Bước 3: Update `preprocess.py` — extract features, fit feature_scaler, thêm X_feat vào .pt — 2026-06-04
- [x] Bước 4: Update `soh_predictor.py` — `forward(x, x_global)`, head Linear(118→32) — 2026-06-04
- [x] Bước 5: Update `train.py` — DataLoader(X, X_feat, y), evaluate(model, X, X_feat, y) — 2026-06-04
- [x] Bước 6: Update `model_loader.py` — load feature_scaler.pkl, export global — 2026-06-04
- [x] Bước 7: Chạy `preprocess.py` → `train.py` → verify MAE/RMSE — 2026-06-04 (MAE=0.61%, RMSE=0.73%)
- [x] Bước 8: Unit test `src/features/extractor.py` + latency benchmark — 2026-06-04 (63/63 PASS)

## Câu hỏi đã giải đáp
- **Pattern A vs B?** → Pattern B (ghép vào last hidden state) — ít thay đổi backbone nhất
- **feature_scaler.pkl cần không?** → Có — kurtosis range -2~50+, spectral entropy 0~1 → normalize tránh feature dominance
- **IsolationForest update không?** → Không — giữ nguyên, tách issue riêng nếu cần
