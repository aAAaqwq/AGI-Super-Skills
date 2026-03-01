# AI Agent Instructions for openclaw-crypto-ai-quant

This guide provides comprehensive instructions for AI coding assistants (Claude Code, Copilot, Cursor, etc.) working on this codebase.

## Production Safety and Branching Guardrails (MUST FOLLOW)

These guardrails exist because the production branch (`master`) is live and trades real money.

Do not change this section unless the user explicitly asks to update `AGENTS.md`.

- The production worktree at `/home/fol2hk/openclaw-plugins/ai_quant` MUST stay checked out on `master` at all times.
- Never run `git checkout`, `git switch`, or any branch-changing command inside `/home/fol2hk/openclaw-plugins/ai_quant`.
- Never edit application code in `/home/fol2hk/openclaw-plugins/ai_quant` directly. Treat this folder as production-run only.
- All code changes MUST be done in a separate worktree folder on a non-`master` branch (for example `/home/fol2hk/openclaw-plugins/ai_quant_wt/<ticket-branch>`).
- All AQC ticket work MUST be delivered through atomic PRs targeting `master` (one logical change per PR, no batching of unrelated fixes).
- Do not commit ticket changes directly on `master`. Use a dedicated ticket branch/worktree, open a PR, complete review, then merge.
- Multi-agent collaboration is expected: multiple active worktrees/branches/PRs may coexist at the same time.
- Mandatory PR flow for every successful code update:
  1. Create an atomic PR to `master`.
  2. Run a reviewer subagent to review the PR.
  3. Merge only after the review is acceptable.
  4. Continue to the next task only after merge completion.
  5. After merge, clean up only branches/worktrees created by the current agent/session (local + remote); never delete branches/worktrees owned by other concurrent agents.

## Project Overview

This is a crypto perpetual futures trading engine for Hyperliquid DEX. The system features:

- Python-based strategy logic and execution engine
- Rust decision kernel (`bt-signals`) shared across backtester, GPU sweep, and live trading (via PyO3 `bt-runtime` bridge)
- Rust backtester with optional CUDA GPU acceleration
- Unified daemon supporting paper, dry_live, and live trading modes
- Kernel orchestrator for gradual Python → Rust signal cutover with shadow mode tracking
- Risk manager with daily loss limits, drawdown kill-switches, rate limiting, and exposure caps
- Real-time market data via Rust WS sidecar (Unix socket)
- Hot-reloadable YAML configuration system with merge chain
- Strategy factory pipeline: nightly sweep → validate → deploy → paper → promote → live ramp
- Ensemble runner for parallel multi-strategy daemons

## Architecture

### Core Components

- **Strategy configuration**: `config/strategy_overrides.yaml` (hot-reloads via mtime polling)
- **Strategy defaults**: `strategy/mei_alpha_v1.py` → `_DEFAULT_STRATEGY_CONFIG` dict
- **Unified engine**: `engine/core.py` → `UnifiedEngine`
- **Daemon entrypoint**: `engine/daemon.py` — paper / dry_live / live mode selection
- **Paper trader**: `strategy/mei_alpha_v1.py` → `PaperTrader` class
- **Live trader**: `live/trader.py` → `LiveTrader` class
- **Kernel orchestrator**: `strategy/kernel_orchestrator.py` → feeds data to Rust decision kernel, routes `OrderIntent` to broker
- **Broker adapter**: `strategy/broker_adapter.py` → translates kernel `OrderIntent` to Hyperliquid orders
- **Shadow mode**: `strategy/shadow_mode.py` → parallel Python + kernel decision tracking with agreement alerting
- **Risk manager**: `engine/risk.py` → `RiskManager` — rate limits, drawdown kill, exposure caps, slippage guard
- **Order Management System**: `engine/oms.py` → `LiveOms` — durable intent/order/fill ledger for live trading
- **OMS reconciler**: `engine/oms_reconciler.py` → position/fill reconciliation
- **Alerting**: `engine/alerting.py` → Discord/Telegram via `openclaw message send`
- **Market data hub**: `engine/market_data.py` → candle + mid data from WS sidecar / SQLite / REST fallback
- **Strategy manager**: `engine/strategy_manager.py` → YAML hot-reload via mtime polling
- **Promoted config**: `engine/promoted_config.py` → loading promoted strategy configs
- **Event logger**: `engine/event_logger.py` → decision + trade event logging
- **SQLite logger**: `engine/sqlite_logger.py` → trade/candle persistence
- **Systemd watchdog**: `engine/systemd_watchdog.py` → sd_notify integration

