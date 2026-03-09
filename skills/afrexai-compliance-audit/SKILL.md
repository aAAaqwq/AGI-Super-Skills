# Compliance Audit Generator

Run internal compliance audits against major frameworks without hiring a consultant.

## What It Does

Generates a structured compliance audit for your organization against any of these frameworks:
- **SOC 2** (Type I & II) — Trust Services Criteria
- **ISO 27001** — Information Security Management
- **GDPR** — Data Protection (EU/UK)
- **HIPAA** — Healthcare Data (US)
- **PCI DSS** — Payment Card Security
- **SOX** — Financial Controls (US public companies)
- **CCPA/CPRA** — California Consumer Privacy

## How to Use

Tell the agent which framework you need audited. Provide context about your organization:
- Industry and size
- Current security controls
- Data types you handle
- Existing certifications
- Known gaps or concerns

### Example Prompts

- "Run a SOC 2 readiness audit for our 40-person SaaS company"
- "Check our GDPR compliance — we process EU customer data and use AWS"
- "Generate an ISO 27001 gap analysis for our fintech startup"
- "Audit our HIPAA controls — we're a healthtech handling PHI"

## Output Format

The agent produces:

### 1. Executive Summary
- Overall readiness score (0-100%)
- Critical gaps count
- Estimated remediation timeline

### 2. Control-by-Control Assessment
For each control domain:
- **Status**: Compliant / Partial / Non-Compliant / Not Assessed
- **Evidence Required**: What auditors will ask for
- **Current Gap**: What's missing
- **Remediation Steps**: Specific actions to close the gap
- **Priority**: Critical / High / Medium / Low
- **Effort**: Hours/days estimate

### 3. Remediation Roadmap
- Phase 1 (0-30 days): Critical fixes
- Phase 2 (30-90 days): High priority items
- Phase 3 (90-180 days): Full compliance

### 4. Evidence Checklist
- Document inventory needed for audit
- Policy templates to create
- Technical configurations to verify

## Agent Instructions

When the user requests a compliance audit:

1. Ask which framework(s) they need assessed
2. Gather context about their organization (industry, size, tech stack, data types)
3. Generate the full audit report following the output format above
4. For each control area, be specific — don't give generic advice. Reference the actual control numbers (e.g., SOC 2 CC6.1, ISO 27001 A.8.2)
5. Prioritize findings by business risk, not alphabetical order
6. Include cost estimates where possible (e.g., "penetration test: $5,000-$15,000")
7. Flag any controls that require third-party tools or services

Be direct. No filler. Every finding should have a clear "do this" action attached.
