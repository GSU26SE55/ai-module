"""Tests for the prescription history store (GH-83 — long-term memory)."""
import sys

import pytest

from src.services.prescription.history_store import PrescriptionHistoryStore


@pytest.fixture
def store(tmp_path):
    """Fresh store per test, isolated from the real models/prescription_history/ dir."""
    return PrescriptionHistoryStore(path=str(tmp_path))


def _save(store, battery_id="B0001", action_code="SCHEDULE_MAINTENANCE", risk_level="Medium"):
    return store.save(
        context=f"SOH 78% degrading {battery_id}",
        battery_id=battery_id,
        action_code=action_code,
        risk_level=risk_level,
        llm_provider="deepseek",
        prescription="Schedule inspection within 2 weeks.",
        action_steps=["Inspect terminals.", "Log readings."],
        ppe_required=["Safety glasses (ANSI Z87.1)"],
    )


class TestSaveAndRetrieve:
    def test_save_returns_uuid(self, store):
        prescription_id = _save(store)
        assert isinstance(prescription_id, str) and len(prescription_id) > 0

    def test_pending_case_excluded_from_retrieval(self, store):
        _save(store)
        assert store.retrieve_similar_accepted("SOH 78% degrading", top_k=2) == []

    def test_accepted_case_returned(self, store):
        prescription_id = _save(store)
        assert store.update_feedback(prescription_id, "accepted") is True

        cases = store.retrieve_similar_accepted("SOH 78% degrading B0001", top_k=2)
        assert len(cases) == 1
        assert cases[0]["prescription"] == "Schedule inspection within 2 weeks."
        assert cases[0]["action_steps"] == ["Inspect terminals.", "Log readings."]
        assert cases[0]["battery_id"] == "B0001"

    def test_rejected_case_excluded_from_retrieval(self, store):
        prescription_id = _save(store)
        store.update_feedback(prescription_id, "rejected")
        assert store.retrieve_similar_accepted("SOH 78% degrading", top_k=2) == []

    def test_edited_case_excluded_from_retrieval(self, store):
        # Only "accepted" counts as few-shot-worthy — "edited" still means the
        # LLM output needed correction.
        prescription_id = _save(store)
        store.update_feedback(prescription_id, "edited", edited_steps=["Corrected step."])
        assert store.retrieve_similar_accepted("SOH 78% degrading", top_k=2) == []

    def test_repeated_battery_id_creates_separate_records(self, store):
        first = _save(store)
        second = _save(store)
        assert first != second


class TestUpdateFeedback:
    def test_unknown_id_returns_false(self, store):
        assert store.update_feedback("00000000-0000-0000-0000-000000000000", "accepted") is False

    def test_edited_steps_and_note_persisted(self, store):
        prescription_id = _save(store)
        assert store.update_feedback(
            prescription_id, "edited", edited_steps=["New step."], note="Technician correction"
        ) is True


class TestFifoEviction:
    def test_evicts_oldest_when_over_cap(self, store, monkeypatch):
        import src.services.prescription.history_store as history_store_module

        monkeypatch.setattr(history_store_module, "MAX_RECORDS", 3)

        ids = [_save(store, battery_id=f"B{i:04d}") for i in range(5)]

        remaining = store._collection.get()["ids"]
        assert len(remaining) == 3
        # Oldest two (first saved) must be evicted; newest three survive.
        assert ids[0] not in remaining
        assert ids[1] not in remaining
        assert ids[4] in remaining


class TestGracefulDegradation:
    def test_unavailable_when_chromadb_missing(self, monkeypatch, tmp_path):
        monkeypatch.setitem(sys.modules, "chromadb", None)
        store = PrescriptionHistoryStore(path=str(tmp_path))
        assert store._ready is False
        assert store.save("ctx", "B0001", "MONITOR", "Low", "none", "p", [], []) is None
        assert store.retrieve_similar_accepted("ctx") == []
        assert store.update_feedback("any-id", "accepted") is False
