# Operations Runbook

Procedures for common operational scenarios. When the bot misbehaves, follow the relevant section below.

## Services Reference

| Service | Unit name | Purpose |
|---------|-----------|---------|
| Paper trader | `openclaw-ai-quant-trader` | Paper trading daemon |
| Live trader | `openclaw-ai-quant-live` | Live trading daemon |
| WS sidecar | `openclaw-ai-quant-ws-sidecar` | Market data WebSocket |
| Monitor | `openclaw-ai-quant-monitor` | Real-time dashboard |

All services are systemd user units. Manage with `systemctl --user <action> <unit>`.

### Optional timers (nightly factory + log pruning + replay alignment gate)

Example service/timer templates live under `systemd/`:

- `openclaw-ai-quant-factory.{service,timer}.example` runs `factory_run.py` nightly.
- `openclaw-ai-quant-prune-runtime-logs.{service,timer}.example` prunes SQLite `runtime_logs` daily.
- `openclaw-ai-quant-replay-alignment-gate.{service,timer}.example` runs deterministic replay alignment checks and writes a release-blocker status file.

Install (example):

```bash
mkdir -p ~/.config/systemd/user
install -m 0644 systemd/openclaw-ai-quant-factory.service.example \
  ~/.config/systemd/user/openclaw-ai-quant-factory.service
install -m 0644 systemd/openclaw-ai-quant-factory.timer.example \
  ~/.config/systemd/user/openclaw-ai-quant-factory.timer
install -m 0644 systemd/openclaw-ai-quant-prune-runtime-logs.service.example \
  ~/.config/systemd/user/openclaw-ai-quant-prune-runtime-logs.service
install -m 0644 systemd/openclaw-ai-quant-prune-runtime-logs.timer.example \
  ~/.config/systemd/user/openclaw-ai-quant-prune-runtime-logs.timer
install -m 0644 systemd/openclaw-ai-quant-replay-alignment-gate.service.example \
  ~/.config/systemd/user/openclaw-ai-quant-replay-alignment-gate.service
install -m 0644 systemd/openclaw-ai-quant-replay-alignment-gate.timer.example \
  ~/.config/systemd/user/openclaw-ai-quant-replay-alignment-gate.timer
systemctl --user daemon-reload
systemctl --user enable --now openclaw-ai-quant-factory.timer
systemctl --user enable --now openclaw-ai-quant-prune-runtime-logs.timer
systemctl --user enable --now openclaw-ai-quant-replay-alignment-gate.timer
```

Configure runtime log retention via:

```
AI_QUANT_RUNTIME_LOG_KEEP_DAYS=14
```

Example replay alignment gate environment (`~/.config/openclaw/ai-quant-replay-gate.env`):

```bash
AI_QUANT_REPLAY_GATE_CANDLES_DB=/home/<user>/openclaw-plugins/ai_quant/candles_dbs/candles_1h.db
AI_QUANT_REPLAY_GATE_FUNDING_DB=/home/<user>/openclaw-plugins/ai_quant/backtester/data/funding_rates_1h.db
AI_QUANT_REPLAY_GATE_INTERVAL=1h
AI_QUANT_REPLAY_GATE_WINDOW_MINUTES=240
AI_QUANT_REPLAY_GATE_LAG_MINUTES=2
AI_QUANT_REPLAY_GATE_MIN_LIVE_TRADES=1
AI_QUANT_REPLAY_GATE_STRICT_NO_RESIDUALS=1
AI_QUANT_REPLAY_GATE_BUNDLE_ROOT=/tmp/openclaw-ai-quant/replay_gate
AI_QUANT_REPLAY_GATE_BLOCKER_FILE=/tmp/openclaw-ai-quant/replay_gate/release_blocker.json
```

Manual trigger:

```bash
systemctl --user start openclaw-ai-quant-replay-alignment-gate.service
```

Check blocker status:

```bash
cat /tmp/openclaw-ai-quant/replay_gate/release_blocker.json
```

Deployment tooling is fail-closed against this blocker by default:

- `python tools/paper_deploy.py ...`
- `python tools/deploy_sweep.py ...`
- `python tools/promote_to_live.py --apply ...`

