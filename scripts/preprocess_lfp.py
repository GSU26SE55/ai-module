"""
Preprocessing script (GH-67 Mức 2): Severson et al. 2019 (Nature Energy) LFP/graphite
battery dataset -> windowed tensors (30, 6), same shape/convention as scripts/preprocess.py.

Source: https://data.matr.io/1/ — raw .mat v7.3 (HDF5) files, one per batch
(Batch1/2/3). Parsing follows the dataset authors' own BuildPkl_BatchN.ipynb
(https://github.com/rdbraatz/data-driven-prediction-of-battery-cycle-life-before-capacity-degradation),
adapted for modern h5py (that notebook's `.value` attribute was removed in h5py 3.x
-> use `[()]` instead).

Differs from scripts/preprocess.py only in: (a) input format (h5py .mat instead of
NASA's per-cycle CSV + metadata.csv), (b) NOMINAL_CAPACITY = 1.1 Ah (A123
APR18650M1A) instead of NASA's 2.0 Ah. Windowing, derived-feature logic
(cycle_count_norm, soc_percent), and spectral feature extraction are UNCHANGED —
reuses src.features.extractor exactly like the NASA pipeline, so inference-time
behavior (src/services/inference.py) stays identical regardless of chemistry.

Usage:
    python scripts/preprocess_lfp.py \
        --data-dir data/raw/severson \
        --output-dir data/processed_lfp

Input: --data-dir must contain 1-3 Severson .mat files (any filename containing
"batch", case-insensitive — matches the official
2017-05-12_batchdata_updated_struct_errorcorrect.mat-style naming).

Output:
    data/processed_lfp/{train,val,test}.pt   — {"X": (N,30,6), "X_feat": (N,57), "y": (N,)}
    models/weights/scaler_lfp.pkl
    models/weights/feature_scaler_lfp.pkl

Split: by battery (cell), NOT by timestep — matches project convention
(.claude/rules/tech/ai.md). Cell IDs across all provided batch files are pooled,
deterministically shuffled (SEED=42), and the last --val-frac / --test-frac
fraction held out. Exact cell keys actually used are printed at the end —
override with --val-ids/--test-ids (comma-separated, e.g. "b1c0,b1c1") once you
know which cells you want held out.
"""

import argparse
import os
import random
import sys
import time

import h5py
import joblib
import numpy as np
import torch
from sklearn.preprocessing import MinMaxScaler, StandardScaler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import (
    BASE_FEATURES,
    LFP_CYCLE_COUNT_NORM,
    LFP_FEATURE_SCALER_PATH,
    LFP_MODEL_VERSION,
    LFP_NOMINAL_CAPACITY_AH,
    LFP_SCALER_PATH,
    WINDOW_SIZE,
    WINDOW_STRIDE,
)
from src.features.extractor import (
    compute_phase_mask,
    compute_soc_percent,
    extract_window_features,
)

SEED = 42
MIN_SOH = 10.0  # same filter convention as scripts/preprocess.py — drop dead/corrupt cycles

# Physically impossible sensor values — thermocouple dropouts and voltage-probe
# glitches in the raw Severson export survive the isfinite() check below (-270.0
# and 400.0 are finite, just absurd) and then poison MinMaxScaler.fit(), which is
# fit on min/max. Measured on the v2.0-lfp artifacts BEFORE this filter: the
# scaler spanned temperature [-270, 400] and voltage [0.736, 6.606], so a real
# 28-45°C swing occupied 2.5% of the [0,1] output range (39x resolution loss) and
# real 2.0-3.65V occupied 28% (3.6x loss) — the temperature channel was
# effectively dead as a model input.
#
# Bounds are deliberately loose: they only need to catch sentinel/glitch values,
# NOT enforce the operating envelope. A123 APR18650M1A runs 2.0-3.65 V/cell at
# 30°C chamber (cells self-heat during the 4-8C fast-charge steps), and Severson's
# protocol legitimately reaches ~8 A charge (7.4C on a 1.1 Ah cell), so the
# current bound stays wide enough not to discard real fast-charge data.
PHYSICAL_RANGES = {
    "voltage": (1.0, 4.5),
    "current": (-25.0, 25.0),
    "temperature": (-20.0, 80.0),
    # Elapsed time within a cycle cannot be negative. Measured on the v2.0-lfp
    # scaler: the time column spanned [-57510.7, 4825.5] — the negative end is
    # another export glitch, and it matters because `time` is a model input AND
    # the integration axis for compute_soc_percent()'s Coulomb counting.
    "time": (0.0, 200_000.0),
}

