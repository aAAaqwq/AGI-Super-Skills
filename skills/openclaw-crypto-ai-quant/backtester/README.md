# Mei Backtester (V8 — Single Source of Truth)

High-performance Rust backtesting simulator for the Mei Alpha strategy.

> **V8 is the sole backtester.** The legacy main-branch backtester has been
> archived as `archive/main-backtester-v6`. All execution paths (CPU replay,
> GPU sweep, live/paper trading via PyO3 bridge) share a single decision
> kernel (`decision_kernel.rs`). See the V8 SSOT migration issues AQC-711
> through AQC-762 for details.

## Build

```bash
# From the repo root
python3 tools/build_mei_backtester.py

# Optional GPU build (requires CUDA toolchain)
python3 tools/build_mei_backtester.py --gpu
```

The binary is version-stamped at build time and supports:

```bash
mei-backtester --version
```

## Commands

### replay — Single backtest

```bash
mei-backtester replay [OPTIONS]
```

### sweep — Parallel parameter sweep

```bash
mei-backtester sweep --sweep-config sweep.yaml [OPTIONS]
```

### dump-indicators — CSV indicator export

```bash
mei-backtester dump-indicators --symbol BTC [OPTIONS]
```

### Candle DB sets (AQC-204)

The candle DB flags (`--candles-db`, `--exit-candles-db`, `--entry-candles-db`) accept:

- A single SQLite DB file path
- A comma-separated list of paths (files and/or directories)
- A directory containing partition DB files (all `*.db` files are loaded)

Examples:

```bash
# Hot DB only (single file)
mei-backtester replay --candles-db candles_dbs/candles_5m.db

# Hot DB + monthly partitions directory
mei-backtester replay --candles-db candles_dbs/candles_5m.db,candles_dbs/partitions/5m
```

### Universe filter (AQC-205)

If you maintain a universe history DB via `tools/sync_universe_history.py`, you can optionally filter backtests to symbols that were active during the tested period:

```bash
mei-backtester replay --universe-filter
mei-backtester sweep --universe-filter
```

The universe DB defaults to `<candles_db_dir>/universe_history.db`. Override with `--universe-db`.

### GPU smoke parity lanes (AQC-176)

For 1h/3m smoke comparisons, use explicit parity lanes:

- Lane A (`--parity-mode identical-symbol-universe`): CPU and GPU are pre-aligned to the same alphabetical symbol universe before scoring parity.
- Lane B (`--parity-mode production`): production behaviour; GPU runtime may truncate symbol universe to the kernel state cap (52 symbols).

Example commands:

```bash
# Lane A (identical symbol universe)
mei-backtester sweep \
  --parity-mode identical-symbol-universe \
  --sweep-spec backtester/sweeps/smoke.yaml \
  --interval 1h --entry-interval 3m --exit-interval 3m \
  --output /tmp/lane_a_cpu.jsonl

mei-backtester sweep \
  --parity-mode identical-symbol-universe \
  --gpu \
  --sweep-spec backtester/sweeps/smoke.yaml \
  --interval 1h --entry-interval 3m --exit-interval 3m \
  --output /tmp/lane_a_gpu.jsonl

# Lane B (production truncation behaviour)
mei-backtester sweep \
  --parity-mode production \
  --sweep-spec backtester/sweeps/smoke.yaml \
  --interval 1h --entry-interval 3m --exit-interval 3m \
  --output /tmp/lane_b_cpu.jsonl

mei-backtester sweep \
  --parity-mode production \
  --gpu \
  --sweep-spec backtester/sweeps/smoke.yaml \
  --interval 1h --entry-interval 3m --exit-interval 3m \
  --output /tmp/lane_b_gpu.jsonl
```

Generate a unified lane report (includes ranking assertions):

```bash
python tools/compare_sweep_outputs.py \
  --lane-a-cpu /tmp/lane_a_cpu.jsonl \
  --lane-a-gpu /tmp/lane_a_gpu.jsonl \
  --lane-b-cpu /tmp/lane_b_cpu.jsonl \
  --lane-b-gpu /tmp/lane_b_gpu.jsonl \
  --output /tmp/gpu_smoke_parity_report.json \
  --print-summary
```

Use the scripted variant to run all four sweeps and generate the report in one step:

```bash
./scripts/ci_gpu_smoke_parity_gate.sh
```

Optional environment knobs:

```bash
export AQC_GPU_PARITY_STRICT=1
export AQC_PARITY_CONFIG_PATH=/absolute/path/to/config/strategy_overrides.yaml
export AQC_PARITY_BASELINE_ANY_MISMATCH_COUNT=288
export AQC_PARITY_BASELINE_MAX_ABS_PNL_DIFF=25225.25
export AQC_PARITY_BASELINE_MEAN_ABS_PNL_DIFF=8552.34
export AQC_PARITY_BASELINE_TRADE_COUNT_MISMATCH_COUNT=288
```

---

## Config Deploy Pipeline

End-to-end workflow: **sweep → deploy → export → replay with init-state**.

### Step 1: Run sweep to find optimal params

```bash
mei-backtester sweep --sweep-config sweep.yaml --output sweep_results.jsonl
```

### Step 2: Deploy best config (`deploy_sweep.py`)

```bash
# Preview changes (SAFE — no side effects)
python tools/deploy_sweep.py --sweep-results sweep_results.jsonl --rank 1 --dry-run

# Deploy to paper only (close paper positions + restart)
python tools/deploy_sweep.py --sweep-results sweep_results.jsonl --rank 1 \
  --close-paper --restart --yes

# Deploy to both live + paper (DANGEROUS — closes real positions)
python tools/deploy_sweep.py --sweep-results sweep_results.jsonl --rank 1 \
  --close-live --close-paper --restart --yes
```

