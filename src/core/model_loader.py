import os

import joblib
import torch

from src.core.config import (
    FEATURE_SCALER_PATH,
    FEATURE_SCALER_VERSION,
    ISO_FOREST_PATH,
    LONG_FEATURE_SCALER_PATH,
    LONG_MAMBA_PATH,
    LONG_MODEL_VERSION,
    LONG_PATCH_SIZE,
    LONG_PATCH_STRIDE,
    LONG_SCALER_PATH,
    MAMBA_PATH,
    MODEL_VERSION,
    SCALER_PATH,
    SCALER_VERSION,
    SPECTRAL_FEAT_DIM,
    WINDOW_SIZE,
)
from src.models.soh_predictor import MambaSOHPredictor

scaler = None
feature_scaler = None
soh_model = None
iso_model = None

# Long-sequence (GH-10) — loaded lazily on first long inference, not at startup
long_scaler         = None   # 8-feature MinMaxScaler (scaler_long.pkl)
long_feature_scaler = None
long_soh_model      = None
long_device         = None


def load_models() -> None:
    global scaler, feature_scaler, soh_model, iso_model

    for path, label in [
        (SCALER_PATH,         "MinMaxScaler"),
        (FEATURE_SCALER_PATH, "Feature StandardScaler"),
        (MAMBA_PATH,          "Mamba model"),
        (ISO_FOREST_PATH,     "Isolation Forest"),
    ]:
        if not os.path.exists(path):
            raise RuntimeError(
                f"[STARTUP] {label} artifact not found at '{path}'. "
                "Run scripts/preprocess.py + scripts/train.py and commit models/weights/ before starting."
            )

    scaler_artifact = joblib.load(SCALER_PATH)
    if scaler_artifact["version"] != SCALER_VERSION:
        raise RuntimeError(
            f"Scaler version mismatch: expected {SCALER_VERSION}, got {scaler_artifact['version']}"
        )
    scaler = scaler_artifact["scaler"]

    feat_scaler_artifact = joblib.load(FEATURE_SCALER_PATH)
    if feat_scaler_artifact["version"] != FEATURE_SCALER_VERSION:
        raise RuntimeError(
            f"Feature scaler version mismatch: expected {FEATURE_SCALER_VERSION}, "
            f"got {feat_scaler_artifact['version']}"
        )
    feature_scaler = feat_scaler_artifact["scaler"]

    checkpoint = torch.load(MAMBA_PATH, map_location="cpu", weights_only=False)
    if checkpoint["version"] != MODEL_VERSION:
        raise RuntimeError(
            f"Model version mismatch: expected {MODEL_VERSION}, got {checkpoint['version']}"
        )
    input_features = checkpoint.get("input_features", 6)
    feat_dim       = checkpoint.get("feat_dim", SPECTRAL_FEAT_DIM)
    d_model        = checkpoint.get("d_model", 64)
    d_state        = checkpoint.get("d_state", 16)
    soh_model = MambaSOHPredictor(input_features=input_features, feat_dim=feat_dim, d_model=d_model, d_state=d_state)
    soh_model.load_state_dict(checkpoint["model_state_dict"])
    soh_model.eval()
    if torch.cuda.is_available():
        try:
            # Fuses chunked scan + FiLM into single CUDA kernel — eliminates CPU-GPU ping-pong.
            # CUDA-only: compilation is lazy (first real forward pass), so a CPU attempt would
            # crash on request #1 instead of failing here — inductor's CPU backend needs a
            # C++ compiler that dev/CI boxes don't have, and there's no CPU-GPU ping-pong to fuse anyway.
            soh_model = torch.compile(soh_model, mode="reduce-overhead")
        except Exception:
            pass  # older PyTorch — fall back to eager silently
    else:
        try:
            # GH-63: production /predict runs CPU-only in many deploys — try fusing the
            # window=30 scan's Python for-loop (src/models/soh_predictor.py _selective_scan,
            # L<=32 path) via inductor. "default" (no CUDA graphs) since there's no GPU.
            # torch.compile() itself is LAZY (wrapping always "succeeds" — the backend only
            # runs on the first real forward pass), so a missing C++ toolchain or unsupported
            # Triton backend (e.g. Windows) would otherwise crash the first production
            # /predict request instead of failing here. Force it now with dummy forward
            # passes so a failure falls back to eager at STARTUP, not on request #1.
            #
            # Warm up BOTH eval (`.eval()`) and train (`.train()`, used by MC Dropout in
            # run_inference()) modes — dynamo guards on `self.training`, so compiling only
            # in eval mode would defer the train-mode graph's compilation to the first real
            # MC-Dropout call, reintroducing the exact crash-on-request-#1 risk this warm-up
            # exists to prevent.
            compiled = torch.compile(soh_model, mode="default")
            dummy_x = torch.zeros(1, WINDOW_SIZE, input_features)
            dummy_feat = torch.zeros(1, feat_dim)
            with torch.no_grad():
                compiled(dummy_x, dummy_feat)  # eval mode (soh_model.eval() above)
                compiled.train()
                compiled(dummy_x, dummy_feat)  # train mode (MC Dropout's actual path)
                compiled.eval()
            soh_model = compiled
        except Exception:
            pass  # compile unavailable/unsupported on this host — eager fallback

    iso_model = joblib.load(ISO_FOREST_PATH)


