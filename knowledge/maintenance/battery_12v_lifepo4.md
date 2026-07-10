# 12V Pack + LiFePO4 — Chemistry & Normalization Notes

The core Mamba SOH model trains on single-cell NASA Ames data (voltage per
cell). Field deployments commonly use 12V *packs* (multiple cells in series)
and LiFePO4 (LFP) chemistry rather than the NMC/LCO chemistry the model was
trained on. This document is the reference for both differences so the
prescription layer explains findings correctly instead of applying single-cell
NMC thresholds to a 12V LFP pack.

## Pack-to-Cell Voltage Normalization
- A 12V LiFePO4 pack is typically `n_series = 4` cells in series (nominal
  3.2V/cell × 4 ≈ 12.8V pack).
- The API accepts `pack_config.n_series` (`src/schemas/predict.py`); voltage
  is divided by `n_series` **before** the scaler and **before** the
  per-cell voltage range check — this happens in `PredictRequest` validation,
  not inside the model itself.
- Without `pack_config`, a raw 12V pack reading is rejected as
  out-of-range for a single cell — the API returns a hint to supply
  `pack_config.n_series` (GH-65).
- The AI module does not infer `n_series` automatically; it must be supplied
  per-battery by the caller (BE) based on the physical pack configuration.

## LiFePO4 vs NMC Chemistry Thresholds
LFP has a flatter discharge curve and different absolute voltage windows than
NMC/LCO — applying NMC thresholds to an LFP cell will misclassify a healthy
cell as undervoltage, or vice versa.

| Parameter | NMC/LCO | LiFePO4 (LFP) |
|---|---|---|
| Cell voltage max (Overvoltage) | 4.2V | 3.65V |
| Cell voltage min (Undervoltage) | 2.5V | 2.0V |
| Nominal voltage | ~3.7V | ~3.2V |
| Thermal stability | Lower — earlier thermal runaway onset | Higher — LFP is comparatively more thermally stable |

- The project's global `VOLTAGE_CELL_RANGE = (2.0, 4.5)` (`src/core/config.py`)
  is deliberately wide enough to admit both chemistries for the OOD/domain
  check — it is not a chemistry-specific safety threshold. The
  chemistry-specific Overvoltage/Undervoltage thresholds above (from
  `anomaly_electrical.md`) are what the prescription layer should cite for a
  specific pack, once chemistry is known.

## Solar 12V/LiFePO4 Field Notes
- LFP's flat discharge curve means voltage alone is a poor SOC proxy near
  mid-charge — rely on the SOH model's trend output rather than a single
  voltage snapshot when advising on charge state for an LFP pack.
- LFP tolerates a wider daily solar charge/discharge cycle count than NMC
  before comparable capacity fade — see `solar_operations.md` for the
  cycling-pattern guidance this affects.

## References
- Manufacturer/industry-standard nominal voltage conventions for LiFePO4
  (3.2V/cell nominal, 2.0-3.65V safe window) — consistent with the
  Undervoltage/Overvoltage citation set in `anomaly_electrical.md` (Plett
  *BMS Vol. 1* ch. 2; IEC 62133-2:2017).
- GH-65 (`feat/GH-65-pack-to-cell-ood-guard`) — pack-to-cell voltage
  normalization implementation, `src/schemas/predict.py`.
- GH-67 — 12V field-accuracy validation and chemistry-mismatch limitation
  documentation.
