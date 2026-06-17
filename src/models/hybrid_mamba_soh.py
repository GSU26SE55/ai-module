"""
HybridMambaSOH — paper-style architecture (Hybrid Mamba-CNN + Physics Stats Head)
ported to battery SOH regression, in pure-PyTorch, for a FAIR comparison with
MambaSOHPredictor ("Mamba A").

Components borrowed from the paper (sunbv56/mamba-forecast-ad):
  - Series Decomposition (moving-average trend / seasonal split)
  - Seasonal branch: Conv1d patch embedding -> local CNN noise barrier -> Mamba
  - Trend branch: linear projection
  - Physics stats fusion (the 54-dim spectral+kurtosis vector, like the 8-dim head)
  - Learnable sigmoid mix of the two branches

Adapted: the paper forecasts a horizon (B,C,H); here we output ONE SOH value (B,).
Same (x, x_feat) input interface as MambaSOHPredictor -> drop-in for comparison.
Reuses the project's pure-PyTorch MambaBlock (Windows-native, no CUDA dep).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

from src.models.soh_predictor import MambaBlock


class SeriesDecomp(nn.Module):
    """Moving-average trend/seasonal decomposition (paper's Series Decomposition)."""

    def __init__(self, kernel_size: int = 5):
        super().__init__()
        self.pad = kernel_size // 2
        self.avg = nn.AvgPool1d(kernel_size, stride=1, padding=self.pad)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # x: (B, L, C)
        xt = x.transpose(1, 2)                      # (B, C, L)
        trend = self.avg(xt).transpose(1, 2)        # (B, L, C)
        trend = trend[:, : x.size(1), :]            # guard odd lengths
        seasonal = x - trend
        return trend, seasonal


class HybridMambaSOH(nn.Module):
    """
    Input:  x      (batch, L, input_features)  — raw window (L=30)
            x_feat (batch, feat_dim)            — 54-dim spectral+kurtosis stats
    Output: (batch,) — SOH%

    Decomp -> [seasonal: patch+CNN+Mamba] + [trend: linear] + stats fusion -> SOH.
    """

    def __init__(
        self,
        input_features: int = 6,
        d_model: int = 64,
        d_state: int = 16,
        n_layers: int = 2,
        feat_dim: int = 54,
        patch_size: int = 8,
        patch_stride: int = 4,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.decomp = SeriesDecomp(kernel_size=5)

        # Seasonal branch: Conv1d patch embed -> depthwise CNN noise barrier -> Mamba
        self.patch = nn.Conv1d(input_features, d_model, kernel_size=patch_size, stride=patch_stride)
        self.cnn = nn.Conv1d(d_model, d_model, kernel_size=3, padding=1, groups=d_model)
        self.mamba_layers = nn.ModuleList(
            [MambaBlock(d_model=d_model, d_state=d_state) for _ in range(n_layers)]
        )
        self.norm = nn.LayerNorm(d_model)

        # Trend branch: per-step linear projection (pooled)
        self.trend_proj = nn.Linear(input_features, d_model)

        # Physics stats fusion (paper's stats head idea, 54-dim here)
        self.stats_norm = nn.BatchNorm1d(feat_dim)
        self.stats_proj = nn.Linear(feat_dim, d_model)

        # Learnable mix + regression head
        self.mix = nn.Parameter(torch.tensor(0.5))
        self.dropout = nn.Dropout(dropout)
        self.fc1 = nn.Linear(d_model, 32)
        self.fc2 = nn.Linear(32, 1)

    def forward(self, x: torch.Tensor, x_feat: torch.Tensor) -> torch.Tensor:
        trend, seasonal = self.decomp(x)

        # Seasonal: patch -> CNN -> Mamba -> avg-pool over patches
        s = self.patch(seasonal.transpose(1, 2))        # (B, d_model, P)
        s = F.silu(self.cnn(s)).transpose(1, 2)         # (B, P, d_model)
        for layer in self.mamba_layers:
            s = layer(s)
        s = self.norm(s).mean(dim=1)                    # (B, d_model)

        # Trend: linear then average over time
        t = self.trend_proj(trend).mean(dim=1)          # (B, d_model)

        # Stats fusion
        st = self.stats_proj(self.stats_norm(x_feat))   # (B, d_model)

        a = torch.sigmoid(self.mix)
        h = a * s + (1.0 - a) * t + st                  # (B, d_model)
        h = self.dropout(F.gelu(self.fc1(h)))
        return self.fc2(h).squeeze(-1)                  # (batch,)
