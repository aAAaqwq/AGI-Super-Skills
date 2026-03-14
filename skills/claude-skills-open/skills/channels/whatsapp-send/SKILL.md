---
name: whatsapp-send
description: Baileys WhatsApp message sending
---
# WhatsApp Send

> Sending messages via WhatsApp Web (Baileys)

## When to use

- "send via whatsapp"
- "write through whatsapp"
- When `preferred_channel = WhatsApp` in data

## Dependencies

- Node.js, @whiskeysockets/baileys
- Active WhatsApp Web session

## Paths

| What | Path |
|------|------|
| Script | `$SALES_PATH/whatsapp/send_whatsapp.js` |
| Session | `$SALES_PATH/whatsapp/baileys_session/` |
| Check chats | `$SALES_PATH/whatsapp/check_chats.js` |

## How to run

```bash
cd $SALES_PATH/whatsapp
node send_whatsapp.js
```

## Recipient configuration

Recipients are hardcoded in the script (`RECIPIENTS` array):

```javascript
const RECIPIENTS = [
    { phone: '380XXXXXXXXX', name: 'Bob', row: 3 },
    { phone: '380YYYYYYYYY', name: 'Carol', row: 4 },
    // ...
];
```

To change -- edit the array in the script.

## Message template

```javascript
const MESSAGE_TEMPLATE = (name) => `Hello, ${name}! This is Ivan from WeLabelData.
...
`;
```

## How it works

1. Connects via Baileys
2. Checks if the number is on WhatsApp (`onWhatsApp`)
3. If yes -- sends a personalized message
4. **60 sec delay** between messages

## Check chats

```bash
node check_chats.js
```

Shows recent chats, but **NOT the full history**.

## Limitations (IMPORTANT!)

- **Baileys does NOT sync message history**
- New incoming messages are visible only in real time
- To check replies -- look at WhatsApp on the phone
- Active session required (QR code on first launch)
- WhatsApp may ban for aggressive sending

## Creating a new session

If the session is stale:

```bash
cd $SALES_PATH/whatsapp
rm -rf baileys_session
node index.js    # will show QR code
# Scan QR from the phone
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Connection closed | Restart, rescan QR |
| Logged out | Delete session, create a new one |
| Number not on WhatsApp | Try another channel (Telegram/Email) |
| Ban/Restrict | Reduce frequency, change number |

## Related skills

- `telegram-send` -- alternative channel
- `email-send-direct` -- single email
- `email-send-bulk` -- mass email sending
