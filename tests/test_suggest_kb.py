"""Tests cho run_suggest_kb — xếp hạng bài viết KB tham khảo khi sửa chữa."""

from src.schemas.suggest import KbCandidate, SuggestKbRequest
from src.services.suggest_kb import run_suggest_kb

CAT_CHARGING, CAT_OVERHEAT, CAT_PERFORMANCE = 1, 2, 4


def _kb(kid, title, tags=None, category=0, helpful=0, code=""):
    return KbCandidate(
        kb_id=kid, code=code or f"KB-{kid}", title=title,
        tags=tags or [], category=category, helpful_count=helpful,
    )


def test_empty_candidates_returns_note():
    res = run_suggest_kb(SuggestKbRequest(category=CAT_CHARGING, description="pin nóng"))
    assert res.suggestions == []
    assert res.note


def test_same_category_scores_higher():
    req = SuggestKbRequest(
        category=CAT_CHARGING, description="lỗi sạc",
        candidates=[
            _kb("other", "Hướng dẫn chung", category=CAT_PERFORMANCE),
            _kb("match", "Hướng dẫn chung", category=CAT_CHARGING),
        ],
    )
    res = run_suggest_kb(req)
    assert res.suggestions[0].kb_id == "match"
    assert "đúng loại lỗi" in res.suggestions[0].reason


def test_other_category_still_included():
    """
    KHÁC KbSuggestionService của BE: category chỉ cộng điểm, KHÔNG lọc cứng.
    Ticket Performance vẫn phải thấy được bài an toàn nhiệt.
    """
    req = SuggestKbRequest(
        category=CAT_PERFORMANCE, description="pin quá nhiệt nguy hiểm",
        candidates=[_kb("safety", "Xử lý pin quá nhiệt", category=CAT_OVERHEAT)],
    )
    res = run_suggest_kb(req)
    assert [s.kb_id for s in res.suggestions] == ["safety"]


def test_tag_match_boosts_score():
    req = SuggestKbRequest(
        category=0, description="kiểm tra module BMS",
        candidates=[
            _kb("notag", "Tài liệu A"),
            _kb("tagged", "Tài liệu B", tags=["BMS"]),
        ],
    )
    res = run_suggest_kb(req)
    assert res.suggestions[0].kb_id == "tagged"
    assert "thẻ" in res.suggestions[0].reason


def test_title_similarity_matters():
    req = SuggestKbRequest(
        category=0, description="pin phồng rộp cần thay thế",
        candidates=[
            _kb("far", "Lịch bảo trì định kỳ hàng quý"),
            _kb("near", "Xử lý pin phồng rộp"),
        ],
    )
    res = run_suggest_kb(req)
    assert res.suggestions[0].kb_id == "near"


def test_vietnamese_accents_normalized():
    """Mô tả có dấu phải khớp tiêu đề có dấu qua chuẩn hoá."""
    req = SuggestKbRequest(
        category=0, description="QUÁ NHIỆT pin",
        candidates=[
            _kb("a", "Bảo trì định kỳ"),
            _kb("b", "Xử lý quá nhiệt"),
        ],
    )
    res = run_suggest_kb(req)
    assert res.suggestions[0].kb_id == "b"


def test_ai_sop_reference_bonus_dominates():
    """Tài liệu AI đã truy hồi qua RAG là tín hiệu mạnh nhất — thắng cả trùng category."""
    req = SuggestKbRequest(
        category=CAT_PERFORMANCE, description="pin suy giảm",
        ai_kb_doc_refs=["maintenance/bms_warning_codes.md"],
        candidates=[
            _kb("cat_match", "Tài liệu không liên quan", category=CAT_PERFORMANCE),
            _kb("ai_ref", "BMS warning codes", category=CAT_OVERHEAT),
        ],
    )
    res = run_suggest_kb(req)
    assert res.suggestions[0].kb_id == "ai_ref"
    assert "AI đã tham chiếu" in res.suggestions[0].reason


def test_ai_action_steps_used_as_keywords():
    req = SuggestKbRequest(
        category=0, description="",
        ai_action_steps=["Kiểm tra cân bằng cell", "Đo điện áp"],
        candidates=[
            _kb("unrelated", "Lịch vệ sinh tấm pin"),
            _kb("cell", "Cân bằng cell trong pack"),
        ],
    )
    res = run_suggest_kb(req)
    assert res.suggestions[0].kb_id == "cell"


def test_helpful_count_breaks_tie():
    req = SuggestKbRequest(
        category=CAT_CHARGING, description="lỗi sạc",
        candidates=[
            _kb("low", "Tài liệu", category=CAT_CHARGING, helpful=1),
            _kb("high", "Tài liệu", category=CAT_CHARGING, helpful=50),
        ],
    )
    res = run_suggest_kb(req)
    assert res.suggestions[0].kb_id == "high"


def test_no_description_returns_note():
    """Ticket không có mô tả — vẫn trả danh sách, kèm ghi chú giải thích cách xếp."""
    req = SuggestKbRequest(
        category=0, description="", candidates=[_kb("a", "", helpful=5)]
    )
    res = run_suggest_kb(req)
    assert res.suggestions
    assert res.note


def test_top_n_clamped():
    candidates = [_kb(f"k{i}", f"Tài liệu {i}") for i in range(20)]
    req = SuggestKbRequest(category=0, description="pin", candidates=candidates, top_n=99)
    assert len(run_suggest_kb(req).suggestions) == 10


def test_default_top_n():
    candidates = [_kb(f"k{i}", f"Tài liệu {i}") for i in range(20)]
    req = SuggestKbRequest(category=0, description="pin", candidates=candidates)
    assert len(run_suggest_kb(req).suggestions) == 5


def test_score_within_range_and_reason_present():
    req = SuggestKbRequest(
        category=CAT_CHARGING, description="lỗi sạc pin",
        ai_kb_doc_refs=["maintenance/sac_pin.md"],
        candidates=[_kb("a", "Sạc pin", tags=["sac"], category=CAT_CHARGING, helpful=9)],
    )
    s = run_suggest_kb(req).suggestions[0]
    assert 0.0 <= s.score <= 1.0
    assert s.reason
