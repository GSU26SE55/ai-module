import numpy as np

from src.core.config import (
    RATE_THRESHOLD,
    TEMPERATURE_OOD_THRESHOLD,
    TEMPERATURE_TRAIN_CLUSTERS,
    TEMPERATURE_TRAIN_CLUSTERS_BY_CHEMISTRY,
)

# ── Thresholds ────────────────────────────────────────────────────────────────
EOL_SOH = 80.0           # end-of-life threshold (NASA 18650 convention)
DEGRADATION_RATE = 0.15  # % SOH lost per cycle (NASA B0005-B0007 average)
# GH-67: 0.15 là tốc độ của cell NASA 18650 NMC 2 Ah — loại chết sau ~150 chu kỳ.
# Dùng nguyên số đó cho pin LFP thì RUL sai ~17 lần: đo trên dump IoT thật
# (LFP 8S/30Ah, cycle_count=0, SOH 100%) ra rul_cycles_estimate=133 và
# cycles_to_maintenance=100 cho một quả pin MỚI — BE mà dùng để lên lịch bảo trì
# thì gọi thợ sớm gấp 17 lần. Cùng mẫu lỗi với TEMPERATURE_TRAIN_CLUSTERS và
# CYCLE_COUNT_NORM: hằng số hiệu chỉnh theo NASA rò sang đường LFP.
#
# 0.0087 suy từ chính bộ Severson mà model LFP được train: EOL 80% ở ~2300 chu kỳ
# ⇒ 20 điểm SOH / 2300 = 0.0087 %/chu kỳ. Chọn nguồn này để nhất quán với
# LFP_CYCLE_COUNT_NORM = 2300 trong config.
# ⚠️ Nếu có datasheet cycle life của chính pack đang dùng thì số đó sát hơn
# (Severson là cell 1.1 Ah bị ép sạc nhanh trong lab): thay = 20 / cycle_life.
DEGRADATION_RATE_BY_CHEMISTRY = {
    "LFP": 0.0087,
}

# GH-67: dưới ngưỡng này coi như không có dòng xả — cùng quy ước với
# scripts/preprocess_lfp.py (discharge = current < -0.1 A).
DISCHARGE_CURRENT_THRESHOLD = -0.1
MAINTENANCE_SOH  = 85.0  # SOH threshold for scheduling maintenance

# NASA 18650 empirical: voltage fade 0.004 V/cycle ≈ 0.15% SOH/cycle
# → conversion factor 0.15/0.004 = 37.5 %SOH per V/cycle
_VOLT_TO_SOH_RATE = 37.5
_STEPS_PER_CYCLE  = 285  # NASA average discharge cycle length (timesteps)

# NASA 18650 Li-ion safe operating limits
VOLTAGE_CRITICAL_LOW  = 3.0    # V — below cutoff voltage
VOLTAGE_WARNING_LOW   = 3.2    # V
VOLTAGE_WARNING_HIGH  = 4.15   # V
VOLTAGE_CRITICAL_HIGH = 4.2    # V — overcharge risk
TEMP_WARNING          = 35.0   # °C
TEMP_CRITICAL         = 45.0   # °C
CURRENT_WARNING       = -2.0   # A (negative = discharge; 1C for 2Ah cell)
CURRENT_CRITICAL      = -3.0   # A (1.5C)

# GH-67: per-cell voltage warning profiles by chemistry —
# (critical_low, warning_low, warning_high, critical_high) in V/cell.
# "NMC" = the NASA 18650 limits above (default for None/unknown chemistry).
# "LFP": LiFePO4 sits on a flat 3.2-3.3 V plateau, so the NMC profile both
# spams false VOLTAGE_LOW below 3.2 V and misses real overcharge (LFP full
# charge is 3.65 V, far under 4.15). Values per the A123 ANR26650M1-B
# datasheet (the Severson et al. 2019 cell): recommended discharge cutoff
# 2.5 V, charge cutoff 3.65 V; 2.8 V = end-of-discharge knee onset, 3.8 V =
# cell-damage risk threshold.
CHEMISTRY_VOLTAGE_PROFILES = {
    "NMC": (VOLTAGE_CRITICAL_LOW, VOLTAGE_WARNING_LOW, VOLTAGE_WARNING_HIGH, VOLTAGE_CRITICAL_HIGH),
    "LFP": (2.5, 2.8, 3.65, 3.8),
}


