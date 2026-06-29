"""
app/indexing/chroma_store.py — Chroma vector store operations.

Uses a separate collection per embedding model so dimension changes never corrupt an existing index.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: Any = None


def _get_client() -> Any:
    global _client
    if _client is not None:
        return _client
    settings = get_settings()
    try:
        from pathlib import Path

        import chromadb  # type: ignore[import]

        Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=settings.chroma_path)
        logger.info("Chroma client initialised at: %s", settings.chroma_path)
    except Exception as exc:
        logger.error("Failed to initialise Chroma: %s", exc)
        raise
    return _client


def reset_chroma_client() -> None:
    """Drop cached client so the next call opens a fresh index on disk."""
    global _client
    _client = None


def get_collection() -> Any:
    """Return (or create) the collection for the current embedding model."""
    settings = get_settings()
    client = _get_client()
    col = client.get_or_create_collection(
        name=settings.chroma_collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    return col


def upsert_chunks(
    ids: list[str],
    documents: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict[str, Any]],
) -> None:
    col = get_collection()
    # Chroma upsert in batches of 500
    batch = 500
    for i in range(0, len(ids), batch):
        col.upsert(
            ids=ids[i : i + batch],
            documents=documents[i : i + batch],
            embeddings=embeddings[i : i + batch],
            metadatas=metadatas[i : i + batch],
        )
    logger.debug(
        "Upserted %d chunks to Chroma collection '%s'.",
        len(ids),
        get_settings().chroma_collection_name,
    )


def delete_by_document_id(document_id: str) -> int:
    """Delete all chunks belonging to a document_id. Returns count deleted."""
    col = get_collection()
    results = col.get(where={"document_id": {"$eq": document_id}}, include=[])
    ids = results.get("ids", [])
    if ids:
        col.delete(ids=ids)
        logger.info("Deleted %d chunks for document_id=%s from Chroma.", len(ids), document_id)
    return len(ids)


def query_collection(
    query_embedding: list[float],
    n_results: int = 30,
    where: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a semantic query and return raw Chroma results."""
    col = get_collection()
    kwargs: dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
    return col.query(**kwargs)


def collection_stats() -> dict[str, Any]:
    col = get_collection()
    settings = get_settings()
    return {
        "collection": settings.chroma_collection_name,
        "count": col.count(),
    }


def get_chunk_by_id(chunk_id: str) -> dict[str, Any] | None:
    """Fetch a single chunk by its ID for source preview."""
    col = get_collection()
    try:
        result = col.get(ids=[chunk_id], include=["documents", "metadatas"])
        if not result.get("ids"):
            return None
        meta = result["metadatas"][0] if result.get("metadatas") else {}
        doc = result["documents"][0] if result.get("documents") else ""
        return {
            "chunk_id": chunk_id,
            "text": doc,
            **meta,
        }
    except Exception as exc:
        logger.warning("Failed to fetch chunk %s: %s", chunk_id, exc)
        return None


def list_all_document_ids() -> list[str]:
    """Retrieve all unique document IDs currently indexed in Chroma."""
    try:
        col = get_collection()
        # Retrieve only the metadatas containing document_id
        results = col.get(include=["metadatas"])
        metas = results.get("metadatas", []) or []
        doc_ids = set()
        for meta in metas:
            if meta and "document_id" in meta:
                doc_ids.add(meta["document_id"])
        return list(doc_ids)
    except Exception as exc:
        logger.warning("Failed to retrieve document IDs from Chroma: %s", exc)
        return []


def get_chunks_by_ids(chunk_ids: list[str]) -> dict[str, str]:
    """Fetch texts for multiple chunk IDs. Returns dict mapping chunk_id -> text."""
    if not chunk_ids:
        return {}
    col = get_collection()
    try:
        result = col.get(ids=chunk_ids, include=["documents"])
        ids = result.get("ids", [])
        docs = result.get("documents", [])
        return {cid: doc for cid, doc in zip(ids, docs)}
    except Exception as exc:
        logger.warning("Failed to fetch chunks %s: %s", chunk_ids, exc)
        return {}

