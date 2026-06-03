# Plan — GH-?: Mamba SOH Training Pipeline (Replace CNN-LSTM)

## Metadata
- **Status:** DRAFT — tạo GitHub Issue rồi đổi tên thư mục `GH-DRAFT` → `GH-{number}`
- **Role:** AI
- **Ngày:** 2026-06-01
- **Sprint:** 3–4

## Mục tiêu

Thay toàn bộ CNN-LSTM bằng **Mamba architecture (pure PyTorch, không dùng `mamba-ssm` CUDA library)**
để compatible với Windows 11 native. Train thật trên NASA Ames dataset (B0005, B0006, B0007, B0018)
và commit real artifacts thay thế dummy.

**Giữ nguyên không đổi:** Isolation Forest, `scripts/preprocess.py`, FastAPI routers/schemas,
`src/services/inference.py` interface, test coverage target ≥ 85%.

---

## Files

| File | Action | Ghi chú |
|------|--------|---------|
| `src/models/soh_predictor.py` | **modify** | Thay `SOHPredictor` (CNN-LSTM) → `MambaSOHPredictor` + `MambaBlock` |
| `src/core/config.py` | **modify** | Rename `LSTM_PATH` → `MAMBA_PATH`; filename `soh_lstm_v1.0.pth` → `soh_mamba_v1.0.pth` |
| `src/core/model_loader.py` | **modify** | Import `MambaSOHPredictor`, load từ `MAMBA_PATH` |
| `scripts/train.py` | **modify** | Import + train `MambaSOHPredictor`, save to `MAMBA_PATH` |
| `scripts/create_dummy_artifacts.py` | **modify** | Dùng `MambaSOHPredictor` để gen dummy |
| `tests/test_models.py` | **modify** | Test `MambaSOHPredictor` forward pass shape |
| `models/weights/soh_mamba_v1.0.pth` | **create** | Trained Mamba weights — commit |
| `models/weights/scaler.pkl` | **update** | Real fitted MinMaxScaler — commit |
| `models/weights/isolation_forest_v1.0.pkl` | **update** | Real fitted IF — commit |
| `CLAUDE.md` | **modify** | Update architecture spec CNN-LSTM → Mamba |
| `scripts/preprocess.py` | no change | Đã implement đầy đủ ở GH-2 |
| `src/services/inference.py` | no change | Interface không đổi |
| `src/routers/` | no change | Không đổi |

---

## Architecture — MambaSOHPredictor

```
Input: (batch, 30, 3)
  → Linear(3 → 64)            # input projection
  → MambaBlock(d_model=64) #1 # selective SSM layer 1
  → MambaBlock(d_model=64) #2 # selective SSM layer 2
  → LayerNorm(64)
  → x[:, -1, :]               # last timestep hidden state
  → Linear(64 → 32) + GELU + Dropout(0.2)
  → Linear(32 → 1)
Output: (batch,)               # SOH % raw (chia 100 khi loss, nhân 100 khi output)
```

### MambaBlock internals

```
input: (B, L, d_model)
  → LayerNorm                  # pre-norm
  → in_proj: Linear(d_model → 2*d_inner)  # split → (x_branch, z_gate)
  → x_branch: depthwise Conv1d(k=4, causal) → SiLU
  → x_branch: selective SSM scan
  → output = ssm_out ⊙ SiLU(z_gate)
  → out_proj: Linear(d_inner → d_model)
  → residual +
output: (B, L, d_model)

Hyperparameters: d_inner = 2*d_model = 128, d_state = 16, d_conv = 4
```

### Implementation đầy đủ — `src/models/soh_predictor.py`

