"""
Anomaly evaluation for the NCKH paper (GH-70): Table 5 (Precision/Recall/F1)
and Figure F6 (anomaly score histogram with the -0.1/-0.3 mapping thresholds).

NASA dataset has no fault annotations, so ground truth is a proxy label:
  - rate (primary, GVHD-approved 2026-07-04): a cycle is anomalous when its
    locally smoothed degradation rate exceeds the RATE_PERCENTILE-th percentile
    of the training-set rate distribution — aligned with the IsolationForest
    contamination prior of 0.1.
  - eol (secondary, original issue proposal): SOH < 80%. Kept for honest
    comparison — degenerate on the 4°C val/test cells (~98% positive).

IsolationForest is refit here on the same train features / hyperparameters /
seed as scripts/train.py, so it is equivalent to the shipped artifact.
Threshold tuning (when F1 < TARGET_F1) uses ONLY the val split.

Usage:
    python scripts/eval_anomaly.py \
        --data-dir data/raw/nasa/cleaned_dataset \
        --processed-dir data/processed \
        --output-dir logs/nckh/anomaly
"""

import argparse
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_recall_fscore_support

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.preprocess import TEST_IDS, TRAIN_IDS, VAL_IDS, load_cycles
from src.core.config import WINDOW_SIZE, WINDOW_STRIDE

SEED = 42
EOL_SOH = 80.0
RATE_PERCENTILE = 90  # aligns with IsolationForest contamination=0.1
SMOOTH_HALF_SPAN = 2  # rolling median window = 2*2+1 = 5 cycles
RATE_HALF_SPAN = 2  # central difference over +/-2 cycles
SCORE_RULES = {"score<=-0.1": -0.1, "score<=-0.3": -0.3}
TARGET_F1 = 0.80
DEGENERATE_BALANCE = 0.90  # stop if one class exceeds this share on val/test

np.random.seed(SEED)


# ── Labeling (pure functions — unit-tested) ──────────────────────────────────


def smooth_soh(soh: np.ndarray, half_span: int = SMOOTH_HALF_SPAN) -> np.ndarray:
    """Rolling median over 2*half_span+1 cycles (shrinks at the edges)."""
    n = len(soh)
    return np.array(
        [np.median(soh[max(0, i - half_span) : i + half_span + 1]) for i in range(n)]
    )


def local_fade_rate(
    soh_smooth: np.ndarray, half_span: int = RATE_HALF_SPAN
) -> np.ndarray:
    """%SOH lost per cycle: central difference, one-sided at the edges."""
    n = len(soh_smooth)
    rates = np.zeros(n)
    for i in range(n):
        lo, hi = max(0, i - half_span), min(n - 1, i + half_span)
        rates[i] = -(soh_smooth[hi] - soh_smooth[lo]) / max(hi - lo, 1)
    return rates


def rate_labels(soh_per_cycle: np.ndarray, threshold: float) -> np.ndarray:
    """Anomalous = locally smoothed fade rate above `threshold` (%SOH/cycle)."""
    return local_fade_rate(smooth_soh(soh_per_cycle)) > threshold


def eol_labels(soh_per_cycle: np.ndarray) -> np.ndarray:
    """Anomalous = below the 80% SOH end-of-life threshold."""
    return soh_per_cycle < EOL_SOH


def expand_to_windows(per_cycle: np.ndarray, n_win_per_cycle: np.ndarray) -> np.ndarray:
    """Repeat each cycle's value once per window sliced from that cycle."""
    return np.repeat(per_cycle, n_win_per_cycle)


def pick_threshold(scores_val: np.ndarray, y_val: np.ndarray) -> tuple[float, float]:
    """Best-F1 score threshold selected on the val split ONLY."""
    candidates = np.unique(np.quantile(scores_val, np.linspace(0.01, 0.99, 99)))
    best_thr, best_f1 = candidates[0], -1.0
    for thr in candidates:
        f1 = evaluate(y_val, scores_val <= thr)["f1"]
        if f1 > best_f1:
            best_thr, best_f1 = float(thr), f1
    return best_thr, best_f1


def evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    p, r, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    return {
        "precision": round(float(p), 4),
        "recall": round(float(r), 4),
        "f1": round(float(f1), 4),
    }


