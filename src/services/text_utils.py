"""Tiện ích chuẩn hoá & so khớp văn bản tiếng Việt — dùng chung cho các service
deterministic (verify ticket, gợi ý staff, gợi ý KB).

Tách ra từ `src/services/verify.py` khi luồng gợi ý cần đúng bộ hàm này: mô tả
ticket và nội dung KB đều là tiếng Việt có dấu, gõ tay, không nhất quán hoa/thường.
Copy-paste sang file thứ hai sẽ khiến hai luồng lệch nhau âm thầm khi một bên
được sửa.
"""

import re
import unicodedata


def strip_accents(s: str) -> str:
    """Bỏ dấu tiếng Việt: "quá nhiệt" → "qua nhiet"."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def norm(s: str) -> str:
    """Chuẩn hóa: lowercase + bỏ dấu + gọn khoảng trắng."""
    return re.sub(r"\s+", " ", strip_accents(s.lower())).strip()


def tokens(s: str) -> set[str]:
    """Tách token đã chuẩn hoá, bỏ token 1 ký tự (nhiễu)."""
    return {t for t in re.split(r"[^a-z0-9]+", norm(s)) if len(t) >= 2}


def jaccard(a: set[str], b: set[str]) -> float:
    """Độ tương đồng Jaccard ∈ [0, 1]. Trả 0.0 nếu một bên rỗng."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def norm_code(s: str) -> str:
    """
    Chuẩn hoá mã do người nhập (skill code, tag): lowercase + trim.

    KHÔNG bỏ dấu — mã kỹ thuật vốn là ASCII ("battery", "charging"); bỏ dấu ở đây
    chỉ che giấu dữ liệu bẩn chứ không sửa được. Dùng cho so khớp mã, còn so khớp
    văn xuôi thì dùng :func:`norm`.
    """
    return s.strip().lower()
