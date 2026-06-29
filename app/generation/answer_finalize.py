"""
app/generation/answer_finalize.py — Turn raw LLM output into a clean, concise answer.

Thinking/meta text is stripped or replaced. Conciseness is enforced by sentence
limiting after generation, not by a low token cap that causes truncation.
"""

from __future__ import annotations

import re
from typing import Any

NO_ANSWER_REPLY = "I could not find this information in the available knowledge base."

_META_PATTERNS = re.compile(
    r"(?:^|\b)(?:hmm|okay|alright|well|so|the user is|they want|i need to|let me|"
    r"let's|let us|i'll|i will|i should|i must|using only|numbered sources?|direct factual|"
    r"note that|looking at|we are given|we have|"
    r"the user asked|give a direct|check the knowledge|knowledge base carefully|"
    r"this document|going through|checking|each source|i'll check|i'll look|i'll go|"
    r"does not mention|doesn't mention|i can see|i see that|from what i|as i can|"
    r"let me look|let me check|let me go|let me see|i'll now|let's check|let's look|"
    r"source\s*:|first,|second,|third,|finally,|in summary|to summarize|in conclusion)\b",
    re.IGNORECASE,
)
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)
_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_PREAMBLE_RE = re.compile(
    r"^(?:based\s+on\s+the\s+(?:provided\s+)?(?:sources?|documents?|knowledge\s+base),?\s*|"
    r"according\s+to\s+the\s+(?:provided\s+)?(?:sources?|documents?|knowledge\s+base),?\s*|"
    r"from\s+the\s+(?:provided\s+)?(?:sources?|documents?|knowledge\s+base),?\s*|"
    r"based\s+on\s+source\s*\[?\d+\]?,?\s*|"
    r"according\s+to\s+source\s*\[?\d+\]?,?\s*|"
    r"in\s+the\s+(?:provided\s+)?(?:sources?|documents?),?\s*)",
    re.IGNORECASE
)
_BOILERPLATE_MARKERS = (
    "employee handbook & hr policy",
    "employee handbook",
    "human resources department",
    "all full-time, confirmed employees",
    "nimbuscloud technologies pvt ltd",
)

# ── Out-of-scope detection ─────────────────────────────────────────────────────
# Questions that are clearly NOT about enterprise documents should be rejected
# before extraction or LLM generation.
_OUT_OF_SCOPE_PATTERNS = re.compile(
    r"\b("
    r"winner|champion|champions|championship|world\s*cup|fifa|nba|nfl|nhl|mlb|ipl|bcci|"
    r"cricket|football|soccer|basketball|baseball|tennis|golf|olympics|olympic|"
    r"score|scoreline|match|tournament|league|stadium|player|athlete|team|squad|"
    r"president|prime\s*minister|politician|election|vote|senator|governor|minister|"
    r"actor|actress|celebrity|singer|musician|band|album|movie|film|series|show|netflix|"
    r"capital\s*of|population\s*of|area\s*of|currency\s*of|language\s*of|address\s*of|location\s*of|where\s*is|"
    r"born\s*in|died\s*in|age\s*of|height\s*of|founder\s*of|invented|discovered|"
    r"weather|temperature|climate|forecast|"
    r"stock\s*price|share\s*price|market\s*cap|cryptocurrency|bitcoin|ethereum|"
    r"recipe|ingredient|cook|bake|boil|fry|"
    r"planet|star|galaxy|universe|nasa|space\s*mission|"
    r"revenue|profit|earnings|fiscal\s*year|annual\s*report|net\s*income|gross\s*margin|"
    r"quarterly\s*results|balance\s*sheet|turnover|valuation|funding|ipo|"
    r"chennai|mumbai|delhi|bangalore|kolkata|hyderabad|pune|india|america|usa|uk|london|paris|tokyo|city"
    r")\b",
    re.IGNORECASE,
)


def is_out_of_scope_question(question: str) -> bool:
    """Return True if the question is clearly outside the enterprise knowledge domain."""
    return bool(_OUT_OF_SCOPE_PATTERNS.search(question))


