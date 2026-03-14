---
name: add-lead
description: Add company/person/relationship to CRM
---
# CRM Add

> Adding a new company, person, or relationship

## When to use

- "add company X"
- "add contact Y"
- "new client/partner/lead"

## Architecture

See `$SKILLS_PATH/skills/crm/README.md`

## Paths

| What | Path |
|------|------|
| Companies | `$CRM_PATH/contacts/companies.csv` |
| People | `$CRM_PATH/contacts/people.csv` |
| Clients | `$CRM_PATH/relationships/clients.csv` |
| Partners | `$CRM_PATH/relationships/partners.csv` |
| Leads | `$CRM_PATH/relationships/leads.csv` |
| Products | `$CRM_PATH/products.csv` |

## Schemas

### contacts/companies.csv
```csv
company_id,name,website,linkedin_url,type,industry,geo,size,description,created_date,last_updated
```
- **type:** company, enterprise, ngo, individual
- **size:** small, medium, enterprise, individual

### contacts/people.csv
```csv
person_id,first_name,last_name,email,phone,linkedin_url,company_id,role,notes,created_date,last_updated
```

### relationships/clients.csv
```csv
client_id,company_id,product_id,status,contract_start,contract_end,mrr,currency,primary_contact_id,notes,created_date,last_updated
```
- **status:** active, paused, churned

### relationships/partners.csv
```csv
partner_id,company_id,product_id,partnership_type,status,since,primary_contact_id,revenue_share,notes,created_date,last_updated
```
- **partnership_type:** training_partner, workforce_partner, reseller_agreement, referral_partner

### relationships/leads.csv
```csv
lead_id,company_id,product_id,stage,source,source_direction,source_detail,priority,primary_contact_id,estimated_value,currency,next_action,next_action_date,notes,created_date,last_updated,last_contact_via_primary
```
- **stage:** new, qualified, proposal, negotiation, won, lost
- **source:** google, website, facebook, linkedin, email, telegram, referral, direct, event, calendly, research
- **source_direction:** inbound, outbound
- **source_detail:** _(optional)_ campaign name, referrer, post URL, etc.

## How to add

### 1. New company

```python
import pandas as pd
from datetime import date

df = pd.read_csv('$CRM_PATH/contacts/companies.csv')

# Check for duplicate
if 'example.com' in df['website'].values:
    print("Company already exists!")
else:
    new_row = {
        'company_id': 'comp-example',
        'name': 'Example Inc',
        'website': 'example.com',
        'type': 'company',
        'industry': 'Technology',
        'geo': 'USA',
        'created_date': str(date.today()),
        'last_updated': str(date.today())
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv('$CRM_PATH/contacts/companies.csv', index=False)
```

### 2. New contact

```python
# First make sure the company exists!
companies = pd.read_csv('$CRM_PATH/contacts/companies.csv')
if 'comp-example' not in companies['company_id'].values:
    print("Add the company first!")

people = pd.read_csv('$CRM_PATH/contacts/people.csv')

new_person = {
    'person_id': 'p-example-001',
    'first_name': 'John',
    'last_name': 'Doe',
    'email': 'john@example.com',
    'company_id': 'comp-example',
    'role': 'CEO',
    'created_date': str(date.today()),
    'last_updated': str(date.today())
}
```

### 3. New client (relationship)

```python
# Company and product must exist!
clients = pd.read_csv('$CRM_PATH/relationships/clients.csv')

new_client = {
    'client_id': 'cli-example-001',
    'company_id': 'comp-example',
    'product_id': 'prod-labeling',
    'status': 'active',
    'contract_start': str(date.today()),
    'primary_contact_id': 'p-example-001',
    'created_date': str(date.today()),
    'last_updated': str(date.today())
}
```

## Validation (REQUIRED!)

### Before saving:
- [ ] ID is unique
- [ ] company_id exists in companies.csv (for people, relationships)
- [ ] product_id exists in products.csv (for relationships)
- [ ] person_id exists in people.csv (for primary_contact_id)
- [ ] No duplicates (check by email, website, name)
- [ ] created_date and last_updated are filled in

### After changes:
- [ ] Run `change-review` skill before PR

## ID formats

| Type | Format | Example |
|------|--------|---------|
| Company | comp-{name} | comp-acme |
| Person | p-{company}-{number} | p-acme-001 |
| Client | cli-{company}-{number} | cli-acme-001 |
| Partner | ptnr-{company}-{number} | ptnr-acme-001 |
| Lead | lead-{company}-{number} | lead-newco-001 |

## Related skills

- `update-lead` -- update existing record
- `query-leads` -- search
- `change-review` -- review before PR
