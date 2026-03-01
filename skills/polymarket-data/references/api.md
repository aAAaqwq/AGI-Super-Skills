# Polymarket APIs

- **Gamma API** (gamma-api.polymarket.com): Market metadata, events, series. Public, no auth. Used by core commands.
- **CLOB API** (clob.polymarket.com): Prices, order books, trades. Public reads, no auth. Used by core commands.
- **Polymarket CLI** (`polymarket` binary): Full platform access via subprocess. Requires separate installation (`brew install polymarket`). Supports all Gamma, CLOB, Data, CTF, and trading operations via `-o json` output. Used for: leaderboard, positions, portfolio, trading, on-chain ops, comments, profiles, full-text search, tags, sports metadata.