_ANOMALY_TIERS = ["Normal", "Degrading", "Failed"]


def classify_anomaly(score: float, soh: float, causal_rate: float | None = None) -> str:
    """
    SOH is the primary driver. IsolationForest score can only downgrade
    Normal → Degrading when a sudden sensor anomaly is detected.

    SOH thresholds (NASA 18650):
      >= 90%: Normal operating range
      80-90%: Degrading — approaching end of useful life
       < 80%: Failed — below EOL threshold

    score: IsolationForest decision_function (negative = more anomalous)

    causal_rate: GH-95 — %SOH lost per cycle vs. this battery's own recent
        history (src/services/battery_history.py), or None when unavailable
        (cold start / missing battery_id / missing cycle info — behaves
        exactly as before GH-95). A 57-dim static window can't see this signal
        (GH-70/GH-95: supervised AUC ~0.5 on any single-window feature set) —
        it needs the battery's own trend, not this window's shape. When it
        exceeds RATE_THRESHOLD (train p90, same definition as GH-70's
        rate-based label), escalate the SOH/score-based tier by one step
        (Normal→Degrading, Degrading→Failed) rather than overriding it —
        RATE_THRESHOLD alone under-performs SOH/score on non-degrading windows.
    """
    if soh < EOL_SOH:
        base = "Failed"
    elif soh < 90.0:
        base = "Degrading"
    else:
        # SOH healthy — IsolationForest can flag sudden sensor anomalies
        base = "Degrading" if score < -0.1 else "Normal"

    if causal_rate is not None and causal_rate > RATE_THRESHOLD:
        idx = min(_ANOMALY_TIERS.index(base) + 1, len(_ANOMALY_TIERS) - 1)
        return _ANOMALY_TIERS[idx]
    return base


def classify_health_stage(soh: float) -> str:
    """Classify battery health using SOH only."""
    if soh < EOL_SOH:
        return "End Of Life"
    if soh < MAINTENANCE_SOH:
        return "Maintenance Required"
    if soh < 90.0:
        return "Degrading"
    return "Healthy"


# GH-86: reject-option threshold — below this, no stage holds a clear majority
# of the MC Dropout samples (the estimate sits in a gray zone between two hard
# thresholds), so the stage is flagged as borderline.
BORDERLINE_CONFIDENCE = 0.7

# Severe → mild; index order doubles as the tie-break preference (safety-first:
# when two stages hold the same share of samples, report the more severe one).
_STAGE_ORDER = ["End Of Life", "Maintenance Required", "Degrading", "Healthy"]


def classify_health_stage_probabilistic(mc_preds: list[float]) -> dict:
    """GH-86: decide health_stage from the MC Dropout sample distribution.

    Each MC sample approximates a draw from the Bayesian posterior over SOH
    (Gal & Ghahramani, ICML 2016), so the share of samples falling in each
    stage bin is that stage's probability — deciding by argmax over those
    shares is robust near the hard thresholds (80/85/90) where the point-
    estimate mean flips stages on ~2% regression error.

    Thresholds themselves stay in classify_health_stage() — single source.

    Returns dict:
        health_stage        — argmax stage (ties break toward more severe)
        stage_probabilities — {stage: share of MC samples}, sums to 1.0
        stage_confidence    — probability of the chosen stage
        is_borderline       — True when stage_confidence < BORDERLINE_CONFIDENCE
    """
    if not mc_preds:
        raise ValueError("mc_preds must contain at least one MC Dropout sample")
    probs = dict.fromkeys(_STAGE_ORDER, 0.0)
    for s in mc_preds:
        probs[classify_health_stage(min(100.0, max(0.0, float(s))))] += 1
    probs = {stage: round(count / len(mc_preds), 3) for stage, count in probs.items()}
    stage = max(_STAGE_ORDER, key=lambda k: (probs[k], -_STAGE_ORDER.index(k)))
    confidence = probs[stage]
    return {
        "health_stage": stage,
        "stage_probabilities": probs,
        "stage_confidence": confidence,
        "is_borderline": confidence < BORDERLINE_CONFIDENCE,
    }


