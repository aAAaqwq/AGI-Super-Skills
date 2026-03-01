# Milestone 8: GPU Decision Logic Codegen (Full SSOT)

> **Status**: Complete. All 37 tickets implemented and validated. See [gpu-runtime-validation-report.md](../docs/gpu-runtime-validation-report.md) and [gpu-codegen-guide.md](../docs/gpu-codegen-guide.md).

**Epic**: AQC-M1200 — Extend template-based CUDA codegen to cover all sweep decision logic
**Goal**: Eliminate GPU↔CPU decision divergence; GPU sweep produces identical signals/exits/sizing as CPU backtester
**Predecessor**: AQC-761 (accounting codegen), AQC-762 (PTX spike — concluded codegen is the path)
**Approach**: Option A — manual string-template codegen with automated drift detection

---

## Context

AQC-761 proved template-based codegen works for accounting (6 functions). The remaining ~90% of GPU sweep decision logic (`sweep_engine.cu` — 1,674 lines) is independently maintained CUDA, diverging from the Rust kernel in:

- **Confidence assignment**: GPU uses DRE, CPU uses volume-based
- **Gate evaluation**: WGSL missing BTC alignment, inverted RSI logic
- **Trailing stop**: WGSL hardcodes 6 params that should be config-driven
- **Smart exits**: WGSL has extra stagnation exit absent in kernel

This milestone replaces all hand-written decision logic in `sweep_engine.cu` with codegen'd functions from the Rust kernel source, achieving true SSOT for GPU sweep.

---

## Ticket Inventory

### Phase 0: Drift Detector & Infrastructure (AQC-1200 — AQC-1202, AQC-1250, AQC-1260, AQC-1270)

| Ticket | Title | Depends On | Est. |
|--------|-------|-----------|------|
| AQC-1200 | Source-hash drift detector in `build.rs` | — | 0.5d |
| AQC-1201 | Decision codegen module scaffold + `render_all_decision()` | — | 0.5d |
| AQC-1202 | Per-function parity test harness (`gpu_decision_parity.rs`) | AQC-1201 | 1.0d |
| AQC-1250 | Extend `GpuComboConfig` with 11 missing decision codegen fields | AQC-1201 | 1.0d |
| **AQC-1260** | **f32/f64 precision benchmark + tolerance specification** | AQC-1201 | 0.5d |
| **AQC-1270** | **Validation: Config round-trip (141 fields)** | AQC-1250, AQC-1260 | 0.5d |

### Phase 1: Gates & Signals Codegen (AQC-1210 — AQC-1213)

| Ticket | Title | Depends On | Est. |
|--------|-------|-----------|------|
| AQC-1210 | `check_gates_codegen()` — 8 gates + TMC/AVE + DRE | AQC-1250 | 1.5d |
| **AQC-1261** | **Validation: Gates axis-by-axis (paired with 1210)** | AQC-1210, AQC-1260 | 1.0d |
| AQC-1211 | `generate_signal_codegen()` — Mode 1/2/3 + MACD helpers | AQC-1250, AQC-1210 | 1.5d |
| **AQC-1262** | **Validation: Signals mode-by-mode (paired with 1211)** | AQC-1211, AQC-1260 | 1.0d |
| AQC-1212 | Parity test: gates + signals vs CPU on fixture data (integration) | AQC-1261, AQC-1262 | 0.5d |
| AQC-1213 | Wire codegen'd gates/signals into `sweep_engine.cu` (replace hand-written) | AQC-1212 | 0.5d |

### Phase 2: Exit Logic Codegen (AQC-1220 — AQC-1226, AQC-1263 — AQC-1267)

