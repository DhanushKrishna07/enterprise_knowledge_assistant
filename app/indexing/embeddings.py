"""
app/indexing/embeddings.py — BGE embedding service with diskcache caching.

Supports BAAI/bge-small-en-v1.5, bge-base-en-v1.5, bge-m3.
Changing EMBEDDING_MODEL env var requires no code changes.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_model_instance: Any = None
_cache_instance: Any = None


def _get_cache() -> Any:
    global _cache_instance
    if _cache_instance is not None:
        return _cache_instance
    try:
        import diskcache  # type: ignore[import]

        settings = get_settings()
        _cache_instance = diskcache.Cache(settings.cache_path + "/embeddings", size_limit=2**32)
    except ImportError:
        logger.warning("diskcache not installed; embedding cache disabled.")
        _cache_instance = None
    return _cache_instance


def _get_model() -> Any:
    """Load and cache the SentenceTransformer model at process startup."""
    global _model_instance
    if _model_instance is not None:
        return _model_instance
    settings = get_settings()
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import]

        logger.info(
            "Loading embedding model: %s on device: %s",
            settings.embedding_model,
            settings.embedding_device,
        )
        _model_instance = SentenceTransformer(
            settings.embedding_model, device=settings.embedding_device
        )
        logger.info("Embedding model loaded successfully.")
    except Exception as exc:
        logger.error("Failed to load embedding model %s: %s", settings.embedding_model, exc)
        raise
    return _model_instance


def embed_texts(
    texts: list[str],
    *,
    content_hashes: list[str] | None = None,
    batch_size: int = 64,
    normalize: bool = True,
) -> list[list[float]]:
    """
    Embed a list of texts.

    If content_hashes is provided, results are cached by (model, hash).
    Returns a list of embedding vectors (list[float]).
    """
    settings = get_settings()
    cache = _get_cache() if not settings.cache_disabled else None
    model = _get_model()

    results: list[list[float] | None] = [None] * len(texts)
    uncached_indices: list[int] = []

    # Check cache
    if cache is not None and content_hashes is not None:
        for i, (text, h) in enumerate(zip(texts, content_hashes)):
            key = f"{settings.embedding_model}::{h}"
            cached = cache.get(key)
            if cached is not None:
                results[i] = cached
            else:
                uncached_indices.append(i)
    else:
        uncached_indices = list(range(len(texts)))

    # Batch-embed uncached texts
    if uncached_indices:
        uncached_texts = [texts[i] for i in uncached_indices]
        try:
            embeddings = model.encode(
                uncached_texts,
                batch_size=batch_size,
                normalize_embeddings=normalize,
                show_progress_bar=False,
            )
            for batch_pos, orig_idx in enumerate(uncached_indices):
                vec = embeddings[batch_pos].tolist()
                results[orig_idx] = vec
                # Store in cache
                if cache is not None and content_hashes is not None:
                    key = f"{settings.embedding_model}::{content_hashes[orig_idx]}"
                    ttl = settings.embedding_cache_ttl if settings.embedding_cache_ttl > 0 else None
                    cache.set(key, vec, expire=ttl)
        except Exception as exc:
            logger.error("Embedding failed: %s", exc)
            raise

    # Replace any None with empty list (shouldn't happen but safeguard)
    return [r if r is not None else [] for r in results]


def embed_query(query: str) -> list[float]:
    """Embed a single query string with short-TTL disk cache."""
    settings = get_settings()
    cache = _get_cache() if not settings.cache_disabled else None
    cache_key = f"query::{settings.embedding_model}::{query.strip().lower()}"

    if cache is not None:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    model = _get_model()
    try:
        vec = model.encode(
            query,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        result = vec.tolist()
        if cache is not None:
            cache.set(cache_key, result, expire=3600)
        return result
    except Exception as exc:
        logger.error("Query embedding failed: %s", exc)
        raise
