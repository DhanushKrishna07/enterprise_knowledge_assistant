"""
app/observability/metrics.py — Metrics aggregator from request_logs and feedback tables.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.core.config import get_settings

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


def get_performance_metrics() -> dict[str, Any]:
    """Retrieve key performance metrics and feedback counts from database."""
    metrics: dict[str, Any] = {
        "total_requests": 0,
        "avg_latency_ms": 0.0,
        "answerability_ratio": 0.0,
        "feedback_total": 0,
        "feedback_positive": 0,
        "feedback_negative": 0,
    }

    try:
        with _connect() as conn:
            # Latency and total requests
            row = conn.execute("SELECT COUNT(*), AVG(latency_ms) FROM request_logs").fetchone()
            if row and row[0]:
                metrics["total_requests"] = row[0]
                metrics["avg_latency_ms"] = round(row[1], 1) if row[1] else 0.0

            # Answerability ratio (percentage of queries successfully answered)
            rows_details = conn.execute("SELECT details_json FROM request_logs").fetchall()
            answered_count = 0
            for r in rows_details:
                try:
                    details = json.loads(r["details_json"])
                    if details.get("answerability") == "answered":
                        answered_count += 1
                except Exception:
                    pass
            if metrics["total_requests"] > 0:
                metrics["answerability_ratio"] = round(
                    answered_count / metrics["total_requests"], 2
                )

            # Feedback aggregation
            row_fb = conn.execute(
                "SELECT COUNT(*), SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END), SUM(CASE WHEN rating = -1 THEN 1 ELSE 0 END) FROM feedback"
            ).fetchone()
            if row_fb and row_fb[0]:
                metrics["feedback_total"] = row_fb[0]
                metrics["feedback_positive"] = row_fb[1] or 0
                metrics["feedback_negative"] = row_fb[2] or 0
    except Exception:
        pass

    return metrics
