# GPU Decision Codegen Developer Guide

How to sync, extend, and debug the GPU decision codegen system.

**Audience**: Developers modifying GPU decision logic who are new to this codegen system.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Adding a New Gate, Exit, or Signal](#adding-a-new-gate-exit-or-signal)
3. [Updating Thresholds or Existing Logic](#updating-thresholds-or-existing-logic)
4. [Precision Rules (T0-T4)](#precision-rules-t0-t4)
5. [Running Parity Tests](#running-parity-tests)
6. [Source-Hash Drift Detector](#source-hash-drift-detector)
7. [CI Pipeline](#ci-pipeline)
8. [Rollback Procedure](#rollback-procedure)
9. [Common Pitfalls](#common-pitfalls)

---

## Architecture Overview

The GPU decision kernel does not contain hand-written trade logic. All decision
functions (gates, signals, exits, sizing, cooldowns) are **generated from Rust
template functions** at build time. The flow:

```
decision_templates.rs      Rust string templates (CUDA source as &str)
        |
        v
  render_all_decision()    Concatenates all templates into one string
        |                  (codegen/decision/mod.rs)
        v
   emit.rs                 Writes to kernels/generated_decision.cu
        |                  + $OUT_DIR/generated_decision.cu
        v
 sweep_engine.cu           #include "generated_decision.cu"
        |                  Thin wrappers cast float<->double
        v
     nvcc                  Compiles to PTX (build.rs)
```

### Key files

| File | Role |
|------|------|
| `codegen/decision/decision_templates.rs` | Template functions returning CUDA source strings |
| `codegen/decision/mod.rs` | `render_all_decision()` orchestrator |
| `codegen/emit.rs` | Filesystem writer |
| `codegen/drift.rs` | Source-hash drift detector |
| `codegen/mod.rs` | Top-level entry: accounting + decision codegen |
| `kernels/sweep_engine.cu` | Production kernel with thin wrappers over codegen |
| `kernels/generated_decision.cu` | AUTO-GENERATED output (do not edit) |
| `build.rs` | Build script: drift check + codegen + nvcc compilation |

### Data flow at runtime

`sweep_engine.cu` stores indicators as `float` in `GpuSnapshot` structs. The
thin wrapper functions cast `float` to `double` on the way in to codegen
functions, and cast `double` back to `float` on the way out. This preserves
the f64 precision of the Rust SSOT inside the codegen functions while keeping
the kernel's storage footprint in f32.

Example thin wrapper (gates):

```cuda
// In sweep_engine.cu
__device__ GateResult check_gates(const GpuSnapshot& snap,
                                   const GpuComboConfig* cfg, ...) {
    GateResultD gd = check_gates_codegen(
        *cfg,
        (double)snap.rsi,       // float -> double
        (double)snap.adx,
        (double)snap.adx_slope,
        // ... all inputs promoted to double
    );

    // Convert GateResultD -> GateResult (double -> float facade)
    GateResult result;
    result.all_gates_pass   = gd.all_gates_pass;
    result.bullish_alignment = gd.bullish_alignment;
    // ...
    return result;
}
```

### Current codegen functions

| Template function | Mirrors | Ticket |
|-------------------|---------|--------|
| `check_gates_codegen()` | `bt-signals/src/gates.rs` | AQC-1210 |
| `generate_signal_codegen()` | `bt-signals/src/entry.rs` | AQC-1211 |
| `compute_sl_price_codegen()` | `bt-core/src/exits/stop_loss.rs` | AQC-1220 |
| `compute_trailing_codegen()` | `bt-core/src/exits/trailing.rs` | AQC-1221 |
| `check_tp_codegen()` | `bt-core/src/exits/take_profit.rs` | AQC-1222 |
| `check_smart_exits_codegen()` | `bt-core/src/exits/smart_exits.rs` | AQC-1223 |
| `check_all_exits_codegen()` | `bt-core/src/exits/mod.rs` | AQC-1224 |
| `compute_entry_size_codegen()` | `risk-core/src/lib.rs` | AQC-1230 |
| `is_pesc_blocked_codegen()` | `bt-core/src/engine.rs` | AQC-1231 |

---

## Adding a New Gate, Exit, or Signal

Follow this step-by-step checklist. Example: adding a hypothetical "Funding
Rate Exit" (sub-check 5 in smart exits, currently a no-op placeholder).

### Step 1: Write the template function

Add or modify a function in `decision_templates.rs`. Each template function
returns a `String` containing the CUDA device function source:

```rust
// In decision_templates.rs
pub fn check_funding_exit_codegen() -> String {
    r#"// Derived from bt-core/src/exits/funding.rs
// Funding headwind exit: closes position when funding rate is adverse.
// All price math in double precision (AQC-734).

__device__ bool check_funding_exit_codegen(
    const GpuComboConfig& cfg,
    int pos_type,
    double funding_rate,
    double profit_atr
) {
    if (cfg.enable_funding_exit == 0u) { return false; }

    // Long pays funding when rate > 0; short pays when rate < 0
    bool is_headwind = (pos_type == POS_LONG)
        ? (funding_rate > (double)cfg.funding_headwind_threshold)
        : (funding_rate < -(double)cfg.funding_headwind_threshold);

    return is_headwind && (profit_atr < (double)cfg.funding_exit_max_profit_atr);
}
"#
    .to_string()
}
```

Key conventions:
- Doc comment references the Rust source file it mirrors.
- All indicator/price math uses `double`.
- All config values accessed via `cfg.field_name` with `(double)` cast.
- No hardcoded magic numbers -- every tunable comes from `GpuComboConfig`.
- Function name ends with `_codegen`.

### Step 2: Wire into render_all_decision()

In `codegen/decision/mod.rs`, add the new template to the render pipeline:

```rust
// In render_all_decision()
out.push_str(&decision_templates::check_funding_exit_codegen());
```

Place it in the correct phase (gates, exits, sizing, or cooldowns).

### Step 3: Add config fields to GpuComboConfig

In `sweep_engine.cu`, add the new fields to `struct GpuComboConfig`:

```cuda
// In GpuComboConfig, at the end of the decision codegen fields section:
unsigned int enable_funding_exit;
float funding_headwind_threshold;
float funding_exit_max_profit_atr;
```

Also add matching fields to the Rust `GpuComboConfig` in `src/buffers.rs` so
the `#[repr(C)]` layout matches exactly.

### Step 4: Write a thin wrapper in sweep_engine.cu

Add a thin wrapper that casts `float` inputs to `double` and calls the codegen
function:

```cuda
// In sweep_engine.cu, after the codegen #include
__device__ bool check_funding_exit(const GpuPosition& pos,
                                    const GpuSnapshot& snap,
                                    const GpuComboConfig* cfg,
                                    float p_atr) {
    return check_funding_exit_codegen(
        *cfg,
        (int)pos.active,
        (double)snap.funding_rate,
        (double)p_atr
    );
}
```

### Step 5: Call from the kernel

Wire the new function into the main `sweep_engine_kernel` at the appropriate
point in the exit priority chain.

### Step 6: Update the drift detector source list

In `codegen/drift.rs`, add the new Rust source file to `DECISION_SOURCE_FILES`:

```rust
pub const DECISION_SOURCE_FILES: &[&str] = &[
    "../bt-signals/src/gates.rs",
    "../bt-signals/src/entry.rs",
    "../bt-core/src/exits/stop_loss.rs",
    // ... existing entries ...
    "../bt-core/src/exits/funding.rs",   // <-- new
];
```

### Step 7: Add parity tests

Add test cases in `tests/gpu_decision_parity.rs` that validate:
1. **Constant matching**: thresholds from Rust appear in CUDA codegen.
2. **Branch coverage**: every conditional path has a corresponding test.
3. **Precision tier**: declare which tier (T0-T4) governs each comparison.

### Step 8: Rebuild and test

```bash
cd backtester
cargo test -p bt-gpu --features codegen --test gpu_decision_parity
cargo test -p bt-gpu --features codegen --test gpu_sweep_full_parity
```

---

## Updating Thresholds or Existing Logic

When changing an existing decision function (e.g., adjusting the ASE tightening
factor from 0.80 to 0.75):

1. **Edit the Rust SSOT first** (e.g., `bt-core/src/exits/stop_loss.rs`).
2. **Mirror the change** in `decision_templates.rs`. Find the corresponding
   section by searching for the comment block (e.g., `ASE`):

   ```rust
   // In compute_sl_price_codegen()
   // Before:
   if (adx_slope < 0.0 && is_underwater) {
       sl_mult *= 0.8;   // ASE tightening: 20%
   }
   // After:
   if (adx_slope < 0.0 && is_underwater) {
       sl_mult *= 0.75;  // ASE tightening: 25%
   }
   ```

3. **Do not edit `generated_decision.cu` directly** -- it will be overwritten.
4. **Run parity tests** to confirm the GPU output still matches CPU:

   ```bash
   cargo test -p bt-gpu --features codegen --test gpu_decision_parity
   ```

5. **If adding a new config field**: update both `GpuComboConfig` in
   `sweep_engine.cu` (CUDA) and `src/buffers.rs` (Rust). The `#[repr(C)]`
   layout must match byte-for-byte.

---

## Precision Rules (T0-T4)

The GPU stores indicators as `float` (f32) but the Rust SSOT uses `f64`. The
codegen functions operate in `double` precision internally, but values are
round-tripped through `float` at the thin wrapper boundary.

Precision tiers are defined in `src/precision.rs`:

| Tier | Tolerance | Use Case | Example |
|------|-----------|----------|---------|
| **T0** | 0 (exact) | Booleans, enums, gate pass/fail | `all_gates_pass`, `signal == SIG_BUY` |
| **T1** | 1.2e-7 | Config lookups, direct comparisons | `cfg.min_adx` read-back |
| **T2** | 1e-6 | Single arithmetic op | `entry_price - atr * sl_mult` |
| **T3** | 1e-5 | Multi-step chains (5-10 ops) | EMA deviation, DRE weight |
| **T4** | 1e-3 | Running sums, catastrophic cancellation | Cumulative PnL, MACD line |

### Rules for template authors

1. **All price/indicator math** in codegen functions must use `double`. Cast
   config values with `(double)cfg.field_name`.

2. **Use `fmax`/`fmin`** (not `std::max`/`std::min`) for clamping. These are
   CUDA device math intrinsics that work on `double`.

3. **The thin wrapper handles precision boundaries**. Inputs are promoted
   `(double)snap.field`, outputs are demoted `(float)result.field`.

4. **Tier violations are BLOCKERs**. If a parity test shows a T2-expected
   comparison failing beyond T2 tolerance, the codegen must be fixed (not the
   tolerance loosened).

### The `SizingResultD` vs `SizingResult` pattern

Codegen functions that return structs with `double` fields use a `D`-suffixed
struct name to avoid collisions with the `float`-based structs in
`sweep_engine.cu`:

```cuda
// In generated_decision.cu (codegen output)
struct SizingResultD {    // double-precision codegen struct
    double size;
    double margin;
    double leverage;
};

// In sweep_engine.cu (kernel facade)
struct SizingResult {     // float-precision wrapper struct
    float size;
    float margin;
    float leverage;
};

// Thin wrapper bridges the two:
__device__ SizingResult compute_entry_size(...) {
    SizingResultD sd = compute_entry_size_codegen(...);
    SizingResult result;
    result.size = (float)sd.size;       // double -> float
    result.margin = (float)sd.margin;
    result.leverage = (float)sd.leverage;
    return result;
}
```

---

## Running Parity Tests

All parity tests require the `codegen` feature flag.

### Per-function parity (50 fixtures, constant + branch validation)

```bash
cd backtester
cargo test -p bt-gpu --features codegen --test gpu_decision_parity
```

### Full-sweep parity (100 random configs, 90-day synthetic data)

```bash
cargo test -p bt-gpu --features codegen --test gpu_sweep_full_parity -- --nocapture
```

### Unit tests (codegen module internals)

```bash
cargo test -p bt-gpu --features codegen --lib
```

### All tests together (what CI runs)

```bash
cargo test -p bt-gpu --features codegen \
  --test gpu_decision_parity \
  --test gpu_sweep_full_parity
cargo test -p bt-gpu --features codegen --lib
```

### What the tests validate

- `gpu_decision_parity.rs`: Per-function structural validation against 50
  diverse fixtures (penny stocks to BTC, long/short, profit/loss, all trend
  regimes). Tests constant matching, branch coverage, and precision tiers.

- `gpu_sweep_full_parity.rs`: End-to-end sweep with 100 seeded random configs
  over 2160 bars (90 days). Validates directional sanity, f32 round-trip
  precision, cross-function consistency, and PESC monotonicity.

---

## Source-Hash Drift Detector

The drift detector (defined in `codegen/drift.rs`) prevents the generated CUDA
from going stale when someone edits the Rust SSOT without updating codegen.

### How it works

1. **`build.rs` always runs drift detection** (even without `--features codegen`).

2. It computes SHA-256 hashes of these Rust source files:
   ```
   ../bt-signals/src/gates.rs
   ../bt-signals/src/entry.rs
   ../bt-core/src/exits/stop_loss.rs
   ../bt-core/src/exits/trailing.rs
   ../bt-core/src/exits/take_profit.rs
   ../bt-core/src/exits/smart_exits.rs
   ../bt-core/src/exits/mod.rs
   ```

3. Hashes are written to `kernels/decision_source_hashes.json` (manifest).

4. When `--features codegen` is enabled, hashes are embedded as a comment in
   `generated_decision.cu`:
   ```
   // SOURCE_HASHES: {"../bt-core/src/exits/mod.rs":"a1b2c3...","../bt-core/src/exits/stop_loss.rs":"d4e5f6..."}
   ```

5. On subsequent builds, `build.rs` compares current hashes against embedded
   hashes. If they differ:
   - Default: emits `cargo:warning=Decision source drift detected!`
   - With `STRICT_CODEGEN_PARITY=1`: **panics** (build fails)

### How to update hashes after editing Rust source

Simply rebuild with the codegen feature enabled:

```bash
cargo build -p bt-gpu --features codegen
```

This regenerates `generated_decision.cu` with fresh hashes. The next build
will see matching hashes and the drift warning disappears.

### Adding a new source file to the watch list

Edit `DECISION_SOURCE_FILES` in `codegen/drift.rs`:

```rust
pub const DECISION_SOURCE_FILES: &[&str] = &[
    "../bt-signals/src/gates.rs",
    // ... existing ...
    "../bt-core/src/exits/new_file.rs",  // <-- add here
];
```

---

## CI Pipeline

The `gpu-decision-parity-gate.yml` workflow runs on every PR that touches
decision-related source files.

### Trigger paths

```yaml
on:
  pull_request:
    paths:
      - 'backtester/crates/bt-signals/src/**'
      - 'backtester/crates/bt-core/src/**'
      - 'backtester/crates/bt-gpu/codegen/**'
      - 'backtester/crates/bt-gpu/kernels/**'
      - 'backtester/crates/bt-gpu/src/**'
      - 'backtester/crates/risk-core/src/**'
```

### What it runs

1. `cargo test -p bt-gpu --features codegen --test gpu_decision_parity --test gpu_sweep_full_parity`
2. `cargo test -p bt-gpu --features codegen --lib`

### What this means for you

- Any change to the Rust SSOT files (`bt-signals`, `bt-core`, `risk-core`)
  triggers the gate.
- Any change to codegen templates, kernels, or `bt-gpu/src/` triggers the gate.
- If you edit a Rust source file without updating the corresponding codegen
  template, the parity tests will fail and block the PR.

---

## Rollback Procedure

If a codegen change breaks production builds or GPU parity:

### Quick rollback (revert the codegen commit)

```bash
# Find the bad commit
git log --oneline -- backtester/crates/bt-gpu/codegen/

# Revert it
git revert <commit-hash>
```

This restores the previous `decision_templates.rs` and the next build
regenerates `generated_decision.cu` from the old templates.

### Emergency: use the last known-good generated file

If you need the kernel running immediately and cannot wait for a clean revert:

```bash
# The generated file is checked into kernels/ for inspection.
# Revert just that file to the last working version:
git checkout <known-good-commit> -- backtester/crates/bt-gpu/kernels/generated_decision.cu

# Build WITHOUT codegen to skip regeneration:
cargo build -p bt-gpu
# (omitting --features codegen means build.rs skips codegen, uses existing file)
```

The drift detector will emit a warning about hash mismatch, but the build will
succeed.

### Re-enabling codegen after rollback

Once you have a fix ready:

```bash
# Apply the fix to decision_templates.rs
# Rebuild with codegen to regenerate the file:
cargo build -p bt-gpu --features codegen

# Run parity tests:
cargo test -p bt-gpu --features codegen --test gpu_decision_parity
cargo test -p bt-gpu --features codegen --test gpu_sweep_full_parity

# Commit both the template fix and the regenerated .cu file
git add backtester/crates/bt-gpu/codegen/ backtester/crates/bt-gpu/kernels/generated_decision.cu
git commit -m "fix: restore GPU decision codegen parity"
```

---

## Common Pitfalls

### 1. `fmax`/`fmin` vs `std::max`/`std::min`

CUDA device code must use `fmax()` and `fmin()` for floating-point clamping.
`std::max` and `std::min` are host functions and will cause compilation errors
in `__device__` code.

```cuda
// WRONG: will not compile in __device__ context
double clamped = std::max(std::min(weight, 1.0), 0.0);

// CORRECT: CUDA math intrinsics
double clamped = fmax(fmin(weight, 1.0), 0.0);
```

### 2. `SizingResultD` vs `SizingResult`

Codegen functions return `double`-precision structs (`SizingResultD`,
`GateResultD`). The kernel uses `float`-precision facade structs
(`SizingResult`, `GateResult`). Never mix them:

```cuda
// WRONG: type mismatch
SizingResult sd = compute_entry_size_codegen(...);

// CORRECT: use the D-suffixed struct, then convert
SizingResultD sd = compute_entry_size_codegen(...);
SizingResult result;
result.size = (float)sd.size;
```

### 3. Always cast `float` to `double` at the wrapper boundary

Every `float` value from `GpuSnapshot` or `GpuPosition` must be explicitly
cast to `double` before passing to codegen functions. Missing casts cause
silent precision loss:

```cuda
// WRONG: implicit float arithmetic inside codegen
double sl = compute_sl_price_codegen(cfg, pos.active,
    pos.entry_price,    // still float!
    snap.atr, ...);

// CORRECT: explicit double promotion
double sl = compute_sl_price_codegen(cfg,
    (int)pos.active,
    (double)pos.entry_price,
    (double)snap.atr, ...);
```

### 4. Config field `(double)` casts inside templates

Inside codegen template strings, always cast config values:

```cuda
// WRONG: float multiplication in the middle of double arithmetic
double threshold = cfg.min_adx * 1.5;

// CORRECT: promote to double first
double threshold = (double)cfg.min_adx * 1.5;
```

`GpuComboConfig` fields are `float` (f32). Forgetting the cast introduces
T1-level errors that compound through multi-step chains.

### 5. Do not edit `generated_decision.cu`

The file header says it:
```
// AUTO-GENERATED from bt-signals + bt-core kernel source -- DO NOT EDIT
```

Any edits will be overwritten on the next `cargo build --features codegen`.
Always edit `decision_templates.rs` instead.

### 6. Forgetting to update `GpuComboConfig` on both sides

The CUDA struct in `sweep_engine.cu` and the Rust struct in `src/buffers.rs`
must have identical layout (`#[repr(C)]`). If you add a field to one but not
the other, the kernel will read garbage values. The config round-trip parity
test (AQC-1270) catches this.

### 7. `unsigned int` vs `int` in codegen function signatures

Gate results and signal types use `unsigned int` in the kernel but codegen
functions sometimes use `int` (e.g., `pos_type`, `confidence`). The thin
wrappers handle the conversion. Keep the convention consistent:
- `pos_type`, `confidence`, `signal` -> `int` inside codegen
- `unsigned int` in the kernel facade

### 8. The `POS_LONG`/`POS_SHORT` constants

These are `#define`d in `sweep_engine.cu` but used inside codegen templates.
Since `generated_decision.cu` is `#include`d after the defines, the constants
are available. However, some codegen functions use literal values for clarity:

```cuda
if (pos_type == 1) {  // POS_LONG
```

Both styles work, but always add the comment showing which constant is meant.

---

## Quick Reference Card

| Task | Command |
|------|---------|
| Rebuild codegen | `cargo build -p bt-gpu --features codegen` |
| Run parity tests | `cargo test -p bt-gpu --features codegen --test gpu_decision_parity --test gpu_sweep_full_parity` |
| Run unit tests | `cargo test -p bt-gpu --features codegen --lib` |
| Check drift | `STRICT_CODEGEN_PARITY=1 cargo build -p bt-gpu` |
| Build without codegen (emergency) | `cargo build -p bt-gpu` |
| Inspect generated output | `cat kernels/generated_decision.cu` |
| Inspect hash manifest | `cat kernels/decision_source_hashes.json` |
