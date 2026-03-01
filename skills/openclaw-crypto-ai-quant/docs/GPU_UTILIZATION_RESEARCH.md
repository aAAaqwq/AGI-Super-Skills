# GPU Utilization Research: Eliminating TPE Ask Idle Time

> **Status**: Phase 1 quick wins implemented. Phase 2 (double-buffer pipeline) planned — see [PLAN_DOUBLE_BUFFER_TPE.md](PLAN_DOUBLE_BUFFER_TPE.md).

## Current Architecture

```
ask (CPU) ──→ gpu (CUDA) ──→ tell (CPU)  ──→ ask (CPU) ──→ gpu (CUDA) ──→ ...
[~5s idle]    [~9s work]     [~0.1s]        [~5s idle]    [~9s work]
```

**Measured timing (20K trials, 142 axes, RTX 3090, batch=4096):**

| Phase | Time | What it does |
|-------|------|-------------|
| `ask`  | ~5,200ms | TPE samples 4096 trials × 142 axes (CPU, Rayon parallel) |
| `gpu`  | ~8,800ms | CUDA indicator + trade kernels evaluate all trials |
| `tell` | ~113ms   | Feed results back to TPE optimizers |

**GPU utilization: ~62%** (idle during entire `ask` + `tell` phases)

## Root Cause Analysis

### Why `ask` is slow (5s per batch)
The `tpe` Rust crate's `ask()` method is O(N) per call where N = number of observations:
1. Sorts all trials by value (once, then cached as `is_sorted`)
2. Splits into superior/inferior sets at γ quantile
3. **Builds two KDE (Kernel Density Estimators)** from observations — O(N) per axis
4. **Samples 24 candidates from superior KDE, evaluates EI** — O(24 × N) per axis
5. We call this 4,096 × 142 = ~581K times per batch (Rayon parallelizes across axes)

With 500 pruned observations, each `ask()` is fast individually, but 4096 calls × 142 axes = ~581K ask() calls per batch. Even at ~10µs each = ~5.8s total.

### Why `tell` is fast (113ms)
`tell()` is just a Vec::push — O(1) per call. 4096 × 142 = ~581K tells ≈ 113ms.

## Optimization Strategies (Ranked by Impact)

### Strategy 1: Double-Buffer Pipeline (RECOMMENDED — ~90% utilization)

**Concept:** While GPU evaluates batch N, CPU simultaneously samples batch N+1.

```
CPU:  [ask_0]──[ask_1 + tell_0]──[ask_2 + tell_1]──[ask_3 + tell_2]──...
GPU:           [gpu_0]───────────[gpu_1]───────────[gpu_2]───────────...
```

**Implementation:**
1. Use `std::thread::spawn` for a dedicated TPE thread
2. Main thread owns GPU, TPE thread owns optimizers
3. Communicate via `crossbeam::channel` (trial_overrides → GPU, results → TPE)
4. GPU launches are already async via `cudarc::LaunchAsync` — just don't sync until needed

**Expected gain:**
- ask (5.2s) fully overlapped with gpu (8.8s) → batch time = max(ask, gpu) = 8.8s
- Current batch time = ask + gpu + tell = 14.1s
- **Speedup: 14.1s → 8.9s per batch (37% faster) → GPU util ~95%**

**Complexity:** Medium. Core TPE loop refactored into two threads. Arena buffers stay on GPU thread.

**Risk:** Low — TPE quality unchanged (same observations, same sampling). GPU results from batch N inform batch N+1 sampling with exactly one-batch delay, which is fine for batched BO.

### Strategy 2: Constant Liar with Speculative Prefetch (~95% utilization)

**Concept:** Instead of waiting for GPU results to update TPE, inject "fake" results (lies) for pending trials so TPE can sample next batch immediately.

**Theory (from literature):**
- **Constant Liar (CL):** After selecting x*, assign fake y = mean(Y) or min(Y) or max(Y) before real evaluation completes
- **Kriging Believer (KB):** Use surrogate model prediction as fake y
- For TPE: CL is simpler because TPE doesn't have a GP surrogate to predict from

**Implementation:**
1. After `ask()` produces batch N params, immediately `tell()` each with `L = mean(observed_pnl)`
2. Start `ask()` for batch N+1 while GPU evaluates batch N
3. When GPU results arrive, "untell" the lies and `tell()` with real values
4. The `tpe` crate doesn't support "untell" — would need to rebuild optimizer from observations cache (we already do this during pruning)

**Expected gain:** Same as Strategy 1 in steady state, but with theoretically better exploration diversity.

**Complexity:** High — requires either modifying `tpe` crate or maintaining shadow observation lists. The rebuild-from-scratch approach (used in our pruning) could work but is O(N²) per batch.

**Risk:** Medium — CL can reduce TPE quality slightly. NNI's research shows CL with `L=mean` works well for moderate parallelism (q ≤ 16 batches ahead), but at q=1 (our case) it's equivalent to Strategy 1.

**Verdict:** Overkill for single-batch-ahead overlap. Strategy 1 achieves the same throughput with no TPE quality loss.

### Strategy 3: Increase Batch Size (Easiest — ~75% utilization)

**Concept:** Larger batch = GPU takes longer per round = `ask` cost relatively smaller.

Current: batch=4096, ask=5.2s, gpu=8.8s → ask is 37% of gpu time
Larger:  batch=8192, ask=~10s, gpu=~17s → ask is 59% of gpu time (worse ratio!)

