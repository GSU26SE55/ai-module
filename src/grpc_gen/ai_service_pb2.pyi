from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Reading(_message.Message):
    __slots__ = ("values",)
    VALUES_FIELD_NUMBER: _ClassVar[int]
    values: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, values: _Optional[_Iterable[float]] = ...) -> None: ...

class ReadingFields(_message.Message):
    __slots__ = ("voltage", "current", "temperature", "time", "cycle_count", "soc_percent")
    VOLTAGE_FIELD_NUMBER: _ClassVar[int]
    CURRENT_FIELD_NUMBER: _ClassVar[int]
    TEMPERATURE_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    CYCLE_COUNT_FIELD_NUMBER: _ClassVar[int]
    SOC_PERCENT_FIELD_NUMBER: _ClassVar[int]
    voltage: float
    current: float
    temperature: float
    time: float
    cycle_count: float
    soc_percent: float
    def __init__(self, voltage: _Optional[float] = ..., current: _Optional[float] = ..., temperature: _Optional[float] = ..., time: _Optional[float] = ..., cycle_count: _Optional[float] = ..., soc_percent: _Optional[float] = ...) -> None: ...

class PackConfig(_message.Message):
    __slots__ = ("n_series", "chemistry", "capacity_ah")
    N_SERIES_FIELD_NUMBER: _ClassVar[int]
    CHEMISTRY_FIELD_NUMBER: _ClassVar[int]
    CAPACITY_AH_FIELD_NUMBER: _ClassVar[int]
    n_series: int
    chemistry: str
    capacity_ah: float
    def __init__(self, n_series: _Optional[int] = ..., chemistry: _Optional[str] = ..., capacity_ah: _Optional[float] = ...) -> None: ...

class PredictRequest(_message.Message):
    __slots__ = ("battery_id", "readings", "reading_objects", "pack_config")
    BATTERY_ID_FIELD_NUMBER: _ClassVar[int]
    READINGS_FIELD_NUMBER: _ClassVar[int]
    READING_OBJECTS_FIELD_NUMBER: _ClassVar[int]
    PACK_CONFIG_FIELD_NUMBER: _ClassVar[int]
    battery_id: str
    readings: _containers.RepeatedCompositeFieldContainer[Reading]
    reading_objects: _containers.RepeatedCompositeFieldContainer[ReadingFields]
    pack_config: PackConfig
    def __init__(self, battery_id: _Optional[str] = ..., readings: _Optional[_Iterable[_Union[Reading, _Mapping]]] = ..., reading_objects: _Optional[_Iterable[_Union[ReadingFields, _Mapping]]] = ..., pack_config: _Optional[_Union[PackConfig, _Mapping]] = ...) -> None: ...

