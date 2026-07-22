# GH-24 — Prescription Evaluation Report

Golden set: 14 scenarios (`tests/fixtures/rag_golden_set.json`).
LLM-enriched: hybrid_template 0/14, hybrid_agentic 0/14 (0 means no LLM key was available — coverage/sop_overlap are still valid, faithfulness is N/A).

## Ablation — mean across golden set

| Metric | rule | hybrid_template | hybrid_agentic |
|---|---|---|---|
| SOP overlap (static, action_code-derived — same across all arms) | 0.202 | — | — |
| Coverage (retrieval recall@k) | N/A (no retrieval) | 0.488 | 0.488 |
| Faithfulness (semantic overlap) | N/A (no retrieval) | N/A | N/A |
| RAG latency (ms) | 0.000 | 258.164 | 29.816 |
| LLM latency (ms) | 0.000 | 0.000 | 0.000 |
| Query-gen latency (ms) | 0.000 | 0.000 | 0.000 |

## Per-scenario

| id | sop_overlap | template coverage | template faithfulness | agentic coverage | agentic faithfulness |
|---|---|---|---|---|---|
| eol-immediate-replacement | 0.500 | 0.500 | N/A | 0.500 | N/A |
| thermal-runaway-critical | 0.000 | 0.667 | N/A | 0.667 | N/A |
| overvoltage-charging | 0.000 | 0.333 | N/A | 0.333 | N/A |
| undervoltage-discharge | 0.000 | 0.000 | N/A | 0.000 | N/A |
| overcurrent-load | 0.000 | 0.333 | N/A | 0.333 | N/A |
| degrading-schedule-replacement | 0.333 | 0.667 | N/A | 0.667 | N/A |
| early-degradation-inspection | 0.500 | 1.000 | N/A | 1.000 | N/A |
| healthy-monitor | 0.500 | 0.500 | N/A | 0.500 | N/A |
| temp-elevated-ventilation | 0.000 | 0.500 | N/A | 0.500 | N/A |
| soc-soh-mismatch | 0.500 | 1.000 | N/A | 1.000 | N/A |
| connectivity-dropout | 0.000 | 0.000 | N/A | 0.000 | N/A |
| humidity-corrosion | 0.000 | 0.500 | N/A | 0.500 | N/A |
| lifepo4-12v-pack | 0.500 | 0.500 | N/A | 0.500 | N/A |
| smoke-detected-emergency | 0.000 | 0.333 | N/A | 0.333 | N/A |
