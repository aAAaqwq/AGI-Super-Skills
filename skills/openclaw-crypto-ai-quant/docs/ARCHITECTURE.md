# System Architecture

## Overview

![System Architecture](diagrams/architecture.svg)

## Components

### 1. Unified Trading Engine (`engine/`)

The core Python daemon that runs paper, dry_live, and live modes from a single entrypoint.

- **Daemon** (`engine/daemon.py`): Entrypoint — selects mode via `AI_QUANT_MODE` env var, initialises all subsystems.
- **UnifiedEngine** (`engine/core.py`): Main trading loop — polls candle keys per symbol, runs strategy analysis only when data changes, two-phase collect-rank-execute for entries.
- **StrategyManager** (`engine/strategy_manager.py`): Hot-reloads `config/strategy_overrides.yaml` via mtime polling. No `importlib.reload` — pure YAML merging.
- **MarketDataHub** (`engine/market_data.py`): Reads mids and candles from WS sidecar first, falls back to SQLite candles table, then REST `candleSnapshot`.
- **RiskManager** (`engine/risk.py`): Rate limiting (global + per-symbol entries, exits, cancels), drawdown kill-switch, daily loss limits, notional caps, slippage guard, file-based and env-based kill-switch polling.
- **LiveOms** (`engine/oms.py`): Durable Order Management System for live trading — intent rows (restart-safe dedupe), orders, fills (deduped by hash+tid), fill-to-intent matching via `client_order_id` with time-proximity fallback.
- **OMS Reconciler** (`engine/oms_reconciler.py`): Reconciles OMS state against exchange positions/fills.
- **Alerting** (`engine/alerting.py`): Discord / Telegram notifications via `openclaw message send`.
- **Event Logger** (`engine/event_logger.py`): Decision + trade event logging for audit trail.
- **Promoted Config** (`engine/promoted_config.py`): Loading promoted strategy configs from the factory pipeline.
- **SQLite Logger** (`engine/sqlite_logger.py`): Trade, candle, and position state persistence.
- **REST Client** (`engine/rest_client.py`): Hyperliquid REST API client.
- **Systemd Watchdog** (`engine/systemd_watchdog.py`): `sd_notify` integration.

File lock prevents duplicate daemons: `ai_quant_paper.lock` or `ai_quant_live.lock` (configurable via `AI_QUANT_LOCK_PATH`).

### 2. Strategy Layer (`strategy/`)

- **Mei Alpha v1** (`strategy/mei_alpha_v1.py`): Signal generation (`analyze()`), exit condition checking, `PaperTrader` class. Multi-indicator with confidence tiers (low/medium/high), ATR-based SL/TP, trailing stops, pyramiding, partial TP.
- **Kernel Orchestrator** (`strategy/kernel_orchestrator.py`): Feeds candle data and prices to the Rust decision kernel via `bt-runtime` (PyO3 bridge), routes resulting `OrderIntent` to the broker adapter. Supports `KERNEL_ONLY` and `SHADOW` modes.
- **Broker Adapter** (`strategy/broker_adapter.py`): Translates kernel `OrderIntent` dicts to Hyperliquid exchange operations (`market_open`, `market_close`). Handles szDecimals rounding, slippage, rate limiting.
- **Shadow Mode** (`strategy/shadow_mode.py`): Parallel Python + Rust kernel decision tracking. `ShadowDecisionTracker` records agreement rates over a rolling window and raises alerts when agreement drops below threshold.
- **Reconciler** (`strategy/reconciler.py`): Position reconciliation logic.
- **Event ID** (`strategy/event_id.py`): Deterministic event ID generation.

### 3. Exchange Adapters (`exchange/`)

- **HyperliquidLiveExecutor** (`exchange/executor.py`): SDK interface — `market_open`, `market_close`, position queries.
- **WebSocket Client** (`exchange/ws.py`): Streams `allMids`, `bbo`, `candle` for market data; `userFills`, `orderUpdates`, `userFundings` for live mode.
- **Sidecar Client** (`exchange/sidecar.py`): Unix socket client for the Rust WS sidecar.
- **Meta** (`exchange/meta.py`): Hyperliquid metadata — sz/price rounding, symbol info.
- **Market Watch** (`exchange/market_watch.py`): Market-wide utilities.

