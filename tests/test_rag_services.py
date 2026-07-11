"""Tests for RAG service components."""
import pytest

from src.services.prescription.safety_gate import (
    LOTO_STEP,
    THERMAL_SOP_STEP,
    apply_safety_gate,
)


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

    def test_input_only_call_never_blocks(self):
        # v1 call shape (no action_steps) → output validation is skipped entirely
        result = apply_safety_gate("P1", "REPLACE_IMMEDIATELY",
                                   [{"code": "TEMP_CRITICAL", "severity": "critical"}],
                                   "Dangerous")
        assert result["blocked"] is False
        assert result["action_steps"] == []
        assert result["ppe_required"] == []


# ── GH-81 output validation ──────────────────────────────────────────────
ELECTRICAL = [{"code": "VOLTAGE_CRITICAL", "severity": "critical"}]
THERMAL = [{"code": "TEMP_CRITICAL", "severity": "critical"}]
NONE: list[dict] = []

# Output variants for the acceptance-criteria matrix
STEPS_NO_LOTO = ["Measure the open-circuit voltage.", "Log the result in the ticket."]
STEPS_BANNED = ["Open the battery casing to inspect the cells.", "Log the result."]
STEPS_CLEAN = [
    "Complete the Lockout/Tagout procedure before any contact.",
    "Evacuate the area and maintain the exclusion zone.",
    "Measure the open-circuit voltage.",
]
FULL_PPE = [
    "Insulated gloves (>=500V)",
    "Safety glasses (ANSI Z87.1)",
    "Arc-flash rated clothing",
    "Steel-toed footwear",
]


def gate_v2(warnings, steps, ppe=None, llm=True, priority="P2", action="SCHEDULE_MAINTENANCE"):
    return apply_safety_gate(
        priority, action, warnings, "Generated prescription text.",
        action_steps=steps, ppe_required=ppe if ppe is not None else list(FULL_PPE),
        llm_generated=llm,
    )


class TestSafetyGateOutputMatrix:
    """AC matrix: (electrical / thermal / none) × (missing LOTO / banned / clean)."""

    # ── electrical critical ──
    def test_electrical_missing_loto_injects(self):
        result = gate_v2(ELECTRICAL, STEPS_NO_LOTO)
        assert result["blocked"] is False
        assert result["action_steps"][0] == LOTO_STEP
        assert any("loto" in w.lower() for w in result["safety_warnings"])

    def test_electrical_banned_blocks(self):
        result = gate_v2(ELECTRICAL, STEPS_BANNED)
        assert result["blocked"] is True
        assert result["human_verification_required"] is True
        assert result["matched_patterns"]
        # blocked output is returned untouched — caller discards it
        assert result["action_steps"] == STEPS_BANNED

    def test_electrical_clean_passes(self):
        result = gate_v2(ELECTRICAL, STEPS_CLEAN)
        assert result["blocked"] is False
        assert result["action_steps"] == STEPS_CLEAN  # no injection

    # ── thermal critical ──
    def test_thermal_missing_containment_injects(self):
        result = gate_v2(THERMAL, STEPS_NO_LOTO)
        assert result["blocked"] is False
        assert THERMAL_SOP_STEP in result["action_steps"]
        assert any("thermal" in w.lower() and "injected" in w.lower()
                   for w in result["safety_warnings"])

    def test_thermal_banned_blocks(self):
        result = gate_v2(THERMAL, STEPS_BANNED)
        assert result["blocked"] is True

    def test_thermal_clean_passes(self):
        result = gate_v2(THERMAL, STEPS_CLEAN)
        assert result["blocked"] is False
        assert THERMAL_SOP_STEP not in result["action_steps"]

    # ── no critical warning ──
    def test_none_missing_loto_no_injection(self):
        result = gate_v2(NONE, STEPS_NO_LOTO)
        assert result["blocked"] is False
        assert result["action_steps"] == STEPS_NO_LOTO

    def test_none_banned_blocks(self):
        result = gate_v2(NONE, STEPS_BANNED)
        assert result["blocked"] is True

    def test_none_clean_passes(self):
        result = gate_v2(NONE, STEPS_CLEAN)
        assert result["blocked"] is False
        assert result["action_steps"] == STEPS_CLEAN


class TestSafetyGateBlocklist:
    @pytest.mark.parametrize("step,label", [
        ("Open the battery casing to inspect the cells.", "open/disassemble"),
        ("Disassemble the cell housing for inspection.", "open/disassemble"),
        ("Short the terminals briefly to test capacity.", "short-circuit"),
        ("Short-circuit the battery to verify the fuse.", "short-circuit"),
        ("Use water to extinguish the battery fire.", "water"),
        ("Spray water on the burning pack.", "water"),
        ("Tighten the terminal bolts while charging.", "charging"),
    ])
    def test_banned_actions_block(self, step, label):
        result = gate_v2(NONE, [step])
        assert result["blocked"] is True, f"expected block for: {step}"

    @pytest.mark.parametrize("step", [
        "Do NOT use water on a lithium fire — use a Class D extinguisher.",
        "Never open the battery casing; return the unit to the vendor.",
        "Avoid any work while charging; disconnect the charger first.",
        "Insulate the terminals to prevent shorting the battery.",
    ])
    def test_negated_phrases_pass(self, step):
        result = gate_v2(NONE, [step])
        assert result["blocked"] is False, f"false positive on: {step}"

    def test_rule_based_output_skips_blocklist(self):
        # Rule text is under our control — e.g. the thermal SOP step contains
        # "do NOT use water" and must never be blocked on the rule path.
        result = gate_v2(THERMAL, ["Use water to cool adjacent equipment."], llm=False)
        assert result["blocked"] is False

    def test_banned_in_prescription_text_blocks(self):
        result = apply_safety_gate(
            "P2", "SCHEDULE_MAINTENANCE", NONE,
            "Open the battery casing and check each cell.",
            action_steps=["Log the result."], ppe_required=[], llm_generated=True,
        )
        assert result["blocked"] is True


