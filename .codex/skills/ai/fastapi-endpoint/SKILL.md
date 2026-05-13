---
name: fastapi-endpoint
description: Creating a FastAPI endpoint or router in the AI module. Triggers when adding a new inference endpoint, prediction route, health check, or any FastAPI path operation. Models (LSTM, IsolationForest) and scaler are loaded once at startup — never per-request.
---

## Nguyên tắc bắt buộc

1. **Tuân thủ tuyệt đối** cấu trúc router, schema, và code pattern được định nghĩa trong skill này — không tự ý thay đổi input shape (30, 3), load model per-request, hay bỏ qua benchmark latency.
2. **Hỏi trước khi code** nếu bất kỳ yêu cầu nào chưa rõ (endpoint mới cần input/output gì, model version nào dùng, threshold classify thế nào). Không đoán mò — một câu hỏi ngắn tốt hơn một giờ implement sai hướng.

---

# AI FastAPI Endpoint Pattern

## Router structure

```python
# src/routers/predict.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import torch
import numpy as np

router = APIRouter(prefix="/predict", tags=["predict"])
```

## Request / Response schemas

```python
class PredictRequest(BaseModel):
    battery_id: str
    readings: list[list[float]]  # shape: (30, 3) — [voltage, current, temperature]

class PredictResponse(BaseModel):
    battery_id: str
    soh_percent: float
    classification: str          # "Normal" | "Degrading" | "Failed"
    confidence: float
    inference_ms: float
```

## Endpoint

```python
@router.post("/", response_model=PredictResponse)
async def predict(request: PredictRequest):
    if len(request.readings) != 30 or any(len(r) != 3 for r in request.readings):
        raise HTTPException(status_code=422, detail="readings must be shape (30, 3)")

    import time
    start = time.perf_counter()

    x = np.array(request.readings, dtype=np.float32)
    x_scaled = scaler.transform(x)                           # MinMaxScaler from startup
    x_tensor = torch.tensor(x_scaled).unsqueeze(0)          # (1, 30, 3)

    with torch.no_grad():
        soh = soh_model(x_tensor).item() * 100              # → SOH%

    score = iso_model.decision_function([x_scaled.flatten()])[0]
    classification = classify_anomaly(score, soh)

    elapsed_ms = (time.perf_counter() - start) * 1000

    return PredictResponse(
        battery_id=request.battery_id,
        soh_percent=round(soh, 2),
        classification=classification,
        confidence=round(min(1.0, abs(score)), 3),
        inference_ms=round(elapsed_ms, 2),
    )
```

## Anomaly classification

```python
def classify_anomaly(score: float, soh: float) -> str:
    if score > -0.1:
        return "Normal"
    elif score > -0.3 or soh >= 80:
        return "Degrading"
    else:
        return "Failed"
```

## Models loaded at startup (main.py)

```python
# Load once — never per-request
scaler_artifact = joblib.load("models/weights/scaler.pkl")
assert scaler_artifact["version"] == SCALER_VERSION
scaler = scaler_artifact["scaler"]

checkpoint = torch.load(f"models/weights/soh_lstm_v{MODEL_VERSION}.pth", map_location="cpu")
soh_model = SOHPredictor()
soh_model.load_state_dict(checkpoint["model_state_dict"])
soh_model.eval()

iso_model = joblib.load(f"models/weights/isolation_forest_v{MODEL_VERSION}.pkl")
```

## Health endpoint

```python
@router.get("/health")
async def health():
    return {
        "status": "ok",
        "model_version": MODEL_VERSION,
        "scaler_loaded": scaler is not None,
        "lstm_loaded": soh_model is not None,
        "isolation_forest_loaded": iso_model is not None,
    }
```

## Latency SLA

- P1 Critical: inference **< 100ms**
- P2/P3: < 500ms

Always return `inference_ms` in response for monitoring.

## Rules

- Never fit/transform scaler on production data — load from `models/weights/scaler.pkl`
- Never reload model per-request — use startup globals
- Random seed = `42` in all training scripts
- Output must always include: classification + soh_percent + confidence
