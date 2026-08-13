"""Tests for the hybrid Prescription Layer (GH-20)."""

import time
from unittest.mock import patch

import numpy as np
import pytest

from src.core.config import (
    BASE_FEATURES,
    INPUT_FEATURES,
    SPECTRAL_FEAT_DIM,
    WINDOW_SIZE,
)
from src.models.soh_predictor import MambaSOHPredictor
from src.services.prescription.rule_prescription import build_rule_prescription

BASE_N = len(BASE_FEATURES)  # GH-54: payload/scaler width (4)


def make_dummy_readings(n: int = WINDOW_SIZE) -> list[list[float]]:
    return [[3.7 + i * 0.001, 1.5, 25.0, float(i)] for i in range(n)]


def fake_inference_result(
    action_code: str = "REPLACE_IMMEDIATELY",
    risk_level: str = "Critical",
    priority: str = "P1",
    warnings: list[dict] | None = None,
    soh: float = 68.0,
) -> dict:
    return {
        "prediction": {
            "soh_percent": soh,
            "health_stage": "End Of Life",
            "degradation_rate_per_cycle": 0.3,
            "soh_trend": "accelerating",
            "rul_cycles_estimate": 5,
        },
        "risk": {
            "risk_level": risk_level,
            "priority": priority,
            "action_code": action_code,
            "reasons": [],
        },
        "evidence": {"warnings": warnings or []},
        "metadata": {"inference_ms": 12.3},
    }


# ── Rule-based decision table (pure, no models) ──────────────────────────────
class TestRulePrescription:
    def test_replace_immediately_steps_and_escalation(self):
        out = build_rule_prescription(
            {"soh_percent": 68.0},
            {
                "action_code": "REPLACE_IMMEDIATELY",
                "risk_level": "Critical",
                "priority": "P1",
            },
            [],
        )
        assert "end-of-life" in out["prescription"].lower()
        assert len(out["action_steps"]) >= 1
        assert out["ppe_required"]  # physical action → PPE present
        assert any("manager" in e.lower() for e in out["escalation_conditions"])
        assert out["sop_references"]

    def test_monitor_has_no_ppe(self):
        out = build_rule_prescription(
            {"soh_percent": 95.0},
            {"action_code": "MONITOR", "risk_level": "Low", "priority": "None"},
            [],
        )
        assert out["ppe_required"] == []
        assert out["escalation_conditions"] == []

    def test_thermal_warning_adds_step_and_escalation(self):
        out = build_rule_prescription(
            {"soh_percent": 70.0},
            {
                "action_code": "REPLACE_IMMEDIATELY",
                "risk_level": "Critical",
                "priority": "P1",
            },
            [{"code": "TEMP_CRITICAL"}],
        )
        assert any("thermal" in s.lower() for s in out["action_steps"])
        assert any("thermal" in e.lower() for e in out["escalation_conditions"])

    def test_electrical_warning_adds_arc_flash_ppe(self):
        out = build_rule_prescription(
            {"soh_percent": 70.0},
            {
                "action_code": "REPLACE_IMMEDIATELY",
                "risk_level": "Critical",
                "priority": "P1",
            },
            [{"code": "OVERVOLTAGE_CRITICAL"}],
        )
        assert any("arc-flash" in p.lower() for p in out["ppe_required"])
        assert any("loto" in e.lower() for e in out["escalation_conditions"])

    def test_unknown_action_code_falls_back_to_monitor(self):
        out = build_rule_prescription(
            {"soh_percent": 90.0},
            {"action_code": "WAT", "risk_level": "Low", "priority": "None"},
            [],
        )
        assert "monitor" in out["prescription"].lower()


