---
name: email-monitor
description: AI inbox classification + Telegram notification
---
# Email Monitor

> Automatic pipeline: Gmail -> AI classification -> CRM activities -> PM tasks -> draft replies -> Telegram

## When to use

- "what's new in email?" / "email status"
- "show email summary for today"
- "check email monitor"
- "show draft replies"
- Runs automatically every hour via launchd

## Pipeline

```
email_monitor.py          → Gmail API, extracts full body
    ↓ JSON (stdout)
email_agent.py            → AI classification (claude CLI haiku)
    ↓ actionable emails JSON (stdin)
email_action_agent.py     → CRM + PM + drafts + git commit + Telegram
```

## Paths

| What | Path |
|------|------|
| Monitor tool | `$GOOGLE_TOOLS_PATH/email_monitor.py` |
| Classify agent | `$GOOGLE_TOOLS_PATH/email_agent.py` |
| Action agent | `$GOOGLE_TOOLS_PATH/email_action_agent.py` |
| State | `$GOOGLE_TOOLS_PATH/data/email_monitor_state.json` |
| Summaries | `$GOOGLE_TOOLS_PATH/data/email_summaries/` |
| Drafts | `$GOOGLE_TOOLS_PATH/data/email_drafts/` |
| Agent log | `$GOOGLE_TOOLS_PATH/data/email_agent_log.json` |
| LaunchAgent | `~/Library/LaunchAgents/com.yourcompany.email-monitor.plist` |

## How to run

### Full pipeline

```bash
# Everything automatic: check → classify → CRM → tasks → drafts → notify
$GOOGLE_TOOLS_PATH/.venv/bin/python3 $GOOGLE_TOOLS_PATH/email_agent.py

# Dry-run (classification without writing records or notifications)
$GOOGLE_TOOLS_PATH/.venv/bin/python3 $GOOGLE_TOOLS_PATH/email_agent.py --dry-run

# Without AI (rule-based classification)
$GOOGLE_TOOLS_PATH/.venv/bin/python3 $GOOGLE_TOOLS_PATH/email_agent.py --no-ai
```

### Monitor only (without classification)

```bash
# JSON with full body of each email
$GOOGLE_TOOLS_PATH/.venv/bin/python3 $GOOGLE_TOOLS_PATH/email_monitor.py

# Human-readable
$GOOGLE_TOOLS_PATH/.venv/bin/python3 $GOOGLE_TOOLS_PATH/email_monitor.py --pretty

# Reset state (reprocess last 20)
rm $GOOGLE_TOOLS_PATH/data/email_monitor_state.json

# Emails from the last N hours
$GOOGLE_TOOLS_PATH/.venv/bin/python3 $GOOGLE_TOOLS_PATH/email_monitor.py --since 2h
```

### Action agent only (with prepared JSON)

```bash
# From file
$GOOGLE_TOOLS_PATH/.venv/bin/python3 $GOOGLE_TOOLS_PATH/email_action_agent.py --file input.json

# Dry-run (shows what it will do, without writing records)
echo '<json>' | $GOOGLE_TOOLS_PATH/.venv/bin/python3 $GOOGLE_TOOLS_PATH/email_action_agent.py --dry-run

# Without drafts
echo '<json>' | $GOOGLE_TOOLS_PATH/.venv/bin/python3 $GOOGLE_TOOLS_PATH/email_action_agent.py --no-draft
```

### View results

```bash
# Summary for today
cat $GOOGLE_TOOLS_PATH/data/email_summaries/$(date +%Y-%m-%d).md

# Draft replies
ls $GOOGLE_TOOLS_PATH/data/email_drafts/
cat $GOOGLE_TOOLS_PATH/data/email_drafts/2026-02-09_task-055.txt

# launchd status
launchctl list | grep email-monitor
```

## Classification

| Category | Action Agent action |
|----------|---------------------|
| URGENT | Activity + draft |
| REPLY_NEEDED | Activity + draft |
| INFO | Activity only |
| SPAM | Skipped |

> **Note (2026-03-02):** Task creation is DISABLED. Sales follow-ups are tracked in `leads.csv` via `next_action`. pm_tasks is for dev/project tasks only. To re-enable task creation, uncomment the block in `email_action_agent.py` around line 420.

## Action Agent: what it does

1. **Match contact** -- looks up the sender in `people.csv` (email), fallback by domain in `companies.csv`
2. **Log activity** -- adds a row to `activities.csv` (type: email, direction: inbound)
3. ~~**Create task**~~ -- DISABLED. Was: adds a row to `pm_tasks_master.csv`
4. **Draft reply** -- generates a draft via `claude -p --model haiku`, saves to `data/email_drafts/`
5. **Git commit** -- auto-commits in $PROJECT_ROOT (activities only)
6. **Telegram notify** -- summary with drafts to Saved Messages

Unknown contacts are tagged with `unknown-contact` -- need to be added to CRM.

## CRM files (read/write)

- `$CRM_PATH/contacts/people.csv`
- `$CRM_PATH/contacts/companies.csv`
- `$CRM_PATH/activities.csv`

## Related skills

- `email-send-direct` -- single email
- `email-send-bulk` -- mass email sending
- `daily-briefing` -- morning overview (reads email summaries)
- `log-activity` -- manual activity logging
- `telegram-session` -- if Telegram notifications are not working
