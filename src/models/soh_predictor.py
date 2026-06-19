import math

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint as _ckpt




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
        # dt_rank: low-rank Δ projection — paper uses ceil(d_model/16), not 1
        self.dt_rank = max(1, math.ceil(d_model / 16))

        self.norm = nn.LayerNorm(d_model)
        # Gap 4 fix: paper uses bias=True for in_proj
        self.in_proj = nn.Linear(d_model, self.d_inner * 2, bias=True)

        # Causal depthwise conv
        self.conv1d = nn.Conv1d(
            self.d_inner, self.d_inner,
            kernel_size=d_conv, groups=self.d_inner,
            padding=d_conv - 1, bias=True,
        )

        # SSM projections: dt (rank=dt_rank), B, C
        # Gap 1 fix: dt_rank=4 (ceil(64/16)) instead of 1 — preserves selectivity
        self.x_proj = nn.Linear(self.d_inner, d_state * 2 + self.dt_rank, bias=False)
        self.dt_proj = nn.Linear(self.dt_rank, self.d_inner, bias=True)

        # Gap 2 fix: init dt_proj bias so softplus(bias) ∈ [dt_min, dt_max] per paper
        dt_init_std = self.dt_rank ** -0.5
        nn.init.uniform_(self.dt_proj.weight, -dt_init_std, dt_init_std)
        dt = torch.exp(
            torch.rand(self.d_inner) * (math.log(0.1) - math.log(0.001)) + math.log(0.001)
        ).clamp(min=1e-4)
        with torch.no_grad():
            # inv_softplus(dt) = dt + log(1 − exp(−dt)), numerically stable form
            self.dt_proj.bias.copy_(dt + torch.log(-torch.expm1(-dt)))

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

    @torch.compiler.disable  # autocast(enabled=False) inside creates a global-state guard that triggers
                             # recompilation every time the outer autocast state changes (train vs eval).
                             # The chunked scan loop also has dynamic bounds → can't be unrolled/fused.
                             # Surrounding layers (in_proj, out_proj, FiLM) still get compiled normally.
    def _selective_scan(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, L, d_inner)
        #
        # The SSM recurrence runs in fp32 regardless of AMP. This matches the
        # official Mamba reference (selective_scan_ref casts u/delta to float):
        # the state h accumulates over L steps, so fp16 underflows / compounds
        # error — and the longer the sequence (toward L=4096) the worse it gets.
        # We disable autocast locally so x_proj/dt_proj/softplus/exp and the
        # recurrence all stay fp32, then cast the output back to the input dtype
        # so the large in_proj/out_proj matmuls keep running fp16 (memory-friendly
        # at L=4096) — i.e. "fp16 matmul + fp32 accumulation" as in Mamba.
        orig_dtype = x.dtype
        B, L, d_inner = x.shape

        dev_type = "cuda" if x.is_cuda else "cpu"
        with torch.autocast(device_type=dev_type, enabled=False):
            x = x.float()

            x_dbl = self.x_proj(x)
            dt_raw, B_proj, C_proj = x_dbl.split(
                [self.dt_rank, self.d_state, self.d_state], dim=-1
            )

            dt = F.softplus(self.dt_proj(dt_raw))         # (B, L, d_inner) fp32
            A  = -torch.exp(self.A_log.float())           # (d_inner, d_state)

            if L <= 32:
                # Sequential scan only for L=30 production inference window.
                # Anything larger (including stage-1 L=256) uses the vectorized
                # chunked path below — avoids a Python for-loop graph break that
                # prevents torch.compile from fusing the scan into a single kernel.
                dA  = torch.exp(dt.unsqueeze(-1) * A)
                dBx = dt.unsqueeze(-1) * B_proj.unsqueeze(2) * x.unsqueeze(-1)
                h = torch.zeros(B, d_inner, self.d_state, device=x.device, dtype=torch.float32)
                ys = []
                for t in range(L):
                    h = dA[:, t] * h + dBx[:, t]
                    ys.append((h * C_proj[:, t].unsqueeze(1)).sum(-1))
                y = torch.stack(ys, dim=1)
            else:
                # Chunked scan: each chunk materialises (B, 256, d_inner, d_state) ~100MB
                # vs materialising the full (B, L, d_inner, d_state) ~6GB upfront.
                # Training: checkpoint each chunk so dA_c/dBx_c/h_c are recomputed in
                # backward instead of stored (full gradient flow preserved).
                # Inference fast-path: with grad disabled there is no backward, so
                # checkpointing only adds overhead (and a no-grad warning) — call the
                # chunk fn directly instead.
                # If fp32 makes L=4096 OOM, lower CHUNK (256 → 128) before reducing batch.
                CHUNK    = 256
                use_ckpt = torch.is_grad_enabled()
                y        = torch.zeros(B, L, d_inner, device=x.device, dtype=torch.float32)
                h_carry  = torch.zeros(B, d_inner, self.d_state, device=x.device, dtype=torch.float32)
                for start in range(0, L, CHUNK):
                    end = min(start + CHUNK, L)
                    chunk_args = (
                        dt[:, start:end], B_proj[:, start:end], C_proj[:, start:end],
                        x[:, start:end], h_carry, A,
                    )
                    if use_ckpt:
                        y_c, h_carry = _ckpt(MambaBlock._scan_forward_chunk, *chunk_args, use_reentrant=False)
                    else:
                        y_c, h_carry = MambaBlock._scan_forward_chunk(*chunk_args)
                    y[:, start:end] = y_c

            y = y + x * self.D

        return y.to(orig_dtype)


    @staticmethod
    def _scan_chunk(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
        """Hillis-Steele parallel prefix scan on a single chunk (C timesteps).

        Uses contiguous slices instead of arange + advanced indexing: the
        positions updated each step are exactly [step:], reading their
        partner at [:-step]. Slicing avoids building an index tensor and the
        gather it triggers, and stays functional (cat) so autograd is intact.
        """
        step = 1
        L = a.shape[1]
        while step < L:
            a_cur, a_prev = a[:, step:], a[:, :-step]
            b_cur, b_prev = b[:, step:], b[:, :-step]
            a = torch.cat([a[:, :step], a_cur * a_prev],         dim=1)
            b = torch.cat([b[:, :step], a_cur * b_prev + b_cur], dim=1)
            step <<= 1
        return b

    @staticmethod
    def _scan_forward_chunk(
        dt_c: torch.Tensor,     # (B, cs, d_inner)
        Bp_c: torch.Tensor,     # (B, cs, d_state)
        C_c: torch.Tensor,      # (B, cs, d_state)
        x_c: torch.Tensor,      # (B, cs, d_inner)
        h_carry: torch.Tensor,  # (B, d_inner, d_state)
        A: torch.Tensor,        # (d_inner, d_state)
    ) -> tuple:
        """One SSM chunk: returns (y_c, h_last). Checkpointed by caller.

        Inputs arrive fp32 (caller runs under autocast(enabled=False)), so dA_c,
        dBx_c, h_c and h_last all stay fp32 — preserving recurrence precision.
        """
        dA_c  = torch.exp(dt_c.unsqueeze(-1) * A)                          # (B, cs, d_inner, d_state)
        dBx_c = dt_c.unsqueeze(-1) * Bp_c.unsqueeze(2) * x_c.unsqueeze(-1)
        dBx_c = dBx_c.clone()
        dBx_c[:, 0] = dA_c[:, 0] * h_carry + dBx_c[:, 0]                 # inject carry
        h_c   = MambaBlock._scan_chunk(dA_c, dBx_c)                        # (B, cs, d_inner, d_state)
        y_c   = (h_c * C_c.unsqueeze(2)).sum(-1)                            # (B, cs, d_inner)
        return y_c, h_c[:, -1]                                              # h_last: (B, d_inner, d_state)


class OfficialMambaBlock(nn.Module):
    """Pre-norm residual wrapper around the OFFICIAL CUDA `mamba_ssm.Mamba`.

    Drop-in for MambaBlock — same (B, L, d_model) -> (B, L, d_model) interface and
    same pre-norm + residual structure, so the rest of the model is unchanged.

    ⚠️ Requires `pip install mamba-ssm causal-conv1d` and a CUDA GPU (Linux —
    Kaggle/Colab). It does NOT build on Windows native. Same math as MambaBlock →
    SAME accuracy, only faster/less VRAM (matters at long L, negligible at L=30).
    Default model path stays pure-PyTorch; this is opt-in via use_official_mamba.
    """

    def __init__(self, d_model: int, d_state: int = 16, d_conv: int = 4, expand: int = 2):
        super().__init__()
        try:
            from mamba_ssm import Mamba
        except ImportError as e:  # pragma: no cover - CUDA-only path
            raise ImportError(
                "official Mamba backend needs `mamba-ssm` (CUDA/Linux, e.g. Kaggle/Colab). "
                "On Windows use the default pure-PyTorch MambaBlock (use_official_mamba=False)."
            ) from e
        self.norm = nn.LayerNorm(d_model)
        self.mamba = Mamba(d_model=d_model, d_state=d_state, d_conv=d_conv, expand=expand)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, L, d_model) — pre-norm residual, matches MambaBlock
        return x + self.mamba(self.norm(x))


