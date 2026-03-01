# V8 SSOT Migration Plan — Unified Engine Architecture

> **Date**: 2026-02-15
> **Status**: Complete — merged to `master`. See [backtester/MIGRATION.md](../../backtester/MIGRATION.md).
> **Goal**: Make the V8 Rust decision kernel the **Single Source of Truth** (SSOT) for ALL execution paths: live, paper, backtest (CPU), and sweep (GPU grid/TPE).

---

## Executive Summary

### Current State: 3 Independent Accounting Implementations

| Path | Language | Accounting | Exit Logic | Signal Logic | State |
|------|----------|-----------|------------|-------------|-------|
| **Live/Paper** | Python (`PaperTrader`) | In-memory balance + margin dict | 7+ exit types inline | `analyze()` signal gen | SQLite persist |
| **Backtest CPU** | Rust (`engine.rs`) | `SimState.balance` + `Position` (25 fields) | `exits/` module (SL/TP/trailing/smart) | `bt-signals` crate | In-memory |
| **Sweep GPU** | CUDA (`sweep_engine.cu`) | f32 registers per-thread | Inline SL/TP/trailing | Inline gates+entry | GPU registers |
| **Kernel** | Rust (`decision_kernel.rs`) | `StrategyState` (cash + margin positions) | None (no exits) | None (intent gating only) | Ephemeral |

**Problems**:
1. Three separate PnL calculations → results diverge
2. GPU has 5 known divergence points from CPU
3. Python Paper Trader tracks margin/funding/trailing independently from kernel
4. Kernel only gates entry intents; doesn't control exits, funding, or partial closes
5. Rule changes require updates in 2-3 places

### Target State: Kernel as SSOT

```
                    ┌─────────────────────────┐
                    │   Decision Kernel (Rust) │
                    │  ─ Cash accounting       │
                    │  ─ Position state        │
                    │  ─ Margin/leverage       │
                    │  ─ Funding settlement    │
                    │  ─ Fee model             │
                    │  ─ Partial close         │
                    │  ─ Entry intent gating   │
                    │  ─ Exit intent gating    │
                    └────────┬────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        ┌─────┴─────┐ ┌─────┴─────┐ ┌─────┴─────┐
        │  CPU       │ │  GPU       │ │  Live/     │
        │  Backtest  │ │  Sweep     │ │  Paper     │
        │  engine.rs │ │  .cu       │ │  (PyO3)    │
        └───────────┘ └───────────┘ └───────────┘
```

---

## Naming Convention

Extends existing `AQC-` scheme from `plan/1/scrum-backlog.md`:

- **Milestones**: `AQC-M7xx` (SSOT Migration)
- **Tickets**: `AQC-7xx` (stories/tasks)
- **Priority**: P0 (must), P1 (should), P2 (nice)
- **Complexity**: Fibonacci story points (1,2,3,5,8,13)
- **Labels**: `ssot`, `kernel`, `gpu-parity`, `live-bridge`, `validation`, `deprecation`

---

## Milestone 1: Kernel Accounting SSOT (Foundation)

**Epic**: `AQC-M700` — Make kernel the authoritative accounting engine
**Goal**: All cash, margin, PnL, and fee calculations flow through the kernel
**Duration estimate**: Sprint 1-2

### AQC-701 (P0, 5) `[ssot, kernel]` Add partial close support to kernel

**Current gap**: Kernel only supports full position close. Engine does partial TP (50%) independently.

**Acceptance criteria**:
- `decision_kernel::step()` accepts a new `MarketEvent.close_fraction: Option<f64>` field
- When `close_fraction` is `Some(0.5)`, kernel computes partial PnL, returns proportional margin, updates position in-place
- Uses `accounting::build_partial_close_plan()` (already exists)
- `Position.quantity`, `Position.notional_usd`, `Position.margin_usd` all updated proportionally
- Deterministic: same inputs → same outputs
- Unit tests: partial close at 25%/50%/75%/100% fractions

**Files**: `bt-core/src/decision_kernel.rs`, `bt-core/src/accounting.rs`
**Dependencies**: None
**Parallel**: Yes