### Databases

- **Paper DB**: `trading_engine.db` (SQLite)
- **Live DB**: `trading_engine_live.db` (SQLite)
- **Candle DBs**: `candles_dbs/candles_{1m,3m,5m,15m,30m,1h}.db`
- **Candle partitions**: `candles_dbs/partitions/{interval}/candles_{interval}_YYYY-MM.db`
- **Funding rates DB**: `candles_dbs/funding_rates.db`
- **BBO snapshots DB**: `candles_dbs/bbo_snapshots.db` (optional)
- **Universe history DB**: `candles_dbs/universe_history.db`
- **Market data DB**: `market_data.db`

### Candle Database Coverage

Hyperliquid only provides roughly the last 5,000 bars per interval for REST backfill (`candleSnapshot`). The figures below are the approximate *backfill window* implied by that limit.

The WS sidecar can retain an append-only local history beyond that window for selected intervals (see `AI_QUANT_CANDLE_PRUNE_DISABLE_INTERVALS`), so do not assume these DBs have fixed coverage. Always query the actual min/max timestamps when choosing backtest ranges.

When running backtests across multiple intervals, ALWAYS restrict all runs to the same date range for valid comparisons:

- `1m`: 3.5 days
- `3m`: 10 days
- `5m`: 17 days
- `15m`: 52 days
- `30m`: 104 days
- `1h`: 208 days

## Configuration System

### Merge Order

Configuration values are merged in this order (later values override earlier):

```
_DEFAULT_STRATEGY_CONFIG ← global YAML ← symbols.<SYM> YAML ← live YAML (if live mode)
```

### Key Configuration Sections

#### `trade`
- `sl_atr_mult`, `tp_atr_mult`: Stop-loss and take-profit multipliers
- `leverage`: Base leverage
- `allocation_pct`: Margin allocated per position (notional = margin × leverage)
- `min_atr_pct`: Minimum ATR percentage threshold (entries below this are skipped)
- `reentry_cooldown_minutes`: Cooldown period before re-entering same symbol
- `enable_pyramiding`: Enable/disable pyramid ADD orders
- `enable_partial_tp`: Enable/disable partial take-profit
- `enable_dynamic_sizing`: Dynamically scale position size by ADX/volatility

#### `market_regime`
- `enable_regime_filter`: Enable market regime filter
- `enable_auto_reverse`: Auto-reverse signals based on market breadth
- `bearish_breadth_threshold_pct`: Threshold for bearish regime detection
- `bullish_breadth_threshold_pct`: Threshold for bullish regime detection

#### `filters`
Entry gate filters:
- `enable_ranging_regime_filter`: Block entries in ranging markets
- `enable_anomaly_filter`: Block entries with anomaly detection
- `enable_btc_alignment_filter`: Require BTC direction alignment
- `enable_market_breadth_filter`: Filter by market-wide breadth

#### `thresholds.entry`
- `min_adx`: Minimum ADX required for entry
- `pullback_pct`: Required pullback percentage
- `slow_drift`: Slow drift threshold

#### `indicators`
Window sizes for technical indicators:
- `ema_fast`, `ema_slow`: EMA periods
- `adx_window`: ADX period
- `bb_window`: Bollinger Bands period
- `bb_std`: Bollinger Bands standard deviation

#### `engine`
- `interval`: Candle interval (e.g., `1h`, `3m`, `5m`)
- `entry_interval`: Interval for entry signal generation
- `exit_interval`: Interval for exit signal generation

