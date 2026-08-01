from fastapi import APIRouter

from src.core import model_loader
from src.core.config import LFP_MODEL_VERSION, MODEL_VERSION
from src.services.prescription import observability

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "model_version": MODEL_VERSION,
        "scaler_loaded": model_loader.scaler is not None,
        "mamba_loaded": model_loader.soh_model is not None,
        "isolation_forest_loaded": model_loader.iso_model is not None,
        # GH-67: the LFP set is optional — a NASA-only deploy boots without it, but
        # then any request with chemistry="LFP" fails instead of being mis-scored.
        # Expose it so that failure mode is visible before a request hits it.
        "lfp_model_version": LFP_MODEL_VERSION,
        "lfp_loaded": model_loader.lfp_soh_model is not None,
        # GH-84: /prescribe idempotency cache + LLM rate-limit observability.
        "prescription_metrics": observability.metrics_snapshot(),
    }
