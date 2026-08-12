import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.core.config import (
    BASE_FEATURES,
    CURRENT_RANGE,
    FEATURES,
    INPUT_FEATURES,
    LONG_SEQ_LEN,
    MAX_WINDOW_SPAN_S,
    NOMINAL_CAPACITY_AH,
    NOMINAL_CAPACITY_AH_BY_CHEMISTRY,
    SOC_RANGE,
    TEMPERATURE_RANGE,
    VOLTAGE_CELL_RANGE,
    VOLTAGE_CELL_RANGE_BY_CHEMISTRY,
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


def check_reading_ranges(
    readings: list[list[float]], pack_config: "PackConfig | None"
) -> None:
    """GH-66 value-range guard, shared by every request shape that carries readings.

    Extracted so PredictLongRequest (GH-10, 31..4096 rows) enforces the SAME
    physical limits as PredictRequest — a second, drifting copy of these bounds
    is exactly how one transport ends up accepting what the other rejects.

    Voltage is checked PER-CELL, i.e. after dividing by pack_config.n_series
    (GH-65) — so a 12V pack with n_series=3 passes, while 12V without
    pack_config is rejected with a hint. GH-67: current is checked on the
    C-rate equivalent của cell danh định theo chemistry
    (current × nominal / pack_config.capacity_ah) — a 50 Ah pack discharging
    10 A (0.2C) passes, while 10 A without capacity_ah is rejected.
    Ranges: src/core/config.py.
    `time` has no range (finite-checked by the caller); cycle_count keeps GH-59 clip.
    """
    n_series = pack_config.n_series if pack_config else 1
    capacity_ah = pack_config.capacity_ah if pack_config else None
    # GH-67: dải per-cell VÀ cell danh định đều theo chemistry khi có khai báo.
    # - VOLTAGE_CELL_RANGE_BY_CHEMISTRY: dải chung [2.0, 4.5] quá lỏng cho LFP
    #   (cell LFP tối đa vật lý 3.65 V), xem config.py.
    # - NOMINAL_CAPACITY_AH_BY_CHEMISTRY: bộ LFP train trên cell Severson 1.1 Ah,
    #   không phải cell NASA 2.0 Ah. Giá trị ở đây PHẢI khớp
    #   art.nominal_capacity_ah bên inference.py — lệch nhau thì guard chấp nhận
    #   thứ mà model không nhận đúng (có test khoá:
    #   test_schema_and_inference_use_the_same_nominal).
    _chem = pack_config.chemistry if pack_config else None
    nominal = NOMINAL_CAPACITY_AH_BY_CHEMISTRY.get(_chem, NOMINAL_CAPACITY_AH)
    i_scale = nominal / capacity_ah if capacity_ah else 1.0
    v_lo, v_hi = VOLTAGE_CELL_RANGE_BY_CHEMISTRY.get(_chem, VOLTAGE_CELL_RANGE)
    i_lo, i_hi = CURRENT_RANGE
    t_lo, t_hi = TEMPERATURE_RANGE
    s_lo, s_hi = SOC_RANGE
    for i, row in enumerate(readings):
        v_cell = row[0] / n_series
        if not v_lo <= v_cell <= v_hi:
            hint = (
                " — if this is a multi-cell pack (e.g. 12V ~ 3S NMC or "
                "25.6V ~ 8S LFP), send pack_config.n_series so voltage can "
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
                else f" (current {row[1]} A × {nominal} / capacity_ah {capacity_ah})"
            )
            raise ValueError(
                f"readings[{i}].current: C-rate equivalent value {i_equiv:.3f} A "
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

        Body lives in module-level check_reading_ranges() so PredictLongRequest
        enforces the identical bounds — see that function for the full rules."""
        check_reading_ranges(self.readings, self.pack_config)
        return self

    @model_validator(mode="after")
    def validate_window_span(self) -> "PredictRequest":
        """GH-67: chặn cửa sổ trải quá dài — lỗ hổng còn lại của range guard GH-66.

        Cột `time` là cột DUY NHẤT không bị chặn dải, mà nó lại là cột làm vỡ dự
        đoán. Ca thật đã gặp: IoT mất kết nối 76 phút giữa cửa sổ, 30 dòng vẫn
        "liên tiếp" trong DB nên BE gửi lên bình thường; model đọc thành "điện áp
        tụt trong 94 phút" và trả SOH 81.84% + SCHEDULE_REPLACEMENT cho pin khoẻ.

        Từ chối hẳn thay vì trả kèm cảnh báo, vì cửa sổ hỏng kiểu này lại cho
        confidence CAO NHẤT (0.799 so với trung vị 0.425) — BE không thể lọc ra
        bằng confidence được. Ngưỡng + số đo: MAX_WINDOW_SPAN_S trong config.py.
        """
        if not self.readings or len(self.readings[0]) < 4:
            return self  # payload 3 cột (legacy) không có cột time để kiểm
        times = [row[3] for row in self.readings]
        for i in range(1, len(times)):
            if times[i] < times[i - 1]:
                raise ValueError(
                    f"readings[{i}].time={times[i]} nhỏ hơn readings[{i-1}].time="
                    f"{times[i-1]} — cột time phải không giảm; sắp xếp lại theo "
                    "thứ tự thời gian trước khi gửi"
                )
        # Cột `time` là vị trí TRONG cửa sổ, phải rebase về 0 ở dòng đầu (quy ước
        # trong docs/grpc-integration-be.md §4.1; training data rebase y hệt —
        # scripts/preprocess_lfp.py `seg[:, time] -= seg[0, time]`).
        #
        # Guard span ở dưới KHÔNG bắt được lỗi này: BE gửi timestamp tuyệt đối với
        # nhịp lấy mẫu bình thường vẫn cho span nhỏ và lọt qua. Đo được: giữ nguyên
        # mọi kênh khác, chỉ dời mốc time 0s → 900s làm SOH tụt 97.85% → 60.21% và
        # lật nhãn sang End Of Life. Không có lỗi nào báo, nên một pin còn mới bị
        # mở ticket P1 mà không ai truy ra nguyên nhân.
        if times[0] > MAX_WINDOW_SPAN_S:
            raise ValueError(
                f"readings[0].time={times[0]:.0f}s — cột time phải rebase về 0 ở "
                "dòng ĐẦU của mỗi window (0, dt, 2·dt, …), không phải timestamp "
                "tuyệt đối. Trừ đi mốc thời gian của dòng đầu trước khi gửi: "
                "`time[i] -= time[0]`. Gửi timestamp tuyệt đối vẫn chạy nhưng cho "
                "SOH sai lệch lớn (đo được: mốc 900s làm SOH 97.9% → 60.2% và lật "
                "nhãn sang End Of Life trên pin còn khoẻ)."
            )
        span = times[-1] - times[0]
        if span > MAX_WINDOW_SPAN_S:
            raise ValueError(
                f"window trải {span:.0f}s ({span/60:.0f} phút), vượt trần "
                f"{MAX_WINDOW_SPAN_S:.0f}s ({MAX_WINDOW_SPAN_S/60:.0f} phút) — "
                "thường là do mất kết nối giữa chừng nên 30 bản ghi liên tiếp "
                "trong DB lại cách nhau rất xa. Bỏ qua cửa sổ này và chờ đủ 30 "
                "bản ghi liền mạch; đo trên cửa sổ dài hơn trần cho ra SOH sai "
                "kèm confidence cao giả tạo."
            )
        return self


class PredictLongRequest(BaseModel):
    """GH-10 — SOH from a long raw series (31..LONG_SEQ_LEN timesteps).

    Deliberately NOT a subclass of PredictRequest: that one pins the length to
    exactly WINDOW_SIZE, which is baked into the window=30 weights. The long
    model is a different artifact with a different input contract, so sharing the
    class would only make one of the two lie about what it accepts.

    Only the 4 base columns are used — the long model derives IC-curve and
    discharge-progress itself, so cycle_count/soc_percent are ignored if sent
    (no soc_mode trap on this path).
    """

    battery_id: str
    readings: list[list[float]] | list[ReadingObject]
    pack_config: PackConfig | None = None

    @field_validator("readings")
    @classmethod
    def validate_long_readings(
        cls, v: list[list[float]] | list[ReadingObject]
    ) -> list[list[float]]:
        # Lower bound is WINDOW_SIZE+1, not 1: at or below 30 rows the caller
        # should use Predict, which is the validated path and also returns
        # anomaly/risk. Silently accepting 5 rows here would hand back a bare SOH
        # from a model that never saw sequences that short.
        if not WINDOW_SIZE < len(v) <= LONG_SEQ_LEN:
            raise ValueError(
                f"readings must have {WINDOW_SIZE + 1}..{LONG_SEQ_LEN} timesteps for "
                f"the long path, got {len(v)} — use /predict (exactly {WINDOW_SIZE}) "
                "for short windows"
            )

        if v and isinstance(v[0], ReadingObject):
            v = [[r.voltage, r.current, r.temperature, r.time] for r in v]

        allowed = {LEGACY_INPUT_FEATURES, BASE_INPUT_FEATURES, FULL_INPUT_FEATURES}
        for i, row in enumerate(v):
            if len(row) not in allowed:
                raise ValueError(
                    f"readings[{i}] must have one of {sorted(allowed)} columns, "
                    f"got {len(row)}"
                )
            for j, value in enumerate(row):
                if not math.isfinite(value):
                    raise ValueError(
                        f"readings[{i}].{FEATURES[j]} is {value} — "
                        "NaN/Inf is not a valid sensor value"
                    )
        return v

    @model_validator(mode="after")
    def validate_long_ranges(self) -> "PredictLongRequest":
        check_reading_ranges(self.readings, self.pack_config)
        return self


class PredictLongResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    battery_id: str
    soh_percent: float
    seq_len: int
    device: str  # "cpu" / "cuda" — the long model uses GPU when available
    inference_ms: float
    model_version: str
    """LONG_MODEL_VERSION — a DIFFERENT artifact from the window=30 model, so this
    never equals metadata.model_version of PredictResponse. Do not compare them."""


class ClassificationFeedbackRequest(BaseModel):
    """F4 — kỹ thuật viên chấm lại phân loại mà AI đã đưa ra cho một pin.

    Khớp `StaffFeedbackEnum` phía BE (1 Correct / 2 FalsePositive / 3 FalseNegative);
    BE map số sang chuỗi trước khi gửi để hợp đồng không phụ thuộc thứ tự enum của một bên.
    """

    battery_id: str
    classification: Literal["Normal", "Degrading", "Failed"]
    """Nhãn AI ĐÃ đưa ra — không phải nhãn đúng. Verdict mới nói AI đúng hay sai."""
    verdict: Literal["correct", "false_positive", "false_negative"]
    model_config = ConfigDict(protected_namespaces=())
    model_version: str = ""
    classified_at: str = ""  # ISO UTC của lần phân loại; "" nếu caller không có
    note: str = ""


class ClassificationFeedbackResponse(BaseModel):
    success: bool
    total: int
    correct: int
    false_positive: int
    false_negative: int
    precision: float | None = None
    """None khi chưa có mẫu nào — KHÁC 0.0 (nghĩa là đã chấm và sai hết)."""
    recall: float | None = None


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
    soh_confidence: float  # MC Dropout uncertainty, exp(-soh_std/5) in (0,1]: 1=confident
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
    """P1/P2/P3/None — computed purely from battery severity (health_stage,
    anomaly_status, critical warnings). NOT the final ticket Priority: this
    module has no ImpactScope (Site/SingleAsset/MultiSite). GH-23: BE must
    treat this as a suggested Urgency signal and combine it with its own
    ImpactScope via the Impact x Urgency Priority Matrix (design.md) to get
    the ticket's actual Priority — see docs/ai-be-integration.md §4."""
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
