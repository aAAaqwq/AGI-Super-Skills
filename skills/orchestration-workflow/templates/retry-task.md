# Task: {TASK_ID} — Retry: {ORIGINAL_TASK_TITLE}

## Previous Attempt
- **Commit**: {PREV_COMMIT or "none"}
- **Failure**: {FAILURE_DESCRIPTION}
- **Root Cause**: {DIAGNOSIS}

## What to Fix
{SPECIFIC_CORRECTION_INSTRUCTIONS}

## Original Requirements
{COPY_FROM_ORIGINAL_PROMPT}

## Constraints
- Max {N} new files, {M} modified files
- Must pass `npm run build`
- **Do NOT repeat the previous mistake**: {WHAT_TO_AVOID}

## Stop Conditions
- Build fails after 2 attempts → stop and report
- Unclear requirement → stop and report (do NOT guess)
