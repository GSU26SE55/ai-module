"""
Prescription generator — Hybrid (rule-based default + optional LLM/RAG enrichment).

POST /prescribe flow:
  1. Run inference (SOH, risk, warnings).
  2. Build rule-based prescription (deterministic, <100ms) — ALWAYS the baseline.
  3. If enrich=True: RAG retrieve docs (+ past accepted cases, GH-83) + LLM
     generate; on success override the prescription text/steps/PPE. On any
     failure → keep the rule-based result.
  4. Apply safety gate (human verification, escalation).
  5. If enrich=True: save the final delivered prescription to history (best-effort,
     GH-83) — becomes future few-shot context once a technician marks it accepted.
  6. Return structured PrescribeResponse dict.

The rule-based path never touches the network, so the default (enrich=False) stays
on the P1 <100ms hot-path. Enrichment is opt-in and explicitly off that path.
"""
import json
import logging
import os
import time

from src.services.inference import run_inference
from src.services.prescription import observability
from src.services.prescription.diagnosis import build_diagnosis_statement
from src.services.prescription.rule_prescription import build_rule_prescription
from src.services.prescription.safety_gate import apply_safety_gate

logger = logging.getLogger(__name__)

# GH-81: dedicated audit trail for blocked prescriptions — separate logger name
# so ops can route/retain it independently, and tests can assert on it (caplog).
_audit_logger = logging.getLogger("safety_gate.audit")

# Lazy singleton — only built when enrichment is first requested, so the rule-only
# path never pays the SentenceTransformer/ChromaDB import + load cost.
_retriever = None


def _get_retriever():
    global _retriever
    if _retriever is None:
        from src.services.prescription.rag_retriever import RagRetriever
        _retriever = RagRetriever()
    return _retriever


# GH-83: same lazy-singleton pattern, separate ChromaDB store (models/prescription_history/,
# not the committed static KB) — only built when enrichment is first requested.
_history_store = None


def _get_history_store():
    global _history_store
    if _history_store is None:
        from src.services.prescription.history_store import PrescriptionHistoryStore
        _history_store = PrescriptionHistoryStore()
    return _history_store


def _build_maintenance_query(prediction: dict, risk: dict) -> str:
    """Build semantic search query from structured prediction."""
    soh   = prediction.get("soh_percent", 0)
    stage = prediction.get("health_stage", "")
    rate  = prediction.get("degradation_rate_per_cycle", 0)
    trend = prediction.get("soh_trend", "stable")
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


