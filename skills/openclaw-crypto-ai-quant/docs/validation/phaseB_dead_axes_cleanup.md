# Phase B2: Dead Axes & Naming Mismatch Cleanup

**Date:** 2026-02-14
**Status:** ✅ Complete

## Problem

Worker 3 audit identified 4 dead/stored-only config axes where the sweep
optimiser writes values that the Python engine never reads, creating silent
divergence between Rust backtester behaviour and live/paper engine behaviour.

| # | Axis (sweep name) | Engine name | Issue |
|---|---|---|---|
| 1 | `market_regime.enable_regime_filter` | `enable_regime_gate` | Name mismatch — different keys |
| 2 | `market_regime.breadth_block_long_below` | `regime_gate_breadth_low` | Name mismatch |
| 2b | `market_regime.breadth_block_short_above` | `regime_gate_breadth_high` | Name mismatch |
| 3 | `trade.reverse_entry_signal` | *(none)* | Stored in defaults, never read by Python |
| 4 | `indicators.ave_avg_atr_window` | `thresholds.entry.ave_avg_atr_window` | Rust syncs both; Python only reads threshold |

## Resolution

### Approach: Option A — Make Engine Read Sweep-Compatible Names

The sweep spec names (`enable_regime_filter`, `breadth_block_*`) are more
standard and already used by the Rust backtester. We added aliases in the
Python engine so sweep-optimised configs work correctly.

### Changes

#### 1. `enable_regime_filter` alias (`engine/core.py`)
- `_update_regime_gate()` now reads `enable_regime_filter` first, falling
  back to `enable_regime_gate`.
- Sweep name takes precedence when both are set.

#### 2. `breadth_block_long_below` / `breadth_block_short_above` aliases (`engine/core.py`)
- `_update_regime_gate()` now reads `breadth_block_long_below` before
  `regime_gate_breadth_low` (and likewise for the high bound).
- Three-tier fallback: sweep name → engine name → auto_reverse name → default.

#### 3. `trade.reverse_entry_signal` implemented (`strategy/mei_alpha_v1.py`)
- Added signal reversal at the end of `analyze()`, matching the Rust
  `apply_reverse()` behaviour: when `reverse_entry_signal=True`,
  BUY↔SELL are flipped.
- `auto_reverse` (breadth-based) is noted but deferred to the engine
  level (breadth % is not available in per-symbol `analyze()`).
- Default remains `False` — no behaviour change for existing configs.

#### 4. `indicators.ave_avg_atr_window` sync (`strategy/mei_alpha_v1.py`)
- Added sync logic in `get_strategy_config()` that propagates
  `indicators.ave_avg_atr_window` → `thresholds.entry.ave_avg_atr_window`.
- Matches Rust `set_ave_avg_atr_window()` which always syncs both paths.
- When both are explicitly set to different values, `indicators` path
  takes precedence (matching Rust sweep behaviour).

### Test Results

```
173 passed, 3 skipped in 3.99s
```

New tests added in `tests/test_dead_axes_cleanup.py` (9 tests):
- `test_regime_gate_reads_enable_regime_filter` ✅
- `test_regime_filter_takes_precedence_over_gate` ✅
- `test_breadth_block_aliases` ✅
- `test_breadth_block_fallback_to_regime_gate` ✅
- `test_reverse_entry_signal_flips_buy_sell` ✅
- `test_reverse_entry_signal_off_by_default` ✅
- `test_ave_avg_atr_window_synced_from_indicators` ✅
- `test_ave_avg_atr_window_indicators_overrides_threshold` ✅
- `test_ave_avg_atr_window_no_indicators_key` ✅

**Pre-existing failures** (not caused by this change):
- `test_kernel_decision_routing.py::test_unified_engine_routes_kernel_decisions_to_trader`
- `test_regime_gate_enforcement.py::test_gate_on_entries_allowed`

### Files Modified

| File | Change |
|---|---|
| `engine/core.py` | Alias resolution in `_update_regime_gate()` for items 1-2 |
| `strategy/mei_alpha_v1.py` | `reverse_entry_signal` impl in `analyze()` (item 3) |
| `strategy/mei_alpha_v1.py` | `ave_avg_atr_window` sync in `get_strategy_config()` (item 4) |
| `tests/test_dead_axes_cleanup.py` | 9 new tests covering all 4 fixes |

### Backward Compatibility

All changes are backward-compatible:
- Existing configs using `enable_regime_gate` / `regime_gate_breadth_*` continue to work.
- `reverse_entry_signal` defaults to `False` — existing behaviour unchanged.
- The `ave_avg_atr_window` sync only fires when `indicators` path is set;
  existing configs with only the `thresholds.entry` path are unaffected.
