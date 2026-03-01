> **Status**: Fixed. All addendum items have been resolved.

You’re not far off with your diagnosis — in the code you uploaded there are a few *concrete*, deterministic mismatches that will make GPU sweeps diverge badly from the CPU backtester (and also make “1h main + 3m entry/exit” behave wrong).

Below are the fixes I’d apply. I’m including unified diffs you can paste straight into your repo (paths match what you referenced in your report).

---

1. bt-cli: make the default config path actually point at your file (and warn when it doesn’t)

Right now `SweepArgs` defaults to `strategy_overrides.yaml`, but your file lives at `config/strategy_overrides.yaml`. Because `load_config()` silently falls back to defaults when the file doesn’t exist, GPU sweeps end up using `entry_min_confidence=High` and can easily produce 0 trades on short sub-bar windows.

Patch `backtester/crates/bt-cli/src/main.rs`:

```diff
--- a/backtester/crates/bt-cli/src/main.rs
+++ b/backtester/crates/bt-cli/src/main.rs
@@ -56,7 +56,7 @@
 struct ReplayArgs {
     #[arg(long)]
     input: String,
-    #[arg(long, default_value = "strategy_overrides.yaml")]
+    #[arg(long, default_value = "config/strategy_overrides.yaml")]
     config: String,
     #[arg(long)]
     interval: String,
@@ -156,7 +156,7 @@
 struct SweepArgs {
     #[arg(long)]
     sweep_spec: String,
-    #[arg(long, default_value = "strategy_overrides.yaml")]
+    #[arg(long, default_value = "config/strategy_overrides.yaml")]
     config: String,
     #[arg(long)]
     interval: String,
@@ -257,7 +257,7 @@
 struct DumpArgs {
     #[arg(long)]
     symbol: String,
-    #[arg(long, default_value = "strategy_overrides.yaml")]
+    #[arg(long, default_value = "config/strategy_overrides.yaml")]
     config: String,
     #[arg(long)]
     interval: String,
@@ -333,6 +333,10 @@ fn cmd_replay(args: ReplayArgs) -> anyhow::Result<()> {
     let candles = bt_core::candle_db::get_candles_df(&args.input, &args.symbol, &args.interval)?;

+    if !std::path::Path::new(&args.config).exists() {
+        eprintln!("[warn] Config file '{}' not found; using built-in defaults (entry_min_confidence defaults to HIGH). Pass --config config/strategy_overrides.yaml.", args.config);
+    }
     let cfg = bt_core::config::load_config(
         &args.config,
         Some(&args.symbol),
@@ -544,6 +548,10 @@ fn cmd_sweep(args: SweepArgs) -> anyhow::Result<()> {
     // Base config for sweep
+    if !std::path::Path::new(&args.config).exists() {
+        eprintln!("[warn] Config file '{}' not found; using built-in defaults (entry_min_confidence defaults to HIGH). Pass --config config/strategy_overrides.yaml.", args.config);
+    }
     let base_cfg = bt_core::config::load_config(&args.config, None, args.live);

     // Load sweep spec
@@ -902,6 +910,10 @@ fn cmd_dump_indicators(args: DumpArgs) -> anyhow::Result<()> {
     let candles = bt_core::candle_db::get_candles_df(&args.input, &args.symbol, &args.interval)?;

+    if !std::path::Path::new(&args.config).exists() {
+        eprintln!("[warn] Config file '{}' not found; using built-in defaults (entry_min_confidence defaults to HIGH). Pass --config config/strategy_overrides.yaml.", args.config);
+    }
     let cfg = bt_core::config::load_config(&args.config, Some(&args.symbol), false);
     let ind_cfg = cfg.indicators.clone();
```

This alone prevents the “silent defaults” footgun you hit.

---

2. bt-gpu: fix sub-bar → main-bar assignment AND align per-bar sub-bar timestamps to the CPU’s union-tick semantics

Your current `prepare_sub_bar_candles()` maps each sub candle to “the smallest main_ts >= sub_ts”. That corresponds to `(ts[i-1], ts[i]]`.

But the CPU engine’s sub-bar scan is `(ts[i], ts[i+1]]` (see `engine.rs` sub-bar loops: start at `ts+1`, stop at `next_ts`). That’s a one-bar shift.