### 4. Live Trader (`live/`)

- **LiveTrader** (`live/trader.py`): Wraps strategy logic with real order execution. Uses the same `mei_alpha_v1.analyze()` and `PaperTrader.check_exit_conditions()` as paper mode. Places real perps orders via SDK. Reconciles positions/equity from `Info.user_state()` periodically.

Safety gates for live mode:
- `AI_QUANT_LIVE_ENABLE=1` + `AI_QUANT_LIVE_CONFIRM=I_UNDERSTAND_THIS_CAN_LOSE_MONEY`
- `AI_QUANT_KILL_SWITCH`: `close_only` or `halt_all`
- `AI_QUANT_KILL_SWITCH_FILE`: file-based kill (no restart needed)
- `AI_QUANT_HARD_KILL_SWITCH`: blocks ALL orders including exits

### 5. WS Sidecar (`ws_sidecar/`)

High-performance Rust binary that streams Hyperliquid WebSocket data.

- Maintains candle DBs for multiple intervals (1m, 3m, 5m, 15m, 30m, 1h)
- Communicates with trading engine via Unix socket
- Bootstraps historical candles automatically on fresh databases
- Optional append-only retention (no pruning) for selected intervals via `AI_QUANT_CANDLE_PRUNE_DISABLE_INTERVALS`
- Optional BBO snapshot storage for slippage modelling

### 6. Monitor Dashboard (`monitor/`)

Read-only Python web dashboard for real-time monitoring.

- Reads SQLite databases (paper + live)
- Displays live mids from WS sidecar via SSE streaming
- Shows position state, recent trades, performance metrics
- Optional Hyperliquid REST balance fetch (live mode)
- No write access to databases or configuration

### 7. Hub Dashboard (`hub/`)

Rust (Axum) + Svelte web application providing an alternative monitoring interface.

### 8. Rust Backtester (`backtester/`)

High-performance historical simulation engine. V8 is the sole backtester — all execution paths (CPU replay, GPU sweep, live/paper via PyO3 bridge) share a single decision kernel.

**Cargo workspace crates:**

| Crate | Purpose |
|-------|---------|
| `bt-core` | Simulation engine, decision kernel, indicators, config, state management, accounting |
| `bt-signals` | Signal generation — entry logic, gates, confidence tiers. Shared across all paths |
| `bt-data` | SQLite candle loader (supports multi-DB and partition directories) |
| `bt-cli` | CLI entry point — `replay`, `sweep`, `dump-indicators` (clap) |
| `bt-gpu` | CUDA GPU parallel sweep + TPE Bayesian optimisation |
| `bt-runtime` | PyO3 bridge — exposes decision kernel to Python via JSON envelope API |
| `risk-core` | Shared, pure risk primitives (entry sizing, confidence tiers) |

**CLI commands:**
- `replay`: Single-run backtest (supports `--init-state` for exported positions)
- `sweep`: Parallel parameter sweep (CPU or `--gpu`)
- `dump-indicators`: CSV indicator export for parity validation

### 9. Strategy Factory (`factory_run.py`, `tools/factory_cycle.py`)

Nightly pipeline for automated strategy generation and deployment:

1. **Sweep**: GPU parameter sweep to find optimal configs
2. **Validate**: OOS walk-forward + slippage stress test + concentration checks
3. **Deploy to paper**: Auto-deploy top candidates
4. **Gate checks**: Paper performance gates (PF ≥ 1.2, DD < 10%, etc.)
5. **Promote to live**: Gradual ramp (25% → 50% → 100% sizing)

See [strategy_lifecycle.md](strategy_lifecycle.md) for the full state machine and [success_metrics.md](success_metrics.md) for gate thresholds.

### 10. Signal Ranking

