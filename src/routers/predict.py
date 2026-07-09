from fastapi import APIRouter

from src.schemas.predict import PredictRequest, PredictResponse
from src.services.inference import run_inference

router = APIRouter(prefix="/predict", tags=["predict"])


@router.post("/", response_model=PredictResponse)
async def predict(request: PredictRequest) -> PredictResponse:
    n_series = request.pack_config.n_series if request.pack_config else 1
    result = run_inference(
        request.readings, n_series=n_series, battery_id=request.battery_id
    )
    return PredictResponse(
        battery_id=request.battery_id,
        **result,
    )
