"""GH-63 — CPU torch.compile attempt must fall back to eager if the backend
can't actually compile (e.g. missing C++ toolchain, unsupported Triton on
Windows). torch.compile() itself is LAZY: wrapping always "succeeds", the
backend only runs on the first real forward pass — so load_models() must
force that forward pass at startup (not defer the failure to request #1)."""

import torch

from src.core import model_loader


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
