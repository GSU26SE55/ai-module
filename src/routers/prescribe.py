"""POST /prescribe — RAG-augmented maintenance prescription endpoint."""
from fastapi import APIRouter

from src.schemas.prescribe import PrescribeRequest, PrescribeResponse
from src.services.prescription import run_prescription

router = APIRouter()


@router.post("/prescribe/", response_model=PrescribeResponse)
async def prescribe(request: PrescribeRequest) -> dict:
    """
    Run AI prediction + RAG retrieval + LLM prescription for a battery.

    Hybrid: rule-based prescription always runs (default + fallback); LLM+RAG
    enriches non-critical (P2/P3) tickets or when `detail=True` is requested.

    Returns structured maintenance recommendation with:
    - SOH prediction and risk assessment
    - Rule-based action steps + PPE (always)
    - Retrieved maintenance/safety documentation (when enriched)
    - Safety gate result (human_verification_required always True for P1)
    """
    return run_prescription(
        readings              = request.readings,
        battery_id            = request.battery_id,
        detail                = request.detail,
        age_cycles            = request.age_cycles,
        last_maintenance_date = request.last_maintenance_date,
        ticket_history        = request.ticket_history,
    )
