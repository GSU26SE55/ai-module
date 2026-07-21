import math

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.core.config import (
    BASE_FEATURES,
    CURRENT_RANGE,
    FEATURES,
    INPUT_FEATURES,
    NOMINAL_CAPACITY_AH,
    SOC_RANGE,
    TEMPERATURE_RANGE,
    VOLTAGE_CELL_RANGE,
    WINDOW_SIZE,
)


LEGACY_INPUT_FEATURES = 3
LEGACY_FEATURES = ["voltage", "current", "temperature"]

# GH-54: 4 base columns — the 2 extra model inputs (cycle_count, soc_percent) are
# derived server-side when the payload only has these 4.
BASE_INPUT_FEATURES = len(BASE_FEATURES)

# GH-56: BE may instead send all 6 columns directly (cycle_count + soc_percent
# computed from the battery's full charge/discharge history — more accurate
# than this service's window-local estimate). Used as-is when present.
FULL_INPUT_FEATURES = INPUT_FEATURES


class ReadingObject(BaseModel):
    """GH-76: named-field alternative to a positional [v, i, t, time, ...] row —
    removes the column-order footgun (schema stays valid even if BE swaps two
    columns by mistake, since a plain float list has no way to catch that)."""

    voltage: float
    current: float
    temperature: float
    time: float
    cycle_count: float | None = None
    soc_percent: float | None = None


class PackConfig(BaseModel):
    """GH-65/GH-67: pack-to-cell normalization for multi-cell packs
    (e.g. 12V ≈ 3S NMC, or 12.8V ≈ 4S LFP).

    voltage_cell = voltage_pack / n_series is applied BEFORE the scaler and BEFORE
    warning thresholds (temperature unchanged). GH-67: a series pack does NOT
    divide current, but the scaler and current thresholds were fit on the NASA
    2 Ah cell's amp scale — when capacity_ah is set, current is rescaled to the
    same C-rate on that cell (current × 2.0 / capacity_ah), also before the
    scaler/range guard/thresholds. chemistry selects the per-cell voltage
    warning profile (anomaly_detector.CHEMISTRY_VOLTAGE_PROFILES); prediction
    accuracy on LFP curves is still unvalidated — that is GH-67 itself."""

    n_series: int = Field(
        1, ge=1, description="cells in series; 1 = single cell (default, legacy behavior)"
    )
    chemistry: str | None = None
    capacity_ah: float | None = Field(
        None,
        gt=0,
        description=(
            "pack nominal capacity (Ah); enables C-rate current normalization "
            "(None = no rescale, NASA 2 Ah behavior)"
        ),
    )

    @field_validator("chemistry")
    @classmethod
    def normalize_chemistry(cls, v: str | None) -> str | None:
        """Canonicalize the common spellings so the profile lookup and the
        metadata trace agree; unknown strings pass through unchanged (they get
        the default NMC voltage profile downstream)."""
        if v is None:
            return v
        return {"lfp": "LFP", "lifepo4": "LFP", "nmc": "NMC"}.get(v.strip().lower(), v)


