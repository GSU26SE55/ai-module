# Action Code SOP — Prescription Response by action_code

## Overview
Four `action_code` values drive the rule-based prescription baseline
(`src/services/rule_prescription.py`). Each maps to a distinct SOP tier and
response window. This document is the source-of-truth reference the LLM
enrichment path retrieves when explaining *why* an action tier applies.

## MONITOR
- **Trigger:** `health_stage = Healthy`, no critical/warning-severity sensor flag.
- **Response:** Continue scheduled quarterly inspection (see
  `battery_maintenance_sop.md` §1, SOH 85-90% tier). No physical action, no PPE.
- **Re-evaluation:** Every inference cycle — trend watched for early drift into
  `SCHEDULE_MAINTENANCE`.

## SCHEDULE_MAINTENANCE
- **Trigger:** `health_stage = Degrading`, anomaly status `Warning`/`Anomaly`,
  or a critical sensor warning on an otherwise healthy battery (escalated per
  `compute_risk_profile`).
- **Response:** Monthly inspection window, within 30 days (`battery_maintenance_sop.md`
  §1-2): visual inspection, terminal voltage at rest, internal resistance
  check against baseline (>50% rise is a replacement trigger).
- **Priority:** Typically P3 Standard (72h) unless a critical warning raises it.

## SCHEDULE_REPLACEMENT
- **Trigger:** `health_stage = Maintenance Required` (SOH crossing the 80-85%
  band, see `SohDegradation` anomaly type below).
- **Response:** Plan replacement window within 7 days
  (`battery_maintenance_sop.md` §3), run a full capacity test to confirm
  remaining usable capacity, monitor SOH/temperature trend until swap.
- **Priority:** P2 High (24h).
- **Escalation:** If SOH drops below 80% before the scheduled date, escalate
  to `REPLACE_IMMEDIATELY`.

## REPLACE_IMMEDIATELY
- **Trigger:** `health_stage = End Of Life` (SOH < 80%, the project's EOL
  convention) or a critical-severity warning that maps `risk_level = Critical`.
- **Response:** Lockout/Tagout isolation (`electrical_safety_sop.md`), measure
  open-circuit voltage and surface temperature before removal, replace with an
  identical-spec unit (`battery_maintenance_sop.md` §3), record final SOH and
  replacement reason in the ticket.
- **Priority:** P1 Critical (4h) — notify manager within 1 hour of the
  escalation trigger.
- **Human verification:** Always required (`safety_gate.py`).

## References
- IEEE Std 1188-2014 — Maintenance, Testing, and Replacement of VRLA Batteries
  (interval/checklist methodology, adapted for Li-ion in this project).
- Naumann, M. et al., "Analysis and modeling of cycle aging of a commercial
  LiFePO4/graphite cell", *J. Power Sources* 2020 — DOI: 10.1016/j.jpowsour.2019.227666
  (EOL 80% SOH convention).
- EU Battery Regulation 2023/1542 — End-of-life 80% SOH threshold for EV
  battery passport, adopted here as the project's EOL convention.
- Internal: `.claude/rules/design.md` — P1/P2/P3 SLA policy (4h/24h/72h).
