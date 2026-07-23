"""Tests for GH-84: /prescribe idempotency cache, LLM rate-limit/budget guard,
and observability counters."""
from unittest.mock import patch

from src.core.config import BASE_FEATURES, WINDOW_SIZE
from src.services.prescription import observability

BASE_N = len(BASE_FEATURES)


def make_dummy_readings(n: int = WINDOW_SIZE) -> list[list[float]]:
    return [[3.7 + i * 0.001, 1.5, 25.0, float(i)] for i in range(n)]


def fake_inference_result(soh: float = 68.0) -> dict:
    return {
        "prediction": {
            "soh_percent": soh,
            "health_stage": "End Of Life",
            "degradation_rate_per_cycle": 0.3,
            "soh_trend": "accelerating",
            "rul_cycles_estimate": 5,
        },
        "risk": {
            "risk_level": "Critical",
            "priority": "P1",
            "action_code": "REPLACE_IMMEDIATELY",
            "reasons": [],
        },
        "evidence": {"warnings": []},
        "metadata": {"inference_ms": 12.3},
    }


class FakeEmptyRetriever:
    def retrieve_maintenance(self, q, top_k=3):
        return []

    def retrieve_safety(self, q, top_k=2):
        return []


CLEAN_LLM_OUT = {
    "prescription": "Replace the battery within 24 hours.",
    "action_steps": ["Complete the Lockout/Tagout procedure.", "Replace the unit."],
    "ppe_required": ["Face shield"],
    "provider": "deepseek",
    "chain_attempted": ["deepseek"],
}
BANNED_LLM_OUT = {
    "prescription": "Inspect the pack internals.",
    "action_steps": ["Open the battery casing to inspect the cells.", "Log findings."],
    "ppe_required": [],
    "provider": "deepseek",
    "chain_attempted": ["deepseek"],
}


# ── Cache primitives (pure observability.py, no orchestrator) ──────────────
class TestCache:
    def test_cache_key_deterministic_and_distinguishes_params(self):
        readings = make_dummy_readings()
        k1 = observability.cache_key("B0005", readings, False, False)
        k2 = observability.cache_key("B0005", readings, False, False)
        k3 = observability.cache_key("B0005", readings, True, False)
        k4 = observability.cache_key("B0006", readings, False, False)
        assert k1 == k2
        assert k1 != k3
        assert k1 != k4

    def test_cache_key_distinguishes_ticket_history(self):
        readings = make_dummy_readings()
        k1 = observability.cache_key("B0005", readings, True, False, ["ticket A"])
        k2 = observability.cache_key("B0005", readings, True, False, ["ticket B"])
        k3 = observability.cache_key("B0005", readings, True, False, None)
        k4 = observability.cache_key("B0005", readings, True, False, [])
        assert k1 != k2
        assert k1 != k3
        assert k3 == k4  # None and [] are equivalent (no history)

    def test_set_then_get_returns_value(self):
        key = observability.cache_key("B0005", make_dummy_readings(), False, False)
        assert observability.cache_get(key) is None
        observability.cache_set(key, {"battery_id": "B0005"})
        assert observability.cache_get(key) == {"battery_id": "B0005"}

    def test_expires_after_ttl(self, monkeypatch):
        monkeypatch.setattr(observability, "CACHE_TTL_S", -1.0)  # already expired
        key = observability.cache_key("B0005", make_dummy_readings(), False, False)
        observability.cache_set(key, {"battery_id": "B0005"})
        assert observability.cache_get(key) is None

    def test_lru_evicts_oldest_when_over_maxsize(self, monkeypatch):
        monkeypatch.setattr(observability, "CACHE_MAXSIZE", 2)
        observability.cache_set("k1", {"v": 1})
        observability.cache_set("k2", {"v": 2})
        observability.cache_set("k3", {"v": 3})  # evicts k1 (oldest)
        assert observability.cache_get("k1") is None
        assert observability.cache_get("k2") == {"v": 2}
        assert observability.cache_get("k3") == {"v": 3}


# ── Rate-limit / budget guard ───────────────────────────────────────────────
class TestBudgetAndSemaphore:
    def test_budget_exhausted_denies_further_slots(self, monkeypatch):
        monkeypatch.setenv("LLM_HOURLY_BUDGET", "1")
        assert observability.try_acquire_llm_slot() is True
        assert observability.try_acquire_llm_slot() is False
        observability.release_llm_slot()

    def test_semaphore_denies_beyond_concurrency_limit(self, monkeypatch):
        monkeypatch.setenv("LLM_HOURLY_BUDGET", "100")
        assert observability.try_acquire_llm_slot() is True
        assert observability.try_acquire_llm_slot() is True
        assert observability.try_acquire_llm_slot() is False  # both slots in use
        observability.release_llm_slot()
        assert observability.try_acquire_llm_slot() is True  # slot freed
        observability.release_llm_slot()
        observability.release_llm_slot()

    def test_llm_budget_remaining_reflects_usage(self, monkeypatch):
        monkeypatch.setenv("LLM_HOURLY_BUDGET", "5")
        assert observability.llm_budget_remaining() == 5
        observability.try_acquire_llm_slot()
        assert observability.llm_budget_remaining() == 4
        observability.release_llm_slot()


