import logging
import threading
import time

import numpy as np
import torch

_MC_LOCK = threading.RLock()  # protects model.train()/eval() during MC Dropout
logger = logging.getLogger(__name__)

from src.core import model_loader
from src.core.config import (
    BASE_FEATURES,
    CAUSAL_RATE_K,
    CYCLE_COUNT_NORM,
    FEATURES,
    INPUT_FEATURES,
    LFP_CYCLE_COUNT_NORM,
    LFP_MODEL_VERSION,
    MODEL_VERSION,
    NOMINAL_CAPACITY_AH,
    TEMPERATURE_OOD_THRESHOLD,
    WINDOW_SIZE,
)
from src.features.extractor import (
    compute_ic_curve_and_discharge_progress,
    compute_soc_percent,
    extract_window_features,
)
from src.models.anomaly_detector import (
    classify_anomaly,
    classify_anomaly_status,
    classify_health_stage_probabilistic,
    compute_degradation_metrics,
    compute_risk_profile,
    generate_warnings,
    temperature_domain_distance,
)
from src.services import battery_history

_FEATURE_NAMES = FEATURES  # single source of truth: src/core/config.py


class _Artifacts:
    """The scaler/model/iso-forest triple plus the constants that must match them.

    Bundled rather than read from module globals at each use site because the two
    sets differ in more than weights: LFP normalises cycle_count by 2300 (Severson
    cells run 150-2300 cycles) while NASA uses 200 (~197 max). Reading the model
    from one set and the constant from the other would shift that input channel
    with no error raised anywhere — the exact silent-mismatch class of bug this
    codebase keeps hitting.
    """

    __slots__ = ("scaler", "feature_scaler", "soh_model", "iso_model",
                 "cycle_count_norm", "artifact_set", "model_version", "soc_mode")

    def __init__(self, scaler, feature_scaler, soh_model, iso_model,
                 cycle_count_norm, artifact_set, model_version, soc_mode="window"):
        self.scaler = scaler
        self.feature_scaler = feature_scaler
        self.soh_model = soh_model
        self.iso_model = iso_model
        self.cycle_count_norm = cycle_count_norm
        self.artifact_set = artifact_set
        self.model_version = model_version
        self.soc_mode = soc_mode


def _resolve_artifacts(chemistry: str | None) -> _Artifacts:
    """Pick the artifact set for this request (GH-67 chemistry-aware selection).

    chemistry is already normalised to "LFP"/"NMC"/None by the PackConfig validator.
    Anything that is not "LFP" keeps the NASA/NMC default, so every existing caller
    and test is unaffected.

    Raises when "LFP" is requested but its artifacts are missing: scoring LFP
    telemetry with NASA weights would be a silent wrong prediction, which
    .claude/rules/tech/ai.md explicitly requires failing on instead.
    """
    if chemistry == "LFP":
        if model_loader.lfp_soh_model is None:
            raise RuntimeError(
                "chemistry='LFP' requested but the LFP artifact set is not loaded. "
                "Ensure models/weights/{scaler_lfp.pkl,feature_scaler_lfp.pkl,"
                f"soh_mamba_v{LFP_MODEL_VERSION}.pth,isolation_forest_v{LFP_MODEL_VERSION}.pkl}} "
                "exist — refusing to score LFP data with the NASA/NMC model."
            )
        return _Artifacts(
            model_loader.lfp_scaler, model_loader.lfp_feature_scaler,
            model_loader.lfp_soh_model, model_loader.lfp_iso_model,
            LFP_CYCLE_COUNT_NORM, "LFP", LFP_MODEL_VERSION,
            model_loader.lfp_soc_mode,
        )
    return _Artifacts(
        model_loader.scaler, model_loader.feature_scaler,
        model_loader.soh_model, model_loader.iso_model,
        CYCLE_COUNT_NORM, "NASA", MODEL_VERSION,
    )


