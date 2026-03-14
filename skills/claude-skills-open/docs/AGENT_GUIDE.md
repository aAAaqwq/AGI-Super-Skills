# Agent Guide

## What is an Agent?

An agent is a skill that runs autonomously -- executing multi-step workflows on a schedule or trigger. Unlike regular skills (invoked by user), agents run in the background via `launchd` (macOS) or `cron`.

## Agent vs Skill

| | Skill | Agent |
|---|-------|-------|
| Trigger | User says something | Schedule / cron / manual |
| Execution | Interactive | Autonomous |
| Duration | Seconds-minutes | Minutes-hours |
| Example | "Add a lead" | Daily briefing at 8am |

## Agent Pattern

Every agent follows this structure:

```
skills/agents/{name}-run/SKILL.md    <- Manual run instructions
$AGENTS_PATH/{name}/                 <- Agent implementation
├── {name}_agent.py                  <- Main script
├── config.yaml                      <- Agent config
├── data/                            <- Agent state/output
└── logs/                            <- Execution logs
```

The `SKILL.md` in `skills/agents/` describes how to run the agent manually (for testing). The actual agent script lives in `$AGENTS_PATH/`.

## Creating an Agent

### 1. Write the spec

Before coding, write an agent spec:

```markdown
# Agent: {name}

## Purpose
What does this agent do?

## Trigger
When/how often does it run?

## Steps
1. Step one
2. Step two
3. ...

## Input
What data does it read?

## Output
What does it produce?

## Error handling
What happens when something fails?
```

### 2. Build the agent script

```python
#!/usr/bin/env python3
"""Agent: {name}"""

import json
import logging
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("$AGENTS_PATH/{name}/logs")
DATA_DIR = Path("$AGENTS_PATH/{name}/data")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"{datetime.now():%Y-%m-%d}.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

def main():
    log.info("Agent started")

    # Step 1: Read input
    # ...

    # Step 2: Process
    # ...

    # Step 3: Output
    # ...

    log.info("Agent completed")

if __name__ == "__main__":
    main()
```

### 3. Create the run skill

Create `skills/agents/{name}-run/SKILL.md`:

```markdown
---
name: {name}-run
description: Run {name} agent manually
---
# {Name} Agent - Manual Run

## When to use
- "run {name} agent"
- Testing/debugging the agent

## How to run
\```bash
cd $AGENTS_PATH/{name}
python3 {name}_agent.py
\```

## Check logs
\```bash
cat $AGENTS_PATH/{name}/logs/$(date +%Y-%m-%d).log
\```
```

### 4. Schedule with launchd (macOS)

Create `~/Library/LaunchAgents/com.yourcompany.{name}-agent.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.yourcompany.{name}-agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/agents/{name}/{name}_agent.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/path/to/agents/{name}/logs/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/agents/{name}/logs/stderr.log</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.yourcompany.{name}-agent.plist
```

## Example Agents

| Agent | Schedule | What it does |
|-------|----------|-------------|
| daily-briefing-run | Every morning | Compile tasks + email + CRM into a report |
| email-outreach-run | On demand | Send batch emails with rate limiting |
| telegram-inbound-run | Every 5 min | Read new Telegram messages, classify, route |
| watchers-run | Every hour | Check CRM triggers (stale leads, overdue invoices) |
| channel-truth-run | Daily | Sync channel contacts with CRM |
| weekly-review-run | Friday evening | Generate weekly progress report |

## Best Practices

1. **Idempotent** -- running twice should not produce duplicates
2. **Log everything** -- timestamps, counts, errors
3. **Fail gracefully** -- catch exceptions, log them, continue
4. **State management** -- track what was processed (last run date, processed IDs)
5. **Rate limiting** -- respect API limits (Telegram, Gmail, etc)
6. **Dry run mode** -- always support `--dry-run` for testing
