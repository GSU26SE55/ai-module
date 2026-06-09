# Google Colab Training Guide - Mamba 4096

Tai lieu nay huong dan tu luc tao Colab runtime den khi:

- clone dung branch;
- mount Google Drive;
- kiem tra dataset;
- preprocess;
- smoke test;
- full training;
- resume sau khi runtime bi ngat;
- lay model artifacts sau training.

Model hien tai dung:

```text
WINDOW_SIZE = 4096
INPUT_FEATURES = 6
SPECTRAL_FEAT_DIM = 54
D_MODEL = 64
D_STATE = 16
physical batch = 1
gradient accumulation = 8
```

Chay tung cell theo dung thu tu. Khong chay tat ca cell clone/preprocess/full-train nhieu lan neu khong can.

## 0. Chuan bi truoc

Can co:

- Google Colab.
- Google Drive.
- Quyen truy cap repo `GSU26SE55/ai-module`.
- GitHub Personal Access Token neu repo private.
- NASA cleaned dataset tren Google Drive.

Dataset nen co cau truc:

```text
MyDrive/
+-- GSU26SE55/
    +-- cleaned_dataset/
        +-- metadata.csv
        +-- data/
        |   +-- *.csv
        +-- extra_infos/
```

## 1. Tao notebook va bat GPU

Trong Google Colab:

```text
Runtime -> Change runtime type -> Hardware accelerator -> GPU -> Save
```

Colab co the cap T4, L4 hoac GPU khac tuy quota. Khong can bat buoc dung T4, nhung full training nen co CUDA GPU.

Cell 1:

```python
!nvidia-smi
```

Cell 2:

```python
import torch

print("PyTorch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())

if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
```

Ket qua can co:

```text
CUDA available: True
```

Neu la `False`:

1. Kiem tra runtime da chon GPU.
2. Chon `Runtime -> Restart session`.
3. Chay lai Cell 1 va Cell 2.

Neu Colab khong cap GPU do quota, chi nen CPU smoke test. Khong nen full-train 100 epoch tren CPU.

## 2. Mount Google Drive

Cell 3:

```python
from google.colab import drive

drive.mount("/content/drive")
```

Neu hien:

```text
Drive already mounted at /content/drive
```

thi Drive da san sang, khong phai loi.

Kiem tra:

```python
!ls /content/drive/MyDrive
```

## 3. Clone repo dung branch

### 3.1 Repo private

Cell 4:

```python
from getpass import getpass

token = getpass("GitHub token: ")
```

Cell 5:

```python
%cd /content
!rm -rf /content/ai-module
!git clone --branch feat/spectral_kurtosis --single-branch https://{token}@github.com/GSU26SE55/ai-module.git /content/ai-module
```

Cell 5b - xoa token khoi Git remote:

```python
%cd /content/ai-module
!git remote set-url origin https://github.com/GSU26SE55/ai-module.git
token = None
```

Token van can duoc nhap lai neu sau nay push/pull private repo ma khong co credential khac.

### 3.2 Repo public

Neu repo public, thay Cell 4-5 bang:

```python
%cd /content
!rm -rf /content/ai-module
!git clone --branch feat/spectral_kurtosis --single-branch https://github.com/GSU26SE55/ai-module.git /content/ai-module
```

### 3.3 Luu y loi current directory

Luon `%cd /content` truoc khi xoa `/content/ai-module`.

Khong lam:

```python
%cd /content/ai-module
!rm -rf /content/ai-module
```

Neu lam sai, shell co the bao:

```text
getcwd: cannot access parent directories
fatal: Unable to read current working directory
```

Sua bang:

```python
%cd /content
```

roi clone lai.

## 4. Kiem tra repo va commit

Cell 6:

```python
%cd /content/ai-module
!pwd
!git branch --show-current
!git log -1 --oneline
!ls
```

Can thay:

```text
/content/ai-module
feat/spectral_kurtosis
requirements.txt
scripts
src
models
```