# ── Hybrid pipeline (run_inference mocked → deterministic, no models) ─────────
class TestPrescriptionPipeline:
    def test_default_is_rule_based_no_network(self):
        from src.services.prescription import orchestrator as prescription

        with patch.object(
            prescription, "run_inference", return_value=fake_inference_result()
        ):
            with patch.object(prescription, "_get_retriever") as mock_ret:
                out = prescription.run_prescription(
                    make_dummy_readings(), "B0005", enrich=False
                )
                mock_ret.assert_not_called()  # rule path must NOT touch RAG
        assert out["enriched"] is False
        assert out["llm_provider"] == "none"
        assert out["maintenance_docs"] == []
        assert out["rag_ms"] == 0.0 and out["llm_ms"] == 0.0
        assert out["action_code"] == "REPLACE_IMMEDIATELY"
        assert out["human_verification_required"] is True  # P1

    def test_response_nests_prediction_anomaly_risk_verbatim(self):
        """GH-87: run_prescription() must forward run_inference()'s prediction/
        anomaly/risk dicts unchanged (no recompute) — including GH-86 uncertainty
        fields, which the flat context fields never carried."""
        from src.services.prescription import orchestrator as prescription

        inference_result = {
            "prediction": {
                "soh_percent": 81.0,
                "soh_confidence": 0.7,
                "soh_std": 2.1,
                "rul_cycles_estimate": 30,
                "degradation_rate_per_cycle": 0.25,
                "soh_trend": "accelerating",
                "cycles_to_maintenance": 0,
                "soh_trajectory": [81.0, 80.7, 80.4],
                "health_stage": "Maintenance Required",
                "stage_probabilities": {"Maintenance Required": 0.65, "Degrading": 0.35},
                "stage_confidence": 0.65,
                "is_borderline": True,
            },
            "anomaly": {
                "anomaly_score": -0.15,
                "anomaly_status": "Degrading",
                "anomaly_confidence": 0.15,
            },
            "risk": {
                "risk_level": "High",
                "priority": "P2",
                "action_code": "SCHEDULE_REPLACEMENT",
                "reasons": ["SOH below maintenance threshold"],
            },
            "evidence": {"warnings": []},
            "metadata": {"inference_ms": 12.3},
        }
        with patch.object(prescription, "run_inference", return_value=inference_result):
            out = prescription.run_prescription(
                make_dummy_readings(), "B0005", enrich=False
            )
        assert out["prediction"] == inference_result["prediction"]
        assert out["anomaly"] == inference_result["anomaly"]
        assert out["risk"] == inference_result["risk"]
        assert out["prediction"]["is_borderline"] is True
        assert out["prediction"]["stage_confidence"] == 0.65

    def test_enrich_success_uses_llm_output(self):
        from src.services.prescription import orchestrator as prescription

        class FakeRetriever:
            def retrieve_maintenance(self, q, top_k=3):
                return [
                    {
                        "title": "M",
                        "content": "c",
                        "source": "maintenance/x.md",
                        "relevance_score": 0.9,
                    }
                ]

            def retrieve_safety(self, q, top_k=2):
                return []

        llm_out = {
            "prescription": "LLM-generated plan",
            "action_steps": ["step a"],
            "ppe_required": ["Face shield"],
            "provider": "deepseek",
        }
        with (
            patch.object(
                prescription, "run_inference", return_value=fake_inference_result()
            ),
            patch.object(prescription, "_get_retriever", return_value=FakeRetriever()),
            patch("src.services.prescription.llm.chain.is_available", return_value=True),
            patch(
                "src.services.prescription.llm.chain.generate_prescription",
                return_value=llm_out,
            ),
        ):
            out = prescription.run_prescription(
                make_dummy_readings(), "B0005", enrich=True
            )
        assert out["enriched"] is True
        assert out["prescription"] == "LLM-generated plan"
        assert out["action_steps"] == ["step a"]
        assert "Face shield" in out["ppe_required"]
        assert len(out["maintenance_docs"]) == 1
        assert out["llm_provider"] == "deepseek"

    def test_enrich_falls_back_when_llm_errors(self):
        from src.services.prescription import orchestrator as prescription

        class FakeRetriever:
            def retrieve_maintenance(self, q, top_k=3):
                return []

            def retrieve_safety(self, q, top_k=2):
                return []

        with (
            patch.object(
                prescription, "run_inference", return_value=fake_inference_result()
            ),
            patch.object(prescription, "_get_retriever", return_value=FakeRetriever()),
            patch("src.services.prescription.llm.chain.is_available", return_value=True),
            patch(
                "src.services.prescription.llm.chain.generate_prescription",
                side_effect=RuntimeError("API down"),
            ),
        ):
            out = prescription.run_prescription(
                make_dummy_readings(), "B0005", enrich=True
            )
        assert out["enriched"] is False  # fell back
        assert "end-of-life" in out["prescription"].lower()  # rule text kept
        assert out["human_verification_required"] is True
        assert out["llm_provider"] == "none"

    def test_enrich_skipped_without_api_key(self):
        from src.services.prescription import orchestrator as prescription

        class FakeRetriever:
            def retrieve_maintenance(self, q, top_k=3):
                return []

            def retrieve_safety(self, q, top_k=2):
                return []

        with (
            patch.object(
                prescription, "run_inference", return_value=fake_inference_result()
            ),
            patch.object(prescription, "_get_retriever", return_value=FakeRetriever()),
            patch("src.services.prescription.llm.chain.is_available", return_value=False),
        ):
            out = prescription.run_prescription(
                make_dummy_readings(), "B0005", enrich=True
            )
        assert out["enriched"] is False
        assert out["llm_provider"] == "none"


