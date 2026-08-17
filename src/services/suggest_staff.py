"""run_suggest_staff — xếp hạng nhân viên phù hợp để xử lý một ticket.

Thiết kế deterministic (luật khớp kỹ năng + tier + tải hiện tại) — KHÔNG dùng LLM,
cùng lý do đã chọn cho `verify.py`: chạy ổn định, test được, và quan trọng nhất là
GIẢI THÍCH ĐƯỢC. Mỗi gợi ý kèm `reason` nói rõ vì sao được chọn; một mô hình sinh
văn bản không đưa ra được điều đó, mà đây lại chính là câu Manager sẽ hỏi.

Human-in-the-loop: AI chỉ xếp hạng — Manager quyết định giao cho ai và vẫn có thể
chọn người ngoài danh sách.
"""

from src.schemas.suggest import (
    DEFAULT_TOP_N,
    MAX_TOP_N,
    StaffCandidate,
    StaffSuggestion,
    SuggestStaffRequest,
    SuggestStaffResponse,
)
from src.services.text_utils import norm_code

# TicketCategoryEnum (khớp BE — TicketService.Domain.Enums.TicketCategoryEnum).
_CAT_CHARGING = 1
_CAT_OVERHEAT = 2
_CAT_NO_POWER = 3
_CAT_PERFORMANCE = 4
_CAT_OTHER = 5
_CAT_REPAIR = 6

# TicketPriorityEnum (khớp BE).
_P1_CRITICAL = 1
_P2_HIGH = 2
_P3_NORMAL = 3

# StaffSkillTierEnum (khớp BE): 1=Generalist, 2=ModuleSpecialist, 3=SeniorSpecialist.
_TIER_GENERALIST = 1
_TIER_MODULE = 2
_TIER_SENIOR = 3

# Tier tối thiểu theo priority — PHẢI khớp AssignmentRoleHelper.ValidatePrimaryHandlerTier
# của BE. Lệch một bậc là Manager bấm chọn người AI gợi ý rồi nhận 403.
_MIN_TIER_BY_PRIORITY = {
    _P1_CRITICAL: _TIER_SENIOR,
    _P2_HIGH: _TIER_MODULE,
    _P3_NORMAL: _TIER_GENERALIST,
}

# Kỹ năng theo loại lỗi: (ưu tiên, chấp nhận được).
_SKILLS_BY_CATEGORY: dict[int, tuple[set[str], set[str]]] = {
    _CAT_CHARGING:    ({"charging"}, {"battery", "general"}),
    _CAT_OVERHEAT:    ({"incident"}, {"battery", "general"}),
    _CAT_NO_POWER:    ({"battery"},  {"charging", "general"}),
    _CAT_PERFORMANCE: ({"battery"},  {"firmware", "general"}),
    _CAT_OTHER:       (set(),        {"general"}),
    _CAT_REPAIR:      ({"battery"},  {"general"}),
}

# Trọng số (thang 100, chia 100 khi trả về).
_W_SKILL_PRIMARY = 50
_W_SKILL_SECONDARY = 25
_W_SKILL_GENERAL_ONLY = 10
_W_TIER_EXACT = 15
_W_TIER_ONE_ABOVE = 8
_W_LOAD_MAX = 10

_CATEGORY_LABELS = {
    _CAT_CHARGING: "charging issue",
    _CAT_OVERHEAT: "overheat",
    _CAT_NO_POWER: "no power",
    _CAT_PERFORMANCE: "poor performance",
    _CAT_OTHER: "other",
    _CAT_REPAIR: "repair",
}

_TIER_LABELS = {
    _TIER_GENERALIST: "Tier 1",
    _TIER_MODULE: "Tier 2",
    _TIER_SENIOR: "Tier 3",
}

_PRIORITY_LABELS = {_P1_CRITICAL: "P1", _P2_HIGH: "P2", _P3_NORMAL: "P3"}


def _score_skill(candidate: StaffCandidate, category: int) -> tuple[int, str]:
    """Điểm khớp kỹ năng ↔ loại lỗi, kèm lý do."""
    primary, secondary = _SKILLS_BY_CATEGORY.get(category, (set(), {"general"}))

    # skill_codes là chuỗi TỰ DO (StaffSkill.SkillCode không có enum/validation), nên
    # Admin nhập tay có thể ra "Battery" / "battery ". Không chuẩn hoá là khớp trượt âm thầm.
    owned = {norm_code(c) for c in candidate.skill_codes if c and c.strip()}

    matched_primary = owned & primary
    if matched_primary:
        return _W_SKILL_PRIMARY, f"primary skill match '{sorted(matched_primary)[0]}'"

    matched_secondary = owned & (secondary - {"general"})
    if matched_secondary:
        return _W_SKILL_SECONDARY, f"related skill '{sorted(matched_secondary)[0]}'"

    if "general" in owned:
        return _W_SKILL_GENERAL_ONLY, "general skill only"

    return 0, "no skill match for this category"


