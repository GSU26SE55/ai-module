"""GH-10: long-sequence training — warmup stages + gradient accumulation."""

import torch

from scripts.train import train_long, truncate_seq
from src.core.config import INPUT_FEATURES, SPECTRAL_FEAT_DIM


def test_truncate_keeps_last_timesteps():
    X = torch.arange(2 * 10 * 3, dtype=torch.float32).reshape(2, 10, 3)
    out = truncate_seq(X, 4)
    assert out.shape == (2, 4, 3)
    assert torch.equal(out, X[:, -4:, :])


def test_truncate_noop_when_shorter():
    X = torch.randn(2, 5, 3)
    assert truncate_seq(X, 8) is X  # unchanged reference


def _make_long_split(path, n, seq_len):
    torch.save(
        {
            "X":                      torch.randn(n, seq_len, INPUT_FEATURES),
            "X_feat":                 torch.randn(n, SPECTRAL_FEAT_DIM),
            "y":                      torch.rand(n) * 20 + 80,  # SOH in [80, 100]
            "seq_len":                seq_len,
            "feature_scaler_version": "long-1.0",
        },
        path,
    )


def test_train_long_smoke(tmp_path, monkeypatch):
    """Warmup loop runs across stages, transfers weights, saves a checkpoint."""
    seq_len = 8
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for name in ("train", "val", "test"):
        _make_long_split(str(data_dir / f"{name}.pt"), n=6, seq_len=seq_len)

    model_path = tmp_path / "soh_mamba_long.pth"
    monkeypatch.setattr("scripts.train.LONG_MAMBA_PATH", str(model_path))

    train_long(
        str(data_dir), str(tmp_path / "logs"),
        accum_steps=2, micro_batch=2, stage_epochs=1, final_epochs=1,
        stages=[4, 8], num_workers=0,
    )

    assert model_path.exists()
    ckpt = torch.load(str(model_path), weights_only=False)
    assert ckpt["pooling"] == "attention"
    assert ckpt["seq_len"] == seq_len
    assert "model_state_dict" in ckpt
