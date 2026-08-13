# Battery Maintenance Standard Operating Procedure

## 1. Scheduled Maintenance Intervals
**Two health stages, split at the 80% EOL threshold.** A pack above 80% SOH
still has its rated useful life left, so it is `Healthy` and generates no
ticket. Inspection intervals below are a *calendar schedule*, not an escalation
ladder — being in a tighter interval does not mean the battery is faulty.

| SOH | `health_stage` | `action_code` | Priority | Inspection interval |
|---|---|---|---|---|
| ≥ 90% | Healthy | `MONITOR` | None | Semi-annual |
| 85-90% | Healthy | `MONITOR` | None | Quarterly |
| 80-85% | Healthy | `MONITOR` | None | Monthly + start replacement procurement |
| < 80% | End Of Life | `REPLACE_IMMEDIATELY` | P1 | Immediate replacement |

> Stage boundary is `classify_health_stage()` in
> `src/models/anomaly_detector.py` — a single threshold, `EOL_SOH` = 80%.
> `MAINTENANCE_SOH` (85%) survives only as the planning lookahead behind
> `cycles_to_maintenance`; it is not a stage boundary and raises no warning.
> A `MONITOR`/no-ticket battery can still get a ticket from a *sensor* warning
> (voltage/current/temperature) — that path is unchanged.
> Only the ≥ 90% semi-annual interval lacks an external source — see References.

## 2. Inspection Checklist
- Visual inspection for swelling, corrosion, leakage
- Terminal voltage measurement at rest
- Internal resistance measurement
- Temperature profile during discharge
- Capacity test (full discharge cycle)

## 3. Replacement Criteria
- SOH falls below 80% (EOL threshold)
- Visible physical damage
- Internal resistance increases > 50% from baseline
- Thermal anomaly detected 3+ consecutive cycles

## 4. Maintenance Tools Required
- Multimeter (precision ±0.1%)
- Battery analyzer/load tester
- Infrared thermometer
- PPE: insulated gloves, safety glasses

## 5. Documentation
- Record SOH, internal resistance, temperature at each inspection
- Log all maintenance actions in TicketService
- Upload discharge curve data for AI re-evaluation

## References
- IEEE Std 1679.1-2017 — Guide for the Characterization and Evaluation of Lithium-Based Batteries in Stationary Applications (inspection & internal-resistance criteria).
- NREL/TP-7A40-73822 — *Best Practices for Operation and Maintenance of Photovoltaic and Energy Storage Systems*, 3rd Ed. (NREL · Sandia National Laboratories · SunSpec Alliance, 2018) — interval/checklist methodology, correct chemistry AND application (PV + storage). Free PDF: https://docs.nrel.gov/docs/fy19osti/73822.pdf
- ⚠️ Previously this row cited **IEEE Std 1188** (VRLA lead-acid). It was borrowed only for methodology, but a lead-acid standard is indefensible as the basis of a lithium SOP — replaced by the line above.
- 80% SOH End-of-Life threshold: standard convention in Li-ion degradation literature; aligns with the NASA Ames dataset EOL definition used by this project's SOH model.
- ⚠️ **Semi-annual interval for the ≥ 90% Healthy tier has no external source** — it is a project default added to close a gap (the table previously had no row for Healthy batteries, so `MONITOR` pointed at the 85–90% quarterly row). Confirm with the maintenance owner before citing it as policy.
