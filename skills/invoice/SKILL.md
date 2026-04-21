---
name: invoice
description: Manual invoice generation without CRM
---
# Invoice Generator

Generate professional invoices for WeLabelData Inc.

## Overview

Two ways to generate invoices:

### 1. Invoice Generator Agent (RECOMMENDED)
Full automation with CRM integration:
- Loads deal data from CRM
- Auto-fills client/contact info
- Updates deal stage to 'invoiced'
- Logs activities
- Sends Telegram notifications
- Human review before sending

**See**: `/invoice-generator-agent` skill

### 2. Direct Script (Manual)
Low-level script for direct use without CRM integration.

This skill generates invoices in HTML and PDF formats with:
- WeLabelData company branding
- Client information (pre-configured or custom)
- International wire transfer details (for non-US clients)
- Auto-incrementing invoice numbers

## Script Location

```
$SCRIPTS_PATH/generate_invoice.py
```

## Usage

### Basic Usage

```bash
cd $PROJECT_ROOT
python3 scripts/generate_invoice.py --client "ClientName" --amount 1000
```

### Known Clients (Auto-fill)

These clients have pre-configured contact info:

| Key | Company | Contact | Location |
|-----|---------|---------|----------|
| `clienta` | Client A BV | John Doe | Netherlands |
| `clientb` | Client B Analytics | Jane Smith | USA |
| `clientc` | Client C sp. z o.o. | Alice Johnson | Poland |
| `clientd` | Client D Inc. | Bob | Japan |
| `cliente` | Client E Tech | Charlie Brown | Sweden |

### Examples

```bash
# Invoice for known client
python3 scripts/generate_invoice.py --client clienta --amount 707 --description "Video annotation services"

# Invoice for new client
python3 scripts/generate_invoice.py --client "New Company" --amount 500 --contact "John Doe" --email "john@example.com"

# Custom invoice number and date
python3 scripts/generate_invoice.py --client clientb --amount 3492 --number 100 --date "2/15/26"

# HTML only (no PDF)
python3 scripts/generate_invoice.py --client clienta --amount 707 --no-pdf
```

### Options

| Flag | Description |
|------|-------------|
| `--client` | Client name or key (required) |
| `--amount` | Invoice amount in USD (required) |
| `--description` | Service description (default: "Services") |
| `--contact` | Contact name (overrides default) |
| `--email` | Contact email (overrides default) |
| `--date` | Invoice date in M/D/YY format |
| `--number` | Invoice number (default: auto-increment) |
| `--output` | Output file path (without extension) |
| `--no-pdf` | Generate HTML only |
| `--no-bank` | Exclude bank/wire details |

## Output

Invoices are saved to:
```
$PROJECT_ROOT/docs/invoices/
```

Format: `Invoice_{number}_WeLabelData_{ClientName}.pdf`

## Invoice Numbering

- Last invoice: tracked in `/docs/company/invoice_tracker.json`
- Auto-increments with each generation
- Override with `--number` flag

## After Generation (Manual Script Only)

If using the direct script (not recommended), manually:
1. Review the generated PDF
2. Update deals.csv with invoice info:
   ```csv
   invoice_date,invoice_number
   2026-02-04,98
   ```
3. Send to client via email/WhatsApp
4. Track in CRM activities

**NOTE**: The Invoice Generator Agent does all of this automatically.

## When to Use Which

| Use Case | Tool | Why |
|----------|------|-----|
| Invoice for existing deal in CRM | **Agent** | Auto CRM integration, activity logging |
| Quick one-off invoice | Script | Faster for non-CRM clients |
| Testing invoice layout | Script | No CRM side effects |
| Production workflow | **Agent** | Full automation + audit trail |

## Related

- `/invoice-generator-agent` - Automated agent with CRM integration (RECOMMENDED)
- Company info: `/docs/company/yourcompany-company-info.md`
- Deals tracking: `/sales/crm/relationships/deals.csv`
- Bank details PDF: `/docs/company/originals/Wire-Details.pdf`
