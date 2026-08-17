"""run_verify — chấm điểm ticket thủ công thật/rác + dò trùng mô tả.

Thiết kế deterministic (heuristic + đối chiếu sensor + so token mô tả) — KHÔNG
bắt buộc LLM/network, để chạy ổn định trong môi trường capstone và test được.
LLM có thể bổ sung sau (optional) nhưng không phải dependency cứng.

Human-in-the-loop: kết quả chỉ là gợi ý cho Manager, không tự chặn ticket.
"""

import re
from datetime import datetime

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


def _sensor_supports_anomaly(snap: TicketSensorSnapshot) -> tuple[bool, str, float]:
    """Does the sensor data actually show a fault? → strengthens the ticket's legitimacy.

    Returns `(supported, reason, severity)` where `severity` is how far past the limit the
    worst reading went, as a FRACTION of that limit (72°C against a 60°C cap → 0.20).

    Severity exists because a yes/no answer made every confirmed ticket score identically:
    61°C and 720°C both meant "matches sensor data", both added the same 0.3, and the Manager
    saw the same number for a marginal breach and a catastrophic one. The caller scales its
    bonus by this value instead.

    Every limit is read from the battery type's own `threshold_configs` — the same row
    `AnomalyRules` uses to raise alerts. Hardcoding them here (it used to be 45°C / SOC 15%)
    makes the AI disagree with the backend about what counts as a fault: an LFP 24V pack has
    a real limit of 60°C, so a 50°C reading the backend ignores was being scored as "matches
    real sensor data", confirming a fault that never existed. A threshold of 0 means the
    caller didn't supply it — skip that rule rather than guess.
    """
    reasons: list[str] = []
    # Mức vượt ngưỡng, đo bằng TỈ LỆ so với chính ngưỡng đó — không phải hiệu số tuyệt đối.
    # Dùng hiệu số thì 2°C vượt nhiệt và 2% tụt SOC thành cùng một mức, dù ý nghĩa khác hẳn.
    exceedances: list[float] = []

    if snap.has_active_alert:
        reasons.append("battery had an active alert")
        # 0.15, KHÔNG phải 0.5. Alert đang mở chỉ chứng minh CÓ bất thường, không nói mức độ —
        # gán bằng trần (0.5) sẽ cho nó điểm ngang một ca vượt ngưỡng 80%, và mọi ticket có
        # alert kèm mô tả tử tế đều đạt 1.00 bất kể số đo thật ra sao. Mức thấp này để các luật
        # bên dưới, vốn đo được cụ thể, chi phối thang điểm khi chúng cùng kích hoạt.
        exceedances.append(0.15)

    if snap.soh_warning_threshold and snap.soh_percent and snap.soh_percent < snap.soh_warning_threshold:
        reasons.append(
            f"SOH {snap.soh_percent:.0f}% below the {snap.soh_warning_threshold:.0f}% threshold"
        )
        exceedances.append(
            (snap.soh_warning_threshold - snap.soh_percent) / snap.soh_warning_threshold
        )

    if snap.temperature_max and snap.temperature and snap.temperature > snap.temperature_max:
        reasons.append(
            f"temperature {snap.temperature:.0f}°C above the {snap.temperature_max:.0f}°C limit"
        )
        exceedances.append(
            (snap.temperature - snap.temperature_max) / abs(snap.temperature_max)
        )

    # Undertemp was missing entirely: a customer reporting a battery frozen at −18°C got
    # "no anomaly seen" and lost points for a perfectly accurate report.
    if snap.temperature_min and snap.temperature and snap.temperature < snap.temperature_min:
        reasons.append(
            f"temperature {snap.temperature:.0f}°C below the {snap.temperature_min:.0f}°C limit"
        )
        # `temperature_min` âm với hầu hết pin (−10°C), nên chia cho trị tuyệt đối; thiếu abs()
        # là dấu bị đảo và mức vượt hoá âm.
        exceedances.append(
            (snap.temperature_min - snap.temperature) / abs(snap.temperature_min)
        )

    if snap.soc_warning_threshold and snap.soc_percent and snap.soc_percent < snap.soc_warning_threshold:
        reasons.append(
            f"SOC {snap.soc_percent:.0f}% below the {snap.soc_warning_threshold:.0f}% threshold"
        )
        exceedances.append(
            (snap.soc_warning_threshold - snap.soc_percent) / snap.soc_warning_threshold
        )

    # Lấy mức vượt LỚN NHẤT, không phải tổng: một viên pin vượt ba ngưỡng nhẹ không nghiêm
    # trọng bằng một viên vượt một ngưỡng gấp đôi, và cộng dồn sẽ nói ngược lại.
    severity = max(exceedances) if exceedances else 0.0
    return (len(reasons) > 0, ", ".join(reasons), severity)


def _hours_apart(a: str, b: str) -> float | None:
    """Khoảng cách giờ giữa hai mốc ISO. None nếu thiếu hoặc không đọc được."""
    if not a or not b:
        return None
    try:
        ta = datetime.fromisoformat(a.replace("Z", "+00:00"))
        tb = datetime.fromisoformat(b.replace("Z", "+00:00"))
    except ValueError:
        return None
    return abs((ta - tb).total_seconds()) / 3600.0


