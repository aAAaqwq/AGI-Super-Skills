# High-Latency Network Handling for 5minbtc

> 2026-06-24 session findings | ping ~260ms to 8.8.8.8

## Problem

When network latency exceeds ~250ms (ping 8.8.8.8), three failures occur simultaneously:

1. **Binance API SSL timeout**: Both `api.binance.us` and `data-api.binance.vision` return HTTP 000
   - Root cause: Python `urlopen(timeout=10)` insufficient for TLS handshake at >250ms
   - Curl with `--connect-timeout 20` works fine → proves it's a timeout, not endpoint outage
   
2. **Web search unavailable**: DuckDuckGo/Startpage backend times out
   - All `web_search` calls fail regardless of query
   
3. **Engine pred_close distortion at extreme progress**: If engine runs late (>80% progress), the half_range×ATR formula overestimates remaining movement

## Diagnostic Flow

```bash
# 1. Check network latency
ping -c 2 -W 3 8.8.8.8

# 2. Test Binance with extended timeout
for ep in "api.binance.us" "data-api.binance.vision"; do
  code=$(curl -s --connect-timeout 20 --max-time 30 -o /dev/null -w "%{http_code}" \
    "https://$ep/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=1")
  echo "$ep → HTTP $code"
done

# 3. If curl works (HTTP 200) but Python fails → timeout patching needed
#    If curl also fails → true network outage, skip this round
```

## Fix: Engine Timeout Patching

When curl with extended timeout works but Python `urlopen(timeout=10)` fails:

```bash
SKILL_DIR=/home/aa/.hermes/profiles/cqo/skills/5minbtc
cd "$SKILL_DIR"

# Backup
cp 5minbtc-engine-v5.7.py 5minbtc-engine-v5.7.py.bak-net

# Increase timeouts: klines 10→25s, others 5→15s
sed -i 's|timeout=10|timeout=25|g' 5minbtc-engine-v5.7.py
sed -i 's|timeout=5|timeout=15|g' 5minbtc-engine-v5.7.py

# Run engine
python3 5minbtc-engine-v5.7.py

# ALWAYS restore
cp 5minbtc-engine-v5.7.py.bak-net 5minbtc-engine-v5.7.py
rm 5minbtc-engine-v5.7.py.bak-net
```

⚠️ **Never leave the patched timeouts in place** — the engine is designed for 3s parallel execution; 25s timeouts would make it unusable in normal conditions.

## Extreme Progress Edge Case

Session ran at 20:14 for a 20:10→20:15 candle (progress=94%, 18s remaining).
Engine pred_close=$62,745 vs current=$62,900 (gap: -$155).

The half_range×ATR formula assumes ~2.5min remaining. At 18s remaining,
the realistic price movement is at most ~$10-20, not $155.

**LLM adjustment formula**:
```
pred_close = current + (engine_pred_close - current) × (remaining_sec / 150)
```

Where 150 = approximate seconds at 50% progress (design target).
At 94% progress with 18s remaining: factor = 18/150 = 0.12
→ pred_close = 62900 + (62745 - 62900) × 0.12 = $62,881

This is a common-sense adjustment — the LLM should note it explicitly in output.

## Web Search Fallback

When web_search fails due to network:
- Don't retry more than 2 rounds total
- Use `5minbtc-news.py` output (RSS-based, doesn't use search backend)
- Note in output: "新闻搜索不可用（网络高延迟），已用引擎内置RSS扫描"

## Session Log (2026-06-24)

- Time: 20:14 CST
- Candle: 20:10→20:15, progress 94.0%, 18s remaining
- Price: $62,900 | Open: $62,883.5 | Body: +$16
- Engine: neutral/weak, conf=44, pred_close=$62,745
- LLM adjustment: pred_close→$62,895 (noted extreme progress)
- Network: ping 260ms, both endpoints SSL timeout, web search dead
- News: 0 articles from all 3 sources
- Outcome: logged as neutral, conf=44
