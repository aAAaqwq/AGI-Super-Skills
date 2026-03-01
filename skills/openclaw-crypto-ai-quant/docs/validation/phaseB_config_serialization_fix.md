# Phase B4 — config.rs `trade_to_json()` Serialization Fix

**Date:** 2026-02-14
**File:** `backtester/crates/bt-core/src/config.rs`

## Problem

`trade_to_json()` was missing 8 fields from serialization. These fields exist on
`TradeConfig` and have defaults in `impl Default for TradeConfig`, but were not
included in the `serde_json::json!({...})` macro call. Since `defaults_as_value()`
relies on `trade_to_json()` to produce the base YAML document for deep-merge,
any YAML config that omitted these fields would silently get `null` instead of
the correct default, causing deserialization errors or zero-initialized values.

## Missing Fields Added

| # | Field | Default Value | Location in JSON |
|---|-------|--------------|------------------|
| 1 | `trailing_start_atr_low_conf` | `0.0` | After `breakeven_buffer_atr` |
| 2 | `trailing_distance_atr_low_conf` | `0.0` | After field 1 |
| 3 | `smart_exit_adx_exhaustion_lt` | `18.0` | After field 2 |
| 4 | `smart_exit_adx_exhaustion_lt_low_conf` | `0.0` | After field 3 |
| 5 | `rsi_exit_ub_lo_profit_low_conf` | `0.0` | After `rsi_exit_lb_hi_profit` |
| 6 | `rsi_exit_ub_hi_profit_low_conf` | `0.0` | After field 5 |
| 7 | `rsi_exit_lb_lo_profit_low_conf` | `0.0` | After field 6 |
| 8 | `rsi_exit_lb_hi_profit_low_conf` | `0.0` | After field 7 |

## Full Audit of All `*_to_json()` Functions

| Function | Struct | Fields in Struct | Fields in JSON | Status |
|----------|--------|-----------------|----------------|--------|
| `trade_to_json` | `TradeConfig` | 75 | 75 (after fix) | ✅ Fixed |
| `indicators_to_json` | `IndicatorsConfig` | 14 | 14 | ✅ Complete |
| `filters_to_json` | `FiltersConfig` | 10 | 10 | ✅ Complete |
| `market_regime_to_json` | `MarketRegimeConfig` | 6 | 6 | ✅ Complete |
| `thresholds_to_json` | `ThresholdsConfig` (5 sub-structs) | 22+5+2+8+2=39 | 39 | ✅ Complete |
| `engine_to_json` | `EngineConfig` | 5 | 5 | ✅ Complete |

**Only `trade_to_json()` had missing fields.** All other serializers are complete.

## Compilation

```
$ cargo check -p bt-core
warning: `bt-core` (lib) generated 2 warnings
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.27s
```

No errors in `config.rs`. The 2 warnings are pre-existing issues in `engine.rs`
(unused mutable variable, unused variable) — unrelated to this fix.

## Impact

Without this fix, YAML configs relying on deep-merge would fail to propagate
defaults for the 8 low-confidence trailing/exit fields. Any symbol that didn't
explicitly set these fields would get `null` → deserialization failure, rather
than the intended default (mostly `0.0`, except `smart_exit_adx_exhaustion_lt`
which defaults to `18.0`).
