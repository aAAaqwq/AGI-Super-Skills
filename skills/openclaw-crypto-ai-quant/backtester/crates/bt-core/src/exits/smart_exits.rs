//! Smart exit conditions — higher-priority exits that override SL/TP.
//!
//! Mirrors `mei_alpha_v1.check_exit_conditions` lines 2726-3022.
//!
//! Each sub-check returns the first matching exit reason.  The checks are
//! evaluated in Python order:
//!   1. Trend Breakdown (EMA Cross) + TBB buffer
//!   2. Trend Exhaustion (ADX < threshold)
//!   3. EMA Macro Breakdown (if require_macro_alignment)
//!   4. Stagnation Exit (low-vol + underwater, skip PAXG)
//!   5. Funding Headwind Exit (multi-filter system, funding_rate = 0 in backtester v1)
//!   6. TSME (Trend Saturation Momentum Exit)
//!   7. MMDE (MACD Persistent Divergence Exit)
//!   8. RSI Overextension Exit

use crate::config::{Confidence, StrategyConfig};
use crate::indicators::IndicatorSnapshot;
use crate::position::{Position, PositionType};

/// Evaluate all smart exit conditions.
///
/// Returns `Some(reason)` for the first triggered exit, or `None` if nothing fires.
pub fn check(
    pos: &Position,
    snap: &IndicatorSnapshot,
    cfg: &StrategyConfig,
    profit_atr: f64,
    duration_hours: f64,
) -> Option<String> {
    let trade = &cfg.trade;
    let filters = &cfg.filters;

    let entry = pos.entry_price;
    let atr = if pos.entry_atr > 0.0 {
        pos.entry_atr
    } else {
        entry * 0.005
    };

    let is_long = matches!(pos.pos_type, PositionType::Long);
    let is_low_conf = matches!(pos.confidence, Confidence::Low);

    // ── ADX exhaustion threshold: use the entry's ADX threshold so entry
    // and exit can never contradict (e.g. slow-drift enters at ADX=10,
    // so exhaustion only fires below 10, not at the old fixed 18).
    // Falls back to trade config for positions without entry_adx_threshold.
    let adx_exhaustion_lt = if pos.entry_adx_threshold > 0.0 {
        pos.entry_adx_threshold
    } else if is_low_conf && trade.smart_exit_adx_exhaustion_lt_low_conf > 0.0 {
        trade.smart_exit_adx_exhaustion_lt_low_conf
    } else {
        trade.smart_exit_adx_exhaustion_lt
    }
    .max(0.0);

    // ──────────────────────────────────────────────────────────────────────
    // 1. Trend Breakdown (EMA Cross) with TBB buffer
    // ──────────────────────────────────────────────────────────────────────
    let ema_dev = if snap.ema_slow > 0.0 {
        (snap.ema_fast - snap.ema_slow).abs() / snap.ema_slow
    } else {
        0.0
    };
    let is_weak_cross = ema_dev < 0.001 && snap.adx > 25.0;

    let ema_cross_exit = if is_long {
        snap.ema_fast < snap.ema_slow && !is_weak_cross
    } else {
        snap.ema_fast > snap.ema_slow && !is_weak_cross
    };

    // 2. Trend Exhaustion (ADX below threshold)
    let exhausted = adx_exhaustion_lt > 0.0 && snap.adx < adx_exhaustion_lt;

    if ema_cross_exit || exhausted {
        if ema_cross_exit {
            return Some("Trend Breakdown (EMA Cross)".to_string());
        }
        return Some(format!("Trend Exhaustion (ADX < {adx_exhaustion_lt})"));
    }

    // ──────────────────────────────────────────────────────────────────────
    // 3. EMA Macro Breakdown (only if require_macro_alignment is enabled)
    // ──────────────────────────────────────────────────────────────────────
    if filters.require_macro_alignment && snap.ema_macro > 0.0 {
        if is_long && snap.close < snap.ema_macro {
            return Some("EMA Macro Breakdown".to_string());
        }
        if !is_long && snap.close > snap.ema_macro {
            return Some("EMA Macro Breakout".to_string());
        }
    }

    // ──────────────────────────────────────────────────────────────────────
    // 4. Stagnation Exit (low-volatility + underwater, skip PAXG)
    // ──────────────────────────────────────────────────────────────────────
    if snap.atr < (atr * 0.70) {
        let is_underwater = if is_long {
            snap.close < entry
        } else {
            snap.close > entry
        };
        if is_underwater && pos.symbol.to_uppercase() != "PAXG" {
            return Some(format!(
                "Stagnation Exit (Low Vol: {:.2} < {:.2})",
                snap.atr,
                atr * 0.70
            ));
        }
    }

    // ──────────────────────────────────────────────────────────────────────
    // 5. Funding Headwind Exit (multi-filter system)
    //    NOTE: In backtester v1 `funding_rate` is always 0.0, so this entire
    //    block is a no-op. Implemented for structural parity with Python.
    // ──────────────────────────────────────────────────────────────────────
    if let Some(reason) = check_funding_headwind(pos, snap, cfg, profit_atr, duration_hours) {
        return Some(reason);
    }

    // ──────────────────────────────────────────────────────────────────────
    // 6. TSME (Trend Saturation Momentum Exit)
    //    ADX > 50, profit >= tsme_min_profit_atr, optional ADX_slope < 0,
    //    2 consecutive MACD momentum contractions
    // ──────────────────────────────────────────────────────────────────────
    if snap.adx > 50.0 {
        let tsme_min_profit = trade.tsme_min_profit_atr;
        let gate_profit_ok = profit_atr >= tsme_min_profit;
        let gate_slope_ok = if trade.tsme_require_adx_slope_negative {
            snap.adx_slope < 0.0
        } else {
            true
        };

        if gate_profit_ok && gate_slope_ok {
            // Check 2 consecutive MACD contractions in the saturated zone.
            let is_exhausted = if is_long {
                snap.macd_hist < snap.prev_macd_hist && snap.prev_macd_hist < snap.prev2_macd_hist
            } else {
                snap.macd_hist > snap.prev_macd_hist && snap.prev_macd_hist > snap.prev2_macd_hist
            };

            if is_exhausted {
                return Some(format!(
                    "Trend Saturation Momentum Exhaustion (ADX: {:.1}, ADX_slope: {:.2})",
                    snap.adx, snap.adx_slope
                ));
            }
        }
    }

    // ──────────────────────────────────────────────────────────────────────
    // 7. MMDE (MACD Persistent Divergence Exit)
    //    profit > 1.5 ATR AND ADX > 35 AND 3 consecutive MACD histogram
    //    moves against position (4 bars total: h < p < pp < ppp for LONG)
    // ──────────────────────────────────────────────────────────────────────
    if profit_atr > 1.5 && snap.adx > 35.0 {
        let is_diverging = if is_long {
            snap.macd_hist < snap.prev_macd_hist
                && snap.prev_macd_hist < snap.prev2_macd_hist
                && snap.prev2_macd_hist < snap.prev3_macd_hist
        } else {
            snap.macd_hist > snap.prev_macd_hist
                && snap.prev_macd_hist > snap.prev2_macd_hist
                && snap.prev2_macd_hist > snap.prev3_macd_hist
        };

        if is_diverging {
            return Some(format!(
                "MACD Persistent Divergence (Profit: {profit_atr:.2} ATR)"
            ));
        }
    }

    // ──────────────────────────────────────────────────────────────────────
    // 8. RSI Overextension Exit (configurable thresholds with profit-switch)
    // ──────────────────────────────────────────────────────────────────────
    if trade.enable_rsi_overextension_exit {
        if let Some(reason) = check_rsi_overextension(pos, snap, cfg, profit_atr) {
            return Some(reason);
        }
    }

    None
}

