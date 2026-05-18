---
name: scaffold-model
description: Scaffold PyTorch model class (CNN-LSTM SOHPredictor) hoặc Isolation Forest wrapper với save/load methods kèm version metadata chuẩn dự án
argument-hint: [ModelName]
allowed-tools: Write, Read, Bash
---

# Scaffold Model `$ARGUMENTS`

Usage: `/scaffold-model <ModelName>`
Example: `/scaffold-model SOHPredictor` | `/scaffold-model AnomalyDetector`

---

## Bước 0 — Xác định loại model

Từ `$ARGUMENTS`, xác định:
- Tên chứa `SOH` / `LSTM` / `CNN` / `Predictor` → **Template A: CNN-LSTM**
- Tên chứa `Anomaly` / `Forest` / `Iso` / `Detector` → **Template B: Isolation Forest**
- Không rõ → hỏi user trước khi tạo file

Tính `{snake_name}` từ `$ARGUMENTS` (PascalCase → snake_case):
`SOHPredictor` → `soh_predictor` | `AnomalyDetector` → `anomaly_detector`

---

## Bước 1 — Tạo thư mục

```bash
mkdir -p models/weights
touch models/__init__.py
```

---

## Bước 2A — Template CNN-LSTM: `models/{snake_name}.py`

```python
import torch
import torch.nn as nn


WINDOW_SIZE    = 30
INPUT_FEATURES = 3      # voltage, current, temperature
HIDDEN_SIZE    = 64
NUM_LAYERS     = 2
DROPOUT        = 0.2


class {ModelName}(nn.Module):
    """
    CNN-LSTM để dự đoán SOH (State of Health) của pin lithium-ion.

    Input:  (batch, 30, 3)  — 30 timestep × [voltage, current, temperature]
    Output: (batch,)        — SOH% trong khoảng [0, 100]
    """

    def __init__(self) -> None:
        super().__init__()
        self.conv1   = nn.Conv1d(INPUT_FEATURES, 32, kernel_size=3, padding=1)
        self.relu    = nn.ReLU()
        self.pool    = nn.MaxPool1d(kernel_size=2)
        self.lstm    = nn.LSTM(32, HIDDEN_SIZE, NUM_LAYERS,
                               batch_first=True, dropout=DROPOUT)
        self.fc1     = nn.Linear(HIDDEN_SIZE, 32)
        self.fc2     = nn.Linear(32, 1)
        self.dropout = nn.Dropout(DROPOUT)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, 30, 3) → output: (batch,)"""
        x = x.permute(0, 2, 1)                        # (batch, 3, 30)
        x = self.pool(self.relu(self.conv1(x)))         # (batch, 32, 15)
        x = x.permute(0, 2, 1)                        # (batch, 15, 32)
        _, (h_n, _) = self.lstm(x)
        x = h_n[-1]                                    # (batch, 64)
        x = self.dropout(self.relu(self.fc1(x)))
        return self.fc2(x).squeeze(-1)                 # (batch,)

    def save(self, path: str, version: str = "1.0") -> None:
        """Lưu weights kèm metadata — BẮT BUỘC để phát hiện version mismatch."""
        import torch
        torch.save({
            "model_state_dict": self.state_dict(),
            "version":          version,
            "window_size":      WINDOW_SIZE,
            "input_features":   INPUT_FEATURES,
        }, path)

    @classmethod
    def load(cls, path: str, expected_version: str = "1.0") -> "{ModelName}":
        import torch
        checkpoint = torch.load(path, map_location="cpu")
        assert checkpoint["version"] == expected_version, (
            f"Model version mismatch: expected {expected_version}, "
            f"got {checkpoint['version']}"
        )
        model = cls()
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        return model
```

---

## Bước 2B — Template Isolation Forest: `models/{snake_name}.py`

```python
import numpy as np
import joblib
from sklearn.ensemble import IsolationForest


CONTAMINATION = 0.1
N_ESTIMATORS  = 100
RANDOM_STATE  = 42


class {ModelName}:
    """
    Isolation Forest để phát hiện bất thường trong chuỗi đo lường pin.

    Mapping score → classification:
      score > -0.1              → "Normal"
      score > -0.3 hoặc SOH≥80  → "Degrading"
      còn lại                   → "Failed"
    """

    def __init__(self) -> None:
        self._model     = IsolationForest(
            contamination=CONTAMINATION,
            n_estimators=N_ESTIMATORS,
            random_state=RANDOM_STATE,
        )
        self._is_fitted = False

    def fit(self, X: np.ndarray) -> None:
        """Fit trên train set. KHÔNG gọi lại trên production data."""
        self._model.fit(X)
        self._is_fitted = True

    def score(self, X: np.ndarray) -> np.ndarray:
        assert self._is_fitted, "Model chưa fit — gọi fit() hoặc load() trước."
        return self._model.decision_function(X)

    def classify(self, score: float, soh: float) -> str:
        if score > -0.1:
            return "Normal"
        if score > -0.3 or soh >= 80:
            return "Degrading"
        return "Failed"

    def save(self, path: str, version: str = "1.0") -> None:
        assert self._is_fitted, "Model chưa fit — không thể lưu."
        joblib.dump({"model": self._model, "version": version}, path)

    @classmethod
    def load(cls, path: str, expected_version: str = "1.0") -> "{ModelName}":
        artifact = joblib.load(path)
        assert artifact["version"] == expected_version, (
            f"Model version mismatch: expected {expected_version}, "
            f"got {artifact['version']}"
        )
        instance = cls()
        instance._model     = artifact["model"]
        instance._is_fitted = True
        return instance
```

---

## Checklist sau scaffold

- [ ] File tạo tại `models/{snake_name}.py`?
- [ ] `models/__init__.py` tồn tại?
- [ ] `save()` và `load()` có version assertion?
- [ ] `RANDOM_STATE = 42` có trong Isolation Forest?
- [ ] Không thêm model thứ 3 ngoài SOHPredictor + AnomalyDetector?

---

## Không được
- Tạo model architecture mới ngoài CNN-LSTM + Isolation Forest mà chưa có leader approval
- Bỏ version metadata trong `save()` — inference cần phát hiện mismatch khi startup
- Fit Isolation Forest trên production / val / test data
