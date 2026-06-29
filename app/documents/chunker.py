"""
app/documents/chunker.py — Token-aware text chunking with overlap and page/section metadata.

Strategy:
  1. Split by structural boundaries (headings, double newlines).
  2. Token-count each segment using tiktoken.
  3. Merge small segments or split large ones to hit the target chunk size.
  4. Maintain overlap by carrying the tail of the previous chunk.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Default tiktoken encoding; falls back to simple whitespace split if unavailable
_ENCODING: object | None = None


def _get_encoding() -> object | None:
    global _ENCODING
    if _ENCODING is not None:
        return _ENCODING
    try:
        import tiktoken  # type: ignore[import]

        _ENCODING = tiktoken.get_encoding("cl100k_base")
    except Exception:
        logger.warning("tiktoken not available; using whitespace token estimate.")
        _ENCODING = None
    return _ENCODING


def _token_count(text: str) -> int:
    enc = _get_encoding()
    if enc is None:
        return len(text.split())  # rough approximation
    return len(enc.encode(text))  # type: ignore[arg-type]


def _tokens_to_text(tokens: list[int]) -> str:
    enc = _get_encoding()
    if enc is None:
        return " ".join(str(t) for t in tokens)
    return enc.decode(tokens)  # type: ignore[arg-type]


def _encode(text: str) -> list[int]:
    enc = _get_encoding()
    if enc is None:
        return list(range(len(text.split())))
    return enc.encode(text)  # type: ignore[return-value]


@dataclass
class TextChunk:
    text: str
    token_count: int
    page_number: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    section_title: str = ""
    chunk_index: int = 0


# ── Heading detection ─────────────────────────────────────────────────────────

_HEADING_RE = re.compile(
    r"^(#{1,6}\s.+|[A-Z][A-Z0-9 &/]{3,}\s*$)",
    re.MULTILINE,
)


def _detect_section(text: str) -> str:
    """Return the last heading found in a block of text, or empty string."""
    matches = _HEADING_RE.findall(text)
    if matches:
        return matches[-1].strip("# ").strip()
    return ""


# ── Main chunking function ────────────────────────────────────────────────────


def chunk_text(
    text: str,
    *,
    page_number: int | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    section_title: str = "",
    target_tokens: int = 700,
    max_tokens: int = 1_000,
    overlap_tokens: int = 120,
    start_index: int = 0,
) -> list[TextChunk]:
    """
    Split *text* into overlapping token-aware chunks.

    Parameters
    ----------
    text          : The text to chunk.
    page_number   : Source page (for single-page inputs).
    page_start    : First page span (for multi-page inputs).
    page_end      : Last page span.
    section_title : Section heading for this text block.
    target_tokens : Desired chunk size in tokens.
    max_tokens    : Hard cap — never exceed this.
    overlap_tokens: Tokens to carry forward from previous chunk.
    start_index   : Starting chunk_index value (for multi-call sequencing).
    """
    if not text.strip():
        return []

    # Split on structural boundaries: headings or paragraph breaks
    segments = _split_by_structure(text)

    chunks: list[TextChunk] = []
    current_tokens: list[int] = []
    current_section = section_title
    idx = start_index

    def flush(carry_tokens: list[int]) -> list[int]:
        nonlocal idx, current_section
        if not current_tokens:
            return carry_tokens
        chunk_text_str = _tokens_to_text(current_tokens).strip()
        tc = len(current_tokens)
        chunks.append(
            TextChunk(
                text=chunk_text_str,
                token_count=tc,
                page_number=page_number,
                page_start=page_start,
                page_end=page_end,
                section_title=current_section,
                chunk_index=idx,
            )
        )
        idx += 1
        # Return overlap tokens from the end of the current chunk
        return current_tokens[-overlap_tokens:] if overlap_tokens > 0 else []

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue

        heading = _detect_section(seg)
        if heading:
            current_section = heading

        # Preserve paragraph breaks in the token stream
        seg_text = seg + "\n\n"
        seg_tokens = _encode(seg_text)

        # If this single segment already exceeds max_tokens, hard-split it
        if len(seg_tokens) > max_tokens:
            for sub_chunk in _hard_split(seg_tokens, target_tokens, max_tokens, overlap_tokens):
                carry = flush(current_tokens)
                current_tokens = carry + sub_chunk
            continue

        # Will adding this segment exceed max?
        if current_tokens and len(current_tokens) + len(seg_tokens) > max_tokens:
            carry = flush(current_tokens)
            current_tokens = carry + seg_tokens
        else:
            current_tokens.extend(seg_tokens)

        # Flush when we hit target
        if len(current_tokens) >= target_tokens:
            carry = flush(current_tokens)
            current_tokens = carry

    # Final flush
    if current_tokens:
        flush(current_tokens)

    return chunks


def _split_by_structure(text: str) -> list[str]:
    """Split on headings and paragraph breaks."""
    # First split on markdown headings
    parts = re.split(r"(?m)^(#{1,6}\s.+)$", text)
    segments: list[str] = []
    i = 0
    while i < len(parts):
        seg = parts[i]
        # If next part is a heading, prepend it to the following body
        if i + 1 < len(parts) and _HEADING_RE.match(parts[i + 1]):
            segments.append(seg)
            segments.append(parts[i + 1])
            i += 2
        else:
            segments.append(seg)
            i += 1

    # Further split each segment on double newlines (paragraphs)
    result: list[str] = []
    for seg in segments:
        paras = re.split(r"\n{2,}", seg)
        result.extend(p for p in paras if p.strip())

    return result


def _hard_split(
    tokens: list[int],
    target: int,
    max_t: int,
    overlap: int,
) -> list[list[int]]:
    """Force-split a very long token list into max_t-sized windows."""
    chunks: list[list[int]] = []
    start = 0
    while start < len(tokens):
        end = min(start + max_t, len(tokens))
        chunks.append(tokens[start:end])
        start = end - overlap if end < len(tokens) else end
    return chunks


# ── Multi-page chunking ────────────────────────────────────────────────────────


def chunk_pages(
    pages: list[tuple[int, str]],  # list of (page_number, text)
    *,
    section_title: str = "",
    target_tokens: int = 700,
    max_tokens: int = 1_000,
    overlap_tokens: int = 120,
) -> list[TextChunk]:
    """Chunk a list of (page_number, text) pairs, preserving page spans."""
    all_chunks: list[TextChunk] = []
    idx = 0
    # Concatenate all pages and chunk; track page spans via character offsets
    # Simple approach: chunk each page independently and keep page_number
    for page_num, text in pages:
        page_chunks = chunk_text(
            text,
            page_number=page_num,
            page_start=page_num,
            page_end=page_num,
            section_title=section_title,
            target_tokens=target_tokens,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            start_index=idx,
        )
        all_chunks.extend(page_chunks)
        idx += len(page_chunks)
    return all_chunks