// ═══════════════════════════════════════════════════════════════════════════
// Funding Headwind sub-check (extracted for readability)
// ═══════════════════════════════════════════════════════════════════════════
fn check_funding_headwind(
    pos: &Position,
    snap: &IndicatorSnapshot,
    cfg: &StrategyConfig,
    profit_atr: f64,
    duration_hours: f64,
) -> Option<String> {
    let _trade = &cfg.trade;
    let funding_rate = snap.funding_rate;
    if funding_rate == 0.0 {
        return None;
    }

    let is_long = matches!(pos.pos_type, PositionType::Long);
    let entry = pos.entry_price;
    // C5: ATR zero-guard — prevent NaN/Inf from division by zero
    let atr = if pos.entry_atr > 0.0 {
        pos.entry_atr
    } else {
        entry * 0.005
    }
    .max(1e-12);

    let is_headwind = if is_long {
        funding_rate > 0.0
    } else {
        funding_rate < 0.0
    };
    if !is_headwind {
        return None;
    }

    let price_diff_atr = (snap.close - entry).abs() / atr;

    // ── AFL (Adaptive Funding Ladder) ────────────────────────────────────
    let mut headwind_threshold = if funding_rate.abs() > 0.0001 {
        0.15
    } else if funding_rate.abs() > 0.00006 {
        0.25
    } else if funding_rate.abs() > 0.00004 {
        0.40
    } else if funding_rate.abs() > 0.00002 {
        0.60
    } else if funding_rate.abs() < 0.00001 {
        0.95 // NZF: near-zero funding buffer
    } else {
        0.80
    };

    // ── Volatility-Adjusted Sensitivity ──────────────────────────────────
    if snap.atr > (atr * 1.2) {
        headwind_threshold *= 0.6;
    }

    // ── TDH (Time-Decay Headwind) with floor ─────────────────────────────
    if duration_hours > 1.0 {
        let decay_factor = (1.0 - (duration_hours - 1.0) / 11.0).max(0.0);
        headwind_threshold = (headwind_threshold * decay_factor).max(0.35);
    }

    // ── TLFB (Trend Loyalty Funding Buffer) ──────────────────────────────
    let is_trend_valid = if is_long {
        snap.ema_fast > snap.ema_slow
    } else {
        snap.ema_fast < snap.ema_slow
    };
    if is_trend_valid && snap.adx > 25.0 {
        headwind_threshold = headwind_threshold.max(0.75);
    }

    // ── MFE (Momentum-Filtered Funding Exit) ─────────────────────────────
    let is_momentum_improving = if is_long {
        snap.macd_hist > snap.prev_macd_hist
    } else {
        snap.macd_hist < snap.prev_macd_hist
    };
    if is_momentum_improving {
        headwind_threshold *= 1.5;
        headwind_threshold = headwind_threshold.max(0.50);
    }

    // ── ABF (ADX-Boosted Funding Threshold) ──────────────────────────────
    if snap.adx > 35.0 {
        headwind_threshold *= 1.4;
    }

    // ── HCFB (High-Confidence Funding Buffer) ────────────────────────────
    if matches!(pos.confidence, Confidence::High) {
        headwind_threshold *= 1.25;
    }

    // ── MTF (Macro-Trend Filtered Funding Exit) ──────────────────────────
    let is_macro_aligned = if snap.ema_macro > 0.0 {
        if is_long {
            snap.close > snap.ema_macro
        } else {
            snap.close < snap.ema_macro
        }
    } else {
        false
    };
    if is_macro_aligned {
        headwind_threshold *= 1.3;
    }

    // ── TCFB (Triple Confirmation Funding Buffer) ────────────────────────
    if is_momentum_improving && is_macro_aligned && matches!(pos.confidence, Confidence::High) {
        headwind_threshold *= 1.5;
    }

    // ── VSFT (Volatility-Scaled Funding Tolerance) ───────────────────────
    if snap.close > 0.0 && (snap.atr / snap.close) < 0.002 {
        headwind_threshold *= 1.25;
    }

    // ── CTEB (Counter-Trend Exhaustion Buffer) ───────────────────────────
    if (!is_long && snap.rsi > 65.0) || (is_long && snap.rsi < 35.0) {
        headwind_threshold *= 1.3;
    }

    // ── ETFS (Extreme Trend Funding Shield) ──────────────────────────────
    if snap.adx > 45.0 {
        headwind_threshold *= 1.6;
    }

    // ── TAES (Trend Acceleration Exit Shield) ────────────────────────────
    if snap.adx_slope > 1.0 {
        headwind_threshold *= 1.4;
    }

    // ── DFG (Dynamic Funding Guard) ──────────────────────────────────────
    if snap.adx > 40.0 {
        headwind_threshold *= 1.25;
    }

    // ── PVS (Profit-Vol Shield) ──────────────────────────────────────────
    if profit_atr > 1.5 && snap.atr_slope > 0.0 {
        headwind_threshold *= 1.5;
    }

    // ── PBFB (Profit-Based Funding Buffer) ───────────────────────────────
    if profit_atr > 3.0 {
        headwind_threshold *= 2.0;
    } else if profit_atr > 2.0 {
        headwind_threshold *= 1.5;
    }

    // ── TWFS (Trend Weakening Funding Sensitivity) ───────────────────────
    if snap.adx_slope < 0.0 {
        headwind_threshold *= 0.75;
    }

    // ── Final check: underwater with headwind ────────────────────────────
    let is_underwater = if is_long {
        snap.close < entry
    } else {
        snap.close > entry
    };
    if is_underwater && price_diff_atr > headwind_threshold {
        return Some(format!(
            "Funding Headwind Exit (FR: {funding_rate:.6}, Thr: {headwind_threshold:.2}, Dur: {duration_hours:.1}h)"
        ));
    }

    None
}

