---
name: client-discovery
description: Analyze client automation/AI requests into structured scoping with hours, pricing, and priorities
---
# Client Discovery

> Take a client's raw list of requests and produce a structured scoping breakdown with categories, hours, pricing, dependencies, and recommended phases.

## When to use

- Client sends a list of automation/AI tasks they want built
- "analyze requests from [client]"
- "scope this project"
- "estimate hours for [client]"
- "create proposal breakdown"
- Before a discovery/scoping call — to come prepared with estimates

## Dependencies

- Other skills: `query-leads` (CRM data), `client-workspace` (for shared docs)
- External: none (this is an analysis skill, no scripts)

## How to execute

### Step 1: Gather inputs

1. **Client's raw request list** — from TG, email, call notes, or shared doc
2. **Client's tech stack** — CRM, ATS, tools they use (from CRM notes or questionnaire)
3. **Company context** — from CRM: size, industry, budget signals

### Step 2: For each request item, analyze

For every item in the client's list, produce:

| Field | Description |
|-------|-------------|
| **Name** | Short name (2-5 words) |
| **Category** | `agent` / `automation` / `integration` / `knowledge-base` / `product` |
| **What client wants** | Plain language — what outcome they expect |
| **What needs to be built** | Technical: APIs, triggers, LLM prompts, data flows |
| **Key questions** | What we need to clarify before building |
| **Integrations** | Which tools/APIs: CRM, ATS, LinkedIn, Bluedot, etc. |
| **Complexity** | `low` (prompt eng, 4-6h) / `medium` (integration, 6-10h) / `high` (multi-system, 10-15h) |
| **Hours estimate** | Range: low-high |
| **Dependencies** | Other items that should be built first |

### Step 3: Prioritize

Group items into:

1. **Quick wins** (low complexity, high impact) — do first, show value fast
2. **High ROI** (medium complexity, core business impact) — second phase
3. **Strategic** (high complexity, long-term value) — third phase
4. **Can skip / already exists** — tools like NotebookLM that solve it out of the box

### Step 4: Check for off-the-shelf solutions

Before estimating custom build hours, check if an existing tool already does it:
- NotebookLM for knowledge bases
- Zapier/Make for simple automations
- Existing SaaS (Fireflies for transcription, Clay for signal tracking, etc.)

Flag these as "buy vs build" decisions with the client.

### Step 5: Produce summary table

```
| # | Request | Hours | $ | Phase | Notes |
|---|---------|-------|---|-------|-------|
| 1 | Job posting AI | 4-6 | 400-600 | Quick win | Few-shot prompting |
| 2 | CRM automation | 8-12 | 800-1200 | Phase 2 | Needs API access |
...
| TOTAL | | 60-90 | $6K-9K | | |
```

### Step 6: Generate discovery questions

Based on gaps in the analysis, generate a pre-call questionnaire:
- Questions about tech stack and data
- Questions about priorities and budget
- Questions about team and users

Use `client-workspace` skill to create a shared Google Doc with these questions.

## Rate Card

| Service | Rate |
|---------|------|
| Consulting / implementation | $100/hr, 15-min increments ($25 min) |
| Quick win (4-6h) | $400-600 |
| Medium project (6-12h) | $600-1200 |
| Complex project (10-15h) | $1000-1500 |

## Output Format

The analysis should be saved as:
1. **CRM activity** — summary in activities.csv
2. **Shared doc** — if questionnaire created, in client's Discovery folder
3. **Text summary** — shown to Ivan for review before the call

## Checklist

- [ ] All client request items analyzed and categorized
- [ ] Hours and pricing estimated for each item
- [ ] Off-the-shelf alternatives checked
- [ ] Items prioritized into phases
- [ ] Discovery questions generated for unknowns
- [ ] Summary table produced
- [ ] CRM activity logged

## Examples

### Client J (2026-03-04)

Client: Diana Prince, Client J (IT recruiting, 22 years experience)
Stack: Recruitee (ATS), Streak (CRM), Bluedot (call recording)
11 automation requests → analyzed into 4 blocks:
- Block 1: CRM & Sales (18-27h, $1.8-2.7K)
- Block 2: Recruiting process (16-22h, $1.6-2.2K)
- Block 3: Knowledge base (13-20h, $1.3-2K) — partly solved by NotebookLM
- Block 4: Client-facing products (14-22h, $1.4-2.2K)
Total: 61-91h, $X-YK

## Related skills

- `client-workspace` — create shared docs for discovery
- `call-prep` — prepare for the discovery/scoping call
- `query-leads` — CRM data lookup
