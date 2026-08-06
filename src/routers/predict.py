from fastapi import APIRouter, HTTPException

from src.schemas.predict import (
    ClassificationFeedbackRequest,
    ClassificationFeedbackResponse,
    PredictLongRequest,
    PredictLongResponse,
    PredictRequest,
    PredictResponse,
)
from src.services.classification_feedback import record_feedback
from src.services.inference import predict_soh_long, run_inference

router = APIRouter(prefix="/predict", tags=["predict"])


@router.post("/", response_model=PredictResponse)
async def predict(request: PredictRequest) -> PredictResponse:
    pack = request.pack_config
    try:
        result = run_inference(
            request.readings,
            n_series=pack.n_series if pack else 1,
            chemistry=pack.chemistry if pack else None,
            capacity_ah=pack.capacity_ah if pack else None,
            battery_id=request.battery_id,
        )
    except ValueError as exc:
        # Payload không khớp bộ artifact được chọn (điển hình: 4 cột cho bộ
        # soc_mode="cycle"). Lỗi của INPUT ⇒ 422, khớp INVALID_ARGUMENT bên gRPC.
        # Để rơi ra 500 sẽ khiến caller tưởng service hỏng và đi retry vô ích.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PredictResponse(
        battery_id=request.battery_id,
        **result,
    )


@router.post("/long", response_model=PredictLongResponse)
async def predict_long(request: PredictLongRequest) -> PredictLongResponse:
    """GH-10 — SOH from a long raw series (31..4096 timesteps).

    Returns SOH ONLY. No MC-dropout (so no confidence/std/health_stage) and no
    IsolationForest (so no anomaly/risk/warnings): that forest is fitted on the
    window=30 feature distribution, and scoring a 4096-step series with it would
    be out-of-distribution — a number that looks valid and means nothing.

    For ticket creation keep using /prescribe. This endpoint is for long-history
    analysis and charts.
    """
    pack = request.pack_config
    result = predict_soh_long(
        request.readings,
        n_series=pack.n_series if pack else 1,
        capacity_ah=pack.capacity_ah if pack else None,
    )
    return PredictLongResponse(battery_id=request.battery_id, **result)


@router.post("/feedback", response_model=ClassificationFeedbackResponse)
async def classification_feedback(
    request: ClassificationFeedbackRequest,
) -> ClassificationFeedbackResponse:
    """F4 — kỹ thuật viên chấm lại phân loại của AI (correct / false_positive / false_negative).

    Khép vòng học cho nhánh anomaly. BE đã lưu `staff_feedback` từ lâu nhưng chưa có đường
    gửi ngược về đây, nên AI không bao giờ biết mình phân loại sai để mà sửa ở lần retrain.

    Trả về bộ đếm chạy hiện tại để caller thấy ghi nhận thành công và theo dõi được
    precision/recall thô mà không cần đọc file.
    """
    try:
        counts = record_feedback(
            battery_id=request.battery_id,
            classification=request.classification,
            verdict=request.verdict,
            model_version=request.model_version,
            classified_at=request.classified_at,
            note=request.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ClassificationFeedbackResponse(success=True, **counts)