def classify_anomaly_status(score: float) -> str:
    """Classify IsolationForest score separately from SOH health state."""
    if score <= -0.3:
        return "Anomaly"
    if score <= -0.1:
        return "Warning"
    return "Normal"


def compute_risk_profile(
    health_stage: str,
    anomaly_status: str,
    warnings: list[dict],
    soh: float,
    cycles_to_maintenance: int,
) -> dict:
    """Build RAG/ticket-friendly risk level, priority, action code, and reasons."""
    has_critical_warning = any(w.get("severity") == "critical" for w in warnings)
    has_warning = any(w.get("severity") == "warning" for w in warnings)

    if health_stage == "End Of Life" or has_critical_warning:
        risk_level = "Critical"
        priority = "P1"
    elif health_stage == "Maintenance Required" or anomaly_status == "Anomaly":
        risk_level = "High"
        priority = "P2"
    elif health_stage == "Degrading" or anomaly_status == "Warning" or has_warning:
        risk_level = "Medium"
        priority = "P3"
    else:
        risk_level = "Low"
        priority = "None"

    # action_code must be consistent with risk_level (fix P1+MONITOR edge case)
    if health_stage == "End Of Life":
        action_code = "REPLACE_IMMEDIATELY"
    elif health_stage == "Maintenance Required":
        action_code = "SCHEDULE_REPLACEMENT"
    elif health_stage == "Degrading" or anomaly_status in {"Warning", "Anomaly"} or has_warning:
        # has_warning here mirrors the priority branch above (P3) — a non-critical
        # warning on an otherwise healthy/normal battery must still result in an
        # action_code other than MONITOR, or the priority/action_code fields
        # disagree on whether any action is needed at all.
        action_code = "SCHEDULE_MAINTENANCE"
    elif has_critical_warning:
        # Critical sensor warning on healthy battery → escalate action to match P1 risk
        action_code = "SCHEDULE_MAINTENANCE"
    else:
        action_code = "MONITOR"

    reasons = []
    if soh < EOL_SOH:
        reasons.append(f"SOH {soh:.1f}% is below {EOL_SOH:.0f}% end-of-life threshold")
    elif soh < MAINTENANCE_SOH:
        reasons.append(f"SOH {soh:.1f}% is below {MAINTENANCE_SOH:.0f}% maintenance threshold")
    elif soh < 90.0:
        reasons.append(f"SOH {soh:.1f}% indicates degradation below 90%")

    if anomaly_status != "Normal":
        reasons.append(f"Sensor anomaly status is {anomaly_status}")
    if cycles_to_maintenance == 0 and soh < MAINTENANCE_SOH:
        reasons.append("Battery is already at or below maintenance planning threshold")
    reasons.extend(w["message"] for w in warnings[:3])
    if not reasons:
        reasons.append("Battery readings are within normal operating range")

    return {
        "risk_level": risk_level,
        "priority": priority,
        "action_code": action_code,
        "reasons": reasons,
    }


def estimate_rul(soh: float, rate: float | None = None) -> int:
    """
    Estimate remaining useful life in charge-discharge cycles.

    If `rate` is provided (observed degradation rate from multi-cycle window),
    uses it for a battery-specific estimate. Otherwise falls back to the NASA
    population average (0.15%/cycle), accurate to ±30%.
    """
    if soh <= EOL_SOH:
        return 0
    effective_rate = rate if (rate and rate > 1e-4) else DEGRADATION_RATE
    return max(0, int((soh - EOL_SOH) / effective_rate))


