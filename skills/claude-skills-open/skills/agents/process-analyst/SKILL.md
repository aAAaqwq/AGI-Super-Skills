---
name: process-analyst
description: Process analysis, gap finding, human dialogue, spec generation
---
# Process Analyst Agent

> Analyzes a business process, finds gaps, clarifies with the human, generates a complete specification for building an agent.

## When to use

- Before building a new agent
- "analyze process X"
- "what is needed to automate Y"

## Dependencies

- Skills: `dispatcher`, `memory`
- Data: CRM schema, PM data, existing skills, existing tools

## Input

Process name or number from the Process Map:

| # | Process | Domain |
|---|---------|--------|
| 1 | Email Pipeline (monitor + classify + action) | Inbound |
| 2 | Telegram inbound (checking replies) | Inbound |
| 3 | WhatsApp inbound (checking chats) | Inbound |
| 4 | LinkedIn inbound (incoming messages) | Inbound |
| 5 | Telegram outreach (mass messaging) | Outreach |
| 6 | Email outreach (mass messaging) | Outreach |
| 7 | LinkedIn outreach | Outreach |
| 8 | WhatsApp outreach | Outreach |
| 9 | Touch Scheduler (follow-up 3-7-14) | Follow-up |
| 10 | Channel Truth (sync last_contact) | Follow-up |
| 11 | CRM add lead/contact/company | CRM |
| 12 | CRM Import (staging -> master) | CRM |
| 13 | Activity logging across all channels | CRM |
| 14 | Daily Briefing (morning report) | PM |
| 15 | Weekly Review | PM |
| 16 | Task Prioritization | PM |
| 17 | Invoice generation | Finance |
| 18 | Payment tracking + follow-up | Finance |
| 19 | Watchers (website change alerts) | Monitoring |
| 20 | Telegram scrape (channels, competitors) | Monitoring |

## How to execute

### Step 1: Gather context

For the specified process, read:

1. **Existing skill** (if any) — from `$SKILLS_PATH/skills/`
2. **Existing tool** (if any) — scripts, API clients
3. **Data** — which CSV/files the process reads or writes
4. **Schema** — `$CRM_PATH/schema.yaml`
5. **Adjacent processes** — what runs before/after this process
6. **Email Pipeline** as reference — `$GOOGLE_TOOLS_PATH/` (the only fully automated agent)

### Step 2: Analysis by checklist

For each process, fill in:

```markdown
## Process Analysis: [Name]

### 1. TRIGGER (what starts the process)
- [ ] Trigger defined (schedule / event / manual)
- [ ] Frequency defined
- [ ] Launch conditions are clear

### 2. INPUT (input data)
- [ ] Data sources defined
- [ ] Data format is clear
- [ ] Data access is available (API keys, credentials)
- [ ] Data volume is estimated

### 3. PROCESSING (processing logic)
- [ ] Business rules described
- [ ] Edge cases defined
- [ ] Dependencies on other processes defined
- [ ] AI component needed? Which model?

### 4. OUTPUT (result)
- [ ] What is created / modified
- [ ] Where it is written (CSV, file, API)
- [ ] Who is the consumer of the result
- [ ] Output format is defined

### 5. ERROR HANDLING
- [ ] What to do on API error
- [ ] What to do with invalid data
- [ ] Retry logic
- [ ] Alerting (where to report an error)

### 6. HUMAN-IN-THE-LOOP
- [ ] Which decisions require human approval
- [ ] Approval format (Telegram notification? CLI prompt?)
- [ ] What to do if human did not respond

### 7. INTEGRATION
- [ ] Which other agents depend on this one
- [ ] Which agents does this one depend on
- [ ] Shared state (which files are shared)
- [ ] Are race conditions possible?

### 8. GAPS (what is missing)
- [ ] List of questions for the owner
- [ ] Missing tools
- [ ] Missing data
- [ ] Missing credentials
```

### Step 3: Dialogue with the human

For each unfilled item -- formulate a clear question:

**Question format:**
```
[SECTION] [QUESTION]
Context: what is already known
Options: if there are obvious choices
Default: if there is a recommendation
```

**Rules:**
- No more than 5 questions at a time
- From most important to least important
- Suggest a default where possible
- If something is obvious from context -- don't ask, just record it

### Step 4: Generate Spec

After all clarifications -- create a file:

```
$AGENTS_PATH/specs/[process-name].spec.md
```

**Spec structure:**

```markdown
# Agent Spec: [Name]

## Meta
- Process ID: #
- Priority: high/medium/low
- Complexity: simple/medium/complex
- Estimated components: N files

## Overview
One paragraph on what the agent does.

## Trigger
- Type: schedule / event / manual
- Schedule: cron expression (if schedule)
- Event: what triggers it (if event)

## Pipeline

```
[Input] → [Step 1] → [Step 2] → ... → [Output]
```

## Steps

### Step 1: [Name]
- Input: what it receives
- Logic: what it does
- Output: what it produces
- Error: what on error
- Model: if AI (sonnet/haiku/opus)

### Step 2: [Name]
...

## Data Flow

| Reads | Writes |
|-------|--------|
| file.csv | file.csv |

## Human Approval Points
- Where approval is needed
- How to notify (Telegram/CLI)
- Timeout: what if no response

## Dependencies
- Other agents: [list]
- Tools: [list]
- Credentials: [list]

## Testing Plan
- Unit: what to test in isolation
- Integration: which agents to test with
- Dry-run: how to run without side effects

## Rollback
- How to rollback if something went wrong
```

### Step 5: Validation

- Re-read the spec
- Check that all gaps are closed
- Check consistency with other specs (if any)
- Save and notify the human

## Output

Spec file in `$AGENTS_PATH/specs/[name].spec.md`

## Examples

### Example 1: Daily Briefing Analysis

```
User: analyze process #14 Daily Briefing

Claude: [reads daily-briefing.md, pm_tasks_master.csv, email agent, activities.csv]
Claude: Here is the analysis of the Daily Briefing process:

TRIGGER: schedule, every morning at 08:00
INPUT: pm_tasks_master.csv, activities.csv, email summaries
PROCESSING: AI summary (haiku)

GAPS -- need to clarify:
1. [TRIGGER] What time for the morning briefing? Default: 08:00
2. [OUTPUT] Where to send the result? Options: Telegram / CLI / both
3. [HUMAN] Is approval needed before sending, or automatic?

Claude: creates spec after responses
```

## Related skills

- `agent-builder` — takes the spec and builds the agent
- `agent-tester` — tests the built agent
- `dispatcher` — task routing
- `memory` — context from previous sessions
