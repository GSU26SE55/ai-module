"""Tests cho run_verify — chấm điểm ticket thật/rác + dò trùng mô tả."""

from src.schemas.verify import (
    DuplicateCandidate,
    TicketSensorSnapshot,
    VerifyTicketRequest,
)
from src.services.verify import run_verify


def test_legitimate_detailed_description():
    """Mô tả rõ ràng + triệu chứng bất thường → hợp lệ."""
    req = VerifyTicketRequest(
        title="Pin nóng bất thường",
        description="Cục pin bị nóng lên rất nhanh và có mùi khét, cần kiểm tra gấp.",
        category=1,
    )
    res = run_verify(req)
    assert res.verdict == "legitimate"
    assert res.score >= 0.5


def test_suspicious_too_short():
    """Mô tả quá ngắn → nghi rác."""
    req = VerifyTicketRequest(title="test", description="abc", category=1)
    res = run_verify(req)
    assert res.verdict == "suspicious"
    assert res.score < 0.5


def test_suspicious_spam():
    """Mô tả spam (ký tự lặp) → nghi rác."""
    req = VerifyTicketRequest(title="x", description="aaaaaaaaaa", category=1)
    res = run_verify(req)
    assert res.verdict == "suspicious"


def test_sensor_snapshot_boosts_legitimacy():
    """Sensor thật bất thường (SOH thấp + alert) → củng cố hợp lệ."""
    req = VerifyTicketRequest(
        title="Pin yếu",
        description="Pin sạc không vào và tụt nhanh.",
        category=1,
        sensor_snapshot=TicketSensorSnapshot(
            soh_percent=55.0, has_active_alert=True, temperature=30.0
        ),
    )
    res = run_verify(req)
    assert res.verdict == "legitimate"
    assert "sensor" in res.reason.lower()


def test_sensor_snapshot_normal_lowers_score():
    """Sensor bình thường trong khi mô tả kêu hỏng → hạ điểm."""
    with_normal = run_verify(
        VerifyTicketRequest(
            title="Pin hỏng",
            description="Tôi nghĩ pin có vấn đề gì đó, không chắc lắm.",
            category=1,
            sensor_snapshot=TicketSensorSnapshot(
                soh_percent=98.0, temperature=25.0, soc_percent=80.0
            ),
        )
    )
    without = run_verify(
        VerifyTicketRequest(
            title="Pin hỏng",
            description="Tôi nghĩ pin có vấn đề gì đó, không chắc lắm.",
            category=1,
        )
    )
    assert with_normal.score <= without.score


def test_duplicate_detected():
    """Mô tả gần giống ticket đang mở cùng category → nghi trùng."""
    req = VerifyTicketRequest(
        title="Pin nóng",
        description="Cục pin bị nóng lên nhanh và có mùi khét cần kiểm tra",
        category=2,
        candidates=[
            DuplicateCandidate(
                ticket_id="TCK-001",
                description="Pin nóng lên nhanh và có mùi khét, kiểm tra gấp",
                category=2,
            ),
            DuplicateCandidate(
                ticket_id="TCK-002",
                description="Pin sụt áp nhẹ vào buổi tối",
                category=3,
            ),
        ],
    )
    res = run_verify(req)
    assert res.duplicate_of_ticket_id == "TCK-001"
    assert res.duplicate_score >= 0.45


def test_no_duplicate_when_different():
    """Mô tả khác hẳn → không nghi trùng."""
    req = VerifyTicketRequest(
        title="Pin nóng",
        description="Cục pin nóng và có mùi khét",
        category=2,
        candidates=[
            DuplicateCandidate(
                ticket_id="TCK-009",
                description="Đèn báo nhấp nháy màu xanh liên tục",
                category=5,
            ),
        ],
    )
    res = run_verify(req)
    assert res.duplicate_of_ticket_id == ""


def test_score_bounded():
    """Score luôn trong [0,1]."""
    res = run_verify(
        VerifyTicketRequest(
            title="Pin nóng cháy phồng rò rỉ khói",
            description="Pin nóng cháy phồng rò rỉ khói bất thường nguy hiểm cần xử lý",
            category=1,
            sensor_snapshot=TicketSensorSnapshot(
                soh_percent=40.0,
                temperature=60.0,
                soc_percent=5.0,
                has_active_alert=True,
            ),
        )
    )
    assert 0.0 <= res.score <= 1.0
