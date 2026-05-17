# Data — AI Module

## Cấu trúc thư mục

```
data/
├── raw/          ← KHÔNG commit (gitignored) — đặt NASA .mat files vào đây
│   └── nasa/     ← B0005.mat, B0006.mat, B0007.mat, B0018.mat
└── processed/    ← KHÔNG commit (gitignored) — output của scripts/preprocess.py
    ├── train.pt
    ├── val.pt
    └── test.pt
```

## Dataset: NASA Ames Battery Aging

| Field | Value |
|-------|-------|
| Source | https://www.kaggle.com/datasets/patrickfleith/nasa-battery-dataset |
| Format | `.mat` (MATLAB) |
| Cells dùng | B0005, B0006, B0007, B0018 |
| Version | — (ghi lại sau khi download) |
| Ngày download | — |

## Setup local

```bash
# 1. Download từ Kaggle, đặt vào data/raw/nasa/
mkdir -p data/raw/nasa
# copy B0005.mat B0006.mat B0007.mat B0018.mat vào data/raw/nasa/

# 2. Chạy preprocessing
python scripts/preprocess.py --data-dir data/raw/nasa --output-dir data/processed

# 3. Train
python scripts/train.py --data-dir data/processed --epochs 50
```

## Quy tắc
- KHÔNG commit raw data hay processed data
- Chỉ commit `models/weights/*.pkl` và `models/weights/*.pth` sau khi train
- Split cố định theo battery ID — không thay đổi
