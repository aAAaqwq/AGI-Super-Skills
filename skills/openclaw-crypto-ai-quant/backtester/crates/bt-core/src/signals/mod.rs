pub use bt_signals::{confidence, entry, gates};

use bt_signals::{
    AnomalyThresholdsView, EntryThresholdsView, FiltersView, IndicatorSnapshotLike,
    RangingThresholdsView, SignalConfigLike, SnapshotView, StochRsiThresholdsView, ThresholdsView,
    TpAndMomentumThresholdsView, TradeView,
};

use crate::config::StrategyConfig;
use crate::indicators::IndicatorSnapshot;

impl IndicatorSnapshotLike for IndicatorSnapshot {
    fn snapshot_view(&self) -> SnapshotView {
        SnapshotView {
            close: self.close,
            high: self.high,
            low: self.low,
            open: self.open,
            volume: self.volume,
            t: self.t,
            ema_slow: self.ema_slow,
            ema_fast: self.ema_fast,
            ema_macro: self.ema_macro,
            adx: self.adx,
            adx_pos: self.adx_pos,
            adx_neg: self.adx_neg,
            adx_slope: self.adx_slope,
            bb_upper: self.bb_upper,
            bb_lower: self.bb_lower,
            bb_width: self.bb_width,
            bb_width_avg: self.bb_width_avg,
            bb_width_ratio: self.bb_width_ratio,
            atr: self.atr,
            atr_slope: self.atr_slope,
            avg_atr: self.avg_atr,
            rsi: self.rsi,
            stoch_rsi_k: self.stoch_rsi_k,
            stoch_rsi_d: self.stoch_rsi_d,
            macd_hist: self.macd_hist,
            prev_macd_hist: self.prev_macd_hist,
            prev2_macd_hist: self.prev2_macd_hist,
            prev3_macd_hist: self.prev3_macd_hist,
            vol_sma: self.vol_sma,
            vol_trend: self.vol_trend,
            prev_close: self.prev_close,
            prev_ema_fast: self.prev_ema_fast,
            prev_ema_slow: self.prev_ema_slow,
            bar_count: self.bar_count,
            funding_rate: self.funding_rate,
        }
    }
}

impl SignalConfigLike for StrategyConfig {
    fn trade_view(&self) -> TradeView {
        TradeView {
            tp_atr_mult: self.trade.tp_atr_mult,
        }
    }

    fn filters_view(&self) -> FiltersView {
        FiltersView {
            enable_ranging_filter: self.filters.enable_ranging_filter,
            enable_anomaly_filter: self.filters.enable_anomaly_filter,
            enable_extension_filter: self.filters.enable_extension_filter,
            require_adx_rising: self.filters.require_adx_rising,
            adx_rising_saturation: self.filters.adx_rising_saturation,
            require_volume_confirmation: self.filters.require_volume_confirmation,
            vol_confirm_include_prev: self.filters.vol_confirm_include_prev,
            use_stoch_rsi_filter: self.filters.use_stoch_rsi_filter,
            require_btc_alignment: self.filters.require_btc_alignment,
            require_macro_alignment: self.filters.require_macro_alignment,
        }
    }

