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
from src.services.prescription import orchestrator
from src.services.prescription.orchestrator import _enrich, _dedup
from src.services.prescription.history_store import PrescriptionHistoryStore


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

    def test_enrich_result_includes_diagnosis(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            out = _enrich(
                {"soh_percent": 90.0, "health_stage": "Degrading"},
                {"risk_level": "Medium", "priority": "P3", "action_code": "SCHEDULE_MAINTENANCE"},
                [],
                self._RULE,
            )
        # diagnosis is built unconditionally (GH-83), even without an API key,
        # since run_prescription() needs it to save the history record.
        assert out["diagnosis"].startswith("Diagnosis:")

    def test_enrich_forwards_past_cases_to_llm(self):
        past_cases = [{"prescription": "Replaced last time", "action_steps": [], "ppe_required": []}]
        fake_store = mock.Mock()
        fake_store.retrieve_similar_accepted.return_value = past_cases
        llm_out = {
            "prescription": "LLM TEXT", "action_steps": ["s"], "ppe_required": [],
            "provider": "deepseek",
        }
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}, clear=True), \
                mock.patch.object(chain, "is_available", return_value=True), \
                mock.patch.object(chain, "generate_prescription", return_value=llm_out) as mock_gen, \
                mock.patch.object(orchestrator, "_get_history_store", return_value=fake_store):
            _enrich({"soh_percent": 90.0}, {"action_code": "SCHEDULE_MAINTENANCE"}, [], self._RULE)

        fake_store.retrieve_similar_accepted.assert_called_once()
        assert mock_gen.call_args[0][3] == past_cases

    def test_enrich_forwards_ticket_history_into_diagnosis(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            out = _enrich(
                {"soh_percent": 90.0, "health_stage": "Degrading"},
                {"risk_level": "Medium", "priority": "P3", "action_code": "SCHEDULE_MAINTENANCE"},
                [],
                self._RULE,
                ticket_history=["2026-06-10: replaced BMS fuse"],
            )
        assert "Past repairs on this battery: 2026-06-10: replaced BMS fuse." in out["diagnosis"]

    def test_enrich_forwards_battery_id_to_history_retrieval(self):
        fake_store = mock.Mock()
        fake_store.retrieve_similar_accepted.return_value = []
        llm_out = {
            "prescription": "LLM TEXT", "action_steps": ["s"], "ppe_required": [],
            "provider": "deepseek",
        }
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}, clear=True), \
                mock.patch.object(chain, "is_available", return_value=True), \
                mock.patch.object(chain, "generate_prescription", return_value=llm_out), \
                mock.patch.object(orchestrator, "_get_history_store", return_value=fake_store):
            _enrich(
                {"soh_percent": 90.0}, {"action_code": "SCHEDULE_MAINTENANCE"}, [], self._RULE,
                battery_id="B0001",
            )

        assert fake_store.retrieve_similar_accepted.call_args.kwargs["battery_id"] == "B0001"


class TestHistoryFewShotIntegration:
    """
    GH-83 end-to-end: run_prescription() writes history on enrich=true, and an
    accepted case surfaces as few-shot context on the next enrich=true call for
    a similar diagnosis — using a real PrescriptionHistoryStore (tmp_path) so
    the save -> feedback -> retrieve round trip is exercised for real, only the
    LLM chain and run_inference are mocked.
    """

    _PREDICTION_RESULT = {
        "prediction": {"soh_percent": 78.0, "soh_std": 1.0, "health_stage": "Degrading"},
        "anomaly": {"anomaly_status": "Degrading", "anomaly_score": -0.2, "anomaly_confidence": 0.3},
        "risk": {"risk_level": "Medium", "priority": "P2", "action_code": "SCHEDULE_MAINTENANCE"},
        "evidence": {"warnings": []},
        "metadata": {"inference_ms": 5.0},
    }
    _READINGS = [[3.7, 1.0, 25.0]] * 30

    def _patch_common(self, monkeypatch, tmp_path):
        store = PrescriptionHistoryStore(path=str(tmp_path))
        monkeypatch.setattr(orchestrator, "_get_history_store", lambda: store)
        monkeypatch.setattr(orchestrator, "run_inference", lambda *a, **kw: self._PREDICTION_RESULT)
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        monkeypatch.setattr(chain, "is_available", lambda: True)
        return store

    def test_prescription_id_empty_when_enrich_false(self, monkeypatch, tmp_path):
        self._patch_common(monkeypatch, tmp_path)
        result = orchestrator.run_prescription(self._READINGS, "B0001", enrich=False)
        assert result["prescription_id"] == ""

    def test_history_not_touched_when_enrich_false(self, monkeypatch, tmp_path):
        def _boom():
            raise AssertionError("history store must not be built on the enrich=false path")
        monkeypatch.setattr(orchestrator, "_get_history_store", _boom)
        monkeypatch.setattr(orchestrator, "run_inference", lambda *a, **kw: self._PREDICTION_RESULT)
        orchestrator.run_prescription(self._READINGS, "B0001", enrich=False)

    def test_accepted_case_surfaces_as_few_shot_on_next_call(self, monkeypatch, tmp_path):
        self._patch_common(monkeypatch, tmp_path)

        llm_out_1 = {
            "prescription": "First fix", "action_steps": ["a"], "ppe_required": [],
            "provider": "deepseek",
        }
        monkeypatch.setattr(chain, "generate_prescription", lambda *a, **kw: llm_out_1)
        result_1 = orchestrator.run_prescription(self._READINGS, "B0001", enrich=True)
        assert result_1["prescription_id"]

        assert orchestrator.submit_prescription_feedback(result_1["prescription_id"], "accepted") is True

        captured = {}

        def fake_generate(context, maint_docs, safety_docs, past_cases=None):
            captured["past_cases"] = past_cases
            return {"prescription": "Second fix", "action_steps": ["b"], "ppe_required": [],
                    "provider": "deepseek"}

        monkeypatch.setattr(chain, "generate_prescription", fake_generate)
        orchestrator.run_prescription(self._READINGS, "B0002", enrich=True)

        assert any(c["prescription"] == "First fix" for c in captured["past_cases"])

    def test_rejected_case_does_not_surface_as_few_shot(self, monkeypatch, tmp_path):
        self._patch_common(monkeypatch, tmp_path)

        llm_out_1 = {
            "prescription": "First fix", "action_steps": ["a"], "ppe_required": [],
            "provider": "deepseek",
        }
        monkeypatch.setattr(chain, "generate_prescription", lambda *a, **kw: llm_out_1)
        result_1 = orchestrator.run_prescription(self._READINGS, "B0001", enrich=True)

        assert orchestrator.submit_prescription_feedback(result_1["prescription_id"], "rejected") is True

        captured = {}

        def fake_generate(context, maint_docs, safety_docs, past_cases=None):
            captured["past_cases"] = past_cases
            return {"prescription": "Second fix", "action_steps": ["b"], "ppe_required": [],
                    "provider": "deepseek"}

        monkeypatch.setattr(chain, "generate_prescription", fake_generate)
        orchestrator.run_prescription(self._READINGS, "B0002", enrich=True)

        assert captured["past_cases"] == []
