# 🤖 Polymarket Short-Horizon Bot

> **🦞 Openclaw AI** Polymarket Trading Bot — TypeScript bot built with the Openclaw AI agent. Predicts crypto price direction on Polymarket’s 5-minute BTC Up/Down markets and tracks results (paper or live).

A **TypeScript bot** that predicts whether Polymarket’s **5-minute Bitcoin Up/Down** markets will move up (YES) or down (NO) over the next 5 minutes. It runs in **paper-trading mode by default** (no real money). You can optionally enable **live order execution** with your own API keys.

---

## 📋 What does this bot do?

1. **📍 Picks a market**  
   It finds the current active “BTC up or down in 5 minutes” market on Polymarket (or uses a market you pin in config).

2. **📊 Collects data every 15 seconds**  
   - Latest YES price from the order book  
   - Short-term price moves (e.g. last ~30 seconds, ~2 minutes)  
   - Recent “whale” 🐋 flow (large trades) on that market  

3. **🔮 Makes a prediction**  
   It combines:  
   - **Momentum** (recent returns)  
   - **Volatility** (recent price range)  
   - **Whale bias** (whether big traders are buying YES or NO)  
   - **Optional LLM bias** (if you set an OpenAI API key)  

   Into a single number: **probability that YES goes up in 5 minutes** (`pUp5m`).

4. **⚖️ Decides an action**  
   - If `pUp5m` is clearly above 0.5 (e.g. &gt; 0.53) → **OPEN YES** ✅  
   - If clearly below 0.5 (e.g. &lt; 0.47) → **OPEN NO** ❌  
   - Otherwise → **HOLD** ⏸️  
   The thresholds are set by `EDGE_THRESHOLD` in `.env`.

5. **📄 Paper vs live**  
   - **Paper (default):** It only *logs* “OPEN YES” or “OPEN NO” and keeps an in-memory list of fake positions. No real orders.  
   - **Live (optional):** If you add CLOB API credentials, it will place real **market BUY** orders for the chosen side (YES or NO token) when it would have “opened” that position in paper mode.

---

## 🔄 How the loop works (step by step)

Each run of the loop (every `LOOP_SECONDS` seconds, default 15):

```
1. Fetch market ticks (last 20 price snapshots) from Polymarket
2. If fewer than 3 ticks, wait (warm up)
3. Fetch whale flow for this market (recent large trades)
4. Build features: returns 30s, returns 2m, volatility 2m, whale bias, whale intensity
5. (Optional) Call LLM scorer with features → get a bias in [-1, 1]
6. Run predictor: linear combo + sigmoid → pUp5m, confidence
7. Paper trader: compare pUp5m to 0.5 ± EDGE_THRESHOLD → HOLD / OPEN YES / OPEN NO
8. If live trading is on and action is OPEN YES/NO → resolve token IDs, call buy(), log result
9. Log action and p5m/confidence to console
```

So: **data → features → prediction → decision → (optional) real order**.

---

## ⚡ Quick start

### 1. 📦 Install and config

```bash
cd polymarket-shorthorizon-bot
npm install
cp .env.example .env
```

