//! Position tracking and PnL accounting for the backtesting simulator.
//!
//! Provides [`Position`] for open position state, [`TradeRecord`] for the
//! trade log (entries, exits, adds), and [`SignalRecord`] for the raw signal
//! audit trail.

use crate::config::{Confidence, Signal};
use crate::indicators::IndicatorSnapshot;
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Position type enum
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PositionType {
    Long,
    Short,
}

impl std::fmt::Display for PositionType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PositionType::Long => write!(f, "LONG"),
            PositionType::Short => write!(f, "SHORT"),
        }
    }
}

// ---------------------------------------------------------------------------
// Position
// ---------------------------------------------------------------------------

/// An open position in the simulator.
#[derive(Debug, Clone)]
pub struct Position {
    pub symbol: String,
    pub pos_type: PositionType,
    pub entry_price: f64,
    pub size: f64, // base asset units
    pub confidence: Confidence,
    pub entry_atr: f64,
    /// ADX threshold used at entry — exit ADX exhaustion uses this value
    /// so entry and exit can never contradict each other.
    pub entry_adx_threshold: f64,
    pub trailing_sl: Option<f64>,
    pub leverage: f64,
    pub margin_used: f64,
    pub adds_count: u32,
    pub tp1_taken: bool,
    pub open_time_ms: i64,
    pub last_add_time_ms: i64,
    /// Most adverse excursion (minimum unrealised PnL) observed while the position was open.
    /// Stored as a signed USD value (typically <= 0.0).
    pub mae_usd: f64,
    /// Most favourable excursion (maximum unrealised PnL) observed while the position was open.
    /// Stored as a signed USD value (typically >= 0.0).
    pub mfe_usd: f64,
}

impl Position {
    /// Unrealised profit in USD at `current_price`.
    pub fn profit_usd(&self, current_price: f64) -> f64 {
        match self.pos_type {
            PositionType::Long => (current_price - self.entry_price) * self.size,
            PositionType::Short => (self.entry_price - current_price) * self.size,
        }
    }

    /// Unrealised profit measured in ATR units.
    pub fn profit_atr(&self, current_price: f64) -> f64 {
        if self.entry_atr <= 0.0 {
            return 0.0;
        }
        let price_diff = match self.pos_type {
            PositionType::Long => current_price - self.entry_price,
            PositionType::Short => self.entry_price - current_price,
        };
        price_diff / self.entry_atr
    }

    /// Current notional value in USD.
    pub fn notional_usd(&self, current_price: f64) -> f64 {
        self.size * current_price
    }

    /// Whether the position is currently losing money.
    pub fn is_underwater(&self, current_price: f64) -> bool {
        self.profit_usd(current_price) < 0.0
    }

    /// Duration in hours since position was opened.
    pub fn duration_hours(&self, current_time_ms: i64) -> f64 {
        let elapsed_ms = (current_time_ms - self.open_time_ms).max(0);
        elapsed_ms as f64 / 3_600_000.0
    }

    /// Duration in minutes since position was opened.
    pub fn duration_minutes(&self, current_time_ms: i64) -> f64 {
        let elapsed_ms = (current_time_ms - self.open_time_ms).max(0);
        elapsed_ms as f64 / 60_000.0
    }

    /// Reduce position size by a fraction (0.0..1.0). Returns the size removed.
    /// Adjusts margin_used proportionally.
    pub fn reduce_by_fraction(&mut self, fraction: f64) -> f64 {
        let fraction = fraction.clamp(0.0, 1.0);
        let removed = self.size * fraction;
        self.size -= removed;
        self.margin_used *= 1.0 - fraction;
        removed
    }

    /// Compute the weighted-average entry after adding `add_size` units at `add_price`.
    pub fn add_to_position(
        &mut self,
        add_price: f64,
        add_size: f64,
        add_margin: f64,
        time_ms: i64,
    ) {
        let total_size = self.size + add_size;
        // H10: near-zero guard — prevent extreme entry_price from tiny denominator
        if total_size < 1e-12 {
            self.entry_price = add_price;
        } else {
            self.entry_price = (self.entry_price * self.size + add_price * add_size) / total_size;
        }
        self.size = total_size;
        self.margin_used += add_margin;
        self.adds_count += 1;
        self.last_add_time_ms = time_ms;
    }

    /// Update MAE/MFE based on the current mark price.
    pub fn update_excursions(&mut self, current_price: f64) {
        let u = self.profit_usd(current_price);
        if u > self.mfe_usd {
            self.mfe_usd = u;
        }
        if u < self.mae_usd {
            self.mae_usd = u;
        }
    }
}

// ---------------------------------------------------------------------------
// Exit context (exit parameter snapshot attached to close/reduce trades)
// ---------------------------------------------------------------------------

/// Captures exit parameters and position state at the moment of exit.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct ExitContext {
    pub trailing_active: bool,
    pub trailing_high_water_mark: f64,
    pub sl_atr_mult_applied: f64,
    pub tp_atr_mult_applied: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub smart_exit_threshold: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub indicator_at_exit: Option<IndicatorSnapshot>,
    pub bars_held: u32,
    pub max_unrealized_pnl: f64,
    pub min_unrealized_pnl: f64,
}

