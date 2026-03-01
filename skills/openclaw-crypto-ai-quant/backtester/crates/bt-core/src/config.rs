//! Strategy configuration for the backtesting simulator.
//!
//! Mirrors the Python `_DEFAULT_STRATEGY_CONFIG` dict from `mei_alpha_v1.py` (lines 226-408).
//! YAML merge hierarchy: defaults <- global <- per-symbol <- live.

use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::path::Path;

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

pub use bt_signals::{Confidence, MacdMode, Signal};

// ---------------------------------------------------------------------------
// Trade config
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct TradeConfig {
    // Core sizing
    pub allocation_pct: f64,
    pub sl_atr_mult: f64,
    pub tp_atr_mult: f64,
    pub leverage: f64,

    // REEF (RSI Entry Extreme Filter)
    pub enable_reef_filter: bool,
    pub reef_long_rsi_block_gt: f64,
    pub reef_short_rsi_block_lt: f64,
    pub reef_adx_threshold: f64,
    pub reef_long_rsi_extreme_gt: f64,
    pub reef_short_rsi_extreme_lt: f64,

    // Dynamic leverage
    pub leverage_low: f64,
    pub leverage_medium: f64,
    pub leverage_high: f64,

    // Execution
    pub slippage_bps: f64,
    pub use_bbo_for_fills: bool,
    pub min_notional_usd: f64,
    pub bump_to_min_notional: bool,
    pub max_total_margin_pct: f64,

    // Dynamic sizing
    pub enable_dynamic_sizing: bool,
    pub confidence_mult_high: f64,
    pub confidence_mult_medium: f64,
    pub confidence_mult_low: f64,
    pub adx_sizing_min_mult: f64,
    pub adx_sizing_full_adx: f64,
    pub vol_baseline_pct: f64,
    pub vol_scalar_min: f64,
    pub vol_scalar_max: f64,

    // Pyramiding
    pub enable_pyramiding: bool,
    pub max_adds_per_symbol: usize,
    pub add_fraction_of_base_margin: f64,
    pub add_cooldown_minutes: usize,
    pub add_min_profit_atr: f64,
    pub add_min_confidence: Confidence,
    pub entry_min_confidence: Confidence,

    // Partial TP
    pub enable_partial_tp: bool,
    pub tp_partial_pct: f64,
    pub tp_partial_min_notional_usd: f64,
    /// ATR multiplier for partial TP level. 0 = use tp_atr_mult (same level as full TP).
    pub tp_partial_atr_mult: f64,
    pub trailing_start_atr: f64,
    pub trailing_distance_atr: f64,

    // SSF + breakeven
    pub enable_ssf_filter: bool,
    pub enable_breakeven_stop: bool,
    pub breakeven_start_atr: f64,
    pub breakeven_buffer_atr: f64,

    // Per-confidence trailing overrides
    pub trailing_start_atr_low_conf: f64,
    pub trailing_distance_atr_low_conf: f64,

    // Smart exit ADX exhaustion
    pub smart_exit_adx_exhaustion_lt: f64,
    pub smart_exit_adx_exhaustion_lt_low_conf: f64,

    // RSI overextension exit
    pub enable_rsi_overextension_exit: bool,
    pub rsi_exit_profit_atr_switch: f64,
    pub rsi_exit_ub_lo_profit: f64,
    pub rsi_exit_ub_hi_profit: f64,
    pub rsi_exit_lb_lo_profit: f64,
    pub rsi_exit_lb_hi_profit: f64,
    pub rsi_exit_ub_lo_profit_low_conf: f64,
    pub rsi_exit_ub_hi_profit_low_conf: f64,
    pub rsi_exit_lb_lo_profit_low_conf: f64,
    pub rsi_exit_lb_hi_profit_low_conf: f64,

    // Reentry cooldown
    pub reentry_cooldown_minutes: usize,
    pub reentry_cooldown_min_mins: usize,
    pub reentry_cooldown_max_mins: usize,

    // Volatility-buffered trailing
    pub enable_vol_buffered_trailing: bool,

    // TSME (Trend Saturation Momentum Exit)
    pub tsme_min_profit_atr: f64,
    pub tsme_require_adx_slope_negative: bool,

    // ATR floor / signal reversal / glitch guard
    pub min_atr_pct: f64,
    pub reverse_entry_signal: bool,
    pub block_exits_on_extreme_dev: bool,
    pub glitch_price_dev_pct: f64,
    pub glitch_atr_mult: f64,

    // Rate limits / capacity
    pub max_open_positions: usize,
    pub entry_cooldown_s: usize,
    pub exit_cooldown_s: usize,
    pub max_entry_orders_per_loop: usize,
}

