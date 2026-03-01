#!/bin/bash
# planning-with-files: Pre-tool-use hook for Cursor
# Reads the first 30 lines of task_plan.md to keep goals in context.
# Returns {"decision": "allow"} — this hook never blocks tools.

PLAN_FILE="task_plan.md"

if [ -f "$PLAN_FILE" ]; then
    # Log plan context to stderr (visible in Cursor's hook logs)
    head -30 "$PLAN_FILE" >&2
fi

echo '{"decision": "allow"}'
exit 0
