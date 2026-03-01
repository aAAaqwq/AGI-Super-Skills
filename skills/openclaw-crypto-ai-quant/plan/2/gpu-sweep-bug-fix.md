> **Status**: Fixed. All GPU parity bugs described here have been resolved.

Yep — there are a few very concrete “this will definitely break parity” issues in the GPU path, and they line up perfectly with the symptoms you described:

1. “0 trades with sub-bars” wasn’t really a kernel bug — it was a silent config fallback (wrong default path → YAML not found → defaults used → `entry_min_confidence=High` blocks basically everything in a 13‑day window).

2. The GPU sub‑bar plumbing was **not matching the CPU engine’s time semantics**. The CPU uses a “main timeframe snapshot” and then advances through sub‑bars on the *forward* interval `(ts, next_ts]`. The GPU prep code was effectively grouping sub‑bars into the wrong main bar bucket and also iterating them by slot index without aligning timestamps across symbols (so the “tick timeline” differed from CPU).

3. GPU kernel divergences:

* confirmed: `hybrid.volume = sc.volume;` (3 places) makes hybrid snapshots behave differently from CPU’s `make_exit_snap()` (CPU keeps main-bar volume)
* confirmed: TP logic didn’t implement `tp_partial_atr_mult` (your YAML sets it to `1.0`, so GPU was fundamentally not running the same strategy)
* confirmed: in the sub‑bar exit loop the GPU was **breaking** after partial TP, which prevents remaining sub‑bars in that hour from being evaluated (CPU continues scanning after partial)

Below are the exact fixes I’d make. They’re small, but they fix the root causes.

---

## Fix 1 — stop silent “defaults” config loading

### A) bt-cli: correct default path

In `backtester/crates/bt-cli/src/main.rs`, change the default for `--config` from `"strategy_overrides.yaml"` to `"config/strategy_overrides.yaml"` (Replay/Sweep/Dump args).

Example:

```rust
// Unified config shared by backtester + live engine
#[arg(long, default_value = "config/strategy_overrides.yaml")]
config: String,
```

Why this matters: your repo’s unified file is `config/strategy_overrides.yaml`. The old default points at a file that often doesn’t exist relative to CWD, and `load_config()` returns defaults silently → “GPU sweep is broken” looking behaviour.

### B) bt-core: warn loudly if config missing

In `backtester/crates/bt-core/src/config.rs` inside `load_config(...)`, add a warning when the YAML path doesn’t exist.

Minimal safe change:

```rust
if !path.exists() {
    eprintln!(
        "[config] WARN: YAML config not found at '{}'; using code defaults.",
        yaml_path
    );
    return StrategyConfig::default();
}
```

This prevents the “I forgot `--config` / wrong path” case from masquerading as a GPU kernel issue.

---

## Fix 2 — make GPU sub‑bar prep match CPU semantics (this is the big one)

### What CPU does (authoritative)

CPU engine’s sub‑bar logic (your `engine.rs`) uses the main snapshot at `ts` and scans sub‑bars in the *forward* window `(ts, next_ts]` (see the `binary_search_by_key(&(ts + 1), ...)` logic and the `sub_ts > next_ts` break).

That implies: each sub‑bar timestamp `t` must be associated with the previous main timestamp bucket `i` such that:

`ts[i] < t <= ts[i+1]`

### What the GPU was doing

`prepare_sub_bar_candles()` was mapping sub‑bars to the **current** main bar (`first ts >= t`) and then the kernel used snapshot at that same bar. That’s a one‑bar shift vs the CPU semantics.

Also, CPU advances by the **union of timestamps across all symbols** each hour. The GPU kernel iterates by `sub_i` slot, but the prep code wasn’t aligning slots to a per‑bar union timeline — so “slot 7” could mean different timestamps for different symbols → entry ranking order changes, exits checked at different times, etc.

### Concrete fix

In `backtester/crates/bt-gpu/src/raw_candles.rs`, update `prepare_sub_bar_candles()` to:

1. Assign each sub‑bar to the *previous* main bar index (`j-1`), not `j`.
2. For each main bar, compute the **union** of sub‑bar timestamps across symbols, and pad each symbol’s sub‑bar series to that shared timeline (missing bars become `close=0`).