def load_long_model(device: str | None = None) -> MambaSOHPredictor:
    """Load the long-sequence model (GH-10) and its artifacts onto the best device.

    Uses a dedicated 8-feature MinMaxScaler (scaler_long.pkl) — the long model
    expects IC curve + phase mask as extra channels (features 7-8).
    Picks CUDA when available so the L=4096 scan can meet the <100ms SLA.
    """
    global long_scaler, long_feature_scaler, long_soh_model, long_device

    for path, label in [
        (LONG_SCALER_PATH,         "Long MinMaxScaler (8-feature)"),
        (LONG_FEATURE_SCALER_PATH, "Long feature scaler"),
        (LONG_MAMBA_PATH,          "Long Mamba model"),
    ]:
        if not os.path.exists(path):
            raise RuntimeError(
                f"[STARTUP] {label} artifact not found at '{path}'. "
                "Run preprocess.py with WINDOW_SIZE=4096 + train.py --long and commit models/weights/ first."
            )

    long_scaler         = joblib.load(LONG_SCALER_PATH)["scaler"]
    long_feature_scaler = joblib.load(LONG_FEATURE_SCALER_PATH)["scaler"]

    long_device = torch.device(device) if device else torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(LONG_MAMBA_PATH, map_location=long_device, weights_only=False)
    if checkpoint["version"] != LONG_MODEL_VERSION:
        raise RuntimeError(
            f"Long model version mismatch: expected {LONG_MODEL_VERSION}, got {checkpoint['version']}"
        )
    model = MambaSOHPredictor(
        input_features=checkpoint.get("input_features", 8),
        feat_dim=checkpoint.get("feat_dim", SPECTRAL_FEAT_DIM),
        d_model=checkpoint.get("d_model", 64),
        d_state=checkpoint.get("d_state", 16),
        pooling=checkpoint.get("pooling", "attention"),
        patch_size=checkpoint.get("patch_size", LONG_PATCH_SIZE),
        patch_stride=checkpoint.get("patch_stride", LONG_PATCH_STRIDE),
        attention_heads=checkpoint.get("attention_heads", 1),
    ).to(long_device)
    state_dict = checkpoint["model_state_dict"]
    if any(k.startswith("_orig_mod.") for k in state_dict):
        # Checkpoint was saved from a torch.compile()-wrapped model (train.py --compile
        # on Kaggle GPU) — compiled wrapper prefixes every key with "_orig_mod.".
        state_dict = {k.removeprefix("_orig_mod."): v for k, v in state_dict.items()}
    model.load_state_dict(state_dict)
    model.eval()
    if torch.cuda.is_available():
        try:
            # Fuses the 16-chunk scan loop into a single CUDA kernel: eliminates
            # 16 CPU→GPU roundtrips per forward pass when L=4096. CUDA-only — same
            # reasoning as load_models() above (lazy compile, no CPU C++ toolchain).
            model = torch.compile(model, mode="reduce-overhead")
        except Exception:
            pass
    long_soh_model = model
    return model
