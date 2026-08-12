"""One process-wide sentence encoder shared by static RAG and history."""

from __future__ import annotations

import os
import threading

_encoder = None
_lock = threading.Lock()


def get_encoder():
    global _encoder
    if _encoder is not None:
        return _encoder
    with _lock:
        if _encoder is None:
            from sentence_transformers import SentenceTransformer

            model_path = os.getenv(
                "AI_EMBEDDING_MODEL_PATH", "sentence-transformers/all-MiniLM-L6-v2"
            )
            _encoder = SentenceTransformer(model_path)
    return _encoder


def encoder_ready() -> bool:
    return _encoder is not None
