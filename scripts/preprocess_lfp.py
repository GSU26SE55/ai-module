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

import h5py
import joblib
import numpy as np
import torch
from sklearn.preprocessing import MinMaxScaler, StandardScaler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import (
    BASE_FEATURES,
    LFP_FEATURE_SCALER_PATH,
    LFP_MODEL_VERSION,
    LFP_NOMINAL_CAPACITY_AH,
    LFP_SCALER_PATH,
    WINDOW_SIZE,
    WINDOW_STRIDE,
)
from src.features.extractor import compute_soc_percent, extract_window_features

SEED = 42
MIN_SOH = 10.0  # same filter convention as scripts/preprocess.py — drop dead/corrupt cycles
CYCLE_COUNT_NORM = 200.0  # kept consistent with src/core/config.py's NASA value;
# Severson cells run much longer (up to ~2300 cycles) — see note printed at runtime.

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)


def _h5_str(dataset) -> str:
    """Decode a MATLAB char array stored as uint16 codes (policy_readable pattern)."""
    return dataset[()].tobytes()[::2].decode(errors="replace")


def load_batch_file(mat_path: str, batch_label: str) -> dict:
    """
    Parse one Severson .mat v7.3 file into {cell_key: {"cycle_life", "policy",
    "cycles": [(V, I, T, t, cycle_idx), ...], "QDischarge": array}}.

    cell_key = f"{batch_label}c{i}" (e.g. "b1c0") — matches the original
    BuildPkl_BatchN.ipynb naming convention.

    Defensive: a malformed cycle (shape mismatch, NaN) is skipped with a
    warning rather than aborting the whole file — real HDF5 exports of this
    dataset are known to have occasional corrupt entries.
    """
    cells: dict = {}
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
                for j in range(n_cycles):
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
                        [V[:n], I[:n], T[:n], t[:n]], axis=1
                    ).astype(np.float32)
                    if not np.all(np.isfinite(cycle_arr)):
                        print(f"    [{key}] cycle {j}: skipped (NaN/Inf)")
                        continue
                    soh = (
                        float(qd_summary[j]) / LFP_NOMINAL_CAPACITY_AH * 100
                        if j < len(qd_summary)
                        else None
                    )
                    if soh is None or soh < MIN_SOH or soh > 105.0:
                        continue
                    kept_cycles.append((cycle_arr, soh, len(kept_cycles)))

                if kept_cycles:
                    cells[key] = {
                        "cycle_life": cycle_life,
                        "policy": policy,
                        "cycles": kept_cycles,
                    }
            except Exception as exc:
                print(f"  [{key}] skipped entirely (cell-level error: {exc})")
                continue

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
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    print(f"Window size: {WINDOW_SIZE} | Stride: {WINDOW_STRIDE} | LFP nominal capacity: {LFP_NOMINAL_CAPACITY_AH} Ah")

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

    all_cells: dict = {}
    for idx, fname in enumerate(mat_files, start=1):
        batch_label = f"b{idx}"
        cells = load_batch_file(os.path.join(args.data_dir, fname), batch_label)
        all_cells.update(cells)

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
    os.makedirs(os.path.dirname(LFP_SCALER_PATH), exist_ok=True)
    joblib.dump(
        {
            "scaler": scaler,
            "version": LFP_MODEL_VERSION,
            "trained_on": train_ids,
            "features": BASE_FEATURES,
            "chemistry": "LFP",
            "nominal_capacity_ah": LFP_NOMINAL_CAPACITY_AH,
        },
        LFP_SCALER_PATH,
    )
    print(f"Saved scaler -> {LFP_SCALER_PATH}")

    print("\nExtracting windows + spectral features (train)...")
    X_train, X_feat_train_raw, y_train = cycles_to_windows(train_ids, all_cells, scaler)
    print(f"  Train: {len(X_train)} windows")

    feat_scaler = StandardScaler()
    X_feat_train = feat_scaler.fit_transform(X_feat_train_raw).astype(np.float32)
    joblib.dump(
        {"scaler": feat_scaler, "version": LFP_MODEL_VERSION, "n_features": X_feat_train.shape[1]},
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

    print("\nLFP preprocessing complete.")
    print(
        "NOTE: held-out val/test cell IDs were chosen by random shuffle (SEED=42), not "
        "hand-picked for a specific SOH/policy spread (unlike NASA's B0046/B0048 choice). "
        "Re-run with --val-ids/--test-ids once you've reviewed the printed cell list, if you "
        "want a deliberate held-out set (e.g. matching cycle-life extremes)."
    )


if __name__ == "__main__":
    main()
