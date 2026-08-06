"""GH-65/GH-66: PackConfig + input range validation / OOD guard on PredictRequest.

Ranges (src/core/config.py): voltage per-cell [2.0, 4.5] V (checked AFTER dividing
by pack_config.n_series), current [-5, 5] A, temperature [-10, 60] °C,
soc_percent [0, 100]. NaN/Inf rejected in every column. Hard reject only.
"""

import math
import os

import pytest
from pydantic import ValidationError

from src.schemas.predict import PackConfig, PredictRequest
from src.schemas.prescribe import PrescribeRequest

GOOD_ROW = [3.7, -1.0, 25.0, 10.0, 68.0, 99.5]


def _window(row=GOOD_ROW, n=30):
    return [list(row) for _ in range(n)]


def test_valid_6col_passes():
    req = PredictRequest(battery_id="B0048", readings=_window())
    assert len(req.readings) == 30
    assert req.pack_config is None


def test_valid_legacy_3col_and_4col_pass():
    PredictRequest(battery_id="B", readings=_window([3.7, -1.0, 25.0]))
    PredictRequest(battery_id="B", readings=_window([3.7, -1.0, 25.0, 10.0]))


def test_boundary_values_pass_inclusive():
    low = [2.0, -5.0, -10.0, 0.0, 0.0, 0.0]
    high = [4.5, 5.0, 60.0, 1.0, 0.0, 100.0]
    PredictRequest(battery_id="B", readings=[low] * 15 + [high] * 15)


@pytest.mark.parametrize(
    ("col", "bad_value", "field_name"),
    [
        (0, 1.99, "voltage"),
        (0, 4.51, "voltage"),
        (1, -5.1, "current"),
        (1, 5.1, "current"),
        (2, -10.5, "temperature"),
        (2, 60.5, "temperature"),
        (5, -0.1, "soc_percent"),
        (5, 100.1, "soc_percent"),
    ],
)
def test_out_of_range_field_rejected_with_field_name(col, bad_value, field_name):
    rows = _window()
    rows[7][col] = bad_value
    with pytest.raises(ValidationError, match=field_name):
        PredictRequest(battery_id="B", readings=rows)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("col", range(6))
def test_nan_inf_rejected_in_every_column(bad, col):
    rows = _window()
    rows[0][col] = bad
    with pytest.raises(ValidationError, match="NaN/Inf"):
        PredictRequest(battery_id="B", readings=rows)


def test_12v_without_pack_config_rejected_with_hint():
    with pytest.raises(ValidationError, match="pack_config"):
        PredictRequest(battery_id="B", readings=_window([12.4, -1.0, 25.0, 1.0]))


def test_12v_with_n_series_3_passes():
    req = PredictRequest(
        battery_id="B",
        readings=_window([12.4, -1.0, 25.0, 1.0]),
        pack_config={"n_series": 3, "chemistry": "NMC"},
    )
    assert req.pack_config.n_series == 3
    # per-cell 12.4/3 ≈ 4.133 V — inside [2.0, 4.5]
    assert math.isclose(req.readings[0][0] / req.pack_config.n_series, 12.4 / 3)


def test_pack_voltage_still_out_of_range_after_division_rejected():
    # 12.4V with n_series=8 → 1.55V per-cell < 2.0 — message shows the division
    with pytest.raises(ValidationError, match="n_series"):
        PredictRequest(
            battery_id="B",
            readings=_window([12.4, -1.0, 25.0, 1.0]),
            pack_config={"n_series": 8},
        )


@pytest.mark.parametrize("n_series", [0, -1])
def test_n_series_must_be_at_least_1(n_series):
    with pytest.raises(ValidationError):
        PredictRequest(
            battery_id="B", readings=_window(), pack_config={"n_series": n_series}
        )


def test_pack_config_defaults_n_series_1():
    assert PackConfig().n_series == 1
    assert PackConfig(chemistry="LiFePO4").n_series == 1