# Severson stores cycle time in MINUTES; NASA (scripts/preprocess.py) and the
# production payload BE sends both use SECONDS. Confirmed on the run-3 artifacts:
# scaler_lfp.pkl fit `time` over [0.000, 24.130], and a 4C discharge of a 1.1 Ah
# cell lasts ~15 min — so 24.13 is minutes, not seconds (24 s at 4C is physically
# impossible).
#
# Two things break without this conversion:
#   1. compute_soc_percent() does t_hours = time / 3600, i.e. it assumes seconds.
#      Fed minutes, it under-counts drawn charge 60x — soc_percent stayed ~100
#      across every training window, so that model input channel was dead.
#   2. Worse at inference: BE sends seconds, but the scaler was fit on minutes.
#      A 300 s reading scales to 12.43 when training only ever saw [0, 1] —
#      massively out of distribution, with no error raised.
TIME_UNIT_SECONDS = {"minutes": 60.0, "seconds": 1.0}

# StandardScaler divides by sqrt(var), so a feature whose training variance is
# pure floating-point rounding noise gets that noise amplified to unit variance.
# Measured on the run-3 feature_scaler_lfp.pkl: 7 of the 57 features sat at
# var 1e-10..4e-9 and were being amplified 15,000x-93,000x —
#   spec.temp.centroid  93,072x     spec.temp.band_mid   76,739x
#   spec.temp.band_high 62,733x     spec.temp.band_low   34,788x
#   spec.temp.gini      26,727x     stat.temp.waveform   19,610x
#   spec.temp.flatness  15,210x
# i.e. almost the whole temperature spectral block. Severson runs in a 30 °C
# chamber, so temperature is near-constant inside a 30-step window; its FFT is
# essentially DC and every spectral-shape descriptor degenerates.
#
# These 7 feed film_proj, which emits the gamma/beta modulating EVERY hidden
# unit — so the noise spreads across the whole representation and shows up as
# prediction variance (RMSE). Flooring scale_ at 1.0 for them makes the value
# collapse to ~0 (x - mean, undivided) instead: a dead input rather than a noise
# input. NASA's scaler is left alone (its degenerate set is much smaller and
# v1.6 is already shipped).
#
# 1e-8 sits in a clear gap: the harmful block is at var ~1e-10, while the
# smallest feature carrying real signal (spec.voltage.centroid) is at ~1.4e-6.
FEATURE_VAR_FLOOR = 1e-8
CYCLE_COUNT_NORM = LFP_CYCLE_COUNT_NORM  # Severson-specific (2300) — NOT the NASA 200
# value, whose cells cycle 10x fewer times. See src/core/config.py comment.

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)


def _h5_str(dataset) -> str:
    """Decode a MATLAB char array stored as uint16 codes (policy_readable pattern)."""
    return dataset[()].tobytes()[::2].decode(errors="replace")


def _nonphysical_channel(cycle_arr: np.ndarray) -> str | None:
    """Name of the first channel holding a physically impossible value, else None.

    Whole-cycle rejection (rather than clipping the offending samples) because a
    cycle with a sensor dropout has untrustworthy dynamics throughout, and the
    30-step windows sliced from it feed spectral/kurtosis features that a clipped
    plateau would distort just as badly as the raw glitch.
    """
    for idx, name in enumerate(BASE_FEATURES):  # voltage, current, temperature, time
        lo, hi = PHYSICAL_RANGES[name]
        col = cycle_arr[:, idx]
        if col.min() < lo or col.max() > hi:
            return name
    return None


