---
name: telegram-inbound-run
description: Automatic inbound Telegram message processing
---
# Telegram Inbound Agent - Manual Run

> Skill for manually triggering Telegram Inbound Reply Monitor Agent

## When to use

- "check Telegram for replies"
- "run Telegram inbound agent"
- "see if anyone replied on Telegram"
- "check Telegram replies"

## What it does

Agent:
1. Extracts messages from Telegram (last 24 hours)
2. Filters contacts that we messaged (outbound)
3. Classifies replies via Claude Haiku (POSITIVE/NEGATIVE/QUESTION/etc)
4. Logs activity in CRM
5. Updates lead statuses
6. Sends notification to Saved Messages
7. Creates git commit

## How to run

### Dry run (no CRM changes)

```bash
cd $AGENTS_PATH/telegram-inbound
python3 telegram_inbound_agent.py --dry-run --since 24h
```

### Full run

```bash
cd $AGENTS_PATH/telegram-inbound
python3 telegram_inbound_agent.py --since 24h
```

### Notification test

```bash
cd $AGENTS_PATH/telegram-inbound
python3 telegram_inbound_agent.py --notify-test
```

### Without AI (rule-based classification)

```bash
cd $AGENTS_PATH/telegram-inbound
python3 telegram_inbound_agent.py --no-ai --since 24h
```

### Larger time window

```bash
# Last 48 hours
python3 telegram_inbound_agent.py --since 48h

# Last 7 days
python3 telegram_inbound_agent.py --since 7d

# Last 14 days
python3 telegram_inbound_agent.py --since 14d
```

## Output

### Stdout (summary)
```
📬 Telegram Inbound: 2026-02-12 09:00

5 new replies (3 positive, 1 questions)

✅ POSITIVE (3):
  • John Doe: Interested in labeling service
  ...
```

### Files
- **Summary**: `$AGENTS_PATH/logs/telegram-inbound-{date}.md`
- **Run log**: `$AGENTS_PATH/logs/telegram_agent_log.json`
- **Errors**: `$AGENTS_PATH/logs/errors/telegram-inbound-{date}.log`

### CRM updates
- **Activities**: added to `sales/crm/activities.csv`
- **Leads**: updated statuses in `sales/crm/relationships/leads.csv`
- **Git commit**: auto-commit with change description

## Flags

| Flag | Description |
|------|-------------|
| `--dry-run` | Classification only, no CRM updates or notifications |
| `--no-ai` | Rule-based classification (without Claude) |
| `--since <duration>` | Time window: 24h, 48h, 7d, 14d |
| `--notify-test` | Test Telegram notification |

## Scheduled Runs

Agent runs automatically 3 times a day:
- **09:00** - morning check
- **13:00** - midday check
- **17:00** - evening check

Via launchd: `com.yourcompany.telegram-inbound`

## Troubleshooting

### "No actionable contacts found"

```bash
# Check activities.csv for outbound Telegram
grep telegram $CRM_PATH/activities.csv | grep outbound

# Check people.csv for telegram usernames
grep telegram_username $CRM_PATH/contacts/people.csv
```

### "Telegram authorization failed"

```bash
# Re-auth
cd $TG_TOOLS_PATH
python3 tools/tg_auth.py
```

### View recent summary

```bash
cat $AGENTS_PATH/logs/telegram-inbound-$(date +%Y-%m-%d).md
```

## Related skills

- `telegram-send` - sending outbound messages
- `change-review` - review CRM changes before commit
- `update-lead` - manual CRM update
- `log-activity` - manual activity logging
