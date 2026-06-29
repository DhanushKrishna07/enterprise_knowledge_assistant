"""
app/retrieval/hybrid.py — Hybrid retrieval: semantic + BM25 fused with Reciprocal Rank Fusion (RRF).

RRF score = sum(1 / (k + rank)) where k=60 by default.
Source diversity: prefer chunks from multiple documents using MMR-style selection.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.cache import cache_get, cache_set, make_retrieval_cache_key
from app.core.config import get_settings
from app.core.logging import get_logger
from app.indexing.bm25_store import get_bm25_store
from app.indexing.chroma_store import query_collection
from app.indexing.embeddings import embed_query
from app.retrieval.filters import build_bm25_where, build_chroma_where

logger = get_logger(__name__)


def _rrf_score(ranks: list[int], k: int = 60) -> float:
    return sum(1.0 / (k + r) for r in ranks)


def hybrid_retrieve(
    query: str,
    *,
    user_role: str = "employee",
    department: str | None = None,
    filter_department: str | None = None,
    document_type: str | None = None,
    author: str | None = None,
    tags: list[str] | None = None,
    policy_version: str | None = None,
    content_types: list[str] | None = None,
    uploaded_after: str | None = None,
    top_k_semantic: int | None = None,
    top_k_keyword: int | None = None,
    top_k_fused: int | None = None,
    diversity_penalty: float = 0.3,
) -> dict[str, Any]:
    """
    Run hybrid retrieval and return fused candidates with full debug metadata.

    Returns
    -------
    dict with keys:
        semantic_results   : list of Chroma result dicts
        keyword_results    : list of BM25 result dicts
        fused_candidates   : deduplicated + RRF-scored candidates
        latencies          : dict of component latency_ms values
    """
    settings = get_settings()
    top_k_s = top_k_semantic or settings.top_k_semantic
    top_k_k = top_k_keyword or settings.top_k_keyword
    top_k_f = top_k_fused or settings.top_k_rerank
    rrf_k = settings.rrf_k

    cache_key = None
    if not settings.cache_disabled:
        cache_key = make_retrieval_cache_key(
            query=query,
            user_role=user_role,
            department=department,
            filters={
                "department": filter_department,
                "document_type": document_type,
                "author": author,
                "tags": tags,
                "policy_version": policy_version,
                "content_types": content_types,
                "uploaded_after": uploaded_after,
            },
            index_version=settings.index_version,
            embedding_model=settings.embedding_model,
        )
        cached = cache_get(cache_key)
        if cached is not None:
            logger.debug("Retrieval cache HIT for: %s", query)
            return cached

    latencies: dict[str, float] = {}

    chroma_where = build_chroma_where(
        user_role=user_role,
        department=department,
        filter_department=filter_department,
        document_type=document_type,
        author=author,
        tags=tags,
        policy_version=policy_version,
        content_types=content_types,
        uploaded_after=uploaded_after,
    )
    bm25_where = build_bm25_where(
        user_role=user_role,
        department=department,
        filter_department=filter_department,
        content_types=content_types,
        document_type=document_type,
        author=author,
        policy_version=policy_version,
    )

    def _run_semantic() -> tuple[list[dict[str, Any]], float]:
        t0 = time.perf_counter()
        query_vec = embed_query(query)
        chroma_raw = query_collection(query_vec, n_results=top_k_s, where=chroma_where)
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        return _parse_semantic_results(chroma_raw, user_role, tags, uploaded_after), elapsed

    def _run_keyword() -> tuple[list[dict[str, Any]], float]:
        t1 = time.perf_counter()
        keyword_raw = get_bm25_store().query(query, n_results=top_k_k, where=bm25_where)
        elapsed = round((time.perf_counter() - t1) * 1000, 1)
        return _parse_keyword_results(keyword_raw, user_role, tags, uploaded_after), elapsed

    with ThreadPoolExecutor(max_workers=2) as pool:
        sem_future = pool.submit(_run_semantic)
        kw_future = pool.submit(_run_keyword)
        semantic_results, semantic_ms = sem_future.result()
        keyword_results, keyword_ms = kw_future.result()

    latencies["semantic_ms"] = semantic_ms
    latencies["keyword_ms"] = keyword_ms

    # ── Reciprocal Rank Fusion ────────────────────────────────────────────────
    t2 = time.perf_counter()

    # Map chunk_id → result dict
    all_by_id: dict[str, dict[str, Any]] = {}
    for r in semantic_results:
        all_by_id[r["chunk_id"]] = r
    for r in keyword_results:
        cid = r["chunk_id"]
        if cid not in all_by_id:
            all_by_id[cid] = r

    # Assign ranks
    sem_rank: dict[str, int] = {r["chunk_id"]: i + 1 for i, r in enumerate(semantic_results)}
    kw_rank: dict[str, int] = {r["chunk_id"]: i + 1 for i, r in enumerate(keyword_results)}

    fused: list[dict[str, Any]] = []
    for cid, result in all_by_id.items():
        ranks = []
        if cid in sem_rank:
            ranks.append(sem_rank[cid])
        if cid in kw_rank:
            ranks.append(kw_rank[cid])
        rrf = _rrf_score(ranks, k=rrf_k)
        entry = dict(result)
        entry["rrf_score"] = rrf
        entry["in_semantic"] = cid in sem_rank
        entry["in_keyword"] = cid in kw_rank
        fused.append(entry)

    fused.sort(key=lambda x: x["rrf_score"], reverse=True)

    # Deduplicate
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for r in fused:
        cid = r["chunk_id"]
        if cid not in seen:
            seen.add(cid)
            deduped.append(r)

    # Fetch missing text content from Chroma for chunks retrieved via BM25 only
    missing_ids = [r["chunk_id"] for r in deduped if not r.get("text")]
    if missing_ids:
        from app.indexing.chroma_store import get_chunks_by_ids

        texts_map = get_chunks_by_ids(missing_ids)
        for r in deduped:
            cid = r["chunk_id"]
            if not r.get("text") and cid in texts_map:
                r["text"] = texts_map[cid]

    # Source diversity: MMR-style — limit same-document dominance
    diverse = _diverse_select(deduped, top_k_f, penalty=diversity_penalty)
    latencies["fusion_ms"] = round((time.perf_counter() - t2) * 1000, 1)

    result = {
        "semantic_results": semantic_results,
        "keyword_results": keyword_results,
        "fused_candidates": deduped,
        "diverse_candidates": diverse,
        "latencies": latencies,
        "counts": {
            "semantic": len(semantic_results),
            "keyword": len(keyword_results),
            "fused": len(deduped),
            "diverse": len(diverse),
        },
    }

    if cache_key is not None:
        cache_set(cache_key, result, ttl=settings.retrieval_cache_ttl)

    return result


def _parse_semantic_results(
    chroma_raw: dict[str, Any],
    user_role: str,
    tags: list[str] | None,
    uploaded_after: str | None,
) -> list[dict[str, Any]]:
    semantic_results: list[dict[str, Any]] = []
    if chroma_raw.get("ids") and chroma_raw["ids"][0]:
        for cid, doc, meta, dist in zip(
            chroma_raw["ids"][0],
            chroma_raw["documents"][0],
            chroma_raw["metadatas"][0],
            chroma_raw["distances"][0],
        ):
            if user_role != "admin":
                roles = [r.strip() for r in meta.get("access_roles", "employee").split(",")]
                if user_role not in roles:
                    continue
            if tags:
                meta_tags = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
                if not all(tag in meta_tags for tag in tags):
                    continue
            if uploaded_after and not _is_after_date(
                meta.get("uploaded_at", meta.get("ingested_at", "")), uploaded_after
            ):
                continue
            score = max(0.0, 1.0 - dist)
            semantic_results.append(
                {
                    "chunk_id": cid,
                    "text": doc,
                    "semantic_score": score,
                    **meta,
                }
            )
    return semantic_results


def _parse_keyword_results(
    keyword_raw: list[dict[str, Any]],
    user_role: str,
    tags: list[str] | None,
    uploaded_after: str | None,
) -> list[dict[str, Any]]:
    keyword_results: list[dict[str, Any]] = []
    for r in keyword_raw:
        if user_role != "admin":
            roles = [role.strip() for role in r.get("access_roles", "employee").split(",")]
            if user_role not in roles:
                continue
        if tags:
            meta_tags = [t.strip() for t in r.get("tags", "").split(",") if t.strip()]
            if not all(tag in meta_tags for tag in tags):
                continue
        if uploaded_after and not _is_after_date(
            r.get("uploaded_at", r.get("ingested_at", "")), uploaded_after
        ):
            continue
        keyword_results.append(r)
    return keyword_results


def _diverse_select(
    candidates: list[dict[str, Any]],
    k: int,
    penalty: float = 0.3,
) -> list[dict[str, Any]]:
    """
    Select up to k candidates, penalizing scores when we've already selected
    a chunk from the same document (MMR-style diversity).
    """
    if not candidates:
        return []

    selected: list[dict[str, Any]] = []
    doc_counts: dict[str, int] = {}
    remaining = list(candidates)

    while len(selected) < k and remaining:
        # Re-score with diversity penalty
        scored = []
        for r in remaining:
            doc_id = r.get("document_id", r.get("filename", ""))
            count = doc_counts.get(doc_id, 0)
            adj_score = r["rrf_score"] * (1.0 - penalty) ** count
            scored.append((adj_score, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1]
        selected.append(best)
        remaining.remove(best)
        doc_id = best.get("document_id", best.get("filename", ""))
        doc_counts[doc_id] = doc_counts.get(doc_id, 0) + 1

    return selected


def _is_after_date(value: str, after: str) -> bool:
    """Return True if value (ISO date string) is on or after the after date."""
    if not value or not after:
        return True
    return value[:10] >= after[:10]