Also, CPU entry ranking is based on the union of timestamps across symbols per bar; your GPU kernel iterates `sub_i` as an ordinal index and assumes alignment. If some symbols have missing sub-bars, ranking diverges.

Patch `backtester/crates/bt-gpu/src/raw_candles.rs`:

```diff
--- a/backtester/crates/bt-gpu/src/raw_candles.rs
+++ b/backtester/crates/bt-gpu/src/raw_candles.rs
@@ -122,11 +122,18 @@
     }
 }

-/// Prepare sub-bar candles aligned to main bar ranges for GPU upload.
+/// Prepare sub-bar candles aligned to the CPU engine's sub-bar semantics.
 ///
-/// For each main bar `i`, sub-bars fall in the half-open range `(ts[i-1], ts[i]]`
-/// (first bar uses `(-inf, ts[0]]`). Sub-bars are sorted chronologically and
-/// packed into a rectangular layout padded with zeroed candles.
+/// CPU (`bt-core/src/engine.rs`) evaluates sub-bars *after* each main indicator bar close:
+/// for a main timestamp `ts[i]`, it scans sub-bars in `(ts[i], ts[i+1]]`
+/// (and for the last bar, `(ts[last], +∞)`).
+///
+/// Therefore a sub-bar at timestamp `t` is assigned to the previous main bar:
+/// `main_idx = lower_bound(main_timestamps, t) - 1`, skipping any `t <= ts[0]`.
+///
+/// The CPU entry path also builds a union of sub-bar timestamps across symbols for each
+/// main bar. The GPU kernel iterates by `sub_idx`, so we pre-align each bar to the per-bar
+/// union timeline and pad missing (symbol, sub_idx) slots with zeroed candles (close=0).
 ///
 /// Layout: `candles[(bar_idx * max_sub + sub_idx) * num_symbols + sym_idx]`
 ///
@@ -150,39 +157,58 @@
         };
     }

-    // For each (bar, symbol), collect sorted sub-bar timestamps
-    // Main bar i covers range (main_ts[i-1], main_ts[i]] in ms
-    // First bar covers (-inf, main_ts[0]]
-
-    // Step 1: For each symbol, sort sub-bars by timestamp and assign to main bars via binary search
-    // sub_bars_by_bar_sym[bar_idx][sym_idx] = Vec<&Bar>
+    // ── Step 1: Assign each sub-bar to its "indicator bar" (CPU semantics) ─────────────
+    // sub_bars_by_bar_sym[bar_idx][sym_idx] = Vec<&OhlcvBar>
     let mut sub_bars_by_bar_sym: Vec<Vec<Vec<&bt_core::candle::OhlcvBar>>> =
         vec![vec![Vec::new(); num_symbols]; num_bars];

+    // union_ts_by_bar[bar_idx] = Vec<sub_ts> (later sort+dedup)
+    let mut union_ts_by_bar: Vec<Vec<i64>> = vec![Vec::new(); num_bars];
+
+    let mut total_mapped: usize = 0;
+    let mut skipped_pre_start: usize = 0;
+
     for (sym_idx, sym) in symbols.iter().enumerate() {
         if let Some(bars) = sub_candles.get(sym) {
             for bar in bars {
-                // Find which main bar this sub-bar belongs to.
-                // Sub-bar at time `t` belongs to the main bar whose timestamp is the
-                // smallest main_ts >= t. (main_ts[i] is the close time of bar i)
-                let main_idx = match main_timestamps.binary_search(&bar.t) {
-                    Ok(i) => i,                    // exact match
-                    Err(i) if i < num_bars => i,   // insert position = next main bar
-                    Err(_) => continue,            // beyond last main bar, skip
+                let t = bar.t;
+
+                // lower_bound(main_timestamps, t): first index with main_ts >= t
+                let ip = match main_timestamps.binary_search(&t) {
+                    Ok(i) => i,
+                    Err(i) => i,
                 };
-                sub_bars_by_bar_sym[main_idx][sym_idx].push(bar);
+
+                // CPU skips sub-bars at or before the first main timestamp because it
+                // starts scanning from (ts[0] + 1) onward.
+                if ip == 0 {
+                    skipped_pre_start += 1;
+                    continue;
+                }
+
+                // Assign to the previous main bar:
+                //   - if t <= ts[last] then bar_idx = ip - 1
+                //   - if t  > ts[last] then ip == num_bars, map to last bar
+                let bar_idx = if ip >= num_bars { num_bars - 1 } else { ip - 1 };
+
+                sub_bars_by_bar_sym[bar_idx][sym_idx].push(bar);
+                union_ts_by_bar[bar_idx].push(t);
+                total_mapped += 1;
             }
         }
     }

-    // Step 2: Find max sub-bars per main bar (across all symbols)
-    let mut max_sub: u32 = 0;
+    // ── Step 2: Build per-bar union timeline, sort per-symbol lists, compute max_sub ──
+    let mut max_sub: usize = 0;
+
     for bar_idx in 0..num_bars {
+        let union = &mut union_ts_by_bar[bar_idx];
+        union.sort_unstable();
+        union.dedup();
+        max_sub = max_sub.max(union.len());
+
         for sym_idx in 0..num_symbols {
-            let count = sub_bars_by_bar_sym[bar_idx][sym_idx].len() as u32;
-            if count > max_sub {
-                max_sub = count;
-            }
+            sub_bars_by_bar_sym[bar_idx][sym_idx].sort_by_key(|b| b.t);
         }
     }

@@ -196,48 +222,65 @@
         };
     }

-    // Step 3: Allocate rectangular buffer and fill
-    let total_slots = num_bars * (max_sub as usize) * num_symbols;
+    // ── Step 3: Allocate rectangular buffer and fill aligned by union timestamp ───────
+    let max_sub_u32 = max_sub as u32;
+    let total_slots = num_bars * max_sub * num_symbols;
+
     let mut flat = vec![GpuRawCandle::zeroed(); total_slots];
     let mut sub_counts = vec![0u32; num_bars * num_symbols];

+    let mut filled_nonzero: usize = 0;
+
     for bar_idx in 0..num_bars {
+        let union = &union_ts_by_bar[bar_idx];
+        let union_len_u32 = union.len() as u32;
+
         for sym_idx in 0..num_symbols {
-            let subs = &mut sub_bars_by_bar_sym[bar_idx][sym_idx];
-            // Sort chronologically (should already be sorted, but ensure)
-            subs.sort_by_key(|b| b.t);
-
-            let count = subs.len();
-            sub_counts[bar_idx * num_symbols + sym_idx] = count as u32;
-
-            for (sub_idx, bar) in subs.iter().enumerate() {
-                let flat_idx = (bar_idx * (max_sub as usize) + sub_idx) * num_symbols + sym_idx;
-                flat[flat_idx] = GpuRawCandle {
-                    open: bar.o as f32,
-                    high: bar.h as f32,
-                    low: bar.l as f32,
-                    close: bar.c as f32,
-                    volume: bar.v as f32,
-                    t_sec: (bar.t / 1000) as u32,
-                    _pad: [0; 2],
-                };
+            sub_counts[bar_idx * num_symbols + sym_idx] = union_len_u32;
+
+            let subs = &sub_bars_by_bar_sym[bar_idx][sym_idx];
+            let mut j = 0usize;
+
+            for (sub_idx, &ts) in union.iter().enumerate() {
+                // Two-pointer merge: union timestamps vs this symbol's sub-bars.
+                if j < subs.len() && subs[j].t == ts {
+                    let bar = subs[j];
+                    j += 1;
+
+                    let flat_idx = (bar_idx * max_sub + sub_idx) * num_symbols + sym_idx;
+                    flat[flat_idx] = GpuRawCandle {
+                        open: bar.o as f32,
+                        high: bar.h as f32,
+                        low: bar.l as f32,
+                        close: bar.c as f32,
+                        volume: bar.v as f32,
+                        t_sec: (bar.t / 1000) as u32,
+                        _pad: [0; 2],
+                    };
+                    filled_nonzero += 1;
+                }
+                // else: leave zeroed (close=0) — kernel skips
             }
         }
     }

+    let total_union_ticks: usize = union_ts_by_bar.iter().map(|v| v.len()).sum();
+
     eprintln!(
-        "[sub-bar] Prepared {} bars × {} max_sub × {} symbols = {} slots ({:.1} MB)",
-        num_bars,
-        max_sub,
-        num_symbols,
+        "[sub-bar] Prepared sub-bars: mapped={}, skipped_pre_start={}, union_ticks_total={}, max_sub_per_bar={} | flat slots={} ({:.1} MB) | filled_nonzero={}",
+        total_mapped,
+        skipped_pre_start,
+        total_union_ticks,
+        max_sub_u32,
         total_slots,
         (total_slots * std::mem::size_of::<GpuRawCandle>()) as f64 / 1e6,
+        filled_nonzero,
     );

     SubBarResult {
         candles: flat,
         sub_counts,
-        max_sub_per_bar: max_sub,
+        max_sub_per_bar: max_sub_u32,
         num_bars,
         num_symbols,
     }
```

