"""
GH-84 — event-driven hardening for /prescribe: idempotency cache, LLM
rate-limit/budget guard, and in-memory counters exposed via /health.

Single-process, in-memory state (dict/deque/Semaphore) — same "single
instance is enough for capstone scope" caveat already accepted for the cache
in GH-84's acceptance criteria; does not cap/dedup across multiple worker
processes.
"""
import hashlib
import json
import logging
import os
import threading
import time
from collections import OrderedDict, deque

logger = logging.getLogger(__name__)

CACHE_TTL_S = 600.0  # 10 min — same 30-reading window implies unchanged battery state
CACHE_MAXSIZE = 256
LLM_SEMAPHORE_SLOTS = 2
BUDGET_WINDOW_S = 3600.0

_cache_lock = threading.Lock()
_cache: "OrderedDict[str, tuple[float, dict]]" = OrderedDict()

_llm_semaphore = threading.Semaphore(LLM_SEMAPHORE_SLOTS)
_budget_lock = threading.Lock()
_budget_calls: "deque[float]" = deque()

_counters_lock = threading.Lock()
_counters: dict = {
    "prescribe_total": 0,
    "enrich_success_total": 0,
    "cache_hit_total": 0,
    "cache_miss_total": 0,
    "blocked_total": 0,
    "budget_exhausted_total": 0,
    "fallback_tier_counts": {},
}


def cache_key(
    battery_id: str,
    readings: list,
    enrich: bool,
    agentic: bool,
    ticket_history: list | None = None,
    n_series: int = 1,
    chemistry: str | None = None,
    capacity_ah: float | None = None,
) -> str:
    # GH-105: ticket_history is part of the LLM context now (diagnosis
    # statement) — must be in the key, or a changed history within the TTL
    # window would silently serve a stale cached response.
    #
    # GH-67: pack_config must be in the key too. All three of these change the
    # prediction for identical `readings`: n_series divides voltage per-cell,
    # capacity_ah rescales current to the NASA C-rate, and chemistry selects both
    # the voltage warning profile AND (Mức 2) the whole artifact set. Without them
    # a 4S LFP request could be served a cached 1S NMC response.
    payload = json.dumps(
        [battery_id, readings, enrich, agentic, ticket_history or [],
         n_series, chemistry, capacity_ah]
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def cache_get(key: str) -> dict | None:
    now = time.monotonic()
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        expires_at, response = entry
        if expires_at < now:
            del _cache[key]
            return None
        _cache.move_to_end(key)
        return response


def cache_set(key: str, response: dict) -> None:
    now = time.monotonic()
    with _cache_lock:
        _cache[key] = (now + CACHE_TTL_S, response)
        _cache.move_to_end(key)
        while len(_cache) > CACHE_MAXSIZE:
            _cache.popitem(last=False)


def llm_hourly_budget() -> int:
    return int(os.getenv("LLM_HOURLY_BUDGET", "60"))


def _prune_budget_window(now: float) -> None:
    while _budget_calls and now - _budget_calls[0] > BUDGET_WINDOW_S:
        _budget_calls.popleft()


def llm_budget_remaining() -> int:
    now = time.monotonic()
    with _budget_lock:
        _prune_budget_window(now)
        return max(0, llm_hourly_budget() - len(_budget_calls))


def try_acquire_llm_slot() -> bool:
    """
    Reserve 1 concurrency slot + 1 hourly-budget unit for a real LLM call.
    Never blocks/queues — returns False immediately if the budget is
    exhausted or both concurrency slots are in use; caller must degrade to
    the rule-based prescription.
    """
    now = time.monotonic()
    with _budget_lock:
        _prune_budget_window(now)
        if len(_budget_calls) >= llm_hourly_budget():
            record_budget_exhausted()
            return False
        if not _llm_semaphore.acquire(blocking=False):
            return False
        _budget_calls.append(now)
    return True


def release_llm_slot() -> None:
    _llm_semaphore.release()


def record_prescribe() -> None:
    with _counters_lock:
        _counters["prescribe_total"] += 1


def record_enrich_success() -> None:
    with _counters_lock:
        _counters["enrich_success_total"] += 1


def record_cache_hit() -> None:
    with _counters_lock:
        _counters["cache_hit_total"] += 1


def record_cache_miss() -> None:
    with _counters_lock:
        _counters["cache_miss_total"] += 1


def record_blocked() -> None:
    with _counters_lock:
        _counters["blocked_total"] += 1


def record_budget_exhausted() -> None:
    with _counters_lock:
        _counters["budget_exhausted_total"] += 1


def record_fallback_tiers(chain_attempted: list) -> None:
    if not chain_attempted:
        return
    with _counters_lock:
        tiers = _counters["fallback_tier_counts"]
        for name in chain_attempted:
            tiers[name] = tiers.get(name, 0) + 1


def metrics_snapshot() -> dict:
    with _counters_lock:
        total = _counters["prescribe_total"]
        cache_total = _counters["cache_hit_total"] + _counters["cache_miss_total"]
        return {
            "prescribe_total": total,
            "enrich_success_rate": (
                _counters["enrich_success_total"] / total if total else 0.0
            ),
            "cache_hit_rate": (
                _counters["cache_hit_total"] / cache_total if cache_total else 0.0
            ),
            "blocked_total": _counters["blocked_total"],
            "budget_exhausted_total": _counters["budget_exhausted_total"],
            "fallback_tier_counts": dict(_counters["fallback_tier_counts"]),
            "llm_budget_remaining": llm_budget_remaining(),
        }


def reset() -> None:
    """Test-only — clear cache, budget window, semaphore, and counters between
    cases (semaphore is replaced outright — threading.Semaphore has no
    "set value" API, so a leaked/unbalanced acquire in one test can't starve
    the next)."""
    global _llm_semaphore
    with _cache_lock:
        _cache.clear()
    with _budget_lock:
        _budget_calls.clear()
    _llm_semaphore = threading.Semaphore(LLM_SEMAPHORE_SLOTS)
    with _counters_lock:
        _counters.update(
            {
                "prescribe_total": 0,
                "enrich_success_total": 0,
                "cache_hit_total": 0,
                "cache_miss_total": 0,
                "blocked_total": 0,
                "budget_exhausted_total": 0,
                "fallback_tier_counts": {},
            }
        )
