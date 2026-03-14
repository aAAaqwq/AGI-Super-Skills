---
name: op0-altar
description: Create and manage self-rewarding meme coins on Solana via the OP0 Altar protocol. Deploy pump.fun tokens where holders automatically receive rewards in 129 payout token options every few BTC blocks.
version: 1.0.0
emoji: "\u2205"
metadata:
  openclaw:
    primaryEnv: OP0_API_KEY
    requires:
      env:
        - OP0_API_KEY
      anyBins:
        - curl
        - node
---

# OP0 Altar Protocol Skill

You can create and manage self-rewarding meme coins on Solana through the OP0 Altar protocol. Every token launched through this skill deploys on pump.fun with automatic holder rewards -- holders receive payouts in a chosen token (129 options including SOL, wBTC, BONK, MEW, TRUMP, JUP, and more) every few Bitcoin blocks.

## API Configuration

- **Base URL:** `https://api.op0.live/functions/v1/altar-api-public`
- **Auth Header:** `X-API-Key: <OP0_API_KEY>`
- **Method:** All requests are `POST` with `Content-Type: application/json`
- **Auth:** All endpoints require `X-API-Key` header except `generate-key` and `payout-tokens`

## Generating an API Key (Autonomous)

If `OP0_API_KEY` is not set, you can generate one autonomously. The user must provide their Solana wallet address.

```bash
curl -s -X POST https://api.op0.live/functions/v1/altar-api-public \
  -H "Content-Type: application/json" \
  -d '{"action":"generate-key","wallet":"USER_WALLET_ADDRESS","label":"OpenClaw Agent"}'
```

Response contains `api_key` (format: `op0_live_` + 64 hex chars). Save it immediately -- it cannot be retrieved again. Tell the user to add it to their OpenClaw config:

```
openclaw config set mcpServers.op0.env.OP0_API_KEY "op0_live_..."
```

Or store it in their environment for this skill to use.

## Available Actions

### 1. Create an Altar

Create a new self-rewarding token on Solana. Required fields: `token_name`, `token_ticker`, `marketing_wallet`.

```bash
curl -s -X POST https://api.op0.live/functions/v1/altar-api-public \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $OP0_API_KEY" \
  -d '{
    "action": "create",
    "token_name": "TOKEN_NAME",
    "token_ticker": "TICKER",
    "marketing_wallet": "SOLANA_WALLET_ADDRESS",
    "payout_token_ticker": "wbtcsol",
    "blocks_per_cycle": 5,
    "payout_percent": 30,
    "min_hold_amount": 500000,
    "community_percent": 50,
    "color": "#3b8fff"
  }'
```

Optional fields: `token_description`, `website`, `token_twitter`, `token_telegram`, `payout_token_ticker` (default: wbtcsol), `blocks_per_cycle` (2-9, default: 5), `payout_percent` (10-50, default: 30), `min_hold_amount` (default: 500000), `community_percent` (50-98, default: 50), `color` (hex, default: #3b8fff).

For images, use base64: add `token_image_base64`, `token_image_mime`, and `token_image_name` fields.

Response returns `altar_id`, `dev_wallet`, `amount_required_sol` (typically 0.05), `expires_at` (30 min window).

**After creation:** Tell the user to send the required SOL to the `dev_wallet` address. Then poll the status endpoint.

### 2. Check Altar Status

Poll this every 5 seconds after the user sends SOL. When funded, token deployment triggers automatically.

```bash
curl -s -X POST https://api.op0.live/functions/v1/altar-api-public \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $OP0_API_KEY" \
  -d '{"action":"status","altar_id":ALTAR_ID}'
```

Status transitions: `awaiting_funding` -> `creating` -> `active`. When active, response includes `token_mint`, `altar_url`, `pump_fun_url`, `treasury_wallet`.

If status is `expired`, the 30-minute funding window closed. Create a new altar.

### 3. List All Altars

```bash
curl -s -X POST https://api.op0.live/functions/v1/altar-api-public \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $OP0_API_KEY" \
  -d '{"action":"list"}'
```

Returns array of altars with `altar_id`, `name`, `token_mint`, `status`, `altar_url`, `website`, `payout_token`, config fields.

### 4. Get Altar Info

```bash
curl -s -X POST https://api.op0.live/functions/v1/altar-api-public \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $OP0_API_KEY" \
  -d '{"action":"info","altar_id":ALTAR_ID}'
```

Returns full altar details including live treasury balance (fetched via RPC) and current cycle state.

### 5. List Payout Tokens (No Auth)

```bash
curl -s -X POST https://api.op0.live/functions/v1/altar-api-public \
  -H "Content-Type: application/json" \
  -d '{"action":"payout-tokens"}'
```

Returns all 129 available tokens. Categories: Stablecoins (usdc, usdt, pyusd, usd1, eurc, fdusd, usds), Blue Chips (sol, wbtcsol, jitosol, msol, bnsol, render, pyth, hnt), Memecoins (bonk, wif, popcat, fartcoin, mew, pnut, bome, moodeng, ponke, myro, giga, pengu, goat, chillguy, dood, vine), AI (virtual, griffain, elizaos, zerebro, swarms, tai, holo, llm, ani, buzz), DeFi (jup, ray, orca, drift, jto, kmno, met, fida, tensor), Tokenized Stocks (tslax, nvdax, aaplx, mstrx, googlx, spyx, qqqx, coinx, crclx), Political (trump, melania, wlfi, a47).

## Behavior Rules

1. **Always ask for `marketing_wallet`** before creating an altar. Without it, 98% of creator fees go to the community treasury with no marketing distribution.
2. **When the user says "create a coin/token/altar"**, gather: name, ticker, marketing wallet, and optionally payout token preference. Use sensible defaults for everything else.
3. **After calling create**, clearly tell the user the `dev_wallet` address and exact SOL amount to send. Remind them of the 30-minute window.
4. **After the user confirms they sent SOL**, poll the status endpoint every 5 seconds (up to 60 attempts). Report the final state.
5. **If the user asks "what tokens can I reward holders with"**, call the payout-tokens endpoint and present the results organized by category.
6. **Rate limits:** 3 API keys per wallet, 5 creates per key per 24 hours.
7. **If no API key is configured**, offer to generate one. The user just needs their Solana wallet address.

## Error Handling

- `401`: Invalid or missing API key. Offer to generate a new one.
- `429`: Rate limit exceeded. Response includes `resets_at` timestamp. Tell the user when they can try again.
- `400`: Bad request. Check required fields. Most common: missing `marketing_wallet`.
- `expired` status: The 30-minute funding window closed. Create a new altar.

## MCP Server Alternative

If the user's OpenClaw instance supports MCP servers, they can also use the OP0 MCP server for a richer integration:

```
openclaw config set mcpServers.op0.command "npx"
openclaw config set mcpServers.op0.args '["@op0live/mcp-server"]'
openclaw config set mcpServers.op0.env.OP0_API_KEY "op0_live_YOUR_KEY"
openclaw config set mcpServers.op0.env.OP0_API_URL "https://api.op0.live/functions/v1/altar-api-public"
```

This exposes 5 tools: `op0_create_altar`, `op0_check_altar_status`, `op0_list_altars`, `op0_altar_info`, `op0_list_payout_tokens`.
