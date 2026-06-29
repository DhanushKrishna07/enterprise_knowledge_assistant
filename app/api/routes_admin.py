"""
app/api/routes_admin.py — Admin-only routes: dashboard, feedback export, retrieval stats.
"""

from __future__ import annotations

import csv
import io
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.dependencies import require_admin
from app.core.config import get_settings
from app.core.logging import get_logger

router = APIRouter(prefix="/admin", tags=["admin"])
logger = get_logger(__name__)


def _db_path() -> str:
    return get_settings().sqlite_url.replace("sqlite:///", "")


def _connect() -> sqlite3.Connection:
    db = _db_path()
    conn = sqlite3.connect(db, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/dashboard")
async def dashboard(admin=Depends(require_admin)) -> dict[str, Any]:
    """Aggregate metrics for the admin dashboard."""
    from app.admin.dashboard_service import get_dashboard_metrics

    return get_dashboard_metrics()


@router.post("/cache/clear")
async def clear_cache(admin=Depends(require_admin)) -> dict[str, Any]:
    """Clear the in-process response and query answer cache."""
    from app.cache.cache_service import get_cache

    cache = get_cache()
    if cache is None:
        return {"status": "skipped", "message": "Cache is disabled or not initialised."}
    try:
        count = len(cache)
        cache.clear()
        logger.info("Cache cleared via admin endpoint (%d entries removed).", count)
        return {"status": "ok", "entries_cleared": count}
    except Exception as exc:
        logger.error("Cache clear failed: %s", exc)
        return {"status": "error", "message": str(exc)}


@router.get("/feedback")
async def list_feedback(
    limit: int = 50,
    admin=Depends(require_admin),
) -> list[dict[str, Any]]:
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM feedback ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


@router.get("/feedback/export")
async def export_feedback_csv(admin=Depends(require_admin)) -> StreamingResponse:
    try:
        with _connect() as conn:
            # Join with users to export email, select only human-relevant fields
            rows = conn.execute(
                "SELECT f.created_at, u.email AS user_email, f.question, f.answer, f.rating, f.category, f.comment "
                "FROM feedback f "
                "LEFT JOIN users u ON f.user_id = u.id "
                "ORDER BY f.created_at DESC"
            ).fetchall()
            data = [dict(r) for r in rows]
    except Exception as exc:
        logger.warning("Failed to export feedback: %s", exc)
        data = []

    output = io.StringIO()
    if data:
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    else:
        # Fallback header if empty
        writer = csv.DictWriter(output, fieldnames=["created_at", "user_email", "question", "answer", "rating", "category", "comment"])
        writer.writeheader()

    output.seek(0)
    return StreamingResponse(
        iter([output.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=feedback_export.csv"},
    )


@router.get("/retrieval-stats")
async def retrieval_stats(
    limit: int = 50,
    admin=Depends(require_admin),
) -> list[dict[str, Any]]:
    """Retrieve detailed trace logs of RAG requests."""
    from app.observability.trace import get_recent_traces

    return get_recent_traces(limit=limit)


def _feedback_stats() -> dict[str, Any]:
    try:
        with _connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            positive = conn.execute("SELECT COUNT(*) FROM feedback WHERE rating = 1").fetchone()[0]
            negative = conn.execute("SELECT COUNT(*) FROM feedback WHERE rating = -1").fetchone()[0]
            return {"total": total, "positive": positive, "negative": negative}
    except Exception:
        return {"total": 0, "positive": 0, "negative": 0}


def _ingestion_stats() -> dict[str, Any]:
    try:
        with _connect() as conn:
            runs = conn.execute(
                "SELECT COUNT(*) as count, SUM(chunks_added) as chunks FROM ingestion_runs"
            ).fetchone()
            return {"runs": runs[0] or 0, "total_chunks": runs[1] or 0}
    except Exception:
        return {"runs": 0, "total_chunks": 0}
