"""
GH-95: compute RATE_THRESHOLD for the causal degradation-rate anomaly rule.

Same methodology as GH-70 (GVHD-approved): train p90 of the locally smoothed
per-cycle fade rate. Re-run here (not imported from eval_anomaly.py's cached
number) because the train split changed under GH-88 (B0047 val->train) —
this recomputes the threshold on the CURRENT split so it stays traceable and
reproducible. Not a model artifact — just prints the value to paste into
src/core/config.py (RATE_THRESHOLD), same convention as other data-derived
constants there (DEGRADATION_RATE, CYCLE_COUNT_NORM).

Usage:
    python scripts/compute_rate_threshold.py
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.eval_anomaly import RATE_PERCENTILE, collect_split, local_fade_rate, smooth_soh  # noqa: E402
from scripts.preprocess import TRAIN_IDS  # noqa: E402

SEED = 42
np.random.seed(SEED)


def main() -> None:
    data_dir = "data/raw/nasa/cleaned_dataset"
    if not os.path.exists(os.path.join(data_dir, "metadata.csv")):
        sys.exit(f"Raw dataset not found at '{data_dir}'.")

    train_batteries = collect_split(data_dir, TRAIN_IDS)
    train_rates = np.concatenate(
        [local_fade_rate(smooth_soh(b["soh"])) for b in train_batteries]
    )
    rate_thr = float(np.percentile(train_rates, RATE_PERCENTILE))
    print(f"RATE_THRESHOLD = {rate_thr:.4f}  # %SOH/cycle, train p{RATE_PERCENTILE}, seed {SEED}")
    print(f"(computed on TRAIN_IDS, {len(TRAIN_IDS)} batteries — current split post GH-88)")


if __name__ == "__main__":
    main()
