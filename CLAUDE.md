# AI Module — GSU26SE55

> Repo này là AI service (FastAPI + PyTorch) của hệ thống Solar Battery Maintenance.
> Context dự án đầy đủ: `.claude/CLAUDE.md` | Rules đầy đủ: `.claude/rules/tech/ai.md`

---

## ⚠️ Model Spec — train và inference PHẢI nhất quán

| Tham số | Giá trị |
|---------|---------|
| Window size | 30 timestep |
| Input features | **6** = 4 base (`BASE_FEATURES`: voltage, current, temperature, **time**) + 2 dẫn xuất tính phía server (`cycle_count/CYCLE_COUNT_NORM`, `soc_percent/100`). Hằng số: `INPUT_FEATURES=6` |
| Feature phụ (FiLM) | **57 chiều** — 10 spectral + 9 statistical × 3 kênh (V/I/T), `extract_window_features()`. Hằng số: `SPECTRAL_FEAT_DIM=57` |
| Normalization | 2 scaler riêng: `scaler.pkl` (MinMax [0,1] trên 4 cột base) + `feature_scaler.pkl` (trên vector 57). 2 cột dẫn xuất **KHÔNG** qua scaler — đã normalize sẵn |
| SOH target | `capacity_current / nominal × 100`. NASA = 2.0 Ah · LFP/Severson = 1.1 Ah (`NOMINAL_CAPACITY_AH_BY_CHEMISTRY`) |
| Train/Val/Test | 24 / 1 / 1 pin — chia theo **battery ID** (1 pin = 1 split). Val=B0046, Test=B0048 (4°C); B0047 chuyển vào train từ GH-88 (2026-07-08) để phủ vùng SOH cao 4°C. Train PHẢI có pin 4°C. Source: `scripts/preprocess.py` |
| **Random seed** | **42 — BẮT BUỘC mọi script (train, preprocess)** |

**Target metrics:** MAE < 2% SOH · RMSE < 3% · Anomaly F1 > 0.80

---

## ⚠️ Architecture — Mamba + Isolation Forest

**MambaSOHPredictor** (production, L=30) — 2 đầu vào: `forward(x, x_feat)`

```text
x (B,30,6) → Linear(6→64) → MambaBlock×2(d_model=64, d_state=16, d_conv=4, expand=2)
           → LayerNorm → last token → h (B,64)
                                        ↓ FiLM
x_feat (B,57) → Linear(57→57) → SiLU → Linear(57→128) → chunk → γ, β
           h = (sigmoid(γ) + 0.5)·h + β  → Linear(64→32) → GELU+Dropout(0.2) → Linear(32→1)
```

> **FiLM conditioning là bắt buộc** — bỏ đi thì checkpoint không load được. Đặc trưng phổ cấp chu kỳ điều biến trạng thái ẩn, không nối vào input.

> **GH-34:** model **long-seq (L=4096)** khác hẳn: Conv1d patch (k=16,s=16) + `PatchDegradationEncoder` + `d_state=32` (`LONG_D_STATE`) + multi-head attention pooling. Window=30 production + RUL **giữ `d_state=16`** (`D_STATE`) + pooling `last`.

> Pure PyTorch mặc định — không cần `mamba-ssm` CUDA, chạy Windows 11 native. Có cờ opt-in `use_official_mamba` dùng kernel CUDA trên Kaggle/Colab (cùng công thức, chỉ nhanh hơn), tự fallback nếu không có.

**Artifact production** — 2 bộ tách theo chemistry, chọn ở `_resolve_artifacts()`:

| chemistry | model | scaler | iforest |
|-----------|-------|--------|---------|
| mặc định (NASA/NMC) | `soh_mamba_v1.6.pth` | `scaler.pkl` + `feature_scaler.pkl` | `isolation_forest_v1.6.pkl` |
| `"LFP"` | `soh_mamba_v2.1-lfp.pth` | `scaler_lfp.pkl` + `feature_scaler_lfp.pkl` | `isolation_forest_v2.1-lfp.pkl` |

**IsolationForest:** `contamination=0.1, n_estimators=100, random_state=42` — fit trên **vector 57 chiều**, không phải chuỗi thô.

**3 hàm phân loại độc lập** (`src/models/anomaly_detector.py`) — đừng gộp:

| Hàm | Luật |
|-----|------|
| `classify_anomaly(score, soh, causal_rate)` | SOH là yếu tố chính: `<80` → Failed · `<90` → Degrading · `≥90` → `score < -0.1 ? Degrading : Normal`. Nếu `causal_rate > RATE_THRESHOLD` (0.5016 %SOH/cycle) → **nâng 1 bậc** |
| `classify_anomaly_status(score)` | `≤ -0.3` → Anomaly · `≤ -0.1` → Warning · else Normal |
| `classify_health_stage(soh)` | **2 tầng**: `<80` → End Of Life · else Healthy. Quyết định bằng argmax trên phân phối MC Dropout (`classify_health_stage_probabilistic`) |

**Training config** (window=30, `scripts/train.py:82-85`): `Adam(lr=5e-4, weight_decay=1e-5)`, weighted MSE (= MSELoss khi tắt `--balance-bands`), `batch=32`, `--epochs` mặc định 100, `PATIENCE=15`, `ReduceLROnPlateau(factor=0.5, patience=5)`.
> Đường long-seq dùng bộ khác: `AdamW` + `CosineAnnealingWarmRestarts` + SmoothL1 near-EOL weighted.

## ⚠️ Critical — hay sai nhất

- Cả **6 artifact** (2 bộ × model + scaler + feature_scaler + iforest) **PHẢI** commit vào Git — inference load từ file, **KHÔNG** fit lại trên production data
- Đổi artifact LFP phải sync 3 hằng trong `config.py`: `LFP_MODEL_VERSION`, `LFP_CYCLE_COUNT_NORM`, `LFP_TEMPERATURE_TRAIN_CLUSTERS` (lấy từ khoá trong `scaler_lfp.pkl`) — lệch là hỏng im lặng, không có lỗi
- **KHÔNG** thêm ML framework ngoài PyTorch + scikit-learn
- Output **bắt buộc**: Classification (Normal/Degrading/Failed) + SOH % + confidence score
- Inference latency **PHẢI** < 100ms (P1 ticket SLA = 4h) — benchmark trước khi `/kltn-ship`
- IoT data pipeline chỉ thêm Sprint 8 nếu core model xong

---

## Scaffold nhanh

| Lệnh | Output |
|------|--------|
| `/scaffold-fastapi-endpoint {name}` | FastAPI router + Pydantic schema |

---

## Workflow

```
/kltn-implement [issue-number] → plan.md → approve → code → /kltn-reviewcode → /kltn-test → /kltn-ship [issue-number]
```