Mechanically:

* find `j = lower_bound(main_ts >= t)`
* if `j==0`: ignore (CPU never trades before first main bar snapshot exists)
* if `j>=num_bars`: assign to last bar (CPU’s last bar scans until `i64::MAX`)
* else assign to `j-1`

Then build `union_ts` per bar and lay out `GpuRawCandle[(bar * max_sub + sub_idx) * ns + sym]` so that **sub_idx corresponds to the same timestamp across all symbols**.

If you want, I can paste the full function body I’m using (it’s ~150 lines), but the key is those two invariants:

* sub‑bars map to `(ts, next_ts]` buckets
* sub‑bar slots are aligned to union timestamps per bar

This change alone usually collapses the “GPU vs CPU wildly different” issue because you stop feeding the kernel a different timeline than the CPU engine.

---

## Fix 3 — kernel parity fixes (volume + partial TP behaviour)

### A) Remove the 3 volume overrides

In `backtester/crates/bt-gpu/kernels/sweep_engine.cu`, delete all occurrences of:

```cpp
hybrid.volume = sc.volume;
```

(you already identified the three spots)

CPU `make_exit_snap()` does **not** override volume, so GPU must keep `ind_snap.volume`.

### B) Implement `tp_partial_atr_mult` (your YAML sets it to 1.0)

Right now the GPU TP check is using the full TP multiplier for partial, so it will never behave like your CPU sweep with `tp_partial_atr_mult: 1.0`.

Update `check_tp()` so that when partial TP is enabled and `tp1_taken == 0`, it uses `cfg->tp_partial_atr_mult` (if > 0) for the TP trigger level.

The essential logic:

* compute `tp_mult_eff`:

  * if partial enabled and not taken:

    * if `tp_partial_atr_mult > 0` use that
    * else use the passed `tp_mult` (old behaviour)
  * otherwise use `tp_mult`

Then compute `tp_price` from `tp_mult_eff`.

### C) Don’t “break” the sub‑bar scan after partial TP

In the SUB‑BAR EXIT inner loop, you must not `break;` after partial. CPU continues scanning later sub‑bars in that same main-bar window. Use `continue;` (or just fall through to the next `sub_i`).

Change:

```cpp
if (tp_result == 1u) {
    apply_partial_close(...);
    break;
}
```

to:

```cpp
if (tp_result == 1u) {
    apply_partial_close(...);
    continue; // keep scanning sub-bars like CPU
}
```

This is a real behavioural divergence.

---

## Quick sanity check after patching

Once you apply the above, run these two and compare:

CPU:

```bash
cargo run --release --manifest-path backtester/Cargo.toml -- \
  sweep --sweep-spec backtester/sweeps/smoke.yaml \
  --config config/strategy_overrides.yaml \
  --interval 1h --entry-interval 3m --exit-interval 3m
```

GPU:

```bash
LD_LIBRARY_PATH=/usr/lib/wsl/lib \
cargo run --release --manifest-path backtester/Cargo.toml --features gpu -- \
  sweep --gpu --sweep-spec backtester/sweeps/smoke.yaml \
  --config config/strategy_overrides.yaml \
  --interval 1h --entry-interval 3m --exit-interval 3m
```

What you should see:

* no more “0 trades across everything”
* trade counts/pnl should get dramatically closer
* any remaining differences will be in small edge semantics (fill model, ordering ties, etc.), not “completely different universe”

---

## One more important limitation to call out

Right now in `cmd_sweep()` the GPU path uses **one** sub‑candle DB for both entry and exit (it picks exit if present, else entry). That’s fine when `--entry-interval` and `--exit-interval` are the same (your 3m/3m case), but it will not match CPU if you ever run entry=3m and exit=1m, etc. Fixing that properly requires two buffers and small kernel changes (entry_sub vs exit_sub).

---

If you want, paste (or upload) your current `prepare_sub_bar_candles()` from the real repo and I’ll give you an exact drop-in replacement matching CPU’s `(ts, next_ts]` semantics and union-tick alignment. That’s the part most likely to still have subtle off-by-one issues if anything is still “weird” after the kernel fixes.
