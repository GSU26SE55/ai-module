from pydantic import BaseModel, ConfigDict, field_validator

from src.core.config import FEATURES, INPUT_FEATURES, WINDOW_SIZE


LEGACY_INPUT_FEATURES = 3
LEGACY_FEATURES = ["voltage", "current", "temperature"]


class PredictRequest(BaseModel):
    battery_id: str
    readings: list[list[float]]  # shape: (30, 6) preferred; (30, 3) allowed for legacy artifacts

    @field_validator("readings")
    @classmethod
    def validate_readings_shape(cls, v: list[list[float]]) -> list[list[float]]:
        if len(v) != WINDOW_SIZE:
            raise ValueError(f"readings must have {WINDOW_SIZE} timesteps, got {len(v)}")
        allowed_feature_counts = {LEGACY_INPUT_FEATURES, INPUT_FEATURES}
        feature_descriptions = {
            LEGACY_INPUT_FEATURES: LEGACY_FEATURES,
            INPUT_FEATURES: FEATURES,
        }
        for i, row in enumerate(v):
            if len(row) not in allowed_feature_counts:
                raise ValueError(
                    f"readings[{i}] must have one of {sorted(allowed_feature_counts)} feature counts "
                    f"{feature_descriptions}, got {len(row)}"
                )
        return v


class WarningItem(BaseModel):
    code: str       # e.g. "VOLTAGE_LOW", "TEMP_CRITICAL", "SOH_LOW"
    severity: str   # "warning" | "critical"
    message: str


class FeatureStat(BaseModel):
    mean: float
    min: float
    max: float


class PredictionInfo(BaseModel):
    soh_percent: float
    soh_confidence: float   # MC Dropout uncertainty [0,1]: 1=confident, 0=uncertain
    soh_std: float          # MC Dropout std in % SOH — raw uncertainty
    rul_cycles_estimate: int
    degradation_rate_per_cycle: float
    soh_trend: str
    cycles_to_maintenance: int
    soh_trajectory: list[float]
    health_stage: str


class AnomalyInfo(BaseModel):
    anomaly_score: float
    anomaly_status: str
    anomaly_confidence: float   # IsolationForest magnitude — NOT calibrated probability


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


class PredictResponse(BaseModel):
    battery_id: str
    prediction: PredictionInfo
    anomaly: AnomalyInfo
    risk: RiskInfo
    evidence: EvidenceInfo
    metadata: ResponseMetadata

    # Backward-compatible flat fields. Keep until BE migrates to nested response.
    soh_percent: float
    classification: str     # "Normal" | "Degrading" | "Failed"
    confidence: float       # |IsolationForest score|, range [0, 1]
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