Neu khong thay `requirements.txt`, clone chua thanh cong hoac dang o sai folder.

## 5. Cai dependencies

Cell 7:

```python
%cd /content/ai-module
%pip install -q -r requirements.txt
```

Sau khi install xong, bat buoc restart kernel de tranh NumPy/pandas binary incompatibility:

```python
import os
import signal

os.kill(os.getpid(), signal.SIGKILL)
```

Colab se reconnect runtime. Sau do:

1. Chay lai cell mount Drive.
2. Kiem tra `/content/ai-module` con ton tai.
3. Khong can clone lai neu repo van con.
4. Khong chay lai `pip install` neu install da thanh cong.

Cell 8 - kiem tra dependencies sau khi reconnect:

```python
import numpy
import pandas
import scipy
import sklearn
import torch

print("NumPy:", numpy.__version__)
print("pandas:", pandas.__version__)
print("SciPy:", scipy.__version__)
print("scikit-learn:", sklearn.__version__)
print("PyTorch:", torch.__version__)
print("CUDA:", torch.cuda.is_available())

if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
```

Expected versions:

```text
NumPy: 1.26.4
pandas: 2.2.2
SciPy: 1.13.1
scikit-learn: 1.5.0
```

Neu van gap:

```text
ValueError: numpy.dtype size changed
```

force reinstall bo numerical packages:

```python
%pip install --force-reinstall --no-cache-dir \
  numpy==1.26.4 \
  pandas==2.2.2 \
  scipy==1.13.1 \
  scikit-learn==1.5.0
```

Sau do restart kernel lan nua:

```python
import os
import signal

os.kill(os.getpid(), signal.SIGKILL)
```

Khong import NumPy/pandas trong cung session sau khi pip thay doi version ma chua restart.

## 6. Khai bao duong dan

Cell 9:

```python
import os

REPO = "/content/ai-module"
DRIVE_ROOT = "/content/drive/MyDrive/GSU26SE55"

DATASET = f"{DRIVE_ROOT}/cleaned_dataset"
PROCESSED = f"{DRIVE_ROOT}/processed"
CHECKPOINTS = f"{DRIVE_ROOT}/checkpoints"
LOGS = f"{DRIVE_ROOT}/logs"
WEIGHTS = f"{DRIVE_ROOT}/weights"

for path in [PROCESSED, CHECKPOINTS, LOGS, WEIGHTS]:
    os.makedirs(path, exist_ok=True)

print("REPO:", REPO)
print("DATASET:", DATASET)
print("PROCESSED:", PROCESSED)
print("CHECKPOINTS:", CHECKPOINTS)
print("LOGS:", LOGS)
print("WEIGHTS:", WEIGHTS)
```

Moi khi restart runtime, can chay lai cell khai bao bien nay.

## 7. Kiem tra dataset tren Drive

Cell 10:

```python
import os

metadata_path = os.path.join(DATASET, "metadata.csv")
data_path = os.path.join(DATASET, "data")

print("metadata.csv:", os.path.isfile(metadata_path))
print("data folder:", os.path.isdir(data_path))

if os.path.isdir(data_path):
    print("CSV count:", len(os.listdir(data_path)))
```

Can thay:

```text
metadata.csv: True
data folder: True
```

Neu la `False`, tim file:

```python
!find /content/drive/MyDrive -name metadata.csv
```

Vi du output:

```text
/content/drive/MyDrive/GSU26SE55/cleaned_dataset/cleaned_dataset/metadata.csv
```

thi sua:

```python
DATASET = "/content/drive/MyDrive/GSU26SE55/cleaned_dataset/cleaned_dataset"
```

Sau do chay lai Cell 10.

Khong chay preprocess khi `metadata.csv` hoac `data folder` con `False`.

## 8. Dua model weights vao Drive

Training luu artifacts vao:

```text
/content/ai-module/models/weights
```

