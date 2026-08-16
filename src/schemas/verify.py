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

    # Ngưỡng THẬT của loại pin này (`threshold_configs` — chính hàng mà `AnomalyRules` đọc để
    # nổ alert). Bắt buộc phải đi kèm snapshot, không được hardcode phía AI: đội pin trộn
    # 12V/24V/48V với nhiều chemistry, một bộ số không mô tả nổi tất cả. Trước đây verify so
    # với 45°C/SOC 15% cố định, trong khi LFP 24V có ngưỡng thật 60°C/SOC 20% ⇒ pin ở 50°C
    # (backend KHÔNG coi là lỗi) vẫn được AI cộng điểm "khớp sensor thật", tức xác nhận một
    # sự cố không tồn tại.
    #
    # 0.0 = không rõ ngưỡng → luật tương ứng bị bỏ qua thay vì đoán bừa.
    temperature_max: float = 0.0
    temperature_min: float = 0.0
    soc_warning_threshold: float = 0.0
    soh_warning_threshold: float = 0.0


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
    score: float  # [0..1] legitimacy (1 = certainly genuine)
    reason: str  # human-readable rationale shown to the Manager (English)
    duplicate_of_ticket_id: str = ""  # "" nếu không nghi trùng
    duplicate_score: float = 0.0  # [0..1] độ tương đồng cao nhất
    duplicate_reason: str = ""
