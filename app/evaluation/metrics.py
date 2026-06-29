"""
app/evaluation/metrics.py — Metrics calculations for Hit@k, MRR, fact coverage, and no-answer correctness.
"""

from __future__ import annotations

from app.generation.answer_service import NO_ANSWER_REPLY


def calculate_mrr(retrieved_docs: list[str], expected_docs: list[str]) -> float:
    """Compute Reciprocal Rank (MRR) of first matching document."""
    if not expected_docs:
        return 1.0  # Unanswerable queries should ideally retrieve nothing/be handled

    for rank, doc in enumerate(retrieved_docs, start=1):
        for exp in expected_docs:
            if exp.lower() in doc.lower():
                return 1.0 / rank
    return 0.0


def calculate_hit_at_k(retrieved_docs: list[str], expected_docs: list[str], k: int = 5) -> float:
    """Compute Hit Rate @ k (Hit@k)."""
    if not expected_docs:
        return 1.0

    for doc in retrieved_docs[:k]:
        for exp in expected_docs:
            if exp.lower() in doc.lower():
                return 1.0
    return 0.0


def check_fact_coverage(generated_answer: str, expected_facts: list[str]) -> float:
    """Compute percentage of expected answer facts present as substrings in response."""
    if not expected_facts:
        return 1.0

    found = 0
    ans_lower = generated_answer.lower()
    for fact in expected_facts:
        if fact.lower() in ans_lower:
            found += 1
    return found / len(expected_facts)


def evaluate_hallucination_and_no_answer(
    generated_answer: str,
    answerable: bool,
) -> bool:
    """
    Verify if system correctly answered or refused:
    - If answerable is False: answer must be a 'no-answer' refusal.
    - If answerable is True: answer must NOT be a 'no-answer' refusal.
    """
    ans_lower = generated_answer.strip().lower()
    refusal_lower = NO_ANSWER_REPLY.strip().lower()

    is_refusal = (
        refusal_lower in ans_lower
        or "could not find" in ans_lower
        or "information is not available" in ans_lower
        or "i don't know" in ans_lower
    )

    if answerable:
        return not is_refusal
    else:
        return is_refusal