These commands now abort when the blocker is red/missing/stale. Override only for emergency/manual workflows:

```bash
python tools/paper_deploy.py ... --ignore-replay-gate
python tools/deploy_sweep.py ... --ignore-replay-gate
python tools/promote_to_live.py --apply ... --ignore-replay-gate
```

### Secrets management

Do not store secrets in the repo. Recommended locations:

- Hyperliquid key material: `~/.config/openclaw/ai-quant-secrets.json` (chmod 600)
- Service environment: `~/.config/openclaw/ai-quant-live.env`
  - Put alerting targets (e.g. `AI_QUANT_ALERT_TARGETS`) here, especially if using webhook URLs.

---

## 1. Pause Trading (Emergency Stop)

Use when: unexpected losses, erratic behaviour, exchange issues, or any situation requiring immediate halt.

### Option A: Kill-switch via environment (close-only)

Blocks new entries but allows exits to close positions.

```bash
# Close-only mode (recommended default)
export AI_QUANT_KILL_SWITCH=close_only
systemctl --user restart openclaw-ai-quant-live

# Full halt — blocks ALL orders including exits
export AI_QUANT_KILL_SWITCH=halt_all
systemctl --user restart openclaw-ai-quant-live
```

### Option B: Kill-switch via file (no restart needed)

The `RiskManager` polls this file periodically.

```bash
# Close-only
echo "close_only" > /tmp/ai-quant-kill

# Full halt
echo "halt_all" > /tmp/ai-quant-kill
```

Set the file path in the service env:
```
AI_QUANT_KILL_SWITCH_FILE=/tmp/ai-quant-kill
```

### Option C: Stop the service entirely

```bash
# Stop live trading
systemctl --user stop openclaw-ai-quant-live

# Stop paper trading
systemctl --user stop openclaw-ai-quant-trader
```

### Clearing the kill-switch

```bash
# Remove file-based kill
rm /tmp/ai-quant-kill

# Clear env-based kill — unset and restart
unset AI_QUANT_KILL_SWITCH
systemctl --user restart openclaw-ai-quant-live
```

### Verification

```bash
# Check service status
systemctl --user status openclaw-ai-quant-live

# Check logs for kill-switch activation
journalctl --user -u openclaw-ai-quant-live --since "10 min ago" | grep -i kill
```

---

## 1a. Emergency Flatten ("Flat Now") (AQC-808)

Use when: you need to *both* pause entries and flatten positions under a known unwind policy.

Policy (default):

- Write a kill-switch file in `close_only` mode (pause new entries, allow exits).
- Flatten positions:
  - Paper: clear `position_state` and insert `SYSTEM CLOSE` trades.
  - Live (optional): submit market-close (reduce-only IOC) per open position with retries.
- Leave the kill-switch in place until post-incident review is complete.

### Paper flatten + pause (safe default)

```bash
python tools/flat_now.py \
  --kill-file /tmp/ai-quant-kill \
  --pause-mode close_only \
  --paper \
  --yes
```

### Live flatten + pause (explicit, destructive)

Live flatten requires `--yes`. Secrets are loaded from `AI_QUANT_SECRETS_PATH` (or `~/.config/openclaw/ai-quant-secrets.json`).

```bash
python tools/flat_now.py \
  --kill-file /tmp/ai-quant-kill \
  --pause-mode close_only \
  --live \
  --yes
```

To flatten both paper and live in one command:

```bash
python tools/flat_now.py \
  --kill-file /tmp/ai-quant-kill \
  --pause-mode close_only \
  --paper \
  --live \
  --yes
```

Notes:

- Avoid `halt_all` when you want exits to run in-engine; it blocks *all* orders including exits.
- This tool does not clear the kill-switch automatically. Clear it manually once you are confident it is safe.

## 1b. Strategy Mode Switching (AQC-1002)

The engine supports an optional strategy-mode overlay selected via `AI_QUANT_STRATEGY_MODE`:

- `primary`: 30m/5m
- `fallback`: 1h/5m
- `conservative`: 1h/15m
- `flat`: safety profile (use with a kill-switch when needed)

Mode overlays are defined under `modes:` in `config/strategy_overrides.yaml`.

