from fastapi import APIRouter

from src.schemas.suggest import (
    SuggestKbRequest,
    SuggestKbResponse,
    SuggestStaffRequest,
    SuggestStaffResponse,
)
from src.services.suggest_kb import run_suggest_kb
from src.services.suggest_staff import run_suggest_staff

router = APIRouter(prefix="/suggest", tags=["suggest"])


@router.post("/staff", response_model=SuggestStaffResponse)
async def suggest_staff(request: SuggestStaffRequest) -> SuggestStaffResponse:
    """Xếp hạng nhân viên phù hợp xử lý ticket. Manager quyết định cuối."""
    return run_suggest_staff(request)


@router.post("/kb", response_model=SuggestKbResponse)
async def suggest_kb(request: SuggestKbRequest) -> SuggestKbResponse:
    """Xếp hạng bài viết KB để tham khảo khi sửa chữa. Kỹ thuật viên quyết định cuối."""
    return run_suggest_kb(request)
