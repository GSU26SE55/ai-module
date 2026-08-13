# Thermal Runaway Response Procedure

## Warning Signs
- Battery temperature > 60°C (the > 45°C `TEMP_CRITICAL` tier in
  `anomaly_thermal.md` is the *stop operation* threshold; > 60°C is the
  runaway-precursor threshold that triggers this procedure)
- Rapid temperature rise > 5°C/minute
- Swelling or deformation of cells
- Unusual odor (electrolyte vapor)
- Smoke or discoloration

## Immediate Actions (First 30 seconds)
1. EVACUATE all non-essential personnel immediately
2. Activate fire alarm
3. Call emergency services (fire department)
4. Do NOT direct water, or any extinguishing agent, onto the involved cells —
   see Fire Suppression below for what water *is* used for

## Safe Distance
- Maintain minimum 50 meter exclusion zone (site policy — see References)
- Upwind positioning only

## Fire Suppression

Read this section as a whole. The single rule is: **nothing is applied to the
involved cells; water is used only to keep neighbouring equipment cool.**

- Small fire, trained responder only: CO2 or dry powder extinguisher.
- Large fire: let the involved cells burn out under controlled conditions.
  Suppression agents do not stop a propagating cell reaction — it is
  self-oxidising.
- Cooling water is applied **only to adjacent equipment and enclosure walls**,
  to stop propagation to neighbouring modules. Never onto the involved cells,
  and never as the primary suppression agent.
- Never seal a burning lithium battery — ventilation required.

## Post-Incident
- Do not re-enter until cleared by fire services
- Document incident for RCA (Root Cause Analysis)
- Inspect all adjacent batteries before restart
- File incident report within 2 hours (site policy — see References)

## human_verification_required: true
Thermal runaway response requires immediate escalation to P1 ticket.

## References
- NFPA 855 — Standard for the Installation of Stationary Energy Storage
  Systems (fire response, ventilation, separation between ESS units).
  ⚠️ NFPA 855 specifies *installation* separation distances, not an emergency
  exclusion radius — the **50 m** figure above is this project's own
  conservative site policy, not an NFPA number. Cite it as internal policy.
- UL 9540A — Test Method for Evaluating Thermal Runaway Fire Propagation in
  Battery Energy Storage Systems (propagation-to-adjacent-module basis for the
  adjacent-equipment cooling rule).
- NFPA 921 — Guide for Fire and Explosion Investigations (post-incident RCA).
- **Water policy — internal, deliberately conservative.** Published fire-service
  guidance for Li-ion (including FAA guidance for cabin incidents) uses water
  as a *cooling* agent and does not prohibit it; this project nonetheless
  forbids applying water to involved cells by untrained staff, because staff
  here are battery technicians, not trained responders. Do not cite FAA or
  NFPA as the source of a blanket "never use water" rule — they do not say
  that. The rule above is ours.
- **Incident-report window (2 hours)** — internal policy. Note it is tighter
  than the P1 SLA of 4h in `.claude/rules/design.md`; that is intentional
  (reporting deadline ≠ resolution deadline), not a contradiction.