class WarningItem(_message.Message):
    __slots__ = ("code", "severity", "message")
    CODE_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    code: str
    severity: str
    message: str
    def __init__(self, code: _Optional[str] = ..., severity: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class FeatureStat(_message.Message):
    __slots__ = ("mean", "min", "max")
    MEAN_FIELD_NUMBER: _ClassVar[int]
    MIN_FIELD_NUMBER: _ClassVar[int]
    MAX_FIELD_NUMBER: _ClassVar[int]
    mean: float
    min: float
    max: float
    def __init__(self, mean: _Optional[float] = ..., min: _Optional[float] = ..., max: _Optional[float] = ...) -> None: ...

class PredictionInfo(_message.Message):
    __slots__ = ("soh_percent", "soh_confidence", "soh_std", "rul_cycles_estimate", "degradation_rate_per_cycle", "soh_trend", "cycles_to_maintenance", "soh_trajectory", "health_stage", "stage_probabilities", "stage_confidence", "is_borderline")
    class StageProbabilitiesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: float
        def __init__(self, key: _Optional[str] = ..., value: _Optional[float] = ...) -> None: ...
    SOH_PERCENT_FIELD_NUMBER: _ClassVar[int]
    SOH_CONFIDENCE_FIELD_NUMBER: _ClassVar[int]
    SOH_STD_FIELD_NUMBER: _ClassVar[int]
    RUL_CYCLES_ESTIMATE_FIELD_NUMBER: _ClassVar[int]
    DEGRADATION_RATE_PER_CYCLE_FIELD_NUMBER: _ClassVar[int]
    SOH_TREND_FIELD_NUMBER: _ClassVar[int]
    CYCLES_TO_MAINTENANCE_FIELD_NUMBER: _ClassVar[int]
    SOH_TRAJECTORY_FIELD_NUMBER: _ClassVar[int]
    HEALTH_STAGE_FIELD_NUMBER: _ClassVar[int]
    STAGE_PROBABILITIES_FIELD_NUMBER: _ClassVar[int]
    STAGE_CONFIDENCE_FIELD_NUMBER: _ClassVar[int]
    IS_BORDERLINE_FIELD_NUMBER: _ClassVar[int]
    soh_percent: float
    soh_confidence: float
    soh_std: float
    rul_cycles_estimate: int
    degradation_rate_per_cycle: float
    soh_trend: str
    cycles_to_maintenance: int
    soh_trajectory: _containers.RepeatedScalarFieldContainer[float]
    health_stage: str
    stage_probabilities: _containers.ScalarMap[str, float]
    stage_confidence: float
    is_borderline: bool
    def __init__(self, soh_percent: _Optional[float] = ..., soh_confidence: _Optional[float] = ..., soh_std: _Optional[float] = ..., rul_cycles_estimate: _Optional[int] = ..., degradation_rate_per_cycle: _Optional[float] = ..., soh_trend: _Optional[str] = ..., cycles_to_maintenance: _Optional[int] = ..., soh_trajectory: _Optional[_Iterable[float]] = ..., health_stage: _Optional[str] = ..., stage_probabilities: _Optional[_Mapping[str, float]] = ..., stage_confidence: _Optional[float] = ..., is_borderline: _Optional[bool] = ...) -> None: ...

class AnomalyInfo(_message.Message):
    __slots__ = ("anomaly_score", "anomaly_status", "anomaly_confidence")
    ANOMALY_SCORE_FIELD_NUMBER: _ClassVar[int]
    ANOMALY_STATUS_FIELD_NUMBER: _ClassVar[int]
    ANOMALY_CONFIDENCE_FIELD_NUMBER: _ClassVar[int]
    anomaly_score: float
    anomaly_status: str
    anomaly_confidence: float
    def __init__(self, anomaly_score: _Optional[float] = ..., anomaly_status: _Optional[str] = ..., anomaly_confidence: _Optional[float] = ...) -> None: ...

class RiskInfo(_message.Message):
    __slots__ = ("risk_level", "priority", "action_code", "reasons")
    RISK_LEVEL_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    ACTION_CODE_FIELD_NUMBER: _ClassVar[int]
    REASONS_FIELD_NUMBER: _ClassVar[int]
    risk_level: str
    priority: str
    action_code: str
    reasons: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, risk_level: _Optional[str] = ..., priority: _Optional[str] = ..., action_code: _Optional[str] = ..., reasons: _Optional[_Iterable[str]] = ...) -> None: ...

class EvidenceInfo(_message.Message):
    __slots__ = ("warnings", "feature_summary")
    class FeatureSummaryEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: FeatureStat
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[FeatureStat, _Mapping]] = ...) -> None: ...
    WARNINGS_FIELD_NUMBER: _ClassVar[int]
    FEATURE_SUMMARY_FIELD_NUMBER: _ClassVar[int]
    warnings: _containers.RepeatedCompositeFieldContainer[WarningItem]
    feature_summary: _containers.MessageMap[str, FeatureStat]
    def __init__(self, warnings: _Optional[_Iterable[_Union[WarningItem, _Mapping]]] = ..., feature_summary: _Optional[_Mapping[str, FeatureStat]] = ...) -> None: ...

class ResponseMetadata(_message.Message):
    __slots__ = ("model_version", "window_size", "input_features", "inference_ms", "n_series", "temperature_domain_distance", "is_temperature_ood", "chemistry", "capacity_ah")
    MODEL_VERSION_FIELD_NUMBER: _ClassVar[int]
    WINDOW_SIZE_FIELD_NUMBER: _ClassVar[int]
    INPUT_FEATURES_FIELD_NUMBER: _ClassVar[int]
    INFERENCE_MS_FIELD_NUMBER: _ClassVar[int]
    N_SERIES_FIELD_NUMBER: _ClassVar[int]
    TEMPERATURE_DOMAIN_DISTANCE_FIELD_NUMBER: _ClassVar[int]
    IS_TEMPERATURE_OOD_FIELD_NUMBER: _ClassVar[int]
    CHEMISTRY_FIELD_NUMBER: _ClassVar[int]
    CAPACITY_AH_FIELD_NUMBER: _ClassVar[int]
    model_version: str
    window_size: int
    input_features: int
    inference_ms: float
    n_series: int
    temperature_domain_distance: float
    is_temperature_ood: bool
    chemistry: str
    capacity_ah: float
    def __init__(self, model_version: _Optional[str] = ..., window_size: _Optional[int] = ..., input_features: _Optional[int] = ..., inference_ms: _Optional[float] = ..., n_series: _Optional[int] = ..., temperature_domain_distance: _Optional[float] = ..., is_temperature_ood: _Optional[bool] = ..., chemistry: _Optional[str] = ..., capacity_ah: _Optional[float] = ...) -> None: ...

