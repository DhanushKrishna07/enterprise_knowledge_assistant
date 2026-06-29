"""User feedback persistence layer."""

from __future__ import annotations

import datetime
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from app.core.config import get_settings


def _db_path() -> str:
    return get_settings().sqlite_url.replace("sqlite:///", "")


def _connect() -> sqlite3.Connection:
    db = _db_path()
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_feedback_table() -> None:
    with _connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            session_id TEXT,
            message_id TEXT,
            question TEXT,
            answer TEXT,
            rating INTEGER,
            category TEXT,
            comment TEXT,
            created_at TEXT
        )
        """)


def save_feedback(
    *,
    user_id: int | None,
    session_id: str | None,
    message_id: str | None,
    question: str,
    answer: str,
    rating: int,
    category: str | None = None,
    comment: str | None = None,
) -> str:
    init_feedback_table()
    fid = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with _connect() as conn:
        conn.execute(
            "INSERT INTO feedback (id, user_id, session_id, message_id, question, answer, "
            "rating, category, comment, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                fid,
                user_id,
                session_id,
                message_id,
                question,
                answer,
                rating,
                category,
                comment,
                now,
            ),
        )
    return fid


def list_feedback(limit: int = 50) -> list[dict[str, Any]]:
    init_feedback_table()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM feedback ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
