"""
Safety gate — blocks or flags unsafe prescriptions before delivery.

v1 rules (input gating, from overall.md §13):
  - P1 always requires human_verification_required = True
  - Any thermal/fire warning → add escalation condition
  - action_code REPLACE_IMMEDIATELY → require technician sign-off

v2 rules (GH-81, output validation — deterministic, no network):
  - Electrical-critical warning + steps missing LOTO → inject the standard
    LOTO step at the front of action_steps (not a silent pass — a
    safety_warning records the injection)
  - Thermal-critical warning + steps missing containment (evacuation/
    ventilation/isolation) → inject the thermal-runaway-SOP step
  - PPE enforcement per knowledge/safety/ppe_matrix.md — missing mandatory
    PPE is unioned in (extends the existing rule-PPE union mechanism)
  - Blocklist of forbidden actions, LLM output only (llm_generated=True) →
    blocked=True; the caller must discard the LLM output and fall back to
    the rule-based prescription. Blocklist is negation-aware: "do NOT use
    water" is standard safe wording from the KB and must not match.

Pure function — no logging or network side effects. The orchestrator owns
the blocked-path swap and audit logging, so the hot path and unit tests
stay deterministic.
"""
import re

from src.services.prescription.rule_prescription import (
    _ARC_FLASH_PPE,
    _BASE_PPE,
    _ELECTRICAL_CRITICAL,
    _WARNING_STEPS,
)

ALWAYS_REQUIRE_HUMAN = {"P1", "REPLACE_IMMEDIATELY"}

THERMAL_KEYWORDS = {"thermal", "fire", "temp_critical", "temp_elevated", "runaway", "smoke"}
# TEMP_CRITICAL → human_required=True; TEMP_ELEVATED → warning only (see logic below)
# NOTE: matched against w["code"].lower(); BMS emits OVERVOLTAGE_CRITICAL → overvoltage_critical
ELECTRICAL_KEYWORDS = {"voltage_critical", "overvoltage_critical", "overcurrent_critical", "electrocution"}

_THERMAL_CRITICAL = {"temp_critical", "thermal", "fire", "runaway", "smoke"}

# ── v2 output validation (GH-81) ────────────────────────────────────────

# Standard LOTO step — same wording as the REPLACE_IMMEDIATELY rule template
# (rule_prescription.py), grounded in electrical_safety_sop.md.
LOTO_STEP = "Isolate the battery from the system using the Lockout/Tagout procedure."
# Thermal containment step — reuse the rule step grounded in thermal_runaway_response.md.
THERMAL_SOP_STEP = _WARNING_STEPS["TEMP_CRITICAL"]

_LOTO_PRESENT_RE = re.compile(r"loto|lock[\s-]?out|tag[\s-]?out", re.IGNORECASE)
_THERMAL_PRESENT_RE = re.compile(r"evacuat|exclusion|ventilat|isolat", re.IGNORECASE)

# Mandatory PPE per hazard — grounded in knowledge/safety/ppe_matrix.md.
# Thermal critical intentionally adds NO PPE: ppe_matrix.md — "no PPE
# substitutes for evacuation"; the containment-step injection covers it.
_STEEL_TOED_PPE = "Steel-toed footwear"
_IR_THERMOMETER_PPE = "Infrared thermometer for standoff checks"

# A banned match only counts when NOT preceded by a negation in the same
# step — the KB and rule templates legitimately say "do NOT use water".
_NEGATION_RE = re.compile(r"\b(?:not|don'?t|never|avoid|prevent)\b", re.IGNORECASE)

# Forbidden actions in LLM output (case-insensitive EN): open/disassemble a
# cell or casing, short-circuit the battery, water on a lithium fire,
# physical work while charging.
_BANNED_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "open/disassemble battery cell or casing",
        re.compile(
            r"\b(?:open(?:ing)?|disassembl\w*|dismantl\w*|punctur\w*|pierc\w*|remov\w*)\b"
            r"[^.;]{0,40}\b(?:cell|casing|housing|enclosure)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "short-circuit the battery",
        re.compile(
            r"\bshort(?:[\s-]?circuit\w*|ing)?\s+the\s+(?:battery|cells?|terminals?|pack)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "use water on lithium fire",
        re.compile(
            r"\b(?:use|using|spray\w*|apply\w*|douse\w*|pour\w*|extinguish\w*\s+with)\b"
            r"[^.;]{0,30}\bwater\b",
            re.IGNORECASE,
        ),
    ),
    (
        "physical work while battery is charging",
        re.compile(r"\b(?:while|during)\s+(?:the\s+battery\s+is\s+)?charging\b", re.IGNORECASE),
    ),
]


