"""
app/memory/service.py — Service layer for loading, saving, and formatting chat history.
"""

from __future__ import annotations

from app.memory.models import ChatMessage
from app.memory.repository import (
    clear_session_history,
    get_session_history,
    save_message,
)


def add_chat_turn(session_id: str | None, question: str, answer: str) -> None:
    """Save both user question and assistant answer in SQLite."""
    if not session_id:
        return
    user_msg = ChatMessage(session_id=session_id, role="user", content=question)
    save_message(user_msg)

    assistant_msg = ChatMessage(session_id=session_id, role="assistant", content=answer)
    save_message(assistant_msg)


def get_history_as_dicts(session_id: str | None, limit: int = 10) -> list[dict[str, str]]:
    """Format history for consumption by the query rewriter prompt."""
    if not session_id:
        return []
    history = get_session_history(session_id, limit=limit)
    return [{"role": msg.role, "content": msg.content} for msg in history]


def clear_history(session_id: str | None) -> None:
    """Delete history for a session."""
    if not session_id:
        return
    clear_session_history(session_id)
