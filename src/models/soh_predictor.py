import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint as grad_checkpoint


@torch.jit.script
def _sequential_scan_jit(dA: torch.Tensor, dBx: torch.Tensor) -> torch.Tensor:
    """
    Sequential SSM scan compiled to TorchScript — runs at C++ speed.
    h_t = dA_t ⊙ h_{t-1} + dBx_t,  h_{-1} = 0
    Avoids Python interpreter overhead: ~10-30× faster than plain Python loop.
    """
    B, L, D, N = dA.shape
    out = torch.empty_like(dBx)
    h = torch.zeros(B, D, N, device=dA.device, dtype=dA.dtype)
    for t in range(L):
        h = dA[:, t] * h + dBx[:, t]
        out[:, t] = h
    return out


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

    def _selective_scan_chunk(
        self,
        x: torch.Tensor,
        h_carry: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Run one scan chunk and return its output plus final SSM state."""
        x_dbl = self.x_proj(x)
        dt_raw, B_proj, C_proj = x_dbl.split(
            [1, self.d_state, self.d_state], dim=-1
        )

        dt = F.softplus(self.dt_proj(dt_raw))
        A = -torch.exp(self.A_log.float())

        # Only materialize four-dimensional SSM tensors for this chunk.
        dA = torch.exp(dt.unsqueeze(-1) * A)
        dBx = dt.unsqueeze(-1) * B_proj.unsqueeze(2) * x.unsqueeze(-1)
        dBx = dBx.clone()
        dBx[:, 0] = dA[:, 0] * h_carry + dBx[:, 0]

        h = self._scan_chunk(dA, dBx)
        y = (h * C_proj.unsqueeze(2)).sum(-1)
        return y + x * self.D, h[:, -1]

    def _selective_scan(self, x: torch.Tensor, chunk_size: int = 256) -> torch.Tensor:
        """
        Scan the full sequence while limiting SSM activation memory to one chunk.

        The carry state connects chunks, so all timesteps remain part of the
        same sequence and no input token is dropped.
        """
        B, L, d_inner = x.shape
        h_carry = torch.zeros(
            B, d_inner, self.d_state, device=x.device, dtype=x.dtype
        )
        chunks_y = []

        for start in range(0, L, chunk_size):
            x_chunk = x[:, start : start + chunk_size]
            if self.training and x_chunk.requires_grad:
                y_chunk, h_carry = grad_checkpoint(
                    self._selective_scan_chunk,
                    x_chunk,
                    h_carry,
                    use_reentrant=False,
                )
            else:
                y_chunk, h_carry = self._selective_scan_chunk(x_chunk, h_carry)
            chunks_y.append(y_chunk)

        return torch.cat(chunks_y, dim=1)

    @staticmethod
    def _sequential_scan(dA: torch.Tensor, dBx: torch.Tensor) -> torch.Tensor:
        """
        Sequential scan compiled to TorchScript (C++ speed, no Python loop overhead).
        O(L) work — faster than parallel scan on CPU for L <= 512.
        """
        return _sequential_scan_jit(dA, dBx)

    @staticmethod
    def _scan_chunk(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
        """Parallel prefix scan on a single chunk (C timesteps)."""
        step = 1
        L = a.shape[1]
        while step < L:
            idx  = torch.arange(step, L, device=a.device)
            prev = idx - step
            new_a = a[:, idx] * a[:, prev]
            new_b = a[:, idx] * b[:, prev] + b[:, idx]
            a = torch.cat([a[:, :step], new_a], dim=1)
            b = torch.cat([b[:, :step], new_b], dim=1)
            step <<= 1
        return b

    @staticmethod
    def _parallel_scan(
        dA: torch.Tensor, dBx: torch.Tensor, chunk_size: int = 256
    ) -> torch.Tensor:
        """
        Chunked parallel scan: h_t = dA_t ⊙ h_{t-1} + dBx_t  (h_{-1} = 0).

        Splits L into chunks of `chunk_size` and chains them via carry state.
        Keeps intermediate tensors at (B, chunk_size, D, N) regardless of L
        → memory scales as O(chunk_size) not O(L), much better cache utilisation.

        Carry injection: for the first element of each chunk,
            b'[0] = a[0] ⊙ h_carry + b[0]
        so scan with h_{-1}=0 produces h'[0] = a[0]⊙h_carry + b[0] ✓

        Args:
            dA, dBx:    (B, L, d_inner, d_state)
            chunk_size: tokens per parallel-scan call (256 balances speed/memory)
        Returns:
            h:          (B, L, d_inner, d_state)
        """
        B, L, D, N = dA.shape

        if L <= chunk_size:
            return MambaBlock._scan_chunk(dA, dBx)

        chunks_h = []
        h_carry  = torch.zeros(B, D, N, device=dA.device, dtype=dA.dtype)

        for start in range(0, L, chunk_size):
            end     = min(start + chunk_size, L)
            a_chunk = dA[:,  start:end]
            b_chunk = dBx[:, start:end].clone()
            b_chunk[:, 0] = a_chunk[:, 0] * h_carry + b_chunk[:, 0]
            h_chunk  = MambaBlock._scan_chunk(a_chunk, b_chunk)
            chunks_h.append(h_chunk)
            h_carry  = h_chunk[:, -1]

        return torch.cat(chunks_h, dim=1)


class MambaSOHPredictor(nn.Module):
    """
    Input:  x      (batch, 30, input_features) — 30 timestep sensor window
            x_feat (batch, feat_dim)            — cycle-level spectral+kurtosis features
    Output: (batch,) — SOH% in range [0, 100]

    Architecture (FiLM conditioning):
      x      → Linear → MambaBlock×2 → LayerNorm → last token h (d_model,)
      x_feat → film_proj → gamma (d_model,) + beta (d_model,)
      h_modulated = sigmoid(gamma+1) * h + beta        ← FiLM
      h_modulated → Linear(d_model→32) → GELU → Dropout → Linear(32→1)

    Head size identical to v1.0 (no concatenation overhead).
    Pure PyTorch, no CUDA kernel — Windows-compatible.
    """

    def __init__(
        self,
        input_features: int = 6,
        d_model: int = 64,
        d_state: int = 16,
        n_layers: int = 2,
        dropout: float = 0.2,
        feat_dim: int = 54,
    ):
        super().__init__()
        self.input_features = input_features
        self.feat_dim = feat_dim
        self.input_proj = nn.Linear(input_features, d_model)
        self.mamba_layers = nn.ModuleList(
            [MambaBlock(d_model=d_model, d_state=d_state) for _ in range(n_layers)]
        )
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)
        # FiLM: project cycle features → gamma + beta for hidden state modulation
        self.film_proj = nn.Linear(feat_dim, d_model * 2)
        # Head: same size as v1.0
        self.fc1 = nn.Linear(d_model, 32)
        self.fc2 = nn.Linear(32, 1)

    def forward(self, x: torch.Tensor, x_feat: torch.Tensor) -> torch.Tensor:
        # x:      (batch, 30, input_features)
        # x_feat: (batch, feat_dim)
        h = self.input_proj(x)                        # (batch, 30, d_model)
        for layer in self.mamba_layers:
            h = layer(h)
        h = self.norm(h)
        h = h[:, -1, :]                               # (batch, d_model)

        # FiLM conditioning — modulate Mamba output with cycle-level features
        film = self.film_proj(x_feat)                 # (batch, d_model*2)
        gamma, beta = film.chunk(2, dim=-1)           # each (batch, d_model)
        # sigmoid(gamma)+0.5 centres scale around 1.0 for training stability
        h = (torch.sigmoid(gamma) + 0.5) * h + beta  # (batch, d_model)

        h = self.dropout(F.gelu(self.fc1(h)))
        return self.fc2(h).squeeze(-1)                # (batch,)