---

### AQC-702 (P0, 3) `[ssot, kernel]` Add average entry recalculation on ADD

**Current gap**: Kernel's `apply_open()` with `kind=Add` doesn't recalculate weighted average entry price. Python PaperTrader does (line 1240).

**Acceptance criteria**:
- When `kind=Add` and position already exists:
  - `new_avg = (old_avg * old_qty + new_price * add_qty) / (old_qty + add_qty)`
  - `Position.avg_entry_price` updated
  - `Position.notional_usd` = cumulative notional
  - `Position.margin_usd` += new margin
- Matches Python PaperTrader's weighted-average formula exactly
- Unit tests: ADD to existing position at different prices, verify avg_entry

**Files**: `bt-core/src/decision_kernel.rs`
**Dependencies**: None
**Parallel**: Yes

---

### AQC-703 (P0, 5) `[ssot, kernel]` Add funding settlement as kernel step type

**Current gap**: Kernel has no funding awareness. Both engine.rs and PaperTrader compute funding independently using `accounting::funding_delta()`.

**Acceptance criteria**:
- New `MarketSignal::Funding { rate: f64 }` variant in `MarketEvent`
- `step()` handles funding: applies `funding_delta(is_long, size, price, rate)` to `cash_usd`
- No position close/open on funding events
- Kernel state records last funding timestamp per position
- Schema version bump to 2 (with backward compat: v1 events without funding still work)
- Unit tests: long position + positive rate → negative cash delta; short → positive

**Files**: `bt-core/src/decision_kernel.rs`, `bt-core/src/accounting.rs`
**Dependencies**: None
**Parallel**: Yes

---

### AQC-704 (P0, 3) `[ssot, kernel]` Expand kernel Position with tracking metadata

**Current gap**: Kernel Position has 8 fields. Engine Position has 25+. Kernel lacks: `confidence`, `entry_atr`, `trailing_sl`, `tp1_taken`, `mae_usd`, `mfe_usd`, `adds_count`.

**Acceptance criteria**:
- Add optional metadata fields to kernel Position:
  ```rust
  pub confidence: Option<u8>,         // 0=Low, 1=Medium, 2=High
  pub entry_atr: Option<f64>,
  pub adds_count: u32,
  pub tp1_taken: bool,
  pub trailing_sl: Option<f64>,
  pub mae_usd: f64,                   // min adverse excursion
  pub mfe_usd: f64,                   // max favorable excursion
  ```
- These fields are pass-through for the kernel (set by caller, stored in state)
- `step()` updates `adds_count` on ADD, passes through others
- JSON serialization round-trips correctly
- Backward compat: missing fields deserialize as defaults

**Files**: `bt-core/src/decision_kernel.rs`
**Dependencies**: None
**Parallel**: Yes

---

### AQC-705 (P0, 3) `[ssot, kernel]` Add kernel state persistence (SQLite)

**Current gap**: Kernel state is ephemeral (in-memory only). Lost on restart. PaperTrader persists to SQLite.

**Acceptance criteria**:
- New `bt-core/src/state_store.rs` module with `save_state(state: &StrategyState, path: &str)` and `load_state(path: &str) -> StrategyState`
- SQLite table: `kernel_state (id INTEGER PRIMARY KEY, timestamp_ms INTEGER, state_json TEXT, checksum TEXT)`
- Save after every N steps (configurable, default=1 for live, 0=disabled for backtest)
- Load on engine start for recovery
- Checksum for integrity validation
- Unit tests: save → load → compare

**Files**: New `bt-core/src/state_store.rs`, `bt-core/src/lib.rs`
**Dependencies**: AQC-704 (expanded position schema)
**Parallel**: After AQC-704

---

### AQC-706 (P0, 2) `[ssot, kernel]` Unified fee model with maker/taker selection

**Current gap**: Kernel always uses taker rate. Python PaperTrader calls `_effective_fee_rate()` which can vary by symbol/order type.

