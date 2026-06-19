"""Confidence / uncertainty for SOH prediction via MC Dropout.

The project spec requires a confidence score alongside SOH. MambaSOHPredictor
already has Dropout(0.2) in its head, so MC Dropout needs no retraining: run N
stochastic forward passes (dropout active), then mean = SOH, std = uncertainty.

Model-agnostic over the (x, x_feat) -> SOH interface (MambaSOHPredictor /
HybridMambaSOH). Does NOT touch the production inference flow — import and call
where a confidence score is needed.
"""

import torch
import torch.nn as nn


def _enable_dropout(model: nn.Module) -> None:
    """Re-activate ONLY Dropout layers (keep the rest in eval; LayerNorm unaffected)."""
    for m in model.modules():
        if isinstance(m, nn.Dropout):
            m.train()


@torch.no_grad()
def predict_with_confidence(
    model: nn.Module,
    x: torch.Tensor,
    x_feat: torch.Tensor,
    n_samples: int = 30,
    std_scale: float = 3.0,
) -> dict:
    """MC Dropout prediction with uncertainty.

    Args:
        model: trained predictor with forward(x, x_feat) -> SOH (model output / 100).
        x:      (B, L, F) window;  x_feat: (B, feat_dim) stats.
        n_samples: number of stochastic passes (GPU: 30 ~fine; CPU: keep <=15 for <100ms).
        std_scale: SOH% std mapped to confidence=0 (3.0 ~ the RMSE target).

    Returns dict of (B,) tensors:
        soh        — mean SOH% prediction
        std        — predictive std (%SOH) = uncertainty
        confidence — in [0,1], = clamp(1 - std/std_scale)
        lower/upper — 95% interval (mean ± 1.96·std)
    """
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2 for an uncertainty estimate.")
    model.eval()
    _enable_dropout(model)
    preds = torch.stack([model(x, x_feat) for _ in range(n_samples)], dim=0) * 100.0  # (N, B)
    soh = preds.mean(dim=0)
    std = preds.std(dim=0)
    confidence = torch.clamp(1.0 - std / std_scale, min=0.0, max=1.0)
    model.eval()  # restore (dropout off)
    return {
        "soh":        soh,
        "std":        std,
        "confidence": confidence,
        "lower":      soh - 1.96 * std,
        "upper":      soh + 1.96 * std,
    }
