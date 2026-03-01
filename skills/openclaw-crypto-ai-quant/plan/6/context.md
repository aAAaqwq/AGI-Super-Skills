# OpenClaw AI Quant: Full Codebase Context

## 1. Purpose and scope

This repository implements a production crypto perpetual futures trading platform for Hyperliquid, with one shared strategy stack used across:

1. GPU parameter sweep and optimisation.
2. CPU backtesting and replay validation.
3. Paper trading execution.
4. Live trading execution.

The strategic objective is deterministic decision parity and operational trust: candidate configurations discovered in sweep should remain behaviourally consistent when replayed on CPU, then exercised in paper, and later promoted to live under explicit gates.

This document describes architecture, structure, data flow, runtime responsibilities, and delivery-critical trust boundaries.

## 2. Repository structure (top-level map)

Key top-level folders and files:

1. `engine/`
Core runtime framework (daemon entrypoint, unified loop, risk, OMS, market data, strategy hot reload, promoted config loading, alerting).

2. `strategy/`
Strategy implementation and orchestration glue, including Python strategy logic, Rust kernel orchestration bridge, broker adapter, reconciliation, and shadow comparison helpers.

3. `live/`
Live execution wrapper and production-facing live trader integration path.

4. `exchange/`
Exchange execution primitives and Hyperliquid integration layer used by live order flow.

5. `backtester/`
Rust workspace containing the simulation engine, shared decision kernel, signal crate, runtime bridge, data loader, and GPU sweep stack.

6. `tools/`
Operational and factory tooling (build, sweep orchestration, deployment, promotion, rollback, export/import state, diagnostics, gates).

7. `config/`
Runtime YAML strategy overrides and mode overlays.

8. `docs/`
Runbooks, release flow, lifecycle guidance, and architecture notes.

9. `factory_run.py`
Main strategy factory entrypoint.

10. `VERSION`
Single source version marker expected to match Rust/Python package versions.

11. `AGENTS.md`
Operational and safety rules for AI-assisted edits and deployment behaviour.

## 3. System architecture (runtime planes)

The platform has four cooperating planes:

1. Decision plane.
Signal evaluation and exit/entry intent generation. The intended canonical path is Rust decision kernel SSOT, bridged into Python runtime via `bt-runtime`.

2. Execution plane.
Order intent normalisation, risk gating, order placement, and fill reconciliation through OMS and exchange adapters.

3. Data plane.
Candle, funding, and optional BBO data ingestion from WS sidecar, SQLite stores, and bounded REST fallback.

4. Control plane.
Factory cycle, replay gates, config promotion/deployment, mode switching, and systemd orchestration.

## 4. Core Python runtime architecture

### 4.1 Daemon and engine loop

1. `engine/daemon.py`
Bootstraps mode (`paper`, `dry_live`, `live`), wiring strategy manager, market data, decision provider, and runtime services.

2. `engine/core.py`
`UnifiedEngine` orchestrates per-cycle processing:
collect market snapshots, evaluate decisions, run risk checks, dispatch intents, and persist audit artefacts.

### 4.2 Strategy configuration and hot reload

1. `engine/strategy_manager.py`
Maintains merged strategy config with mtime polling.

2. Merge precedence:
`_DEFAULT_STRATEGY_CONFIG` (code) <- global YAML <- symbol YAML <- live overlay.

3. Important behaviour:
Most strategy values hot reload; interval changes (`engine.interval` and related mode-dependent interval shifts) require restart.

### 4.3 Decision orchestration

1. `strategy/kernel_orchestrator.py`
Bridge layer from Python runtime context into Rust decision kernel request/response envelopes.

2. `strategy/shadow_mode.py`
Runs comparison path (legacy Python vs kernel output) for agreement tracking during migration and hardening.

3. `strategy/mei_alpha_v1.py`
Contains strategy defaults, analysis helpers, and paper trader utilities; still hosts legacy support surfaces and persistence helpers used by runtime.

### 4.4 Execution and OMS

1. `engine/oms.py`
Durable intent/order/fill pipeline for live and paper consistency with reconciliation-friendly persistence.

2. `engine/oms_reconciler.py`
Detects and heals ledger/state divergence between expected position state and exchange-confirmed state.

3. `strategy/broker_adapter.py`
Maps kernel `OrderIntent` to exchange-compatible execution payloads.

4. `exchange/executor.py`
Hyperliquid-facing execution implementation.

### 4.5 Risk and safety

1. `engine/risk.py`
Drawdown control, kill-switch interpretation, rate limits, exposure limits, and order gap constraints.

2. Kill controls:
Environment and file-driven kill-switches support `close_only` and `halt_all`.

## 5. Rust architecture (shared deterministic core)

`backtester/` is a Rust workspace with crates:

1. `bt-core`
Simulation engine, shared decision kernel, state transitions, indicators, and replay mechanics.

2. `bt-signals`
Entry/gate/confidence logic reused across compute paths.

3. `bt-data`
SQLite and partition-aware candle loading.

4. `bt-cli`
Operational CLI for replay/sweep/dump workflows.

5. `bt-gpu`
CUDA-enabled parallel sweep and search tooling.

6. `bt-runtime`
PyO3 binding exposing Rust decision kernel to Python runtime.

7. `risk-core`
Pure shared risk primitives.

Design intent:
one core decision/execution logic source in Rust, consumed by both offline simulation and online runtime through a narrow binding contract.