def try_extract_answer(
    question: str,
    context_chunks: list[dict[str, Any]],
    *,
    max_sentences: int = 2,
    min_score: int = 2,
) -> dict[str, Any] | None:
    """Return a clean extracted answer when sources clearly match (skips LLM)."""
    # Reject questions that are clearly outside the enterprise knowledge domain.
    if is_out_of_scope_question(question):
        return None
    extracted, score = extract_answer_with_score(question, context_chunks)
    if score >= min_score and extracted:
        # Guard: verify the extracted text actually addresses the question.
        # Without this check a billing paragraph can "answer" a revenue question.
        if not answer_matches_query(question, extracted):
            return None
        return {
            "answer": limit_sentences(extracted, max_sentences),
            "answerability": "answered",
            "cited_sources": [1],
            "from_extraction": True,
        }
    return None


def finalize_from_llm(
    question: str,
    context_chunks: list[dict[str, Any]],
    raw_llm: str,
    *,
    max_sentences: int = 2,
) -> dict[str, Any]:
    """Clean LLM output; fall back to extraction if thinking/meta text is detected."""
    # Reject questions that are clearly outside the enterprise knowledge domain.
    if is_out_of_scope_question(question):
        return {
            "answer": NO_ANSWER_REPLY,
            "answerability": "not_found",
            "cited_sources": None,
            "from_extraction": False,
        }

    extracted, extract_score = extract_answer_with_score(question, context_chunks)

    cited_ids = [int(m) for m in re.findall(r"\[(\d+)\]", raw_llm) if m.isdigit()]
    cleaned = clean_llm_text(raw_llm)

    # Check if the LLM successfully refused to answer
    if cleaned and "could not find" in cleaned.lower():
        return {
            "answer": NO_ANSWER_REPLY,
            "answerability": "not_found",
            "cited_sources": None,
            "from_extraction": False,
        }

    if cleaned and not is_meta_answer(cleaned) and not looks_broken(cleaned):
        if answer_matches_query(question, cleaned):
            return {
                "answer": limit_sentences(cleaned, max_sentences),
                "answerability": "answered",
                "cited_sources": cited_ids or None,
                "from_extraction": False,
            }

    if extracted and extract_score >= 2 and answer_matches_query(question, extracted):
        return {
            "answer": limit_sentences(extracted, max_sentences),
            "answerability": "answered",
            "cited_sources": [1],
            "from_extraction": True,
        }

    return {
        "answer": NO_ANSWER_REPLY,
        "answerability": "not_found",
        "cited_sources": None,
        "from_extraction": False,
    }


def finalize_answer(
    question: str,
    context_chunks: list[dict[str, Any]],
    raw_llm: str | None = None,
    *,
    max_sentences: int = 2,
) -> dict[str, Any]:
    """Produce the final user-visible answer."""
    quick = try_extract_answer(question, context_chunks, max_sentences=max_sentences)
    if quick and raw_llm is None:
        return quick
    if raw_llm:
        return finalize_from_llm(question, context_chunks, raw_llm, max_sentences=max_sentences)
    if quick:
        return quick
    return {
        "answer": NO_ANSWER_REPLY,
        "answerability": "not_found",
        "cited_sources": None,
        "from_extraction": False,
    }


def extract_answer_with_score(
    question: str, chunks: list[dict[str, Any]]
) -> tuple[str | None, int]:
    """Extract answer from FAQ blocks, tables, or focused paragraphs."""
    query_terms = _query_terms(question)
    amount = _extract_amount_from_question(question)
    best_answer: str | None = None
    best_score = 0

    for chunk_idx, chunk in enumerate(chunks):
        text = chunk.get("text", "")
        weight = _chunk_weight(chunk, chunk_idx)

        for q_text, a_text in _parse_faq_blocks(text):
            raw = _score_faq_match(query_terms, q_text, a_text)
            if raw <= 0:
                continue
            score = round((raw + 5) * weight)
            if score > best_score:
                best_score = score
                best_answer = _first_answer_sentence(a_text)

        for answer, score in _extract_from_tables(text, query_terms, question, amount):
            score = round(score * weight)
            if score > best_score:
                best_score = score
                best_answer = answer

        for answer, score in _extract_from_paragraphs(text, query_terms):
            score = round(score * weight)
            if score > best_score:
                best_score = score
                best_answer = answer

    if best_score >= 2:
        return best_answer, best_score

    overview = _extract_policy_overview(question, chunks)
    if overview:
        return overview, 8

    return best_answer, best_score


