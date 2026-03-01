# Worker 3: Python Engine Usage Audit — 142 Sweep Axes

**Generated:** 2026-02-14  
**Source:** `backtester/sweeps/full_144v.yaml` (142 axes)  
**Audited files:** `strategy/mei_alpha_v1.py`, `engine/core.py`, `engine/daemon.py`, `live/trader.py`  

## Legend

| Status | Meaning |
|--------|---------|
| **USED** | Axis value is read from config and actively affects entry/exit/sizing/filtering logic |
| **STORED-ONLY** | Axis is loaded into config dict via defaults/YAML merge but never referenced in decision logic |
| **DEAD** | Axis path in sweep would be stored in config but the code reads it from a *different* config path (wrong section), so the sweep value is ignored |

---

## Summary

| Status | Count |
|--------|-------|
| USED | 130 |
| STORED-ONLY | 7 |
| DEAD | 5 |
| **Total** | **142** |

### 🔴 Critical Findings

1. **`indicators.ave_avg_atr_window`** — **DEAD**. The sweep writes to `indicators.ave_avg_atr_window` but the code reads from `thresholds.entry.ave_avg_atr_window` (line 3625). Sweeping this axis has zero effect.

2. **`market_regime.enable_regime_filter`** — **STORED-ONLY**. Defined in defaults but never checked in any logic. The engine uses `enable_regime_gate` (a separate key) instead.

3. **`market_regime.breadth_block_long_below`** / **`market_regime.breadth_block_short_above`** — **STORED-ONLY**. Defined in defaults but never read by any code path. The engine's regime gate uses `regime_gate_breadth_low/high` instead.

4. **`trade.reverse_entry_signal`** — **STORED-ONLY**. Defined in defaults (`False`) but never checked. The `_reversed_entry` indicator flag is set by a different mechanism (not from this config key).

5. **`trade.slippage_bps`** — **USED** but note: in live mode, `LiveTrader` uses `HL_LIVE_MARKET_SLIPPAGE_PCT` env var for actual order slippage, while `slippage_bps` is used for paper-mode fill simulation only.

### 🟡 Toggle-Gated Waste

6. When **`trade.enable_pyramiding = false`**, the sub-params `max_adds_per_symbol`, `add_cooldown_minutes`, `add_fraction_of_base_margin`, `add_min_profit_atr`, `add_min_confidence` are all checked inside `add_to_position()` which is already gated by `enable_pyramiding`. Sweeping these when pyramiding is off is **harmless but wasteful** — the code short-circuits before reading them.

7. When **`trade.enable_partial_tp = false`**, `tp_partial_pct` and `tp_partial_min_notional_usd` are gated and never reached.

8. When **`trade.enable_breakeven_stop = false`**, `breakeven_start_atr` and `breakeven_buffer_atr` are gated.

9. When **`thresholds.entry.enable_pullback_entries = false`**, all `pullback_*` sub-params are gated.

10. When **`thresholds.entry.enable_slow_drift_entries = false`**, all `slow_drift_*` sub-params are gated.

---

## Full Audit Table