def _longest_discharge_segment(cycle_arr: np.ndarray) -> np.ndarray | None:
    """Longest contiguous discharge run of a Severson cycle, time rebased to 0.

    Severson stores the WHOLE cycle — multi-step fast charge (CC1-CC2-CC3-CC4-CV,
    positive current up to ~8 A) followed by the 4C discharge — in one array.
    NASA's pipeline instead feeds discharge cycles ONLY (scripts/preprocess.py
    filters metadata `type == "discharge"`), and inference sees discharge
    telemetry too. Training the LFP model on windows sliced anywhere in the full
    cycle therefore (a) puts ~half the windows in a charge phase the production
    model never sees, and (b) asks it to regress a discharge-capacity label
    (QDischarge) from charge-phase samples that barely encode it.

    Phase detection reuses src/features/extractor.compute_phase_mask (2 =
    discharge, i.e. current < -0.1 A) so the charge/discharge convention lives in
    exactly one place. Time is rebased so the segment starts at 0, matching NASA's
    per-cycle CSVs — `time` is both a model input channel and the integration axis
    for compute_soc_percent().

    Returns None when no discharge run is at least WINDOW_SIZE long.
    """
    phase = compute_phase_mask(cycle_arr[:, BASE_FEATURES.index("current")])
    idx = np.flatnonzero(phase == 2.0)
    if idx.size < WINDOW_SIZE:
        return None

    # Split idx into contiguous runs, take the longest.
    breaks = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate(([0], breaks + 1))
    ends = np.concatenate((breaks + 1, [idx.size]))
    k = int(np.argmax(ends - starts))
    s, e = int(idx[starts[k]]), int(idx[ends[k] - 1]) + 1
    if e - s < WINDOW_SIZE:
        return None

    seg = cycle_arr[s:e].copy()
    seg[:, BASE_FEATURES.index("time")] -= seg[0, BASE_FEATURES.index("time")]
    return seg


