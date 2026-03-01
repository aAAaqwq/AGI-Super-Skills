//! Exit conditions module for the backtesting simulator.
//!
//! Implements all exit conditions from Python `mei_alpha_v1.py` PaperTrader.
//!
//! Priority order: Stop Loss > Trailing Stop > Take Profit > Smart Exits.
//!
//! All functions are pure computations — the caller is responsible for mutating
//! `Position` fields (e.g., `trailing_sl`, `tp1_taken`) after applying the result.

pub mod smart_exits;
pub mod stop_loss;
pub mod take_profit;
pub mod trailing;

use crate::config::StrategyConfig;
use crate::indicators::IndicatorSnapshot;
use crate::position::{Position, PositionType};

/// Result of evaluating exit conditions for one bar.
#[derive(Debug, Clone)]
pub struct ExitResult {
    /// Whether an exit (full or partial) was triggered.
    pub should_exit: bool,
    /// Human-readable reason string for logging / reporting.
    pub reason: String,
    /// The price at which the exit should be filled.
    pub exit_price: f64,
    /// For partial exits (e.g., partial TP): fraction of the position to close.
    /// `None` means the entire position should be closed.
    pub partial_pct: Option<f64>,
}

impl ExitResult {
    /// No exit triggered — hold the position.
    pub fn no_exit() -> Self {
        Self {
            should_exit: false,
            reason: String::new(),
            exit_price: 0.0,
            partial_pct: None,
        }
    }

    /// Full exit at the given price.
    pub fn exit(reason: &str, price: f64) -> Self {
        Self {
            should_exit: true,
            reason: reason.to_string(),
            exit_price: price,
            partial_pct: None,
        }
    }

    /// Partial exit (reduce position by `pct` fraction, e.g. 0.5 = 50%).
    pub fn partial_exit(reason: &str, price: f64, pct: f64) -> Self {
        Self {
            should_exit: true,
            reason: reason.to_string(),
            exit_price: price,
            partial_pct: Some(pct),
        }
    }
}

/// Action returned by take_profit module.
#[derive(Debug, Clone)]
pub enum ExitAction {
    Hold,
    Close { reason: String },
    Reduce { reason: String, fraction: f64 },
}

/// Check all exit conditions for a position, return the first one that triggers.
///
/// Evaluation priority mirrors `mei_alpha_v1.check_exit_conditions`:
///   1. Stop Loss (with dynamic adjustments + breakeven)
///   2. Trailing Stop (with conditional distance adjustments)
///   3. Take Profit (partial then full)
///   4. Smart Exits (trend breakdown, exhaustion, macro, stagnation, TSME, RSI)
///
/// `current_time_ms` is the current bar timestamp in milliseconds.
pub fn check_all_exits(
    pos: &Position,
    snap: &IndicatorSnapshot,
    cfg: &StrategyConfig,
    current_time_ms: i64,
) -> ExitResult {
    let profit_atr = pos.profit_atr(snap.close);
    let duration_hours = pos.duration_hours(current_time_ms);

    // ── 0. Glitch guard — block exits during extreme price deviations ───
    if cfg.trade.block_exits_on_extreme_dev && snap.prev_close > 0.0 {
        let price_change_pct = (snap.close - snap.prev_close).abs() / snap.prev_close;
        let is_glitch = price_change_pct > cfg.trade.glitch_price_dev_pct
            || (snap.atr > 0.0
                && (snap.close - snap.prev_close).abs() > snap.atr * cfg.trade.glitch_atr_mult);
        if is_glitch {
            return ExitResult::no_exit();
        }
    }

    // ── 1. Stop loss ─────────────────────────────────────────────────────
    let sl = stop_loss::check_stop_loss(pos, snap, cfg);
    if sl.should_exit {
        return sl;
    }

    // ── 2. Trailing stop ─────────────────────────────────────────────────
    // compute_trailing returns Option<f64> (the trailing SL price).
    // Check if price has breached the trailing stop.
    if let Some(tsl_price) = trailing::compute_trailing(pos, snap, cfg, profit_atr) {
        let triggered = match pos.pos_type {
            PositionType::Long => snap.close <= tsl_price,
            PositionType::Short => snap.close >= tsl_price,
        };
        if triggered {
            return ExitResult::exit("Trailing Stop", snap.close);
        }
    }

    // ── 3. Take profit (partial first, then full) ────────────────────────
    let tp_mult = cfg.trade.tp_atr_mult;
    match take_profit::check_tp(pos, snap, cfg, tp_mult, profit_atr) {
        ExitAction::Close { reason } => {
            return ExitResult::exit(&reason, snap.close);
        }
        ExitAction::Reduce { reason, fraction } => {
            return ExitResult::partial_exit(&reason, snap.close, fraction);
        }
        ExitAction::Hold => {}
    }

    // ── 4. Smart exits ───────────────────────────────────────────────────
    if let Some(reason) = smart_exits::check(pos, snap, cfg, profit_atr, duration_hours) {
        return ExitResult::exit(&reason, snap.close);
    }

    ExitResult::no_exit()
}
