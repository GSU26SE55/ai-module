"""
RUL predictor (GH-13): cycle-level Mamba for Remaining Useful Life estimation.

Re-frames the long-context problem onto the CYCLE axis. Each input token is one
discharge cycle represented by its 54-dim spectral+kurtosis feature vector, so a
sequence of RUL_LOOKBACK cycles carries the genuine long-range degradation
trajectory (unlike raw-timestep L=4096, which only spans ~13 cycles and dilutes
the signal). Output = normalised remaining cycles to End-of-Life.

Reuses the pure-PyTorch MambaBlock from soh_predictor — no new SSM code, no CUDA
dependency. The window=30 SOH production model stays untouched.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

from src.models.soh_predictor import MambaBlock


class RULPredictor(nn.Module):
    """
    Input:  x (batch, L_cycles, feat_dim) — sequence of per-cycle feature vectors
    Output: (batch,) — normalised RUL (multiply by RUL_SCALE for cycles)

    Architecture:
      Linear(feat_dim→d_model) → MambaBlock×n_layers → LayerNorm
        → pooling (last|attention) → Linear(d_model→32) → GELU+Dropout → Linear(32→1)

    use_obs_loss: reserved hook for the observability-index auxiliary loss (GH-14).
      When False (default) the forward pass is a plain RUL regressor; the flag is
      stored so a later issue can add the auxiliary term without changing callers.
    """

    def __init__(
        self,
        feat_dim: int = 54,
        d_model: int = 64,
        d_state: int = 16,
        n_layers: int = 2,
        dropout: float = 0.2,
        pooling: str = "last",
        use_obs_loss: bool = False,
    ):
        super().__init__()
        if pooling not in ("last", "attention"):
            raise ValueError(f"pooling must be 'last' or 'attention', got '{pooling}'")
        self.feat_dim = feat_dim
        self.pooling = pooling
        self.use_obs_loss = use_obs_loss  # GH-14 hook — no-op in baseline

        self.input_proj = nn.Linear(feat_dim, d_model)
        self.mamba_layers = nn.ModuleList(
            [MambaBlock(d_model=d_model, d_state=d_state) for _ in range(n_layers)]
        )
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)
        if pooling == "attention":
            self.attn_score = nn.Linear(d_model, 1)
        self.fc1 = nn.Linear(d_model, 32)
        self.fc2 = nn.Linear(32, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, L_cycles, feat_dim)
        h = self.input_proj(x)                       # (batch, L, d_model)
        for layer in self.mamba_layers:
            h = layer(h)
        h = self.norm(h)
        if self.pooling == "attention":
            w = torch.softmax(self.attn_score(h), dim=1)  # (batch, L, 1) over cycles
            h = (w * h).sum(dim=1)                          # (batch, d_model)
        else:  # "last" — most-recent cycle
            h = h[:, -1, :]                                 # (batch, d_model)

        h = self.dropout(F.gelu(self.fc1(h)))
        return self.fc2(h).squeeze(-1)                      # (batch,)