**Acceptance criteria**:
- `MarketEvent` gets optional `fee_role: Option<FeeRole>` field
- If provided, kernel uses that role; if None, defaults to Taker (backward compat)
- `KernelParams` already has `maker_fee_bps` and `taker_fee_bps` — these become authoritative
- Live bridge passes `FeeRole::Taker` for market orders, `FeeRole::Maker` for limit/post-only
- Unit tests: open with maker vs taker fee, verify different cash deductions

**Files**: `bt-core/src/decision_kernel.rs`
**Dependencies**: None
**Parallel**: Yes

---

## Milestone 2: Exit Logic in Kernel

**Epic**: `AQC-M710` — Move exit decision authority into the kernel
**Goal**: Kernel evaluates and produces exit intents, not just entry intents
**Duration estimate**: Sprint 2-3

### AQC-711 (P0, 8) `[ssot, kernel]` Add exit evaluation to kernel step

**Current gap**: All 7 exit types (SL, trailing, TP, partial TP, breakeven, smart exits, glitch guard) are in engine.rs/exits/, not kernel.

**Acceptance criteria**:
- New `ExitParams` struct (extracted from `StrategyConfig` exit-related fields):
  ```rust
  pub struct ExitParams {
      pub sl_atr_mult: f64,
      pub tp_atr_mult: f64,
      pub trailing_start_atr: f64,
      pub trailing_distance_atr: f64,
      pub enable_partial_tp: bool,
      pub tp_partial_pct: f64,
      pub tp_partial_atr_mult: f64,
      pub enable_breakeven_stop: bool,
      pub breakeven_start_atr: f64,
      pub breakeven_buffer_atr: f64,
      // ... (all exit params from config.rs)
  }
  ```
- `step()` checks existing positions against exit conditions when `MarketEvent` provides a price update
- Exit intents (`OrderIntentKind::Close` or `PartialClose`) emitted by kernel
- Exit reason included in diagnostics
- Kernel updates `Position.trailing_sl` and `Position.tp1_taken` internally

**Files**: `bt-core/src/decision_kernel.rs`, new `bt-core/src/kernel_exits.rs`
**Dependencies**: AQC-701 (partial close), AQC-704 (position metadata)
**Parallel**: After M1

---

### AQC-712 (P0, 5) `[ssot, kernel]` Glitch guard in kernel

**Current gap**: Glitch guard (block exits during extreme price moves) is engine-side only.

**Acceptance criteria**:
- Kernel checks `glitch_price_dev_pct` and `glitch_atr_mult` before emitting exit intents
- If price deviation exceeds threshold, exit is blocked and warning emitted in diagnostics
- Matches `block_exits_on_extreme_dev` logic from `exits/mod.rs`
- Unit tests: price spike → exit blocked; normal move → exit allowed

**Files**: `bt-core/src/kernel_exits.rs`
**Dependencies**: AQC-711
**Parallel**: After AQC-711

---

### AQC-713 (P0, 5) `[ssot, kernel]` Smart exits in kernel (TSME, ADX exhaustion, RSI overextension)

**Current gap**: Smart exits require indicator state (ADX, RSI, EMA slope) that kernel doesn't have.

**Acceptance criteria**:
- `MarketEvent` expanded with optional indicator snapshot:
  ```rust
  pub indicators: Option<IndicatorSnapshot> {
      adx: f64, rsi: f64, ema_fast: f64, ema_slow: f64,
      ema_slope: f64, bb_width_ratio: f64, atr: f64,
      stoch_rsi_k: f64, volume: f64, vol_sma: f64,
  }
  ```
- Kernel evaluates smart exits when indicators provided
- TSME: trend saturation + momentum exit when profit_atr > threshold
- ADX exhaustion: exit when ADX < threshold despite winning position
- RSI overextension: exit when RSI extreme + profit condition
- Matches CPU `exits/smart_exits.rs` logic exactly
- Integration tests: replicate CPU exit scenarios in kernel

**Files**: `bt-core/src/kernel_exits.rs`, `bt-core/src/decision_kernel.rs`
**Dependencies**: AQC-711, AQC-704
**Parallel**: After AQC-711

