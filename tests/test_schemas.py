"""GH-65/GH-66: PackConfig + input range validation / OOD guard on PredictRequest.

Ranges (src/core/config.py): voltage per-cell [2.0, 4.5] V (checked AFTER dividing
by pack_config.n_series), current [-5, 5] A, temperature [-10, 60] °C,
soc_percent [0, 100]. NaN/Inf rejected in every column. Hard reject only.
"""

import math

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
