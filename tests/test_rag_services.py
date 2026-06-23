"""Tests for RAG service components."""
import pytest
from src.services.safety_gate import apply_safety_gate


class TestSafetyGate:
    def test_p1_always_requires_human(self):
        result = apply_safety_gate("P1", "REPLACE_IMMEDIATELY", [], "Replace battery")
        assert result["human_verification_required"] is True
        assert result["blocked"] is False

    def test_replace_immediately_requires_human(self):
        result = apply_safety_gate("P2", "REPLACE_IMMEDIATELY", [], "Replace")
        assert result["human_verification_required"] is True

    def test_monitor_low_risk_no_human(self):
        result = apply_safety_gate("None", "MONITOR", [], "All normal")
        assert result["human_verification_required"] is False
        assert result["safety_warnings"] == []

    def test_temp_critical_requires_human(self):
        warnings = [{"code": "TEMP_CRITICAL", "severity": "critical"}]
        result = apply_safety_gate("None", "MONITOR", warnings, "Normal battery")
        assert result["human_verification_required"] is True
        assert any("thermal" in w.lower() or "critical" in w.lower()
                   for w in result["safety_warnings"])

    def test_temp_elevated_warning_only(self):
        warnings = [{"code": "TEMP_ELEVATED", "severity": "warning"}]
        result = apply_safety_gate("None", "MONITOR", warnings, "Normal battery")
        # Elevated temp should warn but NOT require human
        assert result["human_verification_required"] is False
        assert len(result["safety_warnings"]) > 0

    def test_electrical_critical_requires_human(self):
        warnings = [{"code": "VOLTAGE_CRITICAL", "severity": "critical"}]
        result = apply_safety_gate("P1", "SCHEDULE_MAINTENANCE", warnings, "Fix voltage")
        assert result["human_verification_required"] is True
        assert any("electrical" in w.lower() or "loto" in w.lower()
                   for w in result["safety_warnings"])

    def test_replace_immediately_adds_escalation(self):
        result = apply_safety_gate("P1", "REPLACE_IMMEDIATELY", [], "Replace now")
        assert any("replacement" in c.lower() or "manager" in c.lower()
                   for c in result["escalation_conditions"])

    def test_never_blocked_stub(self):
        # Safety gate does not block — human review handles blocking
        result = apply_safety_gate("P1", "REPLACE_IMMEDIATELY",
                                   [{"code": "TEMP_CRITICAL", "severity": "critical"}],
                                   "Dangerous")
        assert result["blocked"] is False


class TestRagRetriever:
    def test_retriever_gracefully_handles_missing_chromadb(self):
        """RagRetriever should not crash if chromadb is not installed."""
        from src.services.rag_retriever import RagRetriever
        retriever = RagRetriever()
        # If chromadb not installed, _ready=False and returns empty list
        docs = retriever.retrieve_maintenance("SOH 82%", top_k=3)
        assert isinstance(docs, list)

    def test_retriever_safety_returns_list(self):
        from src.services.rag_retriever import RagRetriever
        retriever = RagRetriever()
        docs = retriever.retrieve_safety("thermal warning", top_k=2)
        assert isinstance(docs, list)
