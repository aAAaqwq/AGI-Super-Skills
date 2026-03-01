//! Take-profit logic with partial TP support.
//!
//! Mirrors `mei_alpha_v1.check_exit_conditions` lines 2722-2724 (TP price),
//! 3080-3165 (LONG TP block), and 3195-3277 (SHORT TP block).
//!
//! Partial TP ladder:
//!   1. If `enable_partial_tp` AND `tp1_taken == false` AND price hits partial TP level
//!      -> Reduce by `tp_partial_pct`, caller should set `trailing_sl = entry` (breakeven)
//!   2. If `tp1_taken == true` AND `tp_partial_atr_mult > 0` AND price hits full TP
//!      -> Close remainder at full TP
//!   3. If `tp1_taken == true` AND `tp_partial_atr_mult == 0` -> Hold (trailing manages)
//!   4. If partial TP disabled or `tp_partial_pct >= 1.0` -> full Close
//!
//! When `tp_partial_atr_mult > 0`, partial TP fires at a separate (closer) level
//! and full TP remains available for the remainder. When `tp_partial_atr_mult == 0`
//! (default), partial and full TP share the same price — preserving legacy behavior.

use crate::config::StrategyConfig;
use crate::exits::ExitAction;
use crate::indicators::IndicatorSnapshot;
use crate::position::{Position, PositionType};

