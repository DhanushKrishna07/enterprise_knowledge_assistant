"""
app/observability/trace.py — Request tracing repository in SQLite for explainability.
"""

from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

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


def init_trace_table() -> None:
    """Initialize SQLite table for query logs."""
    with _connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS request_logs (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            question TEXT,
            rewritten_query TEXT,
            latency_ms REAL,
            created_at TEXT,
            details_json TEXT
        )
        """)


def log_request_trace(
    request_id: str,
    session_id: str | None,
    question: str,
    rewritten_query: str,
    latency_ms: float,
    details: dict[str, Any],
) -> None:
    """Write RAG trace event to SQLite."""
    init_trace_table()
    now = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO request_logs (id, session_id, question, rewritten_query, latency_ms, created_at, details_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    request_id,
                    session_id,
                    question,
                    rewritten_query,
                    latency_ms,
                    now,
                    json.dumps(details),
                ),
            )
    except Exception as exc:
        logger.warning("Failed to write request trace to database: %s", exc)


def get_recent_traces(limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve the recent RAG request traces."""
    init_trace_table()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM request_logs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            res = []
            for r in rows:
                d = dict(r)
                details_str = d.pop("details_json", "{}") or "{}"
                try:
                    d["details"] = json.loads(details_str)
                except Exception:
                    d["details"] = {}
                res.append(d)
            return res
    except Exception as exc:
        logger.warning("Failed to query request traces: %s", exc)
        return []


def get_trace_stats() -> dict[str, Any]:
    """Aggregate trace statistics."""
    init_trace_table()
    try:
        with _connect() as conn:
            row = conn.execute("SELECT COUNT(*), AVG(latency_ms) FROM request_logs").fetchone()
            total = row[0] or 0
            avg_lat = round(row[1], 1) if row[1] else 0.0
            return {"total_requests": total, "avg_latency_ms": avg_lat}
    except Exception:
        return {"total_requests": 0, "avg_latency_ms": 0.0}
