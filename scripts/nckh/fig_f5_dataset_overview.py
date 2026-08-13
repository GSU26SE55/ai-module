"""NCKH Figure F5 — dataset overview: SOH degradation curves for all 26
batteries in the official paper protocol (OLD split 23/2/1, B0047 in VAL —
NOT the current dev-branch split from GH-88 where B0047 is in TRAIN).

Uses scripts.preprocess.load_cycles() — the SAME production data-loading
path used for every reported number in the paper (MIN_SOH=10.0 filter drops
the isolated capacity≈0 sensor-glitch rows present in the raw NASA metadata;
see docs/nckh/section3-methodology-vi.md).

Palette: validated categorical set from the dataviz skill
(references/palette.md) — slot 6 red (test), slot 2 aqua (val), muted ink
(train, recessive since it is the majority/context group).

Usage: python scripts/nckh/fig_f5_dataset_overview.py
Output: logs/nckh/figures/f5_dataset_overview.{pdf,svg}
"""

import os
import sys

import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.preprocess import load_cycles  # noqa: E402

DATA_DIR = "data/raw/nasa/cleaned_dataset"
OUT_DIR = "logs/nckh/figures"

# Official paper protocol (OLD split 23/2/1) — B0047 in VAL, not TRAIN.
# Current scripts/preprocess.py (dev branch, post GH-88) has B0047 in TRAIN
# (24/1/1) for the production v1.6+ model; that split is intentionally NOT
# used here, see docs/nckh/section3-methodology-vi.md protocol note.
TRAIN_IDS = [
    "B0005", "B0006", "B0007", "B0018",
    "B0025", "B0026", "B0027", "B0028",
    "B0029", "B0030", "B0031", "B0032",
    "B0042", "B0043", "B0044",
    "B0033", "B0034",
    "B0041", "B0045", "B0053", "B0054", "B0055", "B0056",
]
VAL_IDS = ["B0046", "B0047"]
TEST_IDS = ["B0048"]

FOUR_C_IDS = {"B0041", "B0045", "B0053", "B0054", "B0055", "B0056", "B0046", "B0047", "B0048"}

# dataviz skill categorical palette (light mode, fixed slot order)
COLOR_TRAIN = "#898781"  # muted ink — recessive, majority/context group
COLOR_VAL = "#1baf7a"    # slot 2 aqua
COLOR_TEST = "#e34948"   # slot 6 red — headline pin, strongest ink
COLOR_GRID = "#e1e0d9"
COLOR_AXIS = "#c3c2b7"
COLOR_TEXT = "#0b0b0b"
COLOR_MUTED_TEXT = "#52514e"

FONT = "Arial"  # DejaVu Sans mis-renders Vietnamese combining diacritics


def battery_soh_curve(battery_id: str):
    cycles = load_cycles(DATA_DIR, battery_id)  # [(raw_array, soh, cycle_idx), ...]
    xs = [c[2] for c in cycles]
    ys = [c[1] for c in cycles]
    return xs, ys


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    plt.rcParams.update({
        "font.family": FONT,
        "font.size": 9,
        "axes.edgecolor": COLOR_AXIS,
        "axes.labelcolor": COLOR_TEXT,
        "text.color": COLOR_TEXT,
        "xtick.color": COLOR_MUTED_TEXT,
        "ytick.color": COLOR_MUTED_TEXT,
        "axes.grid": True,
        "grid.color": COLOR_GRID,
        "grid.linewidth": 0.6,
        "svg.fonttype": "none",
    })

    fig, ax = plt.subplots(figsize=(7.0, 3.4), dpi=300)
    ax.set_axisbelow(True)

    def plot_group(ids, color, lw, zorder, alpha, label_once):
        labeled = False
        for bid in ids:
            xs, ys = battery_soh_curve(bid)
            if not xs:
                continue
            is_4c = bid in FOUR_C_IDS
            ls = "--" if is_4c and color == COLOR_TRAIN else "-"
            ax.plot(
                xs, ys,
                color=color, lw=lw, alpha=alpha, linestyle=ls,
                zorder=zorder,
                label=label_once if not labeled else None,
            )
            labeled = True

    plot_group(TRAIN_IDS, COLOR_TRAIN, lw=1.0, zorder=1, alpha=0.55,
               label_once="Train (23 batteries) — dashed: 4°C group")
    plot_group(VAL_IDS, COLOR_VAL, lw=1.8, zorder=2, alpha=0.95,
               label_once="Val — B0046, B0047 (4°C)")
    plot_group(TEST_IDS, COLOR_TEST, lw=2.4, zorder=3, alpha=1.0,
               label_once="Test — B0048 (4°C, held out)")

    ax.axhline(80, color=COLOR_MUTED_TEXT, lw=0.8, ls=":", zorder=0)
    ax.text(0.995, 81, "EOL 80%", transform=ax.get_yaxis_transform(),
            fontsize=7, color=COLOR_MUTED_TEXT, ha="right", va="bottom")

    ax.set_xlabel("Discharge cycle")
    ax.set_ylabel("SOH (%)")
    ax.set_title(
        "SOH degradation of the 26 NASA batteries, colored by split",
        fontsize=10, color=COLOR_TEXT, loc="left",
    )
    ax.legend(frameon=False, fontsize=7.5, loc="lower left")
    ax.set_ylim(0, 105)

    fig.tight_layout()
    for ext in ("pdf", "svg", "png"):
        path = os.path.join(OUT_DIR, f"f5_dataset_overview.{ext}")
        fig.savefig(path, bbox_inches="tight")
        print("Saved", path)


if __name__ == "__main__":
    main()
