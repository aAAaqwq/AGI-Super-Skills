---
name: daily-briefing-run
description: Automatic daily briefing agent run
---
# Daily Briefing Agent - Manual Run

> Runs the daily briefing agent manually (outside of schedule).

## When to use

- "run briefing"
- "show morning report"
- "daily briefing"
- Need a report on Sunday/Saturday (outside of schedule)
- Testing after data changes

## What it does

The agent collects information from:
- PM tasks (deadline today, in-progress, hot, blocking)
- Email summaries (urgent, reply needed)
- CRM follow-ups (due today + overdue)

Generates:
- AI executive summary (Claude Haiku)
- Priority ranking
- Recommended task to start
- Formatted briefing markdown

Sends to Telegram Saved Messages.

## How to execute

### Option 1: Dry-run (console, no Telegram)

```bash
cd $AGENTS_PATH/daily-briefing
python3 daily-briefing_agent.py --dry-run --verbose
```

Outputs briefing to stdout, does not send to Telegram.

**Use for:**
- Viewing report without sending
- Testing after changes
- Debugging errors

### Option 2: Full run (with Telegram)

```bash
cd $AGENTS_PATH/daily-briefing
python3 daily-briefing_agent.py --now --verbose
```

Generates and sends to Telegram.

**Use for:**
- Running on weekends (agent skips Saturday/Sunday)
- Re-running briefing if something was missed
- Testing Telegram integration

### Option 3: Tests only

```bash
cd $AGENTS_PATH/daily-briefing
python3 test_daily-briefing.py
```

Runs unit tests without actual execution.

## Flags

- `--dry-run` - generates briefing, outputs to console, does NOT send to Telegram
- `--now` - bypasses schedule check (allows running on weekends)
- `--verbose` - detailed logging (shows each step)

## What to expect

**Successful run:**
```
Step 1: Collecting PM tasks...
Step 2: Collecting email data...
Step 3: Collecting CRM follow-ups...
Step 4: Generating AI summary...
Step 5: Ranking priorities...
Step 6: Formatting briefing...
Step 7: Sending to Telegram...
Telegram notification sent
Step 8: Logging run...
Done! Tasks: 26, Emails: 5, Follow-ups: 3
```

**Error (fallback):**
```
Step 7: Sending to Telegram...
Telegram notification failed: ...
Fallback: saved to /Users/.../data/2026-02-12.md
```

If Telegram failed -- briefing is saved to a file.

## Briefing structure

```markdown
# Good Morning! Daily Briefing for YYYY-MM-DD

## Executive Summary
- [AI bullet points: critical tasks, emails, follow-ups]

## Email (N new, M actionable)
[URGENT: X | REPLY NEEDED: Y | INFO: Z]

## Tasks Deadline TODAY (N)
- [task] (Project: X) - [description]

## In Progress (N)
- [task] - [notes]

## Hot Tasks (N)
| Score | Task | Description | Note |

## Follow-ups TODAY (N)
[OVERDUE: X if any]
- [Name] @ [Company] via [channel]

## Recommended to Start
**[Task]**
- Why: [reasoning]
- Action: [next step]
```

## Automatic schedule

Agent runs automatically via launchd:
- **Mon-Fri at 08:00**
- **Does NOT run** on Saturday/Sunday

Check status:
```bash
launchctl list | grep daily-briefing
```

Logs:
```bash
tail -f $AGENTS_PATH/logs/daily-briefing.log
tail -f $AGENTS_PATH/logs/daily-briefing.error.log
```

## Dependencies

**Other agents:**
- email-monitor (Process #1) - provides email summaries
- Works without email_agent, but Email section will be empty

**Tools:**
- `claude` CLI - for AI summary (optional, works without it)
- tg-tools - for Telegram sending

**Data:**
- `$PM_PATH/pm_tasks_master.csv`
- `$CRM_PATH/contacts/people.csv`
- `$CRM_PATH/contacts/companies.csv`
- `$CRM_PATH/activities.csv`
- `$GOOGLE_TOOLS_PATH/data/email_summaries/YYYY-MM-DD.md`

## Checking run history

```bash
cd $AGENTS_PATH/daily-briefing
python3 -c "
import json
with open('data/agent_log.json') as f:
    log = json.load(f)
    print(json.dumps(log[-5:], indent=2))
"
```

Shows the last 5 runs with metrics:
- timestamp
- task_count, email_count, followup_count
- recommended_task_id
- status (success/partial/error)
- errors[]

## Troubleshooting

**"No such file or directory: pm_tasks_master.csv"**
- File is missing or path is incorrect
- Agent will continue with empty tasks

**"Email summary not available for today"**
- Normal if email_agent has not run yet (before 09:00)
- Or email_agent is broken -- check its logs

**"Claude CLI error"**
- Check: `echo "test" | claude -p --model haiku`
- Agent will skip AI summary, show structured data

**"Telegram notification failed"**
- Check Telegram session: `ls /Users/.../telegram/sessions/*.session`
- Briefing is saved in `data/YYYY-MM-DD.md`

## Output

- **Telegram**: Saved Messages (if successful)
- **Fallback**: `$AGENTS_PATH/daily-briefing/data/YYYY-MM-DD.md`
- **Log**: `$AGENTS_PATH/daily-briefing/data/agent_log.json`

## Related skills

- `email-monitor` - run email agent
- `git-workflow` - if agent code was modified
- `pm/task-prioritize` - manual task prioritization

## Owner

Your Name (your@email.com)

Process ID: #14
Agent type: Scheduled reporting (read-only)
