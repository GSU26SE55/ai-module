"""Tests cho run_suggest_staff — xếp hạng nhân viên xử lý ticket."""

from src.schemas.suggest import StaffCandidate, SuggestStaffRequest
from src.services.suggest_staff import run_suggest_staff

# TicketCategoryEnum / TicketPriorityEnum / StaffSkillTierEnum — khớp BE.
CAT_CHARGING, CAT_OVERHEAT, CAT_PERFORMANCE = 1, 2, 4
P1, P2, P3 = 1, 2, 3
TIER1, TIER2, TIER3 = 1, 2, 3


def _staff(sid, tier, skills, active=0, mx=10, name="NV"):
    return StaffCandidate(
        staff_id=sid, full_name=name, skill_tier=tier,
        skill_codes=skills, active_tickets=active, max_concurrent=mx,
    )


def test_empty_candidates_returns_note():
    res = run_suggest_staff(SuggestStaffRequest(category=CAT_CHARGING, priority=P3))
    assert res.suggestions == []
    assert res.note


def test_skill_match_ranks_first():
    """Người có kỹ năng chính phải xếp trên người chỉ có kỹ năng tổng quát."""
    req = SuggestStaffRequest(
        category=CAT_CHARGING, priority=P3,
        candidates=[
            _staff("generalist", TIER1, ["general"]),
            _staff("charger", TIER1, ["charging"]),
        ],
    )
    res = run_suggest_staff(req)
    assert res.suggestions[0].staff_id == "charger"
    assert "charging" in res.suggestions[0].reason


def test_tier_filter_excludes_underqualified():
    """P1 yêu cầu Tier 3 — Tier 1/2 phải bị loại hoàn toàn khỏi danh sách."""
    req = SuggestStaffRequest(
        category=CAT_OVERHEAT, priority=P1,
        candidates=[
            _staff("t1", TIER1, ["incident"]),
            _staff("t2", TIER2, ["incident"]),
            _staff("t3", TIER3, ["incident"]),
        ],
    )
    res = run_suggest_staff(req)
    assert [s.staff_id for s in res.suggestions] == ["t3"]


def test_all_underqualified_returns_explanatory_note():
    req = SuggestStaffRequest(
        category=CAT_OVERHEAT, priority=P1,
        candidates=[_staff("t1", TIER1, ["incident"])],
    )
    res = run_suggest_staff(req)
    assert res.suggestions == []
    assert "tier" in res.note.lower()


def test_full_capacity_excluded():
    """Người đã đầy tải phải bị loại — nếu không Manager bấm chọn sẽ nhận 403 từ BE."""
    req = SuggestStaffRequest(
        category=CAT_CHARGING, priority=P3,
        candidates=[
            _staff("full", TIER2, ["charging"], active=10, mx=10),
            _staff("free", TIER1, ["general"], active=0, mx=10),
        ],
    )
    res = run_suggest_staff(req)
    assert [s.staff_id for s in res.suggestions] == ["free"]


def test_all_full_returns_load_note():
    req = SuggestStaffRequest(
        category=CAT_CHARGING, priority=P3,
        candidates=[_staff("full", TIER2, ["charging"], active=8, mx=8)],
    )
    res = run_suggest_staff(req)
    assert res.suggestions == []
    assert "đầy tải" in res.note


def test_no_priority_skips_tier_filter():
    """Ticket chưa có priority (Customer tạo) — không được loại ai vì tier."""
    req = SuggestStaffRequest(
        category=CAT_CHARGING, priority=0,
        candidates=[_staff("t1", TIER1, ["charging"])],
    )
    res = run_suggest_staff(req)
    assert len(res.suggestions) == 1


def test_skill_codes_normalized():
    """SkillCode là chuỗi tự do — 'Charging ' phải khớp như 'charging'."""
    req = SuggestStaffRequest(
        category=CAT_CHARGING, priority=P3,
        candidates=[
            _staff("messy", TIER1, ["  Charging "]),
            _staff("plain", TIER1, ["general"]),
        ],
    )
    res = run_suggest_staff(req)
    assert res.suggestions[0].staff_id == "messy"


def test_lighter_load_wins_on_tie():
    """Cùng kỹ năng + tier → người rảnh hơn xếp trước."""
    req = SuggestStaffRequest(
        category=CAT_CHARGING, priority=P3,
        candidates=[
            _staff("busy", TIER1, ["charging"], active=8, mx=10),
            _staff("idle", TIER1, ["charging"], active=1, mx=10),
        ],
    )
    res = run_suggest_staff(req)
    assert res.suggestions[0].staff_id == "idle"


def test_tier_far_above_not_rewarded():
    """
    Tier 3 làm ticket P3 KHÔNG được cộng điểm tier — tránh dồn việc nhẹ cho senior
    rồi khi có P1 thật thì không còn ai rảnh.
    """
    req = SuggestStaffRequest(
        category=CAT_CHARGING, priority=P3,
        candidates=[
            _staff("senior", TIER3, ["charging"]),
            _staff("junior", TIER1, ["charging"]),
        ],
    )
    res = run_suggest_staff(req)
    assert res.suggestions[0].staff_id == "junior"


def test_top_n_clamped():
    candidates = [_staff(f"s{i}", TIER1, ["general"]) for i in range(20)]
    req = SuggestStaffRequest(
        category=CAT_PERFORMANCE, priority=P3, candidates=candidates, top_n=99
    )
    assert len(run_suggest_staff(req).suggestions) == 10  # MAX_TOP_N


def test_default_top_n():
    candidates = [_staff(f"s{i}", TIER1, ["general"]) for i in range(20)]
    req = SuggestStaffRequest(category=CAT_PERFORMANCE, priority=P3, candidates=candidates)
    assert len(run_suggest_staff(req).suggestions) == 5  # DEFAULT_TOP_N


def test_unlimited_capacity_when_max_zero():
    req = SuggestStaffRequest(
        category=CAT_CHARGING, priority=P3,
        candidates=[_staff("nolimit", TIER1, ["charging"], active=99, mx=0)],
    )
    assert len(run_suggest_staff(req).suggestions) == 1


def test_score_within_range_and_reason_present():
    req = SuggestStaffRequest(
        category=CAT_CHARGING, priority=P3,
        candidates=[_staff("s1", TIER1, ["charging"], active=2, mx=10)],
    )
    s = run_suggest_staff(req).suggestions[0]
    assert 0.0 <= s.score <= 1.0
    assert s.reason


def test_note_when_nobody_has_specialised_skill():
    req = SuggestStaffRequest(
        category=CAT_OVERHEAT, priority=P3,
        candidates=[_staff("g", TIER1, ["general"], active=9, mx=10)],
    )
    res = run_suggest_staff(req)
    assert res.suggestions
    assert "kỹ năng chuyên" in res.note