**What it does:**
1. Parses JSONL sweep results, picks rank N (default: #1 = best PnL)
2. Shows config diff: `trade.sl_atr_mult: 2.0 → 1.8` + backtest metrics
3. Requires `--yes` or interactive Y/N confirmation
4. `--close-live`: market close all exchange positions (3 retries, 5s verify each)
5. `--close-paper`: insert CLOSE trades in paper DB + clear position_state
6. Merges overrides into `config/strategy_overrides.yaml` (writes using PyYAML; YAML comments are not preserved)
7. Backs up YAML as `.bak.<timestamp>`
8. Updates `strategy_changelog.json` with auto-incremented version
9. `--restart`: `systemctl --user restart` paper + live services

**Safety:**
- `--dry-run` shows diff + metrics without changing anything
- `--close-live` requires explicit flag — never closes live positions by default
- YAML backup created before every write

### Step 3: Export current state (`export_state.py`)

```bash
# Export paper trader state
python tools/export_state.py --source paper --output state.json

# Export live trader state (requires a secrets file; set AI_QUANT_SECRETS_PATH for non-default locations)
python tools/export_state.py --source live --output state.json
```

**Output format (v1 JSON schema):**
```json
{
  "version": 1,
  "source": "paper",
  "exported_at_ms": 1770563327601,
  "balance": 8745.93,
  "positions": [
    {
      "symbol": "BTC",
      "side": "long",
      "size": 0.003,
      "entry_price": 97000.0,
      "entry_atr": 1200.0,
      "trailing_sl": null,
      "confidence": "medium",
      "leverage": 5.0,
      "margin_used": 58.2,
      "adds_count": 0,
      "tp1_taken": false,
      "open_time_ms": 1770400000000,
      "last_add_time_ms": 0
    }
  ]
}
```

**Paper export:** reconstructs positions from SQLite trades table (mirrors `PaperTrader.load_state()` logic) + position_state metadata.

**Live export:** uses `HyperliquidLiveExecutor` API for exchange positions + live DB for metadata enrichment (entry_atr, trailing_sl, confidence, adds_count, tp1_taken).

### Step 4: Replay with init-state

```bash
# Replay from exported state (uses exported balance + positions)
mei-backtester replay --init-state state.json --trades

# Init-state overrides --initial-balance
mei-backtester replay --init-state state.json --interval 1h --exit-interval 3m
```

**Behaviour:**
- `--init-state` loads balance + positions from the exported JSON file
- Overrides `--initial-balance` when provided
- Init-state positions are monitored from the **first bar** (exit check runs before warmup guard)
- Symbols in init-state but not in candle data are filtered out with a warning
- `trailing_sl: null` means trailing not yet triggered — backtester computes from scratch
- **Sweeps always start clean** — `--init-state` only works with `replay`

### Full E2E Example

```bash
# 1. Sweep for optimal params
mei-backtester sweep --sweep-config sweep.yaml --output sweep_results.jsonl

# 2. Preview + deploy
python tools/deploy_sweep.py --sweep-results sweep_results.jsonl --rank 1 --dry-run
python tools/deploy_sweep.py --sweep-results sweep_results.jsonl --rank 1 \
  --close-paper --restart --yes

# 3. Wait for paper trader to accumulate positions...

# 4. Export state and validate via backtest
python tools/export_state.py --source paper --output /tmp/paper_state.json
mei-backtester replay --init-state /tmp/paper_state.json --trades

# 5. Compare expected vs actual PnL trajectory
```

---

## File Map

| File | Description |
|------|-------------|
| `crates/bt-core/src/engine.rs` | Simulation engine — `run_simulation()` |
| `crates/bt-core/src/decision_kernel.rs` | SSOT decision kernel (shared across all paths) |
| `crates/bt-core/src/init_state.rs` | JSON state loader for `--init-state` |
| `crates/bt-core/src/sweep.rs` | Parallel parameter sweep runner |
| `crates/bt-signals/` | Signal generation — entry logic, gates, confidence |
| `crates/bt-data/` | Candle DB reader (SQLite) |
| `crates/bt-gpu/` | CUDA GPU sweep + TPE Bayesian optimisation |
| `crates/bt-runtime/` | PyO3 bridge to Python |
| `crates/risk-core/` | Shared risk primitives (entry sizing, confidence) |
| `crates/bt-cli/src/main.rs` | CLI entry point (clap) |
| `../tools/export_state.py` | Export live/paper state to JSON |
| `../tools/deploy_sweep.py` | Deploy sweep results to YAML config |

## GPU Decision Codegen

GPU sweep decision logic is generated from Rust kernel source via template-based codegen. See [docs/gpu-codegen-guide.md](docs/gpu-codegen-guide.md) for the developer workflow.

## Key Implementation Details

- **Exit before warmup**: `engine.rs` runs exit checks for existing positions **before** the warmup guard (`bar_count < lookback`). This ensures init-state positions are monitored from bar 1. Entries still require warmup completion.
- **Borrow-safe pattern**: EMA slow history push and bar_count increment use scoped borrows that end before `apply_exit(&mut state)` is called.
- **init_state.rs**: serde Deserialize structs, `load(path)` validates version=1, `into_sim_state()` converts to `(f64, FxHashMap<String, Position>)` with optional symbol filtering.
- **deploy_sweep.py**: uses PyYAML `safe_load`/`safe_dump`; YAML comments are not preserved.
- **export_state.py paper mode**: 4-stage reconstruction — latest balance → identify open positions (OPEN without matching CLOSE) → replay ADD/REDUCE fills → load position_state metadata.
