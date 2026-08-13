# Connectivity/Sensor Anomaly Types — Symptoms, Causes, Response

Covers 2 of the 15 AnomalyType categories (BE `AnomalyTypeEnum`) related to
data-path integrity rather than the battery's physical state — a device that
stops reporting, or two sensors disagreeing, does not necessarily mean the
battery itself is unsafe, but it means the AI prediction can no longer be
trusted until connectivity/sensor integrity is restored.

## DeviceOffline
- **Threshold:** no reading received for 10 minutes.
- **Symptoms:** gap in the sensor reading stream, prediction pipeline has no
  fresh window to score.
- **Causes:** IoT device power loss, network/gateway outage, device firmware
  crash, physical damage to the device.
- **Response:** flag the battery as "unmonitored" rather than inferring a
  health state from stale data; dispatch a connectivity check; do not
  auto-clear until a fresh reading confirms the device is back online.

## SensorMismatch
- **Threshold:** `|V_bms − V_iot| > 0.5V` or `|T_bms − T_iot| > 5°C` — the BMS
  and IoT sensor disagree beyond the tolerance for the same physical
  quantity.
- **Symptoms:** two independent readings of voltage or temperature diverge
  beyond sensor-accuracy tolerance.
- **Causes:** one sensor drifting out of calibration, wiring fault on one
  sensing path, IoT sensor placement not representative of the cell being
  measured by the BMS.
- **Response:** do not trust either reading alone until cross-validated;
  schedule a calibration check on both sensing paths; if the divergence
  correlates with a specific location, inspect wiring at that connection
  point first.

## References
- IEC 61784 — Industrial communication networks (heartbeat/timeout patterns
  informing the 10-minute DeviceOffline threshold; common Modbus TCP practice
  is a 60-300s timeout × 2-10 retries, extended here for a battery
  monitoring cadence rather than a control-loop cadence).
- IEEE Std 21451 — Smart Transducer Interface (cross-sensor validation
  pattern).
- ISO/IEC 21451-1:2010 — Information technology, smart transducer interface
  for sensors and actuators (same family — sensor data-model reference).
