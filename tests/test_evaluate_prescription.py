"""Tests for eval/evaluate_prescription.py (GH-24)."""
import json
from unittest.mock import patch

import numpy as np
import pytest

from eval.evaluate_prescription import (
    ARMS,
    compute_faithfulness,
    compute_recall,
    compute_sop_overlap,
    evaluate,
    orchestrator,
    run_scenario,
    write_report,
)
from src.services.prescription.history_store import PrescriptionHistoryStore


class FakeEncoder:
    """Deterministic bag-of-words encoder — tests cosine similarity logic
    without loading a real sentence-transformers model."""

    _VOCAB = ["thermal", "voltage", "replace", "monitor", "inspect"]

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = []
        for t in texts:
            t_low = t.lower()
            vecs.append([1.0 if w in t_low else 0.0 for w in self._VOCAB])
        return np.array(vecs)


class TestComputeRecall:
    def test_full_overlap(self):
        assert compute_recall({"a", "b"}, {"a", "b", "c"}) == 1.0

    def test_partial_overlap(self):
        assert compute_recall({"a", "b"}, {"a"}) == 0.5

    def test_no_overlap(self):
        assert compute_recall({"a"}, {"b"}) == 0.0

    def test_empty_expected_returns_zero(self):
        assert compute_recall(set(), {"a"}) == 0.0


class TestComputeSopOverlap:
    def test_matches_basename_substring(self):
        expected = {"maintenance/battery_maintenance_sop.md"}
        refs = ["battery_maintenance_sop §3 (Replacement Criteria)"]
        assert compute_sop_overlap(expected, refs) == 1.0

    def test_case_insensitive(self):
        expected = {"maintenance/battery_maintenance_sop.md"}
        refs = ["BATTERY_MAINTENANCE_SOP notes"]
        assert compute_sop_overlap(expected, refs) == 1.0

    def test_no_match(self):
        expected = {"safety/thermal_runaway_response.md"}
        refs = ["battery_maintenance_sop §1"]
        assert compute_sop_overlap(expected, refs) == 0.0

    def test_empty_expected_returns_zero(self):
        assert compute_sop_overlap(set(), ["anything"]) == 0.0

    def test_partial_hit_among_multiple_expected(self):
        expected = {
            "maintenance/battery_maintenance_sop.md",
            "safety/electrical_safety_sop.md",
        }
        refs = ["battery_maintenance_sop §3", "unrelated_doc"]
        assert compute_sop_overlap(expected, refs) == 0.5


class TestComputeFaithfulness:
    def test_picks_max_similarity_doc(self):
        docs = [
            {"content": "monitor routine inspect"},
            {"content": "thermal voltage replace"},
        ]
        score = compute_faithfulness(
            "thermal voltage critical replace now", docs, FakeEncoder()
        )
        assert score == pytest.approx(1.0, abs=1e-6)  # exact match with docs[1]'s vocab

    def test_no_docs_returns_none(self):
        assert compute_faithfulness("some text", [], FakeEncoder()) is None

    def test_empty_text_returns_none(self):
        assert compute_faithfulness("   ", [{"content": "x"}], FakeEncoder()) is None


class _FakeRetriever:
    """Stub retriever — returns no docs, never opens the real ChromaDB store."""

    def retrieve_maintenance(self, query: str, top_k: int = 3) -> list[dict]:
        return []

    def retrieve_safety(self, query: str, top_k: int = 2) -> list[dict]:
        return []


