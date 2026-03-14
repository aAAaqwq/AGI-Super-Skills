---
name: email-send-bulk
description: Gmail API bulk email sending
---
# Email Send Bulk

> Bulk email sending via Gmail API from Google Sheets

## When to use

- "send email"
- "write an email"
- "email campaign"
- When `preferred_channel = Email` in data

## IMPORTANT: Confirmation rule

**ALWAYS show the email text (To, Subject, Body) and ask for user confirmation BEFORE sending.**
Never send an email without an explicit "yes" / "send it" from the user.

## Dependencies

- Python 3.12+ (venv: `$GOOGLE_TOOLS_PATH/.venv/bin/python3`)
- google-api-python-client, google-auth-oauthlib
- Google OAuth token with Gmail scope

## Paths

| What | Path |
|------|------|
| Script | `$GOOGLE_TOOLS_PATH/send_emails.py` |
| Token | `$GOOGLE_TOOLS_PATH/token.json` |
| Credentials | `$GOOGLE_TOOLS_PATH/credentials.json` |

## Spreadsheet Config

- **ID:** `YOUR_SPREADSHEET_ID`
- **Sheet:** `Form Responses (1)`

| Column | Index | Purpose |
|--------|-------|---------|
| B | 1 | Name |
| C | 2 | Email |
| T | 19 | Email Status |
| U | 20 | Email text |

## How to run

```bash
cd $GOOGLE_TOOLS_PATH
.venv/bin/python3 send_emails.py 5      # send 5 emails
.venv/bin/python3 send_emails.py 10     # send 10 emails
.venv/bin/python3 send_emails.py        # default 5
```

## How it works

1. Reads Google Sheet
2. Filters: `status != Sent` AND `email` is not empty AND `text` is not empty
3. Composes email from `Your Name <your@email.com>`
4. Sends via Gmail API
5. Updates status in column T
6. **1 sec delay** between emails

## Subject

Hardcoded in script:
```
Data labeling training from YourCompany Inc.
```

To change -- edit `SUBJECT` in the script.

## Statuses (column T)

- `Sent` -- success
- `Error: ...` -- error details

## Sender

```
From: Your Name <your@email.com>
```

## Limits

- Gmail limit: ~500 emails/day
- ~2000 emails/day for Google Workspace
- 1 sec delay (can be reduced)

## How to prepare email text

Text is taken from column U. Can be prepared via:

```python
# $GOOGLE_TOOLS_PATH/prepare_emails.py
# Generates personalized text for each recipient
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| 401 Unauthorized | Refresh token: `google-auth` |
| Daily limit exceeded | Wait 24 hours |
| Invalid email | Check format in spreadsheet |

## Related skills

- `telegram-send` -- alternative channel
- `google-auth` -- if authorization issues
- `update-lead` -- update status after campaign