| # | Axis Path | Status | Where Used | Notes |
|---|-----------|--------|------------|-------|
| 1 | `filters.adx_rising_saturation` | **USED** | `analyze()` L3671 | Saturation threshold: ADX rising check bypassed if ADX > this value |
| 2 | `filters.enable_anomaly_filter` | **USED** | `analyze()` L3588 | Gates the anomaly detection block |
| 3 | `filters.enable_extension_filter` | **USED** | `analyze()` L3708 | Gates the distance-to-EMA_fast filter |
| 4 | `filters.enable_ranging_filter` | **USED** | `analyze()` L3576 | Gates the ranging market detection |
| 5 | `filters.require_adx_rising` | **USED** | `analyze()` L3665 | Requires ADX to be rising (or > saturation) for entry |
| 6 | `filters.require_btc_alignment` | **USED** | `analyze()` L3692 | Gates BTC bullish/bearish alignment check |
| 7 | `filters.require_macro_alignment` | **USED** | `analyze()` L3687–3689 | Requires EMA_slow > EMA_macro for bullish alignment |
| 8 | `filters.require_volume_confirmation` | **USED** | `analyze()` L3673 | Gates volume confirmation check |
| 9 | `filters.use_stoch_rsi_filter` | **USED** | `analyze()` L3717, L3738, L3760 | Gates StochRSI computation and entry block |
| 10 | `filters.vol_confirm_include_prev` | **USED** | `analyze()` L3675 | Whether previous candle's volume counts for confirmation |
| 11 | `indicators.adx_window` | **USED** | `analyze()` L3542 | ADX indicator window |
| 12 | `indicators.atr_window` | **USED** | `analyze()` L3553 | ATR indicator window |
| 13 | `indicators.ave_avg_atr_window` | **DEAD** | — | Sweep writes to `indicators.ave_avg_atr_window` but code reads `thresholds.entry.ave_avg_atr_window` (L3625). This axis has zero effect. |
| 14 | `indicators.bb_width_avg_window` | **USED** | `analyze()` L3534 | Rolling average BB width window |
| 15 | `indicators.bb_window` | **USED** | `analyze()` L3547 | Bollinger Band window |
| 16 | `indicators.ema_fast_window` | **USED** | `analyze()` L3538 | EMA fast window |
| 17 | `indicators.ema_macro_window` | **USED** | `analyze()` L3539 | EMA macro (200) window |
| 18 | `indicators.ema_slow_window` | **USED** | `analyze()` L3537 | EMA slow window |
| 19 | `indicators.rsi_window` | **USED** | `analyze()` L3556 | RSI indicator window |
| 20 | `indicators.stoch_rsi_smooth1` | **USED** | `analyze()` L3720 | StochRSI smoothing parameter 1 |
| 21 | `indicators.stoch_rsi_smooth2` | **USED** | `analyze()` L3721 | StochRSI smoothing parameter 2 |
| 22 | `indicators.stoch_rsi_window` | **USED** | `analyze()` L3719 | StochRSI window |
| 23 | `indicators.vol_sma_window` | **USED** | `analyze()` L3561 | Volume SMA window |
| 24 | `indicators.vol_trend_window` | **USED** | `analyze()` L3562 | Volume trend window |
| 25 | `market_regime.auto_reverse_breadth_high` | **USED** | `engine/core.py` L1244, L2027 | Used as fallback for `regime_gate_breadth_high` and in heartbeat auto-reverse display |
| 26 | `market_regime.auto_reverse_breadth_low` | **USED** | `engine/core.py` L1240, L2027 | Used as fallback for `regime_gate_breadth_low` and in heartbeat auto-reverse display |
| 27 | `market_regime.breadth_block_long_below` | **STORED-ONLY** | — | In defaults dict only (L368). Never `.get()`'d by any logic path. |
| 28 | `market_regime.breadth_block_short_above` | **STORED-ONLY** | — | In defaults dict only (L367). Never `.get()`'d by any logic path. |
| 29 | `market_regime.enable_auto_reverse` | **USED** | `engine/core.py` L2025 | Checked in heartbeat to compute auto_rev display flag |
| 30 | `market_regime.enable_regime_filter` | **STORED-ONLY** | — | In defaults dict only (L366). Engine uses `enable_regime_gate` instead. |
| 31 | `thresholds.anomaly.ema_fast_dev_pct_gt` | **USED** | `analyze()` L3592 | Anomaly filter: EMA fast deviation threshold |
| 32 | `thresholds.anomaly.price_change_pct_gt` | **USED** | `analyze()` L3591 | Anomaly filter: price change threshold |
| 33 | `thresholds.entry.ave_adx_mult` | **USED** | `analyze()` L3622 | AVE: ADX multiplier for vol spike entries |
| 34 | `thresholds.entry.ave_atr_ratio_gt` | **USED** | `analyze()` L3618 | AVE: ATR ratio threshold |
| 35 | `thresholds.entry.ave_avg_atr_window` | **USED** | `analyze()` L3625 | AVE: rolling average ATR window. **This** is the one actually read by the code. |
| 36 | `thresholds.entry.ave_enabled` | **USED** | `analyze()` L3614 | AVE toggle |
| 37 | `thresholds.entry.btc_adx_override` | **USED** | `analyze()` L3695 | ADX threshold to bypass BTC alignment requirement |
| 38 | `thresholds.entry.enable_pullback_entries` | **USED** | `analyze()` L3700 | Pullback entry mode toggle |
| 39 | `thresholds.entry.enable_slow_drift_entries` | **USED** | `analyze()` L3733 | Slow drift entry mode toggle |
| 40 | `thresholds.entry.high_conf_volume_mult` | **USED** | `analyze()` L3736 | Volume multiplier for high confidence classification |
| 41 | `thresholds.entry.macd_hist_entry_mode` | **USED** | `analyze()` L3683 | MACD histogram gating mode (accel/sign/none) |
| 42 | `thresholds.entry.max_dist_ema_fast` | **USED** | `analyze()` L3709 | Extension filter: max distance from EMA fast |
| 43 | `thresholds.entry.min_adx` | **USED** | `analyze()` L3612, `compute_entry_sizing()`, `check_exit_conditions()` | Core entry ADX threshold |
| 44 | `thresholds.entry.pullback_confidence` | **USED** | `analyze()` L3702 | Confidence level assigned to pullback entries |
| 45 | `thresholds.entry.pullback_min_adx` | **USED** | `analyze()` L3704 | Min ADX for pullback entries |
| 46 | `thresholds.entry.pullback_require_macd_sign` | **USED** | `analyze()` L3714 | Whether pullback entries require MACD sign confirmation |
| 47 | `thresholds.entry.pullback_rsi_long_min` | **USED** | `analyze()` L3706 | RSI floor for long pullback entries |
| 48 | `thresholds.entry.pullback_rsi_short_max` | **USED** | `analyze()` L3710 | RSI ceiling for short pullback entries |
| 49 | `thresholds.entry.slow_drift_min_adx` | **USED** | `analyze()` L3744 | Min ADX for slow drift entries |
| 50 | `thresholds.entry.slow_drift_min_slope_pct` | **USED** | `analyze()` L3740 | Min EMA slow slope for slow drift |
| 51 | `thresholds.entry.slow_drift_require_macd_sign` | **USED** | `analyze()` L3756 | Whether slow drift entries require MACD sign |
| 52 | `thresholds.entry.slow_drift_rsi_long_min` | **USED** | `analyze()` L3748 | RSI floor for long slow drift entries |
| 53 | `thresholds.entry.slow_drift_rsi_short_max` | **USED** | `analyze()` L3752 | RSI ceiling for short slow drift entries |
| 54 | `thresholds.entry.slow_drift_slope_window` | **USED** | `analyze()` L3736 | Window for computing EMA slow slope |
| 55 | `thresholds.ranging.adx_below` | **USED** | `analyze()` L3581 | Ranging filter: ADX threshold |
| 56 | `thresholds.ranging.bb_width_ratio_below` | **USED** | `analyze()` L3583 | Ranging filter: BB width ratio threshold |
| 57 | `thresholds.ranging.min_signals` | **USED** | `analyze()` L3578 | Ranging filter: minimum signals to declare ranging |
| 58 | `thresholds.ranging.rsi_high` | **USED** | `analyze()` L3585 | Ranging filter: RSI upper bound |
| 59 | `thresholds.ranging.rsi_low` | **USED** | `analyze()` L3585 | Ranging filter: RSI lower bound |
| 60 | `thresholds.stoch_rsi.block_long_if_k_gt` | **USED** | `analyze()` L3738 | StochRSI: block long if K > threshold |
| 61 | `thresholds.stoch_rsi.block_short_if_k_lt` | **USED** | `analyze()` L3760 | StochRSI: block short if K < threshold |
| 62 | `thresholds.tp_and_momentum.adx_strong_gt` | **USED** | `analyze()` L3598 | Dynamic TP: ADX strong threshold |
| 63 | `thresholds.tp_and_momentum.adx_weak_lt` | **USED** | `analyze()` L3600 | Dynamic TP: ADX weak threshold |
| 64 | `thresholds.tp_and_momentum.rsi_long_strong` | **USED** | `analyze()` L3730 | DRE: RSI long limit at strong ADX |
| 65 | `thresholds.tp_and_momentum.rsi_long_weak` | **USED** | `analyze()` L3730 | DRE: RSI long limit at weak ADX |
| 66 | `thresholds.tp_and_momentum.rsi_short_strong` | **USED** | `analyze()` L3731 | DRE: RSI short limit at strong ADX |
| 67 | `thresholds.tp_and_momentum.rsi_short_weak` | **USED** | `analyze()` L3731 | DRE: RSI short limit at weak ADX |
| 68 | `thresholds.tp_and_momentum.tp_mult_strong` | **USED** | `analyze()` L3599 | Dynamic TP multiplier for strong trend |
| 69 | `thresholds.tp_and_momentum.tp_mult_weak` | **USED** | `analyze()` L3601 | Dynamic TP multiplier for weak trend |
| 70 | `trade.add_cooldown_minutes` | **USED** | `add_to_position()` (paper & live) | Cooldown between pyramid adds. Gated by `enable_pyramiding`. |
| 71 | `trade.add_fraction_of_base_margin` | **USED** | `add_to_position()` (paper & live) | Fraction of base margin for add sizing. Gated by `enable_pyramiding`. |
| 72 | `trade.add_min_confidence` | **USED** | `add_to_position()` (paper & live) | Min confidence for adds. Gated by `enable_pyramiding`. |
| 73 | `trade.add_min_profit_atr` | **USED** | `add_to_position()` (paper & live) | Min profit in ATR before adding. Gated by `enable_pyramiding`. |
| 74 | `trade.adx_sizing_full_adx` | **USED** | `compute_entry_sizing()`, `add_to_position()` | ADX value at which sizing scalar = 1.0. Gated by `enable_dynamic_sizing`. |
| 75 | `trade.adx_sizing_min_mult` | **USED** | `compute_entry_sizing()`, `add_to_position()` | Min sizing multiplier at min ADX. Gated by `enable_dynamic_sizing`. |
| 76 | `trade.allocation_pct` | **USED** | `compute_entry_sizing()`, `add_to_position()` | Base margin allocation per position |
| 77 | `trade.block_exits_on_extreme_dev` | **USED** | `check_exit_conditions()` L2772 | Toggle to block exits on extreme price deviation (glitch guard) |
| 78 | `trade.breakeven_buffer_atr` | **USED** | `check_exit_conditions()` L2801 | Breakeven stop buffer in ATR. Gated by `enable_breakeven_stop`. |
| 79 | `trade.breakeven_start_atr` | **USED** | `check_exit_conditions()` L2798 | Breakeven trigger distance in ATR. Gated by `enable_breakeven_stop`. |
| 80 | `trade.bump_to_min_notional` | **USED** | `execute_trade()` L2644, `add_to_position()` | Whether to bump sub-minimum orders up to min notional |
| 81 | `trade.confidence_mult_high` | **USED** | `compute_entry_sizing()`, `add_to_position()` | Sizing multiplier for high confidence. Gated by `enable_dynamic_sizing`. |
| 82 | `trade.confidence_mult_low` | **USED** | `compute_entry_sizing()`, `add_to_position()` | Sizing multiplier for low confidence. Gated by `enable_dynamic_sizing`. |
| 83 | `trade.confidence_mult_medium` | **USED** | `compute_entry_sizing()`, `add_to_position()` | Sizing multiplier for medium confidence. Gated by `enable_dynamic_sizing`. |
| 84 | `trade.enable_breakeven_stop` | **USED** | `check_exit_conditions()` L2795 | Toggle breakeven stop |
| 86 | `trade.enable_dynamic_sizing` | **USED** | `compute_entry_sizing()`, `add_to_position()` | Toggle dynamic sizing (confidence + ADX + vol scaling) |
| 87 | `trade.enable_partial_tp` | **USED** | `check_exit_conditions()` | Toggle partial take-profit ladder |
| 88 | `trade.enable_pyramiding` | **USED** | `add_to_position()` (paper & live) | Toggle pyramiding (scaling in) |
| 89 | `trade.enable_reef_filter` | **USED** | `execute_trade()` L2492 | Toggle REEF (RSI Entry Extreme Filter) |
| 90 | `trade.enable_rsi_overextension_exit` | **USED** | `check_exit_conditions()` | Toggle RSI overextension smart exit |
| 91 | `trade.enable_ssf_filter` | **USED** | `execute_trade()` L2466 | Toggle Signal Stability Filter (MACD sign gate) |
| 92 | `trade.enable_vol_buffered_trailing` | **USED** | `check_exit_conditions()` L2828 | Toggle volatility-buffered trailing stop |
| 93 | `trade.entry_cooldown_s` | **USED** | `_can_attempt_entry()` (paper) | Per-symbol entry cooldown in seconds |
| 94 | `trade.entry_min_confidence` | **USED** | `execute_trade()` L2371 | Min confidence for new entries |
| 95 | `trade.exit_cooldown_s` | **USED** | `_can_attempt_exit()` (paper) | Per-symbol exit cooldown in seconds |
| 96 | `trade.glitch_atr_mult` | **USED** | `check_exit_conditions()` L2769 | Glitch guard ATR multiplier. Gated by `block_exits_on_extreme_dev`. |
| 97 | `trade.glitch_price_dev_pct` | **USED** | `check_exit_conditions()` L2768 | Glitch guard price deviation %. Gated by `block_exits_on_extreme_dev`. |
| 98 | `trade.leverage` | **USED** | `_select_leverage()`, `add_to_position()` | Base leverage (used when dynamic leverage is off) |
| 99 | `trade.leverage_high` | **USED** | `_select_leverage()` | Leverage for high confidence |
| 100 | `trade.leverage_low` | **USED** | `_select_leverage()` | Leverage for low confidence |
| 102 | `trade.leverage_medium` | **USED** | `_select_leverage()` | Leverage for medium confidence |
| 103 | `trade.max_adds_per_symbol` | **USED** | `add_to_position()` (paper & live) | Max pyramid adds per symbol. Gated by `enable_pyramiding`. |
| 104 | `trade.max_entry_orders_per_loop` | **USED** | `daemon.py` PaperPlugin/LivePlugin `before_iteration()` | Per-loop entry budget |
| 105 | `trade.max_open_positions` | **USED** | `execute_trade()` L2384 | Max concurrent open positions |
| 106 | `trade.max_total_margin_pct` | **USED** | `execute_trade()`, `add_to_position()` | Global margin cap as % of equity |
| 107 | `trade.min_atr_pct` | **USED** | `PythonAnalyzeDecisionProvider.get_decisions()` in `core.py` | ATR floor: ensures ATR ≥ price × min_atr_pct |
| 108 | `trade.min_notional_usd` | **USED** | `execute_trade()`, `add_to_position()`, `live/trader.py` | Min order notional |
| 109 | `trade.reef_adx_threshold` | **USED** | `execute_trade()` L2494 (REEF v2), `analyze()` audit | ADX threshold for extreme vs baseline REEF |
| 110 | `trade.reef_long_rsi_block_gt` | **USED** | `execute_trade()` L2497 | REEF: block long entry if RSI > this. Gated by `enable_reef_filter`. |
| 111 | `trade.reef_long_rsi_extreme_gt` | **USED** | `execute_trade()` (REEF v2 extreme tier) | REEF extreme tier for high ADX. Gated by `enable_reef_filter`. |
| 112 | `trade.reef_short_rsi_block_lt` | **USED** | `execute_trade()` L2507 | REEF: block short if RSI < this. Gated by `enable_reef_filter`. |
| 113 | `trade.reef_short_rsi_extreme_lt` | **USED** | `execute_trade()` (REEF v2 extreme tier) | REEF extreme tier for high ADX. Gated by `enable_reef_filter`. |
| 114 | `trade.reentry_cooldown_max_mins` | **USED** | `execute_trade()` PESC L2410 | Max cooldown (weak trend ADX ≤ 25) |
| 115 | `trade.reentry_cooldown_min_mins` | **USED** | `execute_trade()` PESC L2409 | Min cooldown (strong trend ADX ≥ 40) |
| 116 | `trade.reentry_cooldown_minutes` | **USED** | `execute_trade()` PESC L2407 | Base re-entry cooldown |
| 117 | `trade.reverse_entry_signal` | **STORED-ONLY** | — | In defaults dict (L316, `False`) but never `.get()`'d by any code path. The `_reversed_entry` flag is set elsewhere. |
| 118 | `trade.rsi_exit_lb_hi_profit` | **USED** | `check_exit_conditions()` | RSI lower bound (high profit regime). Gated by `enable_rsi_overextension_exit`. |
| 119 | `trade.rsi_exit_lb_hi_profit_low_conf` | **USED** | `check_exit_conditions()` | Per-confidence override for low-conf positions. Gated by `enable_rsi_overextension_exit`. |
| 120 | `trade.rsi_exit_lb_lo_profit` | **USED** | `check_exit_conditions()` | RSI lower bound (low profit regime). Gated by `enable_rsi_overextension_exit`. |
| 121 | `trade.rsi_exit_lb_lo_profit_low_conf` | **USED** | `check_exit_conditions()` | Per-confidence override. Gated by `enable_rsi_overextension_exit`. |
| 122 | `trade.rsi_exit_profit_atr_switch` | **USED** | `check_exit_conditions()` | ATR profit threshold switching lo/hi RSI regime. Gated by `enable_rsi_overextension_exit`. |
| 123 | `trade.rsi_exit_ub_hi_profit` | **USED** | `check_exit_conditions()` | RSI upper bound (high profit). Gated by `enable_rsi_overextension_exit`. |
| 124 | `trade.rsi_exit_ub_hi_profit_low_conf` | **USED** | `check_exit_conditions()` | Per-confidence override. Gated by `enable_rsi_overextension_exit`. |
| 125 | `trade.rsi_exit_ub_lo_profit` | **USED** | `check_exit_conditions()` | RSI upper bound (low profit). Gated by `enable_rsi_overextension_exit`. |
| 126 | `trade.rsi_exit_ub_lo_profit_low_conf` | **USED** | `check_exit_conditions()` | Per-confidence override. Gated by `enable_rsi_overextension_exit`. |
| 127 | `trade.sl_atr_mult` | **USED** | `check_exit_conditions()` L2758 | Stop loss ATR multiplier |
| 128 | `trade.slippage_bps` | **USED** | `_get_fill_price()`, `execute_trade()`, `add_to_position()` | Slippage in basis points for paper fill simulation |
| 129 | `trade.smart_exit_adx_exhaustion_lt` | **USED** | `check_exit_conditions()` L2778 | ADX exhaustion exit threshold (legacy fallback) |
| 130 | `trade.smart_exit_adx_exhaustion_lt_low_conf` | **USED** | `check_exit_conditions()` L2783 | Per-confidence override for low-conf positions |
| 131 | `trade.tp_atr_mult` | **USED** | `check_exit_conditions()` L2759 | Take profit ATR multiplier |
| 132 | `trade.tp_partial_min_notional_usd` | **USED** | `check_exit_conditions()` | Min notional for partial TP. Gated by `enable_partial_tp`. |
| 133 | `trade.tp_partial_pct` | **USED** | `check_exit_conditions()` | % of position to close at partial TP. Gated by `enable_partial_tp`. |
| 134 | `trade.trailing_distance_atr` | **USED** | `check_exit_conditions()` L2762 | Trailing stop distance in ATR |
| 135 | `trade.trailing_distance_atr_low_conf` | **USED** | `check_exit_conditions()` L2773 | Per-confidence trailing distance override |
| 136 | `trade.trailing_start_atr` | **USED** | `check_exit_conditions()` L2761 | Trailing stop activation distance in ATR |
| 137 | `trade.trailing_start_atr_low_conf` | **USED** | `check_exit_conditions()` L2770 | Per-confidence trailing start override |
| 138 | `trade.tsme_min_profit_atr` | **USED** | `check_exit_conditions()` | TSME min profit gate. |
| 139 | `trade.tsme_require_adx_slope_negative` | **USED** | `check_exit_conditions()` | TSME ADX slope gate. |
| 140 | `trade.vol_baseline_pct` | **USED** | `compute_entry_sizing()`, `add_to_position()` | ATR-based vol scaling baseline. Gated by non-zero ATR. |
| 141 | `trade.vol_scalar_max` | **USED** | `compute_entry_sizing()`, `add_to_position()` | Max vol scalar clamp |
| 142 | `trade.vol_scalar_min` | **USED** | `compute_entry_sizing()`, `add_to_position()` | Min vol scalar clamp |

