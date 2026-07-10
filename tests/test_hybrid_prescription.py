"""Tests for the hybrid prescription layer (rule engine + enrich routing + LLM fallback).

Matches the current API:
  - rule_prescription.build_rule_prescription(prediction, risk, warnings)
  - prescription._enrich / run_prescription(enrich=...)
  - src.services.prescription.llm.chain.is_available / generate_prescription (GH-79 provider chain)
"""
import os
from unittest import mock

from src.services.prescription.rule_prescription import build_rule_prescription
from src.services.prescription.llm import chain
from src.services.prescription.orchestrator import _enrich, _dedup


class TestRulePrescription:
    def test_eol_thermal_adds_steps_escalation_and_base_ppe(self):
        out = build_rule_prescription(
            {"soh_percent": 72.0, "health_stage": "End Of Life"},
            {"risk_level": "Critical", "priority": "P1", "action_code": "REPLACE_IMMEDIATELY"},
            [{"code": "TEMP_CRITICAL"}],
        )
        assert any("lockout" in s.lower() for s in out["action_steps"])
        assert any("thermal runaway" in s.lower() for s in out["action_steps"])
        assert any("escalate to p1" in e.lower() for e in out["escalation_conditions"])
        assert out["ppe_required"]  # base PPE present for a physical action
        assert out["sop_references"]

    def test_electrical_critical_adds_arc_flash_ppe(self):
        out = build_rule_prescription(
            {"soh_percent": 88.0, "health_stage": "Degrading"},
            {"risk_level": "Medium", "priority": "P3", "action_code": "SCHEDULE_MAINTENANCE"},
            [{"code": "VOLTAGE_CRITICAL"}],
        )
        assert any("arc-flash" in p.lower() for p in out["ppe_required"])
        assert any("loto" in e.lower() or "lockout" in e.lower()
                   for e in out["escalation_conditions"])

    def test_monitor_has_no_ppe(self):
        out = build_rule_prescription(
            {"soh_percent": 96.0, "health_stage": "Healthy"},
            {"risk_level": "Low", "priority": "None", "action_code": "MONITOR"},
            [],
        )
        assert out["ppe_required"] == []
        assert "normal" in out["prescription"].lower()

    def test_unknown_action_code_falls_back_to_monitor(self):
        out = build_rule_prescription(
            {"soh_percent": 90.0}, {"action_code": "WAT"}, []
        )
        assert "monitor" in out["prescription"].lower()


class TestDedup:
    def test_dedup_preserves_order(self):
        assert _dedup(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


class TestLlmClient:
    def test_is_available_reflects_api_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            assert chain.is_available() is False
        # DEEPSEEK_API_KEY — default LLM_PROVIDER_CHAIN is "deepseek,gemini" (GH-79).
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}, clear=True):
            assert chain.is_available() is True

    def test_generate_raises_without_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            try:
                chain.generate_prescription("ctx", [], [])
                assert False, "expected RuntimeError when no API key"
            except RuntimeError:
                pass


class TestEnrichFallback:
    """Without an API key, _enrich keeps the rule baseline and flags enriched=False."""
    _RULE = {
        "prescription": "RULE TEXT",
        "action_steps": ["step A"],
        "ppe_required": ["gloves"],
        "escalation_conditions": [],
        "sop_references": [],
    }

    def test_enrich_without_key_keeps_rule_baseline(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            out = _enrich(
                {"soh_percent": 90.0, "health_stage": "Degrading"},
                {"risk_level": "Medium", "priority": "P3", "action_code": "SCHEDULE_MAINTENANCE"},
                [],
                self._RULE,
            )
        assert out["enriched"] is False
        assert out["prescription"] == "RULE TEXT"
        assert out["action_steps"] == ["step A"]

    def test_enrich_merges_ppe_and_sets_flag_on_llm_success(self):
        llm_out = {
            "prescription": "LLM TEXT",
            "action_steps": ["llm step"],
            "ppe_required": ["face shield"],
            "provider": "deepseek",
        }
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}, clear=True), \
                mock.patch.object(chain, "is_available", return_value=True), \
                mock.patch.object(chain, "generate_prescription", return_value=llm_out):
            out = _enrich(
                {"soh_percent": 90.0}, {"action_code": "SCHEDULE_MAINTENANCE"}, [], self._RULE
            )
        assert out["enriched"] is True
        assert out["prescription"] == "LLM TEXT"
        assert out["llm_provider"] == "deepseek"
        # rule PPE must never be dropped — union with LLM PPE
        assert "gloves" in out["ppe_required"]
        assert "face shield" in out["ppe_required"]

    def test_enrich_falls_back_when_llm_raises(self):
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}, clear=True), \
                mock.patch.object(chain, "is_available", return_value=True), \
                mock.patch.object(chain, "generate_prescription",
                                  side_effect=RuntimeError("API down")):
            out = _enrich(
                {"soh_percent": 90.0}, {"action_code": "SCHEDULE_MAINTENANCE"}, [], self._RULE
            )
        assert out["enriched"] is False
        assert out["prescription"] == "RULE TEXT"
        assert out["llm_provider"] == "none"
