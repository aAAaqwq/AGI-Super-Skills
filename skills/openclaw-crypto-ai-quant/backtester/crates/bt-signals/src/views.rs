use crate::{Confidence, MacdMode};

#[derive(Debug, Clone, Copy)]
pub struct TradeView {
    pub tp_atr_mult: f64,
}

impl Default for TradeView {
    fn default() -> Self {
        Self { tp_atr_mult: 4.0 }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct FiltersView {
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

impl Default for FiltersView {
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

#[derive(Debug, Clone, Copy)]
pub struct EntryThresholdsView {
    pub min_adx: f64,
    pub high_conf_volume_mult: f64,
    pub btc_adx_override: f64,
    pub max_dist_ema_fast: f64,
    pub ave_enabled: bool,
    pub ave_atr_ratio_gt: f64,
    pub ave_adx_mult: f64,
    pub macd_hist_entry_mode: MacdMode,
    pub enable_pullback_entries: bool,
    pub pullback_confidence: Confidence,
    pub pullback_min_adx: f64,
    pub pullback_rsi_long_min: f64,
    pub pullback_rsi_short_max: f64,
    pub pullback_require_macd_sign: bool,
    pub enable_slow_drift_entries: bool,
    pub slow_drift_min_slope_pct: f64,
    pub slow_drift_min_adx: f64,
    pub slow_drift_rsi_long_min: f64,
    pub slow_drift_rsi_short_max: f64,
    pub slow_drift_require_macd_sign: bool,
}

impl Default for EntryThresholdsView {
    fn default() -> Self {
        Self {
            min_adx: 22.0,
            high_conf_volume_mult: 2.5,
            btc_adx_override: 40.0,
            max_dist_ema_fast: 0.04,
            ave_enabled: true,
            ave_atr_ratio_gt: 1.5,
            ave_adx_mult: 1.25,
            macd_hist_entry_mode: MacdMode::Accel,
            enable_pullback_entries: false,
            pullback_confidence: Confidence::Low,
            pullback_min_adx: 22.0,
            pullback_rsi_long_min: 50.0,
            pullback_rsi_short_max: 50.0,
            pullback_require_macd_sign: true,
            enable_slow_drift_entries: false,
            slow_drift_min_slope_pct: 0.0006,
            slow_drift_min_adx: 10.0,
            slow_drift_rsi_long_min: 50.0,
            slow_drift_rsi_short_max: 50.0,
            slow_drift_require_macd_sign: true,
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct RangingThresholdsView {
    pub min_signals: usize,
    pub adx_below: f64,
    pub bb_width_ratio_below: f64,
    pub rsi_low: f64,
    pub rsi_high: f64,
}

impl Default for RangingThresholdsView {
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

#[derive(Debug, Clone, Copy)]
pub struct AnomalyThresholdsView {
    pub price_change_pct_gt: f64,
    pub ema_fast_dev_pct_gt: f64,
}

impl Default for AnomalyThresholdsView {
    fn default() -> Self {
        Self {
            price_change_pct_gt: 0.10,
            ema_fast_dev_pct_gt: 0.50,
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct TpAndMomentumThresholdsView {
    pub adx_strong_gt: f64,
    pub adx_weak_lt: f64,
    pub tp_mult_strong: f64,
    pub tp_mult_weak: f64,
    pub rsi_long_strong: f64,
    pub rsi_long_weak: f64,
    pub rsi_short_strong: f64,
    pub rsi_short_weak: f64,
}

impl Default for TpAndMomentumThresholdsView {
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

#[derive(Debug, Clone, Copy)]
pub struct StochRsiThresholdsView {
    pub block_long_if_k_gt: f64,
    pub block_short_if_k_lt: f64,
}

impl Default for StochRsiThresholdsView {
    fn default() -> Self {
        Self {
            block_long_if_k_gt: 0.85,
            block_short_if_k_lt: 0.15,
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct ThresholdsView {
    pub entry: EntryThresholdsView,
    pub ranging: RangingThresholdsView,
    pub anomaly: AnomalyThresholdsView,
    pub tp_and_momentum: TpAndMomentumThresholdsView,
    pub stoch_rsi: StochRsiThresholdsView,
}

impl Default for ThresholdsView {
    fn default() -> Self {
        Self {
            entry: EntryThresholdsView::default(),
            ranging: RangingThresholdsView::default(),
            anomaly: AnomalyThresholdsView::default(),
            tp_and_momentum: TpAndMomentumThresholdsView::default(),
            stoch_rsi: StochRsiThresholdsView::default(),
        }
    }
}

pub trait SignalConfigLike {
    fn trade_view(&self) -> TradeView;
    fn filters_view(&self) -> FiltersView;
    fn thresholds_view(&self) -> ThresholdsView;
}

#[derive(Debug, Clone, Copy, Default)]
pub struct SignalConfigView {
    pub trade: TradeView,
    pub filters: FiltersView,
    pub thresholds: ThresholdsView,
}

impl SignalConfigLike for SignalConfigView {
    fn trade_view(&self) -> TradeView {
        self.trade
    }

    fn filters_view(&self) -> FiltersView {
        self.filters
    }

    fn thresholds_view(&self) -> ThresholdsView {
        self.thresholds
    }
}

#[derive(Debug, Clone, Copy)]
pub struct SnapshotView {
    pub close: f64,
    pub high: f64,
    pub low: f64,
    pub open: f64,
    pub volume: f64,
    pub t: i64,
    pub ema_slow: f64,
    pub ema_fast: f64,
    pub ema_macro: f64,
    pub adx: f64,
    pub adx_pos: f64,
    pub adx_neg: f64,
    pub adx_slope: f64,
    pub bb_upper: f64,
    pub bb_lower: f64,
    pub bb_width: f64,
    pub bb_width_avg: f64,
    pub bb_width_ratio: f64,
    pub atr: f64,
    pub atr_slope: f64,
    pub avg_atr: f64,
    pub rsi: f64,
    pub stoch_rsi_k: f64,
    pub stoch_rsi_d: f64,
    pub macd_hist: f64,
    pub prev_macd_hist: f64,
    pub prev2_macd_hist: f64,
    pub prev3_macd_hist: f64,
    pub vol_sma: f64,
    pub vol_trend: bool,
    pub prev_close: f64,
    pub prev_ema_fast: f64,
    pub prev_ema_slow: f64,
    pub bar_count: usize,
    pub funding_rate: f64,
}

pub trait IndicatorSnapshotLike {
    fn snapshot_view(&self) -> SnapshotView;
}

impl IndicatorSnapshotLike for SnapshotView {
    fn snapshot_view(&self) -> SnapshotView {
        *self
    }
}
