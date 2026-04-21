---
name: email-read
description: Read inbox and sent via Gmail API
---
# Email Read

> Read emails from Gmail inbox, sent folder, or any label via Gmail API

## When to use

- "check my email"
- "what's in my inbox"
- "read emails"
- "any new messages?"
- "check sent emails" / "did I send that email?"
- "verify email was sent"
- Morning briefing

## Paths

| What | Path |
|------|------|
| Script | `$GOOGLE_TOOLS_PATH/read_emails.py` |
| Token | `$GOOGLE_TOOLS_PATH/token.json` |

## How to run

```bash
cd $GOOGLE_TOOLS_PATH

# Last 10 unread emails (default)
.venv/bin/python3 read_emails.py

# Last N unread emails
.venv/bin/python3 read_emails.py 20

# All emails (read + unread)
.venv/bin/python3 read_emails.py 10 all

# Custom query
.venv/bin/python3 read_emails.py 5 "from:client@example.com"
.venv/bin/python3 read_emails.py 10 "is:unread subject:invoice"
.venv/bin/python3 read_emails.py 5 "after:2026/02/01"

# SENT emails
.venv/bin/python3 read_emails.py 5 "in:sent"
.venv/bin/python3 read_emails.py 3 "in:sent to:alice@clientc.example.com"
.venv/bin/python3 read_emails.py 5 "in:sent after:2026/02/20"
.venv/bin/python3 read_emails.py 5 "in:sent subject:invoice"
```

## Query examples

| Query | Description |
|-------|-------------|
| `is:unread` | Only unread (default) |
| `all` | All messages |
| `from:team@yourcompany.com` | From specific person |
| `subject:invoice` | By subject |
| `after:2026/02/01` | After date |
| `is:starred` | Starred messages |
| `has:attachment` | With attachments |
| `label:important` | By label |
| `in:sent` | Sent emails |
| `in:sent to:user@example.com` | Sent to specific person |
| `in:sent after:2026/02/20` | Recently sent |
| `in:drafts` | Draft emails |

**Important:** When using `in:sent`, `in:drafts`, or `label:` queries, the script automatically removes the INBOX filter so results from other folders are returned correctly.

## Full thread rule

**IMPORTANT:** When checking email about a specific person, company, or topic -- ALWAYS read the full thread (both inbox and sent). Otherwise you only see half the conversation.

```bash
# CORRECT: full thread with a person
.venv/bin/python3 read_emails.py 10 "from:client@example.com after:2026/02/01"
.venv/bin/python3 read_emails.py 10 "in:sent to:client@example.com after:2026/02/01"

# OR in one query (both sides):
.venv/bin/python3 read_emails.py 20 "{from:client@example.com OR to:client@example.com} after:2026/02/01"
```

**When to apply:**
- "any updates from X?" -- read both sides
- "did they reply to the invoice?" -- read both sent and inbox
- Follow-up checks -- always full thread
- If you only see inbox -- you don't know what we already sent

**When NOT needed:**
- "show inbox" / "check email" -- just inbox
- Morning briefing -- only new incoming

## Output format

```
=== INBOX (N messages) ===        # or === SENT (N messages) ===

1. [NEW] Subject line
   From: Sender Name <email@example.com>
   Date: 2026-02-05 10:30
   Preview: First 100 chars of message...

2. Subject line (no [NEW] = already read)
   ...
```

## OAuth scopes

Uses `gmail.readonly` scope from existing token.json.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| 401 Unauthorized | Refresh token: `google-auth` skill |
| No messages | Check query syntax |
| Token expired | Token auto-refreshes, but if fails run google-auth flow |

## Related skills

- `email-send-direct` - Send single email
- `email-send-bulk` - Mass email sending
- `daily-briefing` - Morning summary including inbox
- `google-auth` - Auth troubleshooting