def _detect_duplicate(
    req: VerifyTicketRequest,
) -> tuple[str, float, str]:
    """Ticket trùng nhất trong danh sách candidate, hoặc "" nếu không đủ ngưỡng.

    Hai cách chấm, chọn theo NGUỒN của cặp ticket — vì so văn bản hỏng theo hai kiểu ngược nhau:

      máy↔máy — mô tả sinh từ CÙNG một template, khác mỗi con số. Jaccard đo được 0.73 giữa
        Overheat 67°C và Undertemp −18°C, hai lỗi ngược hẳn nhau. Nên nhánh này đòi CÙNG
        category, và category là điều kiện cứng chứ không phải điểm cộng.

      có người viết — cùng sự cố nhưng khác hẳn cách diễn đạt. Đo trên chính dữ liệu demo:
        khách hàng viết "The battery at the station is unusually hot, it feels very hot to the
        touch" còn máy viết "Battery overheating — the sensor recorded a battery temperature
        of…" ⇒ Jaccard 0.06, dưới ngưỡng 0.45 rất xa. Ticket khách khai về đúng sự cố máy vừa
        bắt lại không được gắn nghi trùng, và Manager không bao giờ biết chúng là một.

        Với cặp này, thứ đáng tin không phải là từ ngữ mà là BỐI CẢNH: cùng viên pin (đã lọc
        sẵn ở tầng gọi), cùng category, và xảy ra gần nhau về thời gian. Ba tín hiệu đó cộng lại
        đã đủ để nghi ngờ; văn bản chỉ còn là điểm cộng.
    """
    new_tokens = _tokens(req.title + " " + req.description)
    best_id, best_score, best_reason = "", 0.0, ""

    for c in req.candidates:
        sim = _jaccard(new_tokens, _tokens(c.description))
        same_cat = req.category != 0 and c.category == req.category
        machine_pair = req.is_machine_written and c.is_machine_written
        hours = _hours_apart(req.detected_at, c.detected_at)

        if machine_pair:
            # Khác category thì bỏ hẳn: template giống nhau khiến Jaccard cao giả tạo.
            if not same_cat:
                continue
            score = min(1.0, sim + 0.15)
            reason = f"{sim * 100:.0f}% description overlap with an open ticket + same category"
        else:
            # Chấm theo cấu trúc. Trọng số phản ánh độ tin của từng tín hiệu, không phải chia đều:
            #   0.45 cùng category — mạnh nhất, vì cả người lẫn máy đều phải chọn đúng loại lỗi.
            #        Một mình nó đã đủ vượt DUPLICATE_THRESHOLD (0.45), và điều đó là CỐ Ý:
            #        candidate vốn đã được lọc còn ticket đang MỞ trên CÙNG viên pin, nên cùng
            #        loại lỗi nữa thì gần như chắc chắn là cùng một sự cố. Khách hàng phát hiện
            #        muộn rồi mới báo là chuyện thường — pin nóng lúc 3h sáng, người ta gọi lúc
            #        1h chiều. Đừng thêm điều kiện thời gian bắt buộc ở đây: nghi sai thì Manager
            #        bỏ qua trong một giây, còn bỏ sót thì hai ticket song song cho một sự cố và
            #        không ai biết chúng liên quan.
            #   0.30 gần nhau về thời gian — CỘNG THÊM khi hai mốc sát nhau, không phải điều kiện
            #        cần. Suy giảm tuyến tính tới 6 giờ rồi thôi tác dụng.
            #   0.25 × Jaccard — vẫn giữ, nhưng chỉ để phân giải khi có nhiều candidate ngang
            #        điểm, chứ không đủ sức tự đẩy qua ngưỡng.
            # Cùng category + cách nhau dưới ~1 giờ ⇒ ≈0.70, vượt DUPLICATE_THRESHOLD kể cả khi
            # hai mô tả không chung một từ nào.
            score = 0.0
            bits: list[str] = []
            if same_cat:
                score += 0.45
                bits.append("same category")
            if hours is not None and hours <= 6.0:
                score += 0.30 * (1.0 - hours / 6.0)
                bits.append(
                    "reported at the same time"
                    if hours < 1.0
                    else f"reported {hours:.0f}h apart"
                )
            score += 0.25 * sim
            if sim > 0.1:
                bits.append(f"{sim * 100:.0f}% description overlap")
            score = min(1.0, score)
            reason = (
                "same battery, " + ", ".join(bits)
                if bits
                else "same battery, no other matching signal"
            )

        if score > best_score:
            best_score, best_id, best_reason = score, c.ticket_id, reason

    if best_score >= DUPLICATE_THRESHOLD:
        return best_id, round(best_score, 3), best_reason
    return "", round(best_score, 3), ""


