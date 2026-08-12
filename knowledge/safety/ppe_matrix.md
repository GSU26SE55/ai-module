# PPE Matrix — Personal Protective Equipment by Hazard Level

Consolidated PPE reference so a prescription always cites a consistent
requirement set, cross-checked against `electrical_safety_sop.md` and
`thermal_runaway_response.md`. `rule_prescription.py::_BASE_PPE` and
`_ARC_FLASH_PPE` implement the "warning/electrical-critical" rows below as
the deterministic baseline — this document is the reference those constants
are grounded in, and the fuller set the LLM path can draw from for less
common combinations.

## Matrix

| Hazard | Warning tier | Critical tier |
|---|---|---|
| **Electrical** (voltage/current) | Insulated gloves (≥500V rating), safety glasses (ANSI Z87.1) | + Arc-flash rated clothing, steel-toed footwear, complete LOTO before contact |
| **Thermal** (temperature) | Insulated gloves, safety glasses *(+ infrared thermometer — a required **tool** for standoff checks, not protective equipment)* | + Full evacuation (no PPE substitutes for evacuation at thermal-runaway precursor stage — see `thermal_runaway_response.md`) |
| **Environmental** (humidity/smoke/water) | Safety glasses, gloves for corrosion-affected terminal handling | + Respiratory protection if smoke present, do not approach until fire-service clearance for a confirmed incident |
| **Physical/mechanical** (any REPLACE_IMMEDIATELY handling) | Insulated gloves, safety glasses, steel-toed footwear | Same — physical battery removal is always at minimum the warning-tier PPE set regardless of the triggering hazard |

## Base Rule (always applies)
Any procedure involving physical contact with the battery requires at
minimum: **insulated gloves (≥500V rating) + safety glasses (ANSI Z87.1)** —
this is the `_BASE_PPE` constant. `MONITOR` actions involve no physical
contact and require no PPE.

Battery terminals are live even after LOTO (`electrical_safety_sop.md`), so
the base set is not waived by "the system is isolated" — isolation removes the
load path, not the source.

## Escalation Rule
Any critical-severity electrical warning (`VOLTAGE_CRITICAL`,
`OVERVOLTAGE_CRITICAL`, `OVERCURRENT_CRITICAL`) adds **arc-flash rated
clothing** to the base set and requires completed Lockout/Tagout before any
contact — this is the `_ARC_FLASH_PPE` constant and matches
`electrical_safety_sop.md`'s Pre-Work Safety Requirements.

## References
- NFPA 70E — Standard for Electrical Safety in the Workplace (arc-flash PPE,
  energized-work boundaries); already cited in `electrical_safety_sop.md`.
- ANSI/ISEA Z87.1 — Eye and Face Protection; already cited in
  `electrical_safety_sop.md`.
- ASTM D120 — Rubber Insulating Gloves (voltage rating); already cited in
  `electrical_safety_sop.md`.
- OSHA 29 CFR 1910.147 — The Control of Hazardous Energy (Lockout/Tagout).
- NFPA 855 — Standard for the Installation of Stationary Energy Storage
  Systems (evacuation/exclusion-zone requirement for thermal/smoke incidents,
  no PPE substitute); already cited in `thermal_runaway_response.md`.
