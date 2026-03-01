//! Parallel parameter sweep engine using rayon.
//!
//! Generates a cartesian product of config overrides from a [`SweepSpec`],
//! runs each combination through `engine::run_simulation` in parallel via
//! rayon, and returns sorted results.

use std::sync::Arc;

use rayon::prelude::*;
use serde::{Deserialize, Serialize};

use crate::candle::{CandleData, FundingRateData};
use crate::config::{Confidence, MacdMode, StrategyConfig};
use crate::engine;
use crate::report::{self, SimReport};

// ---------------------------------------------------------------------------
// Sweep specification (loaded from YAML)
// ---------------------------------------------------------------------------

/// Optional gate condition: this axis is only expanded when the gate axis
/// has a specific value.  When the gate is not satisfied, the axis freezes
/// at its first value (reducing the combination count).
#[derive(Debug, Clone, Deserialize)]
pub struct AxisGate {
    /// Dot-separated path of the gate axis.
    pub path: String,
    /// Gate is satisfied when the gate axis value equals this (±1e-9).
    pub eq: f64,
}

/// A single axis in the parameter sweep.
#[derive(Debug, Clone, Deserialize)]
pub struct SweepAxis {
    /// Dot-separated config path, e.g. "trade.sl_atr_mult"
    pub path: String,
    /// Values to test along this axis.
    pub values: Vec<f64>,
    /// Optional gate: only expand this axis when the gate condition is met.
    /// When the gate is not met, the axis freezes at its first value.
    #[serde(default)]
    pub gate: Option<AxisGate>,
}

/// Full sweep specification (loaded from YAML).
#[derive(Debug, Clone, Deserialize)]
pub struct SweepSpec {
    pub axes: Vec<SweepAxis>,
    #[serde(default = "default_initial_balance")]
    pub initial_balance: f64,
    #[serde(default = "default_lookback")]
    pub lookback: usize,
}

fn default_initial_balance() -> f64 {
    10000.0
}
fn default_lookback() -> usize {
    200
}

// ---------------------------------------------------------------------------
// Sweep result
// ---------------------------------------------------------------------------

/// Result of one sweep configuration.
#[derive(Debug, Clone)]
pub struct SweepResult {
    pub config_id: String,
    pub report: SimReport,
    pub overrides: Vec<(String, f64)>,
}

// ---------------------------------------------------------------------------
// Config generation (cartesian product)
// ---------------------------------------------------------------------------

/// Generate all combinations from the sweep axes, respecting gate conditions.
///
/// Axes are processed in dependency order (ungated first, then gated).
/// When a gate condition is not met, the gated axis freezes at its first
/// value, dramatically reducing the number of combinations.
fn generate_combinations(axes: &[SweepAxis]) -> Vec<Vec<(String, f64)>> {
    if axes.is_empty() {
        return vec![vec![]];
    }

    // Sort: ungated axes first, gated axes second.
    // This ensures gate values are available when processing gated axes.
    let mut sorted: Vec<&SweepAxis> = axes.iter().collect();
    sorted.sort_by_key(|a| u8::from(a.gate.is_some()));

    let mut combos: Vec<Vec<(String, f64)>> = vec![vec![]];

    for axis in &sorted {
        let mut new_combos = Vec::with_capacity(combos.len() * axis.values.len());
        for combo in &combos {
            let expand = if let Some(gate) = &axis.gate {
                // Look up the gate axis value in the current partial combination.
                combo
                    .iter()
                    .find(|(p, _)| *p == gate.path)
                    .map_or(true, |(_, v)| (*v - gate.eq).abs() < 1e-9)
            } else {
                true
            };

            let vals = if expand {
                &axis.values[..]
            } else {
                // Gate not met — freeze at first value.
                &axis.values[..1]
            };

            for val in vals {
                let mut new_combo = combo.clone();
                new_combo.push((axis.path.clone(), *val));
                new_combos.push(new_combo);
            }
        }
        combos = new_combos;
    }

    combos
}

// ---------------------------------------------------------------------------
// apply_override — set a config field by dot-path
// ---------------------------------------------------------------------------

/// Apply a set of overrides to a cloned config.
fn apply_overrides(base: &StrategyConfig, overrides: &[(String, f64)]) -> StrategyConfig {
    let mut cfg = base.clone();
    for (path, value) in overrides {
        apply_one(&mut cfg, path, *value);
    }
    cfg
}

/// Set a single f64 config value by dot-separated path.
///
/// Supports all common sweep parameters. Integer fields (usize) are cast
/// from f64. Unknown paths are logged to stderr.
/// Public wrapper for `apply_one` used by bt-gpu crate.
pub fn apply_one_pub(cfg: &mut StrategyConfig, path: &str, value: f64) {
    apply_one(cfg, path, value);
}

fn set_ave_avg_atr_window(cfg: &mut StrategyConfig, window: usize) {
    cfg.thresholds.entry.ave_avg_atr_window = window;
    cfg.indicators.ave_avg_atr_window = window;
}