# ── Data assembly ─────────────────────────────────────────────────────────────


def collect_split(data_dir: str, battery_ids: list[str]) -> list[dict]:
    """Per battery: SOH per kept cycle + windows per cycle (replays preprocess.py)."""
    batteries = []
    for bid in battery_ids:
        cycles = load_cycles(data_dir, bid)
        batteries.append(
            {
                "id": bid,
                "soh": np.array([soh for _, soh, _ in cycles]),
                "n_win": np.array(
                    [(len(c) - WINDOW_SIZE) // WINDOW_STRIDE + 1 for c, _, _ in cycles]
                ),
            }
        )
    return batteries


def split_window_labels(
    batteries: list[dict], label_def: str, rate_thr: float
) -> np.ndarray:
    per_battery = []
    for b in batteries:
        cyc = (
            rate_labels(b["soh"], rate_thr)
            if label_def == "rate"
            else eol_labels(b["soh"])
        )
        per_battery.append(expand_to_windows(cyc, b["n_win"]))
    return np.concatenate(per_battery)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/raw/nasa/cleaned_dataset")
    parser.add_argument("--processed-dir", default="data/processed")
    parser.add_argument("--output-dir", default="logs/nckh/anomaly")
    args = parser.parse_args()

    if not os.path.exists(os.path.join(args.data_dir, "metadata.csv")):
        sys.exit(
            f"Raw dataset not found at '{args.data_dir}' — download NASA cleaned_dataset first."
        )
    for split in ("train", "val", "test"):
        if not os.path.exists(os.path.join(args.processed_dir, f"{split}.pt")):
            sys.exit(
                f"Missing '{args.processed_dir}/{split}.pt' — run scripts/preprocess.py first."
            )
    os.makedirs(args.output_dir, exist_ok=True)

    # Features from the exact tensors the shipped model was trained on
    feats, splits_meta = {}, {}
    split_ids = {"train": TRAIN_IDS, "val": VAL_IDS, "test": TEST_IDS}
    for split, ids in split_ids.items():
        data = torch.load(
            os.path.join(args.processed_dir, f"{split}.pt"), weights_only=False
        )
        feats[split] = data["X_feat"].numpy()
        splits_meta[split] = collect_split(args.data_dir, ids)
        n_replayed = int(sum(b["n_win"].sum() for b in splits_meta[split]))
        assert n_replayed == len(feats[split]), (
            f"{split}: replayed {n_replayed} windows but X_feat has {len(feats[split])} — "
            "labels would silently misalign; re-run scripts/preprocess.py."
        )

    # Rate threshold from the TRAIN distribution only (no val/test leakage)
    train_rates = np.concatenate(
        [local_fade_rate(smooth_soh(b["soh"])) for b in splits_meta["train"]]
    )
    rate_thr = float(np.percentile(train_rates, RATE_PERCENTILE))
    print(f"Rate threshold (train p{RATE_PERCENTILE}): {rate_thr:.4f} %SOH/cycle")

    # Same fit as scripts/train.py → equivalent to the shipped isolation_forest pkl
    iso = IsolationForest(contamination=0.1, n_estimators=100, random_state=SEED)
    iso.fit(feats["train"])
    scores = {s: iso.decision_function(feats[s]) for s in ("val", "test")}
    hard_pred = {s: iso.predict(feats[s]) == -1 for s in ("val", "test")}

    results = {"seed": SEED, "rate_threshold": rate_thr, "labels": {}}
    for label_def in ("rate", "eol"):
        entry = {}
        for split in ("val", "test"):
            y = split_window_labels(splits_meta[split], label_def, rate_thr)
            pos_rate = float(y.mean())
            rules = {
                name: evaluate(y, scores[split] <= thr)
                for name, thr in SCORE_RULES.items()
            }
            rules["predict==-1"] = evaluate(y, hard_pred[split])
            entry[split] = {
                "n_windows": len(y),
                "pos_rate": round(pos_rate, 4),
                "rules": rules,
            }
            if max(pos_rate, 1 - pos_rate) > DEGENERATE_BALANCE:
                print(
                    f"WARNING {label_def}/{split}: {max(pos_rate, 1 - pos_rate):.1%} single-class "
                    "- metrics degenerate, escalate to GVHD before using in the paper."
                )
        # Threshold tuning on VAL ONLY when no default rule reaches the target
        if max(r["f1"] for r in entry["val"]["rules"].values()) < TARGET_F1:
            y_val = split_window_labels(splits_meta["val"], label_def, rate_thr)
            y_test = split_window_labels(splits_meta["test"], label_def, rate_thr)
            thr, val_f1 = pick_threshold(scores["val"], y_val)
            entry["tuned"] = {
                "threshold": round(thr, 4),
                "val": evaluate(y_val, scores["val"] <= thr),
                "test": evaluate(y_test, scores["test"] <= thr),
            }
            print(
                f"{label_def}: default F1 < {TARGET_F1} -> tuned on val: thr={thr:.4f}, F1={val_f1:.4f}"
            )
        results["labels"][label_def] = entry

    # Figure F6 — score histogram with the documented mapping thresholds
    fig, ax = plt.subplots(figsize=(5, 3))
    bins = np.linspace(
        min(scores["val"].min(), scores["test"].min()),
        max(scores["val"].max(), scores["test"].max()),
        60,
    )
    ax.hist(
        scores["val"], bins=bins, alpha=0.6, label="Val (B0046/47)", color="#0072B2"
    )
    ax.hist(scores["test"], bins=bins, alpha=0.6, label="Test (B0048)", color="#E69F00")
    for thr, style in ((-0.1, "--"), (-0.3, ":")):
        ax.axvline(
            thr,
            color="#D55E00",
            linestyle=style,
            linewidth=1.2,
            label=f"threshold {thr}",
        )
    ax.set_xlabel("IsolationForest anomaly score", fontsize=9)
    ax.set_ylabel("Window count", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=8)
    fig.tight_layout()
    for ext in ("pdf", "svg"):
        fig.savefig(os.path.join(args.output_dir, f"figure_f6.{ext}"))
    plt.close(fig)

    with open(
        os.path.join(args.output_dir, "results.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(results, f, indent=2)

    # Table 5 — markdown, paste-ready for the paper
    lines = [
        "# Table 5 — Anomaly detection (IsolationForest, contamination=0.1, seed 42)",
        "",
        f"Rate label: fade rate > train p{RATE_PERCENTILE} = {rate_thr:.4f} %SOH/cycle "
        "(rolling-median smoothed, central difference). EOL label: SOH < 80%.",
        "",
        "| Label def | Split | Rule | Precision | Recall | F1 | Positive rate |",
        "|-----------|-------|------|-----------|--------|----|---------------|",
    ]
    for label_def, entry in results["labels"].items():
        for split in ("val", "test"):
            for rule, m in entry[split]["rules"].items():
                lines.append(
                    f"| {label_def} | {split} | {rule} | {m['precision']:.3f} "
                    f"| {m['recall']:.3f} | {m['f1']:.3f} | {entry[split]['pos_rate']:.1%} |"
                )
        if "tuned" in entry:
            t = entry["tuned"]
            for split in ("val", "test"):
                m = t[split]
                lines.append(
                    f"| {label_def} | {split} | tuned score<={t['threshold']} (val-selected) "
                    f"| {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} "
                    f"| {entry[split]['pos_rate']:.1%} |"
                )
    lines += [
        "",
        "**Section 3.5 label definition (draft):** Since the NASA dataset lacks fault",
        "annotations, we define a proxy anomaly label: a cycle is anomalous if its locally",
        "smoothed degradation rate exceeds the 90th percentile of the training-set rate",
        "distribution — aligned with the Isolation Forest contamination prior of 0.1.",
        "An absolute SOH threshold (80% EOL) is reported for comparison but is degenerate",
        "on the low-temperature val/test cells (~98% of windows below 80% SOH).",
        "",
        "**Limitations (draft):** Both labels are proxies derived from capacity fade, not",
        "real fault annotations; results measure separation of degradation regimes rather",
        "than field sensor-fault detection.",
    ]
    with open(os.path.join(args.output_dir, "table5.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nSaved results.json, table5.md, figure_f6.pdf/svg -> {args.output_dir}")


if __name__ == "__main__":
    main()