---

### AQC-714 (P1, 3) `[ssot, kernel]` Engine.rs delegates exits to kernel

**Current gap**: engine.rs has its own exit evaluation loop. After kernel has exit logic, engine should delegate.

**Acceptance criteria**:
- Engine's per-bar exit check calls `decision_kernel::step()` with price-update event
- Kernel returns exit intents; engine executes them (apply_exit)
- Remove direct calls to `exits::check_all_exits()` from engine main loop
- Engine's `SimState.positions` stays as extended view; kernel `Position` is canonical for accounting
- All existing backtest results remain within ±0.1% (determinism preserved)
- Integration test: run full replay, compare before/after delegation

**Files**: `bt-core/src/engine.rs`
**Dependencies**: AQC-711, AQC-712, AQC-713
**Parallel**: After all M2 exit tickets

---

## Milestone 3: Signal Logic Unification

**Epic**: `AQC-M720` — Consolidate signal generation path
**Goal**: Signal evaluation flows through a unified Rust interface usable by all paths
**Duration estimate**: Sprint 3-4

### AQC-721 (P1, 5) `[ssot, kernel]` Gate checks as kernel pre-filter

**Current gap**: Gate checks (ranging, anomaly, extension, ADX rising, volume confirm, BTC alignment) are in `bt-signals/gates.rs` but called by engine, not kernel.

**Acceptance criteria**:
- `MarketEvent` expanded with optional gate context (BTC bullish flag, market breadth)
- Kernel calls `check_gates()` before evaluating entry intents
- Gate result stored in diagnostics (for audit trail)
- If gates fail, kernel emits `Hold` intent instead of `Open`
- Matches current engine behavior exactly

**Files**: `bt-core/src/decision_kernel.rs`, `bt-signals/src/gates.rs`
**Dependencies**: AQC-713 (indicator snapshot in events)
**Parallel**: Yes

---

### AQC-722 (P1, 5) `[ssot, kernel]` Entry signal evaluation in kernel

**Current gap**: Entry signal generation (`generate_signal()` from bt-signals) is called by engine.

**Acceptance criteria**:
- Kernel can evaluate entry signals when `MarketEvent` has full indicator snapshot
- Signal modes: trend entry, pullback, slow drift, AVE (adaptive volatility entry)
- Confidence tier assignment inside kernel
- Engine passes raw indicator snapshots; kernel decides signal + confidence
- Backward compat: if no indicators in event, kernel operates in "intent-only" mode (current behavior)

**Files**: `bt-core/src/decision_kernel.rs`, `bt-signals/src/entry.rs`
**Dependencies**: AQC-721
**Parallel**: After AQC-721

---

### AQC-723 (P1, 3) `[ssot, kernel]` Cooldown state in kernel

**Current gap**: Entry/exit cooldowns tracked by engine (`last_entry_attempt_ms`, `last_exit_attempt_ms`). Kernel has no cooldown awareness.

**Acceptance criteria**:
- `StrategyState` gets cooldown tracking:
  ```rust
  pub last_entry_ms: BTreeMap<String, i64>,
  pub last_exit_ms: BTreeMap<String, i64>,
  pub last_close: BTreeMap<String, (i64, String, String)>,  // (ts, type, reason) for PESC
  ```
- Kernel enforces `entry_cooldown_s` and `exit_cooldown_s` before emitting intents
- PESC (post-exit same-direction cooldown) enforced by kernel
- Adaptive reentry cooldown (by ADX) computed in kernel

**Files**: `bt-core/src/decision_kernel.rs`
**Dependencies**: AQC-722
**Parallel**: After AQC-722

---

## Milestone 4: GPU Parity

**Epic**: `AQC-M730` — Fix GPU divergences and establish parity framework
**Goal**: GPU sweep results match CPU within tolerance for identical configs
**Duration estimate**: Sprint 3-4 (parallel with M3)

### AQC-731 (P0, 3) `[gpu-parity]` Fix hardcoded exit slippage (0.5 bps)