fn apply_one(cfg: &mut StrategyConfig, path: &str, value: f64) {
    match path {
        // === Trade config ===
        "trade.sl_atr_mult" => cfg.trade.sl_atr_mult = value,
        "trade.tp_atr_mult" => cfg.trade.tp_atr_mult = value,
        "trade.trailing_start_atr" => cfg.trade.trailing_start_atr = value,
        "trade.trailing_distance_atr" => cfg.trade.trailing_distance_atr = value,
        "trade.allocation_pct" => cfg.trade.allocation_pct = value,
        "trade.leverage" => cfg.trade.leverage = value,
        "trade.max_open_positions" => cfg.trade.max_open_positions = value as usize,
        "trade.min_atr_pct" => cfg.trade.min_atr_pct = value,
        "trade.slippage_bps" => cfg.trade.slippage_bps = value,
        "trade.min_notional_usd" => cfg.trade.min_notional_usd = value,
        "trade.use_bbo_for_fills" => cfg.trade.use_bbo_for_fills = value != 0.0,
        "trade.bump_to_min_notional" => cfg.trade.bump_to_min_notional = value != 0.0,
        "trade.max_total_margin_pct" => cfg.trade.max_total_margin_pct = value,
        "trade.reentry_cooldown_minutes" => cfg.trade.reentry_cooldown_minutes = value as usize,
        "trade.reentry_cooldown_min_mins" => cfg.trade.reentry_cooldown_min_mins = value as usize,
        "trade.reentry_cooldown_max_mins" => cfg.trade.reentry_cooldown_max_mins = value as usize,
        "trade.breakeven_start_atr" => cfg.trade.breakeven_start_atr = value,
        "trade.breakeven_buffer_atr" => cfg.trade.breakeven_buffer_atr = value,
        "trade.confidence_mult_low" => cfg.trade.confidence_mult_low = value,
        "trade.confidence_mult_medium" => cfg.trade.confidence_mult_medium = value,
        "trade.confidence_mult_high" => cfg.trade.confidence_mult_high = value,
        "trade.tsme_min_profit_atr" => cfg.trade.tsme_min_profit_atr = value,
        "trade.rsi_exit_profit_atr_switch" => cfg.trade.rsi_exit_profit_atr_switch = value,
        "trade.rsi_exit_ub_lo_profit" => cfg.trade.rsi_exit_ub_lo_profit = value,
        "trade.rsi_exit_ub_hi_profit" => cfg.trade.rsi_exit_ub_hi_profit = value,
        "trade.rsi_exit_lb_lo_profit" => cfg.trade.rsi_exit_lb_lo_profit = value,
        "trade.rsi_exit_lb_hi_profit" => cfg.trade.rsi_exit_lb_hi_profit = value,
        "trade.rsi_exit_ub_lo_profit_low_conf" => cfg.trade.rsi_exit_ub_lo_profit_low_conf = value,
        "trade.rsi_exit_ub_hi_profit_low_conf" => cfg.trade.rsi_exit_ub_hi_profit_low_conf = value,
        "trade.rsi_exit_lb_lo_profit_low_conf" => cfg.trade.rsi_exit_lb_lo_profit_low_conf = value,
        "trade.rsi_exit_lb_hi_profit_low_conf" => cfg.trade.rsi_exit_lb_hi_profit_low_conf = value,
        "trade.tp_partial_pct" => cfg.trade.tp_partial_pct = value,
        "trade.tp_partial_atr_mult" => cfg.trade.tp_partial_atr_mult = value,
        "trade.tp_partial_min_notional_usd" => cfg.trade.tp_partial_min_notional_usd = value,
        "trade.add_min_profit_atr" => cfg.trade.add_min_profit_atr = value,
        "trade.add_fraction_of_base_margin" => cfg.trade.add_fraction_of_base_margin = value,
        "trade.max_adds_per_symbol" => cfg.trade.max_adds_per_symbol = value as usize,
        "trade.add_cooldown_minutes" => cfg.trade.add_cooldown_minutes = value as usize,
        "trade.leverage_low" => cfg.trade.leverage_low = value,
        "trade.leverage_medium" => cfg.trade.leverage_medium = value,
        "trade.leverage_high" => cfg.trade.leverage_high = value,
        "trade.adx_sizing_min_mult" => cfg.trade.adx_sizing_min_mult = value,
        "trade.adx_sizing_full_adx" => cfg.trade.adx_sizing_full_adx = value,
        "trade.vol_baseline_pct" => cfg.trade.vol_baseline_pct = value,
        "trade.vol_scalar_min" => cfg.trade.vol_scalar_min = value,
        "trade.vol_scalar_max" => cfg.trade.vol_scalar_max = value,
        "trade.entry_cooldown_s" => cfg.trade.entry_cooldown_s = value as usize,
        "trade.exit_cooldown_s" => cfg.trade.exit_cooldown_s = value as usize,
        "trade.max_entry_orders_per_loop" => cfg.trade.max_entry_orders_per_loop = value as usize,
        "trade.glitch_price_dev_pct" => cfg.trade.glitch_price_dev_pct = value,
        "trade.glitch_atr_mult" => cfg.trade.glitch_atr_mult = value,
        "trade.reef_long_rsi_block_gt" => cfg.trade.reef_long_rsi_block_gt = value,
        "trade.reef_short_rsi_block_lt" => cfg.trade.reef_short_rsi_block_lt = value,
        "trade.reef_adx_threshold" => cfg.trade.reef_adx_threshold = value,
        "trade.reef_long_rsi_extreme_gt" => cfg.trade.reef_long_rsi_extreme_gt = value,
        "trade.reef_short_rsi_extreme_lt" => cfg.trade.reef_short_rsi_extreme_lt = value,
        "trade.trailing_start_atr_low_conf" => cfg.trade.trailing_start_atr_low_conf = value,
        "trade.trailing_distance_atr_low_conf" => cfg.trade.trailing_distance_atr_low_conf = value,
        "trade.smart_exit_adx_exhaustion_lt" => cfg.trade.smart_exit_adx_exhaustion_lt = value,
        "trade.smart_exit_adx_exhaustion_lt_low_conf" => {
            cfg.trade.smart_exit_adx_exhaustion_lt_low_conf = value
        }

        // === Confidence enums (0=low, 1=medium, 2=high) ===
        "trade.entry_min_confidence" => {
            cfg.trade.entry_min_confidence = match value as u8 {
                0 => Confidence::Low,
                1 => Confidence::Medium,
                _ => Confidence::High,
            };
        }
        "trade.add_min_confidence" => {
            cfg.trade.add_min_confidence = match value as u8 {
                0 => Confidence::Low,
                1 => Confidence::Medium,
                _ => Confidence::High,
            };
        }
        "thresholds.entry.pullback_confidence" => {
            cfg.thresholds.entry.pullback_confidence = match value as u8 {
                0 => Confidence::Low,
                1 => Confidence::Medium,
                _ => Confidence::High,
            };
        }

        // === Thresholds — entry ===
        "thresholds.entry.min_adx" => cfg.thresholds.entry.min_adx = value,
        "thresholds.entry.high_conf_volume_mult" => {
            cfg.thresholds.entry.high_conf_volume_mult = value
        }
        "thresholds.entry.btc_adx_override" => cfg.thresholds.entry.btc_adx_override = value,
        "thresholds.entry.max_dist_ema_fast" => cfg.thresholds.entry.max_dist_ema_fast = value,
        "thresholds.entry.ave_atr_ratio_gt" => cfg.thresholds.entry.ave_atr_ratio_gt = value,
        "thresholds.entry.ave_adx_mult" => cfg.thresholds.entry.ave_adx_mult = value,
        "thresholds.entry.ave_avg_atr_window" => set_ave_avg_atr_window(cfg, value as usize),
        "thresholds.entry.pullback_min_adx" => cfg.thresholds.entry.pullback_min_adx = value,
        "thresholds.entry.pullback_rsi_long_min" => {
            cfg.thresholds.entry.pullback_rsi_long_min = value
        }
        "thresholds.entry.pullback_rsi_short_max" => {
            cfg.thresholds.entry.pullback_rsi_short_max = value
        }
        "thresholds.entry.slow_drift_slope_window" => {
            cfg.thresholds.entry.slow_drift_slope_window = value as usize
        }
        "thresholds.entry.slow_drift_min_slope_pct" => {
            cfg.thresholds.entry.slow_drift_min_slope_pct = value
        }
        "thresholds.entry.slow_drift_min_adx" => cfg.thresholds.entry.slow_drift_min_adx = value,
        "thresholds.entry.slow_drift_rsi_long_min" => {
            cfg.thresholds.entry.slow_drift_rsi_long_min = value
        }
        "thresholds.entry.slow_drift_rsi_short_max" => {
            cfg.thresholds.entry.slow_drift_rsi_short_max = value
        }
        "thresholds.entry.macd_hist_entry_mode" => {
            cfg.thresholds.entry.macd_hist_entry_mode = match value as u8 {
                0 => MacdMode::Accel,
                1 => MacdMode::Sign,
                _ => MacdMode::None,
            };
        }

        // === Thresholds — ranging ===
        "thresholds.ranging.min_signals" => cfg.thresholds.ranging.min_signals = value as usize,
        "thresholds.ranging.adx_below" => cfg.thresholds.ranging.adx_below = value,
        "thresholds.ranging.bb_width_ratio_below" => {
            cfg.thresholds.ranging.bb_width_ratio_below = value
        }
        "thresholds.ranging.rsi_low" => cfg.thresholds.ranging.rsi_low = value,
        "thresholds.ranging.rsi_high" => cfg.thresholds.ranging.rsi_high = value,

        // === Thresholds — anomaly ===
        "thresholds.anomaly.price_change_pct_gt" => {
            cfg.thresholds.anomaly.price_change_pct_gt = value
        }
        "thresholds.anomaly.ema_fast_dev_pct_gt" => {
            cfg.thresholds.anomaly.ema_fast_dev_pct_gt = value
        }

        // === Thresholds — tp_and_momentum ===
        "thresholds.tp_and_momentum.adx_strong_gt" => {
            cfg.thresholds.tp_and_momentum.adx_strong_gt = value
        }
        "thresholds.tp_and_momentum.adx_weak_lt" => {
            cfg.thresholds.tp_and_momentum.adx_weak_lt = value
        }
        "thresholds.tp_and_momentum.tp_mult_strong" => {
            cfg.thresholds.tp_and_momentum.tp_mult_strong = value
        }
        "thresholds.tp_and_momentum.tp_mult_weak" => {
            cfg.thresholds.tp_and_momentum.tp_mult_weak = value
        }
        "thresholds.tp_and_momentum.rsi_long_strong" => {
            cfg.thresholds.tp_and_momentum.rsi_long_strong = value
        }
        "thresholds.tp_and_momentum.rsi_long_weak" => {
            cfg.thresholds.tp_and_momentum.rsi_long_weak = value
        }
        "thresholds.tp_and_momentum.rsi_short_strong" => {
            cfg.thresholds.tp_and_momentum.rsi_short_strong = value
        }
        "thresholds.tp_and_momentum.rsi_short_weak" => {
            cfg.thresholds.tp_and_momentum.rsi_short_weak = value
        }

        // === Thresholds — stoch_rsi ===
        "thresholds.stoch_rsi.block_long_if_k_gt" => {
            cfg.thresholds.stoch_rsi.block_long_if_k_gt = value
        }
        "thresholds.stoch_rsi.block_short_if_k_lt" => {
            cfg.thresholds.stoch_rsi.block_short_if_k_lt = value
        }

        // === Boolean toggles (0.0 = false, else true) ===
        "trade.enable_dynamic_sizing" => cfg.trade.enable_dynamic_sizing = value != 0.0,
        "trade.enable_pyramiding" => cfg.trade.enable_pyramiding = value != 0.0,
        "trade.enable_partial_tp" => cfg.trade.enable_partial_tp = value != 0.0,
        "trade.enable_ssf_filter" => cfg.trade.enable_ssf_filter = value != 0.0,
        "trade.enable_reef_filter" => cfg.trade.enable_reef_filter = value != 0.0,
        "trade.enable_breakeven_stop" => cfg.trade.enable_breakeven_stop = value != 0.0,
        "trade.enable_rsi_overextension_exit" => {
            cfg.trade.enable_rsi_overextension_exit = value != 0.0
        }
        "trade.enable_vol_buffered_trailing" => {
            cfg.trade.enable_vol_buffered_trailing = value != 0.0
        }
        "trade.tsme_require_adx_slope_negative" => {
            cfg.trade.tsme_require_adx_slope_negative = value != 0.0
        }
        "trade.reverse_entry_signal" => cfg.trade.reverse_entry_signal = value != 0.0,
        "trade.block_exits_on_extreme_dev" => cfg.trade.block_exits_on_extreme_dev = value != 0.0,
        "filters.vol_confirm_include_prev" => cfg.filters.vol_confirm_include_prev = value != 0.0,

        // === Filters ===
        "filters.enable_ranging_filter" => cfg.filters.enable_ranging_filter = value != 0.0,
        "filters.enable_anomaly_filter" => cfg.filters.enable_anomaly_filter = value != 0.0,
        "filters.enable_extension_filter" => cfg.filters.enable_extension_filter = value != 0.0,
        "filters.require_adx_rising" => cfg.filters.require_adx_rising = value != 0.0,
        "filters.adx_rising_saturation" => cfg.filters.adx_rising_saturation = value,
        "filters.require_volume_confirmation" => {
            cfg.filters.require_volume_confirmation = value != 0.0
        }
        "filters.use_stoch_rsi_filter" => cfg.filters.use_stoch_rsi_filter = value != 0.0,
        "filters.require_btc_alignment" => cfg.filters.require_btc_alignment = value != 0.0,
        "filters.require_macro_alignment" => cfg.filters.require_macro_alignment = value != 0.0,

        // === Entry toggles ===
        "thresholds.entry.enable_pullback_entries" => {
            cfg.thresholds.entry.enable_pullback_entries = value != 0.0
        }
        "thresholds.entry.enable_slow_drift_entries" => {
            cfg.thresholds.entry.enable_slow_drift_entries = value != 0.0
        }
        "thresholds.entry.ave_enabled" => cfg.thresholds.entry.ave_enabled = value != 0.0,
        "thresholds.entry.pullback_require_macd_sign" => {
            cfg.thresholds.entry.pullback_require_macd_sign = value != 0.0
        }
        "thresholds.entry.slow_drift_require_macd_sign" => {
            cfg.thresholds.entry.slow_drift_require_macd_sign = value != 0.0
        }

        // === Market regime toggles ===
        "market_regime.enable_regime_filter" => {
            cfg.market_regime.enable_regime_filter = value != 0.0
        }
        "market_regime.enable_auto_reverse" => cfg.market_regime.enable_auto_reverse = value != 0.0,

        // === Indicators ===
        "indicators.ema_slow_window" => cfg.indicators.ema_slow_window = value as usize,
        "indicators.ema_fast_window" => cfg.indicators.ema_fast_window = value as usize,
        "indicators.ema_macro_window" => cfg.indicators.ema_macro_window = value as usize,
        "indicators.adx_window" => cfg.indicators.adx_window = value as usize,
        "indicators.bb_window" => cfg.indicators.bb_window = value as usize,
        "indicators.bb_width_avg_window" => cfg.indicators.bb_width_avg_window = value as usize,
        "indicators.atr_window" => cfg.indicators.atr_window = value as usize,
        "indicators.rsi_window" => cfg.indicators.rsi_window = value as usize,
        "indicators.vol_sma_window" => cfg.indicators.vol_sma_window = value as usize,
        "indicators.vol_trend_window" => cfg.indicators.vol_trend_window = value as usize,
        "indicators.stoch_rsi_window" => cfg.indicators.stoch_rsi_window = value as usize,
        "indicators.stoch_rsi_smooth1" => cfg.indicators.stoch_rsi_smooth1 = value as usize,
        "indicators.stoch_rsi_smooth2" => cfg.indicators.stoch_rsi_smooth2 = value as usize,
        // Backward-compatible alias for legacy sweep configs.
        "indicators.ave_avg_atr_window" => set_ave_avg_atr_window(cfg, value as usize),

        // === Market regime ===
        "market_regime.breadth_block_short_above" => {
            cfg.market_regime.breadth_block_short_above = value
        }
        "market_regime.breadth_block_long_below" => {
            cfg.market_regime.breadth_block_long_below = value
        }
        "market_regime.auto_reverse_breadth_low" => {
            cfg.market_regime.auto_reverse_breadth_low = value
        }
        "market_regime.auto_reverse_breadth_high" => {
            cfg.market_regime.auto_reverse_breadth_high = value
        }

        _ => eprintln!("[sweep] Unknown override path: {path}"),
    }
}

