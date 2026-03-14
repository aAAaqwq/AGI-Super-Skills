---
name: client-workspace
description: Create client folder structure in Drive, share docs, check permissions before calls
---
# Client Workspace

> Create and manage client folders in Google Drive — shared docs, questionnaires, proposals, pre-call checks.

## When to use

- "create workspace for [client]"
- "set up folder for [client]"
- "share doc with [client]"
- "check docs before call with [client]"
- Before any consulting call — verify shared docs are accessible
- After creating a questionnaire, proposal, or contract for a client

## Dependencies

- Other skills: `google-drive`, `query-leads` (CRM lookup)
- External: Python 3, google-api-python-client

## Paths

| What | Path |
|------|------|
| Drive Manager | `$GOOGLE_TOOLS_PATH/drive_manager.py` |
| Token | `$GOOGLE_TOOLS_PATH/token.json` |
| Venv Python | `$GOOGLE_TOOLS_PATH/.venv/bin/python3` |
| CRM People | `$DATA_PATH/sales/crm/contacts/people.csv` |
| CRM Companies | `$DATA_PATH/sales/crm/contacts/companies.csv` |

## Known Folder IDs

| Folder | ID |
|--------|----|
| Clients (root) | `<YOUR_CLIENTS_FOLDER_ID>` |

## Standard Folder Structure

```
Clients/
  {CompanyName}/
    Discovery/        -- questionnaires, call notes, research
    Proposals/        -- scoping docs, estimates, quotes
    Contracts/        -- signed agreements, NDAs
    Deliverables/     -- work product, reports
```

## How to execute

### Step 1: Create client workspace

```bash
DM="$GOOGLE_TOOLS_PATH/.venv/bin/python3 $GOOGLE_TOOLS_PATH/drive_manager.py"
CLIENTS_ROOT="<YOUR_CLIENTS_FOLDER_ID>"

# Create company folder
$DM create-folder "CompanyName" --parent $CLIENTS_ROOT
# Note the folder ID from output, then create subfolders:
$DM create-folder "Discovery" --parent COMPANY_FOLDER_ID
$DM create-folder "Proposals" --parent COMPANY_FOLDER_ID
$DM create-folder "Contracts" --parent COMPANY_FOLDER_ID
$DM create-folder "Deliverables" --parent COMPANY_FOLDER_ID
```

### Step 2: Create shared doc (questionnaire, proposal, etc.)

Write HTML content to a temp file, then create Google Doc:

```bash
# Create doc from HTML
$DM create-doc "Client J — Pre-call Questionnaire" --folder DISCOVERY_FOLDER_ID --html /tmp/questionnaire.html

# Share with client
$DM share DOC_ID --email client@company.com --role writer --notify --message "Please fill in before our call"
```

### Step 3: Pre-call check

Before any call, verify client has access and check activity:

```bash
# List docs in client folder
$DM list COMPANY_FOLDER_ID

# Check permissions on shared docs
$DM permissions DOC_ID

# Check if client opened/edited the doc
$DM info DOC_ID
# Look at: lastModifiedBy, modifiedTime — if not client, they haven't filled it in
```

### Step 4: After sharing — remove public access if present

Drive API sometimes adds `anyone` link access. Always verify and remove:

```bash
$DM permissions DOC_ID
# If "anyone" permission exists, remove it via Python:
# drive.permissions().delete(fileId=DOC_ID, permissionId='anyoneWithLink').execute()
```

## Questionnaire Templates

### Discovery questionnaire (consulting)

HTML template with sections:
1. **Stack & Team** — current tools, team size, roles
2. **Data** — volumes, formats, examples of ideal output
3. **Priorities** — which automation first, biggest pain points
4. **Open** — anything else before the call

Style: fields with `▸` markers or gray boxes for answers. Use checkboxes (☐) for multiple choice.

### Proposal doc

Create after discovery call with:
1. Executive summary
2. Scope per item (description, hours estimate, price)
3. Timeline with phases
4. Terms (rate, payment schedule)

## Checklist

- [ ] Client folder created under `Clients/`
- [ ] Subfolders created (Discovery, Proposals, Contracts, Deliverables)
- [ ] Shared doc created and shared with client email
- [ ] Public link access removed (only named users)
- [ ] CRM updated with folder link (in company notes or people notes)
- [ ] Pre-call: verified client has opened shared docs

## Related skills

- `google-drive` — underlying Drive API commands
- `call-prep` — call preparation (invoke workspace check as part of prep)
- `client-discovery` — analyzing client requests into scoped proposals
- `query-leads` — CRM data lookup