def load_batch_file(
    mat_path: str,
    batch_label: str,
    cycle_stride: int = 1,
    discharge_only: bool = True,
    time_scale: float = 60.0,
) -> dict:
    """
    Parse one Severson .mat v7.3 file into {cell_key: {"cycle_life", "policy",
    "cycles": [(V, I, T, t, cycle_idx), ...], "QDischarge": array}}.

    cell_key = f"{batch_label}c{i}" (e.g. "b1c0") — matches the original
    BuildPkl_BatchN.ipynb naming convention.

    cycle_stride > 1 keeps only every Nth cycle. Severson cells run 800-2300
    cycles (vs NASA's ~170), and consecutive cycles differ by ~0.01-0.02% SOH —
    so the full set is largely redundant while costing a proportional amount of
    parse + feature-extraction time. Stride 5 still leaves 160-460 cycles per
    cell (comparable to NASA's per-cell density) across the same full SOH range.

    ⚠️ cycle_idx here is the TRUE cycle number j from the .mat file, NOT the
    "position among kept cycles" that scripts/preprocess.py documents for NASA.
    That NASA convention only works because it drops almost nothing; under
    subsampling it would compress the aging axis by exactly cycle_stride (cycle
    2000 would report as 400), so cycle_count_norm would no longer mean the same
    thing it does at inference, where BE sends the battery's real cycle count
    (src/services/inference.py::_raw_cycle_count). Using j keeps train and
    inference on the same scale.

    Defensive: a malformed cycle (shape mismatch, NaN) is skipped with a
    warning rather than aborting the whole file — real HDF5 exports of this
    dataset are known to have occasional corrupt entries.
    """
    cells: dict = {}
    n_nonphysical = [0]  # list = mutable counter reachable from the inner loop
    n_no_discharge = [0]
    durations: list[float] = []
    with h5py.File(mat_path, "r") as f:
        if "batch" not in f:
            raise ValueError(
                f"{mat_path}: no top-level 'batch' key — not a recognized Severson "
                f"batch file (found keys: {list(f.keys())})"
            )
        batch = f["batch"]
        num_cells = batch["summary"].shape[0]
        print(f"  {batch_label}: {num_cells} cells in {os.path.basename(mat_path)}")

        for i in range(num_cells):
            key = f"{batch_label}c{i}"
            try:
                cycle_life = float(f[batch["cycle_life"][i, 0]][()][0, 0])
                policy = _h5_str(f[batch["policy_readable"][i, 0]])
                qd_summary = np.hstack(f[batch["summary"][i, 0]]["QDischarge"][0, :].tolist())

                cycles_grp = f[batch["cycles"][i, 0]]
                n_cycles = cycles_grp["V"].shape[0]
                kept_cycles = []
                for j in range(0, n_cycles, cycle_stride):
                    try:
                        V = np.hstack(f[cycles_grp["V"][j, 0]][()])
                        I = np.hstack(f[cycles_grp["I"][j, 0]][()])
                        T = np.hstack(f[cycles_grp["T"][j, 0]][()])
                        t = np.hstack(f[cycles_grp["t"][j, 0]][()])
                    except Exception as exc:
                        print(f"    [{key}] cycle {j}: skipped (unreadable: {exc})")
                        continue
                    n = min(len(V), len(I), len(T), len(t))
                    if n < WINDOW_SIZE:
                        continue
                    cycle_arr = np.stack(
                        [V[:n], I[:n], T[:n], t[:n] * time_scale], axis=1
                    ).astype(np.float32)
                    if not np.all(np.isfinite(cycle_arr)):
                        print(f"    [{key}] cycle {j}: skipped (NaN/Inf)")
                        continue
                    bad = _nonphysical_channel(cycle_arr)
                    if bad is not None:
                        n_nonphysical[0] += 1
                        continue
                    if discharge_only:
                        cycle_arr = _longest_discharge_segment(cycle_arr)
                        if cycle_arr is None:
                            n_no_discharge[0] += 1
                            continue
                        durations.append(float(cycle_arr[-1, 3] - cycle_arr[0, 3]))
                    soh = (
                        float(qd_summary[j]) / LFP_NOMINAL_CAPACITY_AH * 100
                        if j < len(qd_summary)
                        else None
                    )
                    if soh is None or soh < MIN_SOH or soh > 105.0:
                        continue
                    # j = true cycle number (see load_batch_file docstring) —
                    # NOT len(kept_cycles), which would collapse under stride.
                    kept_cycles.append((cycle_arr, soh, j))

                if kept_cycles:
                    cells[key] = {
                        "cycle_life": cycle_life,
                        "policy": policy,
                        "cycles": kept_cycles,
                    }
            except Exception as exc:
                print(f"  [{key}] skipped entirely (cell-level error: {exc})")
                continue

    if n_nonphysical[0]:
        # Watch this number: a handful of dropouts is the expected case. If it is
        # a large share of the batch, switch from dropping cycles to clipping the
        # offending samples — dropping would then be throwing away real training data.
        print(
            f"  {batch_label}: {n_nonphysical[0]} cycles dropped (sensor value outside "
            f"{PHYSICAL_RANGES}) — these are what previously widened the scaler range"
        )
    if n_no_discharge[0]:
        print(f"  {batch_label}: {n_no_discharge[0]} cycles dropped (no discharge run >= {WINDOW_SIZE})")
    if durations:
        med = float(np.median(durations))
        # Decides a real question we cannot answer offline: compute_soc_percent()
        # divides `time` by 3600, i.e. it assumes SECONDS (NASA convention, and
        # what BE sends at inference). A 4C discharge lasts ~15 min, so a median
        # near ~900 means seconds; a median near ~15 means Severson stores minutes
        # and the Coulomb-counted soc_percent channel is off by 60x.
        unit = "giay (khop NASA)" if med > 200 else "PHUT? -> soc_percent lech 60x, BAO LAI"
        print(f"  {batch_label}: discharge duration trung vi = {med:.1f} -> {unit}")
    return cells


