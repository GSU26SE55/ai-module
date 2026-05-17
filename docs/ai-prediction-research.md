# AI Prediction Research — Solar Battery Maintenance

Tài liệu này tổng hợp lý do lựa chọn kỹ thuật và hướng tiếp cận cho 2 core model của AI module.

---

## 1. SOH Prediction — CNN-LSTM

### Bài toán
State of Health (SOH) biểu thị phần trăm dung lượng còn lại của pin so với dung lượng danh định:

```
SOH(%) = capacity_current / capacity_nominal × 100
```

Với NASA Ames dataset: `capacity_nominal = 2.0 Ah`. Pin được coi là hết vòng đời khi SOH < 70–80%.

### Tại sao CNN-LSTM?

| Model | Điểm mạnh | Điểm yếu | Phù hợp bài toán? |
|-------|-----------|----------|------------------|
| Pure LSTM | Học temporal dependency tốt | Chậm hội tụ, dễ overfit với sequence dài | Trung bình |
| Pure CNN | Trích xuất local pattern nhanh | Không nắm bắt long-term dependency | Không |
| **CNN-LSTM** | CNN trích xuất local feature → LSTM học temporal | Phức tạp hơn | **Tốt nhất** |
| Transformer | State-of-the-art cho sequence | Cần nhiều data, latency cao | Quá nặng cho scope capstone |

**CNN block** (`Conv1d + MaxPool1d`) giảm chiều temporal (30 → 15) và trích xuất local patterns như voltage drop, current spike. **LSTM block** (2 layers) học sự phụ thuộc dài hạn qua nhiều discharge cycles.

### Architecture (đã implemented)
```
Input (batch, 30, 3)
    → Conv1d(3→32, k=3, pad=1) + ReLU + MaxPool1d(2)   → (batch, 32, 15)
    → permute → LSTM(32→64, 2 layers, dropout=0.2)       → hidden (batch, 64)
    → Linear(64→32) + ReLU + Dropout(0.2)
    → Linear(32→1)                                        → SOH% (batch,)
```

### Training strategy
- **Loss:** MSELoss (regression task — predict continuous SOH%)
- **Optimizer:** Adam(lr=1e-3) — adaptive learning rate, ít cần tune
- **Early stopping:** patience=10 epochs — tránh overfit
- **Batch size:** 32 — cân bằng speed vs gradient stability
- **Seed:** 42 — reproducibility bắt buộc

### Data split (theo battery ID — tránh leakage)
```
Train: B0005, B0006, B0007      (~70%)
Val:   B0018 (70% đầu)          (~15%)
Test:  B0018 (30% cuối)         (~15%)
```
Chia theo battery ID, không theo timestep — nếu chia theo timestep sẽ có thông tin tương lai từ cùng battery lọt vào train (data leakage).

### Target metrics
| Metric | Target | Lý do |
|--------|--------|-------|
| MAE | < 2% SOH | ±2% là ngưỡng chấp nhận được cho bảo trì pin |
| RMSE | < 3% SOH | Phạt nặng outlier — đảm bảo không có prediction sai lớn |

---

## 2. Anomaly Detection — Isolation Forest

### Bài toán
Phân loại trạng thái pin thành 3 nhãn: **Normal / Degrading / Failed**.

### Tại sao Isolation Forest?

| Model | Yêu cầu | Phù hợp? |
|-------|---------|---------|
| **Isolation Forest** | Unsupervised — không cần label | **Tốt nhất cho scope** |
| SVM One-class | Unsupervised nhưng chậm với data lớn | Trung bình |
| Autoencoder | Deep learning — cần nhiều data & tuning | Quá phức tạp |
| Supervised classifier | Cần nhiều labeled anomaly samples | Không có đủ label |

NASA dataset không có nhãn anomaly rõ ràng cho từng timestep — chỉ có discharge capacity. Isolation Forest phù hợp vì:
1. Unsupervised — tự phát hiện outlier mà không cần label
2. Nhanh (O(n log n)) — đạt latency < 100ms dễ dàng
3. `contamination=0.1` phù hợp với ước tính ~10% cycles là bất thường trong NASA dataset

### Hyperparameters
```python
IsolationForest(
    contamination=0.1,   # ước tính 10% data là bất thường
    n_estimators=100,    # 100 trees — đủ ổn định
    random_state=42,     # reproducibility
)
```

### Classification mapping
```
IsolationForest.decision_function() → score (âm = bất thường hơn)

score > -0.1            → Normal    (pin hoạt động bình thường)
score > -0.3 OR soh≥80  → Degrading (bắt đầu xuống cấp)
else                    → Failed    (pin cần thay thế)
```
SOH ≥ 80 luôn là Degrading dù score xấu — tránh false alarm khi pin còn tốt nhưng có noise nhất thời.

### Feature engineering
IsolationForest nhận flattened window: `(30, 3) → (90,)` — toàn bộ voltage/current/temperature sequence của 30 timestep.

### Target metrics
| Metric | Target |
|--------|--------|
| F1-score | > 0.80 (evaluated on Sprint 4 khi có test labels) |

---

## 3. Inference Pipeline

```
POST /predict
    → validate input (30, 3)
    → MinMaxScaler.transform()     ← scaler.pkl (fit trên train set)
    → SOHPredictor.forward()       ← soh_lstm_v1.0.pth
    → IsolationForest.decision_function()  ← isolation_forest_v1.0.pkl
    → classify_anomaly(score, soh)
    → PredictResponse {soh_percent, classification, confidence, inference_ms}
```

**Latency SLA:** < 100ms (P1 Critical ticket). Với dummy model và real model nhỏ (< 1MB LSTM), latency thực tế ~2–5ms trên CPU.

---

## 4. Roadmap Sprint

| Sprint | Milestone |
|--------|-----------|
| Sprint 1 | ✅ Project scaffold + dummy artifacts + unit tests |
| Sprint 2–3 | Download NASA dataset → preprocess → train → validate |
| Sprint 4 | Đạt target metrics (MAE <2%, RMSE <3%, F1 >0.80) |
| Sprint 5+ | Hyperparameter tuning nếu chưa đạt target |
| Sprint 8 | IoT data pipeline (nếu core model xong) |
