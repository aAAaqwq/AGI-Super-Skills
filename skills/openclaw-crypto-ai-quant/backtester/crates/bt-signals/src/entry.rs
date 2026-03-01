//! Signal generation — 3 entry modes in priority order.
//!
//! Faithfully mirrors `mei_alpha_v1.analyze()` lines 3539-3690.

use super::gates::GateResult;
use crate::{
    Confidence, IndicatorSnapshotLike, MacdMode, Signal, SignalConfigLike, SnapshotView,
    ThresholdsView,
};

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/// Generate a trading signal from a gate result and indicator snapshot.
///
/// The three entry modes are tried in priority order:
///   standard trend -> pullback continuation -> slow drift.
///
/// Returns `(Signal::Neutral, Confidence::Low)` when no mode fires.
///
/// # Arguments
/// * `snap`               - Current bar indicator snapshot.
/// * `gates`              - Pre-computed gate result from [`super::gates::check_gates`].
/// * `cfg`                - Signal-relevant strategy config view.
/// * `ema_slow_slope_pct` - Pre-computed EMA-slow slope used by slow-drift mode:
///                          `(ema_slow_now - ema_slow_prev_N) / close_now`.
pub fn generate_signal<S, C>(
    snap: &S,
    gates: &GateResult,
    cfg: &C,
    ema_slow_slope_pct: f64,
) -> (Signal, Confidence, f64)
where
    S: IndicatorSnapshotLike,
    C: SignalConfigLike,
{
    let snap = snap.snapshot_view();
    let thresholds = cfg.thresholds_view();
    let thr_entry = thresholds.entry;

    // =================================================================
    // Mode 1: Standard trend entry  (Python lines 3539-3605)
    // =================================================================
    if gates.all_gates_pass {
        if let Some((sig, conf)) = try_standard_entry(&snap, gates, &thresholds) {
            return (sig, conf, gates.effective_min_adx);
        }
    }

    // =================================================================
    // Mode 2: Pullback continuation  (Python lines 3607-3657)
    // =================================================================
    if thr_entry.enable_pullback_entries {
        let pullback_gates_ok = !gates.is_anomaly
            && !gates.is_extended
            && !gates.is_ranging
            && gates.vol_confirm
            && snap.adx >= thr_entry.pullback_min_adx;

        if pullback_gates_ok {
            if let Some((sig, conf)) = try_pullback_entry(&snap, gates, &thresholds) {
                return (sig, conf, thr_entry.pullback_min_adx);
            }
        }
    }

    // =================================================================
    // Mode 3: Slow drift  (Python lines 3659-3690)
    // =================================================================
    if thr_entry.enable_slow_drift_entries {
        let slow_gates_ok = !gates.is_anomaly
            && !gates.is_extended
            && !gates.is_ranging
            && gates.vol_confirm
            && snap.adx >= thr_entry.slow_drift_min_adx;

        if slow_gates_ok {
            if let Some((sig, conf)) =
                try_slow_drift_entry(&snap, gates, &thresholds, ema_slow_slope_pct)
            {
                return (sig, conf, thr_entry.slow_drift_min_adx);
            }
        }
    }

    (Signal::Neutral, Confidence::Low, 0.0)
}

// ---------------------------------------------------------------------------
// Mode 1: Standard trend entry
// ---------------------------------------------------------------------------

