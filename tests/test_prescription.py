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
