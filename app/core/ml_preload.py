"""
app/core/ml_preload.py — Import numpy/chroma/BM25 on the main thread before workers start.

Concurrent first imports from thread-pool workers cause numpy circular-import crashes on Windows.
"""

from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger(__name__)
_preloaded = False


def preload_ml_stack() -> None:
    """Load heavy ML dependencies once on the main thread."""
    global _preloaded
    if _preloaded:
        return

    logger.info("Preloading ML stack (numpy, chromadb, bm25)...")
    import numpy  # noqa: F401

    import chromadb  # noqa: F401
    from rank_bm25 import BM25Okapi  # noqa: F401

    BM25Okapi([["warmup"]])  # verify rank-bm25 works

    from app.indexing.chroma_store import get_collection

    get_collection()
    _preloaded = True
    logger.info("ML stack preloaded successfully.")