def _extract_policy_overview(
    question: str, chunks: list[dict[str, Any]]
) -> str | None:
    """Return a summary sentence for broad policy/handbook questions."""
    q_lower = question.lower()
    specific_topics = (
        "leave", "notice", "refund", "expense", "approval", "password", "remote",
        "paternity", "maternity", "sick", "earned", "benefit", "resign", "salary",
        "bonus", "travel", "support", "sla", "security", "compliance",
    )
    if any(t in q_lower for t in specific_topics):
        return None

    is_overview = bool(
        re.search(
            r"\b(?:what is|describe|explain|tell me about|overview of)\b.*\b(?:policy|handbook)\b",
            q_lower,
        )
        or re.search(r"\b(?:employee|hr)\s+policy\b", q_lower)
        or q_lower.strip() in ("employee policy", "hr policy", "what is the employee policy?")
    )
    if not is_overview:
        return None

    for chunk in chunks:
        filename = chunk.get("filename", "").lower()
        if not any(k in filename for k in ("hr", "policy", "handbook", "employee")):
            continue
        text = chunk.get("text", "")
        for para in re.split(r"\n\s*\n+", text):
            para = para.strip()
            if len(para) < 60 or para.startswith("|") or para.startswith("#"):
                continue
            if _is_boilerplate(para):
                continue
            lower = para.lower()
            if any(
                k in lower
                for k in ("policy", "handbook", "leave", "employee", "hr", "benefits", "conduct")
            ):
                return _first_answer_sentence(para)
    return None


def _query_terms(question: str) -> list[str]:
    stopwords = {
        "what", "is", "the", "a", "an", "how", "do", "does", "can", "i", "my", "are",
        "was", "were", "be", "of", "in", "to", "for", "and", "or", "it", "that", "this",
        "who", "which", "when", "where", "get", "got",
        # Company-name tokens that appear in every document and carry no
        # discriminative signal for matching (headers, footers, email addresses).
        "nimbuscloud", "nimbus", "cloud", "drive", "technologies", "pvt", "ltd",
        "com", "example", "support",
    }
    terms = [
        t for t in re.findall(r"\w+", question.lower()) if len(t) > 2 and t not in stopwords
    ]
    return terms or re.findall(r"\w{4,}", question.lower())


def _chunk_weight(chunk: dict[str, Any], index: int) -> float:
    return max(0.6, float(chunk.get("rerank_score_normalized", 1.0 - index * 0.12)))


