# CRM Skills

## Architecture

```
sales/crm/
├── contacts/
│   ├── companies.csv        <- All companies/organizations
│   └── people.csv           <- All contacts
│
├── products.csv             <- Our products/services
│
├── relationships/
│   ├── clients.csv          <- Clients (company + product)
│   ├── partners.csv         <- Partners (company + product)
│   └── leads.csv            <- Leads (company + product + stage)
│
├── projects/                <- Specific initiatives
│   └── {project_name}/
│
└── activities.csv           <- All communications
```

## Working rules

### 1. Contacts are universal
- One person = one record in `people.csv`
- One company = one record in `companies.csv`
- **NEVER** duplicate contacts

### 2. Connections through relationships
- Client = record in `clients.csv` (company_id + product_id)
- Partner = record in `partners.csv`
- Lead = record in `leads.csv`
- A company can simultaneously be a client + partner for different products

### 3. ID formats
- Companies: `comp-{name}` (comp-acme, comp-globex)
- People: `p-{company}-{number}` (p-acme-001)
- Clients: `cli-{company}-{number}` (cli-acme-001)
- Partners: `ptnr-{company}-{number}` (ptnr-acme-001)
- Leads: `lead-{company}-{number}` (lead-newco-001)

### 4. Status transitions
```
Lead -> Client:
1. leads.csv: stage = "won"
2. Create a record in clients.csv
3. DO NOT delete from leads.csv (history)

Lead -> Lost:
1. leads.csv: stage = "lost"
2. Add notes with the reason
```

### 5. Required fields
- **Companies:** company_id, name, created_date, last_updated
- **People:** person_id, first_name, email OR phone, created_date, last_updated
- **Relationships:** *_id, company_id, product_id, status, created_date, last_updated

### 6. Before PR -- required
- Run `change-review` skill
- Verify there are no duplicates
- Verify all IDs exist (referential integrity)

## Skills

| Skill | Description |
|-------|-------------|
| `add-lead` | Add company/person/relationship |
| `update-lead` | Update existing record |
| `query-leads` | Search and filtering |
| `change-review` | Review changes before PR |

## Paths

```
Base:         $CRM_PATH/
Contacts:     $CRM_PATH/contacts/
Relationships:$CRM_PATH/relationships/
Products:     $CRM_PATH/products.csv
Projects:     $CRM_PATH/projects/
```