def _expected_feature_count(art: _Artifacts) -> int:
    """Feature count expected FROM THE PAYLOAD (= scaler width, base features).

    GH-54: model input = base + 2 derived columns computed server-side, so when
    falling back to the model dim, subtract the derived columns."""
    if hasattr(art.scaler, "n_features_in_"):
        return int(art.scaler.n_features_in_)
    if hasattr(art.soh_model, "input_features"):
        n = int(art.soh_model.input_features)
        return n - 2 if n == len(BASE_FEATURES) + 2 else n
    return 3


def _align_features(x: np.ndarray, art: _Artifacts) -> np.ndarray:
    expected = _expected_feature_count(art)
    actual = x.shape[1]
    if actual == expected:
        return x
    if actual > expected:
        return x[:, :expected]
    raise ValueError(
        f"readings provide {actual} features, but loaded artifacts expect {expected}. "
        "Run preprocessing/training for the expanded feature set or send the legacy feature set."
    )


def _compute_feature_summary(raw: np.ndarray) -> dict:
    """Mean/min/max for each sensor column in raw (unscaled) readings."""
    summary = {}
    n = min(raw.shape[1], len(_FEATURE_NAMES))
    for i in range(n):
        col = raw[:, i].astype(float)
        summary[_FEATURE_NAMES[i]] = {
            "mean": round(float(col.mean()), 4),
            "min": round(float(col.min()), 4),
            "max": round(float(col.max()), 4),
        }
    return summary


def _raw_cycle_count(raw: np.ndarray, cycle_idx: int | None) -> float | None:
    """GH-56/GH-95: the battery's cycle number for this window, or None if unknown.

    Same source of truth _append_derived_features() uses internally for
    cycle_count_norm — factored out so GH-95's battery_history (which needs
    the raw, un-normalized count) doesn't duplicate this branch.
    """
    if raw.shape[1] >= len(BASE_FEATURES) + 2:
        return float(raw[0, len(BASE_FEATURES)])
    return float(cycle_idx) if cycle_idx is not None else None


def _append_derived_features(
    x_scaled: np.ndarray, raw: np.ndarray, cycle_idx: int | None, art: _Artifacts
) -> np.ndarray:
    """GH-54: append cycle_count_norm + soc_percent/100 as columns 5-6.

    Only when the loaded model expects exactly 2 more channels than the scaler
    provides (v1.4+ artifacts) — legacy models keep the scaled input as-is.

    GH-56: if the payload already carries 6 columns, BE computed cycle_count
    (raw cycle index) + soc_percent (raw 0-100, from the battery's full
    charge/discharge history — more accurate than this window-local estimate)
    directly, so use them as-is instead of re-deriving. Legacy 3/4-column
    payloads fall back to the previous behaviour: cycle_idx / CYCLE_COUNT_NORM
    (0.0 when the caller doesn't know the cycle) and window-local
    Coulomb-counting SOC / 100.
    """
    model_dim = getattr(art.soh_model, "input_features", x_scaled.shape[1])
    if model_dim != x_scaled.shape[1] + 2:
        return x_scaled
    if raw.shape[1] < len(BASE_FEATURES):
        raise ValueError(
            f"model expects {model_dim} features (incl. derived soc_percent) but the "
            f"payload has only {raw.shape[1]} columns — the 'time' column is required."
        )
    raw_cycle_count = _raw_cycle_count(raw, cycle_idx)
    if raw.shape[1] >= len(BASE_FEATURES) + 2:
        # GH-56: BE sends cycle_count (constant across the window) + soc_percent
        # (per-timestep) directly as columns 5-6 — no server-side derivation needed.
        cycle_count_norm = raw_cycle_count / art.cycle_count_norm
        soc_norm = raw[:, len(BASE_FEATURES) + 1] / 100.0
    else:
        # The window-local fallback defines SOC relative to THIS window, so it
        # always starts at 100% and spans ~[0.91, 1.0]. Artifacts trained with
        # soc_mode="cycle" learned soc spanning the whole discharge (~[0.09, 1.0])
        # — feeding them the fallback is a silent distribution shift on that
        # channel, and a stateless 30-row window cannot reconstruct the real value.
        if art.soc_mode == "cycle":
            raise ValueError(
                f"{art.artifact_set} artifacts were trained with soc_mode='cycle' "
                f"(soc spans the full discharge), but this payload has "
                f"{raw.shape[1]} columns so soc_percent has to be estimated "
                "window-locally — which the model never saw. Send the 6-column "
                "payload (voltage, current, temperature, time, cycle_count, "
                "soc_percent) with the battery's real SOC."
            )
        current = raw[:, BASE_FEATURES.index("current")]
        time_col = raw[:, BASE_FEATURES.index("time")]
        soc_norm = compute_soc_percent(current, time_col, NOMINAL_CAPACITY_AH) / 100.0
        cycle_count_norm = 0.0 if raw_cycle_count is None else raw_cycle_count / art.cycle_count_norm

    # GH-59: the divisor is fit to each dataset's observed max cycle count (NASA
    # ~197 -> 200; Severson/LFP up to ~2300). A real battery outliving that goes
    # out of the range the model was trained on (extrapolation). Clip to keep the
    # feature in-distribution; log so production data can later inform whether the
    # divisor should be raised.
    if raw_cycle_count is not None and not (0 <= raw_cycle_count <= art.cycle_count_norm):
        logger.warning(
            "cycle_count=%s outside expected range [0, %s] (%s artifacts) — "
            "clipping cycle_count_norm to [0, 1]",
            raw_cycle_count,
            art.cycle_count_norm,
            art.artifact_set,
        )
    cycle_count_norm = np.float32(np.clip(cycle_count_norm, 0.0, 1.0))

    return np.column_stack(
        [
            x_scaled,
            np.full(len(x_scaled), cycle_count_norm, dtype=np.float32),
            soc_norm,
        ]
    )


