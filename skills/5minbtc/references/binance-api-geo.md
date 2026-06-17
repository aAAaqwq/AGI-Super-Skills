# Binance API Geo-Restriction Fix

## Problem
From China mainland, ALL standard Binance API endpoints return **HTTP 451** (Unavailable for Legal Reasons):
- `api.binance.com` → 451
- `api.binance.me` → 451
- `api1.binance.com` → 451

## Working Endpoints (tested 2026-05-22, updated 2026-06-14)

| Endpoint | Status | Notes |
|----------|--------|-------|
| `api.binance.us` | ✅ **Primary** | Most reliable across network conditions, including high-latency networks |
| `data-api.binance.vision` | ⚠️ Fallback | Works on low-latency networks; **SSL handshake times out on high-latency networks** (ping >250ms) |

### 2026-06-14 Update: SSL Timeout on data-api.binance.vision

On networks with high latency (ping to 8.8.8.8 ~300ms), `data-api.binance.vision` consistently fails with:
```
TimeoutError: _ssl.c:999: The handshake operation timed out
```
Even with Python `urlopen(..., timeout=20)`, the TLS handshake can't complete. `api.binance.us` handles the same network conditions without issues.

### Endpoint Quick Test
```bash
for ep in "api.binance.us" "data-api.binance.vision"; do
  code=$(curl -s --connect-timeout 10 --max-time 15 -o /dev/null -w "%{http_code}" \
    "https://$ep/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=1")
  echo "$ep → HTTP $code"
done
```

### Engine Endpoint Switch Commands
```bash
SKILL_DIR=/home/aa/.hermes/profiles/cqo/skills/5minbtc

# Switch to api.binance.us
sed -i 's|BINANCE_KLINES = .*|BINANCE_KLINES = "https://api.binance.us/api/v3/klines"|' $SKILL_DIR/5minbtc-engine-v5.7.py
sed -i 's|BINANCE_DEPTH = .*|BINANCE_DEPTH = "https://api.binance.us/api/v3/depth"|' $SKILL_DIR/5minbtc-engine-v5.7.py

# Switch to data-api.binance.vision
sed -i 's|BINANCE_KLINES = .*|BINANCE_KLINES = "https://data-api.binance.vision/api/v3/klines"|' $SKILL_DIR/5minbtc-engine-v5.7.py
sed -i 's|BINANCE_DEPTH = .*|BINANCE_DEPTH = "https://data-api.binance.vision/api/v3/depth"|' $SKILL_DIR/5minbtc-engine-v5.7.py
```

## Files Using Binance API
- `5minbtc-engine-v5.7.py` — `BINANCE_KLINES` and `BINANCE_DEPTH` constants (klines + depth fetch)
- `5minbtc-log.py` — hardcoded URL in `settle_candle()` and `settle-all` (2 occurrences)

## Migration Context
- Original OpenClaw cron ID: `14880142-c824-41cc-b41b-6079b072e322`
- Hermes cron ID: `d8058223a1e0`
- Schedule: `2,7,...,57 20-22 * * *` (UTC) = CST 04:02-06:57
- WORKSPACE hardcoded as `workspace-cqo` → changed to `SKILL_DIR = os.path.dirname(os.path.abspath(__file__))`
