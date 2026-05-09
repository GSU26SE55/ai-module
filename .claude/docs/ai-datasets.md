# AI Datasets — GSU26SE55

Dataset cho training LSTM/CNN-LSTM (SOH prediction) và Isolation Forest (anomaly detection).

---

## Dataset ưu tiên

### 1. NASA Ames Battery Aging Dataset ⭐ (ưu tiên nhất)

| Thông tin | Chi tiết |
|-----------|---------|
| Cell type | 18650 lithium-ion |
| Số cell | 18 cell (B0005–B0056) |
| Dữ liệu | Charge/discharge cycles, impedance |
| Format | `.mat` (MATLAB) |
| Size | ~600 MB |

**Download:**
```
https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/
→ Section: Battery Data Set (Prognostics Center)
```
Hoặc dùng Kaggle mirror (nhanh hơn):
```
https://www.kaggle.com/datasets/patrickfleith/nasa-battery-dataset
```

**Load trong Python:**
```python
import scipy.io
import numpy as np

data = scipy.io.loadmat("B0005.mat")
battery = data["B0005"][0][0]
cycles = battery["cycle"][0]
```

**Columns quan trọng:**
- `voltage_measured` — điện áp đo được (V)
- `current_measured` — dòng điện đo được (A)
- `temperature_measured` — nhiệt độ (°C)
- `capacity` — dung lượng còn lại (Ah) → dùng để tính SOH

**Tính SOH:**
```python
# SOH = capacity_current / capacity_nominal * 100
SOH = cycle_capacity / nominal_capacity * 100  # nominal ~2.0 Ah
```

---

### 2. CALCE CS2 Battery Dataset (backup nếu cần thêm data)

| Thông tin | Chi tiết |
|-----------|---------|
| Cell type | Prismatic lithium-ion (CS2) |
| Số cell | 8 cell (CS2-33 đến CS2-38) |
| Dữ liệu | Charge/discharge cycles |
| Format | `.xlsx` hoặc `.csv` |
| Size | ~200 MB |

**Download:**
```
https://calce.umd.edu/battery-data
→ CS2 Battery Dataset
```

---

### 3. MIT/Stanford Fast-Charging Dataset (tùy chọn — nếu cần diversity)

| Thông tin | Chi tiết |
|-----------|---------|
| Cell type | 18650 NMC lithium-ion |
| Số cell | 124 cell |
| Dữ liệu | Fast-charging profiles, cycle life |
| Format | `.pkl` (Python pickle) |
| Size | ~4 GB |

**Download:**
```
https://data.matr.io/1/projects/5c48dd2bc625d700019f3204
```

> ⚠️ Dataset lớn — chỉ dùng nếu NASA + CALCE không đủ đa dạng.

---

### 4. Oxford Battery Degradation Dataset (tùy chọn)

| Thông tin | Chi tiết |
|-----------|---------|
| Cell type | Kokam lithium pouch |
| Số cell | 8 cell |
| Format | `.mat` |
| Size | ~100 MB |

**Download:**
```
https://ora.ox.ac.uk/objects/uuid:03ba4b01-cfed-46d3-9b1a-7d4a7bdf6fac
```

---

## Folder structure trong repo

```
ai-module/
├── data/
│   ├── raw/            ← Không commit — thêm vào .gitignore
│   │   ├── nasa/       ← NASA .mat files
│   │   └── calce/      ← CALCE .xlsx/.csv files
│   ├── processed/      ← Output của preprocessing script
│   │   ├── train.pt
│   │   ├── val.pt
│   │   └── test.pt
│   └── README.md       ← Ghi rõ nguồn + phiên bản data đã dùng
```

**.gitignore — thêm vào:**
```
data/raw/
data/processed/
*.mat
# ⚠️ KHÔNG ignore *.pkl toàn bộ — scaler.pkl tại models/weights/ phải được commit
# Chỉ ignore pkl trong data/
data/**/*.pkl
```

---

## Preprocessing convention

```python
# data/preprocess.py
import random
import numpy as np
import torch
from sklearn.preprocessing import MinMaxScaler
import joblib

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

# Split theo battery ID — không theo timestep (tránh leakage liên cycle)
# NASA có 18 battery cells → chia:
#   Train: 12 batteries (~67%)
#   Val:    3 batteries (~17%)
#   Test:   3 batteries (~17%)
TRAIN_BATTERIES = ["B0005", "B0006", "B0007", "B0018", "B0025", "B0026",
                   "B0027", "B0028", "B0029", "B0030", "B0031", "B0032"]
VAL_BATTERIES   = ["B0033", "B0034", "B0036"]
TEST_BATTERIES  = ["B0038", "B0039", "B0040"]

# Window size bắt buộc: 30 timestep, 3 features (voltage, current, temperature)
WINDOW_SIZE = 30
FEATURES    = ["voltage_measured", "current_measured", "temperature_measured"]

# Scaler: chỉ fit trên train, transform val và test
scaler = MinMaxScaler()
X_train_scaled = scaler.fit_transform(X_train)   # fit + transform train
X_val_scaled   = scaler.transform(X_val)          # chỉ transform
X_test_scaled  = scaler.transform(X_test)         # chỉ transform

# Lưu scaler để dùng lại khi inference
joblib.dump(scaler, "models/weights/scaler.pkl")
```

---

## Quy tắc sử dụng data

- **KHÔNG commit raw data** vào Git — kích thước lớn, có thể có license restrictions
- Mỗi dev tự download và đặt vào `data/raw/` theo cấu trúc trên
- File `data/README.md` phải ghi rõ: dataset version, ngày download, source URL
- **KHÔNG dùng test set trong training** — data leakage làm accuracy ảo
- **Chia theo battery ID** — không chia theo timestep (tránh thông tin tương lai lọt vào train)
- **`scaler.pkl` phải được commit** — inference cần cùng scaler với training
- Target metric: MAE < 2% SOH, RMSE < 3% SOH, F1 > 0.80 anomaly