# ── GH-81: safety gate v2 — blocked path, judge, audit log ───────────────────
class FakeEmptyRetriever:
    def retrieve_maintenance(self, q, top_k=3):
        return []

    def retrieve_safety(self, q, top_k=2):
        return []


BANNED_LLM_OUT = {
    "prescription": "Inspect the pack internals.",
    "action_steps": ["Open the battery casing to inspect the cells.", "Log findings."],
    "ppe_required": [],
    "provider": "deepseek",
}
CLEAN_LLM_OUT = {
    "prescription": "Replace the battery within 24 hours.",
    "action_steps": ["Complete the Lockout/Tagout procedure.", "Replace the unit."],
    "ppe_required": ["Face shield"],
    "provider": "deepseek",
}


def run_enriched(llm_out=None, llm_side_effect=None, judge=None, judge_side_effect=None,
                 inference=None):
    """Run the pipeline with mocked inference/RAG/LLM; returns the response dict."""
    from src.services.prescription import orchestrator as prescription

    patches = [
        patch.object(
            prescription, "run_inference",
            return_value=inference or fake_inference_result(),
        ),
        patch.object(prescription, "_get_retriever", return_value=FakeEmptyRetriever()),
        patch("src.services.prescription.llm.chain.is_available", return_value=True),
        patch(
            "src.services.prescription.llm.chain.generate_prescription",
            return_value=llm_out, side_effect=llm_side_effect,
        ),
        patch(
            "src.services.prescription.llm.chain.judge_safety",
            return_value=judge, side_effect=judge_side_effect,
        ),
    ]
    with patches[0], patches[1], patches[2], patches[3], patches[4] as judge_mock:
        out = prescription.run_prescription(make_dummy_readings(), "B0005", enrich=True)
    return out, judge_mock


