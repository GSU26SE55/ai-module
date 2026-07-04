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
