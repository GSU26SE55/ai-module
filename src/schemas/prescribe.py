"""
Request/response schemas for POST /prescribe endpoint.
"""
from typing import Literal

from pydantic import BaseModel
from src.schemas.predict import AnomalyInfo, PredictionInfo, PredictRequest, RiskInfo


class PrescribeRequest(PredictRequest):
    """Extends PredictRequest with optional battery history context."""
    age_cycles: int | None = None
    last_maintenance_date: str | None = None
    ticket_history: list[str] = []
    enrich: bool = False
    """If True, also run RAG + LLM enrichment (slower, off the P1 hot-path).
    Default False → deterministic rule-based prescription only (<100ms)."""
    agentic: bool = False
    """GH-82: if True (and enrich=True), run the agentic chain — diagnosis
    statement → LLM query generation → multi-query retrieval (2 LLM calls).
    Ignored when enrich=False; enrich stays the master switch."""


class RetrievedDoc(BaseModel):
    title: str
    content: str
    source: str           # e.g. "maintenance/bms_warning_codes.md"
    relevance_score: float
    # GH-82: which search query retrieved this doc — "template" for the
    # non-agentic path, the generated query text on the agentic path.
    retrieved_via: str = ""


class PrescribeResponse(BaseModel):
    battery_id: str

    # Prediction context (from /predict). GH-87: deprecated — kept for backward
    # compat, superseded by the nested prediction/anomaly/risk blocks below.
    soh_percent: float
    risk_level: str       # Critical / High / Medium / Low
    # P1 / P2 / P3 / None — suggested Urgency signal from battery severity only,
    # NOT the final ticket Priority (no ImpactScope here). GH-23: BE combines
    # this with ImpactScope via the Priority Matrix — see docs/ai-be-integration.md §4.
    priority: str
    action_code: str

    # Prescription (rule-based by default; LLM-generated when enriched=True)
    prescription: str
    action_steps: list[str]
    escalation_conditions: list[str]
    ppe_required: list[str]
    sop_references: list[str] = []

    # True when LLM+RAG enrichment ran successfully; False = rule-based fallback.
    enriched: bool = False
    # Which provider generated the prescription: "deepseek" / "gemini" / "anthropic" / "none".
    llm_provider: str = "none"

    # Retrieved evidence (empty unless enriched)
    maintenance_docs: list[RetrievedDoc] = []
    safety_docs: list[RetrievedDoc] = []

    # Safety gate
    human_verification_required: bool = True
    safety_warnings: list[str] = []
    # GH-81: True when the LLM output was blocked by output validation
    # (forbidden action / unsafe judge verdict) — the returned prescription is
    # the rule-based fallback and human verification is always required.
    blocked: bool = False

    inference_ms: float
    rag_ms: float = 0.0
    llm_ms: float = 0.0
    # GH-82: agentic chain metrics — query-gen latency and the LLM-generated
    # search queries (empty on the template path or query-gen fallback).
    query_gen_ms: float = 0.0
    generated_queries: list[str] = []

    # GH-83: uuid4 identifying the saved history record — only set when
    # enrich=true and the write succeeded; "" on the rule-only path (enrich=false)
    # or if the history store is unavailable. Pass this to POST /prescribe/feedback.
    prescription_id: str = ""

    # GH-87: nested prediction/anomaly/risk context — reuses the same schemas as
    # PredictResponse, so GH-86 uncertainty (health_stage, stage_probabilities,
    # stage_confidence, is_borderline, soh_confidence, soh_std) reaches BE via
    # Prescribe (the last output). Always populated — run_inference() runs
    # unconditionally as step 1 of run_prescription(), regardless of enrich.
    prediction: PredictionInfo
    anomaly: AnomalyInfo
    risk: RiskInfo


class PrescriptionFeedbackRequest(BaseModel):
    """GH-83 — technician feedback for a previously returned prescription_id."""
    prescription_id: str
    status: Literal["accepted", "edited", "rejected"]
    edited_steps: list[str] | None = None
    note: str | None = None


class PrescriptionFeedbackResponse(BaseModel):
    success: bool