**Problem:** TPE ask time scales linearly with batch size. GPU time also scales ~linearly. The ask/gpu ratio stays approximately constant because:
- ask time ∝ batch_size (more calls)
- gpu time ∝ batch_size (more trials to evaluate)

**Expected gain:** Marginal. Slightly less overhead from `tell` phase and loop/sync overhead.

Actually, there IS a sublinear benefit: **indicator dedup**. With larger batches, more trials share identical integer indicator configs. At 4096 we see 0% dedup. At 8192+, integer axes start colliding more:
- 142 axes, ~26 integer axes with small ranges → dedup should kick in at 8K-16K batch
- If dedup goes from 0% to 30%, GPU time drops by 30% while ask time stays the same

**Verdict:** Worth trying as a quick experiment. Set `--tpe-batch 8192` and compare. No code changes needed.

### Strategy 4: CUDA Streams for Kernel Overlap (~5% extra)

**Concept:** Use multiple CUDA streams to overlap indicator and trade kernels.

Currently all kernels run on the default stream (serialized). With arena groups:
```
Stream 1: [indicator_group_0] → [trade_group_0]
Stream 2:                       [indicator_group_1] → [trade_group_1]
```

**Problem:** Our arena_cap=519 slots ≫ batch_size/unique_configs, so we typically have 1 group (no multi-group needed). The indicator and trade kernels are different phases that need sequential execution per group.

**Expected gain:** Minimal (~5%) because:
- Single arena group covers entire batch — no inter-group overlap opportunity
- The real bottleneck is ask(), not GPU kernel scheduling
- htod_sync_copy for configs is tiny (~32KB per batch)

**Complexity:** Low (cudarc 0.12 supports `fork_default_stream()`) but minimal payoff.

**Verdict:** Not worth it unless we solve the ask bottleneck first.

### Strategy 5: Reduce TPE Ask Complexity (~30% ask speedup)

**Concept:** Make each `ask()` call cheaper.

**Options:**
a. **Reduce candidates**: Default is 24 candidates per ask. Set to 12 → ~50% ask speedup at minor quality cost
b. **More aggressive pruning**: Current MAX=1000, PRUNED=500. Try MAX=500, PRUNED=250 → fewer observations for KDE building → ~50% faster ask
c. **Skip TPE for early batches**: First 25% of trials use pure random sampling (no KDE) → instant ask → saves ~25% of total ask time
d. **Axis-level parallelism with batch-ask**: Instead of calling ask() 4096 times per axis, vectorize the sampling. The `tpe` crate doesn't support batch_ask, but we could:
   - Build the KDE once per axis per batch
   - Sample 4096 candidates from it directly using the raw distribution
   - This would be O(1) KDE build + O(4096 × 24) EI evaluations instead of O(4096) KDE builds

**Expected gain:** Options (a)+(b) combined: ask drops from ~5.2s to ~2s. With double-buffer: fully hidden.

**Complexity:** (a) and (b) are one-line changes. (c) is ~20 lines. (d) requires forking/wrapping the tpe crate.

**Verdict:** Quick wins (a)+(b)+(c) are good complements to Strategy 1.

### Strategy 6: Replace TPE with CMA-ES (ALTERNATIVE APPROACH)

**Concept:** CMA-ES (Covariance Matrix Adaptation Evolution Strategy) has natural batch support — it generates an entire population in one shot.

- Optuna supports CMA-ES with `popsize` = batch_size
- CMA-ES ask time is O(d³) for d dimensions, independent of number of observations
- For d=142: O(142³) ≈ 2.9M operations ≈ ~1ms for entire batch

**Expected gain:** ask time drops from ~5.2s to ~1ms. GPU utilization → ~99.99%.

**Problem:**
- CMA-ES works best for continuous spaces. 26 integer axes and 29 boolean axes need special handling
- Would need a Rust CMA-ES implementation (or FFI to Python)
- TPE handles mixed discrete/continuous spaces natively
- CMA-ES may converge differently (not necessarily better or worse)

**Complexity:** Very high (new optimizer, testing, tuning).

**Verdict:** Long-term consideration. Not worth it if double-buffer solves the problem.

## Recommendation

**Phase 1 (Quick wins, no refactoring):**
1. Reduce TPE candidates: 24 → 12 (one-line `TpeOptimizerBuilder`)
2. More aggressive pruning: MAX=500, PRUNED=250 
3. Random sampling for first 25% of trials
4. Try `--tpe-batch 8192` to test dedup benefits

Expected: ask drops to ~2-3s, GPU util ~75-80%

**Phase 2 (Double-buffer pipeline):**
1. Spawn dedicated TPE thread with crossbeam channels
2. GPU thread evaluates batch N while TPE thread samples batch N+1
3. Arena buffers stay on GPU thread (no CUDA context sharing needed)

Expected: GPU util ~90-95%, total sweep time drops ~35-40%

**Phase 3 (If needed):**
1. Implement vectorized batch_ask in a forked `tpe` crate
2. Or evaluate CMA-ES for continuous-only axes with TPE for discrete

## Impact Projection (1M trials, 142 axes)

| Approach | Sweep Time | GPU Util |
|----------|-----------|----------|
| Current | ~62 min | ~62% |
| Phase 1 only | ~50 min | ~75% |
| Phase 2 (double-buffer) | ~40 min | ~92% |
| Phase 1 + 2 combined | ~38 min | ~95% |
| Theoretical max (CMA-ES) | ~36 min | ~99% |
