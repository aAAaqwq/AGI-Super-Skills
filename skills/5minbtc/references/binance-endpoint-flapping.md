# Binance Endpoint Flapping Pattern

> 2026-06-18 session observation

## The Pattern

Both `api.binance.us` and `data-api.binance.vision` exhibit **intermittent flapping** — neither is permanently reliable. The failure is **bi-directional** and appears to be related to WireGuard tunnel instability rather than a problem with any specific Binance endpoint.

## Observed Behavior (2026-06-18)

| Time | api.binance.us | data-api.binance.vision | curl | Python urllib |
|------|---------------|------------------------|------|--------------|
| 20:10 | ❌ | ❌ | ❌ (exit 28 timeout) | ❌ |
| 20:11 | ✅ | — | ✅ (HTTP 200) | — |
| 20:12 | — | ❌ | ❌ (exit 28) | ❌ |
| 20:13 | ✅ | — | ✅ (HTTP 200) | — |

## Key Observations

1. **Both endpoints fail at the same time** when the WireGuard tunnel drops — this rules out endpoint-specific issues
2. **curl and Python urllib fail simultaneously** — the issue is at the kernel/network level, not the SSL library
3. **Retrying 1-2 minutes later often works** — the tunnel self-heals within minutes
4. **Error signature**: `curl: (28) Operation timed out` or `SSL_ERROR_SYSCALL` — no DNS or routing issue, just a dropped connection at the tunnel layer

## Recovery Procedure

```bash
# Step 1: Test both endpoints
for ep in "api.binance.us" "data-api.binance.vision"; do
  code=$(curl -s --connect-timeout 5 --max-time 10 -o /dev/null -w "%{http_code}" \
    "https://$ep/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=1" 2>&1)
  echo "$ep → $code"
done

# Step 2: If both fail, wait 1-2 minutes and retry (tunnel self-heals)
sleep 90
# retry Step 1

# Step 3: If one endpoint works and the other doesn't, switch engine to the working one
# (see binance-api-geo.md for switch commands)

# Step 4: If both still fail after 5 minutes, check WireGuard tunnel
ping -c 3 8.8.8.8
ping -c 3 198.18.0.10  # WireGuard virtual IP
```

## Diagnosis Commands

```bash
# Test basic network (if this fails, it's not Binance-specific)
curl -s --connect-timeout 5 --max-time 10 "https://google.com" -o /dev/null -w "%{http_code}"

# Check if the issue is DNS or tunnel
nslookup api.binance.us
nslookup data-api.binance.vision

# Verbose SSL diagnostics
curl -v --connect-timeout 10 "https://api.binance.us/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=1" 2>&1 | grep -E "SSL|connect|time|error|HTTP"

# Test with resolved IP (bypass DNS)
curl -s --connect-timeout 5 --max-time 10 \
  --resolve "api.binance.us:443:208.115.61.204" \
  "https://api.binance.us/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=1" \
  -o /dev/null -w "%{http_code}"
```

## What NOT To Do

- **Don't switch back and forth rapidly** — flapping makes the endpoint the wrong variable to optimize. Wait for the tunnel to stabilize instead.
- **Don't file a bug against a specific endpoint** — both fail together; it's not endpoint-specific.
- **Don't increase timeout beyond 15s** — if the tunnel is down, a longer timeout just delays recovery.
- **Don't try api.binance.com** — will return HTTP 451 from this network.

## Lesson for the Skill

The correct response to an "all endpoints down" scenario is:
1. Confirm the pattern (test both endpoints)
2. Wait 1-2 minutes
3. Retry
4. If still down: report to user, suggest checking WireGuard tunnel

The incorrect response is: rotating endpoints rapidly, increasing timeouts, or trying unblocked-but-blocked endpoints (api.binance.com).
