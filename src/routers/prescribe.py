"""POST /prescribe — RAG-augmented maintenance prescription endpoint."""
from fastapi import APIRouter, HTTPException

from src.schemas.prescribe import (
    PrescribeRequest,
    PrescribeResponse,
    PrescriptionFeedbackRequest,
    PrescriptionFeedbackResponse,
)
from src.services.prescription import run_prescription, submit_prescription_feedback

router = APIRouter()


@router.post("/prescribe/", response_model=PrescribeResponse)
async def prescribe(request: PrescribeRequest) -> dict:
    """
    Hybrid maintenance prescription for a battery.

    Default (enrich=false): deterministic rule-based prescription, <100ms, no network.
    enrich=true: also run RAG retrieval + LLM generation (slower, off the P1 hot-path);
    falls back to the rule-based result if the LLM is unavailable or errors.
    agentic=true (GH-82, requires enrich=true): LLM expands the diagnosis into
    3-5 search queries before retrieval (2 LLM calls total).

    Returns SOH/risk context, action steps, PPE, retrieved evidence (when enriched),
    and the safety-gate result (human_verification_required forced True for P1).
    """
    return run_prescription(
        readings              = request.readings,
        battery_id            = request.battery_id,
        enrich                = request.enrich,
        n_series              = request.pack_config.n_series if request.pack_config else 1,
        agentic               = request.agentic,
        age_cycles            = request.age_cycles,
        last_maintenance_date = request.last_maintenance_date,
        ticket_history        = request.ticket_history,
    )


@router.post("/prescribe/feedback", response_model=PrescriptionFeedbackResponse)
async def prescribe_feedback(request: PrescriptionFeedbackRequest) -> dict:
    """
    GH-83 — record technician feedback (accepted/edited/rejected) for a
    prescription_id returned by a prior POST /prescribe/ (enrich=true) call.
    Accepted prescriptions become few-shot context for future similar cases.

    404 when prescription_id doesn't exist (or the history store is unavailable).
    """
    ok = submit_prescription_feedback(
        prescription_id = request.prescription_id,
        status          = request.status,
        edited_steps    = request.edited_steps,
        note            = request.note,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="prescription_id not found")
    return {"success": True}
