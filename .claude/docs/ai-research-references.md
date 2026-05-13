# Nghiên cứu tham khảo — AI Anomaly Detection → Auto Ticket Creation

**Ngày:** 2026-05-10
**Người tổng hợp:** Trần Minh Trí (Leader)
**Mục đích:** Tài liệu tham khảo học thuật cho module AI và luồng tạo ticket tự động

---

## Kết luận chính

Các nghiên cứu hiện tại chia thành 2 nhóm riêng biệt, chưa ai nối chúng lại:

| Nhóm | Tình trạng |
|---|---|
| AI phát hiện bất thường / dự đoán SOH pin/solar | Nghiên cứu nhiều, số liệu tốt |
| AI tự động tạo ticket + SLA + notify theo ITIL | Chỉ có trong ITSM (IT services), chưa cho thiết bị vật lý |
| **End-to-end: AI anomaly → ticket → assign Staff → notify Customer** | **Chưa có bài báo nào làm đầy đủ — đây là novelty của dự án** |

---

## Papers nên cite trong báo cáo

| Cite ở đâu | Bài báo | URL |
|---|---|---|
| Lý do chọn LSTM/CNN-LSTM cho SOH prediction | Dubarry et al., *Nature Communications* 2023 | https://pmc.ncbi.nlm.nih.gov/articles/PMC10229535/ |
| Lý do chọn Isolation Forest cho anomaly | Kumar et al., *Scientific Reports* 2025 | https://pmc.ncbi.nlm.nih.gov/articles/PMC11842581/ |
| Kiến trúc CNN-LSTM baseline | CNN-LSTM-Attention, *MDPI Batteries* 2024 | https://www.mdpi.com/2313-0105/11/10/384 |
| Lý do tích hợp ITIL + AI ticketing | ACM AIMLSystems 2024 | https://dl.acm.org/doi/10.1145/3703412.3703433 |
| Isolation Forest cho solar-grid battery | Markov-Constrained IF, *MDPI Mathematics* 2025 | https://www.mdpi.com/2227-7390/14/7/1192 |
| Review toàn diện predictive maintenance solar | Ledmaoui et al., *Sensors* 2025 | https://pmc.ncbi.nlm.nih.gov/articles/PMC11722890/ |
| AIoT predictive maintenance Industry 5.0 | Bitam et al., *Sensors* 2025 | https://pmc.ncbi.nlm.nih.gov/articles/PMC12737171/ |

---

## Số liệu benchmark — dùng làm target cho AI module

| Chỉ số | Nguồn | Số liệu | Ghi chú |
|---|---|---|---|
| SOH prediction RMSE | Nature Communications 2023 | **2.75%** | Trên PV + battery thực — dùng làm baseline |
| CNN-LSTM anomaly false alarm rate | MDPI Batteries 2024 | **~5%** | Cross-battery generalization |
| AI ticket triage — giảm thời gian giải quyết | ACM 2024 | **75%** | ITSM context |
| Isolation Forest + ensemble accuracy (lab) | Scientific Reports 2025 | **99.99%** | Cảnh báo: lab data, không phải thực tế |
| LSTM solar inverter failure prediction | arXiv microgrid 2025 | **94.7%** accuracy, 14 ngày trước | arXiv preprint, chưa peer-review |

> **Cảnh báo quan trọng:** Accuracy 99%+ trong lab có thể chỉ còn ~33% recall trong thực tế vận hành.
> Không đặt target quá cao — mục tiêu thực tế theo `rules/tech/ai.md`: MAE < 2%, RMSE < 3%, F1 > 0.80.

---

## Chi tiết từng paper

### 1. Dubarry et al. — Nature Communications 2023
**"Data-Driven Direct Diagnosis of Li-Ion Batteries Connected to Photovoltaics"**
- Dataset: PV + lithium-ion battery, thực tế (không phải lab thuần)
- Kết quả: RMSE trung bình **2.75%** cho degradation <25%
- 5 thuật toán so sánh: Random Forest, XGBoost, FNN, 1D-CNN, DTW-CNN
- Code & dataset mở: https://github.com/NahuelCostaCortez/PVDiagnosis
- Hạn chế: Chỉ validate single-cell, phụ thuộc vị trí địa lý

### 2. Kumar et al. — Scientific Reports (Nature) 2025
**"Hybrid ML Framework for Predictive Maintenance Using Enhanced Random Forest"**
- Kết hợp Isolation Forest-style + Improved Random Forest + Bayesian Hyperparameter Optimization
- Accuracy: **99.99%**, Precision: **99.98%**, Recall: **100%**, RMSE: **1.575**, R²: **0.9995**
- Phù hợp dự án: framework tích hợp physics-informed + ML, proactive intervention

