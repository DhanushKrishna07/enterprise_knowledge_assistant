"""
app/cache/cache_service.py — DiskCache-backed cache manager for retrieval and LLM outputs.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_cache_instance: Any = None


def get_cache() -> Any:
    """Lazy initialize the DiskCache client."""
    global _cache_instance
    if _cache_instance is not None:
        return _cache_instance

    settings = get_settings()
    if settings.cache_disabled:
        return None

    try:
        import diskcache  # type: ignore[import]

        _cache_instance = diskcache.Cache(f"{settings.cache_path}/rag", size_limit=2**32)
    except ImportError:
        logger.warning("diskcache not installed; caching disabled.")
        _cache_instance = None
    except Exception as exc:
        logger.warning("Failed to open cache directory: %s", exc)
        _cache_instance = None

    return _cache_instance


def cache_get(key: str) -> Any | None:
    """Retrieve an item from the cache."""
    cache = get_cache()
    if cache is None:
        return None
    try:
        return cache.get(key)
    except Exception as exc:
        logger.warning("Cache get failed for key %s: %s", key, exc)
        return None


def cache_set(key: str, value: Any, ttl: int | None = None) -> bool:
    """Store an item in the cache with an optional TTL in seconds."""
    cache = get_cache()
    if cache is None:
        return False
    try:
        expire = ttl if ttl and ttl > 0 else None
        cache.set(key, value, expire=expire)
        return True
    except Exception as exc:
        logger.warning("Cache set failed for key %s: %s", key, exc)
        return False