**IMPORTANT**: The `engine.interval` parameter is NOT hot-reloadable. Changing it requires a service restart.

### Configuration Defaults

The code-level default for `entry_min_confidence` is `"high"`, which blocks 70-90% of entry signals. To allow all confidence levels (low/medium/high), explicitly set `entry_min_confidence: low` in your YAML configuration.

### Strategy Mode Switching

The engine supports an optional strategy-mode overlay selected via `AI_QUANT_STRATEGY_MODE`:

- `primary`: 30m/5m
- `fallback`: 1h/5m
- `conservative`: 1h/15m
- `flat`: safety profile

Mode overlays are defined under `modes:` in `config/strategy_overrides.yaml`. With `AI_QUANT_MODE_SWITCH_ENABLE=1`, the daemon auto-steps-down on kill events.

## Signal Flow

### Signal Generation and Processing

1. **Strategy analysis**: `mei_alpha_v1.analyze(df, sym, btc_bullish)` → `(signal, confidence, now_series)`
2. **Kernel orchestrator** (when enabled): feeds data to Rust decision kernel via `bt-runtime` PyO3 bridge
3. **Shadow mode** (optional): parallel Python + kernel comparison with agreement tracking
4. **Signal reversal** (optional): manual or auto-reverse based on market breadth
5. **Regime filter**: Block trades against market tide
6. **ATR floor enforcement**: Skip if `ATR% < min_atr_pct`
7. **Risk manager gates**: rate limits, exposure caps, drawdown checks
8. **Phase 1**: Collect entry candidates (exits run immediately per-symbol, not ranked)
9. **Phase 2**: Rank entries by score, execute in order

### Signal Ranking Algorithm

Entry signals are ranked using this formula:

```
score = confidence_rank * 100 + ADX
```

Where:
- High confidence: `confidence_rank = 2` → `score = 200 + ADX`
- Medium confidence: `confidence_rank = 1` → `score = 100 + ADX`
- Low confidence: `confidence_rank = 0` → `score = 0 + ADX`

Tiebreaker: Symbol name alphabetical order (ascending)

**Important**: Exits are executed immediately per-symbol and are NOT ranked. Pyramid ADD orders are also executed immediately when a same-direction position exists, NOT ranked.

### Audit Trail

The `now_series` dictionary carries audit flags for debugging:

- `_reversed_entry`: Signal was reversed (manual or auto)
- `_regime_blocked`: Entry blocked by regime filter
- `_atr_floored`: Entry skipped due to ATR floor
- `_market_breadth_pct`: Current market breadth percentage

## Rust Backtester

### Location and Structure

- **Location**: `backtester/` directory
- **Cargo workspace crates**:
  - `bt-core`: Simulation engine, decision kernel, indicators, config, state management
  - `bt-signals`: Signal generation (entry logic, gates, confidence) — shared across all paths
  - `bt-data`: SQLite candle loader (supports multi-DB and partition directories)
  - `bt-cli`: CLI entry point (replay, sweep, dump-indicators)
  - `bt-gpu`: CUDA GPU sweep + TPE Bayesian optimisation
  - `bt-runtime`: PyO3 bridge — exposes decision kernel to Python via JSON envelope API
  - `risk-core`: Shared, pure risk primitives (entry sizing, confidence tiers)

### Building

```bash
# Recommended build script (version-stamped)
python3 tools/build_mei_backtester.py

# GPU build (requires CUDA toolkit)
python3 tools/build_mei_backtester.py --gpu

# Manual cargo build (CPU-only)
cd backtester && cargo build --release -p bt-cli

# Manual GPU build
cd backtester && cargo build --release -p bt-cli --features gpu
```

On WSL2, you may need to set:
```bash
export LD_LIBRARY_PATH=/usr/lib/wsl/lib:$LD_LIBRARY_PATH
```

### Commands

- `replay`: Single-run backtest (supports `--init-state` for exported positions)
- `sweep`: Parallel parameter sweep (CPU or `--gpu`)
- `dump-indicators`: Export indicators for validation
- `--universe-filter`: Filter symbols by listing history from universe DB
- `--parity-mode`: GPU parity lanes (identical-symbol-universe / production)

