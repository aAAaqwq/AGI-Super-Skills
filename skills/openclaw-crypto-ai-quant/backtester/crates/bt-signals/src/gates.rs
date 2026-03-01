//! Entry gate evaluation — 8 boolean gates plus derived scalars.
//!
//! Faithfully mirrors `mei_alpha_v1.analyze()` lines 3344-3537.

use crate::{IndicatorSnapshotLike, SignalConfigLike};
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

/// Outcome of running every entry gate on the current bar.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct GateResult {
    // --- Individual gate flags ---
    pub is_ranging: bool,
    pub is_anomaly: bool,
    pub is_extended: bool,
    pub vol_confirm: bool,
    pub is_trending_up: bool,
    pub adx_above_min: bool,

    // --- Alignment / directional ---
    pub bullish_alignment: bool,
    pub bearish_alignment: bool,
    pub btc_ok_long: bool,
    pub btc_ok_short: bool,

    // --- Derived scalars ---
    pub effective_min_adx: f64,
    pub bb_width_ratio: f64,
    pub dynamic_tp_mult: f64,

    // --- DRE (Dynamic RSI Elasticity) limits ---
    // Linear interpolation of RSI entry limits between weak/strong based on ADX.
    // Only semantically meaningful when `all_gates_pass` is true (standard trend
    // entry), but always computed for audit / debug.
    pub rsi_long_limit: f64,
    pub rsi_short_limit: f64,

    // --- StochRSI values (passed through from snapshot) ---
    pub stoch_k: f64,
    pub stoch_d: f64,
    /// Whether the StochRSI filter is active (mirrors `filters.use_stoch_rsi_filter`).
    pub stoch_rsi_active: bool,

    /// True when *all* gates required for a standard trend entry pass:
    ///   adx_above_min AND !ranging AND !anomaly AND !extended AND vol_confirm AND is_trending_up
    pub all_gates_pass: bool,
}

// ---------------------------------------------------------------------------
// Gate evaluation
// ---------------------------------------------------------------------------

