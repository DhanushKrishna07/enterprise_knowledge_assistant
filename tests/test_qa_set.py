#!/usr/bin/env python
"""
tests/test_qa_set.py — Run Ground-Truth Q&A tests against the RAG pipeline (no HTTP).

Usage:
  python tests/test_qa_set.py
  python tests/test_qa_set.py --question "what is the refund policy?"
  python tests/test_qa_set.py --generate
  python tests/test_qa_set.py --section A
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import time
from pathlib import Path

# Disable caches so tests always hit fresh pipeline logic
os.environ.setdefault("CACHE_DISABLED", "true")
os.environ.setdefault("ENABLE_RESPONSE_CACHE", "false")

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.generation.answer_service import answer_question

# Ground-Truth Test Cases mapped exactly from Test_QA_Set.md
SECTION_A = [
    {
        "id": 1,
        "question": "How many days of Earned Leave do employees get annually?",
        "must_contain": ["18"],
        "source": "HR_Policy.docx",
    },
    {
        "id": 2,
        "question": "What is the notice period for a manager who resigns?",
        "must_contain": ["60"],
        "source": "HR_Policy.docx",
    },
    {
        "id": 3,
        "question": "How many days of paternity leave are employees entitled to?",
        "must_contain": ["5"],
        "source": "HR_Policy.docx",
    },
    {
        "id": 4,
        "question": "What are NimbusCloud Drive's standard working hours?",
        "must_contain": ["9:00", "6:00"],
        "source": "HR_Policy.docx",
    },
    {
        "id": 5,
        "question": "How much storage does the Pro plan include?",
        "must_contain": ["1 tb"],
        "source": "Product_Documentation.pdf",
    },
    {
        "id": 6,
        "question": "What is the refund policy for annual subscriptions?",
        "must_contain": ["7 days", "20%"],
        "source": "Customer_FAQ.md",
    },
    {
        "id": 7,
        "question": "What is the API rate limit?",
        "must_contain": ["1,000", "requests"],
        "source": "Product_Documentation.pdf",
    },
    {
        "id": 8,
        "question": "How long is file version history retained on the Business plan?",
        "must_contain": ["365 days"],
        "source": "Product_Documentation.pdf",
    },
    {
        "id": 9,
        "question": "What is the Recovery Time Objective (RTO) for disaster recovery?",
        "must_contain": ["4 hours"],
        "source": "Technical_Guide.md",
    },
    {
        "id": 10,
        "question": "What encryption standard is used for data at rest?",
        "must_contain": ["aes-256"],
        "source": "Technical_Guide.md",
    },
    {
        "id": 11,
        "question": "What is the minimum password length required by the security policy?",
        "must_contain": ["12"],
        "source": "Compliance_Guidelines.pdf",
    },
    {
        "id": 12,
        "question": "Within how many hours must a confirmed data breach be disclosed to regulators?",
        "must_contain": ["72"],
        "source": "Compliance_Guidelines.pdf",
    },
    {
        "id": 13,
        "question": "What is the first-response SLA for a Critical severity support ticket?",
        "must_contain": ["1 hour"],
        "source": "Customer_FAQ.md",
    },
    {
        "id": 14,
        "question": "What is the minimum seat count for an Enterprise contract?",
        "must_contain": ["100"],
        "source": "Sales_Partner_FAQ.pdf",
    },
    {
        "id": 15,
        "question": "How often are penetration tests conducted?",
        "must_contain": ["twice", "year"],
        "source": "Technical_Guide.md",
    },
    {
        "id": 16,
        "question": "What is the approval required for an expense claim above 50,000?",
        "must_contain": ["finance controller", "department head"],
        "source": "Process_Documents.docx",
    },
    {
        "id": 17,
        "question": "How quickly must a critical security vulnerability be patched?",
        "must_contain": ["48 hours"],
        "source": "IT_Security_Operations.pdf",
    },
    {
        "id": 18,
        "question": "What is the wellness/gym reimbursement cap per year?",
        "must_contain": ["5,000"],
        "source": "HR_Policy.docx",
    },
    {
        "id": 19,
        "question": "What margin does a Gold-tier reseller partner earn?",
        "must_contain": ["15%"],
        "source": "Sales_Partner_FAQ.pdf",
    },
    {
        "id": 20,
        "question": "How long does NimbusCloud retain billing and tax records?",
        "must_contain": ["8 years"],
        "source": "Compliance_Guidelines.pdf",
    },
]

SECTION_B = [
    {
        "id": 21,
        "question": "If a customer reports a P1 incident, how fast should the on-call engineer acknowledge it, and what happens if they don't?",
        "must_contain": ["10 minutes", "escalates", "engineering manager"],
        "source": "Process_Documents.docx",
    },
    {
        "id": 22,
        "question": "An employee wants to claim 45,000 in travel expenses. Which policy documents are relevant, and who needs to approve it?",
        "must_contain": ["travel policy", "department head", "manager"],
        "source": "HR_Policy.docx",
    },
    {
        "id": 23,
        "question": "How does NimbusCloud Drive's SOC 2 certification relate to the security architecture described for engineers?",
        "must_contain": ["soc 2", "compliance", "security"],
        "source": "Compliance_Guidelines.pdf",
    },
]

SECTION_C = [
    {
        "id": 24,
        "question": "What's the leave policy?",
        "must_contain": ["earned leave", "sick leave", "casual leave"],
        "source": "HR_Policy.docx",
    },
    {
        "id": 25,
        "question": "What's the limit?",
        "must_contain": ["limit", "storage", "rate", "request"],
        "source": None,
    },
]

SECTION_D = [
    {
        "id": 26,
        "question": "What is NimbusCloud's revenue for the last fiscal year?",
        "must_contain": ["could not find"],
        "source": None,
    },
    {
        "id": 27,
        "question": "Who is the CEO of NimbusCloud Technologies?",
        "must_contain": ["could not find"],
        "source": None,
    },
    {
        "id": 28,
        "question": "What is the office address in Bangalore?",
        "must_contain": ["could not find"],
        "source": None,
    },
    {
        "id": 29,
        "question": "Does NimbusCloud Drive support Linux ARM (e.g., Raspberry Pi)?",
        "must_contain": ["could not find"],
        "source": None,
    },
    {
        "id": 30,
        "question": "What was discussed in last week's leadership meeting?",
        "must_contain": ["could not find"],
        "source": None,
    },
]

SECTION_E = [
    {
        "id": 31,
        "question": "What's the password policy?",
        "must_contain": ["12 characters", "rotated", "90 days"],
        "source": "Compliance_Guidelines.pdf",
    },
    {
        "id": 32,
        "question": "What's the escalation process?",
        "must_contain": ["grievance", "escalation"],
        "source": "HR_Policy.docx",
    },
    {
        "id": 33,
        "question": "What's the SLA?",
        "must_contain": ["support", "sla"],
        "source": "Customer_FAQ.md",
    },
]


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


async def run_one(case: dict) -> dict:
    q = case["question"]
    t0 = time.perf_counter()
    try:
        result = await answer_question(
            q,
            user_role="admin",
            department=None,
            include_debug=False,
        )
    except Exception as exc:
        return {
            "id": case.get("id"),
            "question": q,
            "ok": False,
            "error": str(exc),
            "ms": round((time.perf_counter() - t0) * 1000, 1),
        }

    answer = result.get("answer", "")
    ms = result.get("latencies", {}).get("total_ms", (time.perf_counter() - t0) * 1000)
    norm = _normalize(answer)

    ok = True
    reasons: list[str] = []

    for needle in case.get("must_contain", []):
        if _normalize(needle) not in norm:
            ok = False
            reasons.append(f"missing '{needle}'")

    if case.get("source"):
        sources = result.get("sources") or []
        doc_names = " ".join(s.get("document", s.get("filename", "")) for s in sources).lower()
        if case["source"].lower() not in doc_names:
            ok = False
            reasons.append(f"expected source containing '{case['source']}'")

    return {
        "id": case.get("id"),
        "question": q,
        "answer": answer,
        "ok": ok,
        "reasons": reasons,
        "sources": [s.get("document", s.get("filename", "")) for s in (result.get("sources") or [])],
        "ms": ms,
    }


def cache_clear() -> None:
    try:
        from app.cache.cache_service import get_cache
        cache = get_cache()
        if cache is not None:
            cache.clear()
            print("Cleared response cache.")
    except Exception as exc:
        print(f"Cache clear note: {exc}")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Test RAG Q&A against ground-truth expected answers")
    parser.add_argument("--question", "-q", help="Run a single question")
    parser.add_argument("--section", choices=["A", "B", "C", "D", "E", "all"], default="all")
    parser.add_argument("--generate", "-g", action="store_true", help="Print the full generated answers instead of truncated previews")
    args = parser.parse_args()

    cache_clear()

    if args.question:
        cases = [{"id": "custom", "question": args.question}]
    else:
        if args.section == "A":
            cases = SECTION_A
        elif args.section == "B":
            cases = SECTION_B
        elif args.section == "C":
            cases = SECTION_C
        elif args.section == "D":
            cases = SECTION_D
        elif args.section == "E":
            cases = SECTION_E
        else:
            cases = SECTION_A + SECTION_B + SECTION_C + SECTION_D + SECTION_E

    print("=" * 70, flush=True)
    print(f"RAG Q&A Ground-Truth Test Run ({len(cases)} cases)", flush=True)
    print("=" * 70, flush=True)

    passed = 0
    sys_encoding = sys.stdout.encoding or "utf-8"

    for case in cases:
        row = await run_one(case)
        status = "PASS" if row["ok"] else "FAIL"
        if row["ok"]:
            passed += 1

        print(f"\n[{status}] #{row.get('id')} ({row.get('ms')}ms)", flush=True)
        print(f"  Q: {row['question']}", flush=True)

        if row.get("error"):
            print(f"  ERROR: {row['error']}", flush=True)
        else:
            ans = row.get("answer", "")
            if not args.generate:
                ans = ans[:150] + "..." if len(ans) > 150 else ans
            # Safe print formatting for Windows console
            ans_safe = ans.encode("utf-8", errors="replace").decode(sys_encoding, errors="replace")
            print(f"  A: {ans_safe}", flush=True)

            if row.get("sources"):
                print(f"  Sources: {row['sources']}", flush=True)
            if row.get("reasons"):
                print(f"  Reasons: {', '.join(row['reasons'])}", flush=True)

    print("\n" + "=" * 70, flush=True)
    print(f"Results: {passed}/{len(cases)} passed", flush=True)
    print("=" * 70, flush=True)
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
