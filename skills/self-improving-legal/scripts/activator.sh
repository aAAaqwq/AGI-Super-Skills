#!/bin/bash
# Legal Self-Improvement Activator Hook
# Triggers on UserPromptSubmit to remind about legal finding capture
# Keep output minimal (~80-120 tokens) to minimize overhead

set -e

cat << 'EOF'
<legal-improvement-reminder>
After completing this task, evaluate if any legal findings should be captured:
- Clause risk identified (unfavorable terms, missing protections, liability issues)?
- Compliance gap discovered (regulatory deadline, audit finding, process gap)?
- Contract deviation found (non-standard terms, unapproved changes)?
- Regulatory change impacting operations (new law, amendment, enforcement action)?
- Precedent shift in relevant jurisdiction (case law, regulatory guidance)?
- Litigation exposure (infringement notice, breach claim, subpoena)?

CRITICAL: NEVER log privileged attorney-client communications, case strategy,
or confidential settlement terms. Abstract to process-level lessons only.

If yes: Log to .learnings/ using the legal self-improvement format.
  - Clause risks/compliance/regulatory → LEARNINGS.md [LRN-YYYYMMDD-XXX]
  - Contract disputes/litigation → LEGAL_ISSUES.md [LEG-YYYYMMDD-XXX]
If high-value (recurring, broadly applicable): Promote to clause library or compliance checklist.
</legal-improvement-reminder>
EOF