/// Check whether the current bar triggers a take-profit exit.
///
/// Returns `ExitAction::Reduce` for partial TP, `ExitAction::Close` for full TP,
/// or `ExitAction::Hold` if TP is not hit.
pub fn check_tp(
    pos: &Position,
    snap: &IndicatorSnapshot,
    cfg: &StrategyConfig,
    tp_mult: f64,
    _profit_atr: f64,
) -> ExitAction {
    let trade = &cfg.trade;

    let entry = pos.entry_price;
    let atr = if pos.entry_atr > 0.0 {
        pos.entry_atr
    } else {
        entry * 0.005
    };

    // ── Full TP price (always based on tp_mult) ──────────────────────────
    let tp_price = match pos.pos_type {
        PositionType::Long => entry + (atr * tp_mult),
        PositionType::Short => entry - (atr * tp_mult),
    };

    // ── Partial TP path ──────────────────────────────────────────────────
    if trade.enable_partial_tp {
        if !pos.tp1_taken {
            // Determine partial TP level: use dedicated mult if set, otherwise same as full TP.
            let partial_mult = if trade.tp_partial_atr_mult > 0.0 {
                trade.tp_partial_atr_mult
            } else {
                tp_mult
            };
            let partial_tp_price = match pos.pos_type {
                PositionType::Long => entry + (atr * partial_mult),
                PositionType::Short => entry - (atr * partial_mult),
            };
            let partial_hit = match pos.pos_type {
                PositionType::Long => snap.close >= partial_tp_price,
                PositionType::Short => snap.close <= partial_tp_price,
            };

            if partial_hit {
                let pct = trade.tp_partial_pct.clamp(0.0, 1.0);

                if pct > 0.0 && pct < 1.0 {
                    let remaining_notional = pos.size * (1.0 - pct) * snap.close;
                    if remaining_notional < trade.tp_partial_min_notional_usd {
                        return ExitAction::Hold;
                    }

                    // Partial reduce.  The caller is responsible for:
                    //   - setting `pos.tp1_taken = true`
                    //   - locking `pos.trailing_sl` to at least `entry` (breakeven)
                    return ExitAction::Reduce {
                        reason: "Take Profit (Partial)".to_string(),
                        fraction: pct,
                    };
                }
                // pct == 0 or pct >= 1.0 falls through to full close check.
            } else {
                // Partial TP not hit yet.
                // When tp_partial_atr_mult == 0, partial == full, so full can't be hit either.
                if trade.tp_partial_atr_mult <= 0.0 {
                    return ExitAction::Hold;
                }
                // When tp_partial_atr_mult > 0, fall through to check full TP
                // (handles edge case where partial_mult > tp_mult).
            }
        } else {
            // tp1 already taken.
            if trade.tp_partial_atr_mult > 0.0 {
                // Separate partial level: check if full TP hit for remaining position.
                let tp_hit = match pos.pos_type {
                    PositionType::Long => snap.close >= tp_price,
                    PositionType::Short => snap.close <= tp_price,
                };
                if tp_hit {
                    return ExitAction::Close {
                        reason: "Take Profit".to_string(),
                    };
                }
            }
            // Same level (tp_partial_atr_mult == 0) or full TP not hit: trailing manages.
            return ExitAction::Hold;
        }
    }

    // ── Full TP check (partial TP disabled, or pct edge case) ────────────
    let tp_hit = match pos.pos_type {
        PositionType::Long => snap.close >= tp_price,
        PositionType::Short => snap.close <= tp_price,
    };

    if !tp_hit {
        return ExitAction::Hold;
    }

    ExitAction::Close {
        reason: "Take Profit".to_string(),
    }
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
            entry_atr: entry * 0.01, // ATR = 1.0 when entry = 100
            entry_adx_threshold: 0.0,
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
    fn tp_not_hit_returns_hold() {
        let pos = default_pos(100.0, PositionType::Long);
        let snap = default_snap(103.0); // profit = 3 ATR, TP at 5.0 ATR
        let cfg = default_cfg();
        match check_tp(&pos, &snap, &cfg, 5.0, 3.0) {
            ExitAction::Hold => {}
            other => panic!("Expected Hold, got {:?}", other),
        }
    }

    #[test]
    fn partial_tp_on_first_hit() {
        let pos = default_pos(100.0, PositionType::Long);
        let snap = default_snap(105.0); // profit = 5.0 ATR, TP at 5.0 ATR
        let cfg = default_cfg();
        match check_tp(&pos, &snap, &cfg, 5.0, 5.0) {
            ExitAction::Reduce { fraction, .. } => {
                assert!((fraction - 0.5).abs() < 0.01);
            }
            other => panic!("Expected Reduce, got {:?}", other),
        }
    }

    #[test]
    fn hold_after_partial_tp_taken() {
        let mut pos = default_pos(100.0, PositionType::Long);
        pos.tp1_taken = true;
        let snap = default_snap(105.0);
        let cfg = default_cfg();
        match check_tp(&pos, &snap, &cfg, 5.0, 5.0) {
            ExitAction::Hold => {}
            other => panic!("Expected Hold after tp1_taken, got {:?}", other),
        }
    }

    #[test]
    fn full_close_when_partial_tp_disabled() {
        let pos = default_pos(100.0, PositionType::Long);
        let snap = default_snap(105.0);
        let mut cfg = default_cfg();
        cfg.trade.enable_partial_tp = false;
        match check_tp(&pos, &snap, &cfg, 5.0, 5.0) {
            ExitAction::Close { reason } => {
                assert_eq!(reason, "Take Profit");
            }
            other => panic!("Expected Close, got {:?}", other),
        }
    }

    #[test]
    fn short_tp_hit() {
        let pos = default_pos(100.0, PositionType::Short);
        let snap = default_snap(95.0); // profit = 5.0 ATR, TP at 5.0 ATR
        let cfg = default_cfg();
        match check_tp(&pos, &snap, &cfg, 5.0, 5.0) {
            ExitAction::Reduce { .. } => {} // partial TP
            other => panic!("Expected Reduce for SHORT partial TP, got {:?}", other),
        }
    }

    // ── Tests for tp_partial_atr_mult (separate partial TP level) ────────

    #[test]
    fn separate_partial_tp_hold_below_partial_level() {
        // tp_partial_atr_mult=3.0, price at 2 ATR profit → Hold
        let pos = default_pos(100.0, PositionType::Long);
        let snap = default_snap(102.0);
        let mut cfg = default_cfg();
        cfg.trade.tp_partial_atr_mult = 3.0;
        match check_tp(&pos, &snap, &cfg, 5.0, 2.0) {
            ExitAction::Hold => {}
            other => panic!("Expected Hold below partial level, got {:?}", other),
        }
    }

    #[test]
    fn separate_partial_tp_reduce_at_partial_level() {
        // tp_partial_atr_mult=3.0, price at 3 ATR profit → Reduce
        let pos = default_pos(100.0, PositionType::Long);
        let snap = default_snap(103.0); // ATR=1.0, partial at 103.0
        let mut cfg = default_cfg();
        cfg.trade.tp_partial_atr_mult = 3.0;
        match check_tp(&pos, &snap, &cfg, 5.0, 3.0) {
            ExitAction::Reduce { fraction, .. } => {
                assert!((fraction - 0.5).abs() < 0.01);
            }
            other => panic!("Expected Reduce at partial level, got {:?}", other),
        }
    }

    #[test]
    fn separate_partial_tp_full_close_after_tp1_taken() {
        // tp_partial_atr_mult=3.0, tp1_taken=true, price at 5 ATR → Close
        let mut pos = default_pos(100.0, PositionType::Long);
        pos.tp1_taken = true;
        let snap = default_snap(105.0);
        let mut cfg = default_cfg();
        cfg.trade.tp_partial_atr_mult = 3.0;
        match check_tp(&pos, &snap, &cfg, 5.0, 5.0) {
            ExitAction::Close { reason } => {
                assert_eq!(reason, "Take Profit");
            }
            other => panic!("Expected Close at full TP after tp1_taken, got {:?}", other),
        }
    }

    #[test]
    fn separate_partial_tp_hold_after_tp1_below_full() {
        // tp_partial_atr_mult=3.0, tp1_taken=true, price at 4 ATR (below full TP=5) → Hold
        let mut pos = default_pos(100.0, PositionType::Long);
        pos.tp1_taken = true;
        let snap = default_snap(104.0);
        let mut cfg = default_cfg();
        cfg.trade.tp_partial_atr_mult = 3.0;
        match check_tp(&pos, &snap, &cfg, 5.0, 4.0) {
            ExitAction::Hold => {}
            other => panic!("Expected Hold between partial and full TP, got {:?}", other),
        }
    }

    #[test]
    fn separate_partial_tp_short_reduce() {
        // SHORT: tp_partial_atr_mult=3.0, price at 3 ATR profit → Reduce
        let pos = default_pos(100.0, PositionType::Short);
        let snap = default_snap(97.0); // ATR=1.0, partial at 97.0
        let mut cfg = default_cfg();
        cfg.trade.tp_partial_atr_mult = 3.0;
        match check_tp(&pos, &snap, &cfg, 5.0, 3.0) {
            ExitAction::Reduce { .. } => {}
            other => panic!("Expected Reduce for SHORT partial TP, got {:?}", other),
        }
    }

    #[test]
    fn zero_partial_atr_mult_preserves_legacy_behavior() {
        // tp_partial_atr_mult=0.0 (default), tp1_taken=true → Hold (trailing manages)
        let mut pos = default_pos(100.0, PositionType::Long);
        pos.tp1_taken = true;
        let snap = default_snap(105.0);
        let cfg = default_cfg(); // tp_partial_atr_mult defaults to 0.0
        match check_tp(&pos, &snap, &cfg, 5.0, 5.0) {
            ExitAction::Hold => {}
            other => panic!("Expected Hold (legacy) after tp1_taken, got {:?}", other),
        }
    }
}
