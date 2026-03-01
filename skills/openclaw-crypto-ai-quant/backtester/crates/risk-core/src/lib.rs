//! Shared, pure risk primitives used across backtesting and live-adjacent code.
//!
//! This crate intentionally keeps business logic free from engine state and I/O.

/// Confidence tier used by risk sizing helpers.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConfidenceTier {
    Low,
    Medium,
    High,
}

/// Inputs for entry sizing.
#[derive(Debug, Clone, Copy)]
pub struct EntrySizingInput {
    pub equity: f64,
    pub price: f64,
    pub atr: f64,
    pub adx: f64,
    pub confidence: ConfidenceTier,
    pub allocation_pct: f64,
    pub enable_dynamic_sizing: bool,
    pub confidence_mult_high: f64,
    pub confidence_mult_medium: f64,
    pub confidence_mult_low: f64,
    pub adx_sizing_min_mult: f64,
    pub adx_sizing_full_adx: f64,
    pub vol_baseline_pct: f64,
    pub vol_scalar_min: f64,
    pub vol_scalar_max: f64,
    pub leverage_low: f64,
    pub leverage_medium: f64,
    pub leverage_high: f64,
}

/// Entry sizing output values.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct EntrySizingResult {
    pub size: f64,
    pub margin_used: f64,
    pub leverage: f64,
    pub notional: f64,
}

/// Compute entry size, margin usage and leverage from strategy risk settings.
pub fn compute_entry_sizing(input: EntrySizingInput) -> EntrySizingResult {
    let mut margin_used = input.equity * input.allocation_pct;

    if input.enable_dynamic_sizing {
        let confidence_mult = match input.confidence {
            ConfidenceTier::High => input.confidence_mult_high,
            ConfidenceTier::Medium => input.confidence_mult_medium,
            ConfidenceTier::Low => input.confidence_mult_low,
        };

        let adx_mult = if input.adx_sizing_full_adx > 0.0 {
            (input.adx / input.adx_sizing_full_adx).clamp(input.adx_sizing_min_mult, 1.0)
        } else {
            input.adx_sizing_min_mult
        };

        let vol_ratio = if input.vol_baseline_pct > 0.0 && input.price > 0.0 {
            (input.atr / input.price) / input.vol_baseline_pct
        } else {
            1.0
        };
        let vol_scalar_raw = if vol_ratio > 0.0 {
            1.0 / vol_ratio
        } else {
            1.0
        };
        let vol_scalar = vol_scalar_raw.clamp(input.vol_scalar_min, input.vol_scalar_max);

        margin_used *= confidence_mult * adx_mult * vol_scalar;
    }

    // Always use per-confidence-tier leverage (low/medium/high).
    let leverage = match input.confidence {
        ConfidenceTier::High => input.leverage_high,
        ConfidenceTier::Medium => input.leverage_medium,
        ConfidenceTier::Low => input.leverage_low,
    };

    let notional = margin_used * leverage;
    let size = if input.price > 0.0 {
        notional / input.price
    } else {
        0.0
    };

    EntrySizingResult {
        size,
        margin_used,
        leverage,
        notional,
    }
}

/// Inputs for add/pyramid sizing.
#[derive(Debug, Clone, Copy)]
pub struct PyramidSizingInput {
    pub equity: f64,
    pub price: f64,
    pub leverage: f64,
    pub allocation_pct: f64,
    pub add_fraction_of_base_margin: f64,
    pub min_notional_usd: f64,
    pub bump_to_min_notional: bool,
}

/// Add/pyramid sizing output values.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PyramidSizingResult {
    pub add_size: f64,
    pub add_margin: f64,
    pub add_notional: f64,
}

/// Compute add/pyramid size using base allocation and existing position leverage.
pub fn compute_pyramid_sizing(input: PyramidSizingInput) -> Option<PyramidSizingResult> {
    if input.price <= 0.0 {
        return None;
    }

    let base_margin = input.equity * input.allocation_pct;
    let add_margin = base_margin * input.add_fraction_of_base_margin;

    let mut add_notional = add_margin * input.leverage;
    let mut add_size = add_notional / input.price;

    if add_notional < input.min_notional_usd {
        if input.bump_to_min_notional {
            add_notional = input.min_notional_usd;
            add_size = add_notional / input.price;
        } else {
            return None;
        }
    }

    Some(PyramidSizingResult {
        add_size,
        add_margin,
        add_notional,
    })
}

/// Why exposure guard blocked a trade attempt.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ExposureBlockReason {
    MaxOpenPositions,
    MarginCap,
}

/// Inputs for exposure checks.
#[derive(Debug, Clone, Copy)]
pub struct ExposureGuardInput {
    pub open_positions: usize,
    pub max_open_positions: Option<usize>,
    pub total_margin_used: f64,
    pub equity: f64,
    pub max_total_margin_pct: f64,
    /// If true, exactly zero remaining margin is allowed.
    pub allow_zero_margin_headroom: bool,
}

/// Exposure decision for entry/add attempts.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct ExposureGuardDecision {
    pub allowed: bool,
    pub margin_headroom: f64,
    pub blocked_reason: Option<ExposureBlockReason>,
}

