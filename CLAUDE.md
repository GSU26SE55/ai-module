# AI Module — GSU26SE55

> Repo này là AI service (FastAPI + PyTorch) của hệ thống Solar Battery Maintenance.
> Context dự án đầy đủ: `.claude/CLAUDE.md` | Rules đầy đủ: `.claude/rules/tech/ai.md`

---

## ⚠️ Model Spec — train và inference PHẢI nhất quán

| Tham số | Giá trị |
|---------|---------|
| Window size | 30 timestep |
| Input features | 3 — voltage, current, temperature |
| Normalization | MinMaxScaler [0, 1] — fit trên train, lưu `models/weights/scaler.pkl` |
| SOH target | `capacity_current / 2.0 × 100` (NASA nominal = 2.0 Ah) |
| Train/Val/Test | 70/15/15 — chia theo **battery ID**, không theo timestep |
| **Random seed** | **42 — BẮT BUỘC mọi script (train, preprocess)** |

**Target metrics:** MAE < 2% SOH · RMSE < 3% · Anomaly F1 > 0.80

---

## ⚠️ Architecture — LSTM/CNN-LSTM + Isolation Forest

**SOHPredictor:** `Conv1d(3→32, k=3) → MaxPool1d(2) → LSTM(32→64, 2 layers, dropout=0.2) → Linear(64→32) → Linear(32→1)`

**IsolationForest:** `contamination=0.1, n_estimators=100, random_state=42`

**Anomaly mapping:** `score > -0.1` → Normal | `> -0.3 hoặc SOH≥80` → Degrading | còn lại → Failed

**Training config:** `Adam(lr=1e-3), MSELoss, epochs=50, patience=10(early stop), batch=32`

## ⚠️ Critical — hay sai nhất

- `scaler.pkl` và `isolation_forest.pkl` **PHẢI** commit vào Git — inference load từ file, **KHÔNG** fit lại trên production data
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
