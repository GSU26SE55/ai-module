import numpy as np

# ── Thresholds ────────────────────────────────────────────────────────────────
EOL_SOH = 80.0           # end-of-life threshold (NASA 18650 convention)
DEGRADATION_RATE = 0.15  # % SOH lost per cycle (NASA B0005-B0007 average)

# NASA 18650 Li-ion safe operating limits
VOLTAGE_CRITICAL_LOW  = 3.0    # V — below cutoff voltage
VOLTAGE_WARNING_LOW   = 3.2    # V
VOLTAGE_WARNING_HIGH  = 4.15   # V
VOLTAGE_CRITICAL_HIGH = 4.2    # V — overcharge risk
TEMP_WARNING          = 35.0   # °C
TEMP_CRITICAL         = 45.0   # °C
CURRENT_WARNING       = -2.0   # A (negative = discharge; 1C for 2Ah cell)
CURRENT_CRITICAL      = -3.0   # A (1.5C)


def classify_anomaly(score: float, soh: float) -> str:
    """
    SOH is the primary driver. IsolationForest score can only downgrade
    Normal → Degrading when a sudden sensor anomaly is detected.

    SOH thresholds (NASA 18650):
      >= 90%: Normal operating range
      80-90%: Degrading — approaching end of useful life
       < 80%: Failed — below EOL threshold

    score: IsolationForest decision_function (negative = more anomalous)
    """
    if soh < EOL_SOH:
        return "Failed"
    elif soh < 90.0:
        return "Degrading"
    else:
        # SOH healthy — IsolationForest can flag sudden sensor anomalies
        return "Degrading" if score < -0.1 else "Normal"


def estimate_rul(soh: float) -> int:
    """
    Estimate remaining useful life in charge-discharge cycles.
    EOL = SOH 80% (NASA convention). Returns 0 when already at/below EOL.

    Based on NASA B0005-B0007 average degradation rate (~0.15% SOH/cycle).
    This is a heuristic estimate — accuracy ±30%.
    """
    if soh <= EOL_SOH:
        return 0
    return max(0, int((soh - EOL_SOH) / DEGRADATION_RATE))


def get_recommended_action(classification: str, soh: float) -> str:
    """Map classification + SOH → recommended maintenance action code."""
    if classification == "Failed":
        return "REPLACE_IMMEDIATELY"
    elif classification == "Degrading":
        return "SCHEDULE_REPLACEMENT" if soh < 85.0 else "SCHEDULE_MAINTENANCE"
    return "MONITOR"


def generate_warnings(raw: np.ndarray, soh: float, classification: str) -> list[dict]:
    """
    Rule-based threshold checks on raw (unscaled) sensor readings.

    Args:
        raw: (30, F) float32 — unscaled readings, F >= 1
             Column order: [voltage, current, temperature, ...]
        soh: SOH% predicted by Mamba model
        classification: "Normal" | "Degrading" | "Failed"

    Returns:
        List of {code, severity, message} dicts ordered by severity (critical first).
    """
    warnings = []
    n_features = raw.shape[1]

    # ── SOH-based ─────────────────────────────────────────────────────────
    if soh < EOL_SOH:
        warnings.append({
            "code": "BATTERY_EOL",
            "severity": "critical",
            "message": (
                f"SOH {soh:.1f}% is below end-of-life threshold ({EOL_SOH:.0f}%) "
                "— battery should be replaced."
            ),
        })
    elif soh < 85.0:
        warnings.append({
            "code": "SOH_CRITICAL",
            "severity": "critical",
            "message": f"SOH {soh:.1f}% is critically low — plan replacement soon.",
        })
    elif soh < 90.0:
        warnings.append({
            "code": "SOH_LOW",
            "severity": "warning",
            "message": f"SOH {soh:.1f}% is below 90% — monitor degradation rate.",
        })

    # ── Voltage (index 0) ─────────────────────────────────────────────────
    v = raw[:, 0]
    v_min, v_max = float(v.min()), float(v.max())

    if v_min < VOLTAGE_CRITICAL_LOW:
        warnings.append({
            "code": "VOLTAGE_CRITICAL",
            "severity": "critical",
            "message": (
                f"Minimum voltage {v_min:.3f}V is below safe cutoff "
                f"({VOLTAGE_CRITICAL_LOW}V) — risk of cell damage."
            ),
        })
    elif v_min < VOLTAGE_WARNING_LOW:
        warnings.append({
            "code": "VOLTAGE_LOW",
            "severity": "warning",
            "message": (
                f"Minimum voltage {v_min:.3f}V is approaching cutoff "
                f"({VOLTAGE_WARNING_LOW}V)."
            ),
        })

    if v_max > VOLTAGE_CRITICAL_HIGH:
        warnings.append({
            "code": "OVERVOLTAGE_CRITICAL",
            "severity": "critical",
            "message": (
                f"Maximum voltage {v_max:.3f}V exceeds safe limit "
                f"({VOLTAGE_CRITICAL_HIGH}V) — overcharge risk."
            ),
        })
    elif v_max > VOLTAGE_WARNING_HIGH:
        warnings.append({
            "code": "OVERVOLTAGE",
            "severity": "warning",
            "message": f"Maximum voltage {v_max:.3f}V is elevated (>{VOLTAGE_WARNING_HIGH}V).",
        })

    # ── Current (index 1) — negative convention for discharge ─────────────
    if n_features >= 2:
        i_min = float(raw[:, 1].min())
        if i_min < CURRENT_CRITICAL:
            warnings.append({
                "code": "OVERCURRENT_CRITICAL",
                "severity": "critical",
                "message": (
                    f"Discharge current {abs(i_min):.2f}A exceeds critical limit "
                    f"({abs(CURRENT_CRITICAL)}A)."
                ),
            })
        elif i_min < CURRENT_WARNING:
            warnings.append({
                "code": "OVERCURRENT",
                "severity": "warning",
                "message": (
                    f"Discharge current {abs(i_min):.2f}A exceeds recommended limit "
                    f"({abs(CURRENT_WARNING)}A)."
                ),
            })

    # ── Temperature (index 2) ─────────────────────────────────────────────
    if n_features >= 3:
        t_max = float(raw[:, 2].max())
        if t_max > TEMP_CRITICAL:
            warnings.append({
                "code": "TEMP_CRITICAL",
                "severity": "critical",
                "message": (
                    f"Peak temperature {t_max:.1f}°C exceeds critical threshold "
                    f"({TEMP_CRITICAL}°C)."
                ),
            })
        elif t_max > TEMP_WARNING:
            warnings.append({
                "code": "TEMP_ELEVATED",
                "severity": "warning",
                "message": f"Peak temperature {t_max:.1f}°C is elevated (>{TEMP_WARNING}°C).",
            })

    # Sort: critical first, then warning
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    warnings.sort(key=lambda w: severity_order.get(w["severity"], 9))
    return warnings
