# Battery Maintenance Standard Operating Procedure

## 1. Scheduled Maintenance Intervals
- SOH 85-90%: Quarterly inspection
- SOH 80-85%: Monthly inspection, plan replacement
- SOH < 80%: Immediate replacement required

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
- IEEE Std 1188 — Recommended Practice for Maintenance, Testing, and Replacement (interval/checklist methodology, adapted for Li-ion).
- 80% SOH End-of-Life threshold: standard convention in Li-ion degradation literature; aligns with the NASA Ames dataset EOL definition used by this project's SOH model.