class PredictRequest(BaseModel):
    battery_id: str
    readings: list[list[float]] | list[ReadingObject]
    # shape: (30, 6) preferred; (30, 4) or legacy (30, 3) also accepted.
    # GH-76: list[ReadingObject] (named fields) accepted as an alternative to the
    # positional list[list[float]] — normalized to the latter in the validator
    # below, so every downstream consumer (run_inference, grpc_server, ...)
    # keeps seeing plain float rows and needs no changes.
    pack_config: PackConfig | None = None

    @field_validator("readings")
    @classmethod
    def validate_readings_shape(
        cls, v: list[list[float]] | list[ReadingObject]
    ) -> list[list[float]]:
        if len(v) != WINDOW_SIZE:
            raise ValueError(
                f"readings must have {WINDOW_SIZE} timesteps, got {len(v)}"
            )

        if v and isinstance(v[0], ReadingObject):
            has_cycle = [r.cycle_count is not None for r in v]
            has_soc = [r.soc_percent is not None for r in v]
            if any(has_cycle) != all(has_cycle) or any(has_soc) != all(has_soc):
                raise ValueError(
                    "cycle_count/soc_percent must be set on either all readings "
                    "or none — got a mix of present/missing across the window"
                )
            if has_cycle[0] != has_soc[0]:
                raise ValueError(
                    "cycle_count and soc_percent must be provided together "
                    "(both or neither) — got only one of the two"
                )
            include_derived = has_cycle[0]
            rows: list[list[float]] = []
            for r in v:
                row = [r.voltage, r.current, r.temperature, r.time]
                if include_derived:
                    row += [r.cycle_count, r.soc_percent]
                rows.append(row)
            v = rows

        allowed_feature_counts = {
            LEGACY_INPUT_FEATURES,
            BASE_INPUT_FEATURES,
            FULL_INPUT_FEATURES,
        }
        feature_descriptions = {
            LEGACY_INPUT_FEATURES: LEGACY_FEATURES,
            BASE_INPUT_FEATURES: BASE_FEATURES,
            FULL_INPUT_FEATURES: FEATURES,
        }
        for i, row in enumerate(v):
            if len(row) not in allowed_feature_counts:
                raise ValueError(
                    f"readings[{i}] must have one of {sorted(allowed_feature_counts)} feature counts "
                    f"{feature_descriptions}, got {len(row)}"
                )
            # GH-66: Pydantic's plain `float` lets NaN/Inf through — reject them
            # here, before any range math (NaN comparisons are silently False).
            for j, value in enumerate(row):
                if not math.isfinite(value):
                    raise ValueError(
                        f"readings[{i}].{FEATURES[j]} is {value} — "
                        "NaN/Inf is not a valid sensor value"
                    )
        return v

    @model_validator(mode="after")
    def validate_reading_ranges(self) -> "PredictRequest":
        """GH-66: value-range guard — reject out-of-distribution readings (422 REST /
        INVALID_ARGUMENT gRPC via the shared schema) instead of letting the scaler
        transform them outside [0,1] and silently predicting garbage SOH.

        Voltage is checked PER-CELL, i.e. after dividing by pack_config.n_series
        (GH-65) — so a 12V pack with n_series=3 passes, while 12V without
        pack_config is rejected with a hint. GH-67: current is checked on the
        NASA-2Ah C-rate equivalent (current × 2.0 / pack_config.capacity_ah) —
        a 50 Ah pack discharging 10 A (0.2C) passes, while 10 A without
        capacity_ah is rejected. Ranges: src/core/config.py.
        `time` has no range (finite-checked above); cycle_count keeps GH-59 clip."""
        n_series = self.pack_config.n_series if self.pack_config else 1
        capacity_ah = self.pack_config.capacity_ah if self.pack_config else None
        i_scale = NOMINAL_CAPACITY_AH / capacity_ah if capacity_ah else 1.0
        v_lo, v_hi = VOLTAGE_CELL_RANGE
        i_lo, i_hi = CURRENT_RANGE
        t_lo, t_hi = TEMPERATURE_RANGE
        s_lo, s_hi = SOC_RANGE
        for i, row in enumerate(self.readings):
            v_cell = row[0] / n_series
            if not v_lo <= v_cell <= v_hi:
                hint = (
                    " — if this is a multi-cell pack (e.g. 12V ~ 3S NMC or "
                    "12.8V ~ 4S LFP), send pack_config.n_series so voltage can "
                    "be normalized per-cell"
                    if n_series == 1
                    else f" (pack voltage {row[0]} / n_series {n_series})"
                )
                raise ValueError(
                    f"readings[{i}].voltage: per-cell value {v_cell:.3f} V outside "
                    f"allowed range [{v_lo}, {v_hi}] V{hint}"
                )
            i_equiv = row[1] * i_scale
            if not i_lo <= i_equiv <= i_hi:
                hint = (
                    " — if this pack's capacity differs from the NASA 2 Ah cell, "
                    "send pack_config.capacity_ah so current can be normalized "
                    "by C-rate"
                    if i_scale == 1.0
                    else f" (current {row[1]} A × {NOMINAL_CAPACITY_AH} / capacity_ah {capacity_ah})"
                )
                raise ValueError(
                    f"readings[{i}].current: NASA-equivalent value {i_equiv:.3f} A "
                    f"outside allowed range [{i_lo}, {i_hi}] A{hint}"
                )
            if not t_lo <= row[2] <= t_hi:
                raise ValueError(
                    f"readings[{i}].temperature={row[2]} °C outside allowed range "
                    f"[{t_lo}, {t_hi}] °C"
                )
            if len(row) >= 6 and not s_lo <= row[5] <= s_hi:
                raise ValueError(
                    f"readings[{i}].soc_percent={row[5]} outside allowed range "
                    f"[{s_lo}, {s_hi}]"
                )
        return self


