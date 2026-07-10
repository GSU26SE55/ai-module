# Environmental Anomaly Types — Symptoms, Causes, Response

Covers 3 of the 15 AnomalyType categories (BE `AnomalyTypeEnum`) driven by
enclosure environment rather than the battery's own electrical/thermal
signals. These are typically reported by IoT enclosure sensors (humidity,
smoke/water) rather than the BMS itself.

## HighHumidity
- **Threshold:** relative humidity > 85% inside the enclosure.
- **Symptoms:** condensation risk on terminals/PCB, corrosion onset on
  exposed metal contacts over repeated cycles.
- **Causes:** enclosure seal failure, inadequate desiccant/ventilation,
  seasonal humid conditions (monsoon/rainy season for outdoor solar sites).
- **Response:** inspect enclosure seals and desiccant; if corrosion is
  visible on terminals, treat as a maintenance trigger per
  `battery_maintenance_sop.md` §2 visual inspection.

## HighTempHumidityCombo
- **Threshold:** combined condition where dew point exceeds ~35°C (high
  temperature *and* high humidity together, not either alone).
- **Symptoms:** accelerated corrosion risk compared to either factor in
  isolation; potential for condensation even without a temperature swing.
- **Causes:** typically compounding — a HighAmbientTemp condition co-occurring
  with a HighHumidity condition, common in outdoor tropical solar deployments.
- **Response:** treat as elevated-priority over either single condition;
  schedule enclosure environmental inspection (ventilation + seal + desiccant)
  rather than waiting for the individual thresholds to separately trend.

## EnvironmentalIncident
- **Threshold:** binary event — smoke or water detected by enclosure sensor.
- **Symptoms:** discrete sensor trigger, not a threshold crossing.
- **Causes:** fire/thermal-runaway byproduct (smoke), flooding/leak ingress
  (water), sensor fault (rare — verify before dismissing).
- **Response:** treat as P1 immediately regardless of concurrent SOH/warning
  state — follow `thermal_runaway_response.md` for smoke, isolate power for
  water ingress before any inspection. Always requires human verification.

## References
- IEC 60068-2-78 — Environmental testing, damp heat steady state.
- MIL-STD-810H Method 507.6 — Humidity testing.
- ASHRAE Standard 90.1 — HVAC guidance for telecom/battery rooms
  (temperature-humidity combo guidance).
- NFPA 855 — Standard for the Installation of Stationary Energy Storage
  Systems (smoke/water incident response).
- UL 9540A — Test Method for Evaluating Thermal Runaway Fire Propagation in
  Battery Energy Storage Systems.
