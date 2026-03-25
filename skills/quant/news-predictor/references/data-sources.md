# Data Sources for News Monitoring (v2 — 5 sources)

## Unified Scanner

All sources consolidated in `scripts/news_monitor_v2.sh`. Single call:
```bash
bash scripts/news_monitor_v2.sh
```
Output: JSON with `{scan_time, items_found, data[{ts,source,title,categories,sentiment,impact}]}`
Filter: only last 6h of news included.

## Source Details

### 1. ⭐ CryptoCompare News API (Primary)
```bash
curl -s "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&limit=10&api_key=$CRYPTOCOMPARE_KEY"
```
- **Key**: stored in `.env.polymarket` as `CRYPTOCOMPARE_KEY`
- **Coverage**: 50+ crypto news sources, real-time, structured JSON
- **Categories**: BTC, ETH, SOL, ALTCOIN, REGULATION, MACROECONOMICS, SECURITY INCIDENTS, etc.
- **Sentiment**: per-article sentiment field (bullish/bearish/neutral)
- **Strength**: largest crypto news aggregator, <1min delay

### 2. ⭐ Yahoo Finance (Prices + Macro)
```bash
curl -s -H "User-Agent: Mozilla/5.0" "https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD?range=1d&interval=1h"
```
- **No API key needed**
- **Tickers**: BTC-USD, ETH-USD, SOL-USD, GC=F (Gold), CL=F (Oil)
- **Data**: Price, 24h change%, volume
- **Sentiment**: auto-derived from price change (>±1% = bullish/bearish)
- **Impact**: abs(change) > 2% = high

### 3. RSS Aggregation (CoinTelegraph + Bloomberg)
```bash
curl -s -H "User-Agent: Mozilla/5.0" "https://cointelegraph.com/rss"
curl -s -H "User-Agent: Mozilla/5.0" "https://feeds.bloomberg.com/markets/news.rss"
```
- **CoinTelegraph**: Crypto-specific, Atom format
- **Bloomberg Markets**: Macro/geopolitical, RSS format
- **Sentiment**: keyword-based (rally/surge=bullish, crash/slump/fear=bearish)
- **Impact**: Bloomberg Fed/CPI/inflation/crash keywords = high

### 4. FRED (Federal Reserve Economic Data)
```bash
curl -s "https://api.stlouisfed.org/fred/series/observations?series_id=CPIAUCSL&api_key=$FRED_KEY&file_type=json&limit=1"
```
- **Key**: stored in `.env.polymarket` as `FRED_KEY` (free registration at https://fred.stlouisfed.org/docs/api/api_key.html)
- **Free tier**: 120 requests/min
- **Series**: CPIAUCSL (CPI), UNRATE (unemployment), FEDFUNDS (Fed rate), GDP, PAYEMS (NFP)
- **Use**: Cross-verify macro data, detect data surprises

### 5. ⭐ Whale Alert (Chain On-Chain)
- **API**: Paid only (not viable)
- **Fallback**: Browser scrape `https://whale-alert.io/transactions`
- **Use**: Detect $1M+ BTC/ETH transfers, exchange inflows/outflows
- **Latency**: <30s for major transfers
- **Impact**: Large exchange inflows = potential selling pressure (bearish)

## Macro Calendar (Hardcoded + ForexFactory)

### Key Recurring Events
- **FOMC**: 8 meetings/year, ~6 weeks apart
- **CPI/PPI**: Monthly, ~13th-15th
- **NFP**: First Friday of each month
- **GDP**: Quarterly

### Live Calendar
```bash
curl -sL "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
```

### Fed Schedule 2026
```
Jan 28-29 (done) | Mar 18-19 (done) | May 6-7
Jun 17-18 | Jul 29-30 | Sep 16-17
Oct 28-29 | Dec 9-10
```

## Signal Storage

All detected signals stored in: `data/news-signals.jsonl`
Risk level: `data/news-risk-level.json` (trading cron reads this before every buy)
