# Skill: /scaffold-fastapi-endpoint

## Kích hoạt
`/scaffold-fastapi-endpoint <tên-endpoint>` — tạo FastAPI endpoint mới với Pydantic schema, model loading, error handling.

**Ví dụ:** `/scaffold-fastapi-endpoint predict-soh`

---

## Quy trình

1. **Xác định endpoint cần tạo**
   - Đọc context: endpoint phục vụ SOH prediction, anomaly detection, hay data preprocessing?
   - Xác định input fields và output fields

2. **Tạo file theo cấu trúc:**

```
ai-module/
├── api/
│   ├── main.py              ← FastAPI app + startup model load
│   ├── routers/
│   │   └── {name}.py        ← Router cho endpoint
│   └── schemas/
│       └── {name}.py        ← Pydantic input/output schemas
├── models/
│   └── {name}_model.py      ← Model class (load từ .pt)
```

3. **Template — schemas/{name}.py**

```python
from pydantic import BaseModel, Field, field_validator
from typing import Literal


class PredictRequest(BaseModel):
    voltage: list[float] = Field(..., min_length=1, description="Voltage readings (V)")
    current: list[float] = Field(..., min_length=1, description="Current readings (A)")
    temperature: list[float] = Field(..., min_length=1, description="Temperature readings (°C)")

    @field_validator("voltage", "current", "temperature")
    @classmethod
    def check_no_empty(cls, v: list[float]) -> list[float]:
        if not v:
            raise ValueError("List cannot be empty")
        return v


class PredictResponse(BaseModel):
    status: Literal["Normal", "Degrading", "Failed"]
    soh_percent: float = Field(..., ge=0.0, le=100.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
```

4. **Template — routers/{name}.py**

```python
from fastapi import APIRouter, HTTPException, Depends, Request
from api.schemas.{name} import PredictRequest, PredictResponse
from models.{name}_model import {Name}Model

router = APIRouter(prefix="/{name}", tags=["{name}"])


def get_model(request: Request) -> {Name}Model:
    """Lấy model đã load từ app state — không load lại mỗi request."""
    return request.app.state.model


@router.post("/predict", response_model=PredictResponse)
async def predict(body: PredictRequest, model: {Name}Model = Depends(get_model)):
    try:
        result = model.predict(
            voltage=body.voltage,
            current=body.current,
            temperature=body.temperature,
        )
        return PredictResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Prediction failed")
```

5. **Template — api/main.py (nếu chưa có)**

```python
import random
import numpy as np
import torch
from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.routers import {name}
from models.{name}_model import {Name}Model

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load model 1 lần khi startup
    app.state.model = {Name}Model.load("models/weights/{name}.pt")
    yield
    # Cleanup nếu cần


app = FastAPI(title="AI Module — GSU26SE55", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Giới hạn lại khi deploy production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router({name}.router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

**Thêm import CORSMiddleware vào đầu file:**
```python
from fastapi.middleware.cors import CORSMiddleware
```

**Chạy server:**
```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Checklist sau khi scaffold

- [ ] Schema có field validator cho input không hợp lệ?
- [ ] `get_model` dependency được định nghĩa trong router, lấy từ `request.app.state.model`?
- [ ] Model load trong `lifespan`, không load trong route handler?
- [ ] Response có đủ 3 fields: `status`, `soh_percent`, `confidence`?
- [ ] `random_seed` được set ở đầu `main.py`?
- [ ] `requirements.txt` có pin version của tất cả dependency?

---

## Không được
- Load model trong mỗi request — phải load 1 lần lúc startup
- Bỏ qua Pydantic validation — không nhận raw dict từ request
- Để exception không được handle trả về 500 mà không có message rõ ràng
- Thêm endpoint thứ 3+ (ngoài SOH prediction + anomaly detection) mà chưa có Leader approval