def test_reading_objects_also_range_validated():
    # GH-76 named-field format goes through the same range guard
    obj = {"voltage": 12.4, "current": -1.0, "temperature": 25.0, "time": 1.0}
    with pytest.raises(ValidationError, match="pack_config"):
        PredictRequest(battery_id="B", readings=[dict(obj) for _ in range(30)])
    PredictRequest(
        battery_id="B",
        readings=[dict(obj) for _ in range(30)],
        pack_config={"n_series": 3},
    )


def test_prescribe_request_inherits_guard():
    with pytest.raises(ValidationError, match="pack_config"):
        PrescribeRequest(battery_id="B", readings=_window([12.4, -1.0, 25.0, 1.0]))
    PrescribeRequest(
        battery_id="B",
        readings=_window([12.4, -1.0, 25.0, 1.0]),
        pack_config={"n_series": 3},
    )


# ── GH-67: chemistry normalization + capacity_ah C-rate current guard ────────


def test_128v_4s_lfp_passes_and_chemistry_normalized():
    req = PredictRequest(
        battery_id="B",
        readings=_window([12.8, -1.0, 25.0, 1.0]),
        pack_config={"n_series": 4, "chemistry": "lifepo4"},
    )
    # per-cell 12.8/4 = 3.2 V — inside [2.0, 4.5]; spelling canonicalized
    assert req.pack_config.chemistry == "LFP"


def test_chemistry_aliases_and_passthrough():
    assert PackConfig(chemistry="lfp").chemistry == "LFP"
    assert PackConfig(chemistry="LiFePO4").chemistry == "LFP"
    assert PackConfig(chemistry="nmc").chemistry == "NMC"
    # unknown strings pass through untouched (NMC thresholds apply downstream)
    assert PackConfig(chemistry="lead-acid").chemistry == "lead-acid"
    assert PackConfig().chemistry is None


@pytest.mark.parametrize("capacity", [0, -2.0])
def test_capacity_ah_must_be_positive(capacity):
    with pytest.raises(ValidationError):
        PackConfig(capacity_ah=capacity)


def test_high_current_without_capacity_rejected_with_hint():
    with pytest.raises(ValidationError, match="capacity_ah"):
        PredictRequest(
            battery_id="B",
            readings=_window([12.8, -10.0, 25.0, 1.0]),
            pack_config={"n_series": 4},
        )


def test_high_current_with_capacity_passes_c_rate_guard():
    # 10 A discharge on a 50 Ah pack = 0.2C → NASA-2Ah equivalent 0.4 A ∈ [-5, 5]
    req = PredictRequest(
        battery_id="B",
        readings=_window([12.8, -10.0, 25.0, 1.0]),
        pack_config={"n_series": 4, "chemistry": "LFP", "capacity_ah": 50.0},
    )
    assert req.pack_config.capacity_ah == 50.0


def test_current_still_out_of_range_after_c_rate_rejected():
    # 200 A on 50 Ah = 4C → NASA equivalent 8 A > 5 A — message shows the rescale
    with pytest.raises(ValidationError, match="capacity_ah 50"):
        PredictRequest(
            battery_id="B",
            readings=_window([12.8, -200.0, 25.0, 1.0]),
            pack_config={"n_series": 4, "capacity_ah": 50.0},
        )


