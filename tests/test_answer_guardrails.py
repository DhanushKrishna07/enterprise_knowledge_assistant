from app.evaluation.metrics import evaluate_hallucination_and_no_answer
from app.generation.answer_finalize import (
    clean_llm_text,
    extract_answer_with_score,
    finalize_from_llm,
    is_meta_answer,
    limit_sentences,
    try_extract_answer,
)


def test_evaluate_hallucination_and_refusal():
    assert (
        evaluate_hallucination_and_no_answer(
            "I could not find this information in the available knowledge base.", answerable=False
        )
        is True
    )
    assert (
        evaluate_hallucination_and_no_answer(
            "Employees receive 24 paid leaves annually.", answerable=True
        )
        is True
    )


def test_meta_answer_detection():
    thinking = (
        "Hmm, the user is asking about a refund policy for subscription cancellations. "
        "They want me to give a direct factual answer using only the numbered sources provided."
    )
    assert is_meta_answer(thinking)
    assert not is_meta_answer(
        "Refunds are available within 7 days of a new subscription or renewal charge."
    )


def test_finalize_from_llm_replaces_thinking():
    chunk_text = (
        "**Q: Can I get a refund if I cancel my subscription?**\n\n"
        "Refunds are available within 7 days of a new subscription or renewal charge "
        "if you have not used more than 20% of your storage quota in that period."
    )
    chunks = [{"text": chunk_text, "filename": "Customer_FAQ.md"}]
    thinking = (
        "Hmm, the user is asking about a refund policy. "
        "They want me to give a direct factual answer using only the numbered sources."
    )
    result = finalize_from_llm("what is the refund policy", chunks, thinking)
    assert "Hmm" not in result["answer"]
    assert "7 days" in result["answer"]
    assert result["from_extraction"] is True


def test_try_extract_answer_skips_llm_path():
    chunk_text = (
        "**Q: Can I get a refund if I cancel my subscription?**"
        "Refunds are available within 7 days of a new subscription or renewal charge."
        "**Q: Other question?**Other answer."
    )
    chunks = [{"text": chunk_text, "filename": "Customer_FAQ.md"}]
    result = try_extract_answer("what is the refund policy", chunks)
    assert result is not None
    assert "7 days" in result["answer"]
    assert result["from_extraction"] is True


def test_extract_ignores_weak_matches_for_out_of_scope():
    chunk_text = (
        "**Q: Can I get a refund?**Refunds are available within 7 days.**Q: Other?**Other."
    )
    chunks = [{"text": chunk_text, "filename": "Customer_FAQ.md"}]
    answer, score = extract_answer_with_score(
        "What is NimbusCloud's revenue for the last fiscal year?", chunks
    )
    assert score == 0
    assert answer is None


def test_limit_sentences():
    text = "First sentence. Second sentence. Third sentence."
    assert limit_sentences(text, 2) == "First sentence. Second sentence."


def test_table_extraction_leave():
    from app.generation.answer_finalize import extract_answer_with_score

    text = """| Leave Type | Days per Year | Notes |
| --- | --- | --- |
| Earned Leave (EL) | 18 | Accrues monthly |
| Sick Leave (SL) | 10 | Non-encashable |"""
    chunks = [{"text": text, "filename": "HR_Policy.docx"}]
    ans, score = extract_answer_with_score(
        "How many days of Earned Leave do employees get annually?", chunks
    )
    assert score >= 2
    assert ans is not None
    assert "18" in ans
    assert "earned" in ans.lower()


def test_table_extraction_expense_tier():
    from app.generation.answer_finalize import extract_answer_with_score

    text = """| Expense Amount | Required Approval |
| --- | --- |
| Up to 10,000 | Reporting Manager |
| 10,001 - 50,000 | Reporting Manager + Department Head |
| Above 50,000 | Department Head + Finance Controller |"""
    chunks = [{"text": text, "filename": "Process_Documents.docx"}]
    ans, score = extract_answer_with_score(
        "What is the approval required for an expense claim above 50000?", chunks
    )
    assert score >= 2
    assert ans is not None
    assert "finance controller" in ans.lower()