class PredictResponse(_message.Message):
    __slots__ = ("battery_id", "prediction", "anomaly", "risk", "evidence", "metadata", "soh_percent", "classification", "confidence", "inference_ms", "rul_cycles_estimate", "degradation_rate_per_cycle", "soh_trend", "cycles_to_maintenance", "soh_trajectory", "anomaly_score", "recommended_action", "warnings", "feature_summary")
    class FeatureSummaryEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: FeatureStat
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[FeatureStat, _Mapping]] = ...) -> None: ...
    BATTERY_ID_FIELD_NUMBER: _ClassVar[int]
    PREDICTION_FIELD_NUMBER: _ClassVar[int]
    ANOMALY_FIELD_NUMBER: _ClassVar[int]
    RISK_FIELD_NUMBER: _ClassVar[int]
    EVIDENCE_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SOH_PERCENT_FIELD_NUMBER: _ClassVar[int]
    CLASSIFICATION_FIELD_NUMBER: _ClassVar[int]
    CONFIDENCE_FIELD_NUMBER: _ClassVar[int]
    INFERENCE_MS_FIELD_NUMBER: _ClassVar[int]
    RUL_CYCLES_ESTIMATE_FIELD_NUMBER: _ClassVar[int]
    DEGRADATION_RATE_PER_CYCLE_FIELD_NUMBER: _ClassVar[int]
    SOH_TREND_FIELD_NUMBER: _ClassVar[int]
    CYCLES_TO_MAINTENANCE_FIELD_NUMBER: _ClassVar[int]
    SOH_TRAJECTORY_FIELD_NUMBER: _ClassVar[int]
    ANOMALY_SCORE_FIELD_NUMBER: _ClassVar[int]
    RECOMMENDED_ACTION_FIELD_NUMBER: _ClassVar[int]
    WARNINGS_FIELD_NUMBER: _ClassVar[int]
    FEATURE_SUMMARY_FIELD_NUMBER: _ClassVar[int]
    battery_id: str
    prediction: PredictionInfo
    anomaly: AnomalyInfo
    risk: RiskInfo
    evidence: EvidenceInfo
    metadata: ResponseMetadata
    soh_percent: float
    classification: str
    confidence: float
    inference_ms: float
    rul_cycles_estimate: int
    degradation_rate_per_cycle: float
    soh_trend: str
    cycles_to_maintenance: int
    soh_trajectory: _containers.RepeatedScalarFieldContainer[float]
    anomaly_score: float
    recommended_action: str
    warnings: _containers.RepeatedCompositeFieldContainer[WarningItem]
    feature_summary: _containers.MessageMap[str, FeatureStat]
    def __init__(self, battery_id: _Optional[str] = ..., prediction: _Optional[_Union[PredictionInfo, _Mapping]] = ..., anomaly: _Optional[_Union[AnomalyInfo, _Mapping]] = ..., risk: _Optional[_Union[RiskInfo, _Mapping]] = ..., evidence: _Optional[_Union[EvidenceInfo, _Mapping]] = ..., metadata: _Optional[_Union[ResponseMetadata, _Mapping]] = ..., soh_percent: _Optional[float] = ..., classification: _Optional[str] = ..., confidence: _Optional[float] = ..., inference_ms: _Optional[float] = ..., rul_cycles_estimate: _Optional[int] = ..., degradation_rate_per_cycle: _Optional[float] = ..., soh_trend: _Optional[str] = ..., cycles_to_maintenance: _Optional[int] = ..., soh_trajectory: _Optional[_Iterable[float]] = ..., anomaly_score: _Optional[float] = ..., recommended_action: _Optional[str] = ..., warnings: _Optional[_Iterable[_Union[WarningItem, _Mapping]]] = ..., feature_summary: _Optional[_Mapping[str, FeatureStat]] = ...) -> None: ...

class PrescribeRequest(_message.Message):
    __slots__ = ("battery_id", "readings", "age_cycles", "last_maintenance_date", "ticket_history", "enrich", "pack_config", "agentic")
    BATTERY_ID_FIELD_NUMBER: _ClassVar[int]
    READINGS_FIELD_NUMBER: _ClassVar[int]
    AGE_CYCLES_FIELD_NUMBER: _ClassVar[int]
    LAST_MAINTENANCE_DATE_FIELD_NUMBER: _ClassVar[int]
    TICKET_HISTORY_FIELD_NUMBER: _ClassVar[int]
    ENRICH_FIELD_NUMBER: _ClassVar[int]
    PACK_CONFIG_FIELD_NUMBER: _ClassVar[int]
    AGENTIC_FIELD_NUMBER: _ClassVar[int]
    battery_id: str
    readings: _containers.RepeatedCompositeFieldContainer[Reading]
    age_cycles: int
    last_maintenance_date: str
    ticket_history: _containers.RepeatedScalarFieldContainer[str]
    enrich: bool
    pack_config: PackConfig
    agentic: bool
    def __init__(self, battery_id: _Optional[str] = ..., readings: _Optional[_Iterable[_Union[Reading, _Mapping]]] = ..., age_cycles: _Optional[int] = ..., last_maintenance_date: _Optional[str] = ..., ticket_history: _Optional[_Iterable[str]] = ..., enrich: _Optional[bool] = ..., pack_config: _Optional[_Union[PackConfig, _Mapping]] = ..., agentic: _Optional[bool] = ...) -> None: ...

