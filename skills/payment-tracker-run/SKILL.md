---
name: payment-tracker-run
description: Automatic payment tracking and follow-up
---
# Payment Tracker - Run

> Monitors outstanding invoices, tracks payment status, sends reminders

## When to use

- "check payments"
- "which invoices are overdue?"
- "payment status check"
- "run payment tracker"
- Manual trigger for immediate payment check

## How to execute

### Full run

```bash
cd $AGENTS_PATH/payment-tracker
python3 payment_tracker_agent.py
```

This will execute:
1. Load outstanding invoices from deals.csv
2. Calculate payment status (OK/DUE_SOON/OVERDUE/PENDING_INVOICE)
3. Enrich with client/company context
4. Generate Telegram notification
5. Create follow-up email drafts
6. Log activities to activities.csv
7. Git commit changes

### Dry-run (no changes)

```bash
python3 payment_tracker_agent.py --dry-run
```

- Analyzes all invoices
- Shows what would be sent
- Does NOT write to CSV
- Does NOT send Telegram
- Does NOT make git commit

### Without notifications

```bash
python3 payment_tracker_agent.py --no-notify
```

- Performs the check
- Logs activities
- Skips Telegram notification

### Test notification

```bash
python3 payment_tracker_agent.py --force-notify
```

- Sends Telegram even if there are no issues
- For testing notification setup

## Output

### Telegram Notification

Sent to Saved Messages ('me'):

```
**Payment Tracker Report**

Total outstanding: **$4,827 USD**
2 overdue, 1 due soon, 0 pending invoice

🔴 **OVERDUE**

• **INV-095** - Enterprise Corp
  $XXX USD • 8 days overdue
  Action: Email Alice

🟡 **DUE SOON**

• **INV-096** - Client D
  $X,XXX USD • Due 2026-02-15 (5 days since invoice)

✅ **OK** (3 invoices on track)
```

### Follow-up Drafts

File: `$AGENTS_PATH/data/payment_followups/YYYY-MM-DD_followup_drafts.md`

Contains ready-made email drafts for overdue invoices.

### Activities Log

Entries in `sales/crm/activities.csv`:
- activity_id: `act-XXX`
- type: `note`
- subject: `Payment tracker: Invoice #INV-095 - OVERDUE`
- created_by: `payment-tracker-agent`

### Agent Log

JSON file: `$AGENTS_PATH/data/payment_tracker_log.json`

```json
{
  "ts": "2026-02-12T10:00:00",
  "outstanding_total": 4827,
  "overdue_count": 2,
  "due_soon_count": 1,
  "pending_invoice_count": 0,
  "notifications_sent": true,
  "errors": []
}
```

## Scheduled Run

The agent runs automatically via launchd:
- **Schedule**: Daily at 10:00 AM (Mon-Fri)
- **Plist**: `~/Library/LaunchAgents/com.yourcompany.payment-tracker.plist`

### Load schedule

```bash
cp $AGENTS_PATH/payment-tracker/com.yourcompany.payment-tracker.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.yourcompany.payment-tracker.plist
```

### Unload schedule

```bash
launchctl unload ~/Library/LaunchAgents/com.yourcompany.payment-tracker.plist
```

### Check status

```bash
launchctl list | grep payment-tracker
```

### View logs

```bash
tail -f /tmp/payment-tracker-agent.log
tail -f /tmp/payment-tracker-agent-error.log
```

## Payment Terms

- **Known clients** (status=active): 7 days
- **New clients** (status=new): 14 days
- **DUE_SOON warning**: 3 days before deadline
- **Follow-up cadence**:
  - DUE_SOON: reminder every 3 days
  - OVERDUE: daily reminders

## Payment Categories

1. **OK**: Invoice on track (days <= payment_terms - 3)
2. **DUE_SOON**: Approaching deadline (payment_terms - 3 < days <= payment_terms)
3. **OVERDUE**: Missed deadline (days > payment_terms)
4. **PENDING_INVOICE**: Deal delivered but invoice not sent yet

## Troubleshooting

### Telegram not sending

```bash
# Test Telegram connection
cd $TG_TOOLS_PATH
python3 -c "from tg_utils.auth import get_client; import asyncio; asyncio.run(get_client())"

# Force notification
cd $AGENTS_PATH/payment-tracker
python3 payment_tracker_agent.py --force-notify
```

### Activities not logging

```bash
# Check CSV permissions
ls -la $CRM_PATH/activities.csv

# Check git status
cd $PROJECT_ROOT
git status

# Dry-run to see what would be logged
cd $AGENTS_PATH/payment-tracker
python3 payment_tracker_agent.py --dry-run
```

### Wrong payment terms

Edit constants in `payment_tracker_agent.py`:
```python
DEFAULT_PAYMENT_TERMS_KNOWN = 7
DEFAULT_PAYMENT_TERMS_NEW = 14
DUE_SOON_BUFFER_DAYS = 3
```

## Integration

### Upstream
- **Invoice Generator** (#17): creates invoice_date, invoice_number in deals.csv
- **Manual bank check**: owner updates paid_date when payment is received

### Downstream
- **Daily Briefing** (#14): can include payment tracker summary
- **Activity Logging** (#13): shares activities.csv

## Human Approval

- Agent does NOT send emails automatically
- Generates drafts for review
- Owner decides when and how to send follow-ups

## Rollback

### Stop agent
```bash
launchctl unload ~/Library/LaunchAgents/com.yourcompany.payment-tracker.plist
```

### Revert activity logs
```bash
cd $PROJECT_ROOT
git log --grep="payment tracker"
git revert <commit-hash>
```

### Clear agent log
```bash
rm $AGENTS_PATH/data/payment_tracker_log.json
```

## Related skills

- `invoice` - invoice creation (process #17)
- `log-activity` - manual CRM activity logging
- `daily-briefing` - morning briefing (process #14)

## Owner

Your Name (your@email.com)
Process ID: #18
