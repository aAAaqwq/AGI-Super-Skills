---
name: legal-review
description: Review legal documents (NDA, contracts, agreements) for sensitive clauses, risks, and red flags
---
# Legal Document Review

> Analyze legal documents for sensitive clauses, risks, unfavorable terms, and red flags. Provides structured review with risk assessment and recommendations.

## When to use

- User asks to review an NDA, contract, or legal agreement
- User wants to find sensitive or risky clauses in a legal document
- User needs to understand implications of a legal document before signing
- User asks to compare document terms against standard/fair practices

## Dependencies

- External: python3 (for DOCX extraction via python-docx)

## How to execute

### Step 1: Extract document text

If the document is a DOCX file, extract text:

```python
from docx import Document
doc = Document('path/to/file.docx')
# Handle both paragraph-based and table-based layouts
text_parts = []
for p in doc.paragraphs:
    if p.text.strip():
        text_parts.append(p.text)
for table in doc.tables:
    for row in table.rows:
        for cell in row.cells:
            if cell.text.strip():
                text_parts.append(cell.text)
```

If PDF, use the Read tool directly (it supports PDFs).

### Step 2: Analyze document

Perform structured analysis covering ALL of the following areas:

#### A. Document Overview
- Type of document (NDA, MSA, SoW, etc.)
- Parties involved and their roles
- Effective date and duration
- Governing law and jurisdiction

#### B. Sensitive Clauses Detection

Scan for and flag these categories with severity levels:

| Category | What to look for | Severity |
|----------|-----------------|----------|
| **Non-compete / Non-solicitation** | Restrictions on working with competitors, hiring employees | HIGH |
| **Unlimited liability** | No cap on damages, indemnification without limits | HIGH |
| **Unilateral termination** | One party can terminate freely, other cannot | HIGH |
| **IP assignment** | Broad IP transfer clauses, work-for-hire beyond scope | HIGH |
| **Penalty clauses** | Financial penalties for breach, liquidated damages | HIGH |
| **Governing law mismatch** | Law of unfamiliar jurisdiction, unfavorable forum | MEDIUM |
| **Confidentiality duration** | Unusually long (>5 years) or perpetual obligations | MEDIUM |
| **Auto-renewal / Lock-in** | Automatic extension, difficult exit terms | MEDIUM |
| **Data processing** | Personal data obligations, GDPR/privacy compliance | MEDIUM |
| **Audit rights** | Right to audit your systems, records, premises | MEDIUM |
| **Force majeure** | Missing or one-sided force majeure clause | LOW |
| **Notice requirements** | Unreasonable notice periods, specific delivery methods | LOW |
| **Amendment process** | Unilateral right to modify terms | MEDIUM |
| **Waiver of jury trial** | Waiving right to jury trial or class action | LOW |
| **Survival clauses** | Obligations that survive termination and their duration | LOW |

#### C. Asymmetry Analysis

Check whether obligations are mutual or one-sided:
- Are confidentiality obligations symmetric?
- Are termination rights equal?
- Are liability and indemnification balanced?
- Who bears more risk?

#### D. Missing Clauses

Flag important clauses that are ABSENT:
- Limitation of liability
- Dispute resolution mechanism
- Data protection / GDPR
- Force majeure
- Warranty disclaimers
- Return/destruction of materials timeline

#### E. Language Red Flags

Flag vague or overly broad language:
- "including but not limited to" with open-ended lists
- "sole discretion" granted to one party
- "reasonable" without defined criteria
- "best efforts" vs "commercially reasonable efforts"
- "any and all" sweeping language
- Undefined key terms

### Step 3: Generate report

Output a structured report:

```
## LEGAL DOCUMENT REVIEW

### Document Info
- Type: [NDA/Contract/etc.]
- Parties: [Party A] <-> [Party B]
- Date: [effective date]
- Duration: [term]
- Governing Law: [jurisdiction]

### Risk Summary
- Overall Risk Level: [LOW / MEDIUM / HIGH / CRITICAL]
- HIGH risks found: [count]
- MEDIUM risks found: [count]

### Sensitive Clauses Found

#### [HIGH] [Category Name]
- Clause: [quote or reference]
- Risk: [what this means for you]
- Recommendation: [what to negotiate or change]

#### [MEDIUM] [Category Name]
...

### Asymmetry Issues
- [list of imbalanced terms]

### Missing Protections
- [list of absent but recommended clauses]

### Recommendations
1. [Prioritized list of changes to request before signing]
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `file_path` | Path to the document (DOCX, PDF, or TXT) | required |
| `party` | Which party you represent (for perspective) | auto-detect from context |
| `focus` | Specific areas to focus on (e.g., "IP", "liability") | all areas |

## Examples

### Example 1: Review NDA before signing

User: "Review this NDA from Client G"
-> Extract DOCX, run full analysis, output structured report

### Example 2: Focus on specific concerns

User: "Check this contract for IP risks"
-> Run analysis with focus on IP assignment, work-for-hire, licensing clauses

## Limitations

- This is AI-assisted analysis, NOT legal advice
- Always consult a qualified lawyer for important agreements
- May miss jurisdiction-specific legal nuances
- Cannot verify factual claims (e.g., company registration codes)

## Related skills

- `invoice-generator-agent` — for creating invoices referenced in contracts
- `email-send-bulk` — for sending signed documents back