// ---------------------------------------------------------------------------
// Override verification
// ---------------------------------------------------------------------------

/// Status of a single override verification check.
#[derive(Debug, Clone, Serialize)]
pub enum OverrideStatus {
    Applied,
    FailedNotFound,
    FailedUnchanged,
}

/// Verification result for a single override path.
#[derive(Debug, Clone, Serialize)]
pub struct OverrideVerification {
    pub path: String,
    pub requested: f64,
    pub before: Option<f64>,
    pub after: Option<f64>,
    pub status: OverrideStatus,
}

/// Read a single f64 config value by dot-separated path (inverse of `apply_one`).
///
/// Returns `None` for unknown paths. Boolean fields return 1.0/0.0.
/// Enum fields (Confidence, MacdMode) return their integer encoding.
fn read_one(cfg: &StrategyConfig, path: &str) -> Option<f64> {
    Some(match path {
        // === Trade config ===
        "trade.sl_atr_mult" => cfg.trade.sl_atr_mult,
        "trade.tp_atr_mult" => cfg.trade.tp_atr_mult,
        "trade.trailing_start_atr" => cfg.trade.trailing_start_atr,
        "trade.trailing_distance_atr" => cfg.trade.trailing_distance_atr,
        "trade.allocation_pct" => cfg.trade.allocation_pct,
        "trade.leverage" => cfg.trade.leverage,
        "trade.max_open_positions" => cfg.trade.max_open_positions as f64,
        "trade.min_atr_pct" => cfg.trade.min_atr_pct,
        "trade.slippage_bps" => cfg.trade.slippage_bps,
        "trade.min_notional_usd" => cfg.trade.min_notional_usd,
        "trade.use_bbo_for_fills" => {
            if cfg.trade.use_bbo_for_fills {
                1.0
            } else {
                0.0
            }
        }
        "trade.bump_to_min_notional" => {
            if cfg.trade.bump_to_min_notional {
                1.0
            } else {
                0.0
            }
        }
        "trade.max_total_margin_pct" => cfg.trade.max_total_margin_pct,
        "trade.reentry_cooldown_minutes" => cfg.trade.reentry_cooldown_minutes as f64,
        "trade.reentry_cooldown_min_mins" => cfg.trade.reentry_cooldown_min_mins as f64,
        "trade.reentry_cooldown_max_mins" => cfg.trade.reentry_cooldown_max_mins as f64,
        "trade.breakeven_start_atr" => cfg.trade.breakeven_start_atr,
        "trade.breakeven_buffer_atr" => cfg.trade.breakeven_buffer_atr,
        "trade.confidence_mult_low" => cfg.trade.confidence_mult_low,
        "trade.confidence_mult_medium" => cfg.trade.confidence_mult_medium,
        "trade.confidence_mult_high" => cfg.trade.confidence_mult_high,
        "trade.tsme_min_profit_atr" => cfg.trade.tsme_min_profit_atr,
        "trade.rsi_exit_profit_atr_switch" => cfg.trade.rsi_exit_profit_atr_switch,
        "trade.rsi_exit_ub_lo_profit" => cfg.trade.rsi_exit_ub_lo_profit,
        "trade.rsi_exit_ub_hi_profit" => cfg.trade.rsi_exit_ub_hi_profit,
        "trade.rsi_exit_lb_lo_profit" => cfg.trade.rsi_exit_lb_lo_profit,
        "trade.rsi_exit_lb_hi_profit" => cfg.trade.rsi_exit_lb_hi_profit,
        "trade.rsi_exit_ub_lo_profit_low_conf" => cfg.trade.rsi_exit_ub_lo_profit_low_conf,
        "trade.rsi_exit_ub_hi_profit_low_conf" => cfg.trade.rsi_exit_ub_hi_profit_low_conf,
        "trade.rsi_exit_lb_lo_profit_low_conf" => cfg.trade.rsi_exit_lb_lo_profit_low_conf,
        "trade.rsi_exit_lb_hi_profit_low_conf" => cfg.trade.rsi_exit_lb_hi_profit_low_conf,
        "trade.tp_partial_pct" => cfg.trade.tp_partial_pct,
        "trade.tp_partial_atr_mult" => cfg.trade.tp_partial_atr_mult,
        "trade.tp_partial_min_notional_usd" => cfg.trade.tp_partial_min_notional_usd,
        "trade.add_min_profit_atr" => cfg.trade.add_min_profit_atr,
        "trade.add_fraction_of_base_margin" => cfg.trade.add_fraction_of_base_margin,
        "trade.max_adds_per_symbol" => cfg.trade.max_adds_per_symbol as f64,
        "trade.add_cooldown_minutes" => cfg.trade.add_cooldown_minutes as f64,
        "trade.leverage_low" => cfg.trade.leverage_low,
        "trade.leverage_medium" => cfg.trade.leverage_medium,
        "trade.leverage_high" => cfg.trade.leverage_high,
        "trade.adx_sizing_min_mult" => cfg.trade.adx_sizing_min_mult,
        "trade.adx_sizing_full_adx" => cfg.trade.adx_sizing_full_adx,
        "trade.vol_baseline_pct" => cfg.trade.vol_baseline_pct,
        "trade.vol_scalar_min" => cfg.trade.vol_scalar_min,
        "trade.vol_scalar_max" => cfg.trade.vol_scalar_max,
        "trade.entry_cooldown_s" => cfg.trade.entry_cooldown_s as f64,
        "trade.exit_cooldown_s" => cfg.trade.exit_cooldown_s as f64,
        "trade.max_entry_orders_per_loop" => cfg.trade.max_entry_orders_per_loop as f64,
        "trade.glitch_price_dev_pct" => cfg.trade.glitch_price_dev_pct,
        "trade.glitch_atr_mult" => cfg.trade.glitch_atr_mult,
        "trade.reef_long_rsi_block_gt" => cfg.trade.reef_long_rsi_block_gt,
        "trade.reef_short_rsi_block_lt" => cfg.trade.reef_short_rsi_block_lt,
        "trade.reef_adx_threshold" => cfg.trade.reef_adx_threshold,
        "trade.reef_long_rsi_extreme_gt" => cfg.trade.reef_long_rsi_extreme_gt,
        "trade.reef_short_rsi_extreme_lt" => cfg.trade.reef_short_rsi_extreme_lt,
        "trade.trailing_start_atr_low_conf" => cfg.trade.trailing_start_atr_low_conf,
        "trade.trailing_distance_atr_low_conf" => cfg.trade.trailing_distance_atr_low_conf,
        "trade.smart_exit_adx_exhaustion_lt" => cfg.trade.smart_exit_adx_exhaustion_lt,
        "trade.smart_exit_adx_exhaustion_lt_low_conf" => {
            cfg.trade.smart_exit_adx_exhaustion_lt_low_conf
        }

        // === Confidence enums (0=low, 1=medium, 2=high) ===
        "trade.entry_min_confidence" => match cfg.trade.entry_min_confidence {
            Confidence::Low => 0.0,
            Confidence::Medium => 1.0,
            Confidence::High => 2.0,
        },
        "trade.add_min_confidence" => match cfg.trade.add_min_confidence {
            Confidence::Low => 0.0,
            Confidence::Medium => 1.0,
            Confidence::High => 2.0,
        },
        "thresholds.entry.pullback_confidence" => match cfg.thresholds.entry.pullback_confidence {
            Confidence::Low => 0.0,
            Confidence::Medium => 1.0,
            Confidence::High => 2.0,
        },

        // === Thresholds — entry ===
        "thresholds.entry.min_adx" => cfg.thresholds.entry.min_adx,
        "thresholds.entry.high_conf_volume_mult" => cfg.thresholds.entry.high_conf_volume_mult,
        "thresholds.entry.btc_adx_override" => cfg.thresholds.entry.btc_adx_override,
        "thresholds.entry.max_dist_ema_fast" => cfg.thresholds.entry.max_dist_ema_fast,
        "thresholds.entry.ave_atr_ratio_gt" => cfg.thresholds.entry.ave_atr_ratio_gt,
        "thresholds.entry.ave_adx_mult" => cfg.thresholds.entry.ave_adx_mult,
        "thresholds.entry.ave_avg_atr_window" => cfg.thresholds.entry.ave_avg_atr_window as f64,
        "thresholds.entry.pullback_min_adx" => cfg.thresholds.entry.pullback_min_adx,
        "thresholds.entry.pullback_rsi_long_min" => cfg.thresholds.entry.pullback_rsi_long_min,
        "thresholds.entry.pullback_rsi_short_max" => cfg.thresholds.entry.pullback_rsi_short_max,
        "thresholds.entry.slow_drift_slope_window" => {
            cfg.thresholds.entry.slow_drift_slope_window as f64
        }
        "thresholds.entry.slow_drift_min_slope_pct" => {
            cfg.thresholds.entry.slow_drift_min_slope_pct
        }
        "thresholds.entry.slow_drift_min_adx" => cfg.thresholds.entry.slow_drift_min_adx,
        "thresholds.entry.slow_drift_rsi_long_min" => cfg.thresholds.entry.slow_drift_rsi_long_min,
        "thresholds.entry.slow_drift_rsi_short_max" => {
            cfg.thresholds.entry.slow_drift_rsi_short_max
        }
        "thresholds.entry.macd_hist_entry_mode" => {
            match cfg.thresholds.entry.macd_hist_entry_mode {
                MacdMode::Accel => 0.0,
                MacdMode::Sign => 1.0,
                MacdMode::None => 2.0,
            }
        }

        // === Thresholds — ranging ===
        "thresholds.ranging.min_signals" => cfg.thresholds.ranging.min_signals as f64,
        "thresholds.ranging.adx_below" => cfg.thresholds.ranging.adx_below,
        "thresholds.ranging.bb_width_ratio_below" => cfg.thresholds.ranging.bb_width_ratio_below,
        "thresholds.ranging.rsi_low" => cfg.thresholds.ranging.rsi_low,
        "thresholds.ranging.rsi_high" => cfg.thresholds.ranging.rsi_high,

        // === Thresholds — anomaly ===
        "thresholds.anomaly.price_change_pct_gt" => cfg.thresholds.anomaly.price_change_pct_gt,
        "thresholds.anomaly.ema_fast_dev_pct_gt" => cfg.thresholds.anomaly.ema_fast_dev_pct_gt,

        // === Thresholds — tp_and_momentum ===
        "thresholds.tp_and_momentum.adx_strong_gt" => cfg.thresholds.tp_and_momentum.adx_strong_gt,
        "thresholds.tp_and_momentum.adx_weak_lt" => cfg.thresholds.tp_and_momentum.adx_weak_lt,
        "thresholds.tp_and_momentum.tp_mult_strong" => {
            cfg.thresholds.tp_and_momentum.tp_mult_strong
        }
        "thresholds.tp_and_momentum.tp_mult_weak" => cfg.thresholds.tp_and_momentum.tp_mult_weak,
        "thresholds.tp_and_momentum.rsi_long_strong" => {
            cfg.thresholds.tp_and_momentum.rsi_long_strong
        }
        "thresholds.tp_and_momentum.rsi_long_weak" => cfg.thresholds.tp_and_momentum.rsi_long_weak,
        "thresholds.tp_and_momentum.rsi_short_strong" => {
            cfg.thresholds.tp_and_momentum.rsi_short_strong
        }
        "thresholds.tp_and_momentum.rsi_short_weak" => {
            cfg.thresholds.tp_and_momentum.rsi_short_weak
        }

        // === Thresholds — stoch_rsi ===
        "thresholds.stoch_rsi.block_long_if_k_gt" => cfg.thresholds.stoch_rsi.block_long_if_k_gt,
        "thresholds.stoch_rsi.block_short_if_k_lt" => cfg.thresholds.stoch_rsi.block_short_if_k_lt,

        // === Boolean toggles ===
        "trade.enable_dynamic_sizing" => {
            if cfg.trade.enable_dynamic_sizing {
                1.0
            } else {
                0.0
            }
        }
        "trade.enable_pyramiding" => {
            if cfg.trade.enable_pyramiding {
                1.0
            } else {
                0.0
            }
        }
        "trade.enable_partial_tp" => {
            if cfg.trade.enable_partial_tp {
                1.0
            } else {
                0.0
            }
        }
        "trade.enable_ssf_filter" => {
            if cfg.trade.enable_ssf_filter {
                1.0
            } else {
                0.0
            }
        }
        "trade.enable_reef_filter" => {
            if cfg.trade.enable_reef_filter {
                1.0
            } else {
                0.0
            }
        }
        "trade.enable_breakeven_stop" => {
            if cfg.trade.enable_breakeven_stop {
                1.0
            } else {
                0.0
            }
        }
        "trade.enable_rsi_overextension_exit" => {
            if cfg.trade.enable_rsi_overextension_exit {
                1.0
            } else {
                0.0
            }
        }
        "trade.enable_vol_buffered_trailing" => {
            if cfg.trade.enable_vol_buffered_trailing {
                1.0
            } else {
                0.0
            }
        }
        "trade.tsme_require_adx_slope_negative" => {
            if cfg.trade.tsme_require_adx_slope_negative {
                1.0
            } else {
                0.0
            }
        }
        "trade.reverse_entry_signal" => {
            if cfg.trade.reverse_entry_signal {
                1.0
            } else {
                0.0
            }
        }
        "trade.block_exits_on_extreme_dev" => {
            if cfg.trade.block_exits_on_extreme_dev {
                1.0
            } else {
                0.0
            }
        }
        "filters.vol_confirm_include_prev" => {
            if cfg.filters.vol_confirm_include_prev {
                1.0
            } else {
                0.0
            }
        }

        // === Filters ===
        "filters.enable_ranging_filter" => {
            if cfg.filters.enable_ranging_filter {
                1.0
            } else {
                0.0
            }
        }
        "filters.enable_anomaly_filter" => {
            if cfg.filters.enable_anomaly_filter {
                1.0
            } else {
                0.0
            }
        }
        "filters.enable_extension_filter" => {
            if cfg.filters.enable_extension_filter {
                1.0
            } else {
                0.0
            }
        }
        "filters.require_adx_rising" => {
            if cfg.filters.require_adx_rising {
                1.0
            } else {
                0.0
            }
        }
        "filters.adx_rising_saturation" => cfg.filters.adx_rising_saturation,
        "filters.require_volume_confirmation" => {
            if cfg.filters.require_volume_confirmation {
                1.0
            } else {
                0.0
            }
        }
        "filters.use_stoch_rsi_filter" => {
            if cfg.filters.use_stoch_rsi_filter {
                1.0
            } else {
                0.0
            }
        }
        "filters.require_btc_alignment" => {
            if cfg.filters.require_btc_alignment {
                1.0
            } else {
                0.0
            }
        }
        "filters.require_macro_alignment" => {
            if cfg.filters.require_macro_alignment {
                1.0
            } else {
                0.0
            }
        }

        // === Entry toggles ===
        "thresholds.entry.enable_pullback_entries" => {
            if cfg.thresholds.entry.enable_pullback_entries {
                1.0
            } else {
                0.0
            }
        }
        "thresholds.entry.enable_slow_drift_entries" => {
            if cfg.thresholds.entry.enable_slow_drift_entries {
                1.0
            } else {
                0.0
            }
        }
        "thresholds.entry.ave_enabled" => {
            if cfg.thresholds.entry.ave_enabled {
                1.0
            } else {
                0.0
            }
        }
        "thresholds.entry.pullback_require_macd_sign" => {
            if cfg.thresholds.entry.pullback_require_macd_sign {
                1.0
            } else {
                0.0
            }
        }
        "thresholds.entry.slow_drift_require_macd_sign" => {
            if cfg.thresholds.entry.slow_drift_require_macd_sign {
                1.0
            } else {
                0.0
            }
        }

        // === Market regime toggles ===
        "market_regime.enable_regime_filter" => {
            if cfg.market_regime.enable_regime_filter {
                1.0
            } else {
                0.0
            }
        }
        "market_regime.enable_auto_reverse" => {
            if cfg.market_regime.enable_auto_reverse {
                1.0
            } else {
                0.0
            }
        }

        // === Indicators ===
        "indicators.ema_slow_window" => cfg.indicators.ema_slow_window as f64,
        "indicators.ema_fast_window" => cfg.indicators.ema_fast_window as f64,
        "indicators.ema_macro_window" => cfg.indicators.ema_macro_window as f64,
        "indicators.adx_window" => cfg.indicators.adx_window as f64,
        "indicators.bb_window" => cfg.indicators.bb_window as f64,
        "indicators.bb_width_avg_window" => cfg.indicators.bb_width_avg_window as f64,
        "indicators.atr_window" => cfg.indicators.atr_window as f64,
        "indicators.rsi_window" => cfg.indicators.rsi_window as f64,
        "indicators.vol_sma_window" => cfg.indicators.vol_sma_window as f64,
        "indicators.vol_trend_window" => cfg.indicators.vol_trend_window as f64,
        "indicators.stoch_rsi_window" => cfg.indicators.stoch_rsi_window as f64,
        "indicators.stoch_rsi_smooth1" => cfg.indicators.stoch_rsi_smooth1 as f64,
        "indicators.stoch_rsi_smooth2" => cfg.indicators.stoch_rsi_smooth2 as f64,
        "indicators.ave_avg_atr_window" => cfg.indicators.ave_avg_atr_window as f64,

        // === Market regime ===
        "market_regime.breadth_block_short_above" => cfg.market_regime.breadth_block_short_above,
        "market_regime.breadth_block_long_below" => cfg.market_regime.breadth_block_long_below,
        "market_regime.auto_reverse_breadth_low" => cfg.market_regime.auto_reverse_breadth_low,
        "market_regime.auto_reverse_breadth_high" => cfg.market_regime.auto_reverse_breadth_high,

        _ => return None,
    })
}