### Manual mode change

```bash
export AI_QUANT_STRATEGY_MODE=fallback

# Restart is required if the mode changes global.engine.interval.
systemctl --user restart openclaw-ai-quant-live
```

### Automatic step-down on kill events

When enabled (`AI_QUANT_MODE_SWITCH_ENABLE=1`), the live daemon steps down one mode on each new kill event
and persists the selected mode to `AI_QUANT_STRATEGY_MODE_FILE` (default: `artifacts/state/strategy_mode.txt`).

If your systemd unit is configured to auto-restart on exit, you can also enable:

- `AI_QUANT_MODE_SWITCH_EXIT_ON_RESTART_REQUIRED=1`

This makes the daemon exit when switching to/from `primary` (where an interval change is likely), allowing
systemd to restart it with the new persisted mode.

---

## 1c. Ensemble Runner (AQC-1003)

The engine supports running a small ensemble (2-3 strategies) by launching multiple daemons with different configs.

This is implemented as a process runner (`tools/ensemble_runner.py`), not an in-process multi-strategy engine.

### Key points

- Each strategy has its own sizing budget via config overrides (e.g. `global.trade.size_multiplier`).
- Global risk caps (portfolio heat/exposure/kill-switch) are enforced by the existing RiskManager logic.
- Start with `dry_live` until you are confident the ensemble behaves as expected.

### Example

Edit the example spec:

- `config/ensemble.example.yaml`

Dry-run the plan:

```bash
python tools/ensemble_runner.py --spec config/ensemble.example.yaml
```

Launch the ensemble in dry-live:

```bash
python tools/ensemble_runner.py \
  --spec config/ensemble.example.yaml \
  --mode dry_live \
  --yes
```

## 2. Roll Back Config

Use when: a bad config was deployed and needs to be reverted to last-known-good.

### Step 1: Identify the previous config

```bash
# Check git log for config changes
git log --oneline -10 -- config/strategy_overrides.yaml
```

### Step 2: Restore the previous version

```bash
# Restore from git (replace <commit> with the last-known-good commit)
git checkout <commit> -- config/strategy_overrides.yaml
```

### Step 3: Verify the rollback

```bash
# Diff against current to confirm the change
git diff config/strategy_overrides.yaml

# Validate config parity
uv run python tools/validate_config.py
```

### Step 4: Reload

YAML config changes hot-reload automatically via mtime polling. No restart is needed unless `engine.interval` was changed.

```bash
# Confirm hot-reload happened (look for "Config reloaded" in logs)
journalctl --user -u openclaw-ai-quant-live --since "2 min ago" | grep -i reload
```

If `engine.interval` changed, a restart is required:

```bash
systemctl --user restart openclaw-ai-quant-live
```

---

## 3. Verify Database Integrity

Use when: suspecting data corruption, missing candles, or stale market data.

### Candle database freshness

```bash
# Check all candle DBs — row counts and time range
for db in candles_dbs/candles_*.db; do
    echo "=== $db ==="
    sqlite3 "$db" "SELECT COUNT(*) AS rows, datetime(MIN(t)/1000, 'unixepoch') AS earliest, datetime(MAX(t)/1000, 'unixepoch') AS latest, datetime(MAX(t_close)/1000, 'unixepoch') AS latest_close FROM candles;"
done
```

### Candle retention beyond 5,000 bars (AQC-203)

Hyperliquid only backfills roughly the last 5,000 bars per interval via `/info` (`candleSnapshot`). To build multi-month 3m/5m histories, the WS sidecar can keep the local candle DB append-only (no pruning) for selected intervals.

#### Migration / rollout

1. Deploy a `openclaw-ai-quant-ws-sidecar` build that includes AQC-203.
2. Ensure the service environment contains:
   - `AI_QUANT_CANDLE_PRUNE_DISABLE_INTERVALS=3m,5m`
   - Set an empty value to re-enable pruning for all intervals: `AI_QUANT_CANDLE_PRUNE_DISABLE_INTERVALS=`
3. Restart the sidecar service:
   - `systemctl --user restart openclaw-ai-quant-ws-sidecar`

No schema changes are required. Existing DB files are reused.

