"""
Tests for the Knowledge Base manifest (GH-80).

knowledge/*.md must stay in sync with models/embeddings/manifest.json, written
by scripts/ingest_rag.py. This is a pure file-hash check — no chromadb /
sentence-transformers import needed, so it runs even in environments without
the optional RAG dependencies installed.
"""
import hashlib
import json
import os

import pytest

REPO_ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWLEDGE_DIR = os.path.join(REPO_ROOT, "knowledge")
MANIFEST_PATH = os.path.join(REPO_ROOT, "models", "embeddings", "manifest.json")


def _sha256_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _current_knowledge_files() -> dict[str, str]:
    """{"maintenance/x.md": "/abs/path", ...} for every .md under knowledge/."""
    files = {}
    for subdir in ("maintenance", "safety"):
        doc_dir = os.path.join(KNOWLEDGE_DIR, subdir)
        if not os.path.isdir(doc_dir):
            continue
        for fname in os.listdir(doc_dir):
            if fname.endswith(".md"):
                files[f"{subdir}/{fname}"] = os.path.join(doc_dir, fname)
    return files


@pytest.fixture()
def manifest() -> dict:
    if not os.path.exists(MANIFEST_PATH):
        pytest.fail(
            f"{MANIFEST_PATH} not found — run `python scripts/ingest_rag.py` "
            "after adding/editing knowledge/*.md."
        )
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestKnowledgeBaseManifestSync:
    def test_every_knowledge_file_hash_matches_manifest(self, manifest):
        current = _current_knowledge_files()
        mismatches = []
        for source, path in current.items():
            entry = manifest["files"].get(source)
            if entry is None:
                mismatches.append(f"{source}: missing from manifest")
                continue
            if _sha256_file(path) != entry["sha256"]:
                mismatches.append(f"{source}: content changed since last ingest")
        assert not mismatches, (
            "knowledge/ <-> manifest.json drift — run `python scripts/ingest_rag.py`:\n"
            + "\n".join(mismatches)
        )

    def test_no_stale_manifest_entries(self, manifest):
        current_sources = set(_current_knowledge_files())
        manifest_sources = set(manifest["files"])
        stale = manifest_sources - current_sources
        assert not stale, (
            f"manifest.json references deleted knowledge files (re-run ingest): {stale}"
        )

    def test_manifest_covers_at_least_12_documents(self, manifest):
        assert len(manifest["files"]) >= 12

    def test_manifest_entries_have_required_fields(self, manifest):
        for source, entry in manifest["files"].items():
            assert "sha256" in entry, source
            assert "chunks" in entry, source
            assert "ingested_at" in entry, source