### Indicator Parity Requirements

All indicators in the Rust backtester MUST match the Python `ta` library within **0.00005 absolute error**.

#### Critical Implementation Details

1. **EMA seeding**: Use `adjust=False` (pandas `ewm` method), NOT SMA seed. This matches `ta.trend.ema_indicator`.

2. **`vol_trend`**: Calculate as `SMA(vol, 5) > SMA(vol, 20)`, NOT `current_vol > SMA(vol, 5)`.

3. **`bb_width`**: Calculate as `(bb_high - bb_low) / Close`, NOT `(bb_high - bb_low) / bb_middle`.

### Validation Workflow

When modifying indicator logic in Rust:

1. Run `dump-indicators` to export Rust output
2. Compare against Python `ta` library output
3. Ensure all indicators match within 0.00005 absolute error
4. Document any intentional deviations

## Risk Manager

`engine/risk.py` → `RiskManager` provides runtime safety:

| Control | Env Variable | Default |
|---------|-------------|---------|
| Kill-switch (env) | `AI_QUANT_KILL_SWITCH` | (unset) |
| Kill-switch (file) | `AI_QUANT_KILL_SWITCH_FILE` | (unset) |
| Max drawdown % | `AI_QUANT_RISK_MAX_DRAWDOWN_PCT` | 0 (disabled) |
| Entry rate limit (global) | `AI_QUANT_RISK_MAX_ENTRY_ORDERS_PER_MIN` | 30 |
| Entry rate limit (per-symbol) | `AI_QUANT_RISK_MAX_ENTRY_ORDERS_PER_MIN_PER_SYMBOL` | 6 |
| Exit rate limit | `AI_QUANT_RISK_MAX_EXIT_ORDERS_PER_MIN` | 120 |
| Cancel rate limit | `AI_QUANT_RISK_MAX_CANCELS_PER_MIN` | 120 |
| Max notional per window | `AI_QUANT_RISK_MAX_NOTIONAL_PER_WINDOW_USD` | 0 (disabled) |
| Min order gap | `AI_QUANT_RISK_MIN_ORDER_GAP_MS` | 0 (disabled) |

Kill-switch modes: `close_only` (no new entries, exits allowed) or `halt_all` (no orders at all).

## Services (systemd)

### Service Management

- **Paper trader**: `systemctl --user restart openclaw-ai-quant-trader`
- **Live trader**: `systemctl --user restart openclaw-ai-quant-live`
- **WebSocket sidecar**: `systemctl --user restart openclaw-ai-quant-ws-sidecar`
- **Monitor**: `systemctl --user restart openclaw-ai-quant-monitor`
- **Factory timer**: `systemctl --user restart openclaw-ai-quant-factory.timer`
- **Log pruning timer**: `systemctl --user restart openclaw-ai-quant-prune-runtime-logs.timer`
- **Replay gate timer**: `systemctl --user restart openclaw-ai-quant-replay-alignment-gate.timer`

### Hot-reload Behaviour

- **YAML configuration changes**: Hot-reload automatically (no restart required)
- **Python code changes**: Require service restart
- **Engine interval changes**: Require service restart (not hot-reloadable)
- **Strategy mode changes** that affect `engine.interval`: Require service restart

## Development

### Python Environment

- **Python version**: >=3.12
- **Package manager**: `uv`

### Setup

```bash
uv sync --dev
```

### Testing

```bash
uv run pytest
```

Coverage is tracked for `sqlite_logger`, `heartbeat`, `risk`, and `executor` modules (see `pyproject.toml` for current thresholds).

### Linting and Formatting

```bash
# Lint
uv run ruff check engine strategy exchange live tools tests monitor

# Format
uv run ruff format engine strategy exchange live tools tests monitor
```

### Rust Development

```bash
# Build all Rust projects
cd backtester && cargo build --release
cd ws_sidecar && cargo build --release
cd hub && cargo build --release

# Run tests
cargo test

# Format
cargo fmt

# Lint
cargo clippy -- -D warnings
```