def compute_degradation_metrics(
    raw: np.ndarray,
    soh_current: float,
    chemistry: str | None = None,
) -> dict:
    """
    Estimate degradation rate and SOH trajectory from a multi-cycle window.

    Works by splitting the window into N segments (≈ 1 per cycle), computing
    mean end-of-discharge voltage per segment, then fitting a linear trend.
    Converts voltage fade slope → %SOH/cycle using NASA 18650 empirical factor.

    Args:
        raw:         (L, F) raw unscaled readings. Column 0 = voltage.
        soh_current: SOH% predicted by Mamba for the current window.

    Returns dict with:
        degradation_rate_per_cycle  — observed %SOH lost per cycle
        rul_cycles_estimate         — battery-specific RUL (replaces formula)
        soh_trend                   — "accelerating" | "stable" | "slowing"
        cycles_to_maintenance       — cycles until SOH < MAINTENANCE_SOH (85%)
        soh_trajectory              — predicted SOH for next 5 cycles

    When the window doesn't span a full NASA cycle (L < _STEPS_PER_CYCLE — always
    true for the production window=30), there isn't enough inter-cycle signal to
    fit a per-cycle voltage-fade slope: splitting a sub-cycle window into 2
    "segments" and extrapolating by _STEPS_PER_CYCLE/seg (~19x for L=30) amplifies
    ordinary sensor noise into a degradation_rate that saturates the 2%/cycle clip
    ceiling (13x the population average), collapsing rul_cycles_estimate toward 0
    even for a healthy battery. Falls back to the population-average
    DEGRADATION_RATE in that case instead of the unreliable extrapolation.
    """
    L = len(raw)

    if L < _STEPS_PER_CYCLE:
        # Đây là nhánh production (window=30) LUÔN đi vào, nên hằng số này chính
        # là RUL mà BE nhận được — phải đúng theo chemistry.
        degradation_rate = DEGRADATION_RATE_BY_CHEMISTRY.get(chemistry, DEGRADATION_RATE)
        trend = "stable"
    else:
        # Number of segments ≈ cycles covered by the window (min 2, max 10)
        n_seg = max(2, min(10, L // _STEPS_PER_CYCLE))
        seg   = L // n_seg
        tail  = max(1, seg // 10)  # use last 10% of each segment (end-of-discharge)

        # Mean end-of-discharge voltage per segment
        voltages = [float(raw[i * seg : (i + 1) * seg, 0][-tail:].mean())
                    for i in range(n_seg)]

        # Linear regression: voltage ~ segment_index
        x      = np.arange(n_seg, dtype=np.float64)
        slope  = float(np.polyfit(x, voltages, 1)[0])       # V / segment

        # Convert slope → %SOH / cycle
        cycles_per_seg   = seg / _STEPS_PER_CYCLE
        v_per_cycle      = slope / max(cycles_per_seg, 1e-6) # V / cycle
        # ⚠️ GH-67: _VOLT_TO_SOH_RATE (37.5) cũng suy từ NASA 18650 nên nhánh này
        # vẫn lệch với LFP. Chưa sửa vì production dùng window=30 (luôn vào nhánh
        # fallback ở trên); chỉ model long-seq L>=500 mới chạm tới đây.
        degradation_rate = float(np.clip(abs(v_per_cycle) * _VOLT_TO_SOH_RATE, 0.0, 2.0))

        # Trend: compare first-half vs second-half fade rate
        mid         = n_seg // 2
        rate_early  = abs(voltages[mid - 1] - voltages[0])         / max(mid, 1)
        rate_late   = abs(voltages[-1]      - voltages[mid])        / max(n_seg - mid, 1)
        if rate_late > rate_early * 1.2:
            trend = "accelerating"
        elif rate_late < rate_early * 0.8:
            trend = "slowing"
        else:
            trend = "stable"

    # Battery-specific RUL
    rul = estimate_rul(soh_current, rate=degradation_rate)

    # Cycles until SOH crosses maintenance threshold
    if soh_current > MAINTENANCE_SOH and degradation_rate > 1e-4:
        to_maintenance = max(0, int((soh_current - MAINTENANCE_SOH) / degradation_rate))
    else:
        to_maintenance = 0

    # SOH trajectory: next 5 cycles
    trajectory = [
        round(max(0.0, soh_current - degradation_rate * i), 1)
        for i in range(1, 6)
    ]

    return {
        "degradation_rate_per_cycle": round(degradation_rate, 4),
        "rul_cycles_estimate":        rul,
        "soh_trend":                  trend,
        "cycles_to_maintenance":      to_maintenance,
        "soh_trajectory":             trajectory,
    }


def get_recommended_action(classification: str, soh: float) -> str:
    """Map classification + SOH → recommended maintenance action code."""
    if classification == "Failed":
        return "REPLACE_IMMEDIATELY"
    elif classification == "Degrading":
        return "SCHEDULE_REPLACEMENT" if soh < 85.0 else "SCHEDULE_MAINTENANCE"
    return "MONITOR"


def temperature_domain_distance(
    temps: np.ndarray, clusters: tuple[float, ...] | None = None
) -> float:
    """GH-91: worst-case distance (°C) from any reading in the window to the
    nearest training chamber setpoint. The model never saw temperatures
    between/beyond those points, so a large distance means the prediction is
    extrapolating even though the value passed the GH-66 flat range guard.
    Uses max (not mean) so one anomalous reading in the window isn't averaged away.

    clusters defaults to the NASA setpoints (4/24/44 °C). GH-67: the LFP artifact
    set must pass LFP_TEMPERATURE_TRAIN_CLUSTERS instead — Severson ran entirely at
    30 °C, so scoring an LFP request against the NASA setpoints flags every normal
    outdoor reading (26–39 °C) as out-of-distribution."""
    setpoints = TEMPERATURE_TRAIN_CLUSTERS if clusters is None else clusters
    distances = [min(abs(float(t) - c) for c in setpoints) for t in temps]
    return float(max(distances))


def generate_warnings(
    raw: np.ndarray, soh: float, classification: str, chemistry: str | None = None
) -> list[dict]:
    """
    Rule-based threshold checks on raw (unscaled) sensor readings.

    Args:
        raw: (30, F) float32 — unscaled readings, F >= 1
             Column order: [voltage, current, temperature, ...]
        soh: SOH% predicted by Mamba model
        classification: "Normal" | "Degrading" | "Failed"
        chemistry: GH-67 — selects the per-cell voltage profile from
             CHEMISTRY_VOLTAGE_PROFILES ("LFP" for LiFePO4 packs); None or an
             unknown value keeps the NASA/NMC thresholds (legacy behavior).

    Returns:
        List of {code, severity, message} dicts ordered by severity (critical first).
    """
    warnings = []
    n_features = raw.shape[1]
    v_crit_lo, v_warn_lo, v_warn_hi, v_crit_hi = CHEMISTRY_VOLTAGE_PROFILES.get(
        chemistry or "NMC", CHEMISTRY_VOLTAGE_PROFILES["NMC"]
    )

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
            # "warning", not "critical": this range is health_stage="Maintenance
            # Required" (action_code=SCHEDULE_REPLACEMENT, not urgent) — a
            # "critical" severity here fed into compute_risk_profile's
            # has_critical_warning check and force-escalated priority to P1
            # even though the action is only "plan replacement soon".
            "severity": "warning",
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

    if v_min < v_crit_lo:
        warnings.append({
            "code": "VOLTAGE_CRITICAL",
            "severity": "critical",
            "message": (
                f"Minimum voltage {v_min:.3f}V is below safe cutoff "
                f"({v_crit_lo}V) — risk of cell damage."
            ),
        })
    elif v_min < v_warn_lo:
        warnings.append({
            "code": "VOLTAGE_LOW",
            "severity": "warning",
            "message": (
                f"Minimum voltage {v_min:.3f}V is approaching cutoff "
                f"({v_warn_lo}V)."
            ),
        })

    if v_max > v_crit_hi:
        warnings.append({
            "code": "OVERVOLTAGE_CRITICAL",
            "severity": "critical",
            "message": (
                f"Maximum voltage {v_max:.3f}V exceeds safe limit "
                f"({v_crit_hi}V) — overcharge risk."
            ),
        })
    elif v_max > v_warn_hi:
        warnings.append({
            "code": "OVERVOLTAGE",
            "severity": "warning",
            "message": f"Maximum voltage {v_max:.3f}V is elevated (>{v_warn_hi}V).",
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

        # GH-91: distinct from the safety thresholds above — flags when the
        # reading is far from every training chamber setpoint, i.e. the model is
        # extrapolating, regardless of whether the temperature itself is safe.
        # GH-67: cụm phụ thuộc bộ artifact — NASA 4/24/44 °C, Severson (LFP) chỉ
        # 30 °C. Đây là đường sinh cờ THỨ HAI (đường kia là risk profile); cả hai
        # đọc chung TEMPERATURE_TRAIN_CLUSTERS_BY_CHEMISTRY để không lệch nhau.
        # GH-67: SOH nghĩa là "xả ra được bao nhiêu Ah so với danh định", nên cửa
        # sổ không có mẫu xả nào thì con số SOH không dựa trên phép đo nào — model
        # chỉ đang nội suy từ điện áp nghỉ. Đo trên dump IoT thật (pin đứng im
        # 17 giờ, 0 mẫu xả): mọi cửa sổ đều ra đúng 100.00%, kể cả khi ép điện áp
        # xuống 23.9 V / SOC 8%. Con số 100% tình cờ đúng vì pin mới, không phải
        # vì đo được.
        #
        # severity="info" là CỐ Ý: compute_risk_profile() chỉ leo thang với
        # "warning"/"critical", nên cờ này KHÔNG đổi health_stage, anomaly_status
        # hay recommended_action — pin vẫn được báo bình thường, không sinh ticket.
        if raw.shape[1] >= 2 and float(raw[:, 1].min()) >= DISCHARGE_CURRENT_THRESHOLD:
            warnings.append({
                "code": "INSUFFICIENT_DISCHARGE",
                "severity": "info",
                "message": (
                    "Cửa sổ không có mẫu xả nào (dòng chưa bao giờ dưới "
                    f"{DISCHARGE_CURRENT_THRESHOLD} A) — SOH là ước lượng từ điện áp "
                    "nghỉ, chưa dựa trên phép đo dung lượng. Đừng vẽ đồ thị suy "
                    "giảm SOH từ các cửa sổ này."
                ),
            })

        clusters = TEMPERATURE_TRAIN_CLUSTERS_BY_CHEMISTRY.get(
            chemistry, TEMPERATURE_TRAIN_CLUSTERS
        )
        domain_dist = temperature_domain_distance(raw[:, 2], clusters)
        if domain_dist > TEMPERATURE_OOD_THRESHOLD:
            cluster_txt = "/".join(f"{c:g}" for c in clusters)
            warnings.append({
                "code": "TEMP_OOD",
                "severity": "warning",
                "message": (
                    f"Temperature {domain_dist:.1f}°C from nearest training "
                    f"cluster ({cluster_txt}°C) — prediction may be extrapolated."
                ),
            })

    # Sort: critical first, then warning
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    warnings.sort(key=lambda w: severity_order.get(w["severity"], 9))
    return warnings