def _dedup(items: list[str]) -> list[str]:
    """Order-preserving de-duplication."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _multi_query_retrieve(fetch, queries: list[str], top_k: int, cap: int) -> list[dict]:
    """
    GH-82: retrieve top_k per query, tag each doc with the query that found it
    (retrieved_via), dedup by chunk_id keeping the highest-relevance copy, and
    return at most `cap` docs sorted by relevance_score.
    """
    best: dict = {}
    for query in queries:
        for doc in fetch(query, top_k=top_k):
            doc = {**doc, "retrieved_via": query}
            # chunk_id from the retriever; content-based fallback for safety.
            key = doc.get("chunk_id") or (doc.get("source", ""), doc.get("content", "")[:80])
            if key not in best or doc["relevance_score"] > best[key]["relevance_score"]:
                best[key] = doc
    ranked = sorted(best.values(), key=lambda d: d["relevance_score"], reverse=True)
    return ranked[:cap]


def _judge_enabled() -> bool:
    """GH-81: LLM-as-judge feature flag — default off (enable when budget allows)."""
    return os.getenv("SAFETY_LLM_JUDGE", "").strip().lower() in {"1", "true", "yes", "on"}


def _run_judge(warnings: list[dict], action_steps: list[str]) -> dict | None:
    """
    GH-81: LLM-as-judge — ask the provider chain whether the generated steps
    are safe for the current warning state. Returns {"safe": bool, "reason": str}
    or None on any failure/timeout: the output already passed rule-based
    validation, so judge unavailability must never block a valid response.
    """
    from src.services.prescription.llm import chain

    try:
        return chain.judge_safety(_build_safety_query(warnings), action_steps)
    except Exception as exc:
        logger.warning("Safety judge unavailable — passing rule-validated output: %s", exc)
        return None


def _audit_block(
    battery_id: str,
    risk: dict,
    warnings: list[dict],
    blocked_output: dict,
    reasons: list[str],
    matched_patterns: list[str],
    source: str,
) -> None:
    """GH-81: one structured audit record per blocked prescription."""
    _audit_logger.warning(
        "PRESCRIPTION_BLOCKED %s",
        json.dumps(
            {
                "battery_id": battery_id,
                "priority": risk.get("priority", "None"),
                "action_code": risk.get("action_code", "MONITOR"),
                "warning_codes": [w.get("code", "") for w in warnings],
                "source": source,  # "blocklist" | "llm_judge"
                "reasons": reasons,
                "matched_patterns": matched_patterns,
                "blocked_prescription": blocked_output.get("prescription", ""),
                "blocked_action_steps": blocked_output.get("action_steps", []),
                "llm_provider": blocked_output.get("llm_provider", "none"),
            },
            ensure_ascii=False,
        ),
    )


def _enrich(
    prediction: dict,
    risk: dict,
    warnings: list[dict],
    rule_out: dict,
    anomaly: dict | None = None,
    agentic: bool = False,
    battery_id: str = "",
    ticket_history: list[str] | None = None,
) -> dict:
    """
    Run RAG retrieval + LLM generation. Returns a partial dict to merge into the
    response. On any failure, returns the rule-based fields with enriched=False
    (docs may still be attached if retrieval succeeded).

    agentic=True (GH-82): first ask the LLM to expand the diagnosis statement
    into 3-5 focused search queries, then retrieve per query with dedup.
    Query-gen failure falls back to the template query — never fatal.
    """
    from src.services.prescription.llm import chain

    # GH-83: built unconditionally (not just when agentic) — it is the "context"
    # embedded for both history retrieval below and the history record saved by
    # run_prescription() after this function returns.
    diagnosis = build_diagnosis_statement(
        prediction, anomaly or {}, risk, warnings, ticket_history=ticket_history
    )

    result = {
        "prescription":   rule_out["prescription"],
        "action_steps":   rule_out["action_steps"],
        "ppe_required":   rule_out["ppe_required"],
        "enriched":       False,
        "llm_provider":   "none",
        "maintenance_docs": [],
        "safety_docs":      [],
        "rag_ms":         0.0,
        "llm_ms":         0.0,
        "query_gen_ms":   0.0,
        "generated_queries": [],
        "chain_attempted": [],
        "diagnosis":      diagnosis,
    }

    # 0. Query planning (GH-82). Template queries by default; when agentic,
    #    LLM expands the diagnosis into focused queries (timed separately).
    maint_queries = [_build_maintenance_query(prediction, risk)]
    safety_queries = [_build_safety_query(warnings)]
    agentic_active = False
    if agentic and chain.is_available():
        t_qg = time.perf_counter()
        try:
            q = chain.generate_queries(diagnosis, budget_s=chain.QUERYGEN_BUDGET_S)
            gen_maint = [s.strip() for s in q.get("maintenance_queries", []) if s.strip()]
            gen_safety = [s.strip() for s in q.get("safety_queries", []) if s.strip()]
            if gen_maint or gen_safety:
                maint_queries = gen_maint or maint_queries
                safety_queries = gen_safety or safety_queries
                result["generated_queries"] = gen_maint + gen_safety
                agentic_active = True
        except Exception as exc:
            logger.warning("Query generation failed — falling back to template query: %s", exc)
        result["query_gen_ms"] = round((time.perf_counter() - t_qg) * 1000, 2)

    # 1. Retrieve (timed). Retriever returns [] gracefully if ChromaDB unavailable.
    t_rag = time.perf_counter()
    try:
        retriever = _get_retriever()
        if agentic_active:
            maint_docs = _multi_query_retrieve(
                retriever.retrieve_maintenance, maint_queries, top_k=2, cap=5)
            safety_docs = _multi_query_retrieve(
                retriever.retrieve_safety, safety_queries, top_k=2, cap=3)
        else:
            maint_docs  = retriever.retrieve_maintenance(maint_queries[0], top_k=3)
            safety_docs = retriever.retrieve_safety(safety_queries[0], top_k=2)
            maint_docs  = [{**d, "retrieved_via": "template"} for d in maint_docs]
            safety_docs = [{**d, "retrieved_via": "template"} for d in safety_docs]
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("RAG retrieval failed: %s", exc)
        maint_docs, safety_docs = [], []
    result["rag_ms"] = round((time.perf_counter() - t_rag) * 1000, 2)
    result["maintenance_docs"] = maint_docs
    result["safety_docs"] = safety_docs

    # 2. LLM (timed). Skip if no provider in the chain has a key configured.
    if not chain.is_available():
        logger.info("No LLM provider key configured — returning rule-based prescription.")
        return result

    # GH-84: reserve 1 concurrency slot + 1 hourly-budget unit for the main
    # generate call — never queue, degrade to rule-based immediately if the
    # budget is exhausted or both concurrency slots are already in use.
    if not observability.try_acquire_llm_slot():
        logger.warning("LLM rate-limit/budget exhausted — returning rule-based prescription.")
        return result

    # 2a. Past-case retrieval (GH-83): accepted cases only, reference-only
    #     few-shot context. retrieve_similar_accepted() is itself best-effort
    #     (returns [] on any failure) — no extra try/except needed here.
    past_cases = _get_history_store().retrieve_similar_accepted(
        diagnosis, battery_id=battery_id, top_k=2
    )

    t_llm = time.perf_counter()
    try:
        context = _build_maintenance_query(prediction, risk)
        llm_out = chain.generate_prescription(context, maint_docs, safety_docs, past_cases)
        result["chain_attempted"] = llm_out.get("chain_attempted", [])
        if not llm_out.get("action_steps"):
            # GH-81 edge case: empty steps from the LLM → keep the rule-based output.
            logger.warning("LLM returned empty action_steps — keeping rule-based prescription.")
        else:
            result["prescription"] = llm_out["prescription"]
            result["action_steps"] = llm_out["action_steps"]
            # Union with rule PPE so safety-critical PPE is never dropped by the LLM.
            result["ppe_required"] = _dedup(rule_out["ppe_required"] + llm_out["ppe_required"])
            result["enriched"] = True
            result["llm_provider"] = llm_out.get("provider", "none")
    except Exception as exc:
        logger.warning("LLM enrichment failed, using rule-based prescription: %s", exc)
    finally:
        observability.release_llm_slot()
    result["llm_ms"] = round((time.perf_counter() - t_llm) * 1000, 2)
    return result


def _run_prescription_uncached(
    readings: list[list[float]],
    battery_id: str,
    enrich: bool = False,
    n_series: int = 1,
    agentic: bool = False,
    **context_kwargs,
) -> dict:
    """
    Full hybrid prescription pipeline.

    Args:
        readings: sensor window passed through to run_inference.
        battery_id: battery identifier.
        enrich: if True, attempt RAG + LLM enrichment (off the P1 hot-path).
        n_series: GH-65 pack_config.n_series, passed through to run_inference.
        agentic: GH-82 — if True (and enrich=True), run the agentic chain:
            diagnosis statement → LLM query generation → multi-query retrieval.
            Ignored when enrich=False (enrich stays the master switch).
        context_kwargs: age_cycles, last_maintenance_date (reserved); ticket_history
            (GH-105) is forwarded into _enrich() when enrich=True.

    Returns:
        PrescribeResponse-compatible dict. "prescription_id" (GH-83) is a uuid4
        when enrich=True and the history write succeeded, "" otherwise (rule-only
        path, or history store unavailable/write failed) — feedback endpoints
        must treat "" as "no record to give feedback on".
    """
    # 1. Inference
    prediction_result = run_inference(
        readings, n_series=n_series, battery_id=battery_id
    )
    prediction = prediction_result.get("prediction", {})
    anomaly    = prediction_result.get("anomaly", {})
    risk       = prediction_result.get("risk", {})
    warnings   = prediction_result.get("evidence", {}).get("warnings", [])
    inference_ms = prediction_result.get("metadata", {}).get("inference_ms", 0)

    # 2. Rule-based baseline (always)
    rule_out = build_rule_prescription(prediction, risk, warnings)

    # 3. Optional enrichment
    if enrich:
        enriched = _enrich(
            prediction, risk, warnings, rule_out, anomaly=anomaly, agentic=agentic,
            battery_id=battery_id, ticket_history=context_kwargs.get("ticket_history"),
        )
    else:
        enriched = {
            "prescription":   rule_out["prescription"],
            "action_steps":   rule_out["action_steps"],
            "ppe_required":   rule_out["ppe_required"],
            "enriched":       False,
            "llm_provider":   "none",
            "maintenance_docs": [],
            "safety_docs":      [],
            "rag_ms":         0.0,
            "llm_ms":         0.0,
            "query_gen_ms":   0.0,
            "generated_queries": [],
        }

    # 4. Safety gate (runs for both paths) — v2 (GH-81) also validates the
    #    OUTPUT: LOTO/thermal injection, PPE enforcement, blocklist on LLM text.
    gate = apply_safety_gate(
        priority      = risk.get("priority", "None"),
        action_code   = risk.get("action_code", "MONITOR"),
        warnings      = warnings,
        prescription  = enriched["prescription"],
        action_steps  = enriched["action_steps"],
        ppe_required  = enriched["ppe_required"],
        llm_generated = enriched["enriched"],
    )

    # 4b. LLM-as-judge (GH-81, optional): only for enriched output that passed
    #     rule validation; an unsafe verdict is treated exactly like a
    #     blocklist hit. Judge failure/timeout → pass (never block on it).
    judge_reasons: list[str] = []
    if not gate["blocked"] and enriched["enriched"] and _judge_enabled():
        verdict = _run_judge(warnings, gate["action_steps"])
        if verdict is not None and not verdict.get("safe", True):
            judge_reasons = [
                f"LLM judge verdict: unsafe — {verdict.get('reason', 'no reason given')}"
            ]

    # 4c. Blocked path: never deliver the LLM output — audit it, fall back to
    #     the rule-based prescription, and re-run the gate once on that output
    #     so it still gets PPE/LOTO enforcement (blocklist is off for rule
    #     text → a second block is impossible, no loop).
    blocked = gate["blocked"] or bool(judge_reasons)
    block_warnings = gate["blocked_reasons"] + judge_reasons
    if blocked:
        _audit_block(
            battery_id, risk, warnings, enriched,
            reasons=block_warnings,
            matched_patterns=gate["matched_patterns"],
            source="blocklist" if gate["blocked"] else "llm_judge",
        )
        enriched = {
            **enriched,  # keep retrieved docs + rag/llm timings
            "prescription": rule_out["prescription"],
            "action_steps": rule_out["action_steps"],
            "ppe_required": rule_out["ppe_required"],
            "enriched":     False,
            "llm_provider": "none",
        }
        gate = apply_safety_gate(
            priority      = risk.get("priority", "None"),
            action_code   = risk.get("action_code", "MONITOR"),
            warnings      = warnings,
            prescription  = enriched["prescription"],
            action_steps  = enriched["action_steps"],
            ppe_required  = enriched["ppe_required"],
            llm_generated = False,
        )

    escalation = _dedup(rule_out["escalation_conditions"] + gate["escalation_conditions"])
    safety_warnings = _dedup(gate["safety_warnings"] + block_warnings)

    # GH-83: best-effort history write of the FINAL delivered content (after the
    # blocked-path swap above, so a blocked LLM output is never persisted as if
    # it were legitimate). Only on the enrich=true path — the rule-only hot path
    # (enrich=false) must never pay for an embedding encode + ChromaDB write.
    prescription_id = ""
    if enrich:
        prescription_id = _get_history_store().save(
            context        = enriched["diagnosis"],
            battery_id     = battery_id,
            action_code    = risk.get("action_code", "MONITOR"),
            risk_level     = risk.get("risk_level", "Low"),
            llm_provider   = enriched["llm_provider"],
            prescription   = enriched["prescription"],
            action_steps   = gate["action_steps"],
            ppe_required   = gate["ppe_required"],
        ) or ""

    return {
        "battery_id":   battery_id,
        "soh_percent":  prediction.get("soh_percent", 0),
        "risk_level":   risk.get("risk_level", "Low"),
        "priority":     risk.get("priority", "None"),
        "action_code":  risk.get("action_code", "MONITOR"),

        # GH-87: nested prediction/anomaly/risk — same dicts run_inference()
        # already computed above, forwarded as-is (no extra forward pass).
        "prediction":   prediction,
        "anomaly":      anomaly,
        "risk":         risk,

        "prescription":          enriched["prescription"],
        "action_steps":          gate["action_steps"],   # post-validation (GH-81 injection)
        "escalation_conditions": escalation,
        "ppe_required":          gate["ppe_required"],   # post-validation (GH-81 PPE union)
        "sop_references":        rule_out["sop_references"],
        "enriched":              enriched["enriched"],
        "llm_provider":          enriched["llm_provider"],
        "prescription_id":       prescription_id,

        "maintenance_docs": enriched["maintenance_docs"],
        "safety_docs":      enriched["safety_docs"],

        "human_verification_required": gate["human_verification_required"] or blocked,
        "safety_warnings":             safety_warnings,
        "blocked":                     blocked,

        "inference_ms": inference_ms,
        "rag_ms":       enriched["rag_ms"],
        "llm_ms":       enriched["llm_ms"],
        "query_gen_ms": enriched["query_gen_ms"],
        "generated_queries": enriched["generated_queries"],
        "chain_attempted":   enriched.get("chain_attempted", []),
    }


def run_prescription(
    readings: list[list[float]],
    battery_id: str,
    enrich: bool = False,
    n_series: int = 1,
    agentic: bool = False,
    **context_kwargs,
) -> dict:
    """
    GH-84: idempotency-cached wrapper around _run_prescription_uncached().

    Same signature/return shape, plus a "cached" bool field. A hit within the
    TTL (key = hash of battery_id/readings/enrich/agentic/ticket_history) short-circuits
    inference/RAG/LLM entirely and returns the exact prior response. A
    blocked=True result is never cached — it must be re-evaluated every call.
    """
    observability.record_prescribe()
    key = observability.cache_key(
        battery_id, readings, enrich, agentic, context_kwargs.get("ticket_history")
    )
    t_total = time.perf_counter()

    cached = observability.cache_get(key)
    if cached is not None:
        observability.record_cache_hit()
        response = {**cached, "cached": True}
    else:
        observability.record_cache_miss()
        response = _run_prescription_uncached(
            readings,
            battery_id,
            enrich=enrich,
            n_series=n_series,
            agentic=agentic,
            **context_kwargs,
        )
        response["cached"] = False
        if response["blocked"]:
            observability.record_blocked()
        else:
            observability.cache_set(key, response)
        if response["enriched"]:
            observability.record_enrich_success()
        observability.record_fallback_tiers(response["chain_attempted"])

    logger.info(
        "prescribe battery_id=%s enrich=%s llm_provider=%s chain_attempted=%s "
        "rag_ms=%s llm_ms=%s total_ms=%s cached=%s blocked=%s",
        battery_id,
        enrich,
        response["llm_provider"],
        response["chain_attempted"],
        response["rag_ms"],
        response["llm_ms"],
        round((time.perf_counter() - t_total) * 1000, 2),
        response["cached"],
        response["blocked"],
    )
    return response


def submit_prescription_feedback(
    prescription_id: str,
    status: str,
    edited_steps: list[str] | None = None,
    note: str | None = None,
) -> bool:
    """
    GH-83: record technician feedback (accepted/edited/rejected) for a
    previously saved prescription. Returns False when the history store is
    unavailable or prescription_id doesn't exist — POST /prescribe/feedback
    maps False to a 404.
    """
    return _get_history_store().update_feedback(prescription_id, status, edited_steps, note)
