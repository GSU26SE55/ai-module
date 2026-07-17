"""NCKH Figure F4 — component ablation bar chart (Table 3), long model v2.2.

Data: hardcoded from logs/nckh/ablation/{pooling_last,d_state16,no_weighted_loss}.json
and the v2.2 checkpoint headline (test_mae=1.5232) — 4 numbers, no need to
re-parse JSON for a one-off figure; source values cross-checked against
docs/nckh/section4-experiments-vi.md Table 3.

Palette: dataviz skill categorical set — baseline in muted ink, positive
ablation delta in categorical red-ish (worse than baseline), negative delta
in a distinct hue (better than baseline) — direction-coded, not just series
identity, since Table 3's story IS the sign of each delta.

Usage: python scripts/nckh/fig_f4_ablation.py
Output: logs/nckh/figures/f4_ablation.{pdf,svg}
"""

import os

import matplotlib.pyplot as plt

OUT_DIR = "logs/nckh/figures"
FONT = "Arial"

# (label, MAE%, is_baseline)
ROWS = [
    ("Full model\n(v2.2)", 1.5232, True),
    ("Attention pooling\n→ last token", 1.9298, False),
    ("d_state\n32 → 16", 1.2403, False),
    ("No EOL-\nweighted loss", 1.3188, False),
]

COLOR_BASELINE = "#898781"  # muted ink
COLOR_WORSE = "#e34948"     # slot 6 red — Δ MAE positive (worse)
COLOR_BETTER = "#1baf7a"    # slot 2 aqua — Δ MAE negative (better)
COLOR_GRID = "#e1e0d9"
COLOR_AXIS = "#c3c2b7"
COLOR_TEXT = "#0b0b0b"
COLOR_MUTED_TEXT = "#52514e"


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

    baseline_mae = ROWS[0][1]
    labels = [r[0] for r in ROWS]
    maes = [r[1] for r in ROWS]
    colors = []
    for label, mae, is_baseline in ROWS:
        if is_baseline:
            colors.append(COLOR_BASELINE)
        elif mae > baseline_mae:
            colors.append(COLOR_WORSE)
        else:
            colors.append(COLOR_BETTER)

    fig, ax = plt.subplots(figsize=(5.2, 3.2), dpi=300)
    ax.set_axisbelow(True)
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)

    x = range(len(ROWS))
    bars = ax.bar(x, maes, color=colors, width=0.6, zorder=3)

    ax.axhline(baseline_mae, color=COLOR_MUTED_TEXT, lw=0.9, ls="--", zorder=2)

    for i, (bar, (label, mae, is_baseline)) in enumerate(zip(bars, ROWS)):
        delta = mae - baseline_mae
        delta_str = "" if is_baseline else f"\n({delta:+.2f})"
        ax.text(bar.get_x() + bar.get_width() / 2, mae + 0.05,
                 f"{mae:.2f}%{delta_str}", ha="center", va="bottom",
                 fontsize=8, color=COLOR_TEXT)

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("MAE on B0048 (%)")
    ax.set_title(
        "Component ablation — long model v2.2 (Table 3)",
        fontsize=10, loc="left",
    )
    ax.set_ylim(0, max(maes) * 1.22)

    # Legend explaining color = direction of Δ, not identity
    from matplotlib.patches import Patch
    handles = [
        Patch(facecolor=COLOR_BASELINE, label="Full model (baseline)"),
        Patch(facecolor=COLOR_WORSE, label="ΔMAE > 0 (worse)"),
        Patch(facecolor=COLOR_BETTER, label="ΔMAE < 0 (better)"),
    ]
    ax.legend(handles=handles, frameon=False, fontsize=7.5, loc="upper left")

    fig.tight_layout()
    for ext in ("pdf", "svg", "png"):
        path = os.path.join(OUT_DIR, f"f4_ablation.{ext}")
        fig.savefig(path, bbox_inches="tight")
        print("Saved", path)


if __name__ == "__main__":
    main()
