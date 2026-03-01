# Development Guide

This repository contains Python (trading engine, strategies, monitoring) and Rust (backtester, WS sidecar, hub dashboard) components.

## Python (uv / ruff / pytest)

Managed by `uv`:

- Project config: `pyproject.toml`
- Lockfile: `uv.lock`
- Dev venv: `.venv/` (uv-managed, gitignored)
- Runtime venv: `venv/` (used by `run_live.sh` / `run_paper.sh` systemd scripts)

### Setup

```bash
uv sync --dev
```

### Lint / Format

```bash
uv run ruff check engine strategy exchange live tools tests monitor
uv run ruff format engine strategy exchange live tools tests monitor
```

### Tests

```bash
uv run pytest
```

Coverage is enforced for `engine/sqlite_logger.py`, `monitor/heartbeat.py`, `engine/risk.py`, and `exchange/executor.py` (see `pyproject.toml` for current thresholds).

## Rust

Three Rust projects: backtester, WS sidecar, and hub dashboard.

### Build

```bash
# Backtester (CPU) — recommended build script (version-stamped)
python3 tools/build_mei_backtester.py

# Backtester (GPU, requires CUDA toolkit)
python3 tools/build_mei_backtester.py --gpu

# Manual backtester build
cd backtester && cargo build --release

# WS Sidecar
cd ws_sidecar && cargo build --release

# Hub dashboard (Rust + Svelte)
cd hub && cargo build --release
```

### Test

```bash
cd backtester && cargo test
cd ws_sidecar && cargo test
cd hub && cargo test
```

### Lint

```bash
cargo fmt --check
cargo clippy -- -D warnings
```

### Notes

- Cargo.lock files are tracked in version control for reproducibility.
- GPU builds require NVIDIA CUDA Toolkit. On WSL2: `export LD_LIBRARY_PATH=/usr/lib/wsl/lib:$LD_LIBRARY_PATH`.
- The backtester binary supports `mei-backtester --version` (version-stamped at build time).

## Project Structure

- `engine/` — Core trading engine (Python): daemon, risk manager, OMS, market data hub, alerting
- `strategy/` — Strategy implementations (Python): signals, kernel orchestrator, shadow mode, broker adapter
- `exchange/` — Exchange adapters (Python): Hyperliquid executor, WebSocket client, sidecar client
- `live/` — Live trading wrapper (Python)
- `monitor/` — Read-only web dashboard (Python)
- `hub/` — Hub dashboard (Rust/Axum + Svelte): candle charts, trade journal, service management
- `tools/` — Operational tools (60+ Python scripts): deploy, export, validate, factory, release
- `config/` — Runtime configuration (YAML, hot-reloads via mtime polling)
- `backtester/` — Rust backtester (Cargo workspace): bt-core, bt-signals, bt-data, bt-cli, bt-gpu, bt-runtime, risk-core
- `ws_sidecar/` — Rust WebSocket market data sidecar
- `research/` — Strategy research modules
- `analysis/` — Post-trade analytics
- `schemas/` — JSON schemas (GPU candidate, etc.)
- `scripts/` — Shell scripts (CI gates, run_paper/live)
- `systemd/` — Service + timer templates
- `tests/` — Python tests (113 files)
- `docs/` — Documentation
- `plan/` — Historical planning documents

## Version Governance

`VERSION` is the single source of truth. All `Cargo.toml` and `pyproject.toml` must match. See [release_process.md](release_process.md).

```bash
# Bump version
tools/release/set_version.sh 0.1.1

# Verify consistency
tools/release/check_versions.sh
```

## Configuration

Strategy parameters live in `config/strategy_overrides.yaml` and hot-reload at runtime (no restart needed). The `engine.interval` parameter is the exception — changing it requires a service restart.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full configuration merge order and data flow.