def _dedup(items: list[str]) -> list[str]:
    """Order-preserving de-duplication (same semantics as orchestrator._dedup)."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _find_banned(texts: list[str]) -> list[str]:
    """Return labels of banned patterns matched (negation-aware) in any text."""
    matched: list[str] = []
    for label, pattern in _BANNED_PATTERNS:
        for text in texts:
            m = pattern.search(text)
            if m is None:
                continue
            # Negation only counts within the same sentence as the match.
            sentence_prefix = re.split(r"[.;]", text[: m.start()])[-1]
            if not _NEGATION_RE.search(sentence_prefix):
                matched.append(label)
                break
    return matched


def apply_safety_gate(
    priority: str,
    action_code: str,
    warnings: list[dict],
    prescription: str,
    action_steps: list[str] | None = None,
    ppe_required: list[str] | None = None,
    llm_generated: bool = False,
) -> dict:
    """
    Evaluate safety constraints and return gate result.

    v1 input gating always runs. v2 output validation (inject/union/blocklist)
    runs only when action_steps is provided; the blocklist additionally
    requires llm_generated=True (rule-based text is under our control).

    Returns:
        {
            "human_verification_required": bool,
            "safety_warnings": list[str],
            "escalation_conditions": list[str],
            "blocked": bool,   # True = do NOT deliver to frontend without human review
            "blocked_reasons": list[str],   # banned-pattern labels (empty unless blocked)
            "matched_patterns": list[str],  # pattern labels that matched (audit)
            "action_steps": list[str],      # validated steps (LOTO/thermal injected)
            "ppe_required": list[str],      # unioned with mandatory PPE
        }
    """
    human_required = priority in ALWAYS_REQUIRE_HUMAN or action_code in ALWAYS_REQUIRE_HUMAN
    safety_warnings = []
    escalation_conditions = []

    warning_codes = {w.get("code", "").lower() for w in warnings}

    if warning_codes & _THERMAL_CRITICAL:
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

    # ── v2 output validation (GH-81) ────────────────────────────────────
    blocked = False
    blocked_reasons: list[str] = []
    matched_patterns: list[str] = []
    out_steps = list(action_steps) if action_steps is not None else []
    out_ppe = list(ppe_required) if ppe_required is not None else []

    if action_steps is not None:
        has_electrical = bool({c.upper() for c in warning_codes} & _ELECTRICAL_CRITICAL)
        has_thermal_critical = bool(warning_codes & _THERMAL_CRITICAL)

        # 1. Blocklist — LLM output only. Rule text is under our control and
        #    legitimately contains phrases like "do NOT use water".
        if llm_generated:
            matched_patterns = _find_banned([prescription, *out_steps])
            if matched_patterns:
                blocked = True
                human_required = True
                blocked_reasons = [
                    f"Forbidden action in generated output: {p}" for p in matched_patterns
                ]
                safety_warnings.extend(blocked_reasons)

        # 2. LOTO / thermal step injection — skipped when blocked (the output
        #    is discarded by the caller anyway).
        if not blocked:
            if has_electrical and not any(_LOTO_PRESENT_RE.search(s) for s in out_steps):
                out_steps.insert(0, LOTO_STEP)
                safety_warnings.append(
                    "Generated steps lacked Lockout/Tagout — standard LOTO step injected"
                )
            if has_thermal_critical and not any(_THERMAL_PRESENT_RE.search(s) for s in out_steps):
                insert_at = 1 if out_steps[:1] == [LOTO_STEP] else 0
                out_steps.insert(insert_at, THERMAL_SOP_STEP)
                safety_warnings.append(
                    "Generated steps lacked thermal containment — thermal runaway SOP step injected"
                )

            # 3. PPE enforcement — union mandatory PPE per ppe_matrix.md.
            mandatory_ppe: list[str] = []
            if has_electrical:
                mandatory_ppe += [*_BASE_PPE, _ARC_FLASH_PPE, _STEEL_TOED_PPE]
            if "temp_elevated" in warning_codes and not has_thermal_critical:
                mandatory_ppe += [*_BASE_PPE, _IR_THERMOMETER_PPE]
            if action_code == "REPLACE_IMMEDIATELY":
                mandatory_ppe += [*_BASE_PPE, _STEEL_TOED_PPE]
            missing = _dedup([p for p in mandatory_ppe if p not in out_ppe])
            if missing:
                out_ppe = _dedup(out_ppe + missing)
                safety_warnings.append(
                    "Mandatory PPE missing from generated output — enforced per PPE matrix: "
                    + ", ".join(missing)
                )

    return {
        "human_verification_required": human_required,
        "safety_warnings": safety_warnings,
        "escalation_conditions": escalation_conditions,
        "blocked": blocked,
        "blocked_reasons": blocked_reasons,
        "matched_patterns": matched_patterns,
        "action_steps": out_steps,
        "ppe_required": out_ppe,
    }
