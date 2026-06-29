import os

import yaml

# Base realistic questions, facts, and sources based on sample docs.
# We will generate 105 entries total.
items = []

# ── 1. HR Policy (27 items) ──────────────────────────────────────────────────
hr_templates = [
    (
        "How many paid leaves do employees get annually?",
        ["24 paid leaves", "annually"],
        ["HR_Policy.md"],
    ),
    ("What is the annual paid leave allowance?", ["24 paid leaves"], ["HR_Policy.md"]),
    ("How much vacation time is given to staff each year?", ["24 paid leaves"], ["HR_Policy.md"]),
    (
        "How many sick leave days do employees receive per year?",
        ["10 sick leave"],
        ["HR_Policy.md"],
    ),
    ("What is the sick leave policy for employees?", ["10 sick leave"], ["HR_Policy.md"]),
    ("Are contractors entitled to paid leave?", ["not entitled", "contract"], ["HR_Policy.md"]),
    ("Can contract workers request paid vacation?", ["not entitled"], ["HR_Policy.md"]),
    (
        "How many days per week can employees work remotely?",
        ["3 days", "per week"],
        ["HR_Policy.md"],
    ),
    ("What is the remote work policy regarding weekly days?", ["3 days"], ["HR_Policy.md"]),
    (
        "How long is the probationary period for new employees?",
        ["90 days", "probationary"],
        ["HR_Policy.md"],
    ),
    ("What is the probation length for new hires?", ["90 days"], ["HR_Policy.md"]),
    (
        "How many weeks of parental leave does the primary caregiver receive?",
        ["16 weeks", "paid"],
        ["HR_Policy.md"],
    ),
    ("What is the parental leave duration for primary caregivers?", ["16 weeks"], ["HR_Policy.md"]),
    (
        "How many days of bereavement leave are granted for immediate family?",
        ["3 days", "bereavement"],
        ["HR_Policy.md"],
    ),
    ("Is bereavement leave paid or unpaid?", ["paid", "bereavement"], ["HR_Policy.md"]),
    (
        "What is the maximum carry-over of paid leaves to the next year?",
        ["5 days", "carry-over"],
        ["HR_Policy.md"],
    ),
    (
        "Are employees allowed to roll over their vacation days?",
        ["5 days", "carry-over"],
        ["HR_Policy.md"],
    ),
    ("Does the company provide jury duty leave?", ["jury duty", "paid"], ["HR_Policy.md"]),
    (
        "What is the policy on unpaid personal leave?",
        ["unpaid personal leave", "approval"],
        ["HR_Policy.md"],
    ),
    (
        "Can I take unpaid leave without my manager's approval?",
        ["manager approval", "unpaid"],
        ["HR_Policy.md"],
    ),
    (
        "Who is eligible for the Employee Assistance Program?",
        ["all employees", "EAP"],
        ["HR_Policy.md"],
    ),
    ("What services are covered under the EAP?", ["counseling", "mental health"], ["HR_Policy.md"]),
    (
        "When are public holidays observed by the company?",
        ["company calendar", "holidays"],
        ["HR_Policy.md"],
    ),
    ("Do contractors get paid for public holidays?", ["not paid", "contractors"], ["HR_Policy.md"]),
    (
        "What happens to unused leaves upon resignation?",
        ["paid out", "resignation"],
        ["HR_Policy.md"],
    ),
    (
        "Am I compensated for unused leaves when leaving the company?",
        ["paid out", "accrued"],
        ["HR_Policy.md"],
    ),
    (
        "What is the notice period required for taking vacation?",
        ["2 weeks", "notice"],
        ["HR_Policy.md"],
    ),
]

for idx, (q, facts, docs) in enumerate(hr_templates):
    items.append(
        {
            "id": f"hr_ext_{idx + 1:03d}",
            "question": q,
            "expected_answer_facts": facts,
            "expected_sources": [{"document": d} for d in docs],
            "answerable": True,
            "tags": ["hr", "extended"],
        }
    )

