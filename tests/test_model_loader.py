"""GH-63 — CPU torch.compile attempt must fall back to eager if the backend
can't actually compile (e.g. missing C++ toolchain, unsupported Triton on
Windows). torch.compile() itself is LAZY: wrapping always "succeeds", the
backend only runs on the first real forward pass — so load_models() must
force that forward pass at startup (not defer the failure to request #1)."""

import os

import pytest
import torch

from src.core import model_loader
from src.core.config import MAMBA_PATH

# GH-88: these tests exercise load_models() with the REAL versioned artifacts.
# On a retrain-required branch (version bumped, Kaggle training not yet done)
# the artifact doesn't exist — skip instead of failing the suite; the tests
# re-activate automatically once the new weights are committed.
pytestmark = pytest.mark.skipif(
    not os.path.exists(MAMBA_PATH),
    reason=f"real model artifact missing ({os.path.basename(MAMBA_PATH)}) — "
    "pending retrain for the bumped MODEL_VERSION",
)


def test_cpu_compile_failure_falls_back_to_eager(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    class _BrokenCompiled:
        def __call__(self, *args, **kwargs):
            raise RuntimeError("simulated backend failure (e.g. no C++ toolchain)")

    monkeypatch.setattr(torch, "compile", lambda model, mode=None: _BrokenCompiled())

    model_loader.load_models()

    assert isinstance(model_loader.soh_model, torch.nn.Module)
    assert not isinstance(model_loader.soh_model, _BrokenCompiled)


def test_cpu_compile_success_is_used(monkeypatch):
    """GH-63 review — a real torch.compile() OptimizedModule supports .train()/
    .eval() (delegated to the wrapped module), so the mock must too. An earlier
    version of this test mocked compile() as a bare function (no .train()/.eval())
    which made the warm-up's `compiled.train()` call raise AttributeError — caught
    by load_models()'s except-and-fall-back-to-eager, so the test passed for the
    WRONG reason (never actually exercised the success path)."""
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    calls = []

    class _FakeCompiled:
        def __init__(self, model):
            self._model = model

        def __call__(self, *args, **kwargs):
            calls.append(self._model.training)
            return self._model(*args, **kwargs)

        def train(self, mode=True):
            self._model.train(mode)
            return self

        def eval(self):
            self._model.eval()
            return self

        @property
        def training(self):
            return self._model.training

    monkeypatch.setattr(torch, "compile", lambda model, mode=None: _FakeCompiled(model))
    # GH-67: load_models() now also loads the LFP set, which warms up its own model
    # the same way. Silence it here so this test keeps asserting on the DEFAULT
    # model's warm-up only — the LFP warm-up has its own test below.
    monkeypatch.setattr(model_loader, "load_lfp_models", lambda: None)

    model_loader.load_models()

    assert calls == [False, True], (
        "warm-up must run once in eval mode (False) and once in train mode "
        "(True, MC Dropout's actual runtime path) — got: " + repr(calls)
    )
    assert isinstance(model_loader.soh_model, _FakeCompiled)
    assert model_loader.soh_model.training is False, (
        "must end in eval mode — run_inference() explicitly switches to train() "
        "itself for MC Dropout and restores eval() afterward"
    )


def test_load_lfp_models_missing_artifact_raises(monkeypatch, tmp_path):
    """A NASA-only deploy must not pretend the LFP set is present."""
    monkeypatch.setattr(model_loader, "LFP_SCALER_PATH", str(tmp_path / "nope.pkl"))
    with pytest.raises(RuntimeError, match="LFP MinMaxScaler artifact not found"):
        model_loader.load_lfp_models()


def test_load_lfp_models_version_mismatch_raises(monkeypatch, tmp_path):
    """Version assert is what stops a stale LFP scaler pairing with new weights —
    the failure mode that is otherwise silent (wrong numbers, no error)."""
    import joblib
    from sklearn.preprocessing import MinMaxScaler

    bad = tmp_path / "scaler_lfp.pkl"
    joblib.dump({"scaler": MinMaxScaler(), "version": "0.0-wrong"}, bad)
    monkeypatch.setattr(model_loader, "LFP_SCALER_PATH", str(bad))
    with pytest.raises(RuntimeError, match="LFP scaler version mismatch"):
        model_loader.load_lfp_models()


def test_load_models_survives_missing_lfp_artifacts(monkeypatch, caplog):
    """load_models() must still boot the default set when LFP is absent —
    otherwise a NASA-only deploy could not start at all."""
    def _boom():
        raise RuntimeError("simulated: LFP artifacts absent")

    monkeypatch.setattr(model_loader, "load_lfp_models", _boom)
    with caplog.at_level("WARNING"):
        model_loader.load_models()

    assert model_loader.soh_model is not None, "default set must still load"
    assert "LFP artifacts not loaded" in caplog.text


def test_lfp_model_warmup_runs_eval_and_train_modes(monkeypatch):
    """Same guarantee as the default set: MC Dropout flips the model into train
    mode, and dynamo guards on `self.training`, so compiling eval-only would defer
    the train graph to the first real LFP request."""
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    calls = []

    class _FakeCompiled:
        def __init__(self, model):
            self._model = model

        def __call__(self, *args, **kwargs):
            calls.append(self._model.training)
            return self._model(*args, **kwargs)

        def train(self, mode=True):
            self._model.train(mode)
            return self

        def eval(self):
            self._model.eval()
            return self

        @property
        def training(self):
            return self._model.training

    monkeypatch.setattr(torch, "compile", lambda model, mode=None: _FakeCompiled(model))
    model_loader.load_lfp_models()

    assert calls == [False, True], (
        "LFP warm-up must run once in eval mode and once in train mode — got: "
        + repr(calls)
    )
    assert model_loader.lfp_soh_model.training is False
    assert model_loader.lfp_iso_model is not None


def test_load_models_enables_flush_denormal(monkeypatch):
    """Subnormal arithmetic runs in x86 microcode and dominated the SSM recurrence:
    p95 was 70.8ms (NASA) / 101.7ms (LFP) without FTZ, the latter breaching the
    <100ms P1 SLA. Predictions are bit-identical with it on, so this must stay."""
    seen = []
    real = torch.set_flush_denormal
    monkeypatch.setattr(torch, "set_flush_denormal", lambda v: (seen.append(v), real(v))[1])

    model_loader.load_models()

    assert seen and seen[0] is True, (
        "load_models() must enable flush-to-zero before any inference — got: " + repr(seen)
    )