| Ticket | Title | Depends On | Est. |
|--------|-------|-----------|------|
| AQC-1220 | `compute_sl_price_codegen()` — ASE/DASE/SLB/breakeven | AQC-1201 | 1.0d |
| **AQC-1263** | **Validation: Stop loss axis-by-axis (paired with 1220)** | AQC-1220, AQC-1260 | 0.75d |
| AQC-1221 | `compute_trailing_codegen()` — VBTS/TATP/TSPV/ratchet | AQC-1201 | 1.0d |
| **AQC-1264** | **Validation: Trailing stop axis (paired with 1221)** | AQC-1221, AQC-1260 | 1.0d |
| AQC-1222 | `check_tp_codegen()` — partial TP + full TP ladder | AQC-1201 | 1.0d |
| **AQC-1265** | **Validation: Take profit axis (paired with 1222)** | AQC-1222, AQC-1260 | 0.75d |
| AQC-1223 | `check_smart_exits_codegen()` — all 8 sub-checks | AQC-1201 | 2.0d |
| **AQC-1266** | **Validation: Smart exits axis-by-axis (paired with 1223)** | AQC-1223, AQC-1260 | 1.5d |
| AQC-1224 | `check_all_exits_codegen()` — orchestrator (priority dispatch) | AQC-1220..1223 | 0.5d |
| **AQC-1267** | **Validation: Exit orchestrator priority sequence (paired with 1224)** | AQC-1224, AQC-1260 | 0.75d |
| AQC-1225 | Parity test: all exits vs CPU on fixture data (integration) | AQC-1263, AQC-1264, AQC-1265, AQC-1266, AQC-1267 | 0.5d |
| AQC-1226 | Wire codegen'd exits into `sweep_engine.cu` (replace hand-written) | AQC-1225 | 0.5d |

### Phase 2b: Entry/Exit Cooldowns (AQC-1251, AQC-1269)

| Ticket | Title | Depends On | Est. |
|--------|-------|-----------|------|
| AQC-1251 | `entry_exit_cooldown_codegen()` — per-symbol time-based cooldowns | AQC-1201, AQC-1250 | 0.5d |
| **AQC-1269** | **Validation: PESC + entry/exit cooldowns axis (paired with 1231/1251)** | AQC-1231, AQC-1251, AQC-1260 | 0.75d |

### Phase 3: Sizing & Cooldowns Codegen (AQC-1230 — AQC-1233, AQC-1252, AQC-1268)

| Ticket | Title | Depends On | Est. |
|--------|-------|-----------|------|
| AQC-1230 | `compute_entry_size_codegen()` — dynamic sizing/leverage/vol scalar | AQC-1201 | 1.0d |
| **AQC-1268** | **Validation: Sizing & leverage axis (paired with 1230)** | AQC-1230, AQC-1260 | 0.75d |
| AQC-1231 | `is_pesc_blocked_codegen()` — reentry cooldown + ADX interpolation | AQC-1201 | 0.5d |
| AQC-1232 | Parity test: sizing + cooldowns vs CPU (integration) | AQC-1268, AQC-1269 | 0.5d |
| AQC-1233 | Wire codegen'd sizing/cooldowns into `sweep_engine.cu` | AQC-1232 | 0.5d |
| AQC-1252 | Add pyramiding `add_min_confidence` check to GPU orchestration | AQC-1233 | 0.25d |

### Phase 4: Integration & Validation (AQC-1240 — AQC-1244)

| Ticket | Title | Depends On | Est. |
|--------|-------|-----------|------|
| AQC-1240 | Full sweep parity test: 100 random configs, 3-month fixture | AQC-1213, 1226, 1233 | 1.0d |
| AQC-1241 | WGSL shader: apply same codegen patterns (or deprecate) | AQC-1240 | 1.0d |
| AQC-1242 | CI gate: `gpu-decision-parity-gate.yml` blocks PR on drift | AQC-1240 | 0.5d |
| AQC-1243 | Remove dead hand-written decision code from `sweep_engine.cu` | AQC-1240 | 0.5d |
| AQC-1244 | Documentation: developer guide "How to sync decision codegen" | AQC-1242 | 0.5d |

---

## Total Estimate

| Phase | Impl Tickets | Val Tickets | Dev Days |
|-------|-------------|-------------|----------|
| Phase 0: Infra + Config | 4 | 2 (AQC-1260, 1270) | 4.0 |
| Phase 1: Gates & Signals | 4 | 2 (AQC-1261, 1262) | 6.0 |
| Phase 2: Exits | 7 | 5 (AQC-1263–1267) | 11.25 |
| Phase 2b: Entry/Exit Cooldowns | 1 | 1 (AQC-1269) | 1.25 |
| Phase 3: Sizing & Cooldowns | 5 | 1 (AQC-1268) | 3.5 |
| Phase 4: Integration | 5 | — | 3.5 |
| **Total** | **26** | **11** = **37 tickets** | **29.5 days** |

