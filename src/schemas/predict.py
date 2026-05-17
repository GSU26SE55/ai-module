from pydantic import BaseModel, field_validator


class PredictRequest(BaseModel):
    battery_id: str
    readings: list[list[float]]  # shape: (30, 3) — [voltage, current, temperature]

    @field_validator("readings")
    @classmethod
    def validate_readings_shape(cls, v: list[list[float]]) -> list[list[float]]:
        if len(v) != 30:
            raise ValueError(f"readings must have 30 timesteps, got {len(v)}")
        for i, row in enumerate(v):
            if len(row) != 3:
                raise ValueError(
                    f"readings[{i}] must have 3 features [voltage, current, temperature], got {len(row)}"
                )
        return v


class PredictResponse(BaseModel):
    battery_id: str
    soh_percent: float
    classification: str  # "Normal" | "Degrading" | "Failed"
    confidence: float
    inference_ms: float