class PatchDegradationEncoder(nn.Module):
    """Per-patch degradation-sensitive feature injection for long sequences (L=4096).

    The global 54-dim feature vector (computed over the full 4096-step window) averages
    degradation dynamics across 100+ discharge cycles. This module computes four
    degradation-sensitive statistics — RMS, peak-to-peak, std, and excess kurtosis —
    per patch per channel, then projects to d_model and adds to each patch token
    embedding before the Mamba backbone.

    Replaces global-only conditioning with per-token local temporal context so the
    model sees HOW battery signals change within the long window, not just their
    global averages. Supported by: DualMamba (Frontiers CS 2026), JEC localized
    features (2025), BatteryML kurtosis evidence (arXiv 2310.14714).

    Input:  x  (B, L, C) — raw MinMaxScaled input (all C channels)
    Output: (B, num_patches, d_model) — added to patch token embeddings before Mamba
    """

    def __init__(
        self,
        patch_size: int,
        patch_stride: int,
        input_features: int,
        d_model: int,
    ):
        super().__init__()
        self.patch_size = patch_size
        self.patch_stride = patch_stride
        stat_dim = 4 * input_features   # RMS, P2P, std, kurtosis × C channels
        self.proj = nn.Sequential(
            nn.Linear(stat_dim, d_model),
            nn.LayerNorm(d_model),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, L, C)
        P = self.patch_size
        S = self.patch_stride
        # Unfold L into patches: (B, nW, C, P) → permute → (B, nW, P, C)
        xp = x.unfold(1, P, S).permute(0, 1, 3, 2)  # (B, nW, P, C)

        # RMS = sqrt(E[x²]) per patch per channel
        rms = xp.pow(2).mean(dim=2).sqrt()                       # (B, nW, C)

        # Peak-to-peak per patch per channel
        ptp = xp.amax(dim=2) - xp.amin(dim=2)                   # (B, nW, C)

        # Population std per patch per channel
        std = xp.std(dim=2, correction=0).clamp(min=1e-8)        # (B, nW, C)

        # Excess kurtosis (impulse indicator) — high near faults / end-of-life
        mu   = xp.mean(dim=2, keepdim=True)                      # (B, nW, 1, C)
        z    = (xp - mu) / std.unsqueeze(2)                      # (B, nW, P, C)
        kurt = z.pow(4).mean(dim=2) - 3.0                        # (B, nW, C)
        kurt = kurt.clamp(-10.0, 50.0)                           # stability: clamp outlier patches

        stats = torch.cat([rms, ptp, std, kurt], dim=-1)         # (B, nW, 4*C)
        return self.proj(stats)                                   # (B, nW, d_model)


