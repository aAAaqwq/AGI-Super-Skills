//! Kernel-native entry signal evaluation.
//!
//! Delegates to `bt_signals::entry::generate_signal()` so the kernel can
//! compute Buy/Sell/Neutral from raw indicator data instead of relying on the
//! engine to pre-compute the signal direction.

use crate::indicators::IndicatorSnapshot;
use crate::signals::gates::GateResult;
use bt_signals::{
    Confidence, EntryThresholdsView, FiltersView, MacdMode, Signal, SignalConfigView,
    StochRsiThresholdsView, ThresholdsView, TradeView,
};
use serde::{Deserialize, Serialize};

// ═══════════════════════════════════════════════════════════════════════════
// EntryParams — serializable config for kernel entry evaluation
// ═══════════════════════════════════════════════════════════════════════════

/// Entry evaluation parameters for the kernel.
/// When present in KernelParams, the kernel can evaluate entry signals
/// from raw indicator data (Evaluate mode).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EntryParams {
    /// MACD gate mode: 0 = Accel, 1 = Sign, 2 = None
    pub macd_mode: u8,

    /// StochRSI thresholds
    pub stoch_block_long_gt: f64,
    pub stoch_block_short_lt: f64,

    /// Volume confidence
    pub high_conf_volume_mult: f64,

    /// Pullback entries
    pub enable_pullback: bool,
    pub pullback_confidence: u8, // 0=Low, 1=Med, 2=High
    pub pullback_min_adx: f64,
    pub pullback_rsi_long_min: f64,
    pub pullback_rsi_short_max: f64,
    pub pullback_require_macd_sign: bool,

    /// Slow drift entries
    pub enable_slow_drift: bool,
    pub slow_drift_min_slope_pct: f64,
    pub slow_drift_min_adx: f64,
    pub slow_drift_rsi_long_min: f64,
    pub slow_drift_rsi_short_max: f64,
    pub slow_drift_require_macd_sign: bool,
}

impl Default for EntryParams {
    fn default() -> Self {
        let entry_defaults = EntryThresholdsView::default();
        let stoch_defaults = StochRsiThresholdsView::default();
        Self {
            macd_mode: 0, // Accel
            stoch_block_long_gt: stoch_defaults.block_long_if_k_gt,
            stoch_block_short_lt: stoch_defaults.block_short_if_k_lt,
            high_conf_volume_mult: entry_defaults.high_conf_volume_mult,
            enable_pullback: entry_defaults.enable_pullback_entries,
            pullback_confidence: 0, // Low
            pullback_min_adx: entry_defaults.pullback_min_adx,
            pullback_rsi_long_min: entry_defaults.pullback_rsi_long_min,
            pullback_rsi_short_max: entry_defaults.pullback_rsi_short_max,
            pullback_require_macd_sign: entry_defaults.pullback_require_macd_sign,
            enable_slow_drift: entry_defaults.enable_slow_drift_entries,
            slow_drift_min_slope_pct: entry_defaults.slow_drift_min_slope_pct,
            slow_drift_min_adx: entry_defaults.slow_drift_min_adx,
            slow_drift_rsi_long_min: entry_defaults.slow_drift_rsi_long_min,
            slow_drift_rsi_short_max: entry_defaults.slow_drift_rsi_short_max,
            slow_drift_require_macd_sign: entry_defaults.slow_drift_require_macd_sign,
        }
    }
}

impl EntryParams {
    fn to_macd_mode(&self) -> MacdMode {
        match self.macd_mode {
            0 => MacdMode::Accel,
            1 => MacdMode::Sign,
            _ => MacdMode::None,
        }
    }

    fn to_pullback_confidence(&self) -> Confidence {
        match self.pullback_confidence {
            0 => Confidence::Low,
            1 => Confidence::Medium,
            _ => Confidence::High,
        }
    }