Folder `/content` se mat khi runtime bi xoa. Vi vay dung symbolic link de weights duoc ghi truc tiep vao Drive.

Cell 11:

```python
import os
import shutil

REPO_WEIGHTS = "/content/ai-module/models/weights"

os.makedirs(REPO_WEIGHTS, exist_ok=True)
os.makedirs(WEIGHTS, exist_ok=True)

# Copy artifacts san co tu Git sang Drive neu Drive chua co.
for name in os.listdir(REPO_WEIGHTS):
    source = os.path.join(REPO_WEIGHTS, name)
    destination = os.path.join(WEIGHTS, name)

    if os.path.isfile(source) and not os.path.exists(destination):
        shutil.copy2(source, destination)

# Thay repo weights folder bang symlink toi Drive.
if os.path.islink(REPO_WEIGHTS):
    os.unlink(REPO_WEIGHTS)
elif os.path.isdir(REPO_WEIGHTS):
    shutil.rmtree(REPO_WEIGHTS)

os.symlink(WEIGHTS, REPO_WEIGHTS)

print("Repo weights:", REPO_WEIGHTS)
print("Real location:", os.path.realpath(REPO_WEIGHTS))
print("Files:", sorted(os.listdir(REPO_WEIGHTS)))
```

Sau moi runtime reset va clone lai repo, chay lai Cell 11.

## 9. Kiem tra processed data

Cell 12:

```python
import os

processed_ready = True

for name in ["train.pt", "val.pt", "test.pt"]:
    path = os.path.join(PROCESSED, name)
    exists = os.path.isfile(path)
    processed_ready = processed_ready and exists
    size_mb = os.path.getsize(path) / 1024 / 1024 if exists else 0
    print(name, exists, f"{size_mb:.2f} MB")

print("Processed ready:", processed_ready)
```

Neu `Processed ready: True`, co the bo qua buoc preprocess va chuyen den buoc 11.

Neu `False`, chay buoc 10.

## 10. Chay preprocessing

Chi chay khi processed data chua co, sai shape, hoac source preprocessing da thay doi.

Cell 13:

```python
%cd /content/ai-module

!python scripts/preprocess.py \
  --data-dir "{DATASET}" \
  --output-dir "{PROCESSED}"
```

Preprocess se tao:

```text
Drive/GSU26SE55/processed/train.pt
Drive/GSU26SE55/processed/val.pt
Drive/GSU26SE55/processed/test.pt
Drive/GSU26SE55/weights/scaler.pkl
Drive/GSU26SE55/weights/feature_scaler.pkl
```

## 11. Kiem tra shape bat buoc

Cell 14:

```python
import torch

expected = {
    "train.pt": ((504, 4096, 6), (504, 54), (504,)),
    "val.pt": ((92, 4096, 6), (92, 54), (92,)),
    "test.pt": ((40, 4096, 6), (40, 54), (40,)),
}

for name, expected_shapes in expected.items():
    data = torch.load(f"{PROCESSED}/{name}", weights_only=False)
    actual = (
        tuple(data["X"].shape),
        tuple(data["X_feat"].shape),
        tuple(data["y"].shape),
    )
    print(name, actual)
    assert actual == expected_shapes, f"{name}: expected {expected_shapes}, got {actual}"

print("Processed shapes are correct")
```

Shape dung:

```text
train.pt: X (504, 4096, 6), X_feat (504, 54), y (504,)
val.pt:   X (92, 4096, 6),  X_feat (92, 54),  y (92,)
test.pt:  X (40, 4096, 6),  X_feat (40, 54),  y (40,)
```

Neu assertion fail, xoa processed data cu tren Drive va preprocess lai bang source moi.

## 12. Smoke test tren GPU

Smoke test xac nhan:

- model doc du 4096 timestep;
- forward/backward hoat dong;
- CUDA va AMP hoat dong;
- khong OOM;
- checkpoint ghi duoc vao Drive.

Cell 15:

