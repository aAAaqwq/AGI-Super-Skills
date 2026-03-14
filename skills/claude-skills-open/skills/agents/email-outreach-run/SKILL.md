---
name: email-outreach-run
description: Automatic email outreach agent run
---
# Email Outreach Agent - Run Skill

> Send mass email campaigns with personalization and approval workflow

## When to use

- User wants to send email outreach campaign
- "send emails to [segment]"
- "email outreach to new leads"
- "send training reminder to participants"

## Prerequisites

1. Gmail API authenticated (`google-auth` skill if needed)
2. CRM data available (`sales/crm/`)
3. Template or AI mode

## How to execute

### Step 1: Determine campaign type

**CRM Segment Mode**:
```bash
cd $AGENTS_PATH/email-outreach

python3 email-outreach_agent.py \
  --segment "stage=new AND product_id=prod-labeling" \
  --template templates/cold_outreach.txt
```

**Manual CSV Mode**:
```bash
python3 email-outreach_agent.py \
  --recipients /path/to/recipients.csv \
  --template templates/training_reminder.txt
```

**AI-Generated Mode**:
```bash
python3 email-outreach_agent.py \
  --segment "stage=qualified" \
  --ai-mode \
  --subject "Following up on our conversation"
```

### Step 2: Always dry-run first

```bash
python3 email-outreach_agent.py \
  --segment "..." \
  --template templates/cold_outreach.txt \
  --dry-run
```

### Step 3: Review approval prompt

Agent shows:
- Number of recipients
- Subject line
- First 3 sample emails

Options:
- `[A]` - Approve and send
- `[T]` - Send test to your@email.com
- `[C]` - Cancel (save draft)

### Step 4: Check results

```bash
# Summary
ls -lh $GOOGLE_TOOLS_PATH/data/email_outreach_summaries/

# Agent log
cat $GOOGLE_TOOLS_PATH/data/email_outreach_log.json | jq '.[-1]'

# CRM activities
tail -10 $CRM_PATH/activities.csv
```

## Templates

Available templates in `agents/email-outreach/templates/`:
- `cold_outreach.txt` - For new leads
- `follow_up.txt` - Follow-up to previous contact
- `training_reminder.txt` - Event/training reminders

**Placeholders**:
- `{name}` - Full name
- `{first_name}` - First name
- `{last_name}` - Last name
- `{company}` / `{company_name}` - Company name
- `{role}` - Job role

## Segment Queries

Filter CRM leads:

```bash
# New leads for specific product
--segment "stage=new AND product_id=prod-labeling"

# Qualified leads
--segment "stage=qualified"

# Custom filters
--segment "stage=new AND product_id=prod-training"
```

## Rate Limits (OWNER DECISIONS)

- **Max**: 50 emails/day
- **Rate**: 1-2 sec between emails
- **Cooldown**: 7 days (same person+product)

## Error Handling

| Error | Action |
|-------|--------|
| "Gmail credentials not found" | Run `google-auth` skill |
| "Daily limit reached" | Wait until tomorrow |
| "No recipients match" | Check segment query, verify CRM data |
| "Invalid email" | Check CSV, emails will be skipped |

## Manual CSV Format

```csv
email,first_name,last_name,company_name
john@example.com,John,Doe,Example Corp
jane@test.com,Jane,Smith,Test Inc
```

Required: `email`
Optional: `first_name`, `last_name`, `company_name`, `person_id`, `product_id`

## Common Use Cases

### Use Case 1: Cold outreach to new leads

```bash
python3 email-outreach_agent.py \
  --segment "stage=new AND product_id=prod-labeling" \
  --template templates/cold_outreach.txt \
  --campaign-name "Q1 Cold Outreach - Labeling"
```

### Use Case 2: Training reminder (manual list)

```bash
# Create CSV with participants
cat > participants.csv << 'EOF'
email,first_name
john@example.com,John
jane@test.com,Jane
EOF

python3 email-outreach_agent.py \
  --recipients participants.csv \
  --template templates/training_reminder.txt
```

### Use Case 3: AI-generated follow-up

```bash
python3 email-outreach_agent.py \
  --segment "stage=qualified" \
  --ai-mode \
  --subject "Following up on data labeling project"
```

## Testing

```bash
# Run unit tests
cd $AGENTS_PATH/email-outreach
python3 test_email_outreach.py

# Dry-run test
python3 email-outreach_agent.py \
  --recipients test_data/test_recipients.csv \
  --template test_data/test_template.txt \
  --dry-run
```

## Output

- **Summary**: `google-tools/data/email_outreach_summaries/YYYY-MM-DD.md`
- **Log**: `google-tools/data/email_outreach_log.json`
- **Activities**: `sales/crm/activities.csv` (appended)
- **Drafts** (on cancel): `google-tools/data/email_outreach_drafts/`

## Integration with other skills

- **Before**: `google-auth` (if Gmail auth needed)
- **After**: Monitor responses via email-agent
- **Future**: `change-review` for CRM updates

## Troubleshooting

### Test send not arriving
```bash
# Check Gmail API
python3 -c "from google.oauth2.credentials import Credentials; print(Credentials.from_authorized_user_file('$GOOGLE_TOOLS_PATH/token.json'))"

# Re-auth if needed
# Run google-auth skill
```

### Template placeholders not being filled
```bash
# Check CSV has the required columns
head -1 recipients.csv

# Placeholders case-sensitive: {name} not {Name}
```

### Daily limit reached
```bash
# Check send log
cat $GOOGLE_TOOLS_PATH/data/email_send_log.json | jq '[.[] | select(.date == "2026-02-12")] | length'

# Wait until tomorrow or increase limit in config.json
```

## Owner Decisions Applied

✅ Human approval required for ALL outreach
✅ Rate limit: 50/day max
✅ Logs to CRM activities
✅ Dry-run flag mandatory for testing
✅ Uses `claude -p --model haiku` (not API key)
✅ Idempotent (re-run safe)

## Related Files

- Agent: `$AGENTS_PATH/email-outreach/email-outreach_agent.py`
- Config: `$AGENTS_PATH/email-outreach/config.json`
- Templates: `$AGENTS_PATH/email-outreach/templates/`
- Spec: `$AGENTS_PATH/specs/email-outreach.spec.md`

## Related skills

- `google-auth` - Gmail API auth
- `telegram-send` - Parallel outreach channel
- `add-lead` - Add new contacts
- `log-activity` - Manual activity logging