def run_inference(
    readings: list[list[float]],
    cycle_idx: int | None = None,
    n_series: int = 1,
    battery_id: str | None = None,
    chemistry: str | None = None,
    capacity_ah: float | None = None,
) -> dict:
    """
    Full inference pipeline: scale → Mamba SOH → IsolationForest → classify.

    Args:
        readings:   (30, 6) preferred — BE sends cycle_count + soc_percent directly
                    as columns 5-6 (GH-56); (30, 4) or legacy (30, 3) also accepted,
                    in which case the 2 derived columns are computed server-side
                    (GH-54: window-local Coulomb counting + cycle_idx below).
        cycle_idx:  0-based discharge-cycle number of this battery, only used when
                    readings has 4 (or 3) columns (default None → cycle_count feature = 0).
                    Ignored when readings already carries 6 columns.
        n_series:   GH-65: cells in series (pack_config.n_series). Voltage arrives as
                    pack voltage and is divided per-cell HERE, before the scaler and
                    before warning thresholds — so a 12V/3S pack is scored on the
                    ~4V cell distribution the model was trained on. 1 = single cell
                    (default, legacy behavior unchanged).
        battery_id: GH-95 — key into src/services/battery_history.py's per-battery
                    SOH history, used to compute a causal degradation rate (this
                    battery vs. its own last CAUSAL_RATE_K recorded cycles). None/
                    missing → causal_rate is None, classify_anomaly() behaves exactly
                    as before GH-95.
        chemistry:  GH-67 (pack_config.chemistry) — selects the per-cell voltage
                    warning profile ("LFP" for LiFePO4). None/unknown → NASA/NMC
                    thresholds (legacy behavior).
        capacity_ah: GH-67 (pack_config.capacity_ah) — pack nominal capacity. When
                    set, current is rescaled to the NASA 2 Ah cell's C-rate
                    equivalent (current × 2.0 / capacity_ah) the same way voltage
                    is divided per-cell: in-place on raw, before the scaler,
                    warnings and feature_summary. A series pack keeps its real
                    current, but the scaler + current thresholds were fit on the
                    2 Ah amp scale. None = no rescale (legacy behavior).

    Returns:
        dict with soh_percent, classification, confidence, inference_ms,
        rul_cycles_estimate, anomaly_score, recommended_action,
        warnings, feature_summary
    """
    start = time.perf_counter()

    # GH-67: pick the artifact set BEFORE anything touches a scaler/model, so the
    # scaler, the model and cycle_count_norm can never come from different sets.
    art = _resolve_artifacts(chemistry)

    raw = np.array(readings, dtype=np.float32)  # (30, F) — keep for warnings + summary
    if n_series > 1:
        # GH-65: pack → per-cell voltage. In-place on the raw copy so EVERYTHING
        # downstream (scaler, anomaly thresholds, feature_summary) sees per-cell
        # values; temperature stays as sent.
        raw[:, BASE_FEATURES.index("voltage")] /= n_series
    if capacity_ah:
        # GH-67: pack current → NASA-2Ah C-rate equivalent, same in-place pattern
        # as the voltage division above. This also keeps the Coulomb-counting SOC
        # fallback in _append_derived_features() correct WITHOUT touching it:
        # ∫|I×2/C|dt / 2Ah  ==  ∫|I|dt / C_real.
        raw[:, BASE_FEATURES.index("current")] *= NOMINAL_CAPACITY_AH / capacity_ah
    x = _align_features(raw, art)  # (30, F_scaler)
    x_scaled = art.scaler.transform(x)
    x_model = _append_derived_features(x_scaled, raw, cycle_idx, art)  # (30, 6) — GH-54
    x_tensor = torch.tensor(x_model, dtype=torch.float32).unsqueeze(0)

    # Cycle-level features: compute from scaled window (first 3 channels: voltage, current, temp)
    # Matches SPECTRAL_FEAT_DIM=57 config (10 spectral incl. Gini + 9 statistical × 3 channels).
    raw_feat = extract_window_features(x_scaled[:, :3])  # (57,)
    feat_scaled = art.feature_scaler.transform(raw_feat.reshape(1, -1))
    x_feat_tensor = torch.tensor(feat_scaled, dtype=torch.float32)  # (1, 57)

    # MC Dropout: MC_RUNS stochastic samples (Dropout ON) in ONE batched forward
    # pass, not a python loop of single-sample calls — measured 295ms -> 120ms on
    # the real model (GH-62). Same statistics (each row independently samples its
    # own dropout mask), just batched compute instead of sequential.
    # GH-63: 20 -> 10 to close the remaining latency gap (measured ~126ms -> ~60ms
    # for the forward pass alone) — fewer MC samples means a noisier soh_std/
    # soh_confidence estimate, but still enough for the intended use (flagging low-
    # confidence predictions), verified against the 20-sample baseline on demo payloads.
    # Lock prevents concurrent requests from corrupting model train/eval state
    MC_RUNS = 10
    with _MC_LOCK:
        art.soh_model.train()  # enable Dropout
        try:
            with torch.no_grad():
                xb = x_tensor.repeat(MC_RUNS, 1, 1)
                xfb = x_feat_tensor.repeat(MC_RUNS, 1)
                mc_preds = (art.soh_model(xb, xfb) * 100).tolist()
        finally:
            art.soh_model.eval()  # always restore eval mode

    soh = float(max(0.0, min(100.0, float(np.mean(mc_preds)))))
    soh_std = float(np.std(mc_preds))
    # confidence: std=0% → 1.0, std=5% → 0.0 (linear scale)
    soh_confidence = round(float(max(0.0, min(1.0, 1.0 - soh_std / 5.0))), 3)
    # GH-86: threshold decisions use the median (robust to MC outliers with
    # n=10); soh_percent stays the mean so reported numbers don't change.
    soh_median = float(max(0.0, min(100.0, float(np.median(mc_preds)))))

    # IsolationForest trained on spectral features (57 dims) — use same features at inference
    score = float(art.iso_model.decision_function(feat_scaled)[0])
    # GH-95: causal_rate compares soh_median to this battery's OWN recent history —
    # computed BEFORE record() below, so it only ever sees cycles strictly before
    # this request (causal, not the offline label's centered/future-peeking window).
    raw_cycle_count = _raw_cycle_count(raw, cycle_idx)
    rate = battery_history.causal_rate(
        battery_id, raw_cycle_count, soh_median, CAUSAL_RATE_K
    )
    classification = classify_anomaly(score, soh_median, causal_rate=rate)
    battery_history.record(battery_id, raw_cycle_count, soh_median)
    anomaly_confidence = round(min(1.0, max(0.0, abs(score))), 3)
    # soh_confidence already computed above via MC Dropout
    stage_info = classify_health_stage_probabilistic(mc_preds)
    health_stage = stage_info["health_stage"]
    anomaly_status = classify_anomaly_status(score)

    # Degradation metrics — battery-specific rate from multi-cycle window
    # More accurate when L >= 500 (spans multiple cycles); falls back to
    # population average (0.15%/cycle) for shorter windows.
    degradation = compute_degradation_metrics(raw, soh)
    warnings = generate_warnings(raw, soh, classification, chemistry=chemistry)
    feature_summary = _compute_feature_summary(raw)
    # GH-91: distance from the window's temperature to the nearest NASA
    # training chamber setpoint (4/24/44°C) — also drives the TEMP_OOD
    # warning inside generate_warnings() above (same helper, same threshold).
    temp_domain_dist = temperature_domain_distance(raw[:, 2])
    risk = compute_risk_profile(
        health_stage=health_stage,
        anomaly_status=anomaly_status,
        warnings=warnings,
        soh=soh,
        cycles_to_maintenance=degradation["cycles_to_maintenance"],
    )

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

    prediction = {
        "soh_percent": round(soh, 2),
        "soh_confidence": soh_confidence,  # MC Dropout uncertainty
        "soh_std": round(soh_std, 3),
        "rul_cycles_estimate": degradation["rul_cycles_estimate"],
        "degradation_rate_per_cycle": degradation["degradation_rate_per_cycle"],
        "soh_trend": degradation["soh_trend"],
        "cycles_to_maintenance": degradation["cycles_to_maintenance"],
        "soh_trajectory": degradation["soh_trajectory"],
        "health_stage": health_stage,
        # GH-86: MC-distribution staging — probability per stage, confidence of
        # the chosen stage, and a borderline flag for the gray zone near 80/85/90
        "stage_probabilities": stage_info["stage_probabilities"],
        "stage_confidence": stage_info["stage_confidence"],
        "is_borderline": stage_info["is_borderline"],
    }
    anomaly = {
        "anomaly_score": round(score, 4),
        "anomaly_status": anomaly_status,
        "anomaly_confidence": anomaly_confidence,
    }
    evidence = {
        "warnings": warnings,
        "feature_summary": feature_summary,
    }
    metadata = {
        "model_version": art.model_version,
        "artifact_set": art.artifact_set,  # GH-67: NASA vs LFP weights actually used
        "window_size": WINDOW_SIZE,
        "input_features": INPUT_FEATURES,
        "inference_ms": elapsed_ms,
        "n_series": n_series,  # GH-65: trace which pack→cell divisor was applied
        # GH-67: trace which voltage profile / C-rate divisor were applied
        # (None = NASA/NMC defaults) — the real-battery validation logs need this.
        "chemistry": chemistry,
        "capacity_ah": capacity_ah,
        "temperature_domain_distance": round(temp_domain_dist, 2),  # GH-91
        "is_temperature_ood": temp_domain_dist > TEMPERATURE_OOD_THRESHOLD,  # GH-91
    }

    return {
        "prediction": prediction,
        "anomaly": anomaly,
        "risk": risk,
        "evidence": evidence,
        "metadata": metadata,
        # Backward-compatible flat fields — derived from the nested blocks above
        # (single source of truth) so the two shapes can't drift apart. Keep
        # until BE migrates to the nested response.
        "soh_percent": prediction["soh_percent"],
        "classification": classification,
        "confidence": prediction["soh_confidence"],
        "inference_ms": metadata["inference_ms"],
        "rul_cycles_estimate": prediction["rul_cycles_estimate"],
        "degradation_rate_per_cycle": prediction["degradation_rate_per_cycle"],
        "soh_trend": prediction["soh_trend"],
        "cycles_to_maintenance": prediction["cycles_to_maintenance"],
        "soh_trajectory": prediction["soh_trajectory"],
        "anomaly_score": anomaly["anomaly_score"],
        "recommended_action": risk["action_code"],
        "warnings": evidence["warnings"],
        "feature_summary": evidence["feature_summary"],
    }