def cycles_to_windows(
    cell_ids: list[str],
    all_cells: dict,
    scaler: MinMaxScaler,
    feat_scaler: StandardScaler | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Same windowing/derived-feature logic as scripts/preprocess.py's
    cycles_to_windows() (window=30, non-overlapping stride, cycle_count_norm +
    Coulomb-counted soc_percent appended after scaling) — kept in lockstep so
    inference (src/services/inference.py) sees identical feature semantics
    regardless of which chemistry trained the weights."""
    all_X, all_feat, all_y = [], [], []

    for cid in cell_ids:
        for cycle_raw, soh, cycle_idx in all_cells[cid]["cycles"]:
            T = len(cycle_raw)
            cycle_scaled = scaler.transform(cycle_raw).astype(np.float32)
            cycle_count_norm = np.float32(np.clip(cycle_idx / CYCLE_COUNT_NORM, 0.0, 1.0))

            for i in range(0, T - WINDOW_SIZE + 1, WINDOW_STRIDE):
                window = cycle_scaled[i : i + WINDOW_SIZE]
                window_feat = extract_window_features(window[:, :3])
                raw_win = cycle_raw[i : i + WINDOW_SIZE]
                soc_norm = (
                    compute_soc_percent(
                        raw_win[:, 1], raw_win[:, 3], nominal_capacity_ah=LFP_NOMINAL_CAPACITY_AH
                    )
                    / 100.0
                )
                window = np.column_stack(
                    [window, np.full(WINDOW_SIZE, cycle_count_norm, dtype=np.float32), soc_norm]
                )
                all_X.append(window)
                all_feat.append(window_feat)
                all_y.append(soh)

    X = np.array(all_X, dtype=np.float32)
    X_feat = np.array(all_feat, dtype=np.float32)
    y = np.array(all_y, dtype=np.float32)

    if feat_scaler is not None:
        X_feat = feat_scaler.transform(X_feat).astype(np.float32)

    return X, X_feat, y


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, help="Dir containing Severson .mat files")
    parser.add_argument("--output-dir", default="data/processed_lfp")
    parser.add_argument("--val-frac", type=float, default=0.05)
    parser.add_argument("--test-frac", type=float, default=0.05)
    parser.add_argument("--val-ids", default=None, help="Comma-separated cell keys, overrides --val-frac")
    parser.add_argument("--test-ids", default=None, help="Comma-separated cell keys, overrides --test-frac")
    parser.add_argument(
        "--cycle-stride",
        type=int,
        default=1,
        help="Keep only every Nth cycle (default 1 = all). Severson cells run 800-2300 "
        "cycles with ~0.01%% SOH change between neighbours, so N=5 cuts dataset size and "
        "preprocess/train time ~5x at negligible information loss. See load_batch_file().",
    )
    parser.add_argument(
        "--phase",
        choices=["discharge", "all"],
        default="discharge",
        help="'discharge' (default) keeps only the longest discharge run of each cycle, "
        "matching scripts/preprocess.py (NASA feeds discharge cycles only) and what "
        "inference sees. 'all' keeps the raw Severson cycle incl. the fast-charge steps "
        "— the pre-2026-07-25 behaviour, kept for ablation.",
    )
    parser.add_argument(
        "--time-unit",
        choices=["minutes", "seconds"],
        default="minutes",
        help="Unit of the raw Severson `t` column (default: minutes — verified against the "
        "run-3 scaler, see TIME_UNIT_SECONDS). Converted to SECONDS internally so training "
        "matches NASA's convention and the payload BE sends at inference.",
    )
    args = parser.parse_args()
    if args.cycle_stride < 1:
        parser.error(f"--cycle-stride must be >= 1, got {args.cycle_stride}")

    os.makedirs(args.output_dir, exist_ok=True)
    print(f"Window size: {WINDOW_SIZE} | Stride: {WINDOW_STRIDE} | LFP nominal capacity: {LFP_NOMINAL_CAPACITY_AH} Ah")
    print(f"Cycle stride: {args.cycle_stride} | cycle_count_norm divisor: {CYCLE_COUNT_NORM}")
    print(f"Phase filter: {args.phase} | time unit vao: {args.time_unit} -> quy ve GIAY")

    mat_files = sorted(
        f for f in os.listdir(args.data_dir)
        if f.lower().endswith(".mat") and "batch" in f.lower()
    )
    if not mat_files:
        raise FileNotFoundError(
            f"No '*batch*.mat' files found in {args.data_dir} — download Batch1/2/3 "
            f"from https://data.matr.io/1/ first."
        )
    print(f"Found {len(mat_files)} batch file(s): {mat_files}")

    # Timing breakdown: the .mat parse and the per-window feature extraction have
    # very different costs, and knowing the split decides whether --cycle-stride
    # or the training loop is what needs tuning to fit Kaggle's 12h session limit.
    t_start = time.perf_counter()

    all_cells: dict = {}
    for idx, fname in enumerate(mat_files, start=1):
        batch_label = f"b{idx}"
        cells = load_batch_file(
            os.path.join(args.data_dir, fname),
            batch_label,
            args.cycle_stride,
            discharge_only=(args.phase == "discharge"),
            time_scale=TIME_UNIT_SECONDS[args.time_unit],
        )
        all_cells.update(cells)
    t_parse = time.perf_counter()
    print(f"\n[TIMING] .mat parse: {t_parse - t_start:.1f}s")

    cell_ids = sorted(all_cells.keys())
    print(f"\nTotal usable cells: {len(cell_ids)}")
    if len(cell_ids) < 5:
        raise ValueError(
            f"Only {len(cell_ids)} usable cells found — too few to split train/val/test. "
            f"Check the .mat file(s) actually parsed correctly (see warnings above)."
        )

    if args.val_ids or args.test_ids:
        val_ids = args.val_ids.split(",") if args.val_ids else []
        test_ids = args.test_ids.split(",") if args.test_ids else []
        train_ids = [c for c in cell_ids if c not in val_ids and c not in test_ids]
    else:
        rng = random.Random(SEED)
        shuffled = cell_ids[:]
        rng.shuffle(shuffled)
        n_val = max(1, int(len(shuffled) * args.val_frac))
        n_test = max(1, int(len(shuffled) * args.test_frac))
        val_ids = shuffled[:n_val]
        test_ids = shuffled[n_val : n_val + n_test]
        train_ids = shuffled[n_val + n_test :]

    print(f"Train: {len(train_ids)} cells | Val: {len(val_ids)} cells {val_ids} | Test: {len(test_ids)} cells {test_ids}")

    print("\nFitting MinMaxScaler on train cells...")
    train_raw = np.concatenate(
        [c for cid in train_ids for c, _, _ in all_cells[cid]["cycles"]], axis=0
    )
    scaler = MinMaxScaler()
    scaler.fit(train_raw)
    # Print the fitted range: this is what silently broke the first v2.0-lfp run
    # (temperature spanned [-270, 400], squashing the real 28-45°C swing into 2.5%
    # of [0,1]). Expect voltage ~[2, 3.7], temperature ~[25, 50] once the
    # PHYSICAL_RANGES filter is doing its job.
    for idx, name in enumerate(BASE_FEATURES[:3]):
        print(f"  scaler range {name:<12}: [{scaler.data_min_[idx]:9.3f}, {scaler.data_max_[idx]:9.3f}]")
    os.makedirs(os.path.dirname(LFP_SCALER_PATH), exist_ok=True)
    joblib.dump(
        {
            "scaler": scaler,
            "version": LFP_MODEL_VERSION,
            "trained_on": train_ids,
            "features": BASE_FEATURES,
            "chemistry": "LFP",
            "nominal_capacity_ah": LFP_NOMINAL_CAPACITY_AH,
            # Traceability: both values change what the model learned, and both
            # must match at inference (cycle_count_norm divisor especially).
            "cycle_stride": args.cycle_stride,
            "cycle_count_norm": CYCLE_COUNT_NORM,
            "phase": args.phase,
            "time_unit_in": args.time_unit,  # luu ra GIAY bat ke input la gi
        },
        LFP_SCALER_PATH,
    )
    print(f"Saved scaler -> {LFP_SCALER_PATH}")

    print("\nExtracting windows + spectral features (train)...")
    X_train, X_feat_train_raw, y_train = cycles_to_windows(train_ids, all_cells, scaler)
    print(f"  Train: {len(X_train)} windows")

    feat_scaler = StandardScaler()
    feat_scaler.fit(X_feat_train_raw)

    # Floor scale_ on degenerate features BEFORE transforming anything, so train,
    # val, test and inference all go through the identical mapping (val/test call
    # feat_scaler.transform() below; inference loads this same pickle). See
    # FEATURE_VAR_FLOOR for why these would otherwise inject amplified noise.
    degenerate = feat_scaler.var_ < FEATURE_VAR_FLOOR
    n_degenerate = int(degenerate.sum())
    if n_degenerate:
        worst = np.argsort(np.where(degenerate, feat_scaler.var_, np.inf))[:n_degenerate]
        print(f"  {n_degenerate}/{len(degenerate)} feature suy bien (var < {FEATURE_VAR_FLOOR:g}) "
              f"-> ep scale_=1.0 thay vi khuech dai nhieu:")
        for i in worst:
            amp = 1.0 / feat_scaler.scale_[i] if feat_scaler.scale_[i] > 0 else 0.0
            print(f"     idx {i:>2}: var={feat_scaler.var_[i]:.3e}  (dang khuech dai {amp:,.0f}x)")
        feat_scaler.scale_[degenerate] = 1.0

    X_feat_train = feat_scaler.transform(X_feat_train_raw).astype(np.float32)
    joblib.dump(
        {
            "scaler": feat_scaler,
            "version": LFP_MODEL_VERSION,
            "n_features": X_feat_train.shape[1],
            "var_floor": FEATURE_VAR_FLOOR,
            "n_degenerate": n_degenerate,
        },
        LFP_FEATURE_SCALER_PATH,
    )
    print(f"Saved feature_scaler -> {LFP_FEATURE_SCALER_PATH}")

    X_val, X_feat_val, y_val = cycles_to_windows(val_ids, all_cells, scaler, feat_scaler)
    X_test, X_feat_test, y_test = cycles_to_windows(test_ids, all_cells, scaler, feat_scaler)

    print(f"\nSplit summary:")
    print(f"  Train: {len(X_train):>6} windows ({len(train_ids)} cells)")
    print(f"  Val  : {len(X_val):>6} windows ({len(val_ids)} cells: {val_ids})")
    print(f"  Test : {len(X_test):>6} windows ({len(test_ids)} cells: {test_ids})")

    for name, X, X_feat, y in [
        ("train", X_train, X_feat_train, y_train),
        ("val", X_val, X_feat_val, y_val),
        ("test", X_test, X_feat_test, y_test),
    ]:
        path = os.path.join(args.output_dir, f"{name}.pt")
        torch.save(
            {
                "X": torch.tensor(X, dtype=torch.float32),
                "X_feat": torch.tensor(X_feat, dtype=torch.float32),
                "y": torch.tensor(y, dtype=torch.float32),
                "feature_scaler_version": LFP_MODEL_VERSION,
            },
            path,
        )
        print(f"Saved {name}.pt ({len(X)} samples)")

    t_end = time.perf_counter()
    print(
        f"\n[TIMING] .mat parse: {t_parse - t_start:.1f}s | "
        f"window+feature extraction: {t_end - t_parse:.1f}s | "
        f"total: {t_end - t_start:.1f}s"
    )
    print(
        f"[TIMING] {len(X_train)} train windows -> at batch=32 that is "
        f"{len(X_train) // 32:,} steps/epoch"
    )

    print("\nLFP preprocessing complete.")
    print(
        "NOTE: held-out val/test cell IDs were chosen by random shuffle (SEED=42), not "
        "hand-picked for a specific SOH/policy spread (unlike NASA's B0046/B0048 choice). "
        "Re-run with --val-ids/--test-ids once you've reviewed the printed cell list, if you "
        "want a deliberate held-out set (e.g. matching cycle-life extremes)."
    )


if __name__ == "__main__":
    main()
