"""NCKH Figure F7 — effect of aging on raw discharge signals (V, I, T) and
the derived IC curve, one battery, cycles colored by age.

Motivates two §3.2 claims visually: (1) the degradation signature spreads
across the WHOLE discharge curve (justifies full-cycle L=4096 input), and
(2) IC-curve peaks shift/shrink with age (justifies the derived channel).
Counterpart of SambaMixer Fig. 1 (they show V/I/T aging on battery #05).

Battery: B0005 (24°C, longest clean history in the train split).
Color: sequential blue ramp, light = young cycle, dark = old cycle
(dataviz rule: sequential = one hue light->dark for magnitude/age).

Usage: python scripts/nckh/fig_f7_aging_signals.py
Output: logs/nckh/figures/f7_aging_signals.{pdf,svg}
"""

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, Normalize

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.preprocess import load_cycles  # noqa: E402

DATA_DIR = "data/raw/nasa/cleaned_dataset"
OUT_DIR = "logs/nckh/figures"
BATTERY = "B0005"
N_SHOWN = 10  # evenly spaced cycles across the battery's life

FONT = "Arial"
COLOR_GRID = "#e1e0d9"
COLOR_AXIS = "#c3c2b7"
COLOR_TEXT = "#0b0b0b"
COLOR_MUTED_TEXT = "#52514e"

# Sequential blue ramp from the dataviz palette (steps 150 -> 700)
BLUE_RAMP = ["#b7d3f6", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
CMAP = LinearSegmentedColormap.from_list("seq_blue", BLUE_RAMP)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    cycles = load_cycles(DATA_DIR, BATTERY)  # [(array[T,4] V/I/T/t, soh, idx), ...]
    n = len(cycles)
    picks = np.linspace(0, n - 1, N_SHOWN).astype(int)
    norm = Normalize(vmin=0, vmax=n - 1)

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

    fig, axes = plt.subplots(2, 2, figsize=(7.0, 5.4), dpi=300,
                             constrained_layout=True)
    (ax_v, ax_i), (ax_t, ax_ic) = axes
    for ax in axes.flat:
        ax.set_axisbelow(True)

    for idx in picks:
        arr, soh, _ = cycles[idx]
        v, i, temp, t = arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3]
        color = CMAP(norm(idx))
        ax_v.plot(t, v, color=color, lw=0.9)
        ax_i.plot(t, i, color=color, lw=0.9)
        ax_t.plot(t, temp, color=color, lw=0.9)
        # IC panel — voltage-binned dQ/dV (standard battery-literature form,
        # 25 mV bins over the active discharge phase). NOTE: the MODEL receives
        # a per-sample IC variant (clipped [0,20], extractor.py) which saturates
        # at the ceiling during smooth constant-current discharge and is not
        # readable as a curve; the binned form below shows the same underlying
        # quantity the way IC analysis is conventionally presented. State this
        # in the figure caption.
        mask = i < -0.5  # discharge phase only
        v_d, i_d, t_d = v[mask], i[mask], t[mask]
        if len(v_d) < 10:
            continue
        dt_d = np.diff(t_d, prepend=t_d[0]).clip(min=0)
        dq_d = np.abs(i_d) * dt_d  # A·s per sample
        bins = np.arange(2.7, 4.15, 0.025)
        q_per_bin, _ = np.histogram(v_d, bins=bins, weights=dq_d)
        centers = (bins[:-1] + bins[1:]) / 2
        ic_binned = q_per_bin / 0.025  # A·s/V
        nz = ic_binned > 0
        ax_ic.plot(centers[nz], ic_binned[nz], color=color, lw=0.9)

    ax_v.set_xlabel("Time within cycle (s)")
    ax_v.set_ylabel("Voltage (V)")
    ax_v.set_title("(a) Voltage", fontsize=9, loc="left")

    ax_i.set_xlabel("Time within cycle (s)")
    ax_i.set_ylabel("Current (A)")
    ax_i.set_title("(b) Current", fontsize=9, loc="left")

    ax_t.set_xlabel("Time within cycle (s)")
    ax_t.set_ylabel("Temperature (°C)")
    ax_t.set_title("(c) Temperature", fontsize=9, loc="left")

    ax_ic.set_xlabel("Voltage (V)")
    ax_ic.set_ylabel("IC = dQ/dV (A·s/V)")
    ax_ic.set_title("(d) IC curve (dQ/dV)", fontsize=9, loc="left")

    # No in-figure suptitle: IEEE convention puts the description in the
    # LaTeX caption below the figure — cleaner, and avoids crowding the
    # colorbar. Caption text: see docs/nckh/section3-methodology-vi.md §3.2.

    sm = ScalarMappable(norm=norm, cmap=CMAP)
    cbar = fig.colorbar(sm, ax=axes, fraction=0.03, pad=0.02)
    cbar.set_label("Cycle index (light → dark = aging)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    for ext in ("pdf", "svg", "png"):
        path = os.path.join(OUT_DIR, f"f7_aging_signals.{ext}")
        fig.savefig(path, bbox_inches="tight")
        print("Saved", path)


if __name__ == "__main__":
    main()
