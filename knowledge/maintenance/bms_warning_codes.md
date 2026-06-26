# BMS Warning Codes Reference

## Voltage Warnings
- VOLTAGE_LOW (3.0-3.2V): Approaching cutoff, reduce load
- VOLTAGE_CRITICAL (<3.0V): Stop discharge immediately, risk of cell damage
- OVERVOLTAGE (>4.15V): Check charger settings
- OVERVOLTAGE_CRITICAL (>4.2V): Stop charging immediately, overcharge risk

## Temperature Warnings
- TEMP_ELEVATED (35-45°C): Increase ventilation, reduce charge/discharge rate
- TEMP_CRITICAL (>45°C): Stop operation, allow cooling, inspect for thermal runaway precursors

## Current Warnings
- OVERCURRENT (>2A discharge): Reduce load to within 1C rating
- OVERCURRENT_CRITICAL (>3A): Emergency load disconnect

## SOH Warnings
- SOH_LOW (85-90%): Schedule inspection within 30 days
- SOH_CRITICAL (80-85%): Schedule replacement within 7 days
- BATTERY_EOL (<80%): Replace immediately

## Response Priority Matrix
| Warning | Severity | Response Time |
|---------|----------|---------------|
| BATTERY_EOL | P1 Critical | 4 hours |
| TEMP_CRITICAL | P1 Critical | 4 hours |
| VOLTAGE_CRITICAL | P1 Critical | 4 hours |
| SOH_CRITICAL | P2 High | 24 hours |
| TEMP_ELEVATED | P2 High | 24 hours |
| SOH_LOW | P3 Standard | 72 hours |