def _add_long_derived_features(x: np.ndarray) -> np.ndarray:
    """Append ic_curve + discharge_progress to a raw (L, 4) window for the long-seq model.

    x may span multiple concatenated discharge cycles (production sends whatever
    window the caller has). Training computes both derived columns PER CYCLE,
    before concatenating cycles into a battery timeline (scripts/preprocess_long.py)
    — so this detects cycle boundaries via resets in the "time" column (time[i] <
    time[i-1] marks a new cycle) and computes each segment independently, instead
    of integrating straight through the voltage/current discontinuity at the
    boundary. A window with no resets (single cycle) is treated as one segment.
    """
    time_col = BASE_FEATURES.index("time")
    resets = np.where(np.diff(x[:, time_col]) < 0)[0] + 1
    bounds = [0, *resets.tolist(), len(x)]

    ic_parts, progress_parts = [], []
    for s, e in zip(bounds[:-1], bounds[1:]):
        ic_seg, progress_seg = compute_ic_curve_and_discharge_progress(
            x[s:e, 0], x[s:e, 1], x[s:e, time_col]
        )
        ic_parts.append(ic_seg)
        progress_parts.append(progress_seg)

    return np.column_stack(
        [x, np.concatenate(ic_parts), np.concatenate(progress_parts)]
    )


