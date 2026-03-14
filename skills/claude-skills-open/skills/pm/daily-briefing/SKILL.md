---
name: daily-briefing
description: Morning briefing: tasks + email + follow-ups
---
# Daily Briefing

> Morning summary: tasks, emails, follow-ups, priorities

## When to use

- "good morning" / "morning"
- "what's today?"
- "daily briefing"
- "start of day"
- At the beginning of work day

## Paths

| What | Path |
|------|------|
| Tasks | `$PM_PATH/pm_tasks_master.csv` |
| Leads | `$CRM_PATH/relationships/leads.csv` |
| People (CRM) | `$CRM_PATH/contacts/people.csv` |
| Email script | `$GOOGLE_TOOLS_PATH/read_emails.py` |

## How to execute

### Step 1: Read tasks

```python
import pandas as pd
from datetime import date

today = str(date.today())

tasks = pd.read_csv('$PM_PATH/pm_tasks_master.csv')

# Deadline today
deadline_today = tasks[tasks['deadline'] == today]

# In progress
in_progress = tasks[tasks['status'] == 'in_progress']

# Hot tasks (not done)
hot_tasks = tasks[(tasks['priority'] == 'hot') & (tasks['status'] != 'done')]

# Top by priority score
tasks_sorted = tasks[tasks['status'].isin(['todo', 'in_progress'])].sort_values(
    'priority_score', ascending=False
)
```

### Step 2: Check leads follow-ups (source of truth for sales)

```python
leads = pd.read_csv('$CRM_PATH/relationships/leads.csv')
leads_today = leads[leads['next_action_date'] == today]
```

### Step 3: Check CRM follow-ups

```python
try:
    people = pd.read_csv('$CRM_PATH/contacts/people.csv')
    followups = people[people['next_followup_date'] == today]
except:
    followups = pd.DataFrame()
```

### Step 4: Check inbox

```bash
cd $GOOGLE_TOOLS_PATH
python3 read_emails.py 10
```

### Step 5: Output format

```markdown
## Good Morning! Daily Briefing for [DATE]

### Inbox ([N] unread)
| From | Subject | Preview |
|------|---------|---------|
| ... | ... | ... |

### Deadline TODAY
| Task | Project | Description |
|------|---------|-------------|
| ... | ... | ... |

### In Progress
| Task | Project | Description |
|------|---------|-------------|
| ... | ... | ... |

### Hot Tasks (Top 5)
| Score | Task | Description | Note |
|-------|------|-------------|------|
| ... | ... | ... | ... |

### Leads Follow-ups TODAY (source of truth)
| Lead | Next Action | Stage |
|------|-------------|-------|
| ... | ... | ... |

### CRM Follow-ups TODAY
| Person | Company | Note |
|--------|---------|------|
| ... | ... | ... |

### Recommended to Start
**[Task name]**
- Project: [project_id]
- Description: [description]
- Why: highest priority_score / blocking others / deadline approaching
```

## Priority logic

1. **Deadline today** - must do
2. **Blocking others** - unblocks team
3. **Highest priority_score** - calculated importance
4. **In progress** - finish what started

## Quick command

For Claude to run daily briefing:
1. Read this skill
2. Execute all steps
3. Format output
4. Ask: "Ready to start with [top task]?"

## Task completion rule

**IMPORTANT:** If during briefing user says a task is already done, or you discover from email/context that a task was completed:

1. **Mark it done immediately** (status=done, last_updated=today, update notes)
2. **Suggest follow-up** if applicable (invoice -> check payment, email -> check reply)
3. **Re-show** updated briefing without the completed task

See `pm-done` skill for full logic and auto-follow-up rules.

## Related skills

- `pm-done` - Mark task done + follow-up
- `show-today` - Tasks only (no email/crm)
- `email-read` - Email only
- `query-leads` - CRM details
- `weekly-review` - Weekly review
