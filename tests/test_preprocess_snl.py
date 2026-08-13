"""Unit tests for scripts/preprocess_snl.py (LFP v2.1 multi-temperature merge).

Every case here encodes a failure that was found on the REAL Sandia archive
(2026-08-11) and that produced no error at the time — the pipeline happily
returned tensors that were silently wrong or silently empty. They are the
regression net for the class of bug this whole retrain exists to fix.
"""

import pickle
import zipfile

import numpy as np
import pytest

from scripts.preprocess_snl import (
    BATTERYARCHIVE_COLUMNS,
    MAX_DT_SECONDS_DEFAULT,
    _assert_schema,
    _iter_pickles,
    load_snl_dir,
)
from src.core.config import BASE_FEATURES, LFP_NOMINAL_CAPACITY_AH, WINDOW_SIZE

V_I = BASE_FEATURES.index("voltage")
I_I = BASE_FEATURES.index("current")
T_I = BASE_FEATURES.index("temperature")
S_I = BASE_FEATURES.index("time")


def _cycle(cycle_number=1, dt=10.0, n_charge=40, n_dis=80, qd=1.05, temp=25.0, t0=0.0):
    """One BatteryLife-shaped cycle: CC charge then CC discharge.

    dt drives the fine/coarse split — the real archive logs reference cycles at
    10 s and ordinary aging cycles at 120 s.
    t0 > 0 mimics a cycle whose clock was NOT reset at cycle start.
    """
    n = n_charge + n_dis
    t = t0 + np.arange(n) * dt
    current = np.concatenate([np.full(n_charge, 0.55), np.full(n_dis, -0.55)])
    voltage = np.concatenate(
        [np.linspace(3.20, 3.60, n_charge), np.linspace(3.35, 2.05, n_dis)]
    )
    return {
        "cycle_number": cycle_number,
        BATTERYARCHIVE_COLUMNS["voltage"]: voltage.tolist(),
        BATTERYARCHIVE_COLUMNS["current"]: current.tolist(),
        BATTERYARCHIVE_COLUMNS["temperature"]: np.full(n, temp).tolist(),
        BATTERYARCHIVE_COLUMNS["time"]: t.tolist(),
        BATTERYARCHIVE_COLUMNS["capacity"]: np.concatenate(
            [np.zeros(n_charge), np.linspace(0.0, qd, n_dis)]
        ).tolist(),
    }


def _write_cell(dirpath, cell_id, cycles, cathode="LFP", nominal=LFP_NOMINAL_CAPACITY_AH):
    payload = {
        "cell_id": cell_id,
        "cathode_material": cathode,
        "nominal_capacity_in_Ah": nominal,
        "cycle_data": cycles,
    }
    path = dirpath / f"{cell_id}.pkl"
    path.write_bytes(pickle.dumps(payload))
    return path


# ---------------------------------------------------------------- schema guard


def test_assert_schema_names_the_missing_and_the_actual_columns():
    """A renamed upstream column must fail loudly, not produce zero-filled tensors."""
    cyc = _cycle()
    cyc["voltage_V"] = cyc.pop(BATTERYARCHIVE_COLUMNS["voltage"])  # upstream rename

    with pytest.raises(KeyError) as exc:
        _assert_schema("cell-x", cyc)

    msg = str(exc.value)
    assert BATTERYARCHIVE_COLUMNS["voltage"] in msg  # what we needed
    assert "voltage_V" in msg  # what was actually there


# ---------------------------------------------------------------- source reading


def test_iter_pickles_reads_a_directory_recursively(tmp_path):
    nested = tmp_path / "SNL" / "inner"
    nested.mkdir(parents=True)
    _write_cell(nested, "A", [_cycle()])
    _write_cell(tmp_path, "B", [_cycle()])

    names = sorted(n for n, _ in _iter_pickles(str(tmp_path)))
    assert names == ["A.pkl", "B.pkl"]


