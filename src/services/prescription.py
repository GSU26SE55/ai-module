"""
Prescription generator — orchestrates predict → retrieve → generate → safety gate.

POST /prescribe flow:
  1. Run inference (SOH, risk, warnings)
  2. Build context queries from prediction
  3. Retrieve maintenance + safety docs
  4. Call LLM to generate prescription
  5. Apply safety gate
  6. Return structured PrescribeResponse
"""
import os
import time

from src.services.inference import run_inference
from src.services.rag_retriever import RagRetriever
from src.services.safety_gate import apply_safety_gate

_retriever = RagRetriever()

# LLM config — uses Claude claude-sonnet-4-6 via Anthropic SDK
# Set ANTHROPIC_API_KEY in .env
LLM_MODEL = "claude-sonnet-4-6"
LLM_MAX_TOKENS = 512


def _build_maintenance_query(prediction: dict, risk: dict) -> str:
    """Build semantic search query from structured prediction."""
    soh   = prediction.get("soh_percent", 0)
    trend = prediction.get("soh_trend", "stable")
    stage = prediction.get("health_stage", "")
    rate  = prediction.get("degradation_rate_per_cycle", 0)
    rul   = prediction.get("rul_cycles_estimate", 0)
    return (
        f"Battery SOH {soh:.1f}%, health stage {stage}, "
        f"degradation rate {rate:.2f}%/cycle, trend {trend}, "
        f"estimated {rul} cycles remaining, "
        f"risk {risk.get('risk_level')}, action {risk.get('action_code')}"
    )


def _build_safety_query(warnings: list[dict]) -> str:
    """Build safety search query from active warnings."""
    codes = [w.get("code", "") for w in warnings]
    return "battery safety " + " ".join(codes) if codes else "battery general safety"


def _call_llm(context: str, maintenance_docs: list[dict], safety_docs: list[dict]) -> dict:
    """
    Call LLM to generate structured prescription.
    Returns dict with prescription, action_steps, ppe_required.
    Stub implementation — replace with real Anthropic API call.
    """
    # TODO: implement with anthropic SDK
    # import anthropic
    # client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    # ...

    # Stub response for skeleton
    return {
        "prescription": (
            f"Based on the battery assessment: {context[:200]}... "
            "Please consult the maintenance SOP and safety checklist before proceeding."
        ),
        "action_steps": [
            "Review battery health report with maintenance team",
            "Follow BMS warning code response procedure",
            "Complete PPE checklist before physical inspection",
        ],
        "ppe_required": ["Insulated gloves", "Safety glasses"],
    }


def run_prescription(readings: list[list[float]], battery_id: str, **context_kwargs) -> dict:
    """
    Full prescription pipeline.

    Args:
        readings: (WINDOW_SIZE, 6) sensor readings
        battery_id: battery identifier
        context_kwargs: age_cycles, last_maintenance_date, ticket_history

    Returns:
        PrescribeResponse-compatible dict
    """
    t_start = time.perf_counter()

    # 1. Inference
    prediction_result = run_inference(readings)
    inference_ms = prediction_result.get("metadata", {}).get("inference_ms", 0)

    prediction = prediction_result.get("prediction", {})
    risk       = prediction_result.get("risk", {})
    warnings   = prediction_result.get("evidence", {}).get("warnings", [])

    t_rag_start = time.perf_counter()

    # 2. Build queries
    maint_query  = _build_maintenance_query(prediction, risk)
    safety_query = _build_safety_query(warnings)

    # 3. Retrieve docs
    maint_docs  = _retriever.retrieve_maintenance(maint_query, top_k=3)
    safety_docs = _retriever.retrieve_safety(safety_query, top_k=2)

    # 4. Generate prescription
    llm_out = _call_llm(maint_query, maint_docs, safety_docs)

    # 5. Safety gate
    gate = apply_safety_gate(
        priority    = risk.get("priority", "None"),
        action_code = risk.get("action_code", "MONITOR"),
        warnings    = warnings,
        prescription= llm_out["prescription"],
    )

    rag_ms = (time.perf_counter() - t_rag_start) * 1000

    return {
        "battery_id":   battery_id,
        "soh_percent":  prediction.get("soh_percent", 0),
        "risk_level":   risk.get("risk_level", "Low"),
        "priority":     risk.get("priority", "None"),
        "action_code":  risk.get("action_code", "MONITOR"),

        "prescription":           llm_out["prescription"],
        "action_steps":           llm_out["action_steps"],
        "escalation_conditions":  gate["escalation_conditions"],
        "ppe_required":           llm_out["ppe_required"],

        "maintenance_docs": maint_docs,
        "safety_docs":      safety_docs,

        "human_verification_required": gate["human_verification_required"],
        "safety_warnings":             gate["safety_warnings"],

        "inference_ms": inference_ms,
        "rag_ms":       round(rag_ms, 2),
    }
