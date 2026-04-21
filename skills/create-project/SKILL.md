---
name: create-project
description: Create new project with breakdown
---
# PM Create Project

> Creating a new project with task breakdown

## When to use

- "new project: X"
- "create a project for Y"
- When there is a new initiative/goal

## Paths

| What | Path |
|------|------|
| Projects | `$PM_PATH/pm_projects_master.csv` |
| Tasks | `$PM_PATH/pm_tasks_master.csv` |

## Schema: Projects

```csv
project_id,project_name,description,goal,status,priority,priority_score,owner,created_date,last_updated,deadline,estimated_hours,actual_hours,actual_tokens,crm_link_type,crm_link_id,tags,notes
```

## How to create a project

```python
import pandas as pd
from datetime import date
import uuid

projects = pd.read_csv('$PM_PATH/pm_projects_master.csv')

new_project = {
    'project_id': f'proj-{uuid.uuid4().hex[:4]}',
    'project_name': 'Project name',
    'description': 'Detailed description',
    'goal': 'What does success look like?',
    'status': 'planning',  # idea/planning/in_progress/on_hold/completed/cancelled
    'priority': 'hot',  # hot/medium/low
    'priority_score': 0.9,
    'owner': 'Ivan',
    'created_date': str(date.today()),
    'last_updated': str(date.today()),
    'deadline': '2025-02-10',  # if applicable
    'estimated_hours': 10,
    'actual_hours': 0,
    'actual_tokens': 0,
    'crm_link_type': '',  # company/person/activity
    'crm_link_id': '',
    'tags': 'tag1;tag2',
    'notes': ''
}

projects = pd.concat([projects, pd.DataFrame([new_project])], ignore_index=True)
projects.to_csv('$PM_PATH/pm_projects_master.csv', index=False)
```

## Add tasks immediately

```python
tasks = pd.read_csv('$PM_PATH/pm_tasks_master.csv')

project_id = 'proj-xxxx'  # ID of the created project

task_list = [
    ('Research', 'Gather information', 2),
    ('Planning', 'Define approach', 1),
    ('Implementation', 'Do the work', 5),
    ('Testing', 'Verify results', 1),
]

for i, (name, desc, hours) in enumerate(task_list):
    new_task = {
        'task_id': f'task-{uuid.uuid4().hex[:4]}',
        'project_id': project_id,
        'parent_task_id': '',
        'task_name': name,
        'description': desc,
        'status': 'todo',
        'priority': 'medium',
        'priority_score': 0.5,
        'assignee': 'Ivan',
        'created_date': str(date.today()),
        'last_updated': str(date.today()),
        'deadline': '',
        'estimated_hours': hours,
        'actual_hours': 0,
        'actual_tokens': 0,
        'blocked_by': '',
        'blocking': '',
        'order_index': i + 1
    }
    tasks = pd.concat([tasks, pd.DataFrame([new_task])], ignore_index=True)

tasks.to_csv('$PM_PATH/pm_tasks_master.csv', index=False)
```

## Project statuses

```
idea → planning → in_progress → on_hold → completed/cancelled
```

## CRM link

If the project is linked to CRM:

```python
'crm_link_type': 'person',  # or 'company', 'activity'
'crm_link_id': 'https://linkedin.com/in/example',  # or website, activity_id
```

## Related skills

- `query-leads` -- if linked to CRM