---

## Ticket Details

### AQC-1200: Source-hash drift detector in `build.rs`

**Goal**: Warn at build time if kernel Rust source changed but codegen hasn't been re-run.

**Implementation**:
```
build.rs enhancements:
1. Compute SHA-256 of each source file:
   - bt-signals/src/gates.rs
   - bt-signals/src/entry.rs
   - bt-core/src/exits/stop_loss.rs
   - bt-core/src/exits/trailing.rs
   - bt-core/src/exits/take_profit.rs
   - bt-core/src/exits/smart_exits.rs
   - bt-core/src/exits/mod.rs
2. Compare against hashes embedded in generated CUDA header comment
3. If mismatch → cargo:warning + fail build if STRICT_CODEGEN_PARITY=1
4. Write rerun-if-changed directives for all source files
```

**Acceptance Criteria**:
- `cargo build -p bt-gpu` succeeds when sources unchanged
- Modifying any source file triggers codegen re-run
- If codegen output is stale (manual edit), build warns with file list
- `STRICT_CODEGEN_PARITY=1` env var promotes warning to hard error (for CI)

**Files**: `backtester/crates/bt-gpu/build.rs`

---

### AQC-1201: Decision codegen module scaffold

**Goal**: Create the module structure for decision logic codegen, parallel to existing accounting codegen.

**Implementation**:
```
New files:
  bt-gpu/codegen/decision_templates.rs  — template functions for all decision logic
  bt-gpu/codegen/decision.rs            — render_all_decision() orchestrator

Modify:
  bt-gpu/codegen/mod.rs  — add decision module, call from run()
  bt-gpu/build.rs         — emit generated_decision.cu alongside generated_accounting.cu
```

**Skeleton**:
```rust
// decision_templates.rs
pub const DECISION_HEADER: &str = "// AUTO-GENERATED from Rust kernel source. DO NOT EDIT.\n// ...";

pub fn check_gates_codegen() -> String { todo!("AQC-1210") }
pub fn generate_signal_codegen() -> String { todo!("AQC-1211") }
pub fn compute_sl_price_codegen() -> String { todo!("AQC-1220") }
pub fn compute_trailing_codegen() -> String { todo!("AQC-1221") }
pub fn check_tp_codegen() -> String { todo!("AQC-1222") }
pub fn check_smart_exits_codegen() -> String { todo!("AQC-1223") }
pub fn check_all_exits_codegen() -> String { todo!("AQC-1224") }
pub fn compute_entry_size_codegen() -> String { todo!("AQC-1230") }
pub fn is_pesc_blocked_codegen() -> String { todo!("AQC-1231") }
```

**Acceptance Criteria**:
- `cargo build -p bt-gpu` compiles (stubs produce empty strings initially)
- `generated_decision.cu` is emitted to out_dir and inspect_dir
- Existing accounting codegen unchanged

**Files**: `bt-gpu/codegen/decision_templates.rs`, `bt-gpu/codegen/decision.rs`, `bt-gpu/codegen/mod.rs`

---

### AQC-1202: Per-function parity test harness

**Goal**: Create test infrastructure that runs Rust decision functions and CUDA-codegen'd equivalents on identical inputs, comparing outputs.

**Implementation**:
```
New file: bt-gpu/tests/gpu_decision_parity.rs

Test structure:
1. Load fixture data (IndicatorSnapshot, StrategyConfig, Position)
2. For each function pair (Rust vs codegen'd):
   a. Call Rust function directly (bt-signals/bt-core crate)
   b. Compile codegen'd CUDA to host-callable function via nvcc
   c. Call CUDA host wrapper with same inputs
   d. Compare outputs within tolerance

Tolerance:
- Boolean/enum outputs: exact match
- f64 thresholds: ±1e-9 relative
- PnL/accounting: ±1e-12 (quantization)

Fixture: reuse existing testdata/gpu_cpu_parity/fixture_1h_3m.csv
Generate 50 random StrategyConfig values per test
```

