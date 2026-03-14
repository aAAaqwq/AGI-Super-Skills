# Planning Rules

Critical rules for effective file-based planning.

## Rule 1: Create Plan First

Never start a complex task without `task_plan.md`. Non-negotiable.

## Rule 2: The 2-Action Rule

After every 2 view/browser/search operations, IMMEDIATELY save key findings to `findings.md`.

This prevents visual/multimodal information from being lost.

## Rule 3: Read Before Decide

Before major decisions, read `task_plan.md`. This keeps goals in your attention window.

## Rule 4: Update After Act

After completing any phase:
- Mark phase status: `in_progress` → `complete`
- Log any errors encountered
- Note files created/modified

## Rule 5: Log ALL Errors

Every error goes in the plan file with this format:

```markdown
## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| FileNotFoundError | 1 | Created default config |
| API timeout | 2 | Added retry logic |
```

## Rule 6: Never Repeat Failures

If an action failed, the next action must be different. Track what you tried and mutate the approach.

## The 3-Strike Error Protocol

```
ATTEMPT 1: Diagnose & Fix
  → Read error carefully
  → Identify root cause
  → Apply targeted fix

ATTEMPT 2: Alternative Approach
  → Same error? Try different method
  → NEVER repeat exact same failing action

ATTEMPT 3: Broader Rethink
  → Question assumptions
  → Search for solutions
  → Consider updating the plan

AFTER 3 FAILURES: Escalate to User
```

## Read vs Write Decision Matrix

| Situation | Action | Reason |
|-----------|--------|--------|
| Just wrote a file | DON'T read | Content still in context |
| Viewed image/PDF | Write findings NOW | Multimodal → text before lost |
| Browser returned data | Write to file | Screenshots don't persist |
| Starting new phase | Read plan/findings | Re-orient if context stale |
| Error occurred | Read relevant file | Need current state to fix |
| Resuming after gap | Read all planning files | Recover state |
