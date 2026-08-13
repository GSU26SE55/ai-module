# BMS Warning Codes Reference

## Voltage Warnings — per cell, chemistry-dependent

Voltage is evaluated **per cell**: pack voltage is divided by
`pack_config.n_series` before any threshold is applied. For the production
pack (LFP, 8S, 24V nominal) use the LFP column.

| Code | LFP (production) | NMC/LCO | Action |
|---|---|---|---|
| VOLTAGE_LOW | 2.5–2.8 V | 3.0–3.2 V | Approaching cutoff, reduce load |
| VOLTAGE_CRITICAL | < 2.5 V | < 3.0 V | Stop discharge immediately, risk of cell damage |
| OVERVOLTAGE | > 3.65 V | > 4.15 V | Check charger settings |
| OVERVOLTAGE_CRITICAL | > 3.8 V | > 4.2 V | Stop charging immediately, overcharge risk |

Source of truth: `CHEMISTRY_VOLTAGE_PROFILES` in
`src/models/anomaly_detector.py`. LFP values are the A123 ANR26650M1-B
datasheet limits (discharge cutoff 2.5 V, charge cutoff 3.65 V); the pack
cut-off of the deployed JK BMS is 8 × 2.5 = 20.0 V, consistent with this.

> The wider `VOLTAGE_CELL_RANGE` (2.0–4.5 V) seen elsewhere in the codebase is
> an out-of-distribution input guard, **not** a safety threshold — do not quote
> 2.0 V as an LFP undervoltage limit.

## Temperature Warnings
- TEMP_ELEVATED (35-45°C): Increase ventilation, reduce charge/discharge rate
- TEMP_CRITICAL (>45°C): Stop operation, allow cooling, inspect for thermal runaway precursors
- Above 60°C or rising > 5°C/min: runaway precursor — `thermal_runaway_response.md`,
  evacuate. Not detected by this pipeline (see `anomaly_thermal.md` limitation note).

## Current Warnings — relative to pack rated capacity

Current is **not** divided by `n_series` (series cells carry the same current),
so thresholds scale with the pack's rated capacity in Ah, not with cell count.

| Code | Threshold | Production pack (30 Ah) | Action |
|---|---|---|---|
| OVERCURRENT | discharge > 1C | > 30 A | Reduce load to within 1C rating |
| OVERCURRENT_CRITICAL | discharge > 1.5C | > 45 A | Emergency load disconnect |

> 🔴 **Known defect in the current build — do not quote absolute amps from it.**
> `CURRENT_WARNING = -2.0 A` / `CURRENT_CRITICAL = -3.0 A` are still hardcoded
> in `src/models/anomaly_detector.py` from the NASA 2 Ah single-cell dataset,
> and are compared against raw pack current without capacity scaling. On the
> 30 Ah production pack this fires `OVERCURRENT_CRITICAL` at **0.1C**, which
> escalates a perfectly normal discharge to risk=Critical / P1 with a forced
> LOTO + arc-flash prescription. Until the constants become capacity-aware,
> treat an `OVERCURRENT*` code on a pack-scale battery as unverified: check the
> reported amps against the table above before acting on it.

## SOH Warnings
- BATTERY_EOL (< 80%): Replace immediately. **The only SOH warning there is.**

A pack above 80% SOH still has its rated useful life left, so no SOH warning is
raised for it and no ticket is forced. Procurement lead time is carried by the
numeric fields instead — `prediction.cycles_to_maintenance` (cycles until 85%,
a planning lookahead) and `prediction.rul_cycles_estimate` — which BE can act on
without a ticket existing.

> **Retired:** `SOH_LOW` (85-90%) and `SOH_CRITICAL` (80-85%) are no longer
> emitted. Both carried `severity="warning"`, which reached
> `compute_risk_profile()`'s `has_warning` check and opened a P3
> `SCHEDULE_MAINTENANCE` ticket — so a pack at 88% SOH generated a maintenance
> ticket despite being healthy by the 80% EOL convention. If BE still has these
> codes in an enum, treat them as never-sent.

## Response Priority Matrix

Every `*_CRITICAL` code carries `severity="critical"`, and any critical-severity
warning forces risk=Critical / P1 in `compute_risk_profile()` — the table lists
all of them so none is silently assumed to be lower.

| Warning | Severity | Priority | Response Time |
|---------|----------|----------|---------------|
| BATTERY_EOL | critical | P1 Critical | 4 hours |
| TEMP_CRITICAL | critical | P1 Critical | 4 hours |
| VOLTAGE_CRITICAL | critical | P1 Critical | 4 hours |
| OVERVOLTAGE_CRITICAL | critical | P1 Critical | 4 hours |
| OVERCURRENT_CRITICAL | critical | P1 Critical | 4 hours |
| TEMP_ELEVATED | warning | P3 Standard | 72 hours |
| OVERVOLTAGE | warning | P3 Standard | 72 hours |
| OVERCURRENT | warning | P3 Standard | 72 hours |
| VOLTAGE_LOW | warning | P3 Standard | 72 hours |

> Any `severity="warning"` code lands on P3 `SCHEDULE_MAINTENANCE`; P2 is now
> reached only by `anomaly_status = "Anomaly"` (IsolationForest sensor pattern),
> not by any SOH band.

## Codes this pipeline does NOT emit
`generate_warnings()` only sees voltage / current / temperature (+ SOH). The
codes above are the complete set it can produce. Anything else described in the
anomaly documents — humidity, smoke/water (`anomaly_environmental.md`), cell
imbalance, internal resistance, abnormal charging (`anomaly_electrical.md`),
device offline, sensor mismatch (`anomaly_connectivity.md`) — is raised BE-side
from other data paths, never by the AI module.

## References
- NMC voltage/temperature window (3.0–4.2V, ≤45°C) per IEC 62619:2022 — Secondary lithium cells for industrial applications (safety requirements).
- LFP voltage window (2.5–3.65V nominal operating, 3.8V damage threshold): A123 ANR26650M1-B datasheet — the cell used in the Severson et al. 2019 dataset this project's LFP artifacts train on.
- C-rate–based current limits: Plett, G., *Battery Management Systems Vol. 1*, ch. 2 (C-rate definition); pack rating per the deployed JK BMS spec.
- UL 1973 — Batteries for Use in Stationary and Motive Auxiliary Power Applications (abnormal operating condition limits).
- Response-time tiers (P1 4h / P2 24h / P3 72h) map to the project SLA policy in `.claude/rules/design.md`.
