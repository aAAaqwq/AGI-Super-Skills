# 📊 Polymarket Skill for OpenClaw

Browse prediction markets, check odds, and trade on [Polymarket](https://polymarket.com) directly from your AI agent.

## What it does

- **Browse markets** - trending, search, filter by category (politics, crypto, sports, etc.)
- **Check odds** - real-time Yes/No prices, volume, end dates
- **View order books** - see bid/ask depth for any market
- **Price history** - track how odds have moved over time
- **Trade** - place limit and market orders (buy/sell) with built-in safety confirmations
- **Manage positions** - view open orders, cancel trades, check balances

## Quick start

### Install the skill

```bash
# Clone directly from GitHub
git clone https://github.com/mvanhorn/clawdbot-skill-polymarket.git ~/.openclaw/skills/polymarket

# Or if you use a custom skills directory
git clone https://github.com/mvanhorn/clawdbot-skill-polymarket.git /path/to/your/skills/polymarket
```

### Browse markets (works immediately, no setup)

Just ask your agent:
- "What's trending on Polymarket?"
- "Search Polymarket for AI regulation"
- "What are the odds on the Fed cutting rates?"

### Trade (requires Polymarket CLI + wallet)

1. Install the [Polymarket CLI](https://github.com/Polymarket/polymarket-cli):
   ```bash
   curl -sSL https://raw.githubusercontent.com/Polymarket/polymarket-cli/main/install.sh | sh
   ```

2. Set up a wallet:
   ```
   polymarket wallet create
   polymarket approve set
   ```

3. Ask your agent:
   - "Buy 10 shares of YES on [market] at $0.45"
   - "What are my open positions?"
   - "Cancel all my orders"

All trades require explicit confirmation before executing. No surprises.

## Safety

- Trades preview by default. Nothing executes without `--confirm`.
- This is real money (USDC on Polygon). The Polymarket CLI is experimental software.
- Your private key lives in `~/.config/polymarket/config.json`. Keep it safe.

## How it works

| Feature | Backend | Auth needed |
|---------|---------|-------------|
| Browse, search, trending | Gamma API (Python) | None |
| Order books, price history | Polymarket CLI | None |
| Trading, orders, positions | Polymarket CLI | Wallet |

Read-only features work without installing anything extra. Trading wraps the official [Polymarket CLI](https://github.com/Polymarket/polymarket-cli) (Rust).

## License

MIT