// ═══════════════════════════════════════════════════════════════════════════
// RSI Overextension sub-check
// ═══════════════════════════════════════════════════════════════════════════
fn check_rsi_overextension(
    pos: &Position,
    snap: &IndicatorSnapshot,
    cfg: &StrategyConfig,
    profit_atr: f64,
) -> Option<String> {
    let trade = &cfg.trade;
    let is_long = matches!(pos.pos_type, PositionType::Long);
    let is_low_conf = matches!(pos.confidence, Confidence::Low);

    let sw = trade.rsi_exit_profit_atr_switch.max(0.0);

    let (rsi_ub, rsi_lb) = if profit_atr < sw {
        // Low-profit regime: wider thresholds (less aggressive exit).
        let mut ub = trade.rsi_exit_ub_lo_profit;
        let mut lb = trade.rsi_exit_lb_lo_profit;
        if is_low_conf {
            if trade.rsi_exit_ub_lo_profit_low_conf > 0.0 {
                ub = trade.rsi_exit_ub_lo_profit_low_conf;
            }
            if trade.rsi_exit_lb_lo_profit_low_conf > 0.0 {
                lb = trade.rsi_exit_lb_lo_profit_low_conf;
            }
        }
        (ub, lb)
    } else {
        // High-profit regime: tighter thresholds (protect profits).
        let mut ub = trade.rsi_exit_ub_hi_profit;
        let mut lb = trade.rsi_exit_lb_hi_profit;
        if is_low_conf {
            if trade.rsi_exit_ub_hi_profit_low_conf > 0.0 {
                ub = trade.rsi_exit_ub_hi_profit_low_conf;
            }
            if trade.rsi_exit_lb_hi_profit_low_conf > 0.0 {
                lb = trade.rsi_exit_lb_hi_profit_low_conf;
            }
        }
        (ub, lb)
    };

    if is_long && snap.rsi > rsi_ub {
        return Some(format!("RSI Overbought ({:.1}, Thr: {rsi_ub})", snap.rsi));
    }
    if !is_long && snap.rsi < rsi_lb {
        return Some(format!("RSI Oversold ({:.1}, Thr: {rsi_lb})", snap.rsi));
    }

    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::Confidence;
    use crate::indicators::IndicatorSnapshot;
    use crate::position::{Position, PositionType};

    fn default_snap(close: f64) -> IndicatorSnapshot {
        IndicatorSnapshot {
            close,
            high: close,
            low: close,
            open: close,
            volume: 0.0,
            t: 0,
            ema_slow: close,
            ema_fast: close,
            ema_macro: close,
            adx: 30.0,
            adx_pos: 15.0,
            adx_neg: 15.0,
            adx_slope: 0.0,
            bb_upper: close * 1.02,
            bb_lower: close * 0.98,
            bb_width: 0.04,
            bb_width_avg: 0.04,
            bb_width_ratio: 1.0,
            atr: close * 0.01,
            atr_slope: 0.0,
            avg_atr: close * 0.01,
            rsi: 50.0,
            stoch_rsi_k: 50.0,
            stoch_rsi_d: 50.0,
            macd_hist: 0.0,
            prev_macd_hist: 0.0,
            prev2_macd_hist: 0.0,
            prev3_macd_hist: 0.0,
            vol_sma: 100.0,
            vol_trend: false,
            prev_close: close,
            prev_ema_fast: close,
            prev_ema_slow: close,
            bar_count: 200,
            funding_rate: 0.0,
        }
    }

    fn default_pos(entry: f64, pos_type: PositionType) -> Position {
        Position {
            symbol: "BTC".to_string(),
            pos_type,
            entry_price: entry,
            entry_atr: entry * 0.01,
            entry_adx_threshold: 0.0, // use legacy fallback in tests
            size: 1.0,
            confidence: Confidence::High,
            trailing_sl: None,
            leverage: 3.0,
            margin_used: entry / 3.0,
            tp1_taken: false,
            adds_count: 0,
            open_time_ms: 0,
            last_add_time_ms: 0,
            mae_usd: 0.0,
            mfe_usd: 0.0,
        }
    }

    fn default_cfg() -> StrategyConfig {
        StrategyConfig::default()
    }

    #[test]
    fn trend_breakdown_long_ema_cross() {
        let pos = default_pos(100.0, PositionType::Long);
        let mut snap = default_snap(100.0);
        snap.ema_fast = 99.0;
        snap.ema_slow = 100.0;
        snap.adx = 20.0; // low ADX -> not a weak cross
        let cfg = default_cfg();
        let result = check(&pos, &snap, &cfg, 0.0, 0.0);
        assert!(result.is_some());
        assert!(result.unwrap().contains("Trend Breakdown"));
    }

    #[test]
    fn weak_cross_suppresses_breakdown() {
        let pos = default_pos(100.0, PositionType::Long);
        let mut snap = default_snap(100.0);
        snap.ema_fast = 99.95; // ema_dev = 0.05% < 0.1%
        snap.ema_slow = 100.0;
        snap.adx = 30.0; // ADX > 25 -> TBB buffer active
        let mut cfg = default_cfg();
        // disable exhaustion so only breakdown is tested
        cfg.trade.smart_exit_adx_exhaustion_lt = 0.0;
        let result = check(&pos, &snap, &cfg, 0.0, 0.0);
        assert!(result.is_none());
    }

    #[test]
    fn trend_exhaustion_adx_below_threshold() {
        let pos = default_pos(100.0, PositionType::Long);
        let mut snap = default_snap(100.0);
        snap.adx = 15.0; // below default threshold of 20
        let cfg = default_cfg();
        let result = check(&pos, &snap, &cfg, 0.0, 0.0);
        assert!(result.is_some());
        assert!(result.unwrap().contains("Trend Exhaustion"));
    }

    #[test]
    fn ema_macro_breakdown() {
        let pos = default_pos(100.0, PositionType::Long);
        let mut snap = default_snap(99.0);
        snap.ema_macro = 100.0; // price < macro -> breakdown
        snap.adx = 30.0; // above exhaustion threshold
        let mut cfg = default_cfg();
        cfg.filters.require_macro_alignment = true;
        let result = check(&pos, &snap, &cfg, 0.0, 0.0);
        assert!(result.is_some());
        assert!(result.unwrap().contains("EMA Macro Breakdown"));
    }

    #[test]
    fn stagnation_exit_underwater_low_vol() {
        let pos = default_pos(100.0, PositionType::Long);
        let mut snap = default_snap(99.0); // underwater
        snap.atr = 0.5; // 50% of entry_atr (1.0), below 70% threshold
        snap.adx = 30.0; // above exhaustion
        let mut cfg = default_cfg();
        cfg.filters.require_macro_alignment = false;
        let result = check(&pos, &snap, &cfg, -1.0, 0.0);
        assert!(result.is_some());
        assert!(result.unwrap().contains("Stagnation Exit"));
    }

    #[test]
    fn stagnation_exit_skips_paxg() {
        let mut pos = default_pos(100.0, PositionType::Long);
        pos.symbol = "PAXG".to_string();
        let mut snap = default_snap(99.0);
        snap.atr = 0.5;
        snap.adx = 30.0;
        let mut cfg = default_cfg();
        cfg.filters.require_macro_alignment = false;
        let result = check(&pos, &snap, &cfg, -1.0, 0.0);
        // Should NOT trigger for PAXG
        assert!(
            result.is_none() || !result.as_ref().unwrap().contains("Stagnation"),
            "PAXG should be exempt from stagnation exit"
        );
    }

    #[test]
    fn tsme_triggers_on_momentum_contraction() {
        let pos = default_pos(100.0, PositionType::Long);
        let mut snap = default_snap(102.0);
        snap.adx = 55.0;
        snap.adx_slope = -1.0;
        snap.macd_hist = 0.5;
        snap.prev_macd_hist = 0.8;
        snap.prev2_macd_hist = 1.1;
        let mut cfg = default_cfg();
        cfg.trade.smart_exit_adx_exhaustion_lt = 0.0; // disable exhaustion
        cfg.filters.require_macro_alignment = false;
        let result = check(&pos, &snap, &cfg, 2.0, 0.0);
        assert!(result.is_some());
        assert!(result.unwrap().contains("Trend Saturation"));
    }

    #[test]
    fn mmde_triggers_on_persistent_divergence() {
        let pos = default_pos(100.0, PositionType::Long);
        let mut snap = default_snap(102.0);
        snap.adx = 40.0;
        snap.macd_hist = 0.3;
        snap.prev_macd_hist = 0.5;
        snap.prev2_macd_hist = 0.7;
        snap.prev3_macd_hist = 0.9;
        let mut cfg = default_cfg();
        cfg.trade.smart_exit_adx_exhaustion_lt = 0.0;
        cfg.filters.require_macro_alignment = false;
        let result = check(&pos, &snap, &cfg, 2.0, 0.0);
        assert!(result.is_some());
        assert!(result.unwrap().contains("MACD Persistent Divergence"));
    }

    #[test]
    fn rsi_overextension_long_overbought() {
        let pos = default_pos(100.0, PositionType::Long);
        let mut snap = default_snap(100.0);
        snap.rsi = 85.0; // above 80 threshold
        snap.adx = 30.0; // above exhaustion
        let mut cfg = default_cfg();
        cfg.filters.require_macro_alignment = false;
        let result = check(&pos, &snap, &cfg, 0.5, 0.0);
        assert!(result.is_some());
        assert!(result.unwrap().contains("RSI Overbought"));
    }

    #[test]
    fn rsi_overextension_hi_profit_tighter_threshold() {
        let pos = default_pos(100.0, PositionType::Long);
        let mut snap = default_snap(100.0);
        snap.rsi = 72.0; // above 70 hi-profit threshold but below 80 lo-profit
        snap.adx = 30.0;
        let mut cfg = default_cfg();
        cfg.filters.require_macro_alignment = false;
        // Below profit switch: rsi_ub = 80 -> 72 < 80 -> no trigger
        let result = check(&pos, &snap, &cfg, 0.5, 0.0);
        assert!(result.is_none());

        // Above profit switch: rsi_ub = 70 -> 72 > 70 -> trigger
        let result2 = check(&pos, &snap, &cfg, 2.0, 0.0);
        assert!(result2.is_some());
        assert!(result2.unwrap().contains("RSI Overbought"));
    }

    #[test]
    fn no_smart_exit_normal_conditions() {
        let pos = default_pos(100.0, PositionType::Long);
        let mut snap = default_snap(101.0);
        snap.ema_fast = 101.0;
        snap.ema_slow = 100.0; // EMA aligned
        snap.adx = 30.0; // above exhaustion
        snap.rsi = 55.0; // normal
        let mut cfg = default_cfg();
        cfg.filters.require_macro_alignment = false;
        let result = check(&pos, &snap, &cfg, 1.0, 0.0);
        assert!(result.is_none());
    }
}
