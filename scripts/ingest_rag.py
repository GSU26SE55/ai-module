"""
Ingest knowledge base documents into ChromaDB vector store (v2 — GH-80).

Usage:
    python scripts/ingest_rag.py

Reads all .md files from knowledge/maintenance/ and knowledge/safety/, chunks
by markdown section (heading-aware — keeps tables/lists intact instead of
cutting at a fixed character offset; falls back to a sliding window only for
oversized sections), embeds with sentence-transformers, stores in ChromaDB.

Writes models/embeddings/manifest.json (per-file sha256/chunk-count/ingested_at)
so tests/test_kb_manifest.py can detect a knowledge/ <-> embeddings drift
(someone edited knowledge/*.md and forgot to re-run this script).

Idempotent: re-running replaces each file's chunks (delete-by-source then
upsert) and removes chunks for any knowledge file that no longer exists
(deleted/renamed since the last ingest).

Run once after adding/updating knowledge documents.
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWLEDGE_DIR  = os.path.join(REPO_ROOT, "knowledge")
EMBEDDINGS_DIR = os.path.join(REPO_ROOT, "models", "embeddings")
MANIFEST_PATH  = os.path.join(EMBEDDINGS_DIR, "manifest.json")

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# A section (## heading block) larger than this falls back to the old
# sliding-window split — keeps most sections (including tables) as one
# self-contained chunk while still bounding worst-case chunk size.
MAX_SECTION_SIZE      = 1500
FALLBACK_CHUNK_SIZE    = 512
FALLBACK_CHUNK_OVERLAP = 64
MIN_CHUNK_SIZE         = 50  # drop near-empty sections/fragments

_H2_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def sha256_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _fallback_chunk(text: str, size: int = FALLBACK_CHUNK_SIZE, overlap: int = FALLBACK_CHUNK_OVERLAP) -> list[str]:
    """Sliding-window split — only used when a single section exceeds MAX_SECTION_SIZE."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end].strip())
        start += size - overlap
    return chunks


def chunk_by_section(text: str) -> list[tuple[str, str]]:
    """
    Split a markdown document by H2 (##) heading into (section_title, content)
    pairs. A section longer than MAX_SECTION_SIZE falls back to the sliding-
    window split (sub-chunks share the section title). Content before the
    first H2 heading (the H1 title line) is not itself chunked — the file's
    title is already captured separately in the `title` metadata field.

    Returns list of (section_title, chunk_text), filtered to non-trivial size.
    """
    matches = list(_H2_RE.finditer(text))
    if not matches:
        # No H2 headings — treat the whole body as one section under the H1
        # title (or "Document" if there isn't even an H1).
        h1 = _H1_RE.search(text)
        section_title = h1.group(1).strip() if h1 else "Document"
        body = text.strip()
        pieces = [body] if len(body) <= MAX_SECTION_SIZE else _fallback_chunk(body)
        return [(section_title, c) for c in pieces if len(c) > MIN_CHUNK_SIZE]

    sections: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        section_title = m.group(1).strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if len(content) <= MAX_SECTION_SIZE:
            sections.append((section_title, content))
        else:
            sections.extend((section_title, c) for c in _fallback_chunk(content))
    return [(t, c) for t, c in sections if len(c) > MIN_CHUNK_SIZE]


def _existing_sources(collection) -> set[str]:
    """All distinct `source` metadata values currently stored in the collection."""
    got = collection.get(include=["metadatas"])
    return {m["source"] for m in got.get("metadatas", []) if m and m.get("source")}


def _delete_by_source(collection, source: str) -> None:
    """Idempotency primitive: drop every chunk previously ingested for `source`."""
    collection.delete(where={"source": source})


def ingest_collection(collection, encoder, knowledge_subdir: str, manifest: dict) -> int:
    """Ingest all .md files in a knowledge subdirectory into a ChromaDB collection."""
    doc_dir = os.path.join(KNOWLEDGE_DIR, knowledge_subdir)
    if not os.path.isdir(doc_dir):
        print(f"  [WARN] Directory not found: {doc_dir}")
        return 0

    total = 0
    current_sources: set[str] = set()
    ingested_at = datetime.now(timezone.utc).isoformat()

    for fname in sorted(os.listdir(doc_dir)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(doc_dir, fname)
        source = f"{knowledge_subdir}/{fname}"
        current_sources.add(source)

        with open(fpath, encoding="utf-8") as f:
            text = f.read()

        title = fname.replace("_", " ").replace(".md", "").title()
        file_hash = sha256_file(fpath)
        sections = chunk_by_section(text)

        # Idempotent: drop this file's previous chunks before re-inserting, so
        # re-running on unchanged content always yields the same chunk count.
        _delete_by_source(collection, source)

        if sections:
            chunk_texts = [content for _, content in sections]
            ids        = [f"{fname}_{i}" for i in range(len(sections))]
            embeddings = encoder.encode(chunk_texts).tolist()
            metadatas  = [
                {
                    "title": title,
                    "source": source,
                    "section": section_title,
                    "doc_version": file_hash[:12],
                    "ingested_at": ingested_at,
                }
                for section_title, _ in sections
            ]
            collection.upsert(ids=ids, embeddings=embeddings, documents=chunk_texts, metadatas=metadatas)
            print(f"  {fname}: {len(sections)} chunks")
            total += len(sections)

        manifest["files"][source] = {
            "sha256": file_hash,
            "chunks": len(sections),
            "ingested_at": ingested_at,
        }

    # Remove chunks for files deleted/renamed since the last ingest run.
    stale_sources = _existing_sources(collection) - current_sources
    for source in stale_sources:
        print(f"  [CLEANUP] removing orphaned chunks for deleted file: {source}")
        _delete_by_source(collection, source)
        manifest["files"].pop(source, None)

    return total


def main() -> None:
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("Install dependencies: pip install chromadb sentence-transformers")
        return

    os.makedirs(EMBEDDINGS_DIR, exist_ok=True)
    client  = chromadb.PersistentClient(path=EMBEDDINGS_DIR)
    encoder = SentenceTransformer(EMBEDDING_MODEL)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "embedding_model": EMBEDDING_MODEL,
        "files": {},
    }

    # cosine space → relevance_score = 1 - cosine_distance ∈ [0, 1] for similar docs
    print("Ingesting maintenance knowledge...")
    maint_col = client.get_or_create_collection("maintenance", metadata={"hnsw:space": "cosine"})
    n_maint = ingest_collection(maint_col, encoder, "maintenance", manifest)

    print("Ingesting safety knowledge...")
    safety_col = client.get_or_create_collection("safety", metadata={"hnsw:space": "cosine"})
    n_safety = ingest_collection(safety_col, encoder, "safety", manifest)

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    print(f"\nDone: {n_maint} maintenance chunks, {n_safety} safety chunks")
    print(f"Vector store: {EMBEDDINGS_DIR}")
    print(f"Manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