**Acceptance Criteria**:
- Test compiles and runs (initially all `#[ignore]` until codegen stubs implemented)
- Framework supports adding new function pairs incrementally
- Clear error messages showing which field diverged and by how much

**Files**: `bt-gpu/tests/gpu_decision_parity.rs`, `bt-gpu/tests/common/cuda_host_wrapper.rs`

---

### AQC-1210: `check_gates_codegen()` — gates template

**Goal**: Codegen CUDA equivalent of `bt-signals/src/gates.rs::check_gates()`.

**Source**: `gates.rs` (~280 code lines, 8 gates + TMC/AVE + DRE)

**Translation scope**:
- Ranging filter (vote system: ADX + BB width + RSI neutral)
- Anomaly filter (price_change_pct + ema_dev_pct)
- Extension filter (distance from EMA_fast)
- Volume confirmation (conditional OR/AND logic)
- ADX rising (saturation bypass)
- ADX threshold with TMC + AVE adaptive multipliers
- Macro alignment (EMA_macro check)
- BTC alignment (symbol check + ADX override)
- Slow-drift ranging override (EMA slope)
- Dynamic TP multiplier (ADX-based switch)
- DRE (linear RSI limit interpolation)

**Type mapping**:
- `GateResult` struct → CUDA `GateResult` with 19 fields (all bool/f32/f64)
- `Option<bool>` for btc_bullish → `int` sentinel (-1=unknown, 0=false, 1=true)
- `symbol == "BTC"` → pre-computed `bool is_btc` parameter

**Acceptance Criteria**:
- `check_gates_codegen()` returns valid CUDA `__device__` function
- All 19 GateResult fields populated
- Generated code compiles with nvcc
- Comment header references exact source file:line ranges

**Files**: `bt-gpu/codegen/decision_templates.rs`

---

### AQC-1211: `generate_signal_codegen()` — signal template

**Goal**: Codegen CUDA equivalent of `bt-signals/src/entry.rs::generate_signal()` + helpers.

**Source**: `entry.rs` (~230 code lines, 3 entry modes + 2 MACD helpers)

**Translation scope**:
- Mode 1: Standard trend (EMA alignment + DRE RSI + MACD gate + StochRSI + BTC + volume confidence)
- Mode 2: Pullback continuation (EMA cross detection + RSI/MACD filters)
- Mode 3: Slow drift (EMA slope + directional check)
- `check_macd_long()` / `check_macd_short()` → `switch(macd_mode)` in CUDA
- Confidence upgrade logic (volume-based → High)

**Critical fix**: CPU confidence is volume-based; current GPU uses DRE. Codegen will align GPU to CPU.

**Type mapping**:
- `MacdMode` enum → `unsigned int` (0=Accel, 1=Sign, 2=None)
- Return `(Signal, Confidence, f64)` → CUDA `SignalResult` struct
- `if let Some((sig,conf)) = try_*()` → struct return with `has_value` flag

**Acceptance Criteria**:
- All 3 entry modes codegen'd
- MACD helper functions codegen'd as separate `__device__` functions
- Confidence assignment matches CPU (volume-based, NOT DRE)
- Generated code compiles with nvcc

**Files**: `bt-gpu/codegen/decision_templates.rs`

---

### AQC-1212: Parity test — gates & signals

**Goal**: Verify codegen'd gates/signals produce identical results to Rust on fixture data.

**Test**: 50 random configs × 200 bars × 5 symbols = 50,000 decision points.
Compare all GateResult fields + SignalResult fields.

**Acceptance Criteria**: Zero mismatches above tolerance.

**Files**: `bt-gpu/tests/gpu_decision_parity.rs` (enable gates + signals tests)

---

### AQC-1213: Wire gates/signals codegen into `sweep_engine.cu`

**Goal**: Replace hand-written `check_gates()` and `generate_signal()` in sweep_engine.cu with `#include "generated_decision.cu"` calls.

**Approach**:
1. Add `#include "generated_decision.cu"` at top of sweep_engine.cu
2. Replace call sites to use `check_gates_codegen()`, `generate_signal_codegen()`
3. Delete old hand-written `check_gates()` (lines 271-344) and `generate_signal()` (lines 354-475)
4. Adapt struct layouts if needed (GateResult field names/types)