impl Default for TradeConfig {
    fn default() -> Self {
        Self {
            allocation_pct: 0.03,
            sl_atr_mult: 2.0,
            tp_atr_mult: 4.0,
            leverage: 3.0,

            enable_reef_filter: true,
            reef_long_rsi_block_gt: 70.0,
            reef_short_rsi_block_lt: 30.0,
            reef_adx_threshold: 45.0,
            reef_long_rsi_extreme_gt: 75.0,
            reef_short_rsi_extreme_lt: 25.0,

            leverage_low: 1.0,
            leverage_medium: 3.0,
            leverage_high: 5.0,

            slippage_bps: 10.0,
            use_bbo_for_fills: true,
            min_notional_usd: 10.0,
            bump_to_min_notional: false,
            max_total_margin_pct: 0.60,

            enable_dynamic_sizing: true,
            confidence_mult_high: 1.0,
            confidence_mult_medium: 0.7,
            confidence_mult_low: 0.5,
            adx_sizing_min_mult: 0.6,
            adx_sizing_full_adx: 40.0,
            vol_baseline_pct: 0.01,
            vol_scalar_min: 0.5,
            vol_scalar_max: 1.0,

            enable_pyramiding: true,
            max_adds_per_symbol: 2,
            add_fraction_of_base_margin: 0.5,
            add_cooldown_minutes: 60,
            add_min_profit_atr: 0.5,
            add_min_confidence: Confidence::Medium,
            entry_min_confidence: Confidence::High,

            enable_partial_tp: true,
            tp_partial_pct: 0.5,
            tp_partial_min_notional_usd: 10.0,
            tp_partial_atr_mult: 0.0,
            trailing_start_atr: 1.0,
            trailing_distance_atr: 0.8,

            trailing_start_atr_low_conf: 0.0,
            trailing_distance_atr_low_conf: 0.0,

            smart_exit_adx_exhaustion_lt: 18.0,
            smart_exit_adx_exhaustion_lt_low_conf: 0.0,

            enable_ssf_filter: true,
            enable_breakeven_stop: true,
            breakeven_start_atr: 0.7,
            breakeven_buffer_atr: 0.05,

            enable_rsi_overextension_exit: true,
            rsi_exit_profit_atr_switch: 1.5,
            rsi_exit_ub_lo_profit: 80.0,
            rsi_exit_ub_hi_profit: 70.0,
            rsi_exit_lb_lo_profit: 20.0,
            rsi_exit_lb_hi_profit: 30.0,
            rsi_exit_ub_lo_profit_low_conf: 0.0,
            rsi_exit_ub_hi_profit_low_conf: 0.0,
            rsi_exit_lb_lo_profit_low_conf: 0.0,
            rsi_exit_lb_hi_profit_low_conf: 0.0,

            reentry_cooldown_minutes: 60,
            reentry_cooldown_min_mins: 45,
            reentry_cooldown_max_mins: 180,

            enable_vol_buffered_trailing: true,

            tsme_min_profit_atr: 1.0,
            tsme_require_adx_slope_negative: true,

            min_atr_pct: 0.003,
            reverse_entry_signal: false,
            block_exits_on_extreme_dev: false,
            glitch_price_dev_pct: 0.40,
            glitch_atr_mult: 12.0,

            max_open_positions: 20,
            entry_cooldown_s: 20,
            exit_cooldown_s: 15,
            max_entry_orders_per_loop: 6,
        }
    }
}

// ---------------------------------------------------------------------------
// Indicators config
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct IndicatorsConfig {
    pub ema_slow_window: usize,
    pub ema_fast_window: usize,
    pub ema_macro_window: usize,
    pub adx_window: usize,
    pub bb_window: usize,
    pub bb_width_avg_window: usize,
    pub atr_window: usize,
    pub rsi_window: usize,
    pub vol_sma_window: usize,
    pub vol_trend_window: usize,
    pub stoch_rsi_window: usize,
    pub stoch_rsi_smooth1: usize,
    pub stoch_rsi_smooth2: usize,
    /// AVE (Adaptive Volatility Entry) average ATR lookback.
    /// Duplicated here from thresholds.entry for ergonomic access in IndicatorBank.
    pub ave_avg_atr_window: usize,
}

/// Backward-compatible alias used by `indicators::IndicatorBank::new`.
pub type IndicatorConfig = IndicatorsConfig;

impl Default for IndicatorsConfig {
    fn default() -> Self {
        Self {
            ema_slow_window: 50,
            ema_fast_window: 20,
            ema_macro_window: 200,
            adx_window: 14,
            bb_window: 20,
            bb_width_avg_window: 30,
            atr_window: 14,
            rsi_window: 14,
            vol_sma_window: 20,
            vol_trend_window: 5,
            stoch_rsi_window: 14,
            stoch_rsi_smooth1: 3,
            stoch_rsi_smooth2: 3,
            ave_avg_atr_window: 50,
        }
    }
}

// ---------------------------------------------------------------------------
// Filters config
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct FiltersConfig {
    pub enable_ranging_filter: bool,
    pub enable_anomaly_filter: bool,
    pub enable_extension_filter: bool,
    pub require_adx_rising: bool,
    pub adx_rising_saturation: f64,
    pub require_volume_confirmation: bool,
    pub vol_confirm_include_prev: bool,
    pub use_stoch_rsi_filter: bool,
    pub require_btc_alignment: bool,
    pub require_macro_alignment: bool,
}

impl Default for FiltersConfig {
    fn default() -> Self {
        Self {
            enable_ranging_filter: true,
            enable_anomaly_filter: true,
            enable_extension_filter: true,
            require_adx_rising: true,
            adx_rising_saturation: 40.0,
            require_volume_confirmation: false,
            vol_confirm_include_prev: true,
            use_stoch_rsi_filter: true,
            require_btc_alignment: true,
            require_macro_alignment: false,
        }
    }
}

// ---------------------------------------------------------------------------
// Market regime config
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct MarketRegimeConfig {
    pub enable_regime_filter: bool,
    pub breadth_block_short_above: f64,
    pub breadth_block_long_below: f64,
    pub enable_auto_reverse: bool,
    pub auto_reverse_breadth_low: f64,
    pub auto_reverse_breadth_high: f64,
}

impl Default for MarketRegimeConfig {
    fn default() -> Self {
        Self {
            enable_regime_filter: false,
            breadth_block_short_above: 90.0,
            breadth_block_long_below: 10.0,
            enable_auto_reverse: false,
            auto_reverse_breadth_low: 10.0,
            auto_reverse_breadth_high: 90.0,
        }
    }
}