def test_iter_pickles_reads_a_zip_without_extracting(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    p = _write_cell(src, "A", [_cycle()])
    zpath = tmp_path / "SNL.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.write(p, arcname="SNL/A.pkl")

    names = [n for n, _ in _iter_pickles(str(zpath))]
    assert names == ["A.pkl"]


# ---------------------------------------------------------------- sampling rate


def test_coarse_cycles_are_dropped_and_fine_cycles_kept(tmp_path):
    """The bug that silently discarded ~95% of the archive.

    SNL logs ordinary aging cycles at dt=120 s. At that rate a discharge segment
    is only 10-29 rows — shorter than WINDOW_SIZE=30 — so it can never yield a
    window. Before the filter these all fell through the generic "short segment"
    branch and the scaler lost the entire 2C/3C current range without a word.
    """
    fine = [_cycle(cycle_number=i, dt=10.0) for i in range(1, 4)]
    coarse = [_cycle(cycle_number=i, dt=120.0) for i in range(10, 14)]
    _write_cell(tmp_path, "SNL_18650_LFP_25C_0-100_0.5-1C_a", fine + coarse)

    cells = load_snl_dir(str(tmp_path))
    kept = cells["SNL_18650_LFP_25C_0-100_0.5-1C_a"]["cycles"]

    assert len(kept) == len(fine)
    assert {c_idx for _, _, c_idx in kept} == {1, 2, 3}


def test_max_dt_seconds_is_configurable(tmp_path):
    _write_cell(tmp_path, "SNL_18650_LFP_25C_0-100_0.5-1C_a",
                [_cycle(cycle_number=i, dt=60.0) for i in range(1, 4)])

    # Everything filtered out is treated as "you pointed at the wrong source",
    # not as an empty-but-valid result — an empty dict would sail on and produce
    # a 0-window tensor several minutes later.
    with pytest.raises(FileNotFoundError):
        load_snl_dir(str(tmp_path), max_dt_seconds=MAX_DT_SECONDS_DEFAULT)

    assert load_snl_dir(str(tmp_path), max_dt_seconds=90.0)


# ---------------------------------------------------------------- chemistry leak


def test_non_lfp_cathodes_are_skipped(tmp_path):
    """SNL.zip also ships NCA and NMC. Letting them into the LFP artifact set is
    the same class of leak that gave the LFP path NASA's 2.0 Ah current ceiling."""
    _write_cell(tmp_path, "SNL_18650_LFP_25C_0-100_0.5-1C_a", [_cycle()] * 3)
    _write_cell(tmp_path, "SNL_18650_NCA_25C_0-100_0.5-1C_a", [_cycle()] * 3, cathode="NCA")
    _write_cell(tmp_path, "SNL_18650_NMC_25C_0-100_0.5-1C_a", [_cycle()] * 3, cathode="NMC")

    cells = load_snl_dir(str(tmp_path))
    assert list(cells) == ["SNL_18650_LFP_25C_0-100_0.5-1C_a"]


def test_capacity_mismatch_is_rejected_not_silently_rescaled(tmp_path):
    """SOH labels derived from two different nominals cannot share one model."""
    _write_cell(tmp_path, "SNL_18650_LFP_25C_0-100_0.5-1C_a", [_cycle()] * 3, nominal=3.2)

    with pytest.raises(ValueError, match="nominal capacity"):
        load_snl_dir(str(tmp_path))


# ---------------------------------------------------------------- time convention


def test_time_is_rebased_to_zero_per_cycle(tmp_path):
    """`time` is a model input AND the Coulomb-counting axis for soc_percent.

    Feeding a clock that keeps running across cycles pushes it outside the range
    the scaler was fitted on and the SOH read collapses (measured: 97.9% -> 60.2%
    from a 900 s offset alone). Segments must always start at 0.
    """
    cycles = [_cycle(cycle_number=i, t0=i * 50_000.0) for i in range(1, 4)]
    _write_cell(tmp_path, "SNL_18650_LFP_25C_0-100_0.5-1C_a", cycles)

    kept = load_snl_dir(str(tmp_path))["SNL_18650_LFP_25C_0-100_0.5-1C_a"]["cycles"]
    assert kept
    for seg, _soh, _idx in kept:
        assert seg[0, S_I] == pytest.approx(0.0)


def test_returned_segment_is_discharge_only(tmp_path):
    """Inference only ever sees discharge telemetry; training on charge windows
    asks the model to regress a discharge-capacity label from charge samples."""
    _write_cell(tmp_path, "SNL_18650_LFP_25C_0-100_0.5-1C_a", [_cycle()] * 3)

    kept = load_snl_dir(str(tmp_path))["SNL_18650_LFP_25C_0-100_0.5-1C_a"]["cycles"]
    for seg, _soh, _idx in kept:
        assert (seg[:, I_I] < -0.1).all()
        assert len(seg) >= WINDOW_SIZE


# ---------------------------------------------------------------- labels


def test_soh_is_capacity_over_nominal(tmp_path):
    _write_cell(tmp_path, "SNL_18650_LFP_25C_0-100_0.5-1C_a",
                [_cycle(cycle_number=i, qd=0.88) for i in range(1, 4)])

    kept = load_snl_dir(str(tmp_path))["SNL_18650_LFP_25C_0-100_0.5-1C_a"]["cycles"]
    expected = 0.88 / LFP_NOMINAL_CAPACITY_AH * 100.0
    for _seg, soh, _idx in kept:
        assert soh == pytest.approx(expected, abs=1e-3)


def test_soh_above_clip_is_capped_not_dropped(tmp_path):
    """A fresh A123 delivers slightly more than its 1.1 Ah datasheet nominal.
    >100% is a spec artifact, not a health state."""
    _write_cell(tmp_path, "SNL_18650_LFP_25C_0-100_0.5-1C_a",
                [_cycle(cycle_number=i, qd=1.12) for i in range(1, 4)])

    kept = load_snl_dir(str(tmp_path), soh_clip=100.0)["SNL_18650_LFP_25C_0-100_0.5-1C_a"]["cycles"]
    assert kept
    assert all(soh == pytest.approx(100.0) for _s, soh, _i in kept)


# ---------------------------------------------------------------- aging axis


def test_cycle_index_is_the_true_cycle_number_not_the_kept_position(tmp_path):
    """cycle_count_norm must mean the same thing at train and inference time.

    Numbering by position among kept cycles would compress the aging axis by
    exactly the stride — cycle 4000 would report as 500 — while BE sends the
    battery's real cycle count.
    """
    cycles = [_cycle(cycle_number=n) for n in (1, 500, 1500, 4000)]
    _write_cell(tmp_path, "SNL_18650_LFP_25C_0-100_0.5-1C_a", cycles)

    kept = load_snl_dir(str(tmp_path), cycle_stride=2)["SNL_18650_LFP_25C_0-100_0.5-1C_a"]["cycles"]
    assert [idx for _s, _y, idx in kept] == [1, 1500]


def test_cycle_stride_is_applied_after_the_sampling_rate_filter(tmp_path):
    """Striding the raw cycle list would mostly subsample unusable coarse cycles
    and could skip the usable ones entirely."""
    cycles = []
    n = 1
    for _ in range(4):
        cycles.append(_cycle(cycle_number=n, dt=10.0))
        n += 1
        for _ in range(3):
            cycles.append(_cycle(cycle_number=n, dt=120.0))
            n += 1
    _write_cell(tmp_path, "SNL_18650_LFP_25C_0-100_0.5-1C_a", cycles)

    kept = load_snl_dir(str(tmp_path), cycle_stride=2)["SNL_18650_LFP_25C_0-100_0.5-1C_a"]["cycles"]
    # 4 fine cycles survive the dt filter; stride 2 over THOSE leaves 2.
    assert len(kept) == 2


# ---------------------------------------------------------------- window provenance


def _fitted_scaler(all_cells):
    from sklearn.preprocessing import MinMaxScaler

    return MinMaxScaler().fit(
        np.concatenate([seg for c in all_cells.values() for seg, _, _ in c["cycles"]])
    )


def _two_cells(tmp_path):
    """Two cells at DIFFERENT chamber temperatures — the whole point of the merge."""
    _write_cell(tmp_path, "SNL_18650_LFP_15C_0-100_0.5-2C_b",
                [_cycle(cycle_number=i, temp=15.0) for i in range(1, 4)])
    _write_cell(tmp_path, "SNL_18650_LFP_35C_0-100_0.5-2C_b",
                [_cycle(cycle_number=i, temp=35.0) for i in range(1, 4)])
    return load_snl_dir(str(tmp_path))


def test_meta_is_opt_in_so_existing_callers_keep_the_3_tuple(tmp_path):
    """cycles_to_windows is shared with preprocess_lfp.py — changing the default
    return shape would break that caller silently at unpack time."""
    from preprocess_lfp import cycles_to_windows

    cells = _two_cells(tmp_path)
    ids = sorted(cells)
    out = cycles_to_windows(ids, cells, _fitted_scaler(cells))
    assert len(out) == 3


def test_meta_records_which_cell_and_what_temperature_each_window_came_from(tmp_path):
    """Without this, a test-set MAE is one aggregate number: the per-cell split
    cannot be reconstructed from X at all, so a cell carrying broken sensor data
    is invisible."""
    from preprocess_lfp import cycles_to_windows

    cells = _two_cells(tmp_path)
    ids = sorted(cells)
    X, _feat, y, meta = cycles_to_windows(ids, cells, _fitted_scaler(cells), return_meta=True)

    assert set(meta) == {"cell_idx", "cell_ids", "temp_mean_c", "cycle_idx"}
    assert meta["cell_ids"] == ids
    for key in ("cell_idx", "temp_mean_c", "cycle_idx"):
        assert len(meta[key]) == len(X) == len(y), f"{key} must be one entry per window"

    # Temperature is RAW °C, not the MinMax-scaled column: bucketing along the
    # scaled axis would tie the numbers to whichever scaler was fit that run.
    for pos, cid in enumerate(ids):
        m = meta["cell_idx"] == pos
        assert m.any(), f"{cid} produced no window"
        expected = 15.0 if "15C" in cid else 35.0
        assert meta["temp_mean_c"][m] == pytest.approx(expected, abs=1e-3)


def test_meta_cycle_idx_matches_the_label_source(tmp_path):
    from preprocess_lfp import cycles_to_windows

    cells = _two_cells(tmp_path)
    ids = sorted(cells)
    _X, _feat, _y, meta = cycles_to_windows(ids, cells, _fitted_scaler(cells), return_meta=True)

    real = {idx for c in cells.values() for _seg, _soh, idx in c["cycles"]}
    assert set(meta["cycle_idx"].tolist()) <= real


# ---------------------------------------------------------------- empty input


def test_no_usable_cells_raises_with_the_download_url(tmp_path):
    _write_cell(tmp_path, "SNL_18650_NCA_25C_0-100_0.5-1C_a", [_cycle()] * 3, cathode="NCA")

    with pytest.raises(FileNotFoundError, match="zenodo"):
        load_snl_dir(str(tmp_path))
