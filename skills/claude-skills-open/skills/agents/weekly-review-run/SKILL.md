---
name: weekly-review-run
description: Automatic weekly review report
---
# Weekly Review - Run Agent

> Generate weekly summary report manually or test the automated agent.

## When to use

- "generate weekly review"
- "run weekly report"
- "show report for the week"
- "test weekly review agent"

## What it does

Generates a comprehensive weekly summary from:
- Metrics: hours, tokens, tasks completed
- Breakdown by projects and activity types
- CRM activities
- Learnings for the week
- Blocked tasks
- Upcoming deadlines
- AI insights (achievements, blockers, recommendations)

## How to execute

### Option 1: Generate report (recommended)

```bash
cd $AGENTS_PATH/weekly-review
python3 weekly_review_agent.py --dry-run
```

**Result:**
- Generates report in `$PROJECT_ROOT/reports/weekly/`
- Shows preview notification
- Does NOT send to Telegram

### Option 2: Full run

```bash
cd $AGENTS_PATH/weekly-review
python3 weekly_review_agent.py
```

**Result:**
- Generates report
- Sends notification to Telegram

### Option 3: Without AI (fast)

```bash
cd $AGENTS_PATH/weekly-review
python3 weekly_review_agent.py --dry-run --no-ai
```

**Result:**
- Data only, no AI insights
- Faster execution

### Option 4: For a specific date

```bash
cd $AGENTS_PATH/weekly-review
python3 weekly_review_agent.py --date 2026-02-14 --dry-run
```

**Result:**
- Report for the week ending 2026-02-14

### Option 5: Telegram test

```bash
cd $AGENTS_PATH/weekly-review
python3 weekly_review_agent.py --notify-test
```

## Output

### Report file

Location: `$PROJECT_ROOT/reports/weekly/weekly_YYYY-MM-DD.md`

Sections:
1. Executive Summary (hours, tokens, tasks)
2. Hours by Project
3. Hours by Activity Type
4. Completed Tasks
5. CRM Activities
6. Learnings
7. Blocked Tasks
8. Upcoming Deadlines
9. AI Insights (achievements, blockers, recommendations)
10. Next Week Focus

### Telegram Notification

Target: Info channel (currently "me" - Saved Messages)

Format:
```
📊 Weekly Review Ready

📅 Period: 2026-02-03 to 2026-02-09
⏱ Hours: 12.5h
✅ Tasks: 8 completed
🎯 Tokens: 45,000

🏆 Top project: lung-xray-analyzer (6.2h)
⚠️ Blocked tasks: 2
📆 Upcoming deadlines: 3

📄 Full report: weekly_2026-02-09.md
```

## Troubleshooting

### Error: files missing

Check if data exists:
```bash
ls -lh $PM_PATH/pm_*.csv
ls -lh $CRM_PATH/activities.csv
```

### Claude CLI error

Test:
```bash
echo "test" | claude -p --model haiku --output-format text
```

If not working -- agent will use fallback (without AI insights).

### Telegram not working

Test:
```bash
python3 weekly_review_agent.py --notify-test
```

Check tg-tools auth:
```bash
ls $SALES_PATH/telegram/sessions/
```

### Empty report

If there is no data for the week -- agent will generate a minimal report with the message "No activity this week".

## Automation

Agent runs automatically **every Friday at 18:00** via launchd.

Status:
```bash
launchctl list | grep weekly-review
```

Logs:
```bash
tail -f $AGENTS_PATH/logs/weekly_review_stderr.log
```

Recent runs:
```bash
cat $AGENTS_PATH/logs/weekly_review.log | jq '.'
```

## Testing

Run test suite:
```bash
cd $AGENTS_PATH/weekly-review
python3 test_weekly_review.py
```

## Related skills

- `daily-briefing` — daily tactical brief (daily vs weekly strategic)
- `task-prioritization` — uses weekly insights for prioritization
- `log-activity` — logs CRM activities that appear in weekly review

## Notes

- **Read-only**: Agent only reads data, does not modify anything
- **Idempotent**: Safe to run multiple times
- **No approvals**: Fully automatic, informational only
- **Graceful degradation**: If a section fails -- continues with available data
