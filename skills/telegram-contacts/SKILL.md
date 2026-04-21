---
name: telegram-contacts
description: Export/import/lookup Telegram contacts
---
# Telegram Contacts

> Export, import, and lookup Telegram contacts

## When to use

- "export contacts from telegram"
- "find a contact in telegram"
- "import contacts to telegram"
- "who is this @username"
- "find by phone number"

## Tool

`$TG_TOOLS_PATH/tools/tg_contacts.py`

## How to run

### Export contacts

```bash
# CSV to stdout
python3 $TG_TOOLS_PATH/tools/tg_contacts.py export

# CSV to file
python3 $TG_TOOLS_PATH/tools/tg_contacts.py export --output contacts.csv

# JSON with last messages
python3 $TG_TOOLS_PATH/tools/tg_contacts.py export --output contacts.json --messages 50
```

CSV columns: user_id, username, first_name, last_name, phone.
JSON additionally: messages, last_message_date, messages_count.

### Lookup contact

```bash
# By username
python3 $TG_TOOLS_PATH/tools/tg_contacts.py lookup @username

# By phone number
python3 $TG_TOOLS_PATH/tools/tg_contacts.py lookup +380671234567
```

Shows: name, username, phone, ID + last 5 messages.
If the contact is not in the list -- temporarily adds and automatically removes after checking.

### Import contacts

```bash
python3 $TG_TOOLS_PATH/tools/tg_contacts.py import --input contacts.csv
```

CSV format: `first_name,last_name,phone`

## Limitations

- JSON export with messages can be slow (0.3 sec per contact)
- Progress is saved every 100 contacts
- Not all phone numbers are registered on Telegram

## Related skills

- `telegram-send` -- sending messages
- `telegram-check` -- checking replies
- `update-lead` -- update CRM after lookup
