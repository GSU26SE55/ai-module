"""
Shared interface + prompt/schema contract for all LLM providers used by the
optional /prescribe enrichment (enrich=true). Providers are tried in order by
src.services.prescription.llm.chain — this module defines what every provider
must return and the grounding rules every provider must enforce, so behavior
stays provider-agnostic from orchestrator.py's point of view.
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
    "4. Keep action_steps short and imperative.\n"
    "5. Past resolved cases (if provided) are for reference only, to see how similar "
    "situations were handled before. They are NOT authoritative — when a past case "
    "conflicts with the retrieved documents, always prioritize the retrieved documents."
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


# ── Query generation (GH-82, agentic chain step 2) ──────────────────────
# Same structured-output mechanism as the prescription call. The LLM turns a
# diagnosis statement into focused KB search queries (Deng et al. 2024 §3.2).
QUERYGEN_TOOL_NAME = "emit_search_queries"
QUERYGEN_TOOL_DESCRIPTION = "Return knowledge-base search queries for the diagnosis."
QUERYGEN_SCHEMA = {
    "type": "object",
    "properties": {
        "maintenance_queries": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "2-4 short English search queries about lithium battery "
                "maintenance procedures relevant to the diagnosis."
            ),
        },
        "safety_queries": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "1-2 short English search queries about safety hazards or "
                "precautions relevant to the diagnosis."
            ),
        },
    },
    "required": ["maintenance_queries", "safety_queries"],
}

QUERYGEN_SYSTEM_PROMPT = (
    "You are a retrieval query planner for a solar lithium-ion battery "
    "maintenance knowledge base. Given a diagnosis statement, generate focused "
    "search queries that would retrieve the most relevant maintenance "
    "procedures and safety documents. "
    "RULES: 3-5 queries total (2-4 maintenance + 1-2 safety); each query under "
    "15 words; English only; specific to the diagnosed condition (e.g. "
    "'capacity fade inspection schedule for degrading battery'), never generic "
    "('battery maintenance')."
)


def build_querygen_content(diagnosis: str) -> str:
    """Shared query-gen user message — identical across providers."""
    return (
        f"Diagnosis statement:\n{diagnosis}\n\n"
        f"Generate the search queries using the {QUERYGEN_TOOL_NAME} tool."
    )


# ── LLM-as-judge (GH-81) ────────────────────────────────────────────────
# Same structured-output mechanism as the prescription call, shared by every
# provider so the verdict shape is provider-agnostic.
JUDGE_TOOL_NAME = "emit_safety_verdict"
JUDGE_TOOL_DESCRIPTION = "Return the safety verdict for the proposed maintenance steps."
JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "safe": {
            "type": "boolean",
            "description": "True if every step is safe to execute given the active warnings.",
        },
        "reason": {
            "type": "string",
            "description": "One-sentence justification, citing the unsafe step if any.",
        },
    },
    "required": ["safe", "reason"],
}

JUDGE_SYSTEM_PROMPT = (
    "You are a battery-safety reviewer for a solar lithium-ion storage system. "
    "Given the battery's active warning state and a proposed list of maintenance "
    "action steps, judge whether the steps are safe to execute. "
    "Steps are UNSAFE if they involve opening or disassembling cells/casings, "
    "short-circuiting the battery, using water on a lithium fire, physical work "
    "while the battery is charging, or skipping Lockout/Tagout under a critical "
    "electrical warning. When uncertain, answer safe=false and state your concern."
)


def build_judge_content(context: str, action_steps: list[str]) -> str:
    """Shared judge user message — identical across providers."""
    steps = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(action_steps))
    return (
        f"Battery warning state:\n{context}\n\n"
        f"Proposed maintenance steps:\n{steps}\n\n"
        f"Are these steps safe for this warning state? "
        f"Answer with the {JUDGE_TOOL_NAME} tool."
    )


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


# ── Long-term memory (GH-83) ─────────────────────────────────────────────
def format_past_cases(past_cases: list[dict]) -> str:
    """
    Render accepted past prescriptions as a reference-only section — shared by
    every provider. Returns "" (omitted from the prompt entirely) when there
    are no past cases, so history-less deployments never change the prompt.
    """
    if not past_cases:
        return ""
    lines = ["Past resolved cases (reference only, prioritize the retrieved documents above):"]
    for case in past_cases:
        steps = "; ".join(case.get("action_steps", []))
        lines.append(
            f"- [{case.get('risk_level', 'Unknown')}/{case.get('action_code', 'Unknown')}] "
            f"{case.get('prescription', '')} Steps: {steps}"
        )
    return "\n".join(lines)


def build_user_content(
    context: str,
    maintenance_docs: list[dict],
    safety_docs: list[dict],
    past_cases: list[dict] | None = None,
) -> str:
    """Shared user message body — identical across providers."""
    past_cases_section = format_past_cases(past_cases or [])
    return (
        f"Battery assessment:\n{context}\n\n"
        f"{format_docs('Retrieved maintenance documents', maintenance_docs)}\n\n"
        f"{format_docs('Retrieved safety documents', safety_docs)}\n\n"
        + (f"{past_cases_section}\n\n" if past_cases_section else "")
        + f"Produce the prescription using the {TOOL_NAME} tool."
    )


class LLMProvider(ABC):
    """Common contract every LLM provider (Anthropic/DeepSeek/Gemini) implements.

    Providers raise RuntimeError on any failure (missing key, SDK error, timeout,
    malformed output) — src.services.prescription.llm.chain catches it and tries the next tier.
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
        past_cases: list[dict] | None = None,
    ) -> dict:
        """
        Returns dict with keys: prescription (str), action_steps (list[str]),
        ppe_required (list[str]). Raises RuntimeError on any failure.

        past_cases (GH-83): accepted past prescriptions retrieved as few-shot
        context — reference only, empty/None when history has no accepted match.
        """

    @abstractmethod
    def judge_safety(self, context: str, action_steps: list[str]) -> dict:
        """
        GH-81 LLM-as-judge: rate whether the generated steps are safe for the
        given warning state. Returns dict with keys: safe (bool), reason (str).
        Raises RuntimeError on any failure — the chain catches it and tries the
        next tier; the orchestrator treats a fully-failed chain as "pass".
        """

    @abstractmethod
    def generate_queries(self, diagnosis: str) -> dict:
        """
        GH-82 agentic step 2: turn a diagnosis statement into KB search
        queries. Returns dict with keys: maintenance_queries (list[str]),
        safety_queries (list[str]). Raises RuntimeError on any failure — the
        chain catches it; the orchestrator falls back to the template query.
        """
