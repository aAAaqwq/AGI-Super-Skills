---
name: call-prep
description: Call preparation: research, CRM, talking points, PDF
---
# Call Prep

> Preparation for a call with a client/lead: research, CRM update, conversation plan, PDF

## When to use

- "prepare for a call with X"
- "call prep for Y"
- "gather info before a meeting"
- "conversation plan with a client"
- There is a scheduled call in the calendar or task

## Dependencies

- CRM data: `query-leads`
- Web search: WebSearch, WebFetch
- PDF: `weasyprint` (Python)

## Paths

| What | Path |
|------|------|
| CRM Companies | `$CRM_PATH/contacts/companies.csv` |
| CRM People | `$CRM_PATH/contacts/people.csv` |
| CRM Leads | `$CRM_PATH/relationships/leads.csv` |
| CRM Activities | `$CRM_PATH/activities.csv` |
| PM Tasks | `$PM_PATH/pm_tasks_master.csv` |
| Output PDF | `$PROJECT_ROOT/docs/{slug}-call-prep.pdf` |

## How to execute

### Step 1: Gather internal data

Read everything from CRM about this person/company:

```
1. companies.csv -- company record
2. people.csv -- person record + notes
3. leads.csv -- lead stage, priority, next_action, notes
4. activities.csv -- communication history (emails, calls, messages)
5. pm_tasks_master.csv -- related tasks
```

**Important:** gather ALL interaction history -- not just the latest entry.

### Step 2: External research

Run in parallel:

```
1. WebSearch: "{name} {company}" -- general info
2. WebSearch: "{name} linkedin founder" -- career, track record
3. WebFetch: company website -- products, positioning, pricing
4. WebSearch: "{company} 2025 2026" -- latest news
5. WebFetch: LinkedIn profile (if URL exists in CRM)
```

**What to look for:**
- Who is this person (track record, previous companies, expertise)
- What the company does (product, business model, stage)
- Company size, funding, revenue
- Latest news, hiring, pivots
- Potential pain points (from job postings, posts, comments)

### Step 3: Update CRM

Based on research, update:
- `companies.csv` -- description, industry, size
- `people.csv` -- role, notes from research
- `leads.csv` -- notes

Use skill `update-lead`.

### Step 3.5: Check client workspace

If a client workspace exists in Drive (`Clients/{CompanyName}/`), check:

```bash
DM="$GOOGLE_TOOLS_PATH/.venv/bin/python3 $GOOGLE_TOOLS_PATH/drive_manager.py"

# Search for client folder
$DM search "CompanyName" --folder <YOUR_CLIENTS_FOLDER_ID>

# List docs in client folder
$DM list CLIENT_FOLDER_ID

# For each shared doc — check if client opened/edited it
$DM info DOC_ID
# → Look at lastModifiedBy: if it's the client, they filled it in
# → Look at modifiedTime: when was it last touched
```

**If questionnaire exists and client filled it in:** read their answers and incorporate into conversation plan.
**If questionnaire exists but client didn't fill it:** mention on the call, go through questions verbally.
**If no workspace exists:** consider creating one with `client-workspace` skill.

See skill: `client-workspace`

### Step 4: Build conversation plan

Standard discovery call structure:

```
Phase 1: Small talk + context (~3 min)
  - How you got in touch
  - What you know about them (but not everything -- let them tell)

Phase 2: Business discovery (~10 min)
  - What does the company do?
  - What products/services?
  - Who are the customers?
  - What stage? (pre-launch, growth, scaling)
  - How many people on the team?

Phase 3: Pain point discovery (~10 min)
  - What specifically hurts? What problem do they want to solve?
  - What have they already tried?
  - What didn't work and why?
  - What is the budget/expectations?
  - What are the deadlines?

Phase 4: Show relevance (~5 min)
  - Specific example of how we solved a similar task
  - Don't sell -- show that you understand the problem
  - Adapt to the level of the conversation partner

Phase 5: Propose a format (~5 min)
  - Option A: Audit (5-10h, understand scope)
  - Option B: Pilot (fixed task, 2 weeks)
  - Option C: Partnership (after pilot)
  - DO NOT name a price without scope

Phase 6: Next steps (~2 min)
  - Specific next step
  - Deadline
  - What is needed from them
```

### Step 5: Identify risks

Typical risks:

| Risk | How to respond |
|------|---------------|
| Wants to "look" for free | An audit is work. Minimum paid. |
| Scope too large | Narrow down to one project/channel |
| Wants equity deal right away | Paid pilot first |
| Already has a solution, comparing | Ask who they're comparing with |
| Not the decision maker | Ask who makes the decision |
| No budget | Propose a minimal pilot |

### Step 6: Generate PDF

Create HTML with all info, convert to PDF via weasyprint:

```python
import weasyprint

html = "..." # structured HTML with sections 1-5
weasyprint.HTML(string=html).write_pdf('/path/to/output.pdf')
```

**PDF structure:**
1. Who they are (table: name, role, contacts, track record)
2. What the company does (business model, products, stage)
3. Meeting context (how you got in touch, pain points)
4. Conversation plan by phases (with specific questions)
5. What NOT to do
6. Risks and how to respond
7. Quick reference (time, contacts, CRM IDs)

**Open PDF:**
```bash
open /path/to/output.pdf
```

## Checklist

- [ ] CRM data gathered (company, person, lead, activities)
- [ ] Web research conducted (LinkedIn, website, news)
- [ ] CRM updated with research
- [ ] Client workspace checked (shared docs, questionnaire answers)
- [ ] Conversation plan built with specific questions
- [ ] Risks identified
- [ ] PDF generated and opened
- [ ] Call time verified (timezone!)

## Examples

### Example 1: Discovery call with a lead

```
User: prepare for a call with Alisa from shftd.ai

Claude:
1. Reads CRM → comp-shftd, p-shftd-001, lead-shftd-001
2. WebSearch "Alisa Chumachenko shftd.ai" → Game Insight, GOSU.ai, Forbes
3. WebFetch shftd.ai → pre-launch, venture studio
4. Updates CRM with research
5. Builds plan: discovery call, 6 phases, specific questions
6. Generates PDF → docs/alisa-shftd-call-prep.pdf
```

### Example 2: Follow-up call with a client

```
User: prepare for a follow-up with Client F Tech

Claude:
1. Reads CRM → comp-clientf, lead, activities (history)
2. Checks what was discussed earlier
3. Builds plan: review progress, discuss blockers, next steps
4. Generates PDF
```

## Limitations

- LinkedIn profiles may be restricted (auth wall)
- New companies may not have web presence
- Pricing/revenue may not always be publicly available
- PDF generation requires weasyprint (`pip install weasyprint`)

## Related skills

- `query-leads` -- reading CRM data
- `update-lead` -- updating CRM with research
- `daily-briefing` -- may contain info about scheduled calls
- `git-workflow` -- commit CRM changes after update
