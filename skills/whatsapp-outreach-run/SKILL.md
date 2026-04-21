---
name: whatsapp-outreach-run
description: Automatic WhatsApp outreach agent run
---
# WhatsApp Outreach Agent - Run Skill

> Run the agent for mass WhatsApp message sending

## When to use

- "run WhatsApp outreach for X"
- "send WhatsApp messages for campaign Y"
- "build and run WhatsApp campaign"

## Before running

1. **Check WhatsApp session:**
   ```bash
   ls $SALES_PATH/whatsapp/baileys_session/
   ```
   If empty -> authenticate first:
   ```bash
   cd $SALES_PATH/whatsapp
   node index.js
   # Scan QR code
   ```

2. **Check setup:**
   ```bash
   cd $AGENTS_PATH/whatsapp-outreach
   python3 test_setup.py
   ```

## How to run

### Step 1: Create or select a campaign

If no campaign exists -- create a config:

```yaml
# $AGENTS_PATH/campaigns/my-campaign.yaml
campaign_name: "Campaign Name"

filters:
  company_id: ["comp-XXX"]      # Optional
  product_id: ["prod-XXX"]      # Optional
  stage: ["new", "qualified"]   # Optional
  preferred_channel: "whatsapp" # Optional

message_template: |
  Hi, {first_name}!

  This is Ivan from WeLabelData.

  Your message here...

variables:
  custom_var: "value"
```

### Step 2: Dry-run (mandatory!)

```bash
cd $AGENTS_PATH/whatsapp-outreach

python3 whatsapp_outreach_agent.py \
  --dry-run \
  --campaign campaigns/my-campaign.yaml
```

Check:
- Number of recipients
- Message personalization
- Filters are working correctly

### Step 3: Test with one recipient

```bash
python3 whatsapp_outreach_agent.py \
  --test-recipient p-XXX
```

Check:
- Message was sent
- Activity was logged
- Git branch was created

### Step 4: Small batch (3 people)

```bash
python3 whatsapp_outreach_agent.py \
  --limit 3 \
  --campaign campaigns/my-campaign.yaml
```

Check:
- 60 second delay is working
- All activities were logged
- Git branch is correct

### Step 5: Full run

```bash
python3 whatsapp_outreach_agent.py \
  --campaign campaigns/my-campaign.yaml
```

- Agent shows preview (first 3 messages)
- Agent asks for confirmation: `[y/N]`
- If `y` -> starts sending
- Progress: `[X/Y] Name → +phone... OK/FAIL`

### Step 6: Review and merge

```bash
cd $PROJECT_ROOT

# Check changes
git diff main

# If OK -> merge
git checkout main
git merge whatsapp-outreach-YYYY-MM-DD-HHMM

# If NOT OK -> delete branch
git branch -D whatsapp-outreach-YYYY-MM-DD-HHMM
```

## Flags

| Flag | Description |
|------|-------------|
| `--campaign FILE` | Path to campaign config (YAML) |
| `--dry-run` | Test run (no sending) |
| `--auto-approve` | Skip human approval (use with caution!) |
| `--test-recipient p-XXX` | Send to one person only |
| `--limit N` | Limit to N recipients |

## Environment Variables

```bash
# Delay between messages (seconds)
export WHATSAPP_DELAY_SECONDS=60

# Daily message limit
export WHATSAPP_DAILY_LIMIT=20

# Lookback for idempotency (days)
export IDEMPOTENCY_LOOKBACK_DAYS=7
```

## Output

### Logs

`$AGENTS_PATH/logs/whatsapp_outreach_YYYY-MM-DD_HH-MM.md`

### Git branch

`whatsapp-outreach-YYYY-MM-DD-HHMM`

### CRM changes

- `sales/crm/activities.csv` — added activities
- `sales/crm/relationships/leads.csv` — updated last_contact_date
- `sales/crm/contacts/people.csv` — added notes (if failed)

## Troubleshooting

### "WhatsApp session expired"

```bash
cd $SALES_PATH/whatsapp
node index.js
# Scan QR code
```

### "FloodWait error"

- Increase `WHATSAPP_DELAY_SECONDS`
- Decrease `WHATSAPP_DAILY_LIMIT`
- Wait 24 hours

### "No recipients found"

- Check filters in campaign config
- Check CRM data (people.csv, leads.csv)
- Check phone numbers in people.csv

### Git branch not created

- Check if there were successful sends
- Check `git status` in $PROJECT_ROOT
- Possibly all sends failed

## Examples

### Client D training reminder

```bash
python3 whatsapp_outreach_agent.py \
  --campaign campaigns/clientd-training-reminder.yaml
```

### Quick test

```bash
python3 whatsapp_outreach_agent.py \
  --dry-run \
  --limit 1 \
  --campaign campaigns/example-whatsapp.yaml
```

## Related files

- **Spec:** `$AGENTS_PATH/specs/whatsapp-outreach.spec.md`
- **README:** `$AGENTS_PATH/whatsapp-outreach/README.md`
- **Implementation:** `$AGENTS_PATH/whatsapp-outreach/IMPLEMENTATION.md`

## Important

- **Always --dry-run first**
- **Never --auto-approve without testing**
- **Max 20 messages per day** (WhatsApp may ban)
- **Human approval required** (per owner decision)
- **Review git branch before merge**
