---
name: scaffold-training
description: Scaffold training script — SOH (Adam lr=1e-3, MSELoss, early stopping patience=10) hoặc Isolation Forest, seed=42, lưu artifacts kèm version metadata
argument-hint: [ModelName]
allowed-tools: Write, Read, Bash
---

# Scaffold Training `$ARGUMENTS`

Usage: `/scaffold-training <ModelName>`
Example: `/scaffold-training SOHPredictor` | `/scaffold-training AnomalyDetector`

---

## Bước 0 — Xác định loại training

Từ `$ARGUMENTS`:
- Tên chứa `SOH` / `LSTM` / `CNN` / `Predictor` → **Template A: PyTorch**
- Tên chứa `Anomaly` / `Forest` / `Iso` / `Detector` → **Template B: Isolation Forest**
- Không rõ → hỏi user

---

## Bước 1 — Tạo thư mục

```bash
mkdir -p train models/weights
touch train/__init__.py
```

---

## Bước 2A — Template PyTorch: `train/train_soh.py`

```python
"""
Training script cho SOHPredictor (CNN-LSTM).

Artifacts output sau khi chạy:
  models/weights/soh_lstm_v{VERSION}.pth  ← weights + metadata
  models/weights/scaler.pkl               ← MinMaxScaler (từ preprocess)

Chạy: python -m train.train_soh
"""
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from data.preprocess import load_dataset, prepare_splits
from models.soh_predictor import SOHPredictor

# ─────────────────────────── config ────────────────────────────────
SEED       = 42
VERSION    = "1.0"
DATA_DIR   = Path("data/raw")
MODEL_PATH = Path(f"models/weights/soh_lstm_v{VERSION}.pth")

LR         = 1e-3
EPOCHS     = 50
PATIENCE   = 10
BATCH_SIZE = 32

# ─────────────────────────── seed ──────────────────────────────────
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)


def train() -> None:
    print("── Load & preprocess ───────────────────────────────────────")
    batteries            = load_dataset(DATA_DIR)
    X_tr, y_tr, X_val, y_val, _, _ = prepare_splits(batteries)

    train_loader = DataLoader(
        TensorDataset(
            torch.tensor(X_tr,  dtype=torch.float32),
            torch.tensor(y_tr,  dtype=torch.float32),
        ),
        batch_size=BATCH_SIZE, shuffle=True,
    )
    val_loader = DataLoader(
        TensorDataset(
            torch.tensor(X_val, dtype=torch.float32),
            torch.tensor(y_val, dtype=torch.float32),
        ),
        batch_size=BATCH_SIZE,
    )
    print(f"  Train: {len(X_tr)} samples | Val: {len(X_val)} samples")

    print("── Init model ──────────────────────────────────────────────")
    model     = SOHPredictor()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    criterion = nn.MSELoss()

    best_val_loss = float("inf")
    patience_left = PATIENCE
    best_state    = None

    print("── Training loop ───────────────────────────────────────────")
    for epoch in range(1, EPOCHS + 1):
        model.train()
        train_loss = _run_epoch(model, train_loader, criterion, optimizer)

        model.eval()
        with torch.no_grad():
            val_loss = _run_epoch(model, val_loader, criterion, optimizer=None)

        print(f"Epoch {epoch:3d}/{EPOCHS}  "
              f"train={train_loss:.4f}  val={val_loss:.4f}  "
              f"patience={patience_left}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_left = PATIENCE
            best_state    = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            patience_left -= 1
            if patience_left == 0:
                print(f"  Early stopping tại epoch {epoch}")
                break

    if best_state:
        model.load_state_dict(best_state)

    print("── Evaluate ────────────────────────────────────────────────")
    model.eval()
    with torch.no_grad():
        mae_tr  = _mae(model(torch.tensor(X_tr,  dtype=torch.float32)).numpy(), y_tr)
        mae_val = _mae(model(torch.tensor(X_val, dtype=torch.float32)).numpy(), y_val)
        rmse_v  = _rmse(model(torch.tensor(X_val, dtype=torch.float32)).numpy(), y_val)

    print(f"  Train MAE : {mae_tr:.2f}%")
    print(f"  Val   MAE : {mae_val:.2f}%  (target < 2%)")
    print(f"  Val   RMSE: {rmse_v:.2f}%  (target < 3%)")

    if mae_val > 2.0:
        print("  ⚠️  MAE vượt target 2% — kiểm tra data hoặc hyperparameter")
    if rmse_v > 3.0:
        print("  ⚠️  RMSE vượt target 3% — kiểm tra data hoặc hyperparameter")

    print("── Save ────────────────────────────────────────────────────")
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(MODEL_PATH), version=VERSION)
    print(f"  Model → {MODEL_PATH}")
    print("── Done ────────────────────────────────────────────────────")


def _run_epoch(
    model: SOHPredictor,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer | None,
) -> float:
    total = 0.0
    for X_b, y_b in loader:
        preds = model(X_b)
        loss  = criterion(preds, y_b)
        if optimizer is not None:
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        total += loss.item() * len(X_b)
    return total / len(loader.dataset)


def _mae(preds: np.ndarray, targets: np.ndarray) -> float:
    return float(np.mean(np.abs(preds - targets)))


def _rmse(preds: np.ndarray, targets: np.ndarray) -> float:
    return float(np.sqrt(np.mean((preds - targets) ** 2)))


if __name__ == "__main__":
    train()
```

---

## Bước 2B — Template Isolation Forest: `train/train_anomaly.py`

```python
"""
Training script cho AnomalyDetector (Isolation Forest).

Artifacts output sau khi chạy:
  models/weights/isolation_forest_v{VERSION}.pkl

Chạy: python -m train.train_anomaly
"""
import random
from pathlib import Path

import numpy as np

from data.preprocess import load_dataset, prepare_splits
from models.anomaly_detector import AnomalyDetector

SEED       = 42
VERSION    = "1.0"
DATA_DIR   = Path("data/raw")
MODEL_PATH = Path(f"models/weights/isolation_forest_v{VERSION}.pkl")

random.seed(SEED)
np.random.seed(SEED)


def train() -> None:
    print("── Load & preprocess ───────────────────────────────────────")
    batteries           = load_dataset(DATA_DIR)
    X_tr, _, _, _, _, _ = prepare_splits(batteries)

    n, w, f = X_tr.shape
    X_flat  = X_tr.reshape(n, w * f)
    print(f"  Train samples: {len(X_flat)}  Features: {w * f}")

    print("── Fit Isolation Forest ────────────────────────────────────")
    model = AnomalyDetector()
    model.fit(X_flat)

    print("── Save ────────────────────────────────────────────────────")
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(MODEL_PATH), version=VERSION)
    print(f"  Model → {MODEL_PATH}")
    print("── Done ────────────────────────────────────────────────────")


if __name__ == "__main__":
    train()
```

---

## Checklist sau scaffold

- [ ] `SEED = 42` ở đầu file, cả 3 seed (`random`, `numpy`, `torch`) được set?
- [ ] `PATIENCE = 10`, `LR = 1e-3`, `EPOCHS = 50`, `BATCH_SIZE = 32`?
- [ ] In ra MAE/RMSE sau training và warning nếu vượt target?
- [ ] Model được `save()` kèm `version` metadata?
- [ ] Không dùng X_test trong training hoặc validation loss?
- [ ] `DATA_DIR` dùng `Path`, không hardcode string tuyệt đối?

---

## Không được
- Dùng test data trong training loop
- Bỏ early stopping
- Claim metric đạt target mà không in số thực tế
- Fit scaler lại trong training script — scaler do `prepare_splits()` xử lý
