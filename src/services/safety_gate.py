"""
Safety gate — blocks or flags unsafe prescriptions before delivery.

Rules (from overall.md §13):
  - P1 always requires human_verification_required = True
  - Any thermal/fire warning → add escalation condition
  - action_code REPLACE_IMMEDIATELY → require technician sign-off
"""


ALWAYS_REQUIRE_HUMAN = {"P1", "REPLACE_IMMEDIATELY"}

THERMAL_KEYWORDS = {"thermal", "fire", "temp_critical", "temp_elevated", "runaway", "smoke"}
# TEMP_CRITICAL → human_required=True; TEMP_ELEVATED → warning only (see logic below)
ELECTRICAL_KEYWORDS = {"voltage_critical", "overcurrent_critical", "electrocution"}


def apply_safety_gate(
    priority: str,
    action_code: str,
    warnings: list[dict],
    prescription: str,
) -> dict:
    """
    Evaluate safety constraints and return gate result.

    Returns:
        {
            "human_verification_required": bool,
            "safety_warnings": list[str],
            "escalation_conditions": list[str],
            "blocked": bool,   # True = do NOT deliver to frontend without human review
        }
    """
    human_required = priority in ALWAYS_REQUIRE_HUMAN or action_code in ALWAYS_REQUIRE_HUMAN
    safety_warnings = []
    escalation_conditions = []

    warning_codes = {w.get("code", "").lower() for w in warnings}

    if warning_codes & {"temp_critical", "thermal", "fire", "runaway", "smoke"}:
        human_required = True
        safety_warnings.append("Critical thermal risk — follow thermal runaway SOP before any work")
        escalation_conditions.append("Critical thermal warning: escalate to P1 immediately")
    elif "temp_elevated" in warning_codes:
        # Moderate thermal risk — warn but don't block
        safety_warnings.append("Elevated temperature detected — increase ventilation, monitor closely")

    if warning_codes & ELECTRICAL_KEYWORDS:
        human_required = True
        safety_warnings.append("Critical electrical hazard — complete LOTO before touching battery")

    if action_code == "REPLACE_IMMEDIATELY":
        escalation_conditions.append("Immediate replacement required — notify manager within 1 hour")

    # Placeholder: LLM safety check (future)
    # if _llm_detects_unsafe_content(prescription):
    #     return {"blocked": True, ...}

    return {
        "human_verification_required": human_required,
        "safety_warnings": safety_warnings,
        "escalation_conditions": escalation_conditions,
        "blocked": False,
    }