**Acceptance Criteria**:
- `sweep_engine.cu` compiles
- GPU sweep produces same results as CPU backtester (parity test from AQC-1212)
- No hand-written gate/signal code remains

**Files**: `bt-gpu/kernels/sweep_engine.cu`

---

### AQC-1220: `compute_sl_price_codegen()` — stop loss template

**Source**: `stop_loss.rs` (~125 code lines)
**Scope**: Base SL + ASE + DASE + SLB + breakeven
**Key**: `match pos.pos_type` → `if (pos.active == POS_LONG)`
**Files**: `bt-gpu/codegen/decision_templates.rs`

---

### AQC-1221: `compute_trailing_codegen()` — trailing stop template

**Source**: `trailing.rs` (~120 code lines)
**Scope**: Per-confidence overrides, RSI Trend-Guard, VBTS, high-profit tightening (TATP/TSPV), weak-trend, ratchet
**Key**: `Option<f64>` for trailing_sl → sentinel value; `matches!(confidence, Low)` → `==` check
**Critical fix**: WGSL hardcodes 6 params — codegen will read from config
**Files**: `bt-gpu/codegen/decision_templates.rs`

---

### AQC-1222: `check_tp_codegen()` — take profit template

**Source**: `take_profit.rs` (~130 code lines)
**Scope**: Full TP + partial TP ladder (tp1_taken flag, notional check, separate partial mult)
**Key**: `ExitAction` enum with data → `struct { int action; double fraction; }`
**Files**: `bt-gpu/codegen/decision_templates.rs`

---

### AQC-1223: `check_smart_exits_codegen()` — smart exits template

**Source**: `smart_exits.rs` (~280 code lines, largest module)
**Scope**: 8 sub-checks:
1. EMA cross + TBB buffer (weak cross suppression)
2. Trend exhaustion (ADX threshold with entry_adx fallback)
3. EMA macro breakdown (conditional on require_macro_alignment)
4. Stagnation exit (ATR contraction + underwater, skip PAXG)
5. Funding headwind (disabled in backtester v1, emit as no-op)
6. TSME (trend saturation momentum exit)
7. MMDE (4-bar MACD divergence)
8. RSI overextension (profit-dependent bounds, low-conf overrides)

**Key**: `format!()` exit reason strings → integer exit codes
**Files**: `bt-gpu/codegen/decision_templates.rs`

---

### AQC-1224: `check_all_exits_codegen()` — exit orchestrator template

**Source**: `exits/mod.rs` (~125 code lines)
**Scope**: Priority dispatch: glitch guard → SL → TSL → TP → smart exits
**Depends on**: AQC-1220, 1221, 1222, 1223
**Files**: `bt-gpu/codegen/decision_templates.rs`

---

### AQC-1225: Parity test — all exits

**Test**: 50 configs × 200 bars × 5 symbols, with positions at various profit levels.
Compare SL price, trailing SL, TP decision, smart exit triggers.
**Files**: `bt-gpu/tests/gpu_decision_parity.rs`

---

### AQC-1226: Wire exits codegen into `sweep_engine.cu`

**Replace**: `compute_sl_price()` (479-532), `compute_trailing()` (536-602), `check_tp()` (607-663), `check_smart_exits()` (667-737)
**Delete**: All hand-written exit code
**Files**: `bt-gpu/kernels/sweep_engine.cu`

---

### AQC-1230: `compute_entry_size_codegen()` — sizing template

**Source**: engine.rs sizing logic
**Scope**: Base margin, dynamic sizing (conf_mult × adx_mult × vol_scalar), dynamic leverage, notional calc
**Files**: `bt-gpu/codegen/decision_templates.rs`

---

### AQC-1231: `is_pesc_blocked_codegen()` — cooldown template

**Source**: cooldowns logic (~23 code lines)
**Scope**: Reentry cooldown with ADX-dependent interpolation (min→max based on ADX 25-40)
**Files**: `bt-gpu/codegen/decision_templates.rs`

---

### AQC-1232: Parity test — sizing & cooldowns