## 6. Data architecture and persistence

### 6.1 SQLite databases

Key stores:

1. `trading_engine.db` (paper runtime state and logs).
2. `trading_engine_live.db` (live runtime state and logs).
3. `candles_dbs/candles_{interval}.db` and monthly partitions.
4. `candles_dbs/funding_rates.db`.
5. `candles_dbs/bbo_snapshots.db` (optional, large footprint).
6. `candles_dbs/universe_history.db`.
7. `market_data.db`.

### 6.2 Runtime audit surfaces

Commonly referenced logical tables:

1. `trades`
Execution outcomes and financial fields.

2. `signals`
Signal emissions and confidence metadata.

3. `decision_events`
Decision-level audit with context, config fingerprinting, and kernel tracing fields.

4. `audit_events`
Runtime-level observability events.

Operational direction is to preserve run-level and config-level traceability for replay and deployment trust.

### 6.3 Candle coverage constraints

Hyperliquid REST backfill is bounded to approximately 5,000 bars per interval. Effective historical span therefore depends on interval. Comparative backtests must align date windows across intervals to avoid false optimisation signals from uneven data availability.

## 7. Strategy factory cycle architecture

Current intended six-step pipeline:

1. Sweep large search space on GPU.
2. Keep top-N by raw objective (for example top 1,000 PnL).
3. Rank shortlists per channel profile (efficient/growth/conservative).
4. Replay shortlisted candidates on CPU for parity and robustness checks.
5. Apply promotion gates.
6. Deploy selected configs into paper services and later promote to live.

Operationally, Step 4 is the parity checkpoint where GPU/CPU mismatches surface immediately. This stage must consume unmutated candidate parameters to preserve chain-of-trust from Step 1 results.

## 8. Chain-of-trust and SSOT model

### 8.1 Intended SSOT chain

1. Rust decision kernel defines canonical state transitions and decision outputs.
2. GPU sweep and CPU replay consume the same Rust logic.
3. Runtime decision provider in daemon uses the Rust kernel (not legacy candle decision path).
4. Paper/live records include sufficient fingerprints to attribute behaviour to exact code/config run context.

### 8.2 Why Python still exists

Python remains as:

1. Runtime orchestration and service wiring.
2. Exchange/OMS integration and safety controls.
3. Data ingestion and persistence coordination.
4. Migration scaffolding and observability.

This is an architecture split, not a decision-logic split: decision SSOT should stay in Rust while Python handles control and integration surfaces.

## 9. Services and operational layout

Systemd user services typically include:

1. Hub API/frontend components.
2. Paper trader instances (multi-mode roles).
3. Live trader daemon.
4. WS sidecar.
5. Factory/replay timers.

Two behavioural rules matter operationally:

1. YAML strategy changes usually hot reload.
2. Code and interval-mode shifts require service restart.

## 10. Build, test, and release workflow

### 10.1 Python

1. Environment via `uv`.
2. Lint/format through Ruff.
3. Tests through `pytest`.

### 10.2 Rust

1. Build per workspace crate or top-level release build.
2. GPU paths require CUDA environment and WSL runtime linkage where relevant.

### 10.3 Version discipline

`VERSION` is the master version marker; release scripts are expected to keep Cargo and Python metadata aligned.

## 11. Architectural risks and delivery-sensitive points

1. Parameter mutation between sweep output and replay input breaks parity trust.
2. Legacy path leakage (for example old provider modes) can invalidate SSOT assumptions.
3. Runtime state bootstrap mismatches can create divergence between database state and in-memory kernel state.
4. Gate semantics must be baseline-aware, particularly after axis/schema refactors.
5. Promotion/deployment sequencing must avoid self-invalidating reference points.

## 12. Recommended working contract for current delivery phase

1. Preserve Rust decision SSOT; avoid reopening legacy decision providers.
2. Keep candidate generation as a zero-mutation transform from selected sweep row to replay/deploy artefact.
3. Treat Step 4 CPU replay as mandatory proof, not optional validation.
4. Maintain run/config fingerprints across decision, trade, and audit writes.
5. Keep factory pipeline deterministic and resumable with explicit run identifiers and gate outputs.

## 13. Quick component index (where to start reading)

1. Runtime loop: `engine/core.py`
2. Daemon bootstrap: `engine/daemon.py`
3. Strategy defaults and persistence helpers: `strategy/mei_alpha_v1.py`
4. Kernel bridge: `strategy/kernel_orchestrator.py`
5. OMS and reconciliation: `engine/oms.py`, `engine/oms_reconciler.py`
6. Live wrapper: `live/trader.py`
7. Exchange execution: `exchange/executor.py`
8. Rust kernel/state engine: `backtester/crates/bt-core/src/decision_kernel.rs`
9. Sweep/GPU orchestration: `backtester/crates/bt-gpu/`
10. Factory/deploy tooling: `factory_run.py`, `tools/factory_cycle.py`, `tools/deploy_sweep.py`, `tools/promote_to_live.py`

## 14. Summary

This codebase is a hybrid control-and-kernel architecture: Python operates orchestration, risk, persistence, and exchange integration; Rust provides the canonical decision and simulation core. Delivery confidence depends on preserving this contract end-to-end through the factory pipeline, with strict parity checks and deterministic artefacts between sweep, replay, paper, and live.
