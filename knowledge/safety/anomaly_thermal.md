# Thermal Anomaly Types — Symptoms, Causes, Response

Covers 2 of the 15 AnomalyType categories (BE `AnomalyTypeEnum`) related to
temperature. Safety-critical — see also `thermal_runaway_response.md` for the
full emergency procedure once a critical threshold is crossed.

## Overheat

Three tiers, not one threshold — the tier decides the response. These are the
same numbers the pipeline uses (`anomaly_detector.py` `CHEMISTRY_TEMP_PROFILES`),
so a prescription and the warning that triggered it never disagree.

**The first two tiers depend on chemistry.** A single 35/45 pair for every cell
type was wrong in a way that mattered: the project's own LFP pack, outdoors,
measured 29.0–34.5 °C — **0.5 °C below the old Elevated tier**. One warmer
afternoon and every window would raise `TEMP_ELEVATED` (`severity: "warning"` →
`risk_level` Medium/P3), i.e. a steady stream of false tickets for a pack sitting
comfortably inside its rated window.

| Tier | LFP | NMC / default | Warning code | Response |
|---|---|---|---|---|
| Elevated | > 45°C | > 35°C | `TEMP_ELEVATED` | Increase ventilation, reduce charge/discharge rate. Keep operating. |
| Critical | > 55°C | > 45°C | `TEMP_CRITICAL` | **Stop operation**, allow cooling, inspect for thermal-runaway precursors. P1. |
| Runaway precursor | > 60°C, or any rise > 5°C/minute | same | — | Treat as an incipient thermal runaway: `thermal_runaway_response.md`, evacuate first, do not approach to inspect. |

Where the LFP numbers come from — and why not simply 60 °C:

- **45 °C** is the top of the LFP **charging** window (0–45 °C, consistent across
  LiFePO4 manufacturers). Above it, charging itself is damaging, so it is the
  right place to say "reduce rate, improve ventilation".
- **55 °C** leaves a 5 °C margin below the runaway-precursor tier. Taking 60 °C
  directly as the Critical threshold would mean warning only once a fire is
  already starting.
- The **60 °C** runaway tier is the top of the LFP **discharge** window; it is a
  fire-safety mark, not an operating limit.

> ⚠️ These two numbers are derived from the LFP charge/discharge window published
> consistently by cell manufacturers, **not** from a standard — no standard
> specifies per-cell operating limits (IEC 62619 defines *safety tests*, not
> operating windows; that is the manufacturer's job). Replace them with the
> figures from this pack's own datasheet as soon as it is available; that is a
> strictly stronger source. `chemistry` is not declared → the NMC/default column
> applies.

- **Symptoms:** BMS `TEMP_ELEVATED`/`TEMP_CRITICAL` warning; rate of rise
  matters as much as the absolute value — a fast rise below 45°C is more
  alarming than a stable reading just above it.
- **Causes:** high ambient temperature combined with load, ventilation
  blockage, internal short-circuit generating heat, charge/discharge rate too
  high for the thermal envelope.
- **Chemistry note:** LFP is more thermally stable than NMC and its runaway
  onset is higher, but the *operational* limits above are deliberately
  chemistry-independent — 45°C is the charge-acceptance limit for both
  chemistries in this deployment, and a conservative single tier avoids two
  competing numbers in the field.

> ⚠️ **Known limitation (AI module).** Input validation rejects any reading
> above `TEMPERATURE_RANGE` = 60°C (`src/core/config.py`, `src/schemas/predict.py`)
> as out-of-range, so a reading in the runaway-precursor band returns a
> validation error rather than a P1 prescription. The > 60°C tier is therefore
> handled by BMS/enclosure alarms and human escalation, **not** by this
> pipeline. Do not rely on an AI prescription to catch a runaway.

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
- LFP charge window 0–45 °C / discharge window −20–60 °C: figures published
  consistently across LiFePO4 cell manufacturers (LiTime, Battle Born, EcoTree,
  Ace Battery). Manufacturer consensus, **not** a standard — see the warning
  under *Overheat*.
- NREL/TP-7A40-73822 — *Best Practices for Operation and Maintenance of
  Photovoltaic and Energy Storage Systems*, 3rd Ed. Free PDF:
  https://docs.nrel.gov/docs/fy19osti/73822.pdf