Notes:
- `Append-only beyond 5,000` is prospective. You cannot backfill older-than-5,000 bars from Hyperliquid, but once collected the sidecar will retain them locally.

#### Verification

```bash
# Per-symbol row counts should exceed 5,000 over time
sqlite3 candles_dbs/candles_3m.db "SELECT symbol, COUNT(*) AS rows FROM candles GROUP BY symbol ORDER BY rows DESC LIMIT 10;"
sqlite3 candles_dbs/candles_5m.db "SELECT symbol, COUNT(*) AS rows FROM candles GROUP BY symbol ORDER BY rows DESC LIMIT 10;"

# Duplicate check (should be 0; PK is (symbol, interval, t))
sqlite3 candles_dbs/candles_3m.db "SELECT COUNT(*) AS dupes FROM (SELECT symbol, interval, t, COUNT(*) AS c FROM candles GROUP BY symbol, interval, t HAVING c > 1);"
sqlite3 candles_dbs/candles_5m.db "SELECT COUNT(*) AS dupes FROM (SELECT symbol, interval, t, COUNT(*) AS c FROM candles GROUP BY symbol, interval, t HAVING c > 1);"
```

#### Disk growth expectations

3m adds ~480 rows/day/symbol, 5m adds ~288 rows/day/symbol. With pruning disabled for both, plan disk accordingly and monitor `candles_dbs/candles_{3m,5m}.db` file sizes.

### Candle DB partitioning / archival (AQC-204)

If you retain multi-month histories (especially 3m/5m), a single `candles_{interval}.db` file can grow large. Partitioning keeps the "hot" DB small while preserving long history in monthly archive DBs.

This repo uses monthly SQLite partitions created by `tools/partition_candles_db.py`:

- Hot DB (written by the WS sidecar): `candles_dbs/candles_{interval}.db`
- Archive partitions: `candles_dbs/partitions/{interval}/candles_{interval}_YYYY-MM.db`

#### Partitioning procedure

Prefer to stop the sidecar before applying changes:

```bash
systemctl --user stop openclaw-ai-quant-ws-sidecar
```

Dry-run (no writes):

```bash
uv run python tools/partition_candles_db.py --interval 5m
```

Apply copy-only:

```bash
uv run python tools/partition_candles_db.py --interval 5m --keep-days 120 --apply
```

Apply copy + delete (shrinks the hot DB over time):

```bash
uv run python tools/partition_candles_db.py --interval 5m --keep-days 120 --apply --delete
```

Optional: run `VACUUM` after deletion (slow, but compacts the file):

```bash
uv run python tools/partition_candles_db.py --interval 5m --keep-days 120 --apply --delete --vacuum
```

Restart the sidecar afterwards:

```bash
systemctl --user start openclaw-ai-quant-ws-sidecar
```

#### Backtester usage across partitions

The backtester can load candles from a comma-separated list of DB paths and/or a directory containing partition DBs.

Example (hot DB + partitions dir):

```bash
./target/release/mei-backtester replay \
  --interval 5m \
  --candles-db candles_dbs/candles_5m.db,candles_dbs/partitions/5m \
  --config config/strategy_overrides.yaml
```

### BBO snapshot database (AQC-206)

Optional, sampled best-bid/best-ask (BBO) snapshots are stored in SQLite for slippage modelling and post-trade analysis.

#### Enablement

- Enable BBO subscriptions: `AI_QUANT_WS_ENABLE_BBO=1`
- Optional: drive mid-price updates from BBO ticks (lower latency for monitor/UI): `AI_QUANT_MIDS_FROM_BBO=1`
- Enable snapshots: `AI_QUANT_BBO_SNAPSHOTS_ENABLE=1`

Tuning knobs:
- `AI_QUANT_BBO_SNAPSHOTS_DB_PATH` (default: `$AI_QUANT_CANDLES_DB_DIR/bbo_snapshots.db`)
- `AI_QUANT_BBO_SNAPSHOTS_SAMPLE_MS` (per-symbol insert throttle; default: 1000)
- `AI_QUANT_BBO_SNAPSHOTS_MAX_QUEUE` (bounded in-memory queue; default: 20000; drops when full)
- `AI_QUANT_BBO_SNAPSHOTS_RETENTION_HOURS` (time-based retention; default: 24)
- `AI_QUANT_BBO_SNAPSHOTS_RETENTION_SWEEP_SECS` (sweep interval; default: 600; min: 30)
- `AI_QUANT_MIDS_FROM_BBO_FALLBACK_AGE_S` (when BBO-driven mids are enabled, use `allMids` fallback once BBO age exceeds this threshold; default: 5.0)