class RetrievedDoc(_message.Message):
    __slots__ = ("title", "content", "source", "relevance_score", "retrieved_via")
    TITLE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    RELEVANCE_SCORE_FIELD_NUMBER: _ClassVar[int]
    RETRIEVED_VIA_FIELD_NUMBER: _ClassVar[int]
    title: str
    content: str
    source: str
    relevance_score: float
    retrieved_via: str
    def __init__(self, title: _Optional[str] = ..., content: _Optional[str] = ..., source: _Optional[str] = ..., relevance_score: _Optional[float] = ..., retrieved_via: _Optional[str] = ...) -> None: ...

class PrescribeResponse(_message.Message):
    __slots__ = ("battery_id", "soh_percent", "risk_level", "priority", "action_code", "prescription", "action_steps", "escalation_conditions", "ppe_required", "sop_references", "enriched", "maintenance_docs", "safety_docs", "human_verification_required", "safety_warnings", "inference_ms", "rag_ms", "llm_ms", "llm_provider", "blocked", "query_gen_ms", "generated_queries", "prescription_id", "prediction", "anomaly", "risk", "cached")
    BATTERY_ID_FIELD_NUMBER: _ClassVar[int]
    SOH_PERCENT_FIELD_NUMBER: _ClassVar[int]
    RISK_LEVEL_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    ACTION_CODE_FIELD_NUMBER: _ClassVar[int]
    PRESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ACTION_STEPS_FIELD_NUMBER: _ClassVar[int]
    ESCALATION_CONDITIONS_FIELD_NUMBER: _ClassVar[int]
    PPE_REQUIRED_FIELD_NUMBER: _ClassVar[int]
    SOP_REFERENCES_FIELD_NUMBER: _ClassVar[int]
    ENRICHED_FIELD_NUMBER: _ClassVar[int]
    MAINTENANCE_DOCS_FIELD_NUMBER: _ClassVar[int]
    SAFETY_DOCS_FIELD_NUMBER: _ClassVar[int]
    HUMAN_VERIFICATION_REQUIRED_FIELD_NUMBER: _ClassVar[int]
    SAFETY_WARNINGS_FIELD_NUMBER: _ClassVar[int]
    INFERENCE_MS_FIELD_NUMBER: _ClassVar[int]
    RAG_MS_FIELD_NUMBER: _ClassVar[int]
    LLM_MS_FIELD_NUMBER: _ClassVar[int]
    LLM_PROVIDER_FIELD_NUMBER: _ClassVar[int]
    BLOCKED_FIELD_NUMBER: _ClassVar[int]
    QUERY_GEN_MS_FIELD_NUMBER: _ClassVar[int]
    GENERATED_QUERIES_FIELD_NUMBER: _ClassVar[int]
    PRESCRIPTION_ID_FIELD_NUMBER: _ClassVar[int]
    PREDICTION_FIELD_NUMBER: _ClassVar[int]
    ANOMALY_FIELD_NUMBER: _ClassVar[int]
    RISK_FIELD_NUMBER: _ClassVar[int]
    CACHED_FIELD_NUMBER: _ClassVar[int]
    battery_id: str
    soh_percent: float
    risk_level: str
    priority: str
    action_code: str
    prescription: str
    action_steps: _containers.RepeatedScalarFieldContainer[str]
    escalation_conditions: _containers.RepeatedScalarFieldContainer[str]
    ppe_required: _containers.RepeatedScalarFieldContainer[str]
    sop_references: _containers.RepeatedScalarFieldContainer[str]
    enriched: bool
    maintenance_docs: _containers.RepeatedCompositeFieldContainer[RetrievedDoc]
    safety_docs: _containers.RepeatedCompositeFieldContainer[RetrievedDoc]
    human_verification_required: bool
    safety_warnings: _containers.RepeatedScalarFieldContainer[str]
    inference_ms: float
    rag_ms: float
    llm_ms: float
    llm_provider: str
    blocked: bool
    query_gen_ms: float
    generated_queries: _containers.RepeatedScalarFieldContainer[str]
    prescription_id: str
    prediction: PredictionInfo
    anomaly: AnomalyInfo
    risk: RiskInfo
    cached: bool
    def __init__(self, battery_id: _Optional[str] = ..., soh_percent: _Optional[float] = ..., risk_level: _Optional[str] = ..., priority: _Optional[str] = ..., action_code: _Optional[str] = ..., prescription: _Optional[str] = ..., action_steps: _Optional[_Iterable[str]] = ..., escalation_conditions: _Optional[_Iterable[str]] = ..., ppe_required: _Optional[_Iterable[str]] = ..., sop_references: _Optional[_Iterable[str]] = ..., enriched: _Optional[bool] = ..., maintenance_docs: _Optional[_Iterable[_Union[RetrievedDoc, _Mapping]]] = ..., safety_docs: _Optional[_Iterable[_Union[RetrievedDoc, _Mapping]]] = ..., human_verification_required: _Optional[bool] = ..., safety_warnings: _Optional[_Iterable[str]] = ..., inference_ms: _Optional[float] = ..., rag_ms: _Optional[float] = ..., llm_ms: _Optional[float] = ..., llm_provider: _Optional[str] = ..., blocked: _Optional[bool] = ..., query_gen_ms: _Optional[float] = ..., generated_queries: _Optional[_Iterable[str]] = ..., prescription_id: _Optional[str] = ..., prediction: _Optional[_Union[PredictionInfo, _Mapping]] = ..., anomaly: _Optional[_Union[AnomalyInfo, _Mapping]] = ..., risk: _Optional[_Union[RiskInfo, _Mapping]] = ..., cached: _Optional[bool] = ...) -> None: ...

class HealthRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HealthResponse(_message.Message):
    __slots__ = ("status", "model_version", "scaler_loaded", "mamba_loaded", "isolation_forest_loaded", "lfp_loaded", "lfp_model_version", "soc_mode", "lfp_soc_mode", "long_loaded", "long_model_version")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    MODEL_VERSION_FIELD_NUMBER: _ClassVar[int]
    SCALER_LOADED_FIELD_NUMBER: _ClassVar[int]
    MAMBA_LOADED_FIELD_NUMBER: _ClassVar[int]
    ISOLATION_FOREST_LOADED_FIELD_NUMBER: _ClassVar[int]
    LFP_LOADED_FIELD_NUMBER: _ClassVar[int]
    LFP_MODEL_VERSION_FIELD_NUMBER: _ClassVar[int]
    SOC_MODE_FIELD_NUMBER: _ClassVar[int]
    LFP_SOC_MODE_FIELD_NUMBER: _ClassVar[int]
    LONG_LOADED_FIELD_NUMBER: _ClassVar[int]
    LONG_MODEL_VERSION_FIELD_NUMBER: _ClassVar[int]
    status: str
    model_version: str
    scaler_loaded: bool
    mamba_loaded: bool
    isolation_forest_loaded: bool
    lfp_loaded: bool
    lfp_model_version: str
    soc_mode: str
    lfp_soc_mode: str
    long_loaded: bool
    long_model_version: str
    def __init__(self, status: _Optional[str] = ..., model_version: _Optional[str] = ..., scaler_loaded: _Optional[bool] = ..., mamba_loaded: _Optional[bool] = ..., isolation_forest_loaded: _Optional[bool] = ..., lfp_loaded: _Optional[bool] = ..., lfp_model_version: _Optional[str] = ..., soc_mode: _Optional[str] = ..., lfp_soc_mode: _Optional[str] = ..., long_loaded: _Optional[bool] = ..., long_model_version: _Optional[str] = ...) -> None: ...

class TicketSensorSnapshot(_message.Message):
    __slots__ = ("soh_percent", "voltage", "current", "temperature", "soc_percent", "has_active_alert", "temperature_max", "temperature_min", "soc_warning_threshold", "soh_warning_threshold")
    SOH_PERCENT_FIELD_NUMBER: _ClassVar[int]
    VOLTAGE_FIELD_NUMBER: _ClassVar[int]
    CURRENT_FIELD_NUMBER: _ClassVar[int]
    TEMPERATURE_FIELD_NUMBER: _ClassVar[int]
    SOC_PERCENT_FIELD_NUMBER: _ClassVar[int]
    HAS_ACTIVE_ALERT_FIELD_NUMBER: _ClassVar[int]
    TEMPERATURE_MAX_FIELD_NUMBER: _ClassVar[int]
    TEMPERATURE_MIN_FIELD_NUMBER: _ClassVar[int]
    SOC_WARNING_THRESHOLD_FIELD_NUMBER: _ClassVar[int]
    SOH_WARNING_THRESHOLD_FIELD_NUMBER: _ClassVar[int]
    soh_percent: float
    voltage: float
    current: float
    temperature: float
    soc_percent: float
    has_active_alert: bool
    temperature_max: float
    temperature_min: float
    soc_warning_threshold: float
    soh_warning_threshold: float
    def __init__(self, soh_percent: _Optional[float] = ..., voltage: _Optional[float] = ..., current: _Optional[float] = ..., temperature: _Optional[float] = ..., soc_percent: _Optional[float] = ..., has_active_alert: _Optional[bool] = ..., temperature_max: _Optional[float] = ..., temperature_min: _Optional[float] = ..., soc_warning_threshold: _Optional[float] = ..., soh_warning_threshold: _Optional[float] = ...) -> None: ...