This fixes both:

* the one-bar shift (critical for “1h main + 3m entry/exit”), and
* the per-bar “union timeline” alignment to match CPU entry ranking.

---

3. sweep_engine.cu: fix volume override, partial-TP handling, and tp_partial_atr_mult

You already spotted the volume override. There are also two other meaningful divergences in the kernel:

* `check_tp()` ignores `tp_partial_atr_mult` (so partial TP happens at the *full* TP level instead of e.g. 1 ATR).
* In the sub-bar exit loop, partial TP does `break;` which stops scanning further sub-bars; CPU continues.

Patch `backtester/crates/bt-gpu/kernels/sweep_engine.cu`:

```diff
--- a/backtester/crates/bt-gpu/kernels/sweep_engine.cu
+++ b/backtester/crates/bt-gpu/kernels/sweep_engine.cu
@@ -531,41 +531,62 @@ __device__ bool check_trailing_exit(const GpuPosition& pos, const GpuSnapshot& snap) {

 // -- Take Profit --------------------------------------------------------------

 // Returns: 0 = hold, 1 = partial, 2 = full close
 __device__ unsigned int check_tp(const GpuPosition& pos, const GpuSnapshot& snap,
                                  const GpuComboConfig* cfg, float tp_mult) {
     float entry = pos.entry_price;
     float atr = (pos.entry_atr > 0.0f) ? pos.entry_atr : (entry * 0.005f);

-    float tp_price;
-    if (pos.active == POS_LONG) {
-        tp_price = entry + (atr * tp_mult);
-    } else {
-        tp_price = entry - (atr * tp_mult);
-    }
-
-    bool tp_hit = false;
-    if (pos.active == POS_LONG) {
-        tp_hit = snap.close >= tp_price;
-    } else {
-        tp_hit = snap.close <= tp_price;
-    }
-
-    if (!tp_hit) return 0u;
-
-    // Partial TP logic
-    if (cfg->enable_partial_tp != 0u) {
-        // If tp1 already taken, let trailing manage
-        if (pos.tp1_taken != 0u) return 0u;
-
-        float pct = cfg->tp_partial_pct;
-        if (pct > 0.0f && pct < 1.0f) {
-            float remaining = pos.size * (1.0f - pct) * snap.close;
-            if (remaining < cfg->tp_partial_min_notional_usd) {
-                return 0u;
-            }
-            return 1u; // partial
-        }
-    }
-
-    return 2u; // full close
+    // Full TP uses the (possibly dynamic) multiplier passed in.
+    float full_mult = tp_mult;
+
+    // Partial TP can use its own ATR multiplier. 0 => same as full.
+    float partial_mult = full_mult;
+    if (cfg->tp_partial_atr_mult > 0.0f) {
+        partial_mult = cfg->tp_partial_atr_mult;
+    }
+
+    float tp_price_full;
+    float tp_price_partial;
+    if (pos.active == POS_LONG) {
+        tp_price_full = entry + (atr * full_mult);
+        tp_price_partial = entry + (atr * partial_mult);
+    } else {
+        tp_price_full = entry - (atr * full_mult);
+        tp_price_partial = entry - (atr * partial_mult);
+    }
+
+    bool partial_hit = false;
+    bool full_hit = false;
+    if (pos.active == POS_LONG) {
+        partial_hit = snap.close >= tp_price_partial;
+        full_hit = snap.close >= tp_price_full;
+    } else {
+        partial_hit = snap.close <= tp_price_partial;
+        full_hit = snap.close <= tp_price_full;
+    }
+
+    if (cfg->enable_partial_tp != 0u) {
+        // TP1 already taken => trailing manages remainder (CPU behaviour).
+        if (pos.tp1_taken != 0u) {
+            return 0u;
+        }
+
+        // Try partial TP first if its level is hit.
+        if (partial_hit) {
+            float pct = fmaxf(fminf(cfg->tp_partial_pct, 1.0f), 0.0f);
+            if (pct > 0.0f && pct < 1.0f) {
+                float remaining = pos.size * (1.0f - pct) * snap.close;
+
+                // If partial would leave dust, skip the partial (keep position unchanged).
+                // If you want "dust => full close" semantics, change this to `return 2u;`.
+                if (remaining < cfg->tp_partial_min_notional_usd) {
+                    return 0u;
+                }
+
+                return 1u; // Partial
+            }
+            // Invalid pct => fall through to full TP
+        }
+    }
+
+    if (full_hit) { return 2u; }
+    return 0u;
 }
@@ -892,7 +913,6 @@ extern "C" __global__ void sweep_kernel(const GpuRawCandle* __restrict__ raw_candles,
                     // overlay price fields from sub candle
                     hybrid.open = sc.open;
                     hybrid.high = sc.high;
                     hybrid.low  = sc.low;
                     hybrid.close= sc.close;
-                    hybrid.volume = sc.volume;
                     hybrid.t_sec = sc.t_sec;

                     float p_atr = profit_atr(pos, hybrid.close);
@@ -949,7 +969,7 @@ extern "C" __global__ void sweep_kernel(const GpuRawCandle* __restrict__ raw_candles,
                     float tp_mult = get_tp_mult(hybrid, &cfg);
                     unsigned int tp_result = check_tp(pos, hybrid, &cfg, tp_mult);
                     if (tp_result == 1u) {
                         apply_partial_close(&state, sym, hybrid, cfg.tp_partial_pct, fee_rate);
-                        break;
+                        continue;
                     }
                     if (tp_result == 2u) {
                         apply_close(&state, sym, hybrid, false, fee_rate);
                         break;
                     }
@@ -973,7 +993,6 @@ extern "C" __global__ void sweep_kernel(const GpuRawCandle* __restrict__ raw_candles,
                     hybrid.open = sc.open;
                     hybrid.high = sc.high;
                     hybrid.low  = sc.low;
                     hybrid.close= sc.close;
-                    hybrid.volume = sc.volume;
                     hybrid.t_sec = sc.t_sec;

                     unsigned int sig = generate_signal(hybrid, &cfg);
@@ -1106,7 +1125,6 @@ extern "C" __global__ void sweep_kernel(const GpuRawCandle* __restrict__ raw_candles,
                             hybrid.open = sc.open;
                             hybrid.high = sc.high;
                             hybrid.low  = sc.low;
                             hybrid.close= sc.close;
-                            hybrid.volume = sc.volume;
                             hybrid.t_sec = sc.t_sec;
                             break;
                         }
```