```python
%cd /content/ai-module

!python scripts/train.py \
  --data-dir "{PROCESSED}" \
  --epochs 1 \
  --batch-size 1 \
  --accumulation-steps 2 \
  --checkpoint-dir "{CHECKPOINTS}/smoke" \
  --log-dir "{LOGS}/smoke" \
  --max-train-batches 2 \
  --max-eval-batches 2 \
  --skip-final-artifacts
```

Can thay:

```text
Device: cuda
Train: 504 | Val: 92 | Test: 40
batch=1
amp=True
Skipping final model/IsolationForest artifacts
```

MAE/RMSE cua smoke test co the 40-80%. Day khong phai loi vi model chi hoc 2 samples.

Neu log la:

```text
Device: cpu
amp=False
```

thi runtime khong dung GPU. Smoke test CPU van duoc, nhung khong nen full train.

## 13. Full training

Full training khong dung:

```text
--max-train-batches
--max-eval-batches
--skip-final-artifacts
```

Cell 16:

```python
%cd /content/ai-module

!python scripts/train.py \
  --data-dir "{PROCESSED}" \
  --epochs 100 \
  --batch-size 1 \
  --accumulation-steps 8 \
  --checkpoint-dir "{CHECKPOINTS}" \
  --log-dir "{LOGS}"
```

Config:

```text
sequence length = 4096
physical batch = 1
effective batch = 8
AMP = FP16 on CUDA
early stopping patience = 15
checkpoint after every epoch
```

Training co the dung truoc epoch 100 do early stopping.

Metric 10 epoch dau co the cao. Danh gia xu huong sau 20-40 epoch:

- Train loss giam, Val MAE giam: tiep tuc train.
- Train loss giam, Val MAE khong giam: domain shift/generalization.
- Train loss khong giam: kiem tra data, scaler, learning rate va artifacts.

## 14. Kiem tra checkpoint trong luc train

Khong can dung cell full training. Checkpoint duoc ghi vao:

```text
MyDrive/GSU26SE55/checkpoints/latest.pt
```

Sau khi training dung hoac runtime bi ngat, kiem tra:

```python
!ls -lh "{CHECKPOINTS}/latest.pt"
```

## 15. Resume sau khi Colab bi ngat

Sau khi runtime bi ngat:

1. Bat GPU.
2. Mount Drive.
3. Clone repo.
4. Cai dependencies.
5. Chay lai Cell 9 de khai bao duong dan.
6. Chay lai Cell 11 de link weights.
7. Kiem tra `latest.pt`.
8. Chay resume.

Cell resume:

```python
%cd /content/ai-module

!python scripts/train.py \
  --data-dir "{PROCESSED}" \
  --epochs 100 \
  --batch-size 1 \
  --accumulation-steps 8 \
  --checkpoint-dir "{CHECKPOINTS}" \
  --resume "{CHECKPOINTS}/latest.pt" \
  --log-dir "{LOGS}"
```

Log can co:

```text
Resumed from .../latest.pt at epoch N
```

`--epochs 100` la epoch dich tong, khong phai train them 100 epoch. Neu checkpoint o epoch 35, script tiep tuc tu epoch 36 den toi da 100.

Khong dung `--resume` neu checkpoint khong ton tai.

## 16. Xem log

Tim log:

```python
!find "{LOGS}" -name "train_*.log" -type f | sort
```

Xem log moi nhat:

```python
import glob
import os

log_files = glob.glob(f"{LOGS}/**/train_*.log", recursive=True)

if log_files:
    latest_log = max(log_files, key=os.path.getmtime)
    print(latest_log)
else:
    latest_log = None
    print("No training log found")
```

```python
if latest_log:
    !tail -n 100 "{latest_log}"
```

## 17. Kiem tra artifacts sau full training

Cell:

