"""
Benchmark Mamba inference latency across different sequence lengths.
Chung minh Mamba xu ly duoc 1000+ token trong SLA 100ms.

Usage:
    python scripts/benchmark_tokens.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import torch
from src.models.soh_predictor import MambaSOHPredictor
from src.core.config import INPUT_FEATURES, SPECTRAL_FEAT_DIM, D_MODEL, D_STATE

model = MambaSOHPredictor(
    input_features=INPUT_FEATURES,
    feat_dim=SPECTRAL_FEAT_DIM,
    d_model=D_MODEL,
    d_state=D_STATE,
)
model.eval()

print(f"Model: d_model={D_MODEL}, d_state={D_STATE}, params={sum(p.numel() for p in model.parameters()):,}")
print(f"Train window size: {30} tokens")
print()
print(f"{'L':>6}  {'Latency':>10}  {'SLA':>8}  Tuong duong")
print("-" * 55)

for L, desc in [
    (30,    "train size (30 steps)"),
    (100,   "~1/3 chu ky"),
    (256,   "~1 full cycle"),
    (512,   "~1.8 cycles"),
    (1000,  "~3-4 cycles"),
    (2000,  "~7 cycles"),
    (5000,  "~17 cycles"),
]:
    x = torch.randn(1, L, INPUT_FEATURES)
    f = torch.randn(1, SPECTRAL_FEAT_DIM)

    # warmup
    for _ in range(5):
        with torch.no_grad():
            model(x, f)

    # benchmark
    t0 = time.perf_counter()
    for _ in range(30):
        with torch.no_grad():
            model(x, f)
    ms = (time.perf_counter() - t0) / 30 * 1000

    sla = "OK  <100ms" if ms < 100 else "BREACH"
    print(f"{L:>6}  {ms:>8.1f}ms  {sla:>10}  {desc}")
