"""
GH-24 — Prescription evaluation harness: coverage / faithfulness / ablation.

Runs the golden set (tests/fixtures/rag_golden_set.json, 14 hand-labeled
scenarios seeded by GH-82) through the real run_prescription() pipeline in
3 arms:
  - rule             enrich=False (deterministic, no RAG/LLM)
  - hybrid_template  enrich=True, agentic=False (GH-20/22 template retrieval)
  - hybrid_agentic   enrich=True, agentic=True  (GH-82 LLM query-gen)

run_inference() is monkeypatched to return each scenario's fixed
prediction/anomaly/risk/warnings dict directly. This decouples the eval from
the SOH/anomaly MODEL (that is GH-70's job, not this one) and keeps results
reproducible — MC Dropout sampling would otherwise make repeat runs vary even
with the same golden set. The prescription history store is also
monkeypatched to a throwaway tempdir so 2x14 enrich=true calls per run don't
write synthetic eval data into models/prescription_history/.

Metrics (see eval/README.md for full definitions):
  - coverage       retrieval recall@k, hybrid arms only (rule never retrieves)
  - sop_overlap    rule engine's static SOP references vs expected_sources —
                    computed ONCE per scenario (action_code-derived, identical
                    across all 3 arms — enrichment never touches sop_references)
  - faithfulness   max cosine similarity (all-MiniLM-L6-v2, same model
                    RagRetriever uses) between the generated prescription text
                    and each retrieved doc's content — only when enriched=True

Coverage and sop_overlap always run offline/CI (no LLM key needed).
Faithfulness needs an LLM key (LLM_PROVIDER_CHAIN, e.g. DEEPSEEK_API_KEY) —
without one, hybrid arms still report coverage (retrieval works standalone)
but faithfulness is None for every scenario.

Usage:
    python eval/evaluate_prescription.py                    # all 3 arms
    python eval/evaluate_prescription.py --output-dir logs/eval

Prerequisites:
    - Vector store built: python scripts/ingest_rag.py
    - For faithfulness/real hybrid text: an LLM key in .env (DEEPSEEK_API_KEY, ...)
"""
import argparse
import json
import os
import random
import sys
import tempfile
import time
from unittest.mock import patch

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.prescription import orchestrator  # noqa: E402
from src.services.prescription.history_store import PrescriptionHistoryStore  # noqa: E402
from src.services.prescription.llm import chain  # noqa: E402
from src.services.prescription.rag_retriever import RagRetriever  # noqa: E402

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

GOLDEN_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests", "fixtures", "rag_golden_set.json",
)
ARMS = ["rule", "hybrid_template", "hybrid_agentic"]
# run_inference() is mocked (see module docstring), so the actual values here
# never reach the model — any well-formed 30-timestep window works.
_DUMMY_READINGS = [[3.7, 1.0, 25.0]] * 30


