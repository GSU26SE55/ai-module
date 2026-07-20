from fastapi import APIRouter

from src.schemas.predict import PredictRequest, PredictResponse
from src.services.inference import run_inference

router = APIRouter(prefix="/predict", tags=["predict"])


@router.post("/", response_model=PredictResponse)
async def predict(request: PredictRequest) -> PredictResponse:
    pack = request.pack_config
    result = run_inference(
        request.readings,
        n_series=pack.n_series if pack else 1,
        chemistry=pack.chemistry if pack else None,
        capacity_ah=pack.capacity_ah if pack else None,
        battery_id=request.battery_id,
    )
    return PredictResponse(
        battery_id=request.battery_id,
        **result,
    )