**Test**: 50 configs × various equity/ADX/confidence combinations.
**Files**: `bt-gpu/tests/gpu_decision_parity.rs`

---

### AQC-1233: Wire sizing/cooldowns codegen into `sweep_engine.cu`

**Replace**: `compute_entry_size()` (747-788), `is_pesc_blocked()` (894-916)
**Files**: `bt-gpu/kernels/sweep_engine.cu`

---

### AQC-1240: Full sweep parity test

**Goal**: End-to-end validation — run 100 random parameter configs through both CPU backtester and GPU sweep, compare final PnL/trade count/win rate.

**Fixture**: 3-month 1h+3m data for 50 symbols
**Tolerance**: PnL ±$0.01 (1e-12 quantized), trade count exact, win rate ±0.001

**Files**: `bt-gpu/tests/gpu_sweep_full_parity.rs`

---

### AQC-1241: WGSL shader alignment or deprecation

**Decision**: Either (a) apply same codegen patterns to `sweep_engine.wgsl`, or (b) deprecate WGSL path.

**Context**: WGSL has 10+ divergences from CUDA (see research). If WebGPU sweep is used, it needs codegen too. If only CUDA is used in production, deprecate WGSL.

**Files**: `bt-gpu/shaders/sweep_engine.wgsl` (update or mark deprecated)

---

### AQC-1242: CI gate — `gpu-decision-parity-gate.yml`

**Goal**: PR that touches any of the 7 kernel source files MUST pass decision parity test.

**Trigger**: Changes to `bt-signals/src/*.rs` or `bt-core/src/exits/*.rs`
**Action**: `cargo test -p bt-gpu --test gpu_decision_parity --test gpu_sweep_full_parity`
**Failure**: Hard block (PR cannot merge)

**Files**: `.github/workflows/gpu-decision-parity-gate.yml`

---

### AQC-1243: Remove dead hand-written code

**Goal**: Delete all hand-written decision logic from `sweep_engine.cu` that has been replaced by codegen'd functions.

**Estimated removal**: ~800-1000 lines (gates, signals, exits, sizing, cooldowns)
**Keep**: Main kernel orchestration loop, indicator loading, result packing, equity tracking

**Files**: `bt-gpu/kernels/sweep_engine.cu`

---

### AQC-1244: Developer guide

**Goal**: Document the codegen workflow for future developers.

**Contents**:
1. How to add a new gate/exit/signal check
2. How to update an existing threshold
3. How to run parity tests locally
4. How the drift detector works
5. How CI catches desynchronization

**Files**: `backtester/docs/gpu-codegen-guide.md`

---

## Dependency Graph

```
AQC-1200 (drift detector)  ─┐
AQC-1201 (scaffold)        ─┤
                             ├── AQC-1202 (parity harness)
                             ├── AQC-1260 (f32/f64 precision benchmark)
                             ├── AQC-1250 (config struct) ─┬── AQC-1270 (VAL: config round-trip 141 fields)
                             │                              ├── AQC-1210 (gates) → AQC-1261 (VAL: gates) ──┐
                             │                              ├── AQC-1211 (signals) → AQC-1262 (VAL: signals) ┤→ AQC-1212 (integration) → AQC-1213 (wire)
                             │                              └── AQC-1251 (entry/exit cooldowns)
                             │
                             ├── AQC-1220 (SL) → AQC-1263 (VAL: SL) ─────────┐
                             ├── AQC-1221 (TSL) → AQC-1264 (VAL: trailing) ───┤
                             ├── AQC-1222 (TP) → AQC-1265 (VAL: TP) ──────────┤
                             ├── AQC-1223 (smart) → AQC-1266 (VAL: smart) ────┤
                             ├── AQC-1224 (orchestrator) → AQC-1267 (VAL: orch) ┤→ AQC-1225 (integration) → AQC-1226 (wire)
                             │
                             ├── AQC-1230 (sizing) → AQC-1268 (VAL: sizing) ─┐
                             ├── AQC-1231 (PESC) ─────────────────────────────┤
                             └── AQC-1251 (cooldowns) → AQC-1269 (VAL: PESC+cooldowns) ┤→ AQC-1232 (integration) → AQC-1233 (wire) → AQC-1252 (pyramid conf)

All AQC-126x validation tickets also depend on AQC-1260 (precision benchmark)

AQC-1213 + AQC-1226 + AQC-1233 + AQC-1252 → AQC-1240 (full parity)
                                               → AQC-1241 (WGSL)
                                               → AQC-1242 (CI gate)
                                               → AQC-1243 (cleanup)
                                               → AQC-1244 (docs)
```