**Current gap**: GPU `sweep_engine.cu` applies hardcoded 0.5 bps exit slippage. CPU uses config-driven slippage.

**Acceptance criteria**:
- Remove hardcoded `0.00005f` from exit price calculation in CUDA kernel
- Pass slippage as GPU param (from `GpuComboConfig`)
- When slippage=0, exit price = signal price (same as CPU default)
- Parity test: GPU vs CPU on same config → exit prices match

**Files**: `bt-gpu/kernels/sweep_engine.cu`, `bt-gpu/src/buffers.rs`
**Dependencies**: None
**Parallel**: Yes

---

### AQC-732 (P0, 3) `[gpu-parity]` Fix trailing SL lock on partial close

**Current gap**: GPU locks trailing SL after partial TP; CPU continues adjusting.

**Acceptance criteria**:
- After partial close in GPU kernel, trailing SL continues tracking (not frozen)
- Match CPU `exits/trailing.rs` behavior: trailing distance recalculated from remaining position
- Parity test: position with partial TP + trailing → same exit price on GPU and CPU

**Files**: `bt-gpu/kernels/sweep_engine.cu`
**Dependencies**: None
**Parallel**: Yes

---

### AQC-733 (P0, 3) `[gpu-parity]` Replace 8 hardcoded trailing thresholds

**Current gap**: GPU has 8 hardcoded trailing distance breakpoints. CPU reads from config.

**Acceptance criteria**:
- Move trailing thresholds into `GpuComboConfig` struct
- Host code packs thresholds from `StrategyConfig` into GPU params
- GPU kernel reads from config instead of hardcoded constants
- Parity test: varying trailing configs → same results on GPU and CPU

**Files**: `bt-gpu/kernels/sweep_engine.cu`, `bt-gpu/src/buffers.rs`
**Dependencies**: None
**Parallel**: Yes

---

### AQC-734 (P1, 5) `[gpu-parity]` f32→f64 precision for critical accounting

**Current gap**: GPU uses f32 for all calculations. CPU uses f64. At high trade counts, rounding diverges.

**Acceptance criteria**:
- GPU uses `double` (f64) for: cash balance, margin, PnL accumulation, fee calculation
- Non-critical paths (indicator computation, gate checks) can stay f32
- Precision test: 10K trades → GPU vs CPU total PnL within 1e-6 relative error

**Files**: `bt-gpu/kernels/sweep_engine.cu`
**Dependencies**: None
**Parallel**: Yes

---

### AQC-735 (P0, 5) `[gpu-parity, validation]` Automated CPU↔GPU parity test framework

**Current gap**: Parity tests exist but are manual. Need automated CI gate.

**Acceptance criteria**:
- New test harness: given a config + candle DB, run both CPU and GPU, compare:
  - Trade count: ±2%
  - Total PnL: ±0.5%
  - Max drawdown: ±1%
  - Final balance: ±0.5%
- Run in CI on every GPU-touching PR
- Tolerance configurable via env var `AQC_GPU_PARITY_TOLERANCE`
- Produces diff report on failure

**Files**: New `tests/gpu_cpu_parity_automated.rs`, `.github/workflows/gpu-parity-gate.yml`
**Dependencies**: AQC-731, AQC-732, AQC-733
**Parallel**: After other M4 tickets

---

### AQC-736 (P1, 3) `[gpu-parity]` Fix glitch guard semantics

**Current gap**: GPU glitch guard uses different threshold comparison than CPU.

**Acceptance criteria**:
- GPU glitch guard matches CPU `block_exits_on_extreme_dev` logic exactly
- Same threshold params, same comparison operators
- Parity test with extreme price moves → identical behavior

**Files**: `bt-gpu/kernels/sweep_engine.cu`
**Dependencies**: None
**Parallel**: Yes

---

## Milestone 5: Python Live Bridge (PyO3 Integration)

**Epic**: `AQC-M740` — Python OMS/PaperTrader delegates accounting to Rust kernel
**Goal**: Live/paper trading uses kernel as SSOT via PyO3 bridge
**Duration estimate**: Sprint 4-5