/// Evaluate max-open-position and margin-cap exposure constraints.
pub fn evaluate_exposure_guard(input: ExposureGuardInput) -> ExposureGuardDecision {
    let margin_headroom = input.equity * input.max_total_margin_pct - input.total_margin_used;

    if let Some(max_open_positions) = input.max_open_positions {
        if input.open_positions >= max_open_positions {
            return ExposureGuardDecision {
                allowed: false,
                margin_headroom,
                blocked_reason: Some(ExposureBlockReason::MaxOpenPositions),
            };
        }
    }

    let blocked_by_margin = if input.allow_zero_margin_headroom {
        margin_headroom < 0.0
    } else {
        margin_headroom <= 0.0
    };
    if blocked_by_margin {
        return ExposureGuardDecision {
            allowed: false,
            margin_headroom,
            blocked_reason: Some(ExposureBlockReason::MarginCap),
        };
    }

    ExposureGuardDecision {
        allowed: true,
        margin_headroom,
        blocked_reason: None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn entry_sizing_dynamic_path_matches_expected_values() {
        let out = compute_entry_sizing(EntrySizingInput {
            equity: 10_000.0,
            price: 100.0,
            atr: 1.0,
            adx: 0.0,
            confidence: ConfidenceTier::High,
            allocation_pct: 0.03,
            enable_dynamic_sizing: true,
            confidence_mult_high: 1.0,
            confidence_mult_medium: 0.8,
            confidence_mult_low: 0.6,
            adx_sizing_min_mult: 0.6,
            adx_sizing_full_adx: 40.0,
            vol_baseline_pct: 0.01,
            vol_scalar_min: 0.6,
            vol_scalar_max: 1.4,
            leverage_low: 1.0,
            leverage_medium: 3.0,
            leverage_high: 5.0,
        });

        assert!((out.margin_used - 180.0).abs() < 1e-9);
        assert!((out.leverage - 5.0).abs() < 1e-9);
        assert!((out.notional - 900.0).abs() < 1e-9);
        assert!((out.size - 9.0).abs() < 1e-9);
    }

    #[test]
    fn entry_sizing_with_zero_price_returns_zero_size() {
        let out = compute_entry_sizing(EntrySizingInput {
            equity: 1_000.0,
            price: 0.0,
            atr: 1.0,
            adx: 30.0,
            confidence: ConfidenceTier::Medium,
            allocation_pct: 0.03,
            enable_dynamic_sizing: false,
            confidence_mult_high: 1.0,
            confidence_mult_medium: 1.0,
            confidence_mult_low: 1.0,
            adx_sizing_min_mult: 0.6,
            adx_sizing_full_adx: 40.0,
            vol_baseline_pct: 0.01,
            vol_scalar_min: 0.6,
            vol_scalar_max: 1.4,
            leverage_low: 1.0,
            leverage_medium: 2.0,
            leverage_high: 5.0,
        });

        // Medium confidence → leverage_medium=2.0, margin=30, notional=60
        assert!((out.margin_used - 30.0).abs() < 1e-9);
        assert!((out.leverage - 2.0).abs() < 1e-9);
        assert!((out.notional - 60.0).abs() < 1e-9);
        assert!((out.size - 0.0).abs() < 1e-9);
    }

    #[test]
    fn pyramid_sizing_bumps_notional_without_changing_margin() {
        let out = compute_pyramid_sizing(PyramidSizingInput {
            equity: 1_000.0,
            price: 100.0,
            leverage: 2.0,
            allocation_pct: 0.01,
            add_fraction_of_base_margin: 0.5,
            min_notional_usd: 15.0,
            bump_to_min_notional: true,
        })
        .expect("sizing should succeed");

        assert!((out.add_margin - 5.0).abs() < 1e-9);
        assert!((out.add_notional - 15.0).abs() < 1e-9);
        assert!((out.add_size - 0.15).abs() < 1e-9);
    }

    #[test]
    fn pyramid_sizing_rejects_below_min_notional_when_bump_disabled() {
        let out = compute_pyramid_sizing(PyramidSizingInput {
            equity: 1_000.0,
            price: 100.0,
            leverage: 2.0,
            allocation_pct: 0.01,
            add_fraction_of_base_margin: 0.5,
            min_notional_usd: 15.0,
            bump_to_min_notional: false,
        });
        assert!(out.is_none());
    }

    #[test]
    fn exposure_guard_blocks_max_positions_before_margin_cap() {
        let d = evaluate_exposure_guard(ExposureGuardInput {
            open_positions: 5,
            max_open_positions: Some(5),
            total_margin_used: 1_000.0,
            equity: 1_000.0,
            max_total_margin_pct: 0.5,
            allow_zero_margin_headroom: false,
        });
        assert!(!d.allowed);
        assert_eq!(
            d.blocked_reason,
            Some(ExposureBlockReason::MaxOpenPositions)
        );
        assert!((d.margin_headroom + 500.0).abs() < 1e-9);
    }

    #[test]
    fn exposure_guard_blocks_on_non_positive_headroom_by_default() {
        let d = evaluate_exposure_guard(ExposureGuardInput {
            open_positions: 1,
            max_open_positions: Some(10),
            total_margin_used: 500.0,
            equity: 1_000.0,
            max_total_margin_pct: 0.5,
            allow_zero_margin_headroom: false,
        });
        assert!(!d.allowed);
        assert_eq!(d.blocked_reason, Some(ExposureBlockReason::MarginCap));
        assert!((d.margin_headroom - 0.0).abs() < 1e-9);
    }

    #[test]
    fn exposure_guard_allows_zero_headroom_when_requested() {
        let d = evaluate_exposure_guard(ExposureGuardInput {
            open_positions: 1,
            max_open_positions: None,
            total_margin_used: 500.0,
            equity: 1_000.0,
            max_total_margin_pct: 0.5,
            allow_zero_margin_headroom: true,
        });
        assert!(d.allowed);
        assert_eq!(d.blocked_reason, None);
        assert!((d.margin_headroom - 0.0).abs() < 1e-9);
    }
}