Snapshots are only written for symbols the sidecar is subscribed to (the union of live client requests and `AI_QUANT_SIDECAR_SYMBOLS`).

#### Verification

```bash
# Row counts + time range per symbol
sqlite3 candles_dbs/bbo_snapshots.db \
  "SELECT symbol, COUNT(*) AS rows, datetime(MIN(ts_ms)/1000, 'unixepoch') AS earliest, datetime(MAX(ts_ms)/1000, 'unixepoch') AS latest FROM bbo_snapshots GROUP BY symbol ORDER BY rows DESC LIMIT 10;"

# Quick retention sanity check (should trend to 0 once retention < 48h)
sqlite3 candles_dbs/bbo_snapshots.db \
  "SELECT COUNT(*) AS older_than_48h FROM bbo_snapshots WHERE ts_ms < (strftime('%s','now') - 48*3600) * 1000;"
```

### Trading database integrity

```bash
# Paper DB
sqlite3 trading_engine.db "PRAGMA integrity_check;"

# Live DB
sqlite3 trading_engine_live.db "PRAGMA integrity_check;"
```

### Reality check (quick diagnostics)

```bash
# Check recent trading activity for a specific symbol
uv run python tools/reality_check.py --symbol BTC --hours 2
```

### Funding rate database

```bash
# Check freshness
sqlite3 candles_dbs/funding_rates.db \
    "SELECT symbol, COUNT(*) AS rows, MAX(time) AS latest FROM funding_rates GROUP BY symbol ORDER BY latest DESC LIMIT 10;"

# Automated freshness + anomaly checks (JSON on stdout; summary on stderr)
uv run python tools/check_funding_rates_db.py --lookback-hours 72 --max-gap-hours 4

# Backfill if stale
uv run python tools/fetch_funding_rates.py --days 7
```

### Universe history database (AQC-205)

Tracks when symbols appear/disappear in the Hyperliquid perp universe to support survivorship-bias-aware backtests.

```bash
# Sync current universe snapshot (recommended: run hourly via cron)
uv run python tools/sync_universe_history.py

# Inspect derived listing/delisting bounds
sqlite3 candles_dbs/universe_history.db \
    "SELECT symbol, first_seen_ms, last_seen_ms FROM universe_listings ORDER BY last_seen_ms DESC LIMIT 20;"
```

Backtester integration:

```bash
# Replay with universe filtering enabled (keeps symbols whose listing interval overlaps the backtest window)
./target/release/mei-backtester replay \
    --candles-db candles_dbs/candles_5m.db \
    --config config/strategy_overrides.yaml \
    --universe-filter

# Sweep with the same filter
./target/release/mei-backtester sweep \
    --candles-db candles_dbs/candles_5m.db \
    --sweep-spec backtester/sweeps/smoke.yaml \
    --universe-filter
```

Notes:
- The universe filter uses `universe_listings.first_seen_ms` / `last_seen_ms` derived from local snapshots. If you have not been running the sync script for the period you are testing, the filter may exclude symbols unexpectedly.
- The universe DB defaults to `<candles_db_dir>/universe_history.db`, so it follows your `--candles-db` location (useful when running the backtester from within `backtester/`).

### WebSocket sidecar health

```bash
# Check sidecar is running and connected
systemctl --user status openclaw-ai-quant-ws-sidecar

# Check sidecar logs for disconnects/errors
journalctl --user -u openclaw-ai-quant-ws-sidecar --since "1 hour ago" | grep -iE "error|disconnect|reconnect"
```

---

## 4. Rerun Validation

Use when: re-validating a config after a pause, before re-deploying, or as part of nightly checks.

### Single config replay (CPU)

