# Binance API Geo-Restriction Fix

## Problem
From China mainland, ALL standard Binance API endpoints return **HTTP 451** (Unavailable for Legal Reasons):
- `api.binance.com` → 451
- `api.binance.me` → 451
- `api1.binance.com` → 451

## Working Endpoints (tested 2026-05-22)

| Endpoint | Status | Notes |
|----------|--------|-------|
| `data-api.binance.vision` | ✅ 200 | **Primary choice** — public data mirror, no auth needed |
| `api.binance.us` | ✅ 200 | US-specific, may have different pairs |

## Verification Command
```bash
curl -s -o /dev/null -w "%{http_code}" "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=5"
# Expected: 200
```

## Files Using Binance API
- `5minbtc-engine.py` — `BINANCE` constant (klines fetch)
- `5minbtc-log.py` — hardcoded URL in `settle_candle()` and `settle-all` (2 occurrences)

## Fix Applied
All `api.binance.me` → `data-api.binance.vision` in both engine and log scripts.

## Migration Context
- Original OpenClaw cron ID: `14880142-c824-41cc-b41b-6079b072e322`
- Hermes cron ID: `d8058223a1e0`
- Schedule: `2,7,...,57 20-22 * * *` (UTC) = CST 04:02-06:57
- WORKSPACE hardcoded as `workspace-cqo` → changed to `SKILL_DIR = os.path.dirname(os.path.abspath(__file__))`
