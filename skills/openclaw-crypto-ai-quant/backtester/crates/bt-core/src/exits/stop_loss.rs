//! ATR-based stop loss with 5 dynamic adjustments + breakeven.
//!
//! Mirrors `mei_alpha_v1.check_exit_conditions` lines 2617-2671.
//!
//! The SL level is recomputed each bar based on these modifiers applied to
//! `sl_atr_mult`:
//!
//!   1. **ASE** (ADX Slope Exit): ADX_slope < 0 AND underwater -> tighten 20% (x0.80)
//!   2. **FTB** (Funding Tailwind Buffer): Disabled in backtester (no funding data)
//!   3. **DASE** (Dynamic ADX SL Expansion): ADX > 40 AND profitable -> widen 15% (x1.15)
//!   4. **SLB** (Saturation Loyalty Buffer): ADX > 45 -> widen 10% (x1.10)
//!   5. **Breakeven Stop**: profit >= breakeven_start_atr * entry_atr -> move SL to
//!      entry +/- breakeven_buffer_atr * entry_atr
//!
//! Exit if: LONG and close <= sl_price, or SHORT and close >= sl_price.

use crate::config::StrategyConfig;
use crate::exits::ExitResult;
use crate::indicators::IndicatorSnapshot;
use crate::position::{Position, PositionType};

/// Check whether the current bar triggers a stop-loss exit.
///
/// Computes the dynamically-adjusted SL price and compares against the close.
pub fn check_stop_loss(
    pos: &Position,
    snap: &IndicatorSnapshot,
    cfg: &StrategyConfig,
) -> ExitResult {
    let sl_price = compute_sl_price(pos, snap, cfg);

    let hit = match pos.pos_type {
        PositionType::Long => snap.close <= sl_price,
        PositionType::Short => snap.close >= sl_price,
    };

    if hit {
        ExitResult::exit("Stop Loss", snap.close)
    } else {
        ExitResult::no_exit()
    }
}

/// Compute the stop-loss price for the given position and current bar.
///
/// This is the *base* SL (before trailing is overlaid). It incorporates all
/// dynamic adjustments (ASE, DASE, SLB, breakeven) each bar.
pub fn compute_sl_price(pos: &Position, snap: &IndicatorSnapshot, cfg: &StrategyConfig) -> f64 {
    let trade = &cfg.trade;

    let entry = pos.entry_price;
    // C5: ATR zero-guard — prevent NaN/Inf from division by zero
    let atr = if pos.entry_atr > 0.0 {
        pos.entry_atr
    } else {
        // Fallback for legacy positions with no ATR recorded.
        entry * 0.005
    }
    .max(1e-12);

    let mut sl_mult = trade.sl_atr_mult;

    // ── 1. ASE (ADX Slope-Adjusted Stop) ─────────────────────────────────
    // If trend is weakening (ADX slope < 0) and position is underwater,
    // tighten the stop by 20%.
    let is_underwater = match pos.pos_type {
        PositionType::Long => snap.close < entry,
        PositionType::Short => snap.close > entry,
    };
    if snap.adx_slope < 0.0 && is_underwater {
        sl_mult *= 0.8;
    }

    // ── 2. FTB (Funding Tailwind Buffer) ─────────────────────────────────
    // Disabled in backtester v1 — no funding rate data available.
    // Kept as a no-op for structural parity with Python.

    // ── 3. DASE (Dynamic ADX Stop Expansion) ─────────────────────────────
    // If ADX > 40 and position is profitable by > 0.5 ATR, widen by 15%.
    if snap.adx > 40.0 {
        let profit_in_atr = match pos.pos_type {
            PositionType::Long => (snap.close - entry) / atr,
            PositionType::Short => (entry - snap.close) / atr,
        };
        if profit_in_atr > 0.5 {
            sl_mult *= 1.15;
        }
    }

    // ── 4. SLB (Saturation Loyalty Buffer) ───────────────────────────────
    // If ADX > 45 (saturated/strong trend), widen overall SL by 10%.
    if snap.adx > 45.0 {
        sl_mult *= 1.10;
    }

    // ── Compute raw SL price ─────────────────────────────────────────────
    let mut sl_price = match pos.pos_type {
        PositionType::Long => entry - (atr * sl_mult),
        PositionType::Short => entry + (atr * sl_mult),
    };

    // ── 5. Breakeven Stop ────────────────────────────────────────────────
    // If profit exceeds breakeven_start_atr ATRs, move SL to
    // entry +/- breakeven_buffer_atr ATRs (protecting at least entry).
    if trade.enable_breakeven_stop && trade.breakeven_start_atr > 0.0 {
        let be_start = atr * trade.breakeven_start_atr;
        let be_buffer = atr * trade.breakeven_buffer_atr;

        match pos.pos_type {
            PositionType::Long => {
                if (snap.close - entry) >= be_start {
                    // Only raise SL, never lower it from the breakeven level.
                    sl_price = sl_price.max(entry + be_buffer);
                }
            }
            PositionType::Short => {
                if (entry - snap.close) >= be_start {
                    // Only lower SL, never raise it from the breakeven level.
                    sl_price = sl_price.min(entry - be_buffer);
                }
            }
        }
    }

    sl_price
}