class DuplicateCandidate(_message.Message):
    __slots__ = ("ticket_id", "description", "category", "detected_at", "is_machine_written")
    TICKET_ID_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    DETECTED_AT_FIELD_NUMBER: _ClassVar[int]
    IS_MACHINE_WRITTEN_FIELD_NUMBER: _ClassVar[int]
    ticket_id: str
    description: str
    category: int
    detected_at: str
    is_machine_written: bool
    def __init__(self, ticket_id: _Optional[str] = ..., description: _Optional[str] = ..., category: _Optional[int] = ..., detected_at: _Optional[str] = ..., is_machine_written: _Optional[bool] = ...) -> None: ...

class VerifyTicketRequest(_message.Message):
    __slots__ = ("title", "description", "detected_at", "category", "sensor_snapshot", "has_sensor_snapshot", "candidates", "is_machine_written")
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DETECTED_AT_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    SENSOR_SNAPSHOT_FIELD_NUMBER: _ClassVar[int]
    HAS_SENSOR_SNAPSHOT_FIELD_NUMBER: _ClassVar[int]
    CANDIDATES_FIELD_NUMBER: _ClassVar[int]
    IS_MACHINE_WRITTEN_FIELD_NUMBER: _ClassVar[int]
    title: str
    description: str
    detected_at: str
    category: int
    sensor_snapshot: TicketSensorSnapshot
    has_sensor_snapshot: bool
    candidates: _containers.RepeatedCompositeFieldContainer[DuplicateCandidate]
    is_machine_written: bool
    def __init__(self, title: _Optional[str] = ..., description: _Optional[str] = ..., detected_at: _Optional[str] = ..., category: _Optional[int] = ..., sensor_snapshot: _Optional[_Union[TicketSensorSnapshot, _Mapping]] = ..., has_sensor_snapshot: _Optional[bool] = ..., candidates: _Optional[_Iterable[_Union[DuplicateCandidate, _Mapping]]] = ..., is_machine_written: _Optional[bool] = ...) -> None: ...

class VerifyTicketResponse(_message.Message):
    __slots__ = ("verdict", "score", "reason", "duplicate_of_ticket_id", "duplicate_score", "duplicate_reason")
    VERDICT_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    DUPLICATE_OF_TICKET_ID_FIELD_NUMBER: _ClassVar[int]
    DUPLICATE_SCORE_FIELD_NUMBER: _ClassVar[int]
    DUPLICATE_REASON_FIELD_NUMBER: _ClassVar[int]
    verdict: str
    score: float
    reason: str
    duplicate_of_ticket_id: str
    duplicate_score: float
    duplicate_reason: str
    def __init__(self, verdict: _Optional[str] = ..., score: _Optional[float] = ..., reason: _Optional[str] = ..., duplicate_of_ticket_id: _Optional[str] = ..., duplicate_score: _Optional[float] = ..., duplicate_reason: _Optional[str] = ...) -> None: ...

class SubmitFeedbackRequest(_message.Message):
    __slots__ = ("prescription_id", "status", "edited_steps", "note")
    PRESCRIPTION_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    EDITED_STEPS_FIELD_NUMBER: _ClassVar[int]
    NOTE_FIELD_NUMBER: _ClassVar[int]
    prescription_id: str
    status: str
    edited_steps: _containers.RepeatedScalarFieldContainer[str]
    note: str
    def __init__(self, prescription_id: _Optional[str] = ..., status: _Optional[str] = ..., edited_steps: _Optional[_Iterable[str]] = ..., note: _Optional[str] = ...) -> None: ...

class SubmitFeedbackResponse(_message.Message):
    __slots__ = ("success",)
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    def __init__(self, success: _Optional[bool] = ...) -> None: ...