class TestSafetyGateV2Pipeline:
    @pytest.fixture(autouse=True)
    def judge_flag_off(self, monkeypatch):
        monkeypatch.delenv("SAFETY_LLM_JUDGE", raising=False)

    def test_blocked_llm_output_returns_rule_based(self, caplog):
        with caplog.at_level("WARNING", logger="safety_gate.audit"):
            out, _ = run_enriched(llm_out=BANNED_LLM_OUT)

        assert out["blocked"] is True
        assert out["human_verification_required"] is True
        assert out["enriched"] is False
        assert out["llm_provider"] == "none"
        # LLM output must never leak — rule-based text is returned instead
        assert "end-of-life" in out["prescription"].lower()
        assert all("open the battery casing" not in s.lower() for s in out["action_steps"])
        assert any("forbidden action" in w.lower() for w in out["safety_warnings"])
        # audit log: one structured record with the matched pattern + blocked output
        audit = [r for r in caplog.records if r.name == "safety_gate.audit"]
        assert len(audit) == 1
        assert "PRESCRIPTION_BLOCKED" in audit[0].getMessage()
        assert "open/disassemble" in audit[0].getMessage()
        assert "Open the battery casing" in audit[0].getMessage()

    def test_blocked_output_still_gets_ppe_loto_enforcement(self):
        # After the swap, the rule-based output is re-gated: electrical critical
        # → LOTO present (rule template) + mandatory PPE unioned.
        out, _ = run_enriched(
            llm_out=BANNED_LLM_OUT,
            inference=fake_inference_result(
                warnings=[{"code": "VOLTAGE_CRITICAL", "severity": "critical"}]
            ),
        )
        assert out["blocked"] is True
        assert any("lockout/tagout" in s.lower() for s in out["action_steps"])
        assert any("steel-toed" in p.lower() for p in out["ppe_required"])

    def test_empty_llm_steps_falls_back_to_rule(self):
        out, _ = run_enriched(
            llm_out={"prescription": "x", "action_steps": [], "ppe_required": [],
                     "provider": "deepseek"}
        )
        assert out["blocked"] is False
        assert out["enriched"] is False
        assert "end-of-life" in out["prescription"].lower()

    def test_judge_not_called_when_flag_off(self):
        out, judge_mock = run_enriched(llm_out=CLEAN_LLM_OUT)
        judge_mock.assert_not_called()
        assert out["blocked"] is False
        assert out["enriched"] is True

    def test_judge_unsafe_blocks(self, monkeypatch, caplog):
        monkeypatch.setenv("SAFETY_LLM_JUDGE", "1")
        with caplog.at_level("WARNING", logger="safety_gate.audit"):
            out, judge_mock = run_enriched(
                llm_out=CLEAN_LLM_OUT,
                judge={"safe": False, "reason": "step 2 unsafe near thermal event"},
            )
        judge_mock.assert_called_once()
        assert out["blocked"] is True
        assert out["enriched"] is False
        assert "end-of-life" in out["prescription"].lower()
        assert any("judge" in w.lower() for w in out["safety_warnings"])
        audit = [r for r in caplog.records if r.name == "safety_gate.audit"]
        assert len(audit) == 1 and "llm_judge" in audit[0].getMessage()

    def test_judge_failure_passes(self, monkeypatch):
        monkeypatch.setenv("SAFETY_LLM_JUDGE", "1")
        out, _ = run_enriched(
            llm_out=CLEAN_LLM_OUT, judge_side_effect=RuntimeError("all providers down")
        )
        assert out["blocked"] is False
        assert out["enriched"] is True  # judge unavailability never blocks

    def test_judge_safe_verdict_keeps_llm_output(self, monkeypatch):
        monkeypatch.setenv("SAFETY_LLM_JUDGE", "1")
        out, _ = run_enriched(llm_out=CLEAN_LLM_OUT, judge={"safe": True, "reason": "ok"})
        assert out["blocked"] is False
        assert out["enriched"] is True
        assert out["prescription"] == CLEAN_LLM_OUT["prescription"]

    def test_judge_not_called_on_rule_path(self, monkeypatch):
        # blocklist already blocked the output → judge must not run
        monkeypatch.setenv("SAFETY_LLM_JUDGE", "1")
        out, judge_mock = run_enriched(llm_out=BANNED_LLM_OUT)
        judge_mock.assert_not_called()
        assert out["blocked"] is True