    fn to_signal_config_view(&self) -> SignalConfigView {
        SignalConfigView {
            trade: TradeView::default(),
            filters: FiltersView::default(),
            thresholds: ThresholdsView {
                entry: EntryThresholdsView {
                    macd_hist_entry_mode: self.to_macd_mode(),
                    high_conf_volume_mult: self.high_conf_volume_mult,
                    enable_pullback_entries: self.enable_pullback,
                    pullback_confidence: self.to_pullback_confidence(),
                    pullback_min_adx: self.pullback_min_adx,
                    pullback_rsi_long_min: self.pullback_rsi_long_min,
                    pullback_rsi_short_max: self.pullback_rsi_short_max,
                    pullback_require_macd_sign: self.pullback_require_macd_sign,
                    enable_slow_drift_entries: self.enable_slow_drift,
                    slow_drift_min_slope_pct: self.slow_drift_min_slope_pct,
                    slow_drift_min_adx: self.slow_drift_min_adx,
                    slow_drift_rsi_long_min: self.slow_drift_rsi_long_min,
                    slow_drift_rsi_short_max: self.slow_drift_rsi_short_max,
                    slow_drift_require_macd_sign: self.slow_drift_require_macd_sign,
                    ..EntryThresholdsView::default()
                },
                stoch_rsi: StochRsiThresholdsView {
                    block_long_if_k_gt: self.stoch_block_long_gt,
                    block_short_if_k_lt: self.stoch_block_short_lt,
                },
                ..ThresholdsView::default()
            },
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// KernelEntryResult
// ═══════════════════════════════════════════════════════════════════════════

#[derive(Debug, Clone, PartialEq)]
pub struct KernelEntryResult {
    pub signal: Signal,
    /// 0=Low, 1=Medium, 2=High
    pub confidence: u8,
    pub entry_adx_threshold: f64,
}

// ═══════════════════════════════════════════════════════════════════════════
// evaluate_entry
// ═══════════════════════════════════════════════════════════════════════════

pub fn evaluate_entry(
    snap: &IndicatorSnapshot,
    gate_result: &GateResult,
    params: &EntryParams,
    ema_slow_slope_pct: f64,
) -> KernelEntryResult {
    use crate::signals::entry;

    let cfg = params.to_signal_config_view();
    let (signal, confidence, entry_adx_threshold) =
        entry::generate_signal(snap, gate_result, &cfg, ema_slow_slope_pct);
    KernelEntryResult {
        signal,
        confidence: confidence as u8,
        entry_adx_threshold,
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;
    use crate::indicators::IndicatorSnapshot;
    use crate::signals::gates::GateResult;

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

    fn bearish_snap() -> IndicatorSnapshot {
        IndicatorSnapshot {
            close: 95.0,
            high: 96.0,
            low: 94.0,
            open: 96.0,
            volume: 1200.0,
            t: 0,
            ema_slow: 98.0,
            ema_fast: 96.5,
            ema_macro: 100.0,
            adx: 32.0,
            adx_pos: 10.0,
            adx_neg: 22.0,
            adx_slope: 1.5,
            bb_upper: 100.0,
            bb_lower: 93.0,
            bb_width: 0.07,
            bb_width_avg: 0.05,
            bb_width_ratio: 1.4,
            atr: 1.5,
            atr_slope: 0.1,
            avg_atr: 1.4,
            rsi: 38.0,
            stoch_rsi_k: 0.2,
            stoch_rsi_d: 0.2,
            macd_hist: -0.5,
            prev_macd_hist: -0.3,
            prev2_macd_hist: -0.1,
            prev3_macd_hist: 0.0,
            vol_sma: 800.0,
            vol_trend: true,
            prev_close: 97.0,
            prev_ema_fast: 97.0,
            prev_ema_slow: 98.2,
            bar_count: 200,
            funding_rate: 0.0,
        }
    }

    fn passing_gates_bullish() -> GateResult {
        GateResult {
            is_ranging: false,
            is_anomaly: false,
            is_extended: false,
            vol_confirm: true,
            is_trending_up: true,
            adx_above_min: true,
            bullish_alignment: true,
            bearish_alignment: false,
            btc_ok_long: true,
            btc_ok_short: true,
            effective_min_adx: 22.0,
            bb_width_ratio: 1.2,
            dynamic_tp_mult: 5.0,
            rsi_long_limit: 55.0,
            rsi_short_limit: 45.0,
            stoch_k: 0.5,
            stoch_d: 0.5,
            stoch_rsi_active: false,
            all_gates_pass: true,
        }
    }

    fn passing_gates_bearish() -> GateResult {
        GateResult {
            is_ranging: false,
            is_anomaly: false,
            is_extended: false,
            vol_confirm: true,
            is_trending_up: true,
            adx_above_min: true,
            bullish_alignment: false,
            bearish_alignment: true,
            btc_ok_long: true,
            btc_ok_short: true,
            effective_min_adx: 22.0,
            bb_width_ratio: 1.2,
            dynamic_tp_mult: 5.0,
            rsi_long_limit: 55.0,
            rsi_short_limit: 45.0,
            stoch_k: 0.5,
            stoch_d: 0.5,
            stoch_rsi_active: false,
            all_gates_pass: true,
        }
    }

    fn failing_gates() -> GateResult {
        GateResult {
            is_ranging: true,
            is_anomaly: false,
            is_extended: false,
            vol_confirm: true,
            is_trending_up: true,
            adx_above_min: true,
            bullish_alignment: false,
            bearish_alignment: false,
            btc_ok_long: true,
            btc_ok_short: true,
            effective_min_adx: 22.0,
            bb_width_ratio: 0.6,
            dynamic_tp_mult: 5.0,
            rsi_long_limit: 55.0,
            rsi_short_limit: 45.0,
            stoch_k: 0.5,
            stoch_d: 0.5,
            stoch_rsi_active: false,
            all_gates_pass: false,
        }
    }

    #[test]
    fn evaluate_entry_standard_buy() {
        let snap = bullish_snap();
        let gates = passing_gates_bullish();
        let params = EntryParams::default();
        let result = evaluate_entry(&snap, &gates, &params, 0.0);
        assert_eq!(result.signal, Signal::Buy);
        assert!(
            result.confidence >= 1,
            "should be at least Medium confidence"
        );
    }

    #[test]
    fn evaluate_entry_standard_sell() {
        let snap = bearish_snap();
        let gates = passing_gates_bearish();
        let params = EntryParams::default();
        let result = evaluate_entry(&snap, &gates, &params, 0.0);
        assert_eq!(result.signal, Signal::Sell);
        assert!(
            result.confidence >= 1,
            "should be at least Medium confidence"
        );
    }

    #[test]
    fn evaluate_entry_neutral_when_gates_fail() {
        let snap = bullish_snap();
        let gates = failing_gates();
        let params = EntryParams::default(); // pullback + drift disabled by default
        let result = evaluate_entry(&snap, &gates, &params, 0.0);
        assert_eq!(result.signal, Signal::Neutral);
    }

    #[test]
    fn evaluate_entry_pullback() {
        // Gates fail (ranging) but pullback gate subset passes.
        // We need: not anomaly, not extended, not ranging, vol_confirm, adx >= pullback_min_adx.
        // So we need a gate_result where all_gates_pass=false but the individual gates
        // that matter for pullback are OK (not ranging, not anomaly, not extended, vol_confirm).
        let snap = bullish_snap();
        let gates = GateResult {
            is_ranging: false,
            is_anomaly: false,
            is_extended: false,
            vol_confirm: true,
            is_trending_up: false, // this makes all_gates_pass=false for standard entry
            adx_above_min: true,
            bullish_alignment: true,
            bearish_alignment: false,
            btc_ok_long: true,
            btc_ok_short: true,
            effective_min_adx: 22.0,
            bb_width_ratio: 1.2,
            dynamic_tp_mult: 5.0,
            rsi_long_limit: 55.0,
            rsi_short_limit: 45.0,
            stoch_k: 0.5,
            stoch_d: 0.5,
            stoch_rsi_active: false,
            all_gates_pass: false,
        };
        let mut params = EntryParams::default();
        params.enable_pullback = true;
        params.pullback_min_adx = 20.0;
        params.pullback_rsi_long_min = 50.0;
        params.pullback_require_macd_sign = true;

        let result = evaluate_entry(&snap, &gates, &params, 0.0);
        assert_eq!(result.signal, Signal::Buy);
        assert_eq!(result.confidence, Confidence::Low as u8);
    }

    #[test]
    fn evaluate_entry_slow_drift() {
        let mut snap = bullish_snap();
        snap.adx = 15.0; // low ADX for drift
        snap.adx_slope = 0.5;

        let gates = GateResult {
            is_ranging: false,
            is_anomaly: false,
            is_extended: false,
            vol_confirm: true,
            is_trending_up: false,
            adx_above_min: false,
            bullish_alignment: true,
            bearish_alignment: false,
            btc_ok_long: true,
            btc_ok_short: true,
            effective_min_adx: 22.0,
            bb_width_ratio: 1.2,
            dynamic_tp_mult: 5.0,
            rsi_long_limit: 55.0,
            rsi_short_limit: 45.0,
            stoch_k: 0.5,
            stoch_d: 0.5,
            stoch_rsi_active: false,
            all_gates_pass: false,
        };

        let mut params = EntryParams::default();
        params.enable_pullback = false; // skip pullback
        params.enable_slow_drift = true;
        params.slow_drift_min_adx = 10.0;
        params.slow_drift_min_slope_pct = 0.0005;
        params.slow_drift_rsi_long_min = 50.0;
        params.slow_drift_require_macd_sign = true;

        // Provide slope large enough to trigger drift
        let result = evaluate_entry(&snap, &gates, &params, 0.001);
        assert_eq!(result.signal, Signal::Buy);
        assert_eq!(result.confidence, Confidence::Low as u8);
    }
}
