"""Schemas cho POST /verify-ticket — chấm điểm ticket thủ công thật/rác + dò trùng.

Human-in-the-loop: AI chỉ gắn nhãn + lý do, Manager quyết định cuối. KHÔNG tự chặn.
"""

from pydantic import BaseModel, Field


class TicketSensorSnapshot(BaseModel):
    """Snapshot sensor pin tại thời điểm phát hiện — để đối chiếu mô tả với thực tế."""

    soh_percent: float = 0.0
    voltage: float = 0.0
    current: float = 0.0
    temperature: float = 0.0
    soc_percent: float = 0.0
    has_active_alert: bool = False


class DuplicateCandidate(BaseModel):
    """1 ticket đang mở cùng pin — để so trùng mô tả."""

    ticket_id: str
    description: str = ""
    category: int = 0  # TicketCategoryEnum (khớp BE)


class VerifyTicketRequest(BaseModel):
    title: str = ""
    description: str = ""
    detected_at: str = ""  # ISO UTC, "" nếu không có
    category: int = 0  # TicketCategoryEnum ticket mới
    sensor_snapshot: TicketSensorSnapshot | None = None
    candidates: list[DuplicateCandidate] = Field(default_factory=list)


class VerifyTicketResponse(BaseModel):
    verdict: str  # "legitimate" | "suspicious"
    score: float  # [0..1] độ hợp lệ (1 = chắc chắn thật)
    reason: str  # lý do (tiếng Việt, cho Manager đọc)
    duplicate_of_ticket_id: str = ""  # "" nếu không nghi trùng
    duplicate_score: float = 0.0  # [0..1] độ tương đồng cao nhất
    duplicate_reason: str = ""
