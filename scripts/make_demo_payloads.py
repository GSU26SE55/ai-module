"""
Generate demo request payloads for /predict and /prescribe from real NASA test data.

Extracts raw 30-step windows from B0048 (held-out test battery, 4°C):
  - demo/predict_healthy.json   — first discharge cycle (highest SOH)
  - demo/predict_degraded.json  — last discharge cycle (lowest SOH)
  - demo/prescribe_degraded.json — degraded window + battery history context

Usage: python -X utf8 scripts/make_demo_payloads.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.preprocess import load_cycles  # noqa: E402
from src.core.config import WINDOW_SIZE  # noqa: E402

BATTERY_ID = "B0048"
DATA_DIR = os.path.join("data", "raw", "nasa", "cleaned_dataset")
OUT_DIR = "demo"


def middle_window(cycle):
    """30-step slice from the middle of the discharge cycle (representative region)."""
    start = max(0, (len(cycle) - WINDOW_SIZE) // 2)
    return cycle[start : start + WINDOW_SIZE]


def main() -> None:
    cycles = load_cycles(DATA_DIR, BATTERY_ID)
    print(f"{BATTERY_ID}: {len(cycles)} discharge cycles, "
          f"SOH {cycles[0][1]:.1f}% (first) -> {cycles[-1][1]:.1f}% (last)")

    os.makedirs(OUT_DIR, exist_ok=True)

    for name, (cycle, soh) in [("healthy", cycles[0]), ("degraded", cycles[-1])]:
        window = middle_window(cycle)
        payload = {
            "battery_id": BATTERY_ID,
            "readings": [[round(float(v), 4) for v in row] for row in window],
        }
        path = os.path.join(OUT_DIR, f"predict_{name}.json")
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"  {path}  (true SOH: {soh:.1f}%)")

    # /prescribe payload: degraded window + maintenance-history context
    degraded_cycle, _ = cycles[-1]
    prescribe_payload = {
        "battery_id": BATTERY_ID,
        "readings": [[round(float(v), 4) for v in row] for row in middle_window(degraded_cycle)],
        "age_cycles": len(cycles),
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