# ── 2. Product FAQ & SLAs (27 items) ─────────────────────────────────────────
product_templates = [
    (
        "What is the refund window for customers?",
        ["30 days", "proof of purchase"],
        ["Product_FAQ.md"],
    ),
    ("How long do I have to request a refund?", ["30 days"], ["Product_FAQ.md"]),
    (
        "Can customers get a refund on digital downloads?",
        ["non-refundable", "once accessed"],
        ["Product_FAQ.md"],
    ),
    ("Is it possible to return digital items?", ["non-refundable"], ["Product_FAQ.md"]),
    (
        "What is the SLA for Priority 1 incidents?",
        ["1 hour", "initial response"],
        ["Product_FAQ.md"],
    ),
    ("How fast is the response for a P1 incident?", ["1 hour"], ["Product_FAQ.md"]),
    ("What is the resolution target for Priority 1 incidents?", ["4 hours"], ["Product_FAQ.md"]),
    ("How long does it take to resolve a P1 ticket?", ["4 hours"], ["Product_FAQ.md"]),
    (
        "Which support tier has the fastest response time?",
        ["Enterprise", "1 hour"],
        ["Product_FAQ.md"],
    ),
    ("What is the response time for the Enterprise support tier?", ["1 hour"], ["Product_FAQ.md"]),
    (
        "How long does it take to process a customer data deletion request?",
        ["30 days"],
        ["Product_FAQ.md"],
    ),
    ("What is the timeline for deleting user data under GDPR?", ["30 days"], ["Product_FAQ.md"]),
    ("Do you offer a service level agreement for uptime?", ["99.9%", "uptime"], ["Product_FAQ.md"]),
    ("What is the monthly uptime commitment?", ["99.9%"], ["Product_FAQ.md"]),
    ("What happens if the uptime SLA is breached?", ["service credits"], ["Product_FAQ.md"]),
    (
        "How do I claim service credits for downtime?",
        ["submit ticket", "30 days"],
        ["Product_FAQ.md"],
    ),
    ("What support channels are available for Basic tier?", ["email only"], ["Product_FAQ.md"]),
    (
        "Can Basic support users call phone support?",
        ["no phone support", "email only"],
        ["Product_FAQ.md"],
    ),
    ("What is the response SLA for Priority 2 tickets?", ["4 hours"], ["Product_FAQ.md"]),
    ("What is the response SLA for Priority 3 tickets?", ["12 hours"], ["Product_FAQ.md"]),
    (
        "What are the support hours for Standard tier?",
        ["9 AM to 5 PM", "business days"],
        ["Product_FAQ.md"],
    ),
    (
        "Does Standard support tier include weekend coverage?",
        ["business days only"],
        ["Product_FAQ.md"],
    ),
    (
        "How is the Enterprise tier support coverage structured?",
        ["24/7", "coverage"],
        ["Product_FAQ.md"],
    ),
    ("Do you support single sign-on (SSO)?", ["SAML", "OIDC", "SSO"], ["Product_FAQ.md"]),
    ("Is SSO available on the Basic plan?", ["Enterprise plan only"], ["Product_FAQ.md"]),
    ("Can I export my project data?", ["JSON", "CSV", "export"], ["Product_FAQ.md"]),
    ("What formats are supported for data export?", ["JSON", "CSV"], ["Product_FAQ.md"]),
]

for idx, (q, facts, docs) in enumerate(product_templates):
    items.append(
        {
            "id": f"prod_ext_{idx + 1:03d}",
            "question": q,
            "expected_answer_facts": facts,
            "expected_sources": [{"document": d} for d in docs],
            "answerable": True,
            "tags": ["product", "extended"],
        }
    )

