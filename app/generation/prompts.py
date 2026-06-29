"""
app/generation/prompts.py — Prompt templates for query rewriting and answer generation.

All prompts target Qwen3 models with /no_think for concise non-thinking output.
"""

from __future__ import annotations

import re
from typing import Any

PROMPT_VERSION = "v2.6"
CHUNK_TEXT_MAX_CHARS = 10000

# ── Query rewriter ────────────────────────────────────────────────────────────

QUERY_REWRITE_SYSTEM = """/no_think
You are an enterprise search query optimizer.
Your ONLY task is to rewrite the user's follow-up question into a standalone search query.

Rules:
- If the question is already standalone (no pronouns/references requiring prior context), return it unchanged.
- If it references prior conversation (e.g., "What about for contractors?"), rewrite it into a self-contained query.
- Keep all entity names, policy names, product names, and acronyms exactly as written.
- Do NOT answer the question.
- Do NOT add explanations.
- Return ONLY the rewritten query on one line.
"""


def build_rewrite_messages(
    question: str,
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Build messages for query rewriting."""
    messages = [{"role": "system", "content": QUERY_REWRITE_SYSTEM}]
    if history:
        context_lines = []
        for turn in history[-6:]:  # last 3 pairs
            role = turn.get("role", "")
            content = turn.get("content", "")
            if role in ("user", "assistant"):
                context_lines.append(f"{role.capitalize()}: {content}")
        if context_lines:
            ctx = "\n".join(context_lines)
            messages.append(
                {
                    "role": "user",
                    "content": f"Prior conversation:\n{ctx}\n\nCurrent question: {question}",
                }
            )
    else:
        messages.append({"role": "user", "content": question})
    return messages


# ── Answer generator ──────────────────────────────────────────────────────────

ANSWER_SYSTEM = """/no_think
You are an Enterprise Knowledge Assistant for NimbusCloud Technologies.
Your ONLY job is to answer questions about the company's internal documents, policies, products, and procedures.

Rules:
- Answer ONLY using the numbered source documents provided below.
- Reply with 1-2 concise factual sentences drawn directly from the sources.
- Do NOT answer general knowledge questions.
- Do NOT use any knowledge outside of the provided source documents.
- If the question cannot be answered from the sources, reply EXACTLY: I could not find this information in the available knowledge base.
- ABSOLUTELY NO internal thinking, no preamble, no explanation, no meta-commentary, and no mention of sources by name.

Examples of CORRECT answers:
I could not find this information in the available knowledge base.
Employees receive 20 days of paid time off per year."""


def dedupe_context_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep unique chunks by chunk_id, preserving retrieval order."""
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for chunk in chunks:
        cid = chunk.get("chunk_id", "")
        if cid and cid in seen:
            continue
        if cid:
            seen.add(cid)
        result.append(chunk)
    return result


def build_answer_messages(
    question: str,
    context_chunks: list[dict[str, Any]],
    rewritten_query: str | None = None,
) -> list[dict[str, str]]:
    """Build messages for answer generation."""
    query_display = rewritten_query or question
    unique_chunks = dedupe_context_chunks(context_chunks)
    context_parts = []
    for i, chunk in enumerate(unique_chunks, start=1):
        filename = chunk.get("filename", "Unknown")
        page = chunk.get("page_number", "")
        page_str = f", p.{page}" if page else ""
        text = _extract_relevant_excerpt(chunk.get("text", ""), query_display)
        context_parts.append(f"[{i}] {filename}{page_str}\n{text}")

    context_str = "\n".join(context_parts)
    user_content = f"Sources:\n{context_str}\n\nQuestion: {query_display}\nAnswer (You MUST respond directly with the final answer. DO NOT include any internal thoughts, reasoning, or 'Hmm...' preambles):"

    return [
        {"role": "system", "content": ANSWER_SYSTEM},
        {"role": "user", "content": user_content},
    ]


def _extract_relevant_excerpt(text: str, query: str, max_chars: int = CHUNK_TEXT_MAX_CHARS) -> str:
    """Find the most relevant paragraph in the chunk, and build a surrounding context window."""
    # We want a default limit of 2000 chars to be safe, fast, and highly contextual
    limit = min(max_chars, 2000)
    if len(text) <= limit:
        return text

    stopwords = {
        "what", "is", "the", "a", "an", "how", "do", "does", "can", "i", "my", "are",
        "was", "were", "be", "of", "in", "to", "for", "and", "or", "it", "that", "this",
        "nimbuscloud", "drive", "technologies", "pvt", "ltd"
    }
    query_terms = {
        t for t in re.findall(r"\w+", query.lower()) if len(t) > 2 and t not in stopwords
    }

    # Split text on any single newline to respect single-spaced documents (like .docx lists)
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return text[:limit]

    # Find the paragraph with the highest score
    best_idx = 0
    best_score = -1
    for idx, p in enumerate(paragraphs):
        p_lower = p.lower()
        score = sum(2 if t in p_lower else 0 for t in query_terms)
        # Boost blocks that look like FAQ Q&A or headings
        if re.match(r"^Q:|\*\*Q:", p, re.IGNORECASE):
            score += 2
        if score > best_score:
            best_score = score
            best_idx = idx

    # Build context window around best_idx (include preceding and succeeding paragraphs)
    window = [paragraphs[best_idx]]
    current_len = len(paragraphs[best_idx])
    
    # Expand window outward
    left = best_idx - 1
    right = best_idx + 1
    while current_len < limit and (left >= 0 or right < len(paragraphs)):
        # Add from right first
        if right < len(paragraphs):
            p_text = paragraphs[right]
            if current_len + len(p_text) + 2 <= limit:
                window.append(p_text)
                current_len += len(p_text) + 2
                right += 1
            else:
                right = len(paragraphs)  # stop right expansion
        # Add from left
        if left >= 0:
            p_text = paragraphs[left]
            if current_len + len(p_text) + 2 <= limit:
                window.insert(0, p_text)
                current_len += len(p_text) + 2
                left -= 1
            else:
                left = -1  # stop left expansion
        if right >= len(paragraphs) and left < 0:
            break

    return "\n\n".join(window)


def _truncate_chunk_text(text: str) -> str:
    if len(text) <= CHUNK_TEXT_MAX_CHARS:
        return text
    return text[:CHUNK_TEXT_MAX_CHARS].rsplit(" ", 1)[0] + "…"


# ── Think block stripper ──────────────────────────────────────────────────────

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_think_blocks(text: str) -> str:
    """Remove Qwen3 hidden thinking blocks from response text."""
    import re
    # Case 1: Standard <think>...</think> tags in the text
    if "<think>" in text.lower():
        if "</think>" in text.lower():
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
        else:
            parts = re.split(r"<think>", text, flags=re.IGNORECASE)
            return parts[0].lstrip()
            
    # Case 2: Hidden <think> injected by Ollama template at start (ends with </think>)
    elif "</think>" in text.lower():
        parts = re.split(r"</think>", text, flags=re.IGNORECASE)
        return parts[1].lstrip()
            
    return text.lstrip()


# ── Follow-up detection (skip rewrite LLM call when unnecessary) ─────────────

_FOLLOWUP_PATTERNS = re.compile(
    r"\b(what about|how about|and for|also|that|those|these|it|they|them|there|"
    r"same|instead|otherwise|compared|versus|vs\.?|for contractors|for employees|"
    r"what if|can you|tell me more|more details|explain further|why|how come)\b",
    re.IGNORECASE,
)


def needs_query_rewrite(question: str, history: list[dict[str, str]] | None) -> bool:
    """Heuristic: only call the rewrite LLM when history exists and question looks like a follow-up."""
    if not history:
        return False
    q = question.strip()
    if len(q) > 80:
        return False
    if _FOLLOWUP_PATTERNS.search(q):
        return True
    words = q.lower().split()
    if len(words) <= 8 and any(w in words for w in ("it", "that", "those", "they", "this", "same")):
        return True
    return False
