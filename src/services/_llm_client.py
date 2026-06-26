"""
Anthropic LLM client for the prescription enrichment layer.

Isolated from the orchestrator (prescription.py) so the network/SDK concern
stays in one place and is easy to mock in tests. The model is Claude Haiku 4.5
— chosen for low latency/cost on the non-critical (P2/P3) enrichment path; P1
never reaches here (see prescription.py routing).

Design constraints (see docs/prescription-layer.md):
  - Structured output: the model MUST return a JSON object matching PRESCRIPTION_SCHEMA.
  - Grounding: the prompt forbids using anything outside the retrieved docs.
  - Graceful degradation: any failure (no key, SDK missing, timeout, bad output)
    returns None, and the caller falls back to the deterministic rule baseline.
"""
import json
import os

# Claude Haiku 4.5 — low-latency/cost tier for the off-hot-path enrichment.
LLM_MODEL = "claude-haiku-4-5"
LLM_MAX_TOKENS = 512
LLM_TIMEOUT_S = 8.0   # bounded — enrichment is off the P1 hot path but must not hang
LLM_MAX_RETRIES = 1

# Structured-output schema — the API guarantees the response matches this.
PRESCRIPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "prescription":  {"type": "string"},
        "action_steps":  {"type": "array", "items": {"type": "string"}},
        "ppe_required":  {"type": "array", "items": {"type": "string"}},
    },
    "required": ["prescription", "action_steps", "ppe_required"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = (
    "You are a battery-maintenance assistant for a solar lithium-ion monitoring "
    "system. You ENRICH a deterministic rule-based maintenance prescription with "
    "clearer prose and any additional steps justified by the retrieved knowledge "
    "documents.\n\n"
    "STRICT RULES:\n"
    "1. Use ONLY the information in the retrieved documents below. Do NOT invent "
    "procedures, thresholds, or part numbers not present in them.\n"
    "2. If the documents do not support a richer prescription, return the rule "
    "baseline text unchanged.\n"
    "3. Never weaken or remove a safety step. You may only add.\n"
    "4. Keep action_steps concrete and ordered."
)


def _format_docs(docs: list[dict]) -> str:
    if not docs:
        return "(none)"
    return "\n\n".join(
        f"[{d.get('source', '?')}] {d.get('title', '')}\n{d.get('content', '')}"
        for d in docs
    )


def _build_user_prompt(
    context: str,
    rule_baseline: dict,
    maintenance_docs: list[dict],
    safety_docs: list[dict],
) -> str:
    return (
        f"BATTERY CONTEXT:\n{context}\n\n"
        f"RULE BASELINE (do not weaken):\n"
        f"- prescription: {rule_baseline.get('prescription', '')}\n"
        f"- action_steps: {json.dumps(rule_baseline.get('action_steps', []))}\n"
        f"- ppe_required: {json.dumps(rule_baseline.get('ppe_required', []))}\n\n"
        f"RETRIEVED MAINTENANCE DOCS:\n{_format_docs(maintenance_docs)}\n\n"
        f"RETRIEVED SAFETY DOCS:\n{_format_docs(safety_docs)}\n\n"
        "Return the enriched prescription as JSON matching the required schema."
    )


def call_structured_prescription(
    context: str,
    rule_baseline: dict,
    maintenance_docs: list[dict],
    safety_docs: list[dict],
) -> dict | None:
    """
    Call Claude Haiku 4.5 for a structured, doc-grounded prescription.

    Returns a dict with keys {prescription, action_steps, ppe_required} on success,
    or None on any failure (missing key, SDK not installed, API error, timeout, or
    malformed output) so the caller can fall back to the rule baseline.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None

    client = anthropic.Anthropic().with_options(
        timeout=LLM_TIMEOUT_S, max_retries=LLM_MAX_RETRIES
    )

    try:
        response = client.messages.create(
            model=LLM_MODEL,
            max_tokens=LLM_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": _build_user_prompt(
                    context, rule_baseline, maintenance_docs, safety_docs
                ),
            }],
            output_config={"format": {"type": "json_schema", "schema": PRESCRIPTION_SCHEMA}},
        )
    except anthropic.APIError:
        return None
    except Exception:
        # Defensive: never let an LLM/transport error break the prescription path.
        return None

    # output_config.format guarantees the first text block is schema-valid JSON.
    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(data.get("prescription"), str):
        return None
    return {
        "prescription": data["prescription"],
        "action_steps": [str(s) for s in data.get("action_steps", [])],
        "ppe_required": [str(s) for s in data.get("ppe_required", [])],
    }