// ═══════════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{Confidence, StrategyConfig};
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
            entry_atr: entry * 0.01, // ATR = 1.0 when entry = 100
            entry_adx_threshold: 0.0,
            size: 1.0,
            confidence: Confidence::High,
            trailing_sl: None,
            leverage: 3.0,
            margin_used: 100.0,
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
    fn base_sl_long() {
        let pos = default_pos(100.0, PositionType::Long);
        let snap = default_snap(100.0);
        let cfg = default_cfg();
        let sl = compute_sl_price(&pos, &snap, &cfg);
        // SL = entry - atr * sl_atr_mult = 100 - 1.0 * 2.0 = 98.0
        assert!((sl - 98.0).abs() < 0.01);
    }

    #[test]
    fn base_sl_short() {
        let pos = default_pos(100.0, PositionType::Short);
        let snap = default_snap(100.0);
        let cfg = default_cfg();
        let sl = compute_sl_price(&pos, &snap, &cfg);
        // SL = entry + atr * sl_atr_mult = 100 + 1.0 * 2.0 = 102.0
        assert!((sl - 102.0).abs() < 0.01);
    }

    #[test]
    fn ase_tightens_when_underwater() {
        let pos = default_pos(100.0, PositionType::Long);
        let mut snap = default_snap(99.0); // underwater
        snap.adx_slope = -1.0;
        let cfg = default_cfg();
        let sl = compute_sl_price(&pos, &snap, &cfg);
        // sl_mult = 2.0 * 0.8 = 1.6; SL = 100 - 1.0 * 1.6 = 98.4
        assert!((sl - 98.4).abs() < 0.01);
    }

    #[test]
    fn dase_widens_when_strong_trend_profitable() {
        let pos = default_pos(100.0, PositionType::Long);
        let mut snap = default_snap(101.0); // profitable > 0.5 ATR (1.0 ATR)
        snap.adx = 42.0;
        let cfg = default_cfg();
        let sl = compute_sl_price(&pos, &snap, &cfg);
        // sl_mult = 2.0 * 1.15 = 2.30; base SL = 100 - 1.0 * 2.30 = 97.70
        // But breakeven is enabled by default: profit 1.0 ATR >= breakeven_start_atr 0.7
        // BE SL = entry + breakeven_buffer_atr * atr = 100 + 0.05 * 1.0 = 100.05
        // Final SL = max(97.70, 100.05) = 100.05
        assert!((sl - 100.05).abs() < 0.01);
    }

    #[test]
    fn slb_widens_when_adx_saturated() {
        let pos = default_pos(100.0, PositionType::Long);
        let mut snap = default_snap(100.0);
        snap.adx = 50.0;
        let cfg = default_cfg();
        let sl = compute_sl_price(&pos, &snap, &cfg);
        // ADX > 40 but not profitable (profit_atr = 0) -> DASE skipped
        // ADX > 45 -> SLB: sl_mult = 2.0 * 1.10 = 2.20
        // SL = 100 - 1.0 * 2.20 = 97.80
        assert!((sl - 97.80).abs() < 0.01);
    }

    #[test]
    fn breakeven_moves_sl_when_profitable() {
        let pos = default_pos(100.0, PositionType::Long);
        // breakeven_start_atr default = 0.7, so need profit >= 0.7 ATR
        let snap = default_snap(100.8); // profit = 0.8 ATR > 0.7
        let cfg = default_cfg();
        let sl = compute_sl_price(&pos, &snap, &cfg);
        // breakeven_buffer_atr default = 0.05
        // BE SL = entry + 0.05 * 1.0 = 100.05
        // Base SL = 100 - 2.0 = 98.0
        // max(98.0, 100.05) = 100.05
        assert!((sl - 100.05).abs() < 0.01);
    }

    #[test]
    fn check_stop_loss_triggers_long() {
        let pos = default_pos(100.0, PositionType::Long);
        // SL = 98.0; close = 97.5 -> should trigger
        let snap = default_snap(97.5);
        let cfg = default_cfg();
        let result = check_stop_loss(&pos, &snap, &cfg);
        assert!(result.should_exit);
        assert_eq!(result.reason, "Stop Loss");
        assert!((result.exit_price - 97.5).abs() < 0.01);
    }

    #[test]
    fn check_stop_loss_no_trigger() {
        let pos = default_pos(100.0, PositionType::Long);
        let snap = default_snap(99.0); // above SL of 98.0
        let cfg = default_cfg();
        let result = check_stop_loss(&pos, &snap, &cfg);
        assert!(!result.should_exit);
    }

    #[test]
    fn sl_atr_mult_direction_is_consistent_for_long_and_short() {
        let mut tight = default_cfg();
        tight.trade.enable_breakeven_stop = false;
        tight.trade.sl_atr_mult = 1.0;

        let mut wide = tight.clone();
        wide.trade.sl_atr_mult = 3.0;

        // Keep dynamic SL modifiers inactive to isolate sl_atr_mult direction.
        let mut long_snap = default_snap(98.5);
        long_snap.adx = 30.0;
        long_snap.adx_slope = 0.0;

        let mut short_snap = default_snap(101.5);
        short_snap.adx = 30.0;
        short_snap.adx_slope = 0.0;

        let long_pos = default_pos(100.0, PositionType::Long);
        let short_pos = default_pos(100.0, PositionType::Short);

        let long_sl_tight = compute_sl_price(&long_pos, &long_snap, &tight);
        let long_sl_wide = compute_sl_price(&long_pos, &long_snap, &wide);
        assert!(
            long_sl_wide < long_sl_tight,
            "LONG SL should move lower when sl_atr_mult widens"
        );

        let short_sl_tight = compute_sl_price(&short_pos, &short_snap, &tight);
        let short_sl_wide = compute_sl_price(&short_pos, &short_snap, &wide);
        assert!(
            short_sl_wide > short_sl_tight,
            "SHORT SL should move higher when sl_atr_mult widens"
        );

        // Same market prices: wider stops should not trigger when tighter stops do.
        assert!(check_stop_loss(&long_pos, &long_snap, &tight).should_exit);
        assert!(!check_stop_loss(&long_pos, &long_snap, &wide).should_exit);

        assert!(check_stop_loss(&short_pos, &short_snap, &tight).should_exit);
        assert!(!check_stop_loss(&short_pos, &short_snap, &wide).should_exit);
    }
}
