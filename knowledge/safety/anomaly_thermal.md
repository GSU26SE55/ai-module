# Thermal Anomaly Types — Symptoms, Causes, Response

Covers 2 of the 15 AnomalyType categories (BE `AnomalyTypeEnum`) related to
temperature. Safety-critical — see also `thermal_runaway_response.md` for the
full emergency procedure once a critical threshold is crossed.

## Overheat
- **Threshold:** cell temperature > 60°C (LiFePO4), > 55°C (NMC).
- **Symptoms:** BMS `TEMP_ELEVATED`/`TEMP_CRITICAL` warning, rapid temperature
  rise rate (> 5°C/minute is a thermal-runaway precursor).
- **Causes:** high ambient temperature combined with load, ventilation
  blockage, internal short-circuit generating heat, charge/discharge rate too
  high for the thermal envelope.
- **Response:** if critical, stop operation immediately and follow
  `thermal_runaway_response.md`; if only elevated, increase ventilation and
  reduce charge/discharge rate.

## HighAmbientTemp
- **Threshold:** ambient (enclosure) temperature > 40°C.
- **Symptoms:** elevated baseline cell temperature even at low load, reduced
  effective capacity (temperature-derated).
- **Causes:** solar-site enclosure heat soak, inadequate enclosure
  ventilation/shading, seasonal peak ambient conditions.
- **Response:** derate charge/discharge rate per the enclosure's thermal
  design limit; schedule a ventilation/shading inspection if the condition
  recurs across multiple cycles rather than a single hot day.

## References
- Feng, X. et al., "Thermal runaway mechanism of lithium ion battery for
  electric vehicles", *J. Power Sources* 2018 — DOI: 10.1016/j.jpowsour.2017.10.069.
- IEEE Std 1625-2008 — Rechargeable Batteries for Portable Computing.
- IEC 62933-5-2:2020 — Electrical energy storage systems, safety requirements
  for grid-integrated EES.
- NREL TP-5400-67102 — Battery Lifetime Analysis and Simulation Tool
  (ambient-temperature derating guidance).
- NFPA 855 — Standard for the Installation of Stationary Energy Storage
  Systems (cross-reference: `thermal_runaway_response.md`).
