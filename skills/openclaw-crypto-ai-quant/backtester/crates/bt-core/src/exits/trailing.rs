//! Trailing stop computation with conditional distance adjustments.
//!
//! Mirrors `mei_alpha_v1.check_exit_conditions` lines 2673-2720.
//!
//! Trailing stop activates when `profit_atr >= trailing_start_atr`.
//! The effective trailing distance is adjusted by several factors:
//!   1. Vol-Buffered (VBTS):  bb_width_ratio > 1.2 -> widen 25%
//!   2. High profit (>2 ATR): tighten to 0.5x, with overrides:
//!      - TATP: ADX > 35 AND adx_slope > 0 -> don't tighten (1.0x)
//!      - TSPV: atr_slope > 0 -> only 0.75x
//!   3. Weak trend: ADX < 25 -> tighten to 0.7x
//!   4. RSI Trend-Guard: min trailing distance = 0.5, raised to 0.7 if RSI favourable
//!   5. Ratchet: LONG trailing_sl can only go up; SHORT trailing_sl can only go down

use crate::config::{Confidence, StrategyConfig};
use crate::indicators::IndicatorSnapshot;
use crate::position::{Position, PositionType};

/// Compute the trailing stop price, or `None` if trailing is not yet active.
///
/// **Important**: This function does NOT mutate `pos.trailing_sl`. The caller must
/// ratchet the returned value into `pos.trailing_sl` after applying the exit action.
/// This keeps the exit logic pure and testable.
///
/// When the position already has a `trailing_sl` from a previous bar, the returned
/// value is guaranteed to be at least as favourable (ratcheted).
pub fn compute_trailing(
    pos: &Position,
    snap: &IndicatorSnapshot,
    cfg: &StrategyConfig,
    profit_atr: f64,
) -> Option<f64> {
    let trade = &cfg.trade;

    let entry = pos.entry_price;
    let atr = if pos.entry_atr > 0.0 {
        pos.entry_atr
    } else {
        entry * 0.005
    };

    // ── Per-confidence overrides for trailing params ──────────────────────
    let mut trailing_start = trade.trailing_start_atr;
    let mut trailing_dist = trade.trailing_distance_atr;

    if matches!(pos.confidence, Confidence::Low) {
        if trade.trailing_start_atr_low_conf > 0.0 {
            trailing_start = trade.trailing_start_atr_low_conf;
        }
        if trade.trailing_distance_atr_low_conf > 0.0 {
            trailing_dist = trade.trailing_distance_atr_low_conf;
        }
    }

    // ── RSI Trend-Guard (v5.016) ─────────────────────────────────────────
    // Floor for effective trailing distance. Raised when RSI is favourable.
    let min_trailing_dist = match pos.pos_type {
        PositionType::Long if snap.rsi > 60.0 => 0.7,
        PositionType::Short if snap.rsi < 40.0 => 0.7,
        _ => 0.5,
    };

    // ── Effective trailing distance ──────────────────────────────────────
    let mut effective_dist = trailing_dist;

    // Vol-Buffered Trailing Stop (v5.015): widen 25% if BB width expanding.
    if trade.enable_vol_buffered_trailing && snap.bb_width_ratio > 1.2 {
        effective_dist *= 1.25;
    }

    // High-profit tightening (>2 ATR) with TATP / TSPV overrides.
    if profit_atr > 2.0 {
        let tighten_mult = if snap.adx > 35.0 && snap.adx_slope > 0.0 {
            // TATP: trend accelerating -> don't tighten
            1.0
        } else if snap.atr_slope > 0.0 {
            // TSPV: vol expanding -> partial tighten
            0.75
        } else {
            0.5
        };
        effective_dist = trailing_dist * tighten_mult;
    } else if snap.adx < 25.0 {
        // Weak-trend tightening.
        effective_dist = trailing_dist * 0.7;
    }

    // Clamp to RSI Trend-Guard floor.
    effective_dist = effective_dist.max(min_trailing_dist);

    // ── Activation gate ──────────────────────────────────────────────────
    if profit_atr < trailing_start {
        // Not enough profit to activate trailing stop yet.
        // But if a previous bar already set a trailing_sl, preserve it.
        return pos.trailing_sl;
    }

    // ── Compute candidate trailing stop price ────────────────────────────
    let candidate = match pos.pos_type {
        PositionType::Long => snap.close - (atr * effective_dist),
        PositionType::Short => snap.close + (atr * effective_dist),
    };

    // ── Ratchet: only allow the trailing stop to improve ─────────────────
    let ratcheted = match pos.pos_type {
        PositionType::Long => match pos.trailing_sl {
            Some(prev) => candidate.max(prev),
            None => candidate,
        },
        PositionType::Short => match pos.trailing_sl {
            Some(prev) => candidate.min(prev),
            None => candidate,
        },
    };

    Some(ratcheted)
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
            entry_atr: entry * 0.01, // 1% ATR
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
    fn trailing_not_active_when_profit_too_low() {
        let pos = default_pos(100.0, PositionType::Long);
        let snap = default_snap(100.5); // profit_atr = 0.5
        let cfg = default_cfg();
        // trailing_start_atr default = 1.0, so 0.5 < 1.0 -> no trailing
        let result = compute_trailing(&pos, &snap, &cfg, 0.5);
        assert!(result.is_none());
    }

    #[test]
    fn trailing_activates_at_threshold() {
        let pos = default_pos(100.0, PositionType::Long);
        let snap = default_snap(102.0); // profit_atr = 2.0 with atr=1.0
        let cfg = default_cfg();
        let result = compute_trailing(&pos, &snap, &cfg, 2.0);
        assert!(result.is_some());
        // profit_atr = 2.0 which is NOT > 2.0, so high-profit tightening does not fire.
        // ADX = 30.0 which is NOT < 25.0, so weak-trend tightening does not fire.
        // bb_width_ratio = 1.0 which is NOT > 1.2, so VBTS does not fire.
        // effective_dist stays at trailing_distance_atr default = 0.8
        // RSI = 50.0 -> min_trailing_dist = 0.5
        // effective_dist = max(0.8, 0.5) = 0.8
        // trailing_sl = 102.0 - 1.0 * 0.8 = 101.2
        let tsl = result.unwrap();
        assert!((tsl - 101.2).abs() < 0.01);
    }

    #[test]
    fn trailing_ratchets_up_for_long() {
        let mut pos = default_pos(100.0, PositionType::Long);
        pos.trailing_sl = Some(101.8);
        let snap = default_snap(102.0);
        let cfg = default_cfg();
        let result = compute_trailing(&pos, &snap, &cfg, 2.0);
        assert!(result.is_some());
        // candidate = 101.2, but prev = 101.8 -> ratchet to 101.8
        let tsl = result.unwrap();
        assert!((tsl - 101.8).abs() < 0.01);
    }
}