    fn thresholds_view(&self) -> ThresholdsView {
        ThresholdsView {
            entry: EntryThresholdsView {
                min_adx: self.thresholds.entry.min_adx,
                high_conf_volume_mult: self.thresholds.entry.high_conf_volume_mult,
                btc_adx_override: self.thresholds.entry.btc_adx_override,
                max_dist_ema_fast: self.thresholds.entry.max_dist_ema_fast,
                ave_enabled: self.thresholds.entry.ave_enabled,
                ave_atr_ratio_gt: self.thresholds.entry.ave_atr_ratio_gt,
                ave_adx_mult: self.thresholds.entry.ave_adx_mult,
                macd_hist_entry_mode: self.thresholds.entry.macd_hist_entry_mode,
                enable_pullback_entries: self.thresholds.entry.enable_pullback_entries,
                pullback_confidence: self.thresholds.entry.pullback_confidence,
                pullback_min_adx: self.thresholds.entry.pullback_min_adx,
                pullback_rsi_long_min: self.thresholds.entry.pullback_rsi_long_min,
                pullback_rsi_short_max: self.thresholds.entry.pullback_rsi_short_max,
                pullback_require_macd_sign: self.thresholds.entry.pullback_require_macd_sign,
                enable_slow_drift_entries: self.thresholds.entry.enable_slow_drift_entries,
                slow_drift_min_slope_pct: self.thresholds.entry.slow_drift_min_slope_pct,
                slow_drift_min_adx: self.thresholds.entry.slow_drift_min_adx,
                slow_drift_rsi_long_min: self.thresholds.entry.slow_drift_rsi_long_min,
                slow_drift_rsi_short_max: self.thresholds.entry.slow_drift_rsi_short_max,
                slow_drift_require_macd_sign: self.thresholds.entry.slow_drift_require_macd_sign,
            },
            ranging: RangingThresholdsView {
                min_signals: self.thresholds.ranging.min_signals,
                adx_below: self.thresholds.ranging.adx_below,
                bb_width_ratio_below: self.thresholds.ranging.bb_width_ratio_below,
                rsi_low: self.thresholds.ranging.rsi_low,
                rsi_high: self.thresholds.ranging.rsi_high,
            },
            anomaly: AnomalyThresholdsView {
                price_change_pct_gt: self.thresholds.anomaly.price_change_pct_gt,
                ema_fast_dev_pct_gt: self.thresholds.anomaly.ema_fast_dev_pct_gt,
            },
            tp_and_momentum: TpAndMomentumThresholdsView {
                adx_strong_gt: self.thresholds.tp_and_momentum.adx_strong_gt,
                adx_weak_lt: self.thresholds.tp_and_momentum.adx_weak_lt,
                tp_mult_strong: self.thresholds.tp_and_momentum.tp_mult_strong,
                tp_mult_weak: self.thresholds.tp_and_momentum.tp_mult_weak,
                rsi_long_strong: self.thresholds.tp_and_momentum.rsi_long_strong,
                rsi_long_weak: self.thresholds.tp_and_momentum.rsi_long_weak,
                rsi_short_strong: self.thresholds.tp_and_momentum.rsi_short_strong,
                rsi_short_weak: self.thresholds.tp_and_momentum.rsi_short_weak,
            },
            stoch_rsi: StochRsiThresholdsView {
                block_long_if_k_gt: self.thresholds.stoch_rsi.block_long_if_k_gt,
                block_short_if_k_lt: self.thresholds.stoch_rsi.block_short_if_k_lt,
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{Confidence, Signal, StrategyConfig};

    fn bullish_snap() -> IndicatorSnapshot {
        IndicatorSnapshot {
            close: 100.0,
            high: 101.0,
            low: 99.0,
            open: 99.5,
            volume: 1200.0,
            t: 0,
            ema_slow: 97.0,
            ema_fast: 99.0,
            ema_macro: 94.0,
            adx: 32.0,
            adx_pos: 22.0,
            adx_neg: 10.0,
            adx_slope: 1.5,
            bb_upper: 103.0,
            bb_lower: 97.0,
            bb_width: 0.06,
            bb_width_avg: 0.05,
            bb_width_ratio: 1.2,
            atr: 1.5,
            atr_slope: 0.1,
            avg_atr: 1.4,
            rsi: 57.0,
            stoch_rsi_k: 0.5,
            stoch_rsi_d: 0.5,
            macd_hist: 0.5,
            prev_macd_hist: 0.3,
            prev2_macd_hist: 0.1,
            prev3_macd_hist: 0.0,
            vol_sma: 800.0,
            vol_trend: true,
            prev_close: 98.0,
            prev_ema_fast: 98.5,
            prev_ema_slow: 96.8,
            bar_count: 200,
            funding_rate: 0.0,
        }
    }

    #[test]
    fn test_adapter_trade_and_filter_mapping() {
        let mut cfg = StrategyConfig::default();
        cfg.trade.tp_atr_mult = 6.2;
        cfg.filters.use_stoch_rsi_filter = false;
        cfg.thresholds.tp_and_momentum.adx_weak_lt = 20.0;
        cfg.thresholds.tp_and_momentum.adx_strong_gt = 40.0;

        let mut snap = bullish_snap();
        snap.adx = 30.0; // between weak/strong => use trade.tp_atr_mult

        let res = gates::check_gates(&snap, &cfg, "ETH", Some(true), 0.0);
        assert!((res.dynamic_tp_mult - 6.2).abs() < f64::EPSILON);
        assert!(!res.stoch_rsi_active);
    }

    #[test]
    fn test_adapter_pullback_confidence_mapping() {
        let mut cfg = StrategyConfig::default();
        cfg.thresholds.entry.enable_pullback_entries = true;
        cfg.thresholds.entry.pullback_confidence = Confidence::Medium;
        cfg.thresholds.entry.pullback_min_adx = 20.0;
        cfg.thresholds.entry.pullback_rsi_long_min = 50.0;

        let mut snap = bullish_snap();
        snap.adx = 25.0;
        snap.adx_slope = 0.5;
        snap.prev_close = 98.0;
        snap.prev_ema_fast = 98.5;
        snap.close = 99.5;
        snap.ema_fast = 99.0;
        snap.rsi = 52.0;
        snap.macd_hist = 0.2;
        snap.prev_macd_hist = 0.3; // decelerating -> standard accel path blocked

        let slope = 0.001;
        let gates = gates::check_gates(&snap, &cfg, "ETH", Some(true), slope);
        let (sig, conf, adx_thr) = entry::generate_signal(&snap, &gates, &cfg, slope);

        assert_eq!(sig, Signal::Buy);
        assert_eq!(conf, Confidence::Medium);
        assert!((adx_thr - 20.0).abs() < 1e-9);
    }
}
