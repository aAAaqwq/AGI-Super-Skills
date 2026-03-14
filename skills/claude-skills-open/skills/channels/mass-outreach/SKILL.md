---
name: mass-outreach
description: Multi-channel outreach via Telegram/Email/WhatsApp
---
# Mass Outreach Skill

> Mass message sending via Telegram, Email, WhatsApp with lessons learned from previous mistakes.

## Lessons Learned (Mistakes NOT to repeat)

### 1. Verify data BEFORE sending

**Mistake:** Asked people to write an intro who had already done so.
- @oleksii_badika - had written an intro, was asked again
- @Geddare (Yaroslava Bahriy) - had written an intro, was asked again

**Solution:**
```
ALWAYS check via Telegram API who has already posted in the "Introduction" topic
DO NOT rely on old CSV data
```

### 2. Verify group membership

**Mistake:** Marked a person as "IN GROUP" when they were not in the group.
- @danylchenko - marked as in group, actually was not

**Solution:**
```
ALWAYS verify membership via client.get_participants(group)
DO NOT rely on notes in CRM
```

### 3. Verify dates

**Mistake:** Wrong dates in the message (Sunday 9, Monday 10 instead of 8 and 9).
- @KR0Ler and @alexpazhyn received incorrect dates

**Solution:**
```python
from datetime import datetime, timedelta

today = datetime.now()
# Find the nearest Sunday
days_until_sunday = (6 - today.weekday()) % 7
if days_until_sunday == 0:
    days_until_sunday = 7
next_sunday = today + timedelta(days=days_until_sunday)
next_monday = next_sunday + timedelta(days=1)

print(f"Sunday: {next_sunday.strftime('%d.%m')}")
print(f"Monday: {next_monday.strftime('%d.%m')}")
```

### 4. Check who has already been contacted

**Mistake:** Did not check sent message history before the campaign.

**Solution:**
```
ALWAYS before sending:
1. Get the list of all potential recipients
2. Check outgoing messages for the last N days
3. Exclude those who have already been contacted
4. Show to the user for confirmation
```

### 5. Rate Limiting

**Rules for Telegram:**
- Minimum 45-60 seconds between messages
- No more than 30-50 messages per day
- If FloodWait -- stop and wait

**Rules for Email:**
- Batch of 10-20 emails
- 5-10 second delay between emails
- No more than 100 per day

## Pre-send checklist

```
[ ] 1. Dates verified (day of week = date)
[ ] 2. Recipient list verified via API
[ ] 3. Checked who has already received messages
[ ] 4. Checked who has written an intro (if relevant)
[ ] 5. Template shown to user and approved
[ ] 6. Rate limits configured
[ ] 7. There is a plan in case of error
```

## Execution template

```python
# 1. Data verification
def verify_recipients(group_name, check_intro=True):
    # Get all group participants
    participants = client.get_participants(group)

    # If needed -- check who has written an intro
    if check_intro:
        intro_messages = client.get_messages(group, limit=2000)
        intro_authors = extract_intro_authors(intro_messages)

    # Check who has already been contacted
    already_sent = check_sent_messages(participants, days=3)

    return {
        'all': participants,
        'with_intro': intro_authors if check_intro else [],
        'already_sent': already_sent,
        'to_send': [p for p in participants if p not in already_sent]
    }

# 2. Sending with rate limiting
def send_with_delay(recipients, message_template, delay=45):
    for i, recipient in enumerate(recipients):
        try:
            message = personalize(message_template, recipient)
            client.send_message(recipient, message)
            print(f"✓ {i+1}/{len(recipients)} - sent")

            if i < len(recipients) - 1:
                time.sleep(delay)

        except FloodWaitError as e:
            print(f"FloodWait: sleeping {e.seconds}s")
            time.sleep(e.seconds)
        except Exception as e:
            print(f"✗ Error: {e}")
            log_error(recipient, e)
```

## After sending

1. Log in activities.csv
2. Update statuses in CRM
3. Commit via change-review
4. Create a follow-up task

## Paths

| What | Path |
|------|------|
| Telegram sessions | `$SALES_PATH/telegram/sessions/` |
| CRM contacts | `$CRM_PATH/contacts/` |
| Activities | `$CRM_PATH/activities.csv` |
| Communities | `$CRM_PATH/communities/` |
