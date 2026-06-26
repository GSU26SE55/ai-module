"""
Rule-based prescription engine — the deterministic DEFAULT + FALLBACK of the
hybrid prescription layer.

Maps the structured prediction (action_code, risk_level, warning codes) to a
maintenance prescription WITHOUT any external dependency or network call:

    action_code        → base prescription text + action steps + PPE
    warning code       → extra safety/action steps (appended, deduped)
    critical hazard    → PPE escalation

Always runs in well under 100ms, so it is safe to call on the P1 critical path.
The LLM+RAG layer (see prescription.py) only *enriches* this baseline; if the
LLM is unavailable or fails, this output is returned verbatim.

Thresholds and warning codes mirror src/models/anomaly_detector.py — keep them
in sync if the anomaly logic changes.
"""

# ── Base prescription per action_code ───────────────────────────────────────
# Each entry: prescription prose + ordered action steps + baseline PPE.
_ACTION_TABLE: dict[str, dict] = {
    "REPLACE_IMMEDIATELY": {
        "prescription": (
            "Battery has reached end-of-life (SOH below the 80% NASA threshold). "
            "Immediate replacement is required — do not return the unit to service."
        ),
        "action_steps": [
            "Isolate the battery from the system using lockout/tagout (LOTO)",
            "Notify the responsible manager within 1 hour",
            "Schedule a certified technician for replacement",
            "Quarantine the failed unit and handle per disposal SOP",
            "Record the replacement in the maintenance log",
        ],
        "ppe_required": ["Insulated gloves", "Safety glasses"],
    },
    "SCHEDULE_REPLACEMENT": {
        "prescription": (
            "Battery has degraded below the 85% maintenance threshold. Plan a "
            "replacement within the next maintenance window and monitor closely "
            "until it is replaced."
        ),
        "action_steps": [
            "Schedule replacement within the next maintenance cycle",
            "Order a replacement unit matching the original specification",
            "Increase monitoring frequency until the unit is replaced",
            "Review the usage pattern for causes of accelerated wear",
        ],
        "ppe_required": ["Insulated gloves", "Safety glasses"],
    },
    "SCHEDULE_MAINTENANCE": {
        "prescription": (
            "Battery is showing degradation or a sensor anomaly. Schedule an "
            "inspection to confirm the condition and prevent further decline."
        ),
        "action_steps": [
            "Schedule a routine inspection",
            "Verify BMS readings against safe operating thresholds",
            "Check electrical connections and the cooling path",
            "Monitor the degradation trend over the next cycles",
        ],
        "ppe_required": ["Insulated gloves", "Safety glasses"],
    },
    "MONITOR": {
        "prescription": (
            "Battery is within the normal operating range. Continue routine "
            "monitoring; no corrective action is required at this time."
        ),
        "action_steps": [
            "Continue scheduled monitoring",
            "No immediate action required",
        ],
        "ppe_required": [],
    },
}

_DEFAULT_ACTION = "MONITOR"

# ── Warning-code → extra action step ────────────────────────────────────────
# Appended to the base steps when the matching warning is active.
_WARNING_STEPS: dict[str, str] = {
    "TEMP_CRITICAL": (
        "Follow the thermal runaway response SOP immediately — ensure ventilation "
        "and do not touch the unit until temperature normalizes"
    ),
    "TEMP_ELEVATED": "Increase ventilation and monitor temperature closely",
    "VOLTAGE_CRITICAL": "Stop discharge and inspect for cell damage before any further use",
    "VOLTAGE_LOW": "Recharge to the safe range and investigate the deep-discharge cause",
    "OVERVOLTAGE_CRITICAL": (
        "Disconnect the charger immediately and inspect for overcharge damage (fire risk)"
    ),
    "OVERVOLTAGE": "Verify charger settings and the BMS overvoltage cutoff",
    "OVERCURRENT_CRITICAL": "Reduce the load immediately and inspect for a short circuit",
    "OVERCURRENT": "Verify that the load is within the rated discharge current",
}

# ── PPE escalation by hazard class ──────────────────────────────────────────
_THERMAL_CRITICAL = {"TEMP_CRITICAL"}
_ELECTRICAL_CRITICAL = {"VOLTAGE_CRITICAL", "OVERVOLTAGE_CRITICAL", "OVERCURRENT_CRITICAL"}

_THERMAL_PPE = ["Face shield", "Class-D fire extinguisher within reach"]
_ELECTRICAL_PPE = ["Arc-flash rated gloves"]


def _dedupe(items: list[str]) -> list[str]:
    """Order-preserving de-duplication."""
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def build_rule_prescription(
    prediction: dict,
    risk: dict,
    warnings: list[dict],
) -> dict:
    """
    Deterministic prescription from structured prediction.

    Args:
        prediction: inference "prediction" block (soh_percent, health_stage, ...)
        risk:       inference "risk" block (risk_level, priority, action_code, reasons)
        warnings:   inference warnings list ({code, severity, message})

    Returns:
        {prescription, action_steps, ppe_required, source: "rule"}
    """
    action_code = risk.get("action_code", _DEFAULT_ACTION)
    base = _ACTION_TABLE.get(action_code, _ACTION_TABLE[_DEFAULT_ACTION])

    warning_codes = [w.get("code", "") for w in warnings]

    # Prescription prose: base + the top reasons from the risk profile for context.
    reasons = risk.get("reasons", [])
    prescription = base["prescription"]
    if reasons:
        prescription += " Reasons: " + "; ".join(reasons[:3]) + "."

    # Action steps: base steps + warning-specific steps (deduped, order preserved).
    steps = list(base["action_steps"])
    for code in warning_codes:
        extra = _WARNING_STEPS.get(code)
        if extra:
            steps.append(extra)
    steps = _dedupe(steps)

    # PPE: baseline + hazard-class escalation.
    ppe = list(base["ppe_required"])
    active = set(warning_codes)
    if active & _THERMAL_CRITICAL:
        ppe += _THERMAL_PPE
    if active & _ELECTRICAL_CRITICAL:
        ppe += _ELECTRICAL_PPE
    ppe = _dedupe(ppe)

    return {
        "prescription": prescription,
        "action_steps": steps,
        "ppe_required": ppe,
        "source": "rule",
    }
