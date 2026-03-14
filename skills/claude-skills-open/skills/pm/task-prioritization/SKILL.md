---
name: task-prioritization
description: Task prioritization and scoring
---
# Task Prioritization Skill

> Manually run the Task Prioritization agent to recalculate priority scores for all active tasks.

## When to use

- User asks to "update task priorities"
- User asks "what are my top priorities" (run this first, then show results)
- After bulk task changes (many deadlines changed, new blockers added, etc.)
- To preview priority changes before they auto-run

## How to execute

### Step 1: Run agent

```bash
cd $AGENTS_PATH/task-prioritization

# Preview changes (recommended first)
python3 task_prioritization_agent.py --dry-run --verbose

# Apply changes
python3 task_prioritization_agent.py
```

### Step 2: Review output

Agent will show:
- Total tasks processed
- Number of significant changes
- Top 5 tasks by priority
- Telegram notification if critical changes

### Step 3: Show user results

Read top tasks from CSV and present:

```bash
# Read updated priorities
head -20 $PM_PATH/pm_tasks_master.csv
```

Sort by priority_score and show top 5-10 tasks.

## Expected behavior

- Updates `priority_score` and `last_updated` columns in pm_tasks_master.csv
- Creates backup before write
- Sends Telegram alert if hot tasks in top 3
- Logs execution to pm_priority_agent_log.csv

## Error handling

If agent fails:
- Check /tmp/task-prioritization-agent-error.log
- Verify pm_tasks_master.csv exists and is readable
- Check if backup file exists: pm_tasks_master.csv.bak

## Related skills

- `show-today` — show today's tasks (uses priority_score)
- `daily-briefing` — morning report (uses priority_score)

## Notes

- Agent runs automatically 3x/day (08:00, 13:00, 18:00 Mon-Fri)
- Manual runs are safe (idempotent)
- Use --dry-run to preview without changes
- Algorithm details in agent README.md
