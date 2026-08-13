# Electrical Safety SOP — Battery Maintenance

> ⚠️ **A battery cannot be de-energised.** LOTO isolates the battery *from the
> system*; the battery terminals themselves stay live for the whole job (a
> 24V 8S LFP pack sits at ≈ 26 V DC with full short-circuit current available
> behind it). Every "verify zero energy" step below applies to the **load side
> of the disconnect**, never to the battery terminals. Treat battery terminals
> as live at all times, use insulated tools, and never bridge them.

## Pre-Work Safety Requirements
1. Complete Lockout/Tagout (LOTO) procedure before any physical work
2. Verify zero energy state on the load side of the disconnect with a
   calibrated meter — battery terminals remain live and are not part of this
   verification
3. Don appropriate PPE before approaching battery system

## PPE Requirements
- Insulated gloves (minimum 500V rating)
- Safety glasses (ANSI Z87.1 rated)
- Arc flash rated clothing when working on live systems
- Steel-toed footwear

## Lockout/Tagout Procedure
1. Notify all affected personnel
2. Identify all energy sources (DC bus, AC input, auxiliary)
3. Shut down equipment using normal stop procedure
4. Isolate energy sources — open all disconnects
5. Apply lockout devices to all isolation points
6. Release/restrain stored energy (discharge capacitors). The battery's own
   stored energy cannot be released — it is restrained by isolation, not
   removed
7. Verify zero energy with meter on the load side before proceeding

## Battery Isolation Steps
1. Disconnect AC grid connection first
2. Open DC output breaker — the battery must be off-load before the BMS is
   touched, or its protection is removed while current is still flowing
3. Apply battery module isolation switches
4. Disable BMS communication (only now, with the pack already isolated)
5. Wait 5 minutes for capacitor discharge
6. Verify 0V on the **load side of the open disconnect** before contact.
   Expect full pack voltage at the battery terminals — that reading is normal
   and is not a fault. If you measure 0V *at the battery terminals*, you are
   measuring the wrong point or the meter is faulty; stop and re-check

## Emergency Response
- Fire: Evacuate, call emergency services, do NOT apply water or any agent to
  the involved cells (`thermal_runaway_response.md` — Fire Suppression)
- Thermal runaway: Evacuate 50m radius, ventilate area
- Electrocution: Do not touch victim — break circuit first
- Chemical exposure: Flush with water, seek medical attention

## human_verification_required: true
All safety procedures require verification by qualified technician before execution.

## References
- NFPA 70E — Standard for Electrical Safety in the Workplace (arc-flash PPE, energized-work boundaries).
- OSHA 29 CFR 1910.147 — The Control of Hazardous Energy (Lockout/Tagout);
  basis for treating a battery as a stored-energy source that is isolated and
  restrained rather than de-energised.
- ANSI/ISEA Z87.1 — Eye and Face Protection.
- ASTM D120 — Rubber Insulating Gloves (voltage rating).