### 3. CNN-LSTM-Attention — MDPI Batteries 2024
**"Hybrid CNN–LSTM–Attention for Anomaly Detection in Lithium-Ion Batteries"**
- Kiến trúc: CNN (local features) + LSTM (temporal) + Attention (key moments)
- Alarm rate: **~5%** ổn định — cross-battery generalization
- Liên quan trực tiếp: so sánh với CNN-LSTM thuần đang dùng trong dự án

### 4. ACM AIMLSystems 2024
**"AI Enhanced Ticket Management System for Optimized Support"**
- AI NLP triage giảm **75% thời gian giải quyết**
- Phân loại ticket tự động theo ITIL: urgency + impact → priority — mapping P1/P2/P3
- Hạn chế: Human validation vẫn cần thiết; data quality thiết yếu

### 5. Markov-Constrained Isolation Forest — MDPI Mathematics 2025
**"Markov-Constrained Isolation Forest for Early Detection of Battery Anomalies in Solar-Grid"**
- Kết hợp Isolation Forest + Markov constraints để giảm false positive
- Trực tiếp: đúng stack Isolation Forest + solar battery của dự án

### 6. Ledmaoui et al. — Sensors MDPI 2025
**"Review of Recent Advances in Predictive Maintenance for Solar Plants"**
- Review 506 bài báo (2018–2023)
- SmartHelio đạt **93% classification accuracy** cho 7 loại lỗi
- Xác nhận: "real-time monitoring and alerts are required" — chưa có chuẩn hóa tích hợp ITSM

### 7. Bitam et al. — Sensors MDPI 2025
**"AIoT for Next-Generation Predictive Maintenance"**
- Deep Learning FDD: **92–99.9% F-score**; RUL prediction RMSE: 1.38–88.7 giờ
- **Research gap quan trọng:** Paper không đề cập automated notification/ticket generation hay SLA — xác nhận đây là gap thực sự

### 8. Hamasha et al. — Journal of Applied Engineering Science 2025
**"IoT-Driven Predictive Maintenance: AI and Edge Computing"**
- Framework gần nhất với dự án: phát hiện bất thường → alert SMS (driver) + email (maintenance) tự động
- Giảm **30–40% chi phí bảo trì**, tăng **40% asset availability**
- Case study: xe tải cứu hỏa Jordan (thiết bị vật lý, không phải IT)

---

## Research Gaps — Novelty của dự án

1. **End-to-end pipeline chưa có:** Không tìm thấy bài báo nào làm đầy đủ:
   `AI anomaly → auto-create ticket → priority SLA → assign Staff → notify Customer`

2. **ITIL cho thiết bị vật lý chưa chuẩn hóa:** ITIL được nghiên cứu kỹ cho IT services, nhưng áp dụng vào bảo trì pin/solar với P1/P2/P3 SLA chưa có framework học thuật.

3. **Human-in-the-loop chưa được nghiên cứu:** Tác động của Staff confirm/reject ticket AI tạo ra lên false positive rate theo thời gian.

4. **Real-world validation gap:** Hầu hết dùng NASA PCoE / CALCE (pin 18650 phòng lab), chưa validate trên battery pack solar thực tế.

---

## Áp dụng vào dự án

### Anomaly types → Priority mapping (từ research)

| Loại bất thường | AI model phát hiện | Priority | SLA |
|---|---|---|---|
| Hot spot, điện áp bất thường đột ngột | Isolation Forest | P1 Critical | 4h |
| Sản lượng sụt giảm >30% đột ngột | Isolation Forest | P2 High | 24h |
| SOH suy giảm từ từ theo trend | LSTM/CNN-LSTM | P3 Standard | 72h |

### BatteryAnomalyDetectedEvent — payload gợi ý

```json
{
  "batteryId": "uuid",
  "anomalyType": "HOT_SPOT | SUDDEN_DROP | SOH_DEGRADATION",
  "classification": "Normal | Degrading | Failed",
  "sohPercent": 72.5,
  "confidenceScore": 0.91,
  "detectedAt": "2026-05-10T08:00:00Z",
  "suggestedPriority": "P1 | P2 | P3"
}
```

### Target metrics thực tế cho AI module

Theo `rules/tech/ai.md` và benchmark từ research:
- SOH regression: **MAE < 2%, RMSE < 3%** (baseline: Nature Comms 2023 đạt 2.75% RMSE)
- Anomaly classification: **F1 > 0.80**
- Inference latency: **< 100ms** cho P1 Critical

---

## Nguồn bổ sung (có thể fetch thêm)

- IEEE Xplore: tìm "predictive maintenance ITSM integration" — bị paywall khi fetch
- Springer LNCS: "AI-driven incident management IoT" — bị paywall
- GitHub dataset: https://github.com/NahuelCostaCortez/PVDiagnosis (Nature Comms 2023)

