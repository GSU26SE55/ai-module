"""
Rule-based prescription — deterministic decision table.

Default path for POST /prescribe (always runs, <100ms, NO external dependencies).
Maps (action_code, risk_level, warning_codes) -> structured maintenance prescription.

This is the fallback whenever the optional LLM+RAG enrichment is disabled or fails,
so the endpoint always returns a safe, actionable result.

Knowledge grounding (see knowledge/):
  - thresholds & steps: knowledge/maintenance/battery_maintenance_sop.md
  - warning semantics:  knowledge/maintenance/bms_warning_codes.md
  - PPE / LOTO:         knowledge/safety/electrical_safety_sop.md
  - thermal response:   knowledge/safety/thermal_runaway_response.md
"""

# action_code -> base prescription template
_ACTION_TEMPLATES: dict[str, dict] = {
    "REPLACE_IMMEDIATELY": {
        "summary": "Battery has reached end-of-life — immediate replacement required.",
        "steps": [
            "Isolate the battery from the system using the Lockout/Tagout procedure.",
            "Measure open-circuit voltage and surface temperature before removal.",
            "Replace with a unit of identical specification per the maintenance SOP §3.",
            "Record final SOH, anomaly status, and replacement reason in the ticket.",
        ],
        "sop_references": [
            "battery_maintenance_sop §3 (Replacement Criteria)",
            "electrical_safety_sop (LOTO + isolation)",
        ],
        "escalation_conditions": ["Immediate replacement required — notify manager within 1 hour."],
    },
    "SCHEDULE_REPLACEMENT": {
        "summary": "Battery is degrading — schedule replacement within 7 days.",
        "steps": [
            "Plan a replacement window within 7 days and order a matching unit.",
            "Run a full capacity test to confirm remaining usable capacity.",
            "Monitor SOH and temperature trend until replacement.",
            "Open or update the maintenance ticket with the scheduled date.",
        ],
        "sop_references": ["battery_maintenance_sop §1, §3"],
        "escalation_conditions": [
            "If SOH drops below 80% before the scheduled date, escalate to immediate replacement.",
        ],
    },
    "SCHEDULE_MAINTENANCE": {
        "summary": "Battery shows early degradation — schedule inspection within 30 days.",
        "steps": [
            "Schedule a monthly inspection per the maintenance SOP.",
            "Check internal resistance against baseline (>50% rise is a replacement trigger).",
            "Verify ventilation and operating temperature are within limits.",
            "Log inspection results for AI re-evaluation.",
        ],
        "sop_references": ["battery_maintenance_sop §1, §2"],
        "escalation_conditions": [
            "If a critical warning appears before the inspection, raise the priority.",
        ],
    },
    "MONITOR": {
        "summary": "Battery is operating normally — continue routine monitoring.",
        "steps": [
            "Continue scheduled quarterly inspections.",
            "Keep logging SOH and sensor readings for trend analysis.",
            "No immediate physical action required.",
        ],
        "sop_references": ["battery_maintenance_sop §1"],
        "escalation_conditions": [],
    },
}

# Fallback when an unknown action_code is received.
_DEFAULT_ACTION = "MONITOR"

# Base PPE for any procedure that involves physical contact with the battery.
_BASE_PPE = ["Insulated gloves (>=500V)", "Safety glasses (ANSI Z87.1)"]
_ARC_FLASH_PPE = "Arc-flash rated clothing"

# Warning codes that imply a critical electrical hazard -> LOTO + arc-flash PPE.
_ELECTRICAL_CRITICAL = {"VOLTAGE_CRITICAL", "OVERVOLTAGE_CRITICAL", "OVERCURRENT_CRITICAL"}

# Per-warning extra step (grounded in bms_warning_codes.md).
_WARNING_STEPS: dict[str, str] = {
    "TEMP_CRITICAL": (
        "Critical temperature: stop operation, follow the thermal runaway response SOP "
        "(evacuate, 50m exclusion, do NOT use water)."
    ),
    "TEMP_ELEVATED": "Elevated temperature: increase ventilation and reduce charge/discharge rate.",
    "VOLTAGE_CRITICAL": "Voltage critical (<3.0V): stop discharge immediately — risk of cell damage.",
    "OVERVOLTAGE_CRITICAL": "Overvoltage critical (>4.2V): stop charging immediately — overcharge risk.",
    "OVERCURRENT_CRITICAL": "Overcurrent critical: emergency load disconnect; keep load within 1C.",
}


def build_rule_prescription(prediction: dict, risk: dict, warnings: list[dict]) -> dict:
    """
    Deterministic prescription from structured prediction output.

    Args:
        prediction: the "prediction" block from run_inference (soh_percent, health_stage, ...).
        risk:       the "risk" block (risk_level, priority, action_code).
        warnings:   list of {"code": str, ...} from evidence.warnings.

    Returns:
        dict with: prescription, action_steps, ppe_required, escalation_conditions,
                   sop_references.
    """
    action_code = risk.get("action_code", _DEFAULT_ACTION)
    template = _ACTION_TEMPLATES.get(action_code, _ACTION_TEMPLATES[_DEFAULT_ACTION])

    soh = prediction.get("soh_percent", 0.0)
    codes = [w.get("code", "") for w in warnings]

    # Steps: base action steps + one extra step per recognised warning (stable order).
    action_steps = list(template["steps"])
    extra_steps = [_WARNING_STEPS[c] for c in _WARNING_STEPS if c in codes]
    action_steps.extend(extra_steps)

    # PPE: base for any physical action (everything except pure MONITOR), arc-flash if electrical hazard.
    ppe: list[str] = []
    if action_code != "MONITOR":
        ppe.extend(_BASE_PPE)
    if any(c in _ELECTRICAL_CRITICAL for c in codes):
        ppe.append(_ARC_FLASH_PPE)

    # Escalation: template escalation + thermal/electrical specifics.
    escalation = list(template["escalation_conditions"])
    if "TEMP_CRITICAL" in codes:
        escalation.append("Critical thermal warning — escalate to P1 immediately.")
    if any(c in _ELECTRICAL_CRITICAL for c in codes):
        escalation.append("Critical electrical hazard — complete LOTO before any contact.")

    prescription = (
        f"{template['summary']} Current SOH {soh:.1f}%, risk {risk.get('risk_level', 'Low')}, "
        f"priority {risk.get('priority', 'None')}."
    )
    if codes:
        prescription += f" Active warnings: {', '.join(codes)}."

    return {
        "prescription": prescription,
        "action_steps": action_steps,
        "ppe_required": ppe,
        "escalation_conditions": escalation,
        "sop_references": list(template["sop_references"]),
    }
