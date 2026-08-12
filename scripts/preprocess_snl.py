"""
Preprocessing (LFP v2.1): Sandia National Laboratories (Preger et al. 2020, JES 167
120532) 18650 LFP cells -> windowed tensors (30, 6), optionally MERGED with the
Severson batches already used by scripts/preprocess_lfp.py.

Why this script exists
----------------------
`soh_mamba_v2.0-lfp.pth` was trained on Severson alone, and every Severson cell ran
in ONE 30 °C chamber. With TEMPERATURE_OOD_THRESHOLD = 5.0 that makes every reading
outside 25-35 °C "out of distribution", and — worse — the SOH itself is extrapolated
there: a perfectly healthy LFP pack read at 10 °C came back 85.7% SOH and produced a
P1 REPLACE_IMMEDIATELY ticket. No flag tweak fixes that; only data at other
temperatures does.

SNL cycles the SAME cell as Severson — A123 APR18650M1A, 1.1 Ah — at 15/25/35 °C, so
the two sets merge without a chemistry or capacity mismatch. Merged temperature
clusters become (15, 25, 30, 35), which clears the false-OOD band across 10-40 °C.

Input format (verified against the real files, 2026-08-11)
----------------------------------------------------------
BatteryLife's standardised pickles, one dict per cell:

    {"cell_id": "SNL_18650_LFP_35C_0-100_0.5-1C_a",
     "nominal_capacity_in_Ah": 1.1,
     "cathode_material": "LFP",
     "cycle_data": [{"cycle_number": 1,
                     "voltage_in_V": [...],        # V
                     "current_in_A": [...],        # A, NEGATIVE = discharge
                     "temperature_in_C": [...],    # °C, real sensor (not setpoint)
                     "time_in_s": [...],           # SECONDS, already 0-based per cycle
                     "discharge_capacity_in_Ah": [...],   # cumulative within cycle
                     ...}, ...]}

Sampling is a uniform 10.0 s, so a 30-row window spans 300 s.

Download (open, CC-BY-4.0, no login, no access request):
    https://zenodo.org/records/19688272/files/SNL.zip   (115 MB, 18 LFP + NCA/NMC)

batteryarchive.org hosts 30 LFP cells but no longer offers direct download; this
mirror carries 18 of them (1 @ 15 °C, 11 @ 25 °C, 6 @ 35 °C). The 15 °C coverage is
the thin spot — see --val-ids/--test-ids notes in main().

Usage
-----
    python scripts/preprocess_snl.py \
        --snl-dir data/raw/snl \
        --severson-dir data/raw/severson \
        --output-dir data/processed_lfp \
        --cycle-stride 3 --phase discharge --soh-clip 100 --soc-mode cycle

`--snl-dir` accepts either a directory containing the .pkl files (at any depth) or
the SNL.zip archive itself.

Everything downstream of parsing — discharge-segment extraction, windowing, derived
features, scaler fitting, artifact metadata — is REUSED from preprocess_lfp.py by
import, not copied. Only the reader differs. That is deliberate: the Severson path
cost ~11 hours of debugging to get right and must not be forked.
"""

import argparse
import os
import pickle
import random
import re
import sys
import time
import zipfile

import joblib
import numpy as np
import torch
from sklearn.preprocessing import MinMaxScaler, StandardScaler

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))  # repo root -> src.*
sys.path.insert(0, _HERE)  # scripts/    -> preprocess_lfp

import preprocess_lfp  # noqa: E402  (module handle — see --cycle-count-norm in main())
from preprocess_lfp import (  # noqa: E402
    CYCLE_COUNT_NORM,
    FEATURE_VAR_FLOOR,
    MAX_DISCHARGE_SECONDS,
    MAX_SOH_KEEP,
    MIN_SOH,
    SEED,
    SOH_CLIP_DEFAULT,
    TIME_UNIT_SECONDS,
    _longest_discharge_segment,
    _nonphysical_channel,
    cycles_to_windows,
    load_batch_file,
)

from src.core.config import (  # noqa: E402
    BASE_FEATURES,
    LFP_FEATURE_SCALER_PATH,
    LFP_MODEL_VERSION,
    LFP_NOMINAL_CAPACITY_AH,
    LFP_SCALER_PATH,
    WINDOW_SIZE,
    WINDOW_STRIDE,
)

