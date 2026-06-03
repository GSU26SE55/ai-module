import torch
import torch.nn as nn
import torch.nn.functional as F


class MambaBlock(nn.Module):
    """
    Pure-PyTorch Mamba block.
    No mamba-ssm CUDA dependency — runs on Windows 11 native.

    d_inner = expand * d_model = 128
    d_state = 16  (SSM state dimension)
    d_conv  = 4   (causal depthwise conv kernel)
    """

    def __init__(self, d_model: int, d_state: int = 16, d_conv: int = 4, expand: int = 2):
        super().__init__()
        self.d_state = d_state
        self.d_inner = expand * d_model

        self.norm = nn.LayerNorm(d_model)
        self.in_proj = nn.Linear(d_model, self.d_inner * 2, bias=False)

        # Causal depthwise conv
        self.conv1d = nn.Conv1d(
            self.d_inner, self.d_inner,
            kernel_size=d_conv, groups=self.d_inner,
            padding=d_conv - 1, bias=True,
        )

        # SSM projections: dt (rank=1), B, C
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

        xz = self.in_proj(x)                         # (B, L, 2*d_inner)
        x_b, z = xz.chunk(2, dim=-1)                 # each (B, L, d_inner)

        # Causal depthwise conv — truncate to L (removes future padding)
        x_b = self.conv1d(x_b.transpose(1, 2))[..., :L].transpose(1, 2)
        x_b = F.silu(x_b)                            # (B, L, d_inner)

        y = self._selective_scan(x_b)                # (B, L, d_inner)
        y = y * F.silu(z)
        return self.out_proj(y) + residual

    def _selective_scan(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, L, d_inner)
        B, L, d_inner = x.shape

        x_dbl = self.x_proj(x)                       # (B, L, d_state*2 + 1)
        dt_raw, B_proj, C_proj = x_dbl.split(
            [1, self.d_state, self.d_state], dim=-1
        )

        dt = F.softplus(self.dt_proj(dt_raw))         # (B, L, d_inner)
        A = -torch.exp(self.A_log.float())            # (d_inner, d_state) — negative

        # ZOH discretization
        dA = torch.exp(
            dt.unsqueeze(-1) * A.unsqueeze(0).unsqueeze(0)
        )                                             # (B, L, d_inner, d_state)
        dB = dt.unsqueeze(-1) * B_proj.unsqueeze(2)  # (B, L, d_inner, d_state)

        # Sequential scan — efficient for L=30
        h = torch.zeros(B, d_inner, self.d_state, device=x.device, dtype=x.dtype)
        ys = []
        for t in range(L):
            h = dA[:, t] * h + dB[:, t] * x[:, t].unsqueeze(-1)
            y_t = (h * C_proj[:, t].unsqueeze(1)).sum(-1)  # (B, d_inner)
            ys.append(y_t)

        y = torch.stack(ys, dim=1)                   # (B, L, d_inner)
        return y + x * self.D


class MambaSOHPredictor(nn.Module):
    """
    Input:  (batch, 30, input_features)  — 30 timestep sensor window
    Output: (batch,)        — SOH% in range [0, 100]

    Architecture: Linear → 2x MambaBlock → LayerNorm → last token → FC head
    Pure PyTorch, no CUDA kernel — Windows-compatible.
    """

    def __init__(
        self,
        input_features: int = 3,
        d_model: int = 64,
        n_layers: int = 2,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.input_features = input_features
        self.input_proj = nn.Linear(input_features, d_model)
        self.mamba_layers = nn.ModuleList(
            [MambaBlock(d_model=d_model) for _ in range(n_layers)]
        )
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)
        self.fc1 = nn.Linear(d_model, 32)
        self.fc2 = nn.Linear(32, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, 30, input_features)
        x = self.input_proj(x)           # (batch, 30, d_model)
        for layer in self.mamba_layers:
            x = layer(x)
        x = self.norm(x)
        x = x[:, -1, :]                  # last timestep: (batch, d_model)
        x = self.dropout(F.gelu(self.fc1(x)))
        return self.fc2(x).squeeze(-1)   # (batch,)