class WarningItem(BaseModel):
    code: str  # e.g. "VOLTAGE_LOW", "TEMP_CRITICAL", "SOH_LOW"
    severity: str  # "warning" | "critical"
    message: str


class FeatureStat(BaseModel):
    mean: float
    min: float
    max: float


class PredictionInfo(BaseModel):
    soh_percent: float
    soh_confidence: float  # MC Dropout uncertainty [0,1]: 1=confident, 0=uncertain
    soh_std: float  # MC Dropout std in % SOH — raw uncertainty
    rul_cycles_estimate: int
    degradation_rate_per_cycle: float
    soh_trend: str
    cycles_to_maintenance: int
    soh_trajectory: list[float]
    health_stage: str
    # GH-86: MC-distribution staging. Defaults keep older cached payloads valid.
    stage_probabilities: dict[str, float] = {}  # {stage: share of MC samples}
    stage_confidence: float = 1.0  # probability of the chosen health_stage
    is_borderline: bool = False  # True when no stage holds a clear majority (<0.7)


class AnomalyInfo(BaseModel):
    anomaly_score: float
    anomaly_status: str
    anomaly_confidence: float  # IsolationForest magnitude — NOT calibrated probability


class RiskInfo(BaseModel):
    risk_level: str
    priority: str
    action_code: str
    reasons: list[str]


class EvidenceInfo(BaseModel):
    warnings: list[WarningItem]
    feature_summary: dict[str, FeatureStat]


class ResponseMetadata(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_version: str
    window_size: int
    input_features: int
    inference_ms: float
    n_series: int = 1  # GH-65: pack→cell divisor applied to voltage (1 = single cell)
    # GH-67: which voltage-warning profile / C-rate divisor were applied —
    # trace for the real-battery validation logs (None = NASA/NMC defaults).
    chemistry: str | None = None
    capacity_ah: float | None = None
    # GH-91: distance (°C) from the window's temperature to the nearest NASA
    # training chamber setpoint (4/24/44°C); is_temperature_ood flags when it
    # exceeds TEMPERATURE_OOD_THRESHOLD, i.e. the prediction is extrapolating.
    temperature_domain_distance: float = 0.0
    is_temperature_ood: bool = False


class PredictResponse(BaseModel):
    battery_id: str
    prediction: PredictionInfo
    anomaly: AnomalyInfo
    risk: RiskInfo
    evidence: EvidenceInfo
    metadata: ResponseMetadata

    # Backward-compatible flat fields. Keep until BE migrates to nested response.
    soh_percent: float
    classification: str  # "Normal" | "Degrading" | "Failed"
    confidence: float  # MC Dropout soh_confidence [0,1] — NOT the IsolationForest score
    inference_ms: float

    # ── RUL & Degradation Trend ───────────────────────────────────────────
    rul_cycles_estimate: int
    """Remaining useful life in cycles until SOH=80% (EOL).
    Battery-specific when window spans ≥2 cycles; falls back to NASA average."""

    degradation_rate_per_cycle: float
    """Observed %SOH lost per charge-discharge cycle.
    Computed from voltage fade trend across multi-cycle window.
    Falls back to NASA population average (0.15%) for short windows."""

    soh_trend: str
    """Degradation velocity: 'accelerating' | 'stable' | 'slowing'."""

    cycles_to_maintenance: int
    """Estimated cycles until SOH crosses 85% maintenance threshold. 0 if already below."""

    soh_trajectory: list[float]
    """Predicted SOH for next 5 cycles based on observed degradation rate."""

    # ── Anomaly Detection ─────────────────────────────────────────────────
    anomaly_score: float
    """Raw IsolationForest decision_function score. Negative = more anomalous."""

    recommended_action: str
    """
    MONITOR               — SOH healthy, no action needed
    SCHEDULE_MAINTENANCE  — SOH 85-90%, plan a check
    SCHEDULE_REPLACEMENT  — SOH 80-85%, replacement upcoming
    REPLACE_IMMEDIATELY   — SOH < 80%, battery at/past EOL
    """

    warnings: list[WarningItem]
    """Threshold-based warnings ordered by severity (critical first)."""

    feature_summary: dict[str, FeatureStat]
    """Mean/min/max for each sensor feature across the window."""