---

## Detailed Notes on STORED-ONLY / DEAD Axes

### 1. `indicators.ave_avg_atr_window` — **DEAD** ⚠️

The sweep YAML has this under `indicators.*` but the code only reads it from `thresholds.entry.ave_avg_atr_window`:

```python
# strategy/mei_alpha_v1.py, line 3625:
ave_window = int(thr_entry.get("ave_avg_atr_window", 50) or 50)
```

The `indicators` section of the default config does NOT contain `ave_avg_atr_window`. Sweeping `indicators.ave_avg_atr_window` writes a value that is never read. **The sweep should use `thresholds.entry.ave_avg_atr_window` instead** (which is already a separate axis at row 35).

**Impact:** This axis produces **3 sweep values × 0 effect = pure waste**. The Rust backtester may read it differently (this audit is Python-only).

### 2. `market_regime.enable_regime_filter` — **STORED-ONLY**

Defined in defaults (L366) but never referenced in logic. The engine's actual regime gate uses `enable_regime_gate` (a different key at L373). This might be a legacy key that was superseded.

### 3. `market_regime.breadth_block_long_below` — **STORED-ONLY**

Defined in defaults (L368) but the code never calls `.get("breadth_block_long_below")`. The engine regime gate uses `regime_gate_breadth_low` (L374).

