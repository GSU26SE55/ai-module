"""
Anthropic Claude client for the optional /prescribe enrichment.

Only imported on the enrich path (enrich=true). Returns a structured prescription
via forced tool-use. Raises on any failure so the caller can fall back to the
deterministic rule-based prescription — the endpoint must never crash on LLM error.

Config (env):
  ANTHROPIC_API_KEY  — required to enrich; if missing, enrichment is skipped.
  ANTHROPIC_MODEL    — optional override (default: claude-haiku-4-5-20251001).
"""
import os

# Default to Claude Haiku 4.5 — cheap/fast, sufficient for short structured output.
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 512
TIMEOUT_S = 10.0
MAX_RETRIES = 1

_SYSTEM_PROMPT = (
    "You are a battery maintenance assistant for a solar lithium-ion storage system. "
    "Generate a concise, actionable maintenance prescription. "
    "STRICT RULES:\n"
    "1. Use ONLY information supported by the retrieved documents provided below. "
    "Do NOT invent procedures, thresholds, part numbers, or safety steps.\n"
    "2. If the retrieved documents do not cover the situation, say so explicitly and "
    "recommend escalating to a qualified technician.\n"
    "3. Never recommend touching a battery under a critical electrical or thermal warning "
    "without Lockout/Tagout and human verification.\n"
    "4. Keep action_steps short and imperative."
)

_TOOL = {
    "name": "emit_prescription",
    "description": "Return the structured maintenance prescription.",
    "input_schema": {
        "type": "object",
        "properties": {
            "prescription": {
                "type": "string",
                "description": "1-3 sentence maintenance recommendation grounded in the retrieved docs.",
            },
            "action_steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ordered, imperative maintenance steps.",
            },
            "ppe_required": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Required personal protective equipment.",
            },
        },
        "required": ["prescription", "action_steps", "ppe_required"],
    },
}


def is_available() -> bool:
    """True if an API key is configured (enrichment possible)."""
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _format_docs(label: str, docs: list[dict]) -> str:
    if not docs:
        return f"{label}: (none retrieved)"
    lines = [f"{label}:"]
    for d in docs:
        src = d.get("source", "unknown")
        content = d.get("content", "").strip()
        lines.append(f"- [{src}] {content}")
    return "\n".join(lines)


def generate_prescription_llm(
    context: str,
    maintenance_docs: list[dict],
    safety_docs: list[dict],
    model: str | None = None,
) -> dict:
    """
    Call Claude to generate a structured prescription.

    Returns dict with keys: prescription, action_steps, ppe_required.
    Raises RuntimeError on missing key / API error / malformed output — caller MUST
    catch and fall back to the rule-based prescription.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set — cannot enrich.")

    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("anthropic SDK not installed.") from exc

    user_content = (
        f"Battery assessment:\n{context}\n\n"
        f"{_format_docs('Retrieved maintenance documents', maintenance_docs)}\n\n"
        f"{_format_docs('Retrieved safety documents', safety_docs)}\n\n"
        "Produce the prescription using the emit_prescription tool."
    )

    client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_S, max_retries=MAX_RETRIES)
    try:
        resp = client.messages.create(
            model=model or os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL),
            max_tokens=MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "emit_prescription"},
            messages=[{"role": "user", "content": user_content}],
        )
    except Exception as exc:  # anthropic.APIError, timeouts, etc.
        raise RuntimeError(f"Anthropic API call failed: {exc}") from exc

    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            out = block.input
            if not isinstance(out, dict) or "prescription" not in out:
                raise RuntimeError("LLM returned malformed tool output.")
            return {
                "prescription": str(out.get("prescription", "")),
                "action_steps": list(out.get("action_steps", [])),
                "ppe_required": list(out.get("ppe_required", [])),
            }

    raise RuntimeError("LLM response contained no tool_use block.")