# ── 3. Security & Compliance (26 items) ──────────────────────────────────────
security_templates = [
    (
        "What is the minimum password length required?",
        ["12 characters"],
        ["Security_Compliance.md"],
    ),
    (
        "What are the password complexity requirements?",
        ["12 characters", "uppercase", "number", "special"],
        ["Security_Compliance.md"],
    ),
    ("Is MFA mandatory for VPN connections?", ["mandatory", "VPN"], ["Security_Compliance.md"]),
    (
        "Do I need multi-factor authentication for remote access?",
        ["mandatory", "VPN", "MFA"],
        ["Security_Compliance.md"],
    ),
    (
        "How long does the company have to notify regulators of a GDPR breach?",
        ["72 hours", "GDPR"],
        ["Security_Compliance.md"],
    ),
    (
        "What is the GDPR data breach notification timeline?",
        ["72 hours"],
        ["Security_Compliance.md"],
    ),
    (
        "What should an employee do if they lose a laptop containing customer data?",
        ["Report to Security", "remote wipe"],
        ["Security_Compliance.md"],
    ),
    (
        "Who do I contact if my laptop is stolen?",
        ["Security Incident Response", "report"],
        ["Security_Compliance.md"],
    ),
    (
        "How long is customer PII retained after contract end?",
        ["7 years"],
        ["Security_Compliance.md"],
    ),
    (
        "What is the retention period for personal data?",
        ["7 years", "PII"],
        ["Security_Compliance.md"],
    ),
    (
        "How often must employees complete security awareness training?",
        ["annually", "training"],
        ["Security_Compliance.md"],
    ),
    (
        "Is cybersecurity training mandatory every year?",
        ["mandatory", "annually"],
        ["Security_Compliance.md"],
    ),
    (
        "What classification is used for internal draft documents?",
        ["Confidential", "classification"],
        ["Security_Compliance.md"],
    ),
    (
        "How should Restricted data be handled?",
        ["encryption", "restricted access"],
        ["Security_Compliance.md"],
    ),
    (
        "Is it permitted to use personal USB drives on company laptops?",
        ["prohibited", "USB"],
        ["Security_Compliance.md"],
    ),
    (
        "What is the policy on external storage devices?",
        ["prohibited", "company-issued only"],
        ["Security_Compliance.md"],
    ),
    (
        "How do we report suspicious emails or phishing?",
        ["phishing report button", "forward to security"],
        ["Security_Compliance.md"],
    ),
    (
        "What is the protocol for suspected email phishing?",
        ["report", "phishing"],
        ["Security_Compliance.md"],
    ),
    (
        "Are automatic updates enabled on work computers?",
        ["mandatory", "auto-update"],
        ["Security_Compliance.md"],
    ),
    (
        "Can I disable antivirus software on my laptop?",
        ["prohibited", "antivirus"],
        ["Security_Compliance.md"],
    ),
    (
        "What is the clean desk policy?",
        ["lock screens", "secure papers"],
        ["Security_Compliance.md"],
    ),
    (
        "Do I need to lock my computer when walking away?",
        ["lock screens", "clean desk"],
        ["Security_Compliance.md"],
    ),
    (
        "How are access keys and credentials to cloud environments stored?",
        ["Secret Manager", "vault"],
        ["Security_Compliance.md"],
    ),
    (
        "Is it okay to hardcode credentials in code repositories?",
        ["prohibited", "hardcode"],
        ["Security_Compliance.md"],
    ),
    (
        "What is the policy for reporting security incidents?",
        ["immediate reporting", "within 24 hours"],
        ["Security_Compliance.md"],
    ),
    (
        "Who investigates suspected security breaches?",
        ["Security Operations Center", "SOC"],
        ["Security_Compliance.md"],
    ),
]

for idx, (q, facts, docs) in enumerate(security_templates):
    items.append(
        {
            "id": f"sec_ext_{idx + 1:03d}",
            "question": q,
            "expected_answer_facts": facts,
            "expected_sources": [{"document": d} for d in docs],
            "answerable": True,
            "tags": ["security", "extended"],
        }
    )