// ---------------------------------------------------------------------------
// Threshold sub-sections
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct EntryThresholds {
    pub min_adx: f64,
    pub high_conf_volume_mult: f64,
    pub btc_adx_override: f64,
    pub max_dist_ema_fast: f64,

    // Adaptive Volatility Entry (AVE)
    pub ave_enabled: bool,
    pub ave_atr_ratio_gt: f64,
    pub ave_adx_mult: f64,
    pub ave_avg_atr_window: usize,

    // MACD gating
    pub macd_hist_entry_mode: MacdMode,

    // Pullback continuation entries
    pub enable_pullback_entries: bool,
    pub pullback_confidence: Confidence,
    pub pullback_min_adx: f64,
    pub pullback_rsi_long_min: f64,
    pub pullback_rsi_short_max: f64,
    pub pullback_require_macd_sign: bool,

    // Slow drift entries
    pub enable_slow_drift_entries: bool,
    pub slow_drift_slope_window: usize,
    pub slow_drift_min_slope_pct: f64,
    pub slow_drift_min_adx: f64,
    pub slow_drift_rsi_long_min: f64,
    pub slow_drift_rsi_short_max: f64,
    pub slow_drift_require_macd_sign: bool,
}

impl Default for EntryThresholds {
    fn default() -> Self {
        Self {
            min_adx: 22.0,
            high_conf_volume_mult: 2.5,
            btc_adx_override: 40.0,
            max_dist_ema_fast: 0.04,

            ave_enabled: true,
            ave_atr_ratio_gt: 1.5,
            ave_adx_mult: 1.25,
            ave_avg_atr_window: 50,

            macd_hist_entry_mode: MacdMode::Accel,

            enable_pullback_entries: false,
            pullback_confidence: Confidence::Low,
            pullback_min_adx: 22.0,
            pullback_rsi_long_min: 50.0,
            pullback_rsi_short_max: 50.0,
            pullback_require_macd_sign: true,

            enable_slow_drift_entries: false,
            slow_drift_slope_window: 20,
            slow_drift_min_slope_pct: 0.0006,
            slow_drift_min_adx: 10.0,
            slow_drift_rsi_long_min: 50.0,
            slow_drift_rsi_short_max: 50.0,
            slow_drift_require_macd_sign: true,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct RangingThresholds {
    pub min_signals: usize,
    pub adx_below: f64,
    pub bb_width_ratio_below: f64,
    pub rsi_low: f64,
    pub rsi_high: f64,
}

impl Default for RangingThresholds {
    fn default() -> Self {
        Self {
            min_signals: 2,
            adx_below: 21.0,
            bb_width_ratio_below: 0.8,
            rsi_low: 47.0,
            rsi_high: 53.0,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct AnomalyThresholds {
    pub price_change_pct_gt: f64,
    pub ema_fast_dev_pct_gt: f64,
}

impl Default for AnomalyThresholds {
    fn default() -> Self {
        Self {
            price_change_pct_gt: 0.10,
            ema_fast_dev_pct_gt: 0.50,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct TpAndMomentumThresholds {
    pub adx_strong_gt: f64,
    pub adx_weak_lt: f64,
    pub tp_mult_strong: f64,
    pub tp_mult_weak: f64,
    pub rsi_long_strong: f64,
    pub rsi_long_weak: f64,
    pub rsi_short_strong: f64,
    pub rsi_short_weak: f64,
}

impl Default for TpAndMomentumThresholds {
    fn default() -> Self {
        Self {
            adx_strong_gt: 40.0,
            adx_weak_lt: 30.0,
            tp_mult_strong: 7.0,
            tp_mult_weak: 3.0,
            rsi_long_strong: 52.0,
            rsi_long_weak: 56.0,
            rsi_short_strong: 48.0,
            rsi_short_weak: 44.0,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct StochRsiThresholds {
    pub block_long_if_k_gt: f64,
    pub block_short_if_k_lt: f64,
}

impl Default for StochRsiThresholds {
    fn default() -> Self {
        Self {
            block_long_if_k_gt: 0.85,
            block_short_if_k_lt: 0.15,
        }
    }
}

// ---------------------------------------------------------------------------
// Thresholds (parent)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct ThresholdsConfig {
    pub entry: EntryThresholds,
    pub ranging: RangingThresholds,
    pub anomaly: AnomalyThresholds,
    pub tp_and_momentum: TpAndMomentumThresholds,
    pub stoch_rsi: StochRsiThresholds,
}

impl Default for ThresholdsConfig {
    fn default() -> Self {
        Self {
            entry: EntryThresholds::default(),
            ranging: RangingThresholds::default(),
            anomaly: AnomalyThresholds::default(),
            tp_and_momentum: TpAndMomentumThresholds::default(),
            stoch_rsi: StochRsiThresholds::default(),
        }
    }
}

// ---------------------------------------------------------------------------
// Engine config (interval / entry / exit — shared with Python engine)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct EngineConfig {
    /// Main indicator candle interval (e.g. "1h", "15m").
    pub interval: String,
    /// Entry signal granularity (e.g. "3m", "5m"). Empty = same as interval.
    pub entry_interval: String,
    /// Exit price candle interval (e.g. "3m", "1m"). Empty = same as interval.
    pub exit_interval: String,
    /// Engine loop target seconds (engine-only, backtester ignores).
    pub loop_target_s: u64,
    /// Signal on candle close (engine-only, backtester ignores).
    pub signal_on_candle_close: bool,
}

impl Default for EngineConfig {
    fn default() -> Self {
        Self {
            interval: "1h".to_string(),
            entry_interval: String::new(),
            exit_interval: String::new(),
            loop_target_s: 60,
            signal_on_candle_close: true,
        }
    }
}

// ---------------------------------------------------------------------------
// Top-level strategy config
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct StrategyConfig {
    pub trade: TradeConfig,
    pub indicators: IndicatorsConfig,
    pub filters: FiltersConfig,
    pub market_regime: MarketRegimeConfig,
    pub thresholds: ThresholdsConfig,
    pub engine: EngineConfig,
}

impl Default for StrategyConfig {
    fn default() -> Self {
        Self {
            trade: TradeConfig::default(),
            indicators: IndicatorsConfig::default(),
            filters: FiltersConfig::default(),
            market_regime: MarketRegimeConfig::default(),
            thresholds: ThresholdsConfig::default(),
            engine: EngineConfig::default(),
        }
    }
}

impl StrategyConfig {
    /// Canonical AVE average ATR window for runtime indicator paths.
    pub fn effective_ave_avg_atr_window(&self) -> usize {
        self.thresholds.entry.ave_avg_atr_window
    }
}

// ---------------------------------------------------------------------------
// YAML overlay structure
// ---------------------------------------------------------------------------
//
// The YAML file has the shape:
//
// ```yaml
// global:
//   trade: { ... }
//   indicators: { ... }
//   filters: { ... }
//   market_regime: { ... }
//   thresholds: { ... }
// symbols:
//   BTC:
//     trade: { ... }
//     filters: { ... }
//     # ... (only the keys that differ from global)
//   ETH:
//     trade: { ... }
// live:
//   trade: { ... }
// ```
//
// We use `serde_yaml::Value` for the raw YAML and perform deep-merge at the
// `Value` level before deserialising into `StrategyConfig`. This way partial
// overrides (e.g. a symbol that only sets `trade.leverage`) work correctly
// without having to wrap every field in `Option<T>`.
//

/// Raw top-level YAML schema used only for parsing.
#[derive(Debug, Deserialize)]
struct YamlRoot {
    #[serde(default)]
    global: serde_yaml::Value,
    #[serde(default)]
    symbols: serde_yaml::Value,
    #[serde(default)]
    live: serde_yaml::Value,
}

// ---------------------------------------------------------------------------
// Deep merge on serde_yaml::Value
// ---------------------------------------------------------------------------

/// Recursively merge `overlay` into `base`.
///
/// - If both are `Mapping`, iterate overlay keys and recurse.
/// - Otherwise overlay wins (scalar / array replacement).
fn deep_merge(base: &mut serde_yaml::Value, overlay: &serde_yaml::Value) {
    match (base, overlay) {
        (serde_yaml::Value::Mapping(ref mut base_map), serde_yaml::Value::Mapping(overlay_map)) => {
            for (key, overlay_val) in overlay_map.iter() {
                if let Some(base_val) = base_map.get_mut(key) {
                    deep_merge(base_val, overlay_val);
                } else {
                    base_map.insert(key.clone(), overlay_val.clone());
                }
            }
        }
        (base, overlay) => {
            // Overlay is not Null => replace.  Null overlay means "use default" so skip.
            if !overlay.is_null() {
                *base = overlay.clone();
            }
        }
    }
}

/// Serialize `StrategyConfig::default()` to a `serde_yaml::Value` so we have a
/// base document with every key present for merging.
fn defaults_as_value() -> serde_yaml::Value {
    // Round-trip through JSON because serde_yaml's to_value can trip on enums
    // serialised as strings.  JSON -> YAML Value is reliable.
    let json_str = serde_json::to_string(&SerializableConfig::from(StrategyConfig::default()))
        .expect("default config serialises to JSON");
    serde_yaml::from_str(&json_str).expect("JSON round-trip to YAML Value")
}

/// Deterministic config fingerprint for audit/reporting.
///
/// The hash is computed from the canonical serialisable mirror used by config
/// merge/loading code (`SerializableConfig`), encoded as compact JSON, then
/// SHA-256 hex.
pub fn strategy_config_fingerprint_sha256(cfg: &StrategyConfig) -> String {
    let payload = serde_json::to_vec(&SerializableConfig::from(cfg.clone())).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(payload);
    format!("{:x}", hasher.finalize())
}

fn validate_loaded_config(cfg: &mut StrategyConfig) {
    if cfg.indicators.bb_width_avg_window == 0 {
        eprintln!(
            "[config] Invalid indicators.bb_width_avg_window=0; clamping to 1 to avoid RingBuf panic."
        );
        cfg.indicators.bb_width_avg_window = 1;
    }
}

// ---------------------------------------------------------------------------
// Serializable mirror (for defaults -> Value round-trip)
// ---------------------------------------------------------------------------
//
// We need `Serialize` to produce the base Value, but the main structs use
// custom `Deserialize` for enums.  Rather than adding Serialize to every
// struct (which would complicate the enum serialization), we define a thin
// serializable mirror used solely in `defaults_as_value()`.

#[derive(serde::Serialize)]
struct SerializableConfig {
    trade: serde_json::Value,
    indicators: serde_json::Value,
    filters: serde_json::Value,
    market_regime: serde_json::Value,
    thresholds: serde_json::Value,
    engine: serde_json::Value,
}

impl From<StrategyConfig> for SerializableConfig {
    fn from(cfg: StrategyConfig) -> Self {
        Self {
            trade: trade_to_json(&cfg.trade),
            indicators: indicators_to_json(&cfg.indicators),
            filters: filters_to_json(&cfg.filters),
            market_regime: market_regime_to_json(&cfg.market_regime),
            thresholds: thresholds_to_json(&cfg.thresholds),
            engine: engine_to_json(&cfg.engine),
        }
    }
}

fn trade_to_json(t: &TradeConfig) -> serde_json::Value {
    serde_json::json!({
        "allocation_pct": t.allocation_pct,
        "sl_atr_mult": t.sl_atr_mult,
        "tp_atr_mult": t.tp_atr_mult,
        "leverage": t.leverage,
        "enable_reef_filter": t.enable_reef_filter,
        "reef_long_rsi_block_gt": t.reef_long_rsi_block_gt,
        "reef_short_rsi_block_lt": t.reef_short_rsi_block_lt,
        "reef_adx_threshold": t.reef_adx_threshold,
        "reef_long_rsi_extreme_gt": t.reef_long_rsi_extreme_gt,
        "reef_short_rsi_extreme_lt": t.reef_short_rsi_extreme_lt,
        "leverage_low": t.leverage_low,
        "leverage_medium": t.leverage_medium,
        "leverage_high": t.leverage_high,
        "slippage_bps": t.slippage_bps,
        "use_bbo_for_fills": t.use_bbo_for_fills,
        "min_notional_usd": t.min_notional_usd,
        "bump_to_min_notional": t.bump_to_min_notional,
        "max_total_margin_pct": t.max_total_margin_pct,
        "enable_dynamic_sizing": t.enable_dynamic_sizing,
        "confidence_mult_high": t.confidence_mult_high,
        "confidence_mult_medium": t.confidence_mult_medium,
        "confidence_mult_low": t.confidence_mult_low,
        "adx_sizing_min_mult": t.adx_sizing_min_mult,
        "adx_sizing_full_adx": t.adx_sizing_full_adx,
        "vol_baseline_pct": t.vol_baseline_pct,
        "vol_scalar_min": t.vol_scalar_min,
        "vol_scalar_max": t.vol_scalar_max,
        "enable_pyramiding": t.enable_pyramiding,
        "max_adds_per_symbol": t.max_adds_per_symbol,
        "add_fraction_of_base_margin": t.add_fraction_of_base_margin,
        "add_cooldown_minutes": t.add_cooldown_minutes,
        "add_min_profit_atr": t.add_min_profit_atr,
        "add_min_confidence": t.add_min_confidence.to_string(),
        "entry_min_confidence": t.entry_min_confidence.to_string(),
        "enable_partial_tp": t.enable_partial_tp,
        "tp_partial_pct": t.tp_partial_pct,
        "tp_partial_min_notional_usd": t.tp_partial_min_notional_usd,
        "tp_partial_atr_mult": t.tp_partial_atr_mult,
        "trailing_start_atr": t.trailing_start_atr,
        "trailing_distance_atr": t.trailing_distance_atr,
        "enable_ssf_filter": t.enable_ssf_filter,
        "enable_breakeven_stop": t.enable_breakeven_stop,
        "breakeven_start_atr": t.breakeven_start_atr,
        "breakeven_buffer_atr": t.breakeven_buffer_atr,
        "trailing_start_atr_low_conf": t.trailing_start_atr_low_conf,
        "trailing_distance_atr_low_conf": t.trailing_distance_atr_low_conf,
        "smart_exit_adx_exhaustion_lt": t.smart_exit_adx_exhaustion_lt,
        "smart_exit_adx_exhaustion_lt_low_conf": t.smart_exit_adx_exhaustion_lt_low_conf,
        "enable_rsi_overextension_exit": t.enable_rsi_overextension_exit,
        "rsi_exit_profit_atr_switch": t.rsi_exit_profit_atr_switch,
        "rsi_exit_ub_lo_profit": t.rsi_exit_ub_lo_profit,
        "rsi_exit_ub_hi_profit": t.rsi_exit_ub_hi_profit,
        "rsi_exit_lb_lo_profit": t.rsi_exit_lb_lo_profit,
        "rsi_exit_lb_hi_profit": t.rsi_exit_lb_hi_profit,
        "rsi_exit_ub_lo_profit_low_conf": t.rsi_exit_ub_lo_profit_low_conf,
        "rsi_exit_ub_hi_profit_low_conf": t.rsi_exit_ub_hi_profit_low_conf,
        "rsi_exit_lb_lo_profit_low_conf": t.rsi_exit_lb_lo_profit_low_conf,
        "rsi_exit_lb_hi_profit_low_conf": t.rsi_exit_lb_hi_profit_low_conf,
        "reentry_cooldown_minutes": t.reentry_cooldown_minutes,
        "reentry_cooldown_min_mins": t.reentry_cooldown_min_mins,
        "reentry_cooldown_max_mins": t.reentry_cooldown_max_mins,
        "enable_vol_buffered_trailing": t.enable_vol_buffered_trailing,
        "tsme_min_profit_atr": t.tsme_min_profit_atr,
        "tsme_require_adx_slope_negative": t.tsme_require_adx_slope_negative,
        "min_atr_pct": t.min_atr_pct,
        "reverse_entry_signal": t.reverse_entry_signal,
        "block_exits_on_extreme_dev": t.block_exits_on_extreme_dev,
        "glitch_price_dev_pct": t.glitch_price_dev_pct,
        "glitch_atr_mult": t.glitch_atr_mult,
        "max_open_positions": t.max_open_positions,
        "entry_cooldown_s": t.entry_cooldown_s,
        "exit_cooldown_s": t.exit_cooldown_s,
        "max_entry_orders_per_loop": t.max_entry_orders_per_loop,
    })
}

fn indicators_to_json(i: &IndicatorsConfig) -> serde_json::Value {
    serde_json::json!({
        "ema_slow_window": i.ema_slow_window,
        "ema_fast_window": i.ema_fast_window,
        "ema_macro_window": i.ema_macro_window,
        "adx_window": i.adx_window,
        "bb_window": i.bb_window,
        "bb_width_avg_window": i.bb_width_avg_window,
        "atr_window": i.atr_window,
        "rsi_window": i.rsi_window,
        "vol_sma_window": i.vol_sma_window,
        "vol_trend_window": i.vol_trend_window,
        "stoch_rsi_window": i.stoch_rsi_window,
        "stoch_rsi_smooth1": i.stoch_rsi_smooth1,
        "stoch_rsi_smooth2": i.stoch_rsi_smooth2,
        "ave_avg_atr_window": i.ave_avg_atr_window,
    })
}

fn filters_to_json(f: &FiltersConfig) -> serde_json::Value {
    serde_json::json!({
        "enable_ranging_filter": f.enable_ranging_filter,
        "enable_anomaly_filter": f.enable_anomaly_filter,
        "enable_extension_filter": f.enable_extension_filter,
        "require_adx_rising": f.require_adx_rising,
        "adx_rising_saturation": f.adx_rising_saturation,
        "require_volume_confirmation": f.require_volume_confirmation,
        "vol_confirm_include_prev": f.vol_confirm_include_prev,
        "use_stoch_rsi_filter": f.use_stoch_rsi_filter,
        "require_btc_alignment": f.require_btc_alignment,
        "require_macro_alignment": f.require_macro_alignment,
    })
}

fn market_regime_to_json(m: &MarketRegimeConfig) -> serde_json::Value {
    serde_json::json!({
        "enable_regime_filter": m.enable_regime_filter,
        "breadth_block_short_above": m.breadth_block_short_above,
        "breadth_block_long_below": m.breadth_block_long_below,
        "enable_auto_reverse": m.enable_auto_reverse,
        "auto_reverse_breadth_low": m.auto_reverse_breadth_low,
        "auto_reverse_breadth_high": m.auto_reverse_breadth_high,
    })
}

fn thresholds_to_json(th: &ThresholdsConfig) -> serde_json::Value {
    serde_json::json!({
        "entry": {
            "min_adx": th.entry.min_adx,
            "high_conf_volume_mult": th.entry.high_conf_volume_mult,
            "btc_adx_override": th.entry.btc_adx_override,
            "max_dist_ema_fast": th.entry.max_dist_ema_fast,
            "ave_enabled": th.entry.ave_enabled,
            "ave_atr_ratio_gt": th.entry.ave_atr_ratio_gt,
            "ave_adx_mult": th.entry.ave_adx_mult,
            "ave_avg_atr_window": th.entry.ave_avg_atr_window,
            "macd_hist_entry_mode": th.entry.macd_hist_entry_mode.to_string(),
            "enable_pullback_entries": th.entry.enable_pullback_entries,
            "pullback_confidence": th.entry.pullback_confidence.to_string(),
            "pullback_min_adx": th.entry.pullback_min_adx,
            "pullback_rsi_long_min": th.entry.pullback_rsi_long_min,
            "pullback_rsi_short_max": th.entry.pullback_rsi_short_max,
            "pullback_require_macd_sign": th.entry.pullback_require_macd_sign,
            "enable_slow_drift_entries": th.entry.enable_slow_drift_entries,
            "slow_drift_slope_window": th.entry.slow_drift_slope_window,
            "slow_drift_min_slope_pct": th.entry.slow_drift_min_slope_pct,
            "slow_drift_min_adx": th.entry.slow_drift_min_adx,
            "slow_drift_rsi_long_min": th.entry.slow_drift_rsi_long_min,
            "slow_drift_rsi_short_max": th.entry.slow_drift_rsi_short_max,
            "slow_drift_require_macd_sign": th.entry.slow_drift_require_macd_sign,
        },
        "ranging": {
            "min_signals": th.ranging.min_signals,
            "adx_below": th.ranging.adx_below,
            "bb_width_ratio_below": th.ranging.bb_width_ratio_below,
            "rsi_low": th.ranging.rsi_low,
            "rsi_high": th.ranging.rsi_high,
        },
        "anomaly": {
            "price_change_pct_gt": th.anomaly.price_change_pct_gt,
            "ema_fast_dev_pct_gt": th.anomaly.ema_fast_dev_pct_gt,
        },
        "tp_and_momentum": {
            "adx_strong_gt": th.tp_and_momentum.adx_strong_gt,
            "adx_weak_lt": th.tp_and_momentum.adx_weak_lt,
            "tp_mult_strong": th.tp_and_momentum.tp_mult_strong,
            "tp_mult_weak": th.tp_and_momentum.tp_mult_weak,
            "rsi_long_strong": th.tp_and_momentum.rsi_long_strong,
            "rsi_long_weak": th.tp_and_momentum.rsi_long_weak,
            "rsi_short_strong": th.tp_and_momentum.rsi_short_strong,
            "rsi_short_weak": th.tp_and_momentum.rsi_short_weak,
        },
        "stoch_rsi": {
            "block_long_if_k_gt": th.stoch_rsi.block_long_if_k_gt,
            "block_short_if_k_lt": th.stoch_rsi.block_short_if_k_lt,
        },
    })
}

fn engine_to_json(e: &EngineConfig) -> serde_json::Value {
    serde_json::json!({
        "interval": e.interval,
        "entry_interval": e.entry_interval,
        "exit_interval": e.exit_interval,
        "loop_target_s": e.loop_target_s,
        "signal_on_candle_close": e.signal_on_candle_close,
    })
}

// ---------------------------------------------------------------------------
// Public loader
// ---------------------------------------------------------------------------

/// Strict config loader.
///
/// Merge hierarchy:
///
///   defaults <- global <- symbols.<symbol> <- live (if `is_live`)
///
/// Returns a descriptive error when the file is missing, unreadable, invalid YAML,
/// or fails typed deserialization after merge.
pub fn load_config_checked(
    yaml_path: &str,
    symbol: Option<&str>,
    is_live: bool,
) -> Result<StrategyConfig, String> {
    let path = Path::new(yaml_path);
    match std::fs::metadata(path) {
        Ok(_) => {}
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            let cwd = std::env::current_dir()
                .map(|p| p.display().to_string())
                .unwrap_or_else(|_| "<unknown>".to_string());
            return Err(format!(
                "YAML config file does not exist: {yaml_path} (cwd: {cwd})"
            ));
        }
        Err(e) => {
            return Err(format!("failed to stat config path {yaml_path}: {e}"));
        }
    }

    let raw = match std::fs::read_to_string(path) {
        Ok(s) => s,
        Err(e) => {
            return Err(format!("failed to read {yaml_path}: {e}"));
        }
    };

    let root: YamlRoot = match serde_yaml::from_str(&raw) {
        Ok(r) => r,
        Err(e) => {
            return Err(format!("failed to parse YAML {yaml_path}: {e}"));
        }
    };

    // Start with full defaults as a Value tree.
    let mut merged = defaults_as_value();

    // Layer 1: global overrides.
    if !root.global.is_null() {
        deep_merge(&mut merged, &root.global);
    }

    // Layer 2: per-symbol overrides.
    if let Some(sym) = symbol {
        if let serde_yaml::Value::Mapping(ref symbols_map) = root.symbols {
            // Try exact match first, then uppercase.
            let sym_key = serde_yaml::Value::String(sym.to_string());
            let sym_key_upper = serde_yaml::Value::String(sym.to_uppercase());
            let sym_val = symbols_map
                .get(&sym_key)
                .or_else(|| symbols_map.get(&sym_key_upper));
            if let Some(sym_overrides) = sym_val {
                deep_merge(&mut merged, sym_overrides);
            }
        }
    }

    // Layer 3: live-mode overrides.
    if is_live && !root.live.is_null() {
        deep_merge(&mut merged, &root.live);
    }

    // Deserialize the merged Value into the typed config.
    match serde_yaml::from_value(merged) {
        Ok(mut cfg) => {
            validate_loaded_config(&mut cfg);
            Ok(cfg)
        }
        Err(e) => Err(format!("failed to deserialize merged config: {e}")),
    }
}

/// Backwards-compatible permissive loader.
///
/// This keeps historical behaviour for callers that expect fallback defaults.
/// New parity-critical paths should prefer `load_config_checked`.
pub fn load_config(yaml_path: &str, symbol: Option<&str>, is_live: bool) -> StrategyConfig {
    match load_config_checked(yaml_path, symbol, is_live) {
        Ok(cfg) => cfg,
        Err(msg) => {
            eprintln!("[config] {msg}. Using defaults.");
            StrategyConfig::default()
        }
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_defaults_roundtrip() {
        // Verify that defaults survive serialization -> deserialization.
        let cfg = StrategyConfig::default();
        assert!((cfg.trade.allocation_pct - 0.03).abs() < f64::EPSILON);
        assert_eq!(cfg.trade.max_adds_per_symbol, 2);
        assert_eq!(cfg.trade.entry_min_confidence, Confidence::High);
        assert_eq!(cfg.trade.add_min_confidence, Confidence::Medium);
        assert_eq!(cfg.indicators.ema_slow_window, 50);
        assert!(cfg.filters.enable_ranging_filter);
        assert!(!cfg.market_regime.enable_regime_filter);
        assert!((cfg.thresholds.entry.min_adx - 22.0).abs() < f64::EPSILON);
        assert_eq!(cfg.thresholds.entry.macd_hist_entry_mode, MacdMode::Accel);
        assert!((cfg.thresholds.stoch_rsi.block_long_if_k_gt - 0.85).abs() < f64::EPSILON);
    }

    #[test]
    fn test_effective_ave_window_uses_thresholds_entry() {
        let mut cfg = StrategyConfig::default();
        cfg.indicators.ave_avg_atr_window = 7;
        cfg.thresholds.entry.ave_avg_atr_window = 33;
        assert_eq!(cfg.effective_ave_avg_atr_window(), 33);
    }

    #[test]
    fn test_confidence_ordering() {
        assert!(Confidence::Low < Confidence::Medium);
        assert!(Confidence::Medium < Confidence::High);
        assert_eq!(Confidence::from_str("low").unwrap(), Confidence::Low);
        assert_eq!(Confidence::from_str("MEDIUM").unwrap(), Confidence::Medium);
        assert_eq!(Confidence::from_str("High").unwrap(), Confidence::High);
        // Unknown values must fail fast.
        assert!(Confidence::from_str("unknown").is_err());
    }

    #[test]
    fn test_macd_mode_from_str() {
        assert_eq!(MacdMode::from_str("accel").unwrap(), MacdMode::Accel);
        assert_eq!(MacdMode::from_str("sign").unwrap(), MacdMode::Sign);
        assert_eq!(MacdMode::from_str("none").unwrap(), MacdMode::None);
        assert_eq!(MacdMode::from_str("ACCEL").unwrap(), MacdMode::Accel);
        // Unknown values must fail fast.
        assert!(MacdMode::from_str("bogus").is_err());
    }

    #[test]
    fn test_deep_merge_scalar() {
        let mut base = serde_yaml::from_str::<serde_yaml::Value>("a: 1\nb: 2").unwrap();
        let overlay = serde_yaml::from_str::<serde_yaml::Value>("b: 99\nc: 3").unwrap();
        deep_merge(&mut base, &overlay);
        let m = base.as_mapping().unwrap();
        assert_eq!(
            m.get(&serde_yaml::Value::String("a".into()))
                .unwrap()
                .as_i64()
                .unwrap(),
            1
        );
        assert_eq!(
            m.get(&serde_yaml::Value::String("b".into()))
                .unwrap()
                .as_i64()
                .unwrap(),
            99
        );
        assert_eq!(
            m.get(&serde_yaml::Value::String("c".into()))
                .unwrap()
                .as_i64()
                .unwrap(),
            3
        );
    }

    #[test]
    fn test_deep_merge_nested() {
        let mut base = serde_yaml::from_str::<serde_yaml::Value>(
            "trade:\n  leverage: 3.0\n  sl_atr_mult: 2.0",
        )
        .unwrap();
        let overlay = serde_yaml::from_str::<serde_yaml::Value>("trade:\n  leverage: 5.0").unwrap();
        deep_merge(&mut base, &overlay);
        let trade = base
            .as_mapping()
            .unwrap()
            .get(&serde_yaml::Value::String("trade".into()))
            .unwrap()
            .as_mapping()
            .unwrap();
        assert_eq!(
            trade
                .get(&serde_yaml::Value::String("leverage".into()))
                .unwrap()
                .as_f64()
                .unwrap(),
            5.0
        );
        // sl_atr_mult should be preserved from base.
        assert_eq!(
            trade
                .get(&serde_yaml::Value::String("sl_atr_mult".into()))
                .unwrap()
                .as_f64()
                .unwrap(),
            2.0
        );
    }

    #[test]
    fn test_load_missing_file() {
        let cfg = load_config("/tmp/nonexistent_strategy_overrides_xyz.yaml", None, false);
        assert!((cfg.trade.allocation_pct - 0.03).abs() < f64::EPSILON);
    }

    #[test]
    fn test_load_yaml_global_override() {
        let yaml = r#"
global:
  trade:
    leverage: 7.5
    allocation_pct: 0.05
  filters:
    require_btc_alignment: false
"#;
        let tmp = std::env::temp_dir().join("bt_config_test_global.yaml");
        std::fs::write(&tmp, yaml).unwrap();
        let cfg = load_config(tmp.to_str().unwrap(), None, false);
        assert!((cfg.trade.leverage - 7.5).abs() < f64::EPSILON);
        assert!((cfg.trade.allocation_pct - 0.05).abs() < f64::EPSILON);
        assert!(!cfg.filters.require_btc_alignment);
        // Non-overridden field keeps default.
        assert!((cfg.trade.sl_atr_mult - 2.0).abs() < f64::EPSILON);
        std::fs::remove_file(&tmp).ok();
    }

    #[test]
    fn test_load_yaml_symbol_override() {
        let yaml = r#"
global:
  trade:
    leverage: 2.0
symbols:
  BTC:
    trade:
      leverage: 10.0
      sl_atr_mult: 1.5
"#;
        let tmp = std::env::temp_dir().join("bt_config_test_sym.yaml");
        std::fs::write(&tmp, yaml).unwrap();
        let cfg = load_config(tmp.to_str().unwrap(), Some("BTC"), false);
        assert!((cfg.trade.leverage - 10.0).abs() < f64::EPSILON);
        assert!((cfg.trade.sl_atr_mult - 1.5).abs() < f64::EPSILON);
        // Without symbol, only global applies.
        let cfg2 = load_config(tmp.to_str().unwrap(), None, false);
        assert!((cfg2.trade.leverage - 2.0).abs() < f64::EPSILON);
        assert!((cfg2.trade.sl_atr_mult - 2.0).abs() < f64::EPSILON);
        std::fs::remove_file(&tmp).ok();
    }

    #[test]
    fn test_load_yaml_live_override() {
        let yaml = r#"
global:
  trade:
    leverage: 2.0
live:
  trade:
    leverage: 1.0
    max_open_positions: 5
"#;
        let tmp = std::env::temp_dir().join("bt_config_test_live.yaml");
        std::fs::write(&tmp, yaml).unwrap();
        // Not live -> no live layer.
        let cfg = load_config(tmp.to_str().unwrap(), None, false);
        assert!((cfg.trade.leverage - 2.0).abs() < f64::EPSILON);
        assert_eq!(cfg.trade.max_open_positions, 20);
        // Live -> live layer applied.
        let cfg_live = load_config(tmp.to_str().unwrap(), None, true);
        assert!((cfg_live.trade.leverage - 1.0).abs() < f64::EPSILON);
        assert_eq!(cfg_live.trade.max_open_positions, 5);
        std::fs::remove_file(&tmp).ok();
    }

    #[test]
    fn test_full_merge_hierarchy() {
        let yaml = r#"
global:
  trade:
    leverage: 2.0
    allocation_pct: 0.05
symbols:
  ETH:
    trade:
      leverage: 4.0
live:
  trade:
    allocation_pct: 0.02
"#;
        let tmp = std::env::temp_dir().join("bt_config_test_full.yaml");
        std::fs::write(&tmp, yaml).unwrap();
        // defaults(3.0) <- global(2.0) <- ETH(4.0) <- live(alloc=0.02)
        let cfg = load_config(tmp.to_str().unwrap(), Some("ETH"), true);
        assert!((cfg.trade.leverage - 4.0).abs() < f64::EPSILON);
        assert!((cfg.trade.allocation_pct - 0.02).abs() < f64::EPSILON);
        std::fs::remove_file(&tmp).ok();
    }

    #[test]
    fn test_load_yaml_clamps_zero_bb_width_avg_window() {
        let yaml = r#"
global:
  indicators:
    bb_width_avg_window: 0
"#;
        let tmp = std::env::temp_dir().join("bt_config_test_bb_width_avg_window_zero.yaml");
        std::fs::write(&tmp, yaml).unwrap();
        let cfg = load_config(tmp.to_str().unwrap(), None, false);
        assert_eq!(cfg.indicators.bb_width_avg_window, 1);
        std::fs::remove_file(&tmp).ok();
    }
}
