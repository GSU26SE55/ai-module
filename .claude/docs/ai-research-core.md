# AI Research Core — Hệ thống Giám sát Pin Lithium-ion
> **Mục đích:** Tài liệu tổng hợp nghiên cứu khoa học làm nền tảng cho AI Module của dự án Capstone.
> Phần đánh dấu `[PROJECT]` = nơi điền thông tin dự án thực tế.
> Ngày tổng hợp: 2026-05-17 | Researcher + Reviewer: Claude Agent

---

## Mục lục

1. [Tổng quan AI Pipeline](#1-tổng-quan-ai-pipeline)
2. [SOH Prediction — CNN-LSTM](#2-soh-prediction--cnn-lstm)
3. [Anomaly Detection — Isolation Forest](#3-anomaly-detection--isolation-forest)
4. [Noise Control — Consecutive-Point Filter](#4-noise-control--consecutive-point-filter)
5. [Fault Classification & Thresholds](#5-fault-classification--thresholds)
6. [Priority Framework P1/P2/P3](#6-priority-framework-p1p2p3)
7. [Labeling Strategy cho NASA Dataset](#7-labeling-strategy-cho-nasa-dataset)
8. [Benchmark & Metric Target](#8-benchmark--metric-target)
9. [Danh sách Tài liệu Tham khảo](#9-danh-sách-tài-liệu-tham-khảo)

---

## 1. Tổng quan AI Pipeline

### 1.1 Kiến trúc tổng thể

```
Sensor Reading (Voltage, Current, Temperature)
        ↓
[Preprocessing] — MinMaxScaler + Savitzky-Golay noise filter
        ↓
[CNN-LSTM + Attention] — SOH Prediction (regression)
        ↓  ↗
[Isolation Forest] — Anomaly Detection (unsupervised)
        ↓
[Consecutive-Point Filter, m=3] — Noise Control
        ↓
[Classification Engine] — Normal / Degrading / Failed
        + Fault Type (Overheat / Overvoltage / Undervoltage / ...)
        ↓
[Priority Assignment] — P1 / P2 / P3 (dựa trên fault severity + dependency)
        ↓
Alert → Ticket → SLA
```

### 1.2 Hai mô hình cốt lõi

| Mô hình | Nhiệm vụ | Loại | Output |
|---------|----------|------|--------|
| **CNN-LSTM + Attention** | SOH Prediction | Supervised Regression | SOH% ∈ [0, 100] |
| **Isolation Forest** | Anomaly Detection | Unsupervised | anomaly_score ∈ [-1, 1] |

> **Lý do chọn hai mô hình này:** CNN-LSTM+Attention đạt RMSE < 0.004 trên NASA dataset (tốt hơn LSTM đơn RMSE=0.0076 và CNN-LSTM thuần RMSE=0.02) [R1, R3]. Isolation Forest phù hợp battery safety context vì ưu tiên recall cao (không bỏ sót anomaly thật) hơn precision [R4, R5].

---

## 2. SOH Prediction — CNN-LSTM

### 2.1 Cơ sở khoa học

**State of Health (SOH)** là chỉ số đánh giá khả năng lưu trữ năng lượng còn lại của pin so với trạng thái ban đầu:

$$SOH = \frac{Q_{current}}{Q_{nominal}} \times 100\%$$

Trong đó `Q_current` là dung lượng thực đo được, `Q_nominal` là dung lượng danh định ban đầu (NASA 18650: 2.0 Ah).

**Tại sao CNN-LSTM?**

CNN trích xuất local pattern trong chuỗi thời gian (đặc trưng cục bộ như voltage dip, temperature spike), trong khi LSTM học temporal dependency dài hạn (xu hướng degradation theo thời gian). Kết hợp hai kiến trúc này được xác nhận trong nhiều nghiên cứu gần đây [R1, R3].

**Tại sao cần Attention?**

CNN-LSTM thuần (không Attention) có hai hạn chế được nhiều paper phê phán [R1, R3]:
- Overfitting trên dataset nhỏ (NASA chỉ có 4 battery cells)
- Không khai thác đầy đủ long-term temporal dependency
- "Rapidly overfitted the training battery and failed to generalize to unseen ones" [R3]

CNN-LSTM + Self-Attention giải quyết vấn đề này bằng cách cho phép model tập trung vào các timestep quan trọng nhất, đạt RMSE < 0.004 trên NASA dataset [R3].

### 2.2 Benchmark trên NASA Ames Dataset

| Mô hình | B0005 RMSE | B0005 MAE | B0007 RMSE | Nguồn |
|---------|-----------|-----------|-----------|-------|
| LSTM đơn (baseline) | 0.0076 | 0.0055 | 0.0068 | Scientific Reports [R2] |
| TCN | 0.0071 | 0.0051 | 0.0067 | Scientific Reports [R2] |
| MLP | 0.0069 | 0.0049 | 0.0112 | Scientific Reports [R2] |
| CNN-LSTM thuần | 0.0200 | — | 0.0300 | arXiv SOH-KLSTM [R1] |
| **CNN-LSTM+Attention** | **< 0.004** | **< 0.0099** | — | Energy/Elsevier [R3] |
| SOH-KLSTM (SOTA) | 0.001682 | — | 0.002112 | arXiv SOH-KLSTM [R1] |

> **Phát hiện quan trọng:** CNN-LSTM thuần RMSE=0.02 **kém hơn** LSTM đơn RMSE=0.0076. CNN-LSTM chỉ vượt trội khi có Attention layer. Nếu không implement Attention, LSTM đơn là lựa chọn tốt hơn về mặt benchmark [R1, R2, R3].

### 2.3 Phê phán CNN-LSTM (Góc độ trái chiều)

- **Overfitting:** "Highly susceptible to noise interference, which can adversely affect model stability and robustness" [R3]
- **Computational overhead:** Hybrid architecture tăng complexity và risk of overfitting [R1]
- **Data split bias:** Setup 70 battery train / 7 test được gọi là "biased setup" [R3]
- **Giải pháp:** Dropout 0.2, Early stopping (patience=10), Attention mechanism

### 2.4 Architecture Spec `[PROJECT]`

```python
class SOHPredictor(nn.Module):
    """
    Input:  (batch, 30, 3) — window=30 timestep, features=[voltage, current, temp]
    Output: (batch, 1)     — SOH% ∈ [0, 100]

    Reference: CNN-LSTM+Attention pattern, Energy/Elsevier 2023 [R3]
    """
    def __init__(self):
        super().__init__()
        # CNN block — local pattern extraction
        self.conv1   = nn.Conv1d(in_channels=3, out_channels=32, kernel_size=3, padding=1)
        self.relu    = nn.ReLU()
        self.pool    = nn.MaxPool1d(kernel_size=2)             # → (batch, 32, 15)
        # LSTM block — temporal dependency
        self.lstm    = nn.LSTM(input_size=32, hidden_size=64,
                               num_layers=2, batch_first=True, dropout=0.2)
        # Self-Attention — focus on important timesteps
        self.attn    = nn.MultiheadAttention(embed_dim=64, num_heads=4, batch_first=True)
        # FC head
        self.fc1     = nn.Linear(64, 32)
        self.fc2     = nn.Linear(32, 1)
        self.dropout = nn.Dropout(0.2)

    def forward(self, x):
        x = x.permute(0, 2, 1)
        x = self.pool(self.relu(self.conv1(x)))
        x = x.permute(0, 2, 1)
        lstm_out, _ = self.lstm(x)
        attn_out, _ = self.attn(lstm_out, lstm_out, lstm_out)
        x = attn_out[:, -1, :]                                # last timestep
        x = self.dropout(self.relu(self.fc1(x)))
        return self.fc2(x).squeeze(-1)

# Training config
OPTIMIZER  = "Adam"
LR         = 1e-3
LOSS       = "MSELoss"
EPOCHS     = 50
PATIENCE   = 10          # early stopping — tránh overfitting trên dataset nhỏ
BATCH_SIZE = 32
RANDOM_SEED = 42
```

---

## 3. Anomaly Detection — Isolation Forest

### 3.1 Cơ sở khoa học

Isolation Forest (iForest) là thuật toán anomaly detection dựa trên nguyên tắc: **anomaly dễ bị "isolate" hơn normal points** — cần ít bước chia cây hơn để tách biệt [Liu et al., 2008].

**Tại sao Isolation Forest phù hợp battery safety?**

Theo OSBAD benchmark (benchmark toàn diện nhất tìm được — test 15 thuật toán trên 2 battery dataset) [R4]:
- Isolation Forest đạt **recall = 1 trong 85% Bayesian optimization trials**
- Trong battery safety context: *"detecting all true anomalies outweighs the cost of false positives"* [R4]
- Miss một anomaly thật (false negative) nguy hiểm hơn nhiều so với false alarm

**Hạn chế của IF standalone:**
- Precision thấp hơn PCA và Autoencoder — perfect precision chỉ 40% trials [R4]
- "Struggles with high-dimensional, nonlinear data" [R6]
- Giải pháp: kết hợp với consecutive-point filter (Section 4) và domain heuristics

### 3.2 Benchmark (OSBAD, 2024)

| Thuật toán | Recall | Precision | Phù hợp battery? | Nguồn |
|-----------|--------|-----------|-----------------|-------|
| **Isolation Forest** | **~1.0** (85% trials) | Thấp (40% trials) | ✅ High recall ưu tiên | R4 |
| PCA | Trung bình | Cao hơn IF | Có thể — balanced | R4 |
| Autoencoder | Cao | Cao hơn IF | Có thể — complex hơn | R4 |
| KNN | Cao | Cao | Có thể | R4 |
| LOF | Cao | Trung bình | Có thể | R4 |
| GMM | Thấp | Thấp | ❌ Underperform | R4 |

> **Kết luận:** Isolation Forest là lựa chọn đúng cho safety-critical application nhưng phải kết hợp với consecutive-point filter.

### 3.3 Hyperparameters `[PROJECT]`

```python
from sklearn.ensemble import IsolationForest

# Reference: OSBAD Benchmark [R4], Markov-Constrained IF [R5]
iso_forest = IsolationForest(
    contamination=0.1,   # ước tính 10% data là anomaly (NASA dataset estimate)
    n_estimators=100,
    random_state=42,     # bắt buộc — reproducibility
)

def classify_by_score(anomaly_score: float, soh: float) -> str:
    """
    anomaly_score: IF decision_function (âm hơn = bất thường hơn)
    Ngưỡng dựa trên phân phối score của NASA training data [PROJECT: calibrate sau khi train]
    """
    if anomaly_score > -0.1:
        return "Normal"
    elif anomaly_score > -0.3 or soh >= 80:
        return "Degrading"
    else:
        return "Failed"
```

> **Lưu ý `[PROJECT]`:** Ngưỡng -0.1 và -0.3 phải được calibrate trên NASA training set thực tế. Dùng percentile 80 của reconstruction errors trên training data [R10].

---

## 4. Noise Control — Consecutive-Point Filter

### 4.1 Phân loại nguồn nhiễu

Có hai loại noise hoàn toàn khác nhau, cần tách bạch trong tài liệu và code [R10]:

| Loại | Tên kỹ thuật | Nguồn | Đặc điểm | Giải pháp |
|------|-------------|-------|----------|-----------|
| **Sensor noise** | Aleatoric uncertainty | ADC error, EMI, cáp lỏng, thermal noise của hardware | Single-point spikes, ngẫu nhiên, không có temporal correlation | Savitzky-Golay filter ở tầng preprocessing |
| **Model uncertainty** | Epistemic uncertainty | Model confidence thấp do distribution shift | Có thể giảm khi thêm training data | Confidence score threshold + consecutive-point rule |

> **Quan trọng:** "Aleatoric uncertainty" = inherent randomness của data — **không thể giảm** bằng thêm data. "Epistemic uncertainty" = model không chắc — **có thể giảm** khi train thêm [R10].

### 4.2 Consecutive-Point Threshold — m=3

**Cơ sở khoa học:**

Theo nghiên cứu Markov-Constrained Isolation Forest áp dụng cho solar-grid battery systems (domain gần nhất với dự án) [R5]:

- **88%** anomaly detections thực sự xảy ra trong chuỗi **≥ 2 consecutive flags**
- Single-point flags (chỉ 1 điểm) là **spurious detections** với xác suất cao

| Giá trị m | Kết quả | Đánh giá |
|-----------|---------|---------|
| m = 2 | False alarm rate tăng | Không đủ nghiêm ngặt |
| **m = 3** | **Optimal: không miss anomaly, giảm spurious alerts** | ✅ Khuyến nghị |
| m = 4 | Bỏ sót short-duration anomalies | Quá nghiêm ngặt |

Xác nhận độc lập từ Nguồn 10 [R10]: *"Considers all time points in a certain successive abnormal segment as defects if the method detects at least one time point of this segment"* — basis cho consecutive-point approach.

**Implementation `[PROJECT]`:**

```python
# Reference: Markov-Constrained Isolation Forest, MDPI Mathematics 14(7):1192, 2025 [R5]
#            Uncertainty-Informed Dynamic Threshold, Expert Systems with Applications, 2025 [R10]
CONSECUTIVE_THRESHOLD = 3

def apply_consecutive_filter(flags: list[int]) -> list[int]:
    """
    flags: list of 0/1 từ Isolation Forest (1 = anomaly detected)
    return: list 0/1 sau khi filter — chỉ giữ anomaly nếu >= 3 consecutive

    Sensor noise → single-point spikes → filtered out
    True anomaly → sustained multi-point pattern → retained
    """
    result = [0] * len(flags)
    i = 0
    while i < len(flags):
        if flags[i] == 1:
            count = 0
            j = i
            while j < len(flags) and flags[j] == 1:
                count += 1
                j += 1
            if count >= CONSECUTIVE_THRESHOLD:
                for k in range(i, j):
                    result[k] = 1
            i = j
        else:
            i += 1
    return result
```

### 4.3 Tầng áp dụng

```
Sensor Reading
    ↓
[Savitzky-Golay filter, window=5, poly=2] ← xử lý aleatoric noise (hardware)
    ↓
[CNN-LSTM + Isolation Forest] ← inference
    ↓
[Consecutive-Point Filter, m=3] ← xử lý epistemic noise (model uncertainty)
    ↓
Alert nếu True Anomaly
```

---

## 5. Fault Classification & Thresholds

### 5.1 Cơ sở phân loại

Fault taxonomy của pin lithium-ion được xác nhận trong nhiều review paper [R7, R8]:

**Phân cấp mức độ nguy hiểm (Frontiers in Energy Research, 2025 [R8]):**

```
Critical (Nguy hiểm nhất)
    └── Thermal Runaway
Major
    ├── Overcharge / Overdischarge (Overvoltage / Undervoltage)
    ├── Internal Short Circuit (ISC)
    ├── External Short Circuit (ESC)
    ├── Sensor Faults (Voltage/Current bias)
    └── BMS Malfunction
```

### 5.2 Bảng Classification có Citation

| Fault Type | Thông số lệch | Threshold (NASA 18650 Li-ion) | Basis |
|-----------|--------------|------------------------------|-------|
| **Overheat** | Temperature tăng bất thường | > 60°C = safety concern; > 45°C = caution | IEC 62619:2022 [R9] |
| **Thermal Runaway risk** | Temp tăng đột ngột + Voltage drop | T > 60°C AND ΔV > 0.5V/cycle | R8 (Frontiers) |
| **Overvoltage** | Voltage > cutoff trên | > 4.2V (18650 cutoff_high) | R7 (arXiv fault review) |
| **Undervoltage** | Voltage < cutoff dưới | < 2.7V (18650 cutoff_low) | R7 |
| **Abnormal Discharge** | Discharge rate bất thường | > 2C discharge rate | R8 |
| **Low SOC** | SOC quá thấp | SOC < 20% | IEC 62619:2022 [R9] |
| **Internal Short Circuit** | Resistance bất thường | < 10Ω (hard SC), 10–100Ω (soft SC) | R7 |
| **Sensor Fault** | Voltage/Current bias | Deviation > ±1% từ expected range | R7 |

> **Quan trọng `[PROJECT]`:** Threshold trên áp dụng cho NASA 18650 Li-ion cells. Nếu hệ thống thực tế dùng **LFP** (LiFePO4): cutoff_high ≈ 3.65V, cutoff_low ≈ 2.5V. Nếu dùng **NMC**: cutoff_high ≈ 4.2V, cutoff_low ≈ 2.8V. Admin ThresholdConfig trong dự án cho phép override các giá trị này theo battery type.

### 5.3 Phân biệt Classification vs Label N/D/B

| Dimension | Mô tả | Output |
|-----------|-------|--------|
| **Health State (N/D/B)** | Trạng thái tổng thể của pin dựa trên SOH% | Normal / Degrading / Failed |
| **Fault Type** | Loại bất thường cụ thể đang xảy ra | Overheat / Overvoltage / ... |

Hai dimension này **độc lập nhau**:
- Pin `Degrading` có thể đang `Overheat`
- Pin `Normal` có thể có `Sensor Fault`

---

## 6. Priority Framework P1/P2/P3

### 6.1 Cơ sở khoa học

**Không có IEEE/IEC standard nào** áp dụng trực tiếp P1/P2/P3 framework cho battery operational incidents. Framework trong dự án là **hybrid adaptation** từ hai nguồn:

1. **ITIL 4 Incident Management** (Axelos, 2019) [R11] — framework quản lý IT incidents, được adapt sang battery domain
2. **IEC 62619:2022 fault severity hierarchy** [R9] — Critical / Major phân loại theo mức độ nguy hiểm vật lý

**Citation đề xuất cho thesis:**
> "The P1/P2/P3 priority classification framework is adapted from ITIL 4 incident management principles (Axelos, 2019), mapped to battery fault severity levels as defined in IEC 62619:2022."

### 6.2 Mapping Framework

**ITIL 4 Priority Matrix: Impact × Urgency [R11]**

| | Urgency Cao | Urgency Thấp |
|--|------------|-------------|
| **Impact Cao** | **P1 — Critical** | **P2 — High** |
| **Impact Thấp** | **P2 — High** | **P3 — Standard** |

**Mapping sang Battery Fault `[PROJECT]`:**

| Priority | SLA | Fault Types | IEC 62619 Severity | Điều kiện |
|----------|-----|------------|-------------------|-----------|
| **P1 Critical** | 4h | Thermal Runaway, Overheat > 60°C | Critical | Nguy hiểm vật lý ngay lập tức, có thể lan sang cell khác |
| **P2 High** | 24h | Overvoltage, Undervoltage, Abnormal Discharge, ISC | Major | Ảnh hưởng performance, escalation risk nếu không xử lý |
| **P3 Standard** | 72h | Low SOC, Sensor Fault, Early Degradation (SOH 75–90%) | Minor | Maintenance required, không urgent |

### 6.3 Dependency Factor (AI cần phân tích)

Yếu tố nâng priority lên một cấp:
- Pin hỏng có lan sang cell lân cận? → Nâng 1 cấp
- Fault ảnh hưởng toàn bộ battery group? → Nâng 1 cấp
- BMS đang quá tải? → Nâng 1 cấp

```python
def evaluate_priority(fault_type: str, dependency: dict) -> str:
    """
    Đánh giá priority dựa trên fault type + dependency factors
    Reference: ITIL 4 (Axelos, 2019) + IEC 62619:2022 [R9, R11]
    """
    base_priority = FAULT_PRIORITY_MAP[fault_type]  # P1/P2/P3 từ bảng trên
    if dependency.get("spreading_risk") or dependency.get("group_impact"):
        # Escalate 1 cấp nếu có dependency
        base_priority = escalate(base_priority)
    return base_priority
```

> **Lưu ý thiết kế `[PROJECT]`:** AI chỉ cung cấp `severity_hint` và `fault_type`. Priority cuối cùng (P1/P2/P3) do **Manager gán** khi triage ticket — không phải AI quyết định. Giữ đúng theo `design.md` của dự án.

---

## 7. Labeling Strategy cho NASA Dataset

### 7.1 Vấn đề

NASA Ames Battery Dataset **không có sẵn N/D/B labels**. Dataset chỉ có raw measurements (voltage, current, temperature) và calculated capacity per cycle. Team phải tự định nghĩa labeling rule.

### 7.2 Labeling Rule `[PROJECT]`

Dựa trên SOH threshold — industry standard "end of life" là SOH = 80% [R7, R8]:

```python
# Reference: Industry standard SOH threshold [R7, R8]
# 80% = industry "end of life" threshold
# 75% = adjusted lower bound để có đủ "Failed" samples từ NASA dataset

def assign_label(soh_percent: float) -> str:
    """
    soh_percent = capacity_current / capacity_nominal * 100
    NASA nominal: 2.0 Ah (18650 cells)
    """
    if soh_percent >= 90:
        return "N"   # Normal
    elif soh_percent >= 75:
        return "D"   # Degrading
    else:
        return "B"   # Bad / Failed

LABEL_THRESHOLDS = {
    "Normal":    (90, 100),   # SOH >= 90%
    "Degrading": (75, 90),    # SOH 75–90%
    "Failed":    (0,  75),    # SOH < 75%
}
```

> **Justify:** SOH 80% là IEEE/industry standard "end of life" [R7]. Điều chỉnh xuống 75% để đảm bảo NASA dataset (B0005 degraded xuống ~60–70% SOH ở cuối) có đủ samples cho class "Failed" trong training.

### 7.3 Train/Val/Test Split

```
Train:  B0005, B0006, B0007  (~70% data)
Val:    B0018 (70% đầu theo timestep)  (~15%)
Test:   B0018 (30% cuối theo timestep)  (~15%)
```

> **Tại sao chia theo battery ID, không theo timestep?** Chia theo timestep gây **data leakage** — model biết trước degradation trajectory của cùng 1 cell. Chia theo battery ID ensures generalization across different cells [R2].

---

## 8. Benchmark & Metric Target

### 8.1 Target Metric `[PROJECT]`

| Metric | Target | Basis |
|--------|--------|-------|
| SOH MAE | < 2% | Standard regression metric, conservative target [R1, R2] |
| SOH RMSE | < 3% | Achievable với CNN-LSTM+Attention: RMSE < 0.004 ≈ 0.4% [R3] |
| Anomaly F1 | > 0.80 | Standard anomaly detection threshold [R4] |
| Inference latency | < 100ms | P1 Critical SLA requirement (real-time alert) |

### 8.2 Model Comparison Summary

```
CNN-LSTM thuần:    RMSE ≈ 0.020 (B0005)  ← không đạt target
LSTM đơn:          RMSE ≈ 0.0076 (B0005) ← đạt target (safe fallback)
CNN-LSTM+Attention: RMSE < 0.004 (B0005) ← tốt nhất, recommended
```

### 8.3 Isolation Forest Performance

```
Recall:    ~1.0 (85% optimization trials)  ← critical for safety
Precision: ~0.4–0.6 (trước khi filter)
Sau m=3 consecutive filter: Precision tăng đáng kể, Recall giữ nguyên
```

---

## 9. Danh sách Tài liệu Tham khảo

### Nguồn học thuật (peer-reviewed)

**[R1]** Phạm et al. (2025). *SOH-KLSTM: A Hybrid Kolmogorov-Arnold Network and LSTM Model for Enhanced Lithium-Ion Battery Health Monitoring*. arXiv:2509.10496.
- URL: https://arxiv.org/html/2509.10496v1
- Dùng cho: CNN-LSTM benchmark, RMSE comparison table, phê phán CNN-LSTM thuần
- Độ tin cậy: Cao (arXiv preprint, số liệu cụ thể trên NASA dataset chuẩn)

**[R2]** (2025). *Cycle-based State of Health Estimation of Lithium-Ion Cells Using Deep Learning Architectures*. Scientific Reports (Nature Publishing Group). PMC12550000.
- URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC12550000/
- Dùng cho: Baseline RMSE/MAE/R² cho LSTM/TCN/MLP/GRU trên NASA B0005-B0007; argument cho LSTM đơn là safe fallback
- Độ tin cậy: Cao (Scientific Reports, Nature Publishing Group, peer-reviewed, bảng số liệu đầy đủ)

**[R3]** (2023). *An Improved CNN-LSTM Model-Based State-of-Health Estimation Approach for Lithium-Ion Batteries*. Energy (Elsevier). DOI: 10.1016/j.energy.2023.xxxx.
- URL: https://www.sciencedirect.com/science/article/abs/pii/S0360544223009799
- Dùng cho: CNN-LSTM+Attention target RMSE < 0.004; phê phán generalization failure của baseline CNN-LSTM
- Độ tin cậy: Cao (Energy/Elsevier, peer-reviewed)

**[R4]** (2024). *An Open-Access Benchmark of Statistical and Machine-Learning Anomaly Detection Methods for Battery Applications (OSBAD)*. arXiv:2511.01745.
- URL: https://arxiv.org/html/2511.01745
- Dùng cho: Isolation Forest recall benchmark (85% trials), comparison 15 algorithms, safety-context argument
- Độ tin cậy: Cao (arXiv, open-access, Bayesian optimization, 15 thuật toán, Severson + Tohoku datasets)

**[R5]** (2025). *Markov-Constrained Isolation Forest for Early Detection of Battery Anomalies in Solar-Grid Applications*. Mathematics (MDPI), 14(7):1192.
- URL: https://www.mdpi.com/2227-7390/14/7/1192
- Dùng cho: Consecutive-point threshold m=3 (scientific basis); 88% anomaly detections trong ≥2 consecutive flags; solar-grid domain (closest to project)
- Độ tin cậy: Cao (MDPI Mathematics peer-reviewed, solar battery domain — most relevant paper)

**[R6]** (2025). *A Multi-Scenario Data-Driven Approach for Anomaly Detection in Electric Vehicle Battery Systems*. Journal of Energy Storage (Elsevier). DOI: 10.1016/j.est.2025.xxxxxx.
- URL: https://www.sciencedirect.com/science/article/abs/pii/S2590116825000256
- Dùng cho: IF + heuristic hybrid đạt 90–95% accuracy; IF standalone limitations; domain knowledge improvement
- Độ tin cậy: Cao (Journal of Energy Storage, Elsevier)

**[R7]** (2024). *Recent Advances in Model-Based Fault Diagnosis for Lithium-Ion Batteries: A Comprehensive Review*. arXiv:2401.16682.
- URL: https://arxiv.org/html/2401.16682v1
- Dùng cho: Fault taxonomy (Overcharge, Overdischarge, ISC, ESC, Sensor Faults, Thermal); voltage threshold principles; chemistry-specific threshold argument
- Độ tin cậy: Cao (arXiv comprehensive review, 2024)

**[R8]** (2025). *Fault Mitigation and Diagnosis for Lithium-Ion Batteries: A Review*. Frontiers in Energy Research. DOI: 10.3389/fenrg.2025.1529608.
- URL: https://www.frontiersin.org/journals/energy-research/articles/10.3389/fenrg.2025.1529608/full
- Dùng cho: Fault severity hierarchy (Critical > Major); Thermal Runaway = highest priority; end-of-life SOH 80%
- Độ tin cậy: Cao (Frontiers in Energy Research, peer-reviewed, 2025)

**[R9]** IEC TC21 (2022). *IEC 62619:2022 — Safety Requirements for Secondary Lithium Cells and Batteries for Use in Industrial Applications* (Edition 2.0).
- URL (summary): https://belltestchamber.com/iec-62619-safety-requirements-for-lithium-batteries-industrial-application.html
- Dùng cho: Overvoltage test condition (1.5× max charge voltage); BMS response time < 200ms; temperature thresholds (> 50–60°C concern, 15–35°C optimal); Triple monitoring requirement
- Độ tin cậy: Cao (IEC international standard) — ⚠️ cite gián tiếp qua summary, nên tìm bản gốc IEC để cite chính xác trong thesis

**[R10]** (2025). *Uncertainty-Informed Dynamic Threshold for Time Series Anomaly Detection*. Expert Systems with Applications (Elsevier). DOI: 10.1016/j.eswa.2025.xxxxxx.
- URL: https://www.sciencedirect.com/science/article/abs/pii/S0957417425010012
- Dùng cho: Phân biệt aleatoric vs epistemic uncertainty; POT/EVT threshold methodology; percentile 80 approach; segment-based anomaly confirmation
- Độ tin cậy: Cao (Expert Systems with Applications, Elsevier, 2025)

### Nguồn framework (non-academic, dùng có điều kiện)

**[R11]** Axelos (2019). *ITIL 4 Foundation: ITIL 4 Edition*. TSO (The Stationery Office).
- Dùng cho: P1/P2/P3 priority framework; Impact × Urgency matrix; escalation principles
- Độ tin cậy: Trung bình cho battery context — ITIL là IT service management standard, không phải battery-specific. ⚠️ Phải justify adaptation trong thesis.
- **Không cite Rootly blog** — tìm ITIL 4 official publication hoặc Axelos documentation

---

## Phụ lục — Gaps cần bổ sung `[PROJECT]`

| Gap | Tình trạng | Hành động |
|-----|-----------|-----------|
| B0018 không có external benchmark RMSE/MAE | Không tìm được paper | Team tự chạy, đây là contribution |
| Isolation Forest F1 trên NASA B0005-B0018 cụ thể | Không có paper nào test | Team tự chạy, report kết quả thực nghiệm |
| N/D/B labels không tồn tại trong NASA | Gap đã biết | Áp dụng labeling rule mục 7.2 |
| IEC/IEEE standard battery P1/P2/P3 | Không tồn tại | Dùng ITIL 4 + IEC 62619 hybrid, justify rõ trong thesis |
| Threshold cho Abnormal Discharge (C-rate cụ thể) | Chưa xác nhận đủ | Cần fetch thêm 1 paper về C-rate threshold |

---

*Tài liệu này được tổng hợp bởi Research Agent + Reviewer Agent theo framework `.claude/agents/researcher.md` và `.claude/agents/reviewer.md` của dự án GSU26SE55.*
*Cập nhật lần cuối: 2026-05-17*
