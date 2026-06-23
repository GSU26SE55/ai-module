"""
Request/response schemas for POST /prescribe endpoint.
"""
from pydantic import BaseModel
from src.schemas.predict import PredictRequest


class PrescribeRequest(PredictRequest):
    """Extends PredictRequest with optional battery history context."""
    age_cycles: int | None = None
    last_maintenance_date: str | None = None
    ticket_history: list[str] = []


class RetrievedDoc(BaseModel):
    title: str
    content: str
    source: str           # e.g. "maintenance/bms_warning_codes.md"
    relevance_score: float


class PrescribeResponse(BaseModel):
    battery_id: str

    # Prediction context (from /predict)
    soh_percent: float
    risk_level: str       # Critical / High / Medium / Low
    priority: str         # P1 / P2 / P3 / None
    action_code: str

    # RAG-generated prescription
    prescription: str     # LLM-generated maintenance recommendation
    action_steps: list[str]
    escalation_conditions: list[str]
    ppe_required: list[str]

    # Retrieved evidence
    maintenance_docs: list[RetrievedDoc]
    safety_docs: list[RetrievedDoc]

    # Safety gate
    human_verification_required: bool = True
    safety_warnings: list[str] = []

    inference_ms: float
    rag_ms: float
