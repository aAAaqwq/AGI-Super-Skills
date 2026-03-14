---
name: invoice-generator-agent
description: Automatic invoice generation with CRM integration
---
# Invoice Generator Agent

> Generates professional invoices for WeLabelData Inc. with CRM integration

## When to use

- "generate invoice for deal-enterprise-002"
- "create invoice for Enterprise Corp"
- "invoice for Client D"
- When deal.stage = 'delivered' and an invoice needs to be issued

## How to execute

### Step 1: Run the agent

**By Deal ID:**
```bash
cd $AGENTS_PATH/invoice-generator
python3 invoice_generator_agent.py --deal deal-enterprise-002
```

**By client name:**
```bash
python3 invoice_generator_agent.py --client "Enterprise Corp"
```

**Interactive mode** (shows all deals with stage='delivered'):
```bash
python3 invoice_generator_agent.py --interactive
```

**Dry-run** (check without writing):
```bash
python3 invoice_generator_agent.py --dry-run --deal deal-enterprise-002
```

### Step 2: The agent will execute

1. **Load deal** from deals.csv + client/company/contact info
2. **Validate**: stage must be 'delivered' or 'in_progress'
3. **Get invoice number**: atomically from invoice_tracker.json (with file locking)
4. **Generate invoice**: call generate_invoice.py → HTML + PDF
5. **Update CRM**: deals.csv → stage='invoiced', invoice_date, invoice_number
6. **Show for review**:
   ```
   ✓ Invoice #100 generated
   Client:      Client D Inc.
   Amount:      $1,000.00 USD
   Description: Training services
   Files:       docs/invoices/Invoice_100_WeLabelData_ClientD.pdf

   Review the invoice and choose:
   1. Open PDF for review
   2. Send to client now
   3. Skip sending (manual delivery)
   4. Cancel (delete invoice)
   ```
7. **Process user decision**:
   - Open PDF → opens PDF viewer
   - Send now → shows instructions for sending email (placeholder for now)
   - Skip → generates but does not send (for manual delivery)
   - Cancel → deletes files, rolls back invoice number, does not change CRM
8. **Log activity** → activities.csv
9. **Send Telegram** → Saved Messages with details
10. **Write log** → invoice_generator_log.json

### Step 3: If email needs to be sent

Email sending is not yet implemented; the agent will show instructions:
```
Email sending not yet implemented in this version.
Please send the invoice manually using your email client.

To: bob@clientd.example.com
Subject: Invoice #100 - WeLabelData - Training services
Attachment: docs/invoices/Invoice_100_WeLabelData_ClientD.pdf
```

Use skill `/email-send-direct` or google-tools to send.

## Human Approval

**IMPORTANT**: The agent ALWAYS requires human review before sending.

### Review options:
- **Open PDF** → opens PDF for viewing, then asks again
- **Send now** → (placeholder for now) shows instructions for email
- **Skip sending** (DEFAULT) → generates invoice, updates CRM, does not send
- **Cancel** → full rollback (deletes files, restores invoice_tracker, does not change deals.csv)

## Rollback

If the user chooses "Cancel":
1. Deletes invoice files (HTML + PDF)
2. Restores invoice_tracker.json to the previous number
3. Does NOT change deals.csv (no CRM update was made)
4. Logs 'cancelled' activity
5. Sends Telegram notification

## Client mapping

The agent automatically maps CRM companies → client keys for generate_invoice.py:

| Client Key | Company patterns |
|-----------|-----------------|
| clienta | clienta, doe, clientk |
| clientb | clientb |
| clientc | clientc |
| clientd | clientd |
| cliente | cliente, clientetech |

Unknown clients → custom client with company.name

## Data Flow

### Reads:
- `sales/crm/relationships/deals.csv`
- `sales/crm/relationships/clients.csv`
- `sales/crm/contacts/companies.csv`
- `sales/crm/contacts/people.csv`
- `docs/company/invoice_tracker.json`

