---
name: crm-import
description: Import data from staging to master CRM with validation
---
# CRM Import

> Import new data from staging to master CRM database with validation and approval.

## When to use

- "import CRM data from X"
- "add new people/companies/leads from file Y"
- "validate staging data"
- A file appeared in `$CRM_PATH/_staging/incoming/`

## Input

- CSV file with new records
- Table type (auto-detect or explicitly specified)

## How to execute

### Step 1: Run the agent

```bash
cd $AGENTS_PATH/crm-import

# Auto-detect table type
python3 crm-import_agent.py sales/crm/_staging/incoming/new_people.csv

# Or specify explicitly
python3 crm-import_agent.py data.csv --table companies
```

**Modes:**
- `--dry-run` -- validation without git commit
- `--validate-only` -- schema validation only
- `--show-duplicates` -- show potential duplicates

### Step 2: The agent will perform

1. Schema validation (required fields, ID format, enums)
2. Deduplication check (exact + fuzzy matching)
3. Foreign key validation
4. Business rules check
5. ID generation (if missing)
6. Git branch creation + commit
7. Telegram notification

### Step 3: You will receive a Telegram message

```
CRM Import Ready for Review

Table: people
New records: 5
Branch: crm-import-people-new_people-2026-02-12
Commit: a1b2c3d4

Next steps:
1. Review changes: git diff main..crm-import-people-new_people-2026-02-12
2. Approve: gh pr create (then merge)
3. Reject: git branch -D crm-import-people-new_people-2026-02-12
```

### Step 4: Review changes

```bash
cd $PROJECT_ROOT
git diff main..crm-import-people-new_people-2026-02-12
```

### Step 5: Approve or Reject

**Approve:**
```bash
gh pr create --base main --head crm-import-people-new_people-2026-02-12 \
  --title "Import new people records" \
  --body "Importing 5 new people from staging"

# Merge PR
gh pr merge --merge
```

**Reject:**
```bash
git branch -D crm-import-people-new_people-2026-02-12
```

## Output

- Git branch with new records
- Validation report (if there are issues)
- Telegram notification with summary
- Console log with details

## Validation Rules

### Critical (stops the import)
- Missing required fields
- Invalid ID format
- Invalid enum values
- Foreign key violations

### High (flagged for review)
- Potential duplicates (fuzzy match)
- Business rule violations (e.g., person without email AND phone)

### Info (log only)
- Auto-generated IDs
- Auto-set timestamps
- Skipped exact duplicates

## ID Generation

If ID is missing, the agent generates it automatically:

| Table | Format | Example |
|-------|--------|---------|
| companies | `comp-{slug}` | `comp-acme-corp` |
| people | `p-{company-slug}-{N}` | `p-acme-001` |
| clients | `cli-{company-slug}-{N}` | `cli-acme-001` |
| partners | `ptnr-{company-slug}-{N}` | `ptnr-acme-001` |
| leads | `lead-{company-slug}-{N}` | `lead-acme-001` |
| deals | `deal-{company-slug}-{N}` | `deal-acme-001` |
| products | `prod-{slug}` | `prod-labeling` |
| activities | `act-{N}` | `act-042` |

## Deduplication

**Exact match (skip):**
- Primary key match
- Email match (people)
- Website match (companies)
- LinkedIn URL match

**Fuzzy match (review):**
- People: similar name + same company
- Companies: similar name (ignoring Inc/Ltd/etc)

## Examples

### Example 1: Import new people

```bash
# Create staging file
cat > sales/crm/_staging/incoming/new_people.csv << EOF
person_id,first_name,last_name,email,company_id,role,created_date,last_updated
,John,Smith,john@example.com,comp-acme,Engineer,,
,Jane,Doe,jane@example.com,comp-acme,Manager,,
EOF

# Import
python3 crm-import_agent.py sales/crm/_staging/incoming/new_people.csv

# Result:
# - ID: p-acme-001, p-acme-002
# - Branch: crm-import-people-new_people-2026-02-12
# - Telegram notification
```

### Example 2: Dry-run before import

```bash
# Verify without commit
python3 crm-import_agent.py data.csv --dry-run

# If OK -> run
python3 crm-import_agent.py data.csv
```

### Example 3: Show duplicates

```bash
python3 crm-import_agent.py data.csv --show-duplicates
```

## Rollback

If you need to revert:

```bash
# Find merge commit
git log --oneline --grep="Import.*records"

# Revert
git revert <commit-sha>
```

## Staging Directory

```
sales/crm/_staging/
├── incoming/     # New files for import
├── review/       # Duplicate review reports
└── archive/      # Processed files
```

## Errors

### "Cannot auto-detect table type"
-> Add `--table people`

### "Foreign key violation"
-> Import the parent record first (e.g., company before people)

### "Critical schema issues"
-> Fix required fields, ID format, enum values in the CSV

### "Git commit failed"
-> Check `git status`, the working directory may be dirty

## Related skills

- `change-review` -- called automatically by the agent
- `git-workflow` -- for PR creation and merge

## Dependencies

- Python 3.8+
- pandas, pyyaml
- git, gh CLI
- tg-tools (Telegram)

## Limitations

- CSV only (no Google Sheets support yet)
- Insert only (no updating existing records)
- One table at a time
- Synchronous processing (for <1000 records)

## Future improvements

- Google Sheets integration
- Bulk update mode
- Multi-table import (denormalized -> normalized)
- Auto-scheduling (watch directory)
- ML fuzzy matching