class MambaSOHPredictor(nn.Module):
    """
    Input:  x      (batch, L, input_features) — L=30 (window=30 production) or L=4096 (long-seq)
            x_feat (batch, feat_dim)           — cycle-level spectral+kurtosis features
    Output: (batch,) — SOH% in range [0, 100]

    Architecture:
      patch_size=1  (L=30 default, no patching):
        x → Linear(C→d_model) → MambaBlock×2 → LayerNorm → last token h
      patch_size=16 (L=4096 long-seq, P16S16):
        x → Conv1d(C, d_model, k=16, s=16) → PatchDegradationEncoder → MambaBlock×2
            → LayerNorm → attn-pool h
        L=4096 compresses to 256 tokens (16×). PatchDegradationEncoder injects local
        RMS/P2P/std/kurtosis per 16-step patch, overcoming the global-feature averaging
        bottleneck that limited the v1.x MAE ceiling.

      h → FiLM(x_feat, 2-layer MLP) → Linear(d_model→32) → GELU+Dropout → Linear(32→1)

    Patch size 16 follows PatchTST/MambaDecomp (Nie et al. NeurIPS 2023).
    PatchDegradationEncoder inspired by DualMamba (2026) and localized feature
    selection (JEC 2025). Pure PyTorch, no CUDA kernel — Windows-compatible.
    """

    def __init__(
        self,
        input_features: int = 6,
        d_model: int = 64,
        d_state: int = 16,
        n_layers: int = 2,
        dropout: float = 0.2,
        feat_dim: int = 54,
        pooling: str = "last",
        use_official_mamba: bool = False,
        patch_size: int = 1,    # 1 = no patching (L=30 default); 16 for L=4096
        patch_stride: int = 1,  # = patch_size for non-overlapping (fastest)
    ):
        super().__init__()
        if pooling not in ("last", "attention"):
            raise ValueError(f"pooling must be 'last' or 'attention', got '{pooling}'")
        self.input_features = input_features
        self.feat_dim = feat_dim
        self.pooling = pooling
        self.patch_size   = patch_size
        self.patch_stride = patch_stride if patch_stride > 0 else patch_size
        # Default: pure-PyTorch MambaBlock (Windows-native). Opt-in: official CUDA
        # mamba_ssm (Kaggle/Colab GPU only) — same math, faster, no accuracy change.
        # Graceful fallback: if official requested but mamba_ssm/CUDA unavailable,
        # warn and use pure-PyTorch so "Run All" never crashes on the flag.
        if use_official_mamba:
            try:
                import mamba_ssm  # noqa: F401  (probe availability)
            except ImportError:
                import warnings
                warnings.warn("use_official_mamba=True but mamba_ssm unavailable "
                              "-> falling back to pure-PyTorch MambaBlock.")
                use_official_mamba = False
        self.use_official_mamba = use_official_mamba
        if patch_size > 1:
            # Conv1d patch extractor + projector: (B,C,L) → (B,d_model,num_patches)
            # Replaces input_proj; no padding so num_patches = (L - patch_size) // patch_stride + 1
            self.patch_embed = nn.Conv1d(
                input_features, d_model,
                kernel_size=self.patch_size, stride=self.patch_stride, bias=True,
            )
            self.patch_norm = nn.LayerNorm(d_model)
            # Per-patch degradation encoder: injects local RMS/P2P/std/kurtosis into
            # each patch token, overcoming the global-feature averaging bottleneck.
            self.patch_deg_enc = PatchDegradationEncoder(
                patch_size=self.patch_size,
                patch_stride=self.patch_stride,
                input_features=input_features,
                d_model=d_model,
            )
        else:
            self.input_proj = nn.Linear(input_features, d_model)
        _Block = OfficialMambaBlock if use_official_mamba else MambaBlock
        self.mamba_layers = nn.ModuleList(
            [_Block(d_model=d_model, d_state=d_state) for _ in range(n_layers)]
        )
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)
        # Attention pooling (long-seq): score each token → softmax → weighted sum.
        # "last" stays default so window=30 inference is byte-for-byte unchanged.
        if pooling == "attention":
            self.attn_score = nn.Linear(d_model, 1)
            # Discharge-weighted bias: patches that span the discharge phase
            # (phase channel ≈ 2) contain the strongest SOH signal. A learnable
            # scalar bias (init=2.0) is added to the raw attention logits for
            # these patches before softmax, steering the model toward
            # end-of-discharge context without hard masking.
            # Active only when patch_size>1 AND input has a phase channel (idx=-1).
            if patch_size > 1:
                self.discharge_bias = nn.Parameter(torch.tensor(2.0))
        # FiLM: 2-layer MLP projects cycle features → gamma + beta for hidden state
        # modulation. Deeper MLP improves nonlinear feature conditioning vs single
        # Linear, especially when feat_dim (54) and d_model (64) are close in size.
        self.film_proj = nn.Sequential(
            nn.Linear(feat_dim, feat_dim),
            nn.SiLU(),
            nn.Linear(feat_dim, d_model * 2),
        )
        # Head: same size as v1.0
        self.fc1 = nn.Linear(d_model, 32)
        self.fc2 = nn.Linear(32, 1)

    def forward(self, x: torch.Tensor, x_feat: torch.Tensor) -> torch.Tensor:
        # x:      (batch, L, input_features)  — L=30 (no-patch) or L=4096 (patch)
        # x_feat: (batch, feat_dim)
        if self.patch_size > 1:
            # Conv1d patch embedding: (B, L, C) → (B, num_patches, d_model)
            h = self.patch_embed(x.transpose(1, 2)).transpose(1, 2)
            h = self.patch_norm(h)
            # Inject per-patch local degradation stats (RMS/P2P/std/kurtosis per channel)
            # into each token before the Mamba backbone. This gives the SSM local-context
            # signals that global FiLM conditioning (over L=4096) cannot provide.
            h = h + self.patch_deg_enc(x)             # (batch, num_patches, d_model)
        else:
            h = self.input_proj(x)                    # (batch, L, d_model)
        for layer in self.mamba_layers:
            h = layer(h)
        h = self.norm(h)
        if self.pooling == "attention":
            scores = self.attn_score(h)                    # (batch, T, 1)
            if self.patch_size > 1 and hasattr(self, "discharge_bias"):
                # Phase channel is the last input channel (index -1).
                # Values: 0=rest, 1=charge, 2=discharge.
                # Mean phase per patch → discharge indicator in [0, 1].
                phase = x[..., -1]                         # (batch, L)
                phase_per_patch = phase.unfold(1, self.patch_size, self.patch_stride).mean(dim=-1)
                # Normalise to [0,1]: discharge (2) → 1, rest (0) → 0
                discharge_ind = (phase_per_patch / 2.0).clamp(0.0, 1.0).unsqueeze(-1)
                scores = scores + self.discharge_bias * discharge_ind
            w = torch.softmax(scores, dim=1)               # (batch, T, 1)
            h = (w * h).sum(dim=1)                         # (batch, d_model)
        else:  # "last"
            h = h[:, -1, :]                               # (batch, d_model)

        # FiLM conditioning — modulate Mamba output with cycle-level features
        film = self.film_proj(x_feat)                 # (batch, d_model*2)
        gamma, beta = film.chunk(2, dim=-1)           # each (batch, d_model)
        # sigmoid(gamma)+0.5 centres scale around 1.0 for training stability
        h = (torch.sigmoid(gamma) + 0.5) * h + beta  # (batch, d_model)

        h = self.dropout(F.gelu(self.fc1(h)))
        return self.fc2(h).squeeze(-1)                # (batch,)