# ── GH-82: agentic chain — query-gen, multi-query retrieval, dedup ───────────
class RecordingRetriever:
    """2 docs per maintenance query (1 unique + 1 shared chunk), 1 per safety
    query — records every call for retrieval assertions."""

    def __init__(self):
        self.calls = []

    def retrieve_maintenance(self, q, top_k=3):
        self.calls.append(("maintenance", q, top_k))
        return [
            {"title": "M", "content": f"m-{q}", "source": "maintenance/battery_maintenance_sop.md",
             "relevance_score": 0.9, "chunk_id": f"m-{q}"},
            {"title": "M", "content": "shared", "source": "maintenance/action_code_sop.md",
             "relevance_score": 0.8, "chunk_id": "m-shared"},
        ]

    def retrieve_safety(self, q, top_k=2):
        self.calls.append(("safety", q, top_k))
        return [
            {"title": "S", "content": f"s-{q}", "source": "safety/ppe_matrix.md",
             "relevance_score": 0.7, "chunk_id": f"s-{q}"},
        ]


QUERIES_OUT = {
    "maintenance_queries": ["capacity fade inspection", "replacement criteria eol", "internal resistance check"],
    "safety_queries": ["lockout tagout before replacement"],
    "provider": "deepseek",
}


def run_agentic_pipeline(queries=None, queries_side_effect=None, agentic=True, enrich=True):
    from src.services.prescription import orchestrator as prescription

    retriever = RecordingRetriever()
    with (
        patch.object(prescription, "run_inference", return_value=fake_inference_result()),
        patch.object(prescription, "_get_retriever", return_value=retriever),
        patch("src.services.prescription.llm.chain.is_available", return_value=True),
        patch(
            "src.services.prescription.llm.chain.generate_queries",
            return_value=queries, side_effect=queries_side_effect,
        ) as qg_mock,
        patch(
            "src.services.prescription.llm.chain.generate_prescription",
            return_value=dict(CLEAN_LLM_OUT),
        ) as gen_mock,
    ):
        out = prescription.run_prescription(
            make_dummy_readings(), "B0005", enrich=enrich, agentic=agentic
        )
    return out, retriever, qg_mock, gen_mock


class TestAgenticPipeline:
    @pytest.fixture(autouse=True)
    def judge_flag_off(self, monkeypatch):
        monkeypatch.delenv("SAFETY_LLM_JUDGE", raising=False)

    def test_agentic_two_llm_calls_and_per_query_retrieval(self):
        out, retriever, qg_mock, gen_mock = run_agentic_pipeline(queries=QUERIES_OUT)
        # exactly 2 LLM calls: query-gen + summarize
        qg_mock.assert_called_once()
        gen_mock.assert_called_once()
        # retrieval ran per query with top_k=2
        maint_calls = [c for c in retriever.calls if c[0] == "maintenance"]
        safety_calls = [c for c in retriever.calls if c[0] == "safety"]
        assert [c[1] for c in maint_calls] == QUERIES_OUT["maintenance_queries"]
        assert [c[1] for c in safety_calls] == QUERIES_OUT["safety_queries"]
        assert all(c[2] == 2 for c in retriever.calls)
        assert out["enriched"] is True
        assert out["generated_queries"] == (
            QUERIES_OUT["maintenance_queries"] + QUERIES_OUT["safety_queries"]
        )
        assert out["query_gen_ms"] >= 0.0

    def test_agentic_dedup_and_retrieved_via(self):
        out, _, _, _ = run_agentic_pipeline(queries=QUERIES_OUT)
        docs = out["maintenance_docs"]
        # 3 unique + shared chunk dedup'd to 1 → 4 docs (≤ cap 5)
        assert len(docs) == 4
        shared = [d for d in docs if d["chunk_id"] == "m-shared"]
        assert len(shared) == 1
        # shared chunk keeps the first (highest-relevance tie) query as source
        assert shared[0]["retrieved_via"] == QUERIES_OUT["maintenance_queries"][0]
        assert all(d["retrieved_via"] in QUERIES_OUT["maintenance_queries"] for d in docs)
        # sorted by relevance: unique docs (0.9) before shared (0.8)
        assert [d["relevance_score"] for d in docs] == sorted(
            [d["relevance_score"] for d in docs], reverse=True
        )

    def test_agentic_caps_maintenance_docs_at_5(self):
        many = {
            "maintenance_queries": [f"q{i}" for i in range(4)],  # 4×1 unique + shared = 5
            "safety_queries": ["s1", "s2", "s3", "s4"],          # 4 unique > cap 3
            "provider": "deepseek",
        }
        out, _, _, _ = run_agentic_pipeline(queries=many)
        assert len(out["maintenance_docs"]) == 5
        assert len(out["safety_docs"]) == 3

    def test_query_gen_failure_falls_back_to_template(self):
        out, retriever, qg_mock, gen_mock = run_agentic_pipeline(
            queries_side_effect=RuntimeError("all providers down")
        )
        qg_mock.assert_called_once()
        gen_mock.assert_called_once()  # pipeline still completes with LLM summarize
        # template fallback: single query per collection, original top_k
        assert [c[2] for c in retriever.calls] == [3, 2]
        assert out["enriched"] is True
        assert out["generated_queries"] == []
        assert all(d["retrieved_via"] == "template" for d in out["maintenance_docs"])
        assert out["query_gen_ms"] >= 0.0

    def test_empty_queries_fall_back_to_template(self):
        out, retriever, _, _ = run_agentic_pipeline(
            queries={"maintenance_queries": [], "safety_queries": [], "provider": "deepseek"}
        )
        assert [c[2] for c in retriever.calls] == [3, 2]
        assert out["generated_queries"] == []

    def test_agentic_false_never_calls_query_gen(self):
        out, retriever, qg_mock, _ = run_agentic_pipeline(queries=QUERIES_OUT, agentic=False)
        qg_mock.assert_not_called()
        assert [c[2] for c in retriever.calls] == [3, 2]  # unchanged template behavior
        assert out["generated_queries"] == []
        assert out["query_gen_ms"] == 0.0
        assert all(d["retrieved_via"] == "template" for d in out["maintenance_docs"])

    def test_agentic_ignored_without_enrich(self):
        out, retriever, qg_mock, gen_mock = run_agentic_pipeline(
            queries=QUERIES_OUT, agentic=True, enrich=False
        )
        qg_mock.assert_not_called()
        gen_mock.assert_not_called()
        assert retriever.calls == []  # rule path touches nothing
        assert out["enriched"] is False
        assert out["query_gen_ms"] == 0.0
        assert out["generated_queries"] == []


