"""
RAG retriever — semantic search over knowledge base using ChromaDB.

Usage:
    retriever = RagRetriever()
    docs = retriever.retrieve_maintenance("SOH 82%, degrading, rate 0.28%/cycle", top_k=3)
    docs = retriever.retrieve_safety("thermal warning, temperature 48C", top_k=2)
"""
import os

# TODO: install chromadb + sentence-transformers
# pip install chromadb sentence-transformers

EMBEDDINGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "models", "embeddings",
)
KNOWLEDGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "knowledge",
)


class RagRetriever:
    """
    Semantic retriever over maintenance and safety knowledge bases.
    Call ingest() once (or via scripts/ingest_rag.py) to build the vector store.
    """

    def __init__(self) -> None:
        # Lazy import — only needed when RAG is active
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            self._client = chromadb.PersistentClient(path=EMBEDDINGS_DIR)
            self._encoder = SentenceTransformer("all-MiniLM-L6-v2")
            self._maintenance_col = self._client.get_or_create_collection("maintenance")
            self._safety_col     = self._client.get_or_create_collection("safety")
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
        for i, doc in enumerate(results.get("documents", [[]])[0]):
            docs.append({
                "title":           results["metadatas"][0][i].get("title", ""),
                "content":         doc,
                "source":          results["metadatas"][0][i].get("source", ""),
                "relevance_score": 1.0 - results["distances"][0][i],
            })
        return docs
