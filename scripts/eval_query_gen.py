"""
GH-82 — Retrieval recall: template query vs agentic LLM query-gen.

Compares file-level recall of the two retrieval modes on the mini golden set
(tests/fixtures/rag_golden_set.json — hand-labeled expected KB sources per
diagnosis scenario). Numbers go into GH-82; GH-24 extends this golden set.

Usage:
    python scripts/eval_query_gen.py                  # both modes (agentic needs an LLM key)
    python scripts/eval_query_gen.py --template-only  # no LLM key needed
    python scripts/eval_query_gen.py --agentic-only

Prerequisites:
    - Vector store built: python scripts/ingest_rag.py
    - Agentic mode: DEEPSEEK_API_KEY (or another provider in LLM_PROVIDER_CHAIN)

Recall@retrieved = |expected_sources ∩ retrieved_sources| / |expected_sources|
(file-level; retrieved set = maintenance + safety docs of that mode).
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.prescription.diagnosis import build_diagnosis_statement  # noqa: E402
from src.services.prescription.llm import chain  # noqa: E402
from src.services.prescription.orchestrator import (  # noqa: E402
    _build_maintenance_query,
    _build_safety_query,
    _multi_query_retrieve,
)
from src.services.prescription.rag_retriever import RagRetriever  # noqa: E402

GOLDEN_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests", "fixtures", "rag_golden_set.json",
)


def _recall(expected: set[str], docs: list[dict]) -> float:
    retrieved = {d.get("source", "") for d in docs}
    return len(expected & retrieved) / len(expected) if expected else 0.0


def run_template(retriever: RagRetriever, scenario: dict) -> list[dict]:
    """Current production behavior: 1 template query per collection (top 3+2)."""
    maint = retriever.retrieve_maintenance(
        _build_maintenance_query(scenario["prediction"], scenario["risk"]), top_k=3)
    safety = retriever.retrieve_safety(
        _build_safety_query(scenario["warnings"]), top_k=2)
    return maint + safety


def run_agentic(retriever: RagRetriever, scenario: dict) -> tuple[list[dict], list[str], float]:
    """Agentic chain: diagnosis → LLM query-gen → multi-query retrieval (same
    helpers as the orchestrator, so numbers reflect production behavior)."""
    diagnosis = build_diagnosis_statement(
        scenario["prediction"], scenario["anomaly"], scenario["risk"], scenario["warnings"])
    t0 = time.perf_counter()
    q = chain.generate_queries(diagnosis, budget_s=chain.QUERYGEN_BUDGET_S)
    query_gen_ms = (time.perf_counter() - t0) * 1000
    maint_q = [s for s in q.get("maintenance_queries", []) if s.strip()]
    safety_q = [s for s in q.get("safety_queries", []) if s.strip()]
    maint = _multi_query_retrieve(retriever.retrieve_maintenance, maint_q, top_k=2, cap=5)
    safety = _multi_query_retrieve(retriever.retrieve_safety, safety_q, top_k=2, cap=3)
    return maint + safety, maint_q + safety_q, query_gen_ms


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-only", action="store_true")
    parser.add_argument("--agentic-only", action="store_true")
    args = parser.parse_args()
    do_template = not args.agentic_only
    do_agentic = not args.template_only

    with open(GOLDEN_PATH, encoding="utf-8") as f:
        scenarios = json.load(f)["scenarios"]

    retriever = RagRetriever()
    if not getattr(retriever, "_ready", False):
        sys.exit("Retriever not ready — install chromadb/sentence-transformers and run scripts/ingest_rag.py first.")

    if do_agentic and not chain.is_available():
        sys.exit("Agentic mode needs an LLM key (e.g. DEEPSEEK_API_KEY) — or run with --template-only.")

    rows = []
    for sc in scenarios:
        expected = set(sc["expected_sources"])
        row = {"id": sc["id"], "n_expected": len(expected)}

        if do_template:
            row["template_recall"] = _recall(expected, run_template(retriever, sc))

        if do_agentic:
            try:
                docs, queries, qg_ms = run_agentic(retriever, sc)
                row["agentic_recall"] = _recall(expected, docs)
                row["n_queries"] = len(queries)
                row["query_gen_ms"] = round(qg_ms, 0)
            except Exception as exc:
                print(f"  [WARN] {sc['id']}: query-gen failed ({exc}) — skipping agentic cell")
                row["agentic_recall"] = None
        rows.append(row)

    # ── report ──
    header = f"{'scenario':<32}{'exp':>4}"
    if do_template:
        header += f"{'template':>10}"
    if do_agentic:
        header += f"{'agentic':>10}{'#q':>4}{'qgen_ms':>9}"
    print("\n" + header)
    print("-" * len(header))
    for r in rows:
        line = f"{r['id']:<32}{r['n_expected']:>4}"
        if do_template:
            line += f"{r['template_recall']:>10.2f}"
        if do_agentic:
            ar = r.get("agentic_recall")
            line += f"{ar if ar is not None else float('nan'):>10.2f}"
            line += f"{r.get('n_queries', 0):>4}{r.get('query_gen_ms', 0):>9.0f}"
        print(line)

    print("-" * len(header))
    if do_template:
        mean_t = sum(r["template_recall"] for r in rows) / len(rows)
        print(f"Mean template recall: {mean_t:.3f}")
    if do_agentic:
        ok = [r["agentic_recall"] for r in rows if r.get("agentic_recall") is not None]
        if ok:
            print(f"Mean agentic recall:  {sum(ok) / len(ok):.3f}  ({len(ok)}/{len(rows)} scenarios)")


if __name__ == "__main__":
    main()