### AQC-741 (P0, 8) `[live-bridge]` Expand PyO3 bridge for full kernel stepping

**Current gap**: `bt-runtime` only exposes `step_decision(state_json, event_json, params_json)` for intent gating. Python does its own accounting.

**Acceptance criteria**:
- `bt-runtime` exposes:
  - `step_full(state_json, event_json, params_json, exit_params_json) -> decision_json` — full step with exit evaluation
  - `apply_funding(state_json, symbol, rate, price) -> state_json` — funding settlement
  - `get_equity(state_json, prices_json) -> f64` — mark-to-market equity
  - `save_state(state_json, path)` / `load_state(path) -> state_json` — persistence
- All functions accept/return JSON strings (simple serialization)
- Python type stubs generated for IDE support
- Integration tests: Python calls Rust bridge, verifies results match

**Files**: `bt-runtime/src/lib.rs`, new `bt-runtime/src/bridge.rs`
**Dependencies**: M1 complete (AQC-701 through AQC-706), M2 complete (AQC-711 through AQC-714)
**Parallel**: After M1+M2

---

### AQC-742 (P0, 8) `[live-bridge]` PaperTrader accounting delegation

**Current gap**: PaperTrader maintains its own balance, positions, margin, PnL calculations independently.

**Acceptance criteria**:
- PaperTrader uses Rust kernel for ALL accounting:
  - Open: `step_full()` → extract fills → record to SQLite
  - ADD: `step_full()` with existing position in state → kernel re-averages entry
  - Close/Partial: `step_full()` → kernel computes PnL and margin return
  - Funding: `apply_funding()` → kernel applies delta
