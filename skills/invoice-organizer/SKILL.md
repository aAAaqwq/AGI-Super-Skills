---
name: invoice-organizer
description: Use when "organizing invoices", "sorting receipts", "tax preparation", "expense tracking", or asking about "invoice renaming", "financial documents", "bookkeeping automation"
version: 1.0.0
---

<!-- Adapted from: awesome-claude-skills/invoice-organizer -->

# Invoice Organizer Guide

Automatically organize invoices and receipts for tax preparation and bookkeeping.

## When to Use

- Preparing for tax season
- Managing business expenses
- Organizing messy receipt folders
- Setting up invoice filing systems
- Archiving financial records
- Preparing documentation for accountants

## Workflow

1. **Scan** - Identify all invoice files
2. **Extract** - Read key information from each
3. **Rename** - Apply consistent naming format
4. **Organize** - Sort into logical folders
5. **Report** - Generate CSV summary

## Information Extraction

From each invoice, extract:

- Vendor/company name
- Invoice number
- Date
- Amount
- Product/service description
- Payment method

## Naming Convention

```
YYYY-MM-DD Vendor - Invoice - Description.ext
```

Examples:

- `2024-03-15 Adobe - Invoice - Creative Cloud.pdf`
- `2024-01-10 Amazon - Receipt - Office Supplies.pdf`

## Organization Patterns

### By Vendor

```
Invoices/
├── Adobe/
├── Amazon/
├── Google/
└── Microsoft/
```

### By Year and Category (Tax-Friendly)

```
Invoices/
├── 2024/
│   ├── Software/
│   ├── Hardware/
│   ├── Services/
│   └── Travel/
└── 2023/
```

### By Quarter

```
Invoices/
├── 2024/
│   ├── Q1/
│   ├── Q2/
│   ├── Q3/
│   └── Q4/
```

### By Tax Category

```
Invoices/
├── Deductible/
├── Partially-Deductible/
└── Personal/
```

## Commands

```bash
# Find all invoices
find . -type f \( -name "*.pdf" -o -name "*.jpg" -o -name "*.png" \) -print

# Create folder structure
mkdir -p "Invoices/2024/Software/Adobe"

# Copy with new name (preserve original)
cp "original.pdf" "Invoices/2024/Software/Adobe/2024-03-15 Adobe - Invoice - Creative Cloud.pdf"
```

## CSV Export Format

```csv
Date,Vendor,Invoice Number,Description,Amount,Category,File Path
2024-03-15,Adobe,INV-12345,Creative Cloud,52.99,Software,path/to/file.pdf
```

Useful for:

- Importing into accounting software
- Sharing with accountants
- Expense tracking and reporting
- Tax preparation

## Handling Special Cases

### Missing Information

- Flag file for manual review
- Use file modification date as fallback
- Create "Needs-Review/" folder

### Duplicate Invoices

- Compare file hashes
- Keep highest quality version
- Note duplicates in summary

### Multiple Formats

Works with:

- PDF invoices
- Scanned receipts (JPG, PNG)
- Email attachments
- Screenshots
- Bank statements

## Best Practices

- Backup originals before reorganizing
- Use consistent date format (YYYY-MM-DD)
- Organize monthly, not annually
- Keep receipts 7 years (audit period)
- Tag by deductibility for taxes
