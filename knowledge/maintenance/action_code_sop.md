# Action Code SOP — Prescription Response by action_code

## Overview
Three `action_code` values drive the rule-based prescription baseline
(`src/services/rule_prescription.py`). Each maps to a distinct SOP tier and
response window. This document is the source-of-truth reference the LLM
enrichment path retrieves when explaining *why* an action tier applies.

**SOH alone only ever produces `MONITOR` or `REPLACE_IMMEDIATELY`** — the split
is the 80% EOL threshold and there is nothing in between. `SCHEDULE_MAINTENANCE`
comes from *sensor* evidence (voltage/current/temperature warnings, anomalous
sensor pattern), never from a SOH band.

## MONITOR
- **Trigger:** `health_stage = Healthy` (**SOH ≥ 80%** — the whole rated life),
  no critical/warning-severity sensor flag.
- **Response:** Continue the calendar inspection interval for the battery's SOH
  (`battery_maintenance_sop.md` §1 — semi-annual ≥ 90%, quarterly 85-90%,
  monthly 80-85%). No physical action, no PPE. In the 80-85% band, start
  replacement procurement on the `cycles_to_maintenance` estimate — this is
  planning, not a ticket.
- **Re-evaluation:** Every inference cycle — trend watched for drift toward the
  80% EOL threshold.

## SCHEDULE_MAINTENANCE
- **Trigger:** anomaly status `Warning`/`Anomaly`, any warning-severity sensor
  flag, or a critical sensor warning on an otherwise healthy battery (escalated
  per `compute_risk_profile`). **Not** triggered by any SOH value above 80%.
- **Response:** Monthly inspection window, within 30 days (`battery_maintenance_sop.md`
  §1-2): visual inspection, terminal voltage at rest, internal resistance
  check against baseline (>50% rise is a replacement trigger).
- **Priority:** Typically P3 Standard (72h) unless a critical warning raises it.

## SCHEDULE_REPLACEMENT — RETIRED, never emitted
- **Status:** no longer produced by any code path. It was reachable only from
  `health_stage = "Maintenance Required"` (SOH 80-85%), a stage that no longer
  exists now that everything above the 80% EOL threshold is `Healthy`.
- **What replaced it:** the 80-85% band is `MONITOR` with a monthly inspection
  interval, and procurement lead time comes from the numeric
  `cycles_to_maintenance` field rather than from a P2 ticket
  (`battery_maintenance_sop.md` §1).
- If BE still holds this value in an enum, treat it as never-sent.

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
- NREL/TP-7A40-73822 — *Best Practices for Operation and Maintenance of Photovoltaic and Energy Storage Systems*, 3rd Ed. (NREL · Sandia National Laboratories · SunSpec Alliance, 2018) — interval/checklist methodology for PV + storage O&M.
  Free PDF: https://docs.nrel.gov/docs/fy19osti/73822.pdf
  Replaces the earlier IEEE Std 1188-2014 citation: that standard covers **VRLA
  lead-acid**, so it was the wrong chemistry AND the wrong application even though
  only its methodology was being borrowed.
- Naumann, M. et al., "Analysis and modeling of cycle aging of a commercial
  LiFePO4/graphite cell", *J. Power Sources* 2020 — DOI: 10.1016/j.jpowsour.2019.227666
  (EOL 80% SOH convention).
- EU Battery Regulation 2023/1542 — End-of-life 80% SOH threshold for EV
  battery passport, adopted here as the project's EOL convention.
- Internal: `.claude/rules/design.md` — P1/P2/P3 SLA policy (4h/24h/72h).