class PredictLongRequest(_message.Message):
    __slots__ = ("battery_id", "readings", "pack_config")
    BATTERY_ID_FIELD_NUMBER: _ClassVar[int]
    READINGS_FIELD_NUMBER: _ClassVar[int]
    PACK_CONFIG_FIELD_NUMBER: _ClassVar[int]
    battery_id: str
    readings: _containers.RepeatedCompositeFieldContainer[Reading]
    pack_config: PackConfig
    def __init__(self, battery_id: _Optional[str] = ..., readings: _Optional[_Iterable[_Union[Reading, _Mapping]]] = ..., pack_config: _Optional[_Union[PackConfig, _Mapping]] = ...) -> None: ...

class PredictLongResponse(_message.Message):
    __slots__ = ("battery_id", "soh_percent", "seq_len", "device", "inference_ms", "model_version")
    BATTERY_ID_FIELD_NUMBER: _ClassVar[int]
    SOH_PERCENT_FIELD_NUMBER: _ClassVar[int]
    SEQ_LEN_FIELD_NUMBER: _ClassVar[int]
    DEVICE_FIELD_NUMBER: _ClassVar[int]
    INFERENCE_MS_FIELD_NUMBER: _ClassVar[int]
    MODEL_VERSION_FIELD_NUMBER: _ClassVar[int]
    battery_id: str
    soh_percent: float
    seq_len: int
    device: str
    inference_ms: float
    model_version: str
    def __init__(self, battery_id: _Optional[str] = ..., soh_percent: _Optional[float] = ..., seq_len: _Optional[int] = ..., device: _Optional[str] = ..., inference_ms: _Optional[float] = ..., model_version: _Optional[str] = ...) -> None: ...

class ClassificationFeedbackRequest(_message.Message):
    __slots__ = ("battery_id", "classification", "verdict", "model_version", "classified_at", "note")
    BATTERY_ID_FIELD_NUMBER: _ClassVar[int]
    CLASSIFICATION_FIELD_NUMBER: _ClassVar[int]
    VERDICT_FIELD_NUMBER: _ClassVar[int]
    MODEL_VERSION_FIELD_NUMBER: _ClassVar[int]
    CLASSIFIED_AT_FIELD_NUMBER: _ClassVar[int]
    NOTE_FIELD_NUMBER: _ClassVar[int]
    battery_id: str
    classification: str
    verdict: str
    model_version: str
    classified_at: str
    note: str
    def __init__(self, battery_id: _Optional[str] = ..., classification: _Optional[str] = ..., verdict: _Optional[str] = ..., model_version: _Optional[str] = ..., classified_at: _Optional[str] = ..., note: _Optional[str] = ...) -> None: ...

class ClassificationFeedbackResponse(_message.Message):
    __slots__ = ("success", "total", "correct", "false_positive", "false_negative", "precision", "has_precision", "recall", "has_recall")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    CORRECT_FIELD_NUMBER: _ClassVar[int]
    FALSE_POSITIVE_FIELD_NUMBER: _ClassVar[int]
    FALSE_NEGATIVE_FIELD_NUMBER: _ClassVar[int]
    PRECISION_FIELD_NUMBER: _ClassVar[int]
    HAS_PRECISION_FIELD_NUMBER: _ClassVar[int]
    RECALL_FIELD_NUMBER: _ClassVar[int]
    HAS_RECALL_FIELD_NUMBER: _ClassVar[int]
    success: bool
    total: int
    correct: int
    false_positive: int
    false_negative: int
    precision: float
    has_precision: bool
    recall: float
    has_recall: bool
    def __init__(self, success: _Optional[bool] = ..., total: _Optional[int] = ..., correct: _Optional[int] = ..., false_positive: _Optional[int] = ..., false_negative: _Optional[int] = ..., precision: _Optional[float] = ..., has_precision: _Optional[bool] = ..., recall: _Optional[float] = ..., has_recall: _Optional[bool] = ...) -> None: ...

class StaffCandidate(_message.Message):
    __slots__ = ("staff_id", "full_name", "skill_tier", "skill_codes", "active_tickets", "max_concurrent")
    STAFF_ID_FIELD_NUMBER: _ClassVar[int]
    FULL_NAME_FIELD_NUMBER: _ClassVar[int]
    SKILL_TIER_FIELD_NUMBER: _ClassVar[int]
    SKILL_CODES_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_TICKETS_FIELD_NUMBER: _ClassVar[int]
    MAX_CONCURRENT_FIELD_NUMBER: _ClassVar[int]
    staff_id: str
    full_name: str
    skill_tier: int
    skill_codes: _containers.RepeatedScalarFieldContainer[str]
    active_tickets: int
    max_concurrent: int
    def __init__(self, staff_id: _Optional[str] = ..., full_name: _Optional[str] = ..., skill_tier: _Optional[int] = ..., skill_codes: _Optional[_Iterable[str]] = ..., active_tickets: _Optional[int] = ..., max_concurrent: _Optional[int] = ...) -> None: ...