/// Standard trend entry -- requires all gates to have passed.
///
/// Uses DRE (Dynamic RSI Elasticity) limits pre-computed in [`GateResult`]:
///   - `rsi_long_limit`  / `rsi_short_limit`
///
/// Checks (in order):
///   1. Alignment + close vs EMA_fast for direction
///   2. RSI vs DRE-interpolated limit
///   3. MACD histogram gate (accel / sign / none)
///   4. StochRSI filter (block overbought long / oversold short)
///   5. BTC alignment
///   6. Volume-based confidence upgrade to High
///
/// Python lines 3564-3605.
fn try_standard_entry(
    snap: &SnapshotView,
    gates: &GateResult,
    thresholds: &ThresholdsView,
) -> Option<(Signal, Confidence)> {
    let thr_entry = thresholds.entry;
    let stoch_thr = thresholds.stoch_rsi;
    let macd_mode = thr_entry.macd_hist_entry_mode;
    let high_conf_mult = thr_entry.high_conf_volume_mult;

    // --- LONG ---
    if gates.bullish_alignment && snap.close > snap.ema_fast {
        if snap.rsi > gates.rsi_long_limit {
            let macd_ok = check_macd_long(macd_mode, snap.macd_hist, snap.prev_macd_hist);
            if macd_ok {
                let stoch_ok = if gates.stoch_rsi_active {
                    gates.stoch_k < stoch_thr.block_long_if_k_gt
                } else {
                    true
                };
                if stoch_ok && gates.btc_ok_long {
                    let conf = if snap.volume > snap.vol_sma * high_conf_mult {
                        Confidence::High
                    } else {
                        Confidence::Medium
                    };
                    return Some((Signal::Buy, conf));
                }
            }
        }
    }
    // --- SHORT (elif in Python — only reached if LONG branch did not enter) ---
    else if gates.bearish_alignment && snap.close < snap.ema_fast {
        if snap.rsi < gates.rsi_short_limit {
            let macd_ok = check_macd_short(macd_mode, snap.macd_hist, snap.prev_macd_hist);
            if macd_ok {
                let stoch_ok = if gates.stoch_rsi_active {
                    gates.stoch_k > stoch_thr.block_short_if_k_lt
                } else {
                    true
                };
                if stoch_ok && gates.btc_ok_short {
                    let conf = if snap.volume > snap.vol_sma * high_conf_mult {
                        Confidence::High
                    } else {
                        Confidence::Medium
                    };
                    return Some((Signal::Sell, conf));
                }
            }
        }
    }

    None
}

// ---------------------------------------------------------------------------
// Mode 2: Pullback continuation
// ---------------------------------------------------------------------------

/// Pullback continuation entry -- catches trend re-entries via EMA cross.
///
/// Gate subset (checked by caller): !anomaly, !extended, !ranging,
/// vol_confirm, ADX >= pullback_min_adx.
///
/// Cross detection:
///   - cross_up: prev_close <= prev_ema_fast AND close > ema_fast
///   - cross_dn: prev_close >= prev_ema_fast AND close < ema_fast
///
/// Python lines 3607-3657.
fn try_pullback_entry(
    snap: &SnapshotView,
    gates: &GateResult,
    thresholds: &ThresholdsView,
) -> Option<(Signal, Confidence)> {
    let thr_entry = thresholds.entry;

    let prev_close = snap.prev_close;
    let prev_ema_fast = snap.prev_ema_fast;

    // Cross up: prev bar was at/below EMA_fast, current bar crossed above.
    let cross_up = (prev_close <= prev_ema_fast) && (snap.close > snap.ema_fast);
    // Cross down: prev bar was at/above EMA_fast, current bar crossed below.
    let cross_dn = (prev_close >= prev_ema_fast) && (snap.close < snap.ema_fast);

    let pullback_conf = thr_entry.pullback_confidence;

    // Long pullback continuation
    if cross_up && gates.bullish_alignment && gates.btc_ok_long {
        let macd_ok = if thr_entry.pullback_require_macd_sign {
            snap.macd_hist > 0.0
        } else {
            true
        };
        if macd_ok && snap.rsi >= thr_entry.pullback_rsi_long_min {
            return Some((Signal::Buy, pullback_conf));
        }
    }
    // Short pullback continuation (elif in Python)
    else if cross_dn && gates.bearish_alignment && gates.btc_ok_short {
        let macd_ok = if thr_entry.pullback_require_macd_sign {
            snap.macd_hist < 0.0
        } else {
            true
        };
        if macd_ok && snap.rsi <= thr_entry.pullback_rsi_short_max {
            return Some((Signal::Sell, pullback_conf));
        }
    }

    None
}

// ---------------------------------------------------------------------------
// Mode 3: Slow drift
// ---------------------------------------------------------------------------

