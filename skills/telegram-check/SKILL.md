---
name: telegram-check
description: Check inbound Telegram messages
---
# Telegram Check

> Check inbound messages/replies via tg-tools

## When to use

- "check telegram"
- "who replied on telegram"
- "any new messages?"
- After a campaign -- check replies

## Dependencies

- `$TG_TOOLS_PATH/` (tg-contacts, tg-scrape)
- Active Telegram session

## How to run

### Check a specific contact

```bash
python3 $TG_TOOLS_PATH/tools/tg_contacts.py lookup @username
python3 $TG_TOOLS_PATH/tools/tg_contacts.py lookup +380671234567
```

Shows: name, username, phone, ID + last 5 messages.

### Check messages in a group/channel

```bash
python3 $TG_TOOLS_PATH/tools/tg_scrape.py messages "Group Name" --limit 20
python3 $TG_TOOLS_PATH/tools/tg_scrape.py messages "Group Name" --days 7
```

### Export all contacts with messages

```bash
python3 $TG_TOOLS_PATH/tools/tg_contacts.py export --output contacts.json --messages 5
```

JSON with last messages for each contact.

## Typical responses (patterns)

| Pattern | Status |
|---------|--------|
| "yes", "can do", "will be there" | `responded` + `hot` |
| "no", "can't" | `responded` + `declined` |
| "when?", "details?" | `responded` + `interested` |
| No response | `no_response` |

## Related skills

- `telegram-send` -- sending messages
- `telegram-session` -- if session is broken
- `update-lead` -- update status in CRM after checking