```bash
# Replay with current config on 5m candles
./target/release/mei-backtester replay \
    --candles-db candles_dbs/candles_5m.db \
    --config config/strategy_overrides.yaml
```

### Slippage stress test

```bash
# Test at 10, 20, 30 bps slippage
for bps in 10 20 30; do
    echo "=== Slippage: ${bps} bps ==="
    ./target/release/mei-backtester replay \
        --candles-db candles_dbs/candles_5m.db \
        --config config/strategy_overrides.yaml \
        --slippage-bps "$bps"
done
```

### Config parity validation

```bash
# Verify Python defaults match Rust defaults and YAML is fully explicit
uv run python tools/validate_config.py
```

### Indicator parity check

```bash
# Export Rust indicators and compare against Python ta library
./target/release/mei-backtester dump-indicators \
    --candles-db candles_dbs/candles_1h.db \
    --symbol BTC
```

---

## 5. Restart Services

Use when: deploying code changes, recovering from crashes, or after system maintenance.

### Restart order (recommended)

Services should be restarted in dependency order:

```bash
# 1. WebSocket sidecar first (data source)
systemctl --user restart openclaw-ai-quant-ws-sidecar

# 2. Wait for sidecar to connect (check logs)
sleep 5
journalctl --user -u openclaw-ai-quant-ws-sidecar --since "10 sec ago" | tail -3

# 3. Trading daemon
systemctl --user restart openclaw-ai-quant-live    # or openclaw-ai-quant-trader for paper

# 4. Monitor (optional, non-critical)
systemctl --user restart openclaw-ai-quant-monitor
```

### Full stop (all services)

```bash
systemctl --user stop openclaw-ai-quant-live
systemctl --user stop openclaw-ai-quant-trader
systemctl --user stop openclaw-ai-quant-monitor
systemctl --user stop openclaw-ai-quant-ws-sidecar
```

### Full start (all services)

```bash
systemctl --user start openclaw-ai-quant-ws-sidecar
sleep 5
systemctl --user start openclaw-ai-quant-trader     # paper
# systemctl --user start openclaw-ai-quant-live     # live (uncomment when ready)
systemctl --user start openclaw-ai-quant-monitor
```

### Post-restart health check

```bash
# Verify all services are active
systemctl --user status openclaw-ai-quant-ws-sidecar openclaw-ai-quant-live openclaw-ai-quant-monitor

# Check for errors in the last minute
journalctl --user -u openclaw-ai-quant-live --since "1 min ago" | grep -iE "error|exception|traceback"

# Confirm config was loaded
journalctl --user -u openclaw-ai-quant-live --since "1 min ago" | grep -i "config"
```

---

## 6. Export State for Debugging

Use when: you need a snapshot of the current trader state for analysis or to seed a backtest.

```bash
# Export paper state
uv run python tools/export_state.py --source paper --output /tmp/paper_state.json

# Export live state
uv run python tools/export_state.py --source live --output /tmp/live_state.json

# Export trade history to CSV
uv run python tools/export_csv.py
```

---

## 7. Factory Stage Gate (dry -> smoke -> real)

Use when: promoting configuration candidates from nightly factory output.

Use this section for all automated rollouts. Do not deploy to live without a successful gate sequence.

### Precondition

- Keep the strategy config under version control.
- Ensure `factory_cycle` can write selection/evidence files to `artifacts/`.
- Confirm the following keys are present in `reports/selection.json` after each stage:
  - `selection_stage`
  - `deploy_stage`
  - `promotion_stage`
- Confirm candidate evidence is attached in:
  - `candidate_configs` inside `run_metadata.json`
  - `items` inside `reports/report.json`
  - `evidence_bundle_paths` in `selection.json`
- Confirm replay equivalence proof exists for promotion candidates:
  - `selected.canonical_cpu_verified == true`
  - `selected.replay_equivalence_status == "pass"`
  - `selected.candidate_mode == true`
  - `selected.schema_version == 1`
  - `selected.replay_equivalence_report_path` file exists
  - `selected.replay_equivalence_count` is recorded

### Stage command