That patch covers:

* remove the 3 places where sub-bar volume overwrote main-bar volume,
* implement `tp_partial_atr_mult`,
* don’t break out of the symbol’s sub-bar exit loop after partial TP (CPU keeps scanning).

---

One more thing to keep in mind

In your CLI GPU path you do:

```rust
let gpu_sub_candles = exit_candles.as_ref().or(entry_candles.as_ref());
```

So GPU can only use *one* sub-candle stream for both entry and exit. If you ever set `--entry-interval` and `--exit-interval` to different values, GPU will inherently diverge from CPU (CPU uses separate entry/exit sub-candle sets). If you need that feature, the kernel/host API needs two sub-candle buffers (or an interleaved layout) and two `sub_counts`.

---

Quick sanity check after applying

I’d validate in this order:

1. Run CPU sweep and GPU sweep on the same small spec (your smoke.yaml is perfect), with `--interval 1h --entry-interval 3m --exit-interval 3m` and the same `--config config/strategy_overrides.yaml`.
2. Compare at minimum: total trades, final equity, win-rate, avg pnl, max DD, and number of force-closes.
3. If still off, log a single combo and a single symbol with “replay-style” deterministic execution (same candles) and compare first divergence timestamp.

If you want, paste your current `smoke.yaml` (or one combo from it) and I’ll point to the next most-likely parity gaps (there are a couple other places where GPU and CPU can drift if certain features are enabled), but the three patches above are the big “this will absolutely break 1h+3m and/or confidence gating” class of issues.
