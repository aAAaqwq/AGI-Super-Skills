# Closure Loop

Use this reference when a task risks stopping at reporting instead of resolution.

## Closure loop

```text
Signal detected
→ classify (real issue, stale state, false positive, unknown)
→ assign owner
→ define target outcome
→ act
→ verify with evidence
→ either close or escalate
```

## Four classifications

### 1. Real issue
A real failure or gap exists.
- Example: API call failing now
- Action: fix or route immediately

### 2. Stale state
The UI/session says `running`, but execution is already dead or irrelevant.
- Example: aborted exec but status still appears active
- Action: confirm with owner, mark as stale, decide whether cleanup is needed

### 3. False positive
Alert condition triggered, but no business impact exists.
- Example: transient timeout with healthy retry path and no user-visible failure
- Action: document why it is safe, then close

### 4. Unknown
Evidence is insufficient.
- Action: investigate before claiming anything

## Minimum closure checklist

Do not say “resolved” unless all applicable items are true:
- Owner is named
- Desired outcome is explicit
- Fresh evidence exists
- Residual risk is stated
- Next step is known if not fully closed

## Escalation examples

### Bad
- “I notified ops.”
- “I’m monitoring it.”
- “Looks OK now.”

### Good
- “Ops confirmed this was a stale running state from an aborted exec, no active workload remained, and the next run path is healthy.”
- “Quant reran the monitor and posted a fresh output; anomaly closed.”
- “Data failed again after retry, so this is no longer monitoring-only; it is now an owned incident.”

## Evidence ladder

Prefer stronger evidence in this order:
1. fresh runtime result
2. fresh test/log output
3. owner confirmation with specifics
4. historical pattern
5. guess

Never report level 5 as closure.
