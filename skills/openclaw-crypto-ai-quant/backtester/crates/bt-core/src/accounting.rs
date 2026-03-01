//! Shared accounting primitives for fees, rounding, and position transitions.
//! This module keeps fee/funding and monetary calculations consistent across CPU
//! execution paths.

/// Precision scale used for deterministic rounding in the simulator.
pub const ACCOUNTING_QUANTUM: f64 = 1_000_000_000_000.0;

/// Default Hyperliquid fees (taker and maker currently identical in this model).
pub const DEFAULT_MAKER_FEE_BPS: f64 = 3.5;
pub const DEFAULT_TAKER_FEE_BPS: f64 = 3.5;

/// Convenience rate constants (bps converted to decimal).
pub const DEFAULT_MAKER_FEE_RATE: f64 = DEFAULT_MAKER_FEE_BPS / 10_000.0;
pub const DEFAULT_TAKER_FEE_RATE: f64 = DEFAULT_TAKER_FEE_BPS / 10_000.0;

/// Rounding helper shared by all runners.
#[inline]
pub fn quantize(value: f64) -> f64 {
    (value * ACCOUNTING_QUANTUM).round() / ACCOUNTING_QUANTUM
}

/// Fee role used by maker/taker models.
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FeeRole {
    Maker,
    Taker,
}

/// Shared taker/maker fee model.
#[derive(Debug, Clone, Copy)]
pub struct FeeModel {
    pub maker_fee_bps: f64,
    pub taker_fee_bps: f64,
}

impl Default for FeeModel {
    fn default() -> Self {
        Self {
            maker_fee_bps: DEFAULT_MAKER_FEE_BPS,
            taker_fee_bps: DEFAULT_TAKER_FEE_BPS,
        }
    }
}

impl FeeModel {
    #[inline]
    pub fn role_rate(self, role: FeeRole) -> f64 {
        match role {
            FeeRole::Maker => self.maker_fee_bps / 10_000.0,
            FeeRole::Taker => self.taker_fee_bps / 10_000.0,
        }
    }
}

/// Result of a directional accounting transition used by open/close operations.
#[derive(Debug, Clone, Copy)]
pub struct FillAccounting {
    pub notional: f64,
    pub fee_usd: f64,
    pub pnl: f64,
    pub cash_delta: f64,
}

pub fn apply_open_fill(notional: f64, fee_rate: f64) -> FillAccounting {
    let notional = quantize(notional);
    let fee_usd = quantize(notional * fee_rate);
    let cash_delta = quantize(-(notional + fee_usd));
    FillAccounting {
        notional,
        fee_usd,
        pnl: 0.0,
        cash_delta,
    }
}

#[inline]
pub fn mark_to_market_pnl(is_long: bool, entry_price: f64, exit_price: f64, size: f64) -> f64 {
    let raw_pnl = (exit_price - entry_price) * size;
    let pnl = if is_long { raw_pnl } else { -raw_pnl };
    quantize(pnl)
}

pub fn apply_close_fill(
    is_long: bool,
    entry_price: f64,
    exit_price: f64,
    size: f64,
    fee_rate: f64,
) -> FillAccounting {
    let notional = quantize(exit_price * size);
    let pnl = mark_to_market_pnl(is_long, entry_price, exit_price, size);
    let fee_usd = quantize(notional * fee_rate);
    let cash_delta = quantize(pnl - fee_usd);
    FillAccounting {
        notional,
        fee_usd,
        pnl,
        cash_delta,
    }
}

/// Returns the amount closed and remaining size/margin after a partial close.
#[derive(Debug, Clone, Copy)]
pub struct PartialClosePlan {
    pub closed_size: f64,
    pub remaining_size: f64,
    pub remaining_margin: f64,
}

#[inline]
pub fn build_partial_close_plan(size: f64, margin_used: f64, fraction: f64) -> PartialClosePlan {
    let fraction = fraction.clamp(0.0, 1.0);
    let closed_size = quantize(size * fraction);
    let remaining_size = quantize(size - closed_size);
    let remaining_margin = quantize(margin_used * (1.0 - fraction));
    PartialClosePlan {
        closed_size,
        remaining_size,
        remaining_margin,
    }
}

/// Hyperliquid-style funding formula used by both CPU and GPU model layers.
#[inline]
pub fn funding_delta(is_long: bool, size: f64, mark_price: f64, rate: f64) -> f64 {
    let signed_size = if is_long { size } else { -size };
    quantize(-signed_size * mark_price * rate)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn quantize_rounding_works_to_12_dp() {
        let value = 1.2345_6789_0123_4567;
        let rounded = quantize(value);
        assert_eq!(rounded, 1.234567890123);

        let tiny = 0.000_000_000_000_4;
        assert_eq!(quantize(tiny), 0.0);
    }

    #[test]
    fn partial_close_plan_clamps_fraction_and_updates_margin() {
        let plan = build_partial_close_plan(10.0, 3.5, 0.33);
        assert_eq!(plan.closed_size, 3.3);
        assert_eq!(plan.remaining_size, 6.7);
        assert_eq!(plan.remaining_margin, 2.345);

        let plan = build_partial_close_plan(10.0, 3.5, 2.0);
        assert_eq!(plan.closed_size, 10.0);
        assert_eq!(plan.remaining_size, 0.0);
        assert_eq!(plan.remaining_margin, 0.0);

        let plan = build_partial_close_plan(10.0, 3.5, -1.0);
        assert_eq!(plan.closed_size, 0.0);
        assert_eq!(plan.remaining_size, 10.0);
        assert_eq!(plan.remaining_margin, 3.5);
    }

    #[test]
    fn open_and_close_apply_shared_rules() {
        let open = apply_open_fill(10_000.0, DEFAULT_TAKER_FEE_RATE);
        assert_eq!(open.notional, 10_000.0);
        assert_eq!(open.fee_usd, 3.5);
        assert_eq!(open.cash_delta, -10_003.5);

        let close = apply_close_fill(true, 10_000.0, 10_200.0, 0.001, DEFAULT_TAKER_FEE_RATE);
        assert_eq!(close.notional, 10.2);
        assert_eq!(close.fee_usd, 0.00357);
        assert_eq!(close.pnl, 0.2);
        assert_eq!(close.cash_delta, 0.19643);
    }

    #[test]
    fn fee_model_selects_maker_or_taker_rate() {
        let model = FeeModel {
            maker_fee_bps: 1.0,
            taker_fee_bps: 2.0,
        };

        assert!((model.role_rate(FeeRole::Maker) - 0.0001).abs() < 1e-12);
        assert!((model.role_rate(FeeRole::Taker) - 0.0002).abs() < 1e-12);
    }

    #[test]
    fn close_pnl_is_directional() {
        let long = apply_close_fill(true, 10_000.0, 10_200.0, 1.0, DEFAULT_TAKER_FEE_RATE);
        let short = apply_close_fill(false, 10_000.0, 10_200.0, 1.0, DEFAULT_TAKER_FEE_RATE);

        assert_eq!(long.pnl, 200.0);
        assert_eq!(short.pnl, -200.0);
    }

    #[test]
    fn funding_delta_signs_are_long_short_consistent() {
        let long_delta = funding_delta(true, 2.0, 10_000.0, 0.0001);
        let short_delta = funding_delta(false, 2.0, 10_000.0, 0.0001);
        assert!(long_delta < 0.0);
        assert!(short_delta > 0.0);
        assert_eq!(long_delta, -2.0);
        assert_eq!(short_delta, 2.0);
    }
}
