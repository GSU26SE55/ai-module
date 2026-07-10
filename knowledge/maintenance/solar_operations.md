# Solar-Specific Operations — Daily Cycling & Seasonal Inspection

Battery packs in this system charge/discharge on a daily solar cycle rather
than the continuous-load pattern of many industrial battery deployments.
This document covers the operational patterns specific to that cycle.

## Daily Charge/Discharge Cycling
- Typical pattern: charge during daylight generation hours, discharge
  overnight/during low-generation periods — one full cycle per day under
  normal operation.
- A day with abnormally low generation (heavy cloud cover, panel
  soiling/shading) can produce a partial-charge cycle, which if repeated
  compounds into a `LowSoc` condition (see `anomaly_soc_soh.md`) even without
  any single anomalous reading.
- Partial-cycling over many days accelerates capacity fade compared to full
  cycles at the same total throughput — worth noting in a prescription when
  the degradation trend correlates with a low-generation period rather than
  pure calendar aging.

## Ambient Temperature Impact
- Outdoor solar-site enclosures see wider ambient swings than an
  indoor/climate-controlled deployment — both diurnal (day/night) and
  seasonal.
- High ambient combined with daytime charging load is the most common
  trigger for `HighAmbientTemp`/`Overheat` conditions at solar sites (see
  `anomaly_thermal.md`) — charging is exactly when internal heat generation
  and peak ambient temperature tend to coincide.
- Cold-start conditions (early morning, winter) can reduce effective charge
  acceptance — a lower-than-expected charge current at cycle start is not
  automatically an `AbnormalCharging` fault if ambient temperature explains it.

## Seasonal Inspection Guidance
- Pre-wet-season: verify enclosure seals and desiccant before the humidity
  season (see `anomaly_environmental.md` — HighHumidity/HighTempHumidityCombo
  risk increases materially in wet season for outdoor sites).
- Pre-high-ambient season: verify ventilation/shading before the hottest
  months, since `HighAmbientTemp` derating reduces effective site capacity
  when least expected (peak cooling-load season).
- Post-season inspection: compare degradation-rate trend across the season
  transition — a step-change in `degradation_rate_per_cycle` coinciding with
  a seasonal transition is a signal to check enclosure environmental
  controls rather than assume pure cell aging.

## References
- Ledmaoui, K. et al., "Review of Recent Advances in Predictive Maintenance
  for Solar Plants", *Sensors* (MDPI) 2025 — review of 506 papers, confirms
  real-time monitoring/alerting need for solar deployments; already cited in
  `.claude/docs/ai-research-references.md` §6.
- Bitam, S. et al., "AIoT for Next-Generation Predictive Maintenance",
  *Sensors* (MDPI) 2025 — already cited in `.claude/docs/ai-research-references.md` §7.
- Markov-Constrained Isolation Forest for Early Detection of Battery
  Anomalies in Solar-Grid, *MDPI Mathematics* 2025 — already cited in
  `.claude/docs/ai-research-references.md` §5 (same solar-battery domain as
  this project's Isolation Forest anomaly detector).