# ── Latency: rule path must stay on the P1 <100ms hot-path ───────────────────
class TestPrescriptionLatency:
    @pytest.fixture(autouse=True)
    def patch_model_loader(self):
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import MinMaxScaler, StandardScaler

        dummy_scaler = MinMaxScaler()
        dummy_scaler.fit(np.random.rand(50, BASE_N))
        dummy_feat_scaler = StandardScaler()
        dummy_feat_scaler.fit(np.random.rand(50, SPECTRAL_FEAT_DIM))
        dummy_model = MambaSOHPredictor(
            input_features=INPUT_FEATURES,
            feat_dim=SPECTRAL_FEAT_DIM,
            d_model=8,
            d_state=4,
        )
        dummy_model.eval()
        dummy_iso = IsolationForest(n_estimators=10, random_state=42)
        dummy_iso.fit(np.random.rand(50, SPECTRAL_FEAT_DIM))

        with patch("src.services.inference.model_loader") as mock_loader:
            mock_loader.scaler = dummy_scaler
            mock_loader.feature_scaler = dummy_feat_scaler
            mock_loader.soh_model = dummy_model
            mock_loader.iso_model = dummy_iso
            yield

    def test_rule_path_under_100ms(self):
        from src.services.prescription import run_prescription

        readings = make_dummy_readings()
        # warm-up (first call pays lazy init / JIT)
        run_prescription(readings, "B0005", enrich=False)
        latencies = []
        for _ in range(20):
            t = time.perf_counter()
            out = run_prescription(readings, "B0005", enrich=False)
            latencies.append((time.perf_counter() - t) * 1000)
        avg_ms = sum(latencies) / len(latencies)
        assert out["enriched"] is False
        assert avg_ms < 100, f"Rule-path prescribe too slow: {avg_ms:.1f}ms >= 100ms"
