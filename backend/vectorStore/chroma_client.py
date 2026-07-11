"""
vectorStore/chroma_client.py
Singleton ChromaDB client with persistence.

All reads/writes to the vector store go through get_chroma_collection().
The collection uses cosine similarity (best for text embeddings).
"""
from functools import lru_cache

import chromadb
from chromadb.config import Settings as ChromaSettings

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


@lru_cache()
def _get_client() -> chromadb.ClientAPI:
    """Return a singleton persistent ChromaDB client."""
    settings = get_settings()
    persist_dir = settings.CHROMA_PERSIST_DIR
    logger.info("Initialising ChromaDB at: %s", persist_dir)
    return chromadb.PersistentClient(
        path=persist_dir,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def get_chroma_collection() -> chromadb.Collection:
    """
    Return (or create) the main ChromaDB collection.

    Metadata schema enforced per document chunk:
        {
            "session_id": str,   # links to PostgreSQL sessions.id
            "type"      : str,   # "resume" | "jd" | "github" | "linkedin"
            "source"    : str,   # filename or URL
            "chunk_index": int,  # sequential index within doc
        }

    The collection uses cosine distance for semantic similarity searches.
    """
    client = _get_client()
    settings = get_settings()
    collection = client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},  # cosine similarity
    )
    logger.debug(
        "ChromaDB collection '%s' — %d docs",
        settings.CHROMA_COLLECTION_NAME,
        collection.count(),
    )
    return collection


def delete_session_vectors(session_id: str) -> int:
    """
    Remove all vectors for a given session_id from ChromaDB.
    Returns number of documents deleted.
    """
    collection = get_chroma_collection()
    results = collection.get(where={"session_id": session_id})
    ids = results.get("ids", [])
    if ids:
        collection.delete(ids=ids)
        logger.info("Deleted %d vectors for session %s", len(ids), session_id)
    return len(ids)