---

## Success Criteria

1. GPU sweep produces **identical** PnL/trade count/win rate to CPU backtester for any config
2. Build fails if kernel source changes without codegen re-run (`STRICT_CODEGEN_PARITY=1`)
3. CI blocks PRs that break decision parity
4. Zero hand-written decision logic remains in `sweep_engine.cu`
5. Developer can add a new gate/exit in <30 minutes (Rust change + template update + parity test)

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Template drift (silent wrong results) | AQC-1200 hash detector + AQC-1242 CI gate |
| Precision divergence (f32 vs f64) | AQC-1202 parity harness — tolerance may need relaxation to ~1e-6 for f32 |
| WGSL bitrot | AQC-1241 forces decision: codegen or deprecate |
| Build complexity | AQC-1201 scaffold keeps decision codegen modular |
| Regression during wiring | AQC-1213/1226/1233 wire incrementally with parity checks |
| Orchestration drift (not caught by detector) | AQC-1200 only monitors 7 Rust files — `engine.rs` changes need manual review |
| Trailing stop sweep-ability loss | Codegen hardcodes Rust values (VBTS 1.2, tighten 0.5/0.75/1.0) — trade-off accepted for SSOT |
| Dynamic TP ambiguity | `dynamic_tp_mult` computed in gates but CPU exits use `cfg.tp_atr_mult` — verify before codegen |

---

## Holistic Review Findings (2026-02-16)

Reviewer agent performed line-by-line comparison of all 23 original tickets against:
- `sweep_engine.cu` (1674 lines CUDA)
- 7 Rust kernel source files
- `GpuComboConfig` in `buffers.rs`
- CPU engine orchestration in `engine.rs`
- TPE sweep pipeline in `tpe_sweep.rs`

### Gaps Found → New Tickets Created

| Gap | Root Cause | Fix Ticket |
|-----|-----------|------------|
| 11 config fields missing from `GpuComboConfig` | GPU never had pullback, anomaly, ranging, stoch_rsi, ave_enabled, tp_mult_strong/weak | AQC-1250 (#325) |
| `entry_cooldown_s` / `exit_cooldown_s` absent on GPU | CPU has per-symbol time cooldowns, GPU has none | AQC-1251 (#326) |
| Pyramiding skips `add_min_confidence` check | Config field exists but never used in GPU pyramid logic | AQC-1252 (#327) |

### Known Divergences (Will Be Fixed by Existing Tickets)

| Divergence | GPU Behavior | CPU Behavior | Fixed By |
|-----------|-------------|-------------|----------|
| Confidence assignment | DRE + AVE based | Volume-based | AQC-1211 |
| Anomaly filter metric | `bb_width_ratio` | `price_change_pct + ema_dev_pct` | AQC-1210 |
| TMC adjustment | Not implemented | ADX slope > 0.5 caps min_adx at 25 | AQC-1210 |
| TSME contraction | 1-bar check | 2 consecutive bars | AQC-1223 |
| MMDE thresholds | `profit_atr > 0.5`, no ADX | `profit_atr > 1.5 AND adx > 35` | AQC-1223 |
| Smart exit TBB buffer | None | Weak cross suppression | AQC-1223 |
| EMA macro breakdown | Always checks | Only if `require_macro_alignment` | AQC-1223 |
| Stagnation exit | Not implemented | ATR contraction + underwater | AQC-1223 |

### Accepted Trade-offs

1. **Orchestration loop stays hand-written** (AQC-1243) — entry ranking, margin checks, slippage not codegen'd
2. **MAE/MFE not tracked on GPU** — intentional, not needed for sweep optimization
3. **Trailing hardcoded values lose sweep-ability** — SSOT correctness > parameter sweep space
4. **f32 precision** — parity tolerance may need relaxation from 1e-9 to ~1e-6
