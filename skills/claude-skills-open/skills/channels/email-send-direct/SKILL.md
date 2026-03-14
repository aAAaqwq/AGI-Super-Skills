---
name: email-send-direct
description: Single email: dry-run, reply, attachments
---
# Email Send Direct

> Send a single email via Gmail API from CLI

## When to use

- "write an email to X"
- "send email to Y"
- "reply to the email"
- Any single email sending (not mass campaign)

## IMPORTANT: Confirmation rule

**ALWAYS first --dry-run, show preview to the user, and only after "yes" send without --dry-run.**

## Composing Guidelines

**Before writing a single word:**

1. **Read the full thread** — inbox AND sent, not just the latest message. Use `email-read` skill to pull last 3-5 days of correspondence with this contact.
2. **Check CRM** — read `leads.csv` and `people.csv` for context: deal stage, last activity, relationship notes. The email must reflect where we actually are, not where we were a week ago.
3. **Identify what they asked** — list every question or request from their last message. Each one must be answered.

**Writing rules:**

- **Answer their questions first.** Don't open with pleasantries or context-setting. If they asked "can you invoice monthly?" — start with "Yes, we'll submit monthly invoices."
- **Match the thread tone.** If the conversation is casual ("Hey Ivan"), reply casual. If formal ("Dear Mr. Pasichnyk"), reply formal. Mirror their level.
- **No bot language.** Never write: "Please find attached", "I hope this email finds you well", "As per our conversation", "Don't hesitate to reach out". Write like a human.
- **No unnecessary bullet points or formatting.** Business emails are paragraphs. Use bullets only when listing 3+ distinct items that genuinely benefit from a list.
- **Reference shared context.** Use "as discussed", "as you mentioned", "following up on our call" — shows you're in the conversation, not generating from a template.
- **Keep it short.** 3-5 sentences for a reply. 2-3 short paragraphs max for a proposal email. If you need more, the content belongs in an attachment.
- **One clear call-to-action.** End with exactly one thing you want them to do: review, sign, reply, schedule.

**Ivan's voice:**

- Short, concrete, direct
- Professional but warm — not stiff, not overly casual
- Says "we" for company actions, "I" for personal commitments
- Signs off: "Best," or "Thanks," — never "Best regards," or "Sincerely,"
- First email in thread: "Hi [Name]," — replies: often no greeting, just jumps in

**Anti-patterns (never do these):**

| Bad | Why | Instead |
|-----|-----|---------|
| "Please find attached the proposal" | Corporate robot | "Proposal is attached" or "Attached is the proposal we discussed" |
| Bullet-point summary of what's attached | They can read it themselves | One sentence saying what it is |
| Repeating info they already know | Wastes their time | Reference it briefly, move forward |
| "Let me know if you have any questions" | Empty filler | Specific CTA: "Let me know if the terms work" |
| Long intro before answering their question | Buries the answer | Answer first, context after |

## Paths

| What | Path |
|------|------|
| Script | `$GOOGLE_TOOLS_PATH/send_email.py` |
| Token | `$GOOGLE_TOOLS_PATH/token.json` |
| venv | `$GOOGLE_TOOLS_PATH/.venv/bin/python3` |

## How to run

### Simple email

```bash
cd $GOOGLE_TOOLS_PATH
.venv/bin/python3 send_email.py \
    --to user@example.com \
    --subject "Subject" \
    --body "Message text" \
    --dry-run
```

### With CC

```bash
.venv/bin/python3 send_email.py \
    --to user@example.com \
    --cc other@example.com \
    --cc another@example.com \
    --subject "Subject" \
    --body "Message" \
    --dry-run
```

### With attachment

```bash
.venv/bin/python3 send_email.py \
    --to user@example.com \
    --subject "NDA attached" \
    --body "Please find attached." \
    --attach /path/to/file.pdf \
    --attach /path/to/another.pdf \
    --dry-run
```

### Reply in thread (search by query)

```bash
.venv/bin/python3 send_email.py \
    --to user@example.com \
    --subject "Re: Original Subject" \
    --body "Reply text" \
    --reply-to 'from:user@example.com subject:"Original Subject"' \
    --dry-run
```

### Reply in thread (by message ID)

```bash
.venv/bin/python3 send_email.py \
    --to user@example.com \
    --subject "Re: Original Subject" \
    --body "Reply text" \
    --reply-to-id MESSAGE_ID \
    --dry-run
```

### Body from file

```bash
.venv/bin/python3 send_email.py \
    --to user@example.com \
    --subject "Subject" \
    --body-file /path/to/message.txt \
    --dry-run
```

## Parameters

| Parameter | Description | Required |
|-----------|-------------|----------|
| `--to EMAIL` | Recipient (can specify multiple) | yes |
| `--cc EMAIL` | CC (can specify multiple) | no |
| `--subject TEXT` | Email subject | yes |
| `--body TEXT` | Email body text | yes* |
| `--body-file FILE` | Body text from file | yes* |
| `--attach FILE` | Attachment (can specify multiple) | no |
| `--reply-to QUERY` | Gmail query for thread lookup | no |
| `--reply-to-id ID` | Gmail message ID for reply | no |
| `--dry-run` | Preview only, do not send | no |

*Either `--body` or `--body-file` is required.

## Workflow for Claude

```
1. Prepare the email text
2. Run with --dry-run
3. Show preview to the user
4. After confirmation -- run WITHOUT --dry-run
5. Script automatically verifies sending (labels, snippet)
```

## Output

### Dry-run
```
============================================================
  EMAIL PREVIEW
============================================================
  From:    Your Name <your@email.com>
  To:      user@example.com
  Cc:      other@example.com
  Subject: Re: Topic
  Thread:  abc123 (reply)
  Attach:  file.pdf (23,794 bytes)
------------------------------------------------------------
Message body here...
============================================================

[DRY RUN] Email not sent.
```

### After send
```
  Sent! Message ID: 19c90af2b9ceaf61

  Verify:  OK
  ID:      19c90af2b9ceaf61
  To:      user@example.com
  Cc:      other@example.com
  Subject: Re: Topic
  Labels:  ['SENT']
  Snippet: Message body here...
  Attach:  ['file.pdf']
```

## Sender

```
From: Your Name <your@email.com>
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| 401 Unauthorized | Refresh token: `google-auth` skill |
| Attachment not found | Check file path |
| Thread not found | Check --reply-to query |
| Encoding issues | Body is automatically UTF-8 |

## Related skills

- `email-send-bulk` -- mass sending via Google Sheets
- `email-read` -- reading email
- `email-monitor` -- automatic monitoring
- `google-auth` -- if authorization issues
