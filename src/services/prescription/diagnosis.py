"""
Diagnosis statement builder — step 1 of the agentic prescription chain (GH-82).

Wraps the /predict result into the structured 3-part statement from
Deng et al. 2024 §3.2 (Diagnosis / Inference evidence / Description).
Fully deterministic — no LLM, no new computation; only fields the
prediction pipeline already returns.
"""
from src.services.prescription.rule_prescription import _ACTION_TEMPLATES, _DEFAULT_ACTION


def build_diagnosis_statement(
    prediction: dict,
    anomaly: dict,
    risk: dict,
    warnings: list[dict],
) -> str:
    """
    Args:
        prediction: "prediction" block from run_inference (soh_percent, soh_std,
                    health_stage, ...).
        anomaly:    "anomaly" block (anomaly_status, anomaly_score,
                    anomaly_confidence) — pass {} if unavailable.
        risk:       "risk" block (risk_level, priority, action_code).
        warnings:   evidence.warnings list of {"code": str, ...}.

    Returns:
        3-line statement: Diagnosis / Inference evidence / Description.
    """
    soh = prediction.get("soh_percent", 0.0)
    soh_std = prediction.get("soh_std", 0.0)
    stage = prediction.get("health_stage", "unknown")
    status = anomaly.get("anomaly_status", "Unknown")
    score = anomaly.get("anomaly_score", 0.0)
    confidence = anomaly.get("anomaly_confidence", 0.0)
    codes = [w.get("code", "") for w in warnings if w.get("code")]

    action_code = risk.get("action_code", _DEFAULT_ACTION)
    template = _ACTION_TEMPLATES.get(action_code, _ACTION_TEMPLATES[_DEFAULT_ACTION])

    return (
        f"Diagnosis: {status} lithium-ion battery, health stage {stage}.\n"
        f"Inference evidence: SOH {soh:.1f}% (± {soh_std:.1f}), "
        f"anomaly score {score:.3f} (confidence {confidence:.2f}), "
        f"active warnings: {', '.join(codes) if codes else 'none'}.\n"
        f"Description: {template['summary']} "
        f"Risk {risk.get('risk_level', 'Low')}, priority {risk.get('priority', 'None')}, "
        f"recommended action {action_code}."
    )
