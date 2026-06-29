"""
app/indexing/index_reset.py — Wipe vector/keyword indexes for a full manual reindex.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger
from app.indexing.bm25_store import reset_bm25_store
from app.indexing.chroma_store import reset_chroma_client

logger = get_logger(__name__)


def clear_indexed_documents_table() -> None:
    settings = get_settings()
    db_path = settings.sqlite_url.replace("sqlite:///", "")
    if not Path(db_path).exists():
        return
    try:
        with sqlite3.connect(db_path, timeout=30.0) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS indexed_documents "
                "(document_id TEXT PRIMARY KEY, checksum TEXT, indexed_at TEXT)"
            )
            conn.execute("DELETE FROM indexed_documents")
            conn.commit()
        logger.info("Cleared indexed_documents checksum table.")
    except Exception as exc:
        logger.warning("Failed to clear indexed_documents: %s", exc)
        raise


def clear_rag_caches() -> None:
    settings = get_settings()
    try:
        from app.cache.cache_service import get_cache

        cache = get_cache()
        if cache is not None:
            cache.clear()
    except Exception as exc:
        logger.warning("Failed to clear diskcache: %s", exc)

    cache_dir = Path(settings.cache_path) / "rag"
    if cache_dir.exists():
        try:
            shutil.rmtree(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning("Failed to reset rag cache directory: %s", exc)


def clear_search_indexes() -> None:
    """Delete Chroma data, BM25 pickle, checksum records, and RAG caches."""
    settings = get_settings()
    chroma_dir = Path(settings.chroma_path)
    bm25_file = chroma_dir.parent / "bm25_index.pkl"

    reset_chroma_client()
    reset_bm25_store()

    if chroma_dir.exists():
        shutil.rmtree(chroma_dir)
        logger.info("Removed Chroma index at %s", chroma_dir)

    if bm25_file.exists():
        bm25_file.unlink()
        logger.info("Removed BM25 index at %s", bm25_file)

    clear_indexed_documents_table()
    clear_rag_caches()