Two-phase collect-rank-execute system:

- **Phase 1**: Collect entry candidates (exits run immediately per-symbol, not ranked)
- **Phase 2**: Rank entries by `score = confidence_rank × 100 + ADX`, execute in order

Tiebreaker: symbol name alphabetical order. Pyramid ADD orders execute immediately (not ranked).

### 11. Market Breadth & Auto-Reverse

- **Market breadth**: Percentage of watchlist symbols with `EMA_fast > EMA_slow`. Acts as regime filter to block trades against the prevailing market tide.
- **Auto-reverse**: Fades noise in choppy, range-bound markets by reversing position direction to fade false breakouts.

## Databases

| Database | Path | Purpose |
|----------|------|---------|
| Paper DB | `trading_engine.db` | Paper trades, positions, candles, runtime logs |
| Live DB | `trading_engine_live.db` | Live trades, positions, OMS ledger |
| Candle DBs | `candles_dbs/candles_{interval}.db` | OHLCV candle data per interval |
| Candle partitions | `candles_dbs/partitions/{interval}/` | Monthly archive partitions |
| Funding rates | `candles_dbs/funding_rates.db` | Historical funding rates |
| BBO snapshots | `candles_dbs/bbo_snapshots.db` | Best bid/ask snapshots (optional) |
| Universe history | `candles_dbs/universe_history.db` | Symbol listing/delisting tracking |
| Market data | `market_data.db` | WS sidecar market data |

## Project Structure

```
.
├── engine/                    # Unified trading engine (Python)
│   ├── core.py                # UnifiedEngine — main trading loop
│   ├── daemon.py              # Entrypoint (paper / dry_live / live)
│   ├── market_data.py         # MarketDataHub — candle + mid data
│   ├── strategy_manager.py    # YAML hot-reload via mtime polling
│   ├── oms.py                 # Order Management System
│   ├── oms_reconciler.py      # OMS reconciliation
│   ├── risk.py                # RiskManager
│   ├── alerting.py            # Discord / Telegram notifications
│   ├── event_logger.py        # Decision + trade event logging
│   ├── promoted_config.py     # Promoted config loading
│   ├── rest_client.py         # Hyperliquid REST client
│   ├── sqlite_logger.py       # SQLite persistence
│   └── systemd_watchdog.py    # sd_notify watchdog
├── strategy/                  # Strategy implementations
│   ├── mei_alpha_v1.py        # Signals, confidence, PaperTrader
│   ├── kernel_orchestrator.py # Rust kernel orchestrator (PyO3)
│   ├── broker_adapter.py      # OrderIntent → exchange orders
│   ├── shadow_mode.py         # Shadow mode decision tracking
│   ├── reconciler.py          # Position reconciliation
│   └── event_id.py            # Deterministic event IDs
├── exchange/                  # Exchange adapters
│   ├── executor.py            # HyperliquidLiveExecutor
│   ├── ws.py                  # WebSocket client
│   ├── sidecar.py             # WS sidecar Unix socket client
│   ├── meta.py                # Metadata + sz rounding
│   └── market_watch.py        # Market watch utilities
├── live/                      # Live trading
│   └── trader.py              # LiveTrader
├── monitor/                   # Real-time dashboard (Python)
│   ├── server.py              # HTTP + SSE server
│   └── heartbeat.py           # Heartbeat checks
├── hub/                       # Hub dashboard (Rust + Svelte)
│   ├── src/                   # Axum backend
│   └── frontend/              # Svelte frontend
├── config/                    # Runtime configuration
│   ├── *.example.yaml         # YAML config templates
│   └── secrets.json.example   # Secrets template
├── tools/                     # Operational tools (60+ scripts)
│   ├── deploy_sweep.py        # Deploy sweep results to YAML
│   ├── export_state.py        # Export paper/live state to JSON
│   ├── factory_cycle.py       # Strategy factory automation
│   ├── promote_to_live.py     # Paper → live promotion
│   ├── paper_deploy.py        # Paper deployment
│   ├── flat_now.py            # Emergency flatten + pause
│   ├── manual_trade.py        # Manual trade entry/exit
│   ├── validate_config.py     # Config parity validation
│   ├── reality_check.py       # Quick trading diagnostics
│   ├── rollback_to_last_good.py
│   ├── build_mei_backtester.py # Backtester build script
│   ├── release/               # Version bump + asset build
│   └── ...                    # Audit, analysis, CI tools
├── backtester/                # Rust backtester (Cargo workspace)
│   ├── crates/bt-core/        # Simulation engine + indicators
│   ├── crates/bt-signals/     # Decision kernel (shared signal logic)
│   ├── crates/bt-data/        # SQLite candle loader
│   ├── crates/bt-cli/         # CLI (replay, sweep, dump-indicators)
│   ├── crates/bt-gpu/         # CUDA GPU sweep + TPE
│   ├── crates/bt-runtime/     # PyO3 bridge to Python
│   ├── crates/risk-core/      # Rust risk primitives
│   └── sweeps/                # Sweep configs + runner scripts
├── ws_sidecar/                # Rust WS sidecar
├── analysis/                  # Post-trade analysis
├── research/                  # Strategy research modules
├── schemas/                   # JSON schemas (GPU candidate, etc.)
├── scripts/                   # Shell scripts (CI gates, run_paper/live)
├── sweep_full/                # Full sweep runner scripts
├── systemd/                   # Service + timer templates
├── tests/                     # Python tests (113 files)
├── docs/                      # Documentation
├── plan/                      # Planning documents
├── factory_run.py             # Strategy factory entrypoint
├── diag_*.py                  # Diagnostic scripts
├── pyproject.toml             # Python project config (uv)
└── VERSION                    # Single source of truth for version
```