# Column names required in every cycle_data entry. Asserted rather than assumed:
# if the upstream mirror ever renames a field, this raises with the ACTUAL keys
# printed instead of silently producing a tensor of zeros.
BATTERYARCHIVE_COLUMNS = {
    "voltage": "voltage_in_V",
    "current": "current_in_A",
    "temperature": "temperature_in_C",
    "time": "time_in_s",
    "capacity": "discharge_capacity_in_Ah",
}

# SNL time is already in seconds and already rebased per cycle.
SNL_TIME_SCALE = TIME_UNIT_SECONDS["seconds"]

# SNL logs at TWO different rates and only one of them is usable here (measured
# 2026-08-11 on the real archive):
#   - periodic reference-performance cycles: dt = 10 s, 0.5C, ~745 discharge rows
#   - ordinary aging cycles:                 dt = 120 s -> a 3C discharge is only
#     10 rows and a 1C discharge 29 rows, both SHORTER than WINDOW_SIZE = 30
# Windowing the 120 s cycles is impossible, so they are dropped up front rather
# than silently producing "short segment" warnings for ~95% of the archive.
# Keeping only the fine cycles still leaves 53-151 cycles per cell and ~33.7k
# windows overall, spanning SOH 97.9% -> 73.2%.
MAX_DT_SECONDS_DEFAULT = 30.0

# Deliberate held-out cells. Chosen from the real inventory, not at random:
#   - both reach BELOW 80% SOH, so val/test actually cover the band where the
#     replace/keep decision is made. Most SNL LFP cells stop around 83-88%.
#   - one at 25 °C and one at 35 °C, so per-temperature error is measurable.
# The single 15 °C cell stays in TRAIN on purpose: holding it out would remove
# 15 °C from training entirely, which is the whole point of this retrain. The
# consequence is honest and must be reported — 15 °C generalisation is NOT
# measured by this split. Fixing that needs the 3 extra 15 °C cells that only
# batteryarchive.org has (email info@batteryarchive.org).
DEFAULT_SNL_VAL = ["SNL_18650_LFP_25C_0-100_0.5-3C_c"]
DEFAULT_SNL_TEST = ["SNL_18650_LFP_35C_0-100_0.5-2C_b"]


def _iter_pickles(source: str):
    """Yield (name, bytes) for every .pkl under a directory or inside a .zip."""
    if zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as z:
            for entry in sorted(z.namelist()):
                if entry.endswith(".pkl"):
                    yield os.path.basename(entry), z.read(entry)
        return

    if not os.path.isdir(source):
        raise FileNotFoundError(f"--snl-dir '{source}' is neither a directory nor a zip")

    hits = []
    for root, _dirs, files in os.walk(source):
        for f in files:
            if f.endswith(".pkl"):
                hits.append(os.path.join(root, f))
    for path in sorted(hits):
        with open(path, "rb") as fh:
            yield os.path.basename(path), fh.read()


def _assert_schema(cell_id: str, cycle: dict) -> None:
    missing = [c for c in BATTERYARCHIVE_COLUMNS.values() if c not in cycle]
    if missing:
        raise KeyError(
            f"{cell_id}: cycle_data entry is missing {missing}. "
            f"Actual keys present: {sorted(cycle.keys())}. "
            f"The upstream mirror changed its schema — update BATTERYARCHIVE_COLUMNS."
        )


