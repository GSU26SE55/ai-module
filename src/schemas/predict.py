from pydantic import BaseModel, field_validator

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


class PredictResponse(BaseModel):
    battery_id: str
    soh_percent: float
    classification: str  # "Normal" | "Degrading" | "Failed"
    confidence: float
    inference_ms: float
