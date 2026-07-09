"""
GH-95: per-battery SOH history for the causal degradation-rate anomaly rule.

/predict is otherwise stateless (one window per request). The 57-dim spectral
IsolationForest score doesn't correlate with rapid-degradation labels (GH-70:
F1 0.30-0.45) because a single window can't see how a battery's SOH is
trending over its own recent cycles. A small in-memory per-battery history
(keyed by battery_id, already sent in every request — no BE contract change)
closes that gap: causal_rate() compares the current prediction against the
battery's own SOH a few cycles back.

Limitations (accepted for capstone scope, NOT safe to ignore in a larger
deployment):
- In-memory, single-process — state is lost on restart and NOT shared across
  multiple replicas behind a load balancer (each replica would see a partial,
  inconsistent history for the same battery).
- Unbounded number of DISTINCT battery_id keys (no eviction across batteries,
  only per-battery history is bounded) — acceptable at capstone fleet size.
"""

import threading
from collections import deque

_MAXLEN = 8  # keep last N (cycle, soh) points per battery — covers CAUSAL_RATE_K up to 8
_lock = threading.RLock()
_history: dict[str, deque[tuple[float, float]]] = {}


def record(battery_id: str | None, cycle_count: float | None, soh: float) -> None:
    """Append this window's (cycle_count, soh) to battery_id's history.

    No-op when battery_id or cycle_count is missing (nothing useful to key/order by).
    """
    if not battery_id or cycle_count is None:
        return
    with _lock:
        buf = _history.setdefault(battery_id, deque(maxlen=_MAXLEN))
        buf.append((float(cycle_count), float(soh)))


def causal_rate(
    battery_id: str | None, current_cycle: float | None, current_soh: float, k: int
) -> float | None:
    """%SOH lost per cycle, comparing THIS request's prediction to ~k cycles earlier.

    Causal by construction: `current_cycle`/`current_soh` are this in-flight
    request's own values (not yet `record()`-ed — call this BEFORE record()),
    compared against a point already recorded from a PRIOR request. Only ever
    looks at cycles strictly before the current one, unlike GH-70's offline
    label which uses a centered window (looks at future cycles too, only
    possible for post-hoc evaluation).

    Args:
        battery_id:    request's battery id, or None/empty (-> None).
        current_cycle: this request's cycle number, or None (-> None, can't
                       compute a rate without knowing where "now" is).
        current_soh:   this request's predicted SOH%.
        k:             how many recorded points back to compare against
                       (clamped to however much history exists).

    Returns:
        None when there's no battery_id/current_cycle, no prior history yet
        (cold start), or the cycle numbers aren't strictly increasing
        (retry/out-of-order — division would be meaningless). Otherwise
        %SOH/cycle, positive = degrading.
    """
    if not battery_id or current_cycle is None:
        return None
    with _lock:
        buf = _history.get(battery_id)
        if not buf:
            return None
        idx = max(0, len(buf) - k)
        cycle_then, soh_then = buf[idx]
    dc = current_cycle - cycle_then
    if dc <= 0:
        return None
    return (soh_then - current_soh) / dc