---

## GitHub Repos tham khảo — AI Module Implementation

> Nghiên cứu thực hiện: 2026-05-13 | Researcher + Reviewer agents

### Tier 1 — Dùng ngay

#### A. huzaifi18/RUL_prediction ⭐ PRIMARY MODEL
- **URL:** https://github.com/huzaifi18/RUL_prediction
- **Stars:** 118 | **License:** MIT
- **Dataset:** NASA (thư mục `data/NASA` verified)
- **Model:** MC-SCNN-LSTM (Multi-Channel Separate CNN + LSTM)
- **Metric:** RMSE=0.0276, MAE=0.0220, MAPE=1.42% (cải thiện 61% vs baseline)
- **Paper:** DOI:10.1145/3575882.3575903
- **Dùng để:** Architecture CNN-LSTM đa kênh, training pipeline, comparative baseline

#### B. mayankbaluni/Battery_Remaining_Useful_Life ⭐ PRIMARY MODEL
- **URL:** https://github.com/mayankbaluni/Battery_Remaining_Useful_Life
- **Stars:** 19 | **License:** Không rõ ⚠️ — chỉ dùng như reference, không copy code
- **Dataset:** NASA (voltage/current/temperature)
- **Model:** Multi-branch 1D CNN + LSTM → concatenate → FC (PyTorch)
- **Metric:** MAE=0.022, RMSE=0.027 (cải thiện 56% vs LSTM baseline)
- **Dùng để:** Architecture reference, training loop pattern
- **⚠️ Lưu ý:** RMSE=0.027 trên scale 0-1 = 2.7% — document normalization convention ngay từ đầu

#### C. anirudhkhatry/SOH-prediction-using-NASA-Dataset ⭐ DATA PIPELINE
- **URL:** https://github.com/anirudhkhatry/SOH-prediction-using-NASA-Dataset
- **Stars:** 31
- **Dataset:** NASA **B0005, B0006, B0007, B0018** — chính xác 4 battery dự án dùng
- **Model:** SVM (không dùng)
- **Dùng để:** `mat2json.py` + `util.py` — data loading từ .mat files, tiết kiệm 2-3 ngày data engineering

### Tier 2 — Hỗ trợ

| Repo | URL | Dùng để |
|------|-----|---------|
| alishbaimran/Attention-based-CNN-BiLSTM | https://github.com/alishbaimran/Attention-based-CNN-BiLSTM-Battery-SOH-Prediction | Attention mechanism (Sprint 5+), data exploration notebook |
| Sa1f27/predictive-maintenance-mlops | https://github.com/Sa1f27/predictive-maintenance-mlops | FastAPI project structure, Dockerfile, MLflow — strip ML model, giữ serving pattern |
| rapidrabbit76/FastAPI-DL-Micro-Batching | https://github.com/rapidrabbit76/FastAPI-Deep-Learning-Model-Micro-Batching-Serving | PyTorch + FastAPI async inference pattern |

### Khoảng trống phải tự implement (không có repo mẫu)

1. **Isolation Forest cho battery** — tự build features: capacity fade per cycle, voltage plateau duration, charging time deviation
2. **3-class output (Normal/Degrading/Failed)** — define threshold: SOH > 80% → Normal, 60-80% → Degrading, < 60% → Failed
3. **Confidence score calibration** — IsolationForest anomaly score → % dùng Platt scaling
4. **FastAPI + PyTorch + NASA end-to-end** — ghép Tier 2 (serving) + Tier 1 A/B (model) + Tier 1 C (data)
5. **Inference latency benchmark** — tự đo với `time.perf_counter()`, batch_size=1; xem xét ONNX nếu > 100ms

### Lộ trình tích hợp

```
Sprint 1 (trước 25/5):
  → Clone Repo C: copy mat2json.py + util.py → data pipeline B0005-B0018
  → Implement MC-SCNN-LSTM từ Repo A (PyTorch, input: batch×30×3, output: SOH%)
  → Fork Repo Sa1f27: strip domain, giữ FastAPI structure + Dockerfile

Sprint 2-3 (26/5 → 22/6):
  → Implement Isolation Forest (tự build — không có repo mẫu)
  → Ghép pipeline: data → model → FastAPI → benchmark latency < 100ms
  → Calibrate anomaly score → confidence %

Sprint 4+ (nếu MAE chưa đạt):
  → Thử Attention từ alishbaimran (benchmark latency BiLSTM trước khi commit)
  → ONNX export nếu latency > 100ms (giảm 30-50%)
  → MLflow tracking (pattern từ Sa1f27)
```
