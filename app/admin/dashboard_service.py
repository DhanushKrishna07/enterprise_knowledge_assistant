"""
app/admin/dashboard_service.py — Dashboard metrics aggregator service.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.indexing.bm25_store import get_bm25_store
from app.indexing.chroma_store import collection_stats
from app.observability.metrics import get_performance_metrics

_DB_PATH: str | None = None


def _db() -> str:
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = get_settings().sqlite_url.replace("sqlite:///", "")
    return _DB_PATH


def _connect() -> sqlite3.Connection:
    db = _db()
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_dashboard_metrics() -> dict[str, Any]:
    """Retrieve combined configuration, ingestion, index, feedback and trace performance metrics."""
    settings = get_settings()

    # Chroma stats
    try:
        chroma = collection_stats()
    except Exception:
        chroma = {"collection": "unavailable", "count": 0}

    # BM25 stats
    try:
        bm25_count = get_bm25_store().chunk_count
    except Exception:
        bm25_count = 0

    # Ingestion stats
    ingestion = {"runs": 0, "total_chunks": 0}
    try:
        with _connect() as conn:
            runs = conn.execute(
                "SELECT COUNT(*) as count, SUM(chunks_added) as chunks FROM ingestion_runs"
            ).fetchone()
            if runs:
                ingestion["runs"] = runs[0] or 0
                ingestion["total_chunks"] = runs[1] or 0
    except Exception:
        pass

    # Observability performance and feedback metrics
    perf = get_performance_metrics()

    return {
        "index": {
            "chroma_collection": chroma.get("collection"),
            "vector_chunks": chroma.get("count"),
            "bm25_chunks": bm25_count,
            "embedding_model": settings.embedding_model,
        },
        "feedback": {
            "total": perf["feedback_total"],
            "positive": perf["feedback_positive"],
            "negative": perf["feedback_negative"],
        },
        "ingestion": ingestion,
        "performance": {
            "total_requests": perf["total_requests"],
            "avg_latency_ms": perf["avg_latency_ms"],
            "answerability_ratio": perf["answerability_ratio"],
        },
        "config": {
            "llm_model": settings.llm_model,
            "reranker_model": settings.reranker_model,
            "top_k_semantic": settings.top_k_semantic,
            "top_k_context": settings.top_k_context,
        },
    }