def predict_soh_long(readings: list[list[float]], device: str | None = None) -> dict:
    """Fast-path SOH inference for long sequences (L up to 4096), GH-10.

    Single forward pass (no MC-dropout) with the attention-pooling long model on
    GPU when available. Lazily loads the long artifacts on first call. Returns SOH
    only — anomaly/IsolationForest is trained on the window=30 feature distribution
    and is out of scope for the long pipeline.

    Args:
        readings: (L, 4) preferred or legacy (L, 3) raw sensor values, L up to 4096.
        device:   override device ("cpu" / "cuda"); defaults to CUDA if available.
    """
    if model_loader.long_soh_model is None or (
        device is not None and str(model_loader.long_device) != device
    ):
        model_loader.load_long_model(device)
    dev = model_loader.long_device

    start = time.perf_counter()
    raw = np.array(readings, dtype=np.float32)
    # The long path has always sized its base-feature alignment off the DEFAULT
    # scaler (both sets carry the same 4 base columns); resolving the default
    # bundle here keeps that behaviour byte-for-byte after the GH-67 refactor.
    x = _align_features(raw, _resolve_artifacts(None))  # (L, 4) — align to base features

    # Extend to 6 features: append ic_curve + discharge_progress (per-cycle,
    # matching training — see _add_long_derived_features).
    x6 = _add_long_derived_features(x)  # (L, 6)

    x_scaled = model_loader.long_scaler.transform(x6)
    x_tensor = torch.tensor(x_scaled, dtype=torch.float32).unsqueeze(0).to(dev)

    raw_feat = extract_window_features(x_scaled[:, :3])
    feat_scaled = model_loader.long_feature_scaler.transform(raw_feat.reshape(1, -1))
    x_feat_tensor = torch.tensor(feat_scaled, dtype=torch.float32).to(dev)

    with torch.no_grad():
        soh = float(model_loader.long_soh_model(x_tensor, x_feat_tensor).item()) * 100
    soh = float(max(0.0, min(100.0, soh)))
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

    return {
        "soh_percent": round(soh, 2),
        "seq_len": int(raw.shape[0]),
        "device": str(dev),
        "inference_ms": elapsed_ms,
    }
