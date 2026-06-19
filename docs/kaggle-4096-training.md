# Kaggle Training Guide — Mamba L=4096

Huong dan nay tu dau den cuoi de train Mamba voi 4096 token tren Kaggle GPU (P100 / T4).

Config target:

```
WINDOW_SIZE        = 4096
WINDOW_STRIDE      = 100
INPUT_FEATURES     = 6
SPECTRAL_FEAT_DIM  = 54
D_MODEL            = 64
D_STATE            = 16
BATCH_SIZE         = 4     (GPU, parallel scan)
MODEL_VERSION      = 1.3
```

Chay theo thu tu cell trong notebook `notebooks/kaggle_train_4096.ipynb`.

---

## 0. Chuan bi dataset tren Kaggle

### 0.1 Upload NASA dataset

1. Vao `kaggle.com/datasets` -> `+ New Dataset`
2. Ten dataset: `nasa-battery-dataset`
3. Upload toan bo thu muc `cleaned_dataset/` (co `metadata.csv` va `data/*.csv`)
4. Visibility: Private

Sau khi upload xong, dataset URL se la:
```
https://www.kaggle.com/datasets/<username>/nasa-battery-dataset
```

### 0.2 Tao notebook

1. `kaggle.com/code` -> `+ New Notebook`
2. Upload `notebooks/kaggle_train_4096.ipynb`
3. Settings (ben phai):
   - `Accelerator`: **GPU P100** (hoac T4)
   - `Internet`: On (de clone repo)
4. `+ Add Data` -> chon dataset `nasa-battery-dataset`

Dataset se mount vao:
```
/kaggle/input/nasa-battery-dataset/
```

---

## 1. Kiem tra GPU

Cell 1 trong notebook:

```python
!nvidia-smi

import torch
print("PyTorch:", torch.__version__)
print("CUDA:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
    print("VRAM:", torch.cuda.get_device_properties(0).total_memory // 1024**3, "GB")
```

Ket qua can co `CUDA: True`. Neu `False`, kiem tra Settings -> Accelerator.

---

## 2. Clone repo

### Repo public

```python
import subprocess
subprocess.run([
    "git", "clone", "--branch", "feat/spectral_kurtosis",
    "--single-branch",
    "https://github.com/GSU26SE55/ai-module.git",
    "/kaggle/working/ai-module"
], check=True)
```

### Repo private

```python
from kaggle_secrets import UserSecretsClient
token = UserSecretsClient().get_secret("GITHUB_TOKEN")

import subprocess
subprocess.run([
    "git", "clone", "--branch", "feat/spectral_kurtosis",
    "--single-branch",
    f"https://{token}@github.com/GSU26SE55/ai-module.git",
    "/kaggle/working/ai-module"
], check=True)

# Xoa token khoi remote
subprocess.run([
    "git", "-C", "/kaggle/working/ai-module",
    "remote", "set-url", "origin",
    "https://github.com/GSU26SE55/ai-module.git"
], check=True)
```

Them GitHub token vao Kaggle Secrets:
- `Add-ons` -> `Secrets` -> `+ New Secret`
- Label: `GITHUB_TOKEN`, Value: token cua ban.

---

## 3. Cai dependencies

```python
%pip install -q scipy scikit-learn
```

Kaggle da co NumPy, pandas, PyTorch CUDA. Chi can scipy va scikit-learn.

Kiem tra:
```python
import scipy, sklearn, torch
print("scipy:", scipy.__version__)
print("sklearn:", sklearn.__version__)
print("torch:", torch.__version__)
```

---

## 4. Khai bao duong dan

```python
import os, sys

REPO      = "/kaggle/working/ai-module"
DATASET   = "/kaggle/input/nasa-battery-dataset/cleaned_dataset"
PROCESSED = "/kaggle/working/processed"
WEIGHTS   = "/kaggle/working/weights"
LOGS      = "/kaggle/working/logs"

os.makedirs(PROCESSED, exist_ok=True)
os.makedirs(WEIGHTS,   exist_ok=True)
os.makedirs(LOGS,      exist_ok=True)

# Symlink weights vao repo
repo_weights = f"{REPO}/models/weights"
os.makedirs(repo_weights, exist_ok=True)

# Neu chua symlink
if not os.path.islink(repo_weights):
    import shutil
    shutil.rmtree(repo_weights, ignore_errors=True)
    os.symlink(WEIGHTS, repo_weights)

sys.path.insert(0, REPO)

# Kiem tra dataset
metadata = f"{DATASET}/metadata.csv"
data_dir = f"{DATASET}/data"
print("metadata.csv:", os.path.isfile(metadata))
print("data/:", os.path.isdir(data_dir))
if os.path.isdir(data_dir):
    print("CSV count:", len([f for f in os.listdir(data_dir) if f.endswith(".csv")]))
```

