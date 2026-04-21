---
name: log-activity
description: Log activity to activities.csv
---
# CRM Log Activity

> Logging outreach activities (calls, messages, emails)

## When to use

- After any outreach
- "log what I wrote"
- "record a call"
- For effectiveness analytics

## Paths

| What | Path |
|------|------|
| Activities | `$CRM_PATH/activities.csv` |
| People | `$CRM_PATH/contacts/people.csv` |

## Schema

```csv
activity_id,linkedin_url,date,channel,activity_type,message_preview,result,response_quality,next_followup_date,audience_segment,hook_type,notes
```

## How to log

```python
import pandas as pd
from datetime import date, timedelta
import uuid

activities = pd.read_csv('$CRM_PATH/activities.csv')

new_activity = {
    'activity_id': f'act-{uuid.uuid4().hex[:8]}',
    'linkedin_url': 'https://linkedin.com/in/example',  # or email
    'date': str(date.today()),
    'channel': 'telegram',  # linkedin/email/twitter/telegram/whatsapp
    'activity_type': 'dm',  # dm/connect_request/followup/email/call/research
    'message_preview': 'Hi! This is Ivan from WeLabelData...',  # first 100 characters
    'result': 'sent',  # sent/replied/no_response/accepted/rejected
    'response_quality': '',  # positive/neutral/negative/meeting
    'next_followup_date': str(date.today() + timedelta(days=7)),
    'audience_segment': 'training_course',
    'hook_type': 'course_invitation',
    'notes': ''
}

activities = pd.concat([activities, pd.DataFrame([new_activity])], ignore_index=True)
activities.to_csv('$CRM_PATH/activities.csv', index=False)
```

## After logging -- update the person

```python
people = pd.read_csv('$CRM_PATH/contacts/people.csv')

mask = people['linkedin_url'] == 'https://linkedin.com/in/example'
people.loc[mask, 'status'] = 'contacted'
people.loc[mask, 'last_contact_date'] = str(date.today())
people.loc[mask, 'next_followup_date'] = str(date.today() + timedelta(days=7))
people.loc[mask, 'last_updated'] = str(date.today())

people.to_csv('$CRM_PATH/contacts/people.csv', index=False)
```

## Channels (channel)

- `linkedin` -- LinkedIn DM
- `email` -- Email
- `telegram` -- Telegram
- `whatsapp` -- WhatsApp
- `twitter` -- Twitter/X

## Activity types (activity_type)

- `dm` -- Direct message
- `connect_request` -- Connection request
- `followup` -- Follow-up contact
- `email` -- Email message
- `call` -- Phone call
- `research` -- Research (not outreach)

## Results (result)

- `sent` -- Sent, waiting for response
- `replied` -- Received a response
- `no_response` -- No response (after N days)
- `accepted` -- Accepted request/invitation
- `rejected` -- Declined

## Response quality (response_quality)

- `positive` -- Interested
- `neutral` -- Neither yes nor no
- `negative` -- Not interested
- `meeting` -- Meeting scheduled

## Batch logging

For mass outreach -- log multiple at once:

```python
sent_to = ['email1@test.com', 'email2@test.com', 'email3@test.com']

for email in sent_to:
    new_activity = {
        'activity_id': f'act-{uuid.uuid4().hex[:8]}',
        'linkedin_url': email,  # using email as ID
        'date': str(date.today()),
        'channel': 'telegram',
        'activity_type': 'dm',
        'result': 'sent',
        # ...
    }
    activities = pd.concat([activities, pd.DataFrame([new_activity])], ignore_index=True)
```

## Related skills

- `telegram-send` -- before logging
- `update-lead` -- update person status
