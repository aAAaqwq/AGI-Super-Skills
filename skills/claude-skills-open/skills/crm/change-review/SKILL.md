---
name: change-review
description: Validate CRM/PM changes before PR
---
# Change Review

> Review of CRM and PM data changes before PR -- a data equivalent of code-review

**Public repository:** https://github.com/your-org/claude-change-review-skill

## When to use

- Before a PR with CRM changes
- Before a PR with PM changes (tasks, projects)
- "check my CRM changes"
- "change review"
- "data review"

## Paths

| What | Path |
|------|------|
| CRM | `$CRM_PATH/` |
| CRM Schema | `$CRM_PATH/schema.yaml` |
| PM | `$PM_PATH/` |

## How to execute

### Step 1: Read schema.yaml

```bash
# ALWAYS read the schema first -- it contains all the rules
cat $CRM_PATH/schema.yaml
```

Schema contains:
- `primary_key` -- unique identifier
- `required` -- required fields
- `unique` -- unique fields
- `foreign_keys` -- relationships between tables
- `composite_unique` -- composite unique keys
- `enums` -- allowed values
- `id_format` -- regex for ID format
- `rules` -- business rules

### Step 2: Get the diff

```bash
git diff HEAD -- sales/crm/
```

### Step 3: Load data

```python
import pandas as pd
import yaml

# Read schema
with open('$CRM_PATH/schema.yaml') as f:
    schema = yaml.safe_load(f)

# Load all tables
base_path = '$CRM_PATH/'
tables = {}
for table_name, table_def in schema['tables'].items():
    tables[table_name] = pd.read_csv(base_path + table_def['file'])
```

### Step 4: Validate against schema

```python
import re

def validate_table(name, df, table_schema, all_tables):
    issues = []

    # 1. Primary key uniqueness
    pk = table_schema['primary_key']
    if df[pk].duplicated().any():
        dups = df[df[pk].duplicated()][pk].tolist()
        issues.append(('critical', f'Duplicate {pk}: {dups}'))

    # 2. Required fields
    for field in table_schema.get('required', []):
        missing = df[df[field].isna()]
        if len(missing) > 0:
            issues.append(('critical', f'Missing required {field}: {len(missing)} rows'))

    # 3. Unique fields
    for field in table_schema.get('unique', []):
        if field == pk:
            continue
        dups = df[df[field].notna() & df[field].duplicated()]
        if len(dups) > 0:
            issues.append(('high', f'Duplicate {field}: {dups[field].tolist()}'))

    # 4. Foreign keys
    for fk_field, ref in table_schema.get('foreign_keys', {}).items():
        ref_table, ref_field = ref.split('.')
        valid_values = all_tables[ref_table][ref_field]
        invalid = df[df[fk_field].notna() & ~df[fk_field].isin(valid_values)]
        if len(invalid) > 0:
            issues.append(('critical', f'Invalid {fk_field} references: {invalid[fk_field].tolist()}'))

    # 5. Composite unique
    for fields in table_schema.get('composite_unique', []):
        dups = df[df.duplicated(subset=fields, keep=False)]
        if len(dups) > 0:
            issues.append(('critical', f'Duplicate {"+".join(fields)} combination'))

    # 6. Enum values
    for field, valid_values in table_schema.get('enums', {}).items():
        invalid = df[df[field].notna() & ~df[field].isin(valid_values)]
        if len(invalid) > 0:
            issues.append(('high', f'Invalid {field} values: {invalid[field].unique().tolist()}'))

    # 7. ID format
    if 'id_format' in table_schema:
        pattern = table_schema['id_format']
        invalid = df[~df[pk].str.match(pattern, na=False)]
        if len(invalid) > 0:
            issues.append(('low', f'Invalid ID format: {invalid[pk].tolist()}'))

    return issues

# Validate all tables
for name, table_schema in schema['tables'].items():
    if name in tables:
        issues = validate_table(name, tables[name], table_schema, tables)
        for severity, msg in issues:
            print(f'[{severity.upper()}] {name}: {msg}')
```

### Step 5: Business rules (from schema.rules)

```python
# Example: won_lead_has_client
if 'leads' in tables and 'clients' in tables:
    won_leads = tables['leads'][tables['leads']['stage'] == 'won']
    for _, lead in won_leads.iterrows():
        client_exists = (
            (tables['clients']['company_id'] == lead['company_id']) &
            (tables['clients']['product_id'] == lead['product_id'])
        ).any()
        if not client_exists:
            print(f"[HIGH] Won lead without client: {lead['lead_id']}")
```

### Step 6: Output

```markdown
## Change Review Summary

**Schema version:** 1.0
**Files reviewed:** [list]
**Risk Level:** Critical / High / Medium / Low

### Critical Issues (must fix)
- [table:field] Description

### High Priority
- [table:field] Description

### Validation by Schema
- [x] Primary keys unique
- [x] Required fields present
- [x] Foreign keys valid
- [x] Enum values valid
- [x] Business rules passed
```

---

## Severity Levels

| Level | Schema Rule | Examples |
|-------|-------------|----------|
| **Critical** | primary_key, required, foreign_keys, composite_unique | Duplicate ID, broken FK |
| **High** | unique, enums, rules | Duplicate email, invalid status |
| **Medium** | (manual check) | Missing optional fields |
| **Low** | id_format | Wrong ID pattern |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Broken FK | Add parent record or fix ID |
| Duplicate PK | Change ID or remove duplicate |
| Invalid enum | Use values from schema.yaml |
| Wrong ID format | See id_format in schema.yaml |

## Related skills

- `add-lead` -- adding records (also reads schema.yaml)
- `update-lead` -- updating records
- `code-review` -- for code (not data)
