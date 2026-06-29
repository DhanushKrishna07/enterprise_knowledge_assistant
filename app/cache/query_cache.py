"""Fast query-level answer cache — checked before retrieval."""

from __future__ import annotations

from typing import Any

from app.cache.cache_service import cache_get, cache_set
from app.cache.keys import make_query_answer_cache_key
from app.core.config import get_settings
from app.generation.prompts import PROMPT_VERSION


def can_use_query_cache(
    question: str,
    conversation_history: list[dict[str, str]] | None,
) -> bool:
    """Cache standalone questions even within an active chat session."""
    if not conversation_history:
        return True
    from app.generation.prompts import needs_query_rewrite

    return not needs_query_rewrite(question, conversation_history)


def lookup_query_answer(
    question: str,
    *,
    user_role: str,
    department: str | None,
    filters: dict[str, Any] | None,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any] | None:
    settings = get_settings()
    if (
        settings.cache_disabled
        or not settings.enable_response_cache
        or not can_use_query_cache(question, conversation_history)
    ):
        return None

    key = make_query_answer_cache_key(
        query=question,
        user_role=user_role,
        department=department,
        filters=filters,
        index_version=settings.index_version,
        prompt_version=PROMPT_VERSION,
    )
    cached = cache_get(key)
    if cached is None:
        return None
    return dict(cached)


def store_query_answer(
    question: str,
    *,
    user_role: str,
    department: str | None,
    filters: dict[str, Any] | None,
    response: dict[str, Any],
    conversation_history: list[dict[str, str]] | None = None,
) -> None:
    settings = get_settings()
    if (
        settings.cache_disabled
        or not settings.enable_response_cache
        or not can_use_query_cache(question, conversation_history)
    ):
        return

    key = make_query_answer_cache_key(
        query=question,
        user_role=user_role,
        department=department,
        filters=filters,
        index_version=settings.index_version,
        prompt_version=PROMPT_VERSION,
    )
    cache_set(key, response, ttl=settings.response_cache_ttl)