def _score_tier(candidate: StaffCandidate, priority: int) -> tuple[int, str]:
    """
    Điểm theo tier. Vượt từ 2 bậc trở lên KHÔNG cộng thêm — để tránh dồn hết ticket P3
    cho Tier 3 rồi khi có P1 thật thì không còn ai rảnh.
    """
    min_tier = _MIN_TIER_BY_PRIORITY.get(priority)
    tier_label = _TIER_LABELS.get(candidate.skill_tier, f"Tier {candidate.skill_tier}")

    if min_tier is None:  # ticket chưa có priority → không xét tier
        return 0, ""

    gap = candidate.skill_tier - min_tier
    prio_label = _PRIORITY_LABELS.get(priority, f"P{priority}")
    if gap == 0:
        return _W_TIER_EXACT, f"{tier_label} matches {prio_label} requirement"
    if gap == 1:
        return _W_TIER_ONE_ABOVE, f"{tier_label} above {prio_label} requirement"
    return 0, f"{tier_label} far above {prio_label} requirement"


def _score_load(candidate: StaffCandidate) -> tuple[float, str]:
    """Điểm theo mức rảnh. max_concurrent = 0 ⇒ coi như không giới hạn."""
    if candidate.max_concurrent <= 0:
        return float(_W_LOAD_MAX), "no ticket limit set"

    free_ratio = 1.0 - (candidate.active_tickets / candidate.max_concurrent)
    free_ratio = max(0.0, min(1.0, free_ratio))
    return (
        free_ratio * _W_LOAD_MAX,
        f"handling {candidate.active_tickets}/{candidate.max_concurrent} tickets",
    )


def _tier_ok(candidate: StaffCandidate, priority: int) -> bool:
    min_tier = _MIN_TIER_BY_PRIORITY.get(priority)
    if min_tier is None:  # chưa có priority → không chặn ai
        return True
    return candidate.skill_tier >= min_tier


def _has_capacity(candidate: StaffCandidate) -> bool:
    if candidate.max_concurrent <= 0:
        return True
    return candidate.active_tickets < candidate.max_concurrent


def run_suggest_staff(req: SuggestStaffRequest) -> SuggestStaffResponse:
    """Xếp hạng ứng viên; trả top N kèm lý do."""
    if not req.candidates:
        return SuggestStaffResponse(
            suggestions=[], note="No staff available to take this ticket."
        )

    # 1. Lọc cứng — PHẢI khớp đúng điều kiện TicketAssignCommandHandler validate, nếu không
    #    Manager bấm chọn người AI gợi ý sẽ nhận 403 và tính năng thành phản tác dụng.
    eligible = [c for c in req.candidates if _tier_ok(c, req.priority) and _has_capacity(c)]

    if not eligible:
        blocked_by_tier = sum(1 for c in req.candidates if not _tier_ok(c, req.priority))
        blocked_by_load = sum(1 for c in req.candidates if not _has_capacity(c))
        prio_label = _PRIORITY_LABELS.get(req.priority, "")
        if blocked_by_tier and not blocked_by_load:
            note = f"No staff meets the required tier for this {prio_label} ticket."
        elif blocked_by_load and not blocked_by_tier:
            note = "All eligible staff are already at full capacity."
        else:
            note = (
                f"No eligible candidates: {blocked_by_tier} below required tier, "
                f"{blocked_by_load} at full capacity."
            )
        return SuggestStaffResponse(suggestions=[], note=note)

    # 2. Chấm điểm.
    scored: list[tuple[float, int, StaffSuggestion]] = []
    for c in eligible:
        skill_pts, skill_reason = _score_skill(c, req.category)
        tier_pts, tier_reason = _score_tier(c, req.priority)
        load_pts, load_reason = _score_load(c)

        total = skill_pts + tier_pts + load_pts
        reasons = [r for r in (skill_reason, tier_reason, load_reason) if r]

        scored.append((
            total,
            c.active_tickets,
            StaffSuggestion(
                staff_id=c.staff_id,
                full_name=c.full_name,
                score=round(total / 100.0, 3),
                reason="; ".join(reasons),
                tier_ok=True,
            ),
        ))

    # Điểm cao trước; hoà điểm thì ưu tiên người đang rảnh hơn.
    scored.sort(key=lambda x: (-x[0], x[1]))

    top_n = req.top_n if req.top_n > 0 else DEFAULT_TOP_N
    top_n = max(1, min(top_n, MAX_TOP_N))
    suggestions = [s for _, _, s in scored[:top_n]]

    # Cảnh báo khi KHÔNG AI có kỹ năng chuyên — xét trực tiếp điểm kỹ năng thay vì suy ra
    # từ tổng điểm (tổng còn cộng tier + tải nên không phản ánh đúng phần kỹ năng).
    cat_label = _CATEGORY_LABELS.get(req.category, "this category")
    note = ""
    best_skill_pts = max(_score_skill(c, req.category)[0] for c in eligible)
    if best_skill_pts <= _W_SKILL_GENERAL_ONLY:
        note = f"No one has a specialized skill for {cat_label} — consider assigning with a supporter."

    return SuggestStaffResponse(suggestions=suggestions, note=note)