def load_snl_dir(
    source: str,
    cycle_stride: int = 1,
    discharge_only: bool = True,
    soh_clip: float = SOH_CLIP_DEFAULT,
    cathode: str = "LFP",
    max_dt_seconds: float = MAX_DT_SECONDS_DEFAULT,
) -> dict:
    """Parse SNL pickles into the same structure load_batch_file() returns.

    Returns {cell_id: {"cycle_life": int,
                       "policy": str,          # temperature/DOD/C-rate from the id
                       "cycles": [(arr(T,4) [V,I,T,t], soh, cycle_idx), ...]}}

    Cells whose cathode does not match `cathode` are skipped — the SNL archive also
    ships NCA and NMC, and mixing chemistries into the LFP artifact set is exactly
    the class of leak that produced the wrong current ceiling in GH-67.
    """
    v_i = BASE_FEATURES.index("voltage")
    i_i = BASE_FEATURES.index("current")
    t_i = BASE_FEATURES.index("temperature")
    s_i = BASE_FEATURES.index("time")

    cells: dict = {}
    n_skipped_chem = 0
    for fname, raw in _iter_pickles(source):
        obj = pickle.loads(raw)
        if not isinstance(obj, dict) or "cycle_data" not in obj:
            print(f"  [skip] {fname}: not a BatteryLife cell dict")
            continue
        if str(obj.get("cathode_material", "")).upper() != cathode.upper():
            n_skipped_chem += 1
            continue

        cell_id = obj.get("cell_id") or os.path.splitext(fname)[0]
        nominal = float(obj.get("nominal_capacity_in_Ah") or LFP_NOMINAL_CAPACITY_AH)
        if abs(nominal - LFP_NOMINAL_CAPACITY_AH) > 1e-6:
            raise ValueError(
                f"{cell_id}: nominal capacity {nominal} Ah != LFP_NOMINAL_CAPACITY_AH "
                f"{LFP_NOMINAL_CAPACITY_AH} Ah. SOH labels from two different nominals "
                f"cannot share one model — fix the config or exclude this cell."
            )

        # Drop the coarsely-logged aging cycles BEFORE applying cycle_stride, so the
        # stride subsamples usable cycles instead of mostly-unusable ones.
        fine = []
        n_coarse = 0
        for cyc in obj["cycle_data"]:
            _assert_schema(cell_id, cyc)
            t = np.asarray(cyc[BATTERYARCHIVE_COLUMNS["time"]], dtype=float)
            if t.size < WINDOW_SIZE * 2 or np.median(np.diff(t)) > max_dt_seconds:
                n_coarse += 1
                continue
            fine.append(cyc)

        kept, n_short, n_too_long, n_bad_soh = [], 0, 0, 0
        n_nonphys: dict[str, int] = {}
        for j, cyc in enumerate(fine):
            if j % cycle_stride:
                continue

            cap = cyc[BATTERYARCHIVE_COLUMNS["capacity"]]
            if cap is None or len(cap) == 0:
                n_bad_soh += 1
                continue
            soh = float(np.nanmax(np.asarray(cap, dtype=float))) / nominal * 100.0
            if not np.isfinite(soh) or soh < MIN_SOH or soh > MAX_SOH_KEEP:
                n_bad_soh += 1
                continue
            soh = min(soh, soh_clip)

            arr = np.empty((len(cyc[BATTERYARCHIVE_COLUMNS["time"]]), 4), dtype=np.float64)
            arr[:, v_i] = np.asarray(cyc[BATTERYARCHIVE_COLUMNS["voltage"]], dtype=float)
            arr[:, i_i] = np.asarray(cyc[BATTERYARCHIVE_COLUMNS["current"]], dtype=float)
            arr[:, t_i] = np.asarray(cyc[BATTERYARCHIVE_COLUMNS["temperature"]], dtype=float)
            arr[:, s_i] = np.asarray(cyc[BATTERYARCHIVE_COLUMNS["time"]], dtype=float) * SNL_TIME_SCALE
            if not np.isfinite(arr).all():
                n_nonphys["nan"] = n_nonphys.get("nan", 0) + 1
                continue

            seg = _longest_discharge_segment(arr) if discharge_only else arr
            if seg is None or len(seg) < WINDOW_SIZE:
                n_short += 1
                continue
            dur = float(seg[-1, s_i] - seg[0, s_i])
            if dur > MAX_DISCHARGE_SECONDS:
                n_too_long += 1
                continue
            bad = _nonphysical_channel(seg)
            if bad is not None:
                n_nonphys[bad] = n_nonphys.get(bad, 0) + 1
                continue

            # cycle_number is the TRUE cycle index — same convention as the Severson
            # loader. Using position-among-kept-cycles would compress the aging axis
            # by exactly cycle_stride and break cycle_count_norm at inference.
            cycle_idx = int(cyc.get("cycle_number", j + 1))
            kept.append((seg.astype(np.float32), np.float32(soh), cycle_idx))

        if len(kept) < 2:
            print(f"  [skip] {cell_id}: only {len(kept)} usable cycles")
            continue

        m = re.search(r"_(\d+)C_([\d\-]+)_([\d.]+)-([\d.]+)C_", cell_id)
        policy = f"{m.group(1)}C/{m.group(2)}/{m.group(4)}C" if m else "?"
        cells[cell_id] = {"cycle_life": kept[-1][2], "policy": policy, "cycles": kept}

        temps = np.concatenate([c[:, t_i] for c, _, _ in kept[::50]]) if kept else np.array([0.0])
        sohs = np.array([s for _, s, _ in kept])
        print(
            f"  {cell_id:<40} {len(kept):>4} cyc | SOH {sohs.max():5.1f} -> {sohs.min():5.1f}% "
            f"| T {np.nanmean(temps):5.1f}C "
            f"| drop coarse={n_coarse} short={n_short} long={n_too_long} soh={n_bad_soh} "
            f"nonphys={n_nonphys or '-'}"
        )

    if n_skipped_chem:
        print(f"  ({n_skipped_chem} cell(s) skipped — cathode != {cathode})")
    if not cells:
        raise FileNotFoundError(
            f"No usable {cathode} cells parsed from '{source}'. Expected BatteryLife "
            f"pickles named SNL_18650_{cathode}_*.pkl — download "
            f"https://zenodo.org/records/19688272/files/SNL.zip"
        )
    return cells


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--snl-dir", required=True, help="Dir of SNL .pkl files, or SNL.zip")
    parser.add_argument("--severson-dir", default=None, help="Dir with Severson *batch*.mat (optional but recommended)")
    parser.add_argument(
        "--reuse-scaler", action="store_true",
        help="Load the committed scaler_lfp.pkl/feature_scaler_lfp.pkl instead of fitting "
             "new ones, and do NOT overwrite them. Use this to SCORE an existing checkpoint "
             "on a subset of cells (e.g. SNL only, without the 8 GB Severson dataset): "
             "refitting on a subset changes the input scale the model was trained on, so "
             "the resulting error would measure that mismatch instead of the model.",
    )
    parser.add_argument("--output-dir", default="data/processed_lfp")
    parser.add_argument("--cycle-stride", type=int, default=3,
                        help="Stride for SEVERSON cycles (v2.0 used 3)")
    parser.add_argument("--snl-cycle-stride", type=int, default=1,
                        help="Stride for SNL cycles, applied AFTER the sampling-rate "
                             "filter. Default 1: only 53-151 usable cycles survive per "
                             "cell, so there is nothing to spare.")
    parser.add_argument("--max-dt-seconds", type=float, default=MAX_DT_SECONDS_DEFAULT,
                        help=f"Keep SNL cycles whose median sampling interval is <= this "
                             f"(default {MAX_DT_SECONDS_DEFAULT:g}s). See MAX_DT_SECONDS_DEFAULT.")
    parser.add_argument("--phase", choices=["discharge", "full"], default="discharge")
    parser.add_argument("--time-unit", choices=list(TIME_UNIT_SECONDS), default="minutes",
                        help="Unit of the SEVERSON time column (SNL is always seconds)")
    parser.add_argument("--soh-clip", type=float, default=SOH_CLIP_DEFAULT)
    parser.add_argument(
        "--artifact-version", default=LFP_MODEL_VERSION,
        help="Version stamped into scaler_lfp.pkl, feature_scaler_lfp.pkl and the .pt "
             f"files (default {LFP_MODEL_VERSION} from config). train.py's "
             "--feature-scaler-version MUST be given the same string or load_split() "
             "rejects the tensors. This is a CLI arg and not just the config constant "
             "because LFP_MODEL_VERSION cannot be bumped to 2.1-lfp until the 2.1 "
             "weights exist — bumping it earlier breaks loading the live 2.0 artifacts.",
    )
    parser.add_argument(
        "--cycle-count-norm", type=float, default=None,
        help="Divisor for cycle_count_norm. Default = LFP_CYCLE_COUNT_NORM from config "
             f"({CYCLE_COUNT_NORM:g}), which was sized for Severson's ~2300-cycle cells. "
             "SNL cells run to 4569 cycles, so with the Severson value roughly half of "
             "every SNL cell clips to 1.0 and the aging axis flattens exactly where the "
             "cell is oldest. Pass 4600 when merging. Whatever is used here is written "
             "into scaler_lfp.pkl and MUST be mirrored into LFP_CYCLE_COUNT_NORM before "
             "the new weights go live, or inference will disagree with training.",
    )
    parser.add_argument("--soc-mode", choices=["cycle", "window"], default="cycle")
    parser.add_argument(
        "--cluster-min-share", type=float, default=0.002,
        help="Minimum share of train windows a 5 °C bin must hold to count as a "
             "temperature cluster (default 0.002 = 0.2%%). Calibrated on the real "
             "merged set (427k windows, 2026-08-11): the 15 °C bin holds 0.36%% and is "
             "a whole dedicated cell over 65 cycles spanning SOH 93.9->84.7 — real "
             "coverage. The 45 °C bin holds 0.03%% and is only scattered self-heating "
             "peaks from Severson's 4C discharge — not coverage. 0.2%% separates the "
             "two; 1%% would wrongly throw away the only 15 °C cell we have.",
    )
    parser.add_argument("--val-ids", default=None, help="Comma-separated cell ids (overrides defaults)")
    parser.add_argument("--test-ids", default=None, help="Comma-separated cell ids (overrides defaults)")
    parser.add_argument("--severson-val-frac", type=float, default=0.04,
                        help="Fraction of Severson cells added to val (keeps the 30 °C "
                             "figure comparable with v2.0-lfp)")
    parser.add_argument("--severson-test-frac", type=float, default=0.04)
    args = parser.parse_args()

    if args.cycle_stride < 1:
        parser.error(f"--cycle-stride must be >= 1, got {args.cycle_stride}")
    if args.snl_cycle_stride < 1:
        parser.error(f"--snl-cycle-stride must be >= 1, got {args.snl_cycle_stride}")
    os.makedirs(args.output_dir, exist_ok=True)

    # cycles_to_windows() reads this off the preprocess_lfp module, so overriding it
    # here is what actually takes effect. Recorded in the scaler metadata below.
    ccn = CYCLE_COUNT_NORM if args.cycle_count_norm is None else args.cycle_count_norm
    preprocess_lfp.CYCLE_COUNT_NORM = ccn
    if ccn != CYCLE_COUNT_NORM:
        print(f"[!] cycle_count_norm ghi de: {CYCLE_COUNT_NORM:g} -> {ccn:g}. "
              f"PHAI sua LFP_CYCLE_COUNT_NORM trong src/core/config.py thanh {ccn:g} "
              f"cung commit voi weight moi.")

    print(f"Window {WINDOW_SIZE} | stride {WINDOW_STRIDE} | nominal {LFP_NOMINAL_CAPACITY_AH} Ah")
    print(f"severson stride {args.cycle_stride} | snl stride {args.snl_cycle_stride} "
          f"| max_dt {args.max_dt_seconds:g}s | cycle_count_norm {ccn:g}")
    print(f"phase {args.phase} | soh_clip {args.soh_clip}% | soc_mode {args.soc_mode}")

    t_start = time.perf_counter()

    print(f"\n=== SNL: {args.snl_dir} ===")
    all_cells = load_snl_dir(
        args.snl_dir,
        cycle_stride=args.snl_cycle_stride,
        discharge_only=(args.phase == "discharge"),
        soh_clip=args.soh_clip,
        max_dt_seconds=args.max_dt_seconds,
    )
    snl_ids = sorted(all_cells)

    severson_ids: list[str] = []
    if args.severson_dir:
        print(f"\n=== Severson: {args.severson_dir} ===")
        mats = sorted(
            f for f in os.listdir(args.severson_dir)
            if f.lower().endswith(".mat") and "batch" in f.lower()
        )
        if not mats:
            raise FileNotFoundError(f"No '*batch*.mat' in {args.severson_dir}")
        print(f"Found {len(mats)} batch file(s): {mats}")
        for idx, fname in enumerate(mats, start=1):
            all_cells.update(
                load_batch_file(
                    os.path.join(args.severson_dir, fname),
                    f"b{idx}",
                    args.cycle_stride,
                    discharge_only=(args.phase == "discharge"),
                    time_scale=TIME_UNIT_SECONDS[args.time_unit],
                    soh_clip=args.soh_clip,
                )
            )
        severson_ids = sorted(set(all_cells) - set(snl_ids))
    else:
        print("\n[!] --severson-dir khong duoc truyen: train CHI tren SNL. "
              "Mat 124 cell @30°C -> ket qua khong so sanh duoc voi v2.0-lfp.")

    t_parse = time.perf_counter()
    print(f"\n[TIMING] parse: {t_parse - t_start:.1f}s")
    print(f"Cells: {len(snl_ids)} SNL + {len(severson_ids)} Severson = {len(all_cells)}")

    # --- split ----------------------------------------------------------------
    if args.val_ids or args.test_ids:
        val_ids = [c for c in (args.val_ids.split(",") if args.val_ids else []) if c]
        test_ids = [c for c in (args.test_ids.split(",") if args.test_ids else []) if c]
    else:
        val_ids = [c for c in DEFAULT_SNL_VAL if c in all_cells]
        test_ids = [c for c in DEFAULT_SNL_TEST if c in all_cells]
        rng = random.Random(SEED)
        shuffled = severson_ids[:]
        rng.shuffle(shuffled)
        n_val = int(len(shuffled) * args.severson_val_frac)
        n_test = int(len(shuffled) * args.severson_test_frac)
        val_ids += shuffled[:n_val]
        test_ids += shuffled[n_val : n_val + n_test]

    unknown = [c for c in val_ids + test_ids if c not in all_cells]
    if unknown:
        raise ValueError(
            f"Held-out ids not found in the parsed set: {unknown}\n"
            f"Available SNL ids:\n  " + "\n  ".join(snl_ids)
        )
    overlap = set(val_ids) & set(test_ids)
    if overlap:
        raise ValueError(f"Cell(s) in BOTH val and test: {sorted(overlap)}")

    train_ids = [c for c in sorted(all_cells) if c not in val_ids and c not in test_ids]
    if not train_ids:
        raise ValueError("Train split is empty")

    train_snl = [c for c in train_ids if c in snl_ids]
    print(f"\nTrain {len(train_ids)} cells ({len(train_snl)} SNL) | "
          f"Val {len(val_ids)} | Test {len(test_ids)}")
    print(f"  val : {val_ids}")
    print(f"  test: {test_ids}")

    # --- temperature clusters: the entire reason this retrain exists -----------
    # Measured on the TRAIN split only, and from the actual sensor values rather
    # than the chamber setpoint in the cell id. That distinction matters: Severson
    # discharges at 4C and the cell self-heats well past its 30 °C chamber, so the
    # "30 °C dataset" really contributes windows up to ~45 °C. Declaring clusters
    # from setpoints would understate what the model has actually seen, and keep
    # flagging real readings as out-of-distribution.
    #
    # A 5 °C bin is kept only if it holds >= --cluster-min-share of the sampled
    # values; a handful of stray windows is not training coverage.
    t_i = BASE_FEATURES.index("temperature")
    sample = np.concatenate(
        [arr[:, t_i] for cid in train_ids for arr, _, _ in all_cells[cid]["cycles"][::20]]
    )
    sample = sample[np.isfinite(sample)]
    binned = np.round(sample / 5.0) * 5.0
    vals, counts = np.unique(binned, return_counts=True)
    share = counts / counts.sum()
    clusters = [float(v) for v, s in zip(vals, share) if s >= args.cluster_min_share]

    print("\nPhan bo nhiet do TRONG TRAIN (do tu cam bien, khong phai setpoint):")
    for v, c, s in zip(vals, counts, share):
        mark = "  <- cluster" if s >= args.cluster_min_share else ""
        print(f"  {v:5.0f}°C  {c:>9,}  {s * 100:5.2f}%{mark}")
    print(f"\nLFP_TEMPERATURE_TRAIN_CLUSTERS = {tuple(clusters)}")
    gaps = [
        g for g in np.arange(min(clusters) - 5, max(clusters) + 10, 5)
        if min(abs(g - c) for c in clusters) > 5.0
    ]
    covered = (min(clusters) - 5.0, max(clusters) + 5.0)
    print(f"  -> het co OOD gia trong khoang {covered[0]:.0f}-{covered[1]:.0f}°C"
          + (f"; VAN HO tai {gaps}" if gaps else ""))
    if args.reuse_scaler:
        print("  -> [reuse-scaler] Day chi la thong tin: KHONG sua config theo cum nay. "
              "Tap cell o day la tap con, cum that nam trong scaler_lfp.pkl da commit.")
    else:
        print("  -> chep dung tuple tren vao src/core/config.py CUNG COMMIT voi weight moi.")

    # --- scalers (fit on train only, or reuse the committed pair) -------------
    if args.reuse_scaler:
        # Scoring mode: the model on disk was trained against THIS scale. Fitting a
        # new scaler on a subset of cells would silently shift every input channel.
        for path, label in [(LFP_SCALER_PATH, "scaler_lfp.pkl"),
                            (LFP_FEATURE_SCALER_PATH, "feature_scaler_lfp.pkl")]:
            if not os.path.exists(path):
                raise FileNotFoundError(
                    f"--reuse-scaler needs {label} at '{path}', but it is not there. "
                    f"Commit the artifact set first, or drop --reuse-scaler to fit fresh."
                )
        art = joblib.load(LFP_SCALER_PATH)
        if art["version"] != args.artifact_version:
            raise ValueError(
                f"--reuse-scaler: {LFP_SCALER_PATH} is version {art['version']} but "
                f"--artifact-version says {args.artifact_version}. Scoring data against "
                f"a scaler from a different artifact set is exactly the mistake this "
                f"flag exists to prevent."
            )
        scaler = art["scaler"]
        saved_ccn = art.get("cycle_count_norm")
        if saved_ccn is not None and float(saved_ccn) != float(ccn):
            raise ValueError(
                f"--reuse-scaler: artifact was built with cycle_count_norm="
                f"{saved_ccn:g} but this run uses {ccn:g}. Pass "
                f"--cycle-count-norm {saved_ccn:g} so the cycle channel matches."
            )
        print(f"\n[reuse-scaler] Dung lai {LFP_SCALER_PATH} (v{art['version']}, "
              f"fit tren {len(art.get('trained_on', []))} cell) — KHONG fit lai, KHONG ghi de.")
        for idx, name in enumerate(BASE_FEATURES):
            print(f"  {name:<12}: [{scaler.data_min_[idx]:9.3f}, {scaler.data_max_[idx]:9.3f}]")
    else:
        print("\nFitting MinMaxScaler on train cells...")
        train_raw = np.concatenate(
            [arr for cid in train_ids for arr, _, _ in all_cells[cid]["cycles"]], axis=0
        )
        scaler = MinMaxScaler()
        scaler.fit(train_raw)
        for idx, name in enumerate(BASE_FEATURES):
            print(f"  {name:<12}: [{scaler.data_min_[idx]:9.3f}, {scaler.data_max_[idx]:9.3f}]")

    t_max = float(scaler.data_max_[BASE_FEATURES.index("time")])
    print(f"\n  [i] time max = {t_max:.0f}s. Rang buoc cho BE: 30 x dt <= {t_max:.0f} "
          f"=> chu ky lay mau <= {t_max / WINDOW_SIZE:.0f}s.")
    if t_max > MAX_DISCHARGE_SECONDS:
        print(f"  [!] time max vuot {MAX_DISCHARGE_SECONDS:.0f}s — mot outlier con lot luoi.")

    if args.reuse_scaler:
        print("[reuse-scaler] Bo qua ghi scaler_lfp.pkl — artifact production giu nguyen.")
    else:
        os.makedirs(os.path.dirname(LFP_SCALER_PATH), exist_ok=True)
        joblib.dump(
            {
                "scaler": scaler,
                "version": args.artifact_version,
                "trained_on": train_ids,
                "features": BASE_FEATURES,
                "chemistry": "LFP",
                "nominal_capacity_ah": LFP_NOMINAL_CAPACITY_AH,
                "cycle_stride": args.cycle_stride,
                "snl_cycle_stride": args.snl_cycle_stride,
                "max_dt_seconds": args.max_dt_seconds,
                "cycle_count_norm": ccn,
                "phase": args.phase,
                "time_unit_in": "seconds(SNL)+" + args.time_unit + "(severson)",
                "soh_clip": args.soh_clip,
                "soc_mode": args.soc_mode,
                "sources": {"snl": len(snl_ids), "severson": len(severson_ids)},
                "temperature_clusters": clusters,
            },
            LFP_SCALER_PATH,
        )
        print(f"Saved scaler -> {LFP_SCALER_PATH}")

    print("\nExtracting windows + spectral features (train)...")
    X_train, X_feat_train_raw, y_train, meta_train = cycles_to_windows(
        train_ids, all_cells, scaler, soc_mode=args.soc_mode, return_meta=True
    )
    print(f"  Train: {len(X_train)} windows")
    if len(X_train) == 0:
        raise ValueError("0 train windows — check --phase / --cycle-stride")

    if args.reuse_scaler:
        feat_art = joblib.load(LFP_FEATURE_SCALER_PATH)
        if feat_art["version"] != args.artifact_version:
            raise ValueError(
                f"--reuse-scaler: {LFP_FEATURE_SCALER_PATH} is version "
                f"{feat_art['version']}, expected {args.artifact_version}"
            )
        feat_scaler = feat_art["scaler"]
        X_feat_train = feat_scaler.transform(X_feat_train_raw).astype(np.float32)
        print(f"[reuse-scaler] Dung lai {LFP_FEATURE_SCALER_PATH} "
              f"(v{feat_art['version']}, {feat_art.get('n_features')} feature) — KHONG ghi de.")
    else:
        feat_scaler = StandardScaler()
        feat_scaler.fit(X_feat_train_raw)
        degenerate = feat_scaler.var_ < FEATURE_VAR_FLOOR
        n_degenerate = int(degenerate.sum())
        if n_degenerate:
            print(f"  {n_degenerate}/{len(degenerate)} feature suy bien (var < {FEATURE_VAR_FLOOR:g}) "
                  f"-> ep scale_=1.0")
            feat_scaler.scale_[degenerate] = 1.0
        X_feat_train = feat_scaler.transform(X_feat_train_raw).astype(np.float32)

        joblib.dump(
            {
                "scaler": feat_scaler,
                "version": args.artifact_version,
                "n_features": X_feat_train.shape[1],
                "var_floor": FEATURE_VAR_FLOOR,
                "n_degenerate": n_degenerate,
            },
            LFP_FEATURE_SCALER_PATH,
        )
        print(f"Saved feature_scaler -> {LFP_FEATURE_SCALER_PATH}")

    X_val, X_feat_val, y_val, meta_val = cycles_to_windows(
        val_ids, all_cells, scaler, feat_scaler, soc_mode=args.soc_mode, return_meta=True
    )
    X_test, X_feat_test, y_test, meta_test = cycles_to_windows(
        test_ids, all_cells, scaler, feat_scaler, soc_mode=args.soc_mode, return_meta=True
    )

    for name, X, y in [("train", X_train, y_train), ("val", X_val, y_val), ("test", X_test, y_test)]:
        if len(X) == 0:
            raise ValueError(f"{name} split produced 0 windows — split is unusable")
        print(f"  {name:<5}: {len(X):>7} windows | SOH {y.min():5.1f} - {y.max():5.1f}%")

    for name, X, X_feat, y, meta in [
        ("train", X_train, X_feat_train, y_train, meta_train),
        ("val", X_val, X_feat_val, y_val, meta_val),
        ("test", X_test, X_feat_test, y_test, meta_test),
    ]:
        path = os.path.join(args.output_dir, f"{name}.pt")
        torch.save(
            {
                "X": torch.tensor(X, dtype=torch.float32),
                "X_feat": torch.tensor(X_feat, dtype=torch.float32),
                "y": torch.tensor(y, dtype=torch.float32),
                "feature_scaler_version": args.artifact_version,
                # Provenance per window — lets scripts/eval_soh_by_temp.py cut the
                # error by temperature and by cell. train.py's load_split() reads
                # only X/X_feat/y and ignores these, so old and new files stay
                # interchangeable for training.
                "cell_idx": torch.tensor(meta["cell_idx"], dtype=torch.int32),
                "cell_ids": meta["cell_ids"],
                "temp_mean_c": torch.tensor(meta["temp_mean_c"], dtype=torch.float32),
                "cycle_idx": torch.tensor(meta["cycle_idx"], dtype=torch.int32),
            },
            path,
        )
        print(f"Saved {path} ({len(X)} samples)")

    t_end = time.perf_counter()
    print(f"\n[TIMING] parse {t_parse - t_start:.1f}s | windows {t_end - t_parse:.1f}s | "
          f"total {t_end - t_start:.1f}s")
    print(f"[TIMING] {len(X_train)} train windows -> {len(X_train) // 32:,} steps/epoch at batch=32")
    print("\nSNL+Severson preprocessing complete.")


if __name__ == "__main__":
    main()
