"""
app/generation/streaming.py — Server-Sent Events streaming for the /ask/stream endpoint.

Emits typed JSON events:
  retrieval_started | query_rewritten | semantic_search_done | keyword_search_done
  | rerank_done | generation_token | final_sources | done | error
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from app.cache import cache_get, cache_set, make_response_cache_key
from app.cache.query_cache import lookup_query_answer, store_query_answer
from app.core.config import get_settings
from app.core.executors import run_retrieval_fn
from app.core.startup_state import is_warming, wait_for_models
from app.core.logging import get_logger
from app.generation.citation_service import build_citations
from app.generation.ollama_client import chat_complete, check_model_available
from app.generation.answer_finalize import is_out_of_scope_question
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


def _dedupe_for_generation(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return dedupe_context_chunks(chunks)


def _event(event_type: str, data: Any) -> str:
    """Format a single SSE event as a JSON line."""
    return json.dumps({"event": event_type, "data": data}) + "\n"


async def stream_answer(
    question: str,
    *,
    session_id: str | None = None,
    conversation_history: list[dict[str, str]] | None = None,
    top_k_context: int | None = None,
    filters: dict[str, Any] | None = None,
    user_role: str = "employee",
    department: str | None = None,
) -> AsyncIterator[str]:
    """
    Async generator yielding JSON-line SSE events for the streaming answer endpoint.
    """
    import time
    t_start = time.perf_counter()
    settings = get_settings()
    top_k = top_k_context or settings.top_k_context
    filters = filters or {}

    yield _event("retrieval_started", {"session_id": session_id})

    if is_warming() and not await wait_for_models(timeout=90.0):
        yield _event("error", {"message": "Search models are still loading. Please try again in a few seconds."})
        yield _event("done", {})
        return

    # ── Early out-of-scope rejection ───────────────────────────────────────────────
    if is_out_of_scope_question(question):
        logger.info("Out-of-scope question rejected early (stream): %s", question)
        _latency = round((time.perf_counter() - t_start) * 1000, 1)
        yield _event("query_rewritten", {"rewritten_query": question})
        yield _event("semantic_search_done", {"count": 0})
        yield _event("keyword_search_done", {"count": 0})
        yield _event("rerank_done", {"count": 0, "latency_ms": 0})
        yield _event("generation_token", {"token": NO_ANSWER_REPLY})
        yield _event(
            "final_sources",
            {
                "sources": [],
                "answer": NO_ANSWER_REPLY,
                "confidence": 0.0,
                "answerability": "not_found",
                "rewritten_query": question,
                "session_id": session_id,
                "prompt_version": PROMPT_VERSION,
                "retrieval_trace": {
                    "original_question": question,
                    "rewritten_query": question,
                    "filters": {},
                    "latencies": {"total_ms": _latency},
                    "answerability": "not_found",
                    "out_of_scope": True,
                },
            },
        )
        try:
            import uuid as _uuid
            from app.observability.trace import log_request_trace as _log_trace
            _log_trace(
                request_id=str(_uuid.uuid4()),
                session_id=session_id,
                question=question,
                rewritten_query=question,
                latency_ms=_latency,
                details={
                    "answerability": "not_found",
                    "out_of_scope": True,
                    "latencies": {"total_ms": _latency},
                },
            )
        except Exception as _exc:
            logger.warning("Failed to log out-of-scope trace: %s", _exc)
        yield _event("done", {})
        return

    cached_full = lookup_query_answer(
        question,
        user_role=user_role,
        department=filters.get("department") or department,
        filters=filters,
        conversation_history=conversation_history,
    )
    if cached_full is not None:
        logger.info("Query answer cache HIT (early): %s", question)
        rewritten_query = cached_full.get("rewritten_query", question)
        yield _event("query_rewritten", {"rewritten_query": rewritten_query})
        yield _event("semantic_search_done", {"count": 0, "cache_hit": True})
        yield _event("keyword_search_done", {"count": 0, "cache_hit": True})
        yield _event("rerank_done", {"count": 0, "latency_ms": 0, "cache_hit": True})
        answer = cached_full.get("answer", NO_ANSWER_REPLY)
        yield _event("generation_token", {"token": answer})
        latency_ms = round((time.perf_counter() - t_start) * 1000, 1)
        _trace_details = {
            "original_question": question,
            "rewritten_query": rewritten_query,
            "filters": filters,
            "latencies": {"cache_hit": True, "total_ms": latency_ms},
            "answerability": cached_full.get("answerability"),
            "confidence": cached_full.get("confidence", 0.0),
        }
        yield _event(
            "final_sources",
            {
                "sources": cached_full.get("sources", []),
                "answer": answer,
                "confidence": cached_full.get("confidence", 0.0),
                "answerability": cached_full.get("answerability", "answered"),
                "rewritten_query": rewritten_query,
                "session_id": session_id,
                "prompt_version": PROMPT_VERSION,
                "retrieval_trace": _trace_details,
            },
        )
        try:
            import uuid as _uuid
            from app.observability.trace import log_request_trace as _log_trace
            _log_trace(
                request_id=str(_uuid.uuid4()),
                session_id=session_id,
                question=question,
                rewritten_query=rewritten_query,
                latency_ms=latency_ms,
                details=_trace_details,
            )
        except Exception as _exc:
            logger.warning("Failed to log early-cache-hit trace: %s", _exc)
        yield _event("done", {})
        return

    # ── Query rewriting (skip when standalone) ────────────────────────────────
    rewritten_query = question
    should_rewrite = conversation_history and (
        not settings.skip_rewrite_heuristic or needs_query_rewrite(question, conversation_history)
    )
    if should_rewrite:
        try:
            msgs = build_rewrite_messages(question, conversation_history)
            raw = await chat_complete(msgs, max_tokens=settings.rewrite_max_tokens, temperature=0.0)
            raw = strip_think_blocks(raw).strip()
            if raw:
                rewritten_query = raw
        except Exception as exc:
            logger.warning("Rewrite failed: %s", exc)

    yield _event("query_rewritten", {"rewritten_query": rewritten_query})

    retrieval = await run_retrieval_fn(
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
    yield _event("semantic_search_done", {"count": retrieval["counts"]["semantic"]})
    yield _event("keyword_search_done", {"count": retrieval["counts"]["keyword"]})

    ranked, rerank_ms = await run_retrieval_fn(
        rerank, rewritten_query, retrieval["diverse_candidates"], top_k
    )
    yield _event("rerank_done", {"count": len(ranked), "latency_ms": rerank_ms})

    # ── No-answer check ───────────────────────────────────────────────────────
    top_score = ranked[0].get("rerank_score_normalized", 0.0) if ranked else 0.0
    is_no_answer = top_score < settings.no_answer_threshold or not ranked
    context_chunks = _dedupe_for_generation(ranked[:top_k])

    # ── Check Response Cache ──────────────────────────────────────────────────
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
            logger.info("Answer response cache HIT for streaming query: %s", rewritten_query)
            cached_answer = cached_response.get("answer", "")
            cached_sources = cached_response.get("sources", [])
            cached_confidence = cached_response.get("confidence", 0.0)
            cached_answerability = cached_response.get("answerability", "answered")

            yield _event("generation_token", {"token": cached_answer})

            latency_ms = round((time.perf_counter() - t_start) * 1000, 1)
            trace_details = {
                "original_question": question,
                "rewritten_query": rewritten_query,
                "filters": filters,
                "semantic_count": retrieval["counts"]["semantic"],
                "keyword_count": retrieval["counts"]["keyword"],
                "fusion_count": retrieval["counts"]["fused"],
                "reranked_count": len(ranked),
                "selected_count": len(context_chunks),
                "selected_chunk_ids": chunk_ids,
                "latencies": {"rerank_ms": rerank_ms, "cache_hit": True, "total_ms": latency_ms},
                "answerability": cached_answerability,
                "confidence": cached_confidence,
            }
            yield _event(
                "final_sources",
                {
                    "sources": cached_sources,
                    "answer": cached_answer,
                    "confidence": cached_confidence,
                    "answerability": cached_answerability,
                    "rewritten_query": rewritten_query,
                    "session_id": session_id,
                    "prompt_version": PROMPT_VERSION,
                    "retrieval_trace": trace_details,
                },
            )
            try:
                import uuid
                from app.observability.trace import log_request_trace
                log_request_trace(
                    request_id=str(uuid.uuid4()),
                    session_id=session_id,
                    question=question,
                    rewritten_query=rewritten_query,
                    latency_ms=latency_ms,
                    details=trace_details,
                )
            except Exception as exc:
                logger.warning("Failed to log request trace in streaming service: %s", exc)

            yield _event("done", {})
            return

    # ── Answer generation (extraction first — avoids slow LLM) ────────────────
    from app.generation.answer_finalize import finalize_from_llm, try_extract_answer

    cited_source_ids: list[int] | None = None
    quick = (
        try_extract_answer(question, context_chunks, max_sentences=settings.answer_max_sentences)
        if settings.enable_quick_extraction and context_chunks
        else None
    )
    if quick:
        final_answer = quick["answer"]
        answerability = quick["answerability"]
        cited_source_ids = quick.get("cited_sources")
        confidence = top_score if not is_no_answer else 0.85
        yield _event("generation_token", {"token": final_answer})
    elif is_no_answer:
        yield _event("generation_token", {"token": NO_ANSWER_REPLY})
        final_answer = NO_ANSWER_REPLY
        confidence = top_score
        answerability = "not_found"
    elif not await check_model_available():
        result = finalize_from_llm(
            question, context_chunks, "", max_sentences=settings.answer_max_sentences
        )
        final_answer = result["answer"]
        answerability = result["answerability"]
        cited_source_ids = result.get("cited_sources")
        confidence = float(top_score if answerability == "answered" else 0.0)
        yield _event("generation_token", {"token": final_answer})
    else:
        answer_msgs = build_answer_messages(question, context_chunks, rewritten_query)
        full_text = ""
        try:
            # Use chat_complete with the hard LLM_GENERATION_TIMEOUT (default 8s).
            # We were already not streaming tokens to the client, so chat_stream +
            # buffering only added latency (up to llm_stream_timeout = 30s).
            # chat_complete is simpler, faster, and applies the same timeout as
            # the non-streaming /ask endpoint.
            full_text = await asyncio.wait_for(
                chat_complete(
                    answer_msgs,
                    temperature=0.0,
                    max_tokens=settings.answer_max_tokens,
                ),
                timeout=settings.llm_generation_timeout,
            )
            full_text = strip_think_blocks(full_text)
        except asyncio.TimeoutError:
            logger.warning(
                "LLM generation timed out after %ss; using extraction fallback",
                settings.llm_generation_timeout,
            )
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc)
            yield _event("error", {"message": str(exc)})

        result = finalize_from_llm(
            question,
            context_chunks,
            full_text,
            max_sentences=settings.answer_max_sentences,
        )
        final_answer = result["answer"]
        answerability = result["answerability"]
        cited_source_ids = result.get("cited_sources")
        confidence = float(top_score if answerability == "answered" else 0.0)
        # Emit the single clean answer token
        yield _event("generation_token", {"token": final_answer})

    # ── Final sources + done ──────────────────────────────────────────────────
    latency_ms = round((time.perf_counter() - t_start) * 1000, 1)

    citations = build_citations(
        context_chunks,
        final_answer,
        cited_source_ids=cited_source_ids if answerability != "not_found" else None,
    )
    trace_details = {
        "original_question": question,
        "rewritten_query": rewritten_query,
        "filters": filters,
        "semantic_count": retrieval["counts"]["semantic"],
        "keyword_count": retrieval["counts"]["keyword"],
        "fusion_count": retrieval["counts"]["fused"],
        "reranked_count": len(ranked),
        "selected_count": len(context_chunks),
        "selected_chunk_ids": [c.get("chunk_id") for c in context_chunks],
        "latencies": {"rerank_ms": rerank_ms, "cache_hit": False, "total_ms": latency_ms},
        "answerability": answerability,
        "confidence": confidence,
    }
    yield _event(
        "final_sources",
        {
            "sources": citations,
            "answer": final_answer,
            "confidence": round(confidence, 4),
            "answerability": answerability,
            "rewritten_query": rewritten_query,
            "session_id": session_id,
            "prompt_version": PROMPT_VERSION,
            "retrieval_trace": trace_details,
        },
    )

    if cache_key is not None and answerability == "answered":
        response_payload = {
            "answer": final_answer,
            "sources": citations,
            "confidence": round(confidence, 4),
            "session_id": session_id,
            "rewritten_query": rewritten_query,
            "answerability": answerability,
            "latencies": {"rerank_ms": rerank_ms, "cache_hit": False, "total_ms": latency_ms},
            "prompt_version": PROMPT_VERSION,
        }
        cache_set(cache_key, response_payload, ttl=settings.response_cache_ttl)

    store_query_answer(
        question,
        user_role=user_role,
        department=filters.get("department") or department,
        filters=filters,
        conversation_history=conversation_history,
        response={
            "answer": final_answer,
            "sources": citations,
            "confidence": round(confidence, 4),
            "answerability": answerability,
            "rewritten_query": rewritten_query,
            "prompt_version": PROMPT_VERSION,
        },
    )

    await _log_trace_async(
        question=question,
        rewritten_query=rewritten_query,
        session_id=session_id,
        latency_ms=latency_ms,
        trace_details=trace_details,
    )

    yield _event("done", {})


async def _log_trace_async(
    *,
    question: str,
    rewritten_query: str,
    session_id: str | None,
    latency_ms: float,
    trace_details: dict[str, Any],
) -> None:
    try:
        import uuid

        from app.observability.trace import log_request_trace

        await run_retrieval_fn(
            log_request_trace,
            str(uuid.uuid4()),
            session_id,
            question,
            rewritten_query,
            latency_ms,
            trace_details,
        )
    except Exception as exc:
        logger.warning("Failed to log request trace in streaming service: %s", exc)