class SuggestStaffRequest(_message.Message):
    __slots__ = ("category", "priority", "description", "candidates", "top_n")
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    CANDIDATES_FIELD_NUMBER: _ClassVar[int]
    TOP_N_FIELD_NUMBER: _ClassVar[int]
    category: int
    priority: int
    description: str
    candidates: _containers.RepeatedCompositeFieldContainer[StaffCandidate]
    top_n: int
    def __init__(self, category: _Optional[int] = ..., priority: _Optional[int] = ..., description: _Optional[str] = ..., candidates: _Optional[_Iterable[_Union[StaffCandidate, _Mapping]]] = ..., top_n: _Optional[int] = ...) -> None: ...

class StaffSuggestion(_message.Message):
    __slots__ = ("staff_id", "full_name", "score", "reason", "tier_ok")
    STAFF_ID_FIELD_NUMBER: _ClassVar[int]
    FULL_NAME_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    TIER_OK_FIELD_NUMBER: _ClassVar[int]
    staff_id: str
    full_name: str
    score: float
    reason: str
    tier_ok: bool
    def __init__(self, staff_id: _Optional[str] = ..., full_name: _Optional[str] = ..., score: _Optional[float] = ..., reason: _Optional[str] = ..., tier_ok: _Optional[bool] = ...) -> None: ...

class SuggestStaffResponse(_message.Message):
    __slots__ = ("suggestions", "note")
    SUGGESTIONS_FIELD_NUMBER: _ClassVar[int]
    NOTE_FIELD_NUMBER: _ClassVar[int]
    suggestions: _containers.RepeatedCompositeFieldContainer[StaffSuggestion]
    note: str
    def __init__(self, suggestions: _Optional[_Iterable[_Union[StaffSuggestion, _Mapping]]] = ..., note: _Optional[str] = ...) -> None: ...

class KbCandidate(_message.Message):
    __slots__ = ("kb_id", "code", "title", "tags", "category", "helpful_count")
    KB_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    HELPFUL_COUNT_FIELD_NUMBER: _ClassVar[int]
    kb_id: str
    code: str
    title: str
    tags: _containers.RepeatedScalarFieldContainer[str]
    category: int
    helpful_count: int
    def __init__(self, kb_id: _Optional[str] = ..., code: _Optional[str] = ..., title: _Optional[str] = ..., tags: _Optional[_Iterable[str]] = ..., category: _Optional[int] = ..., helpful_count: _Optional[int] = ...) -> None: ...

class SuggestKbRequest(_message.Message):
    __slots__ = ("category", "description", "candidates", "top_n", "ai_action_steps", "ai_sop_references", "ai_kb_doc_refs")
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    CANDIDATES_FIELD_NUMBER: _ClassVar[int]
    TOP_N_FIELD_NUMBER: _ClassVar[int]
    AI_ACTION_STEPS_FIELD_NUMBER: _ClassVar[int]
    AI_SOP_REFERENCES_FIELD_NUMBER: _ClassVar[int]
    AI_KB_DOC_REFS_FIELD_NUMBER: _ClassVar[int]
    category: int
    description: str
    candidates: _containers.RepeatedCompositeFieldContainer[KbCandidate]
    top_n: int
    ai_action_steps: _containers.RepeatedScalarFieldContainer[str]
    ai_sop_references: _containers.RepeatedScalarFieldContainer[str]
    ai_kb_doc_refs: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, category: _Optional[int] = ..., description: _Optional[str] = ..., candidates: _Optional[_Iterable[_Union[KbCandidate, _Mapping]]] = ..., top_n: _Optional[int] = ..., ai_action_steps: _Optional[_Iterable[str]] = ..., ai_sop_references: _Optional[_Iterable[str]] = ..., ai_kb_doc_refs: _Optional[_Iterable[str]] = ...) -> None: ...

class KbSuggestion(_message.Message):
    __slots__ = ("kb_id", "code", "title", "score", "reason")
    KB_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    kb_id: str
    code: str
    title: str
    score: float
    reason: str
    def __init__(self, kb_id: _Optional[str] = ..., code: _Optional[str] = ..., title: _Optional[str] = ..., score: _Optional[float] = ..., reason: _Optional[str] = ...) -> None: ...

class SuggestKbResponse(_message.Message):
    __slots__ = ("suggestions", "note")
    SUGGESTIONS_FIELD_NUMBER: _ClassVar[int]
    NOTE_FIELD_NUMBER: _ClassVar[int]
    suggestions: _containers.RepeatedCompositeFieldContainer[KbSuggestion]
    note: str
    def __init__(self, suggestions: _Optional[_Iterable[_Union[KbSuggestion, _Mapping]]] = ..., note: _Optional[str] = ...) -> None: ...