## Critical Rules for AI Assistants

### Security

1. **NEVER commit sensitive files**: `secrets.json`, `.env`, or any file containing private keys, wallet addresses, or API keys.

2. **Live trading safety**: Never disable kill switches (`AI_QUANT_KILL_SWITCH`, `AI_QUANT_HARD_KILL_SWITCH`) without explicit user confirmation.

### Configuration Management

3. **NEVER auto-tune strategy config via automated scripts**. Always use suggestion-only mode. This prevents accidental deployment of untested parameters. (Lesson from emergency rollback incident.)

4. **Code defaults vs YAML overrides**: The code-level default for `entry_min_confidence` is `"high"`, which blocks most entries. Remember to set `entry_min_confidence: low` in YAML to allow all confidence levels.

### Backtesting

5. **Date range consistency**: When comparing backtest results across different intervals, ALWAYS restrict all runs to the same date range. Different candle databases have different coverage spans.

6. **Indicator parity**: Backtester indicator calculations MUST match Python `ta` library within 0.00005 absolute error. Validate using `dump-indicators` after any indicator changes.

### Debugging

7. **Audit flags**: The `now_series` dictionary carries debugging flags (`_reversed_entry`, `_regime_blocked`, `_atr_floored`, `_market_breadth_pct`). Check these when investigating unexpected behaviour.

8. **When validating Rust indicators**: Always use `dump-indicators` and compare against Python `ta` output. Document the validation process.

9. **Shadow mode**: When the kernel orchestrator is running in shadow mode, check `decision_events` table and `ShadowDecisionTracker` agreement rates to diagnose discrepancies between Python and Rust signal paths.

### Deployment

10. **Replay alignment gate**: Deployment tooling (`paper_deploy.py`, `deploy_sweep.py`, `promote_to_live.py`) is fail-closed against the replay alignment blocker by default. Only override with `--ignore-replay-gate` for emergency workflows.

## Key Files Quick Reference

| File | Purpose |
|------|---------|
| `strategy/mei_alpha_v1.py` | Strategy signals + PaperTrader |
| `strategy/kernel_orchestrator.py` | Rust kernel orchestrator (PyO3 bridge) |
| `strategy/broker_adapter.py` | Kernel OrderIntent → Hyperliquid orders |
| `strategy/shadow_mode.py` | Shadow mode decision tracking |
| `strategy/reconciler.py` | Position reconciliation |
| `live/trader.py` | Live order execution wrapper |
| `exchange/executor.py` | HyperliquidLiveExecutor (SDK interface) |
| `engine/core.py` | Main trading loop (UnifiedEngine) |
| `engine/daemon.py` | Daemon entrypoint (paper / dry_live / live) |
| `engine/strategy_manager.py` | YAML hot-reload |
| `engine/market_data.py` | Candle/mid data hub |
| `engine/oms.py` | Order Management System |
| `engine/oms_reconciler.py` | OMS reconciliation |
| `engine/risk.py` | RiskManager — rate limits, drawdown, kill-switch |
| `engine/alerting.py` | Discord / Telegram notifications |
| `engine/promoted_config.py` | Promoted config loading |
| `config/strategy_overrides.yaml` | Live strategy config (hot-reloads) |
| `backtester/crates/bt-core/src/engine.rs` | Backtester simulation engine |
| `backtester/crates/bt-core/src/decision_kernel.rs` | Shared decision kernel |
| `backtester/crates/bt-signals/` | Signal generation (entry/gates/confidence) |
| `backtester/crates/bt-gpu/src/gpu_host.rs` | CUDA GPU dispatch |
| `backtester/crates/bt-runtime/src/lib.rs` | PyO3 bridge to Python |
| `backtester/crates/risk-core/` | Rust risk primitives |
| `tools/deploy_sweep.py` | Deploy sweep results to YAML |
| `tools/export_state.py` | Export trader state to JSON |
| `tools/factory_cycle.py` | Strategy factory automation |
| `tools/promote_to_live.py` | Paper → live promotion |
| `tools/flat_now.py` | Emergency flatten + pause |
| `tools/validate_config.py` | Config parity validation |
| `tools/rollback_to_last_good.py` | Config rollback |
| `factory_run.py` | Strategy factory entrypoint |