/// Verify that each override path in the sweep spec actually takes effect on the config.
///
/// For each unique (path, value) pair:
/// 1. Reads the field BEFORE applying
/// 2. Applies the override
/// 3. Reads the field AFTER applying
/// 4. Reports whether the override was applied, not found, or unchanged
pub fn verify_overrides(
    base_cfg: &StrategyConfig,
    overrides: &[(String, f64)],
) -> Vec<OverrideVerification> {
    overrides
        .iter()
        .map(|(path, value)| {
            let before = read_one(base_cfg, path);

            if before.is_none() {
                return OverrideVerification {
                    path: path.clone(),
                    requested: *value,
                    before: None,
                    after: None,
                    status: OverrideStatus::FailedNotFound,
                };
            }

            let mut test_cfg = base_cfg.clone();
            apply_one(&mut test_cfg, path, *value);
            let after = read_one(&test_cfg, path);

            let status = match (&before, &after) {
                (Some(b), Some(a)) if (a - b).abs() < 1e-12 && (a - value).abs() > 1e-12 => {
                    OverrideStatus::FailedUnchanged
                }
                _ => OverrideStatus::Applied,
            };

            OverrideVerification {
                path: path.clone(),
                requested: *value,
                before,
                after,
                status,
            }
        })
        .collect()
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/// Run a parameter sweep: generate all config combinations, run each in parallel.
///
/// Results are sorted by `total_pnl` descending (best first).
///
/// `from_ts`/`to_ts` are forwarded to the simulation engine to restrict trading to a
/// specific time window.
pub fn run_sweep(
    base_cfg: &StrategyConfig,
    spec: &SweepSpec,
    candles: &CandleData,
    exit_candles: Option<&CandleData>,
    entry_candles: Option<&CandleData>,
    funding_rates: Option<&FundingRateData>,
    from_ts: Option<i64>,
    to_ts: Option<i64>,
) -> Vec<SweepResult> {
    // Pre-resolve gates whose gate axis is not being swept.
    // If the gate axis is fixed (from base config), we can simplify:
    //   - Gate permanently satisfied → remove the gate (always expand)
    //   - Gate permanently unsatisfied → freeze at first value
    let swept_paths: std::collections::HashSet<&str> =
        spec.axes.iter().map(|a| a.path.as_str()).collect();

    let resolved_axes: Vec<SweepAxis> = spec
        .axes
        .iter()
        .map(|axis| {
            if let Some(gate) = &axis.gate {
                if !swept_paths.contains(gate.path.as_str()) {
                    if let Some(base_val) = read_one(base_cfg, &gate.path) {
                        if (base_val - gate.eq).abs() < 1e-9 {
                            // Gate permanently satisfied — expand all values.
                            return SweepAxis {
                                path: axis.path.clone(),
                                values: axis.values.clone(),
                                gate: None,
                            };
                        } else {
                            // Gate permanently unsatisfied — freeze.
                            return SweepAxis {
                                path: axis.path.clone(),
                                values: vec![axis.values[0]],
                                gate: None,
                            };
                        }
                    }
                }
            }
            axis.clone()
        })
        .collect();

    let gated = resolved_axes.iter().filter(|a| a.gate.is_some()).count();
    let combos = generate_combinations(&resolved_axes);
    let total = combos.len();
    eprintln!(
        "[sweep] Generated {total} config combinations across {} axes ({gated} gated)",
        resolved_axes.len()
    );

    let candles = Arc::new(candles.clone());
    let exit_candles_arc = exit_candles.map(|ec| Arc::new(ec.clone()));
    let entry_candles_arc = entry_candles.map(|ec| Arc::new(ec.clone()));
    let funding_rates_arc = funding_rates.map(|fr| Arc::new(fr.clone()));
    let initial_balance = spec.initial_balance;
    let lookback = spec.lookback;

    let mut results: Vec<SweepResult> = combos
        .par_iter()
        .enumerate()
        .map(|(i, overrides)| {
            let cfg = apply_overrides(base_cfg, overrides);
            let config_id = format!("sweep_{:04}", i);

            let sim = engine::run_simulation(engine::RunSimulationInput {
                candles: &candles,
                cfg: &cfg,
                initial_balance,
                lookback,
                exit_candles: exit_candles_arc.as_deref(),
                entry_candles: entry_candles_arc.as_deref(),
                funding_rates: funding_rates_arc.as_deref(),
                init_state: None, // sweeps always start clean (no init-state)
                from_ts,
                to_ts,
            });

            let rpt = report::build_report(report::BuildReportInput {
                trades: &sim.trades,
                signals: &sim.signals,
                equity_curve: &sim.equity_curve,
                gate_stats: &sim.gate_stats,
                initial_balance,
                final_balance: sim.final_balance,
                config_id: &config_id,
                include_trades: false, // don't embed per-trade detail in sweep
                include_equity_curve: false, // don't embed equity curve in sweep
            });

            SweepResult {
                config_id,
                report: rpt,
                overrides: overrides.clone(),
            }
        })
        .collect();

    // Sort by total PnL descending (best first).
    results.sort_by(|a, b| {
        b.report
            .total_pnl
            .partial_cmp(&a.report.total_pnl)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    results
}

/// Load a sweep specification from a YAML file.
pub fn load_sweep_spec(path: &str) -> Result<SweepSpec, String> {
    let raw =
        std::fs::read_to_string(path).map_err(|e| format!("Failed to read sweep spec: {e}"))?;
    serde_yaml::from_str(&raw).map_err(|e| format!("Failed to parse sweep spec: {e}"))
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_combinations_empty() {
        let combos = generate_combinations(&[]);
        assert_eq!(combos.len(), 1);
        assert!(combos[0].is_empty());
    }

    #[test]
    fn test_generate_combinations_single_axis() {
        let axes = vec![SweepAxis {
            path: "trade.sl_atr_mult".to_string(),
            values: vec![1.0, 2.0, 3.0],
            gate: None,
        }];
        let combos = generate_combinations(&axes);
        assert_eq!(combos.len(), 3);
        assert!((combos[0][0].1 - 1.0).abs() < 1e-9);
        assert!((combos[1][0].1 - 2.0).abs() < 1e-9);
        assert!((combos[2][0].1 - 3.0).abs() < 1e-9);
    }

    #[test]
    fn test_generate_combinations_two_axes() {
        let axes = vec![
            SweepAxis {
                path: "trade.sl_atr_mult".to_string(),
                values: vec![1.0, 2.0],
                gate: None,
            },
            SweepAxis {
                path: "trade.tp_atr_mult".to_string(),
                values: vec![3.0, 4.0, 5.0],
                gate: None,
            },
        ];
        let combos = generate_combinations(&axes);
        // 2 x 3 = 6
        assert_eq!(combos.len(), 6);
        // Each combo has 2 entries
        for combo in &combos {
            assert_eq!(combo.len(), 2);
        }
    }

    #[test]
    fn test_apply_overrides_trade_fields() {
        let base = StrategyConfig::default();
        let overrides = vec![
            ("trade.sl_atr_mult".to_string(), 1.5),
            ("trade.tp_atr_mult".to_string(), 6.0),
            ("trade.leverage".to_string(), 5.0),
            ("trade.max_open_positions".to_string(), 10.0),
        ];
        let cfg = apply_overrides(&base, &overrides);
        assert!((cfg.trade.sl_atr_mult - 1.5).abs() < 1e-9);
        assert!((cfg.trade.tp_atr_mult - 6.0).abs() < 1e-9);
        assert!((cfg.trade.leverage - 5.0).abs() < 1e-9);
        assert_eq!(cfg.trade.max_open_positions, 10);
    }

    #[test]
    fn test_apply_overrides_thresholds() {
        let base = StrategyConfig::default();
        let overrides = vec![
            ("thresholds.entry.min_adx".to_string(), 18.0),
            (
                "thresholds.entry.slow_drift_min_slope_pct".to_string(),
                0.001,
            ),
            ("thresholds.ranging.adx_below".to_string(), 25.0),
        ];
        let cfg = apply_overrides(&base, &overrides);
        assert!((cfg.thresholds.entry.min_adx - 18.0).abs() < 1e-9);
        assert!((cfg.thresholds.entry.slow_drift_min_slope_pct - 0.001).abs() < 1e-9);
        assert!((cfg.thresholds.ranging.adx_below - 25.0).abs() < 1e-9);
    }

    #[test]
    fn test_apply_overrides_filters() {
        let base = StrategyConfig::default();
        let overrides = vec![("filters.adx_rising_saturation".to_string(), 35.0)];
        let cfg = apply_overrides(&base, &overrides);
        assert!((cfg.filters.adx_rising_saturation - 35.0).abs() < 1e-9);
    }

    #[test]
    fn test_apply_overrides_indicators() {
        let base = StrategyConfig::default();
        let overrides = vec![
            ("indicators.ema_slow_window".to_string(), 100.0),
            ("indicators.ema_fast_window".to_string(), 30.0),
        ];
        let cfg = apply_overrides(&base, &overrides);
        assert_eq!(cfg.indicators.ema_slow_window, 100);
        assert_eq!(cfg.indicators.ema_fast_window, 30);
    }

    #[test]
    fn test_apply_overrides_ave_window_legacy_alias_path() {
        let mut base = StrategyConfig::default();
        base.indicators.ave_avg_atr_window = 13;
        base.thresholds.entry.ave_avg_atr_window = 21;

        let overrides = vec![("indicators.ave_avg_atr_window".to_string(), 77.0)];
        let cfg = apply_overrides(&base, &overrides);

        assert_eq!(cfg.indicators.ave_avg_atr_window, 77);
        assert_eq!(cfg.thresholds.entry.ave_avg_atr_window, 77);
    }

    #[test]
    fn test_apply_overrides_ave_window_threshold_path_keeps_alias_sync() {
        let mut base = StrategyConfig::default();
        base.indicators.ave_avg_atr_window = 9;
        base.thresholds.entry.ave_avg_atr_window = 15;

        let overrides = vec![("thresholds.entry.ave_avg_atr_window".to_string(), 31.0)];
        let cfg = apply_overrides(&base, &overrides);

        assert_eq!(cfg.thresholds.entry.ave_avg_atr_window, 31);
        assert_eq!(cfg.indicators.ave_avg_atr_window, 31);
    }

    #[test]
    fn test_apply_overrides_preserves_untouched() {
        let base = StrategyConfig::default();
        let overrides = vec![("trade.leverage".to_string(), 10.0)];
        let cfg = apply_overrides(&base, &overrides);
        // Changed
        assert!((cfg.trade.leverage - 10.0).abs() < 1e-9);
        // Preserved
        assert!((cfg.trade.allocation_pct - base.trade.allocation_pct).abs() < 1e-9);
        assert!((cfg.trade.sl_atr_mult - base.trade.sl_atr_mult).abs() < 1e-9);
        assert_eq!(
            cfg.indicators.ema_slow_window,
            base.indicators.ema_slow_window
        );
    }

    #[test]
    fn test_sweep_spec_deserialization() {
        let yaml = r#"
axes:
  - path: trade.sl_atr_mult
    values: [1.0, 1.5, 2.0]
  - path: trade.tp_atr_mult
    values: [3.0, 4.0]
initial_balance: 5000.0
lookback: 100
"#;
        let spec: SweepSpec = serde_yaml::from_str(yaml).unwrap();
        assert_eq!(spec.axes.len(), 2);
        assert!((spec.initial_balance - 5000.0).abs() < 1e-9);
        assert_eq!(spec.lookback, 100);
        assert_eq!(spec.axes[0].values.len(), 3);
        assert_eq!(spec.axes[1].values.len(), 2);
    }

    #[test]
    fn test_sweep_spec_defaults() {
        let yaml = r#"
axes:
  - path: trade.leverage
    values: [2.0]
"#;
        let spec: SweepSpec = serde_yaml::from_str(yaml).unwrap();
        assert!((spec.initial_balance - 10000.0).abs() < 1e-9);
        assert_eq!(spec.lookback, 200);
    }

    #[test]
    fn test_verify_overrides_valid_paths() {
        let base = StrategyConfig::default();
        let overrides = vec![
            ("trade.sl_atr_mult".to_string(), 99.0),
            ("trade.leverage".to_string(), 3.0),
            ("indicators.ema_slow_window".to_string(), 50.0),
        ];
        let results = verify_overrides(&base, &overrides);
        assert_eq!(results.len(), 3);
        for v in &results {
            assert!(
                matches!(v.status, OverrideStatus::Applied),
                "Expected Applied for {}, got {:?}",
                v.path,
                v.status,
            );
            assert!(v.before.is_some());
            assert!(v.after.is_some());
        }
        // Verify the after values match what we requested
        assert!((results[0].after.unwrap() - 99.0).abs() < 1e-9);
        assert!((results[1].after.unwrap() - 3.0).abs() < 1e-9);
        assert!((results[2].after.unwrap() - 50.0).abs() < 1e-9);
    }

    #[test]
    fn test_verify_overrides_unknown_path() {
        let base = StrategyConfig::default();
        let overrides = vec![("trade.nonexistent_field".to_string(), 42.0)];
        let results = verify_overrides(&base, &overrides);
        assert_eq!(results.len(), 1);
        assert!(matches!(results[0].status, OverrideStatus::FailedNotFound));
        assert!(results[0].before.is_none());
        assert!(results[0].after.is_none());
    }

    #[test]
    fn test_verify_overrides_mixed_valid_and_invalid() {
        let base = StrategyConfig::default();
        let overrides = vec![
            ("trade.sl_atr_mult".to_string(), 2.5),
            ("bogus.path".to_string(), 1.0),
            ("filters.adx_rising_saturation".to_string(), 40.0),
        ];
        let results = verify_overrides(&base, &overrides);
        assert_eq!(results.len(), 3);
        assert!(matches!(results[0].status, OverrideStatus::Applied));
        assert!(matches!(results[1].status, OverrideStatus::FailedNotFound));
        assert!(matches!(results[2].status, OverrideStatus::Applied));
    }

    #[test]
    fn test_read_one_round_trips_with_apply_one() {
        let mut cfg = StrategyConfig::default();
        apply_one(&mut cfg, "trade.leverage", 7.0);
        assert!((read_one(&cfg, "trade.leverage").unwrap() - 7.0).abs() < 1e-9);

        apply_one(&mut cfg, "trade.enable_pyramiding", 1.0);
        assert!((read_one(&cfg, "trade.enable_pyramiding").unwrap() - 1.0).abs() < 1e-9);

        apply_one(&mut cfg, "indicators.atr_window", 21.0);
        assert!((read_one(&cfg, "indicators.atr_window").unwrap() - 21.0).abs() < 1e-9);

        // Unknown path returns None
        assert!(read_one(&cfg, "does.not.exist").is_none());
    }

    #[test]
    fn test_generate_combinations_gate_satisfied() {
        // When gate is satisfied (enable=1), gated axes expand normally.
        let axes = vec![
            SweepAxis {
                path: "trade.enable_dynamic_sizing".to_string(),
                values: vec![0.0, 1.0],
                gate: None,
            },
            SweepAxis {
                path: "trade.leverage".to_string(),
                values: vec![1.0, 2.0, 3.0],
                gate: Some(AxisGate {
                    path: "trade.enable_dynamic_sizing".to_string(),
                    eq: 0.0,
                }),
            },
            SweepAxis {
                path: "trade.leverage_low".to_string(),
                values: vec![1.0, 2.0],
                gate: Some(AxisGate {
                    path: "trade.enable_dynamic_sizing".to_string(),
                    eq: 1.0,
                }),
            },
            SweepAxis {
                path: "trade.leverage_high".to_string(),
                values: vec![5.0, 7.0],
                gate: Some(AxisGate {
                    path: "trade.enable_dynamic_sizing".to_string(),
                    eq: 1.0,
                }),
            },
        ];
        let combos = generate_combinations(&axes);
        // enable=0: leverage expands (3), low freezes (1), high freezes (1) → 3
        // enable=1: leverage freezes (1), low expands (2), high expands (2) → 4
        // Total: 3 + 4 = 7
        assert_eq!(combos.len(), 7);
    }

    #[test]
    fn test_generate_combinations_no_gate_full_cartesian() {
        // Without gates, same axes would produce full cartesian product.
        let axes = vec![
            SweepAxis {
                path: "trade.enable_dynamic_sizing".to_string(),
                values: vec![0.0, 1.0],
                gate: None,
            },
            SweepAxis {
                path: "trade.leverage".to_string(),
                values: vec![1.0, 2.0, 3.0],
                gate: None,
            },
            SweepAxis {
                path: "trade.leverage_low".to_string(),
                values: vec![1.0, 2.0],
                gate: None,
            },
            SweepAxis {
                path: "trade.leverage_high".to_string(),
                values: vec![5.0, 7.0],
                gate: None,
            },
        ];
        let combos = generate_combinations(&axes);
        // Full cartesian: 2 × 3 × 2 × 2 = 24
        assert_eq!(combos.len(), 24);
    }

    #[test]
    fn test_gate_deserialization() {
        let yaml = r#"
axes:
  - path: trade.enable_dynamic_sizing
    values: [0, 1]
  - path: trade.leverage_low
    values: [1, 2, 3]
    gate:
      path: trade.enable_dynamic_sizing
      eq: 1
initial_balance: 10000.0
lookback: 200
"#;
        let spec: SweepSpec = serde_yaml::from_str(yaml).unwrap();
        assert_eq!(spec.axes.len(), 2);
        assert!(spec.axes[0].gate.is_none());
        let gate = spec.axes[1].gate.as_ref().unwrap();
        assert_eq!(gate.path, "trade.enable_dynamic_sizing");
        assert!((gate.eq - 1.0).abs() < 1e-9);
    }

    #[test]
    fn test_gate_freezes_at_first_value() {
        // When gate is NOT met, the axis should freeze at its first value.
        let axes = vec![
            SweepAxis {
                path: "toggle".to_string(),
                values: vec![0.0],
                gate: None,
            },
            SweepAxis {
                path: "sub_param".to_string(),
                values: vec![10.0, 20.0, 30.0],
                gate: Some(AxisGate {
                    path: "toggle".to_string(),
                    eq: 1.0,
                }),
            },
        ];
        let combos = generate_combinations(&axes);
        // toggle=0 always → sub_param frozen at 10.0 → 1 combo
        assert_eq!(combos.len(), 1);
        let sub_val = combos[0].iter().find(|(p, _)| p == "sub_param").unwrap().1;
        assert!((sub_val - 10.0).abs() < 1e-9);
    }
}
