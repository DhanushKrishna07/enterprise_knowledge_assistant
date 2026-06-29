"""
app/generation/answer_service.py — Full RAG pipeline: rewrite → retrieve → rerank → generate.

This is the main orchestration function called by the API routes.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.cache import cache_get, cache_set, make_response_cache_key
from app.cache.query_cache import lookup_query_answer, store_query_answer
from app.core.config import get_settings
from app.core.logging import get_logger
from app.generation.answer_finalize import finalize_from_llm, try_extract_answer, is_out_of_scope_question
from app.generation.citation_service import build_citations
from app.core.executors import run_retrieval_fn
from app.core.startup_state import wait_for_models
from app.generation.ollama_client import chat_complete, check_model_available
from app.generation.prompts import (
    PROMPT_VERSION,
    build_answer_messages,
    build_rewrite_messages,
    dedupe_context_chunks,
    needs_query_rewrite,
    strip_think_blocks,
)
from app.retrieval.hybrid import hybrid_retrieve
from app.retrieval.reranker import rerank

logger = get_logger(__name__)

NO_ANSWER_REPLY = "I could not find this information in the available knowledge base."


async def answer_question(
    question: str,
    *,
    session_id: str | None = None,
    conversation_history: list[dict[str, str]] | None = None,
    top_k_context: int | None = None,
    filters: dict[str, Any] | None = None,
    user_role: str = "employee",
    department: str | None = None,
    include_debug: bool = False,
) -> dict[str, Any]:
    """
    Full RAG pipeline (non-streaming).

    Returns a structured response dict matching the API schema.
    """
    settings = get_settings()
    top_k = top_k_context or settings.top_k_context
    filters = filters or {}
    t_total = time.perf_counter()
    latencies: dict[str, float] = {}

    if not await wait_for_models(timeout=90.0):
        return {
            "answer": "Search models are still loading. Please try again in a few seconds.",
            "sources": [],
            "confidence": 0.0,
            "session_id": session_id,
            "rewritten_query": question,
            "answerability": "not_found",
            "retrieval_trace": None,
            "latencies": {"total_ms": round((time.perf_counter() - t_total) * 1000, 1)},
            "prompt_version": PROMPT_VERSION,
        }

    # ── 0. Early out-of-scope rejection ───────────────────────────────────────────
    if is_out_of_scope_question(question):
        logger.info("Out-of-scope question rejected early: %s", question)
        _total_ms = round((time.perf_counter() - t_total) * 1000, 1)
        _log_trace_safe(
            session_id=session_id,
            question=question,
            rewritten_query=question,
            latency_ms=_total_ms,
            answerability="not_found",
            extra={},
        )
        return {
            "answer": NO_ANSWER_REPLY,
            "sources": [],
            "confidence": 0.0,
            "session_id": session_id,
            "rewritten_query": question,
            "answerability": "not_found",
            "retrieval_trace": None,
            "latencies": {"total_ms": _total_ms},
            "prompt_version": PROMPT_VERSION,
        }

    cached_full = lookup_query_answer(
        question,
        user_role=user_role,
        department=filters.get("department") or department,
        filters=filters,
        conversation_history=conversation_history,
    )
    if cached_full is not None:
        logger.info("Query answer cache HIT (early): %s", question)
        _total_ms = round((time.perf_counter() - t_total) * 1000, 1)
        _log_trace_safe(
            session_id=session_id,
            question=question,
            rewritten_query=question,
            latency_ms=_total_ms,
            answerability=str(cached_full.get("answerability", "answered")),
            extra={"cache_hit": True},
        )
        response = dict(cached_full)
        response["session_id"] = session_id
        response["latencies"] = {"cache_hit": True, "total_ms": _total_ms}
        response["retrieval_trace"] = None if not include_debug else {"cache_hit": True}
        return response

    # ── 1. Query rewriting (skip when question is standalone) ───────────────
    rewritten_query = question
    should_rewrite = conversation_history and (
        not settings.skip_rewrite_heuristic or needs_query_rewrite(question, conversation_history)
    )
    if should_rewrite:
        try:
            t0 = time.perf_counter()
            rewrite_msgs = build_rewrite_messages(question, conversation_history)
            raw_rewrite = await chat_complete(
                rewrite_msgs,
                temperature=0.0,
                max_tokens=settings.rewrite_max_tokens,
            )
            raw_rewrite = strip_think_blocks(raw_rewrite).strip()
            if raw_rewrite:
                rewritten_query = raw_rewrite
            latencies["rewrite_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            logger.debug("Rewritten query: %s", rewritten_query)
        except Exception as exc:
            logger.warning("Query rewriting failed; using original question: %s", exc)

    # ── 2. Hybrid retrieval (run in thread pool — CPU-bound) ──────────────────
    t_ret = time.perf_counter()
    retrieval_result = await run_retrieval_fn(
        hybrid_retrieve,
        rewritten_query,
        user_role=user_role,
        department=department,
        filter_department=filters.get("department"),
        document_type=filters.get("document_type"),
        author=filters.get("author"),
        tags=filters.get("tags"),
        policy_version=filters.get("policy_version"),
        content_types=filters.get("content_types"),
        uploaded_after=filters.get("uploaded_after"),
    )
    latencies.update(retrieval_result["latencies"])
    latencies["retrieval_total_ms"] = round((time.perf_counter() - t_ret) * 1000, 1)

    # ── 3. Re-ranking ─────────────────────────────────────────────────────────
    candidates = retrieval_result["diverse_candidates"]
    t_rerank = time.perf_counter()
    ranked_chunks, rerank_ms = await run_retrieval_fn(
        rerank, rewritten_query, candidates, top_k
    )
    latencies["rerank_ms"] = rerank_ms
    latencies["rerank_total_ms"] = round((time.perf_counter() - t_rerank) * 1000, 1)

    # ── 4. No-answer check ────────────────────────────────────────────────────
    top_score = ranked_chunks[0].get("rerank_score_normalized", 0.0) if ranked_chunks else 0.0
    is_no_answer = top_score < settings.no_answer_threshold or not ranked_chunks

    # ── 5. Answer generation ──────────────────────────────────────────────────
    context_chunks = _dedupe_for_generation(ranked_chunks[:top_k])
    t_gen = time.perf_counter()

    cache_key = None
    if settings.enable_response_cache and not settings.cache_disabled and not is_no_answer:
        chunk_ids = [c["chunk_id"] for c in context_chunks]
        chunk_hashes = [c.get("content_hash", "") for c in context_chunks]
        cache_key = make_response_cache_key(
            query=rewritten_query,
            user_role=user_role,
            department=filters.get("department") or department,
            filters=filters,
            retrieved_chunk_ids=chunk_ids,
            retrieved_chunk_hashes=chunk_hashes,
            llm_model=settings.llm_model,
            prompt_version=PROMPT_VERSION,
        )
        cached_response = cache_get(cache_key)
        if cached_response is not None:
            logger.info("Answer response cache HIT for query: %s", rewritten_query)
            response = dict(cached_response)
            response["session_id"] = session_id
            response["latencies"] = dict(response.get("latencies", {}))
            response["latencies"]["total_ms"] = round((time.perf_counter() - t_total) * 1000, 1)
            response["latencies"]["cache_hit"] = True
            _trace_details = {
                "filters": filters,
                "semantic_count": retrieval_result["counts"]["semantic"],
                "keyword_count": retrieval_result["counts"]["keyword"],
                "fusion_count": retrieval_result["counts"]["fused"],
                "reranked_count": len(ranked_chunks),
                "selected_count": len(context_chunks),
                "selected_chunk_ids": chunk_ids,
                "latencies": response["latencies"],
                "answerability": response.get("answerability", "answered"),
                "confidence": response.get("confidence", 0.0),
            }
            if include_debug:
                response["retrieval_trace"] = {
                    "original_question": question,
                    "rewritten_query": rewritten_query,
                    **_trace_details
                }
            else:
                response["retrieval_trace"] = None

            _log_trace_safe(
                session_id=session_id,
                question=question,
                rewritten_query=rewritten_query,
                latency_ms=response["latencies"]["total_ms"],
                answerability=str(response.get("answerability", "answered")),
                extra=_trace_details,
            )
            return response

    cited_source_ids: list[int] | None = None
    quick = (
        try_extract_answer(question, context_chunks, max_sentences=settings.answer_max_sentences)
        if settings.enable_quick_extraction and context_chunks
        else None
    )
    if quick:
        answer_text = quick["answer"]
        answerability = quick["answerability"]
        cited_source_ids = quick.get("cited_sources")
        confidence = compute_confidence(ranked_chunks) if not is_no_answer else 0.85
        logger.info("Answer from source extraction (skipped LLM)")
    elif is_no_answer:
        answer_text = NO_ANSWER_REPLY
        confidence = top_score
        answerability = "not_found"
    elif not await check_model_available():
        result = finalize_from_llm(
            question, context_chunks, "", max_sentences=settings.answer_max_sentences
        )
        answer_text = result["answer"]
        answerability = result["answerability"]
        cited_source_ids = result.get("cited_sources")
        confidence = float(
            compute_confidence(ranked_chunks) if answerability == "answered" else 0.0
        )
    else:
        answer_msgs = build_answer_messages(question, context_chunks, rewritten_query)
        try:
            raw_answer = await asyncio.wait_for(
                chat_complete(
                    answer_msgs,
                    temperature=0.0,
                    max_tokens=settings.answer_max_tokens,
                ),
                timeout=settings.llm_generation_timeout,
            )
            raw_answer = strip_think_blocks(raw_answer)
            result = finalize_from_llm(
                question,
                context_chunks,
                raw_answer,
                max_sentences=settings.answer_max_sentences,
            )
            answer_text = result["answer"]
            answerability = result["answerability"]
            cited_source_ids = result.get("cited_sources")
            confidence = float(
                compute_confidence(ranked_chunks) if answerability == "answered" else 0.0
            )
        except asyncio.TimeoutError:
            logger.warning("LLM generation timed out; using extraction fallback")
            result = finalize_from_llm(
                question, context_chunks, "", max_sentences=settings.answer_max_sentences
            )
            answer_text = result["answer"]
            answerability = result["answerability"]
            cited_source_ids = result.get("cited_sources")
            confidence = float(
                compute_confidence(ranked_chunks) if answerability == "answered" else 0.0
            )
        except Exception as exc:
            logger.error("Answer generation failed: %s", exc)
            answer_text = NO_ANSWER_REPLY
            confidence = 0.0
            answerability = "not_found"
            cited_source_ids = None

    latencies["generation_ms"] = round((time.perf_counter() - t_gen) * 1000, 1)
    latencies["total_ms"] = round((time.perf_counter() - t_total) * 1000, 1)

    citations = build_citations(
        context_chunks,
        answer_text,
        cited_source_ids=cited_source_ids if answerability != "not_found" else None,
    )

    response: dict[str, Any] = {
        "answer": answer_text,
        "sources": citations,
        "confidence": round(confidence, 4),
        "session_id": session_id,
        "rewritten_query": rewritten_query,
        "answerability": answerability,
        "retrieval_trace": None,
        "latencies": latencies,
        "prompt_version": PROMPT_VERSION,
    }

    if include_debug:
        response["retrieval_trace"] = _build_trace(
            question,
            rewritten_query,
            filters,
            retrieval_result,
            ranked_chunks,
            context_chunks,
            latencies,
        )

    if cache_key is not None and answerability == "answered":
        cache_set(cache_key, response, ttl=settings.response_cache_ttl)

    store_query_answer(
        question,
        user_role=user_role,
        department=filters.get("department") or department,
        filters=filters,
        conversation_history=conversation_history,
        response={
            "answer": answer_text,
            "sources": citations,
            "confidence": round(confidence, 4),
            "answerability": answerability,
            "rewritten_query": rewritten_query,
            "prompt_version": PROMPT_VERSION,
        },
    )

    try:
        import uuid

        from app.observability.trace import log_request_trace

        req_id = str(uuid.uuid4())
        log_request_trace(
            request_id=req_id,
            session_id=session_id,
            question=question,
            rewritten_query=rewritten_query,
            latency_ms=latencies.get("total_ms", 0.0),
            details={
                "filters": filters,
                "semantic_count": retrieval_result["counts"]["semantic"],
                "keyword_count": retrieval_result["counts"]["keyword"],
                "fusion_count": retrieval_result["counts"]["fused"],
                "reranked_count": len(ranked_chunks),
                "selected_count": len(context_chunks),
                "selected_chunk_ids": [c.get("chunk_id") for c in context_chunks],
                "latencies": latencies,
                "answerability": answerability,
                "confidence": confidence,
            },
        )
    except Exception as exc:
        logger.warning("Failed to log request trace in answer service: %s", exc)

    return response


def _build_trace(
    question: str,
    rewritten_query: str,
    filters: dict[str, Any],
    retrieval_result: dict[str, Any],
    ranked_chunks: list[dict[str, Any]],
    context_chunks: list[dict[str, Any]],
    latencies: dict[str, float],
) -> dict[str, Any]:
    return {
        "original_question": question,
        "rewritten_query": rewritten_query,
        "filters": filters,
        "semantic_count": retrieval_result["counts"]["semantic"],
        "keyword_count": retrieval_result["counts"]["keyword"],
        "fusion_count": retrieval_result["counts"]["fused"],
        "reranked_count": len(ranked_chunks),
        "selected_count": len(context_chunks),
        "selected_chunk_ids": [c.get("chunk_id") for c in context_chunks],
        "latencies": latencies,
    }


async def _async_hybrid_retrieve(query: str, **kwargs: Any) -> dict[str, Any]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: hybrid_retrieve(query, **kwargs))


async def _async_rerank(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int,
) -> tuple[list[dict[str, Any]], float]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, rerank, query, candidates, top_k)


def _dedupe_for_generation(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return dedupe_context_chunks(chunks)


def compute_confidence(ranked_chunks: list[dict[str, Any]]) -> float:
    """Heuristic confidence from re-ranker scores."""
    if not ranked_chunks:
        return 0.0
    top = ranked_chunks[0].get("rerank_score_normalized", 0.0)
    if len(ranked_chunks) >= 2:
        second = ranked_chunks[1].get("rerank_score_normalized", 0.0)
        if second > 0.6:
            top = min(1.0, top + 0.05)
    return round(top, 4)


def _log_trace_safe(
    *,
    session_id: str | None,
    question: str,
    rewritten_query: str,
    latency_ms: float,
    answerability: str,
    extra: dict[str, Any],
) -> None:
    """Log a request trace for early-exit paths (out-of-scope, cache hits).

    Ensures every request — including those that skip the full pipeline —
    increments the total request count and appears in the traces table.
    """
    try:
        import uuid
        from app.observability.trace import log_request_trace

        log_request_trace(
            request_id=str(uuid.uuid4()),
            session_id=session_id,
            question=question,
            rewritten_query=rewritten_query,
            latency_ms=latency_ms,
            details={"answerability": answerability, **extra},
        )
    except Exception as exc:
        logger.warning("Failed to log early-exit trace: %s", exc)

