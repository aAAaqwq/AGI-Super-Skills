---
name: expense-tracker
description: Manage expense tracker bot — deploy, check expenses, export data, sync locally
---
# Expense Tracker

> Telegram bot for expense tracking. Send text or photo to bot, Claude Haiku parses it, stores in D1.

## When to use

- User asks about expenses, spending, budget
- User wants to deploy or update the expense bot
- User wants to see expense summary or export data
- User asks to sync expenses locally

## Dependencies

- External: Cloudflare Workers (wrangler), Node.js
- Services: Telegram Bot API, Claude API (Haiku), Cloudflare D1

## Paths

| What | Path |
|------|------|
| Project | `$HOME/expense-bot/` |
| Source | `$HOME/expense-bot/src/` |
| Schema | `$HOME/expense-bot/schema.sql` |
| Worker config | `$HOME/expense-bot/wrangler.toml` |
| Local export | `$DATA_PATH/personal/expenses_YYYY_MM.csv` |

## How to execute

### Deploy

```bash
cd ~/expense-bot && npx wrangler deploy
```

### Set webhook (after first deploy)

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook?url=https://expense-bot.<subdomain>.workers.dev/webhook"
```

### Apply schema

```bash
cd ~/expense-bot && npx wrangler d1 execute expense-db --file=schema.sql
```

### Check expenses via API

```bash
curl -H "Authorization: Bearer $TOKEN" "https://expense-bot.<subdomain>.workers.dev/api/summary?month=2026-03"
```

### Sync expenses locally

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "https://expense-bot.<subdomain>.workers.dev/api/export?month=2026-03" \
  > $DATA_PATH/personal/expenses_2026_03.csv
```

### Set secrets

```bash
cd ~/expense-bot
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put ANTHROPIC_API_KEY
npx wrangler secret put API_AUTH_TOKEN
npx wrangler secret put ALLOWED_USERS
```

## Setup (first time)

1. Create bot via @BotFather on Telegram
2. `cd ~/expense-bot && npx wrangler d1 create expense-db`
3. Update `database_id` in `wrangler.toml`
4. `npx wrangler d1 execute expense-db --file=schema.sql`
5. Set secrets (see above)
6. `npx wrangler deploy`
7. Set webhook (see above)

## Bot commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome + usage |
| `/today` | Today's expenses |
| `/week` | This week by category |
| `/month` | Monthly summary |
| `/budget` | Budget vs actual |
| `/setbudget food 200` | Set monthly budget |
| `/export` | Download CSV |
| `/delete 123` | Delete expense by ID |

## Architecture

```
Telegram -> CF Worker /webhook -> Claude Haiku (parse) -> D1 (store) -> TG reply
                                  /api/* (JSON/CSV export, auth by Bearer token)
```

## Cost

~$0.30/month (Claude Haiku API only, everything else is free tier)
