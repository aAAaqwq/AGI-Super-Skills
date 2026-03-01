# Phase 2: Double-Buffer TPE Pipeline

> **Status**: Planned. See [GPU_UTILIZATION_RESEARCH.md](GPU_UTILIZATION_RESEARCH.md) for context.

## Goal
Overlap CPU-side TPE `ask()` with GPU kernel execution to reach ~92-95% GPU utilization.

## Current Flow (Serial)
```
Round 0:  [ask_0  5.2s] → [gpu_0  8.8s] → [tell_0  0.1s]
Round 1:                                    [ask_1  5.2s] → [gpu_1  8.8s] → [tell_1  0.1s]
                                                            ↑ GPU idle 5.2s
Total per round: 14.1s     GPU util: 62%
```

## Target Flow (Pipelined)
```
TPE thread:  [ask_0] → [tell_0 + ask_1] → [tell_1 + ask_2] → [tell_2 + ask_3] → ...
GPU thread:             [gpu_0]          → [gpu_1]          → [gpu_2]          → ...
             ↑ priming   ↑ overlap         ↑ overlap          ↑ overlap
Total per round: max(ask, gpu) ≈ 8.8s     GPU util: ~95%
```

## Architecture

### Two Threads
1. **GPU thread** (main thread) — owns `GpuDeviceState`, arena buffers, CUDA context
2. **TPE thread** (spawned) — owns `axis_opts`, observation cache, RNG

### Communication (crossbeam channels)
```
                 ┌──────────────────┐
  trial_tx ────→ │   GPU Thread     │ ────→ result_tx
                 │  evaluate batch  │
  trial_rx ←──── │  build results   │ ←──── result_rx
                 └──────────────────┘

                 ┌──────────────────┐
  result_tx ───→ │   TPE Thread     │ ───→ trial_tx
                 │  tell() results  │
  result_rx ←─── │  ask() next batch│ ←─── trial_rx
                 └──────────────────┘
```

**Messages:**
```rust
/// GPU thread → TPE thread: results from batch N
struct GpuBatchResult {
    batch_idx: usize,
    results: Vec<buffers::GpuResult>,           // raw GPU output
    trial_overrides: Vec<Vec<(String, f64)>>,    // for GpuSweepResult construction
    trial_raw_values: Vec<Vec<f64>>,             // for tell()
}

/// TPE thread → GPU thread: sampled params for batch N+1
struct TpeBatchRequest {
    batch_idx: usize,
    trial_overrides: Vec<Vec<(String, f64)>>,    // for GPU eval + result construction
    trial_raw_values: Vec<Vec<f64>>,             // echoed back for tell()
}
```

### Sequence
```
1. GPU thread: init device, upload candles, alloc arenas
2. GPU thread: send init signal to TPE thread
3. TPE thread: ask() batch 0, send TpeBatchRequest → GPU thread
4. GPU thread: receive batch 0, launch GPU kernels
5. TPE thread: (idle — nothing to tell yet for first batch)
6. GPU thread: GPU done → send GpuBatchResult → TPE thread
7. TPE thread: receive results → tell() batch 0 → ask() batch 1 → send → GPU thread
8. GPU thread: receive batch 1 → launch GPU kernels (overlapped with step 7's ask)
9. ... repeat until all trials done
10. GPU thread: send Done signal → TPE thread exits
11. GPU thread: collect all GpuSweepResult, sort, return
```

## File Changes

### 1. `backtester/crates/bt-gpu/Cargo.toml`
- Add `crossbeam-channel = "0.5"`

### 2. `backtester/crates/bt-gpu/src/tpe_sweep.rs`
Main changes:

**a. New message types** (top of file)
```rust
struct GpuBatchResult { ... }
struct TpeBatchRequest { ... }
enum TpeToGpu {
    Batch(TpeBatchRequest),
    Done,  // TPE thread finished all batches
}
enum GpuToTpe {
    Results(GpuBatchResult),
    Shutdown,  // no more batches needed
}
```

**b. Extract TPE logic into `tpe_worker()` function**
Moves out of `run_tpe_sweep()`:
- `axis_opts` creation + ownership
- `ask()` sampling logic (current lines ~280-315)
- `tell()` + observation cache + pruning logic (current lines ~380-480)
- Loops receiving `GpuToTpe::Results`, calls tell+ask, sends `TpeToGpu::Batch`

**c. Refactor `run_tpe_sweep()` as GPU orchestrator**
- Creates channels: `(tpe_tx, tpe_rx)` and `(gpu_tx, gpu_rx)`
- Spawns TPE thread via `std::thread::spawn`
- Main loop: receive `TpeBatchRequest` → evaluate on GPU → send `GpuBatchResult`
- Collects `GpuSweepResult` vec (moved from TPE side to GPU side)
- Joins TPE thread on completion

