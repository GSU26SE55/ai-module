"""GH-10: long-sequence training — warmup stages + gradient accumulation."""

import argparse
from unittest.mock import patch

import pytest
import torch

from scripts.train import _parse_warmup_stages, main, train_long, truncate_seq
from src.core.config import LONG_INPUT_FEATURES, SPECTRAL_FEAT_DIM


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
            "X": torch.randn(n, seq_len, LONG_INPUT_FEATURES),
            "X_feat": torch.randn(n, SPECTRAL_FEAT_DIM),
            "y": torch.rand(n) * 20 + 80,  # SOH in [80, 100]
            "seq_len": seq_len,
            "feature_scaler_version": "long-2.0",
        },
        path,
    )


def test_train_long_smoke(tmp_path, monkeypatch):
    """Warmup loop runs across stages, transfers weights, saves a checkpoint."""
    seq_len = 32  # >= patch_size (LONG_PATCH_SIZE=16) so patching yields >=1 token
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for name in ("train", "val", "test"):
        _make_long_split(str(data_dir / f"{name}.pt"), n=6, seq_len=seq_len)

    model_path = tmp_path / "soh_mamba_long.pth"
    monkeypatch.setattr("scripts.train.LONG_MAMBA_PATH", str(model_path))

    train_long(
        str(data_dir),
        str(tmp_path / "logs"),
        accum_steps=2,
        micro_batch=2,
        stage_epochs=1,
        final_epochs=1,
        stages=[16, 32],
        num_workers=0,
        weighted_loss=True,  # exercise the EOL-upweight SmoothL1 path
    )

    assert model_path.exists()
    ckpt = torch.load(str(model_path), weights_only=False)
    assert ckpt["pooling"] == "attention"
    assert ckpt["seq_len"] == seq_len
    assert "model_state_dict" in ckpt


# ── GH-43: --warmup-stages CLI ─────────────────────────────────────────


class TestWarmupStagesCli:
    def test_parse_valid(self):
        assert _parse_warmup_stages("2048,4096") == [2048, 4096]
        assert _parse_warmup_stages("4096") == [4096]  # final-only, no warmup
        assert _parse_warmup_stages("256, 512") == [256, 512]  # tolerate spaces

    def test_parse_invalid_raises_argparse_error(self):
        with pytest.raises(argparse.ArgumentTypeError, match="comma-separated ints"):
            _parse_warmup_stages("2048,abc")
        with pytest.raises(argparse.ArgumentTypeError, match="at least one stage"):
            _parse_warmup_stages(",")
        with pytest.raises(argparse.ArgumentTypeError, match="positive"):
            _parse_warmup_stages("0,4096")
        with pytest.raises(argparse.ArgumentTypeError, match="positive"):
            _parse_warmup_stages("-256,4096")

    def test_cli_forwards_stages_to_train_long(self):
        with (
            patch("scripts.train.train_long") as mock_train_long,
            patch(
                "sys.argv",
                ["train.py", "--long", "--warmup-stages", "2048,4096"],
            ),
        ):
            main()
        assert mock_train_long.call_args.kwargs["stages"] == [2048, 4096]

    def test_cli_default_keeps_five_stage_baseline(self):
        """No flag → stages=None → train_long falls back to WARMUP_STAGES."""
        with (
            patch("scripts.train.train_long") as mock_train_long,
            patch("sys.argv", ["train.py", "--long"]),
        ):
            main()
        assert mock_train_long.call_args.kwargs["stages"] is None