### 4. `market_regime.breadth_block_short_above` — **STORED-ONLY**

Same as above; the code uses `regime_gate_breadth_high` instead.

### 5. `trade.reverse_entry_signal` — **STORED-ONLY**

Defined in defaults (L316, `False`). No code path checks `trade_cfg.get("reverse_entry_signal")`. The `_reversed_entry` indicator flag used in logging is set by a separate mechanism (indicator annotation), not from this config key.

---

## Toggle-Gated Sub-Parameter Analysis

### `enable_pyramiding` gates:
When `enable_pyramiding = false`, `add_to_position()` returns immediately at the first check. These sub-params are never evaluated:
- `trade.max_adds_per_symbol`
- `trade.add_cooldown_minutes`
- `trade.add_fraction_of_base_margin`
- `trade.add_min_profit_atr`
- `trade.add_min_confidence`

**Sweep waste when pyramiding=off:** 5 axes × their values = wasted combinations.

### `enable_partial_tp` gates:
- `trade.tp_partial_pct`
- `trade.tp_partial_min_notional_usd`

### `enable_breakeven_stop` gates:
- `trade.breakeven_start_atr`
- `trade.breakeven_buffer_atr`

### `enable_pullback_entries` gates:
- `thresholds.entry.pullback_confidence`
- `thresholds.entry.pullback_min_adx`
- `thresholds.entry.pullback_rsi_long_min`
- `thresholds.entry.pullback_rsi_short_max`
- `thresholds.entry.pullback_require_macd_sign`