def run_verify(req: VerifyTicketRequest) -> VerifyTicketResponse:
    """Chấm điểm hợp lệ [0..1] + verdict + dò trùng. Deterministic, không cần network."""
    desc_norm = _norm(req.description)
    title_norm = _norm(req.title)

    # Mốc trung tính 0.45, không phải 0.5. Chênh lệch nhỏ nhưng có lý do: tổng thưởng tối đa là
    # 0.20 (văn bản) + 0.45 (cảm biến vượt ≥50%) = 0.65, nên khởi điểm 0.5 sẽ chạm trần 1.0 từ
    # mức vượt ~20% và mọi ca nặng hơn thế lại hiện ra cùng một con số — đúng cái phải tránh.
    score = 0.45
    reasons: list[str] = []

    # Các bước 1–4 chỉ đọc VĂN BẢN, và phần thưởng của chúng cố ý giữ nhỏ: tổng tối đa +0.20,
    # đủ để tách một báo cáo viết đàng hoàng khỏi rác, không đủ để đẩy điểm lên vùng cao.
    #
    # Trước đây +0.15 (độ dài) và +0.20 (từ khoá) cộng vào mốc 0.5 cho đúng 0.85 trên MỌI ticket
    # viết chỉn chu, rồi bước 5 cộng thêm 0.3 là chạm trần 1.0 — nên 61°C (vượt 1.7%) và 90°C
    # (vượt 50%) hiện ra cùng một con số. Cách viết quyết định điểm, còn số đo thật thì không.
    # Giờ vùng điểm cao dành cho bằng chứng cảm biến ở bước 5.

    # 1. Description length — too short reads as junk.
    if len(desc_norm) < MIN_DESCRIPTION_LEN:
        score -= 0.3
        reasons.append("description is too short")
    else:
        score += 0.08

    # 2. Missing title.
    if not title_norm:
        score -= 0.1
        reasons.append("no title")

    # 3. Concrete fault wording raises confidence.
    text = title_norm + " " + desc_norm
    if any(kw in text for kw in _ANOMALY_KEYWORDS):
        score += 0.12
        reasons.append("describes a specific fault symptom")

    # 4. Crude spam: one character repeated, or digits only.
    if re.fullmatch(r"(.)\1{5,}", desc_norm.replace(" ", "")) or re.fullmatch(
        r"[0-9\s]+", desc_norm
    ):
        score -= 0.4
        reasons.append("description looks like spam")

    # 5. Cross-check against real sensor data — the strongest signal either way.
    #
    # Ba nhánh, không phải hai. Bản cũ im lặng khi KHÔNG CÓ số đo, nên một ticket chưa hề được
    # đối chiếu với thực tế lại chấm bằng đúng ticket đã đối chiếu và không thấy gì bất thường —
    # và câu lý do không hé lộ điều đó. Manager đọc "Legitimate: describes a specific fault
    # symptom" dễ hiểu nhầm là hệ thống đã kiểm tra cảm biến rồi.
    if req.sensor_snapshot is None:
        # Phạt NHẸ HƠN nhánh "đã đo và thấy bình thường" (−0.20 bên dưới), và thứ tự đó là có
        # chủ đích: không có dữ liệu nghĩa là chưa biết, còn đo được mà mọi chỉ số trong ngưỡng
        # là bằng chứng NGƯỢC lại lời khai. Đảo thứ tự sẽ phạt sự thiếu vắng dữ liệu — thứ khách
        # hàng không kiểm soát — nặng hơn mâu thuẫn thật sự.
        score -= 0.10
        reasons.append(
            "no sensor readings around the reported time — assessed from the text only"
        )
    else:
        supported, sensor_reason, severity = _sensor_supports_anomaly(req.sensor_snapshot)
        if supported:
            # Thưởng theo mức vượt ngưỡng: 0.18 sàn (vừa chạm ngưỡng) → 0.43 trần (vượt ≥50%).
            #
            # Sàn 0.18 đủ để một vi phạm sát ngưỡng vượt hẳn LEGITIMATE_THRESHOLD, phần còn lại
            # trải theo mức vượt. Trần 50% có chủ đích: vượt 500% không "thật" hơn vượt 50%, chỉ
            # nguy hiểm hơn — mức nguy hiểm là việc của severity/priority, không phải của điểm
            # hợp lệ. Tổng cao nhất 0.45 + 0.20 + 0.43 = 1.08, cắt về 1.0, nên chỉ những ca vượt
            # gần trần mới hoà nhau ở 1.0 — đúng chỗ mà việc phân biệt hết ý nghĩa.
            bonus = 0.18 + min(severity, 0.5) * 0.50
            score += bonus
            reasons.append(
                f"matches sensor data ({sensor_reason}, {severity * 100:.0f}% past the limit)"
            )
        else:
            # Đo được mà mọi chỉ số trong ngưỡng là bằng chứng NGƯỢC lại lời khai — nặng hơn
            # việc không có dữ liệu, vì đây là mâu thuẫn thật chứ không phải chỗ trống.
            score -= 0.20
            reasons.append(
                "sensor readings around that time stayed within every threshold"
            )

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