## Configuration Merge Order

```
_DEFAULT_STRATEGY_CONFIG ← global YAML ← symbols.<SYM> YAML ← live YAML (if live mode)
```

The `engine.interval` parameter is NOT hot-reloadable — changing it requires a service restart. All other YAML parameters hot-reload via mtime polling.

## Data Flow

### Market Data Path

![Market Data Path](diagrams/market-data-path.svg)

1. **Hyperliquid** → WS streams (`allMids`, `bbo`, `candle`)
2. **WS Sidecar** receives, persists candles to SQLite DBs, serves via Unix socket
3. **MarketDataHub** reads from sidecar (preferred), falls back to SQLite → REST
4. **UnifiedEngine** polls per-symbol candle keys; only fetches full DataFrame when data changes

### Signal Path

![Signal Path](diagrams/signal-path.svg)

1. `mei_alpha_v1.analyze(df, sym, btc_bullish)` → `(signal, confidence, now_series)`
2. Kernel orchestrator (optional): Rust decision kernel via `bt-runtime` PyO3 bridge
3. Shadow mode (optional): parallel comparison, agreement tracking
4. Signal reversal (optional): manual or auto-reverse based on market breadth
5. Regime filter → ATR floor → Risk manager gates
6. Phase 1: Collect candidates (exits run immediately)
7. Phase 2: Rank entries by score, execute in order

### Order Execution Path (Live)

![Order Execution Path](diagrams/order-execution-path.svg)

1. Entry/exit decision → `OrderIntent`
2. OMS creates intent row (dedupe guard)
3. Broker adapter translates to SDK call (`market_open` / `market_close`)
4. `HyperliquidLiveExecutor` sends order
5. Fill arrives via `userFills` WS stream → OMS matches fill to intent
6. SQLite logger persists trade record

## References

- [runbook.md](runbook.md) — Operations procedures
- [strategy_lifecycle.md](strategy_lifecycle.md) — Config state machine
- [success_metrics.md](success_metrics.md) — Risk limits and promotion criteria
- [backtester/README.md](../backtester/README.md) — Backtester details
- [monitor/README.md](../monitor/README.md) — Dashboard details
- [engine/README.md](../engine/README.md) — Engine internals
