"""Shared pytest fixtures."""
import atexit
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest

# Unit tests must never bind the production gRPC port or download from the network.
os.environ.setdefault("AI_ENABLE_GRPC", "false")
os.environ.setdefault("AI_REQUIRE_LFP", "false")
os.environ.setdefault("AI_REQUIRE_RAG", "false")
os.environ.setdefault("AI_PRELOAD_RAG", "false")
os.environ.setdefault("AI_ENV_FILE", "/dev/null")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# ChromaDB may rewrite HNSW index files merely by opening/querying a persistent
# collection. Never let tests touch the checksum-protected committed KB seed.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_TEST_DATA_ROOT = Path(tempfile.mkdtemp(prefix="solar-ai-tests-"))
_TEST_KB_DIR = _TEST_DATA_ROOT / "embeddings"
shutil.copytree(_PROJECT_ROOT / "models" / "embeddings", _TEST_KB_DIR)
os.environ["AI_DATA_DIR"] = str(_TEST_DATA_ROOT)
os.environ["AI_KB_DIR"] = str(_TEST_KB_DIR)
os.environ["AI_PRESCRIPTION_HISTORY_DIR"] = str(
    _TEST_DATA_ROOT / "prescription-history"
)
os.environ["AI_CLASSIFICATION_FEEDBACK_DIR"] = str(
    _TEST_DATA_ROOT / "classification-feedback"
)
atexit.register(shutil.rmtree, _TEST_DATA_ROOT, ignore_errors=True)


class _DeterministicEncoder:
    """Small 384-dim test double compatible with the committed Chroma store."""

    def encode(self, texts):
        rows = []
        for text in texts:
            seed = sum(text.encode("utf-8")) % 997
            rng = np.random.RandomState(seed)
            rows.append(rng.normal(size=384).astype(np.float32))
        return np.stack(rows)


@pytest.fixture(autouse=True)
def _reset_prescription_observability():
    """GH-84: the /prescribe idempotency cache, rate-limit budget, and
    counters are module-level shared state — reset between every test so one
    test's cached response / budget usage can't leak into another."""
    from src.services.prescription import observability

    observability.reset()
    yield
    observability.reset()


@pytest.fixture(autouse=True)
def _offline_embedding_encoder(monkeypatch):
    """Keep the full test suite deterministic and independent of Hugging Face."""
    from src.services.prescription import embedding

    monkeypatch.setattr(embedding, "_encoder", _DeterministicEncoder())