class TestRunScenarioAndEvaluate:
    _SCENARIO = {
        "id": "test-scenario",
        "prediction": {"soh_percent": 82.0, "health_stage": "Degrading"},
        "anomaly": {
            "anomaly_status": "Degrading",
            "anomaly_score": -0.2,
            "anomaly_confidence": 0.2,
        },
        "risk": {
            "risk_level": "High",
            "priority": "P2",
            "action_code": "SCHEDULE_MAINTENANCE",
        },
        "warnings": [],
        "expected_sources": ["maintenance/battery_maintenance_sop.md"],
    }

    def test_rule_arm_never_touches_retriever(self, tmp_path):
        store = PrescriptionHistoryStore(path=str(tmp_path))
        with patch.object(orchestrator, "_get_retriever") as mock_ret:
            result = run_scenario(self._SCENARIO, "rule", store)
            mock_ret.assert_not_called()
        assert result["enriched"] is False
        assert result["action_code"] == "SCHEDULE_MAINTENANCE"
        assert result["rag_ms"] == 0.0 and result["llm_ms"] == 0.0

    def test_hybrid_template_arm_sets_enrich_not_agentic(self, tmp_path):
        store = PrescriptionHistoryStore(path=str(tmp_path))
        with patch.object(orchestrator, "run_prescription") as mock_run:
            mock_run.return_value = {"battery_id": "test-scenario"}
            run_scenario(self._SCENARIO, "hybrid_template", store)
        _, kwargs = mock_run.call_args
        assert kwargs["enrich"] is True
        assert kwargs["agentic"] is False

    def test_hybrid_agentic_arm_sets_both_flags(self, tmp_path):
        store = PrescriptionHistoryStore(path=str(tmp_path))
        with patch.object(orchestrator, "run_prescription") as mock_run:
            mock_run.return_value = {"battery_id": "test-scenario"}
            run_scenario(self._SCENARIO, "hybrid_agentic", store)
        _, kwargs = mock_run.call_args
        assert kwargs["enrich"] is True
        assert kwargs["agentic"] is True

    def test_evaluate_reports_sop_overlap_once_per_scenario(self):
        with (
            patch("src.services.prescription.llm.chain.is_available", return_value=False),
            patch.object(orchestrator, "_get_retriever", return_value=_FakeRetriever()),
        ):
            rows = evaluate([self._SCENARIO], encoder=FakeEncoder())
        assert len(rows) == 1
        row = rows[0]
        assert "sop_overlap" in row
        assert "rule_sop_overlap" not in row  # not duplicated per-arm
        for arm in ARMS:
            assert f"{arm}_rag_ms" in row

    def test_hybrid_arms_have_none_faithfulness_without_llm_key(self):
        with (
            patch("src.services.prescription.llm.chain.is_available", return_value=False),
            patch.object(orchestrator, "_get_retriever", return_value=_FakeRetriever()),
        ):
            rows = evaluate([self._SCENARIO], encoder=FakeEncoder())
        row = rows[0]
        assert row["hybrid_template_faithfulness"] is None
        assert row["hybrid_agentic_faithfulness"] is None
        assert row["hybrid_template_enriched"] is False
        assert row["rule_coverage"] is None  # rule never retrieves


class TestWriteReport:
    def test_writes_json_and_markdown(self, tmp_path):
        rows = [
            {
                "id": "s1",
                "n_expected": 1,
                "sop_overlap": 0.5,
                "rule_rag_ms": 0.0,
                "rule_llm_ms": 0.0,
                "rule_query_gen_ms": 0.0,
                "hybrid_template_coverage": 1.0,
                "hybrid_template_faithfulness": 0.8,
                "hybrid_template_enriched": True,
                "hybrid_template_rag_ms": 10.0,
                "hybrid_template_llm_ms": 500.0,
                "hybrid_template_query_gen_ms": 0.0,
                "hybrid_agentic_coverage": 1.0,
                "hybrid_agentic_faithfulness": None,
                "hybrid_agentic_enriched": False,
                "hybrid_agentic_rag_ms": 12.0,
                "hybrid_agentic_llm_ms": 0.0,
                "hybrid_agentic_query_gen_ms": 300.0,
            }
        ]
        out_dir = str(tmp_path / "eval_out")
        write_report(rows, out_dir)

        with open(f"{out_dir}/results.json", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == rows

        with open(f"{out_dir}/report.md", encoding="utf-8") as f:
            content = f.read()
        assert "SOP overlap" in content
        assert "s1" in content
        assert "1/1" in content or "hybrid_template 1/1" in content
