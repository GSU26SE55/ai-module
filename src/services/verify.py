"""run_verify — chấm điểm ticket thủ công thật/rác + dò trùng mô tả.

Thiết kế deterministic (heuristic + đối chiếu sensor + so token mô tả) — KHÔNG
bắt buộc LLM/network, để chạy ổn định trong môi trường capstone và test được.
LLM có thể bổ sung sau (optional) nhưng không phải dependency cứng.

Human-in-the-loop: kết quả chỉ là gợi ý cho Manager, không tự chặn ticket.
"""

import re
import unicodedata

from src.schemas.verify import (
    TicketSensorSnapshot,
    VerifyTicketRequest,
    VerifyTicketResponse,
)

# Ngưỡng verdict: score < ngưỡng → "suspicious".
LEGITIMATE_THRESHOLD = 0.5
# Ngưỡng so trùng: similarity ≥ ngưỡng → nghi trùng.
DUPLICATE_THRESHOLD = 0.45
# Mô tả quá ngắn → nghi rác.
MIN_DESCRIPTION_LEN = 15

# Từ khóa bất thường thật (mô tả có → hợp lệ hơn). Không dấu để match cả có/không dấu.
_ANOMALY_KEYWORDS = {
    "nong", "nhiet", "khoi", "chay", "phong", "phinh", "ro ri", "chay xe",
    "sut ap", "yeu", "chai", "sac", "khong len", "mat dien", "tut", "giam",
    "bao dong", "canh bao", "loi", "hong", "bat thuong", "khac thuong",
    "overheat", "voltage", "soh", "degrad", "swell", "leak", "smoke", "fire",
}


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def _norm(s: str) -> str:
    """Chuẩn hóa: lowercase + bỏ dấu + gọn khoảng trắng."""
    return re.sub(r"\s+", " ", _strip_accents(s.lower())).strip()


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", _norm(s)) if len(t) >= 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _sensor_supports_anomaly(snap: TicketSensorSnapshot) -> tuple[bool, str]:
    """Sensor có thực sự bất thường không → củng cố tính hợp lệ của ticket."""
    reasons = []
    if snap.has_active_alert:
        reasons.append("pin đang có cảnh báo active")
    if snap.soh_percent and snap.soh_percent < 80:
        reasons.append(f"SOH {snap.soh_percent:.0f}% dưới ngưỡng EOL 80%")
    if snap.temperature and snap.temperature > 45:
        reasons.append(f"nhiệt độ {snap.temperature:.0f}°C cao")
    if snap.soc_percent and snap.soc_percent < 15:
        reasons.append(f"SOC {snap.soc_percent:.0f}% rất thấp")
    return (len(reasons) > 0, ", ".join(reasons))


def _detect_duplicate(
    req: VerifyTicketRequest,
) -> tuple[str, float, str]:
    """So mô tả ticket mới với từng candidate → ticket trùng nhất (nếu vượt ngưỡng)."""
    new_tokens = _tokens(req.title + " " + req.description)
    best_id, best_score, best_reason = "", 0.0, ""
    for c in req.candidates:
        sim = _jaccard(new_tokens, _tokens(c.description))
        # Cùng category → cộng thêm (điều kiện (b) trong nghiệp vụ).
        same_cat = req.category != 0 and c.category == req.category
        adjusted = min(1.0, sim + (0.15 if same_cat else 0.0))
        if adjusted > best_score:
            best_score = adjusted
            best_id = c.ticket_id
            cat_note = " + cùng loại (category)" if same_cat else ""
            best_reason = (
                f"Mô tả tương đồng {sim * 100:.0f}% với ticket đang mở{cat_note}"
            )
    if best_score >= DUPLICATE_THRESHOLD:
        return best_id, round(best_score, 3), best_reason
    return "", round(best_score, 3), ""


def run_verify(req: VerifyTicketRequest) -> VerifyTicketResponse:
    """Chấm điểm hợp lệ [0..1] + verdict + dò trùng. Deterministic, không cần network."""
    desc_norm = _norm(req.description)
    title_norm = _norm(req.title)

    score = 0.5  # trung tính
    reasons: list[str] = []

    # 1. Độ dài mô tả — quá ngắn → nghi rác.
    if len(desc_norm) < MIN_DESCRIPTION_LEN:
        score -= 0.3
        reasons.append("mô tả quá ngắn/sơ sài")
    else:
        score += 0.15

    # 2. Tiêu đề rỗng / trùng mô tả y hệt → nghi.
    if not title_norm:
        score -= 0.1
        reasons.append("thiếu tiêu đề")

    # 3. Từ khóa bất thường → tăng độ hợp lệ.
    text = title_norm + " " + desc_norm
    if any(kw in text for kw in _ANOMALY_KEYWORDS):
        score += 0.2
        reasons.append("mô tả nêu triệu chứng bất thường cụ thể")

    # 4. Spam đơn giản: cùng 1 ký tự lặp nhiều / toàn số.
    if re.fullmatch(r"(.)\1{5,}", desc_norm.replace(" ", "")) or re.fullmatch(
        r"[0-9\s]+", desc_norm
    ):
        score -= 0.4
        reasons.append("mô tả có dấu hiệu spam")

    # 5. Đối chiếu sensor thật — bất thường thật → củng cố hợp lệ mạnh.
    if req.sensor_snapshot is not None:
        supported, sensor_reason = _sensor_supports_anomaly(req.sensor_snapshot)
        if supported:
            score += 0.3
            reasons.append(f"khớp dữ liệu sensor thật ({sensor_reason})")
        else:
            score -= 0.1
            reasons.append("sensor pin tại thời điểm này không thấy bất thường rõ")

    score = max(0.0, min(1.0, round(score, 3)))
    verdict = "legitimate" if score >= LEGITIMATE_THRESHOLD else "suspicious"

    prefix = "Hợp lệ" if verdict == "legitimate" else "Nghi ngờ"
    reason = f"{prefix}: " + ("; ".join(reasons) if reasons else "không có tín hiệu bất thường")

    dup_id, dup_score, dup_reason = _detect_duplicate(req)

    return VerifyTicketResponse(
        verdict=verdict,
        score=score,
        reason=reason,
        duplicate_of_ticket_id=dup_id,
        duplicate_score=dup_score,
        duplicate_reason=dup_reason,
    )
