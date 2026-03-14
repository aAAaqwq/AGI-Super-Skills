---
name: pm-done
description: Mark task done + schedule follow-up
---
# PM Done

> Mark a task as done and optionally create a follow-up task

## When to use

- After completing any task from pm_tasks_master.csv during a conversation
- "mark task done"
- "task X is done"
- When user confirms a task is completed (e.g., "invoice sent", "email sent", "done")
- **AUTO-TRIGGER:** When Claude helps complete something that maps to a task in the CSV (e.g., sends an invoice, writes an email, creates a deliverable), Claude MUST mark it done immediately

## Paths

| What | Path |
|------|------|
| Tasks | `$PM_PATH/pm_tasks_master.csv` |
| Projects | `$PM_PATH/pm_projects_master.csv` |

## How to execute

### Step 1: Find the task

```python
import pandas as pd
from datetime import date, timedelta

tasks = pd.read_csv('$PM_PATH/pm_tasks_master.csv', on_bad_lines='skip')

# Find by keyword, task_id, or project_id
# Example: find Client D invoice task
match = tasks[tasks['task_name'].str.contains('invoice', case=False, na=False) &
              (tasks['status'] != 'done')]
```

### Step 2: Mark as done

```python
today = str(date.today())

tasks.loc[tasks['task_id'] == 'task-XXX', 'status'] = 'done'
tasks.loc[tasks['task_id'] == 'task-XXX', 'last_updated'] = today
tasks.loc[tasks['task_id'] == 'task-XXX', 'notes'] = tasks.loc[
    tasks['task_id'] == 'task-XXX', 'notes'
].fillna('').astype(str) + f' DONE {today}. [completion details]'

tasks.to_csv('$PM_PATH/pm_tasks_master.csv', index=False)
```

### Step 3: Ask about follow-up

After marking done, ALWAYS ask user:

> "Task marked done. Should I create a follow-up? For example: check payment in 5 days, verify delivery, etc."

If user says yes (or if the task type naturally needs a follow-up):

```python
import uuid

followup_task = {
    'task_id': f'task-{uuid.uuid4().hex[:4]}',
    'project_id': original_task['project_id'],
    'parent_task_id': '',
    'task_name': 'Follow-up: [what to check]',
    'description': '[Details of what to verify]',
    'status': 'todo',
    'priority': 'medium',
    'priority_score': 0.5,
    'assignee': 'Ivan',
    'created_date': today,
    'last_updated': today,
    'deadline': str(date.today() + timedelta(days=N)),  # typically 3-7 days
    'estimated_hours': 0.25,
    'actual_hours': '',
    'actual_tokens': '',
    'blocked_by': '',
    'blocking': '',
    'crm_activity_id': '',
    'crm_person_linkedin_url': '',
    'tags': original_task.get('tags', ''),
    'notes': f'Follow-up from {original_task["task_id"]}',
    'order_index': ''
}

tasks = pd.concat([tasks, pd.DataFrame([followup_task])], ignore_index=True)
tasks.to_csv('$PM_PATH/pm_tasks_master.csv', index=False)
```

## Auto-follow-up rules

These task types ALWAYS need a follow-up (suggest automatically):

| Task type | Follow-up | Days |
|-----------|-----------|------|
| Invoice sent | Check if paid | 5-7 |
| Email sent (important) | Check for reply | 3-5 |
| Proposal/quote sent | Check for response | 3-5 |
| Deliverable submitted | Check for feedback | 3-5 |
| Meeting scheduled | Prepare for meeting | 1 day before |
| Escalation sent | Check for resolution | 2-3 |

## Task completion rule (for all PM skills)

**IMPORTANT:** When Claude helps execute a task during a conversation (sends email, creates invoice, writes a message, etc.), Claude MUST:

1. **Identify** the matching task in pm_tasks_master.csv
2. **Mark it done** immediately (status=done, last_updated=today, notes updated)
3. **Suggest follow-up** if applicable (see auto-follow-up rules above)
4. **Confirm** to user: "Marked [task_name] as done. Created follow-up for [date]."

This prevents stale tasks from showing up in daily briefings.

## Scope: dev/project tasks only (since 2026-03-02)

pm_tasks_master.csv is for dev/project tasks only. Sales follow-ups (invoice checks, payment follow-ups, deal closing) are tracked in `leads.csv` via `next_action` and `next_action_date`. Do NOT create pm tasks for sales activities.

## Related skills

- `show-today` -- daily task view (references this skill)
- `daily-briefing` -- morning summary
- `create-project` -- create project with tasks
- `log-activity` -- CRM activity logging
- `update-lead` -- update sales follow-ups in leads.csv