### `enable_slow_drift_entries` gates:
- `thresholds.entry.slow_drift_slope_window`
- `thresholds.entry.slow_drift_min_slope_pct`
- `thresholds.entry.slow_drift_min_adx`
- `thresholds.entry.slow_drift_rsi_long_min`
- `thresholds.entry.slow_drift_rsi_short_max`
- `thresholds.entry.slow_drift_require_macd_sign`

### `enable_reef_filter` gates:
- `trade.reef_long_rsi_block_gt`
- `trade.reef_short_rsi_block_lt`
- `trade.reef_adx_threshold`
- `trade.reef_long_rsi_extreme_gt`
- `trade.reef_short_rsi_extreme_lt`

### `enable_dynamic_sizing` gates:
- `trade.confidence_mult_high`
- `trade.confidence_mult_medium`
- `trade.confidence_mult_low`
- `trade.adx_sizing_min_mult`
- `trade.adx_sizing_full_adx`

### `enable_rsi_overextension_exit` gates:
- All `trade.rsi_exit_*` params (8 axes)
- `trade.rsi_exit_profit_atr_switch`

### `enable_vol_buffered_trailing` gates:
- (No dedicated sub-params in sweep; it modifies `trailing_distance_atr` internally.)

### `block_exits_on_extreme_dev` gates:
- `trade.glitch_price_dev_pct`
- `trade.glitch_atr_mult`

---

## Recommendations

1. **Remove or re-path `indicators.ave_avg_atr_window`** from the sweep — it is a dead axis. The code reads `thresholds.entry.ave_avg_atr_window` which is already swept separately.

2. **Remove `market_regime.enable_regime_filter`** from sweep — STORED-ONLY, engine uses `enable_regime_gate`.

3. **Remove `market_regime.breadth_block_long_below` and `breadth_block_short_above`** from sweep — STORED-ONLY, engine uses `regime_gate_breadth_low/high`.

4. **Remove `trade.reverse_entry_signal`** from sweep — STORED-ONLY, no code reads it.

5. **Consider conditional sweep logic** for toggle-gated sub-params (e.g. skip pyramiding sub-params when `enable_pyramiding=0`) to reduce sweep space.

6. **Verify Rust backtester parity** — this audit covers the Python engine only. The Rust backtester (`bt_runtime`) may read these config values differently; a parallel audit of the Rust code is recommended.