/// Slow drift entry -- captures low-volatility grind regimes.
///
/// Gate subset (checked by caller): !anomaly, !extended, !ranging,
/// vol_confirm, ADX >= slow_drift_min_adx.
///
/// Uses EMA_slow slope to determine grind direction.
/// Always returns `Confidence::Low` when triggered.
///
/// Python lines 3659-3690.
fn try_slow_drift_entry(
    snap: &SnapshotView,
    gates: &GateResult,
    thresholds: &ThresholdsView,
    ema_slow_slope_pct: f64,
) -> Option<(Signal, Confidence)> {
    let thr_entry = thresholds.entry;
    let min_slope = thr_entry.slow_drift_min_slope_pct;

    // Long drift: slope >= +threshold, price above EMA_slow.
    if gates.bullish_alignment
        && snap.close > snap.ema_slow
        && gates.btc_ok_long
        && ema_slow_slope_pct >= min_slope
    {
        let macd_ok = if thr_entry.slow_drift_require_macd_sign {
            snap.macd_hist > 0.0
        } else {
            true
        };
        if macd_ok && snap.rsi >= thr_entry.slow_drift_rsi_long_min {
            return Some((Signal::Buy, Confidence::Low));
        }
    }
    // Short drift: slope <= -threshold, price below EMA_slow.  (elif in Python)
    else if gates.bearish_alignment
        && snap.close < snap.ema_slow
        && gates.btc_ok_short
        && ema_slow_slope_pct <= -min_slope
    {
        let macd_ok = if thr_entry.slow_drift_require_macd_sign {
            snap.macd_hist < 0.0
        } else {
            true
        };
        if macd_ok && snap.rsi <= thr_entry.slow_drift_rsi_short_max {
            return Some((Signal::Sell, Confidence::Low));
        }
    }

    None
}

// ---------------------------------------------------------------------------
// MACD helpers
// ---------------------------------------------------------------------------

/// Check MACD histogram gate for a LONG signal.
///
/// - `Accel`: MACD_hist > prev_MACD_hist  (momentum accelerating)
/// - `Sign`:  MACD_hist > 0               (positive momentum)
/// - `None`:  always true
#[inline]
fn check_macd_long(mode: MacdMode, macd_hist: f64, prev_macd_hist: f64) -> bool {
    match mode {
        MacdMode::Accel => macd_hist > prev_macd_hist,
        MacdMode::Sign => macd_hist > 0.0,
        MacdMode::None => true,
    }
}