# ── Counters / /health snapshot ─────────────────────────────────────────────
class TestMetricsSnapshot:
    def test_zero_calls_no_division_error(self):
        snap = observability.metrics_snapshot()
        assert snap["prescribe_total"] == 0
        assert snap["enrich_success_rate"] == 0.0
        assert snap["cache_hit_rate"] == 0.0

    def test_rates_and_counts_after_known_sequence(self):
        observability.record_prescribe()
        observability.record_prescribe()
        observability.record_cache_miss()
        observability.record_cache_hit()
        observability.record_enrich_success()
        observability.record_blocked()
        observability.record_budget_exhausted()
        observability.record_fallback_tiers(["deepseek", "gemini"])

        snap = observability.metrics_snapshot()
        assert snap["prescribe_total"] == 2
        assert snap["enrich_success_rate"] == 0.5
        assert snap["cache_hit_rate"] == 0.5
        assert snap["blocked_total"] == 1
        assert snap["budget_exhausted_total"] == 1
        assert snap["fallback_tier_counts"] == {"deepseek": 1, "gemini": 1}


# ── Integration: caching wired into run_prescription() ──────────────────────
class TestRunPrescriptionCaching:
    def test_identical_calls_within_ttl_hit_cache_once(self):
        from src.services.prescription import orchestrator as prescription

        with (
            patch.object(prescription, "run_inference", return_value=fake_inference_result()),
            patch.object(prescription, "_get_retriever", return_value=FakeEmptyRetriever()),
            patch("src.services.prescription.llm.chain.is_available", return_value=True),
            patch(
                "src.services.prescription.llm.chain.generate_prescription",
                return_value=CLEAN_LLM_OUT,
            ) as mock_gen,
        ):
            readings = make_dummy_readings()
            out1 = prescription.run_prescription(readings, "B0005", enrich=True)
            out2 = prescription.run_prescription(readings, "B0005", enrich=True)

        assert mock_gen.call_count == 1
        assert out1["cached"] is False
        assert out2["cached"] is True
        assert {k: v for k, v in out1.items() if k != "cached"} == {
            k: v for k, v in out2.items() if k != "cached"
        }

    def test_blocked_response_never_cached(self):
        from src.services.prescription import orchestrator as prescription

        with (
            patch.object(prescription, "run_inference", return_value=fake_inference_result()),
            patch.object(prescription, "_get_retriever", return_value=FakeEmptyRetriever()),
            patch("src.services.prescription.llm.chain.is_available", return_value=True),
            patch(
                "src.services.prescription.llm.chain.generate_prescription",
                return_value=BANNED_LLM_OUT,
            ) as mock_gen,
        ):
            readings = make_dummy_readings()
            out1 = prescription.run_prescription(readings, "B0005", enrich=True)
            out2 = prescription.run_prescription(readings, "B0005", enrich=True)

        assert out1["blocked"] is True
        assert out2["blocked"] is True
        assert out1["cached"] is False
        assert out2["cached"] is False  # blocked → never served from cache
        assert mock_gen.call_count == 2  # re-evaluated every time

    def test_different_ticket_history_not_cached_together(self):
        # GH-105: ticket_history is part of the cache key — a changed repair
        # history must never be served the other request's stale response.
        from src.services.prescription import orchestrator as prescription

        with (
            patch.object(prescription, "run_inference", return_value=fake_inference_result()),
            patch.object(prescription, "_get_retriever", return_value=FakeEmptyRetriever()),
            patch("src.services.prescription.llm.chain.is_available", return_value=True),
            patch(
                "src.services.prescription.llm.chain.generate_prescription",
                return_value=CLEAN_LLM_OUT,
            ) as mock_gen,
        ):
            readings = make_dummy_readings()
            out1 = prescription.run_prescription(
                readings, "B0005", enrich=True, ticket_history=["ticket A"]
            )
            out2 = prescription.run_prescription(
                readings, "B0005", enrich=True, ticket_history=["ticket B"]
            )

        assert mock_gen.call_count == 2
        assert out1["cached"] is False
        assert out2["cached"] is False

    def test_budget_exhausted_falls_back_to_rule_based(self, monkeypatch):
        from src.services.prescription import orchestrator as prescription

        monkeypatch.setenv("LLM_HOURLY_BUDGET", "0")
        with (
            patch.object(prescription, "run_inference", return_value=fake_inference_result()),
            patch.object(prescription, "_get_retriever", return_value=FakeEmptyRetriever()),
            patch("src.services.prescription.llm.chain.is_available", return_value=True),
            patch(
                "src.services.prescription.llm.chain.generate_prescription",
                return_value=CLEAN_LLM_OUT,
            ) as mock_gen,
        ):
            out = prescription.run_prescription(
                make_dummy_readings(), "B0005", enrich=True
            )

        assert out["enriched"] is False
        assert out["llm_provider"] == "none"
        mock_gen.assert_not_called()
        snap = observability.metrics_snapshot()
        assert snap["budget_exhausted_total"] == 1
