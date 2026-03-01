//! Precision tier tolerances for GPU (f32) vs CPU (f64) validation.
//!
//! The GPU decision kernel uses f32 for all computation, while the CPU
//! reference engine uses f64. This module defines formal tolerance tiers
//! for validating that f32 results remain acceptable across different
//! categories of computation.
//!
//! # Tiers
//!
//! | Tier | Tolerance   | Use Case                                          |
//! |------|-------------|---------------------------------------------------|
//! | T0   | 0 (exact)   | Boolean comparisons, enum values, gate pass/fail  |
//! | T1   | ≈1.19e-7    | Config lookups, direct threshold comparisons       |
//! | T2   | ≤1e-6       | Single arithmetic ops (price × atr_mult, etc.)    |
//! | T3   | ≤1e-5       | Multi-step chains (EMA value, ADX smoothing)      |
//! | T4   | ≤1e-3       | Running sums, equity curves, cumulative PnL,      |
//! |      |             | and subtraction of correlated large values         |
//!
//! # Note on catastrophic cancellation
//!
//! Subtracting two large correlated f32 values (e.g., `EMA_12 − EMA_26`
//! where both are ~50000) amplifies relative error of the *difference*
//! well beyond what the constituent values' errors suggest. For BTC-scale
//! prices, MACD line, EMA deviation, and similar "difference of large
//! correlated values" operations empirically show 1e-4 to 5e-4 relative
//! error — firmly in T4 territory regardless of chain length.

/// T0: Exact match — booleans, enums, gate pass/fail.
pub const TIER_T0_TOLERANCE: f64 = 0.0;

/// T1: f32 round-trip — `f64 → f32 → f64` introduces at most one ULP of
/// relative error, which for f32 is `2^{-23} ≈ 1.19e-7`.
pub const TIER_T1_TOLERANCE: f64 = 1.2e-7;

/// T2: Single arithmetic operation — one multiply or divide in f32.
pub const TIER_T2_TOLERANCE: f64 = 1.0e-6;

/// T3: Chained operations — multi-step computation chains (5–10 ops)
/// where operands are independent (no catastrophic cancellation).
pub const TIER_T3_TOLERANCE: f64 = 1.0e-5;

/// T4: Accumulated error — running sums over hundreds/thousands of bars,
/// and operations involving subtraction of correlated large values
/// (catastrophic cancellation). Empirically measured up to ~5e-4 for
/// MACD histogram over 30 bars on BTC-scale prices.
pub const TIER_T4_TOLERANCE: f64 = 1.0e-3;

/// Check whether `actual` is within `tier_tol` relative error of `expected`.
///
/// Special cases:
/// - Both zero → true (no error).
/// - `expected` is zero but `actual` is not → compare `|actual|` against
///   `tier_tol` (absolute fallback to avoid division by zero).
/// - Otherwise → standard relative error `|actual − expected| / |expected|`.
pub fn within_tolerance(expected: f64, actual: f64, tier_tol: f64) -> bool {
    if expected == 0.0 && actual == 0.0 {
        return true;
    }
    if expected == 0.0 {
        return actual.abs() < tier_tol;
    }
    let rel = ((actual - expected) / expected).abs();
    rel <= tier_tol
}

/// T0 exact-match helper for booleans, enums, and other discrete values.
pub fn exact_match<T: PartialEq>(expected: T, actual: T) -> bool {
    expected == actual
}

/// Compute the relative error between `expected` (f64 reference) and `actual`
/// (f32-derived value cast back to f64).
///
/// Returns `0.0` when both values are zero. When `expected` is zero and
/// `actual` is not, returns `f64::INFINITY` to signal unbounded relative error.
pub fn relative_error(expected: f64, actual: f64) -> f64 {
    if expected == 0.0 && actual == 0.0 {
        return 0.0;
    }
    if expected == 0.0 {
        return f64::INFINITY;
    }
    ((actual - expected) / expected).abs()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn within_tolerance_both_zero() {
        assert!(within_tolerance(0.0, 0.0, TIER_T0_TOLERANCE));
    }

    #[test]
    fn within_tolerance_expected_zero_actual_tiny() {
        // |actual| < tier_tol should pass
        assert!(within_tolerance(0.0, 1e-8, TIER_T1_TOLERANCE));
        // |actual| > tier_tol should fail
        assert!(!within_tolerance(0.0, 1.0, TIER_T1_TOLERANCE));
    }

    #[test]
    fn within_tolerance_exact() {
        assert!(within_tolerance(42.0, 42.0, TIER_T0_TOLERANCE));
        assert!(!within_tolerance(42.0, 42.0001, TIER_T0_TOLERANCE));
    }

    #[test]
    fn within_tolerance_tier_boundaries() {
        let expected = 1_000_000.0;
        // 1e-7 relative = 0.1 absolute on 1M
        let actual_t1_pass = expected + expected * 1.0e-7;
        assert!(within_tolerance(
            expected,
            actual_t1_pass,
            TIER_T1_TOLERANCE
        ));

        let actual_t1_fail = expected + expected * 2.0e-7;
        assert!(!within_tolerance(
            expected,
            actual_t1_fail,
            TIER_T1_TOLERANCE
        ));
    }

    #[test]
    fn relative_error_basics() {
        assert_eq!(relative_error(0.0, 0.0), 0.0);
        assert_eq!(relative_error(0.0, 1.0), f64::INFINITY);
        assert!((relative_error(100.0, 100.01) - 1e-4).abs() < 1e-12);
    }

    #[test]
    fn exact_match_works() {
        assert!(exact_match(true, true));
        assert!(!exact_match(true, false));
        assert!(exact_match(42u32, 42u32));
        assert!(!exact_match(42u32, 43u32));
    }
}
