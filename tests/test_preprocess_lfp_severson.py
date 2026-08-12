"""Severson batch-file loader guards (scripts/preprocess_lfp.py).

Builds a minimal HDF5 file matching the v7.3 .mat layout the loader walks, so the
cell-exclusion rule can be tested without the 8 GB dataset.
"""

import h5py
import numpy as np
import pytest

from scripts.preprocess_lfp import SEVERSON_CONTINUATION_CELLS, load_batch_file


def _write_batch(path, n_cells, n_cycles=4, n_samples=200):
    """Minimal stand-in for a Severson .mat: object references all the way down."""
    with h5py.File(path, "w") as f:
        batch = f.create_group("batch")
        life_refs, policy_refs, summary_refs, cycles_refs = [], [], [], []

        for _ in range(n_cells):
            life = f.create_dataset(f"_life{len(life_refs)}", data=np.array([[900.0]]))
            life_refs.append(life.ref)

            pol = f.create_dataset(
                f"_pol{len(policy_refs)}",
                data=np.array([ord(c) for c in "3.6C(80%)-3.6C"], dtype=np.uint16),
            )
            policy_refs.append(pol.ref)

            summ = f.create_group(f"_summ{len(summary_refs)}")
            summ["QDischarge"] = np.linspace(1.08, 0.90, n_cycles).reshape(1, -1)
            summary_refs.append(summ.ref)

            grp = f.create_group(f"_cyc{len(cycles_refs)}")
            v_refs, i_refs, t_refs, s_refs = [], [], [], []
            for _c in range(n_cycles):
                # Charge then discharge, 30 °C, 1 s sampling.
                volt = np.concatenate([np.linspace(3.2, 3.6, 60),
                                       np.linspace(3.35, 2.1, n_samples - 60)])
                cur = np.concatenate([np.full(60, 1.1), np.full(n_samples - 60, -4.4)])
                tem = np.full(n_samples, 30.0)
                # Minutes in (time_scale=60 default). 140 discharge samples x 0.119 min
                # x 60 = ~1000 s, matching the real 4C segment length so the loader's
                # unit sniffer resolves to seconds instead of warning.
                sec = np.arange(n_samples, dtype=float) * 0.119
                for arr, refs, tag in ((volt, v_refs, "V"), (cur, i_refs, "I"),
                                       (tem, t_refs, "T"), (sec, s_refs, "t")):
                    ds = f.create_dataset(f"_{tag}{len(cycles_refs)}_{_c}", data=arr)
                    refs.append(ds.ref)
            for tag, refs in (("V", v_refs), ("I", i_refs), ("T", t_refs), ("t", s_refs)):
                grp[tag] = np.array(refs, dtype=h5py.ref_dtype).reshape(-1, 1)
            cycles_refs.append(grp.ref)

        batch["cycle_life"] = np.array(life_refs, dtype=h5py.ref_dtype).reshape(-1, 1)
        batch["policy_readable"] = np.array(policy_refs, dtype=h5py.ref_dtype).reshape(-1, 1)
        batch["summary"] = np.array(summary_refs, dtype=h5py.ref_dtype).reshape(-1, 1)
        batch["cycles"] = np.array(cycles_refs, dtype=h5py.ref_dtype).reshape(-1, 1)
    return path


def test_batch1_keeps_every_cell(tmp_path):
    """The exclusion list is batch-2 only — b1c7/b1c8/b1c9 are ordinary cells and
    must NOT be caught by a substring-style match."""
    path = _write_batch(tmp_path / "b1.mat", n_cells=17)

    cells = load_batch_file(str(path), "b1")

    assert "b1c7" in cells and "b1c8" in cells and "b1c15" in cells and "b1c16" in cells
    assert len(cells) == 17


def test_batch2_continuation_cells_are_dropped(tmp_path):
    """b2c7/8/9/15/16 are b1c0-b1c4 continued under new keys: their cycle numbering
    restarts at 1 while the cell already has 208-1060 cycles of fade, so cycle_count
    contradicts the SOH label. Measured worst-5-of-146 on the v2.1 train split."""
    path = _write_batch(tmp_path / "b2.mat", n_cells=17)

    cells = load_batch_file(str(path), "b2")

    assert SEVERSON_CONTINUATION_CELLS.isdisjoint(cells), (
        f"continuation cells leaked into the split: "
        f"{sorted(SEVERSON_CONTINUATION_CELLS & set(cells))}"
    )
    assert len(cells) == 17 - len(SEVERSON_CONTINUATION_CELLS)
    assert "b2c0" in cells and "b2c10" in cells  # neighbours untouched


def test_exclusion_list_is_exactly_the_documented_five():
    """Pinned so a future edit cannot quietly widen the drop: every extra key here
    throws away real training data."""
    assert SEVERSON_CONTINUATION_CELLS == {"b2c7", "b2c8", "b2c9", "b2c15", "b2c16"}
    assert all(k.startswith("b2c") for k in SEVERSON_CONTINUATION_CELLS)


@pytest.mark.parametrize("label", ["b1", "b3"])
def test_other_batches_are_untouched_by_the_rule(tmp_path, label):
    path = _write_batch(tmp_path / f"{label}.mat", n_cells=10)

    cells = load_batch_file(str(path), label)

    assert len(cells) == 10