```python
import torch
import torch.nn as nn
import torch.nn.functional as F


class MambaBlock(nn.Module):
    """
    Pure-PyTorch Mamba block.
    No mamba-ssm CUDA dependency — runs on Windows 11 native.
    """

    def __init__(self, d_model: int, d_state: int = 16, d_conv: int = 4, expand: int = 2):
        super().__init__()
        self.d_state = d_state
        self.d_inner = expand * d_model

        self.norm = nn.LayerNorm(d_model)
        self.in_proj = nn.Linear(d_model, self.d_inner * 2, bias=False)

        self.conv1d = nn.Conv1d(
            self.d_inner, self.d_inner,
            kernel_size=d_conv, groups=self.d_inner,
            padding=d_conv - 1, bias=True,
        )

        # SSM: dt (rank=1), B, C projections
        self.x_proj = nn.Linear(self.d_inner, d_state * 2 + 1, bias=False)
        self.dt_proj = nn.Linear(1, self.d_inner, bias=True)

        # A — log-initialized, learnable; shape (d_inner, d_state)
        A = torch.arange(1, d_state + 1, dtype=torch.float32)
        self.A_log = nn.Parameter(
            A.log().unsqueeze(0).expand(self.d_inner, -1).clone()
        )
        self.D = nn.Parameter(torch.ones(self.d_inner))

        self.out_proj = nn.Linear(self.d_inner, d_model, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, L, d_model)
        residual = x
        x = self.norm(x)
        B, L, _ = x.shape

        xz = self.in_proj(x)                        # (B, L, 2*d_inner)
        x_b, z = xz.chunk(2, dim=-1)                # each (B, L, d_inner)

        # Causal depthwise conv — truncate to L (removes future padding)
        x_b = self.conv1d(x_b.transpose(1, 2))[..., :L].transpose(1, 2)
        x_b = F.silu(x_b)                           # (B, L, d_inner)

        y = self._selective_scan(x_b)               # (B, L, d_inner)
        y = y * F.silu(z)
        return self.out_proj(y) + residual

    def _selective_scan(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, L, d_inner)
        B, L, d_inner = x.shape

        x_dbl = self.x_proj(x)                      # (B, L, d_state*2 + 1)
        dt_raw, B_proj, C_proj = x_dbl.split(
            [1, self.d_state, self.d_state], dim=-1
        )

        dt = F.softplus(self.dt_proj(dt_raw))        # (B, L, d_inner)
        A = -torch.exp(self.A_log.float())           # (d_inner, d_state)

        # ZOH discretization
        dA = torch.exp(
            dt.unsqueeze(-1) * A.unsqueeze(0).unsqueeze(0)
        )                                            # (B, L, d_inner, d_state)
        dB = dt.unsqueeze(-1) * B_proj.unsqueeze(2) # (B, L, d_inner, d_state)

        # Sequential scan — fast for L=30
        h = torch.zeros(B, d_inner, self.d_state, device=x.device, dtype=x.dtype)
        ys = []
        for t in range(L):
            h = dA[:, t] * h + dB[:, t] * x[:, t].unsqueeze(-1)
            y_t = (h * C_proj[:, t].unsqueeze(1)).sum(-1)  # (B, d_inner)
            ys.append(y_t)

        y = torch.stack(ys, dim=1)                  # (B, L, d_inner)
        return y + x * self.D


class MambaSOHPredictor(nn.Module):
    """
    Input:  (batch, 30, 3)  — 30 timestep, 3 features [voltage, current, temp]
    Output: (batch,)        — SOH% in range [0, 100]

    Architecture: Linear → 2x MambaBlock → LayerNorm → last token → FC head
    Pure PyTorch, no CUDA kernel — Windows-compatible.
    """

    def __init__(self, d_model: int = 64, n_layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.input_proj = nn.Linear(3, d_model)
        self.mamba_layers = nn.ModuleList(
            [MambaBlock(d_model=d_model) for _ in range(n_layers)]
        )
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)
        self.fc1 = nn.Linear(d_model, 32)
        self.fc2 = nn.Linear(32, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, 30, 3)
        x = self.input_proj(x)          # (batch, 30, d_model)
        for layer in self.mamba_layers:
            x = layer(x)
        x = self.norm(x)
        x = x[:, -1, :]                  # last timestep: (batch, d_model)
        x = self.dropout(F.gelu(self.fc1(x)))
        return self.fc2(x).squeeze(-1)   # (batch,)
```

---

## Approach chi tiết

### Bước 1 — Thay model (`src/models/soh_predictor.py`)
Copy toàn bộ implementation ở trên vào file. Xóa class `SOHPredictor` cũ.

### Bước 2 — Update config (`src/core/config.py`)
```python
# Đổi 2 dòng:
MAMBA_PATH = os.path.join(WEIGHTS_DIR, f"soh_mamba_v{MODEL_VERSION}.pth")
# Xóa dòng: LSTM_PATH = ...
```

### Bước 3 — Update model_loader (`src/core/model_loader.py`)
```python
# Đổi import:
from src.models.soh_predictor import MambaSOHPredictor

# Đổi trong load_models():
#   - (LSTM_PATH, "LSTM model")  →  (MAMBA_PATH, "Mamba model")
#   - torch.load(LSTM_PATH, ...)  →  torch.load(MAMBA_PATH, ...)
#   - soh_model = SOHPredictor()  →  soh_model = MambaSOHPredictor()
```