- PaperTrader's `self.balance` replaced by kernel's `state.cash_usd`
- PaperTrader's `self.positions` derived from kernel's `state.positions`
- SQLite still records trades/fills for audit (from kernel's fill events)
- Parallel run mode: old PaperTrader + new kernel-delegated, compare for 1 week

**Files**: `strategy/mei_alpha_v1.py` (PaperTrader class)
**Dependencies**: AQC-741
**Parallel**: After AQC-741

---

### AQC-743 (P0, 5) `[live-bridge]` OMS fill reconciliation with kernel state

**Current gap**: OMS matches fills independently. Kernel state not updated from exchange fills.

**Acceptance criteria**:
- After OMS confirms a fill (via WS or REST), kernel state is updated:
  - Create `MarketEvent` from fill data (symbol, price, quantity, side)
  - Feed to kernel via `step_full()`
  - Kernel state persisted after each confirmed fill
- Reconciliation mismatch (kernel says A, exchange says B) → alert + manual review
- Fill dedup: OMS's `fill_hash` dedup prevents double-counting in kernel

**Files**: `engine/oms.py`, `engine/core.py` (`KernelDecisionRustBindingProvider`)
**Dependencies**: AQC-741, AQC-742
**Parallel**: After AQC-742

---

### AQC-744 (P1, 5) `[live-bridge]` Kernel state recovery on restart

**Current gap**: Kernel state lost on restart. PaperTrader rebuilds from SQLite replay.

**Acceptance criteria**:
- On startup, load kernel state from SQLite (via `load_state()`)
- Validate loaded state against OMS audit trail (most recent fills)
- If state is stale (older than last fill), replay missing fills to catch up
- If state is corrupt (checksum mismatch), rebuild from OMS fill history
- Startup health check logs: "Kernel state loaded, age=Xs, positions=N, cash=$X"

**Files**: `engine/core.py`, `bt-runtime/src/lib.rs`
**Dependencies**: AQC-705 (state persistence), AQC-741
**Parallel**: After AQC-741

---

### AQC-745 (P1, 3) `[live-bridge]` Equity calculation via kernel

**Current gap**: PaperTrader computes equity independently (`get_live_balance()`). Should use kernel.

**Acceptance criteria**:
- Monitor dashboard calls `get_equity(state_json, prices_json)` via PyO3
- Returns: realized cash + unrealized PnL - estimated close fees
- Matches PaperTrader's `get_live_balance()` within ±$0.01
- Performance: < 1ms per call (no JSON overhead for hot path)

**Files**: `monitor/server.py`, `bt-runtime/src/lib.rs`
**Dependencies**: AQC-741
**Parallel**: After AQC-741

---

## Milestone 6: Validation & Deprecation

**Epic**: `AQC-M750` — Validate parity across all paths, retire main backtester
**Goal**: Prove V8 matches main, then archive main
**Duration estimate**: Sprint 5-6

### AQC-751 (P0, 5) `[validation]` Main vs V8 CPU replay parity test

**Acceptance criteria**:
- Run identical config (v6.100) on both main and V8 CPU backtester
- Compare: trade count (±5%), total PnL (±1%), max DD (±2%)
- Document any legitimate differences (e.g., V8 has entry/exit cooldowns)
- If within tolerance → V8 validated as main replacement
- If divergence → investigate and fix

**Dependencies**: None (can start immediately)
**Parallel**: Yes

---

### AQC-752 (P0, 3) `[validation]` Live vs kernel parity shadow test

**Acceptance criteria**:
- Run PaperTrader with BOTH old accounting and new kernel-delegated accounting in parallel for 7 days
- Compare after each trade: balance delta, margin used, PnL
- Tolerance: ±$0.01 per trade
- If divergence detected → halt live trading, investigate

**Dependencies**: AQC-742 (PaperTrader delegation)
**Parallel**: After M5

---

### AQC-753 (P0, 3) `[validation]` GPU↔CPU↔Live three-way parity report

**Acceptance criteria**:
- For same config + same candle window (e.g., last 14 days):
  - GPU sweep top result
  - CPU replay result
  - Paper trading result (from kernel state)
- Three-way comparison report in `artifacts/parity/`
- All within tolerance → system validated
- Automated weekly run in CI

**Dependencies**: AQC-735 (GPU parity framework), AQC-752 (live parity)
**Parallel**: After both

---

### AQC-754 (P1, 2) `[deprecation]` Archive main backtester

**Acceptance criteria**:
- Main backtester (`ai_quant/backtester/`) tagged as `archive/main-backtester-v6`
- Factory pipeline (`factory_run.py`, `factory_cycle.py`) fully uses V8 binary
- Git worktree for main removed from development workflow
- README updated to point to V8 as sole backtester
- Keep main read-only for 30 days in case of rollback

**Dependencies**: AQC-751, AQC-753 (all parity validated)
**Parallel**: After parity validation

---

### AQC-755 (P1, 2) `[deprecation]` Remove dual accounting in PaperTrader

**Acceptance criteria**:
- PaperTrader's `self.balance` and `self.positions` dict removed
- All accounting queries go through kernel state
- `get_live_balance()` delegates to kernel's `get_equity()`
- Old `_compute_position_pnl()` removed
- SQLite audit trail continues (from kernel fill events)

**Dependencies**: AQC-752 (live parity validated)
**Parallel**: After AQC-752

---

## Milestone 7: GPU Codegen (Long-term)

**Epic**: `AQC-M760` — Auto-generate GPU kernel from Rust source
**Goal**: Eliminate manual CUDA maintenance, guarantee CPU↔GPU parity by construction
**Duration estimate**: Sprint 6-8 (stretch goal)

### AQC-761 (P2, 13) `[gpu-parity]` Template-based CUDA codegen from kernel

**Acceptance criteria**:
- Rust build script generates `.cu` accounting functions from `decision_kernel.rs`
- Template approach: Rust types → C struct definitions, Rust functions → CUDA device functions
- Generated functions: `apply_open`, `apply_close`, `apply_partial_close`, `funding_delta`
- Manual GPU code only for: thread scheduling, memory layout, indicator computation
- Parity guaranteed by construction for accounting paths

**Dependencies**: M4 complete (manual parity fixes)
**Parallel**: Stretch goal

---

### AQC-762 (P2, 8) `[gpu-parity]` Rust-to-PTX compilation exploration

**Acceptance criteria**:
- Spike: compile `accounting.rs` to PTX using `nvptx64-nvidia-cuda` target
- Evaluate: compilation time, kernel launch overhead, register pressure
- Decision: codegen vs PTX for next phase
- Document findings in `plan/4/gpu-codegen-spike.md`

**Dependencies**: None
**Parallel**: Yes (research spike)

---

## Dependency Graph

```
M1 (Kernel Foundation)
├── AQC-701 Partial close
├── AQC-702 Avg entry on ADD
├── AQC-703 Funding settlement
├── AQC-704 Position metadata
│   └── AQC-705 State persistence
├── AQC-706 Fee model
│
M2 (Exit Logic) ──depends──→ M1
├── AQC-711 Exit evaluation (needs 701, 704)
│   ├── AQC-712 Glitch guard
│   ├── AQC-713 Smart exits
│   └── AQC-714 Engine delegation (needs 711-713)
│
M3 (Signal Logic) ──depends──→ M2
├── AQC-721 Gate checks (needs 713 indicators)
│   └── AQC-722 Entry evaluation
│       └── AQC-723 Cooldown state
│
M4 (GPU Parity) ──parallel with M2/M3──
├── AQC-731 Exit slippage fix
├── AQC-732 Trailing SL lock fix
├── AQC-733 Trailing thresholds fix
├── AQC-734 f32→f64 precision
├── AQC-735 Parity framework (needs 731-733)
├── AQC-736 Glitch guard fix
│
M5 (Live Bridge) ──depends──→ M1 + M2
├── AQC-741 PyO3 expansion (needs M1+M2)
│   ├── AQC-742 PaperTrader delegation
│   │   └── AQC-743 OMS reconciliation
│   ├── AQC-744 State recovery (needs 705)
│   └── AQC-745 Equity calculation
│
M6 (Validation) ──depends──→ M4 + M5
├── AQC-751 Main vs V8 parity (independent)
├── AQC-752 Live vs kernel parity (needs 742)
├── AQC-753 Three-way parity (needs 735, 752)
├── AQC-754 Archive main (needs 751, 753)
└── AQC-755 Remove dual accounting (needs 752)
│
M7 (GPU Codegen) ──stretch──→ M4
├── AQC-761 Template codegen
└── AQC-762 Rust-to-PTX spike
```

## Sprint Plan (Suggested)

| Sprint | Focus | Tickets | Parallel Tracks |
|--------|-------|---------|-----------------|
| **S1** | Kernel foundation | AQC-701, 702, 703, 704, 706 | GPU fixes: 731, 732, 733, 736 |
| **S2** | Kernel exits + persistence | AQC-705, 711, 712, 713 | GPU: 734, 735; Validation: 751 |
| **S3** | Engine delegation + signals | AQC-714, 721, 722, 723 | GPU codegen spike: 762 |
| **S4** | Live bridge | AQC-741, 742 | Continue signal work |
| **S5** | OMS integration + recovery | AQC-743, 744, 745 | Live shadow test: 752 |
| **S6** | Validation + deprecation | AQC-753, 754, 755 | GPU codegen: 761 |

## Agentic SDLC Notes

Each ticket is designed for autonomous agent execution:

1. **Clear acceptance criteria**: Every ticket has measurable outcomes
2. **File targets specified**: Agents know exactly which files to modify
3. **Dependencies explicit**: No hidden ordering assumptions
4. **Test requirements**: Every ticket requires unit/integration tests
5. **Backward compat**: Schema versioning prevents breaking changes

**Agent workflow per ticket**:
1. Read ticket description + acceptance criteria
2. Read target files + dependent code
3. Implement changes
4. Write tests matching acceptance criteria
5. Run `cargo test` / `pytest` to validate
6. Create PR with ticket ID in title (e.g., `AQC-701: Add partial close to kernel`)
7. CI gates validate parity (GPU if applicable)

**Parallel agent execution**:
- Within each sprint, independent tickets (marked "Parallel: Yes") can be assigned to separate agents
- M4 (GPU fixes) runs entirely in parallel with M2/M3
- Validation tickets (M6) require prior milestones but can start AQC-751 immediately
