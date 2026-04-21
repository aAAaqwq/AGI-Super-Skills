---
name: documents
description: Manage company & personal documents — rekvizity, passport, INN, bank details, scans. Store locally + Google Drive. Send data blocks on request.
---
# Documents

> Manage company & personal documents: structured data (rekvizity, passport, bank) + scans in Google Drive. Quick retrieval and sending when clients/partners request.

## When to use

- "надішли реквізити на X" / "send rekvizity to X"
- "дай паспортні дані" / "give passport data"
- "потрібні дані ФОП для договору"
- "завантаж документ" / "upload document scan"
- "де мої документи?" / "where are my documents?"
- When a client/partner asks for company or personal data for contracts, invoices, NDA
- When user provides new document scans to organize

## Dependencies

- Other skills: `google-drive`, `email-send-bulk` (for sending)
- External: Python 3, google-api-python-client

## Paths

### Local (structured data)

| What | Path |
|------|------|
| Passport & INN data | `$DATA_PATH/personal/passport_data.md` |
| Company wiki | `~/company-wiki/` |

### Google Drive (scans & originals)

| Folder | ID | Purpose |
|--------|----|---------|
| **Company** (root) | `<YOUR_COMPANY_FOLDER_ID>` | All company/personal docs |
| Legal | `<YOUR_LEGAL_FOLDER_ID>` | Contracts, NDA, agreements (signed) |
| Personal | `<YOUR_PERSONAL_FOLDER_ID>` | Passport, INN, personal ID scans |
| Bank | `<YOUR_BANK_FOLDER_ID>` | Bank statements, account details |

### Drive structure

```
WeLabelData (root: <YOUR_DRIVE_ROOT_ID>)
├── Company/                    <- THIS SKILL
│   ├── Legal/                  <- signed contracts, NDA, agreements
│   ├── Personal/               <- passport, INN, ID scans
│   └── Bank/                   <- bank statements, account details
├── Clients/                    <- client-workspace skill
│   ├── ClientF/
│   ├── ClientG/
│   └── ...
└── Templates/                  <- invoice, NDA, proposal templates
    ├── Invoices/
    ├── NDA/
    └── Proposals/
```

## Structured Data Blocks

These are ready-to-send text blocks. Read from `passport_data.md` and format for the context.

### Block: ФОП Реквізити (for contracts/invoices)

```
ФОП <YOUR_FULL_NAME>
ІПН (РНОКПП): <YOUR_TAX_ID>
Тел: <YOUR_PHONE>
Email: <YOUR_EMAIL>
```

### Block: Паспортні дані (for legal/contracts)

```
Паспорт громадянина України:
- Серія та номер: <YOUR_PASSPORT_SERIES_NUMBER>
- Виданий: <YOUR_PASSPORT_ISSUER>
```

### Block: Повні реквізити (FOP + passport + INN)

```
ФОП <YOUR_FULL_NAME>
ІПН (РНОКПП): <YOUR_TAX_ID>
Паспорт: серія <YOUR_PASSPORT_SERIES> №<YOUR_PASSPORT_NUMBER>, виданий <YOUR_PASSPORT_ISSUER>
Тел: <YOUR_PHONE>
Email: <YOUR_EMAIL>
```

## How to execute

### Retrieve data for email/contract

1. Read structured data from `passport_data.md`
2. Select the appropriate block based on what was requested
3. Format and send (via `send_email.py` or copy to clipboard)

```bash
# Read current data
cat $DATA_PATH/personal/passport_data.md
```

### Upload new document scan

1. Determine the type (personal, legal, bank)
2. Upload to the correct Drive folder
3. Update `passport_data.md` if the scan contains new structured data

```bash
DM="$GOOGLE_TOOLS_PATH/.venv/bin/python3 $GOOGLE_TOOLS_PATH/drive_manager.py"

# Personal documents (passport, INN, etc.)
$DM upload /path/to/scan.jpg --folder <YOUR_PERSONAL_FOLDER_ID> --name "Descriptive-name.jpg"

# Legal documents (contracts, NDA)
$DM upload /path/to/contract.pdf --folder <YOUR_LEGAL_FOLDER_ID> --name "Contract-ClientName-YYYY-MM.pdf"

# Bank documents
$DM upload /path/to/statement.pdf --folder <YOUR_BANK_FOLDER_ID> --name "Bank-statement-YYYY-MM.pdf"
```

### Send rekvizity by email

```bash
cd $GOOGLE_TOOLS_PATH

# Send FOP rekvizity (reply to thread)
.venv/bin/python3 send_email.py \
  --to partner@example.com \
  --subject "Re: Original Subject" \
  --body "BLOCK_TEXT_HERE" \
  --reply-to "from:partner@example.com subject:Original Subject"
```

### List what's in Drive

```bash
DM="$GOOGLE_TOOLS_PATH/.venv/bin/python3 $GOOGLE_TOOLS_PATH/drive_manager.py"

# All company docs
$DM list <YOUR_COMPANY_FOLDER_ID>

# Personal docs (passport, INN)
$DM list <YOUR_PERSONAL_FOLDER_ID>

# Legal docs
$DM list <YOUR_LEGAL_FOLDER_ID>

# Bank docs
$DM list <YOUR_BANK_FOLDER_ID>
```

## Naming conventions

| Type | Format | Example |
|------|--------|---------|
| Passport scan | `Passport-pages-{N}-{M}.jpg` | `Passport-pages-2-3.jpg` |
| INN card | `IPN-card.jpg` | `IPN-card.jpg` |
| Contract | `Contract-{Client}-{YYYY-MM}.pdf` | `Contract-ClientG-2026-03.pdf` |
| NDA | `NDA-{Client}-{YYYY-MM}.pdf` | `NDA-ClientG-2026-03.pdf` |
| Bank statement | `Bank-statement-{YYYY-MM}.pdf` | `Bank-statement-2026-02.pdf` |
| ID card | `ID-card-{type}.jpg` | `ID-card-biometric.jpg` |

## Current documents in Drive

### Personal/
- `Passport-pages-2-3.jpg` — main passport page (photo, name, DOB)
- `Passport-pages-4-5.jpg` — passport issuance page
- `Passport-pages-10-11-registration.jpg` — registration stamp
- `IPN-card.jpg` — tax identification card

## Adding new data types

When user provides new documents (e.g., bank details, biometric passport, driving license):

1. Extract structured data from the document
2. Add a new section to `passport_data.md` (or create separate file if large)
3. Upload scan to the appropriate Drive folder
4. Add a new "Block" section to this SKILL.md for quick retrieval
5. Commit changes via git-workflow

## Security notes

- `passport_data.md` contains sensitive PII — NEVER commit to public repos
- Drive folders are private by default — do NOT share Company/ folder publicly
- When sending data by email — always confirm with user before sending
- Keep local copies in `data/personal/` which is in `.gitignore`

## Related skills

- `company-wiki` — company infrastructure, services, accounts (not personal data)
- `google-drive` — underlying Drive API commands
- `client-workspace` — client folder management
- `invoice-generator-agent` — uses FOP rekvizity for invoice generation
- `legal-review` — review contracts before signing