```bash
./scripts/run_factory_stage_gate.sh \
  --run-prefix v8_factory_gate \
  --dry-profile smoke \
  --smoke-profile smoke \
  --real-profile daily \
  --config config/strategy_overrides.yaml \
  --artifacts-dir artifacts
```

### Stage definitions

1. Dry stage (`dry`)
   - Runs `factory_cycle` with `--no-deploy`.
   - Expected:
     - `selection_stage == "selected"`
     - `deploy_stage == "no_deploy"` (or `"skipped"`)
     - `promotion_stage == "skipped"`
2. Smoke stage (`smoke`)
   - Runs `factory_cycle` with `--no-deploy`.
   - Expected:
     - `selection_stage == "selected"`
     - `deploy_stage == "no_deploy"` (or `"skipped"`)
     - `promotion_stage == "skipped"`
3. Real stage (`real`)
   - Runs `factory_cycle` without `--no-deploy` unless deployment is intentionally blocked.
   - If deployment is intentionally blocked, behaviour must match dry/smoke.
   - Expected:
     - `selection_stage == "selected"`
     - `deploy_stage != "pending"`
     - `promotion_stage != "pending"`

### Evidence bundle

`run_factory_stage_gate.sh` writes a consolidated manifest:

```text
artifacts/<run-prefix>_<timestamp>.evidence.json
```

Each stage entry includes:

- `run_id`
- `stage`
- `selection_stage`
- `deploy_stage`
- `promotion_stage`
- `evidence_bundle_paths`
- `selected.canonical_cpu_verified`
- `selected.replay_equivalence_status`

### Hard gate acceptance (recommended before promotion)

Use this checklist before moving from `smoke` to `real` and before approving any real deployment:

- `selection.json` must pass:

  ```bash
  python3 scripts/validate_factory_selection_gate.py \
    --selection-json artifacts/<run_id>/reports/selection.json \
    --stage smoke
  ```

- `selection.json` must contain:
  - `evidence_bundle_paths.run_metadata_json` (existing and readable)
  - `evidence_bundle_paths.report_json`
  - `evidence_bundle_paths.selection_json`
  - `evidence_bundle_paths.selection_md`
  - `selected.canonical_cpu_verified == true`
  - `selected.pipeline_stage`, `selected.sweep_stage`, `selected.replay_stage`, `selected.validation_gate`
  - `selected.candidate_mode == true`
  - `selected.schema_version == 1`
  - `selected.replay_equivalence_report_path` exists and path exists
  - `selected.replay_report_path` exists and path exists
  - `selected.replay_equivalence_count` is an integer >= 0

- `run_metadata.json` must contain the same `selected.config_id` row, and replay proof paths must match when present.

Retain this manifest with the promotion ticket.

---

## Quick Reference: Environment Variables (Risk)

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_QUANT_KILL_SWITCH` | (unset) | `close_only` or `halt_all` |
| `AI_QUANT_KILL_SWITCH_FILE` | (unset) | Path to kill-switch file |
| `AI_QUANT_RISK_MAX_DRAWDOWN_PCT` | 0 (disabled) | Equity drawdown % to trigger kill |
| `AI_QUANT_RISK_MAX_ENTRY_ORDERS_PER_MIN` | 30 | Global entry rate limit |
| `AI_QUANT_RISK_MAX_ENTRY_ORDERS_PER_MIN_PER_SYMBOL` | 6 | Per-symbol entry rate limit |
| `AI_QUANT_RISK_MAX_EXIT_ORDERS_PER_MIN` | 120 | Exit rate limit |
| `AI_QUANT_RISK_MAX_CANCELS_PER_MIN` | 120 | Cancel rate limit |
| `AI_QUANT_RISK_MAX_NOTIONAL_PER_WINDOW_USD` | 0 (disabled) | Max entry notional per window |
| `AI_QUANT_RISK_MIN_ORDER_GAP_MS` | 0 (disabled) | Minimum ms between any two orders |

## References

- [Success Metrics & Guardrails](success_metrics.md) — risk thresholds and kill-switch triggers
- [Strategy Lifecycle](strategy_lifecycle.md) — config state machine and rotation rules
- [Architecture](ARCHITECTURE.md) — system design, components, and data flow
- [Release Process](release_process.md) — version governance and tag-driven releases
