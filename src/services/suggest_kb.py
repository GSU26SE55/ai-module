"""run_suggest_kb — xếp hạng bài viết Knowledge Base phù hợp để kỹ thuật viên
tham khảo khi sửa chữa một ticket.

Deterministic (cùng lý do như `suggest_staff.py`): giải thích được vì sao một bài
được đề xuất, và chạy ổn định không phụ thuộc mạng.

Human-in-the-loop: AI chỉ xếp hạng — kỹ thuật viên bấm áp dụng thì BE mới tạo
`TicketKbReference`. AI KHÔNG tự gắn tài liệu vào ticket.

KHÁC `KbSuggestionService` của BE (phục vụ chat): ở đây category KHÔNG lọc cứng mà chỉ
cộng điểm. Ticket auto từ `SohDegradation` mang category Performance; lọc cứng sẽ khiến
bài an toàn nhiệt/PPE không bao giờ nổi lên dù đó đúng là thứ cần khi xử lý pin nóng.
"""

from src.schemas.suggest import (
    DEFAULT_TOP_N,
    MAX_TOP_N,
    KbCandidate,
    KbSuggestion,
    SuggestKbRequest,
    SuggestKbResponse,
)
from src.services.text_utils import jaccard, norm_code, tokens

# Trọng số (thang 100 + bonus, chia 100 khi trả về).
_W_CATEGORY = 40
_W_TAGS_PER_HIT = 10
_W_TAGS_MAX = 30
_W_TITLE = 20
_W_HELPFUL = 10
# Bonus khi bài KB khớp tài liệu AI ĐÃ THỰC SỰ truy hồi qua RAG lúc kê đơn.
# Đặt CAO HƠN _W_CATEGORY có chủ ý: trùng category chỉ nói "cùng nhóm lỗi", còn khớp
# tài liệu AI tham chiếu nghĩa là chính bài này đã được dùng để phân tích ca này.
# Một bài đúng nội dung nhưng khác category phải thắng bài cùng category mà không liên quan.
_W_AI_REF_BONUS = 45

# Điểm tối đa lý thuyết — để chuẩn hoá score về [0..1].
_MAX_SCORE = _W_CATEGORY + _W_TAGS_MAX + _W_TITLE + _W_HELPFUL + _W_AI_REF_BONUS


def _ai_reference_tokens(req: SuggestKbRequest) -> set[str]:
    """
    Token rút từ tài liệu AI đã tham chiếu.

    `ai_kb_doc_refs` là ĐƯỜNG DẪN FILE trong knowledge base của ai-module
    (vd "maintenance/bms_warning_codes.md"), KHÔNG phải `KnowledgeBaseArticle.Code`
    của hệ thống — hai kho tài liệu tách rời nhau. Vì vậy chỉ có thể so khớp mềm
    theo token tên file với tiêu đề bài viết, không map thẳng được id.
    """
    raw = " ".join(list(req.ai_sop_references) + list(req.ai_kb_doc_refs))
    # Bỏ phần thư mục + đuôi file để còn lại từ khoá: "maintenance/bms_warning_codes.md"
    # → "bms warning codes".
    cleaned = raw.replace("/", " ").replace("_", " ").replace("-", " ").replace(".md", " ")
    return tokens(cleaned)


def _score_candidate(
    c: KbCandidate,
    req: SuggestKbRequest,
    query_tokens: set[str],
    ai_tokens: set[str],
    max_helpful: int,
) -> tuple[float, str]:
    score = 0.0
    reasons: list[str] = []

    if req.category and c.category == req.category:
        score += _W_CATEGORY
        reasons.append("đúng loại lỗi")

    # Tags — KbSuggestionService của BE bỏ qua trường này dù nó chính xác hơn quét toàn văn.
    tag_hits = [t for t in c.tags if t and norm_code(t) and tokens(t) & query_tokens]
    if tag_hits:
        pts = min(len(tag_hits) * _W_TAGS_PER_HIT, _W_TAGS_MAX)
        score += pts
        reasons.append(f"khớp thẻ {', '.join(sorted(tag_hits)[:3])}")

    title_sim = jaccard(tokens(c.title), query_tokens)
    if title_sim > 0:
        score += title_sim * _W_TITLE
        if title_sim >= 0.15:
            reasons.append("tiêu đề sát nội dung sự cố")

    if max_helpful > 0 and c.helpful_count > 0:
        score += (c.helpful_count / max_helpful) * _W_HELPFUL
        if c.helpful_count >= max_helpful:
            reasons.append(f"được đánh giá hữu ích nhiều nhất ({c.helpful_count})")

    if ai_tokens and tokens(c.title) & ai_tokens:
        score += _W_AI_REF_BONUS
        reasons.append("AI đã tham chiếu tài liệu này khi phân tích")

    return score, "; ".join(reasons) if reasons else "liên quan chung tới loại lỗi"


def run_suggest_kb(req: SuggestKbRequest) -> SuggestKbResponse:
    """Xếp hạng bài viết KB; trả top N kèm lý do."""
    if not req.candidates:
        return SuggestKbResponse(
            suggestions=[], note="Chưa có bài viết nào được xuất bản cho loại lỗi này."
        )

    # Nguồn từ khoá, ưu tiên dữ liệu AI đã sinh cho chính ticket này (chính xác hơn hẳn
    # mô tả thô). Ticket do Customer tạo không có phần này ⇒ chỉ còn description.
    query_text = " ".join(
        [req.description] + list(req.ai_action_steps) + list(req.ai_sop_references)
    )
    query_tokens = tokens(query_text)
    ai_tokens = _ai_reference_tokens(req)
    max_helpful = max((c.helpful_count for c in req.candidates), default=0)

    scored: list[tuple[float, KbSuggestion]] = []
    for c in req.candidates:
        pts, reason = _score_candidate(c, req, query_tokens, ai_tokens, max_helpful)
        scored.append((
            pts,
            KbSuggestion(
                kb_id=c.kb_id,
                code=c.code,
                title=c.title,
                score=round(min(pts / _MAX_SCORE, 1.0), 3),
                reason=reason,
            ),
        ))

    # Điểm cao trước; hoà thì giữ nguyên thứ tự BE gửi (đã sort theo helpful_count).
    scored.sort(key=lambda x: -x[0])

    top_n = req.top_n if req.top_n > 0 else DEFAULT_TOP_N
    top_n = max(1, min(top_n, MAX_TOP_N))
    suggestions = [s for _, s in scored[:top_n]]

    note = ""
    if not query_tokens:
        note = "Ticket không có mô tả để so khớp — danh sách xếp theo mức độ hữu ích."

    return SuggestKbResponse(suggestions=suggestions, note=note)
