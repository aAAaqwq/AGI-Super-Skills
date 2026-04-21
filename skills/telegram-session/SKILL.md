---
name: telegram-session
description: Create/update Telethon session
---
# Infra Telegram Session

> Managing Telegram session via tg-auth

## When to use

- "telegram is not working"
- "SessionExpiredError" / "AuthKeyUnregisteredError"
- "check telegram session"
- First launch on a new device

## Tool

`$TG_TOOLS_PATH/tools/tg_auth.py`

## How to execute

### Check session

```bash
python3 $TG_TOOLS_PATH/tools/tg_auth.py check
```

Shows: name, username, phone + last 10 chats.

### QR Login (new session)

```bash
# QR + wait for scan (2 min timeout)
python3 $TG_TOOLS_PATH/tools/tg_auth.py qr

# Only show QR (without waiting)
python3 $TG_TOOLS_PATH/tools/tg_auth.py qr --no-wait
```

On phone: Settings > Devices > Link Desktop Device > scan QR.

### List sessions

```bash
python3 $TG_TOOLS_PATH/tools/tg_auth.py sessions
```

Shows all `.session` files in the sessions directory.

### Custom session

```bash
python3 $TG_TOOLS_PATH/tools/tg_auth.py --session /path/to/session check
```

## Paths

| What | Path |
|------|------|
| Default session | `$SALES_PATH/telegram/sessions/telegram_session.session` |
| ENV | `$SALES_PATH/.env` |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| SessionExpiredError | `tg-auth qr` -- create a new session |
| AuthKeyUnregisteredError | `tg-auth qr` -- re-login |
| "Not authorized" | `tg-auth qr` |
| FloodWaitError | Wait the specified time |
| QR timeout | Run `tg-auth qr` again |

## Related skills

- `telegram-send` -- sending messages
- `telegram-check` -- checking replies
