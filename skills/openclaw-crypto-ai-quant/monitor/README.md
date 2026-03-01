# Monitor Dashboard (read-only)

Local Python dashboard for monitoring **Live** + **Paper** daemons. For the Rust + Svelte alternative, see the [hub/](../hub/) dashboard.

- Reads SQLite DBs + daemon runtime logs (no secrets).
- Reads mid ticks from the local Rust **WS sidecar** (no direct Hyperliquid WS calls).
- Optionally fetches **Live** balances from Hyperliquid REST `user_state` (read-only) so the UI shows
  `accountValue` and `withdrawable` directly instead of relying on DB-derived estimates.
- No order placement. No cancels. Read-only.

## Run (manual)

From the repo root:

```bash
.venv/bin/python3 -u monitor/server.py
```

Open:

```text
http://127.0.0.1:61010/
```

Real-time mids stream endpoint (SSE):

```text
GET /api/mids/stream
```

## Run (systemd user service)

Install:

```bash
cp systemd/openclaw-ai-quant-monitor.service.example ~/.config/systemd/user/openclaw-ai-quant-monitor.service
systemctl --user daemon-reload
systemctl --user enable --now openclaw-ai-quant-monitor.service
```

Logs:

```bash
journalctl --user -u openclaw-ai-quant-monitor.service -f
```

## Env vars

- `AIQ_MONITOR_BIND` (default `127.0.0.1`)
- `AIQ_MONITOR_PORT` (default `61010`)
- `AI_QUANT_WS_SIDECAR_SOCK` (optional; defaults to `%t/openclaw-ai-quant-ws.sock`)
- `AIQ_MONITOR_MIDS_POLL_MS` (default `1000`; legacy fallback when sidecar lacks `wait_mids`)
- `AIQ_MONITOR_MIDS_WAIT_TIMEOUT_S` (default `25`; blocking wait timeout for sidecar push updates)
- `AIQ_MONITOR_MIDS_MAX_AGE_S` (default `60`)
- `AIQ_MONITOR_MIDS_STREAM_KEEPALIVE_S` (default `15`; SSE keepalive for `/api/mids/stream`)
- `AIQ_MONITOR_INTERVAL` (default `AI_QUANT_INTERVAL` else `1m`)

Optional overrides:

- `AIQ_MONITOR_LIVE_DB` (default `trading_engine_live.db`)
- `AIQ_MONITOR_PAPER_DB` (default `trading_engine.db`)

Hyperliquid balance (Live mode only):

- `AIQ_MONITOR_HL_BALANCE_ENABLE` (default `true`)
- `AIQ_MONITOR_HL_BALANCE_TTL_S` (default `5`)
- `AIQ_MONITOR_HL_TIMEOUT_S` (default `4`)
- `AIQ_MONITOR_HL_BASE_URL` (optional; overrides Hyperliquid Info base URL)
- `HL_INFO_BASE_URL` (optional; alternative base URL override)
- `AIQ_MONITOR_HL_MAIN_ADDRESS` / `AIQ_MONITOR_MAIN_ADDRESS` (recommended; wallet address to query)
- `AIQ_MONITOR_SECRETS_PATH` / `AI_QUANT_SECRETS_PATH` (optional; used only to read `main_address`)

Notes:

- Heartbeats are read from SQLite `runtime_logs` (preferred). If unavailable, use the systemd journal (`journalctl --user -u openclaw-ai-quant-*.service`).
