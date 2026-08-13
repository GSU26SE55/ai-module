"""
Prescription history store — long-term memory for the prescription layer (GH-83).

Persists each enriched prescription (context embedding + final output +
feedback status) in its own ChromaDB collection, at a path SEPARATE from the
static knowledge base (models/embeddings/, GH-80). The KB is a committed,
reproducible artifact checked by test_kb_manifest; this store is runtime data
that grows with every enrich=true call and with technician feedback, so it
must never share that file — see docs/adr/0004-prescription-long-term-memory.md.
Not committed to Git (see .gitignore).

Usage:
    store = PrescriptionHistoryStore()
    prescription_id = store.save(context, battery_id, action_code, risk_level,
                                  llm_provider, prescription, action_steps, ppe_required)
    past_cases = store.retrieve_similar_accepted(context, top_k=2)
    store.update_feedback(prescription_id, "accepted")
"""
import json
import logging
import time
import uuid

from src.core.runtime import data_path
from src.services.prescription.embedding import get_encoder

logger = logging.getLogger(__name__)

# Requires chromadb + sentence-transformers (pinned in requirements.txt) — same
# optional dependency as rag_retriever.py, lazy-imported below.
HISTORY_DIR = str(data_path("AI_PRESCRIPTION_HISTORY_DIR", "prescription_history"))

# FIFO cap — oldest records (by save timestamp) evicted once this is exceeded.
MAX_RECORDS = 500


class PrescriptionHistoryStore:
    """
    Long-term memory for prescriptions: write-after-enrich, retrieve-as-few-shot,
    update-on-feedback. All methods are best-effort — any failure (missing
    dependency, disk error, malformed record) degrades to a no-op instead of
    raising, so the prescription pipeline never breaks because of history I/O.
    """

    def __init__(self, path: str | None = None) -> None:
        # Lazy import — only needed when enrich=true actually runs. Catches
        # more than ImportError: chromadb's own import chain can raise other
        # errors depending on the host environment (e.g. home-directory
        # detection for its default embedder cache) — any of that must degrade
        # to _ready=False rather than crash the caller (_get_history_store() is
        # not wrapped in its own try/except at the call site, unlike RagRetriever).
        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=path or HISTORY_DIR)
            self._encoder = get_encoder()
            self._collection = self._client.get_or_create_collection(
                "prescription_history", metadata={"hnsw:space": "cosine"})
            self._ready = True
        except Exception as exc:
            logger.warning("Prescription history store unavailable: %s", exc)
            self._ready = False

    def save(
        self,
        context: str,
        battery_id: str,
        action_code: str,
        risk_level: str,
        llm_provider: str,
        prescription: str,
        action_steps: list[str],
        ppe_required: list[str],
    ) -> str | None:
        """
        Best-effort write of the final prescription. Returns the new
        prescription_id (uuid4) on success, None if the store is unavailable
        or the write failed — callers must treat None as "no history record"
        and never let it affect the /prescribe response.
        """
        if not self._ready:
            return None

        prescription_id = str(uuid.uuid4())
        try:
            embedding = self._encoder.encode([context]).tolist()
            document = json.dumps({
                "prescription": prescription,
                "action_steps": action_steps,
                "ppe_required": ppe_required,
            }, ensure_ascii=False)
            self._collection.add(
                ids=[prescription_id],
                embeddings=embedding,
                documents=[document],
                metadatas=[{
                    "battery_id": battery_id,
                    "action_code": action_code,
                    "risk_level": risk_level,
                    "llm_provider": llm_provider,
                    "timestamp": time.time(),
                    "feedback_status": "pending",
                }],
            )
        except Exception as exc:
            logger.warning("Failed to save prescription history record: %s", exc)
            return None

        self._evict_if_over_cap()
        return prescription_id

    def retrieve_similar_accepted(
        self, context: str, battery_id: str | None = None, top_k: int = 2
    ) -> list[dict]:
        """
        Top-k most similar past cases with feedback_status == "accepted", for
        use as few-shot context. Returns [] if the store is unavailable, empty,
        or the query fails — callers must treat that as "no past cases", never
        as an error.

        GH-105: when battery_id is given, cases from that battery are tried
        first; if none exist yet, falls back to the global (any battery)
        query — a binary fallback, not a top-k top-up.
        """
        if not self._ready:
            return []
        try:
            embedding = self._encoder.encode([context]).tolist()
            if battery_id:
                scoped = self._collection.query(
                    query_embeddings=embedding,
                    n_results=top_k,
                    where={"$and": [
                        {"feedback_status": "accepted"},
                        {"battery_id": battery_id},
                    ]},
                )
                parsed = self._parse(scoped)
                if parsed:
                    return parsed
            results = self._collection.query(
                query_embeddings=embedding,
                n_results=top_k,
                where={"feedback_status": "accepted"},
            )
            return self._parse(results)
        except Exception as exc:
            logger.warning("Prescription history retrieval failed: %s", exc)
            return []

    def update_feedback(
        self,
        prescription_id: str,
        status: str,
        edited_steps: list[str] | None = None,
        note: str | None = None,
    ) -> bool:
        """
        Record technician feedback for a prescription_id. Returns False if the
        store is unavailable, the id doesn't exist, or the update failed —
        the caller (POST /prescribe/feedback) maps False to a 404.
        """
        if not self._ready:
            return False
        try:
            existing = self._collection.get(ids=[prescription_id])
            if not existing["ids"]:
                return False

            metadata = dict(existing["metadatas"][0])
            metadata["feedback_status"] = status
            if edited_steps is not None:
                metadata["edited_steps"] = json.dumps(edited_steps, ensure_ascii=False)
            if note is not None:
                metadata["note"] = note

            self._collection.update(ids=[prescription_id], metadatas=[metadata])
            return True
        except Exception as exc:
            logger.warning("Failed to update prescription feedback %s: %s", prescription_id, exc)
            return False

    def _evict_if_over_cap(self) -> None:
        """FIFO evict: delete oldest-by-timestamp records once count > MAX_RECORDS."""
        try:
            all_records = self._collection.get()
            ids = all_records.get("ids", [])
            if len(ids) <= MAX_RECORDS:
                return

            metadatas = all_records.get("metadatas", [])
            ordered = sorted(
                zip(ids, metadatas), key=lambda pair: pair[1].get("timestamp", 0.0)
            )
            n_to_evict = len(ids) - MAX_RECORDS
            evict_ids = [record_id for record_id, _ in ordered[:n_to_evict]]
            self._collection.delete(ids=evict_ids)
        except Exception as exc:
            logger.warning("Prescription history eviction failed (non-fatal): %s", exc)

    @staticmethod
    def _parse(results: dict) -> list[dict]:
        cases = []
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        for i, doc in enumerate(documents):
            try:
                parsed = json.loads(doc)
            except (TypeError, ValueError):
                continue
            meta = metadatas[i] if i < len(metadatas) else {}
            cases.append({
                "prescription": parsed.get("prescription", ""),
                "action_steps": parsed.get("action_steps", []),
                "ppe_required": parsed.get("ppe_required", []),
                "battery_id": meta.get("battery_id", ""),
                "action_code": meta.get("action_code", ""),
                "risk_level": meta.get("risk_level", ""),
            })
        return cases
