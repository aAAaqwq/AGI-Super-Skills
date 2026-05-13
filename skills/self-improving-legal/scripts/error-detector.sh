#!/bin/bash
# Legal Self-Improvement Error Detector Hook
# Triggers on PostToolUse for Bash to detect legal-relevant patterns
# Reads CLAUDE_TOOL_OUTPUT environment variable

set -e

OUTPUT="${CLAUDE_TOOL_OUTPUT:-}"

LEGAL_PATTERNS=(
    "breach"
    "violation"
    "non-compliance"
    "noncompliance"
    "litigation"
    "injunction"
    "subpoena"
    "infringement"
    "GDPR"
    "CCPA"
    "deadline"
    "overdue"
    "penalty"
    "regulatory"
    "non-compete"
    "indemnity"
    "liability"
    "arbitration"
    "cease and desist"
    "cease-and-desist"
    "class action"
    "settlement"
    "deposition"
    "discovery"
    "compliance"
    "filing"
    "statute of limitations"
    "force majeure"
    "confidentiality"
    "trade secret"
    "patent"
    "trademark"
    "copyright"
    "HIPAA"
    "SOX"
    "sanctions"
    "anti-trust"
    "antitrust"
)

contains_legal_pattern=false
matched_pattern=""
for pattern in "${LEGAL_PATTERNS[@]}"; do
    if [[ "$OUTPUT" == *"$pattern"* ]]; then
        contains_legal_pattern=true
        matched_pattern="$pattern"
        break
    fi
done

if [ "$contains_legal_pattern" = true ]; then
    cat << EOF
<legal-finding-detected>
Legal-relevant pattern detected in command output: "$matched_pattern"

Consider logging to .learnings/ if:
- A contract clause risk or deviation was identified
- A compliance gap or regulatory issue was found
- A litigation-related matter was discovered
- A regulatory deadline or filing requirement was revealed
- An IP infringement or trade secret issue surfaced

CRITICAL: NEVER log privileged attorney-client communications, case strategy,
or confidential settlement terms. Abstract to process-level lessons only.

Format: [LEG-YYYYMMDD-XXX] for legal issues, [LRN-YYYYMMDD-XXX] for learnings.
</legal-finding-detected>
EOF
fi