Edit `.env` if you want (see [Environment variables](#environment-variables) below). You can leave everything default for **paper-only** runs.

### 2. 🚀 Run the bot (paper mode)

```bash
npm run dev
```

You’ll see logs like:

- `warming up price buffer` until it has enough ticks  
- Then: `OPEN YES $100 @ 0.52 | r30=...` or `HOLD | p5m=0.48 conf=0.12` etc.

No real orders are placed.

### 3. 📊 (Optional) Run the Compare UI

In another terminal:

```bash
npm run ui
```

Open **http://localhost:8787** in your browser.

- **Get Prediction** 🔍 — fetches the same snapshot the bot uses (market, current YES price, prediction, whale stats).  
- **Auto Compare** ⏱️ — you set “Entry YES price” and “Auto settle delay (sec)” (e.g. 300 for 5 min). The UI waits that long, then fetches the new YES price and records whether the bot’s predicted side (YES/NO) would have been correct.  
- **History** 📜 — table of past comparisons and **accuracy** (e.g. “Total: 10 | Correct: 6 | Accuracy: 60%”).

This helps you see how often the strategy would have been right before turning on live trading.

---

## 🔧 Environment variables

Copy `.env.example` to `.env` and adjust as needed.

| Variable | Description | Default |
|----------|-------------|--------|
| **Data sources** | | |
| `POLYMARKET_REST_BASE` | Gamma API base URL | `https://gamma-api.polymarket.com` |
| `POLYMARKET_MARKET_SLUG` | Pin a specific market (e.g. `btc-updown-5m-1234567890`) | (empty = auto-select current 5m BTC market) |
| `POLYMARKET_MARKET_ID` | Or pin by market ID | (empty) |
| **Optional LLM** | | |
| `OPENAI_API_KEY` | If set, features are sent to the LLM for an extra bias signal | (empty = no LLM) |
| `OPENAI_BASE_URL` | OpenAI-compatible API base | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | Model name | `gpt-4o-mini` |
| **Runtime** | | |
| `LOOP_SECONDS` | Seconds between each loop run | `15` |
| `MAX_POSITION_USD` | Size in USD for paper/live “position” | `100` |
| `EDGE_THRESHOLD` | Min edge to open: \|pUp5m - 0.5\| &gt; this (e.g. 0.03 → open if pUp5m &gt; 0.53 or &lt; 0.47) | `0.03` |
| **Live trading (optional)** | | |
| `PRIVATE_KEY` | Wallet private key (hex). **Required for live.** | (empty = paper only) |
| `CLOB_API_KEY` | From Polymarket CLOB “create or derive API key” | (empty) |
| `CLOB_SECRET` | Same | (empty) |
| `CLOB_PASS_PHRASE` | Same | (empty) |
| `CLOB_API_URL` | CLOB API base | `https://clob.polymarket.com` |
| `CLOB_CHAIN_ID` | Chain ID (Polygon mainnet) | `137` |

**Live trading is only enabled when** `PRIVATE_KEY`, `CLOB_API_KEY`, `CLOB_SECRET`, and `CLOB_PASS_PHRASE` are all set. Otherwise the bot is paper-only.

---

## 📊 Compare UI in detail

- **Get Prediction** 🔍  
  Calls the same backend as the bot (`/api/prediction`): current market, YES price, 5m prediction (pUp5m, side), confidence, whale stats. Good for a quick sanity check.

- **Auto Compare (5m)** ⏱️  
  1. Click “Get Prediction” once so the snapshot is loaded.  
  2. “Entry YES price” is pre-filled with current YES; you can change it.  
  3. Set “Auto settle delay” to 300 (5 minutes) or another value.  
  4. Click “Start Auto Compare.”  
  5. The UI waits that many seconds, then fetches the current YES price again and records: predicted side vs actual (YES if exit price ≥ entry, else NO). It appends one row to History and updates accuracy.

- **Whale Panel** 🐋  
  Shows the same whale breakdown as in the snapshot (top wallets, net YES, gross, bias).

- **History** 📜  
  Stored in `localStorage`. Columns: Time, Market, Pred Side, Entry YES, Exit YES, Actual (YES/NO), Correct (✅/❌). Below: total count, correct count, accuracy %.

---

## 💰 Optional: live order execution

If you want the bot to **place real orders** when it would open a position in paper mode:

1. **🔑 Get CLOB API credentials**  
   See [Polymarket CLOB Quickstart](https://docs.polymarket.com/developers/CLOB/quickstart). You’ll use your wallet to create or derive API keys (L2 auth).

2. **📝 Put them in `.env`**  
   Set `PRIVATE_KEY`, `CLOB_API_KEY`, `CLOB_SECRET`, `CLOB_PASS_PHRASE`. Optionally `CLOB_API_URL`, `CLOB_CHAIN_ID`.

3. **🚀 Run the bot**  
   `npm run dev`. The log will say “Starting short-horizon bot (LIVE).” When the paper logic would “OPEN YES” or “OPEN NO,” the bot will:
   - Resolve the market’s condition ID and YES/NO token IDs via the CLOB API  
   - Call `buy(tokenId, MAX_POSITION_USD, priceLimit)` (FOK market buy)  
   - Log success (order ID, status) or failure (error message)

**Code:** Live logic is in `src/main.ts`. Order placement is in `src/connectors/orderExecution.ts` (`placeOrder`, `buy`, `sell`). The bot only **buys** when opening; it does not implement selling or closing positions automatically.

---

## 📁 Project structure (high level)

| Path | Role |
|------|------|
| `src/main.ts` | Entry point: loop every N seconds, fetch data → features → predict → paper/live action |
| `src/config.ts` | Reads `.env`, exposes `cfg` (URLs, keys, thresholds, `liveTradingEnabled`) |
| `src/connectors/polymarket.ts` | Talks to Gamma API (market, ticks) and Data API (trades for whale flow). Exposes `getConditionId()` for live orders |
| `src/connectors/orderExecution.ts` | CLOB client wrapper: `placeOrder`, `buy`, `sell`, `getTokenIdsForCondition` |
| `src/engine/features.ts` | Builds feature vector from ticks + whale (returns, vol, whale bias/intensity) |
| `src/engine/predictor.ts` | Combines features + LLM bias → pUp5m, confidence |
| `src/engine/paperTrader.ts` | In-memory “positions”; given prediction + current price → HOLD / OPEN YES / OPEN NO |
| `src/models/llmScorer.ts` | Optional: calls OpenAI (or compatible) API with features, returns bias in [-1, 1] |
| `src/uiServer.ts` | Serves the Compare UI and `/api/prediction` |
| `ui/` | Static Compare UI (HTML, JS, CSS) |

---

## ⚠️ Important notes

- **📄 Paper by default**  
   No credentials ⇒ no real orders. Only logs and in-memory paper positions.

- **📍 Market selection**  
   If you don’t set `POLYMARKET_MARKET_SLUG` or `POLYMARKET_MARKET_ID`, the bot picks the current 5-minute BTC up/down market (by time bucket or recent trades).

- **🐋 Whale flow**  
   Built from public trade data (e.g. Data API). “Whales” here = wallets with ≥ $200 notional in the sampled window. It’s a proxy, not full wallet-level history.

- **⚠️ No guarantees**  
   This is a heuristic/experimental strategy. Past or paper accuracy does not guarantee future results. Use live trading at your own risk and only with money you can afford to lose.

- **🔄 Selling / closing**  
   The bot only opens positions (market buy YES or NO). It does not automatically sell or close. You would need to do that manually or extend the code.

---

## 🛠️ Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | 🚀 Run the bot (paper or live, depending on `.env`) with tsx |
| `npm run ui` | 📊 Start the Compare UI server on port 8787 |
| `npm run build` | 📦 Compile TypeScript to `dist/` |
| `npm start` | ▶️ Run compiled bot: `node dist/main.js` |

---

*Built with [Openclaw 🦞](https://github.com/openclaw) AI agent.*
