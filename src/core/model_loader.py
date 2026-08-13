import logging
import os

import joblib
import torch

from src.core.config import (
    FEATURE_SCALER_PATH,
    FEATURE_SCALER_VERSION,
    ISO_FOREST_PATH,
    LFP_FEATURE_SCALER_PATH,
    LFP_ISO_FOREST_PATH,
    LFP_MAMBA_PATH,
    LFP_MODEL_VERSION,
    LFP_SCALER_PATH,
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
from src.core.runtime import env_bool
from src.models.soh_predictor import MambaSOHPredictor

logger = logging.getLogger(__name__)

# Default (NASA/NMC) artifact set — the names every existing caller and test binds to.
scaler = None
feature_scaler = None
soh_model = None
iso_model = None

# Long-sequence (GH-10) — loaded lazily on first long inference, not at startup
long_scaler         = None   # 8-feature MinMaxScaler (scaler_long.pkl)
long_feature_scaler = None
long_soh_model      = None
long_device         = None

# LFP chemistry variant (GH-67 Mức 2) — its own scaler/model/iso-forest, trained on
# Severson instead of NASA. Selected in run_inference() when pack_config.chemistry
# == "LFP". Loaded at startup (not lazily like the long model) because this IS a
# production hot path: BE sends chemistry="LFP" for the real 4S pack, so a lazy load
# would make the FIRST such request pay the load + torch.compile cost and risk the
# <100ms P1 SLA exactly once, unpredictably.
lfp_scaler         = None
lfp_feature_scaler = None
lfp_soh_model      = None
lfp_iso_model      = None
lfp_soc_mode       = "window"  # GH-67: how soc_percent was counted at train time


def _resolve_feat_dim(checkpoint: dict, artifact_name: str) -> int:
    """GH-67: chốt artifact khớp hợp đồng đặc trưng hiện tại của extractor.

    `extract_window_features()` trông như hàm tiện ích, nhưng nó là HỢP ĐỒNG ĐẦU
    VÀO của mọi model dùng nó. Đổi nó là đổi hồi tố hợp đồng của TẤT CẢ checkpoint
    đã lưu trước đó — và kiểu hỏng này không sập lúc thay đổi, nó nằm im.

    Ca thật: commit e3f93da (2026-06-27) thêm Gini vào `_spectral_features`, đẩy
    9 → 10 đặc trưng/kênh (3 × 18 = 54 → 3 × 19 = 57). Checkpoint RUL lưu
    2026-06-17 với feat_dim=54 chết hẳn (ma trận lớp đầu 54 × 64, đưa vào 57 số là
    lỗi shape) và không ai biết hơn một tháng. Các model khác sống sót chỉ vì
    TÌNH CỜ được train lại sau đó.

    Luôn raise khi lệch — hậu quả do CALL SITE quyết định, không cần cờ ở đây:
      · load_models()      không bọc try  ⇒ service không boot (đúng: thiếu bộ
                                            mặc định thì service vô dụng)
      · load_lfp_models()  đã bọc try     ⇒ chỉ log warning, artifact để None, và
                                            _resolve_artifacts("LFP") sẽ từ chối
                                            rơi về bộ NASA ⇒ request LFP nhận lỗi
                                            rõ ràng thay vì bị chấm sai
    """
    saved = checkpoint.get("feat_dim")
    if saved is None:
        # Artifact cũ hơn khoá này (vd soh_mamba_v1.0.pth) — không nằm trên đường
        # production, nên cảnh báo là đủ, không chặn.
        logger.warning(
            "%s khong co khoa 'feat_dim' — gia dinh %d. Artifact nay cu hon luc "
            "feat_dim duoc luu; neu no nam tren duong production thi train lai.",
            artifact_name, SPECTRAL_FEAT_DIM,
        )
        return SPECTRAL_FEAT_DIM
    if saved != SPECTRAL_FEAT_DIM:
        raise RuntimeError(
            f"{artifact_name} luu voi feat_dim={saved} nhung extract_window_features() "
            f"hien sinh {SPECTRAL_FEAT_DIM} dac trung (SPECTRAL_FEAT_DIM). Checkpoint "
            f"duoc luu TRUOC mot thay doi cua extractor (vd commit e3f93da them Gini). "
            f"Train lai artifact, hoac checkout dung commit extractor tuong ung — "
            f"KHONG sua SPECTRAL_FEAT_DIM cho khop, lam the la cham bang dac trung sai."
        )
    return saved


def load_models() -> None:
    global scaler, feature_scaler, soh_model, iso_model

    # Flush-to-zero for subnormal floats. x86 handles subnormals in microcode, which
    # is orders of magnitude slower than normal arithmetic, and the SSM recurrence
    # (h decays multiplicatively over 30 steps, x10 MC-Dropout samples) generates
    # them in bulk. Measured on this CPU, end-to-end run_inference():
    #     NASA  avg 51.0 -> 21.2 ms   p95 70.8  -> 24.6 ms
    #     LFP   avg 73.0 -> 26.5 ms   p95 101.7 -> 30.6 ms
    # The LFP p95 was BREACHING the <100ms P1 SLA before this; both sets now clear
    # it with room to spare.
    #
    # Safe to do globally: subnormals are < 1.2e-38, far below anything that can
    # move an SOH percentage. Verified empirically — with identical seeds the
    # predictions are bit-identical (max delta 0.000000% over 8 MC-Dropout draws on
    # BOTH artifact sets), so this is pure speed, not a precision trade.
    torch.set_flush_denormal(True)

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
    feat_dim       = _resolve_feat_dim(checkpoint, MAMBA_PATH)
    d_model        = checkpoint.get("d_model", 64)
    d_state        = checkpoint.get("d_state", 16)
    soh_model = MambaSOHPredictor(input_features=input_features, feat_dim=feat_dim, d_model=d_model, d_state=d_state)
    soh_model.load_state_dict(checkpoint["model_state_dict"])
    soh_model.eval()
    compile_enabled = env_bool("AI_TORCH_COMPILE", default=True)
    if not compile_enabled:
        pass
    elif torch.cuda.is_available():
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

    # Best-effort: a deploy that only ever serves NASA/NMC batteries must still boot
    # when the LFP artifacts are absent. A request that actually asks for chemistry
    # ="LFP" then fails loudly in run_inference() rather than being scored with the
    # wrong weights.
    try:
        load_lfp_models()
    except Exception as exc:
        logger.warning(
            "LFP artifacts not loaded (%s) — requests with chemistry='LFP' will fail "
            "until models/weights/*_lfp.* are present.", exc
        )


def _compile_for_inference(model: MambaSOHPredictor, input_features: int, feat_dim: int):
    """torch.compile + force the lazy backend to run now, in BOTH eval and train mode.

    Same reasoning as load_models(): compilation is deferred to the first real forward
    pass, so without this warm-up a missing C++ toolchain would crash production
    request #1 instead of falling back to eager here. Train mode matters because
    run_inference()'s MC Dropout flips the model into it, and dynamo guards on
    `self.training` — compiling eval only would defer the train graph to the first
    real MC-Dropout call.
    """
    if not env_bool("AI_TORCH_COMPILE", default=True):
        return model
    try:
        if torch.cuda.is_available():
            return torch.compile(model, mode="reduce-overhead")
        compiled = torch.compile(model, mode="default")
        dummy_x = torch.zeros(1, WINDOW_SIZE, input_features)
        dummy_feat = torch.zeros(1, feat_dim)
        with torch.no_grad():
            compiled(dummy_x, dummy_feat)
            compiled.train()
            compiled(dummy_x, dummy_feat)
            compiled.eval()
        return compiled
    except Exception:
        return model  # compile unavailable/unsupported on this host — eager fallback


def load_lfp_models() -> None:
    """Load the LFP (Severson-trained) artifact set into the lfp_* globals.

    Kept separate from load_models() rather than parameterised: the two sets have
    different versions, different cycle_count normalisation (LFP_CYCLE_COUNT_NORM
    2300 vs 200) and are selected per request, so conflating them would make a
    version mismatch silent.
    """
    global lfp_scaler, lfp_feature_scaler, lfp_soh_model, lfp_iso_model, lfp_soc_mode

    for path, label in [
        (LFP_SCALER_PATH,         "LFP MinMaxScaler"),
        (LFP_FEATURE_SCALER_PATH, "LFP feature StandardScaler"),
        (LFP_MAMBA_PATH,          "LFP Mamba model"),
        (LFP_ISO_FOREST_PATH,     "LFP Isolation Forest"),
    ]:
        if not os.path.exists(path):
            raise RuntimeError(
                f"[STARTUP] {label} artifact not found at '{path}'. "
                "Run scripts/preprocess_lfp.py + scripts/train.py with the LFP output "
                "paths and commit models/weights/ before serving chemistry='LFP'."
            )

    scaler_artifact = joblib.load(LFP_SCALER_PATH)
    # GH-67: preprocess_lfp.py records how soc_percent was Coulomb-counted.
    # "cycle" means soc spans the whole discharge (~100% -> ~9%); a 3/4-column
    # payload cannot reproduce that from a single stateless 30-row window, so
    # run_inference() refuses those rather than feeding the model a near-constant
    # [0.91, 1.0] channel it never saw in training. Default "window" keeps any
    # older artifact working unchanged.
    lfp_soc_mode = scaler_artifact.get("soc_mode", "window")
    if scaler_artifact["version"] != LFP_MODEL_VERSION:
        raise RuntimeError(
            f"LFP scaler version mismatch: expected {LFP_MODEL_VERSION}, "
            f"got {scaler_artifact['version']}"
        )
    feat_artifact = joblib.load(LFP_FEATURE_SCALER_PATH)
    if feat_artifact["version"] != LFP_MODEL_VERSION:
        raise RuntimeError(
            f"LFP feature scaler version mismatch: expected {LFP_MODEL_VERSION}, "
            f"got {feat_artifact['version']}"
        )

    checkpoint = torch.load(LFP_MAMBA_PATH, map_location="cpu", weights_only=False)
    if checkpoint["version"] != LFP_MODEL_VERSION:
        raise RuntimeError(
            f"LFP model version mismatch: expected {LFP_MODEL_VERSION}, "
            f"got {checkpoint['version']}"
        )
    input_features = checkpoint.get("input_features", 6)
    feat_dim = _resolve_feat_dim(checkpoint, LFP_MAMBA_PATH)
    model = MambaSOHPredictor(
        input_features=input_features,
        feat_dim=feat_dim,
        d_model=checkpoint.get("d_model", 64),
        d_state=checkpoint.get("d_state", 16),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    lfp_scaler = scaler_artifact["scaler"]
    lfp_feature_scaler = feat_artifact["scaler"]
    lfp_soh_model = _compile_for_inference(model, input_features, feat_dim)
    lfp_iso_model = joblib.load(LFP_ISO_FOREST_PATH)
    logger.info(
        "LFP artifacts loaded (v%s, trained on %s cells, soc_mode=%s)",
        LFP_MODEL_VERSION,
        len(scaler_artifact.get("trained_on", [])),
        scaler_artifact.get("soc_mode", "?"),
    )


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
        feat_dim=_resolve_feat_dim(checkpoint, LONG_MAMBA_PATH),
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
    if env_bool("AI_TORCH_COMPILE", default=True) and torch.cuda.is_available():
        try:
            # Fuses the 16-chunk scan loop into a single CUDA kernel: eliminates
            # 16 CPU→GPU roundtrips per forward pass when L=4096. CUDA-only — same
            # reasoning as load_models() above (lazy compile, no CPU C++ toolchain).
            model = torch.compile(model, mode="reduce-overhead")
        except Exception:
            pass
    long_soh_model = model
    return model