## Additional Resources

- **Strategy version history**: `strategy_changelog.json` (runtime-generated, gitignored)
- **Project management**: `pyproject.toml`
- **Version**: `VERSION` (single source of truth; all Cargo.toml and pyproject.toml must match)
- **Dependencies**: Python managed via `uv` (see `pyproject.toml`); Rust via Cargo
- **Operations runbook**: `docs/runbook.md`
- **Strategy lifecycle**: `docs/strategy_lifecycle.md`
- **Success metrics**: `docs/success_metrics.md`
- **Release process**: `docs/release_process.md`

## Common Patterns

### Reading Strategy Config

```python
from engine.strategy_manager import StrategyManager

strategy = StrategyManager(yaml_path="config/strategy_overrides.yaml")
config = strategy.get_config(symbol="BTC")
```

### Accessing Market Data

```python
from engine.market_data import MarketDataHub

market = MarketDataHub()
df = market.get_candles(symbol="BTC", interval="1h", lookback_bars=200)
```

### Running Backtests

```bash
# Single run
mei-backtester replay --candles-db candles_dbs/candles_1h.db

# Parameter sweep
mei-backtester sweep --sweep-config sweeps/smoke.yaml

# Replay with exported state
python tools/export_state.py --source paper --output /tmp/state.json
mei-backtester replay --init-state /tmp/state.json --trades
```

### Emergency Stop

```bash
# File-based kill-switch (no restart needed)
echo "close_only" > /tmp/ai-quant-kill

# Emergency flatten
python tools/flat_now.py --kill-file /tmp/ai-quant-kill --pause-mode close_only --paper --yes
```

## Troubleshooting

### Common Issues

1. **Service won't start**: Check systemd logs with `journalctl --user -u openclaw-ai-quant-trader -f`

2. **YAML changes not taking effect**: Verify mtime polling is working. Check engine logs for "Config reloaded" messages.

3. **Indicator mismatch in backtester**: Run `dump-indicators` and compare against Python `ta` output. Check EMA seeding, `vol_trend`, and `bb_width` implementations.

4. **GPU build fails**: Ensure CUDA toolkit is installed. On WSL2, set `LD_LIBRARY_PATH=/usr/lib/wsl/lib:$LD_LIBRARY_PATH`.

5. **Unexpected entry filtering**: Check `entry_min_confidence` setting. Code default is `"high"`, which blocks most entries. Set to `"low"` in YAML to allow all confidence levels.

6. **Kernel/Python signal divergence**: Check shadow mode agreement rates in `decision_events` table. Use `ShadowDecisionReport` to diagnose which signals diverge.

7. **OMS intent failures**: If live entries fail, check `AI_QUANT_OMS_REQUIRE_INTENT_FOR_ENTRY` (default: enabled, fail-closed). Review OMS tables for duplicate detection.

8. **Deployment blocked by replay gate**: Check `/tmp/openclaw-ai-quant/replay_gate/release_blocker.json`. Use `--ignore-replay-gate` only for emergency workflows.

## Best Practices

1. **Always read the code before suggesting changes**. Understand the existing implementation.

2. **Test configuration changes in paper mode first** before deploying to live trading.

3. **Validate backtester changes** using `dump-indicators` and comparison against Python `ta` library.

4. **Document significant changes** in commit messages and consider updating `strategy_changelog.json`.

5. **Preserve test coverage**. Check `pyproject.toml` for current coverage requirements.

6. **Use YAML for strategy tuning**, not Python code edits. YAML changes hot-reload; code changes require restart.

7. **When in doubt, ask the user** before making risky changes (especially for live trading or automated parameter tuning).

8. **Version consistency**: When bumping versions, use `tools/release/set_version.sh` and verify with `tools/release/check_versions.sh`.
