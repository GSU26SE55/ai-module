"""
Generate demo request payloads for /predict and /prescribe from real NASA test data.

Extracts raw 30-step windows (B0048 held-out test battery, 4°C; B0005 train battery):
  - demo/predict_healthy.json       — B0048 first discharge cycle (highest SOH)
  - demo/predict_degraded.json      — B0048 last discharge cycle (lowest SOH)
  - demo/predict_healthy_b0005.json — B0005 first discharge cycle (highest SOH)
  - demo/prescribe_degraded.json    — B0048 degraded window + battery history context

Usage: python -X utf8 scripts/make_demo_payloads.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.preprocess import load_cycles  # noqa: E402
from src.core.config import WINDOW_SIZE  # noqa: E402

DATA_DIR = os.path.join("data", "raw", "nasa", "cleaned_dataset")
OUT_DIR = "demo"


def middle_window(cycle):
    """30-step slice from the middle of the discharge cycle (representative region)."""
    start = max(0, (len(cycle) - WINDOW_SIZE) // 2)
    return cycle[start : start + WINDOW_SIZE]


def write_predict_payload(battery_id, cycle, soh, name):
    payload = {
        "battery_id": battery_id,
        "readings": [
            [round(float(v), 4) for v in row] for row in middle_window(cycle)
        ],
    }
    path = os.path.join(OUT_DIR, f"predict_{name}.json")
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"  {path}  (true SOH: {soh:.1f}%)")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    cycles_48 = load_cycles(DATA_DIR, "B0048")
    print(
        f"B0048: {len(cycles_48)} discharge cycles, "
        f"SOH {cycles_48[0][1]:.1f}% (first) -> {cycles_48[-1][1]:.1f}% (last)"
    )
    healthy_cycle, healthy_soh, _ = cycles_48[0]
    degraded_cycle, degraded_soh, _ = cycles_48[-1]
    write_predict_payload("B0048", healthy_cycle, healthy_soh, "healthy")
    write_predict_payload("B0048", degraded_cycle, degraded_soh, "degraded")

    cycles_05 = load_cycles(DATA_DIR, "B0005")
    print(f"B0005: {len(cycles_05)} discharge cycles, SOH {cycles_05[0][1]:.1f}% (first)")
    b0005_cycle, b0005_soh, _ = cycles_05[0]
    write_predict_payload("B0005", b0005_cycle, b0005_soh, "healthy_b0005")

    # /prescribe payload: B0048 degraded window + maintenance-history context
    prescribe_payload = {
        "battery_id": "B0048",
        "readings": [
            [round(float(v), 4) for v in row] for row in middle_window(degraded_cycle)
        ],
        "age_cycles": len(cycles_48),
        "last_maintenance_date": "2026-05-15",
        "ticket_history": ["P2 - voltage sag detected 2026-06-10"],
        "enrich": False,
    }
    path = os.path.join(OUT_DIR, "prescribe_degraded.json")
    with open(path, "w") as f:
        json.dump(prescribe_payload, f, indent=2)
    print(f"  {path}  (enrich=false — set true for RAG+LLM)")


if __name__ == "__main__":
    main()
