from fastapi import APIRouter

from src.schemas.verify import VerifyTicketRequest, VerifyTicketResponse
from src.services.verify import run_verify

router = APIRouter(prefix="/verify-ticket", tags=["verify"])


@router.post("/", response_model=VerifyTicketResponse)
async def verify_ticket(request: VerifyTicketRequest) -> VerifyTicketResponse:
    return run_verify(request)