# ── 4. IT Processes (15 items) ───────────────────────────────────────────────
it_templates = [
    (
        "How do I request production database access?",
        ["IT Self-Service Portal", "manager approval", "CISO"],
        ["IT_Process_Guide.md"],
    ),
    (
        "What is the procedure for getting database access?",
        ["IT Self-Service Portal", "approval"],
        ["IT_Process_Guide.md"],
    ),
    (
        "How often are company laptops replaced?",
        ["4-year", "refresh cycle"],
        ["IT_Process_Guide.md"],
    ),
    ("When am I eligible for a laptop upgrade?", ["4-year"], ["IT_Process_Guide.md"]),
    (
        "How quickly is system access revoked when an employee is offboarded?",
        ["4 hours", "HR notification"],
        ["IT_Process_Guide.md"],
    ),
    (
        "What is the offboarding SLA for account termination?",
        ["4 hours", "revoked"],
        ["IT_Process_Guide.md"],
    ),
    (
        "What approval levels are required for production database access?",
        ["Direct Manager", "Department Head", "DBA team", "CISO"],
        ["IT_Process_Guide.md"],
    ),
    (
        "Who needs to sign off on a production database access request?",
        ["CISO", "Manager", "DBA"],
        ["IT_Process_Guide.md"],
    ),
    ("How do I request a new software license?", ["IT catalog", "ticket"], ["IT_Process_Guide.md"]),
    (
        "Can I install unauthorized software on my machine?",
        ["prohibited", "whitelisted only"],
        ["IT_Process_Guide.md"],
    ),
    (
        "What is the process for submitting an IT support ticket?",
        ["IT Portal", "email support"],
        ["IT_Process_Guide.md"],
    ),
    (
        "Where do I go to report a broken monitor?",
        ["IT Self-Service", "ticket"],
        ["IT_Process_Guide.md"],
    ),
    (
        "How are guest Wi-Fi accounts requested?",
        ["sponsor approval", "IT desk"],
        ["IT_Process_Guide.md"],
    ),
    (
        "What is the standard configuration time for new hire laptops?",
        ["5 business days"],
        ["IT_Process_Guide.md"],
    ),
    (
        "Who schedules the offboarding equipment return?",
        ["IT Operations", "HR checklist"],
        ["IT_Process_Guide.md"],
    ),
]

for idx, (q, facts, docs) in enumerate(it_templates):
    items.append(
        {
            "id": f"it_ext_{idx + 1:03d}",
            "question": q,
            "expected_answer_facts": facts,
            "expected_sources": [{"document": d} for d in docs],
            "answerable": True,
            "tags": ["it", "extended"],
        }
    )

# ── 5. Unanswerable Hallucination Tests (10 items) ───────────────────────────
unanswerable_templates = [
    "What is the CEO's personal cell phone number?",
    "How much does the company pay for its office leases?",
    "What are the specific dates of the next company retreat?",
    "What is the current stock price of the company?",
    "Which external consulting firm did we hire for the 2025 audit?",
    "What is the password to the company's main safe?",
    "How many coffee machines are there in the HQ office?",
    "What is the formula of the proprietary algorithm we use?",
    "What is the name of the CISO's favorite dog?",
    "When will the company announce its next merger?",
]

for idx, q in enumerate(unanswerable_templates):
    items.append(
        {
            "id": f"unans_ext_{idx + 1:03d}",
            "question": q,
            "expected_answer_facts": [],
            "expected_sources": [],
            "answerable": False,
            "tags": ["no-answer", "hallucination-test", "extended"],
        }
    )

# Write to yaml file
os.makedirs("eval", exist_ok=True)
with open("eval/golden_qa_extended.yaml", "w", encoding="utf-8") as f:
    yaml.dump(items, f, default_flow_style=False, sort_keys=False)

print(f"Successfully generated {len(items)} questions in eval/golden_qa_extended.yaml")
