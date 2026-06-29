"""
app/cache/keys.py — Cache key generators for retrieval and RAG response caching.

Includes ACL/role fields to prevent cross-tenant/cross-role leaks.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def make_retrieval_cache_key(
    query: str,
    user_role: str,
    department: str | None,
    filters: dict[str, Any] | None,
    index_version: int,
    embedding_model: str,
) -> str:
    """
    Generate a cache key for hybrid retrieval results.
    """
    # Deterministic serialized filters
    serialized_filters = json.dumps(filters or {}, sort_keys=True)
    payload = {
        "query": query.strip().lower(),
        "user_role": user_role,
        "department": department or "",
        "filters": serialized_filters,
        "index_version": index_version,
        "embedding_model": embedding_model,
    }
    data_str = json.dumps(payload, sort_keys=True)
    h = hashlib.sha256(data_str.encode("utf-8")).hexdigest()
    return f"retrieval::{h}"


def make_response_cache_key(
    query: str,
    user_role: str,
    department: str | None,
    filters: dict[str, Any] | None,
    retrieved_chunk_ids: list[str],
    retrieved_chunk_hashes: list[str],
    llm_model: str,
    prompt_version: str,
) -> str:
    """
    Generate a cache key for generated answers.
    Includes chunk IDs and hashes to automatically invalidate if documents are updated.
    """
    serialized_filters = json.dumps(filters or {}, sort_keys=True)
    payload = {
        "query": query.strip().lower(),
        "user_role": user_role,
        "department": department or "",
        "filters": serialized_filters,
        "chunk_ids": retrieved_chunk_ids,
        "chunk_hashes": retrieved_chunk_hashes,
        "llm_model": llm_model,
        "prompt_version": prompt_version,
    }
    data_str = json.dumps(payload, sort_keys=True)
    h = hashlib.sha256(data_str.encode("utf-8")).hexdigest()
    return f"response::{h}"


def normalize_query(query: str) -> str:
    """Normalize a user query for stable cache keys."""
    import re

    return re.sub(r"\s+", " ", query.strip().lower())


def make_query_answer_cache_key(
    query: str,
    user_role: str,
    department: str | None,
    filters: dict[str, Any] | None,
    index_version: int,
    prompt_version: str,
) -> str:
    """Cache key for a full answer — checked before retrieval for instant repeat queries."""
    serialized_filters = json.dumps(filters or {}, sort_keys=True)
    payload = {
        "query": normalize_query(query),
        "user_role": user_role,
        "department": department or "",
        "filters": serialized_filters,
        "index_version": index_version,
        "prompt_version": prompt_version,
    }
    data_str = json.dumps(payload, sort_keys=True)
    h = hashlib.sha256(data_str.encode("utf-8")).hexdigest()
    return f"query_answer::{h}"