// ---------------------------------------------------------------------------
// Trade record (log entry for each trade action)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Default)]
pub struct TradeRecord {
    pub timestamp_ms: i64,
    pub symbol: String,
    /// Action string: "OPEN_LONG", "OPEN_SHORT", "CLOSE_LONG", "CLOSE_SHORT",
    /// "ADD_LONG", "ADD_SHORT", "REDUCE_LONG", "REDUCE_SHORT".
    pub action: String,
    pub price: f64,
    pub size: f64,
    pub notional: f64,
    pub reason: String,
    pub confidence: Confidence,
    pub pnl: f64, // 0 for opens/adds, realized PnL for closes
    pub fee_usd: f64,
    pub balance: f64, // balance after trade
    pub entry_atr: f64,
    pub leverage: f64,
    pub margin_used: f64,
    /// Most adverse excursion (minimum unrealised PnL) observed while the position was open.
    /// Only meaningful for close/reduce records.
    pub mae_usd: f64,
    /// Most favourable excursion (maximum unrealised PnL) observed while the position was open.
    /// Only meaningful for close/reduce records.
    pub mfe_usd: f64,
    /// Exit parameters and position state at exit. Only populated for close/reduce records.
    pub exit_context: Option<ExitContext>,
}

impl TradeRecord {
    /// True if this record represents a position close (full or partial).
    pub fn is_close(&self) -> bool {
        self.action.starts_with("CLOSE") || self.action.starts_with("REDUCE")
    }

    /// True if this record represents a new position open.
    pub fn is_open(&self) -> bool {
        self.action.starts_with("OPEN")
    }

    /// True if PnL is positive (winning trade).
    pub fn is_winner(&self) -> bool {
        self.pnl > 0.0
    }
}

// ---------------------------------------------------------------------------
// Signal record (raw signal audit trail)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct SignalRecord {
    pub timestamp_ms: i64,
    pub symbol: String,
    pub signal: Signal,
    pub confidence: Confidence,
    pub price: f64,
    pub adx: f64,
    pub rsi: f64,
    pub atr: f64,
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn make_long_pos(entry: f64) -> Position {
        Position {
            symbol: "BTC".to_string(),
            pos_type: PositionType::Long,
            entry_price: entry,
            size: 0.1,
            confidence: Confidence::High,
            entry_atr: entry * 0.01,
            entry_adx_threshold: 22.0,
            trailing_sl: None,
            leverage: 3.0,
            margin_used: entry * 0.1 / 3.0,
            adds_count: 0,
            tp1_taken: false,
            open_time_ms: 0,
            last_add_time_ms: 0,
            mae_usd: 0.0,
            mfe_usd: 0.0,
        }
    }

    #[test]
    fn test_profit_usd_long() {
        let pos = make_long_pos(100.0);
        assert!((pos.profit_usd(105.0) - 0.5).abs() < 0.001);
        assert!((pos.profit_usd(95.0) - (-0.5)).abs() < 0.001);
    }

    #[test]
    fn test_profit_usd_short() {
        let mut pos = make_long_pos(100.0);
        pos.pos_type = PositionType::Short;
        assert!((pos.profit_usd(95.0) - 0.5).abs() < 0.001);
        assert!((pos.profit_usd(105.0) - (-0.5)).abs() < 0.001);
    }

    #[test]
    fn test_profit_atr() {
        let pos = make_long_pos(100.0);
        // entry_atr = 1.0, price moved +2 -> profit_atr = 2.0
        assert!((pos.profit_atr(102.0) - 2.0).abs() < 0.001);
    }

    #[test]
    fn test_is_underwater() {
        let pos = make_long_pos(100.0);
        assert!(pos.is_underwater(99.0));
        assert!(!pos.is_underwater(101.0));
    }

    #[test]
    fn test_duration_hours() {
        let pos = make_long_pos(100.0);
        let hours = pos.duration_hours(3_600_000);
        assert!((hours - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_reduce_by_fraction() {
        let mut pos = make_long_pos(100.0);
        let original_size = pos.size;
        let original_margin = pos.margin_used;
        let removed = pos.reduce_by_fraction(0.5);
        assert!((removed - original_size * 0.5).abs() < 1e-9);
        assert!((pos.size - original_size * 0.5).abs() < 1e-9);
        assert!((pos.margin_used - original_margin * 0.5).abs() < 1e-9);
    }

    #[test]
    fn test_add_to_position() {
        let mut pos = make_long_pos(100.0);
        // size=0.1 @ 100, add 0.1 @ 110 -> avg = (100*0.1 + 110*0.1)/0.2 = 105
        pos.add_to_position(110.0, 0.1, 3.67, 60_000);
        assert!((pos.entry_price - 105.0).abs() < 0.001);
        assert!((pos.size - 0.2).abs() < 1e-9);
        assert_eq!(pos.adds_count, 1);
        assert_eq!(pos.last_add_time_ms, 60_000);
    }

    #[test]
    fn test_trade_record_helpers() {
        let tr = TradeRecord {
            timestamp_ms: 0,
            symbol: "ETH".to_string(),
            action: "CLOSE_LONG".to_string(),
            price: 100.0,
            size: 1.0,
            notional: 100.0,
            reason: "Take Profit".to_string(),
            confidence: Confidence::High,
            pnl: 5.0,
            fee_usd: 0.035,
            balance: 1005.0,
            entry_atr: 1.0,
            leverage: 3.0,
            margin_used: 33.33,
            mae_usd: 0.0,
            mfe_usd: 0.0,
            exit_context: None,
        };
        assert!(tr.is_close());
        assert!(!tr.is_open());
        assert!(tr.is_winner());
    }
}
