"""
app/api/routes_feedback.py — User feedback collection route.
"""

from __future__ import annotations

import datetime
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.api.schemas import FeedbackRequest
from app.core.config import get_settings
from app.core.logging import get_logger

router = APIRouter(prefix="/feedback", tags=["feedback"])
logger = get_logger(__name__)


def _db_path() -> str:
    return get_settings().sqlite_url.replace("sqlite:///", "")


def _connect() -> sqlite3.Connection:
    db = _db_path()
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_table() -> None:
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


@router.post("")
async def submit_feedback(
    request: FeedbackRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    _init_table()
    now = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    fid = str(uuid.uuid4())
    with _connect() as conn:
        # Remove any existing feedback for this message to prevent duplicate counts
        conn.execute("DELETE FROM feedback WHERE message_id = ?", (request.message_id,))
        conn.execute(
            "INSERT INTO feedback (id, user_id, session_id, message_id, question, answer, rating, category, comment, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                fid,
                current_user.get("id"),
                request.session_id,
                request.message_id,
                request.question,
                request.answer,
                request.rating,
                request.category,
                request.comment,
                now,
            ),
        )
    logger.info("Feedback recorded (replaced previous if any): id=%s rating=%d", fid, request.rating)
    return {"id": fid, "status": "recorded"}
