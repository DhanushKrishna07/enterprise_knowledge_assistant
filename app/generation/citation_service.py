"""
app/generation/citation_service.py — Format retrieval chunks into citation objects.
"""

from __future__ import annotations

from typing import Any


def build_citations(
    context_chunks: list[dict[str, Any]],
    answer_text: str | None = None,
    cited_source_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    """
    Convert context chunks into citation dicts.

    Priority for which chunks to include:
    1. cited_source_ids from the LLM response
    2. Inline [N] references in answer_text
    3. Top-scoring chunk only (default)

    Results are deduplicated by (document, page).
    """
    import re
    from app.generation.answer_finalize import NO_ANSWER_REPLY

    # If the answer is a refusal or missing, do not return any citations/sources
    if not answer_text or NO_ANSWER_REPLY in answer_text or "could not find" in answer_text.lower():
        return []

    unique_chunks = _dedupe_chunks(context_chunks)

    used_ids: set[int] = set()
    if cited_source_ids:
        used_ids = {i for i in cited_source_ids if isinstance(i, int) and i > 0}
    elif answer_text:
        for match in re.finditer(r"\[(\d+)\]", answer_text):
            try:
                used_ids.add(int(match.group(1)))
            except ValueError:
                pass

    citations = []
    for i, chunk in enumerate(unique_chunks, start=1):
        if used_ids and i not in used_ids:
            continue
        citations.append(_chunk_to_citation(i, chunk))

    if not citations and unique_chunks:
        citations = [_chunk_to_citation(1, unique_chunks[0])]

    return _dedupe_citations(citations)


def _dedupe_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep best-scoring chunk per document+page."""
    best: dict[tuple[str, str | int | None], dict[str, Any]] = {}
    for chunk in chunks:
        key = (chunk.get("filename", ""), chunk.get("page_number"))
        score = chunk.get("rerank_score_normalized", chunk.get("rerank_score", 0.0))
        existing = best.get(key)
        if existing is None or score > existing.get("_dedupe_score", 0.0):
            entry = dict(chunk)
            entry["_dedupe_score"] = score
            best[key] = entry
    return list(best.values())


def _dedupe_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate document+page entries, keeping highest score."""
    seen: dict[tuple[str, str | int | None], dict[str, Any]] = {}
    for cite in citations:
        key = (cite.get("document", ""), cite.get("page"))
        existing = seen.get(key)
        if existing is None or cite.get("score", 0) > existing.get("score", 0):
            seen[key] = cite
    return list(seen.values())


def _chunk_to_citation(index: int, chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "citation_id": index,
        "document": chunk.get("filename", "Unknown"),
        "page": chunk.get("page_number") or None,
        "chunk_id": chunk.get("chunk_id", ""),
        "snippet": _truncate(chunk.get("text", ""), 300),
        "score": round(
            chunk.get("rerank_score_normalized", chunk.get("rrf_score", 0.0)), 4
        ),
        "content_type": chunk.get("content_type", "text"),
        "extraction_method": chunk.get("extraction_method", ""),
        "section_title": chunk.get("section_title", ""),
        "department": chunk.get("department", ""),
    }


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"
