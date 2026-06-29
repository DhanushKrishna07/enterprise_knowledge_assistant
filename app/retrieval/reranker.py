"""
app/retrieval/reranker.py — Cross-encoder re-ranking using BAAI/bge-reranker-base.

Scores (query, chunk_text) pairs and sorts candidates by relevance.
Model is cached at process startup.
"""

from __future__ import annotations

import re
import time
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_reranker: Any = None


def _get_reranker() -> Any:
    global _reranker
    if _reranker is not None:
        return _reranker
    settings = get_settings()
    if not settings.reranker_model or settings.reranker_model.lower() in ("none", "null", "") or settings.reranker_model.strip().startswith("#"):
        logger.info("Re-ranker is disabled (model name is empty, none, or commented out).")
        return None
    try:
        from sentence_transformers import CrossEncoder  # type: ignore[import]

        logger.info("Loading re-ranker model: %s", settings.reranker_model)
        _reranker = CrossEncoder(settings.reranker_model, device=settings.reranker_device)
        logger.info("Re-ranker loaded successfully.")
    except Exception as exc:
        logger.error("Failed to load re-ranker %s: %s", settings.reranker_model, exc)
        _reranker = None
    return _reranker


def _filename_relevance_boost(query: str, filename: str) -> float:
    """Boost rerank score when the source filename matches query intent."""
    if not filename:
        return 0.0

    fn = re.sub(r"[_\-.]+", " ", filename.lower())
    fn = re.sub(r"\.\w+$", "", fn).strip()
    q = query.lower()

    boost = 0.0
    for word in re.findall(r"\w{3,}", q):
        if word in fn:
            boost += 0.4

    policy_query = any(t in q for t in ("policy", "handbook", "employee", "hr", "leave", "benefit"))
    policy_file = any(t in fn for t in ("hr", "policy", "handbook", "employee"))
    if policy_query and policy_file:
        boost += 2.5

    process_query = any(t in q for t in ("process", "procedure", "workflow", "approval", "expense"))
    process_file = any(t in fn for t in ("process", "procedure", "workflow", "operations"))
    if process_query and process_file:
        boost += 1.5

    return boost


def rerank(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int | None = None,
) -> tuple[list[dict[str, Any]], float]:
    """
    Re-rank candidates using the cross-encoder.

    Parameters
    ----------
    query      : The (possibly rewritten) retrieval query.
    candidates : List of candidate dicts with at least a 'text' field.
    top_k      : How many to keep after re-ranking (None = keep all).

    Returns
    -------
    (ranked_candidates, latency_ms)
    Each candidate dict gets a 'rerank_score' field added.
    """
    settings = get_settings()
    if top_k is None:
        top_k = settings.top_k_context

    if not candidates:
        return [], 0.0

    reranker = _get_reranker()
    t0 = time.perf_counter()

    if reranker is None:
        # Fallback: return candidates as-is (ordered by rrf_score or semantic_score)
        logger.warning("Re-ranker unavailable; returning candidates without re-ranking.")
        for c in candidates:
            c["rerank_score"] = c.get("rrf_score", c.get("semantic_score", 0.0))
    else:
        pairs = [(query, c.get("text", "")) for c in candidates]
        try:
            scores = reranker.predict(pairs, show_progress_bar=False)
            for candidate, score in zip(candidates, scores):
                candidate["rerank_score"] = float(score)
        except Exception as exc:
            logger.error("Re-ranker inference failed: %s", exc)
            for c in candidates:
                c["rerank_score"] = c.get("rrf_score", 0.0)

    for candidate in candidates:
        boost = _filename_relevance_boost(query, candidate.get("filename", ""))
        if boost:
            candidate["rerank_score"] = candidate.get("rerank_score", 0.0) + boost

    latency_ms = round((time.perf_counter() - t0) * 1000, 1) if reranker is not None else 0.0

    ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)

    # Normalize scores to 0–1 using absolute sigmoid so off-topic queries
    # correctly get low scores rather than being inflated by relative normalization.
    # sigmoid(x) maps raw cross-encoder logits to (0, 1).
    import math

    def _sigmoid(x: float) -> float:
        try:
            return 1.0 / (1.0 + math.exp(-x))
        except OverflowError:
            return 0.0 if x < 0 else 1.0

    if reranker is not None:
        # Use absolute sigmoid normalization: truly irrelevant docs stay near 0
        for r in ranked:
            raw = r["rerank_score"]
            r["rerank_score_raw"] = raw
            r["rerank_score_normalized"] = round(_sigmoid(raw), 4)
    else:
        # Fallback (no cross-encoder): use relative normalization on RRF scores
        max_s = ranked[0]["rerank_score"] if ranked else 1.0
        min_s = ranked[-1]["rerank_score"] if ranked else 0.0
        spread = max_s - min_s
        for i, r in enumerate(ranked):
            r["rerank_score_raw"] = r["rerank_score"]
            if spread <= 1e-9:
                r["rerank_score_normalized"] = max(0.0, 1.0 - i * 0.12)
            else:
                r["rerank_score_normalized"] = (r["rerank_score"] - min_s) / spread

    return ranked[:top_k], latency_ms