---

## 5. Cap nhat config sang L=4096

```python
config_path = f"{REPO}/src/core/config.py"

with open(config_path) as f:
    content = f.read()

replacements = {
    'MODEL_VERSION = "1.1"': 'MODEL_VERSION = "1.3"',
    'WINDOW_SIZE = 30':      'WINDOW_SIZE = 4096',
    'WINDOW_STRIDE = 30':    'WINDOW_STRIDE = 100',
}
for old, new in replacements.items():
    content = content.replace(old, new)

with open(config_path, "w") as f:
    f.write(content)

# Kiem tra
from src.core.config import WINDOW_SIZE, WINDOW_STRIDE, MODEL_VERSION
print(f"WINDOW_SIZE={WINDOW_SIZE}, STRIDE={WINDOW_STRIDE}, VERSION={MODEL_VERSION}")
```

---

## 6. Preprocess

```python
os.chdir(REPO)
!python scripts/preprocess.py \
    --data-dir "{DATASET}" \
    --output-dir "{PROCESSED}"
```

Ket qua mong doi:
```
Train: ~1386 windows from 504 cycles
Val  :  ~462 windows from 92 cycles
Test :  ~152 windows from 40 cycles
```

---

## 7. Kiem tra data shape

```python
import torch

for name in ["train.pt", "val.pt", "test.pt"]:
    d = torch.load(f"{PROCESSED}/{name}", weights_only=False)
    print(f"{name}: X={tuple(d['X'].shape)}, "
          f"X_feat={tuple(d['X_feat'].shape)}, y={tuple(d['y'].shape)}")
```

Tat ca X phai co shape `(N, 4096, 6)`.

---

## 8. Smoke test (2 batch)

Xac nhan forward/backward hoat dong tren GPU truoc khi full train.

```python
os.chdir(REPO)
!python scripts/train.py \
    --data-dir "{PROCESSED}" \
    --epochs 1 \
    --log-dir "{LOGS}/smoke"
```

Neu `Test MAE` xuyen hien va khong co loi CUDA OOM, chay full train.

---

## 9. Full training

```python
os.chdir(REPO)
!python scripts/train.py \
    --data-dir "{PROCESSED}" \
    --epochs 150 \
    --log-dir "{LOGS}"
```

Uoc tinh thoi gian tren P100:
- Moi epoch: 3-5 phut
- Early stopping: thong thuong o epoch 40-70
- Tong: ~3-5 gio

---

## 10. Kiem tra artifacts

```python
required = [
    "scaler.pkl",
    "feature_scaler.pkl",
    "soh_mamba_v1.3.pth",
    "isolation_forest_v1.3.pkl",
]
for f in required:
    path = f"{WEIGHTS}/{f}"
    ok   = os.path.isfile(path)
    size = os.path.getsize(path) / 1024 if ok else 0
    print(f"{f}: {ok}  ({size:.0f} KB)")
```

---

## 11. Download artifacts

Tao file zip de download tu Kaggle Output:

```python
import shutil
shutil.make_archive("/kaggle/working/artifacts_v1.3", "zip", WEIGHTS)
print("Created: /kaggle/working/artifacts_v1.3.zip")
```

File se hien trong tab `Output` cua notebook tren Kaggle.

---

## 12. Copy artifacts vao repo local

Sau khi download `artifacts_v1.3.zip`, giai nen vao `ai-module/models/weights/`:

```
models/weights/
  scaler.pkl
  feature_scaler.pkl
  soh_mamba_v1.3.pth
  isolation_forest_v1.3.pkl
```

Commit toan bo:
```bash
git add models/weights/
git commit -m "feat: Mamba v1.3 trained at L=4096 on Kaggle GPU"
```

---

## 13. Loi thuong gap

### CUDA out of memory

Giam batch size trong `scripts/train.py`:
```python
BATCH_SIZE = 2  # hoac 1
```

### `metadata.csv` not found

```python
!find /kaggle/input -name "metadata.csv"
```
Cap nhat bien `DATASET` theo ket qua tim duoc.

### Config khong update

Restart kernel va chay lai tu Cell 4 (khai bao duong dan).

### Train qua cham (CPU mode)

Kiem tra:
```python
import torch
print(torch.cuda.is_available())  # phai la True
```
Neu `False`, doi Settings -> Accelerator -> GPU -> Save -> restart.
