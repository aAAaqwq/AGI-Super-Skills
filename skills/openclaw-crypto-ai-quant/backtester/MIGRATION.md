# V8 SSOT Migration

**Status**: Complete — merged to `master`.

## Archive

The legacy main-branch backtester is tagged as `archive/main-backtester-v6`. It is read-only and retained for reference.

## What Changed

V8 establishes a **single source of truth (SSOT)** architecture:

- **Decision Kernel** (`crates/bt-core/src/decision_kernel.rs`): Pure deterministic state machine shared by all execution paths (CPU replay, GPU sweep, live/paper via PyO3 bridge)
- **GPU Sweep** (`crates/bt-gpu/kernels/sweep_engine.cu`): CUDA kernel aligned with CPU kernel semantics via template-based codegen (glitch guard, trailing SL, f64 accounting)
- **GPU Decision Codegen** (`crates/bt-gpu/codegen/`): All GPU decision functions (gates, signals, exits, sizing, cooldowns) are generated from Rust kernel source — no hand-written decision logic in CUDA
- **PyO3 Bridge** (`crates/bt-runtime/src/lib.rs`): Rust-to-Python FFI for live/paper trading via `step_full()`, `apply_funding()`, `get_equity()`
- **Parity Tests**: GPU-to-CPU, codegen drift detection, and three-way parity frameworks

## Key Files

| File | Role |
|------|------|
| `crates/bt-core/src/decision_kernel.rs` | SSOT decision kernel |
| `crates/bt-signals/src/` | Signal generation (shared across all paths) |
| `crates/bt-gpu/kernels/sweep_engine.cu` | GPU sweep engine |
| `crates/bt-gpu/codegen/` | Template-based CUDA codegen from Rust source |
| `crates/bt-gpu/src/buffers.rs` | GPU config/state layout (512B config, 4032B state) |
| `crates/bt-runtime/src/lib.rs` | PyO3 bridge |
| `crates/risk-core/src/lib.rs` | Shared risk primitives |

## References

- [GPU Codegen Developer Guide](docs/gpu-codegen-guide.md)
- [GPU Runtime Validation Report](docs/gpu-runtime-validation-report.md)
