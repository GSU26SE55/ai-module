# SOC/SOH Anomaly Types — Symptoms, Causes, Response

Covers 2 of the 15 AnomalyType categories (BE `AnomalyTypeEnum`) related to
state-of-charge and state-of-health drift. These are the anomaly types most
directly tied to the project's Mamba SOH predictor output.

## LowSoc
- **Threshold:** SOC critical 10%, SOC warning 20%.
- **Symptoms:** state-of-charge dropping toward the operational floor faster
  than the expected daily solar cycle.
- **Causes:** insufficient solar generation for the load profile (cloudy
  period, panel soiling/shading), load higher than sized for the pack,
  charge controller misconfiguration.
- **Response:** if critical (<10%), shed non-essential load immediately to
  protect the pack from deep-discharge damage; if warning tier (10-20%),
  review the load/generation balance for the site before the next cycle.

## SohDegradation
- **Threshold:** SOH < 80% = End-of-Life, the single health-stage boundary.
  Above it the pack is `Healthy` — the 80-85% and 85-90% bands are inspection
  intervals for planning, not degraded states, and raise no warning.
- **Symptoms:** gradual downward SOH trend across cycles (`degradation_rate_per_cycle`
  in the prediction output), not a single-reading spike.
- **Causes:** normal cycle aging (SEI growth, electrode degradation), thermal
  stress accumulation, incomplete charge/discharge cycling pattern.
- **Response:** map directly to `action_code_sop.md` — **≥80% → `MONITOR`**
  (inspection interval tightens with SOH but no ticket is opened),
  **<80% → `REPLACE_IMMEDIATELY`**. See `battery_maintenance_sop.md` §1 for the
  interval table. `SCHEDULE_REPLACEMENT` is retired and never emitted.

## References
- Naumann, M. et al., "Analysis and modeling of cycle aging of a commercial
  LiFePO4/graphite cell", *J. Power Sources* 2020 — DOI: 10.1016/j.jpowsour.2019.227666
  (EOL 80% convention, cycle-aging mechanism).
- NREL/TP-7A40-73822 — *Best Practices for Operation and Maintenance of Photovoltaic and Energy Storage Systems*, 3rd Ed. (NREL · Sandia National Laboratories · SunSpec Alliance, 2018) — interval/checklist methodology.
  Free PDF: https://docs.nrel.gov/docs/fy19osti/73822.pdf
  (Replaces IEEE Std 1188-2014 — that one is for **VRLA lead-acid**.)
- EU Battery Regulation 2023/1542 — EOL 80% SOH threshold for EV battery
  passport.
- UN/DOT 38.3 — Lithium battery transport (30% SoC shipment reference point;
  operational LowSoc thresholds here follow common EV/ESS ops-guide practice,
  e.g. Tesla Powerwall/Roadster operations manuals).
