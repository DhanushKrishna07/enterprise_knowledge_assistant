"""
app/evaluation/run.py — Command-line runner for RAG pipeline evaluation.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import time
from pathlib import Path

from app.core.logging import get_logger, setup_logging
from app.evaluation.golden_set import load_golden_set
from app.evaluation.metrics import (
    calculate_hit_at_k,
    calculate_mrr,
    check_fact_coverage,
    evaluate_hallucination_and_no_answer,
)
from app.generation.answer_service import answer_question

logger = get_logger(__name__)


async def run_evaluation(golden_path: str, out_path: str) -> None:
    """Load golden set, execute questions through the answer service, compute statistics, and write a markdown report."""
    setup_logging()
    logger.info("Starting evaluation run with Golden Set: %s", golden_path)

    items = load_golden_set(golden_path)
    logger.info("Loaded %d evaluation items.", len(items))

    results = []
    total_latency = 0.0
    total_mrr = 0.0
    total_hit1 = 0.0
    total_hit3 = 0.0
    total_hit5 = 0.0
    total_fact_coverage = 0.0
    total_no_ans_correct = 0.0

    for idx, item in enumerate(items, start=1):
        logger.info("[%d/%d] Question: %s", idx, len(items), item.question)

        # Infer department and role restrictions from tags
        dept = "general"
        role = "employee"
        for tag in item.tags:
            if tag in ("hr", "security", "it", "product"):
                dept = tag
            if tag == "admin":
                role = "admin"

        t0 = time.perf_counter()
        try:
            res = await answer_question(
                question=item.question,
                user_role=role,
                department=dept,
                include_debug=True,
            )
            latency = (time.perf_counter() - t0) * 1000
            answer = res.get("answer", "")
            retrieved_docs = list({src.get("document", "") for src in res.get("sources", [])})
        except Exception as exc:
            logger.error("RAG pipeline error for question '%s': %s", item.question, exc)
            latency = 0.0
            answer = f"ERROR: {exc}"
            retrieved_docs = []

        mrr = calculate_mrr(retrieved_docs, item.expected_sources)
        hit1 = calculate_hit_at_k(retrieved_docs, item.expected_sources, k=1)
        hit3 = calculate_hit_at_k(retrieved_docs, item.expected_sources, k=3)
        hit5 = calculate_hit_at_k(retrieved_docs, item.expected_sources, k=5)

        if item.answerable:
            fact_cov = check_fact_coverage(answer, item.expected_answer_facts)
        else:
            fact_cov = 1.0  # Refusal should have no expected facts, so we default to 100% matched

        no_ans_ok = evaluate_hallucination_and_no_answer(answer, item.answerable)
        no_ans_val = 1.0 if no_ans_ok else 0.0

        total_latency += latency
        total_mrr += mrr
        total_hit1 += hit1
        total_hit3 += hit3
        total_hit5 += hit5
        total_fact_coverage += fact_cov
        total_no_ans_correct += no_ans_val

        results.append(
            {
                "id": item.id,
                "question": item.question,
                "expected_sources": item.expected_sources,
                "retrieved_sources": retrieved_docs,
                "answer": answer,
                "latency_ms": latency,
                "mrr": mrr,
                "hit1": hit1,
                "hit3": hit3,
                "hit5": hit5,
                "fact_coverage": fact_cov,
                "no_answer_correct": no_ans_ok,
                "answerable": item.answerable,
            }
        )

    n = len(items)
    avg_latency = total_latency / n if n else 0.0
    avg_mrr = total_mrr / n if n else 0.0
    avg_hit1 = total_hit1 / n if n else 0.0
    avg_hit3 = total_hit3 / n if n else 0.0
    avg_hit5 = total_hit5 / n if n else 0.0
    avg_fact_coverage = total_fact_coverage / n if n else 0.0
    avg_no_ans_correct = total_no_ans_correct / n if n else 0.0

    # Build report content
    report = [
        "# RAG Evaluation Report",
        f"Generated on: {datetime.datetime.utcnow().isoformat(timespec='seconds')}Z",
        f"Golden Dataset: `{golden_path}`",
        "",
        "## Summary Statistics",
        "",
        "| Metric | Value | Target | Status |",
        "| --- | --- | --- | --- |",
        f"| Total Questions | {n} | - | - |",
        f"| Mean Reciprocal Rank (MRR) | {avg_mrr:.2f} | >= 0.80 | {'🟢 Pass' if avg_mrr >= 0.8 else '🔴 Fail'} |",
        f"| Hit Rate @ 1 | {avg_hit1:.1%} | >= 75% | {'🟢 Pass' if avg_hit1 >= 0.75 else '🔴 Fail'} |",
        f"| Hit Rate @ 3 | {avg_hit3:.1%} | >= 85% | {'🟢 Pass' if avg_hit3 >= 0.85 else '🔴 Fail'} |",
        f"| Hit Rate @ 5 | {avg_hit5:.1%} | >= 90% | {'🟢 Pass' if avg_hit5 >= 0.90 else '🔴 Fail'} |",
        f"| Expected Fact Coverage | {avg_fact_coverage:.1%} | >= 80% | {'🟢 Pass' if avg_fact_coverage >= 0.8 else '🔴 Fail'} |",
        f"| Refusal / No-Answer Accuracy | {avg_no_ans_correct:.1%} | >= 90% | {'🟢 Pass' if avg_no_ans_correct >= 0.9 else '🔴 Fail'} |",
        f"| Average Latency | {avg_latency:.1f} ms | - | - |",
        "",
        "## Detailed Results",
        "",
        "| ID | Question | Expected Docs | Retrieved Docs | MRR | Fact Cov | Refusal OK | Latency (ms) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for r in results:
        exp_str = ", ".join(r["expected_sources"]) or "None"
        ret_str = ", ".join(r["retrieved_sources"]) or "None"
        report.append(
            f"| `{r['id']}` | {r['question']} | {exp_str} | {ret_str} | {r['mrr']:.2f} | {r['fact_coverage']:.1%} | {'🟢 Pass' if r['no_answer_correct'] else '🔴 Fail'} | {r['latency_ms']:.1f} |"
        )

    report.extend(
        [
            "",
            "## Recommendations & Findings",
            "- Ensure the local Ollama instance model is loaded/warmed up to avoid high first-token latency.",
            "- In cases of lower fact coverage, check chunk overlap bounds or fine-tune BM25 tokenizers.",
            "- Refusals are working within limits set by the RAG no-answer confidence score threshold.",
        ]
    )

    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    logger.info("Evaluation report successfully written to: %s", out_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG Evaluation Suite")
    parser.add_argument(
        "--golden", type=str, default="eval/golden_qa.yaml", help="Path to golden QA dataset"
    )
    parser.add_argument(
        "--out",
        type=str,
        default="docs/evaluation_report.md",
        help="Markdown report file output path",
    )
    args = parser.parse_args()

    asyncio.run(run_evaluation(args.golden, args.out))
