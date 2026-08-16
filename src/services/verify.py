"""run_verify — chấm điểm ticket thủ công thật/rác + dò trùng mô tả.

Thiết kế deterministic (heuristic + đối chiếu sensor + so token mô tả) — KHÔNG
bắt buộc LLM/network, để chạy ổn định trong môi trường capstone và test được.
LLM có thể bổ sung sau (optional) nhưng không phải dependency cứng.

Human-in-the-loop: kết quả chỉ là gợi ý cho Manager, không tự chặn ticket.
"""

import re

from src.schemas.verify import (
    TicketSensorSnapshot,
    VerifyTicketRequest,
    VerifyTicketResponse,
)
from src.services.text_utils import jaccard, norm, strip_accents, tokens

# Ngưỡng verdict: score < ngưỡng → "suspicious".
LEGITIMATE_THRESHOLD = 0.5
# Ngưỡng so trùng: similarity ≥ ngưỡng → nghi trùng.
DUPLICATE_THRESHOLD = 0.45
# Mô tả quá ngắn → nghi rác.
MIN_DESCRIPTION_LEN = 15

# Fault wording that makes a report credible. Stored accent-free because `_norm` strips
# accents, so one entry matches both "nóng" and "nong".
#
# Vietnamese entries stay: the reporter is the Customer, and they write in their own words —
# dropping them would penalise every Vietnamese-language report. What is standardised is the
# text the AI *emits* (reasons shown to the Manager), not the text it *reads*.
_ANOMALY_KEYWORDS = {
    # Vietnamese — as typed by customers
    "nong", "nhiet", "khoi", "chay", "phong", "phinh", "ro ri", "chay xe",
    "sut ap", "yeu", "chai", "sac", "khong len", "mat dien", "tut", "giam",
    "bao dong", "canh bao", "loi", "hong", "bat thuong", "khac thuong",
    "lanh", "dong bang", "khong sac", "het pin", "chap", "no",
    # English
    "overheat", "voltage", "soh", "degrad", "swell", "leak", "smoke", "fire",
    "hot", "cold", "freez", "burn", "spark", "bulge", "drain", "dead",
    "not charging", "won't charge", "wont charge", "no power", "shut down",
    "shutdown", "fault", "error", "alarm", "abnormal", "damage",
}


# Chuyển sang src/services/text_utils.py để luồng gợi ý (staff/KB) dùng chung cùng một
# cách chuẩn hoá. Giữ alias để phần còn lại của file không đổi.
_strip_accents = strip_accents
_norm = norm
_tokens = tokens
_jaccard = jaccard


def _sensor_supports_anomaly(snap: TicketSensorSnapshot) -> tuple[bool, str]:
    """Does the sensor data actually show a fault? → strengthens the ticket's legitimacy.

    Every limit is read from the battery type's own `threshold_configs` — the same row
    `AnomalyRules` uses to raise alerts. Hardcoding them here (it used to be 45°C / SOC 15%)
    makes the AI disagree with the backend about what counts as a fault: an LFP 24V pack has
    a real limit of 60°C, so a 50°C reading the backend ignores was being scored as "matches
    real sensor data", confirming a fault that never existed. A threshold of 0 means the
    caller didn't supply it — skip that rule rather than guess.
    """
    reasons = []
    if snap.has_active_alert:
        reasons.append("battery had an active alert")
    if snap.soh_warning_threshold and snap.soh_percent and snap.soh_percent < snap.soh_warning_threshold:
        reasons.append(
            f"SOH {snap.soh_percent:.0f}% below the {snap.soh_warning_threshold:.0f}% threshold"
        )
    if snap.temperature_max and snap.temperature and snap.temperature > snap.temperature_max:
        reasons.append(
            f"temperature {snap.temperature:.0f}°C above the {snap.temperature_max:.0f}°C limit"
        )
    # Undertemp was missing entirely: a customer reporting a battery frozen at −18°C got
    # "no anomaly seen" and lost points for a perfectly accurate report.
    if snap.temperature_min and snap.temperature and snap.temperature < snap.temperature_min:
        reasons.append(
            f"temperature {snap.temperature:.0f}°C below the {snap.temperature_min:.0f}°C limit"
        )
    if snap.soc_warning_threshold and snap.soc_percent and snap.soc_percent < snap.soc_warning_threshold:
        reasons.append(
            f"SOC {snap.soc_percent:.0f}% below the {snap.soc_warning_threshold:.0f}% threshold"
        )
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
            cat_note = " + same category" if same_cat else ""
            best_reason = (
                f"{sim * 100:.0f}% description overlap with an open ticket{cat_note}"
            )
    if best_score >= DUPLICATE_THRESHOLD:
        return best_id, round(best_score, 3), best_reason
    return "", round(best_score, 3), ""


def run_verify(req: VerifyTicketRequest) -> VerifyTicketResponse:
    """Chấm điểm hợp lệ [0..1] + verdict + dò trùng. Deterministic, không cần network."""
    desc_norm = _norm(req.description)
    title_norm = _norm(req.title)

    score = 0.5  # neutral starting point
    reasons: list[str] = []

    # 1. Description length — too short reads as junk.
    if len(desc_norm) < MIN_DESCRIPTION_LEN:
        score -= 0.3
        reasons.append("description is too short")
    else:
        score += 0.15

    # 2. Missing title.
    if not title_norm:
        score -= 0.1
        reasons.append("no title")

    # 3. Concrete fault wording raises confidence.
    text = title_norm + " " + desc_norm
    if any(kw in text for kw in _ANOMALY_KEYWORDS):
        score += 0.2
        reasons.append("describes a specific fault symptom")

    # 4. Crude spam: one character repeated, or digits only.
    if re.fullmatch(r"(.)\1{5,}", desc_norm.replace(" ", "")) or re.fullmatch(
        r"[0-9\s]+", desc_norm
    ):
        score -= 0.4
        reasons.append("description looks like spam")

    # 5. Cross-check against real sensor data — the strongest signal either way.
    if req.sensor_snapshot is not None:
        supported, sensor_reason = _sensor_supports_anomaly(req.sensor_snapshot)
        if supported:
            score += 0.3
            reasons.append(f"matches sensor data ({sensor_reason})")
        else:
            score -= 0.1
            reasons.append("sensor data shows no clear anomaly at that time")

    score = max(0.0, min(1.0, round(score, 3)))
    verdict = "legitimate" if score >= LEGITIMATE_THRESHOLD else "suspicious"

    prefix = "Legitimate" if verdict == "legitimate" else "Suspicious"
    reason = f"{prefix}: " + ("; ".join(reasons) if reasons else "no notable signal")

    dup_id, dup_score, dup_reason = _detect_duplicate(req)

    return VerifyTicketResponse(
        verdict=verdict,
        score=score,
        reason=reason,
        duplicate_of_ticket_id=dup_id,
        duplicate_score=dup_score,
        duplicate_reason=dup_reason,
    )
