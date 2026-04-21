---
name: update-lead
description: Update status, contacts, notes in CRM
---
# CRM Update Lead

> Updating status, priority, and other fields of an existing lead

## When to use

- "update status to responded"
- "change priority to high"
- "add a note"
- "change source to google"
- After receiving a response

## Paths

| What | Path |
|------|------|
| Leads | `$CRM_PATH/relationships/leads.csv` |
| People | `$CRM_PATH/contacts/people.csv` |

## How to update

```python
import pandas as pd
from datetime import date

# Load
df = pd.read_csv('$CRM_PATH/contacts/people.csv')

# Find by linkedin_url or email
mask = df['email'] == 'example@email.com'
# or
mask = df['linkedin_url'] == 'https://linkedin.com/in/example'

# Update fields
df.loc[mask, 'status'] = 'responded'
df.loc[mask, 'priority'] = 'high'
df.loc[mask, 'notes'] = 'Responded positively 2025-02-03'
df.loc[mask, 'last_updated'] = str(date.today())  # REQUIRED!

# Save
df.to_csv('$CRM_PATH/contacts/people.csv', index=False)
```

## How to update leads.csv

```python
import pandas as pd
from datetime import date

leads = pd.read_csv('$CRM_PATH/relationships/leads.csv')

mask = leads['lead_id'] == 'lead-example-001'

leads.loc[mask, 'stage'] = 'qualified'
leads.loc[mask, 'next_action'] = 'Schedule discovery call'
leads.loc[mask, 'next_action_date'] = '2026-03-10'
leads.loc[mask, 'last_updated'] = str(date.today())

leads.to_csv('$CRM_PATH/relationships/leads.csv', index=False)
```

## Batch update

```python
# Update all who responded "yes"
responded_emails = ['email1@test.com', 'email2@test.com']

for email in responded_emails:
    mask = df['email'] == email
    df.loc[mask, 'status'] = 'responded'
    df.loc[mask, 'priority'] = 'high'
    df.loc[mask, 'last_updated'] = str(date.today())

df.to_csv(path, index=False)
```

## Stages (leads.csv)

```
new -> qualified -> proposal -> negotiation -> won/lost
```

## Statuses (people.csv)

```
new -> researched -> contacted -> responded -> meeting -> won/lost
```

Do not skip stages without a reason.

## Source of Truth (since 2026-03-02)

**leads.csv `next_action` is the canonical source for sales follow-ups.**

- Do NOT create pm_tasks for sales follow-ups (invoices, payment checks, deal closing).
- Instead, update the lead's `next_action` and `next_action_date` in leads.csv.
- pm_tasks_master.csv is for dev/project tasks only.

## Source fields

Leads have three source fields:
- **source** — enum: google, website, facebook, linkedin, email, telegram, referral, direct, event, calendly, research
- **source_direction** — inbound or outbound
- **source_detail** — _(optional)_ campaign name, referrer, post URL, etc.

## Rules

1. **ALWAYS** update `last_updated`
2. If you change `status` -- add an explanation in `notes`
3. If there is a response -- record the text in `response` or `notes`
4. Verify the record exists before updating
5. For sales actions, update `next_action` + `next_action_date` in leads.csv (not pm_tasks)

## Related skills

- `query-leads` -- find a lead before updating
- `log-activity` -- log activity
- `telegram-check` -- check for responses
