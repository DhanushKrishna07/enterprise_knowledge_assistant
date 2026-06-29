# Ground-Truth Test Set — NimbusCloud Technologies Knowledge Base

Use this as your evaluation set for accuracy, citation correctness, and hallucination
prevention. Every "Expected Source" below was verified against the current documents.

## A. Straightforward factual questions (answer should be found verbatim or near-verbatim)

| # | Question | Expected Answer | Expected Source |
|---|----------|------------------|------------------|
| 1 | How many days of Earned Leave do employees get annually? | 18 days | HR_Policy.docx |
| 2 | What is the notice period for a manager who resigns? | 60 days | HR_Policy.docx |
| 3 | How many days of paternity leave are employees entitled to? | 5 days | HR_Policy.docx |
| 4 | What are NimbusCloud Drive's standard working hours? | 9:00 AM to 6:00 PM, Monday through Friday | HR_Policy.docx |
| 5 | How much storage does the Pro plan include? | 1 TB per user | Product_Documentation.pdf, p.1 |
| 6 | What is the refund policy for annual subscriptions? | Refunds are available within 7 days of a new subscription or renewal charge if you have not used more than 20% of your storage quota in that period | Customer_FAQ.md |
| 7 | What is the API rate limit? | 1,000 requests per hour per API key | Product_Documentation.pdf, p.2 |
| 8 | How long is file version history retained on the Business plan? | 365 days | Product_Documentation.pdf, p.1 (see also Recent Release Notes, p.3) |
| 9 | What is the Recovery Time Objective (RTO) for disaster recovery? | 4 hours | Technical_Guide.md |
| 10 | What encryption standard is used for data at rest? | AES-256 | Technical_Guide.md |
| 11 | What is the minimum password length required by the security policy? | 12 characters | Compliance_Guidelines.pdf, p.2 |
| 12 | Within how many hours must a confirmed data breach be disclosed to regulators? | 72 hours | Compliance_Guidelines.pdf, p.2 |
| 13 | What is the first-response SLA for a Critical severity support ticket? | 1 hour (P1) on Enterprise plan | Customer_FAQ.md |
| 14 | What is the minimum seat count for an Enterprise contract? | 100 seats | Sales_Partner_FAQ.pdf, p.1 |
| 15 | How often are penetration tests conducted? | Twice a year | Technical_Guide.md |
| 16 | What is the approval required for an expense claim above ₹50,000? | Department Head + Finance Controller | Process_Documents.docx |
| 17 | How quickly must a critical security vulnerability be patched? | Within 48 hours | Technical_Guide.md (cross-check: IT_Security_Operations.pdf, p.1) |
| 18 | What is the wellness/gym reimbursement cap per year? | ₹5,000 | HR_Policy.docx |
| 19 | What margin does a Gold-tier reseller partner earn? | 15% | Sales_Partner_FAQ.pdf, p.1 |
| 20 | How long does NimbusCloud retain billing and tax records? | 8 years | Compliance_Guidelines.pdf, p.1 |

## B. Cross-document / multi-hop questions (tests multi-document reasoning)

| # | Question | Expected Answer | Expected Sources |
|---|----------|------------------|-------------------|
| 21 | If a customer reports a P1 incident, how fast should the on-call engineer acknowledge it, and what happens if they don't? | Must acknowledge within 10 minutes; if not, it auto-escalates to secondary on-call, then the Engineering Manager | Technical_Guide.md + Process_Documents.docx |
| 22 | An employee wants to claim ₹45,000 in travel expenses. Which policy documents are relevant, and who needs to approve it? | Travel Policy (HR_Policy.docx) sets expense caps (₹10,000 per day domestic cap); approval per Expense Reimbursement Process (Process_Documents.docx) — since amount is between ₹10,001–₹50,000, it needs Reporting Manager + Department Head | HR_Policy.docx, Process_Documents.docx |
| 23 | How does NimbusCloud Drive's SOC 2 certification relate to the security architecture described for engineers? | SOC 2 Type II covers Security, Availability, Confidentiality (Compliance_Guidelines.pdf, p.2); the underlying controls (encryption, access control, vulnerability management) are detailed in Technical_Guide.md | Compliance_Guidelines.pdf p.2, Technical_Guide.md |

## C. Ambiguous questions (tests clarification / reasonable scoping)

| # | Question | Notes |
|---|----------|-------|
| 24 | "What's the leave policy?" | Should return the general Leave Policy table (HR_Policy.docx) rather than guessing which leave type the user means; a good system might ask which leave type, or summarize all types. |
| 25 | "What's the limit?" (no context) | Too vague — a good system should ask for clarification (storage limit? expense limit? rate limit?) rather than picking one at random. |

## D. Out-of-scope questions (should trigger "information not available" — tests hallucination prevention)

These have **no answer** anywhere in the corpus. A well-built system should say it doesn't know, not invent a plausible-sounding number.

| # | Question | Correct Behavior |
|---|----------|-------------------|
| 26 | What is NimbusCloud's revenue for the last fiscal year? | Not in any document — should say information is unavailable |
| 27 | Who is the CEO of NimbusCloud Technologies? | Not stated anywhere — should not invent a name |
| 28 | What is the office address in Bangalore? | No physical address is given anywhere — should not fabricate one |
| 29 | Does NimbusCloud Drive support Linux ARM (e.g., Raspberry Pi)? | System requirements only list Ubuntu/Fedora generically; ARM support is not mentioned — should not assume yes/no with confidence |
| 30 | What was discussed in last week's leadership meeting? | Not in the knowledge base at all |

## E. Near-duplicate / easily-confused questions (tests retrieval precision)

| # | Question | Why it's tricky |
|---|----------|------------------|
| 31 | "What's the password policy?" | Appears only in Compliance_Guidelines.pdf (p.2), but a weak retriever might also pull irrelevant chunks from Technical_Guide.md's authentication section. Good system should cite Compliance_Guidelines.pdf specifically (and may optionally mention the related MFA requirement from Technical_Guide.md). |
| 32 | "What's the escalation process?" | Could match HR's Grievance Redressal (HR_Policy.docx) OR the IT Incident Escalation Process (Process_Documents.docx) — a good system should ask which one, or clearly distinguish both in the answer. |
| 33 | "What's the SLA?" | Could mean Support SLA (Customer_FAQ.md) or P1/P2 incident response times (Process_Documents.docx) — tests whether the system disambiguates rather than merging unrelated numbers into one answer. |

---

### Suggested scoring approach
- **Section A (20 questions):** exact-match or semantic-match accuracy, plus correct document citation. This is your core "Accuracy" metric.
- **Section B (3 questions):** checks whether your system retrieves from >1 document and synthesizes correctly.
- **Section C (2 questions):** checks graceful handling of ambiguity — does it ask, or does it silently guess?
- **Section D (5 questions):** the most important set for **hallucination prevention** — log a fail anytime the system states a fabricated fact instead of saying "not found."
- **Section E (3 questions):** checks retrieval precision when topically similar chunks exist in multiple documents.

You can compute: `Accuracy = correct / total`, `Hallucination Rate = fabricated answers in Section D / 5`, and `Citation Precision = correct doc / total answered`.
