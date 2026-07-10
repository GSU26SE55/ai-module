# Electrical Anomaly Types — Symptoms, Causes, Response

Covers 6 of the 15 AnomalyType categories (BE `AnomalyTypeEnum`) that stem
from voltage/current abnormalities. Grounded in the citation table already
established in `.claude/docs/ai-research-references.md` Phụ lục B2 §1.

## Overvoltage
- **Threshold:** cell voltage max 4.2V (NMC/LCO chemistry), 3.65V (LFP).
- **Symptoms:** BMS `OVERVOLTAGE`/`OVERVOLTAGE_CRITICAL` warning, charger
  continues past cutoff.
- **Causes:** charger setpoint misconfiguration, faulty voltage sensing, BMS
  cutoff relay failure.
- **Response:** stop charging immediately if critical (>4.2V NMC / >3.65V LFP);
  check charger settings if only elevated; log event for BMS calibration review.

## Undervoltage
- **Threshold:** cell voltage min 2.5V (NMC), 2.0V (LFP).
- **Symptoms:** BMS `VOLTAGE_LOW`/`VOLTAGE_CRITICAL` warning, capacity drop
  under load.
- **Causes:** deep discharge beyond cutoff, parasitic load left connected,
  cell degradation reducing usable capacity.
- **Response:** stop discharge immediately if below critical threshold — risk
  of irreversible cell damage; reduce load and inspect wiring for parasitic
  drains if only approaching cutoff.

## RapidDischarge
- **Threshold:** discharge current > 1C (chemistry/pack-rated C-rate).
- **Symptoms:** BMS `OVERCURRENT`/`OVERCURRENT_CRITICAL` warning, elevated
  terminal temperature during discharge.
- **Causes:** load short-circuit, undersized cabling causing current spike
  misreading, sudden high-power draw (e.g. inverter surge).
- **Response:** emergency load disconnect if critical; keep load within 1C
  rating otherwise; inspect for short-circuit path before reconnecting.

## AbnormalCharging
- **Threshold:** charge current 0.5C-1C depending on chemistry (exceeding
  manufacturer charge-rate spec).
- **Symptoms:** charge current above spec, temperature rise during charge
  cycle disproportionate to rate.
- **Causes:** charger/BMS mismatch, wrong charge profile selected for
  chemistry (NMC vs LFP charge curves differ).
- **Response:** halt charging, verify charger profile matches battery
  chemistry and rated charge current, resume only after confirming setpoint.

## HighInternalResistance
- **Threshold:** DCIR increase > 30% from baseline measurement.
- **Symptoms:** voltage sag under load greater than historical baseline,
  reduced usable capacity at same SOH%.
- **Causes:** electrolyte degradation, SEI layer growth, connector/terminal
  corrosion increasing contact resistance.
- **Response:** schedule inspection — measure DCIR against baseline
  (`battery_maintenance_sop.md` §2); >50% rise from baseline is a
  replacement-criteria trigger.

## CellImbalance
- **Threshold:** inter-cell voltage delta (ΔV) > 100mV within a pack.
- **Symptoms:** individual cell voltages diverging during charge/discharge,
  reduced effective pack capacity.
- **Causes:** manufacturing variance between cells, uneven thermal
  distribution in the pack, failing cell balancing circuit.
- **Response:** run BMS active/passive balancing cycle; if imbalance persists
  after balancing, schedule inspection of the specific out-of-range cell.

## References
- IEC 62133-2:2017 — Secondary cells, safety requirements for portable
  applications (overvoltage limits).
- Plett, G., *Battery Management Systems Vol. 1: Battery Modeling*, ch. 2, 5
  (voltage windows, C-rate definitions).
- Vetter, J. et al., "Ageing mechanisms in lithium-ion batteries",
  *J. Power Sources* 2005 — DOI: 10.1016/j.jpowsour.2005.01.006.
- Schmalstieg, J. et al., "A holistic aging model for Li(NiMnCo)O2 based
  18650 lithium-ion batteries", *J. Power Sources* 2014 — DOI: 10.1016/j.jpowsour.2014.02.012.
- IEC 62660-2:2018 — Reliability and abuse testing for EV traction batteries.
- Naumann, M. et al., "Analysis and modeling of cycle aging of a commercial
  LiFePO4/graphite cell", *J. Power Sources* 2020 — DOI: 10.1016/j.jpowsour.2019.227666.
- Lewerenz, M. et al., "Differential voltage analysis as a tool for analyzing
  inhomogeneous aging", *J. Power Sources* 2017 — DOI: 10.1016/j.jpowsour.2017.07.029.
- Plett, G., *Battery Management Systems Vol. 2: Equivalent-Circuit Methods*,
  ch. 4 (cell balancing).
