"""
Shared interface + prompt/schema contract for all LLM providers used by the
optional /prescribe enrichment (enrich=true). Providers are tried in order by
src.services.llm.chain — this module defines what every provider must return
and the grounding rules every provider must enforce, so behavior stays
provider-agnostic from prescription.py's point of view.
"""
from abc import ABC, abstractmethod

TIMEOUT_S = 10.0
MAX_RETRIES = 1

SYSTEM_PROMPT = (
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

# Tool/function name + JSON schema shared by every provider (Anthropic forced
# tool-use, DeepSeek OpenAI-style function calling, Gemini response_schema all
# target this same shape so prescription.py never has to branch on which
# provider answered).
TOOL_NAME = "emit_prescription"
TOOL_DESCRIPTION = "Return the structured maintenance prescription."
RESPONSE_SCHEMA = {
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
}


def format_docs(label: str, docs: list[dict]) -> str:
    """Render retrieved docs as plain text for the user message — shared by every provider."""
    if not docs:
        return f"{label}: (none retrieved)"
    lines = [f"{label}:"]
    for d in docs:
        src = d.get("source", "unknown")
        content = d.get("content", "").strip()
        lines.append(f"- [{src}] {content}")
    return "\n".join(lines)


def build_user_content(context: str, maintenance_docs: list[dict], safety_docs: list[dict]) -> str:
    """Shared user message body — identical across providers."""
    return (
        f"Battery assessment:\n{context}\n\n"
        f"{format_docs('Retrieved maintenance documents', maintenance_docs)}\n\n"
        f"{format_docs('Retrieved safety documents', safety_docs)}\n\n"
        f"Produce the prescription using the {TOOL_NAME} tool."
    )


class LLMProvider(ABC):
    """Common contract every LLM provider (Anthropic/DeepSeek/Gemini) implements.

    Providers raise RuntimeError on any failure (missing key, SDK error, timeout,
    malformed output) — src.services.llm.chain catches it and tries the next tier.
    """

    name: str

    @abstractmethod
    def is_available(self) -> bool:
        """True if this provider has the credentials needed to be tried."""

    @abstractmethod
    def generate_prescription(
        self,
        context: str,
        maintenance_docs: list[dict],
        safety_docs: list[dict],
    ) -> dict:
        """
        Returns dict with keys: prescription (str), action_steps (list[str]),
        ppe_required (list[str]). Raises RuntimeError on any failure.
        """
