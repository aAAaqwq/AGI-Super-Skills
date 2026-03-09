# Cron Anti-Freeze Pattern

## The Problem

OpenClaw subagents are **asynchronous**. When the main session spawns subagents (developer, 4 reviewers, fix-subagent), it doesn't actively wait — it relies on completion events to resume.

**The freeze scenario:**
1. Main session spawns 4 review subagents
2. All 4 finish successfully
3. Completion event is fired... but main session doesn't wake up
4. The full-cycle pipeline stalls indefinitely
5. User has to manually ping the agent to continue

This is a known issue with event-driven async orchestration: completion events may not always reliably resume the parent session.

**Without anti-freeze:** the user must ping the agent manually → defeats the purpose of full automation.

---

## The Solution: Dual Cron as Insurance

**Rule:** After spawning any group of subagents → immediately schedule two cron jobs.

```
spawn subagents
     │
     ├─► cron_1 at T + expected_runtime + 3min  (primary)
     └─► cron_2 at T + expected_runtime + 6min  (backup)
```

Both crons fire at scheduled time and check subagent status:
- If **all done** → aggregate results → proceed with pipeline
- If **still active** → reschedule to `now + 5min`, delete current cron

---

## Timing Formula

```
T = time subagents were spawned
expected_runtime = subagent runTimeoutSeconds
buffer = 3 min

cron_1 = T + expected_runtime + buffer
cron_2 = T + expected_runtime + buffer + 3min
```

### Timing Table

| Subagent group | Timeout | Cron 1 | Cron 2 |
|----------------|---------|--------|--------|
| 4 review roles | 1200s (20 min) | T + 23 min | T + 26 min |
| Fix subagent | 600s (10 min) | T + 13 min | T + 16 min |
| Developer subagent | 900s (15 min) | T + 18 min | T + 21 min |

---

## Cron Job Template

```
Full-cycle self-ping: round {N} review <project>/<branch>.
Check subagents list (labels contain '<role>').

If ALL done → aggregate sessions_history, count blocking.
  blocking > 0 → spawn fix-subagent (do NOT message user).
  blocking = 0 → create PR → send user final output.

If ANY active → delete this cron, schedule new one at now+5min with same text.

Do NOT message user until final result (PR or fatal error).
```

### Self-Rescheduling Logic

```python
# Pseudocode inside cron-triggered session event:

active_subagents = subagents(action="list")["active"]
my_review_labels = ["developer-review", "architect-review", "tester-review", "security-review"]

still_running = any(
    any(label in s.get("label", "") for label in my_review_labels)
    for s in active_subagents
)

if still_running:
    # Remove current cron (it's deleteAfterRun anyway)
    # Schedule new cron for now + 5 minutes
    cron_create(
        text="Full-cycle self-ping: round {N} review <project>/<branch>. [same instructions]",
        runAt="now+5min",
        deleteAfterRun=True
    )
else:
    # All subagents done → aggregate and proceed
    reviews = collect_results_from_sessions_history()
    blocking_count = aggregate_blocking(reviews)
    
    if blocking_count > 0:
        spawn_fix_subagent(blocking_list)
        schedule_fix_crons()
    else:
        create_pr()
        send_final_output_to_user()
```

---

## Key Properties

### `deleteAfterRun: true`

Each cron is **one-shot**:
- Fires once at scheduled time
- Auto-deletes after execution
- No manual cleanup needed

### Two Crons = Redundancy

If cron_1 fires but doesn't wake the session (rare but possible):
- cron_2 fires 3 minutes later
- Same logic, fresh attempt

If both fire but session is already running (cron woke it):
- First cron: does its work
- Second cron: checks subagents → all done or no relevant ones → no-op

### No Double-Execution Risk

If the main session already continued on its own (completion event worked):
- Cron fires → checks subagents list → all done already
- `blocking_count` was already processed, fix was spawned or PR was created
- Cron sees the work is done → no-op

---

## When NOT to Use Cron

**Skip cron scheduling when** subagents already returned results in the **active session**:

```
# Subagent returns result synchronously in same session turn
result = await sessions_spawn(task=..., waitForCompletion=True)
# → result available immediately
# → NO cron needed, aggregate immediately
```

Only schedule crons when you're using **fire-and-forget** spawning without waiting for completion in the same turn.

---

## Example: Review Round Crons

```python
# After spawning all 4 review subagents:
now = current_time()

cron_create(
    label="full-cycle-review-ping-1",
    text="""
    Full-cycle self-ping: round 1 review my-project/feat/jwt-auth.
    Check subagents list (labels contain 'review').
    
    If ALL done → aggregate sessions_history for keys: [key_dev, key_arch, key_test, key_sec]
    Count blocking findings. 
    blocking > 0 → spawn fix-subagent with blocking list.
    blocking = 0 → create PR → send user final output.
    
    If ANY active → delete this cron, schedule new at now+5min with same text.
    Do NOT message user until PR or fatal error.
    """,
    runAt=now + timedelta(minutes=23),
    deleteAfterRun=True
)

cron_create(
    label="full-cycle-review-ping-2",
    text="[same text as ping-1]",
    runAt=now + timedelta(minutes=26),
    deleteAfterRun=True
)
```

---

## Example: Fix Round Crons

```python
# After spawning fix subagent:
now = current_time()

cron_create(
    label="full-cycle-fix-ping-1",
    text="""
    Full-cycle self-ping: fix round 1 for my-project/feat/jwt-auth.
    Check subagents list (labels contain 'fix').
    
    If done → re-run full review (spawn 4 roles again) → schedule review crons.
    If active → reschedule this cron to now+5min.
    
    Do NOT message user.
    """,
    runAt=now + timedelta(minutes=13),
    deleteAfterRun=True
)
```

---

## Why This Works

The anti-freeze pattern is essentially **polling with exponential backoff collapsed to fixed intervals**:

1. First check at T+N (expected completion time + buffer)
2. If not done: reschedule at T+N+5, T+N+10, etc.
3. Eventually all subagents finish → pipeline continues

The dual-cron redundancy ensures no single missed event causes a permanent stall.

**Result:** Full cycle automation that's self-healing and doesn't require user intervention.
