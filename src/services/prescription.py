"""
Prescription generator — HYBRID orchestrator.

Strategy (see docs/prescription-layer.md, Phương án C):
  - Rule-based engine is the DEFAULT and the FALLBACK. It always runs, is
    deterministic, has no external dependency, and stays well under 100ms — so
    it is safe on the P1 critical path.
  - The LLM+RAG layer only ENRICHES the rule baseline, and only when it adds
    value without hurting the SLA: for P2/P3 (non-critical) tickets, or on
    explicit `detail=True` request. P1 stays rule-only for speed and safety.
  - If the LLM is unavailable, errors, or times out, the rule output is
    returned verbatim (graceful degradation).

POST /prescribe flow:
  1. Run inference (SOH, risk, warnings)
  2. Build rule-based prescription (always)
  3. Decide whether to enrich with LLM+RAG
  4. If enriching: retrieve docs → call LLM → merge onto rule baseline
  5. Apply safety gate
  6. Return structured PrescribeResponse
"""
import time

from src.services._llm_client import call_structured_prescription
from src.services.inference import run_inference
from src.services.rag_retriever import RagRetriever
from src.services.rules_prescription import build_rule_prescription
from src.services.safety_gate import apply_safety_gate

_retriever = RagRetriever()

# Priorities that get LLM enrichment by default (P1 stays rule-only for SLA/safety).
_LLM_ENRICH_PRIORITIES = {"P2", "P3", "None"}


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


def _should_enrich(priority: str, detail: bool) -> bool:
    """Hybrid routing: enrich with LLM for non-critical tickets or on demand."""
    if detail:
        return True
    return priority in _LLM_ENRICH_PRIORITIES


def _merge_llm_onto_rule(rule_out: dict, llm_out: dict) -> dict:
    """
    Combine LLM enrichment with the rule baseline.

    The LLM provides richer prose, but the rule action steps and PPE are kept as
    the guaranteed safety baseline; LLM extras are appended (deduped).
    """
    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for it in items:
            if it not in seen:
                seen.add(it)
                out.append(it)
        return out

    return {
        "prescription": llm_out.get("prescription") or rule_out["prescription"],
        "action_steps": _dedupe(rule_out["action_steps"] + llm_out.get("action_steps", [])),
        "ppe_required": _dedupe(rule_out["ppe_required"] + llm_out.get("ppe_required", [])),
        "source": "llm",
    }


def run_prescription(
    readings: list[list[float]],
    battery_id: str,
    detail: bool = False,
    **context_kwargs,
) -> dict:
    """
    Hybrid prescription pipeline.

    Args:
        readings: (WINDOW_SIZE, F) sensor readings
        battery_id: battery identifier
        detail: force LLM+RAG enrichment regardless of priority
        context_kwargs: age_cycles, last_maintenance_date, ticket_history

    Returns:
        PrescribeResponse-compatible dict
    """
    # 1. Inference
    prediction_result = run_inference(readings)
    inference_ms = prediction_result.get("metadata", {}).get("inference_ms", 0)

    prediction = prediction_result.get("prediction", {})
    risk       = prediction_result.get("risk", {})
    warnings   = prediction_result.get("evidence", {}).get("warnings", [])
    priority   = risk.get("priority", "None")

    t_rag_start = time.perf_counter()

    # 2. Rule-based prescription — always (default + fallback)
    rule_out = build_rule_prescription(prediction, risk, warnings)
    final = rule_out
    maint_docs: list[dict] = []
    safety_docs: list[dict] = []

    # 3-4. Optionally enrich with LLM+RAG
    if _should_enrich(priority, detail):
        maint_query  = _build_maintenance_query(prediction, risk)
        safety_query = _build_safety_query(warnings)
        maint_docs   = _retriever.retrieve_maintenance(maint_query, top_k=3)
        safety_docs  = _retriever.retrieve_safety(safety_query, top_k=2)

        llm_out = call_structured_prescription(
            maint_query, rule_out, maint_docs, safety_docs
        )
        if llm_out is not None:
            final = _merge_llm_onto_rule(rule_out, llm_out)
        else:
            # Enrichment requested but unavailable → keep rule baseline, flag it.
            final = {**rule_out, "source": "rule (llm-unavailable)"}

    # 5. Safety gate
    gate = apply_safety_gate(
        priority    = priority,
        action_code = risk.get("action_code", "MONITOR"),
        warnings    = warnings,
        prescription= final["prescription"],
    )

    rag_ms = (time.perf_counter() - t_rag_start) * 1000

    return {
        "battery_id":   battery_id,
        "soh_percent":  prediction.get("soh_percent", 0),
        "risk_level":   risk.get("risk_level", "Low"),
        "priority":     priority,
        "action_code":  risk.get("action_code", "MONITOR"),

        "prescription":           final["prescription"],
        "action_steps":           final["action_steps"],
        "escalation_conditions":  gate["escalation_conditions"],
        "ppe_required":           final["ppe_required"],
        "prescription_source":    final["source"],

        "maintenance_docs": maint_docs,
        "safety_docs":      safety_docs,

        "human_verification_required": gate["human_verification_required"],
        "safety_warnings":             gate["safety_warnings"],

        "inference_ms": inference_ms,
        "rag_ms":       round(rag_ms, 2),
    }
