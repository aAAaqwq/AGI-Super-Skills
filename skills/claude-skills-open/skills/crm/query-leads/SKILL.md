---
name: query-leads
description: Search, filter, reports on CRM data
---
# CRM Query Leads

> Search, filtering, and reports on CRM data

## When to use

- "show high-priority leads"
- "who needs follow-up"
- "how many leads from YC"
- "CRM statistics"

## Paths

| What | Path |
|------|------|
| Leads | `$CRM_PATH/relationships/leads.csv` |
| Companies | `$CRM_PATH/contacts/companies.csv` |
| People | `$CRM_PATH/contacts/people.csv` |
| Activities | `$CRM_PATH/activities.csv` |

## Basic query

```python
import pandas as pd
from datetime import date

leads = pd.read_csv('$CRM_PATH/relationships/leads.csv')
people = pd.read_csv('$CRM_PATH/contacts/people.csv')
companies = pd.read_csv('$CRM_PATH/contacts/companies.csv')
```

## Common queries

### High-priority leads

```python
high = leads[leads['priority'] == 'high']
print(high[['lead_id', 'company_id', 'stage', 'next_action']])
```

### Follow-ups for today

```python
today = str(date.today())
followups = leads[leads['next_action_date'] == today]
print(followups[['lead_id', 'company_id', 'next_action']])
```

### By source

```python
# All inbound leads
inbound = leads[leads['source_direction'] == 'inbound']

# All from a specific source
from_facebook = leads[leads['source'] == 'facebook']

# Filter by campaign detail
campaign = leads[leads['source_detail'].str.contains('lookalike', na=False)]
```

### By stage

```python
# Leads in negotiation
negotiation = leads[leads['stage'] == 'negotiation']

# Won deals
won = leads[leads['stage'] == 'won']
```

### Statistics

```python
# Count by stage
print(leads['stage'].value_counts())

# Count by priority
print(leads['priority'].value_counts())

# Count by source
print(leads['source'].value_counts())
```

### Joining leads with companies and people

```python
# Add company name to leads
merged = leads.merge(
    companies[['company_id', 'name', 'industry']],
    on='company_id',
    how='left'
)

# Add primary contact info
merged = merged.merge(
    people[['person_id', 'first_name', 'last_name', 'email']],
    left_on='primary_contact_id',
    right_on='person_id',
    how='left'
)
```

## Export results

```python
# To CSV
hot.to_csv('/tmp/hot_leads.csv', index=False)

# To JSON
hot.to_json('/tmp/hot_leads.json', orient='records', force_ascii=False)

# Just a list of emails
emails = hot['email'].dropna().tolist()
print(', '.join(emails))
```

## Related skills

- `add-lead` -- add a new lead
- `update-lead` -- update existing record
- `show-today` -- tasks related to CRM
