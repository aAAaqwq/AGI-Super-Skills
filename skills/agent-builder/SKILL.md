---
name: agent-builder
description: Build agent from spec: code, skill, config, launchd
---
# Agent Builder

> Takes a spec from Process Analyst and implements the agent: code, skill, config, launchd.

## When to use

- After Process Analyst has created a spec
- "build an agent for process X"
- "implement spec Y"

## Input

Spec file from `$AGENTS_PATH/specs/[name].spec.md`

## How to execute

### Step 1: Read the spec

- Read the spec file completely
- Read the reference implementation: Email Pipeline (`$GOOGLE_TOOLS_PATH/email_agent.py`)
- Understand the pipeline: trigger → steps → output

### Step 2: Define architecture

Based on the spec, define:

```
agents/[name]/
├── [name]_agent.py        ← Main agent script
├── config.json            ← Configuration (paths, params)
├── README.md              ← Documentation
└── test_[name].py         ← Tests
```

**Build rules:**

1. **One file = one step** (if step is complex) or **one file = entire pipeline** (if simple)
2. **Claude CLI for AI** — use `claude -p --model [model]` instead of API key
3. **CSV for data** — read/write via pandas or csv module
4. **Git auto-commit** — if agent modifies CRM/PM data
5. **Telegram notification** — if human approval is needed
6. **Dry-run mode** — mandatory `--dry-run` flag
7. **Logging** — stdout for launchd, file for debug
8. **Idempotency** — re-run must not duplicate data

### Step 3: Build

For each step from the spec:

1. Write the function/script
2. Handle errors according to the spec
3. Add logging
4. Add dry-run branch

### Step 4: Create skill

Create skill file `skills/agents/[name]-run.md` with instructions on how to run the agent manually.

### Step 5: Create launchd plist (if scheduled)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "...">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.yourcompany.[name]-agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$AGENTS_PATH/[name]/[name]_agent.py</string>
    </array>
    <key>StartInterval</key>
    <integer>[seconds]</integer>
    <key>StandardOutPath</key>
    <string>/tmp/[name]-agent.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/[name]-agent-error.log</string>
</dict>
</plist>
```

### Step 6: Hand off to Agent Tester

Notify that the agent is ready for testing.

## Output

- Agent code in `$AGENTS_PATH/[name]/`
- Skill file in `$SKILLS_PATH/skills/agents/`
- Launchd plist (if scheduled)

## Examples

### Reference: Email Pipeline

```
google-tools/
├── email_monitor.py        ← Step 1: Gmail API check
├── email_agent.py          ← Step 2: AI classify (haiku)
├── email_action_agent.py   ← Step 3: CRM match + log
└── data/
    ├── email_summaries/    ← Output: summaries
    └── email_drafts/       ← Output: draft replies
```

Trigger: launchd every 3600s
Model: Claude haiku (classification)
Output: CRM activities + PM tasks + drafts + Telegram notify

## Related skills

- `process-analyst` — creates the spec
- `agent-tester` — tests the agent
- `git-workflow` — commit and PR
