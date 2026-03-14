---
name: telegram-send
description: Telegram DM sending from CSV, rate limiting, idempotency
---
# Telegram Send

> Sending messages via Telegram (Telethon) with CSV input

## When to use

- "send via telegram"
- "message everyone through telegram"
- "telegram campaign"
- When `preferred_channel = Telegram` in data

## Dependencies

- Python 3, Telethon, python-dotenv
- Active Telegram session

## Paths

| What | Path |
|------|------|
| Tool | `$TG_TOOLS_PATH/tools/tg_send.py` |
| Shared lib | `$TG_TOOLS_PATH/tg_utils/` |
| Telegram Session | `$SALES_PATH/telegram/sessions/telegram_session.session` |
| ENV | `$SALES_PATH/.env` |
| Send Log | `$TG_TOOLS_PATH/data/send_log.json` |

## How to run

### Step 1: Prepare CSV

Claude prepares CSV with recipients. Minimum columns:

```csv
key,name,phone,username,message
p-001,Alice,+380XXXXXXXXX,,Hello Alice! Message text.
p-002,Ruslan,,,Nizami_ua,Hello Ruslan!
```

Or without the `message` column -- then use the `--message` template.

### Step 2: Dry-run (verification)

```bash
python3 $TG_TOOLS_PATH/tools/tg_send.py \
    --input contacts.csv --dry-run
```

Or with a template:
```bash
python3 $TG_TOOLS_PATH/tools/tg_send.py \
    --input contacts.csv --message "Hello, {name}! Text." --dry-run
```

### Step 3: Send

```bash
python3 $TG_TOOLS_PATH/tools/tg_send.py \
    --input contacts.csv --send

# Or test on the first contact:
python3 $TG_TOOLS_PATH/tools/tg_send.py \
    --input contacts.csv --send --test 1
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--input FILE` | CSV file (or `-` for stdin) | required |
| `--message TMPL` | Message template with `{name}` | - |
| `--message-file FILE` | Template from file | - |
| `--dry-run` | Preview only | true (default) |
| `--send` | Actual sending | false |
| `--test N` | Send only to first N | - |
| `--max N` | Max number of messages | - |
| `--cold` | Limits for cold outreach (5/day, batch pauses) | false |
| `--delay MIN MAX` | Override delay (sec) | 20 60 |
| `--status` | Show send log | - |
| `--reset-log` | Reset log | - |
| `--reset-cooldown` | Reset flood cooldown | - |
| `--key-col NAME` | Column for idempotency | key |
| `--name-col NAME` | Column for name | name |
| `--phone-col NAME` | Column for phone | phone |
| `--user-col NAME` | Column for username | username |
| `--msg-col NAME` | Column for message | message |

## Architecture

**Claude (LLM) is responsible for:** selecting recipients, composing text, generating CSV, interpreting results, updating CRM.

**tg-send is responsible for:** Telegram session, phone normalization, message delivery, rate limiting, idempotency, flood handling.

### Shared library (`tg_utils/`)

| Module | Purpose |
|--------|---------|
| `auth.py` | Connecting to Telegram, loading credentials |
| `phone.py` | Phone normalization (UA/PL/IE/US) |
| `rate_limit.py` | Delays, batch pauses, flood cooldown |
| `send_log.py` | Send log (idempotency) |
| `contacts.py` | Entity resolution (username/phone), ImportContactsRequest |
| `output.py` | JSON-line output for composition |

## Rate Limiting

| Mode | Delay | Limit/day | Batch pause |
|------|-------|-----------|-------------|
| Warm (default) | 20-60s | 35 | - |
| Cold (`--cold`) | 30-60s | 5 | 30min every 3 |

## Output

Stdout: JSON lines (for pipe/composition):
```json
{"event":"send","status":"ok","key":"p-001","target":"@user","name":"Alice","ts":"..."}
{"event":"summary","sent":5,"failed":1,"skipped":2,"ts":"..."}
```

Stderr: human-readable progress.

## Limitations

- Not all phone numbers are registered on Telegram
- Privacy settings can block (UserPrivacyRestrictedError)
- FloodWaitError = 24h cooldown, PeerFloodError = 48h cooldown
- Temporary contacts are automatically removed after sending

## Troubleshooting

| Problem | Solution |
|---------|----------|
| FloodWaitError | Automatic 24h cooldown. `--reset-cooldown` to reset |
| PeerFloodError | 48h cooldown. Wait or `--reset-cooldown` |
| SessionExpired | `telegram-session` |
| UserPrivacyRestrictedError | Person has blocked DMs |
| "Not authorized" | Need QR login via `tg-auth` |

## Related skills

- `telegram-check` -- checking replies
- `telegram-session` -- if session is broken
- `email-send-direct` -- single email
- `email-send-bulk` -- mass email sending
- `whatsapp-send` -- alternative channel

## Related tools

All Telegram tools: `$TG_TOOLS_PATH/tools/`
- `tg-auth` -- session, QR login
- `tg-contacts` -- export/import contacts, lookup
- `tg-groups` -- groups, posting, members
- `tg-scrape` -- channel search, scraping
