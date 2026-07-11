"""
vectorStore/indexer.py
Unified ingestion pipeline: chunk → embed → store in ChromaDB.

Public API:
    index_document(text, session_id, doc_type, source)  →  list[str]  (chroma IDs)
    query_session(session_id, query_text, n_results, doc_type_filter)  →  list[dict]
    get_session_chunk_count(session_id)  →  int
"""
from __future__ import annotations

import uuid
from typing import Any

from langchain_core.documents import Document

from core.logging import get_logger
from parsing.chunking import chunk_text
from vectorStore.chroma_client import get_chroma_collection
from vectorStore.embeddings import get_embeddings

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _embed_documents(docs: list[Document]) -> list[list[float]]:
    """Batch-embed a list of LangChain Documents."""
    embeddings = get_embeddings()
    texts = [doc.page_content for doc in docs]
    return embeddings.embed_documents(texts)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def index_document(
    text: str,
    *,
    session_id: str,
    doc_type: str,
    source: str,
) -> list[str]:
    """
    Chunk `text`, embed chunks, and store in ChromaDB with metadata.

    Args:
        text       : raw text to index
        session_id : ties every chunk back to a session (used for filtering)
        doc_type   : one of "resume" | "jd" | "github" | "linkedin"
        source     : human-readable source label (filename or URL)

    Returns:
        list of ChromaDB document IDs that were inserted.

    Raises:
        ValueError if text is empty or doc_type is invalid.
    """
    _VALID_TYPES = {"resume", "jd", "github", "linkedin"}
    if doc_type not in _VALID_TYPES:
        raise ValueError(f"doc_type must be one of {_VALID_TYPES}, got {doc_type!r}")
    if not text or not text.strip():
        logger.warning("index_document called with empty text for session=%s type=%s", session_id, doc_type)
        return []

    # ── Chunk ─────────────────────────────────────────────────────────────────
    docs = chunk_text(text, session_id=session_id, doc_type=doc_type, source=source)
    if not docs:
        logger.warning("No chunks produced for session=%s type=%s", session_id, doc_type)
        return []

    logger.info(
        "Indexing %d chunks [type=%s source=%s session=%s]",
        len(docs), doc_type, source, session_id,
    )

    # ── Embed ─────────────────────────────────────────────────────────────────
    vectors = _embed_documents(docs)

    # ── Store ─────────────────────────────────────────────────────────────────
    collection = get_chroma_collection()

    ids = [
        f"{session_id}_{doc_type}_{doc.metadata['chunk_index']}_{uuid.uuid4().hex[:8]}"
        for doc in docs
    ]

    # ChromaDB metadata values must be str | int | float | bool
    metadatas = [
        {
            "session_id": doc.metadata["session_id"],
            "type": doc.metadata["type"],
            "source": doc.metadata["source"],
            "chunk_index": doc.metadata["chunk_index"],
        }
        for doc in docs
    ]

    collection.add(
        ids=ids,
        embeddings=vectors,
        documents=[doc.page_content for doc in docs],
        metadatas=metadatas,
    )

    logger.info("Stored %d chunks in ChromaDB for session=%s", len(ids), session_id)
    return ids


def query_session(
    session_id: str,
    query_text: str,
    *,
    n_results: int = 5,
    doc_type_filter: str | None = None,
) -> list[dict[str, Any]]:
    """
    Semantic search scoped to a single session.

    Args:
        session_id      : restrict results to this session
        query_text      : natural-language query
        n_results       : how many chunks to return (default 5)
        doc_type_filter : optional filter — "resume" | "jd" | "github" | "linkedin"

    Returns:
        List of dicts: {id, text, metadata, distance}
    """
    embeddings = get_embeddings()
    collection = get_chroma_collection()

    query_vec = embeddings.embed_query(query_text)

    where: dict[str, Any] = {"session_id": session_id}
    if doc_type_filter:
        where["type"] = doc_type_filter

    results = collection.query(
        query_embeddings=[query_vec],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for i, doc_id in enumerate(results["ids"][0]):
        hits.append({
            "id": doc_id,
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })

    logger.debug(
        "query_session: session=%s query=%r type_filter=%s → %d results",
        session_id, query_text[:60], doc_type_filter, len(hits),
    )
    return hits


def get_session_chunk_count(session_id: str) -> int:
    """Return the total number of indexed chunks for a session."""
    collection = get_chroma_collection()
    result = collection.get(where={"session_id": session_id})
    return len(result.get("ids", []))