/// Check MACD histogram gate for a SHORT signal.
///
/// - `Accel`: MACD_hist < prev_MACD_hist  (momentum accelerating downward)
/// - `Sign`:  MACD_hist < 0               (negative momentum)
/// - `None`:  always true
#[inline]
fn check_macd_short(mode: MacdMode, macd_hist: f64, prev_macd_hist: f64) -> bool {
    match mode {
        MacdMode::Accel => macd_hist < prev_macd_hist,
        MacdMode::Sign => macd_hist < 0.0,
        MacdMode::None => true,
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::gates::check_gates;
    use crate::{MacdMode, SignalConfigView, SnapshotView};

    // -- Helpers --

    /// Build a snapshot that should trigger a standard BUY with default config.
    fn bullish_snap() -> SnapshotView {
        SnapshotView {
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
            vol_sma: 800.0,
            vol_trend: true,
            prev_close: 98.0,
            prev_ema_fast: 98.5,
            prev_ema_slow: 96.8,
            bar_count: 200,
            funding_rate: 0.0,
            prev3_macd_hist: 0.0,
        }
    }

    /// Build a snapshot that should trigger a standard SELL with default config.
    fn bearish_snap() -> SnapshotView {
        SnapshotView {
            close: 95.0,
            high: 96.0,
            low: 94.0,
            open: 96.0,
            volume: 1200.0,
            t: 0,
            ema_slow: 97.0,
            ema_fast: 96.0,
            ema_macro: 99.0,
            adx: 32.0,
            adx_pos: 10.0,
            adx_neg: 22.0,
            adx_slope: 1.5,
            bb_upper: 99.0,
            bb_lower: 93.0,
            bb_width: 0.06,
            bb_width_avg: 0.05,
            bb_width_ratio: 1.2,
            atr: 1.5,
            atr_slope: 0.1,
            avg_atr: 1.4,
            rsi: 42.0,
            stoch_rsi_k: 0.5,
            stoch_rsi_d: 0.5,
            macd_hist: -0.5,
            prev_macd_hist: -0.3,
            prev2_macd_hist: -0.1,
            vol_sma: 800.0,
            vol_trend: true,
            prev_close: 97.0,
            prev_ema_fast: 96.5,
            prev_ema_slow: 97.2,
            bar_count: 200,
            funding_rate: 0.0,
            prev3_macd_hist: 0.0,
        }
    }

    /// Convenience: run gates + signal generation in one call.
    fn run_full(
        snap: &SnapshotView,
        cfg: &SignalConfigView,
        btc_bullish: Option<bool>,
        slope: f64,
    ) -> (Signal, Confidence) {
        let gates = check_gates(snap, cfg, "ETH", btc_bullish, slope);
        let (sig, conf, _) = generate_signal(snap, &gates, cfg, slope);
        (sig, conf)
    }

    // -- Standard trend entry tests --

    #[test]
    fn test_standard_buy() {
        let snap = bullish_snap();
        let cfg = SignalConfigView::default();
        let (sig, conf) = run_full(&snap, &cfg, Some(true), 0.001);
        assert_eq!(sig, Signal::Buy);
        assert_eq!(conf, Confidence::Medium);
    }

    #[test]
    fn test_standard_sell() {
        let snap = bearish_snap();
        let cfg = SignalConfigView::default();
        let (sig, conf) = run_full(&snap, &cfg, Some(false), -0.001);
        assert_eq!(sig, Signal::Sell);
        assert!(matches!(conf, Confidence::Medium));
    }

    #[test]
    fn test_high_volume_upgrades_confidence() {
        let mut snap = bullish_snap();
        snap.volume = 3000.0; // > vol_sma(800) * 2.5 = 2000
        let cfg = SignalConfigView::default();
        let (sig, conf) = run_full(&snap, &cfg, Some(true), 0.001);
        assert_eq!(sig, Signal::Buy);
        assert_eq!(conf, Confidence::High);
    }

    #[test]
    fn test_neutral_when_gates_fail() {
        let mut snap = bullish_snap();
        snap.adx = 15.0; // below min_adx
        snap.adx_slope = -1.0;
        let cfg = SignalConfigView::default();
        let (sig, _) = run_full(&snap, &cfg, Some(true), 0.0);
        assert_eq!(sig, Signal::Neutral);
    }

    #[test]
    fn test_neutral_when_rsi_below_dre_limit() {
        let mut snap = bullish_snap();
        snap.rsi = 40.0; // well below DRE rsi_long_limit
        let cfg = SignalConfigView::default();
        let (sig, _) = run_full(&snap, &cfg, Some(true), 0.0);
        assert_eq!(sig, Signal::Neutral);
    }

    #[test]
    fn test_macd_accel_blocks_decelerating() {
        let mut snap = bullish_snap();
        snap.macd_hist = 0.2;
        snap.prev_macd_hist = 0.3; // hist declining -> accel fails for long
        let cfg = SignalConfigView::default();
        let (sig, _) = run_full(&snap, &cfg, Some(true), 0.001);
        assert_eq!(sig, Signal::Neutral);
    }

    #[test]
    fn test_macd_sign_mode() {
        let mut snap = bullish_snap();
        snap.macd_hist = 0.1;
        snap.prev_macd_hist = 0.5; // accel would fail, but sign mode only checks > 0
        let mut cfg = SignalConfigView::default();
        cfg.thresholds.entry.macd_hist_entry_mode = MacdMode::Sign;
        let (sig, _) = run_full(&snap, &cfg, Some(true), 0.001);
        assert_eq!(sig, Signal::Buy);
    }

    #[test]
    fn test_macd_none_mode() {
        let mut snap = bullish_snap();
        snap.macd_hist = -0.5; // would fail both accel and sign
        snap.prev_macd_hist = 0.5;
        let mut cfg = SignalConfigView::default();
        cfg.thresholds.entry.macd_hist_entry_mode = MacdMode::None;
        let (sig, _) = run_full(&snap, &cfg, Some(true), 0.001);
        assert_eq!(sig, Signal::Buy);
    }

    #[test]
    fn test_stoch_rsi_blocks_long() {
        let mut snap = bullish_snap();
        snap.stoch_rsi_k = 0.90; // above block_long_if_k_gt (0.85)
        let cfg = SignalConfigView::default();
        let (sig, _) = run_full(&snap, &cfg, Some(true), 0.001);
        assert_eq!(sig, Signal::Neutral);
    }

    #[test]
    fn test_stoch_rsi_blocks_short() {
        let mut snap = bearish_snap();
        snap.stoch_rsi_k = 0.10; // below block_short_if_k_lt (0.15)
        let cfg = SignalConfigView::default();
        let (sig, _) = run_full(&snap, &cfg, Some(false), -0.001);
        assert_eq!(sig, Signal::Neutral);
    }

    #[test]
    fn test_btc_bearish_blocks_long() {
        let snap = bullish_snap();
        let mut cfg = SignalConfigView::default();
        cfg.filters.require_btc_alignment = true;
        let (sig, _) = run_full(&snap, &cfg, Some(false), 0.001);
        assert_eq!(sig, Signal::Neutral, "BTC bearish should block ETH long");
    }

    // -- Pullback entry tests --

    #[test]
    fn test_pullback_long() {
        // Set up a cross-up scenario: prev_close <= prev_ema_fast, close > ema_fast.
        let mut snap = bullish_snap();
        snap.adx = 25.0;
        snap.adx_slope = 0.5;
        snap.prev_close = 98.0;
        snap.prev_ema_fast = 98.5;
        snap.close = 99.5;
        snap.ema_fast = 99.0;
        snap.rsi = 52.0;
        snap.macd_hist = 0.2;
        snap.prev_macd_hist = 0.3; // decelerating -> standard accel blocks
        let mut cfg = SignalConfigView::default();
        cfg.thresholds.entry.enable_pullback_entries = true;
        cfg.thresholds.entry.pullback_min_adx = 20.0;
        cfg.thresholds.entry.pullback_rsi_long_min = 50.0;
        let (sig, conf) = run_full(&snap, &cfg, Some(true), 0.001);
        // Standard entry should fail (MACD decel), pullback should fire.
        assert_eq!(sig, Signal::Buy);
        assert_eq!(conf, Confidence::Low);
    }

    #[test]
    fn test_pullback_short() {
        let mut snap = bearish_snap();
        // Cross-dn: prev_close >= prev_ema_fast AND close < ema_fast
        snap.prev_close = 97.0;
        snap.prev_ema_fast = 96.5;
        snap.close = 95.0;
        snap.ema_fast = 96.0;
        snap.rsi = 48.0;
        snap.macd_hist = -0.2;
        snap.prev_macd_hist = -0.1; // decel for short accel mode
        snap.adx = 25.0;
        snap.adx_slope = -0.5; // not rising, not saturated -> is_trending_up = false
        let mut cfg = SignalConfigView::default();
        cfg.thresholds.entry.enable_pullback_entries = true;
        cfg.thresholds.entry.pullback_min_adx = 20.0;
        cfg.thresholds.entry.pullback_rsi_short_max = 50.0;
        // Standard blocked because is_trending_up = false (adx_slope < 0, adx < 40)
        // Use btc_bullish=Some(false) so btc_ok_short = true (required for short signal)
        let (sig, conf) = run_full(&snap, &cfg, Some(false), 0.0);
        assert_eq!(sig, Signal::Sell);
        assert_eq!(conf, Confidence::Low);
    }

    #[test]
    fn test_pullback_blocked_by_anomaly() {
        let mut snap = bullish_snap();
        snap.prev_close = 100.0;
        snap.close = 115.0; // 15% -> anomaly
        let mut cfg = SignalConfigView::default();
        cfg.thresholds.entry.enable_pullback_entries = true;
        let (sig, _) = run_full(&snap, &cfg, Some(true), 0.0);
        assert_eq!(sig, Signal::Neutral);
    }

    #[test]
    fn test_pullback_blocked_by_low_adx() {
        let mut snap = bullish_snap();
        snap.prev_close = 98.0;
        snap.prev_ema_fast = 98.5;
        snap.close = 99.5;
        snap.ema_fast = 99.0;
        snap.rsi = 52.0;
        snap.macd_hist = 0.2;
        snap.prev_macd_hist = 0.3;
        snap.adx = 15.0; // below pullback_min_adx
        snap.adx_slope = -1.0;
        let mut cfg = SignalConfigView::default();
        cfg.thresholds.entry.enable_pullback_entries = true;
        cfg.thresholds.entry.pullback_min_adx = 20.0;
        let (sig, _) = run_full(&snap, &cfg, Some(true), 0.0);
        assert_eq!(sig, Signal::Neutral);
    }

    // -- Slow drift tests --

    #[test]
    fn test_slow_drift_long() {
        let mut snap = bullish_snap();
        snap.adx = 15.0; // below standard min_adx (22) but above slow_drift_min_adx (10)
        snap.adx_slope = -0.5; // not rising
        snap.rsi = 52.0;
        snap.macd_hist = 0.1;
        snap.close = 98.0;
        snap.ema_slow = 97.0;
        let mut cfg = SignalConfigView::default();
        cfg.thresholds.entry.enable_slow_drift_entries = true;
        cfg.thresholds.entry.slow_drift_min_adx = 10.0;
        cfg.thresholds.entry.slow_drift_rsi_long_min = 50.0;
        cfg.thresholds.entry.slow_drift_min_slope_pct = 0.0006;
        let slope = 0.001; // above 0.0006
        let gates = check_gates(&snap, &cfg, "ETH", Some(true), slope);
        assert!(
            !gates.all_gates_pass,
            "Standard gates should fail (low ADX)"
        );
        let (sig, conf, adx_thr) = generate_signal(&snap, &gates, &cfg, slope);
        assert_eq!(sig, Signal::Buy);
        assert_eq!(conf, Confidence::Low);
        assert!(
            (adx_thr - 10.0).abs() < 1e-9,
            "slow drift should use slow_drift_min_adx"
        );
    }

    #[test]
    fn test_slow_drift_short() {
        let mut snap = bearish_snap();
        snap.adx = 15.0;
        snap.adx_slope = -0.5;
        snap.rsi = 48.0;
        snap.macd_hist = -0.1;
        snap.close = 96.0;
        snap.ema_slow = 99.0;
        snap.ema_fast = 97.0;
        let mut cfg = SignalConfigView::default();
        cfg.thresholds.entry.enable_slow_drift_entries = true;
        cfg.thresholds.entry.slow_drift_min_adx = 10.0;
        cfg.thresholds.entry.slow_drift_rsi_short_max = 50.0;
        cfg.thresholds.entry.slow_drift_min_slope_pct = 0.0006;
        let slope = -0.001; // below -0.0006
                            // Use btc_bullish=Some(false) so btc_ok_short = true (required for short signal)
        let gates = check_gates(&snap, &cfg, "ETH", Some(false), slope);
        let (sig, conf, _) = generate_signal(&snap, &gates, &cfg, slope);
        assert_eq!(sig, Signal::Sell);
        assert_eq!(conf, Confidence::Low);
    }

    #[test]
    fn test_slow_drift_blocked_when_slope_too_flat() {
        let mut snap = bullish_snap();
        snap.adx = 15.0;
        snap.adx_slope = -0.5;
        snap.close = 98.0;
        snap.ema_slow = 97.0;
        snap.macd_hist = 0.1;
        let mut cfg = SignalConfigView::default();
        cfg.thresholds.entry.enable_slow_drift_entries = true;
        cfg.thresholds.entry.slow_drift_min_slope_pct = 0.0006;
        let slope = 0.0003; // below 0.0006
        let (sig, _) = run_full(&snap, &cfg, Some(true), slope);
        assert_eq!(sig, Signal::Neutral);
    }

    #[test]
    fn test_slow_drift_blocked_by_macd_sign() {
        let mut snap = bullish_snap();
        snap.adx = 15.0;
        snap.adx_slope = -0.5;
        snap.rsi = 52.0;
        snap.macd_hist = -0.1; // negative -> fails MACD sign for long
        snap.close = 98.0;
        snap.ema_slow = 97.0;
        let mut cfg = SignalConfigView::default();
        cfg.thresholds.entry.enable_slow_drift_entries = true;
        cfg.thresholds.entry.slow_drift_min_adx = 10.0;
        cfg.thresholds.entry.slow_drift_require_macd_sign = true;
        cfg.thresholds.entry.slow_drift_min_slope_pct = 0.0006;
        let slope = 0.001;
        let (sig, _) = run_full(&snap, &cfg, Some(true), slope);
        assert_eq!(sig, Signal::Neutral);
    }

    // -- Priority order tests --

    #[test]
    fn test_standard_takes_priority_over_pullback() {
        // Snapshot that qualifies for both standard and pullback
        let mut snap = bullish_snap();
        snap.prev_close = 98.0;
        snap.prev_ema_fast = 98.5;
        snap.close = 100.0;
        snap.ema_fast = 99.0;
        let mut cfg = SignalConfigView::default();
        cfg.thresholds.entry.enable_pullback_entries = true;
        let (sig, conf) = run_full(&snap, &cfg, Some(true), 0.001);
        // Standard fires first with Medium confidence (not Low from pullback)
        assert_eq!(sig, Signal::Buy);
        assert_eq!(conf, Confidence::Medium);
    }

    #[test]
    fn test_pullback_takes_priority_over_slow_drift() {
        let mut snap = bullish_snap();
        snap.prev_close = 98.0;
        snap.prev_ema_fast = 98.5;
        snap.close = 99.5;
        snap.ema_fast = 99.0;
        snap.rsi = 52.0;
        snap.macd_hist = 0.2;
        snap.prev_macd_hist = 0.3; // standard blocked by MACD decel
        snap.adx = 25.0;
        snap.adx_slope = 0.5;
        let mut cfg = SignalConfigView::default();
        cfg.thresholds.entry.enable_pullback_entries = true;
        cfg.thresholds.entry.pullback_min_adx = 20.0;
        cfg.thresholds.entry.pullback_rsi_long_min = 50.0;
        cfg.thresholds.entry.enable_slow_drift_entries = true;
        cfg.thresholds.entry.slow_drift_min_adx = 10.0;
        cfg.thresholds.entry.slow_drift_rsi_long_min = 50.0;
        cfg.thresholds.entry.slow_drift_min_slope_pct = 0.0006;
        let (sig, conf) = run_full(&snap, &cfg, Some(true), 0.001);
        // Pullback fires first (confidence from config, default Low)
        assert_eq!(sig, Signal::Buy);
        assert_eq!(conf, Confidence::Low);
    }

    #[test]
    fn test_neutral_when_nothing_qualifies() {
        let mut snap = bullish_snap();
        snap.rsi = 50.0; // neutral zone -> ranging + below DRE limit
        snap.adx = 18.0;
        snap.bb_width_ratio = 0.7;
        let cfg = SignalConfigView::default();
        let (sig, _) = run_full(&snap, &cfg, Some(true), 0.0);
        assert_eq!(sig, Signal::Neutral);
    }

    // -- MACD helper unit tests --

    #[test]
    fn test_check_macd_long_helpers() {
        assert!(check_macd_long(MacdMode::Accel, 0.5, 0.3));
        assert!(!check_macd_long(MacdMode::Accel, 0.3, 0.5));
        assert!(check_macd_long(MacdMode::Sign, 0.1, -999.0));
        assert!(!check_macd_long(MacdMode::Sign, -0.1, 999.0));
        assert!(check_macd_long(MacdMode::None, -100.0, 100.0));
    }

    #[test]
    fn test_check_macd_short_helpers() {
        assert!(check_macd_short(MacdMode::Accel, -0.5, -0.3));
        assert!(!check_macd_short(MacdMode::Accel, -0.3, -0.5));
        assert!(check_macd_short(MacdMode::Sign, -0.1, 999.0));
        assert!(!check_macd_short(MacdMode::Sign, 0.1, -999.0));
        assert!(check_macd_short(MacdMode::None, 100.0, -100.0));
    }
}
