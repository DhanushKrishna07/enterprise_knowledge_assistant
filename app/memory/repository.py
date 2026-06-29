"""
app/memory/repository.py — Database operations for conversation memory.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.config import get_settings
from app.memory.models import ChatMessage

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


def init_memory_table() -> None:
    """Initialize the chat_messages SQLite table."""
    with _connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id)"
        )


def save_message(msg: ChatMessage) -> None:
    """Save a chat message to SQLite database."""
    init_memory_table()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO chat_messages (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (msg.id, msg.session_id, msg.role, msg.content, msg.created_at),
        )


def get_session_history(session_id: str, limit: int = 30) -> list[ChatMessage]:
    """Retrieve chat history messages for a session ordered by created_at ascending."""
    init_memory_table()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()

    messages = []
    for r in reversed(rows):
        messages.append(
            ChatMessage(
                id=r["id"],
                session_id=r["session_id"],
                role=r["role"],
                content=r["content"],
                created_at=r["created_at"],
            )
        )
    return messages


def clear_session_history(session_id: str) -> None:
    """Delete all messages for a session."""
    init_memory_table()
    with _connect() as conn:
        conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
