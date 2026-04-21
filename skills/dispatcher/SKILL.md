---
name: dispatcher
description: Route complex multi-step tasks, multi-skill orchestration, post-execution checklist
user-invocable: false
---
# Dispatcher

> **MANDATORY first step** before selecting any skill. Contains the complete routing table for all 61+ skills. The system prompt only shows ~50 skills — this file is the single source of truth.

## IMPORTANT: Always Load First

**Claude Code has a ~50 skill limit in the system prompt.** Skills beyond this limit are silently dropped. The dispatcher contains the COMPLETE routing table. Always consult this file before choosing a skill, especially for:
- Sending emails → `email-send-direct` (NOT `email-send-bulk`)
- Call preparation → `call-prep`
- Document/rekvizity requests → `documents`

## When to use

- **ALWAYS** — before selecting a skill for any task
- Task requires 2+ skills (e.g.: query CRM -> send telegram)
- It's unclear which skill is needed
- An execution plan is needed for a complex task

## Step 1: Analyze the task

Determine:
- **Domain:** CRM, PM, Sales, Channels, Finance, Dev, Infra, Legal, Agents?
- **Action:** read, create, update, send, review, deploy, monitor?
- **Object:** company, person, task, message, invoice, document, agent?

## Step 2: Skill Routing Table

### CRM — Contacts & Relationships

| Trigger | Skill |
|---------|-------|
| Add new company/person/lead | `add-lead` |
| Update lead status, notes, contacts | `update-lead` |
| Search, filter, reports on CRM data | `query-leads` |
| Import data from staging to CRM | `crm-import` |
| Log email/call/meeting activity | `log-activity` |
| Validate CRM/PM changes before PR | `change-review` |

### PM — Tasks & Projects

| Trigger | Skill |
|---------|-------|
| "What should I do today?" / priority tasks | `show-today` |
| Morning briefing (tasks + email + follow-ups) | `daily-briefing` |
| Weekly project review report | `weekly-review` |
| Create new project with task breakdown | `create-project` |
| Mark task done + schedule follow-up | `pm-done` |
| Task prioritization and scoring | `task-prioritization` |

### Sales — Consulting & Client Work

| Trigger | Skill |
|---------|-------|
| Prepare for a call with client/lead | `call-prep` |
| Analyze client requests → scoping + pricing | `client-discovery` |
| Create client folder, share docs, pre-call check | `client-workspace` |
| Multi-channel outreach (TG + email + WhatsApp) | `mass-outreach` |

### Channels — Communication

| Trigger | Skill |
|---------|-------|
| Send single email (with dry-run, reply, attachments) | `email-send-direct` |
| Bulk email sending | `email-send-bulk` |
| Read inbox / sent emails via Gmail API | `email-read` |
| AI inbox classification + TG notification | `email-monitor` |
| Send Telegram DM (CSV, rate-limited) | `telegram-send` |
| Check inbound Telegram messages | `telegram-check` |
| Export/import/lookup Telegram contacts | `telegram-contacts` |
| Telegram group management (post, members) | `telegram-groups` |
| Search Telegram channels, read posts | `telegram-scrape` |
| Send WhatsApp message (Baileys) | `whatsapp-send` |
| LinkedIn automation (mouse/keyboard, CDP) | `linkedin-cdp` |
| Connect to AI agent via MCP | `mcp-agent-connect` |

### Finance — Invoices & Payments

| Trigger | Skill |
|---------|-------|
| Generate invoice (manual, no CRM) | `invoice` |
| Auto-generate invoice with CRM integration | `invoice-generator-agent` |
| Track expenses, export data | `expense-tracker` |
| Stripe webhook management (AI Kitchen Pro) | `stripe-webhook` |

### Dev — Code & Deployment

| Trigger | Skill |
|---------|-------|
| AI code review for PR or local changes | `code-review` |
| Git: branch, PR, merge, cleanup | `git-workflow` |
| Deploy website via GitHub PR + Cloud Build | `deploy-website` |

### Infra — Tools & Auth

| Trigger | Skill |
|---------|-------|
| Google OAuth setup / refresh tokens | `google-auth` |
| Google Drive: upload, folders, share, create doc | `google-drive` |
| Facebook CDP automation (comments, data) | `infra-facebook-cdp` |
| Create/update Telethon session | `telegram-session` |
| ttyd + Tailscale for mobile terminal access | `remote-access` |

### Legal

| Trigger | Skill |
|---------|-------|
| Review NDA, contracts, agreements | `legal-review` |

### Agents — Autonomous Runners