/// Evaluate all 8 entry gates and return the combined result.
///
/// # Arguments
/// * `snap`               - Current bar indicator snapshot.
/// * `cfg`                - Signal-relevant strategy config view.
/// * `symbol`             - The symbol being analysed (e.g. "ETH").
/// * `btc_bullish`        - BTC trend direction (`None` = unknown / no data).
/// * `ema_slow_slope_pct` - Pre-computed EMA-slow slope:
///                          `(ema_slow_now - ema_slow_prev_N) / close_now`
///                          over the configured `slow_drift_slope_window`.
pub fn check_gates<S, C>(
    snap: &S,
    cfg: &C,
    symbol: &str,
    btc_bullish: Option<bool>,
    ema_slow_slope_pct: f64,
) -> GateResult
where
    S: IndicatorSnapshotLike,
    C: SignalConfigLike,
{
    let snap = snap.snapshot_view();
    let flt = cfg.filters_view();
    let thr = cfg.thresholds_view();
    let thr_entry = thr.entry;
    let thr_ranging = thr.ranging;
    let tp = thr.tp_and_momentum;
    let trade = cfg.trade_view();

    // -------------------------------------------------------------------
    // Gate 1: Ranging filter (vote system)
    //   Python lines 3344-3363
    // -------------------------------------------------------------------
    let bb_width_ratio = snap.bb_width_ratio;
    let mut is_ranging = false;
    if flt.enable_ranging_filter {
        let min_signals = thr_ranging.min_signals.max(1);
        let mut votes: u32 = 0;

        // Vote 1: ADX below threshold
        if snap.adx < thr_ranging.adx_below {
            votes += 1;
        }
        // Vote 2: BB width ratio below threshold
        if bb_width_ratio < thr_ranging.bb_width_ratio_below {
            votes += 1;
        }
        // Vote 3: RSI in neutral zone
        if snap.rsi > thr_ranging.rsi_low && snap.rsi < thr_ranging.rsi_high {
            votes += 1;
        }

        is_ranging = votes >= min_signals as u32;
    }

    // -------------------------------------------------------------------
    // Gate 2: Anomaly filter
    //   Python lines 3365-3371
    // -------------------------------------------------------------------
    let is_anomaly = if flt.enable_anomaly_filter {
        let a = thr.anomaly;
        let price_change_pct = if snap.prev_close > 0.0 {
            (snap.close - snap.prev_close).abs() / snap.prev_close
        } else {
            0.0
        };
        let ema_dev_pct = if snap.ema_fast > 0.0 {
            (snap.close - snap.ema_fast).abs() / snap.ema_fast
        } else {
            0.0
        };
        price_change_pct > a.price_change_pct_gt || ema_dev_pct > a.ema_fast_dev_pct_gt
    } else {
        false
    };

    // -------------------------------------------------------------------
    // Gate 3: Extension filter (distance from EMA_fast)
    //   Python lines 3533-3537
    // -------------------------------------------------------------------
    let is_extended = if flt.enable_extension_filter {
        let dist = if snap.ema_fast > 0.0 {
            (snap.close - snap.ema_fast).abs() / snap.ema_fast
        } else {
            0.0
        };
        dist > thr_entry.max_dist_ema_fast
    } else {
        false
    };

    // -------------------------------------------------------------------
    // Gate 4: Volume confirmation (optional)
    //   Python lines 3432-3440
    //
    //   NOTE: The Python checks prev["Volume"] > prev["vol_sma"] for the
    //   include_prev path. The indicator snapshot does not carry previous-bar
    //   volume/vol_sma separately. We approximate: when `vol_confirm_include_prev`
    //   is true we relax the gate to require *either* current vol > vol_sma
    //   (matching "current bar passes") OR vol_trend (the multi-bar rolling
    //   volume trend, which captures the essence of "recent bars had strong
    //   volume"). When `vol_confirm_include_prev` is false we require both
    //   current vol > vol_sma AND vol_trend — the strict path.
    // -------------------------------------------------------------------
    let vol_confirm = if flt.require_volume_confirmation {
        if flt.vol_confirm_include_prev {
            // Relaxed: current bar volume above SMA, OR vol_trend already true
            // (vol_trend is a rolling N-bar metric, so it implicitly reflects
            // whether "current or previous" bars had strong volume).
            (snap.volume > snap.vol_sma) || snap.vol_trend
        } else {
            (snap.volume > snap.vol_sma) && snap.vol_trend
        }
    } else {
        true // gate disabled -> passes
    };

    // -------------------------------------------------------------------
    // Gate 5: ADX rising (or saturated)
    //   Python lines 3426-3430
    // -------------------------------------------------------------------
    let is_trending_up = if flt.require_adx_rising {
        let saturation = flt.adx_rising_saturation;
        // snap.adx_slope == adx - prev_adx, so adx_slope > 0 <=> ADX rising.
        (snap.adx_slope > 0.0) || (snap.adx > saturation)
    } else {
        true
    };

    // -------------------------------------------------------------------
    // Gate 6: ADX threshold (effective_min_adx with TMC + AVE)
    //   Python lines 3383-3424
    // -------------------------------------------------------------------
    let mut effective_min_adx = thr_entry.min_adx;

    // TMC: Trend Momentum Confirmation (v4.6)
    //   If ADX slope > 0.5, cap effective_min_adx at 25.0.
    if snap.adx_slope > 0.5 {
        effective_min_adx = effective_min_adx.min(25.0);
    }

    // AVE: Adaptive Volatility Entry (v4.7)
    //   If ATR / avg_ATR > threshold, multiply effective_min_adx by ave_adx_mult.
    if thr_entry.ave_enabled && snap.avg_atr > 0.0 {
        let atr_ratio = snap.atr / snap.avg_atr;
        if atr_ratio > thr_entry.ave_atr_ratio_gt {
            let mult = if thr_entry.ave_adx_mult > 0.0 {
                thr_entry.ave_adx_mult
            } else {
                1.0
            };
            effective_min_adx *= mult;
        }
    }

    let adx_above_min = snap.adx > effective_min_adx;

    // -------------------------------------------------------------------
    // Gate 7: Macro alignment (EMA cross + optional macro EMA)
    //   Python lines 3448-3452
    // -------------------------------------------------------------------
    let mut bullish_alignment = snap.ema_fast > snap.ema_slow;
    let mut bearish_alignment = snap.ema_fast < snap.ema_slow;

    if flt.require_macro_alignment {
        bullish_alignment = bullish_alignment && (snap.ema_slow > snap.ema_macro);
        bearish_alignment = bearish_alignment && (snap.ema_slow < snap.ema_macro);
    }

    // -------------------------------------------------------------------
    // Gate 8: BTC alignment (optional)
    //   Python lines 3454-3461
    // -------------------------------------------------------------------
    let sym_upper = symbol.to_ascii_uppercase();
    let require_btc = flt.require_btc_alignment;
    let btc_adx_override = thr_entry.btc_adx_override;

    let btc_ok_long = !require_btc
        || sym_upper == "BTC"
        || btc_bullish.is_none()
        || btc_bullish == Some(true)
        || snap.adx > btc_adx_override;

    let btc_ok_short = !require_btc
        || sym_upper == "BTC"
        || btc_bullish.is_none()
        || btc_bullish == Some(false)
        || snap.adx > btc_adx_override;

    // -------------------------------------------------------------------
    // Slow-drift ranging override
    //   Python lines 3524-3526
    //   If slow drift enabled and EMA_slow slope exceeds threshold, clear ranging.
    // -------------------------------------------------------------------
    if thr_entry.enable_slow_drift_entries
        && is_ranging
        && ema_slow_slope_pct.abs() >= thr_entry.slow_drift_min_slope_pct
    {
        is_ranging = false;
    }

    // -------------------------------------------------------------------
    // Dynamic TP multiplier
    //   Python lines 3373-3379
    // -------------------------------------------------------------------
    let dynamic_tp_mult = if snap.adx > tp.adx_strong_gt {
        tp.tp_mult_strong
    } else if snap.adx < tp.adx_weak_lt {
        tp.tp_mult_weak
    } else {
        trade.tp_atr_mult
    };

    // -------------------------------------------------------------------
    // DRE (Dynamic RSI Elasticity) — v4.1
    //   Python lines 3551-3560
    //   Linear interpolation of RSI limits between weak and strong based on ADX.
    // -------------------------------------------------------------------
    let adx_min = thr_entry.min_adx;
    let adx_max = if tp.adx_strong_gt > adx_min {
        tp.adx_strong_gt
    } else {
        adx_min + 1.0
    };
    let weight = ((snap.adx - adx_min) / (adx_max - adx_min)).clamp(0.0, 1.0);
    let rsi_long_limit = tp.rsi_long_weak + weight * (tp.rsi_long_strong - tp.rsi_long_weak);
    let rsi_short_limit = tp.rsi_short_weak + weight * (tp.rsi_short_strong - tp.rsi_short_weak);

    // -------------------------------------------------------------------
    // StochRSI passthrough
    // -------------------------------------------------------------------
    let stoch_rsi_active = flt.use_stoch_rsi_filter;
    let stoch_k = snap.stoch_rsi_k;
    let stoch_d = snap.stoch_rsi_d;

    // -------------------------------------------------------------------
    // Combined check: all gates required for standard trend entry
    // -------------------------------------------------------------------
    let all_gates_pass = adx_above_min
        && !is_ranging
        && !is_anomaly
        && !is_extended
        && vol_confirm
        && is_trending_up;

    GateResult {
        is_ranging,
        is_anomaly,
        is_extended,
        vol_confirm,
        is_trending_up,
        adx_above_min,
        bullish_alignment,
        bearish_alignment,
        btc_ok_long,
        btc_ok_short,
        effective_min_adx,
        bb_width_ratio,
        dynamic_tp_mult,
        rsi_long_limit,
        rsi_short_limit,
        stoch_k,
        stoch_d,
        stoch_rsi_active,
        all_gates_pass,
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{SignalConfigView, SnapshotView};

    /// Helper: default snapshot with sensible trending values.
    fn trending_snap() -> SnapshotView {
        SnapshotView {
            close: 100.0,
            high: 101.0,
            low: 99.0,
            open: 100.0,
            volume: 1000.0,
            t: 0,
            ema_slow: 98.0,
            ema_fast: 99.0,
            ema_macro: 95.0,
            adx: 30.0,
            adx_pos: 20.0,
            adx_neg: 10.0,
            adx_slope: 1.0,
            bb_upper: 102.0,
            bb_lower: 98.0,
            bb_width: 0.04,
            bb_width_avg: 0.03,
            bb_width_ratio: 1.33,
            atr: 1.5,
            atr_slope: 0.1,
            avg_atr: 1.4,
            rsi: 55.0,
            stoch_rsi_k: 0.5,
            stoch_rsi_d: 0.5,
            macd_hist: 0.5,
            prev_macd_hist: 0.3,
            prev2_macd_hist: 0.1,
            vol_sma: 800.0,
            vol_trend: true,
            prev_close: 99.5,
            prev_ema_fast: 98.5,
            prev_ema_slow: 97.8,
            bar_count: 200,
            funding_rate: 0.0,
            prev3_macd_hist: 0.0,
        }
    }

    #[test]
    fn test_all_gates_pass_trending() {
        let snap = trending_snap();
        let cfg = SignalConfigView::default();
        let res = check_gates(&snap, &cfg, "ETH", Some(true), 0.001);
        assert!(
            res.all_gates_pass,
            "All gates should pass for a strong trend"
        );
        assert!(res.bullish_alignment);
        assert!(res.btc_ok_long);
    }

    #[test]
    fn test_ranging_blocks() {
        let mut snap = trending_snap();
        snap.adx = 18.0; // below 21 -> vote
        snap.bb_width_ratio = 0.7; // below 0.8 -> vote
        snap.rsi = 50.0; // in 47-53 -> vote
        let cfg = SignalConfigView::default();
        let res = check_gates(&snap, &cfg, "ETH", Some(true), 0.0);
        assert!(res.is_ranging);
        assert!(!res.all_gates_pass);
    }

    #[test]
    fn test_slow_drift_unranges() {
        let mut snap = trending_snap();
        snap.adx = 18.0;
        snap.bb_width_ratio = 0.7;
        snap.rsi = 50.0;
        let mut cfg = SignalConfigView::default();
        cfg.thresholds.entry.enable_slow_drift_entries = true;
        cfg.thresholds.entry.slow_drift_min_slope_pct = 0.0006;
        let res = check_gates(&snap, &cfg, "ETH", Some(true), 0.001);
        assert!(!res.is_ranging, "Slow drift slope should override ranging");
    }

    #[test]
    fn test_btc_alignment_blocks_long() {
        let snap = trending_snap();
        let mut cfg = SignalConfigView::default();
        cfg.filters.require_btc_alignment = true;
        let res = check_gates(&snap, &cfg, "ETH", Some(false), 0.0);
        assert!(!res.btc_ok_long, "BTC bearish should block ETH long");
        assert!(res.btc_ok_short, "BTC bearish should allow ETH short");
    }

    #[test]
    fn test_btc_override_by_high_adx() {
        let mut snap = trending_snap();
        snap.adx = 45.0; // above btc_adx_override (40.0)
        let mut cfg = SignalConfigView::default();
        cfg.filters.require_btc_alignment = true;
        let res = check_gates(&snap, &cfg, "ETH", Some(false), 0.0);
        assert!(res.btc_ok_long, "High ADX should override BTC alignment");
    }

    #[test]
    fn test_ave_raises_threshold() {
        let mut snap = trending_snap();
        snap.atr = 3.0; // 3.0 / 1.4 ~ 2.14 > 1.5
        snap.adx = 24.0; // just above default 22 but below 22 * 1.25 = 27.5
        let cfg = SignalConfigView::default();
        let res = check_gates(&snap, &cfg, "ETH", Some(true), 0.0);
        assert!(
            res.effective_min_adx > 22.0,
            "AVE should raise effective_min_adx: got {}",
            res.effective_min_adx
        );
        assert!(
            !res.adx_above_min,
            "ADX 24 should be below raised threshold"
        );
    }

    #[test]
    fn test_tmc_lowers_threshold() {
        let mut snap = trending_snap();
        snap.adx = 24.0;
        snap.adx_slope = 1.0; // > 0.5
        let mut cfg = SignalConfigView::default();
        cfg.thresholds.entry.min_adx = 28.0;
        let res = check_gates(&snap, &cfg, "ETH", Some(true), 0.0);
        assert!(
            res.effective_min_adx <= 25.0,
            "TMC should cap effective_min_adx at 25: got {}",
            res.effective_min_adx
        );
    }

    #[test]
    fn test_anomaly_filter_fires_on_large_price_move() {
        let mut snap = trending_snap();
        snap.prev_close = 100.0;
        snap.close = 115.0; // 15% move
        let cfg = SignalConfigView::default();
        let res = check_gates(&snap, &cfg, "ETH", Some(true), 0.0);
        assert!(res.is_anomaly, "15% price move should trigger anomaly");
        assert!(!res.all_gates_pass);
    }

    #[test]
    fn test_extension_filter() {
        let mut snap = trending_snap();
        // EMA_fast = 99.0, close far above -> extended
        snap.close = 105.0; // 6.06% distance > 4% default threshold
        let cfg = SignalConfigView::default();
        let res = check_gates(&snap, &cfg, "ETH", Some(true), 0.0);
        assert!(
            res.is_extended,
            "6% distance from EMA should trigger extension"
        );
        assert!(!res.all_gates_pass);
    }

    #[test]
    fn test_dynamic_tp_mult_strong() {
        let mut snap = trending_snap();
        snap.adx = 45.0; // > 40.0 (adx_strong_gt)
        let cfg = SignalConfigView::default();
        let res = check_gates(&snap, &cfg, "ETH", Some(true), 0.0);
        assert!(
            (res.dynamic_tp_mult - 7.0).abs() < f64::EPSILON,
            "Strong ADX should get tp_mult_strong"
        );
    }

    #[test]
    fn test_dynamic_tp_mult_weak() {
        let mut snap = trending_snap();
        snap.adx = 25.0; // < 30.0 (adx_weak_lt)
        let cfg = SignalConfigView::default();
        let res = check_gates(&snap, &cfg, "ETH", Some(true), 0.0);
        assert!(
            (res.dynamic_tp_mult - 3.0).abs() < f64::EPSILON,
            "Weak ADX should get tp_mult_weak"
        );
    }

    #[test]
    fn test_dre_interpolation() {
        // ADX at midpoint between min_adx(22) and adx_strong_gt(40) => weight 0.5
        let mut snap = trending_snap();
        snap.adx = 31.0; // (31 - 22) / (40 - 22) = 9/18 = 0.5
        let cfg = SignalConfigView::default();
        let res = check_gates(&snap, &cfg, "ETH", Some(true), 0.0);
        // rsi_long_weak=56, rsi_long_strong=52 => 56 + 0.5 * (52-56) = 54
        assert!(
            (res.rsi_long_limit - 54.0).abs() < 0.01,
            "DRE long limit should be 54.0 at midpoint, got {}",
            res.rsi_long_limit,
        );
        // rsi_short_weak=44, rsi_short_strong=48 => 44 + 0.5 * (48-44) = 46
        assert!(
            (res.rsi_short_limit - 46.0).abs() < 0.01,
            "DRE short limit should be 46.0 at midpoint, got {}",
            res.rsi_short_limit,
        );
    }

    #[test]
    fn test_btc_symbol_always_ok() {
        let snap = trending_snap();
        let mut cfg = SignalConfigView::default();
        cfg.filters.require_btc_alignment = true;
        let res = check_gates(&snap, &cfg, "BTC", Some(false), 0.0);
        assert!(res.btc_ok_long);
        assert!(res.btc_ok_short);
    }

    #[test]
    fn test_stoch_rsi_passthrough() {
        let mut snap = trending_snap();
        snap.stoch_rsi_k = 0.92;
        snap.stoch_rsi_d = 0.88;
        let cfg = SignalConfigView::default();
        let res = check_gates(&snap, &cfg, "ETH", Some(true), 0.0);
        assert!((res.stoch_k - 0.92).abs() < f64::EPSILON);
        assert!((res.stoch_d - 0.88).abs() < f64::EPSILON);
        assert!(res.stoch_rsi_active);
    }
}