class TestLfpVoltageRange:
    """GH-67 — dải per-cell riêng cho LFP.

    Dải chung [2.0, 4.5] phải đủ rộng cho NMC (sạc đầy 4.2 V), nên với LFP nó
    quá lỏng: pack 8S/24V ở 26.4 V mà khai nhầm n_series=6 ra 4.40 V/cell vẫn
    lọt, dù cell LFP tối đa vật lý chỉ 3.65 V.
    """

    PACK_V = 26.4  # pin dự án: 8S LFP, đang sạc gần đầy

    def _req(self, n_series, chemistry):
        return PredictRequest(
            battery_id="BAT-LFP",
            readings=_window([self.PACK_V, -30.0, 30.0, 0.0, 800.0, 80.0]),
            pack_config={
                "n_series": n_series,
                "chemistry": chemistry,
                "capacity_ah": 30.0,
            },
        )

    def test_correct_n_series_passes(self):
        req = self._req(8, "LFP")
        assert req.pack_config.n_series == 8

    def test_n_series_too_low_now_rejected(self):
        """26.4/6 = 4.40 V/cell — bất khả thi với LFP, dải chung không chặn được."""
        with pytest.raises(ValidationError, match="n_series"):
            self._req(6, "LFP")

    def test_same_payload_passes_without_chemistry(self):
        """Không khai chemistry ⇒ vẫn dải chung — chứng minh đúng dải LFP mới chặn."""
        PredictRequest(
            battery_id="BAT",
            readings=_window([self.PACK_V, -30.0, 30.0, 0.0, 800.0, 80.0]),
            pack_config={"n_series": 6, "capacity_ah": 30.0},
        )

    def test_nmc_keeps_the_wide_range(self):
        """NMC sạc đầy 4.2 V/cell phải tiếp tục qua được — không hồi quy."""
        PredictRequest(
            battery_id="BAT-NMC",
            readings=_window([4.2, -2.0, 30.0, 0.0, 800.0, 80.0]),
            pack_config={"n_series": 1, "chemistry": "NMC"},
        )

    def test_n_series_too_high_still_slips_through(self):
        """Ghi lại giới hạn đã biết: 26.4/10 = 2.64 V/cell là điện áp xả sâu hợp
        lệ, không có cách nào chặn từ 1 cửa sổ. BE phải đối chiếu
        evidence.feature_summary.voltage.mean ≈ 3.2-3.3 V một lần lúc tích hợp."""
        self._req(10, "LFP")


class TestWindowSpanGuard:
    """GH-67 — chặn cửa sổ trải quá dài (mất kết nối giữa chừng).

    Số đo trên dữ liệu IoT thật: cửa sọ 94 phút cho SOH 81.84% +
    SCHEDULE_REPLACEMENT trên pin khoẻ, kèm confidence 0.799 (cao nhất cả file)
    nên BE không lọc được bằng confidence.
    """

    def _rows(self, times):
        return [[26.4, 0.0, 30.0, float(t), 0.0, 46.0] for t in times]

    def _req(self, times):
        return PredictRequest(
            battery_id="BAT-2026-REAL-001",
            readings=self._rows(times),
            pack_config={"n_series": 8, "chemistry": "LFP", "capacity_ah": 30.0},
        )

    def test_normal_17s_sampling_passes(self):
        """Nhịp thật của IoT là ~17s/dòng — không được chặn nhầm."""
        self._req([i * 17 for i in range(30)])

    def test_window_spanning_a_connection_gap_is_rejected(self):
        """Đúng hình dạng cửa sổ đã gây báo lỗi giả: 17 mẫu sát nhau, mất kết
        nối 76 phút, rồi 13 mẫu sát nhau."""
        times = [i * 17 for i in range(17)] + [17 * 17 + 4572 + i * 17 for i in range(13)]
        with pytest.raises(ValidationError, match="vượt trần"):
            self._req(times)

    def test_boundary_at_the_cap(self):
        from src.core.config import MAX_WINDOW_SPAN_S

        self._req([i * MAX_WINDOW_SPAN_S / 29 for i in range(30)])  # đúng trần → qua
        with pytest.raises(ValidationError, match="vượt trần"):
            self._req([i * (MAX_WINDOW_SPAN_S + 30) / 29 for i in range(30)])

    def test_large_gap_but_short_window_still_passes(self):
        """Đã đo: 15 mẫu + trống 1400s + 15 mẫu (dài 1429s) vẫn ra SOH 100.00%.
        Độ dài cửa sổ mới là yếu tố quyết định, nên đừng thêm luật khoảng trống
        riêng — sẽ chặn nhầm dữ liệu còn dùng được."""
        self._req(list(range(15)) + [15 + 1400 + i for i in range(15)])

    def test_time_going_backwards_is_rejected(self):
        """Span = t[-1]-t[0] chỉ có nghĩa khi time không giảm — bản ghi đảo thứ
        tự sẽ cho span nhỏ giả tạo và lọt qua."""
        times = [i * 17 for i in range(30)]
        times[20] = times[19] - 100
        with pytest.raises(ValidationError, match="không giảm"):
            self._req(times)

    def test_legacy_3col_payload_skips_the_check(self):
        """Payload 3 cột không có cột time — không được vỡ."""
        PredictRequest(battery_id="B", readings=_window([3.7, -1.0, 25.0]))


