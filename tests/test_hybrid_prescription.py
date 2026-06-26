"""Tests for the hybrid prescription layer (rule engine + routing)."""
import os
from unittest import mock

from src.services.rules_prescription import build_rule_prescription
from src.services.prescription import _should_enrich, _merge_llm_onto_rule
from src.services._llm_client import call_structured_prescription


class TestRulePrescription:
    def test_eol_p1_thermal_escalates_steps_and_ppe(self):
        out = build_rule_prescription(
            {"soh_percent": 72.0, "health_stage": "End Of Life"},
            {"risk_level": "Critical", "priority": "P1",
             "action_code": "REPLACE_IMMEDIATELY", "reasons": ["SOH 72% below EOL"]},
            [{"code": "BATTERY_EOL", "severity": "critical"},
             {"code": "TEMP_CRITICAL", "severity": "critical"}],
        )
        assert out["source"] == "rule"
        assert any("lockout" in s.lower() for s in out["action_steps"])
        assert any("thermal runaway" in s.lower() for s in out["action_steps"])
        # thermal-critical PPE escalation
        assert "Face shield" in out["ppe_required"]

    def test_electrical_critical_adds_arc_flash_ppe(self):
        out = build_rule_prescription(
            {"soh_percent": 88.0, "health_stage": "Degrading"},
            {"risk_level": "Medium", "priority": "P3",
             "action_code": "SCHEDULE_MAINTENANCE", "reasons": []},
            [{"code": "VOLTAGE_CRITICAL", "severity": "critical"}],
        )
        assert "Arc-flash rated gloves" in out["ppe_required"]

    def test_monitor_has_no_ppe(self):
        out = build_rule_prescription(
            {"soh_percent": 96.0, "health_stage": "Healthy"},
            {"risk_level": "Low", "priority": "None",
             "action_code": "MONITOR", "reasons": []},
            [],
        )
        assert out["ppe_required"] == []
        assert "monitoring" in out["prescription"].lower()

    def test_unknown_action_code_falls_back_to_monitor(self):
        out = build_rule_prescription(
            {"soh_percent": 90.0}, {"action_code": "WAT", "reasons": []}, []
        )
        assert "monitoring" in out["prescription"].lower()

    def test_action_steps_are_deduped(self):
        out = build_rule_prescription(
            {"soh_percent": 70.0}, {"action_code": "REPLACE_IMMEDIATELY", "reasons": []},
            [{"code": "TEMP_CRITICAL"}, {"code": "TEMP_CRITICAL"}],
        )
        assert len(out["action_steps"]) == len(set(out["action_steps"]))


class TestHybridRouting:
    def test_p1_not_enriched_by_default(self):
        assert _should_enrich("P1", detail=False) is False

    def test_non_critical_enriched_by_default(self):
        assert _should_enrich("P2", detail=False) is True
        assert _should_enrich("P3", detail=False) is True
        assert _should_enrich("None", detail=False) is True

    def test_detail_forces_enrich_even_for_p1(self):
        assert _should_enrich("P1", detail=True) is True

    def test_merge_keeps_rule_baseline_and_appends_llm(self):
        rule = {"prescription": "RULE", "action_steps": ["A", "B"],
                "ppe_required": ["gloves"], "source": "rule"}
        llm = {"prescription": "LLM", "action_steps": ["B", "C"],
               "ppe_required": ["gloves", "goggles"]}
        merged = _merge_llm_onto_rule(rule, llm)
        assert merged["prescription"] == "LLM"
        assert merged["action_steps"] == ["A", "B", "C"]   # rule first, deduped
        assert merged["ppe_required"] == ["gloves", "goggles"]
        assert merged["source"] == "llm"

    def test_merge_falls_back_to_rule_text_when_llm_empty(self):
        rule = {"prescription": "RULE", "action_steps": ["A"],
                "ppe_required": [], "source": "rule"}
        merged = _merge_llm_onto_rule(rule, {"prescription": "", "action_steps": []})
        assert merged["prescription"] == "RULE"


class TestLlmClientFallback:
    _RULE = {"prescription": "RULE", "action_steps": ["A"], "ppe_required": []}

    def test_returns_none_without_api_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            out = call_structured_prescription("ctx", self._RULE, [], [])
        assert out is None

    def test_returns_none_when_sdk_missing(self):
        # Simulate the anthropic SDK not being installed → graceful degradation.
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}, clear=True):
            with mock.patch.dict("sys.modules", {"anthropic": None}):
                out = call_structured_prescription("ctx", self._RULE, [], [])
        assert out is None