def _parse_faq_blocks(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for match in re.finditer(
        r"\*\*Q:\s*([^*]+)\*\*\s*(.*?)(?=\*\*Q:|##|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    ):
        question = match.group(1).strip()
        answer = match.group(2).strip()
        answer = re.split(r"\*\*Q:", answer, maxsplit=1)[0].strip()
        answer = re.split(r"##", answer, maxsplit=1)[0].strip()
        if answer:
            pairs.append((question, answer))
    return pairs


def _parse_markdown_tables(text: str) -> list[list[list[str]]]:
    """Return list of tables; each table is a list of rows; each row is a list of cells."""
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            if len(current) >= 2:
                tables.append(current)
            current = []
            continue
        if re.match(r"^\|[-:\s|]+\|$", line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if any(cells):
            current.append(cells)
    if len(current) >= 2:
        tables.append(current)
    return tables


def _extract_from_tables(
    text: str,
    query_terms: list[str],
    question: str,
    amount: int | None,
) -> list[tuple[str, int]]:
    results: list[tuple[str, int]] = []
    q_lower = question.lower()

    for table in _parse_markdown_tables(text):
        if len(table) < 2:
            continue
        headers = [h.lower() for h in table[0]]
        header_line = " ".join(headers)

        if _is_metadata_table(headers):
            continue

        if amount is not None and any(k in header_line for k in ("expense", "amount", "approval")):
            tier_answer = _match_amount_tier(table[1:], amount)
            if tier_answer:
                results.append((tier_answer, 10))

        if "notice" in header_line and ("manager" in q_lower or "resign" in q_lower):
            for row in table[1:]:
                row_label = row[0].lower() if row else ""
                if any(k in row_label for k in ("band 4", "band 5", "band 6", "senior", "lead")):
                    results.append(
                        (f"Managers ({row[0]}): {row[1]} notice period.", 12)
                    )
                    break

        for row in table[1:]:
            row_text = " ".join(row).lower()
            score = _score_row_match(query_terms, row, headers, q_lower)
            if score <= 0:
                continue
            answer = _format_table_answer(headers, row, q_lower)
            results.append((answer, score + 3))

    return results


def _is_metadata_table(headers: list[str]) -> bool:
    header_line = " ".join(headers)
    meta_keys = ("field", "details", "document code", "version", "effective date", "owner")
    return sum(1 for k in meta_keys if k in header_line) >= 2


def _match_amount_tier(rows: list[list[str]], amount: int) -> str | None:
    """Pick approval tier for a numeric expense amount."""
    tiers: list[tuple[int | None, int | None, str]] = []
    for row in rows:
        if len(row) < 2:
            continue
        label = row[0]
        approval = row[1].strip()
        label_lower = label.lower()
        nums = [int(n.replace(",", "")) for n in re.findall(r"[\d,]+", label)]
        if "above" in label_lower or "over" in label_lower or "more than" in label_lower:
            threshold = nums[0] if nums else None
            tiers.append((threshold, None, approval))
        elif len(nums) >= 2:
            tiers.append((nums[0], nums[1], approval))
        elif len(nums) == 1 and ("up to" in label_lower or "upto" in label_lower):
            tiers.append((0, nums[0], approval))

    for low, high, approval in tiers:
        if high is None and low is not None and amount >= low:
            return f"Approval required: {approval}."
        if high is not None and low is not None and low <= amount <= high:
            return f"Approval required: {approval}."
        if high is not None and low == 0 and amount <= high:
            return f"Approval required: {approval}."
    return None


def _score_row_match(
    query_terms: list[str],
    row: list[str],
    headers: list[str],
    question_lower: str,
) -> int:
    row_text = " ".join(row).lower()
    strong = [t for t in query_terms if len(t) >= 4] or query_terms
    if not any(t in row_text for t in strong):
        return 0

    score = sum(3 for t in query_terms if t in row[0].lower())
    score += sum(1 for t in query_terms if t in row_text)

    if "manager" in question_lower and any(
        k in row_text for k in ("band 4", "band 5", "band 6", "senior", "lead")
    ):
        score += 6
    if "earned" in question_lower and "earned" in row_text:
        score += 5
    if "notice" in question_lower and "notice" in row_text:
        score += 4
    if "approval" in question_lower and "approval" in " ".join(headers):
        score += 3
    if "expense" in question_lower and "expense" in " ".join(headers):
        score += 3
    return score


def _format_table_answer(headers: list[str], row: list[str], question_lower: str) -> str:
    header_line = " ".join(headers)
    if "leave" in header_line:
        return f"Employees receive {row[1]} of {row[0]} annually."
    if "notice" in header_line:
        return f"{row[0]}: {row[1]} notice period."
    if "approval" in header_line or "expense" in header_line:
        return f"For {row[0]}, approval is required from {row[1]}."
    if len(row) >= 2:
        return f"{row[0]}: {row[1]}."
    return row[0]


def _extract_from_paragraphs(
    text: str, query_terms: list[str]
) -> list[tuple[str, int]]:
    results: list[tuple[str, int]] = []
    # Split on double newlines OR single newlines followed by a bullet/list marker
    # to avoid treating an entire bullet list as a single paragraph.
    split_pattern = r"\n\s*\n+|\n(?=\s*[-*•\d]+\.)|\n(?=\s*[-*•]\s+)"
    for para in re.split(split_pattern, text):
        para = para.strip()
        if len(para) < 20 or para.startswith("|") or para.startswith("#"):
            continue
        if _is_boilerplate(para) or "resign must serve" in para.lower():
            continue
        score = _score_plain_match(query_terms, para)
        if score > 0:
            results.append((_first_answer_sentence(para), score))
    return results


def _extract_amount_from_question(question: str) -> int | None:
    cleaned = re.sub(r"[₹$€]", "", question)
    # Require at least one digit to avoid matching isolated punctuation commas
    matches = re.findall(r"\d[\d,]*", cleaned)
    if not matches:
        return None
    try:
        val = matches[-1].replace(",", "")
        return int(val) if val else None
    except ValueError:
        return None


def _is_boilerplate(text: str) -> bool:
    lower = text.lower()[:250]
    hits = sum(1 for m in _BOILERPLATE_MARKERS if m in lower)
    return hits >= 2 or (hits >= 1 and "outlined below" in lower)


def _score_faq_match(query_terms: list[str], q_text: str, a_text: str) -> int:
    strong = [t for t in query_terms if len(t) >= 4] or query_terms
    combined = f"{q_text} {a_text}".lower()
    if not any(t in combined for t in strong):
        return 0
        
    longest_term = max(query_terms, key=len) if query_terms else ""
    if longest_term and len(longest_term) >= 6 and longest_term not in combined:
        return 0
        
    score = sum(2 for t in query_terms if t in q_text.lower())
    score += sum(1 for t in query_terms if t in a_text.lower())
    return score


def _score_plain_match(query_terms: list[str], para: str) -> int:
    strong = [t for t in query_terms if len(t) >= 4] or query_terms
    lower = para.lower()
    if not any(t in lower for t in strong):
        return 0
        
    longest_term = max(query_terms, key=len) if query_terms else ""
    if longest_term and len(longest_term) >= 6 and longest_term not in lower:
        return 0
        
    return sum(1 for t in query_terms if t in lower)


def _first_answer_sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return limit_sentences(text, 2)


def answer_matches_query(question: str, answer: str) -> bool:
    """Return True only when the answer genuinely addresses the question.

    Two-gate check:
    1. The single most-distinctive term (longest, >= 5 chars) MUST appear.
       This stops a billing answer satisfying a revenue question.
    2. At least one of the remaining key terms must also appear.
    """
    stopwords = {
        "what", "is", "the", "a", "an", "how", "do", "does", "can", "are", "was", "were",
        "about", "many", "much", "last", "first", "does", "nimbuscloud", "required",
        "that", "this", "with", "from", "have", "will", "your", "their",
        # Generic question/topic words — appear in every enterprise Q, not discriminating
        "policy", "policies", "procedure", "procedures", "information", "details",
        "tell", "explain", "describe", "rules", "guideline", "guidelines",
        "requirements", "requirement",
    }
    terms = [t for t in re.findall(r"\w+", question.lower()) if len(t) >= 4 and t not in stopwords]
    if not terms:
        return True
    lower = answer.lower()

    # Gate 1: the longest (most specific) key term must be present
    longest = max(terms, key=len)
    if len(longest) >= 5 and longest not in lower:
        return False

    # Gate 2: at least one term must appear
    return any(t in lower for t in terms)


def is_meta_answer(text: str) -> bool:
    if _META_PATTERNS.search(text):
        return True
    lower = text.lower()
    return any(
        p in lower
        for p in (
            "user is asking",
            "they want me",
            "sources provided",
            "numbered source",
            "factual answer using",
            "provided text seems",
            "no actual employee policy",
            "document is clearly about",
        )
    )


def looks_broken(text: str) -> bool:
    text = text.strip()
    if not text or len(text) < 15:
        return True
    if text.endswith(('"', "Q", ":", "-", "…", "**")):
        return True
    return False


def clean_llm_text(raw: str) -> str:
    # Discard all text preceding the closing </think> tag if present
    if "</think>" in raw:
        raw = raw.split("</think>", 1)[1]
        
    text = _THINK_TAG_RE.sub("", raw)
    text = _FENCE_RE.sub("", text).strip()
    # Remove [n] citation markers
    text = re.sub(r"\s*\[\d+\]\s*", " ", text).strip()
    # Remove "Source : filename.pdf, p.1" style lines the model emits when reasoning
    text = re.sub(
        r"Source\s*:\s*[^.!?\n]+(?:\.|\n|$)",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    # Remove numbered/ordered list markers the model uses while analysing ("1.", "2.", etc.)
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    
    # Repeatedly strip introductory preambles (e.g. "Based on the provided sources...")
    prev = ""
    while prev != text:
        prev = text
        text = _PREAMBLE_RE.sub("", text).strip()
        
    # Split into sentences and drop any sentence that contains meta/reasoning language
    sentences = re.split(r"(?<=[.!?])\s+", text)
    cleaned_sentences = []
    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue
        if _META_PATTERNS.search(s_clean):
            continue
        # Also drop bare source-navigation sentences like "Source HR_Policy.docx states:"
        if re.match(r"^(?:source|document|file)\b", s_clean, re.IGNORECASE):
            continue
        cleaned_sentences.append(s_clean)
        
    text = " ".join(cleaned_sentences).strip()
    return text


def limit_sentences(text: str, max_sentences: int = 2) -> str:
    text = text.strip()
    if not text:
        return text
    parts = re.split(r"(?<=[.!?])\s+", text)
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return text
    return " ".join(parts[:max_sentences]).strip()
