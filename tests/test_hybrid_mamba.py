"""Tests for HybridMambaSOH (paper-style Mamba B) — GH-13 comparison."""

import torch

from src.models.hybrid_mamba_soh import HybridMambaSOH, SeriesDecomp


def test_series_decomp_reconstructs():
    d = SeriesDecomp(kernel_size=5)
    x = torch.randn(2, 30, 6)
    trend, seasonal = d(x)
    assert trend.shape == x.shape and seasonal.shape == x.shape
    # trend + seasonal == x
    assert torch.allclose(trend + seasonal, x, atol=1e-5)


def test_hybrid_output_shape():
    m = HybridMambaSOH(input_features=6, feat_dim=54, d_model=64, d_state=16)
    out = m(torch.randn(4, 30, 6), torch.randn(4, 54))
    assert out.shape == (4,)


def test_hybrid_param_parity_with_current():
    from src.models.soh_predictor import MambaSOHPredictor
    a = sum(p.numel() for p in MambaSOHPredictor(input_features=6, feat_dim=54).parameters())
    b = sum(p.numel() for p in HybridMambaSOH(input_features=6, feat_dim=54).parameters())
    # within 10% — fair architecture comparison requires parameter parity
    assert abs(b - a) / a < 0.10


def test_hybrid_grad_flows():
    m = HybridMambaSOH(input_features=6, feat_dim=54)
    m(torch.randn(3, 30, 6), torch.randn(3, 54)).sum().backward()
    assert m.fc2.weight.grad is not None
