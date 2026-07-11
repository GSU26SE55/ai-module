"""
RAG retriever — semantic search over knowledge base using ChromaDB.

Usage:
    retriever = RagRetriever()
    docs = retriever.retrieve_maintenance("SOH 82%, degrading, rate 0.28%/cycle", top_k=3)
    docs = retriever.retrieve_safety("thermal warning, temperature 48C", top_k=2)
"""
import os

# Requires chromadb + sentence-transformers (pinned in requirements.txt).
# Build the vector store once via: python scripts/ingest_rag.py

EMBEDDINGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "models", "embeddings",
)
KNOWLEDGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "knowledge",
)


class RagRetriever:
    """
    Semantic retriever over maintenance and safety knowledge bases.
    Build the vector store once via scripts/ingest_rag.py before use.
    """

    def __init__(self) -> None:
        # Lazy import — only needed when RAG is active
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            self._client = chromadb.PersistentClient(path=EMBEDDINGS_DIR)
            self._encoder = SentenceTransformer("all-MiniLM-L6-v2")
            # cosine space → relevance_score = 1 - cosine_distance ∈ [0, 1] for similar docs.
            # NOTE: ChromaDB reconstructs its default ONNX embedder when reopening a persisted
            # collection; `import onnxruntime` can fail inside a worker thread on Windows. We
            # always pass our own query embeddings, so this only affects the enrich path and is
            # handled by the caller's fallback. See logs/GH-20/test.md (RISK).
            self._maintenance_col = self._client.get_or_create_collection(
                "maintenance", metadata={"hnsw:space": "cosine"})
            self._safety_col = self._client.get_or_create_collection(
                "safety", metadata={"hnsw:space": "cosine"})
            self._ready = True
        except ImportError:
            self._ready = False

    def retrieve_maintenance(self, query: str, top_k: int = 3) -> list[dict]:
        """Return top_k maintenance docs relevant to the prediction context."""
        if not self._ready:
            return []
        embedding = self._encoder.encode([query]).tolist()
        results = self._maintenance_col.query(
            query_embeddings=embedding, n_results=top_k
        )
        return self._format(results)

    def retrieve_safety(self, query: str, top_k: int = 2) -> list[dict]:
        """Return top_k safety docs relevant to the detected warnings."""
        if not self._ready:
            return []
        embedding = self._encoder.encode([query]).tolist()
        results = self._safety_col.query(
            query_embeddings=embedding, n_results=top_k
        )
        return self._format(results)

    @staticmethod
    def _format(results: dict) -> list[dict]:
        docs = []
        ids = results.get("ids", [[]])[0]
        for i, doc in enumerate(results.get("documents", [[]])[0]):
            docs.append({
                "title":           results["metadatas"][0][i].get("title", ""),
                "content":         doc,
                "source":          results["metadatas"][0][i].get("source", ""),
                # cosine distance ∈ [0, 2]; clamp similarity to [0, 1]
                "relevance_score": max(0.0, 1.0 - results["distances"][0][i]),
                # GH-82: chunk id for multi-query dedup (internal key — the
                # response schema does not expose it).
                "chunk_id":        ids[i] if i < len(ids) else "",
            })
        return docs
