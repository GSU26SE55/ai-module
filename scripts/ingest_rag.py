"""
Ingest knowledge base documents into ChromaDB vector store.

Usage:
    python scripts/ingest_rag.py

Reads all .md files from knowledge/maintenance/ and knowledge/safety/,
chunks them, embeds with sentence-transformers, stores in ChromaDB.

Run once after adding/updating knowledge documents.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWLEDGE_DIR = os.path.join(REPO_ROOT, "knowledge")
EMBEDDINGS_DIR = os.path.join(REPO_ROOT, "models", "embeddings")

CHUNK_SIZE    = 512   # characters per chunk
CHUNK_OVERLAP = 64


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end].strip())
        start += size - overlap
    return [c for c in chunks if len(c) > 50]


def ingest_collection(
    collection,
    encoder,
    knowledge_subdir: str,
) -> int:
    """Ingest all .md files in a knowledge subdirectory into a ChromaDB collection."""
    doc_dir = os.path.join(KNOWLEDGE_DIR, knowledge_subdir)
    if not os.path.isdir(doc_dir):
        print(f"  [WARN] Directory not found: {doc_dir}")
        return 0

    total = 0
    for fname in sorted(os.listdir(doc_dir)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(doc_dir, fname)
        with open(fpath, encoding="utf-8") as f:
            text = f.read()

        title  = fname.replace("_", " ").replace(".md", "").title()
        chunks = chunk_text(text)

        ids        = [f"{fname}_{i}" for i in range(len(chunks))]
        embeddings = encoder.encode(chunks).tolist()
        metadatas  = [{"title": title, "source": f"{knowledge_subdir}/{fname}", "chunk": i}
                      for i in range(len(chunks))]

        collection.upsert(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
        print(f"  {fname}: {len(chunks)} chunks")
        total += len(chunks)

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
    encoder = SentenceTransformer("all-MiniLM-L6-v2")

    print("Ingesting maintenance knowledge...")
    maint_col = client.get_or_create_collection("maintenance")
    n_maint = ingest_collection(maint_col, encoder, "maintenance")

    print("Ingesting safety knowledge...")
    safety_col = client.get_or_create_collection("safety")
    n_safety = ingest_collection(safety_col, encoder, "safety")

    print(f"\nDone: {n_maint} maintenance chunks, {n_safety} safety chunks")
    print(f"Vector store: {EMBEDDINGS_DIR}")


if __name__ == "__main__":
    main()