| Trigger | Skill |
|---------|-------|
| Build agent from spec | `agent-builder` |
| Test agent (dry-run, unit, integration) | `agent-tester` |
| Process analysis, gap finding, spec generation | `process-analyst` |
| Auto: daily briefing | `daily-briefing-run` |
| Auto: weekly review | `weekly-review-run` |
| Auto: email outreach | `email-outreach-run` |
| Auto: Telegram inbound processing | `telegram-inbound-run` |
| Auto: Telegram scraping | `telegram-scraper-run` |
| Auto: LinkedIn inbound processing | `linkedin-inbound-run` |
| Auto: WhatsApp outreach | `whatsapp-outreach-run` |
| Auto: channel/contact sync | `channel-truth-run` |
| Auto: lead trigger monitoring | `watchers-run` |
| Auto: payment tracking | `payment-tracker-run` |
| Auto: experiment runner | `experiment-runner-run` |

### Documents & Data

| Trigger | Skill |
|---------|-------|
| Send rekvizity, passport data, INN | `documents` |
| Upload document scans to Drive | `documents` |
| "де мої документи?" / company data | `documents` |

### Core — Always Available

| Trigger | Skill |
|---------|-------|
| Persistent memory (observations, summaries) | `memory` |
| Timezone conversion, local time | `timezone` |
| Company knowledge base (domains, infra, accounts) | `company-wiki` |
| AI agent contacts (add, list, remove MCP) | `agent-contacts` |

## Step 3: Multi-Skill Orchestration

Examples of combinations:

**"Send all clients a message about new prices"**
```
1. query-leads → get clients (relationships/clients.csv)
2. For each → find contact (contacts/people.csv)
3. telegram-send / email-send-bulk → send
4. log-activity → record in activities.csv
```

**"Good morning, what's new?"**
```
1. daily-briefing → tasks + email + follow-ups
```

**"Prepare for a call with X and send the agenda"**
```
1. call-prep → research + plan (includes workspace check)
2. email-send-direct → send agenda
3. log-activity → record activity
```

**"Client sent a list of automation requests"**
```
1. query-leads → get CRM context
2. client-discovery → analyze requests, estimate hours, prioritize
3. client-workspace → create shared questionnaire doc
4. log-activity → record activity
```

**"Set up folder for new client"**
```
1. query-leads → get company + contact email
2. client-workspace → create folder structure + share
3. log-activity → record activity
```

**"Generate and send invoice to client"**
```
1. query-leads → get client + billing info
2. invoice-generator-agent → generate invoice
3. google-drive → upload to client folder
4. email-send-direct → send to client
5. log-activity → record
```

**"Deploy website changes"**
```
1. code-review → check changes
2. git-workflow → branch + PR
3. deploy-website → deploy via Cloud Build
```

**"Review this NDA and send feedback"**
```
1. legal-review → analyze document
2. email-send-direct → send feedback
3. log-activity → record
```

**"Send rekvizity / passport data to partner"**
```
1. documents → read structured data blocks
2. email-send-direct → send (reply to thread)
3. log-activity → record
```

**"User provides document scans"**
```
1. documents → extract data, upload scans to Drive
2. Update passport_data.md with structured data
```

## Step 4: Execute

- Simple task → execute immediately
- Complex task → load skill via Read tool
- Multi-step → create a plan, execute sequentially

## Post-Execution Checklist

After executing a task that modifies data:

```
What changed?
      │
      ├── DATA (CSV in CRM/PM)?
      │         ↓
      │    change-review → git-workflow
      │
      └── CODE (*.py, *.js, *.md)?
                ↓
           code-review → git-workflow
```

**If there was outreach (email/telegram/call):**
1. Add a record in `activities.csv` (log-activity)
2. Update task in `pm_tasks_master.csv`
3. change-review → PR → merge

**If CRM/PM data was modified:**
1. Validation against `schema.yaml`
2. change-review → PR → merge

**If code or skills were modified:**
1. code-review → PR → merge

## Data Paths

| Domain | Path |
|--------|------|
| CRM | `$CRM_PATH/` |
| PM | `$PM_PATH/` |
| CRM Schema | `sales/crm/schema.yaml` (always read first for CRM tasks) |

## New Skill Registration Checklist

When creating a new skill, ALWAYS complete ALL steps:

1. **Create SKILL.md** in `~/claude-skills/skills/{category}/{skill-name}/SKILL.md`
   - Use template: `~/claude-skills/skills/TEMPLATE.md`
   - Must have frontmatter with `name` and `description`

2. **Create symlink:** `ln -s ~/claude-skills/skills/{category}/{skill-name} ~/.claude/skills/{skill-name}`

3. **Update THIS dispatcher:**
   - Add to the correct section in Step 2 Routing Table
   - Add orchestration example in Step 3 if relevant

4. **Verify discovery:**
   - Check if skill appears in system prompt (it won't if >50 skills)
   - If NOT visible — that's OK, dispatcher covers it

5. **Commit via git-workflow:** branch → PR → merge

**CRITICAL:** Steps 3-4 are what gets forgotten. If you skip updating the dispatcher, the skill becomes invisible when the system prompt drops it.

## When dispatcher is NOT needed

- User explicitly says which skill ("load telegram-send")
- Simple answer to a question (no actions required)
- Continuation of a previous task (context already exists)