def load_golden_set(path: str = GOLDEN_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["scenarios"]


def compute_recall(expected: set[str], retrieved_sources: set[str]) -> float:
    """Retrieval recall@k — |expected ∩ retrieved| / |expected|."""
    return len(expected & retrieved_sources) / len(expected) if expected else 0.0


def compute_sop_overlap(expected: set[str], sop_references: list[str]) -> float:
    """Fraction of expected_sources whose basename (e.g. "battery_maintenance_sop")
    appears in the rule engine's static sop_references text. sop_references use
    human-readable names with section refs ("battery_maintenance_sop §3 (...)"),
    not file paths, hence substring match rather than set equality."""
    if not expected:
        return 0.0
    ref_text = " ".join(sop_references).lower()
    hits = sum(
        1
        for src in expected
        if src.rsplit("/", 1)[-1].removesuffix(".md").lower() in ref_text
    )
    return hits / len(expected)


def compute_faithfulness(text: str, docs: list[dict], encoder) -> float | None:
    """Max cosine similarity between the generated text and any retrieved
    doc's content — "is at least one retrieved doc grounding this text".
    None when there is nothing to compare (no docs, or no text was generated)."""
    if not docs or not text.strip():
        return None
    text_emb = encoder.encode([text])[0]
    doc_embs = encoder.encode([d["content"] for d in docs])
    denom = np.linalg.norm(doc_embs, axis=1) * np.linalg.norm(text_emb) + 1e-9
    sims = (doc_embs @ text_emb) / denom
    return float(sims.max())


def run_scenario(scenario: dict, arm: str, history_store: PrescriptionHistoryStore) -> dict:
    """Run one golden-set scenario through the real run_prescription() pipeline
    for the given arm, with run_inference() short-circuited to the scenario's
    fixed prediction/anomaly/risk/warnings (see module docstring for why)."""
    inference_result = {
        "prediction": scenario["prediction"],
        "anomaly": scenario["anomaly"],
        "risk": scenario["risk"],
        "evidence": {"warnings": scenario["warnings"]},
        "metadata": {"inference_ms": 0.0},
    }
    with (
        patch.object(orchestrator, "run_inference", return_value=inference_result),
        patch.object(orchestrator, "_get_history_store", return_value=history_store),
    ):
        return orchestrator.run_prescription(
            _DUMMY_READINGS,
            scenario["id"],
            enrich=(arm != "rule"),
            agentic=(arm == "hybrid_agentic"),
        )


def evaluate(scenarios: list[dict], encoder) -> list[dict]:
    history_store = PrescriptionHistoryStore(path=tempfile.mkdtemp(prefix="gh24-eval-history-"))
    rows = []
    for sc in scenarios:
        expected = set(sc["expected_sources"])
        row = {"id": sc["id"], "n_expected": len(expected)}
        sop_overlap = None
        for arm in ARMS:
            result = run_scenario(sc, arm, history_store)
            if sop_overlap is None:
                sop_overlap = compute_sop_overlap(expected, result["sop_references"])
            retrieved = {d["source"] for d in result["maintenance_docs"] + result["safety_docs"]}
            row[f"{arm}_coverage"] = compute_recall(expected, retrieved) if arm != "rule" else None
            row[f"{arm}_enriched"] = result["enriched"]
            generated_text = f"{result['prescription']} {' '.join(result['action_steps'])}"
            row[f"{arm}_faithfulness"] = (
                compute_faithfulness(
                    generated_text, result["maintenance_docs"] + result["safety_docs"], encoder
                )
                if arm != "rule" and result["enriched"]
                else None
            )
            row[f"{arm}_rag_ms"] = result["rag_ms"]
            row[f"{arm}_llm_ms"] = result["llm_ms"]
            row[f"{arm}_query_gen_ms"] = result["query_gen_ms"]
        row["sop_overlap"] = sop_overlap
        rows.append(row)
    return rows


def _mean(values: list[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _fmt(v: float | None) -> str:
    return f"{v:.3f}" if v is not None else "N/A"


def write_report(rows: list[dict], output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)

    n_enriched = {
        arm: sum(1 for r in rows if r.get(f"{arm}_enriched")) for arm in ARMS if arm != "rule"
    }
    lines = [
        "# GH-24 — Prescription Evaluation Report",
        "",
        f"Golden set: {len(rows)} scenarios (`tests/fixtures/rag_golden_set.json`).",
        f"LLM-enriched: hybrid_template {n_enriched['hybrid_template']}/{len(rows)}, "
        f"hybrid_agentic {n_enriched['hybrid_agentic']}/{len(rows)} "
        "(0 means no LLM key was available — coverage/sop_overlap are still valid, "
        "faithfulness is N/A).",
        "",
        "## Ablation — mean across golden set",
        "",
        "| Metric | rule | hybrid_template | hybrid_agentic |",
        "|---|---|---|---|",
        f"| SOP overlap (static, action_code-derived — same across all arms) "
        f"| {_fmt(_mean([r['sop_overlap'] for r in rows]))} | — | — |",
    ]
    for metric, label in (
        ("coverage", "Coverage (retrieval recall@k)"),
        ("faithfulness", "Faithfulness (semantic overlap)"),
        ("rag_ms", "RAG latency (ms)"),
        ("llm_ms", "LLM latency (ms)"),
        ("query_gen_ms", "Query-gen latency (ms)"),
    ):
        cells = [_fmt(_mean([r.get(f"{arm}_{metric}") for r in rows])) for arm in ARMS]
        rule_cell = "N/A (no retrieval)" if metric in ("coverage", "faithfulness") else cells[0]
        lines.append(f"| {label} | {rule_cell} | {cells[1]} | {cells[2]} |")

    lines += [
        "",
        "## Per-scenario",
        "",
        "| id | sop_overlap | template coverage | template faithfulness "
        "| agentic coverage | agentic faithfulness |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['id']} | {_fmt(r['sop_overlap'])} "
            f"| {_fmt(r['hybrid_template_coverage'])} | {_fmt(r['hybrid_template_faithfulness'])} "
            f"| {_fmt(r['hybrid_agentic_coverage'])} | {_fmt(r['hybrid_agentic_faithfulness'])} |"
        )

    with open(os.path.join(output_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-dir", default="logs/eval")
    args = parser.parse_args()

    scenarios = load_golden_set()

    retriever = RagRetriever()
    if not getattr(retriever, "_ready", False):
        sys.exit(
            "RagRetriever not ready — install chromadb/sentence-transformers "
            "and run scripts/ingest_rag.py first."
        )
    encoder = retriever._encoder

    if not chain.is_available():
        print(
            "[WARN] No LLM provider key configured — hybrid arms will report "
            "enriched=False, faithfulness will be N/A for all scenarios. Set an "
            "LLM_PROVIDER_CHAIN key (e.g. DEEPSEEK_API_KEY) in .env for real numbers."
        )

    t0 = time.perf_counter()
    rows = evaluate(scenarios, encoder)
    elapsed = time.perf_counter() - t0

    write_report(rows, args.output_dir)
    print(f"Evaluated {len(rows)} scenarios x {len(ARMS)} arms in {elapsed:.1f}s")
    print(f"Report written to {args.output_dir}/report.md and {args.output_dir}/results.json")


if __name__ == "__main__":
    main()