def test_span_cap_stays_within_lfp_scaler_range():
    """GH-67 — trần này bắt nguồn từ dải `time` mà scaler LFP được fit (1453.9s).
    Retrain làm hẹp dải đó mà quên sửa trần ⇒ lại nhận cửa sổ ngoài miền."""
    import joblib

    from src.core.config import FEATURES, LFP_SCALER_PATH, MAX_WINDOW_SPAN_S

    if not os.path.exists(LFP_SCALER_PATH):
        pytest.skip("chưa có artifact LFP")
    art = joblib.load(LFP_SCALER_PATH)
    scaler = art["scaler"] if isinstance(art, dict) else art
    ceiling = float(scaler.data_max_[FEATURES.index("time")])
    assert MAX_WINDOW_SPAN_S <= ceiling * 1.1, (
        f"MAX_WINDOW_SPAN_S={MAX_WINDOW_SPAN_S} vượt quá dải train {ceiling:.1f}s"
    )


class TestCRateNominalByChemistry:
    """GH-67 — quy dòng pack về C-rate phải dùng cell danh định của ĐÚNG bộ
    artifact. Trước đây luôn dùng 2.0 Ah (cell NASA) kể cả cho LFP, trong khi bộ
    LFP train trên cell Severson 1.1 Ah ⇒ xả 1C bị model đọc thành 1.82C.
    """

    def _accept(self, current, chemistry):
        try:
            PredictRequest(
                battery_id="BAT-2026-REAL-001",
                readings=_window([26.4, current, 30.0, 0.0, 800.0, 46.0]),
                pack_config={"n_series": 8, "chemistry": chemistry, "capacity_ah": 30.0},
            )
            return True
        except ValidationError:
            return False

    def test_1c_discharge_on_a_30ah_pack_passes(self):
        assert self._accept(-30.0, "LFP")

    def test_lfp_ceiling_is_about_136a_not_75a(self):
        """5 A × 30/1.1 = 136 A. Trần cũ 75 A (5 × 30/2.0) chặn cả tải 100 A
        trong khi BMS JK rated 100-200 A."""
        assert self._accept(-136.0, "LFP")
        assert not self._accept(-140.0, "LFP")

    def test_nasa_path_keeps_the_old_75a_ceiling(self):
        assert self._accept(-75.0, None)
        assert not self._accept(-80.0, None)

    def test_lfp_accepts_what_nasa_rejects_at_100a(self):
        """Ca cụ thể đã đo: tải 100 A trên pack 30 Ah."""
        assert self._accept(-100.0, "LFP")
        assert not self._accept(-100.0, None)


def test_schema_and_inference_use_the_same_nominal():
    """Guard bên schema và phép nhân bên inference phải dùng CÙNG một cell danh
    định — lệch nhau thì guard chấp nhận thứ mà model không nhận đúng."""
    from unittest.mock import patch

    from src.core import model_loader
    from src.core.config import NOMINAL_CAPACITY_AH, NOMINAL_CAPACITY_AH_BY_CHEMISTRY
    from src.services.inference import _resolve_artifacts

    # _resolve_artifacts("LFP") từ chối chạy khi chưa nạp bộ LFP — test này chỉ
    # kiểm hằng số đi đúng đường, không cần trọng số thật.
    with patch.object(model_loader, "lfp_soh_model", object()):
        for chemistry in ("LFP", None):
            expected = NOMINAL_CAPACITY_AH_BY_CHEMISTRY.get(chemistry, NOMINAL_CAPACITY_AH)
            assert _resolve_artifacts(chemistry).nominal_capacity_ah == expected
