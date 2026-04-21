---
name: weekly-review
description: Weekly project review report
---
# PM Weekly Review

> Weekly work review -- hours, tokens, progress

## When to use

- "weekly report"
- "what was done this week"
- At the end of the week
- Before planning the next week

## Paths

| What | Path |
|------|------|
| Tasks | `$PM_PATH/pm_tasks_master.csv` |
| Execution Log | `$PM_PATH/pm_execution_log.csv` |
| Learnings | `$PM_PATH/pm_learnings.csv` |
| Script | `$PROJECT_ROOT/projects/scripts/weekly_report.py` |

## Quick start

```bash
cd $PROJECT_ROOT
python3 projects/scripts/weekly_report.py
```

## Manual analysis

```python
import pandas as pd
from datetime import date, timedelta

# Last 7 days
week_ago = str(date.today() - timedelta(days=7))
today = str(date.today())

tasks = pd.read_csv('$PM_PATH/pm_tasks_master.csv')
log = pd.read_csv('$PM_PATH/pm_execution_log.csv')
learnings = pd.read_csv('$PM_PATH/pm_learnings.csv')

# Filter by date
log_week = log[(log['date'] >= week_ago) & (log['date'] <= today)]
```

## Metrics

```python
# Total hours
total_hours = log_week['duration_minutes'].sum() / 60
print(f"Total hours: {total_hours:.1f}")

# Total tokens
total_tokens = log_week['tokens_total'].sum()
print(f"Total tokens: {total_tokens:,}")

# Completed tasks
completed = tasks[(tasks['status'] == 'done') & (tasks['last_updated'] >= week_ago)]
print(f"Tasks completed: {len(completed)}")

# By activity type
by_type = log_week.groupby('activity_type')['duration_minutes'].sum() / 60
print("\nBy type:")
print(by_type)

# By project
by_project = log_week.groupby('project_id')['duration_minutes'].sum() / 60
print("\nBy project:")
print(by_project)
```

## Report format

```
=== WEEKLY REPORT ===
Period: 2025-01-27 — 2025-02-03

METRICS
* Hours: 12.5
* Tokens: 45,230
* Tasks completed: 8

BY PROJECT
* proj-001 (Client D): 6.5 hrs
* proj-002 (CRM): 4.0 hrs
* proj-003 (Infra): 2.0 hrs

BY TYPE
* coding: 5.5 hrs
* research: 3.0 hrs
* planning: 2.0 hrs
* discussion: 2.0 hrs

COMPLETED TASKS
* [proj-001] Send outreach
* [proj-001] Check responses
* [proj-002] Update CRM schema
...

LEARNINGS
* Telegram has a 60 sec limit between messages
* WhatsApp does not sync history
...

BLOCKED
* [proj-003] task-004: Waiting for Tailscale account

NEXT WEEK
* Finish proj-001
* Start proj-004
```

## Saving the report

```python
report_path = f'$PROJECT_ROOT/reports/weekly_{today}.md'
with open(report_path, 'w') as f:
    f.write(report_content)
```

## Related skills

- `show-today` -- what's for today