```python
import os

required_artifacts = [
    "scaler.pkl",
    "feature_scaler.pkl",
    "soh_mamba_v1.2.pth",
    "isolation_forest_v1.2.pkl",
]

for name in required_artifacts:
    path = os.path.join(WEIGHTS, name)
    exists = os.path.isfile(path)
    size_mb = os.path.getsize(path) / 1024 / 1024 if exists else 0
    print(name, exists, f"{size_mb:.2f} MB")
```

Tat ca phai la `True`.

## 18. Loi thuong gap

### `requirements.txt` not found

```python
%cd /content/ai-module
!ls
%pip install -q -r requirements.txt
```

### `numpy.dtype size changed`

Nguyen nhan: kernel dang giu NumPy version cu trong memory trong khi pandas/scipy da duoc pip thay doi.

Sua:

```python
%pip install --force-reinstall --no-cache-dir \
  numpy==1.26.4 \
  pandas==2.2.2 \
  scipy==1.13.1 \
  scikit-learn==1.5.0
```

Sau do bat buoc restart:

```python
import os
import signal

os.kill(os.getpid(), signal.SIGKILL)
```

### `metadata.csv` not found

```python
!find /content/drive/MyDrive -name metadata.csv
```

Gan `DATASET` bang thu muc cha cua file tim duoc.

### `getcwd: cannot access parent directories`

```python
%cd /content
```

Sau do clone lai. Khong xoa repo khi current directory dang nam trong repo.

### `Invalid username or token`

- Token phai co quyen doc private repo.
- Classic token can scope `repo`.
- Neu organization bat SSO, authorize token cho organization.
- Khong ghi token truc tiep vao notebook.

### `CUDA out of memory`

Dung:

```text
--batch-size 1
--accumulation-steps 8
```

Sau do:

1. Restart session.
2. Chay lai cac cell can thiet.
3. Khong chay cac model/tensor GPU khac song song.
4. Khong tang batch size.

### CUDA unavailable

Neu Colab khong cap GPU:

- chay CPU smoke test voi `--no-amp`;
- khong nen full train;
- doi quota reset hoac dung runtime GPU khac.

CPU smoke:

```python
%cd /content/ai-module

!python scripts/train.py \
  --data-dir "{PROCESSED}" \
  --epochs 1 \
  --batch-size 1 \
  --accumulation-steps 2 \
  --checkpoint-dir "{CHECKPOINTS}/cpu-smoke" \
  --log-dir "{LOGS}/cpu-smoke" \
  --max-train-batches 2 \
  --max-eval-batches 2 \
  --skip-final-artifacts \
  --no-amp
```

## 19. Khong nen lam

- Khong full train bang smoke flags.
- Khong danh gia model bang smoke metric.
- Khong tang batch size khi sequence la 4096.
- Khong xoa `/content/ai-module` khi dang `%cd` trong folder do.
- Khong preprocess lai moi lan neu processed data tren Drive da dung shape.
- Khong luu checkpoint chi trong `/content`; hay luu tren Drive.
- Khong commit raw dataset, processed tensors hoac training checkpoint.

## 20. Full workflow ngan gon

Dung khi repo da clone, Drive da mount va processed data da co:

```python
%cd /content/ai-module
%pip install -q -r requirements.txt
```

```python
import os

DRIVE_ROOT = "/content/drive/MyDrive/GSU26SE55"
PROCESSED = f"{DRIVE_ROOT}/processed"
CHECKPOINTS = f"{DRIVE_ROOT}/checkpoints"
LOGS = f"{DRIVE_ROOT}/logs"

assert os.path.isfile(f"{PROCESSED}/train.pt")
assert os.path.isfile(f"{PROCESSED}/val.pt")
assert os.path.isfile(f"{PROCESSED}/test.pt")
```

```python
%cd /content/ai-module

!python scripts/train.py \
  --data-dir "{PROCESSED}" \
  --epochs 100 \
  --batch-size 1 \
  --accumulation-steps 8 \
  --checkpoint-dir "{CHECKPOINTS}" \
  --log-dir "{LOGS}"
```