class TestSafetyGatePpeEnforcement:
    def test_electrical_critical_unions_missing_ppe(self):
        result = gate_v2(ELECTRICAL, STEPS_CLEAN, ppe=["Insulated gloves (>=500V)"])
        assert "Arc-flash rated clothing" in result["ppe_required"]
        assert "Steel-toed footwear" in result["ppe_required"]
        # existing PPE is preserved, not replaced
        assert "Insulated gloves (>=500V)" in result["ppe_required"]
        assert any("ppe" in w.lower() for w in result["safety_warnings"])

    def test_full_ppe_not_duplicated(self):
        result = gate_v2(ELECTRICAL, STEPS_CLEAN, ppe=list(FULL_PPE))
        assert result["ppe_required"] == FULL_PPE  # unchanged, no dupes

    def test_temp_elevated_adds_ir_thermometer(self):
        warnings = [{"code": "TEMP_ELEVATED", "severity": "warning"}]
        result = gate_v2(warnings, STEPS_CLEAN, ppe=[])
        assert any("thermometer" in p.lower() for p in result["ppe_required"])

    def test_thermal_critical_adds_no_ppe(self):
        # ppe_matrix.md: no PPE substitutes for evacuation at thermal-critical
        result = gate_v2(THERMAL, STEPS_CLEAN, ppe=[])
        assert result["ppe_required"] == []

    def test_replace_immediately_requires_steel_toed(self):
        result = gate_v2(NONE, STEPS_CLEAN, ppe=[], action="REPLACE_IMMEDIATELY")
        assert "Steel-toed footwear" in result["ppe_required"]


# ── GH-82: diagnosis statement builder ───────────────────────────────────
class TestDiagnosisStatement:
    def _build(self, **over):
        from src.services.prescription.diagnosis import build_diagnosis_statement

        args = {
            "prediction": {"soh_percent": 78.5, "soh_std": 1.6, "health_stage": "Degrading"},
            "anomaly": {"anomaly_status": "Degrading", "anomaly_score": -0.25,
                        "anomaly_confidence": 0.25},
            "risk": {"risk_level": "High", "priority": "P2",
                     "action_code": "SCHEDULE_REPLACEMENT"},
            "warnings": [{"code": "SOH_LOW", "severity": "warning"}],
        }
        args.update(over)
        return build_diagnosis_statement(**args)

    def test_contains_three_parts(self):
        out = self._build()
        assert out.startswith("Diagnosis:")
        assert "Inference evidence:" in out
        assert "Description:" in out

    def test_contains_prediction_evidence(self):
        out = self._build()
        assert "78.5%" in out and "± 1.6" in out
        assert "Degrading" in out
        assert "-0.250" in out
        assert "SOH_LOW" in out
        assert "SCHEDULE_REPLACEMENT" in out
        assert "schedule replacement" in out.lower()  # action template summary

    def test_no_warnings_says_none(self):
        out = self._build(warnings=[])
        assert "active warnings: none" in out

    def test_empty_anomaly_block_defaults(self):
        out = self._build(anomaly={})
        assert out.startswith("Diagnosis: Unknown")

    def test_unknown_action_code_falls_back_to_monitor(self):
        out = self._build(risk={"action_code": "WAT", "risk_level": "Low", "priority": "None"})
        assert "operating normally" in out.lower()

    def test_deterministic(self):
        assert self._build() == self._build()


# ── GH-82: retriever chunk_id for multi-query dedup ─────────────────────
class TestRetrieverFormat:
    def test_format_includes_chunk_id(self):
        from src.services.prescription.rag_retriever import RagRetriever

        results = {
            "ids": [["doc_a_0", "doc_a_1"]],
            "documents": [["chunk one", "chunk two"]],
            "metadatas": [[{"title": "T", "source": "maintenance/a.md"},
                           {"title": "T", "source": "maintenance/a.md"}]],
            "distances": [[0.1, 0.4]],
        }
        docs = RagRetriever._format(results)
        assert [d["chunk_id"] for d in docs] == ["doc_a_0", "doc_a_1"]
        assert docs[0]["relevance_score"] == pytest.approx(0.9)

    def test_format_missing_ids_defaults_empty(self):
        from src.services.prescription.rag_retriever import RagRetriever

        results = {
            "documents": [["chunk one"]],
            "metadatas": [[{"title": "T", "source": "maintenance/a.md"}]],
            "distances": [[0.2]],
        }
        docs = RagRetriever._format(results)
        assert docs[0]["chunk_id"] == ""


class TestRagRetriever:
    def test_retriever_gracefully_handles_missing_chromadb(self):
        """RagRetriever should not crash if chromadb is not installed."""
        from src.services.prescription.rag_retriever import RagRetriever
        retriever = RagRetriever()
        # If chromadb not installed, _ready=False and returns empty list
        docs = retriever.retrieve_maintenance("SOH 82%", top_k=3)
        assert isinstance(docs, list)

    def test_retriever_safety_returns_list(self):
        from src.services.prescription.rag_retriever import RagRetriever
        retriever = RagRetriever()
        docs = retriever.retrieve_safety("thermal warning", top_k=2)
        assert isinstance(docs, list)