### Bước 4 — Update train.py (`scripts/train.py`)
```python
# Đổi import:
from src.models.soh_predictor import MambaSOHPredictor
from src.core.config import MAMBA_PATH  # thay LSTM_PATH

# Trong train():
#   - model = SOHPredictor()  →  model = MambaSOHPredictor()
#   - torch.save(..., LSTM_PATH)  →  torch.save(..., MAMBA_PATH)
#   - print label "LSTM" → "Mamba"
```

### Bước 5 — Update create_dummy_artifacts.py
```python
# Đổi import + MambaSOHPredictor() thay SOHPredictor()
# Đổi filename output: soh_mamba_v1.0.pth
```

### Bước 6 — Update tests/test_models.py
```python
# Đổi import MambaSOHPredictor
# Test vẫn giữ: forward pass (1, 30, 3) → output shape (1,)
```

### Bước 7 — Download NASA data + Preprocess
```bash
# Đặt B0005.mat, B0006.mat, B0007.mat, B0018.mat vào data/raw/nasa/
python scripts/preprocess.py --data-dir data/raw/nasa --output-dir data/processed
# Output: data/processed/{train,val,test}.pt + models/weights/scaler.pkl
```

### Bước 8 — Train thật
```bash
python scripts/train.py --data-dir data/processed --epochs 50
# Kỳ vọng: early stopping ~30–40 epoch
# Target: MAE < 2% SOH, RMSE < 3% SOH
```
Nếu chưa đạt target sau 50 epoch: thử `--epochs 100` hoặc tăng `d_model=128`.

### Bước 9 — Commit 3 artifacts
```bash
git add models/weights/scaler.pkl models/weights/soh_mamba_v1.0.pth models/weights/isolation_forest_v1.0.pkl
git commit -m "feat: add trained Mamba + IF artifacts v1.0"
```

### Bước 10 — Benchmark + Test
```bash
pytest tests/ -v --cov=src
# test_latency phải PASS (< 100ms với sequential scan L=30)
```

### Bước 11 — Update CLAUDE.md
Thay block "Architecture" trong CLAUDE.md (root) từ CNN-LSTM sang Mamba spec.

---

## Edge Cases
- `readings` sai shape → HTTP 422 (không thay đổi, inference.py xử lý trước khi vào model)
- Latency sequential scan với L=30: dự kiến 5–20ms CPU (an toàn so với 100ms limit)
- Nếu `scaler.pkl` đã bị fit bởi dummy run cũ → xóa và refit bằng `preprocess.py` với data thật
- Model checkpoint cũ `soh_lstm_v1.0.pth` — giữ lại trong git, không xóa (backward ref)

---

## Success Criteria

| Tiêu chí | Cách verify |
|----------|------------|
| Forward pass đúng shape | `pytest tests/test_models.py` PASS |
| App boot với artifact thật | `uvicorn main:app` không exception |
| `POST /predict` trả đúng schema | curl với input (30,3) → `soh_percent`, `classification`, `confidence`, `inference_ms` |
| MAE < 2% SOH | In ra sau `python scripts/train.py` (eval trên test set) |
| RMSE < 3% SOH | In ra sau `python scripts/train.py` |
| Latency < 100ms | `test_inference.py::test_latency` PASS |
| Coverage ≥ 85% | `pytest --cov=src` |

---

## Steps checklist

- [ ] Bước 1: Thay `src/models/soh_predictor.py` → `MambaBlock` + `MambaSOHPredictor`
- [ ] Bước 2: Update `src/core/config.py` → `MAMBA_PATH`, filename `soh_mamba_v1.0.pth`
- [ ] Bước 3: Update `src/core/model_loader.py` → import + load `MambaSOHPredictor`
- [ ] Bước 4: Update `scripts/train.py` → import + train `MambaSOHPredictor`
- [ ] Bước 5: Update `scripts/create_dummy_artifacts.py` → `MambaSOHPredictor`
- [ ] Bước 6: Update `tests/test_models.py` → test `MambaSOHPredictor` forward pass
- [ ] Bước 7: Download NASA `.mat` files → chạy `python scripts/preprocess.py`
- [ ] Bước 8: Chạy `python scripts/train.py --epochs 50` → verify MAE < 2%
- [ ] Bước 9: Commit 3 artifacts thật vào Git
- [ ] Bước 10: `pytest tests/ -v --cov=src` → PASS ≥ 85%
- [ ] Bước 11: Update `CLAUDE.md` architecture spec
