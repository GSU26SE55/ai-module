"""Schemas cho POST /suggest/staff và POST /suggest/kb.

Human-in-the-loop: AI chỉ XẾP HẠNG và nêu lý do — Manager quyết định giao việc cho ai,
kỹ thuật viên quyết định đọc tài liệu nào. AI KHÔNG tự phân công, KHÔNG tự gắn tài liệu.

ai-module không đọc được DB của TicketService, nên BE truy vấn ứng viên rồi gửi kèm
trong request (cùng cách `VerifyTicketRequest.candidates` đang làm).
"""

from pydantic import BaseModel, Field

# Số gợi ý mặc định khi caller không chỉ định (top_n = 0).
DEFAULT_TOP_N = 5
MAX_TOP_N = 10


# ── Gợi ý Staff ────────────────────────────────────────────────────────────


class StaffCandidate(BaseModel):
    """1 nhân viên ứng viên — BE đã lọc sẵn Active + IsAvailable + đúng vai trò Staff."""

    staff_id: str
    full_name: str = ""
    skill_tier: int = 0  # StaffSkillTierEnum: 1=Generalist, 2=ModuleSpecialist, 3=SeniorSpecialist
    skill_codes: list[str] = Field(default_factory=list)
    active_tickets: int = 0  # BE đếm sẵn (đã loại PreviousPrimaryHandler)
    max_concurrent: int = 0  # 0 = không giới hạn


class SuggestStaffRequest(BaseModel):
    category: int = 0  # TicketCategoryEnum
    priority: int = 0  # TicketPriorityEnum; 0 = ticket chưa được gán priority
    description: str = ""  # Title + Description ticket
    candidates: list[StaffCandidate] = Field(default_factory=list)
    top_n: int = 0  # 0 → DEFAULT_TOP_N


class StaffSuggestion(BaseModel):
    staff_id: str
    full_name: str = ""
    score: float  # [0..1]
    reason: str  # English — surfaced verbatim on web and mobile
    tier_ok: bool = True


class SuggestStaffResponse(BaseModel):
    suggestions: list[StaffSuggestion] = Field(default_factory=list)
    # Lý do danh sách rỗng/ngắn — để UI nói được "vì sao không có ai" thay vì hiện bảng trắng.
    note: str = ""


# ── Gợi ý KB ───────────────────────────────────────────────────────────────


class KbCandidate(BaseModel):
    """1 bài viết KB — BE đã lọc sẵn Status=Published."""

    kb_id: str
    code: str = ""
    title: str = ""
    tags: list[str] = Field(default_factory=list)
    category: int = 0  # TicketCategoryEnum
    helpful_count: int = 0


class SuggestKbRequest(BaseModel):
    category: int = 0
    description: str = ""  # Title + Description ticket
    candidates: list[KbCandidate] = Field(default_factory=list)
    top_n: int = 0

    # Dữ liệu AI đã sinh cho chính ticket này (bảng `ticket_ai_suggestions`).
    # Rỗng với ticket do Customer tạo — khi đó chỉ dựa vào `description`.
    ai_action_steps: list[str] = Field(default_factory=list)
    # Tín hiệu MẠNH NHẤT: tài liệu AI thực sự truy hồi được qua RAG khi kê đơn.
    ai_sop_references: list[str] = Field(default_factory=list)
    ai_kb_doc_refs: list[str] = Field(default_factory=list)


class KbSuggestion(BaseModel):
    kb_id: str
    code: str = ""
    title: str = ""
    score: float  # [0..1]
    reason: str


class SuggestKbResponse(BaseModel):
    suggestions: list[KbSuggestion] = Field(default_factory=list)
    note: str = ""
