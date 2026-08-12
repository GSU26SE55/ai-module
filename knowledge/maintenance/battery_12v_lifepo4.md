# LFP Pack + Chemistry — Normalization Notes

> **Deployed pack (source of truth for every example here):** LiFePO4, **8S**,
> **24V nominal (25.6V)**, **30 Ah**, JK BMS rated 100–200 A. Sensors report
> **whole-pack voltage**, not per-cell. Earlier revisions of this document
> described a 4S/12V pack — that configuration is not deployed; ignore any
> 4S/12.8V figure still circulating in older notes.

The core Mamba SOH model trains on single-cell NASA Ames data (voltage per
cell). Field deployments use LFP *packs* (multiple cells in series) rather than
the single NMC/LCO cell the base model was trained on. This document is the
reference for both differences so the prescription layer explains findings
correctly instead of applying single-cell NMC thresholds to an LFP pack.

## Pack-to-Cell Voltage Normalization
- The deployed pack is `n_series = 8` (nominal 3.2V/cell × 8 = 25.6V pack).
  Operating span: 8 × 3.65 = **29.2V** fully charged, 8 × 2.5 = **20.0V**
  discharge cutoff.
- The API accepts `pack_config.n_series` (`src/schemas/predict.py`); voltage
  is divided by `n_series` **before** the scaler and **before** the
  per-cell voltage range check — this happens in `PredictRequest` validation,
  not inside the model itself.
- Without `pack_config`, a raw 24V pack reading is rejected as
  out-of-range for a single cell — the API returns a hint to supply
  `pack_config.n_series` (GH-65).
- **Current is not divided by `n_series`** — cells in series all carry the
  same current. Current limits therefore scale with the pack's rated capacity
  (30 Ah), not with cell count: see `bms_warning_codes.md`.
- The AI module does not infer `n_series` automatically; it must be supplied
  per-battery by the caller (BE) based on the physical pack configuration.

## LiFePO4 vs NMC Chemistry Thresholds
LFP has a flatter discharge curve and different absolute voltage windows than
NMC/LCO — applying NMC thresholds to an LFP cell will misclassify a healthy
cell as undervoltage, or vice versa.

| Parameter | NMC/LCO | LiFePO4 (LFP) |
|---|---|---|
| Cell voltage max — charge cutoff (Overvoltage) | 4.15V | 3.65V |
| Cell voltage max — damage risk (critical) | 4.2V | 3.8V |
| Cell voltage min — approaching cutoff | 3.2V | 2.8V |
| Cell voltage min — discharge cutoff (Undervoltage critical) | 3.0V | 2.5V |
| Nominal voltage | ~3.7V | ~3.2V |
| Thermal stability | Lower — earlier thermal runaway onset | Higher — LFP is comparatively more thermally stable |

- The project's global `VOLTAGE_CELL_RANGE = (2.0, 4.5)` (`src/core/config.py`)
  is deliberately wide enough to admit both chemistries for the OOD/domain
  check — it is **not** a chemistry-specific safety threshold, and 2.0V must
  never be quoted as the LFP undervoltage limit. The chemistry-specific
  thresholds in the table above (matching `CHEMISTRY_VOLTAGE_PROFILES` in
  `src/models/anomaly_detector.py`) are what the prescription layer should cite
  for a specific pack, once chemistry is known.

## Solar LFP Field Notes
- LFP's flat discharge curve means voltage alone is a poor SOC proxy near
  mid-charge — rely on the SOH model's trend output rather than a single
  voltage snapshot when advising on charge state for an LFP pack.
- LFP tolerates a wider daily solar charge/discharge cycle count than NMC
  before comparable capacity fade — see `solar_operations.md` for the
  cycling-pattern guidance this affects.

## References
- A123 ANR26650M1-B datasheet — LFP cell limits (3.2V/cell nominal, 2.5V
  discharge cutoff, 3.65V charge cutoff); the cell behind the Severson et al.
  2019 dataset this project's LFP artifacts train on. Same set cited in
  `anomaly_electrical.md` (Plett *BMS Vol. 1* ch. 2; IEC 62133-2:2017).
- Deployed hardware spec — LFP 8S / 24V / 30 Ah, JK BMS 100–200 A.
- GH-65 (`feat/GH-65-pack-to-cell-ood-guard`) — pack-to-cell voltage
  normalization implementation, `src/schemas/predict.py`.
- GH-67 — LFP field-accuracy validation and chemistry-mismatch limitation
  documentation.

> 📝 **Filename note.** This file is still named `battery_12v_lifepo4.md` for
> manifest/embedding stability, but its content is the 24V 8S pack. Renaming it
> requires re-running `scripts/ingest_rag.py` (manifest keys + embeddings) —
> left as a separate decision.