### Writes:
- `docs/invoices/Invoice_{n}_WeLabelData_{Client}.html`
- `docs/invoices/Invoice_{n}_WeLabelData_{Client}.pdf`
- `sales/crm/relationships/deals.csv` (update: stage, invoice_date, invoice_number)
- `sales/crm/activities.csv` (append)
- `docs/company/invoice_tracker.json` (increment)
- `agents/data/invoice_generator_log.json`
- Telegram notification via tg-tools

## Error Handling

| Error | Behavior |
|-------|----------|
| Deal not found | Exit with message, suggest --interactive |
| Deal already has invoice | Warn, ask for confirmation to regenerate |
| Invalid stage | Exit, explain which stages are valid ('delivered', 'in_progress') |
| generate_invoice.py fail | Show stderr, exit without CRM update |
| PDF generation fail | Save HTML, continue with CRM update |
| CRM write fail | Critical, save files but warn about manual CRM fix |
| Telegram fail | Warning, continue (non-critical) |

## Testing

### Dry-run
```bash
python3 invoice_generator_agent.py --dry-run --deal deal-enterprise-002
```
Shows parameters without creating files or CRM updates.

### Full test with rollback
```bash
python3 invoice_generator_agent.py --interactive
# Select deal
# Review invoice
# Choose "4. Cancel"
# Verify that files are deleted, invoice_tracker unchanged
```

## Examples

### Generate for a specific deal
```bash
python3 invoice_generator_agent.py --deal deal-enterprise-002
```

### Find deal by client
```bash
python3 invoice_generator_agent.py --client "Client D"
```

### Interactive selection
```bash
python3 invoice_generator_agent.py --interactive
```

### Generate without approval prompt
```bash
python3 invoice_generator_agent.py --no-approve --deal deal-enterprise-002
```
Auto-skip sending, just generates and logs.

## Integration

### Upstream:
- Requires deals.csv with stage='delivered'
- Requires CRM data (clients, companies, people)
- Uses generate_invoice.py

### Downstream:
- **Payment Tracker** reads deals with stage='invoiced'
- **Daily Briefing** can show recent invoices
- Manual workflows use the generated PDF files

## File Locking

Invoice numbering uses `fcntl.flock()` for atomic increment:
- Prevents race conditions during parallel generation
- Critical section: read invoice_tracker.json → +1 → write

## Output example

```
Generating invoice #100...

==================================================
✓ Invoice #100 generated
==================================================
Client:      Client D Inc.
Contact:     Bob
Amount:      $1,000.00 USD
Description: Training services
==================================================
Files:
  PDF:  /Users/.../docs/invoices/Invoice_100_WeLabelData_ClientD.pdf
  HTML: /Users/.../docs/invoices/Invoice_100_WeLabelData_ClientD.html
==================================================

Review the invoice and choose:
  1. Open PDF for review
  2. Send to client now
  3. Skip sending (manual delivery)
  4. Cancel (delete invoice)

Choice [3]: 3

✓ Done! Invoice #100 generated successfully.
```

Telegram notification:
```
Invoice Generated

Invoice #100 | $1,000.00 USD
Client: Client D Inc. (Bob)
Description: Training services

Status: Skipped
Files: /Users/.../Invoice_100_WeLabelData_ClientD.pdf

Deal: deal-clientd-001 → stage updated to 'invoiced'
```

## Related skills

- `/invoice` - original skill (direct call to generate_invoice.py)
- `/email-send-direct` - for sending email
- `/log-activity` - for logging CRM activities
- `/telegram-send` - for notifications

## Notes

- Invoice numbering is global (not per-client, not per-year)
- Re-generation keeps the same number (overwrites files)
- Default action: "Skip sending" (generates, user sends manually)
- All non-USA clients receive international wire details
- Payment terms: 7 days (default, uses payment tracker)