**d. GpuSweepResult construction moves to GPU thread**
Currently built inside the tell loop. Move to GPU thread after eval:
- GPU thread has `trial_overrides` (from TpeBatchRequest) + `gpu_results`
- Can build `GpuSweepResult` without needing TPE state
- Eliminates need to send `GpuSweepResult` back through channels

### 3. `backtester/crates/bt-gpu/src/gpu_host.rs`
- No changes needed. `GpuDeviceState.dev` is `Arc<CudaDevice>`, stays on GPU thread.

### 4. Tests
New tests in existing test files or new `tests/test_tpe_pipeline.rs`:

| # | Test | What it verifies |
|---|------|-----------------|
| 1 | `test_pipeline_produces_same_results_as_serial` | Deterministic seed → identical results (regression) |
| 2 | `test_pipeline_timing_overlap` | ask_ms of batch N+1 overlaps with gpu_ms of batch N |
| 3 | `test_pipeline_single_batch` | Edge case: total_trials ≤ batch_size (only 1 batch, no pipeline) |
| 4 | `test_pipeline_exact_multiple` | trials = exact multiple of batch_size |
| 5 | `test_pipeline_remainder_batch` | Last batch is smaller than batch_size |
| 6 | `test_pipeline_pruning_still_works` | Observation pruning fires correctly across thread boundary |

## Determinism Guarantee

**Critical:** The pipelined version MUST produce identical results to serial for the same seed.

Why it works:
- TPE thread uses the same RNG sequence (seeded identically)
- `ask()` called same number of times in same order
- `tell()` called with same (raw_values, objective) pairs in same order
- Only difference: timing of when ask/tell happen relative to GPU — but TPE state transitions are identical

The key invariant: **TPE thread always tell()s batch N before ask()ing batch N+1.** This is naturally enforced by the channel protocol — TPE blocks on `gpu_rx.recv()` before proceeding to next ask.

## Thread Safety

| Resource | Thread | Send/Sync? |
|----------|--------|-----------|
| `GpuDeviceState` | GPU only | Arc<CudaDevice> is Send+Sync but we don't share |
| `CudaSlice` arenas | GPU only | Not Send (GPU memory) — correct, stays on GPU thread |
| `axis_opts` (TpeOptimizer) | TPE only | Moved to TPE thread at spawn |
| `observation_cache` | TPE only | Vec, moved to TPE thread |
| `all_results` (GpuSweepResult) | GPU only | Built on GPU thread |
| `trial_overrides/raw_values` | Created on TPE, sent to GPU | Vec<Vec<...>> is Send |

No shared mutable state. No locks needed. Pure message-passing.

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Non-determinism vs serial | Low | Same RNG seed + same call order. Test #1 verifies. |
| Channel deadlock | Low | Linear pipeline (no cycles). TPE sends then waits. GPU sends then waits. |
| Panic in TPE thread | Low | `thread::spawn` + `JoinHandle::join()` propagates panics to GPU thread. |
| First batch has no overlap | Expected | First batch is "priming" — TPE has nothing to tell. Pipeline benefit starts from batch 2. For 1M trials / 4096 batch = 244 batches, losing 1 is negligible. |
| Memory: two batches of overrides in flight | Low | 2 × 4096 × 142 × ~64 bytes ≈ 75 MB. Trivial. |

## Metrics

After implementation, the log line changes from:
```
[TPE] 4096/20000 done | ask=5200ms gpu=8800ms tell=113ms
```
to:
```
[TPE] 4096/20000 done | ask=5200ms gpu=8800ms tell=113ms overlap=5200ms idle=0ms
```

Where `overlap` = time ask was running while GPU was busy, `idle` = time GPU waited for ask.

## Estimated Effort

| Component | Lines | Complexity |
|-----------|-------|-----------|
| Message types | ~30 | Low |
| `tpe_worker()` extraction | ~120 (moved, not new) | Medium |
| `run_tpe_sweep()` refactor | ~80 new orchestration | Medium |
| GpuSweepResult construction move | ~30 (moved) | Low |
| Logging/metrics | ~15 | Low |
| Tests | ~150 | Medium |
| **Total** | **~300 new + ~150 moved** | **Medium** |

Net new code: ~300 lines. Most is restructuring existing code into two functions.

## Order of Operations

1. Add `crossbeam-channel` dependency
2. Define message types
3. Extract `tpe_worker()` — compile check (no behavior change yet)
4. Refactor `run_tpe_sweep()` to spawn thread + use channels
5. Move `GpuSweepResult` construction to GPU thread
6. Add overlap timing metrics to log line
7. Write tests (determinism test is most important)
8. Run 20K smoke test — compare results with serial baseline
9. Benchmark: measure actual overlap and GPU utilization improvement
