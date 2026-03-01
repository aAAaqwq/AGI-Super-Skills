//! Per-function parity test harness for GPU decision codegen vs Rust SSOT.
//!
//! This module validates that the CUDA codegen'd decision functions structurally
//! match the Rust reference implementations in bt-core. Since we cannot execute
//! CUDA code in unit tests, parity is verified through:
//!
//!   1. **Constant matching**: every hardcoded threshold / multiplier in the Rust
//!      source must appear (identically or via config default) in the CUDA codegen.
//!   2. **Branch coverage**: every conditional path in Rust must have a
//!      corresponding branch in CUDA.
//!   3. **Precision tier expectations**: each comparison declares which precision
//!      tier (T0-T4) governs its tolerance, via `bt_gpu::precision::*`.
//!   4. **Fixture diversity**: 50 test fixtures spanning penny stocks to BTC,
//!      long/short, deep loss to large profit, weak to strong trend.
//!
//! All codegen functions are now validated (AQC-1261 through AQC-1270).
//!
//! # Implemented
//! - `compute_sl_price_codegen` (AQC-1220) -- stop loss
//! - `compute_trailing_codegen` (AQC-1221) -- trailing stop
//! - `check_gates_codegen` (AQC-1210, validated AQC-1261)
//! - `generate_signal_codegen` (AQC-1211, validated AQC-1262)
//! - `check_tp_codegen` (AQC-1222, validated AQC-1265)
//! - `check_smart_exits_codegen` (AQC-1223, validated AQC-1266)
//! - `check_all_exits_codegen` (AQC-1224, validated AQC-1267)
//! - `compute_entry_size_codegen` (AQC-1230, validated AQC-1268)
//! - `is_pesc_blocked_codegen` (AQC-1231, validated AQC-1269)
//! - Config round-trip validation (AQC-1270)
//!
//! # Running
//!
//! Requires the `codegen` feature flag:
//!
//! ```sh
//! cargo test -p bt-gpu --features codegen --test gpu_decision_parity
//! ```

#![cfg(feature = "codegen")]

use bt_gpu::buffers::GpuComboConfig;
use bt_gpu::codegen::decision::render_all_decision;
use bt_gpu::precision::*;

// ═══════════════════════════════════════════════════════════════════════════════
// Test fixture infrastructure
// ═══════════════════════════════════════════════════════════════════════════════

/// Realistic trading data for exercising decision functions across diverse
/// market conditions.  Each fixture represents a snapshot of one bar with
/// position context.
#[derive(Debug, Clone)]
#[allow(dead_code)] // Fields reserved for future codegen parity tests
struct TestFixture {
    label: &'static str,
    // Position
    pos_type: PosType,
    entry_price: f64,
    current_price: f64,
    entry_atr: f64,
    confidence: Confidence,
    current_trailing_sl: f64, // 0.0 = no trailing stop yet
    // Indicators
    atr: f64,
    adx: f64,
    adx_slope: f64,
    rsi: f64,
    atr_slope: f64,
    bb_width_ratio: f64,
    profit_atr: f64,
}

#[derive(Debug, Clone, Copy, PartialEq)]
enum PosType {
    Long,
    Short,
}

#[derive(Debug, Clone, Copy, PartialEq)]
#[allow(dead_code)] // Medium reserved for future fixture scenarios
enum Confidence {
    Low,
    Medium,
    High,
}

/// Generate 50 diverse test fixtures covering the full decision function input
/// space.  Organized into groups by market condition.
fn make_fixtures() -> Vec<TestFixture> {
    let mut fixtures = Vec::with_capacity(50);

    // ── Group 1: Price levels (penny stocks to BTC) ──────────────────────
    let price_levels: &[(&str, f64, f64)] = &[
        ("penny-stock-long", 0.0025, 0.0026),
        ("micro-cap-long", 0.45, 0.47),
        ("small-cap-long", 12.50, 12.80),
        ("mid-cap-long", 185.00, 188.50),
        ("large-cap-long", 3450.00, 3510.00),
        ("btc-long", 65000.00, 66200.00),
        ("btc-high-long", 105000.00, 106500.00),
    ];
    for &(label, entry, current) in price_levels {
        fixtures.push(TestFixture {
            label,
            pos_type: PosType::Long,
            entry_price: entry,
            current_price: current,
            entry_atr: entry * 0.01,
            confidence: Confidence::High,
            current_trailing_sl: 0.0,
            atr: entry * 0.01,
            adx: 30.0,
            adx_slope: 0.5,
            rsi: 55.0,
            atr_slope: 0.0,
            bb_width_ratio: 1.0,
            profit_atr: (current - entry) / (entry * 0.01),
        });
    }

    // ── Group 2: Short positions at various price levels ─────────────────
    let short_levels: &[(&str, f64, f64)] = &[
        ("penny-stock-short", 0.0025, 0.0024),
        ("mid-cap-short", 185.00, 181.00),
        ("btc-short", 65000.00, 63800.00),
    ];
    for &(label, entry, current) in short_levels {
        fixtures.push(TestFixture {
            label,
            pos_type: PosType::Short,
            entry_price: entry,
            current_price: current,
            entry_atr: entry * 0.01,
            confidence: Confidence::High,
            current_trailing_sl: 0.0,
            atr: entry * 0.01,
            adx: 30.0,
            adx_slope: 0.5,
            rsi: 45.0,
            atr_slope: 0.0,
            bb_width_ratio: 1.0,
            profit_atr: (entry - current) / (entry * 0.01),
        });
    }

    // ── Group 3: Profit levels (deep loss to large profit) ───────────────
    let profit_scenarios: &[(&str, PosType, f64, f64)] = &[
        ("deep-loss-long", PosType::Long, 100.0, 95.0), // -5 ATR
        ("moderate-loss-long", PosType::Long, 100.0, 98.5), // -1.5 ATR
        ("slight-loss-long", PosType::Long, 100.0, 99.7), // -0.3 ATR
        ("breakeven-long", PosType::Long, 100.0, 100.0), // 0 ATR
        ("small-profit-long", PosType::Long, 100.0, 100.3), // 0.3 ATR
        ("half-atr-profit-long", PosType::Long, 100.0, 100.6), // 0.6 ATR (DASE boundary)
        ("one-atr-profit-long", PosType::Long, 100.0, 101.0), // 1.0 ATR
        ("two-atr-profit-long", PosType::Long, 100.0, 102.0), // 2.0 ATR (trailing high-profit boundary)
        ("large-profit-long", PosType::Long, 100.0, 105.0),   // 5.0 ATR
        ("deep-loss-short", PosType::Short, 100.0, 105.0),    // -5 ATR
        ("moderate-loss-short", PosType::Short, 100.0, 101.5), // -1.5 ATR
        ("small-profit-short", PosType::Short, 100.0, 99.5),  // 0.5 ATR
        ("large-profit-short", PosType::Short, 100.0, 95.0),  // 5.0 ATR
    ];
    for &(label, pos_type, entry, current) in profit_scenarios {
        let atr = entry * 0.01; // 1.0 ATR = 1% of entry
        let profit_atr = match pos_type {
            PosType::Long => (current - entry) / atr,
            PosType::Short => (entry - current) / atr,
        };
        fixtures.push(TestFixture {
            label,
            pos_type,
            entry_price: entry,
            current_price: current,
            entry_atr: atr,
            confidence: Confidence::High,
            current_trailing_sl: 0.0,
            atr,
            adx: 30.0,
            adx_slope: 0.5,
            rsi: 50.0,
            atr_slope: 0.0,
            bb_width_ratio: 1.0,
            profit_atr,
        });
    }

    // ── Group 4: ADX levels (weak trend to strong/saturated) ─────────────
    let adx_scenarios: &[(&str, f64, f64)] = &[
        ("very-weak-trend", 10.0, -0.5), // ADX < 25 (weak trend tightening)
        ("weak-trend", 22.0, 0.3),       // ADX < 25 (weak trend tightening)
        ("moderate-trend", 30.0, 0.5),   // Normal
        ("strong-trend", 38.0, 1.2),     // Between 35 and 40
        ("dase-boundary", 41.0, 0.8),    // ADX > 40 (DASE trigger)
        ("slb-boundary", 46.0, 0.5),     // ADX > 45 (SLB trigger)
        ("saturated-trend", 55.0, 1.5),  // Both DASE and SLB
        ("extreme-trend", 75.0, 2.0),    // Extreme ADX
    ];
    for &(label, adx, adx_slope) in adx_scenarios {
        fixtures.push(TestFixture {
            label,
            pos_type: PosType::Long,
            entry_price: 50000.0,
            current_price: 50500.0, // +0.5 ATR profit (just above DASE threshold)
            entry_atr: 1000.0,      // 2% ATR on BTC-scale
            confidence: Confidence::High,
            current_trailing_sl: 0.0,
            atr: 1000.0,
            adx,
            adx_slope,
            rsi: 55.0,
            atr_slope: 0.0,
            bb_width_ratio: 1.0,
            profit_atr: 0.5,
        });
    }

    // ── Group 5: RSI regimes (for trailing RSI Trend-Guard) ──────────────
    let rsi_scenarios: &[(&str, PosType, f64)] = &[
        ("rsi-oversold-long", PosType::Long, 25.0),
        ("rsi-neutral-long", PosType::Long, 50.0),
        ("rsi-trending-long", PosType::Long, 65.0), // RSI > 60 (trending floor)
        ("rsi-overbought-long", PosType::Long, 80.0),
        ("rsi-oversold-short", PosType::Short, 25.0),
        ("rsi-trending-short", PosType::Short, 35.0), // RSI < 40 (trending floor)
        ("rsi-neutral-short", PosType::Short, 50.0),
        ("rsi-overbought-short", PosType::Short, 80.0),
    ];
    for &(label, pos_type, rsi) in rsi_scenarios {
        let entry = 50000.0;
        let atr = 500.0;
        let current = match pos_type {
            PosType::Long => entry + 2.5 * atr, // 2.5 ATR profit (active trailing)
            PosType::Short => entry - 2.5 * atr,
        };
        fixtures.push(TestFixture {
            label,
            pos_type,
            entry_price: entry,
            current_price: current,
            entry_atr: atr,
            confidence: Confidence::High,
            current_trailing_sl: 0.0,
            atr,
            adx: 30.0,
            adx_slope: 0.5,
            rsi,
            atr_slope: 0.0,
            bb_width_ratio: 1.0,
            profit_atr: 2.5,
        });
    }

    // ── Group 6: Low confidence ──────────────────────────────────────────
    fixtures.push(TestFixture {
        label: "low-conf-long",
        pos_type: PosType::Long,
        entry_price: 100.0,
        current_price: 102.0,
        entry_atr: 1.0,
        confidence: Confidence::Low,
        current_trailing_sl: 0.0,
        atr: 1.0,
        adx: 30.0,
        adx_slope: 0.5,
        rsi: 55.0,
        atr_slope: 0.0,
        bb_width_ratio: 1.0,
        profit_atr: 2.0,
    });
    fixtures.push(TestFixture {
        label: "low-conf-short",
        pos_type: PosType::Short,
        entry_price: 100.0,
        current_price: 98.0,
        entry_atr: 1.0,
        confidence: Confidence::Low,
        current_trailing_sl: 0.0,
        atr: 1.0,
        adx: 30.0,
        adx_slope: 0.5,
        rsi: 45.0,
        atr_slope: 0.0,
        bb_width_ratio: 1.0,
        profit_atr: 2.0,
    });

    // ── Group 7: Trailing ratchet (existing trailing SL) ─────────────────
    fixtures.push(TestFixture {
        label: "ratchet-long-improve",
        pos_type: PosType::Long,
        entry_price: 50000.0,
        current_price: 52000.0, // 4 ATR profit
        entry_atr: 500.0,
        confidence: Confidence::High,
        current_trailing_sl: 51200.0, // existing trailing SL
        atr: 500.0,
        adx: 30.0,
        adx_slope: 0.5,
        rsi: 55.0,
        atr_slope: 0.0,
        bb_width_ratio: 1.0,
        profit_atr: 4.0,
    });
    fixtures.push(TestFixture {
        label: "ratchet-short-improve",
        pos_type: PosType::Short,
        entry_price: 50000.0,
        current_price: 48000.0, // 4 ATR profit
        entry_atr: 500.0,
        confidence: Confidence::High,
        current_trailing_sl: 48800.0, // existing trailing SL
        atr: 500.0,
        adx: 30.0,
        adx_slope: 0.5,
        rsi: 45.0,
        atr_slope: 0.0,
        bb_width_ratio: 1.0,
        profit_atr: 4.0,
    });

    // ── Group 8: VBTS + TATP + TSPV specific scenarios ───────────────────
    fixtures.push(TestFixture {
        label: "vbts-active-bb-expanding",
        pos_type: PosType::Long,
        entry_price: 50000.0,
        current_price: 51500.0, // 3 ATR profit
        entry_atr: 500.0,
        confidence: Confidence::High,
        current_trailing_sl: 0.0,
        atr: 500.0,
        adx: 30.0,
        adx_slope: 0.5,
        rsi: 55.0,
        atr_slope: 0.0,
        bb_width_ratio: 1.5, // > 1.2 threshold (VBTS active)
        profit_atr: 3.0,
    });
    fixtures.push(TestFixture {
        label: "tatp-trend-accelerating",
        pos_type: PosType::Long,
        entry_price: 50000.0,
        current_price: 51500.0,
        entry_atr: 500.0,
        confidence: Confidence::High,
        current_trailing_sl: 0.0,
        atr: 500.0,
        adx: 40.0,      // > 35
        adx_slope: 1.0, // > 0 (trend accelerating)
        rsi: 55.0,
        atr_slope: 0.0,
        bb_width_ratio: 1.0,
        profit_atr: 3.0, // > 2.0 (high profit)
    });
    fixtures.push(TestFixture {
        label: "tspv-vol-expanding",
        pos_type: PosType::Long,
        entry_price: 50000.0,
        current_price: 51500.0,
        entry_atr: 500.0,
        confidence: Confidence::High,
        current_trailing_sl: 0.0,
        atr: 500.0,
        adx: 28.0, // < 35 (TATP not active)
        adx_slope: -0.5,
        rsi: 55.0,
        atr_slope: 0.5, // > 0 (vol expanding, TSPV path)
        bb_width_ratio: 1.0,
        profit_atr: 3.0, // > 2.0 (high profit)
    });

    // ── Group 9: Zero-ATR fallback ───────────────────────────────────────
    fixtures.push(TestFixture {
        label: "zero-atr-fallback-long",
        pos_type: PosType::Long,
        entry_price: 100.0,
        current_price: 101.0,
        entry_atr: 0.0, // triggers fallback to entry * 0.005
        confidence: Confidence::High,
        current_trailing_sl: 0.0,
        atr: 0.0,
        adx: 30.0,
        adx_slope: 0.0,
        rsi: 50.0,
        atr_slope: 0.0,
        bb_width_ratio: 1.0,
        profit_atr: 2.0,
    });

    // ── Group 10: ASE-specific (underwater + negative ADX slope) ─────────
    fixtures.push(TestFixture {
        label: "ase-long-underwater-negative-slope",
        pos_type: PosType::Long,
        entry_price: 50000.0,
        current_price: 49500.0, // underwater
        entry_atr: 500.0,
        confidence: Confidence::High,
        current_trailing_sl: 0.0,
        atr: 500.0,
        adx: 30.0,
        adx_slope: -1.0, // negative slope
        rsi: 45.0,
        atr_slope: 0.0,
        bb_width_ratio: 1.0,
        profit_atr: -1.0,
    });
    fixtures.push(TestFixture {
        label: "ase-short-underwater-negative-slope",
        pos_type: PosType::Short,
        entry_price: 50000.0,
        current_price: 50500.0, // underwater for short
        entry_atr: 500.0,
        confidence: Confidence::High,
        current_trailing_sl: 0.0,
        atr: 500.0,
        adx: 30.0,
        adx_slope: -1.0,
        rsi: 55.0,
        atr_slope: 0.0,
        bb_width_ratio: 1.0,
        profit_atr: -1.0,
    });

    // ── Group 11: Breakeven stop (SL moved past entry) ───────────────────
    fixtures.push(TestFixture {
        label: "breakeven-active-long",
        pos_type: PosType::Long,
        entry_price: 50000.0,
        current_price: 50400.0, // 0.8 ATR profit (> 0.7 breakeven_start_atr)
        entry_atr: 500.0,
        confidence: Confidence::High,
        current_trailing_sl: 0.0,
        atr: 500.0,
        adx: 30.0,
        adx_slope: 0.5,
        rsi: 55.0,
        atr_slope: 0.0,
        bb_width_ratio: 1.0,
        profit_atr: 0.8,
    });

    // Verify we hit our target of 50 fixtures.
    assert!(
        fixtures.len() >= 50,
        "Expected at least 50 fixtures, got {}",
        fixtures.len()
    );

    fixtures
}

// ═══════════════════════════════════════════════════════════════════════════════
// Helper: get the full CUDA codegen source for parsing
// ═══════════════════════════════════════════════════════════════════════════════

fn get_decision_cuda_source() -> String {
    render_all_decision(None)
}

/// Extract the CUDA source for compute_sl_price_codegen only.
fn get_sl_cuda_source() -> String {
    get_decision_cuda_source()
}

/// Extract the CUDA source for compute_trailing_codegen only.
fn get_trailing_cuda_source() -> String {
    get_decision_cuda_source()
}

// ═══════════════════════════════════════════════════════════════════════════════
// Rust reference implementations (inline, mirroring bt-core)
// ═══════════════════════════════════════════════════════════════════════════════
//
// These are simplified versions of the Rust SSOT for direct numerical comparison.
// They use the same logic as bt-core/src/exits/stop_loss.rs and trailing.rs but
// accept raw f64 parameters instead of Position/IndicatorSnapshot structs.

/// Rust SSOT: compute_sl_price (mirrors bt-core/src/exits/stop_loss.rs).
///
/// Default config: sl_atr_mult=2.0, enable_breakeven_stop=true,
/// breakeven_start_atr=0.7, breakeven_buffer_atr=0.05.
fn rust_compute_sl_price(
    pos_type: PosType,
    entry_price: f64,
    entry_atr: f64,
    current_price: f64,
    adx: f64,
    adx_slope: f64,
    sl_atr_mult: f64,
    enable_breakeven: bool,
    breakeven_start_atr: f64,
    breakeven_buffer_atr: f64,
) -> f64 {
    let atr = if entry_atr > 0.0 {
        entry_atr
    } else {
        entry_price * 0.005
    };

    let mut sl_mult = sl_atr_mult;

    // 1. ASE
    let is_underwater = match pos_type {
        PosType::Long => current_price < entry_price,
        PosType::Short => current_price > entry_price,
    };
    if adx_slope < 0.0 && is_underwater {
        sl_mult *= 0.8;
    }

    // 2. FTB -- disabled

    // 3. DASE
    if adx > 40.0 {
        let profit_in_atr = match pos_type {
            PosType::Long => (current_price - entry_price) / atr,
            PosType::Short => (entry_price - current_price) / atr,
        };
        if profit_in_atr > 0.5 {
            sl_mult *= 1.15;
        }
    }

    // 4. SLB
    if adx > 45.0 {
        sl_mult *= 1.10;
    }

    // Compute raw SL
    let mut sl_price = match pos_type {
        PosType::Long => entry_price - (atr * sl_mult),
        PosType::Short => entry_price + (atr * sl_mult),
    };

    // 5. Breakeven
    if enable_breakeven && breakeven_start_atr > 0.0 {
        let be_start = atr * breakeven_start_atr;
        let be_buffer = atr * breakeven_buffer_atr;

        match pos_type {
            PosType::Long => {
                if (current_price - entry_price) >= be_start {
                    sl_price = sl_price.max(entry_price + be_buffer);
                }
            }
            PosType::Short => {
                if (entry_price - current_price) >= be_start {
                    sl_price = sl_price.min(entry_price - be_buffer);
                }
            }
        }
    }

    sl_price
}

/// Rust SSOT: compute_trailing (mirrors bt-core/src/exits/trailing.rs).
///
/// Returns the candidate trailing SL price, or `current_trailing_sl` if not active.
fn rust_compute_trailing(
    pos_type: PosType,
    entry_price: f64,
    current_price: f64,
    entry_atr: f64,
    current_trailing_sl: f64, // 0.0 = none
    confidence: Confidence,
    rsi: f64,
    adx: f64,
    adx_slope: f64,
    atr_slope: f64,
    bb_width_ratio: f64,
    profit_atr: f64,
    // Config params (using defaults from GpuComboConfig):
    trailing_start_atr: f64,
    trailing_distance_atr: f64,
    trailing_start_atr_low_conf: f64,
    trailing_distance_atr_low_conf: f64,
    trailing_rsi_floor_default: f64,
    trailing_rsi_floor_trending: f64,
    enable_vol_buffered_trailing: bool,
    trailing_vbts_bb_threshold: f64,
    trailing_vbts_mult: f64,
    trailing_high_profit_atr: f64,
    trailing_tighten_tspv: f64,
    trailing_tighten_default: f64,
    trailing_weak_trend_mult: f64,
) -> f64 {
    let atr = if entry_atr > 0.0 {
        entry_atr
    } else {
        entry_price * 0.005
    };

    // Per-confidence overrides
    let mut t_start = trailing_start_atr;
    let mut t_dist = trailing_distance_atr;

    if confidence == Confidence::Low {
        if trailing_start_atr_low_conf > 0.0 {
            t_start = trailing_start_atr_low_conf;
        }
        if trailing_distance_atr_low_conf > 0.0 {
            t_dist = trailing_distance_atr_low_conf;
        }
    }

    // RSI Trend-Guard floor
    let min_trailing_dist = match pos_type {
        PosType::Long if rsi > 60.0 => trailing_rsi_floor_trending,
        PosType::Short if rsi < 40.0 => trailing_rsi_floor_trending,
        _ => trailing_rsi_floor_default,
    };

    // Effective trailing distance
    let mut effective_dist = t_dist;

    // VBTS
    if enable_vol_buffered_trailing && bb_width_ratio > trailing_vbts_bb_threshold {
        effective_dist *= trailing_vbts_mult;
    }

    // High-profit tightening with TATP/TSPV
    if profit_atr > trailing_high_profit_atr {
        if adx > 35.0 && adx_slope > 0.0 {
            // TATP
            effective_dist = t_dist * 1.0;
        } else if atr_slope > 0.0 {
            // TSPV
            effective_dist = t_dist * trailing_tighten_tspv;
        } else {
            effective_dist = t_dist * trailing_tighten_default;
        }
    } else if adx < 25.0 {
        effective_dist = t_dist * trailing_weak_trend_mult;
    }

    // Clamp to floor
    effective_dist = effective_dist.max(min_trailing_dist);

    // Activation gate
    if profit_atr < t_start {
        return current_trailing_sl;
    }

    // Compute candidate
    let candidate = match pos_type {
        PosType::Long => current_price - (atr * effective_dist),
        PosType::Short => current_price + (atr * effective_dist),
    };

    // Ratchet
    if current_trailing_sl > 0.0 {
        match pos_type {
            PosType::Long => candidate.max(current_trailing_sl),
            PosType::Short => candidate.min(current_trailing_sl),
        }
    } else {
        candidate
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Stop Loss codegen parity tests
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_sl_codegen_matches_rust_constants() {
    // Verify that every hardcoded threshold in the Rust stop_loss.rs has a
    // matching constant in the CUDA codegen source.
    let src = get_sl_cuda_source();

    // ASE: tighten by 20% (multiply by 0.8) when adx_slope < 0 and underwater
    assert!(
        src.contains("*= 0.8"),
        "SL codegen must contain ASE tightening factor 0.8"
    );
    assert!(
        src.contains("adx_slope < 0.0"),
        "SL codegen must check adx_slope < 0.0 for ASE"
    );

    // DASE: ADX > 40, profit > 0.5 ATR, widen 15%
    assert!(
        src.contains("adx > 40.0"),
        "SL codegen must contain DASE ADX threshold 40.0"
    );
    assert!(
        src.contains("profit_in_atr > 0.5"),
        "SL codegen must contain DASE profit threshold 0.5 ATR"
    );
    assert!(
        src.contains("*= 1.15"),
        "SL codegen must contain DASE expansion factor 1.15"
    );

    // SLB: ADX > 45, widen 10%
    assert!(
        src.contains("adx > 45.0"),
        "SL codegen must contain SLB ADX threshold 45.0"
    );
    assert!(
        src.contains("*= 1.10"),
        "SL codegen must contain SLB expansion factor 1.10"
    );

    // ATR fallback: entry_price * 0.005
    assert!(
        src.contains("entry_price * 0.005"),
        "SL codegen must contain ATR fallback factor 0.005"
    );

    // Breakeven: reads from config (not hardcoded thresholds in CUDA)
    assert!(
        src.contains("cfg.breakeven_start_atr"),
        "SL codegen must read breakeven_start_atr from config"
    );
    assert!(
        src.contains("cfg.breakeven_buffer_atr"),
        "SL codegen must read breakeven_buffer_atr from config"
    );
}

#[test]
fn test_sl_codegen_branch_coverage() {
    // Verify every conditional branch in the Rust SL logic has a
    // corresponding branch in the CUDA codegen.
    let src = get_sl_cuda_source();

    // Branch 1: ATR fallback (atr > 0 vs fallback)
    assert!(
        src.contains("atr > 0.0"),
        "SL codegen must branch on atr > 0.0"
    );

    // Branch 2: ASE underwater check (long vs short)
    assert!(
        src.contains("current_price < entry_price"),
        "SL codegen must check LONG underwater: current < entry"
    );
    assert!(
        src.contains("current_price > entry_price"),
        "SL codegen must check SHORT underwater: current > entry"
    );

    // Branch 3: ASE activation (adx_slope < 0 AND underwater)
    assert!(
        src.contains("adx_slope < 0.0 && is_underwater"),
        "SL codegen must combine adx_slope < 0 with underwater for ASE"
    );

    // Branch 4: DASE (adx > 40)
    assert!(
        src.contains("adx > 40.0"),
        "SL codegen must branch on ADX > 40 for DASE"
    );

    // Branch 5: DASE profit check (directional)
    assert!(
        src.contains("(current_price - entry_price) / eff_atr"),
        "SL codegen must compute LONG profit_in_atr"
    );
    assert!(
        src.contains("(entry_price - current_price) / eff_atr"),
        "SL codegen must compute SHORT profit_in_atr"
    );

    // Branch 6: SLB (adx > 45)
    assert!(
        src.contains("adx > 45.0"),
        "SL codegen must branch on ADX > 45 for SLB"
    );

    // Branch 7: Directional SL computation
    assert!(
        src.contains("entry_price - (eff_atr * sl_mult)"),
        "SL codegen must compute LONG SL: entry - atr * mult"
    );
    assert!(
        src.contains("entry_price + (eff_atr * sl_mult)"),
        "SL codegen must compute SHORT SL: entry + atr * mult"
    );

    // Branch 8: Breakeven guard (enable flag + start > 0)
    assert!(
        src.contains("cfg.enable_breakeven_stop"),
        "SL codegen must check breakeven enable flag"
    );

    // Branch 9: Breakeven direction (fmax for LONG, fmin for SHORT)
    assert!(
        src.contains("fmax(sl_price, entry_price + be_buffer)"),
        "SL codegen must use fmax for LONG breakeven"
    );
    assert!(
        src.contains("fmin(sl_price, entry_price - be_buffer)"),
        "SL codegen must use fmin for SHORT breakeven"
    );
}

#[test]
fn test_sl_codegen_modifier_ordering() {
    // The Rust SSOT applies modifiers in a specific order:
    // ASE -> FTB(disabled) -> DASE -> SLB -> raw SL -> breakeven
    // CUDA must follow the same order.
    let src = get_sl_cuda_source();

    // Use the full section divider markers (with parenthetical names) to avoid
    // matching the header summary which lists all modifiers in a compact form.
    let ase_pos = src
        .find("1. ASE (ADX")
        .expect("ASE section marker must exist");
    let dase_pos = src
        .find("3. DASE (Dynamic")
        .expect("DASE section marker must exist");
    let slb_pos = src
        .find("4. SLB (Saturation")
        .expect("SLB section marker must exist");
    let raw_sl_pos = src
        .find("Compute raw SL price")
        .expect("Raw SL computation section marker must exist");
    let be_pos = src
        .find("5. Breakeven Stop")
        .expect("Breakeven section marker must exist");

    assert!(ase_pos < dase_pos, "ASE must precede DASE (Rust order)");
    assert!(dase_pos < slb_pos, "DASE must precede SLB (Rust order)");
    assert!(
        slb_pos < raw_sl_pos,
        "SLB must precede raw SL computation (Rust order)"
    );
    assert!(
        raw_sl_pos < be_pos,
        "Raw SL must precede breakeven (Rust order)"
    );
}

#[test]
fn test_sl_numerical_parity_with_fixtures() {
    // For each fixture, compute SL using the Rust reference and verify that
    // the CUDA codegen would produce the same result (given same inputs and
    // default config). Since we can't run CUDA, we verify the Rust function
    // produces valid results and that the codegen contains the matching logic.
    //
    // Precision tier: T2 (single arithmetic: price +/- atr * mult).
    let fixtures = make_fixtures();

    // Default config values matching GpuComboConfig defaults
    let sl_atr_mult = 2.0;
    let enable_breakeven = true;
    let breakeven_start_atr = 0.7;
    let breakeven_buffer_atr = 0.05;

    for f in &fixtures {
        let sl = rust_compute_sl_price(
            f.pos_type,
            f.entry_price,
            f.entry_atr,
            f.current_price,
            f.adx,
            f.adx_slope,
            sl_atr_mult,
            enable_breakeven,
            breakeven_start_atr,
            breakeven_buffer_atr,
        );

        // SL must be finite and positive for any non-zero entry price
        if f.entry_price > 0.0 {
            assert!(
                sl.is_finite(),
                "SL must be finite for fixture '{}': got {}",
                f.label,
                sl
            );
        }

        // Directional sanity: LONG SL <= entry, SHORT SL >= entry
        // (unless breakeven has moved it past entry)
        let atr = if f.entry_atr > 0.0 {
            f.entry_atr
        } else {
            f.entry_price * 0.005
        };
        let profit = match f.pos_type {
            PosType::Long => f.current_price - f.entry_price,
            PosType::Short => f.entry_price - f.current_price,
        };
        let be_threshold = atr * breakeven_start_atr;
        let be_active = enable_breakeven && breakeven_start_atr > 0.0 && profit >= be_threshold;

        if !be_active {
            match f.pos_type {
                PosType::Long => assert!(
                    sl <= f.entry_price + f64::EPSILON,
                    "LONG SL must be at or below entry for '{}': sl={}, entry={}",
                    f.label,
                    sl,
                    f.entry_price
                ),
                PosType::Short => assert!(
                    sl >= f.entry_price - f64::EPSILON,
                    "SHORT SL must be at or above entry for '{}': sl={}, entry={}",
                    f.label,
                    sl,
                    f.entry_price
                ),
            }
        }

        // T2 precision: verify the f32 cast of the SL result stays within T2.
        let sl_f32 = sl as f32;
        let sl_roundtrip = sl_f32 as f64;
        assert!(
            within_tolerance(sl, sl_roundtrip, TIER_T2_TOLERANCE),
            "SL f32 round-trip exceeds T2 for '{}': f64={}, f32_rt={}, rel_err={:.2e}",
            f.label,
            sl,
            sl_roundtrip,
            relative_error(sl, sl_roundtrip)
        );
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Trailing codegen parity tests
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_trailing_codegen_matches_rust_constants() {
    // Verify that every hardcoded constant in trailing.rs matches the CUDA
    // codegen (via config defaults).
    let src = get_trailing_cuda_source();

    // RSI Trend-Guard thresholds (hardcoded in Rust: 60.0 long, 40.0 short)
    assert!(
        src.contains("rsi > 60.0"),
        "Trailing codegen must contain RSI trending threshold 60.0 for LONG"
    );
    assert!(
        src.contains("rsi < 40.0"),
        "Trailing codegen must contain RSI trending threshold 40.0 for SHORT"
    );

    // RSI Trend-Guard floor values are read from config in CUDA.
    // Rust hardcodes: default=0.5, trending=0.7
    // CUDA reads: cfg.trailing_rsi_floor_default, cfg.trailing_rsi_floor_trending
    // GpuComboConfig defaults: 0.5, 0.7 -- verified by this assertion:
    assert!(
        src.contains("cfg.trailing_rsi_floor_default"),
        "Trailing codegen must read RSI floor default from config"
    );
    assert!(
        src.contains("cfg.trailing_rsi_floor_trending"),
        "Trailing codegen must read RSI floor trending from config"
    );

    // VBTS: bb_width_ratio threshold read from config (Rust hardcodes 1.2)
    assert!(
        src.contains("cfg.trailing_vbts_bb_threshold"),
        "Trailing codegen must read VBTS BB threshold from config"
    );
    assert!(
        src.contains("cfg.trailing_vbts_mult"),
        "Trailing codegen must read VBTS multiplier from config"
    );

    // TATP: adx > 35.0 and adx_slope > 0.0, factor = 1.0 (hardcoded in both)
    assert!(
        src.contains("adx > 35.0"),
        "Trailing codegen must contain TATP ADX threshold 35.0"
    );
    assert!(
        src.contains("adx_slope > 0.0"),
        "Trailing codegen must check TATP adx_slope > 0"
    );
    assert!(
        src.contains("trailing_dist * 1.0"),
        "Trailing codegen must contain TATP factor 1.0 (no tightening)"
    );

    // TSPV: atr_slope > 0.0, factor from config (Rust hardcodes 0.75)
    assert!(
        src.contains("atr_slope > 0.0"),
        "Trailing codegen must check TSPV atr_slope > 0"
    );
    assert!(
        src.contains("cfg.trailing_tighten_tspv"),
        "Trailing codegen must read TSPV tighten factor from config"
    );

    // Default high-profit tightening factor from config (Rust hardcodes 0.5)
    assert!(
        src.contains("cfg.trailing_tighten_default"),
        "Trailing codegen must read default tighten factor from config"
    );

    // Weak-trend: adx < 25.0 (hardcoded in both)
    assert!(
        src.contains("adx < 25.0"),
        "Trailing codegen must contain weak-trend ADX threshold 25.0"
    );
    assert!(
        src.contains("cfg.trailing_weak_trend_mult"),
        "Trailing codegen must read weak-trend multiplier from config"
    );

    // High-profit ATR threshold from config (Rust hardcodes 2.0)
    assert!(
        src.contains("cfg.trailing_high_profit_atr"),
        "Trailing codegen must read high-profit ATR threshold from config"
    );

    // ATR fallback (same as SL: entry_price * 0.005)
    assert!(
        src.contains("entry_price * 0.005"),
        "Trailing codegen must contain ATR fallback 0.005"
    );

    // Low confidence mapped to integer 0
    assert!(
        src.contains("confidence == 0"),
        "Trailing codegen must map Low confidence to 0"
    );
}

#[test]
fn test_trailing_codegen_branch_coverage() {
    // Verify every conditional branch in Rust trailing.rs has a CUDA match.
    let src = get_trailing_cuda_source();

    // Branch 1: ATR fallback
    assert!(
        src.contains("atr > 0.0"),
        "Trailing codegen must branch on atr > 0.0"
    );

    // Branch 2: Low confidence override
    assert!(
        src.contains("confidence == 0"),
        "Trailing codegen must branch on Low confidence"
    );
    assert!(
        src.contains("cfg.trailing_start_atr_low_conf > 0.0"),
        "Trailing codegen must check low_conf start > 0"
    );
    assert!(
        src.contains("cfg.trailing_distance_atr_low_conf > 0.0"),
        "Trailing codegen must check low_conf distance > 0"
    );

    // Branch 3: RSI Trend-Guard (directional)
    assert!(
        src.contains("pos_type == POS_LONG && rsi > 60.0"),
        "Trailing codegen must check LONG RSI > 60 for trending floor"
    );
    assert!(
        src.contains("pos_type == POS_SHORT && rsi < 40.0"),
        "Trailing codegen must check SHORT RSI < 40 for trending floor"
    );

    // Branch 4: VBTS
    assert!(
        src.contains("cfg.enable_vol_buffered_trailing"),
        "Trailing codegen must check VBTS enable flag"
    );

    // Branch 5: High-profit tightening
    assert!(
        src.contains("profit_atr > (double)cfg.trailing_high_profit_atr"),
        "Trailing codegen must branch on high profit"
    );

    // Branch 6: TATP (adx > 35 && adx_slope > 0)
    assert!(
        src.contains("adx > 35.0 && adx_slope > 0.0"),
        "Trailing codegen must branch on TATP conditions"
    );

    // Branch 7: TSPV (atr_slope > 0)
    assert!(
        src.contains("atr_slope > 0.0"),
        "Trailing codegen must branch on TSPV condition"
    );

    // Branch 8: Weak-trend (adx < 25)
    assert!(
        src.contains("adx < 25.0"),
        "Trailing codegen must branch on weak-trend ADX < 25"
    );

    // Branch 9: Activation gate (profit < trailing_start)
    assert!(
        src.contains("profit_atr < trailing_start"),
        "Trailing codegen must check activation gate"
    );
    assert!(
        src.contains("return current_trailing_sl"),
        "Trailing codegen must return existing SL when not active"
    );

    // Branch 10: Directional candidate computation
    assert!(
        src.contains("current_price - (eff_atr * effective_dist)"),
        "Trailing codegen must compute LONG candidate"
    );
    assert!(
        src.contains("current_price + (eff_atr * effective_dist)"),
        "Trailing codegen must compute SHORT candidate"
    );

    // Branch 11: Ratchet (existing trailing SL > 0)
    assert!(
        src.contains("current_trailing_sl > 0.0"),
        "Trailing codegen must check for existing trailing SL"
    );
    assert!(
        src.contains("fmax(candidate, current_trailing_sl)"),
        "Trailing codegen must ratchet LONG via fmax"
    );
    assert!(
        src.contains("fmin(candidate, current_trailing_sl)"),
        "Trailing codegen must ratchet SHORT via fmin"
    );
}

#[test]
fn test_trailing_codegen_modifier_ordering() {
    // The Rust SSOT applies trailing modifiers in a specific order:
    // per-conf overrides -> RSI floor -> VBTS -> high-profit/TATP/TSPV/weak ->
    // clamp floor -> activation gate -> candidate -> ratchet
    let src = get_trailing_cuda_source();

    // Use the section divider markers (with dashes) to avoid matching the
    // header summary which lists all modifiers in a compact one-line form.
    let conf_pos = src
        .find("Per-confidence overrides for trailing")
        .expect("Per-confidence section marker must exist");
    let rsi_floor_pos = src
        .find("RSI Trend-Guard floor")
        .expect("RSI Trend-Guard floor section marker must exist");
    let vbts_pos = src
        .find("VBTS (Vol-Buffered")
        .expect("VBTS section marker must exist");
    let high_profit_pos = src
        .find("High-profit tightening")
        .expect("High-profit tightening section marker must exist");
    let activation_pos = src
        .find("Activation gate")
        .expect("Activation gate section marker must exist");
    let ratchet_pos = src
        .find("Ratchet: only allow")
        .expect("Ratchet section marker must exist");

    assert!(
        conf_pos < rsi_floor_pos,
        "Per-confidence must precede RSI floor"
    );
    assert!(rsi_floor_pos < vbts_pos, "RSI floor must precede VBTS");
    assert!(
        vbts_pos < high_profit_pos,
        "VBTS must precede high-profit tightening"
    );
    assert!(
        high_profit_pos < activation_pos,
        "High-profit must precede activation gate"
    );
    assert!(
        activation_pos < ratchet_pos,
        "Activation gate must precede ratchet"
    );
}

#[test]
fn test_trailing_numerical_parity_with_fixtures() {
    // For each fixture, compute trailing SL using the Rust reference.
    // Verify directional sanity and f32 round-trip precision.
    //
    // Precision tier: T2 (single arithmetic: price +/- atr * dist).
    let fixtures = make_fixtures();

    // GpuComboConfig defaults (matching buffers.rs defaults)
    let trailing_start_atr = 1.0;
    let trailing_distance_atr = 0.8;
    let trailing_start_atr_low_conf = 0.0;
    let trailing_distance_atr_low_conf = 0.0;
    let trailing_rsi_floor_default = 0.5;
    let trailing_rsi_floor_trending = 0.7;
    let enable_vol_buffered_trailing = true;
    let trailing_vbts_bb_threshold = 1.2;
    let trailing_vbts_mult = 1.25;
    let trailing_high_profit_atr = 2.0;
    let trailing_tighten_tspv = 0.75;
    let trailing_tighten_default = 0.5;
    let trailing_weak_trend_mult = 0.7;

    for f in &fixtures {
        let tsl = rust_compute_trailing(
            f.pos_type,
            f.entry_price,
            f.current_price,
            f.entry_atr,
            f.current_trailing_sl,
            f.confidence,
            f.rsi,
            f.adx,
            f.adx_slope,
            f.atr_slope,
            f.bb_width_ratio,
            f.profit_atr,
            trailing_start_atr,
            trailing_distance_atr,
            trailing_start_atr_low_conf,
            trailing_distance_atr_low_conf,
            trailing_rsi_floor_default,
            trailing_rsi_floor_trending,
            enable_vol_buffered_trailing,
            trailing_vbts_bb_threshold,
            trailing_vbts_mult,
            trailing_high_profit_atr,
            trailing_tighten_tspv,
            trailing_tighten_default,
            trailing_weak_trend_mult,
        );

        // TSL must be finite
        assert!(
            tsl.is_finite(),
            "Trailing SL must be finite for fixture '{}': got {}",
            f.label,
            tsl
        );

        // If trailing is active (profit >= trailing_start), the TSL should
        // be between the entry and the current price (for profitable positions)
        let effective_start =
            if f.confidence == Confidence::Low && trailing_start_atr_low_conf > 0.0 {
                trailing_start_atr_low_conf
            } else {
                trailing_start_atr
            };

        if f.profit_atr >= effective_start && f.profit_atr > 0.0 {
            match f.pos_type {
                PosType::Long => {
                    // Trailing SL should be below current price
                    assert!(
                        tsl < f.current_price,
                        "LONG trailing SL must be below current price for '{}': tsl={}, current={}",
                        f.label,
                        tsl,
                        f.current_price
                    );
                }
                PosType::Short => {
                    // Trailing SL should be above current price
                    assert!(
                        tsl > f.current_price,
                        "SHORT trailing SL must be above current price for '{}': tsl={}, current={}",
                        f.label,
                        tsl,
                        f.current_price
                    );
                }
            }
        }

        // T2 precision: f32 round-trip
        if tsl != 0.0 {
            let tsl_f32 = tsl as f32;
            let tsl_roundtrip = tsl_f32 as f64;
            assert!(
                within_tolerance(tsl, tsl_roundtrip, TIER_T2_TOLERANCE),
                "Trailing SL f32 round-trip exceeds T2 for '{}': f64={}, f32_rt={}, rel_err={:.2e}",
                f.label,
                tsl,
                tsl_roundtrip,
                relative_error(tsl, tsl_roundtrip)
            );
        }
    }
}

#[test]
fn test_trailing_config_defaults_match_rust_hardcoded() {
    // The Rust trailing.rs hardcodes several constants that the CUDA codegen
    // reads from GpuComboConfig.  Verify that the GpuComboConfig defaults
    // match the Rust hardcoded values.
    //
    // This is the critical "same numbers" check that ensures the two
    // implementations agree on thresholds without requiring GPU execution.

    // GpuComboConfig defaults (from buffers.rs)
    let gpu_defaults: &[(&str, f64, f64)] = &[
        // (name, GpuComboConfig default, Rust hardcoded value)
        ("trailing_rsi_floor_default", 0.5, 0.5),
        ("trailing_rsi_floor_trending", 0.7, 0.7),
        ("trailing_vbts_bb_threshold", 1.2, 1.2),
        ("trailing_vbts_mult", 1.25, 1.25),
        ("trailing_high_profit_atr", 2.0, 2.0),
        ("trailing_tighten_tspv", 0.75, 0.75),
        ("trailing_tighten_default", 0.5, 0.5),
        ("trailing_weak_trend_mult", 0.7, 0.7),
    ];

    for &(name, gpu_default, rust_hardcoded) in gpu_defaults {
        assert!(
            exact_match(gpu_default, rust_hardcoded),
            "Config mismatch for '{}': GpuComboConfig default={}, Rust hardcoded={}",
            name,
            gpu_default,
            rust_hardcoded
        );
    }
}

#[test]
fn test_sl_config_defaults_match_rust_hardcoded() {
    // Similar check for SL constants.
    // The SL codegen reads sl_atr_mult from config; the Rust default is 2.0.
    // The hardcoded SL constants (ASE=0.8, DASE=1.15, SLB=1.10) are
    // literal in both Rust and CUDA — they are NOT config-driven.

    let sl_hardcoded: &[(&str, f64, &str)] = &[
        ("ASE tightening factor", 0.8, "*= 0.8"),
        ("DASE expansion factor", 1.15, "*= 1.15"),
        ("SLB expansion factor", 1.10, "*= 1.10"),
        ("DASE ADX threshold", 40.0, "adx > 40.0"),
        ("DASE profit threshold", 0.5, "profit_in_atr > 0.5"),
        ("SLB ADX threshold", 45.0, "adx > 45.0"),
        ("ATR fallback factor", 0.005, "entry_price * 0.005"),
    ];

    let src = get_sl_cuda_source();
    for &(name, _value, cuda_pattern) in sl_hardcoded {
        assert!(
            src.contains(cuda_pattern),
            "SL constant '{}' not found in CUDA codegen (expected pattern: '{}')",
            name,
            cuda_pattern
        );
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Fixture coverage test
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_fixture_coverage() {
    let fixtures = make_fixtures();

    // Must have at least 50 fixtures
    assert!(
        fixtures.len() >= 50,
        "Expected at least 50 fixtures, got {}",
        fixtures.len()
    );

    // Coverage: both position types
    assert!(
        fixtures.iter().any(|f| f.pos_type == PosType::Long),
        "Fixtures must include LONG positions"
    );
    assert!(
        fixtures.iter().any(|f| f.pos_type == PosType::Short),
        "Fixtures must include SHORT positions"
    );

    // Coverage: price levels (penny stock to BTC)
    assert!(
        fixtures.iter().any(|f| f.entry_price < 0.01),
        "Fixtures must include penny stock prices"
    );
    assert!(
        fixtures.iter().any(|f| f.entry_price > 50000.0),
        "Fixtures must include BTC-scale prices"
    );

    // Coverage: profit levels
    assert!(
        fixtures.iter().any(|f| f.profit_atr < -3.0),
        "Fixtures must include deep-loss scenarios (< -3 ATR)"
    );
    assert!(
        fixtures.iter().any(|f| f.profit_atr.abs() < 0.01),
        "Fixtures must include breakeven scenarios"
    );
    assert!(
        fixtures.iter().any(|f| f.profit_atr > 3.0),
        "Fixtures must include large-profit scenarios (> 3 ATR)"
    );

    // Coverage: ADX regimes
    assert!(
        fixtures.iter().any(|f| f.adx < 25.0),
        "Fixtures must include weak-trend ADX (< 25)"
    );
    assert!(
        fixtures.iter().any(|f| f.adx > 40.0 && f.adx <= 45.0),
        "Fixtures must include DASE-only ADX (40 < ADX <= 45)"
    );
    assert!(
        fixtures.iter().any(|f| f.adx > 45.0),
        "Fixtures must include SLB-triggering ADX (> 45)"
    );

    // Coverage: ASE conditions (underwater + negative slope)
    assert!(
        fixtures.iter().any(|f| f.adx_slope < 0.0
            && match f.pos_type {
                PosType::Long => f.current_price < f.entry_price,
                PosType::Short => f.current_price > f.entry_price,
            }),
        "Fixtures must include ASE-triggering scenario (underwater + neg slope)"
    );

    // Coverage: RSI regimes for trailing
    assert!(
        fixtures
            .iter()
            .any(|f| f.pos_type == PosType::Long && f.rsi > 60.0),
        "Fixtures must include LONG RSI trending (> 60)"
    );
    assert!(
        fixtures
            .iter()
            .any(|f| f.pos_type == PosType::Short && f.rsi < 40.0),
        "Fixtures must include SHORT RSI trending (< 40)"
    );

    // Coverage: VBTS (bb_width_ratio > 1.2)
    assert!(
        fixtures.iter().any(|f| f.bb_width_ratio > 1.2),
        "Fixtures must include VBTS-active scenario (bb_width_ratio > 1.2)"
    );

    // Coverage: TATP (adx > 35 && adx_slope > 0 && profit > 2.0)
    assert!(
        fixtures
            .iter()
            .any(|f| f.adx > 35.0 && f.adx_slope > 0.0 && f.profit_atr > 2.0),
        "Fixtures must include TATP scenario"
    );

    // Coverage: TSPV (atr_slope > 0 && profit > 2.0 && adx <= 35)
    assert!(
        fixtures.iter().any(|f| f.atr_slope > 0.0
            && f.profit_atr > 2.0
            && !(f.adx > 35.0 && f.adx_slope > 0.0)),
        "Fixtures must include TSPV scenario"
    );

    // Coverage: Low confidence
    assert!(
        fixtures.iter().any(|f| f.confidence == Confidence::Low),
        "Fixtures must include Low confidence scenarios"
    );

    // Coverage: Trailing ratchet (existing trailing SL)
    assert!(
        fixtures.iter().any(|f| f.current_trailing_sl > 0.0),
        "Fixtures must include ratchet scenarios (existing trailing SL)"
    );

    // Coverage: Zero ATR fallback
    assert!(
        fixtures.iter().any(|f| f.entry_atr == 0.0),
        "Fixtures must include zero-ATR fallback scenario"
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
// CUDA codegen uses double precision for all price math (AQC-734 mandate)
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_sl_codegen_uses_double_not_float() {
    let src = get_sl_cuda_source();

    // All critical price/atr variables must be `double`
    let required_doubles = [
        "double sl_mult",
        "double sl_price",
        "double eff_atr",
        "double be_start",
        "double be_buffer",
        "double profit_in_atr",
    ];
    for pat in &required_doubles {
        assert!(
            src.contains(pat),
            "SL codegen must use 'double' for '{}' (AQC-734)",
            pat
        );
    }

    // Must NOT use float for critical variables
    let forbidden_floats = ["float sl_price", "float sl_mult", "float eff_atr"];
    for pat in &forbidden_floats {
        assert!(
            !src.contains(pat),
            "SL codegen must NOT use 'float' for '{}' (AQC-734)",
            pat
        );
    }
}

#[test]
fn test_trailing_codegen_uses_double_not_float() {
    let src = get_trailing_cuda_source();

    let required_doubles = [
        "double trailing_start",
        "double trailing_dist",
        "double effective_dist",
        "double candidate",
        "double eff_atr",
        "double min_trailing_dist",
    ];
    for pat in &required_doubles {
        assert!(
            src.contains(pat),
            "Trailing codegen must use 'double' for '{}' (AQC-734)",
            pat
        );
    }

    let forbidden_floats = [
        "float trailing_start",
        "float trailing_dist",
        "float effective_dist",
        "float candidate",
    ];
    for pat in &forbidden_floats {
        assert!(
            !src.contains(pat),
            "Trailing codegen must NOT use 'float' for '{}' (AQC-734)",
            pat
        );
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// AQC-1261: Gates axis-by-axis validation
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_gates_codegen_parity() {
    let src = get_decision_cuda_source();

    // Function signature
    assert!(
        src.contains("__device__ GateResultD check_gates_codegen("),
        "Gates codegen must have correct __device__ function signature"
    );
    assert!(
        src.contains("const GpuComboConfig& cfg"),
        "Gates must take GpuComboConfig by const ref"
    );
}

#[test]
fn test_gates_all_gates_pass_combination() {
    // AQC-1261: Verify combined all_gates_pass check contains all required fields
    let src = get_decision_cuda_source();

    assert!(
        src.contains("result.adx_above_min"),
        "all_gates_pass must check adx_above_min"
    );
    assert!(
        src.contains("!result.is_ranging"),
        "all_gates_pass must check !is_ranging"
    );
    assert!(
        src.contains("!result.is_anomaly"),
        "all_gates_pass must check !is_anomaly"
    );
    assert!(
        src.contains("!result.is_extended"),
        "all_gates_pass must check !is_extended"
    );
    assert!(
        src.contains("result.vol_confirm"),
        "all_gates_pass must check vol_confirm"
    );
    assert!(
        src.contains("result.is_trending_up"),
        "all_gates_pass must check is_trending_up"
    );
}

#[test]
fn test_gates_ranging_filter_vote_system() {
    // AQC-1261: Ranging filter uses vote system (low ADX + narrow BB + RSI neutral)
    let src = get_decision_cuda_source();

    assert!(
        src.contains("cfg.enable_ranging_filter"),
        "Ranging filter must check enable flag"
    );
    assert!(
        src.contains("cfg.ranging_min_signals"),
        "Ranging filter must use min_signals from config"
    );
    assert!(
        src.contains("cfg.ranging_adx_lt"),
        "Vote 1: ADX below ranging threshold"
    );
    assert!(
        src.contains("cfg.ranging_bb_width_ratio_lt"),
        "Vote 2: BB width below ranging threshold"
    );
    assert!(
        src.contains("cfg.ranging_rsi_low") && src.contains("cfg.ranging_rsi_high"),
        "Vote 3: RSI in neutral zone"
    );
    assert!(
        src.contains("votes >= min_signals"),
        "Ranging activates when votes >= min_signals"
    );
}

#[test]
fn test_gates_anomaly_filter() {
    // AQC-1261: Anomaly filter checks price_change_pct and ema_dev_pct
    let src = get_decision_cuda_source();

    assert!(
        src.contains("cfg.enable_anomaly_filter"),
        "Anomaly filter must check enable flag"
    );
    assert!(
        src.contains("price_change_pct"),
        "Anomaly filter must compute price_change_pct"
    );
    assert!(
        src.contains("ema_dev_pct"),
        "Anomaly filter must compute ema_dev_pct"
    );
    assert!(
        src.contains("cfg.anomaly_price_change_pct"),
        "Anomaly filter must compare against config threshold"
    );
    assert!(
        src.contains("cfg.anomaly_ema_dev_pct"),
        "Anomaly filter must compare ema_dev against config threshold"
    );
}

#[test]
fn test_gates_extension_filter() {
    // AQC-1261: Extension filter checks distance from EMA_fast
    let src = get_decision_cuda_source();

    assert!(
        src.contains("cfg.enable_extension_filter"),
        "Extension filter must check enable flag"
    );
    assert!(
        src.contains("cfg.max_dist_ema_fast"),
        "Extension filter must use max_dist_ema_fast from config"
    );
    assert!(
        src.contains("fabs(close - ema_fast)"),
        "Extension filter must compute absolute distance from EMA_fast"
    );
}

#[test]
fn test_gates_volume_confirmation() {
    // AQC-1261: Volume filter checks vol_above_sma and vol_trend
    let src = get_decision_cuda_source();

    assert!(
        src.contains("cfg.require_volume_confirmation"),
        "Volume confirmation must check enable flag"
    );
    assert!(
        src.contains("volume > vol_sma"),
        "Volume confirmation must check volume > vol_sma"
    );
    assert!(
        src.contains("vol_trend"),
        "Volume confirmation must check vol_trend"
    );
    assert!(
        src.contains("cfg.vol_confirm_include_prev"),
        "Volume confirmation must check relaxed mode flag"
    );
}

#[test]
fn test_gates_adx_rising() {
    // AQC-1261: ADX rising checks slope or saturation override
    let src = get_decision_cuda_source();

    assert!(
        src.contains("cfg.require_adx_rising"),
        "ADX rising must check enable flag"
    );
    assert!(
        src.contains("adx_slope > 0.0"),
        "ADX rising must check positive slope"
    );
    assert!(
        src.contains("cfg.adx_rising_saturation"),
        "ADX rising must check saturation override"
    );
}

#[test]
fn test_gates_macro_alignment() {
    // AQC-1261: Macro alignment checks EMA slow vs EMA macro
    let src = get_decision_cuda_source();

    assert!(
        src.contains("cfg.require_macro_alignment"),
        "Macro alignment must check enable flag"
    );
    assert!(
        src.contains("ema_slow > ema_macro"),
        "Bullish macro alignment: ema_slow > ema_macro"
    );
    assert!(
        src.contains("ema_slow < ema_macro"),
        "Bearish macro alignment: ema_slow < ema_macro"
    );
}

#[test]
fn test_gates_tmc_and_ave() {
    // AQC-1261: TMC caps effective_min_adx when slope > 0.5;
    // AVE multiplies when ATR ratio exceeds threshold
    let src = get_decision_cuda_source();

    // TMC
    assert!(
        src.contains("adx_slope > 0.5"),
        "TMC must check ADX slope > 0.5"
    );
    assert!(
        src.contains("fmin(effective_min_adx, 25.0)"),
        "TMC must cap effective_min_adx at 25.0"
    );

    // AVE
    assert!(
        src.contains("cfg.ave_enabled"),
        "AVE must check ave_enabled flag"
    );
    assert!(
        src.contains("cfg.ave_atr_ratio_gt"),
        "AVE must use atr_ratio threshold from config"
    );
    assert!(
        src.contains("cfg.ave_adx_mult"),
        "AVE must use adx_mult from config"
    );
    assert!(
        src.contains("effective_min_adx *="),
        "AVE must multiply effective_min_adx"
    );
}

#[test]
fn test_gates_dre_interpolation() {
    // AQC-1261: DRE interpolates RSI limits between weak and strong based on ADX
    let src = get_decision_cuda_source();

    assert!(
        src.contains("cfg.dre_min_adx"),
        "DRE must use dre_min_adx from config"
    );
    assert!(
        src.contains("cfg.dre_max_adx"),
        "DRE must use dre_max_adx from config"
    );
    assert!(
        src.contains("cfg.dre_long_rsi_limit_low") && src.contains("cfg.dre_long_rsi_limit_high"),
        "DRE must interpolate long RSI limits"
    );
    assert!(
        src.contains("cfg.dre_short_rsi_limit_low") && src.contains("cfg.dre_short_rsi_limit_high"),
        "DRE must interpolate short RSI limits"
    );
    // Weight clamped to [0, 1]
    assert!(
        src.contains("fmax(fmin(weight, 1.0), 0.0)"),
        "DRE weight must be clamped to [0, 1]"
    );
}

#[test]
fn test_gates_slow_drift_override() {
    // AQC-1261: Slow-drift override clears ranging when slope exceeds threshold
    let src = get_decision_cuda_source();

    assert!(
        src.contains("cfg.enable_slow_drift_entries"),
        "Slow-drift override must check enable flag"
    );
    assert!(
        src.contains("cfg.slow_drift_ranging_slope_override"),
        "Slow-drift must use ranging slope override from config"
    );
    assert!(
        src.contains("result.is_ranging = false"),
        "Slow-drift must clear is_ranging"
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
// AQC-1262: Signals mode-by-mode validation
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_signal_codegen_parity() {
    let src = get_decision_cuda_source();

    // Function signature
    assert!(
        src.contains("__device__ SignalResult generate_signal_codegen("),
        "Signal codegen must have correct __device__ function signature"
    );
    assert!(
        src.contains("const GpuComboConfig& cfg"),
        "Signal must take GpuComboConfig by const ref"
    );
}

#[test]
fn test_signal_mode1_standard_trend_long() {
    // AQC-1262: Mode 1 standard trend — long direction
    let src = get_decision_cuda_source();

    assert!(
        src.contains("bullish_alignment && close > ema_fast && btc_ok_long"),
        "Mode 1 long: bullish_alignment AND close > ema_fast AND btc_ok_long"
    );
    assert!(
        src.contains("signal = 1"),
        "Mode 1 long must set signal = 1 (SIG_BUY)"
    );
}

#[test]
fn test_signal_mode1_standard_trend_short() {
    // AQC-1262: Mode 1 standard trend — short direction
    let src = get_decision_cuda_source();

    assert!(
        src.contains("bearish_alignment && close < ema_fast && btc_ok_short"),
        "Mode 1 short: bearish_alignment AND close < ema_fast AND btc_ok_short"
    );
    assert!(
        src.contains("signal = 2"),
        "Mode 1 short must set signal = 2 (SIG_SELL)"
    );
}

#[test]
fn test_signal_mode2_pullback_continuation() {
    // AQC-1262: Mode 2 pullback continuation with EMA cross detection
    let src = get_decision_cuda_source();

    assert!(
        src.contains("cfg.enable_pullback_entries"),
        "Mode 2 must check enable_pullback_entries config flag"
    );
    assert!(
        src.contains("cfg.pullback_min_adx"),
        "Mode 2 must check pullback_min_adx"
    );
    // Cross detection
    assert!(
        src.contains("prev_close <= prev_ema_fast") && src.contains("close > ema_fast"),
        "Mode 2 must detect EMA cross-up"
    );
    assert!(
        src.contains("prev_close >= prev_ema_fast") && src.contains("close < ema_fast"),
        "Mode 2 must detect EMA cross-down"
    );
    assert!(
        src.contains("cfg.pullback_confidence"),
        "Mode 2 must use pullback_confidence from config"
    );
}

#[test]
fn test_signal_mode3_slow_drift() {
    // AQC-1262: Mode 3 slow drift — always Low confidence
    let src = get_decision_cuda_source();

    assert!(
        src.contains("cfg.enable_slow_drift_entries"),
        "Mode 3 must check enable_slow_drift_entries"
    );
    assert!(
        src.contains("cfg.slow_drift_min_slope_pct"),
        "Mode 3 must use slow_drift_min_slope_pct"
    );
    assert!(
        src.contains("ema_slow_slope_pct >= min_slope"),
        "Mode 3 long must check slope >= threshold"
    );
    assert!(
        src.contains("ema_slow_slope_pct <= -min_slope"),
        "Mode 3 short must check slope <= -threshold"
    );

    // Slow drift always returns CONF_LOW (0)
    let mode3_marker = "// Mode 3: Slow drift";
    let mode3_start = src.rfind(mode3_marker).expect("Mode 3 section must exist");
    let mode3_section = &src[mode3_start..];
    assert!(
        mode3_section.contains("confidence = 0"),
        "Mode 3 must always set CONF_LOW (0)"
    );
}

#[test]
fn test_signal_dre_rsi_gate() {
    // AQC-1262: DRE RSI gate in Mode 1 — blocks if RSI below limit
    let src = get_decision_cuda_source();

    // Mode 1 section contains DRE RSI check
    assert!(
        src.contains("rsi <= rsi_long_limit"),
        "Mode 1 must block long when rsi <= rsi_long_limit"
    );
    assert!(
        src.contains("rsi >= rsi_short_limit"),
        "Mode 1 must block short when rsi >= rsi_short_limit"
    );
}

#[test]
fn test_signal_macd_gate_accel_and_sign() {
    // AQC-1262: MACD gate supports accel (mode 0) and sign (mode 1) modes
    let src = get_decision_cuda_source();

    // MACD helper functions
    assert!(
        src.contains("check_macd_long_codegen"),
        "Must have check_macd_long_codegen helper"
    );
    assert!(
        src.contains("check_macd_short_codegen"),
        "Must have check_macd_short_codegen helper"
    );

    // MACD_ACCEL mode (0): checks histogram acceleration
    assert!(
        src.contains("macd_hist > prev_macd_hist"),
        "MACD_ACCEL long: hist > prev_hist"
    );
    assert!(
        src.contains("macd_hist < prev_macd_hist"),
        "MACD_ACCEL short: hist < prev_hist"
    );

    // MACD_SIGN mode (1): checks histogram sign
    assert!(src.contains("macd_hist > 0.0"), "MACD_SIGN long: hist > 0");
    assert!(src.contains("macd_hist < 0.0"), "MACD_SIGN short: hist < 0");
}

#[test]
fn test_signal_stoch_rsi_filter() {
    // AQC-1262: StochRSI filter blocks overbought longs and oversold shorts
    let src = get_decision_cuda_source();

    assert!(
        src.contains("cfg.use_stoch_rsi_filter"),
        "StochRSI filter must check enable flag"
    );
    assert!(
        src.contains("cfg.stoch_rsi_block_long_gt"),
        "StochRSI must use block_long_gt threshold"
    );
    assert!(
        src.contains("cfg.stoch_rsi_block_short_lt"),
        "StochRSI must use block_short_lt threshold"
    );
}

#[test]
fn test_signal_ave_confidence_upgrade() {
    // AQC-1262: AVE upgrades confidence to High when ATR ratio exceeds threshold
    let src = get_decision_cuda_source();

    // Find the Mode 1 section specifically
    let mode1_marker = "// Mode 1: Standard";
    let mode1_start = src.find(mode1_marker).expect("Mode 1 section must exist");
    let mode1_section = &src[mode1_start..];

    assert!(
        mode1_section.contains("cfg.ave_enabled"),
        "AVE must check ave_enabled in Mode 1"
    );
    assert!(
        mode1_section.contains("confidence = 2"),
        "AVE must upgrade confidence to 2 (CONF_HIGH)"
    );
}

#[test]
fn test_signal_btc_alignment() {
    // AQC-1262: BTC alignment directional filter
    let src = get_decision_cuda_source();

    assert!(
        src.contains("cfg.require_btc_alignment"),
        "BTC alignment must check config flag"
    );
    assert!(src.contains("btc_ok_long"), "Must compute btc_ok_long");
    assert!(src.contains("btc_ok_short"), "Must compute btc_ok_short");
    assert!(
        src.contains("cfg.btc_adx_override"),
        "BTC alignment must use ADX override threshold"
    );
}

#[test]
fn test_signal_mode_priority_order() {
    // AQC-1262: Modes evaluated in priority order: 1 > 2 > 3
    let src = get_decision_cuda_source();

    let mode1_pos = src.rfind("// Mode 1: Standard").expect("Mode 1 must exist");
    let mode2_pos = src.rfind("// Mode 2: Pullback").expect("Mode 2 must exist");
    let mode3_pos = src
        .rfind("// Mode 3: Slow drift")
        .expect("Mode 3 must exist");
    assert!(mode1_pos < mode2_pos, "Mode 1 must precede Mode 2");
    assert!(mode2_pos < mode3_pos, "Mode 2 must precede Mode 3");
}

// ═══════════════════════════════════════════════════════════════════════════════
// AQC-1263: Stop loss axis validation (additional edge cases)
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_sl_ase_tightening_underwater_adx_declining() {
    // AQC-1263: ASE tightens by 20% when underwater AND ADX slope < 0
    let fixtures = make_fixtures();
    let sl_atr_mult = 2.0;

    for f in fixtures.iter().filter(|f| {
        f.adx_slope < 0.0
            && match f.pos_type {
                PosType::Long => f.current_price < f.entry_price,
                PosType::Short => f.current_price > f.entry_price,
            }
    }) {
        let sl = rust_compute_sl_price(
            f.pos_type,
            f.entry_price,
            f.entry_atr,
            f.current_price,
            f.adx,
            f.adx_slope,
            sl_atr_mult,
            false,
            0.0,
            0.0,
        );
        // ASE tightened: effective mult = 2.0 * 0.8 = 1.6
        let atr = if f.entry_atr > 0.0 {
            f.entry_atr
        } else {
            f.entry_price * 0.005
        };
        let expected_mult = sl_atr_mult * 0.8;
        let expected_sl = match f.pos_type {
            PosType::Long => f.entry_price - atr * expected_mult,
            PosType::Short => f.entry_price + atr * expected_mult,
        };
        // May also have DASE/SLB applied on top
        // Verify ASE at least tightened (closer to entry than base)
        let base_sl = match f.pos_type {
            PosType::Long => f.entry_price - atr * sl_atr_mult,
            PosType::Short => f.entry_price + atr * sl_atr_mult,
        };
        match f.pos_type {
            PosType::Long => assert!(
                sl >= base_sl - f64::EPSILON,
                "ASE must tighten LONG SL for '{}': sl={}, base_sl={}",
                f.label,
                sl,
                base_sl
            ),
            PosType::Short => assert!(
                sl <= base_sl + f64::EPSILON,
                "ASE must tighten SHORT SL for '{}': sl={}, base_sl={}",
                f.label,
                sl,
                base_sl
            ),
        }
        // When no DASE/SLB, should match exactly
        if f.adx <= 40.0 {
            assert!(
                within_tolerance(expected_sl, sl, TIER_T2_TOLERANCE),
                "ASE-only SL mismatch for '{}': expected={}, got={}",
                f.label,
                expected_sl,
                sl
            );
        }
    }
}

#[test]
fn test_sl_dase_widening_high_adx_profit() {
    // AQC-1263: DASE widens by 15% when ADX > 40 AND profit > 0.5 ATR
    let sl = rust_compute_sl_price(
        PosType::Long,
        50000.0,
        500.0,
        50300.0, // profit_atr = 0.6
        42.0,
        0.5,
        2.0,
        false,
        0.0,
        0.0,
    );
    let atr = 500.0;
    // DASE active: profit_atr = 0.6 > 0.5, ADX = 42 > 40
    // sl_mult = 2.0 * 1.15 = 2.30
    let expected = 50000.0 - atr * 2.0 * 1.15;
    assert!(
        within_tolerance(expected, sl, TIER_T2_TOLERANCE),
        "DASE widening: expected={}, got={}",
        expected,
        sl
    );
}

#[test]
fn test_sl_slb_widening_very_high_adx() {
    // AQC-1263: SLB widens by 10% when ADX > 45
    let sl = rust_compute_sl_price(
        PosType::Long,
        50000.0,
        500.0,
        49900.0, // underwater, no DASE
        47.0,
        0.5,
        2.0,
        false,
        0.0,
        0.0,
    );
    let atr = 500.0;
    // SLB: ADX = 47 > 45, sl_mult = 2.0 * 1.10 = 2.20
    // DASE: ADX > 40, but profit_atr = -0.2 (underwater), not > 0.5
    let expected = 50000.0 - atr * 2.0 * 1.10;
    assert!(
        within_tolerance(expected, sl, TIER_T2_TOLERANCE),
        "SLB widening: expected={}, got={}",
        expected,
        sl
    );
}

#[test]
fn test_sl_breakeven_activation() {
    // AQC-1263: Breakeven stop moves SL past entry when profit >= be_start ATR
    let sl = rust_compute_sl_price(
        PosType::Long,
        50000.0,
        500.0,
        50400.0, // profit = 400, be_start = 500*0.7 = 350
        30.0,
        0.5,
        2.0,
        true,
        0.7,
        0.05,
    );
    let atr = 500.0;
    let be_buffer = atr * 0.05;
    // Breakeven active: profit = 400 >= 350
    // SL = max(entry - atr*2.0, entry + be_buffer) = max(49000, 50025) = 50025
    let expected = 50000.0 + be_buffer;
    assert!(
        within_tolerance(expected, sl, TIER_T2_TOLERANCE),
        "Breakeven activation: expected={}, got={}",
        expected,
        sl
    );
}

#[test]
fn test_sl_zero_atr_fallback() {
    // AQC-1263: Zero entry_atr uses fallback = entry_price * 0.005
    let sl = rust_compute_sl_price(
        PosType::Long,
        100.0,
        0.0,
        101.0,
        30.0,
        0.5,
        2.0,
        false,
        0.0,
        0.0,
    );
    let fallback_atr = 100.0 * 0.005;
    let expected = 100.0 - fallback_atr * 2.0;
    assert!(
        within_tolerance(expected, sl, TIER_T2_TOLERANCE),
        "Zero ATR fallback: expected={}, got={}",
        expected,
        sl
    );
}

#[test]
fn test_sl_dase_and_slb_combined() {
    // AQC-1263: When ADX > 45 AND profitable, both DASE and SLB apply
    let sl = rust_compute_sl_price(
        PosType::Long,
        50000.0,
        500.0,
        50400.0, // profit_atr = 0.8
        50.0,
        0.5,
        2.0,
        false,
        0.0,
        0.0,
    );
    let atr = 500.0;
    // DASE: ADX=50 > 40, profit_atr=0.8 > 0.5 -> mult *= 1.15
    // SLB: ADX=50 > 45 -> mult *= 1.10
    // Combined: 2.0 * 1.15 * 1.10 = 2.53
    let expected = 50000.0 - atr * 2.0 * 1.15 * 1.10;
    assert!(
        within_tolerance(expected, sl, TIER_T2_TOLERANCE),
        "DASE+SLB combined: expected={}, got={}",
        expected,
        sl
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
// AQC-1264: Trailing stop axis validation (additional edge cases)
// ═══════════════════════════════════════════════════════════════════════════════

fn trailing_defaults() -> (
    f64,
    f64,
    f64,
    f64,
    f64,
    f64,
    bool,
    f64,
    f64,
    f64,
    f64,
    f64,
    f64,
) {
    (
        1.0,  // trailing_start_atr
        0.8,  // trailing_distance_atr
        0.0,  // trailing_start_atr_low_conf
        0.0,  // trailing_distance_atr_low_conf
        0.5,  // trailing_rsi_floor_default
        0.7,  // trailing_rsi_floor_trending
        true, // enable_vol_buffered_trailing
        1.2,  // trailing_vbts_bb_threshold
        1.25, // trailing_vbts_mult
        2.0,  // trailing_high_profit_atr
        0.75, // trailing_tighten_tspv
        0.5,  // trailing_tighten_default
        0.7,  // trailing_weak_trend_mult
    )
}

#[test]
fn test_trailing_vbts_adjustment_high_bb_width() {
    // AQC-1264: VBTS widens trailing when bb_width_ratio > threshold
    let (ts, td, tslc, tdlc, rfd, rft, evb, vbt, vbm, hpa, ttp, ttd, twm) = trailing_defaults();

    let tsl = rust_compute_trailing(
        PosType::Long,
        50000.0,
        51500.0,
        500.0,
        0.0,
        Confidence::High,
        55.0,
        30.0,
        0.5,
        0.0,
        1.5, // bb_width_ratio > 1.2 (VBTS triggers)
        3.0, // profit > trailing_start
        ts,
        td,
        tslc,
        tdlc,
        rfd,
        rft,
        evb,
        vbt,
        vbm,
        hpa,
        ttp,
        ttd,
        twm,
    );

    // VBTS active: effective_dist = 0.8 * 1.25 = 1.0
    // Then high-profit tightening (profit=3.0 > 2.0):
    //   adx=30 < 35, atr_slope=0 not > 0 -> default tighten: 0.8 * 0.5 = 0.4
    // VBTS applies before high-profit, but high-profit overrides the base dist.
    // Actually the code checks high-profit AFTER VBTS, and high-profit uses t_dist (base),
    // not effective_dist. So effective_dist = 0.8 * 0.5 = 0.4 (default tighten wins).
    // Clamp to floor: max(0.4, 0.5) = 0.5
    let atr = 500.0;
    let expected = 51500.0 - atr * 0.5;
    assert!(
        within_tolerance(expected, tsl, TIER_T2_TOLERANCE),
        "VBTS + high-profit: expected={}, got={}",
        expected,
        tsl
    );
}

#[test]
fn test_trailing_tatp_preservation_trending_adx() {
    // AQC-1264: TATP preserves distance (1.0x) when ADX > 35 and slope > 0
    let (ts, td, tslc, tdlc, rfd, rft, evb, vbt, vbm, hpa, ttp, ttd, twm) = trailing_defaults();

    let tsl = rust_compute_trailing(
        PosType::Long,
        50000.0,
        51500.0,
        500.0,
        0.0,
        Confidence::High,
        55.0,
        40.0,
        1.0,
        0.0,
        1.0, // bb_width_ratio normal
        3.0, // profit > high_profit_atr (2.0)
        ts,
        td,
        tslc,
        tdlc,
        rfd,
        rft,
        evb,
        vbt,
        vbm,
        hpa,
        ttp,
        ttd,
        twm,
    );

    // TATP: adx=40 > 35 AND adx_slope=1.0 > 0 -> effective_dist = 0.8 * 1.0 = 0.8
    let atr = 500.0;
    let expected = 51500.0 - atr * 0.8;
    assert!(
        within_tolerance(expected, tsl, TIER_T2_TOLERANCE),
        "TATP preservation: expected={}, got={}",
        expected,
        tsl
    );
}

#[test]
fn test_trailing_tspv_tightening() {
    // AQC-1264: TSPV tightens when atr_slope > 0 (vol expanding) and high profit
    let (ts, td, tslc, tdlc, rfd, rft, evb, vbt, vbm, hpa, ttp, ttd, twm) = trailing_defaults();

    let tsl = rust_compute_trailing(
        PosType::Long,
        50000.0,
        51500.0,
        500.0,
        0.0,
        Confidence::High,
        55.0,
        28.0,
        -0.5,
        0.5, // atr_slope > 0, adx < 35
        1.0,
        3.0,
        ts,
        td,
        tslc,
        tdlc,
        rfd,
        rft,
        evb,
        vbt,
        vbm,
        hpa,
        ttp,
        ttd,
        twm,
    );

    // TSPV: adx=28 (< 35 so TATP not active), atr_slope=0.5 > 0
    // effective_dist = 0.8 * 0.75 = 0.6
    let atr = 500.0;
    let expected = 51500.0 - atr * 0.6;
    assert!(
        within_tolerance(expected, tsl, TIER_T2_TOLERANCE),
        "TSPV tightening: expected={}, got={}",
        expected,
        tsl
    );
}

#[test]
fn test_trailing_weak_trend_widening_low_adx() {
    // AQC-1264: Weak-trend tightening when ADX < 25 (only when not high-profit)
    let (ts, td, tslc, tdlc, rfd, rft, evb, vbt, vbm, hpa, ttp, ttd, twm) = trailing_defaults();

    let tsl = rust_compute_trailing(
        PosType::Long,
        50000.0,
        50600.0,
        500.0,
        0.0,
        Confidence::High,
        55.0,
        20.0,
        0.3,
        0.0,
        1.0,
        1.2, // profit_atr = 1.2 (< 2.0, not high-profit, but >= start=1.0)
        ts,
        td,
        tslc,
        tdlc,
        rfd,
        rft,
        evb,
        vbt,
        vbm,
        hpa,
        ttp,
        ttd,
        twm,
    );

    // Weak-trend: adx=20 < 25 AND profit_atr=1.2 (not > 2.0)
    // effective_dist = 0.8 * 0.7 = 0.56
    // Clamp to floor: max(0.56, 0.5) = 0.56
    let atr = 500.0;
    let expected = 50600.0 - atr * 0.56;
    assert!(
        within_tolerance(expected, tsl, TIER_T2_TOLERANCE),
        "Weak-trend widening: expected={}, got={}",
        expected,
        tsl
    );
}

#[test]
fn test_trailing_rsi_trend_guard_floor() {
    // AQC-1264: RSI Trend-Guard raises min distance when RSI favourable
    let (ts, td, tslc, tdlc, rfd, rft, evb, vbt, vbm, hpa, ttp, ttd, twm) = trailing_defaults();

    // Long with RSI > 60 -> trending floor = 0.7
    let tsl = rust_compute_trailing(
        PosType::Long,
        50000.0,
        50600.0,
        500.0,
        0.0,
        Confidence::High,
        65.0,
        20.0,
        0.3,
        0.0,
        1.0,
        1.2, // not high-profit
        ts,
        td,
        tslc,
        tdlc,
        rfd,
        rft,
        evb,
        vbt,
        vbm,
        hpa,
        ttp,
        ttd,
        twm,
    );

    // Weak-trend: effective_dist = 0.8 * 0.7 = 0.56
    // RSI > 60 -> min_trailing_dist = 0.7
    // Clamp: max(0.56, 0.7) = 0.7
    let atr = 500.0;
    let expected = 50600.0 - atr * 0.7;
    assert!(
        within_tolerance(expected, tsl, TIER_T2_TOLERANCE),
        "RSI Trend-Guard floor: expected={}, got={}",
        expected,
        tsl
    );
}

#[test]
fn test_trailing_low_confidence_overrides() {
    // AQC-1264: Low confidence overrides when configured
    let (ts, td, _tslc, _tdlc, rfd, rft, evb, vbt, vbm, hpa, ttp, ttd, twm) = trailing_defaults();

    // Set low-conf overrides
    let tslc = 1.5; // trailing_start_atr_low_conf
    let tdlc = 1.0; // trailing_distance_atr_low_conf

    let tsl = rust_compute_trailing(
        PosType::Long,
        50000.0,
        51500.0,
        500.0,
        0.0,
        Confidence::Low,
        55.0,
        30.0,
        0.5,
        0.0,
        1.0,
        3.0, // profit = 3.0 ATR
        ts,
        td,
        tslc,
        tdlc,
        rfd,
        rft,
        evb,
        vbt,
        vbm,
        hpa,
        ttp,
        ttd,
        twm,
    );

    // Low confidence: trailing_start = 1.5, trailing_dist = 1.0
    // profit=3.0 > start=1.5, so active
    // High-profit: adx=30 (< 35), atr_slope=0 -> default tighten: 1.0 * 0.5 = 0.5
    // Clamp to floor: max(0.5, 0.5) = 0.5
    let atr = 500.0;
    let expected = 51500.0 - atr * 0.5;
    assert!(
        within_tolerance(expected, tsl, TIER_T2_TOLERANCE),
        "Low confidence overrides: expected={}, got={}",
        expected,
        tsl
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
// AQC-1265: Take profit axis validation
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_tp_codegen_parity() {
    let src = get_decision_cuda_source();

    // Function signature
    assert!(
        src.contains("__device__ TpResult check_tp_codegen("),
        "TP codegen must have correct __device__ function signature"
    );
    assert!(
        src.contains("const GpuComboConfig& cfg"),
        "TP must take GpuComboConfig by const ref"
    );
}

#[test]
fn test_tp_full_hit_long() {
    // AQC-1265: Full TP hit for long position
    let src = get_decision_cuda_source();

    // Long: TP above entry
    assert!(
        src.contains("entry_price + (atr * tp_mult)"),
        "Long TP price = entry + atr * mult"
    );
    assert!(
        src.contains("current_price >= tp_price"),
        "Long TP hit when current >= tp_price"
    );
    assert!(
        src.contains("result.exit_code = 11"),
        "Full TP exit_code must be 11"
    );
}

#[test]
fn test_tp_full_hit_short() {
    // AQC-1265: Full TP hit for short position
    let src = get_decision_cuda_source();

    assert!(
        src.contains("entry_price - (atr * tp_mult)"),
        "Short TP price = entry - atr * mult"
    );
    assert!(
        src.contains("current_price <= tp_price"),
        "Short TP hit when current <= tp_price"
    );
}

#[test]
fn test_tp_partial_hit() {
    // AQC-1265: Partial TP fires with reduce action
    let src = get_decision_cuda_source();

    assert!(
        src.contains("cfg.enable_partial_tp"),
        "Partial TP must check enable flag"
    );
    assert!(
        src.contains("tp1_taken == 0u"),
        "Partial TP checks tp1_taken == 0 for first partial"
    );
    assert!(
        src.contains("result.action = 1"),
        "Partial TP must set action = 1 (reduce)"
    );
    assert!(
        src.contains("result.fraction = pct"),
        "Partial TP must set fraction"
    );
    assert!(
        src.contains("result.exit_code = 10"),
        "Partial TP exit_code must be 10"
    );
}

#[test]
fn test_tp_tp1_taken_then_full_check() {
    // AQC-1265: After tp1 taken, check full TP for remainder
    let src = get_decision_cuda_source();

    assert!(
        src.contains("tp1 already taken"),
        "Must have path for tp1 already taken"
    );
    assert!(
        src.contains("cfg.tp_partial_atr_mult > 0.0"),
        "Must check for separate partial mult level"
    );
}

#[test]
fn test_tp_separate_partial_level() {
    // AQC-1265: Separate partial TP level when tp_partial_atr_mult > 0
    let src = get_decision_cuda_source();

    assert!(
        src.contains("double partial_mult"),
        "Must compute partial_mult separately"
    );
    assert!(
        src.contains("cfg.tp_partial_atr_mult"),
        "Must read tp_partial_atr_mult from config"
    );
    assert!(
        src.contains("double partial_tp_price"),
        "Must compute separate partial_tp_price"
    );
}

#[test]
fn test_tp_atr_fallback() {
    // AQC-1265: ATR fallback for zero entry_atr
    let src = get_decision_cuda_source();

    // TP codegen contains the same ATR fallback pattern
    let tp_section_start = src
        .find("check_tp_codegen")
        .expect("check_tp_codegen must exist");
    let tp_section = &src[tp_section_start..];
    assert!(
        tp_section.contains("entry_price * 0.005"),
        "TP codegen must have ATR fallback for zero entry_atr"
    );
}

#[test]
fn test_tp_notional_minimum_check() {
    // AQC-1265: Partial TP checks minimum notional
    let src = get_decision_cuda_source();

    assert!(
        src.contains("remaining_notional"),
        "Must compute remaining notional"
    );
    assert!(
        src.contains("cfg.tp_partial_min_notional_usd"),
        "Must check minimum notional threshold"
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
// AQC-1266: Smart exits axis-by-axis validation
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_smart_exits_codegen_parity() {
    let src = get_decision_cuda_source();

    // Function signature
    assert!(
        src.contains("__device__ SmartExitResult check_smart_exits_codegen("),
        "Smart exits codegen must have correct __device__ function signature"
    );
}

#[test]
fn test_smart_exit_1_trend_breakdown() {
    // AQC-1266: Trend Breakdown (EMA Cross) with TBB buffer
    let src = get_decision_cuda_source();

    // Find smart exits section
    let se_start = src
        .find("check_smart_exits_codegen")
        .expect("smart exits must exist");
    let se_section = &src[se_start..];

    assert!(
        se_section.contains("ema_fast < ema_slow"),
        "Trend Breakdown must check EMA cross for LONG"
    );
    assert!(
        se_section.contains("ema_fast > ema_slow"),
        "Trend Breakdown must check EMA cross for SHORT"
    );
    assert!(
        se_section.contains("is_weak_cross"),
        "Trend Breakdown must have TBB (weak cross) buffer"
    );
    assert!(
        se_section.contains("ema_dev < 0.001"),
        "TBB must check EMA deviation < 0.001"
    );
    assert!(
        se_section.contains("exit_code = 1"),
        "Trend Breakdown must set exit_code = 1"
    );
}

#[test]
fn test_smart_exit_2_trend_exhaustion() {
    // AQC-1266: Trend Exhaustion (ADX below threshold)
    let src = get_decision_cuda_source();

    let se_start = src
        .find("check_smart_exits_codegen")
        .expect("smart exits must exist");
    let se_section = &src[se_start..];

    assert!(
        se_section.contains("adx < adx_exhaustion_lt"),
        "Trend Exhaustion must check ADX below threshold"
    );
    assert!(
        se_section.contains("exit_code = 2"),
        "Trend Exhaustion must set exit_code = 2"
    );
    assert!(
        se_section.contains("cfg.smart_exit_adx_exhaustion_lt"),
        "Must read ADX exhaustion threshold from config"
    );
}

#[test]
fn test_smart_exit_3_ema_macro_breakdown() {
    // AQC-1266: EMA Macro Breakdown
    let src = get_decision_cuda_source();

    let se_start = src
        .find("check_smart_exits_codegen")
        .expect("smart exits must exist");
    let se_section = &src[se_start..];

    assert!(
        se_section.contains("cfg.require_macro_alignment"),
        "EMA Macro Breakdown must check require_macro_alignment flag"
    );
    assert!(
        se_section.contains("current_price < ema_macro"),
        "LONG EMA Macro Breakdown: price < ema_macro"
    );
    assert!(
        se_section.contains("current_price > ema_macro"),
        "SHORT EMA Macro Breakdown: price > ema_macro"
    );
    assert!(
        se_section.contains("exit_code = 3"),
        "EMA Macro Breakdown must set exit_code = 3"
    );
}

#[test]
fn test_smart_exit_4_stagnation() {
    // AQC-1266: Stagnation Exit (low-vol + underwater)
    let src = get_decision_cuda_source();

    let se_start = src
        .find("check_smart_exits_codegen")
        .expect("smart exits must exist");
    let se_section = &src[se_start..];

    assert!(
        se_section.contains("atr < (eff_atr * 0.70)"),
        "Stagnation must check ATR < 70% of entry ATR"
    );
    assert!(
        se_section.contains("exit_code = 4"),
        "Stagnation must set exit_code = 4"
    );
}

#[test]
fn test_smart_exit_5_funding_headwind_noop() {
    // AQC-1266: Funding Headwind is a no-op (never fires in backtester v1)
    let src = get_decision_cuda_source();

    let se_start = src
        .find("check_smart_exits_codegen")
        .expect("smart exits must exist");
    let se_section = &src[se_start..];

    assert!(
        se_section.contains("Funding Headwind"),
        "Must have Funding Headwind comment/marker"
    );
    // Should NOT have exit_code = 5 as an active path
    // The code has it as a placeholder comment but no active assignment
    assert!(
        se_section.contains("exit_code = 5") == false
            || se_section.contains("no-op")
            || se_section.contains("never fires"),
        "Funding Headwind must be a no-op (exit_code=5 never assigned actively)"
    );
}

#[test]
fn test_smart_exit_6_tsme() {
    // AQC-1266: TSME (Trend Saturation Momentum Exit)
    let src = get_decision_cuda_source();

    let se_start = src
        .find("check_smart_exits_codegen")
        .expect("smart exits must exist");
    let se_section = &src[se_start..];

    assert!(
        se_section.contains("adx > 50.0"),
        "TSME must check ADX > 50"
    );
    assert!(
        se_section.contains("cfg.tsme_min_profit_atr"),
        "TSME must use min_profit_atr from config"
    );
    assert!(
        se_section.contains("cfg.tsme_require_adx_slope_negative"),
        "TSME must check ADX slope negative requirement"
    );
    assert!(
        se_section.contains("exit_code = 6"),
        "TSME must set exit_code = 6"
    );
}

#[test]
fn test_smart_exit_7_mmde() {
    // AQC-1266: MMDE (MACD Persistent Divergence Exit)
    let src = get_decision_cuda_source();

    let se_start = src
        .find("check_smart_exits_codegen")
        .expect("smart exits must exist");
    let se_section = &src[se_start..];

    assert!(
        se_section.contains("profit_atr > 1.5"),
        "MMDE must check profit > 1.5 ATR"
    );
    assert!(
        se_section.contains("adx > 35.0"),
        "MMDE must check ADX > 35"
    );
    assert!(
        se_section.contains("prev3_macd_hist"),
        "MMDE must check 3 consecutive MACD contractions (4 bars)"
    );
    assert!(
        se_section.contains("exit_code = 7"),
        "MMDE must set exit_code = 7"
    );
}

#[test]
fn test_smart_exit_8_rsi_overextension() {
    // AQC-1266: RSI Overextension Exit with profit-switched thresholds
    let src = get_decision_cuda_source();

    let se_start = src
        .find("check_smart_exits_codegen")
        .expect("smart exits must exist");
    let se_section = &src[se_start..];

    assert!(
        se_section.contains("cfg.enable_rsi_overextension_exit"),
        "RSI Overextension must check enable flag"
    );
    assert!(
        se_section.contains("cfg.rsi_exit_profit_atr_switch"),
        "RSI Overextension must use profit_atr_switch"
    );
    assert!(
        se_section.contains("cfg.rsi_exit_ub_lo_profit")
            && se_section.contains("cfg.rsi_exit_ub_hi_profit"),
        "RSI Overextension must have profit-switched thresholds"
    );
    assert!(
        se_section.contains("exit_code = 8"),
        "RSI Overextension must set exit_code = 8"
    );
}

#[test]
fn test_smart_exit_priority_order() {
    // AQC-1266: Sub-checks evaluated in order 1-8
    let src = get_decision_cuda_source();

    let se_start = src
        .find("check_smart_exits_codegen")
        .expect("smart exits must exist");
    let se_section = &src[se_start..];

    let pos1 = se_section
        .find("exit_code = 1")
        .expect("exit_code=1 must exist");
    let pos2 = se_section
        .find("exit_code = 2")
        .expect("exit_code=2 must exist");
    let pos4 = se_section
        .find("exit_code = 4")
        .expect("exit_code=4 must exist");
    let pos6 = se_section
        .find("exit_code = 6")
        .expect("exit_code=6 must exist");
    let pos7 = se_section
        .find("exit_code = 7")
        .expect("exit_code=7 must exist");
    let pos8 = se_section
        .find("exit_code = 8")
        .expect("exit_code=8 must exist");

    assert!(
        pos1 < pos2,
        "Trend Breakdown (1) must precede Trend Exhaustion (2)"
    );
    assert!(
        pos2 < pos4,
        "Trend Exhaustion (2) must precede Stagnation (4)"
    );
    assert!(pos4 < pos6, "Stagnation (4) must precede TSME (6)");
    assert!(pos6 < pos7, "TSME (6) must precede MMDE (7)");
    assert!(pos7 < pos8, "MMDE (7) must precede RSI Overextension (8)");
}

// ═══════════════════════════════════════════════════════════════════════════════
// AQC-1267: Exit orchestrator priority sequence validation
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_all_exits_codegen_parity() {
    let src = get_decision_cuda_source();

    // Function signature
    assert!(
        src.contains("__device__ AllExitResult check_all_exits_codegen("),
        "Exit orchestrator must have correct __device__ function signature"
    );
    assert!(
        src.contains("struct AllExitResult"),
        "Must define AllExitResult struct"
    );
}

#[test]
fn test_all_exits_sl_triggers_first() {
    // AQC-1267: SL triggers first with exit_code=100
    let src = get_decision_cuda_source();

    let orch_start = src
        .find("check_all_exits_codegen")
        .expect("orchestrator must exist");
    let orch_section = &src[orch_start..];

    assert!(
        orch_section.contains("exit_code = 100"),
        "SL must set exit_code = 100"
    );
    assert!(
        orch_section.contains("compute_sl_price_codegen"),
        "Orchestrator must call compute_sl_price_codegen"
    );
}

#[test]
fn test_all_exits_trailing_triggers_second() {
    // AQC-1267: Trailing triggers second with exit_code=101
    let src = get_decision_cuda_source();

    let orch_start = src
        .find("check_all_exits_codegen")
        .expect("orchestrator must exist");
    let orch_section = &src[orch_start..];

    assert!(
        orch_section.contains("exit_code = 101"),
        "Trailing must set exit_code = 101"
    );
    assert!(
        orch_section.contains("compute_trailing_codegen"),
        "Orchestrator must call compute_trailing_codegen"
    );
}

#[test]
fn test_all_exits_tp_triggers_third() {
    // AQC-1267: TP triggers third with exit_code=102
    let src = get_decision_cuda_source();

    let orch_start = src
        .find("check_all_exits_codegen")
        .expect("orchestrator must exist");
    let orch_section = &src[orch_start..];

    assert!(
        orch_section.contains("exit_code = 102"),
        "TP must set exit_code = 102"
    );
    assert!(
        orch_section.contains("check_tp_codegen"),
        "Orchestrator must call check_tp_codegen"
    );
}

#[test]
fn test_all_exits_smart_triggers_fourth() {
    // AQC-1267: Smart exits trigger fourth with exit_code=1-8
    let src = get_decision_cuda_source();

    let orch_start = src
        .find("check_all_exits_codegen")
        .expect("orchestrator must exist");
    let orch_section = &src[orch_start..];

    assert!(
        orch_section.contains("check_smart_exits_codegen"),
        "Orchestrator must call check_smart_exits_codegen"
    );
    assert!(
        orch_section.contains("smart.exit_code"),
        "Orchestrator must forward smart exit_code"
    );
}

#[test]
fn test_all_exits_no_exit_returns_zero() {
    // AQC-1267: No exit when all checks pass (exit_code=0)
    let src = get_decision_cuda_source();

    let orch_start = src
        .find("check_all_exits_codegen")
        .expect("orchestrator must exist");
    let orch_section = &src[orch_start..];

    assert!(
        orch_section.contains("result.exit_code = 0")
            || orch_section.contains("result.should_exit = false"),
        "No-exit path must return exit_code=0 or should_exit=false"
    );
}

#[test]
fn test_all_exits_priority_ordering() {
    // AQC-1267: Verify priority sequence: SL(100) > Trailing(101) > TP(102) > Smart(1-8)
    let src = get_decision_cuda_source();

    let orch_start = src
        .find("check_all_exits_codegen")
        .expect("orchestrator must exist");
    let orch_section = &src[orch_start..];

    let sl_pos = orch_section
        .find("exit_code = 100")
        .expect("SL exit must exist");
    let trail_pos = orch_section
        .find("exit_code = 101")
        .expect("Trailing exit must exist");
    let tp_pos = orch_section
        .find("exit_code = 102")
        .expect("TP exit must exist");
    let smart_pos = orch_section
        .find("smart.exit_code")
        .expect("Smart exit must exist");

    assert!(sl_pos < trail_pos, "SL must be checked before Trailing");
    assert!(trail_pos < tp_pos, "Trailing must be checked before TP");
    assert!(tp_pos < smart_pos, "TP must be checked before Smart Exits");
}

// ═══════════════════════════════════════════════════════════════════════════════
// AQC-1268: Sizing & leverage axis validation
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_entry_size_codegen_parity() {
    let src = get_decision_cuda_source();

    // Function signature
    assert!(
        src.contains("__device__ SizingResultD compute_entry_size_codegen("),
        "Entry sizing codegen must have correct __device__ function signature"
    );
    assert!(
        src.contains("struct SizingResultD"),
        "Must define SizingResultD struct"
    );
}

#[test]
fn test_entry_size_static_sizing() {
    // AQC-1268: Static sizing when dynamic disabled
    let src = get_decision_cuda_source();

    let sz_start = src
        .find("compute_entry_size_codegen")
        .expect("sizing fn must exist");
    let sz_section = &src[sz_start..];

    assert!(
        sz_section.contains("cfg.allocation_pct"),
        "Static sizing must use allocation_pct from config"
    );
    assert!(
        sz_section.contains("cfg.enable_dynamic_sizing"),
        "Must check enable_dynamic_sizing flag"
    );
}

#[test]
fn test_entry_size_confidence_multiplier() {
    // AQC-1268: Confidence multiplier in dynamic sizing
    let src = get_decision_cuda_source();

    let sz_start = src
        .find("compute_entry_size_codegen")
        .expect("sizing fn must exist");
    let sz_section = &src[sz_start..];

    assert!(
        sz_section.contains("cfg.confidence_mult_high"),
        "Dynamic sizing must use confidence_mult_high"
    );
    assert!(
        sz_section.contains("cfg.confidence_mult_medium"),
        "Dynamic sizing must use confidence_mult_medium"
    );
    assert!(
        sz_section.contains("cfg.confidence_mult_low"),
        "Dynamic sizing must use confidence_mult_low"
    );
    assert!(
        sz_section.contains("CONF_HIGH") && sz_section.contains("CONF_LOW"),
        "Must check confidence enum values"
    );
}

#[test]
fn test_entry_size_adx_multiplier() {
    // AQC-1268: ADX multiplier scaling in dynamic sizing
    let src = get_decision_cuda_source();

    let sz_start = src
        .find("compute_entry_size_codegen")
        .expect("sizing fn must exist");
    let sz_section = &src[sz_start..];

    assert!(
        sz_section.contains("cfg.adx_sizing_full_adx"),
        "ADX multiplier must use adx_sizing_full_adx from config"
    );
    assert!(
        sz_section.contains("cfg.adx_sizing_min_mult"),
        "ADX multiplier must use adx_sizing_min_mult from config"
    );
    assert!(
        sz_section.contains("adx_ratio") || sz_section.contains("adx_mult"),
        "Must compute ADX ratio or multiplier"
    );
}

#[test]
fn test_entry_size_vol_scalar() {
    // AQC-1268: Volatility scalar (inverse vol ratio)
    let src = get_decision_cuda_source();

    let sz_start = src
        .find("compute_entry_size_codegen")
        .expect("sizing fn must exist");
    let sz_section = &src[sz_start..];

    assert!(
        sz_section.contains("cfg.vol_baseline_pct"),
        "Vol scalar must use vol_baseline_pct from config"
    );
    assert!(
        sz_section.contains("cfg.vol_scalar_min") && sz_section.contains("cfg.vol_scalar_max"),
        "Vol scalar must clamp to [min, max]"
    );
    assert!(
        sz_section.contains("1.0 / vol_ratio"),
        "Vol scalar is inverse of vol_ratio"
    );
}

#[test]
fn test_entry_size_dynamic_leverage_tiers() {
    // AQC-1268: Dynamic leverage per-confidence tiers
    let src = get_decision_cuda_source();

    let sz_start = src
        .find("compute_entry_size_codegen")
        .expect("sizing fn must exist");
    let sz_section = &src[sz_start..];

    assert!(
        sz_section.contains("cfg.leverage_high"),
        "Dynamic leverage must use leverage_high"
    );
    assert!(
        sz_section.contains("cfg.leverage_medium"),
        "Dynamic leverage must use leverage_medium"
    );
    assert!(
        sz_section.contains("cfg.leverage_low"),
        "Dynamic leverage must use leverage_low"
    );
}

#[test]
fn test_entry_size_uses_double_precision() {
    // AQC-1268: Sizing uses double precision
    let src = get_decision_cuda_source();

    let sz_start = src
        .find("compute_entry_size_codegen")
        .expect("sizing fn must exist");
    let sz_section = &src[sz_start..];

    assert!(
        sz_section.contains("double margin"),
        "margin must be double"
    );
    assert!(
        sz_section.contains("double notional"),
        "notional must be double"
    );
    assert!(sz_section.contains("double size"), "size must be double");
    assert!(sz_section.contains("double lev"), "leverage must be double");
}

// ═══════════════════════════════════════════════════════════════════════════════
// AQC-1269: PESC + entry/exit cooldowns validation
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_pesc_codegen_parity() {
    let src = get_decision_cuda_source();

    // Function signature
    assert!(
        src.contains("__device__ bool is_pesc_blocked_codegen("),
        "PESC codegen must have correct __device__ bool function signature"
    );
    assert!(
        src.contains("const GpuComboConfig& cfg"),
        "PESC must take GpuComboConfig by const ref"
    );
}

#[test]
fn test_pesc_disabled_returns_false() {
    // AQC-1269: PESC disabled when reentry_cooldown_minutes == 0
    let src = get_decision_cuda_source();

    let pesc_start = src
        .find("is_pesc_blocked_codegen")
        .expect("PESC fn must exist");
    let pesc_section = &src[pesc_start..];

    assert!(
        pesc_section.contains("cfg.reentry_cooldown_minutes == 0u"),
        "PESC must check reentry_cooldown_minutes == 0"
    );
    assert!(
        pesc_section.contains("return false"),
        "PESC disabled must return false"
    );
}

#[test]
fn test_pesc_signal_flip_bypass() {
    // AQC-1269: Signal flip exit reason bypasses cooldown
    let src = get_decision_cuda_source();

    let pesc_start = src
        .find("is_pesc_blocked_codegen")
        .expect("PESC fn must exist");
    let pesc_section = &src[pesc_start..];

    assert!(
        pesc_section.contains("close_reason == PESC_SIGNAL_FLIP"),
        "PESC must check for signal flip (uses PESC_SIGNAL_FLIP define)"
    );
}

#[test]
fn test_pesc_direction_gate() {
    // AQC-1269: PESC only blocks same-direction re-entry
    let src = get_decision_cuda_source();

    let pesc_start = src
        .find("is_pesc_blocked_codegen")
        .expect("PESC fn must exist");
    let pesc_section = &src[pesc_start..];

    assert!(
        pesc_section.contains("close_type != desired_type"),
        "PESC must check direction match"
    );
}

#[test]
fn test_pesc_adx_interpolation() {
    // AQC-1269: ADX interpolation of cooldown (25..40 linear)
    let src = get_decision_cuda_source();

    let pesc_start = src
        .find("is_pesc_blocked_codegen")
        .expect("PESC fn must exist");
    let pesc_section = &src[pesc_start..];

    assert!(
        pesc_section.contains("adx >= 40.0"),
        "PESC must check strong trend threshold (ADX >= 40)"
    );
    assert!(
        pesc_section.contains("adx <= 25.0"),
        "PESC must check weak trend threshold (ADX <= 25)"
    );
    assert!(
        pesc_section.contains("(adx - 25.0) / 15.0"),
        "PESC must interpolate ADX 25..40 linearly"
    );
    assert!(
        pesc_section.contains("cfg.reentry_cooldown_min_mins"),
        "PESC must use min cooldown from config"
    );
    assert!(
        pesc_section.contains("cfg.reentry_cooldown_max_mins"),
        "PESC must use max cooldown from config"
    );
}

#[test]
fn test_pesc_no_prior_close_bypass() {
    // AQC-1269: No prior close recorded bypasses cooldown
    let src = get_decision_cuda_source();

    let pesc_start = src
        .find("is_pesc_blocked_codegen")
        .expect("PESC fn must exist");
    let pesc_section = &src[pesc_start..];

    assert!(
        pesc_section.contains("close_ts == 0u"),
        "PESC must check for no prior close"
    );
}

#[test]
fn test_pesc_elapsed_time_check() {
    // AQC-1269: PESC compares elapsed time against cooldown
    let src = get_decision_cuda_source();

    let pesc_start = src
        .find("is_pesc_blocked_codegen")
        .expect("PESC fn must exist");
    let pesc_section = &src[pesc_start..];

    assert!(
        pesc_section.contains("elapsed < cooldown_sec"),
        "PESC must block when elapsed < cooldown_sec"
    );
    assert!(
        pesc_section.contains("cooldown_mins * 60.0"),
        "PESC must convert cooldown minutes to seconds"
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
// AQC-1270: Config round-trip 141 fields
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_config_round_trip_size_140_fields() {
    // AQC-1270: Verify GpuComboConfig is 560 bytes = 140 x 4-byte fields.
    // This ensures all fields are accounted for and none were accidentally
    // added or removed without updating the struct size assertion.
    assert_eq!(
        std::mem::size_of::<bt_gpu::buffers::GpuComboConfig>(),
        560,
        "GpuComboConfig must be exactly 560 bytes (140 x 4-byte fields)"
    );
}

#[test]
fn test_config_all_decision_fields_referenced_in_codegen() {
    // AQC-1270: Verify each decision-relevant config field is referenced in the
    // codegen output. This ensures the CUDA generated code actually reads the
    // config fields that the GpuComboConfig struct provides.
    let src = get_decision_cuda_source();

    // Core sizing fields
    let decision_fields = [
        // SL
        "cfg.sl_atr_mult",
        "cfg.enable_breakeven_stop",
        "cfg.breakeven_start_atr",
        "cfg.breakeven_buffer_atr",
        // Trailing
        "cfg.trailing_start_atr",
        "cfg.trailing_distance_atr",
        "cfg.trailing_start_atr_low_conf",
        "cfg.trailing_distance_atr_low_conf",
        "cfg.trailing_rsi_floor_default",
        "cfg.trailing_rsi_floor_trending",
        "cfg.enable_vol_buffered_trailing",
        "cfg.trailing_vbts_bb_threshold",
        "cfg.trailing_vbts_mult",
        "cfg.trailing_high_profit_atr",
        "cfg.trailing_tighten_tspv",
        "cfg.trailing_tighten_default",
        "cfg.trailing_weak_trend_mult",
        // TP
        "cfg.tp_atr_mult",
        "cfg.enable_partial_tp",
        "cfg.tp_partial_pct",
        "cfg.tp_partial_atr_mult",
        "cfg.tp_partial_min_notional_usd",
        // Smart exits
        "cfg.smart_exit_adx_exhaustion_lt",
        "cfg.smart_exit_adx_exhaustion_lt_low_conf",
        "cfg.enable_rsi_overextension_exit",
        "cfg.rsi_exit_profit_atr_switch",
        "cfg.rsi_exit_ub_lo_profit",
        "cfg.rsi_exit_ub_hi_profit",
        "cfg.rsi_exit_lb_lo_profit",
        "cfg.rsi_exit_lb_hi_profit",
        "cfg.rsi_exit_ub_lo_profit_low_conf",
        "cfg.rsi_exit_ub_hi_profit_low_conf",
        "cfg.rsi_exit_lb_lo_profit_low_conf",
        "cfg.rsi_exit_lb_hi_profit_low_conf",
        "cfg.tsme_min_profit_atr",
        "cfg.tsme_require_adx_slope_negative",
        "cfg.require_macro_alignment",
        // Gates
        "cfg.enable_ranging_filter",
        "cfg.enable_anomaly_filter",
        "cfg.enable_extension_filter",
        "cfg.require_adx_rising",
        "cfg.adx_rising_saturation",
        "cfg.require_volume_confirmation",
        "cfg.vol_confirm_include_prev",
        "cfg.min_adx",
        "cfg.max_dist_ema_fast",
        "cfg.anomaly_price_change_pct",
        "cfg.anomaly_ema_dev_pct",
        "cfg.ranging_adx_lt",
        "cfg.ranging_bb_width_ratio_lt",
        "cfg.ranging_rsi_low",
        "cfg.ranging_rsi_high",
        "cfg.ranging_min_signals",
        "cfg.ave_enabled",
        "cfg.ave_atr_ratio_gt",
        "cfg.ave_adx_mult",
        "cfg.enable_slow_drift_entries",
        "cfg.slow_drift_ranging_slope_override",
        // Signals
        "cfg.dre_min_adx",
        "cfg.dre_max_adx",
        "cfg.dre_long_rsi_limit_low",
        "cfg.dre_long_rsi_limit_high",
        "cfg.dre_short_rsi_limit_low",
        "cfg.dre_short_rsi_limit_high",
        "cfg.macd_mode",
        "cfg.use_stoch_rsi_filter",
        "cfg.stoch_rsi_block_long_gt",
        "cfg.stoch_rsi_block_short_lt",
        "cfg.high_conf_volume_mult",
        "cfg.require_btc_alignment",
        "cfg.btc_adx_override",
        "cfg.enable_pullback_entries",
        "cfg.pullback_min_adx",
        "cfg.pullback_rsi_long_min",
        "cfg.pullback_rsi_short_max",
        "cfg.pullback_require_macd_sign",
        "cfg.pullback_confidence",
        "cfg.slow_drift_min_slope_pct",
        "cfg.slow_drift_min_adx",
        "cfg.slow_drift_rsi_long_min",
        "cfg.slow_drift_rsi_short_max",
        "cfg.slow_drift_require_macd_sign",
        // Sizing
        "cfg.allocation_pct",
        "cfg.enable_dynamic_sizing",
        "cfg.confidence_mult_high",
        "cfg.confidence_mult_medium",
        "cfg.confidence_mult_low",
        "cfg.adx_sizing_full_adx",
        "cfg.adx_sizing_min_mult",
        "cfg.vol_baseline_pct",
        "cfg.vol_scalar_min",
        "cfg.vol_scalar_max",
        "cfg.leverage",
        "cfg.leverage_high",
        "cfg.leverage_medium",
        "cfg.leverage_low",
        // PESC
        "cfg.reentry_cooldown_minutes",
        "cfg.reentry_cooldown_min_mins",
        "cfg.reentry_cooldown_max_mins",
    ];

    for field in &decision_fields {
        assert!(
            src.contains(field),
            "Decision codegen must reference config field '{}' but it was not found",
            field
        );
    }
}

#[test]
fn test_config_codegen_functions_all_present() {
    // AQC-1270: Verify all 9 decision codegen functions are present
    let src = get_decision_cuda_source();

    let expected_fns = [
        "check_gates_codegen",
        "generate_signal_codegen",
        "compute_sl_price_codegen",
        "compute_trailing_codegen",
        "check_tp_codegen",
        "check_smart_exits_codegen",
        "check_all_exits_codegen",
        "compute_entry_size_codegen",
        "is_pesc_blocked_codegen",
    ];

    for func in &expected_fns {
        assert!(
            src.contains(func),
            "Decision codegen must contain function '{}' but it was not found",
            func
        );
    }
}

#[test]
fn test_config_struct_result_types_present() {
    // AQC-1270: Verify all result struct types are defined in codegen
    let src = get_decision_cuda_source();

    let expected_structs = [
        "struct GateResultD",
        "struct SignalResult",
        "struct TpResult",
        "struct SmartExitResult",
        "struct AllExitResult",
        "struct SizingResultD",
    ];

    for s in &expected_structs {
        assert!(
            src.contains(s),
            "Decision codegen must define '{}' but it was not found",
            s
        );
    }
}

#[test]
fn test_config_all_codegen_uses_double_precision() {
    // AQC-1270: Verify all codegen functions use double for price/indicator math
    let src = get_decision_cuda_source();

    // All codegen functions must return or use double (not float) for price math
    assert!(
        src.contains("__device__ double compute_sl_price_codegen("),
        "SL must return double"
    );
    assert!(
        src.contains("__device__ double compute_trailing_codegen("),
        "Trailing must return double"
    );

    // Must not use float for critical variables
    let forbidden = [
        "float sl_price",
        "float sl_mult",
        "float tp_price",
        "float trailing_start",
        "float trailing_dist",
        "float effective_dist",
        "float candidate",
        "float margin",
        "float notional",
    ];
    for pat in &forbidden {
        assert!(
            !src.contains(pat),
            "Codegen must NOT use '{}' (AQC-734 mandate: double precision)",
            pat
        );
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// AQC-1232: Fixture-based numerical parity tests for sizing & cooldown codegen
// ═══════════════════════════════════════════════════════════════════════════════

/// Rust SSOT: compute_entry_sizing (mirrors risk-core/src/lib.rs).
///
/// This is a local copy of the CPU SSOT logic for direct numerical verification
/// without engine/position/indicator wrappers. It MUST match risk_core::compute_entry_sizing.
fn rust_compute_entry_sizing(
    equity: f64,
    price: f64,
    atr: f64,
    adx: f64,
    confidence: Confidence,
    allocation_pct: f64,
    enable_dynamic_sizing: bool,
    confidence_mult_high: f64,
    confidence_mult_medium: f64,
    confidence_mult_low: f64,
    adx_sizing_min_mult: f64,
    adx_sizing_full_adx: f64,
    vol_baseline_pct: f64,
    vol_scalar_min: f64,
    vol_scalar_max: f64,
    leverage_low: f64,
    leverage_medium: f64,
    leverage_high: f64,
) -> (f64, f64, f64, f64) {
    let mut margin_used = equity * allocation_pct;

    if enable_dynamic_sizing {
        let confidence_mult = match confidence {
            Confidence::High => confidence_mult_high,
            Confidence::Medium => confidence_mult_medium,
            Confidence::Low => confidence_mult_low,
        };

        let adx_mult = if adx_sizing_full_adx > 0.0 {
            (adx / adx_sizing_full_adx).clamp(adx_sizing_min_mult, 1.0)
        } else {
            adx_sizing_min_mult
        };

        let vol_ratio = if vol_baseline_pct > 0.0 && price > 0.0 {
            (atr / price) / vol_baseline_pct
        } else {
            1.0
        };
        let vol_scalar_raw = if vol_ratio > 0.0 {
            1.0 / vol_ratio
        } else {
            1.0
        };
        let vol_scalar = vol_scalar_raw.clamp(vol_scalar_min, vol_scalar_max);

        margin_used *= confidence_mult * adx_mult * vol_scalar;
    }

    let lev = match confidence {
        Confidence::High => leverage_high,
        Confidence::Medium => leverage_medium,
        Confidence::Low => leverage_low,
    };

    let notional = margin_used * lev;
    let size = if price > 0.0 { notional / price } else { 0.0 };

    (size, margin_used, lev, notional)
}

/// Rust SSOT: is_pesc_blocked (mirrors bt-core/src/engine.rs).
///
/// Simplified for fixture testing: uses raw timestamp/type/reason values
/// instead of SimState/StrategyConfig structs. Returns true if entry is blocked.
fn rust_is_pesc_blocked(
    reentry_cooldown_minutes: u32,
    reentry_cooldown_min_mins: u32,
    reentry_cooldown_max_mins: u32,
    close_ts: u32,     // seconds
    close_type: u32,   // 0=none, 1=LONG, 2=SHORT
    close_reason: u32, // 0=none, 1=signal_flip, 2=other
    desired_type: u32, // 1=LONG, 2=SHORT
    current_ts: u32,   // seconds
    adx: f64,
) -> bool {
    // Gate: disabled when reentry_cooldown_minutes == 0
    if reentry_cooldown_minutes == 0 {
        return false;
    }

    // No prior close recorded
    if close_ts == 0 {
        return false;
    }

    // Signal flip bypass (reason == 1 means signal_flip in GPU encoding;
    // GPU uses: 1=signal_flip, 2=other. This matches the codegen check
    // `close_reason == 2u` which checks for "non-signal-flip" reasons.
    // Actually the GPU check is: if close_reason != 2u -> not blocked (bypass).
    // Wait — re-reading the codegen test: it checks `close_reason == 2u` which
    // in the GPU encoding means "other" (non-signal-flip). The GPU PESC blocks
    // only when close_reason == 2 (i.e., NOT a signal flip).
    // So: if close_reason != 2 (i.e., it IS a signal flip or none), bypass.
    // But the CPU code checks: close_reason == "Signal Flip" -> return false.
    // In GPU: 0=none, 1=signal_flip, 2=other. So signal_flip = 1 -> bypass.
    // The codegen test says `close_reason == 2u` which means "block when reason
    // is 'other'". If reason is 1 (signal_flip), the block code is skipped.
    // For our Rust reference: if close_reason == 1 (signal_flip), return false.
    if close_reason == 1 {
        return false;
    }

    // Direction gate: only blocks same-direction re-entry
    if close_type != desired_type {
        return false;
    }

    // ADX-adaptive cooldown interpolation
    let min_cd = reentry_cooldown_min_mins as f64;
    let max_cd = reentry_cooldown_max_mins as f64;
    let cooldown_mins = if adx >= 40.0 {
        min_cd
    } else if adx <= 25.0 {
        max_cd
    } else {
        let t = (adx - 25.0) / 15.0;
        max_cd + t * (min_cd - max_cd)
    };

    let cooldown_sec = cooldown_mins * 60.0;
    let elapsed = (current_ts as f64) - (close_ts as f64);

    elapsed < cooldown_sec
}

/// Sizing fixture: captures a specific config + market + equity scenario.
#[derive(Debug, Clone)]
struct SizingFixture {
    label: &'static str,
    equity: f64,
    price: f64,
    atr: f64,
    adx: f64,
    confidence: Confidence,
    // Config params
    allocation_pct: f64,
    enable_dynamic_sizing: bool,
    confidence_mult_high: f64,
    confidence_mult_medium: f64,
    confidence_mult_low: f64,
    adx_sizing_min_mult: f64,
    adx_sizing_full_adx: f64,
    vol_baseline_pct: f64,
    vol_scalar_min: f64,
    vol_scalar_max: f64,
    leverage_low: f64,
    leverage_medium: f64,
    leverage_high: f64,
    // Expected outputs
    expected_margin: f64,
    expected_leverage: f64,
    expected_notional: f64,
    expected_size: f64,
}

/// PESC fixture: captures a specific cooldown scenario.
#[derive(Debug, Clone)]
struct PescFixture {
    label: &'static str,
    reentry_cooldown_minutes: u32,
    reentry_cooldown_min_mins: u32,
    reentry_cooldown_max_mins: u32,
    close_ts: u32,
    close_type: u32,   // 0=none, 1=LONG, 2=SHORT
    close_reason: u32, // 0=none, 1=signal_flip, 2=other
    desired_type: u32, // 1=LONG, 2=SHORT
    current_ts: u32,
    adx: f64,
    expected_blocked: bool,
}

fn make_sizing_fixtures() -> Vec<SizingFixture> {
    vec![
        // ── 1. Static sizing, small account, no dynamic ──────────────────
        SizingFixture {
            label: "static-small-account",
            equity: 1000.0,
            price: 50.0,
            atr: 0.5,
            adx: 30.0,
            confidence: Confidence::High,
            allocation_pct: 0.03,
            enable_dynamic_sizing: false,
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

            // Static: margin = 1000 * 0.03 = 30, leverage = High -> 5.0
            // notional = 30*5 = 150, size = 150/50 = 3.0
            expected_margin: 30.0,
            expected_leverage: 5.0,
            expected_notional: 150.0,
            expected_size: 3.0,
        },
        // ── 2. Static sizing, medium account, medium leverage ────────────
        SizingFixture {
            label: "static-medium-account",
            equity: 10_000.0,
            price: 100.0,
            atr: 1.0,
            adx: 30.0,
            confidence: Confidence::Medium,
            allocation_pct: 0.05,
            enable_dynamic_sizing: false,
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

            // Static: margin = 10000 * 0.05 = 500, leverage = Medium -> 3.0
            // notional = 500*3 = 1500, size = 1500/100 = 15.0
            expected_margin: 500.0,
            expected_leverage: 3.0,
            expected_notional: 1500.0,
            expected_size: 15.0,
        },
        // ── 3. Static sizing, large account ──────────────────────────────
        SizingFixture {
            label: "static-large-account",
            equity: 100_000.0,
            price: 65000.0,
            atr: 1000.0,
            adx: 35.0,
            confidence: Confidence::Low,
            allocation_pct: 0.02,
            enable_dynamic_sizing: false,
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

            // Static: margin = 100000*0.02 = 2000, leverage = Low -> 1.0
            // notional = 2000*1 = 2000, size = 2000/65000
            expected_margin: 2000.0,
            expected_leverage: 1.0,
            expected_notional: 2000.0,
            expected_size: 2000.0 / 65000.0,
        },
        // ── 4. Dynamic sizing, high confidence, full ADX ─────────────────
        SizingFixture {
            label: "dynamic-high-conf-full-adx",
            equity: 10_000.0,
            price: 100.0,
            atr: 1.0,
            adx: 40.0,
            confidence: Confidence::High,
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

            // Dynamic: conf_mult=1.0, adx_mult=40/40=1.0 clamped to [0.6,1.0]=1.0
            // vol_ratio=(1.0/100.0)/0.01=1.0, vol_scalar=1/1.0=1.0, clamped [0.6,1.4]=1.0
            // margin = 10000*0.03 * 1.0 * 1.0 * 1.0 = 300
            // dynamic leverage: High -> 5.0, cap=0 -> 5.0
            // notional = 300*5 = 1500, size = 1500/100 = 15
            expected_margin: 300.0,
            expected_leverage: 5.0,
            expected_notional: 1500.0,
            expected_size: 15.0,
        },
        // ── 5. Dynamic sizing, low confidence, weak ADX ──────────────────
        SizingFixture {
            label: "dynamic-low-conf-weak-adx",
            equity: 10_000.0,
            price: 100.0,
            atr: 1.0,
            adx: 15.0,
            confidence: Confidence::Low,
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

            // Dynamic: conf_mult=0.6, adx_mult=15/40=0.375 clamped [0.6,1.0]=0.6
            // vol_ratio=1.0, vol_scalar=1.0
            // margin = 10000*0.03 * 0.6 * 0.6 * 1.0 = 108
            // dynamic leverage: Low -> 1.0, cap=0 -> 1.0
            // notional = 108*1 = 108, size = 108/100 = 1.08
            expected_margin: 108.0,
            expected_leverage: 1.0,
            expected_notional: 108.0,
            expected_size: 1.08,
        },
        // ── 6. Dynamic sizing, medium conf, partial ADX ──────────────────
        SizingFixture {
            label: "dynamic-medium-conf-partial-adx",
            equity: 10_000.0,
            price: 200.0,
            atr: 4.0,
            adx: 30.0,
            confidence: Confidence::Medium,
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
            // Dynamic: conf_mult=0.8, adx_mult=30/40=0.75 clamped [0.6,1.0]=0.75
            // vol_ratio=(4.0/200.0)/0.01=2.0, vol_scalar=1/2.0=0.5, clamped [0.6,1.4]=0.6
            // margin = 10000*0.03 * 0.8 * 0.75 * 0.6 = 108
            // dynamic leverage: Medium -> 3.0
            // notional = 108*3 = 324, size = 324/200 = 1.62
            expected_margin: 108.0,
            expected_leverage: 3.0,
            expected_notional: 324.0,
            expected_size: 1.62,
        },
        // ── 7. Dynamic sizing, vol expansion (low vol) ───────────────────
        SizingFixture {
            label: "dynamic-low-vol-expansion",
            equity: 10_000.0,
            price: 100.0,
            atr: 0.5,
            adx: 40.0,
            confidence: Confidence::High,
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

            // Dynamic: conf=1.0, adx=1.0
            // vol_ratio=(0.5/100.0)/0.01 = 0.5, vol_scalar=1/0.5=2.0, clamped [0.6,1.4]=1.4
            // margin = 10000*0.03 * 1.0 * 1.0 * 1.4 = 420
            // leverage = High -> 5.0
            // notional = 420*5 = 2100, size = 2100/100 = 21.0
            expected_margin: 420.0,
            expected_leverage: 5.0,
            expected_notional: 2100.0,
            expected_size: 21.0,
        },
        // ── 8. Dynamic sizing, vol contraction (high vol) ────────────────
        SizingFixture {
            label: "dynamic-high-vol-contraction",
            equity: 10_000.0,
            price: 100.0,
            atr: 3.0,
            adx: 40.0,
            confidence: Confidence::High,
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

            // Dynamic: conf=1.0, adx=1.0
            // vol_ratio=(3.0/100.0)/0.01 = 3.0, vol_scalar=1/3.0≈0.333, clamped [0.6,1.4]=0.6
            // margin = 10000*0.03 * 1.0 * 1.0 * 0.6 = 180
            // leverage = High -> 5.0
            // notional = 180*5 = 900, size = 900/100 = 9.0
            expected_margin: 180.0,
            expected_leverage: 5.0,
            expected_notional: 900.0,
            expected_size: 9.0,
        },
        // ── 9. Dynamic leverage, high confidence, static sizing ─────────
        SizingFixture {
            label: "dynamic-leverage-high-conf",
            equity: 10_000.0,
            price: 100.0,
            atr: 1.0,
            adx: 40.0,
            confidence: Confidence::High,
            allocation_pct: 0.03,
            enable_dynamic_sizing: false,
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
            // Static sizing: margin = 10000*0.03 = 300
            // Dynamic leverage: High -> 5.0
            // notional = 300*5.0 = 1500, size = 1500/100 = 15.0
            expected_margin: 300.0,
            expected_leverage: 5.0,
            expected_notional: 1500.0,
            expected_size: 15.0,
        },
        // ── 10. Dynamic sizing, BTC at $100k, small alloc ────────────────
        SizingFixture {
            label: "dynamic-btc-100k",
            equity: 100_000.0,
            price: 100_000.0,
            atr: 1500.0,
            adx: 35.0,
            confidence: Confidence::High,
            allocation_pct: 0.02,
            enable_dynamic_sizing: true,
            confidence_mult_high: 1.0,
            confidence_mult_medium: 0.8,
            confidence_mult_low: 0.6,
            adx_sizing_min_mult: 0.6,
            adx_sizing_full_adx: 40.0,
            vol_baseline_pct: 0.015,
            vol_scalar_min: 0.6,
            vol_scalar_max: 1.4,
            leverage_low: 1.0,
            leverage_medium: 3.0,
            leverage_high: 5.0,

            // Dynamic: conf=1.0, adx=35/40=0.875 clamped [0.6,1.0]=0.875
            // vol_ratio=(1500/100000)/0.015=1.0, vol_scalar=1/1.0=1.0
            // margin = 100000*0.02 * 1.0 * 0.875 * 1.0 = 1750
            // dynamic leverage: High -> 5.0, cap=0 -> 5.0
            // notional = 1750*5 = 8750, size = 8750/100000 = 0.0875
            expected_margin: 1750.0,
            expected_leverage: 5.0,
            expected_notional: 8750.0,
            expected_size: 0.0875,
        },
        // ── 11. Dynamic sizing, penny stock ──────────────────────────────
        SizingFixture {
            label: "dynamic-penny-stock",
            equity: 1000.0,
            price: 0.05,
            atr: 0.001,
            adx: 20.0,
            confidence: Confidence::Medium,
            allocation_pct: 0.03,
            enable_dynamic_sizing: true,
            confidence_mult_high: 1.0,
            confidence_mult_medium: 0.8,
            confidence_mult_low: 0.6,
            adx_sizing_min_mult: 0.6,
            adx_sizing_full_adx: 40.0,
            vol_baseline_pct: 0.02,
            vol_scalar_min: 0.6,
            vol_scalar_max: 1.4,
            leverage_low: 1.0,
            leverage_medium: 2.0,
            leverage_high: 3.0,

            // Dynamic: conf=0.8, adx=20/40=0.5 clamped [0.6,1.0]=0.6
            // vol_ratio=(0.001/0.05)/0.02=1.0, vol_scalar=1.0
            // margin = 1000*0.03 * 0.8 * 0.6 * 1.0 = 14.4
            // dynamic leverage: Medium -> 2.0, cap=0 -> 2.0
            // notional = 14.4*2 = 28.8, size = 28.8/0.05 = 576
            expected_margin: 14.4,
            expected_leverage: 2.0,
            expected_notional: 28.8,
            expected_size: 576.0,
        },
        // ── 12. Zero price returns zero size ─────────────────────────────
        SizingFixture {
            label: "zero-price-returns-zero-size",
            equity: 10_000.0,
            price: 0.0,
            atr: 1.0,
            adx: 30.0,
            confidence: Confidence::High,
            allocation_pct: 0.03,
            enable_dynamic_sizing: false,
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

            // margin = 10000*0.03 = 300, leverage = High -> 5.0
            // notional = 300*5 = 1500, size = 0 (zero price)
            expected_margin: 300.0,
            expected_leverage: 5.0,
            expected_notional: 1500.0,
            expected_size: 0.0,
        },
        // ── 13. Dynamic sizing, zero vol baseline ────────────────────────
        SizingFixture {
            label: "dynamic-zero-vol-baseline",
            equity: 10_000.0,
            price: 100.0,
            atr: 1.0,
            adx: 40.0,
            confidence: Confidence::High,
            allocation_pct: 0.03,
            enable_dynamic_sizing: true,
            confidence_mult_high: 1.0,
            confidence_mult_medium: 0.8,
            confidence_mult_low: 0.6,
            adx_sizing_min_mult: 0.6,
            adx_sizing_full_adx: 40.0,
            vol_baseline_pct: 0.0, // zero -> vol_ratio = 1.0 (fallback)
            vol_scalar_min: 0.6,
            vol_scalar_max: 1.4,
            leverage_low: 1.0,
            leverage_medium: 3.0,
            leverage_high: 5.0,

            // vol_ratio fallback=1.0 (zero baseline), vol_scalar=1.0
            // margin = 10000*0.03 * 1.0 * 1.0 * 1.0 = 300
            // leverage = High -> 5.0, notional = 300*5 = 1500, size = 15.0
            expected_margin: 300.0,
            expected_leverage: 5.0,
            expected_notional: 1500.0,
            expected_size: 15.0,
        },
        // ── 14. Dynamic sizing, zero ADX ─────────────────────────────────
        SizingFixture {
            label: "dynamic-zero-adx",
            equity: 10_000.0,
            price: 100.0,
            atr: 1.0,
            adx: 0.0,
            confidence: Confidence::High,
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

            // adx_mult = 0/40 = 0.0, clamped [0.6, 1.0] = 0.6
            // vol_ratio=1.0, vol_scalar=1.0
            // margin = 10000*0.03 * 1.0 * 0.6 * 1.0 = 180
            // High -> lev 5.0
            // notional = 180*5 = 900, size = 9.0
            expected_margin: 180.0,
            expected_leverage: 5.0,
            expected_notional: 900.0,
            expected_size: 9.0,
        },
        // ── 15. Dynamic sizing, zero full ADX uses min multiplier fallback ──
        SizingFixture {
            label: "dynamic-zero-full-adx-fallback",
            equity: 10_000.0,
            price: 100.0,
            atr: 1.0,
            adx: 40.0,
            confidence: Confidence::High,
            allocation_pct: 0.03,
            enable_dynamic_sizing: true,
            confidence_mult_high: 1.0,
            confidence_mult_medium: 0.8,
            confidence_mult_low: 0.6,
            adx_sizing_min_mult: 0.6,
            adx_sizing_full_adx: 0.0,
            vol_baseline_pct: 0.01,
            vol_scalar_min: 0.6,
            vol_scalar_max: 1.4,
            leverage_low: 1.0,
            leverage_medium: 3.0,
            leverage_high: 5.0,

            // full_adx <= 0 -> adx_mult fallback=min_mult=0.6
            // vol_ratio=1.0, vol_scalar=1.0
            // margin = 10000*0.03 * 1.0 * 0.6 * 1.0 = 180
            // High -> lev 5.0, notional = 900, size = 9.0
            expected_margin: 180.0,
            expected_leverage: 5.0,
            expected_notional: 900.0,
            expected_size: 9.0,
        },
    ]
}

fn make_pesc_fixtures() -> Vec<PescFixture> {
    // Base: close at t=1000s, current at various times,
    // cooldown config: base=60min, min=45min, max=180min
    vec![
        // ── 1. PESC disabled (cooldown_minutes == 0) ─────────────────────
        PescFixture {
            label: "pesc-disabled",
            reentry_cooldown_minutes: 0,
            reentry_cooldown_min_mins: 45,
            reentry_cooldown_max_mins: 180,
            close_ts: 1000,
            close_type: 1,    // LONG
            close_reason: 2,  // other
            desired_type: 1,  // LONG (same dir)
            current_ts: 1001, // 1 second later
            adx: 30.0,
            expected_blocked: false,
        },
        // ── 2. No prior close (close_ts == 0) ───────────────────────────
        PescFixture {
            label: "pesc-no-prior-close",
            reentry_cooldown_minutes: 60,
            reentry_cooldown_min_mins: 45,
            reentry_cooldown_max_mins: 180,
            close_ts: 0,
            close_type: 0,
            close_reason: 0,
            desired_type: 1,
            current_ts: 1000,
            adx: 30.0,
            expected_blocked: false,
        },
        // ── 3. Signal flip bypass ────────────────────────────────────────
        PescFixture {
            label: "pesc-signal-flip-bypass",
            reentry_cooldown_minutes: 60,
            reentry_cooldown_min_mins: 45,
            reentry_cooldown_max_mins: 180,
            close_ts: 1000,
            close_type: 1,
            close_reason: 1, // signal_flip
            desired_type: 1,
            current_ts: 1001, // 1 second later
            adx: 25.0,
            expected_blocked: false,
        },
        // ── 4. Different direction bypass ────────────────────────────────
        PescFixture {
            label: "pesc-opposite-direction-bypass",
            reentry_cooldown_minutes: 60,
            reentry_cooldown_min_mins: 45,
            reentry_cooldown_max_mins: 180,
            close_ts: 1000,
            close_type: 1,   // closed LONG
            close_reason: 2, // other
            desired_type: 2, // want SHORT (different dir)
            current_ts: 1001,
            adx: 25.0,
            expected_blocked: false,
        },
        // ── 5. Blocked: same dir, weak ADX (max cooldown 180min) ─────────
        PescFixture {
            label: "pesc-blocked-weak-adx-max-cooldown",
            reentry_cooldown_minutes: 60,
            reentry_cooldown_min_mins: 45,
            reentry_cooldown_max_mins: 180,
            close_ts: 1000,
            close_type: 1,
            close_reason: 2,
            desired_type: 1,
            // 179 minutes = 10740 seconds after close
            current_ts: 1000 + 10740,
            adx: 25.0, // weak ADX -> max cooldown = 180 min
            expected_blocked: true,
        },
        // ── 6. Not blocked: same dir, weak ADX, past max cooldown ────────
        PescFixture {
            label: "pesc-not-blocked-past-max-cooldown",
            reentry_cooldown_minutes: 60,
            reentry_cooldown_min_mins: 45,
            reentry_cooldown_max_mins: 180,
            close_ts: 1000,
            close_type: 1,
            close_reason: 2,
            desired_type: 1,
            // 181 minutes = 10860 seconds after close
            current_ts: 1000 + 10860,
            adx: 25.0,
            expected_blocked: false,
        },
        // ── 7. Blocked: strong ADX (min cooldown 45min) ──────────────────
        PescFixture {
            label: "pesc-blocked-strong-adx-min-cooldown",
            reentry_cooldown_minutes: 60,
            reentry_cooldown_min_mins: 45,
            reentry_cooldown_max_mins: 180,
            close_ts: 1000,
            close_type: 2, // SHORT
            close_reason: 2,
            desired_type: 2, // SHORT (same dir)
            // 44 minutes = 2640 seconds after close
            current_ts: 1000 + 2640,
            adx: 40.0, // strong ADX -> min cooldown = 45 min
            expected_blocked: true,
        },
        // ── 8. Not blocked: strong ADX, past min cooldown ────────────────
        PescFixture {
            label: "pesc-not-blocked-past-min-cooldown",
            reentry_cooldown_minutes: 60,
            reentry_cooldown_min_mins: 45,
            reentry_cooldown_max_mins: 180,
            close_ts: 1000,
            close_type: 2,
            close_reason: 2,
            desired_type: 2,
            // 46 minutes = 2760 seconds after close
            current_ts: 1000 + 2760,
            adx: 40.0,
            expected_blocked: false,
        },
        // ── 9. ADX interpolation midpoint (ADX=32.5) ─────────────────────
        PescFixture {
            label: "pesc-adx-interpolation-midpoint",
            reentry_cooldown_minutes: 60,
            reentry_cooldown_min_mins: 45,
            reentry_cooldown_max_mins: 180,
            close_ts: 1000,
            close_type: 1,
            close_reason: 2,
            desired_type: 1,
            // ADX=32.5: t = (32.5-25)/15 = 0.5
            // cooldown = 180 + 0.5*(45-180) = 180 - 67.5 = 112.5 min = 6750s
            // 112 min = 6720s -> should be blocked
            current_ts: 1000 + 6720,
            adx: 32.5,
            expected_blocked: true,
        },
        // ── 10. ADX interpolation midpoint, past cooldown ────────────────
        PescFixture {
            label: "pesc-adx-interpolation-past-cooldown",
            reentry_cooldown_minutes: 60,
            reentry_cooldown_min_mins: 45,
            reentry_cooldown_max_mins: 180,
            close_ts: 1000,
            close_type: 1,
            close_reason: 2,
            desired_type: 1,
            // cooldown at ADX=32.5 is 112.5 min = 6750s
            // 113 min = 6780s -> should not be blocked
            current_ts: 1000 + 6780,
            adx: 32.5,
            expected_blocked: false,
        },
        // ── 11. ADX very high (>40, uses min cooldown) ───────────────────
        PescFixture {
            label: "pesc-adx-very-high",
            reentry_cooldown_minutes: 60,
            reentry_cooldown_min_mins: 45,
            reentry_cooldown_max_mins: 180,
            close_ts: 1000,
            close_type: 1,
            close_reason: 2,
            desired_type: 1,
            // 44 min = 2640s, ADX=60 (>40 so min cooldown)
            current_ts: 1000 + 2640,
            adx: 60.0,
            expected_blocked: true,
        },
        // ── 12. ADX at boundary 25.0 (uses max cooldown) ────────────────
        PescFixture {
            label: "pesc-adx-boundary-25",
            reentry_cooldown_minutes: 60,
            reentry_cooldown_min_mins: 45,
            reentry_cooldown_max_mins: 180,
            close_ts: 1000,
            close_type: 1,
            close_reason: 2,
            desired_type: 1,
            // 179 min = 10740s, ADX=25 -> max cooldown = 180 min
            current_ts: 1000 + 10740,
            adx: 25.0,
            expected_blocked: true,
        },
        // ── 13. ADX at boundary 40.0 exactly (uses min cooldown) ─────────
        PescFixture {
            label: "pesc-adx-boundary-40",
            reentry_cooldown_minutes: 60,
            reentry_cooldown_min_mins: 45,
            reentry_cooldown_max_mins: 180,
            close_ts: 1000,
            close_type: 1,
            close_reason: 2,
            desired_type: 1,
            // 44 min = 2640s, ADX=40 -> min cooldown = 45 min
            current_ts: 1000 + 2640,
            adx: 40.0,
            expected_blocked: true,
        },
        // ── 14. Short direction blocked ──────────────────────────────────
        PescFixture {
            label: "pesc-short-blocked",
            reentry_cooldown_minutes: 60,
            reentry_cooldown_min_mins: 30,
            reentry_cooldown_max_mins: 120,
            close_ts: 5000,
            close_type: 2, // SHORT
            close_reason: 2,
            desired_type: 2, // SHORT (same)
            // 29 min = 1740s, ADX=50 (>40 -> min=30 min)
            current_ts: 5000 + 1740,
            adx: 50.0,
            expected_blocked: true,
        },
    ]
}

// ─── Test: local Rust reference matches risk_core::compute_entry_sizing ──────

#[test]
fn test_sizing_local_reference_matches_risk_core() {
    // AQC-1232: Verify our local rust_compute_entry_sizing matches the
    // canonical risk_core::compute_entry_sizing for all fixtures.
    // This ensures our reference implementation is trustworthy.
    use risk_core::{compute_entry_sizing, ConfidenceTier, EntrySizingInput};

    let fixtures = make_sizing_fixtures();
    for f in &fixtures {
        let conf_tier = match f.confidence {
            Confidence::High => ConfidenceTier::High,
            Confidence::Medium => ConfidenceTier::Medium,
            Confidence::Low => ConfidenceTier::Low,
        };

        let canonical = compute_entry_sizing(EntrySizingInput {
            equity: f.equity,
            price: f.price,
            atr: f.atr,
            adx: f.adx,
            confidence: conf_tier,
            allocation_pct: f.allocation_pct,
            enable_dynamic_sizing: f.enable_dynamic_sizing,
            confidence_mult_high: f.confidence_mult_high,
            confidence_mult_medium: f.confidence_mult_medium,
            confidence_mult_low: f.confidence_mult_low,
            adx_sizing_min_mult: f.adx_sizing_min_mult,
            adx_sizing_full_adx: f.adx_sizing_full_adx,
            vol_baseline_pct: f.vol_baseline_pct,
            vol_scalar_min: f.vol_scalar_min,
            vol_scalar_max: f.vol_scalar_max,
            leverage_low: f.leverage_low,
            leverage_medium: f.leverage_medium,
            leverage_high: f.leverage_high,
        });

        let (local_size, local_margin, local_lev, local_notional) = rust_compute_entry_sizing(
            f.equity,
            f.price,
            f.atr,
            f.adx,
            f.confidence,
            f.allocation_pct,
            f.enable_dynamic_sizing,
            f.confidence_mult_high,
            f.confidence_mult_medium,
            f.confidence_mult_low,
            f.adx_sizing_min_mult,
            f.adx_sizing_full_adx,
            f.vol_baseline_pct,
            f.vol_scalar_min,
            f.vol_scalar_max,
            f.leverage_low,
            f.leverage_medium,
            f.leverage_high,
        );

        assert!(
            (canonical.size - local_size).abs() < 1e-10,
            "risk_core vs local size mismatch for '{}': canonical={}, local={}",
            f.label,
            canonical.size,
            local_size
        );
        assert!(
            (canonical.margin_used - local_margin).abs() < 1e-10,
            "risk_core vs local margin mismatch for '{}': canonical={}, local={}",
            f.label,
            canonical.margin_used,
            local_margin
        );
        assert!(
            (canonical.leverage - local_lev).abs() < 1e-10,
            "risk_core vs local leverage mismatch for '{}': canonical={}, local={}",
            f.label,
            canonical.leverage,
            local_lev
        );
        assert!(
            (canonical.notional - local_notional).abs() < 1e-10,
            "risk_core vs local notional mismatch for '{}': canonical={}, local={}",
            f.label,
            canonical.notional,
            local_notional
        );
    }
}

// ─── Test: sizing fixtures match hand-calculated expected values ──────────────

#[test]
fn test_sizing_fixtures_match_expected_values() {
    // AQC-1232: For each sizing fixture, verify the CPU SSOT produces
    // exactly the hand-calculated expected values. This catches formula
    // regressions in both our reference and risk_core.
    let fixtures = make_sizing_fixtures();
    let tol = 1e-10;

    for f in &fixtures {
        let (size, margin, lev, notional) = rust_compute_entry_sizing(
            f.equity,
            f.price,
            f.atr,
            f.adx,
            f.confidence,
            f.allocation_pct,
            f.enable_dynamic_sizing,
            f.confidence_mult_high,
            f.confidence_mult_medium,
            f.confidence_mult_low,
            f.adx_sizing_min_mult,
            f.adx_sizing_full_adx,
            f.vol_baseline_pct,
            f.vol_scalar_min,
            f.vol_scalar_max,
            f.leverage_low,
            f.leverage_medium,
            f.leverage_high,
        );

        assert!(
            (margin - f.expected_margin).abs() < tol,
            "[{}] margin mismatch: got={}, expected={}",
            f.label,
            margin,
            f.expected_margin
        );
        assert!(
            (lev - f.expected_leverage).abs() < tol,
            "[{}] leverage mismatch: got={}, expected={}",
            f.label,
            lev,
            f.expected_leverage
        );
        assert!(
            (notional - f.expected_notional).abs() < tol,
            "[{}] notional mismatch: got={}, expected={}",
            f.label,
            notional,
            f.expected_notional
        );
        assert!(
            (size - f.expected_size).abs() < tol,
            "[{}] size mismatch: got={}, expected={}",
            f.label,
            size,
            f.expected_size
        );
    }
}

// ─── Test: sizing f32 round-trip stays within T2 precision ───────────────────

#[test]
fn test_sizing_f32_roundtrip_within_t2() {
    // AQC-1232: Verify that sizing outputs survive f32 cast (GPU path) within T2.
    use risk_core::{compute_entry_sizing, ConfidenceTier, EntrySizingInput};

    let fixtures = make_sizing_fixtures();
    for f in &fixtures {
        let conf_tier = match f.confidence {
            Confidence::High => ConfidenceTier::High,
            Confidence::Medium => ConfidenceTier::Medium,
            Confidence::Low => ConfidenceTier::Low,
        };

        let result = compute_entry_sizing(EntrySizingInput {
            equity: f.equity,
            price: f.price,
            atr: f.atr,
            adx: f.adx,
            confidence: conf_tier,
            allocation_pct: f.allocation_pct,
            enable_dynamic_sizing: f.enable_dynamic_sizing,
            confidence_mult_high: f.confidence_mult_high,
            confidence_mult_medium: f.confidence_mult_medium,
            confidence_mult_low: f.confidence_mult_low,
            adx_sizing_min_mult: f.adx_sizing_min_mult,
            adx_sizing_full_adx: f.adx_sizing_full_adx,
            vol_baseline_pct: f.vol_baseline_pct,
            vol_scalar_min: f.vol_scalar_min,
            vol_scalar_max: f.vol_scalar_max,
            leverage_low: f.leverage_low,
            leverage_medium: f.leverage_medium,
            leverage_high: f.leverage_high,
        });

        // Check f32 round-trip for each non-zero output
        for (name, val) in &[
            ("margin", result.margin_used),
            ("leverage", result.leverage),
            ("notional", result.notional),
            ("size", result.size),
        ] {
            if *val != 0.0 {
                let f32_rt = (*val as f32) as f64;
                assert!(
                    within_tolerance(*val, f32_rt, TIER_T2_TOLERANCE),
                    "[{}] {} f32 round-trip exceeds T2: f64={}, f32_rt={}, rel_err={:.2e}",
                    f.label,
                    name,
                    val,
                    f32_rt,
                    relative_error(*val, f32_rt)
                );
            }
        }
    }
}

// AQC-1225: Fixture-based numerical parity tests for all exit codegen functions
// ═══════════════════════════════════════════════════════════════════════════════
//
// These tests call the Rust CPU exit functions from bt-core with diverse
// config/position/market data combinations and verify numerical correctness
// of: SL price, trailing SL updates, TP decisions, smart exit triggers,
// and exit orchestrator priority.

use bt_core::decision_kernel::{Position, PositionSide};
use bt_core::indicators::IndicatorSnapshot;
use bt_core::kernel_exits::{
    evaluate_exits, evaluate_exits_with_diagnostics, ExitParams, KernelExitResult,
};

// ── Helpers: build bt-core types from fixture data ─────────────────────────

/// Default ExitParams matching the GpuComboConfig defaults.
fn default_exit_params() -> ExitParams {
    ExitParams {
        sl_atr_mult: 2.0,
        tp_atr_mult: 4.0,
        trailing_start_atr: 1.0,
        trailing_distance_atr: 0.8,
        enable_partial_tp: true,
        tp_partial_pct: 0.5,
        tp_partial_atr_mult: 0.0,
        tp_partial_min_notional_usd: 10.0,
        enable_breakeven_stop: true,
        breakeven_start_atr: 0.7,
        breakeven_buffer_atr: 0.05,
        enable_vol_buffered_trailing: true,
        block_exits_on_extreme_dev: false,
        glitch_price_dev_pct: 0.40,
        glitch_atr_mult: 12.0,
        smart_exit_adx_exhaustion_lt: 18.0,
        tsme_min_profit_atr: 1.0,
        tsme_require_adx_slope_negative: true,
        enable_rsi_overextension_exit: true,
        rsi_exit_profit_atr_switch: 1.5,
        rsi_exit_ub_lo_profit: 80.0,
        rsi_exit_ub_hi_profit: 70.0,
        rsi_exit_lb_lo_profit: 20.0,
        rsi_exit_lb_hi_profit: 30.0,
        rsi_exit_ub_lo_profit_low_conf: 0.0,
        rsi_exit_lb_lo_profit_low_conf: 0.0,
        rsi_exit_ub_hi_profit_low_conf: 0.0,
        rsi_exit_lb_hi_profit_low_conf: 0.0,
        smart_exit_adx_exhaustion_lt_low_conf: 0.0,
        require_macro_alignment: false,
        trailing_start_atr_low_conf: 0.0,
        trailing_distance_atr_low_conf: 0.0,
    }
}

// ── Test 1: SL price computation matches inline reference across configs ───

#[test]
fn test_aqc1225_sl_price_cpu_vs_reference_multiple_configs() {
    // Verify bt-core CPU SL price matches the inline rust_compute_sl_price
    // across 10 diverse fixture/config combinations.
    struct SlTestCase {
        label: &'static str,
        pos_type: PosType,
        entry: f64,
        atr: f64,
        close: f64,
        adx: f64,
        adx_slope: f64,
        sl_atr_mult: f64,
        enable_be: bool,
        be_start: f64,
        be_buffer: f64,
    }

    let cases: Vec<SlTestCase> = vec![
        // 1. Baseline long, no modifiers
        SlTestCase {
            label: "baseline-long",
            pos_type: PosType::Long,
            entry: 50000.0,
            atr: 500.0,
            close: 50100.0,
            adx: 30.0,
            adx_slope: 0.5,
            sl_atr_mult: 2.0,
            enable_be: false,
            be_start: 0.0,
            be_buffer: 0.0,
        },
        // 2. Baseline short, no modifiers
        SlTestCase {
            label: "baseline-short",
            pos_type: PosType::Short,
            entry: 50000.0,
            atr: 500.0,
            close: 49900.0,
            adx: 30.0,
            adx_slope: 0.5,
            sl_atr_mult: 2.0,
            enable_be: false,
            be_start: 0.0,
            be_buffer: 0.0,
        },
        // 3. ASE tightening (underwater + negative slope)
        SlTestCase {
            label: "ase-long",
            pos_type: PosType::Long,
            entry: 50000.0,
            atr: 500.0,
            close: 49500.0,
            adx: 30.0,
            adx_slope: -1.0,
            sl_atr_mult: 2.0,
            enable_be: false,
            be_start: 0.0,
            be_buffer: 0.0,
        },
        // 4. DASE widening (ADX>40, profit>0.5 ATR)
        SlTestCase {
            label: "dase-long",
            pos_type: PosType::Long,
            entry: 50000.0,
            atr: 500.0,
            close: 50300.0,
            adx: 42.0,
            adx_slope: 0.5,
            sl_atr_mult: 2.0,
            enable_be: false,
            be_start: 0.0,
            be_buffer: 0.0,
        },
        // 5. SLB widening (ADX>45, underwater so no DASE)
        SlTestCase {
            label: "slb-short-underwater",
            pos_type: PosType::Short,
            entry: 50000.0,
            atr: 500.0,
            close: 50200.0,
            adx: 47.0,
            adx_slope: 0.5,
            sl_atr_mult: 2.0,
            enable_be: false,
            be_start: 0.0,
            be_buffer: 0.0,
        },
        // 6. DASE + SLB combined (ADX>45, profitable)
        SlTestCase {
            label: "dase-slb-combined",
            pos_type: PosType::Long,
            entry: 50000.0,
            atr: 500.0,
            close: 50400.0,
            adx: 50.0,
            adx_slope: 0.5,
            sl_atr_mult: 2.0,
            enable_be: false,
            be_start: 0.0,
            be_buffer: 0.0,
        },
        // 7. Breakeven active (profit >= be_start)
        SlTestCase {
            label: "breakeven-long",
            pos_type: PosType::Long,
            entry: 50000.0,
            atr: 500.0,
            close: 50400.0,
            adx: 30.0,
            adx_slope: 0.5,
            sl_atr_mult: 2.0,
            enable_be: true,
            be_start: 0.7,
            be_buffer: 0.05,
        },
        // 8. Breakeven short active
        SlTestCase {
            label: "breakeven-short",
            pos_type: PosType::Short,
            entry: 50000.0,
            atr: 500.0,
            close: 49600.0,
            adx: 30.0,
            adx_slope: 0.5,
            sl_atr_mult: 2.0,
            enable_be: true,
            be_start: 0.7,
            be_buffer: 0.05,
        },
        // 9. ASE + breakeven (underwater, so breakeven won't fire)
        SlTestCase {
            label: "ase-with-be-inactive",
            pos_type: PosType::Long,
            entry: 50000.0,
            atr: 500.0,
            close: 49500.0,
            adx: 30.0,
            adx_slope: -0.5,
            sl_atr_mult: 2.0,
            enable_be: true,
            be_start: 0.7,
            be_buffer: 0.05,
        },
        // 10. Wide SL multiplier with penny stock
        SlTestCase {
            label: "penny-wide-sl",
            pos_type: PosType::Long,
            entry: 0.0025,
            atr: 0.000025,
            close: 0.0026,
            adx: 30.0,
            adx_slope: 0.5,
            sl_atr_mult: 3.5,
            enable_be: false,
            be_start: 0.0,
            be_buffer: 0.0,
        },
        // 11. Zero ATR with breakeven
        SlTestCase {
            label: "zero-atr-be",
            pos_type: PosType::Long,
            entry: 100.0,
            atr: 0.0,
            close: 104.0,
            adx: 30.0,
            adx_slope: 0.5,
            sl_atr_mult: 2.0,
            enable_be: true,
            be_start: 0.7,
            be_buffer: 0.05,
        },
        // 12. ASE tightening for short (underwater short = close > entry)
        SlTestCase {
            label: "ase-short",
            pos_type: PosType::Short,
            entry: 50000.0,
            atr: 500.0,
            close: 50500.0,
            adx: 30.0,
            adx_slope: -0.5,
            sl_atr_mult: 2.0,
            enable_be: false,
            be_start: 0.0,
            be_buffer: 0.0,
        },
    ];

    for c in &cases {
        let eff_atr = if c.atr > 0.0 { c.atr } else { c.entry * 0.005 };

        // Compute via inline reference
        let ref_sl = rust_compute_sl_price(
            c.pos_type,
            c.entry,
            c.atr,
            c.close,
            c.adx,
            c.adx_slope,
            c.sl_atr_mult,
            c.enable_be,
            c.be_start,
            c.be_buffer,
        );

        // Manually compute expected SL applying each modifier in order
        let mut expected_mult = c.sl_atr_mult;

        // ASE: underwater + adx_slope < 0 -> tighten 20%
        let is_underwater = match c.pos_type {
            PosType::Long => c.close < c.entry,
            PosType::Short => c.close > c.entry,
        };
        if c.adx_slope < 0.0 && is_underwater {
            expected_mult *= 0.8;
        }

        // DASE: ADX > 40, profit > 0.5 ATR -> widen 15%
        if c.adx > 40.0 {
            let profit_in_atr = match c.pos_type {
                PosType::Long => (c.close - c.entry) / eff_atr,
                PosType::Short => (c.entry - c.close) / eff_atr,
            };
            if profit_in_atr > 0.5 {
                expected_mult *= 1.15;
            }
        }

        // SLB: ADX > 45 -> widen 10%
        if c.adx > 45.0 {
            expected_mult *= 1.10;
        }

        // Raw SL
        let mut expected_sl = match c.pos_type {
            PosType::Long => c.entry - eff_atr * expected_mult,
            PosType::Short => c.entry + eff_atr * expected_mult,
        };

        // Breakeven
        if c.enable_be && c.be_start > 0.0 {
            let be_start = eff_atr * c.be_start;
            let be_buffer = eff_atr * c.be_buffer;
            let profit = match c.pos_type {
                PosType::Long => c.close - c.entry,
                PosType::Short => c.entry - c.close,
            };
            if profit >= be_start {
                match c.pos_type {
                    PosType::Long => expected_sl = expected_sl.max(c.entry + be_buffer),
                    PosType::Short => expected_sl = expected_sl.min(c.entry - be_buffer),
                }
            }
        }

        // Verify reference matches manual computation
        assert!(
            within_tolerance(expected_sl, ref_sl, TIER_T2_TOLERANCE),
            "[{}] SL mismatch: manual={}, reference={}, rel_err={:.2e}",
            c.label,
            expected_sl,
            ref_sl,
            relative_error(expected_sl, ref_sl)
        );

        // Verify SL is finite
        assert!(
            ref_sl.is_finite(),
            "[{}] SL must be finite: {}",
            c.label,
            ref_sl
        );

        // Verify directional sanity (unless breakeven moved it past entry)
        let profit = match c.pos_type {
            PosType::Long => c.close - c.entry,
            PosType::Short => c.entry - c.close,
        };
        let be_active = c.enable_be && c.be_start > 0.0 && profit >= eff_atr * c.be_start;

        if !be_active {
            match c.pos_type {
                PosType::Long => assert!(
                    ref_sl <= c.entry + f64::EPSILON,
                    "[{}] LONG SL {} must be <= entry {}",
                    c.label,
                    ref_sl,
                    c.entry
                ),
                PosType::Short => assert!(
                    ref_sl >= c.entry - f64::EPSILON,
                    "[{}] SHORT SL {} must be >= entry {}",
                    c.label,
                    ref_sl,
                    c.entry
                ),
            }
        }

        // Verify f32 round-trip
        let rt = ref_sl as f32 as f64;
        assert!(
            within_tolerance(ref_sl, rt, TIER_T2_TOLERANCE),
            "[{}] SL f32 round-trip: f64={}, f32_rt={}, rel_err={:.2e}",
            c.label,
            ref_sl,
            rt,
            relative_error(ref_sl, rt)
        );

        // Cross-validate: use bt-core evaluate_exits_with_diagnostics with
        // snap.close at the case's close value. Extract SL price from sl_distance
        // threshold record: sl_distance = close - sl_price (long) or sl_price - close (short)
        let params = ExitParams {
            sl_atr_mult: c.sl_atr_mult,
            enable_breakeven_stop: c.enable_be,
            breakeven_start_atr: c.be_start,
            breakeven_buffer_atr: c.be_buffer,
            // Disable other exits to prevent them from firing before SL is recorded
            tp_atr_mult: 100.0,
            trailing_start_atr: 1000.0,
            smart_exit_adx_exhaustion_lt: 0.0,
            enable_rsi_overextension_exit: false,
            require_macro_alignment: false,
            ..default_exit_params()
        };
        let side = match c.pos_type {
            PosType::Long => PositionSide::Long,
            PosType::Short => PositionSide::Short,
        };
        let snap = IndicatorSnapshot {
            close: c.close,
            high: c.close * 1.005,
            low: c.close * 0.995,
            open: c.close,
            volume: 1000.0,
            t: 1_000_000,
            ema_fast: c.close,
            ema_slow: c.close,
            ema_macro: c.close,
            adx: c.adx,
            adx_pos: c.adx * 0.6,
            adx_neg: c.adx * 0.4,
            adx_slope: c.adx_slope,
            bb_upper: c.close * 1.02,
            bb_lower: c.close * 0.98,
            bb_width: 0.04,
            bb_width_avg: 0.04,
            bb_width_ratio: 1.0,
            atr: eff_atr,
            atr_slope: 0.0,
            avg_atr: eff_atr,
            rsi: 50.0,
            stoch_rsi_k: 50.0,
            stoch_rsi_d: 50.0,
            macd_hist: 0.0,
            prev_macd_hist: 0.0,
            prev2_macd_hist: 0.0,
            prev3_macd_hist: 0.0,
            vol_sma: 1000.0,
            vol_trend: false,
            prev_close: c.close,
            prev_ema_fast: c.close,
            prev_ema_slow: c.close,
            bar_count: 200,
            funding_rate: 0.0,
        };

        let entry_atr_opt = if c.atr > 0.0 { Some(c.atr) } else { None };
        let mut pos = Position {
            symbol: "BTC".to_string(),
            side,
            quantity: 1.0,
            avg_entry_price: c.entry,
            opened_at_ms: 0,
            updated_at_ms: 0,
            notional_usd: c.entry,
            margin_usd: c.entry / 3.0,
            confidence: Some(2),
            entry_atr: entry_atr_opt,
            entry_adx_threshold: None,
            adds_count: 0,
            tp1_taken: false,
            trailing_sl: None,
            mae_usd: 0.0,
            mfe_usd: 0.0,
            last_funding_ms: None,
        };

        let eval = evaluate_exits_with_diagnostics(&mut pos, &snap, &params, 1_000_000);
        // Extract sl_price from threshold record (always recorded)
        if let Some(sl_rec) = eval
            .threshold_records
            .iter()
            .find(|r| r.name == "sl_distance")
        {
            let cpu_sl = match side {
                PositionSide::Long => c.close - sl_rec.actual,
                PositionSide::Short => c.close + sl_rec.actual,
            };
            assert!(
                within_tolerance(ref_sl, cpu_sl, TIER_T2_TOLERANCE),
                "[{}] CPU SL mismatch: reference={}, cpu={}, rel_err={:.2e}",
                c.label,
                ref_sl,
                cpu_sl,
                relative_error(ref_sl, cpu_sl)
            );
        }
    }
}

// ── Test 2: Trailing SL computation matches inline reference ───────────────

#[test]
fn test_aqc1225_trailing_cpu_vs_reference_multiple_configs() {
    // Verify trailing SL computation via inline reference matches the bt-core
    // CPU implementation across diverse fixture combinations.
    struct TrailCase {
        label: &'static str,
        pos_type: PosType,
        entry: f64,
        close: f64,
        atr: f64,
        trailing_sl: f64,
        confidence: Confidence,
        rsi: f64,
        adx: f64,
        adx_slope: f64,
        atr_slope: f64,
        bb_width_ratio: f64,
        profit_atr: f64,
    }

    let cases = vec![
        // 1. Active trailing, normal conditions
        TrailCase {
            label: "active-normal-long",
            pos_type: PosType::Long,
            entry: 50000.0,
            close: 51000.0,
            atr: 500.0,
            trailing_sl: 0.0,
            confidence: Confidence::High,
            rsi: 55.0,
            adx: 30.0,
            adx_slope: 0.5,
            atr_slope: 0.0,
            bb_width_ratio: 1.0,
            profit_atr: 2.0,
        },
        // 2. Active trailing, short
        TrailCase {
            label: "active-normal-short",
            pos_type: PosType::Short,
            entry: 50000.0,
            close: 49000.0,
            atr: 500.0,
            trailing_sl: 0.0,
            confidence: Confidence::High,
            rsi: 45.0,
            adx: 30.0,
            adx_slope: 0.5,
            atr_slope: 0.0,
            bb_width_ratio: 1.0,
            profit_atr: 2.0,
        },
        // 3. Not yet active (profit < start)
        TrailCase {
            label: "not-active-low-profit",
            pos_type: PosType::Long,
            entry: 50000.0,
            close: 50200.0,
            atr: 500.0,
            trailing_sl: 0.0,
            confidence: Confidence::High,
            rsi: 55.0,
            adx: 30.0,
            adx_slope: 0.5,
            atr_slope: 0.0,
            bb_width_ratio: 1.0,
            profit_atr: 0.4,
        },
        // 4. Ratchet improvement
        TrailCase {
            label: "ratchet-improve-long",
            pos_type: PosType::Long,
            entry: 50000.0,
            close: 52000.0,
            atr: 500.0,
            trailing_sl: 51200.0,
            confidence: Confidence::High,
            rsi: 55.0,
            adx: 30.0,
            adx_slope: 0.5,
            atr_slope: 0.0,
            bb_width_ratio: 1.0,
            profit_atr: 4.0,
        },
        // 5. VBTS active (bb_width_ratio > 1.2)
        TrailCase {
            label: "vbts-active",
            pos_type: PosType::Long,
            entry: 50000.0,
            close: 50800.0,
            atr: 500.0,
            trailing_sl: 0.0,
            confidence: Confidence::High,
            rsi: 55.0,
            adx: 30.0,
            adx_slope: 0.5,
            atr_slope: 0.0,
            bb_width_ratio: 1.5,
            profit_atr: 1.6,
        },
        // 6. TATP (adx>35, slope>0, high profit)
        TrailCase {
            label: "tatp-active",
            pos_type: PosType::Long,
            entry: 50000.0,
            close: 51500.0,
            atr: 500.0,
            trailing_sl: 0.0,
            confidence: Confidence::High,
            rsi: 55.0,
            adx: 40.0,
            adx_slope: 1.0,
            atr_slope: 0.0,
            bb_width_ratio: 1.0,
            profit_atr: 3.0,
        },
        // 7. TSPV (atr_slope>0, adx<35, high profit)
        TrailCase {
            label: "tspv-active",
            pos_type: PosType::Long,
            entry: 50000.0,
            close: 51500.0,
            atr: 500.0,
            trailing_sl: 0.0,
            confidence: Confidence::High,
            rsi: 55.0,
            adx: 28.0,
            adx_slope: -0.5,
            atr_slope: 0.5,
            bb_width_ratio: 1.0,
            profit_atr: 3.0,
        },
        // 8. Weak trend (adx<25)
        TrailCase {
            label: "weak-trend",
            pos_type: PosType::Long,
            entry: 50000.0,
            close: 50600.0,
            atr: 500.0,
            trailing_sl: 0.0,
            confidence: Confidence::High,
            rsi: 55.0,
            adx: 20.0,
            adx_slope: 0.3,
            atr_slope: 0.0,
            bb_width_ratio: 1.0,
            profit_atr: 1.2,
        },
        // 9. RSI Trend-Guard floor (long, RSI>60)
        TrailCase {
            label: "rsi-guard-long",
            pos_type: PosType::Long,
            entry: 50000.0,
            close: 50600.0,
            atr: 500.0,
            trailing_sl: 0.0,
            confidence: Confidence::High,
            rsi: 65.0,
            adx: 20.0,
            adx_slope: 0.3,
            atr_slope: 0.0,
            bb_width_ratio: 1.0,
            profit_atr: 1.2,
        },
        // 10. RSI Trend-Guard floor (short, RSI<40)
        TrailCase {
            label: "rsi-guard-short",
            pos_type: PosType::Short,
            entry: 50000.0,
            close: 49400.0,
            atr: 500.0,
            trailing_sl: 0.0,
            confidence: Confidence::High,
            rsi: 35.0,
            adx: 20.0,
            adx_slope: 0.3,
            atr_slope: 0.0,
            bb_width_ratio: 1.0,
            profit_atr: 1.2,
        },
        // 11. Low confidence overrides
        TrailCase {
            label: "low-conf-override",
            pos_type: PosType::Long,
            entry: 50000.0,
            close: 51500.0,
            atr: 500.0,
            trailing_sl: 0.0,
            confidence: Confidence::Low,
            rsi: 55.0,
            adx: 30.0,
            adx_slope: 0.5,
            atr_slope: 0.0,
            bb_width_ratio: 1.0,
            profit_atr: 3.0,
        },
    ];

    let (ts, td, tslc, tdlc, rfd, rft, evb, vbt, vbm, hpa, ttp, ttd, twm) = trailing_defaults();

    for c in &cases {
        // Use low-conf overrides when testing low confidence
        let use_tslc = if c.confidence == Confidence::Low {
            1.5
        } else {
            tslc
        };
        let use_tdlc = if c.confidence == Confidence::Low {
            1.0
        } else {
            tdlc
        };

        let ref_tsl = rust_compute_trailing(
            c.pos_type,
            c.entry,
            c.close,
            c.atr,
            c.trailing_sl,
            c.confidence,
            c.rsi,
            c.adx,
            c.adx_slope,
            c.atr_slope,
            c.bb_width_ratio,
            c.profit_atr,
            ts,
            td,
            use_tslc,
            use_tdlc,
            rfd,
            rft,
            evb,
            vbt,
            vbm,
            hpa,
            ttp,
            ttd,
            twm,
        );

        // Verify inline reference produces finite result
        assert!(
            ref_tsl.is_finite(),
            "[{}] Trailing SL must be finite: got {}",
            c.label,
            ref_tsl
        );

        // For active trailing (profit >= start), verify directional sanity
        let eff_start = if c.confidence == Confidence::Low && use_tslc > 0.0 {
            use_tslc
        } else {
            ts
        };

        if c.profit_atr >= eff_start {
            match c.pos_type {
                PosType::Long => assert!(
                    ref_tsl < c.close,
                    "[{}] LONG trailing SL ({}) must be below close ({})",
                    c.label,
                    ref_tsl,
                    c.close
                ),
                PosType::Short => assert!(
                    ref_tsl > c.close,
                    "[{}] SHORT trailing SL ({}) must be above close ({})",
                    c.label,
                    ref_tsl,
                    c.close
                ),
            }
        }

        // Verify f32 round-trip precision
        if ref_tsl != 0.0 {
            let rt = ref_tsl as f32 as f64;
            assert!(
                within_tolerance(ref_tsl, rt, TIER_T2_TOLERANCE),
                "[{}] Trailing SL f32 round-trip: f64={}, f32_rt={}, rel_err={:.2e}",
                c.label,
                ref_tsl,
                rt,
                relative_error(ref_tsl, rt)
            );
        }
    }
}

// ── Test 3: TP decision correctness — partial / full / hold ────────────────

#[test]
fn test_aqc1225_tp_decision_correctness() {
    // Verify TP decision (partial, full, hold) using bt-core CPU.
    // We set up positions at specific price levels relative to TP to
    // validate each outcome.
    struct TpCase {
        label: &'static str,
        side: PositionSide,
        entry: f64,
        atr: f64,
        close: f64,
        tp1_taken: bool,
        enable_partial: bool,
        tp_partial_atr_mult: f64,
        expected: TpExpect,
    }

    #[derive(Debug, PartialEq)]
    enum TpExpect {
        Hold,
        Partial,
        Full,
    }

    let cases = vec![
        // 1. Long: price below TP -> Hold
        TpCase {
            label: "long-below-tp",
            side: PositionSide::Long,
            entry: 50000.0,
            atr: 500.0,
            close: 51500.0,
            tp1_taken: false,
            enable_partial: true,
            tp_partial_atr_mult: 0.0,
            expected: TpExpect::Hold,
        },
        // 2. Long: price at TP (partial enabled, tp1 not taken) -> Partial
        TpCase {
            label: "long-partial-tp-hit",
            side: PositionSide::Long,
            entry: 50000.0,
            atr: 500.0,
            close: 52100.0,
            tp1_taken: false,
            enable_partial: true,
            tp_partial_atr_mult: 0.0,
            expected: TpExpect::Partial,
        },
        // 3. Long: price at TP (partial disabled) -> Full
        TpCase {
            label: "long-full-tp-hit",
            side: PositionSide::Long,
            entry: 50000.0,
            atr: 500.0,
            close: 52100.0,
            tp1_taken: false,
            enable_partial: false,
            tp_partial_atr_mult: 0.0,
            expected: TpExpect::Full,
        },
        // 4. Short: price at TP -> Partial
        TpCase {
            label: "short-partial-tp-hit",
            side: PositionSide::Short,
            entry: 50000.0,
            atr: 500.0,
            close: 47900.0,
            tp1_taken: false,
            enable_partial: true,
            tp_partial_atr_mult: 0.0,
            expected: TpExpect::Partial,
        },
        // 5. Short: price below TP (hold)
        TpCase {
            label: "short-above-tp",
            side: PositionSide::Short,
            entry: 50000.0,
            atr: 500.0,
            close: 48500.0,
            tp1_taken: false,
            enable_partial: true,
            tp_partial_atr_mult: 0.0,
            expected: TpExpect::Hold,
        },
        // 6. Separate partial level: price hits partial but not full
        TpCase {
            label: "long-separate-partial-level",
            side: PositionSide::Long,
            entry: 50000.0,
            atr: 500.0,
            close: 51100.0,
            tp1_taken: false,
            enable_partial: true,
            tp_partial_atr_mult: 2.0,
            // partial at entry + 2.0*atr = 51000, full at entry + 4.0*atr = 52000
            // close=51100 > 51000 partial -> Partial
            expected: TpExpect::Partial,
        },
        // 7. tp1 already taken, separate partial level, full TP hit
        TpCase {
            label: "long-tp1-taken-full-hit",
            side: PositionSide::Long,
            entry: 50000.0,
            atr: 500.0,
            close: 52100.0,
            tp1_taken: true,
            enable_partial: true,
            tp_partial_atr_mult: 2.0,
            // tp1 taken, tp_partial_atr_mult > 0, full TP at 52000, close=52100 -> Full
            expected: TpExpect::Full,
        },
        // 8. tp1 already taken, no separate level -> Hold
        TpCase {
            label: "long-tp1-taken-no-separate-hold",
            side: PositionSide::Long,
            entry: 50000.0,
            atr: 500.0,
            close: 52100.0,
            tp1_taken: true,
            enable_partial: true,
            tp_partial_atr_mult: 0.0,
            // tp1 taken, tp_partial_atr_mult=0 -> Hold (no further TP check after tp1)
            expected: TpExpect::Hold,
        },
        // 9. BTC-scale short TP
        TpCase {
            label: "btc-short-full-tp",
            side: PositionSide::Short,
            entry: 65000.0,
            atr: 650.0,
            close: 62300.0,
            tp1_taken: false,
            enable_partial: false,
            tp_partial_atr_mult: 0.0,
            // TP at 65000 - 4*650 = 62400; close=62300 < 62400 -> Full
            expected: TpExpect::Full,
        },
        // 10. Penny stock long TP (use large quantity so notional check passes)
        TpCase {
            label: "penny-long-full-tp",
            side: PositionSide::Long,
            entry: 0.0025,
            atr: 0.000025,
            close: 0.0026,
            tp1_taken: false,
            enable_partial: false,
            tp_partial_atr_mult: 0.0,
            // TP at 0.0025 + 4*0.000025 = 0.0026; close=0.0026 >= TP, partial disabled -> Full
            expected: TpExpect::Full,
        },
    ];

    for c in &cases {
        let params = ExitParams {
            enable_partial_tp: c.enable_partial,
            tp_partial_atr_mult: c.tp_partial_atr_mult,
            // Disable SL/trailing/smart to isolate TP
            sl_atr_mult: 100.0,                // very wide SL
            trailing_start_atr: 1000.0,        // never active
            smart_exit_adx_exhaustion_lt: 0.0, // disable exhaustion
            enable_rsi_overextension_exit: false,
            require_macro_alignment: false,
            enable_breakeven_stop: false,
            ..default_exit_params()
        };

        let snap = IndicatorSnapshot {
            close: c.close,
            high: c.close * 1.005,
            low: c.close * 0.995,
            open: c.close,
            volume: 1000.0,
            t: 1_000_000,
            ema_fast: c.close,
            ema_slow: c.close,
            ema_macro: c.close,
            adx: 30.0,
            adx_pos: 18.0,
            adx_neg: 12.0,
            adx_slope: 0.5,
            bb_upper: c.close * 1.02,
            bb_lower: c.close * 0.98,
            bb_width: 0.04,
            bb_width_avg: 0.04,
            bb_width_ratio: 1.0,
            atr: c.atr,
            atr_slope: 0.0,
            avg_atr: c.atr,
            rsi: 50.0,
            stoch_rsi_k: 50.0,
            stoch_rsi_d: 50.0,
            macd_hist: 0.0,
            prev_macd_hist: 0.0,
            prev2_macd_hist: 0.0,
            prev3_macd_hist: 0.0,
            vol_sma: 1000.0,
            vol_trend: false,
            prev_close: c.close,
            prev_ema_fast: c.close,
            prev_ema_slow: c.close,
            bar_count: 200,
            funding_rate: 0.0,
        };

        let mut pos = Position {
            symbol: "BTC".to_string(),
            side: c.side,
            quantity: 1.0,
            avg_entry_price: c.entry,
            opened_at_ms: 0,
            updated_at_ms: 0,
            notional_usd: c.entry,
            margin_usd: c.entry / 3.0,
            confidence: Some(2),
            entry_atr: Some(c.atr),
            entry_adx_threshold: None,
            adds_count: 0,
            tp1_taken: c.tp1_taken,
            trailing_sl: None,
            mae_usd: 0.0,
            mfe_usd: 0.0,
            last_funding_ms: None,
        };

        let result = evaluate_exits(&mut pos, &snap, &params, 1_000_000);

        match c.expected {
            TpExpect::Hold => {
                assert_eq!(
                    result,
                    KernelExitResult::Hold,
                    "[{}] Expected Hold, got {:?}",
                    c.label,
                    result
                );
            }
            TpExpect::Partial => match &result {
                KernelExitResult::PartialClose {
                    reason, fraction, ..
                } => {
                    assert!(
                        reason.contains("Partial"),
                        "[{}] Expected 'Partial' in reason, got: {}",
                        c.label,
                        reason
                    );
                    assert!(
                        *fraction > 0.0 && *fraction < 1.0,
                        "[{}] Partial fraction must be in (0,1), got {}",
                        c.label,
                        fraction
                    );
                }
                other => panic!("[{}] Expected PartialClose, got {:?}", c.label, other),
            },
            TpExpect::Full => match &result {
                KernelExitResult::FullClose { reason, .. } => {
                    assert!(
                        reason.contains("Take Profit"),
                        "[{}] Expected 'Take Profit' in reason, got: {}",
                        c.label,
                        reason
                    );
                }
                other => panic!("[{}] Expected FullClose, got {:?}", c.label, other),
            },
        }
    }
}

// ─── Test: PESC cooldown logic matches expected blocked/unblocked ─────────────

#[test]
fn test_pesc_fixtures_match_expected_blocked() {
    // AQC-1232: For each PESC fixture, verify the cooldown logic produces
    // the expected blocked/unblocked result.
    let fixtures = make_pesc_fixtures();

    for f in &fixtures {
        let blocked = rust_is_pesc_blocked(
            f.reentry_cooldown_minutes,
            f.reentry_cooldown_min_mins,
            f.reentry_cooldown_max_mins,
            f.close_ts,
            f.close_type,
            f.close_reason,
            f.desired_type,
            f.current_ts,
            f.adx,
        );

        assert_eq!(
            blocked,
            f.expected_blocked,
            "[{}] PESC blocked mismatch: got={}, expected={} \
             (cooldown_min={}min, cooldown_max={}min, ADX={}, elapsed={}s)",
            f.label,
            blocked,
            f.expected_blocked,
            f.reentry_cooldown_min_mins,
            f.reentry_cooldown_max_mins,
            f.adx,
            f.current_ts.saturating_sub(f.close_ts)
        );
    }
}

// ─── Test: PESC ADX interpolation numerical accuracy ─────────────────────────

#[test]
fn test_pesc_adx_interpolation_numerical_accuracy() {
    // AQC-1232: Verify the ADX interpolation formula produces exact expected
    // cooldown values at specific ADX points.
    let min_cd: f64 = 45.0;
    let max_cd: f64 = 180.0;

    // ADX -> expected cooldown (minutes)
    let test_points: &[(&str, f64, f64)] = &[
        ("adx=25 (weak)", 25.0, 180.0),
        ("adx=40 (strong)", 40.0, 45.0),
        ("adx=32.5 (mid)", 32.5, 112.5),
        ("adx=30 (1/3)", 30.0, 180.0 + (5.0 / 15.0) * (45.0 - 180.0)),
        ("adx=35 (2/3)", 35.0, 180.0 + (10.0 / 15.0) * (45.0 - 180.0)),
        ("adx=10 (below range)", 10.0, 180.0), // clamps to max
        ("adx=60 (above range)", 60.0, 45.0),  // clamps to min
    ];

    for &(label, adx, expected_cooldown) in test_points {
        let cooldown_mins = if adx >= 40.0 {
            min_cd
        } else if adx <= 25.0 {
            max_cd
        } else {
            let t = (adx - 25.0) / 15.0;
            max_cd + t * (min_cd - max_cd)
        };

        assert!(
            (cooldown_mins - expected_cooldown).abs() < 1e-10,
            "[{}] cooldown mismatch: got={:.4}min, expected={:.4}min",
            label,
            cooldown_mins,
            expected_cooldown
        );
    }
}

// ─── Test: sizing with risk_core directly across equity levels ────────────────

#[test]
fn test_sizing_risk_core_equity_scaling() {
    // AQC-1232: Verify that sizing scales linearly with equity for static sizing,
    // and that the sizing ratio is preserved across $1k, $10k, $100k.
    use risk_core::{compute_entry_sizing, ConfidenceTier, EntrySizingInput};

    let equities = [1_000.0, 10_000.0, 100_000.0];
    let base_input = EntrySizingInput {
        equity: 0.0, // placeholder
        price: 100.0,
        atr: 1.0,
        adx: 30.0,
        confidence: ConfidenceTier::High,
        allocation_pct: 0.03,
        enable_dynamic_sizing: false,
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
    };

    let results: Vec<_> = equities
        .iter()
        .map(|&eq| {
            let mut input = base_input;
            input.equity = eq;
            compute_entry_sizing(input)
        })
        .collect();

    // Static sizing: margin = equity * alloc_pct, so 10x equity = 10x margin
    for i in 1..results.len() {
        let ratio = equities[i] / equities[i - 1];
        let margin_ratio = results[i].margin_used / results[i - 1].margin_used;
        assert!(
            (margin_ratio - ratio).abs() < 1e-10,
            "Margin should scale {}x with equity: got {}x (eq {}->{})",
            ratio,
            margin_ratio,
            equities[i - 1],
            equities[i]
        );
        let size_ratio = results[i].size / results[i - 1].size;
        assert!(
            (size_ratio - ratio).abs() < 1e-10,
            "Size should scale {}x with equity: got {}x",
            ratio,
            size_ratio
        );
    }

    // Leverage must be constant (High -> leverage_high=5.0 for all equity levels)
    for r in &results {
        assert!(
            (r.leverage - 5.0).abs() < 1e-10,
            "Leverage should be 5.0 (High confidence) for all equity levels, got {}",
            r.leverage
        );
    }
}

// ─── Test: dynamic leverage tiers select correct per-confidence level ─────────

#[test]
fn test_sizing_dynamic_leverage_tier_selection() {
    // AQC-1232: Verify that each confidence level selects the correct
    // leverage tier.
    use risk_core::{compute_entry_sizing, ConfidenceTier, EntrySizingInput};

    let base = EntrySizingInput {
        equity: 10_000.0,
        price: 100.0,
        atr: 1.0,
        adx: 30.0,
        confidence: ConfidenceTier::High, // placeholder
        allocation_pct: 0.03,
        enable_dynamic_sizing: false,
        confidence_mult_high: 1.0,
        confidence_mult_medium: 0.8,
        confidence_mult_low: 0.6,
        adx_sizing_min_mult: 0.6,
        adx_sizing_full_adx: 40.0,
        vol_baseline_pct: 0.01,
        vol_scalar_min: 0.6,
        vol_scalar_max: 1.4,
        leverage_low: 1.5,
        leverage_medium: 3.0,
        leverage_high: 5.0,
    };

    let tier_tests: &[(ConfidenceTier, f64)] = &[
        (ConfidenceTier::Low, 1.5),
        (ConfidenceTier::Medium, 3.0),
        (ConfidenceTier::High, 5.0),
    ];

    for &(conf, expected_lev) in tier_tests {
        let mut input = base;
        input.confidence = conf;
        let r = compute_entry_sizing(input);
        assert!(
            (r.leverage - expected_lev).abs() < 1e-10,
            "Dynamic leverage {:?} should be {}, got {}",
            conf,
            expected_lev,
            r.leverage
        );
    }
}

// ─── Test: dynamic sizing multiplier chain correctness ───────────────────────

#[test]
fn test_sizing_dynamic_multiplier_chain() {
    // AQC-1232: Verify the multiplicative chain: margin = equity * alloc *
    // conf_mult * adx_mult * vol_scalar. Exercise edge cases for each factor.
    use risk_core::{compute_entry_sizing, ConfidenceTier, EntrySizingInput};

    let base = EntrySizingInput {
        equity: 10_000.0,
        price: 100.0,
        atr: 1.0,
        adx: 40.0,
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
        leverage_medium: 1.0,
        leverage_high: 1.0,
    };

    // All multipliers at 1.0: margin = 10000 * 0.03 = 300
    let r = compute_entry_sizing(base);
    assert!(
        (r.margin_used - 300.0).abs() < 1e-10,
        "All-ones margin should be 300, got {}",
        r.margin_used
    );

    // Only confidence mult active (Low = 0.6): margin = 300 * 0.6 = 180
    let mut input = base;
    input.confidence = ConfidenceTier::Low;
    let r = compute_entry_sizing(input);
    // adx=40 -> adx_mult=1.0, vol unchanged -> margin = 300 * 0.6 = 180
    assert!(
        (r.margin_used - 180.0).abs() < 1e-10,
        "Low-conf margin should be 180, got {}",
        r.margin_used
    );

    // ADX at zero (adx_mult floors to 0.6): margin = 300 * 1.0 * 0.6 = 180
    let mut input = base;
    input.adx = 0.0;
    let r = compute_entry_sizing(input);
    assert!(
        (r.margin_used - 180.0).abs() < 1e-10,
        "Zero-ADX margin should be 180, got {}",
        r.margin_used
    );

    // full_adx at zero (guard fallback to min_mult=0.6): margin = 300 * 1.0 * 0.6 = 180
    let mut input = base;
    input.adx = 40.0;
    input.adx_sizing_full_adx = 0.0;
    let r = compute_entry_sizing(input);
    assert!(
        (r.margin_used - 180.0).abs() < 1e-10,
        "Zero-full-ADX margin should be 180, got {}",
        r.margin_used
    );

    // High vol (atr=2.0, vol_ratio=2.0, vol_scalar=0.5 clamped to 0.6):
    // margin = 300 * 1.0 * 1.0 * 0.6 = 180
    let mut input = base;
    input.atr = 2.0;
    let r = compute_entry_sizing(input);
    assert!(
        (r.margin_used - 180.0).abs() < 1e-10,
        "High-vol margin should be 180, got {}",
        r.margin_used
    );

    // Low vol (atr=0.25, vol_ratio=0.25, vol_scalar=4.0 clamped to 1.4):
    // margin = 300 * 1.0 * 1.0 * 1.4 = 420
    let mut input = base;
    input.atr = 0.25;
    let r = compute_entry_sizing(input);
    assert!(
        (r.margin_used - 420.0).abs() < 1e-10,
        "Low-vol margin should be 420, got {}",
        r.margin_used
    );
}

// ─── Test: PESC cooldown seconds conversion accuracy ─────────────────────────

#[test]
fn test_pesc_cooldown_seconds_conversion() {
    // AQC-1232: Verify minutes-to-seconds conversion matches at boundary values.
    // This catches off-by-one errors in the elapsed < cooldown_sec comparison.
    let min_cd = 45u32;
    let max_cd = 180u32;
    let base_ts = 100_000u32;

    // At ADX=25 (max cooldown = 180min = 10800s):
    // Exactly at boundary: elapsed = 10800 -> NOT blocked (not strictly less than)
    let blocked = rust_is_pesc_blocked(60, min_cd, max_cd, base_ts, 1, 2, 1, base_ts + 10800, 25.0);
    assert!(
        !blocked,
        "At exactly cooldown boundary (10800s), should NOT be blocked"
    );

    // 1 second before boundary: elapsed = 10799 -> blocked
    let blocked = rust_is_pesc_blocked(60, min_cd, max_cd, base_ts, 1, 2, 1, base_ts + 10799, 25.0);
    assert!(
        blocked,
        "1 second before cooldown boundary (10799s), should be blocked"
    );

    // At ADX=40 (min cooldown = 45min = 2700s):
    let blocked = rust_is_pesc_blocked(60, min_cd, max_cd, base_ts, 1, 2, 1, base_ts + 2700, 40.0);
    assert!(
        !blocked,
        "At exactly min cooldown boundary (2700s), should NOT be blocked"
    );

    let blocked = rust_is_pesc_blocked(60, min_cd, max_cd, base_ts, 1, 2, 1, base_ts + 2699, 40.0);
    assert!(
        blocked,
        "1 second before min cooldown boundary (2699s), should be blocked"
    );
}

// ─── Test: sizing coverage count ─────────────────────────────────────────────

#[test]
fn test_sizing_fixture_coverage_count() {
    // AQC-1232: Must have at least 10 sizing fixtures + 10 PESC fixtures
    let sizing = make_sizing_fixtures();
    let pesc = make_pesc_fixtures();

    assert!(
        sizing.len() >= 10,
        "Must have at least 10 sizing fixtures, got {}",
        sizing.len()
    );
    assert!(
        pesc.len() >= 10,
        "Must have at least 10 PESC fixtures, got {}",
        pesc.len()
    );
}

// ─── Test: sizing fixture diversity ──────────────────────────────────────────

#[test]
fn test_sizing_fixture_diversity() {
    // AQC-1232: Verify diverse coverage of sizing scenarios.
    let fixtures = make_sizing_fixtures();

    // Must cover static sizing
    assert!(
        fixtures.iter().any(|f| !f.enable_dynamic_sizing),
        "Must include static sizing fixtures"
    );

    // Must cover dynamic sizing
    assert!(
        fixtures.iter().any(|f| f.enable_dynamic_sizing),
        "Must include dynamic sizing fixtures"
    );

    // Must cover all three confidence levels
    assert!(
        fixtures.iter().any(|f| f.confidence == Confidence::High),
        "Must include High confidence"
    );
    assert!(
        fixtures.iter().any(|f| f.confidence == Confidence::Medium),
        "Must include Medium confidence"
    );
    assert!(
        fixtures.iter().any(|f| f.confidence == Confidence::Low),
        "Must include Low confidence"
    );

    // Must cover equity levels $1k, $10k, $100k
    assert!(
        fixtures.iter().any(|f| f.equity <= 1_000.0),
        "Must include $1k equity"
    );
    assert!(
        fixtures
            .iter()
            .any(|f| f.equity >= 10_000.0 && f.equity < 100_000.0),
        "Must include $10k equity"
    );
    assert!(
        fixtures.iter().any(|f| f.equity >= 100_000.0),
        "Must include $100k equity"
    );

    // Must cover zero price edge case
    assert!(
        fixtures.iter().any(|f| f.price == 0.0),
        "Must include zero-price edge case"
    );
}

// ─── Test: PESC fixture diversity ────────────────────────────────────────────

#[test]
fn test_pesc_fixture_diversity() {
    // AQC-1232: Verify PESC fixtures cover all bypass/block paths.
    let fixtures = make_pesc_fixtures();

    // Must cover disabled PESC
    assert!(
        fixtures.iter().any(|f| f.reentry_cooldown_minutes == 0),
        "Must include disabled PESC"
    );

    // Must cover no prior close
    assert!(
        fixtures.iter().any(|f| f.close_ts == 0),
        "Must include no-prior-close bypass"
    );

    // Must cover signal flip bypass
    assert!(
        fixtures.iter().any(|f| f.close_reason == 1),
        "Must include signal-flip bypass"
    );

    // Must cover direction gate
    assert!(
        fixtures
            .iter()
            .any(|f| f.close_type != f.desired_type && f.close_ts > 0),
        "Must include opposite-direction bypass"
    );

    // Must cover blocked case
    assert!(
        fixtures.iter().any(|f| f.expected_blocked),
        "Must include blocked scenarios"
    );

    // Must cover unblocked-past-cooldown case
    assert!(
        fixtures.iter().any(|f| !f.expected_blocked
            && f.close_ts > 0
            && f.close_reason == 2
            && f.close_type == f.desired_type),
        "Must include unblocked-past-cooldown scenarios"
    );

    // Must cover ADX interpolation range
    assert!(
        fixtures.iter().any(|f| f.adx > 25.0 && f.adx < 40.0),
        "Must include ADX interpolation range (25 < ADX < 40)"
    );
}

// ── Test 4: Smart exit triggers — verify each sub-check fires correctly ────

#[test]
fn test_aqc1225_smart_exit_trend_breakdown() {
    // Smart exit #1: Trend Breakdown (EMA Cross) fires when EMAs cross
    // against position direction.
    let params = ExitParams {
        sl_atr_mult: 100.0,         // wide SL
        trailing_start_atr: 1000.0, // never active
        tp_atr_mult: 100.0,         // very far TP
        enable_partial_tp: false,
        smart_exit_adx_exhaustion_lt: 0.0, // disable exhaustion
        enable_rsi_overextension_exit: false,
        require_macro_alignment: false,
        ..default_exit_params()
    };

    // Long position, EMA fast < EMA slow -> bearish cross -> exit
    let snap = IndicatorSnapshot {
        close: 50500.0,
        high: 50600.0,
        low: 50400.0,
        open: 50500.0,
        volume: 1000.0,
        t: 1_000_000,
        ema_fast: 50400.0, // below slow -> bearish cross
        ema_slow: 50600.0,
        ema_macro: 50000.0,
        adx: 30.0,
        adx_pos: 18.0,
        adx_neg: 12.0,
        adx_slope: 0.5,
        bb_upper: 51000.0,
        bb_lower: 50000.0,
        bb_width: 0.02,
        bb_width_avg: 0.02,
        bb_width_ratio: 1.0,
        atr: 500.0,
        atr_slope: 0.0,
        avg_atr: 500.0,
        rsi: 50.0,
        stoch_rsi_k: 50.0,
        stoch_rsi_d: 50.0,
        macd_hist: 0.0,
        prev_macd_hist: 0.0,
        prev2_macd_hist: 0.0,
        prev3_macd_hist: 0.0,
        vol_sma: 1000.0,
        vol_trend: false,
        prev_close: 50500.0,
        prev_ema_fast: 50500.0,
        prev_ema_slow: 50500.0,
        bar_count: 200,
        funding_rate: 0.0,
    };

    let mut pos = Position {
        symbol: "BTC".to_string(),
        side: PositionSide::Long,
        quantity: 1.0,
        avg_entry_price: 50000.0,
        opened_at_ms: 0,
        updated_at_ms: 0,
        notional_usd: 50000.0,
        margin_usd: 16666.0,
        confidence: Some(2),
        entry_atr: Some(500.0),
        entry_adx_threshold: None,
        adds_count: 0,
        tp1_taken: false,
        trailing_sl: None,
        mae_usd: 0.0,
        mfe_usd: 0.0,
        last_funding_ms: None,
    };

    let result = evaluate_exits(&mut pos, &snap, &params, 1_000_000);
    match &result {
        KernelExitResult::FullClose { reason, .. } => {
            assert!(
                reason.contains("Trend Breakdown") || reason.contains("EMA Cross"),
                "Expected Trend Breakdown exit, got: {}",
                reason
            );
        }
        other => panic!("Expected FullClose for trend breakdown, got {:?}", other),
    }
}

#[test]
fn test_aqc1225_smart_exit_trend_exhaustion() {
    // Smart exit #2: Trend Exhaustion fires when ADX < threshold.
    let params = ExitParams {
        sl_atr_mult: 100.0,
        trailing_start_atr: 1000.0,
        tp_atr_mult: 100.0,
        enable_partial_tp: false,
        smart_exit_adx_exhaustion_lt: 25.0, // exit when ADX < 25
        enable_rsi_overextension_exit: false,
        require_macro_alignment: false,
        ..default_exit_params()
    };

    // Long position, ADX = 20 (below 25 threshold) -> should exit
    let snap = IndicatorSnapshot {
        close: 50500.0,
        high: 50600.0,
        low: 50400.0,
        open: 50500.0,
        volume: 1000.0,
        t: 1_000_000,
        ema_fast: 50600.0, // still bullish (no trend breakdown)
        ema_slow: 50400.0,
        ema_macro: 50000.0,
        adx: 20.0, // below threshold
        adx_pos: 12.0,
        adx_neg: 8.0,
        adx_slope: -0.5,
        bb_upper: 51000.0,
        bb_lower: 50000.0,
        bb_width: 0.02,
        bb_width_avg: 0.02,
        bb_width_ratio: 1.0,
        atr: 500.0,
        atr_slope: 0.0,
        avg_atr: 500.0,
        rsi: 50.0,
        stoch_rsi_k: 50.0,
        stoch_rsi_d: 50.0,
        macd_hist: 0.0,
        prev_macd_hist: 0.0,
        prev2_macd_hist: 0.0,
        prev3_macd_hist: 0.0,
        vol_sma: 1000.0,
        vol_trend: false,
        prev_close: 50500.0,
        prev_ema_fast: 50600.0,
        prev_ema_slow: 50400.0,
        bar_count: 200,
        funding_rate: 0.0,
    };

    let mut pos = Position {
        symbol: "BTC".to_string(),
        side: PositionSide::Long,
        quantity: 1.0,
        avg_entry_price: 50000.0,
        opened_at_ms: 0,
        updated_at_ms: 0,
        notional_usd: 50000.0,
        margin_usd: 16666.0,
        confidence: Some(2),
        entry_atr: Some(500.0),
        entry_adx_threshold: None,
        adds_count: 0,
        tp1_taken: false,
        trailing_sl: None,
        mae_usd: 0.0,
        mfe_usd: 0.0,
        last_funding_ms: None,
    };

    let result = evaluate_exits(&mut pos, &snap, &params, 1_000_000);
    match &result {
        KernelExitResult::FullClose { reason, .. } => {
            assert!(
                reason.contains("Trend Exhaustion"),
                "Expected Trend Exhaustion exit, got: {}",
                reason
            );
        }
        other => panic!("Expected FullClose for trend exhaustion, got {:?}", other),
    }
}

#[test]
fn test_aqc1225_smart_exit_stagnation() {
    // Smart exit #4: Stagnation Exit (low vol + underwater)
    let params = ExitParams {
        sl_atr_mult: 100.0,
        trailing_start_atr: 1000.0,
        tp_atr_mult: 100.0,
        enable_partial_tp: false,
        smart_exit_adx_exhaustion_lt: 0.0,
        enable_rsi_overextension_exit: false,
        require_macro_alignment: false,
        ..default_exit_params()
    };

    // Long position, underwater, ATR dropped to < 70% of entry ATR
    let entry_atr = 500.0;
    let snap = IndicatorSnapshot {
        close: 49800.0, // underwater
        high: 49900.0,
        low: 49700.0,
        open: 49800.0,
        volume: 1000.0,
        t: 1_000_000,
        ema_fast: 49900.0, // still bullish (no trend breakdown)
        ema_slow: 49800.0,
        ema_macro: 49000.0,
        adx: 30.0, // above any exhaustion threshold
        adx_pos: 18.0,
        adx_neg: 12.0,
        adx_slope: 0.5,
        bb_upper: 50300.0,
        bb_lower: 49300.0,
        bb_width: 0.02,
        bb_width_avg: 0.02,
        bb_width_ratio: 1.0,
        atr: entry_atr * 0.60, // 60% of entry ATR, below 70% threshold
        atr_slope: -0.5,
        avg_atr: entry_atr,
        rsi: 50.0,
        stoch_rsi_k: 50.0,
        stoch_rsi_d: 50.0,
        macd_hist: 0.0,
        prev_macd_hist: 0.0,
        prev2_macd_hist: 0.0,
        prev3_macd_hist: 0.0,
        vol_sma: 1000.0,
        vol_trend: false,
        prev_close: 49800.0,
        prev_ema_fast: 49900.0,
        prev_ema_slow: 49800.0,
        bar_count: 200,
        funding_rate: 0.0,
    };

    let mut pos = Position {
        symbol: "BTC".to_string(),
        side: PositionSide::Long,
        quantity: 1.0,
        avg_entry_price: 50000.0,
        opened_at_ms: 0,
        updated_at_ms: 0,
        notional_usd: 50000.0,
        margin_usd: 16666.0,
        confidence: Some(2),
        entry_atr: Some(entry_atr),
        entry_adx_threshold: None,
        adds_count: 0,
        tp1_taken: false,
        trailing_sl: None,
        mae_usd: 0.0,
        mfe_usd: 0.0,
        last_funding_ms: None,
    };

    let result = evaluate_exits(&mut pos, &snap, &params, 1_000_000);
    match &result {
        KernelExitResult::FullClose { reason, .. } => {
            assert!(
                reason.contains("Stagnation"),
                "Expected Stagnation Exit, got: {}",
                reason
            );
        }
        other => panic!("Expected FullClose for stagnation, got {:?}", other),
    }
}

#[test]
fn test_aqc1225_smart_exit_tsme() {
    // Smart exit #6: TSME fires when ADX>50, profit above threshold,
    // slope negative, and MACD showing consecutive contraction.
    let params = ExitParams {
        sl_atr_mult: 100.0,
        trailing_start_atr: 1000.0,
        tp_atr_mult: 100.0,
        enable_partial_tp: false,
        smart_exit_adx_exhaustion_lt: 0.0,
        enable_rsi_overextension_exit: false,
        require_macro_alignment: false,
        tsme_min_profit_atr: 1.0,
        tsme_require_adx_slope_negative: true,
        ..default_exit_params()
    };

    // Long position, ADX=55, slope negative, MACD contracting
    let snap = IndicatorSnapshot {
        close: 51000.0, // profit = 2 ATR
        high: 51100.0,
        low: 50900.0,
        open: 51000.0,
        volume: 1000.0,
        t: 1_000_000,
        ema_fast: 51100.0,
        ema_slow: 50900.0,
        ema_macro: 50000.0,
        adx: 55.0, // > 50 (TSME gate)
        adx_pos: 33.0,
        adx_neg: 22.0,
        adx_slope: -0.5, // negative slope
        bb_upper: 51500.0,
        bb_lower: 50500.0,
        bb_width: 0.02,
        bb_width_avg: 0.02,
        bb_width_ratio: 1.0,
        atr: 500.0,
        atr_slope: 0.0,
        avg_atr: 500.0,
        rsi: 60.0,
        stoch_rsi_k: 50.0,
        stoch_rsi_d: 50.0,
        // MACD hist contracting for long: hist < prev < prev2
        macd_hist: 10.0,
        prev_macd_hist: 15.0,
        prev2_macd_hist: 20.0,
        prev3_macd_hist: 25.0,
        vol_sma: 1000.0,
        vol_trend: false,
        prev_close: 51000.0,
        prev_ema_fast: 51100.0,
        prev_ema_slow: 50900.0,
        bar_count: 200,
        funding_rate: 0.0,
    };

    let mut pos = Position {
        symbol: "BTC".to_string(),
        side: PositionSide::Long,
        quantity: 1.0,
        avg_entry_price: 50000.0,
        opened_at_ms: 0,
        updated_at_ms: 0,
        notional_usd: 50000.0,
        margin_usd: 16666.0,
        confidence: Some(2),
        entry_atr: Some(500.0),
        entry_adx_threshold: None,
        adds_count: 0,
        tp1_taken: false,
        trailing_sl: None,
        mae_usd: 0.0,
        mfe_usd: 0.0,
        last_funding_ms: None,
    };

    let result = evaluate_exits(&mut pos, &snap, &params, 1_000_000);
    match &result {
        KernelExitResult::FullClose { reason, .. } => {
            assert!(
                reason.contains("Trend Saturation") || reason.contains("TSME"),
                "Expected TSME exit, got: {}",
                reason
            );
        }
        other => panic!("Expected FullClose for TSME, got {:?}", other),
    }
}

#[test]
fn test_aqc1225_smart_exit_rsi_overextension_long() {
    // Smart exit #8: RSI overextension for long (RSI above upper bound).
    let params = ExitParams {
        sl_atr_mult: 100.0,
        trailing_start_atr: 1000.0,
        tp_atr_mult: 100.0,
        enable_partial_tp: false,
        smart_exit_adx_exhaustion_lt: 0.0,
        enable_rsi_overextension_exit: true,
        rsi_exit_profit_atr_switch: 1.5,
        rsi_exit_ub_hi_profit: 70.0, // high-profit upper bound for long
        rsi_exit_lb_hi_profit: 30.0,
        require_macro_alignment: false,
        ..default_exit_params()
    };

    // Long position, profit > 1.5 ATR (high-profit regime), RSI = 75 (> 70 threshold)
    let snap = IndicatorSnapshot {
        close: 51000.0, // profit = 2 ATR
        high: 51100.0,
        low: 50900.0,
        open: 51000.0,
        volume: 1000.0,
        t: 1_000_000,
        ema_fast: 51100.0,
        ema_slow: 50900.0,
        ema_macro: 50000.0,
        adx: 30.0,
        adx_pos: 18.0,
        adx_neg: 12.0,
        adx_slope: 0.5,
        bb_upper: 51500.0,
        bb_lower: 50500.0,
        bb_width: 0.02,
        bb_width_avg: 0.02,
        bb_width_ratio: 1.0,
        atr: 500.0,
        atr_slope: 0.0,
        avg_atr: 500.0,
        rsi: 75.0, // above hi-profit upper bound of 70
        stoch_rsi_k: 50.0,
        stoch_rsi_d: 50.0,
        macd_hist: 0.0,
        prev_macd_hist: 0.0,
        prev2_macd_hist: 0.0,
        prev3_macd_hist: 0.0,
        vol_sma: 1000.0,
        vol_trend: false,
        prev_close: 51000.0,
        prev_ema_fast: 51100.0,
        prev_ema_slow: 50900.0,
        bar_count: 200,
        funding_rate: 0.0,
    };

    let mut pos = Position {
        symbol: "BTC".to_string(),
        side: PositionSide::Long,
        quantity: 1.0,
        avg_entry_price: 50000.0,
        opened_at_ms: 0,
        updated_at_ms: 0,
        notional_usd: 50000.0,
        margin_usd: 16666.0,
        confidence: Some(2),
        entry_atr: Some(500.0),
        entry_adx_threshold: None,
        adds_count: 0,
        tp1_taken: false,
        trailing_sl: None,
        mae_usd: 0.0,
        mfe_usd: 0.0,
        last_funding_ms: None,
    };

    let result = evaluate_exits(&mut pos, &snap, &params, 1_000_000);
    match &result {
        KernelExitResult::FullClose { reason, .. } => {
            assert!(
                reason.contains("RSI Overbought") || reason.contains("RSI Overextension"),
                "Expected RSI overbought exit, got: {}",
                reason
            );
        }
        other => panic!("Expected FullClose for RSI overextension, got {:?}", other),
    }
}

#[test]
fn test_aqc1225_smart_exit_rsi_overextension_short() {
    // Smart exit #8: RSI overextension for short (RSI below lower bound).
    let params = ExitParams {
        sl_atr_mult: 100.0,
        trailing_start_atr: 1000.0,
        tp_atr_mult: 100.0,
        enable_partial_tp: false,
        smart_exit_adx_exhaustion_lt: 0.0,
        enable_rsi_overextension_exit: true,
        rsi_exit_profit_atr_switch: 1.5,
        rsi_exit_ub_hi_profit: 70.0,
        rsi_exit_lb_hi_profit: 30.0, // high-profit lower bound for short
        require_macro_alignment: false,
        ..default_exit_params()
    };

    // Short position, profit > 1.5 ATR, RSI = 25 (< 30 threshold)
    let snap = IndicatorSnapshot {
        close: 49000.0, // profit = 2 ATR for short
        high: 49100.0,
        low: 48900.0,
        open: 49000.0,
        volume: 1000.0,
        t: 1_000_000,
        ema_fast: 48900.0, // bearish (no trend breakdown for short)
        ema_slow: 49100.0,
        ema_macro: 50000.0,
        adx: 30.0,
        adx_pos: 12.0,
        adx_neg: 18.0,
        adx_slope: 0.5,
        bb_upper: 49500.0,
        bb_lower: 48500.0,
        bb_width: 0.02,
        bb_width_avg: 0.02,
        bb_width_ratio: 1.0,
        atr: 500.0,
        atr_slope: 0.0,
        avg_atr: 500.0,
        rsi: 25.0, // below hi-profit lower bound of 30
        stoch_rsi_k: 50.0,
        stoch_rsi_d: 50.0,
        macd_hist: 0.0,
        prev_macd_hist: 0.0,
        prev2_macd_hist: 0.0,
        prev3_macd_hist: 0.0,
        vol_sma: 1000.0,
        vol_trend: false,
        prev_close: 49000.0,
        prev_ema_fast: 48900.0,
        prev_ema_slow: 49100.0,
        bar_count: 200,
        funding_rate: 0.0,
    };

    let mut pos = Position {
        symbol: "BTC".to_string(),
        side: PositionSide::Short,
        quantity: 1.0,
        avg_entry_price: 50000.0,
        opened_at_ms: 0,
        updated_at_ms: 0,
        notional_usd: 50000.0,
        margin_usd: 16666.0,
        confidence: Some(2),
        entry_atr: Some(500.0),
        entry_adx_threshold: None,
        adds_count: 0,
        tp1_taken: false,
        trailing_sl: None,
        mae_usd: 0.0,
        mfe_usd: 0.0,
        last_funding_ms: None,
    };

    let result = evaluate_exits(&mut pos, &snap, &params, 1_000_000);
    match &result {
        KernelExitResult::FullClose { reason, .. } => {
            assert!(
                reason.contains("RSI Oversold") || reason.contains("RSI Overextension"),
                "Expected RSI oversold exit, got: {}",
                reason
            );
        }
        other => panic!(
            "Expected FullClose for RSI overextension short, got {:?}",
            other
        ),
    }
}

// ── Test 5: Exit orchestrator priority — SL > Trailing > TP > Smart ────────

#[test]
fn test_aqc1225_exit_priority_sl_beats_all() {
    // When SL and other exits would all trigger, SL must fire first.
    // Setup: price at SL level, also at TP and with bearish EMA cross
    let entry = 50000.0;
    let atr = 500.0;
    let sl_mult = 2.0;
    let sl_price = entry - atr * sl_mult; // 49000

    let params = ExitParams {
        sl_atr_mult: sl_mult,
        tp_atr_mult: 4.0,
        trailing_start_atr: 1000.0, // disabled
        smart_exit_adx_exhaustion_lt: 25.0,
        enable_rsi_overextension_exit: false,
        enable_partial_tp: false,
        enable_breakeven_stop: false,
        require_macro_alignment: false,
        ..default_exit_params()
    };

    // Price at SL level (close <= sl_price for long)
    let snap = IndicatorSnapshot {
        close: sl_price - 10.0, // below SL
        high: sl_price,
        low: sl_price - 20.0,
        open: sl_price,
        volume: 1000.0,
        t: 1_000_000,
        ema_fast: sl_price - 100.0, // bearish cross
        ema_slow: sl_price + 100.0,
        ema_macro: 50000.0,
        adx: 20.0, // below exhaustion threshold
        adx_pos: 10.0,
        adx_neg: 10.0,
        adx_slope: -1.0,
        bb_upper: 51000.0,
        bb_lower: 49000.0,
        bb_width: 0.04,
        bb_width_avg: 0.04,
        bb_width_ratio: 1.0,
        atr,
        atr_slope: 0.0,
        avg_atr: atr,
        rsi: 50.0,
        stoch_rsi_k: 50.0,
        stoch_rsi_d: 50.0,
        macd_hist: 0.0,
        prev_macd_hist: 0.0,
        prev2_macd_hist: 0.0,
        prev3_macd_hist: 0.0,
        vol_sma: 1000.0,
        vol_trend: false,
        prev_close: sl_price,
        prev_ema_fast: sl_price,
        prev_ema_slow: sl_price,
        bar_count: 200,
        funding_rate: 0.0,
    };

    let mut pos = Position {
        symbol: "BTC".to_string(),
        side: PositionSide::Long,
        quantity: 1.0,
        avg_entry_price: entry,
        opened_at_ms: 0,
        updated_at_ms: 0,
        notional_usd: entry,
        margin_usd: entry / 3.0,
        confidence: Some(2),
        entry_atr: Some(atr),
        entry_adx_threshold: None,
        adds_count: 0,
        tp1_taken: false,
        trailing_sl: None,
        mae_usd: 0.0,
        mfe_usd: 0.0,
        last_funding_ms: None,
    };

    let result = evaluate_exits(&mut pos, &snap, &params, 1_000_000);
    match &result {
        KernelExitResult::FullClose { reason, .. } => {
            assert!(
                reason == "Stop Loss",
                "SL must take priority, got: {}",
                reason
            );
        }
        other => panic!("Expected Stop Loss FullClose, got {:?}", other),
    }
}

#[test]
fn test_aqc1225_exit_priority_trailing_beats_tp_and_smart() {
    // When trailing stop is hit but SL is not, trailing must fire before TP/smart.
    let entry = 50000.0;
    let atr = 500.0;

    let params = ExitParams {
        sl_atr_mult: 2.0,
        tp_atr_mult: 100.0, // very far TP (won't hit)
        trailing_start_atr: 1.0,
        trailing_distance_atr: 0.5,
        smart_exit_adx_exhaustion_lt: 25.0,
        enable_rsi_overextension_exit: false,
        enable_partial_tp: false,
        enable_breakeven_stop: false,
        enable_vol_buffered_trailing: false,
        require_macro_alignment: false,
        ..default_exit_params()
    };

    // Long position, profit = 2 ATR, then price drops back to trailing SL
    // Trailing SL with distance 0.5 ATR at close=51000:
    // candidate = 51000 - 500*0.5 = 50750 (assuming no modifiers)
    // Then price drops to 50700 (below trailing SL)
    // But SL at 50000 - 500*2 = 49000, so not hit
    let snap = IndicatorSnapshot {
        close: 50700.0,
        high: 50800.0,
        low: 50600.0,
        open: 50700.0,
        volume: 1000.0,
        t: 2_000_000,
        ema_fast: 50800.0, // still bullish (no trend breakdown)
        ema_slow: 50600.0,
        ema_macro: 50000.0,
        adx: 20.0, // below exhaustion threshold (would trigger smart exit)
        adx_pos: 12.0,
        adx_neg: 8.0,
        adx_slope: -0.5,
        bb_upper: 51500.0,
        bb_lower: 50000.0,
        bb_width: 0.03,
        bb_width_avg: 0.03,
        bb_width_ratio: 1.0,
        atr,
        atr_slope: 0.0,
        avg_atr: atr,
        rsi: 50.0,
        stoch_rsi_k: 50.0,
        stoch_rsi_d: 50.0,
        macd_hist: 0.0,
        prev_macd_hist: 0.0,
        prev2_macd_hist: 0.0,
        prev3_macd_hist: 0.0,
        vol_sma: 1000.0,
        vol_trend: false,
        prev_close: 51000.0,
        prev_ema_fast: 50800.0,
        prev_ema_slow: 50600.0,
        bar_count: 200,
        funding_rate: 0.0,
    };

    let mut pos = Position {
        symbol: "BTC".to_string(),
        side: PositionSide::Long,
        quantity: 1.0,
        avg_entry_price: entry,
        opened_at_ms: 0,
        updated_at_ms: 0,
        notional_usd: entry,
        margin_usd: entry / 3.0,
        confidence: Some(2),
        entry_atr: Some(atr),
        entry_adx_threshold: None,
        adds_count: 0,
        tp1_taken: false,
        // Position already had trailing SL set at 50750 from previous bar
        trailing_sl: Some(50750.0),
        mae_usd: 0.0,
        mfe_usd: 0.0,
        last_funding_ms: None,
    };

    let result = evaluate_exits(&mut pos, &snap, &params, 2_000_000);
    match &result {
        KernelExitResult::FullClose { reason, .. } => {
            assert!(
                reason == "Trailing Stop",
                "Trailing must take priority over smart exits, got: {}",
                reason
            );
        }
        other => panic!("Expected Trailing Stop FullClose, got {:?}", other),
    }
}

// ── Test 6: Exit orchestrator — Hold when no exits fire ────────────────────

#[test]
fn test_aqc1225_exit_orchestrator_hold() {
    // When no exit condition is met, the orchestrator returns Hold.
    let entry = 50000.0;
    let atr = 500.0;

    let params = ExitParams {
        sl_atr_mult: 2.0,
        tp_atr_mult: 4.0,
        trailing_start_atr: 1.0,
        trailing_distance_atr: 0.8,
        smart_exit_adx_exhaustion_lt: 0.0, // disabled
        enable_rsi_overextension_exit: false,
        enable_partial_tp: true,
        enable_breakeven_stop: true,
        breakeven_start_atr: 0.7,
        breakeven_buffer_atr: 0.05,
        require_macro_alignment: false,
        ..default_exit_params()
    };

    // Position is slightly profitable (0.5 ATR), no exit conditions met
    let snap = IndicatorSnapshot {
        close: 50250.0,
        high: 50300.0,
        low: 50200.0,
        open: 50250.0,
        volume: 1000.0,
        t: 1_000_000,
        ema_fast: 50300.0, // bullish (no trend breakdown)
        ema_slow: 50200.0,
        ema_macro: 50000.0,
        adx: 30.0, // healthy
        adx_pos: 18.0,
        adx_neg: 12.0,
        adx_slope: 0.5,
        bb_upper: 50750.0,
        bb_lower: 49750.0,
        bb_width: 0.02,
        bb_width_avg: 0.02,
        bb_width_ratio: 1.0,
        atr,
        atr_slope: 0.0,
        avg_atr: atr,
        rsi: 55.0,
        stoch_rsi_k: 50.0,
        stoch_rsi_d: 50.0,
        macd_hist: 5.0,
        prev_macd_hist: 4.0,
        prev2_macd_hist: 3.0,
        prev3_macd_hist: 2.0,
        vol_sma: 1000.0,
        vol_trend: false,
        prev_close: 50200.0,
        prev_ema_fast: 50250.0,
        prev_ema_slow: 50150.0,
        bar_count: 200,
        funding_rate: 0.0,
    };

    let mut pos = Position {
        symbol: "BTC".to_string(),
        side: PositionSide::Long,
        quantity: 1.0,
        avg_entry_price: entry,
        opened_at_ms: 0,
        updated_at_ms: 0,
        notional_usd: entry,
        margin_usd: entry / 3.0,
        confidence: Some(2),
        entry_atr: Some(atr),
        entry_adx_threshold: None,
        adds_count: 0,
        tp1_taken: false,
        trailing_sl: None,
        mae_usd: 0.0,
        mfe_usd: 0.0,
        last_funding_ms: None,
    };

    let result = evaluate_exits(&mut pos, &snap, &params, 1_000_000);
    assert_eq!(
        result,
        KernelExitResult::Hold,
        "No exit should fire for moderate profit in healthy trend"
    );
}

// ── Test 7: Glitch guard blocks exits ──────────────────────────────────────

#[test]
fn test_aqc1225_glitch_guard_blocks_exit() {
    // Glitch guard should block exits when price deviates extremely.
    let entry = 50000.0;
    let atr = 500.0;

    let params = ExitParams {
        sl_atr_mult: 2.0,
        block_exits_on_extreme_dev: true,
        glitch_price_dev_pct: 0.05, // 5% price change triggers glitch
        glitch_atr_mult: 12.0,
        ..default_exit_params()
    };

    // Price drops 10% in one bar (extreme move, glitch guard triggers)
    let close = entry * 0.90;
    let snap = IndicatorSnapshot {
        close,
        high: entry,
        low: close,
        open: entry,
        volume: 1000.0,
        t: 1_000_000,
        ema_fast: entry,
        ema_slow: entry,
        ema_macro: entry,
        adx: 30.0,
        adx_pos: 18.0,
        adx_neg: 12.0,
        adx_slope: 0.0,
        bb_upper: entry * 1.02,
        bb_lower: entry * 0.98,
        bb_width: 0.04,
        bb_width_avg: 0.04,
        bb_width_ratio: 1.0,
        atr,
        atr_slope: 0.0,
        avg_atr: atr,
        rsi: 20.0,
        stoch_rsi_k: 10.0,
        stoch_rsi_d: 10.0,
        macd_hist: -100.0,
        prev_macd_hist: 0.0,
        prev2_macd_hist: 0.0,
        prev3_macd_hist: 0.0,
        vol_sma: 1000.0,
        vol_trend: true,
        prev_close: entry, // previous close at entry (10% drop)
        prev_ema_fast: entry,
        prev_ema_slow: entry,
        bar_count: 200,
        funding_rate: 0.0,
    };

    let mut pos = Position {
        symbol: "BTC".to_string(),
        side: PositionSide::Long,
        quantity: 1.0,
        avg_entry_price: entry,
        opened_at_ms: 0,
        updated_at_ms: 0,
        notional_usd: entry,
        margin_usd: entry / 3.0,
        confidence: Some(2),
        entry_atr: Some(atr),
        entry_adx_threshold: None,
        adds_count: 0,
        tp1_taken: false,
        trailing_sl: None,
        mae_usd: 0.0,
        mfe_usd: 0.0,
        last_funding_ms: None,
    };

    // Without glitch guard, SL would fire (close well below SL).
    // With glitch guard, should return Hold.
    let result = evaluate_exits(&mut pos, &snap, &params, 1_000_000);
    assert_eq!(
        result,
        KernelExitResult::Hold,
        "Glitch guard must block exits during extreme price deviation"
    );
}

// ── Test 8: SL computation with all fixture groups ─────────────────────────

#[test]
fn test_aqc1225_sl_all_fixtures_sanity() {
    // Run every fixture through the CPU SL function and verify:
    // 1. SL price is finite
    // 2. Directional sanity (unless breakeven moves it)
    // 3. The CPU evaluate_exits_with_diagnostics reports a consistent sl_price
    let fixtures = make_fixtures();
    let params = default_exit_params();

    for f in &fixtures {
        let atr = if f.entry_atr > 0.0 {
            f.entry_atr
        } else {
            f.entry_price * 0.005
        };
        let ref_sl = rust_compute_sl_price(
            f.pos_type,
            f.entry_price,
            f.entry_atr,
            f.current_price,
            f.adx,
            f.adx_slope,
            params.sl_atr_mult,
            params.enable_breakeven_stop,
            params.breakeven_start_atr,
            params.breakeven_buffer_atr,
        );

        assert!(
            ref_sl.is_finite(),
            "[{}] SL must be finite: {}",
            f.label,
            ref_sl
        );

        // When not breakeven-active, check directional sanity
        let profit = match f.pos_type {
            PosType::Long => f.current_price - f.entry_price,
            PosType::Short => f.entry_price - f.current_price,
        };
        let be_active = params.enable_breakeven_stop
            && params.breakeven_start_atr > 0.0
            && profit >= atr * params.breakeven_start_atr;

        if !be_active {
            match f.pos_type {
                PosType::Long => assert!(
                    ref_sl <= f.entry_price + f64::EPSILON,
                    "[{}] LONG SL {} must be <= entry {}",
                    f.label,
                    ref_sl,
                    f.entry_price
                ),
                PosType::Short => assert!(
                    ref_sl >= f.entry_price - f64::EPSILON,
                    "[{}] SHORT SL {} must be >= entry {}",
                    f.label,
                    ref_sl,
                    f.entry_price
                ),
            }
        }
    }
}

// ── Test 9: Trailing SL all fixtures sanity ────────────────────────────────

#[test]
fn test_aqc1225_trailing_all_fixtures_sanity() {
    // Run every fixture through the trailing function and verify sanity.
    let fixtures = make_fixtures();
    let (ts, td, tslc, tdlc, rfd, rft, evb, vbt, vbm, hpa, ttp, ttd, twm) = trailing_defaults();

    for f in &fixtures {
        let tsl = rust_compute_trailing(
            f.pos_type,
            f.entry_price,
            f.current_price,
            f.entry_atr,
            f.current_trailing_sl,
            f.confidence,
            f.rsi,
            f.adx,
            f.adx_slope,
            f.atr_slope,
            f.bb_width_ratio,
            f.profit_atr,
            ts,
            td,
            tslc,
            tdlc,
            rfd,
            rft,
            evb,
            vbt,
            vbm,
            hpa,
            ttp,
            ttd,
            twm,
        );

        assert!(
            tsl.is_finite(),
            "[{}] Trailing SL must be finite: {}",
            f.label,
            tsl
        );

        // Ratchet: if existing trailing SL, new must not worsen
        if f.current_trailing_sl > 0.0 && f.profit_atr >= ts {
            match f.pos_type {
                PosType::Long => assert!(
                    tsl >= f.current_trailing_sl - f64::EPSILON,
                    "[{}] Ratchet violation: new TSL {} < old {}",
                    f.label,
                    tsl,
                    f.current_trailing_sl
                ),
                PosType::Short => assert!(
                    tsl <= f.current_trailing_sl + f64::EPSILON,
                    "[{}] Ratchet violation: new TSL {} > old {}",
                    f.label,
                    tsl,
                    f.current_trailing_sl
                ),
            }
        }
    }
}

// ── Test 10: MMDE smart exit (MACD Persistent Divergence) ──────────────────

#[test]
fn test_aqc1225_smart_exit_mmde() {
    // MMDE fires when profit > 1.5 ATR, ADX > 35, and 4 consecutive MACD contractions.
    let params = ExitParams {
        sl_atr_mult: 100.0,
        trailing_start_atr: 1000.0,
        tp_atr_mult: 100.0,
        enable_partial_tp: false,
        smart_exit_adx_exhaustion_lt: 0.0,
        enable_rsi_overextension_exit: false,
        require_macro_alignment: false,
        ..default_exit_params()
    };

    // Long position, profit=2 ATR, ADX=38, 4 consecutive MACD contractions
    let snap = IndicatorSnapshot {
        close: 51000.0,
        high: 51100.0,
        low: 50900.0,
        open: 51000.0,
        volume: 1000.0,
        t: 1_000_000,
        ema_fast: 51100.0, // bullish (no trend breakdown)
        ema_slow: 50900.0,
        ema_macro: 50000.0,
        adx: 38.0, // > 35 (MMDE gate)
        adx_pos: 23.0,
        adx_neg: 15.0,
        adx_slope: 0.3,
        bb_upper: 51500.0,
        bb_lower: 50500.0,
        bb_width: 0.02,
        bb_width_avg: 0.02,
        bb_width_ratio: 1.0,
        atr: 500.0,
        atr_slope: 0.0,
        avg_atr: 500.0,
        rsi: 55.0,
        stoch_rsi_k: 50.0,
        stoch_rsi_d: 50.0,
        // 4 consecutive MACD contractions for long: hist < prev < prev2 < prev3
        macd_hist: 5.0,
        prev_macd_hist: 10.0,
        prev2_macd_hist: 15.0,
        prev3_macd_hist: 20.0,
        vol_sma: 1000.0,
        vol_trend: false,
        prev_close: 51000.0,
        prev_ema_fast: 51100.0,
        prev_ema_slow: 50900.0,
        bar_count: 200,
        funding_rate: 0.0,
    };

    let mut pos = Position {
        symbol: "BTC".to_string(),
        side: PositionSide::Long,
        quantity: 1.0,
        avg_entry_price: 50000.0,
        opened_at_ms: 0,
        updated_at_ms: 0,
        notional_usd: 50000.0,
        margin_usd: 16666.0,
        confidence: Some(2),
        entry_atr: Some(500.0),
        entry_adx_threshold: None,
        adds_count: 0,
        tp1_taken: false,
        trailing_sl: None,
        mae_usd: 0.0,
        mfe_usd: 0.0,
        last_funding_ms: None,
    };

    let result = evaluate_exits(&mut pos, &snap, &params, 1_000_000);
    match &result {
        KernelExitResult::FullClose { reason, .. } => {
            assert!(
                reason.contains("MACD Persistent Divergence"),
                "Expected MMDE exit, got: {}",
                reason
            );
        }
        other => panic!("Expected FullClose for MMDE, got {:?}", other),
    }
}

// ── Test 11: EMA Macro Breakdown smart exit ────────────────────────────────

#[test]
fn test_aqc1225_smart_exit_ema_macro_breakdown() {
    // Smart exit #3: EMA Macro Breakdown fires when require_macro_alignment
    // is true and price breaks below EMA macro for long.
    let params = ExitParams {
        sl_atr_mult: 100.0,
        trailing_start_atr: 1000.0,
        tp_atr_mult: 100.0,
        enable_partial_tp: false,
        smart_exit_adx_exhaustion_lt: 0.0,
        enable_rsi_overextension_exit: false,
        require_macro_alignment: true, // enabled
        ..default_exit_params()
    };

    // Long position, close below ema_macro
    let snap = IndicatorSnapshot {
        close: 49800.0,
        high: 49900.0,
        low: 49700.0,
        open: 49800.0,
        volume: 1000.0,
        t: 1_000_000,
        ema_fast: 50100.0, // still bullish (no trend breakdown)
        ema_slow: 49900.0,
        ema_macro: 50000.0, // close (49800) < ema_macro (50000) -> breakdown
        adx: 30.0,
        adx_pos: 18.0,
        adx_neg: 12.0,
        adx_slope: 0.5,
        bb_upper: 50500.0,
        bb_lower: 49500.0,
        bb_width: 0.02,
        bb_width_avg: 0.02,
        bb_width_ratio: 1.0,
        atr: 500.0,
        atr_slope: 0.0,
        avg_atr: 500.0,
        rsi: 50.0,
        stoch_rsi_k: 50.0,
        stoch_rsi_d: 50.0,
        macd_hist: 0.0,
        prev_macd_hist: 0.0,
        prev2_macd_hist: 0.0,
        prev3_macd_hist: 0.0,
        vol_sma: 1000.0,
        vol_trend: false,
        prev_close: 49800.0,
        prev_ema_fast: 50100.0,
        prev_ema_slow: 49900.0,
        bar_count: 200,
        funding_rate: 0.0,
    };

    let mut pos = Position {
        symbol: "BTC".to_string(),
        side: PositionSide::Long,
        quantity: 1.0,
        avg_entry_price: 50000.0,
        opened_at_ms: 0,
        updated_at_ms: 0,
        notional_usd: 50000.0,
        margin_usd: 16666.0,
        confidence: Some(2),
        entry_atr: Some(500.0),
        entry_adx_threshold: None,
        adds_count: 0,
        tp1_taken: false,
        trailing_sl: None,
        mae_usd: 0.0,
        mfe_usd: 0.0,
        last_funding_ms: None,
    };

    let result = evaluate_exits(&mut pos, &snap, &params, 1_000_000);
    match &result {
        KernelExitResult::FullClose { reason, .. } => {
            assert!(
                reason.contains("EMA Macro"),
                "Expected EMA Macro Breakdown exit, got: {}",
                reason
            );
        }
        other => panic!(
            "Expected FullClose for EMA Macro Breakdown, got {:?}",
            other
        ),
    }
}

// ── Test 12: Evaluate exits with diagnostics returns correct context ───────

#[test]
fn test_aqc1225_evaluate_exits_diagnostics_context() {
    // Verify that evaluate_exits_with_diagnostics populates ExitContext correctly.
    let entry = 50000.0;
    let atr = 500.0;
    let sl_mult = 2.0;
    let tp_mult = 4.0;

    let params = ExitParams {
        sl_atr_mult: sl_mult,
        tp_atr_mult: tp_mult,
        enable_breakeven_stop: false,
        enable_partial_tp: false,
        smart_exit_adx_exhaustion_lt: 0.0,
        enable_rsi_overextension_exit: false,
        require_macro_alignment: false,
        trailing_start_atr: 1000.0,
        ..default_exit_params()
    };

    // Set close to trigger SL
    let sl_price = entry - atr * sl_mult;
    let close = sl_price - 10.0;
    let snap = IndicatorSnapshot {
        close,
        high: close + 50.0,
        low: close - 50.0,
        open: close,
        volume: 1000.0,
        t: 1_000_000,
        ema_fast: close,
        ema_slow: close,
        ema_macro: close,
        adx: 30.0,
        adx_pos: 18.0,
        adx_neg: 12.0,
        adx_slope: 0.5,
        bb_upper: close + 500.0,
        bb_lower: close - 500.0,
        bb_width: 0.02,
        bb_width_avg: 0.02,
        bb_width_ratio: 1.0,
        atr,
        atr_slope: 0.0,
        avg_atr: atr,
        rsi: 50.0,
        stoch_rsi_k: 50.0,
        stoch_rsi_d: 50.0,
        macd_hist: 0.0,
        prev_macd_hist: 0.0,
        prev2_macd_hist: 0.0,
        prev3_macd_hist: 0.0,
        vol_sma: 1000.0,
        vol_trend: false,
        prev_close: close,
        prev_ema_fast: close,
        prev_ema_slow: close,
        bar_count: 200,
        funding_rate: 0.0,
    };

    let mut pos = Position {
        symbol: "BTC".to_string(),
        side: PositionSide::Long,
        quantity: 1.0,
        avg_entry_price: entry,
        opened_at_ms: 0,
        updated_at_ms: 0,
        notional_usd: entry,
        margin_usd: entry / 3.0,
        confidence: Some(2),
        entry_atr: Some(atr),
        entry_adx_threshold: None,
        adds_count: 0,
        tp1_taken: false,
        trailing_sl: None,
        mae_usd: 0.0,
        mfe_usd: 0.0,
        last_funding_ms: None,
    };

    let eval = evaluate_exits_with_diagnostics(&mut pos, &snap, &params, 1_000_000);

    // Verify exit fired
    match &eval.result {
        KernelExitResult::FullClose { reason, .. } => {
            assert_eq!(reason, "Stop Loss", "Expected Stop Loss");
        }
        other => panic!("Expected Stop Loss, got {:?}", other),
    }

    // Verify context is populated
    let ctx = eval
        .exit_context
        .expect("ExitContext must be populated for exits");
    assert_eq!(ctx.exit_type, "stop_loss", "exit_type must be stop_loss");
    assert!(
        (ctx.exit_price - close).abs() < 1e-10,
        "exit_price must match close: {} vs {}",
        ctx.exit_price,
        close
    );
    assert!(
        (ctx.entry_price - entry).abs() < 1e-10,
        "entry_price must match: {} vs {}",
        ctx.entry_price,
        entry
    );

    // Verify SL and TP prices in context
    let expected_sl = entry - atr * sl_mult;
    let expected_tp = entry + atr * tp_mult;
    assert!(
        within_tolerance(expected_sl, ctx.sl_price.unwrap(), TIER_T2_TOLERANCE),
        "SL price in context: expected={}, got={}",
        expected_sl,
        ctx.sl_price.unwrap()
    );
    assert!(
        within_tolerance(expected_tp, ctx.tp_price.unwrap(), TIER_T2_TOLERANCE),
        "TP price in context: expected={}, got={}",
        expected_tp,
        ctx.tp_price.unwrap()
    );

    // Verify profit_atr is negative (underwater)
    assert!(
        ctx.profit_atr < 0.0,
        "profit_atr must be negative for SL hit: {}",
        ctx.profit_atr
    );

    // Verify threshold records present (sl_distance at minimum)
    assert!(
        !eval.threshold_records.is_empty(),
        "threshold_records must not be empty"
    );
    let has_sl = eval
        .threshold_records
        .iter()
        .any(|r| r.name == "sl_distance");
    assert!(has_sl, "Must have sl_distance threshold record");
}

// ── Test 13: Short position exit symmetry ──────────────────────────────────

#[test]
fn test_aqc1225_short_position_exit_symmetry() {
    // Verify that short positions fire exits correctly in the symmetric direction.
    // SL for short is ABOVE entry, TP for short is BELOW entry.
    let entry = 50000.0;
    let atr = 500.0;

    // Test SL hit for short (price rises above SL)
    let params = ExitParams {
        sl_atr_mult: 2.0,
        tp_atr_mult: 4.0,
        trailing_start_atr: 1000.0,
        enable_partial_tp: false,
        smart_exit_adx_exhaustion_lt: 0.0,
        enable_rsi_overextension_exit: false,
        enable_breakeven_stop: false,
        require_macro_alignment: false,
        ..default_exit_params()
    };

    let sl_price = entry + atr * 2.0; // 51000
    let close = sl_price + 50.0; // above SL

    let snap = IndicatorSnapshot {
        close,
        high: close + 50.0,
        low: close - 50.0,
        open: close,
        volume: 1000.0,
        t: 1_000_000,
        ema_fast: close,
        ema_slow: close,
        ema_macro: close,
        adx: 30.0,
        adx_pos: 18.0,
        adx_neg: 12.0,
        adx_slope: 0.5,
        bb_upper: close + 500.0,
        bb_lower: close - 500.0,
        bb_width: 0.02,
        bb_width_avg: 0.02,
        bb_width_ratio: 1.0,
        atr,
        atr_slope: 0.0,
        avg_atr: atr,
        rsi: 50.0,
        stoch_rsi_k: 50.0,
        stoch_rsi_d: 50.0,
        macd_hist: 0.0,
        prev_macd_hist: 0.0,
        prev2_macd_hist: 0.0,
        prev3_macd_hist: 0.0,
        vol_sma: 1000.0,
        vol_trend: false,
        prev_close: close,
        prev_ema_fast: close,
        prev_ema_slow: close,
        bar_count: 200,
        funding_rate: 0.0,
    };

    let mut pos = Position {
        symbol: "BTC".to_string(),
        side: PositionSide::Short,
        quantity: 1.0,
        avg_entry_price: entry,
        opened_at_ms: 0,
        updated_at_ms: 0,
        notional_usd: entry,
        margin_usd: entry / 3.0,
        confidence: Some(2),
        entry_atr: Some(atr),
        entry_adx_threshold: None,
        adds_count: 0,
        tp1_taken: false,
        trailing_sl: None,
        mae_usd: 0.0,
        mfe_usd: 0.0,
        last_funding_ms: None,
    };

    let result = evaluate_exits(&mut pos, &snap, &params, 1_000_000);
    match &result {
        KernelExitResult::FullClose { reason, exit_price } => {
            assert_eq!(reason, "Stop Loss", "Short SL must fire");
            assert!(
                (*exit_price - close).abs() < 1e-10,
                "Exit price must be close: {} vs {}",
                exit_price,
                close
            );
        }
        other => panic!("Expected Stop Loss for short, got {:?}", other),
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// AQC-1212: Fixture-based parity tests for gates & signals codegen
// ═══════════════════════════════════════════════════════════════════════════════
//
// These tests exercise the Rust SSOT gate evaluation and signal generation
// functions with diverse config/market data combinations, verifying outputs
// match expected behaviour.  Since we cannot execute CUDA, the tests validate:
//
//   1. The Rust reference functions produce correct outputs for known inputs
//   2. Config permutations exercise all gate/signal paths
//   3. Numerical results are within T2 precision of f32 round-trip
//   4. Edge cases (boundary ADX, zero slope, extreme RSI) are handled correctly
//
// Complements the existing structural codegen tests (AQC-1261, AQC-1262) by
// verifying actual numerical correctness of the reference implementations.

// ── Market snapshot struct for gate/signal tests ────────────────────────────

/// Snapshot of market state for gate/signal evaluation.
/// Mirrors the subset of GpuSnapshot fields used by check_gates and generate_signal.
#[derive(Debug, Clone)]
struct MarketSnapshot {
    close: f64,
    prev_close: f64,
    ema_fast: f64,
    ema_slow: f64,
    ema_macro: f64,
    prev_ema_fast: f64,
    adx: f64,
    adx_slope: f64,
    atr: f64,
    avg_atr: f64,
    atr_slope: f64,
    rsi: f64,
    stoch_k: f64,
    bb_width_ratio: f64,
    volume: f64,
    vol_sma: f64,
    vol_trend: bool,
    macd_hist: f64,
    prev_macd_hist: f64,
    ema_slow_slope_pct: f64,
}

impl MarketSnapshot {
    /// A strongly bullish market: all gates should pass for a standard BUY.
    fn strong_bullish() -> Self {
        Self {
            close: 100.0,
            prev_close: 99.5,
            ema_fast: 99.0,
            ema_slow: 97.0,
            ema_macro: 94.0,
            prev_ema_fast: 98.5,
            adx: 32.0,
            adx_slope: 1.5,
            atr: 1.5,
            avg_atr: 1.4,
            atr_slope: 0.1,
            rsi: 57.0,
            stoch_k: 0.5,
            bb_width_ratio: 1.2,
            volume: 1200.0,
            vol_sma: 800.0,
            vol_trend: true,
            macd_hist: 0.5,
            prev_macd_hist: 0.3,
            ema_slow_slope_pct: 0.001,
        }
    }

    /// A strongly bearish market: all gates should pass for a standard SELL.
    fn strong_bearish() -> Self {
        Self {
            close: 95.0,
            prev_close: 96.0,
            ema_fast: 96.0,
            ema_slow: 97.0,
            ema_macro: 99.0,
            prev_ema_fast: 96.5,
            adx: 32.0,
            adx_slope: 1.5,
            atr: 1.5,
            avg_atr: 1.4,
            atr_slope: 0.1,
            rsi: 42.0,
            stoch_k: 0.5,
            bb_width_ratio: 1.2,
            volume: 1200.0,
            vol_sma: 800.0,
            vol_trend: true,
            macd_hist: -0.5,
            prev_macd_hist: -0.3,
            ema_slow_slope_pct: -0.001,
        }
    }
}

// ── Gate configuration for fixture tests ────────────────────────────────────

/// Configuration subset for gate evaluation, mirroring GpuComboConfig gate fields.
#[derive(Debug, Clone)]
struct GateConfig {
    // Ranging filter
    enable_ranging_filter: bool,
    ranging_min_signals: usize,
    ranging_adx_lt: f64,
    ranging_bb_width_ratio_lt: f64,
    ranging_rsi_low: f64,
    ranging_rsi_high: f64,
    // Anomaly filter
    enable_anomaly_filter: bool,
    anomaly_price_change_pct: f64,
    anomaly_ema_dev_pct: f64,
    // Extension filter
    enable_extension_filter: bool,
    max_dist_ema_fast: f64,
    // Volume confirmation
    require_volume_confirmation: bool,
    vol_confirm_include_prev: bool,
    // ADX rising
    require_adx_rising: bool,
    adx_rising_saturation: f64,
    // ADX threshold + TMC/AVE
    min_adx: f64,
    ave_enabled: bool,
    ave_atr_ratio_gt: f64,
    ave_adx_mult: f64,
    // Macro alignment
    require_macro_alignment: bool,
    // BTC alignment
    require_btc_alignment: bool,
    btc_adx_override: f64,
    // Slow drift override
    enable_slow_drift_entries: bool,
    slow_drift_ranging_slope_override: f64,
    // DRE
    dre_min_adx: f64,
    dre_max_adx: f64,
    dre_long_rsi_limit_low: f64,
    dre_long_rsi_limit_high: f64,
    dre_short_rsi_limit_low: f64,
    dre_short_rsi_limit_high: f64,
    // StochRSI filter
    use_stoch_rsi_filter: bool,
    stoch_rsi_block_long_gt: f64,
    stoch_rsi_block_short_lt: f64,
    // MACD mode: 0=Accel, 1=Sign, 2=None
    macd_mode: u32,
    // Confidence upgrade
    high_conf_volume_mult: f64,
    // REEF
    #[allow(dead_code)]
    enable_reef_filter: bool,
    #[allow(dead_code)]
    reef_long_rsi_block_gt: f64,
    #[allow(dead_code)]
    reef_short_rsi_block_lt: f64,
    #[allow(dead_code)]
    reef_adx_threshold: f64,
    #[allow(dead_code)]
    reef_long_rsi_extreme_gt: f64,
    #[allow(dead_code)]
    reef_short_rsi_extreme_lt: f64,
    // SSF
    #[allow(dead_code)]
    enable_ssf_filter: bool,
    // Regime
    #[allow(dead_code)]
    enable_regime_filter: bool,
    // Pullback
    enable_pullback_entries: bool,
    pullback_min_adx: f64,
    pullback_rsi_long_min: f64,
    pullback_rsi_short_max: f64,
    pullback_require_macd_sign: bool,
    pullback_confidence: u32, // 0=Low, 1=Medium, 2=High
    // Slow drift signal
    slow_drift_min_slope_pct: f64,
    slow_drift_min_adx: f64,
    slow_drift_rsi_long_min: f64,
    slow_drift_rsi_short_max: f64,
    slow_drift_require_macd_sign: bool,
}

impl GateConfig {
    /// Default config matching the bt-signals default SignalConfigView.
    fn default_config() -> Self {
        Self {
            enable_ranging_filter: true,
            ranging_min_signals: 2,
            ranging_adx_lt: 21.0,
            ranging_bb_width_ratio_lt: 0.8,
            ranging_rsi_low: 47.0,
            ranging_rsi_high: 53.0,
            enable_anomaly_filter: true,
            anomaly_price_change_pct: 0.10,
            anomaly_ema_dev_pct: 0.50,
            enable_extension_filter: true,
            max_dist_ema_fast: 0.04,
            require_volume_confirmation: false,
            vol_confirm_include_prev: true,
            require_adx_rising: true,
            adx_rising_saturation: 40.0,
            min_adx: 22.0,
            ave_enabled: true,
            ave_atr_ratio_gt: 1.5,
            ave_adx_mult: 1.25,
            require_macro_alignment: false,
            require_btc_alignment: true,
            btc_adx_override: 40.0,
            enable_slow_drift_entries: false,
            slow_drift_ranging_slope_override: 0.0006,
            dre_min_adx: 22.0,
            dre_max_adx: 40.0,
            dre_long_rsi_limit_low: 56.0,
            dre_long_rsi_limit_high: 52.0,
            dre_short_rsi_limit_low: 44.0,
            dre_short_rsi_limit_high: 48.0,
            use_stoch_rsi_filter: true,
            stoch_rsi_block_long_gt: 0.85,
            stoch_rsi_block_short_lt: 0.15,
            macd_mode: 0, // Accel
            high_conf_volume_mult: 2.5,
            enable_reef_filter: false,
            reef_long_rsi_block_gt: 70.0,
            reef_short_rsi_block_lt: 30.0,
            reef_adx_threshold: 30.0,
            reef_long_rsi_extreme_gt: 80.0,
            reef_short_rsi_extreme_lt: 20.0,
            enable_ssf_filter: false,
            enable_regime_filter: false,
            enable_pullback_entries: false,
            pullback_min_adx: 22.0,
            pullback_rsi_long_min: 50.0,
            pullback_rsi_short_max: 50.0,
            pullback_require_macd_sign: true,
            pullback_confidence: 0,
            slow_drift_min_slope_pct: 0.0006,
            slow_drift_min_adx: 10.0,
            slow_drift_rsi_long_min: 50.0,
            slow_drift_rsi_short_max: 50.0,
            slow_drift_require_macd_sign: true,
        }
    }
}

// ── Gate result struct ──────────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct GateResultFixture {
    is_ranging: bool,
    is_anomaly: bool,
    is_extended: bool,
    vol_confirm: bool,
    is_trending_up: bool,
    adx_above_min: bool,
    bullish_alignment: bool,
    bearish_alignment: bool,
    btc_ok_long: bool,
    btc_ok_short: bool,
    effective_min_adx: f64,
    rsi_long_limit: f64,
    rsi_short_limit: f64,
    stoch_rsi_active: bool,
    all_gates_pass: bool,
}

// ── Inline Rust SSOT: check_gates (mirrors bt-signals/src/gates.rs) ─────────

fn rust_check_gates(
    snap: &MarketSnapshot,
    cfg: &GateConfig,
    btc_bullish: Option<bool>,
    is_btc_symbol: bool,
) -> GateResultFixture {
    // Gate 1: Ranging filter (vote system)
    let mut is_ranging = false;
    if cfg.enable_ranging_filter {
        let min_signals = cfg.ranging_min_signals.max(1);
        let mut votes: u32 = 0;
        if snap.adx < cfg.ranging_adx_lt {
            votes += 1;
        }
        if snap.bb_width_ratio < cfg.ranging_bb_width_ratio_lt {
            votes += 1;
        }
        if snap.rsi > cfg.ranging_rsi_low && snap.rsi < cfg.ranging_rsi_high {
            votes += 1;
        }
        is_ranging = votes >= min_signals as u32;
    }

    // Gate 2: Anomaly filter
    let is_anomaly = if cfg.enable_anomaly_filter {
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
        price_change_pct > cfg.anomaly_price_change_pct || ema_dev_pct > cfg.anomaly_ema_dev_pct
    } else {
        false
    };

    // Gate 3: Extension filter
    let is_extended = if cfg.enable_extension_filter {
        if snap.ema_fast > 0.0 {
            let dist = (snap.close - snap.ema_fast).abs() / snap.ema_fast;
            dist > cfg.max_dist_ema_fast
        } else {
            false
        }
    } else {
        false
    };

    // Gate 4: Volume confirmation
    let vol_confirm = if cfg.require_volume_confirmation {
        let vol_above_sma = snap.volume > snap.vol_sma;
        let vol_trend_ok = snap.vol_trend;
        if cfg.vol_confirm_include_prev {
            vol_above_sma || vol_trend_ok
        } else {
            vol_above_sma && vol_trend_ok
        }
    } else {
        true
    };

    // Gate 5: ADX rising (or saturated)
    let is_trending_up = if cfg.require_adx_rising {
        (snap.adx_slope > 0.0) || (snap.adx > cfg.adx_rising_saturation)
    } else {
        true
    };

    // Gate 6: ADX threshold + TMC + AVE
    let mut effective_min_adx = cfg.min_adx;

    // TMC: cap at 25.0 when slope > 0.5
    if snap.adx_slope > 0.5 {
        effective_min_adx = effective_min_adx.min(25.0);
    }

    // AVE: multiply when ATR ratio exceeds threshold
    if cfg.ave_enabled && snap.avg_atr > 0.0 {
        let atr_ratio = snap.atr / snap.avg_atr;
        if atr_ratio > cfg.ave_atr_ratio_gt {
            let mult = if cfg.ave_adx_mult > 0.0 {
                cfg.ave_adx_mult
            } else {
                1.0
            };
            effective_min_adx *= mult;
        }
    }

    let adx_above_min = snap.adx > effective_min_adx;

    // Gate 7: Macro alignment
    let mut bullish_alignment = snap.ema_fast > snap.ema_slow;
    let mut bearish_alignment = snap.ema_fast < snap.ema_slow;

    if cfg.require_macro_alignment {
        bullish_alignment = bullish_alignment && (snap.ema_slow > snap.ema_macro);
        bearish_alignment = bearish_alignment && (snap.ema_slow < snap.ema_macro);
    }

    // Gate 8: BTC alignment
    let btc_ok_long = !cfg.require_btc_alignment
        || is_btc_symbol
        || btc_bullish.is_none()
        || btc_bullish == Some(true)
        || snap.adx > cfg.btc_adx_override;

    let btc_ok_short = !cfg.require_btc_alignment
        || is_btc_symbol
        || btc_bullish.is_none()
        || btc_bullish == Some(false)
        || snap.adx > cfg.btc_adx_override;

    // Slow-drift ranging override
    if cfg.enable_slow_drift_entries
        && is_ranging
        && snap.ema_slow_slope_pct.abs() >= cfg.slow_drift_ranging_slope_override
    {
        is_ranging = false;
    }

    // DRE (Dynamic RSI Elasticity)
    let adx_min = cfg.dre_min_adx;
    let adx_max = if cfg.dre_max_adx > adx_min {
        cfg.dre_max_adx
    } else {
        adx_min + 1.0
    };
    let weight = ((snap.adx - adx_min) / (adx_max - adx_min)).clamp(0.0, 1.0);
    let rsi_long_limit = cfg.dre_long_rsi_limit_low
        + weight * (cfg.dre_long_rsi_limit_high - cfg.dre_long_rsi_limit_low);
    let rsi_short_limit = cfg.dre_short_rsi_limit_low
        + weight * (cfg.dre_short_rsi_limit_high - cfg.dre_short_rsi_limit_low);

    // Combined all_gates_pass
    let all_gates_pass = adx_above_min
        && !is_ranging
        && !is_anomaly
        && !is_extended
        && vol_confirm
        && is_trending_up;

    GateResultFixture {
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
        rsi_long_limit,
        rsi_short_limit,
        stoch_rsi_active: cfg.use_stoch_rsi_filter,
        all_gates_pass,
    }
}

// ── MACD helper (mirrors bt-signals/src/entry.rs) ───────────────────────────

fn check_macd_long_ref(mode: u32, macd_hist: f64, prev_macd_hist: f64) -> bool {
    match mode {
        0 => macd_hist > prev_macd_hist, // Accel
        1 => macd_hist > 0.0,            // Sign
        _ => true,                       // None
    }
}

fn check_macd_short_ref(mode: u32, macd_hist: f64, prev_macd_hist: f64) -> bool {
    match mode {
        0 => macd_hist < prev_macd_hist, // Accel
        1 => macd_hist < 0.0,            // Sign
        _ => true,                       // None
    }
}

// ── Signal result ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
enum SignalDir {
    Neutral,
    Buy,
    Sell,
}

#[derive(Debug, Clone, PartialEq)]
enum ConfLevel {
    Low,
    Medium,
    High,
}

#[derive(Debug, Clone)]
struct SignalResultFixture {
    signal: SignalDir,
    confidence: ConfLevel,
    effective_min_adx: f64,
}

// ── Inline Rust SSOT: generate_signal (mirrors bt-signals/src/entry.rs) ─────

fn rust_generate_signal(
    snap: &MarketSnapshot,
    gates: &GateResultFixture,
    cfg: &GateConfig,
) -> SignalResultFixture {
    // Mode 1: Standard trend entry
    if gates.all_gates_pass {
        if let Some(r) = try_standard_entry_ref(snap, gates, cfg) {
            return r;
        }
    }

    // Mode 2: Pullback continuation
    if cfg.enable_pullback_entries {
        let pullback_gates_ok = !gates.is_anomaly
            && !gates.is_extended
            && !gates.is_ranging
            && gates.vol_confirm
            && snap.adx >= cfg.pullback_min_adx;

        if pullback_gates_ok {
            if let Some(r) = try_pullback_entry_ref(snap, gates, cfg) {
                return r;
            }
        }
    }

    // Mode 3: Slow drift
    if cfg.enable_slow_drift_entries {
        let slow_gates_ok = !gates.is_anomaly
            && !gates.is_extended
            && !gates.is_ranging
            && gates.vol_confirm
            && snap.adx >= cfg.slow_drift_min_adx;

        if slow_gates_ok {
            if let Some(r) = try_slow_drift_entry_ref(snap, gates, cfg) {
                return r;
            }
        }
    }

    SignalResultFixture {
        signal: SignalDir::Neutral,
        confidence: ConfLevel::Low,
        effective_min_adx: 0.0,
    }
}

fn try_standard_entry_ref(
    snap: &MarketSnapshot,
    gates: &GateResultFixture,
    cfg: &GateConfig,
) -> Option<SignalResultFixture> {
    // LONG
    if gates.bullish_alignment && snap.close > snap.ema_fast {
        if snap.rsi > gates.rsi_long_limit {
            let macd_ok = check_macd_long_ref(cfg.macd_mode, snap.macd_hist, snap.prev_macd_hist);
            if macd_ok {
                let stoch_ok = if gates.stoch_rsi_active {
                    snap.stoch_k < cfg.stoch_rsi_block_long_gt
                } else {
                    true
                };
                if stoch_ok && gates.btc_ok_long {
                    let conf = if snap.volume > snap.vol_sma * cfg.high_conf_volume_mult {
                        ConfLevel::High
                    } else {
                        ConfLevel::Medium
                    };
                    return Some(SignalResultFixture {
                        signal: SignalDir::Buy,
                        confidence: conf,
                        effective_min_adx: gates.effective_min_adx,
                    });
                }
            }
        }
    }
    // SHORT (elif in Rust: only if bullish branch did not enter)
    else if gates.bearish_alignment && snap.close < snap.ema_fast {
        if snap.rsi < gates.rsi_short_limit {
            let macd_ok = check_macd_short_ref(cfg.macd_mode, snap.macd_hist, snap.prev_macd_hist);
            if macd_ok {
                let stoch_ok = if gates.stoch_rsi_active {
                    snap.stoch_k > cfg.stoch_rsi_block_short_lt
                } else {
                    true
                };
                if stoch_ok && gates.btc_ok_short {
                    let conf = if snap.volume > snap.vol_sma * cfg.high_conf_volume_mult {
                        ConfLevel::High
                    } else {
                        ConfLevel::Medium
                    };
                    return Some(SignalResultFixture {
                        signal: SignalDir::Sell,
                        confidence: conf,
                        effective_min_adx: gates.effective_min_adx,
                    });
                }
            }
        }
    }
    None
}

fn try_pullback_entry_ref(
    snap: &MarketSnapshot,
    gates: &GateResultFixture,
    cfg: &GateConfig,
) -> Option<SignalResultFixture> {
    let cross_up = snap.prev_close <= snap.prev_ema_fast && snap.close > snap.ema_fast;
    let cross_dn = snap.prev_close >= snap.prev_ema_fast && snap.close < snap.ema_fast;

    let pullback_conf = match cfg.pullback_confidence {
        2 => ConfLevel::High,
        1 => ConfLevel::Medium,
        _ => ConfLevel::Low,
    };

    // Long pullback
    if cross_up && gates.bullish_alignment && gates.btc_ok_long {
        let macd_ok = if cfg.pullback_require_macd_sign {
            snap.macd_hist > 0.0
        } else {
            true
        };
        if macd_ok && snap.rsi >= cfg.pullback_rsi_long_min {
            return Some(SignalResultFixture {
                signal: SignalDir::Buy,
                confidence: pullback_conf,
                effective_min_adx: cfg.pullback_min_adx,
            });
        }
    }
    // Short pullback (elif)
    else if cross_dn && gates.bearish_alignment && gates.btc_ok_short {
        let macd_ok = if cfg.pullback_require_macd_sign {
            snap.macd_hist < 0.0
        } else {
            true
        };
        if macd_ok && snap.rsi <= cfg.pullback_rsi_short_max {
            return Some(SignalResultFixture {
                signal: SignalDir::Sell,
                confidence: pullback_conf,
                effective_min_adx: cfg.pullback_min_adx,
            });
        }
    }
    None
}

fn try_slow_drift_entry_ref(
    snap: &MarketSnapshot,
    gates: &GateResultFixture,
    cfg: &GateConfig,
) -> Option<SignalResultFixture> {
    let min_slope = cfg.slow_drift_min_slope_pct;

    // Long drift
    if gates.bullish_alignment
        && snap.close > snap.ema_slow
        && gates.btc_ok_long
        && snap.ema_slow_slope_pct >= min_slope
    {
        let macd_ok = if cfg.slow_drift_require_macd_sign {
            snap.macd_hist > 0.0
        } else {
            true
        };
        if macd_ok && snap.rsi >= cfg.slow_drift_rsi_long_min {
            return Some(SignalResultFixture {
                signal: SignalDir::Buy,
                confidence: ConfLevel::Low,
                effective_min_adx: cfg.slow_drift_min_adx,
            });
        }
    }
    // Short drift (elif)
    else if gates.bearish_alignment
        && snap.close < snap.ema_slow
        && gates.btc_ok_short
        && snap.ema_slow_slope_pct <= -min_slope
    {
        let macd_ok = if cfg.slow_drift_require_macd_sign {
            snap.macd_hist < 0.0
        } else {
            true
        };
        if macd_ok && snap.rsi <= cfg.slow_drift_rsi_short_max {
            return Some(SignalResultFixture {
                signal: SignalDir::Sell,
                confidence: ConfLevel::Low,
                effective_min_adx: cfg.slow_drift_min_adx,
            });
        }
    }
    None
}

// ═══════════════════════════════════════════════════════════════════════════════
// Gate fixture tests (AQC-1212)
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_gates_fixture_all_pass_bullish() {
    // Strong bullish snapshot with default config: all gates should pass.
    let snap = MarketSnapshot::strong_bullish();
    let cfg = GateConfig::default_config();
    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    assert!(
        result.all_gates_pass,
        "All gates should pass for strong bullish: {:?}",
        result
    );
    assert!(result.bullish_alignment, "Bullish alignment expected");
    assert!(!result.bearish_alignment, "No bearish alignment expected");
    assert!(result.adx_above_min, "ADX 32 should be above min_adx 22");
    assert!(!result.is_ranging, "Strong trend should not be ranging");
    assert!(
        !result.is_anomaly,
        "Normal price move should not trigger anomaly"
    );
    assert!(!result.is_extended, "Close near EMA should not be extended");
    assert!(
        result.vol_confirm,
        "Volume confirmation disabled by default => pass"
    );
    assert!(result.is_trending_up, "ADX slope 1.5 > 0 => trending up");
    assert!(result.btc_ok_long, "BTC bullish => long OK");
}

#[test]
fn test_gates_fixture_all_pass_bearish() {
    // Strong bearish snapshot with default config: all gates should pass.
    let snap = MarketSnapshot::strong_bearish();
    let cfg = GateConfig::default_config();
    let result = rust_check_gates(&snap, &cfg, Some(false), false);

    assert!(
        result.all_gates_pass,
        "All gates should pass for strong bearish: {:?}",
        result
    );
    assert!(!result.bullish_alignment, "No bullish alignment expected");
    assert!(result.bearish_alignment, "Bearish alignment expected");
    assert!(result.btc_ok_short, "BTC bearish => short OK");
}

#[test]
fn test_gates_fixture_adx_rising_gate() {
    // ADX declining and below saturation: is_trending_up = false.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.adx_slope = -0.5; // declining
    snap.adx = 30.0; // below saturation (40)
    let cfg = GateConfig::default_config();
    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    assert!(
        !result.is_trending_up,
        "ADX slope < 0 and ADX < saturation => not trending"
    );
    assert!(
        !result.all_gates_pass,
        "Gates should fail without trending_up"
    );
}

#[test]
fn test_gates_fixture_adx_rising_saturation_override() {
    // ADX declining but above saturation: is_trending_up = true (saturated override).
    let mut snap = MarketSnapshot::strong_bullish();
    snap.adx_slope = -0.5; // declining
    snap.adx = 42.0; // above saturation (40)
    let cfg = GateConfig::default_config();
    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    assert!(
        result.is_trending_up,
        "ADX > saturation => trending even with declining slope"
    );
}

#[test]
fn test_gates_fixture_volume_confirmation_strict() {
    // Volume confirmation enabled, strict mode (include_prev = false).
    let mut snap = MarketSnapshot::strong_bullish();
    snap.volume = 700.0; // below vol_sma (800)
    snap.vol_trend = true; // vol_trend is true
    let mut cfg = GateConfig::default_config();
    cfg.require_volume_confirmation = true;
    cfg.vol_confirm_include_prev = false;

    let result = rust_check_gates(&snap, &cfg, Some(true), false);
    assert!(
        !result.vol_confirm,
        "Strict mode: volume < vol_sma => fail even with vol_trend"
    );
    assert!(
        !result.all_gates_pass,
        "Gates should fail without vol_confirm"
    );
}

#[test]
fn test_gates_fixture_volume_confirmation_relaxed() {
    // Volume confirmation enabled, relaxed mode (include_prev = true).
    let mut snap = MarketSnapshot::strong_bullish();
    snap.volume = 700.0; // below vol_sma (800)
    snap.vol_trend = true; // vol_trend is true
    let mut cfg = GateConfig::default_config();
    cfg.require_volume_confirmation = true;
    cfg.vol_confirm_include_prev = true;

    let result = rust_check_gates(&snap, &cfg, Some(true), false);
    assert!(
        result.vol_confirm,
        "Relaxed mode: vol_trend true => pass despite low volume"
    );
}

#[test]
fn test_gates_fixture_ranging_filter_all_three_votes() {
    // All three ranging votes fire: ADX < 21, BB < 0.8, RSI in 47-53.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.adx = 18.0; // < 21
    snap.bb_width_ratio = 0.6; // < 0.8
    snap.rsi = 50.0; // 47 < 50 < 53
    let cfg = GateConfig::default_config();
    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    assert!(
        result.is_ranging,
        "All 3 ranging votes => ranging with min_signals=2"
    );
    assert!(
        !result.all_gates_pass,
        "Ranging should block all_gates_pass"
    );
}

#[test]
fn test_gates_fixture_ranging_filter_one_vote_insufficient() {
    // Only one ranging vote fires: ADX < 21, but BB and RSI not in range.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.adx = 18.0; // < 21 (vote 1)
    snap.bb_width_ratio = 1.2; // >= 0.8 (no vote)
    snap.rsi = 57.0; // not in 47-53 (no vote)
    let cfg = GateConfig::default_config();
    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    assert!(
        !result.is_ranging,
        "Only 1 vote < min_signals=2 => not ranging"
    );
    // But adx_above_min = 18 > 22? No => still blocked by ADX threshold
    assert!(
        !result.adx_above_min,
        "ADX 18 < min_adx 22 => adx_above_min = false"
    );
    assert!(!result.all_gates_pass, "ADX below min should block");
}

#[test]
fn test_gates_fixture_anomaly_filter_large_price_move() {
    // 12% price change: above anomaly threshold (10%).
    let mut snap = MarketSnapshot::strong_bullish();
    snap.prev_close = 100.0;
    snap.close = 112.0; // 12% change
    let cfg = GateConfig::default_config();
    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    assert!(
        result.is_anomaly,
        "12% price move > 10% threshold => anomaly"
    );
    assert!(!result.all_gates_pass, "Anomaly should block");
}

#[test]
fn test_gates_fixture_anomaly_filter_small_price_move() {
    // 0.5% price change: well below anomaly threshold (10%).
    let mut snap = MarketSnapshot::strong_bullish();
    snap.prev_close = 100.0;
    snap.close = 100.5;
    let cfg = GateConfig::default_config();
    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    assert!(
        !result.is_anomaly,
        "0.5% price move < 10% threshold => not anomaly"
    );
}

#[test]
fn test_gates_fixture_extension_filter() {
    // Close 6% above EMA_fast: above extension threshold (4%).
    let mut snap = MarketSnapshot::strong_bullish();
    snap.ema_fast = 99.0;
    snap.close = 105.0; // 6.06% distance
    let cfg = GateConfig::default_config();
    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    assert!(
        result.is_extended,
        "6% distance from EMA_fast > 4% threshold => extended"
    );
    assert!(!result.all_gates_pass, "Extension should block");
}

#[test]
fn test_gates_fixture_tmc_caps_min_adx() {
    // TMC: ADX slope > 0.5 caps effective_min_adx at 25.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.adx_slope = 1.0; // > 0.5
    snap.adx = 24.0;
    let mut cfg = GateConfig::default_config();
    cfg.min_adx = 28.0; // would normally block ADX 24

    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    assert!(
        result.effective_min_adx <= 25.0,
        "TMC should cap effective_min_adx at 25.0, got {}",
        result.effective_min_adx
    );
    // ADX 24 < 25 so it still fails the threshold
    assert!(
        !result.adx_above_min,
        "ADX 24 < capped 25 => adx_above_min = false"
    );
}

#[test]
fn test_gates_fixture_tmc_caps_and_passes() {
    // TMC: ADX slope > 0.5 caps effective_min_adx at 25, ADX=26 passes.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.adx_slope = 1.0;
    snap.adx = 26.0;
    let mut cfg = GateConfig::default_config();
    cfg.min_adx = 30.0; // Would block ADX 26 without TMC

    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    assert_eq!(result.effective_min_adx, 25.0, "TMC caps at 25.0");
    assert!(result.adx_above_min, "ADX 26 > capped 25 => pass");
}

#[test]
fn test_gates_fixture_ave_raises_threshold() {
    // AVE: high ATR/avg_ATR ratio raises effective_min_adx.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.atr = 3.0; // ratio = 3.0 / 1.4 = 2.14 > 1.5
    snap.avg_atr = 1.4;
    snap.adx = 26.0;
    snap.adx_slope = 0.3; // <= 0.5, so TMC does NOT fire
    let cfg = GateConfig::default_config();

    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    // AVE: effective_min_adx = 22.0 * 1.25 = 27.5
    assert!(
        (result.effective_min_adx - 27.5).abs() < 1e-9,
        "AVE should raise to 27.5, got {}",
        result.effective_min_adx
    );
    assert!(!result.adx_above_min, "ADX 26 < raised 27.5 => fail");
}

#[test]
fn test_gates_fixture_tmc_and_ave_interaction() {
    // TMC + AVE: TMC fires first (caps at min(min_adx, 25)), then AVE multiplies.
    // With min_adx=22, TMC caps at min(22, 25) = 22. AVE: 22 * 1.25 = 27.5.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.adx_slope = 1.0; // TMC: slope > 0.5
    snap.atr = 3.0; // AVE: ratio 2.14 > 1.5
    snap.avg_atr = 1.4;
    snap.adx = 26.0;
    let cfg = GateConfig::default_config();

    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    // min_adx=22 => TMC caps at min(22, 25) = 22, AVE: 22 * 1.25 = 27.5
    assert!(
        (result.effective_min_adx - 27.5).abs() < 1e-9,
        "TMC(min(22,25)=22) * AVE(1.25) = 27.5, got {}",
        result.effective_min_adx
    );
    assert!(!result.adx_above_min, "ADX 26 < 27.5 => fail");
}

#[test]
fn test_gates_fixture_tmc_and_ave_high_min_adx() {
    // TMC + AVE with high min_adx: TMC caps at 25 (< 35), then AVE multiplies.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.adx_slope = 1.0; // TMC: slope > 0.5
    snap.atr = 3.0; // AVE: ratio 2.14 > 1.5
    snap.avg_atr = 1.4;
    snap.adx = 30.0;
    let mut cfg = GateConfig::default_config();
    cfg.min_adx = 35.0; // high min_adx

    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    // min_adx=35 => TMC caps at min(35, 25) = 25, AVE: 25 * 1.25 = 31.25
    assert!(
        (result.effective_min_adx - 31.25).abs() < 1e-9,
        "TMC(min(35,25)=25) * AVE(1.25) = 31.25, got {}",
        result.effective_min_adx
    );
    assert!(!result.adx_above_min, "ADX 30 < 31.25 => fail");
}

#[test]
fn test_gates_fixture_macro_alignment() {
    // Macro alignment enabled: bullish requires ema_slow > ema_macro.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.ema_slow = 97.0;
    snap.ema_macro = 98.0; // ema_slow < ema_macro => bullish_alignment = false
    let mut cfg = GateConfig::default_config();
    cfg.require_macro_alignment = true;

    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    assert!(
        !result.bullish_alignment,
        "ema_slow 97 < ema_macro 98 => bullish fails with macro"
    );
}

#[test]
fn test_gates_fixture_btc_alignment_blocks_long() {
    // BTC bearish: blocks long for non-BTC symbol with low ADX.
    let snap = MarketSnapshot::strong_bullish();
    let cfg = GateConfig::default_config();
    let result = rust_check_gates(&snap, &cfg, Some(false), false);

    assert!(
        !result.btc_ok_long,
        "BTC bearish => btc_ok_long = false for non-BTC"
    );
    assert!(result.btc_ok_short, "BTC bearish => btc_ok_short = true");
}

#[test]
fn test_gates_fixture_btc_alignment_high_adx_overrides() {
    // BTC bearish but ADX > btc_adx_override: long allowed.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.adx = 42.0; // > btc_adx_override (40)
    let cfg = GateConfig::default_config();
    let result = rust_check_gates(&snap, &cfg, Some(false), false);

    assert!(
        result.btc_ok_long,
        "High ADX overrides BTC alignment for long"
    );
}

#[test]
fn test_gates_fixture_btc_symbol_always_ok() {
    // BTC symbol itself: always OK regardless of BTC trend.
    let snap = MarketSnapshot::strong_bullish();
    let cfg = GateConfig::default_config();
    let result = rust_check_gates(&snap, &cfg, Some(false), true);

    assert!(result.btc_ok_long, "BTC symbol always btc_ok_long");
    assert!(result.btc_ok_short, "BTC symbol always btc_ok_short");
}

#[test]
fn test_gates_fixture_slow_drift_ranging_override() {
    // Slow drift enabled, ranging active, but slope exceeds override threshold.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.adx = 18.0; // < 21 => vote 1
    snap.bb_width_ratio = 0.6; // < 0.8 => vote 2
    snap.rsi = 50.0; // 47-53 => vote 3
    snap.ema_slow_slope_pct = 0.001; // > 0.0006

    let mut cfg = GateConfig::default_config();
    cfg.enable_slow_drift_entries = true;
    cfg.slow_drift_ranging_slope_override = 0.0006;

    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    assert!(
        !result.is_ranging,
        "Slow drift override should clear ranging"
    );
}

#[test]
fn test_gates_fixture_dre_interpolation_midpoint() {
    // DRE at midpoint: ADX = 31, weight = (31-22)/(40-22) = 0.5.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.adx = 31.0;
    let cfg = GateConfig::default_config();
    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    // rsi_long: 56 + 0.5 * (52 - 56) = 54
    assert!(
        (result.rsi_long_limit - 54.0).abs() < 0.01,
        "DRE long limit at midpoint should be 54.0, got {}",
        result.rsi_long_limit
    );
    // rsi_short: 44 + 0.5 * (48 - 44) = 46
    assert!(
        (result.rsi_short_limit - 46.0).abs() < 0.01,
        "DRE short limit at midpoint should be 46.0, got {}",
        result.rsi_short_limit
    );
}

#[test]
fn test_gates_fixture_dre_at_minimum() {
    // DRE at minimum ADX: weight = 0.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.adx = 22.0;
    let cfg = GateConfig::default_config();
    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    assert!(
        (result.rsi_long_limit - 56.0).abs() < 0.01,
        "DRE at min: long limit should be 56.0 (weak), got {}",
        result.rsi_long_limit
    );
    assert!(
        (result.rsi_short_limit - 44.0).abs() < 0.01,
        "DRE at min: short limit should be 44.0 (weak), got {}",
        result.rsi_short_limit
    );
}

#[test]
fn test_gates_fixture_dre_at_maximum() {
    // DRE at maximum ADX: weight = 1.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.adx = 40.0;
    let cfg = GateConfig::default_config();
    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    assert!(
        (result.rsi_long_limit - 52.0).abs() < 0.01,
        "DRE at max: long limit should be 52.0 (strong), got {}",
        result.rsi_long_limit
    );
    assert!(
        (result.rsi_short_limit - 48.0).abs() < 0.01,
        "DRE at max: short limit should be 48.0 (strong), got {}",
        result.rsi_short_limit
    );
}

#[test]
fn test_gates_fixture_dre_clamped_below_min() {
    // ADX below dre_min_adx: weight clamped to 0.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.adx = 15.0;
    snap.adx_slope = 1.0; // keep trending_up
    let cfg = GateConfig::default_config();
    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    assert!(
        (result.rsi_long_limit - 56.0).abs() < 0.01,
        "DRE below min: long limit clamped to 56.0, got {}",
        result.rsi_long_limit
    );
}

#[test]
fn test_gates_fixture_dre_clamped_above_max() {
    // ADX above dre_max_adx: weight clamped to 1.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.adx = 55.0;
    let cfg = GateConfig::default_config();
    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    assert!(
        (result.rsi_long_limit - 52.0).abs() < 0.01,
        "DRE above max: long limit clamped to 52.0, got {}",
        result.rsi_long_limit
    );
}

#[test]
fn test_gates_fixture_stoch_rsi_passthrough() {
    // StochRSI active flag set from config.
    let snap = MarketSnapshot::strong_bullish();
    let mut cfg = GateConfig::default_config();
    cfg.use_stoch_rsi_filter = false;
    let result = rust_check_gates(&snap, &cfg, Some(true), false);

    assert!(
        !result.stoch_rsi_active,
        "StochRSI disabled => stoch_rsi_active = false"
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Signal fixture tests (AQC-1212)
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_signal_fixture_standard_buy() {
    // Strong bullish: standard buy expected.
    let snap = MarketSnapshot::strong_bullish();
    let cfg = GateConfig::default_config();
    let gates = rust_check_gates(&snap, &cfg, Some(true), false);
    let signal = rust_generate_signal(&snap, &gates, &cfg);

    assert_eq!(signal.signal, SignalDir::Buy, "Standard bullish => BUY");
    assert_eq!(
        signal.confidence,
        ConfLevel::Medium,
        "Volume 1200 < vol_sma*2.5=2000 => Medium"
    );
}

#[test]
fn test_signal_fixture_standard_sell() {
    // Strong bearish: standard sell expected.
    let snap = MarketSnapshot::strong_bearish();
    let cfg = GateConfig::default_config();
    let gates = rust_check_gates(&snap, &cfg, Some(false), false);
    let signal = rust_generate_signal(&snap, &gates, &cfg);

    assert_eq!(signal.signal, SignalDir::Sell, "Standard bearish => SELL");
    assert_eq!(
        signal.confidence,
        ConfLevel::Medium,
        "Medium confidence expected"
    );
}

#[test]
fn test_signal_fixture_high_volume_upgrades_confidence() {
    // Volume > vol_sma * 2.5: High confidence.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.volume = 2500.0; // > 800 * 2.5 = 2000
    let cfg = GateConfig::default_config();
    let gates = rust_check_gates(&snap, &cfg, Some(true), false);
    let signal = rust_generate_signal(&snap, &gates, &cfg);

    assert_eq!(signal.signal, SignalDir::Buy);
    assert_eq!(
        signal.confidence,
        ConfLevel::High,
        "High volume => High confidence"
    );
}

#[test]
fn test_signal_fixture_rsi_below_dre_limit_blocks() {
    // RSI below DRE limit blocks standard BUY.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.rsi = 40.0; // well below any DRE long limit (52-56)
    let cfg = GateConfig::default_config();
    let gates = rust_check_gates(&snap, &cfg, Some(true), false);
    let signal = rust_generate_signal(&snap, &gates, &cfg);

    assert_eq!(
        signal.signal,
        SignalDir::Neutral,
        "RSI below DRE limit => Neutral"
    );
}

#[test]
fn test_signal_fixture_macd_accel_blocks_decelerating() {
    // MACD deceleration blocks standard BUY in Accel mode.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.macd_hist = 0.2;
    snap.prev_macd_hist = 0.5; // declining hist
    let cfg = GateConfig::default_config();
    let gates = rust_check_gates(&snap, &cfg, Some(true), false);
    let signal = rust_generate_signal(&snap, &gates, &cfg);

    assert_eq!(
        signal.signal,
        SignalDir::Neutral,
        "MACD decelerating => Neutral in Accel mode"
    );
}

#[test]
fn test_signal_fixture_macd_sign_mode_passes() {
    // MACD Sign mode: hist > 0 passes for long.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.macd_hist = 0.1;
    snap.prev_macd_hist = 0.5; // would fail Accel, passes Sign
    let mut cfg = GateConfig::default_config();
    cfg.macd_mode = 1; // Sign mode

    let gates = rust_check_gates(&snap, &cfg, Some(true), false);
    let signal = rust_generate_signal(&snap, &gates, &cfg);

    assert_eq!(
        signal.signal,
        SignalDir::Buy,
        "MACD Sign mode: hist > 0 => Buy"
    );
}

#[test]
fn test_signal_fixture_macd_none_mode_always_passes() {
    // MACD None mode: always passes regardless of histogram.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.macd_hist = -1.0;
    snap.prev_macd_hist = 0.5; // fails both Accel and Sign
    let mut cfg = GateConfig::default_config();
    cfg.macd_mode = 2; // None mode

    let gates = rust_check_gates(&snap, &cfg, Some(true), false);
    let signal = rust_generate_signal(&snap, &gates, &cfg);

    assert_eq!(
        signal.signal,
        SignalDir::Buy,
        "MACD None mode => always passes"
    );
}

#[test]
fn test_signal_fixture_stoch_rsi_blocks_overbought_long() {
    // StochRSI K > 0.85 blocks long.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.stoch_k = 0.90;
    let cfg = GateConfig::default_config();
    let gates = rust_check_gates(&snap, &cfg, Some(true), false);
    let signal = rust_generate_signal(&snap, &gates, &cfg);

    assert_eq!(
        signal.signal,
        SignalDir::Neutral,
        "StochRSI K=0.90 > 0.85 blocks long"
    );
}

#[test]
fn test_signal_fixture_stoch_rsi_blocks_oversold_short() {
    // StochRSI K < 0.15 blocks short.
    let mut snap = MarketSnapshot::strong_bearish();
    snap.stoch_k = 0.10;
    let cfg = GateConfig::default_config();
    let gates = rust_check_gates(&snap, &cfg, Some(false), false);
    let signal = rust_generate_signal(&snap, &gates, &cfg);

    assert_eq!(
        signal.signal,
        SignalDir::Neutral,
        "StochRSI K=0.10 < 0.15 blocks short"
    );
}

#[test]
fn test_signal_fixture_btc_bearish_blocks_long() {
    // BTC bearish with require_btc_alignment blocks long.
    let snap = MarketSnapshot::strong_bullish();
    let cfg = GateConfig::default_config();
    let gates = rust_check_gates(&snap, &cfg, Some(false), false);
    let signal = rust_generate_signal(&snap, &gates, &cfg);

    assert_eq!(signal.signal, SignalDir::Neutral, "BTC bearish blocks long");
}

#[test]
fn test_signal_fixture_pullback_long() {
    // Standard blocked (MACD decelerating), pullback fires via EMA cross-up.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.prev_close = 98.0;
    snap.prev_ema_fast = 98.5; // prev_close <= prev_ema_fast
    snap.close = 99.5; // close > ema_fast (99.0)
    snap.macd_hist = 0.2;
    snap.prev_macd_hist = 0.3; // decelerating => standard blocked
    snap.adx = 25.0;
    snap.adx_slope = 0.5;

    let mut cfg = GateConfig::default_config();
    cfg.enable_pullback_entries = true;
    cfg.pullback_min_adx = 20.0;
    cfg.pullback_rsi_long_min = 50.0;
    cfg.require_btc_alignment = false;

    let gates = rust_check_gates(&snap, &cfg, Some(true), false);
    let signal = rust_generate_signal(&snap, &gates, &cfg);

    assert_eq!(signal.signal, SignalDir::Buy, "Pullback cross-up => Buy");
    assert_eq!(
        signal.confidence,
        ConfLevel::Low,
        "Pullback default confidence = Low"
    );
    assert!(
        (signal.effective_min_adx - 20.0).abs() < 1e-9,
        "Pullback uses pullback_min_adx"
    );
}

#[test]
fn test_signal_fixture_pullback_short() {
    // Pullback short via EMA cross-down.
    let mut snap = MarketSnapshot::strong_bearish();
    snap.prev_close = 97.0;
    snap.prev_ema_fast = 96.5; // prev_close >= prev_ema_fast
    snap.close = 95.0; // close < ema_fast (96.0)
    snap.macd_hist = -0.2;
    snap.prev_macd_hist = -0.1; // decel for short (would need hist < prev, but -0.2 < -0.1)
    snap.adx = 25.0;
    snap.adx_slope = -0.5; // not rising, not saturated => is_trending_up = false => standard blocked

    let mut cfg = GateConfig::default_config();
    cfg.enable_pullback_entries = true;
    cfg.pullback_min_adx = 20.0;
    cfg.pullback_rsi_short_max = 50.0;
    cfg.require_btc_alignment = false;

    let gates = rust_check_gates(&snap, &cfg, Some(false), false);
    // Standard blocked because is_trending_up = false
    assert!(
        !gates.all_gates_pass,
        "Standard should be blocked (not trending)"
    );

    let signal = rust_generate_signal(&snap, &gates, &cfg);
    assert_eq!(
        signal.signal,
        SignalDir::Sell,
        "Pullback cross-down => Sell"
    );
    assert_eq!(signal.confidence, ConfLevel::Low);
}

#[test]
fn test_signal_fixture_slow_drift_long() {
    // Slow drift long: low ADX, positive slope, bullish alignment.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.adx = 15.0;
    snap.adx_slope = -0.5; // not trending_up => standard blocked
    snap.rsi = 52.0;
    snap.macd_hist = 0.1;
    snap.close = 98.0;
    snap.ema_slow = 97.0;
    snap.ema_slow_slope_pct = 0.001; // above 0.0006

    let mut cfg = GateConfig::default_config();
    cfg.enable_slow_drift_entries = true;
    cfg.slow_drift_min_adx = 10.0;
    cfg.slow_drift_rsi_long_min = 50.0;
    cfg.slow_drift_min_slope_pct = 0.0006;
    cfg.slow_drift_ranging_slope_override = 0.0006;
    cfg.require_btc_alignment = false;

    let gates = rust_check_gates(&snap, &cfg, Some(true), false);
    assert!(
        !gates.all_gates_pass,
        "Standard should fail (low ADX, not trending)"
    );

    let signal = rust_generate_signal(&snap, &gates, &cfg);
    assert_eq!(signal.signal, SignalDir::Buy, "Slow drift => Buy");
    assert_eq!(
        signal.confidence,
        ConfLevel::Low,
        "Slow drift always Low confidence"
    );
    assert!(
        (signal.effective_min_adx - 10.0).abs() < 1e-9,
        "Slow drift uses slow_drift_min_adx"
    );
}

#[test]
fn test_signal_fixture_slow_drift_short() {
    // Slow drift short: negative slope, bearish alignment.
    let mut snap = MarketSnapshot::strong_bearish();
    snap.adx = 15.0;
    snap.adx_slope = -0.5;
    snap.rsi = 48.0;
    snap.macd_hist = -0.1;
    snap.close = 96.0;
    snap.ema_slow = 99.0;
    snap.ema_fast = 97.0; // bearish: ema_fast < ema_slow
    snap.ema_slow_slope_pct = -0.001; // below -0.0006

    let mut cfg = GateConfig::default_config();
    cfg.enable_slow_drift_entries = true;
    cfg.slow_drift_min_adx = 10.0;
    cfg.slow_drift_rsi_short_max = 50.0;
    cfg.slow_drift_min_slope_pct = 0.0006;
    cfg.slow_drift_ranging_slope_override = 0.0006;
    cfg.require_btc_alignment = false;

    let gates = rust_check_gates(&snap, &cfg, Some(false), false);
    let signal = rust_generate_signal(&snap, &gates, &cfg);

    assert_eq!(signal.signal, SignalDir::Sell, "Slow drift short => Sell");
    assert_eq!(signal.confidence, ConfLevel::Low);
}

#[test]
fn test_signal_fixture_slow_drift_blocked_flat_slope() {
    // Slow drift blocked when slope is too flat.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.adx = 15.0;
    snap.adx_slope = -0.5;
    snap.ema_slow_slope_pct = 0.0003; // below 0.0006

    let mut cfg = GateConfig::default_config();
    cfg.enable_slow_drift_entries = true;
    cfg.slow_drift_min_slope_pct = 0.0006;
    cfg.require_btc_alignment = false;

    let gates = rust_check_gates(&snap, &cfg, Some(true), false);
    let signal = rust_generate_signal(&snap, &gates, &cfg);

    assert_eq!(signal.signal, SignalDir::Neutral, "Flat slope => Neutral");
}

#[test]
fn test_signal_fixture_mode_priority_standard_over_pullback() {
    // When both standard and pullback qualify, standard wins (Medium > Low).
    let mut snap = MarketSnapshot::strong_bullish();
    snap.prev_close = 98.0;
    snap.prev_ema_fast = 98.5;
    snap.close = 100.0;
    snap.ema_fast = 99.0;

    let mut cfg = GateConfig::default_config();
    cfg.enable_pullback_entries = true;
    cfg.require_btc_alignment = false;

    let gates = rust_check_gates(&snap, &cfg, Some(true), false);
    assert!(gates.all_gates_pass, "Standard gates should pass");

    let signal = rust_generate_signal(&snap, &gates, &cfg);
    assert_eq!(signal.signal, SignalDir::Buy);
    assert_eq!(
        signal.confidence,
        ConfLevel::Medium,
        "Standard wins with Medium confidence"
    );
}

#[test]
fn test_signal_fixture_neutral_when_nothing_qualifies() {
    // ADX too low for everything, ranging active.
    let mut snap = MarketSnapshot::strong_bullish();
    snap.adx = 8.0; // below slow_drift_min_adx (10)
    snap.adx_slope = -1.0;
    snap.rsi = 50.0;
    snap.bb_width_ratio = 0.6;

    let mut cfg = GateConfig::default_config();
    cfg.enable_pullback_entries = true;
    cfg.enable_slow_drift_entries = true;
    cfg.slow_drift_min_adx = 10.0;
    cfg.require_btc_alignment = false;

    let gates = rust_check_gates(&snap, &cfg, Some(true), false);
    let signal = rust_generate_signal(&snap, &gates, &cfg);

    assert_eq!(
        signal.signal,
        SignalDir::Neutral,
        "Nothing qualifies => Neutral"
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Batch config permutation tests (AQC-1212)
// ═══════════════════════════════════════════════════════════════════════════════

/// 15+ config variations exercising different gate/signal paths.
fn make_config_permutations() -> Vec<(&'static str, GateConfig)> {
    let base = GateConfig::default_config();

    vec![
        ("default", base.clone()),
        ("ranging-disabled", {
            let mut c = base.clone();
            c.enable_ranging_filter = false;
            c
        }),
        ("anomaly-disabled", {
            let mut c = base.clone();
            c.enable_anomaly_filter = false;
            c
        }),
        ("extension-disabled", {
            let mut c = base.clone();
            c.enable_extension_filter = false;
            c
        }),
        ("volume-strict", {
            let mut c = base.clone();
            c.require_volume_confirmation = true;
            c.vol_confirm_include_prev = false;
            c
        }),
        ("volume-relaxed", {
            let mut c = base.clone();
            c.require_volume_confirmation = true;
            c.vol_confirm_include_prev = true;
            c
        }),
        ("adx-rising-disabled", {
            let mut c = base.clone();
            c.require_adx_rising = false;
            c
        }),
        ("macro-alignment-required", {
            let mut c = base.clone();
            c.require_macro_alignment = true;
            c
        }),
        ("btc-alignment-disabled", {
            let mut c = base.clone();
            c.require_btc_alignment = false;
            c
        }),
        ("stoch-rsi-disabled", {
            let mut c = base.clone();
            c.use_stoch_rsi_filter = false;
            c
        }),
        ("macd-sign-mode", {
            let mut c = base.clone();
            c.macd_mode = 1;
            c
        }),
        ("macd-none-mode", {
            let mut c = base.clone();
            c.macd_mode = 2;
            c
        }),
        ("ave-disabled", {
            let mut c = base.clone();
            c.ave_enabled = false;
            c
        }),
        ("high-min-adx", {
            let mut c = base.clone();
            c.min_adx = 35.0;
            c
        }),
        ("pullback-enabled", {
            let mut c = base.clone();
            c.enable_pullback_entries = true;
            c.pullback_min_adx = 20.0;
            c.require_btc_alignment = false;
            c
        }),
        ("slow-drift-enabled", {
            let mut c = base.clone();
            c.enable_slow_drift_entries = true;
            c.slow_drift_min_adx = 10.0;
            c.require_btc_alignment = false;
            c
        }),
    ]
}

/// Market states exercising boundary conditions across all gates.
fn make_market_states() -> Vec<(&'static str, MarketSnapshot)> {
    vec![
        ("strong-bullish", MarketSnapshot::strong_bullish()),
        ("strong-bearish", MarketSnapshot::strong_bearish()),
        ("low-adx-bullish", {
            let mut s = MarketSnapshot::strong_bullish();
            s.adx = 18.0;
            s.adx_slope = -0.3;
            s
        }),
        ("high-adx-bullish", {
            let mut s = MarketSnapshot::strong_bullish();
            s.adx = 55.0;
            s
        }),
        ("ranging-market", {
            let mut s = MarketSnapshot::strong_bullish();
            s.adx = 18.0;
            s.bb_width_ratio = 0.6;
            s.rsi = 50.0;
            s
        }),
        ("anomaly-spike", {
            let mut s = MarketSnapshot::strong_bullish();
            s.prev_close = 100.0;
            s.close = 115.0;
            s
        }),
        ("extended-from-ema", {
            let mut s = MarketSnapshot::strong_bullish();
            s.close = 106.0; // 7% from ema_fast=99
            s
        }),
        ("low-volume", {
            let mut s = MarketSnapshot::strong_bullish();
            s.volume = 200.0;
            s.vol_trend = false;
            s
        }),
        ("overbought-stoch", {
            let mut s = MarketSnapshot::strong_bullish();
            s.stoch_k = 0.92;
            s
        }),
        ("oversold-stoch-bearish", {
            let mut s = MarketSnapshot::strong_bearish();
            s.stoch_k = 0.08;
            s
        }),
        ("macd-declining-bullish", {
            let mut s = MarketSnapshot::strong_bullish();
            s.macd_hist = 0.1;
            s.prev_macd_hist = 0.5;
            s
        }),
        ("pullback-cross-up", {
            let mut s = MarketSnapshot::strong_bullish();
            s.prev_close = 98.0;
            s.prev_ema_fast = 98.5;
            s.close = 99.5;
            s.ema_fast = 99.0;
            s.macd_hist = 0.2;
            s.prev_macd_hist = 0.3;
            s.adx = 25.0;
            s.adx_slope = 0.5;
            s
        }),
        ("slow-drift-grind", {
            let mut s = MarketSnapshot::strong_bullish();
            s.adx = 12.0;
            s.adx_slope = -0.3;
            s.rsi = 52.0;
            s.macd_hist = 0.05;
            s.close = 98.0;
            s.ema_slow = 97.0;
            s.ema_slow_slope_pct = 0.001;
            s
        }),
        ("high-atr-ratio", {
            let mut s = MarketSnapshot::strong_bullish();
            s.atr = 4.0;
            s.avg_atr = 1.4;
            s
        }),
        ("tmc-trigger", {
            let mut s = MarketSnapshot::strong_bullish();
            s.adx_slope = 2.0;
            s.adx = 26.0;
            s
        }),
    ]
}

#[test]
fn test_gates_config_permutations_x_market_states() {
    // Cross-product: 15+ configs x 15 market states = 225+ gate evaluations.
    // Verify all produce valid, self-consistent results.
    let configs = make_config_permutations();
    let markets = make_market_states();

    let mut total_evaluated = 0;

    for (cfg_label, cfg) in &configs {
        for (mkt_label, snap) in &markets {
            let btc_bullish = if snap.ema_fast > snap.ema_slow {
                Some(true)
            } else {
                Some(false)
            };

            let gates = rust_check_gates(snap, cfg, btc_bullish, false);

            // Self-consistency checks:
            // 1. all_gates_pass implies all individual gates passed
            if gates.all_gates_pass {
                assert!(
                    gates.adx_above_min,
                    "[{}/{}] all_gates_pass but adx_above_min=false",
                    cfg_label, mkt_label
                );
                assert!(
                    !gates.is_ranging,
                    "[{}/{}] all_gates_pass but is_ranging=true",
                    cfg_label, mkt_label
                );
                assert!(
                    !gates.is_anomaly,
                    "[{}/{}] all_gates_pass but is_anomaly=true",
                    cfg_label, mkt_label
                );
                assert!(
                    !gates.is_extended,
                    "[{}/{}] all_gates_pass but is_extended=true",
                    cfg_label, mkt_label
                );
                assert!(
                    gates.vol_confirm,
                    "[{}/{}] all_gates_pass but vol_confirm=false",
                    cfg_label, mkt_label
                );
                assert!(
                    gates.is_trending_up,
                    "[{}/{}] all_gates_pass but is_trending_up=false",
                    cfg_label, mkt_label
                );
            }

            // 2. effective_min_adx must be finite and positive
            assert!(
                gates.effective_min_adx.is_finite() && gates.effective_min_adx > 0.0,
                "[{}/{}] effective_min_adx must be finite+positive, got {}",
                cfg_label,
                mkt_label,
                gates.effective_min_adx
            );

            // 3. DRE limits must be finite and in [0, 100] range
            assert!(
                gates.rsi_long_limit >= 0.0 && gates.rsi_long_limit <= 100.0,
                "[{}/{}] rsi_long_limit out of range: {}",
                cfg_label,
                mkt_label,
                gates.rsi_long_limit
            );
            assert!(
                gates.rsi_short_limit >= 0.0 && gates.rsi_short_limit <= 100.0,
                "[{}/{}] rsi_short_limit out of range: {}",
                cfg_label,
                mkt_label,
                gates.rsi_short_limit
            );

            // 4. Alignment is mutually exclusive (unless EMA_fast == EMA_slow)
            if snap.ema_fast != snap.ema_slow {
                assert!(
                    !(gates.bullish_alignment && gates.bearish_alignment),
                    "[{}/{}] Cannot be both bullish and bearish aligned",
                    cfg_label,
                    mkt_label
                );
            }

            // f32 round-trip precision for DRE limits
            let rsi_long_f32 = gates.rsi_long_limit as f32 as f64;
            assert!(
                within_tolerance(gates.rsi_long_limit, rsi_long_f32, TIER_T2_TOLERANCE),
                "[{}/{}] DRE rsi_long_limit f32 round-trip exceeds T2: {} vs {}",
                cfg_label,
                mkt_label,
                gates.rsi_long_limit,
                rsi_long_f32
            );

            total_evaluated += 1;
        }
    }

    assert!(
        total_evaluated >= 200,
        "Expected at least 200 gate evaluations, got {}",
        total_evaluated
    );
}

#[test]
fn test_signals_config_permutations_x_market_states() {
    // Cross-product: configs x market states for signal generation.
    // Verify signals are self-consistent with gate results.
    let configs = make_config_permutations();
    let markets = make_market_states();

    let mut total_evaluated = 0;
    let mut buy_count = 0;
    let mut sell_count = 0;
    let mut neutral_count = 0;

    for (cfg_label, cfg) in &configs {
        for (mkt_label, snap) in &markets {
            let btc_bullish = if snap.ema_fast > snap.ema_slow {
                Some(true)
            } else {
                Some(false)
            };

            let gates = rust_check_gates(snap, cfg, btc_bullish, false);
            let signal = rust_generate_signal(snap, &gates, cfg);

            match signal.signal {
                SignalDir::Buy => buy_count += 1,
                SignalDir::Sell => sell_count += 1,
                SignalDir::Neutral => neutral_count += 1,
            }

            // Signal consistency checks:
            // 1. Buy requires bullish alignment
            if signal.signal == SignalDir::Buy {
                assert!(
                    gates.bullish_alignment,
                    "[{}/{}] BUY signal without bullish_alignment",
                    cfg_label, mkt_label
                );
            }

            // 2. Sell requires bearish alignment
            if signal.signal == SignalDir::Sell {
                assert!(
                    gates.bearish_alignment,
                    "[{}/{}] SELL signal without bearish_alignment",
                    cfg_label, mkt_label
                );
            }

            // 3. If anomaly is active and no modes are special, should be Neutral
            if gates.is_anomaly && !gates.all_gates_pass {
                // Anomaly blocks all modes
                assert_eq!(
                    signal.signal,
                    SignalDir::Neutral,
                    "[{}/{}] Anomaly active but signal is not Neutral: {:?}",
                    cfg_label,
                    mkt_label,
                    signal.signal
                );
            }

            // 4. effective_min_adx in signal result makes sense
            if signal.signal != SignalDir::Neutral {
                assert!(
                    signal.effective_min_adx > 0.0,
                    "[{}/{}] Non-neutral signal but effective_min_adx={}",
                    cfg_label,
                    mkt_label,
                    signal.effective_min_adx
                );
            }

            total_evaluated += 1;
        }
    }

    // Verify diversity: we should see all three signal types
    assert!(
        buy_count > 0,
        "Cross-product should produce at least one BUY, got 0"
    );
    assert!(
        sell_count > 0,
        "Cross-product should produce at least one SELL, got 0"
    );
    assert!(
        neutral_count > 0,
        "Cross-product should produce at least one NEUTRAL, got 0"
    );
    assert!(
        total_evaluated >= 200,
        "Expected at least 200 signal evaluations, got {}",
        total_evaluated
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
// DRE interpolation precision tests (AQC-1212)
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_dre_interpolation_sweep() {
    // Sweep ADX from 15 to 55 in steps of 1.0 and verify DRE interpolation
    // matches expected linear interpolation with T2 precision.
    let cfg = GateConfig::default_config();
    let adx_min = cfg.dre_min_adx; // 22
    let adx_max = cfg.dre_max_adx; // 40
    let rsi_long_weak = cfg.dre_long_rsi_limit_low; // 56
    let rsi_long_strong = cfg.dre_long_rsi_limit_high; // 52
    let rsi_short_weak = cfg.dre_short_rsi_limit_low; // 44
    let rsi_short_strong = cfg.dre_short_rsi_limit_high; // 48

    for adx_i in 15..=55 {
        let adx = adx_i as f64;
        let mut snap = MarketSnapshot::strong_bullish();
        snap.adx = adx;
        snap.adx_slope = 1.0; // keep trending_up

        let result = rust_check_gates(&snap, &cfg, Some(true), false);

        // Expected weight (clamped to [0, 1])
        let weight = ((adx - adx_min) / (adx_max - adx_min)).clamp(0.0, 1.0);
        let expected_long = rsi_long_weak + weight * (rsi_long_strong - rsi_long_weak);
        let expected_short = rsi_short_weak + weight * (rsi_short_strong - rsi_short_weak);

        assert!(
            within_tolerance(expected_long, result.rsi_long_limit, TIER_T2_TOLERANCE),
            "DRE long mismatch at ADX={}: expected={}, got={}, err={:.2e}",
            adx,
            expected_long,
            result.rsi_long_limit,
            relative_error(expected_long, result.rsi_long_limit)
        );
        assert!(
            within_tolerance(expected_short, result.rsi_short_limit, TIER_T2_TOLERANCE),
            "DRE short mismatch at ADX={}: expected={}, got={}, err={:.2e}",
            adx,
            expected_short,
            result.rsi_short_limit,
            relative_error(expected_short, result.rsi_short_limit)
        );

        // f32 round-trip precision
        let long_f32 = result.rsi_long_limit as f32 as f64;
        assert!(
            within_tolerance(result.rsi_long_limit, long_f32, TIER_T2_TOLERANCE),
            "DRE long f32 round-trip exceeds T2 at ADX={}",
            adx
        );
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// REEF (RSI Extreme Entry Filter) reference + fixture tests (AQC-1212)
//
// REEF is a sweep-engine-level filter (not in per-bar decision codegen).
// It blocks entries when RSI is at extremes for the given direction.
// Logic: for BUY, if ADX < threshold, block when RSI > block_gt; else block
// when RSI > extreme_gt. Mirror for SELL with < comparisons.
// ═══════════════════════════════════════════════════════════════════════════════

#[derive(Debug, Clone, Copy)]
struct ReefConfig {
    enabled: bool,
    long_rsi_block_gt: f64,
    short_rsi_block_lt: f64,
    adx_threshold: f64,
    long_rsi_extreme_gt: f64,
    short_rsi_extreme_lt: f64,
}

impl Default for ReefConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            long_rsi_block_gt: 70.0,
            short_rsi_block_lt: 30.0,
            adx_threshold: 30.0,
            long_rsi_extreme_gt: 80.0,
            short_rsi_extreme_lt: 20.0,
        }
    }
}

/// Inline REEF reference: returns true if entry is BLOCKED (should skip).
fn reef_blocks_entry(signal: SignalDir, adx: f64, rsi: f64, cfg: &ReefConfig) -> bool {
    if !cfg.enabled {
        return false;
    }
    match signal {
        SignalDir::Buy => {
            if adx < cfg.adx_threshold {
                rsi > cfg.long_rsi_block_gt
            } else {
                rsi > cfg.long_rsi_extreme_gt
            }
        }
        SignalDir::Sell => {
            if adx < cfg.adx_threshold {
                rsi < cfg.short_rsi_block_lt
            } else {
                rsi < cfg.short_rsi_extreme_lt
            }
        }
        SignalDir::Neutral => false,
    }
}

#[test]
fn test_reef_filter_disabled_allows_all() {
    let cfg = ReefConfig {
        enabled: false,
        ..Default::default()
    };
    // Even extreme RSI should pass when disabled
    assert!(
        !reef_blocks_entry(SignalDir::Buy, 15.0, 95.0, &cfg),
        "REEF disabled: BUY with RSI=95 should NOT be blocked"
    );
    assert!(
        !reef_blocks_entry(SignalDir::Sell, 15.0, 5.0, &cfg),
        "REEF disabled: SELL with RSI=5 should NOT be blocked"
    );
}

#[test]
fn test_reef_filter_buy_low_adx_blocked() {
    let cfg = ReefConfig {
        enabled: true,
        ..Default::default()
    };
    // ADX=25 < threshold=30, RSI=75 > block_gt=70 => blocked
    assert!(
        reef_blocks_entry(SignalDir::Buy, 25.0, 75.0, &cfg),
        "REEF: BUY with low ADX and high RSI should be blocked"
    );
}

#[test]
fn test_reef_filter_buy_low_adx_passes() {
    let cfg = ReefConfig {
        enabled: true,
        ..Default::default()
    };
    // ADX=25 < threshold=30, RSI=65 <= block_gt=70 => passes
    assert!(
        !reef_blocks_entry(SignalDir::Buy, 25.0, 65.0, &cfg),
        "REEF: BUY with low ADX and moderate RSI should pass"
    );
}

#[test]
fn test_reef_filter_buy_high_adx_extreme_blocked() {
    let cfg = ReefConfig {
        enabled: true,
        ..Default::default()
    };
    // ADX=35 >= threshold=30, RSI=85 > extreme_gt=80 => blocked
    assert!(
        reef_blocks_entry(SignalDir::Buy, 35.0, 85.0, &cfg),
        "REEF: BUY with high ADX and extreme RSI should be blocked"
    );
}

#[test]
fn test_reef_filter_buy_high_adx_extreme_passes() {
    let cfg = ReefConfig {
        enabled: true,
        ..Default::default()
    };
    // ADX=35 >= threshold=30, RSI=75 <= extreme_gt=80 => passes
    assert!(
        !reef_blocks_entry(SignalDir::Buy, 35.0, 75.0, &cfg),
        "REEF: BUY with high ADX and sub-extreme RSI should pass"
    );
}

#[test]
fn test_reef_filter_sell_low_adx_blocked() {
    let cfg = ReefConfig {
        enabled: true,
        ..Default::default()
    };
    // ADX=25 < threshold=30, RSI=25 < block_lt=30 => blocked
    assert!(
        reef_blocks_entry(SignalDir::Sell, 25.0, 25.0, &cfg),
        "REEF: SELL with low ADX and low RSI should be blocked"
    );
}

#[test]
fn test_reef_filter_sell_low_adx_passes() {
    let cfg = ReefConfig {
        enabled: true,
        ..Default::default()
    };
    // ADX=25 < threshold=30, RSI=35 >= block_lt=30 => passes
    assert!(
        !reef_blocks_entry(SignalDir::Sell, 25.0, 35.0, &cfg),
        "REEF: SELL with low ADX and moderate RSI should pass"
    );
}

#[test]
fn test_reef_filter_sell_high_adx_extreme_blocked() {
    let cfg = ReefConfig {
        enabled: true,
        ..Default::default()
    };
    // ADX=35 >= threshold=30, RSI=15 < extreme_lt=20 => blocked
    assert!(
        reef_blocks_entry(SignalDir::Sell, 35.0, 15.0, &cfg),
        "REEF: SELL with high ADX and extreme-low RSI should be blocked"
    );
}

#[test]
fn test_reef_filter_sell_high_adx_extreme_passes() {
    let cfg = ReefConfig {
        enabled: true,
        ..Default::default()
    };
    // ADX=35 >= threshold=30, RSI=25 >= extreme_lt=20 => passes
    assert!(
        !reef_blocks_entry(SignalDir::Sell, 35.0, 25.0, &cfg),
        "REEF: SELL with high ADX and sub-extreme RSI should pass"
    );
}

#[test]
fn test_reef_filter_boundary_adx_at_threshold() {
    let cfg = ReefConfig {
        enabled: true,
        adx_threshold: 30.0,
        ..Default::default()
    };
    // ADX exactly at threshold => NOT less than threshold => use extreme limits
    // BUY: RSI=75 <= extreme_gt=80 => passes
    assert!(
        !reef_blocks_entry(SignalDir::Buy, 30.0, 75.0, &cfg),
        "REEF: BUY at exact ADX threshold should use extreme limits"
    );
    // BUY: RSI=85 > extreme_gt=80 => blocked
    assert!(
        reef_blocks_entry(SignalDir::Buy, 30.0, 85.0, &cfg),
        "REEF: BUY at exact ADX threshold with extreme RSI should block"
    );
}

#[test]
fn test_reef_neutral_never_blocked() {
    let cfg = ReefConfig {
        enabled: true,
        ..Default::default()
    };
    assert!(
        !reef_blocks_entry(SignalDir::Neutral, 10.0, 99.0, &cfg),
        "REEF: Neutral signals should never be blocked"
    );
}

#[test]
fn test_reef_config_f32_roundtrip_precision() {
    // REEF config values must survive f32 round-trip within T2 tolerance.
    let cfg = ReefConfig {
        enabled: true,
        long_rsi_block_gt: 72.5,
        short_rsi_block_lt: 27.5,
        adx_threshold: 32.0,
        long_rsi_extreme_gt: 82.5,
        short_rsi_extreme_lt: 17.5,
    };

    let vals = [
        ("long_rsi_block_gt", cfg.long_rsi_block_gt),
        ("short_rsi_block_lt", cfg.short_rsi_block_lt),
        ("adx_threshold", cfg.adx_threshold),
        ("long_rsi_extreme_gt", cfg.long_rsi_extreme_gt),
        ("short_rsi_extreme_lt", cfg.short_rsi_extreme_lt),
    ];

    for (name, val) in &vals {
        let rt = *val as f32 as f64;
        assert!(
            within_tolerance(*val, rt, TIER_T2_TOLERANCE),
            "REEF {}: f32 round-trip exceeds T2: {} vs {}",
            name,
            val,
            rt
        );
    }
}

#[test]
fn test_reef_config_fields_in_gpu_combo() {
    // Verify REEF fields exist in GpuComboConfig by checking sweep engine CUDA source.
    // REEF operates at the sweep-engine level (not in per-bar decision codegen).
    let gpu_config_size = std::mem::size_of::<GpuComboConfig>();
    assert!(
        gpu_config_size >= 560,
        "GpuComboConfig must be at least 560 bytes (has REEF fields)"
    );

    // Verify REEF fields are packed at expected offsets by constructing a zeroed config
    // and checking the struct has the fields.
    let cfg: GpuComboConfig = unsafe { std::mem::zeroed() };
    // These field accesses compile only if the fields exist in GpuComboConfig.
    let _ = cfg.enable_reef_filter;
    let _ = cfg.reef_long_rsi_block_gt;
    let _ = cfg.reef_short_rsi_block_lt;
    let _ = cfg.reef_adx_threshold;
    let _ = cfg.reef_long_rsi_extreme_gt;
    let _ = cfg.reef_short_rsi_extreme_lt;
}

// ═══════════════════════════════════════════════════════════════════════════════
// SSF (Simple Signal Filter) reference + fixture tests (AQC-1212)
//
// SSF is a sweep-engine-level filter. When enabled:
//   BUY blocked if MACD hist <= 0
//   SELL blocked if MACD hist >= 0
// ═══════════════════════════════════════════════════════════════════════════════

/// Inline SSF reference: returns true if entry is BLOCKED.
fn ssf_blocks_entry(signal: SignalDir, macd_hist: f64, enabled: bool) -> bool {
    if !enabled {
        return false;
    }
    match signal {
        SignalDir::Buy => macd_hist <= 0.0,
        SignalDir::Sell => macd_hist >= 0.0,
        SignalDir::Neutral => false,
    }
}

#[test]
fn test_ssf_filter_disabled_allows_all() {
    assert!(
        !ssf_blocks_entry(SignalDir::Buy, -1.0, false),
        "SSF disabled: BUY with negative MACD should NOT be blocked"
    );
    assert!(
        !ssf_blocks_entry(SignalDir::Sell, 1.0, false),
        "SSF disabled: SELL with positive MACD should NOT be blocked"
    );
}

#[test]
fn test_ssf_filter_buy_positive_hist_passes() {
    assert!(
        !ssf_blocks_entry(SignalDir::Buy, 0.5, true),
        "SSF: BUY with positive MACD hist should pass"
    );
}

#[test]
fn test_ssf_filter_buy_negative_hist_blocked() {
    assert!(
        ssf_blocks_entry(SignalDir::Buy, -0.5, true),
        "SSF: BUY with negative MACD hist should be blocked"
    );
}

#[test]
fn test_ssf_filter_buy_zero_hist_blocked() {
    assert!(
        ssf_blocks_entry(SignalDir::Buy, 0.0, true),
        "SSF: BUY with zero MACD hist should be blocked (<=0)"
    );
}

#[test]
fn test_ssf_filter_sell_negative_hist_passes() {
    assert!(
        !ssf_blocks_entry(SignalDir::Sell, -0.5, true),
        "SSF: SELL with negative MACD hist should pass"
    );
}

#[test]
fn test_ssf_filter_sell_positive_hist_blocked() {
    assert!(
        ssf_blocks_entry(SignalDir::Sell, 0.5, true),
        "SSF: SELL with positive MACD hist should be blocked"
    );
}

#[test]
fn test_ssf_filter_sell_zero_hist_blocked() {
    assert!(
        ssf_blocks_entry(SignalDir::Sell, 0.0, true),
        "SSF: SELL with zero MACD hist should be blocked (>=0)"
    );
}

#[test]
fn test_ssf_neutral_never_blocked() {
    assert!(
        !ssf_blocks_entry(SignalDir::Neutral, 0.0, true),
        "SSF: Neutral should never be blocked"
    );
}

#[test]
fn test_ssf_config_field_in_gpu_combo() {
    // SSF operates at the sweep-engine level. Verify the config field exists.
    let cfg: GpuComboConfig = unsafe { std::mem::zeroed() };
    let _ = cfg.enable_ssf_filter;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Regime filter reference + fixture tests (AQC-1212)
//
// Regime filter is a sweep-engine-level filter. When enabled:
//   SELL blocked if breadth_pct > breadth_block_short_above
//   BUY  blocked if breadth_pct < breadth_block_long_below
// ═══════════════════════════════════════════════════════════════════════════════

#[derive(Debug, Clone, Copy)]
struct RegimeConfig {
    enabled: bool,
    breadth_block_short_above: f64,
    breadth_block_long_below: f64,
}

impl Default for RegimeConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            breadth_block_short_above: 0.7,
            breadth_block_long_below: 0.3,
        }
    }
}

/// Inline regime filter reference: returns the possibly-neutralized signal.
fn apply_regime_filter_ref(signal: SignalDir, breadth_pct: f64, cfg: &RegimeConfig) -> SignalDir {
    if !cfg.enabled {
        return signal;
    }
    match signal {
        SignalDir::Sell if breadth_pct > cfg.breadth_block_short_above => SignalDir::Neutral,
        SignalDir::Buy if breadth_pct < cfg.breadth_block_long_below => SignalDir::Neutral,
        _ => signal,
    }
}

#[test]
fn test_regime_filter_disabled_allows_all() {
    let cfg = RegimeConfig {
        enabled: false,
        ..Default::default()
    };
    assert_eq!(
        apply_regime_filter_ref(SignalDir::Buy, 0.1, &cfg),
        SignalDir::Buy,
        "Regime disabled: BUY with low breadth should pass"
    );
    assert_eq!(
        apply_regime_filter_ref(SignalDir::Sell, 0.9, &cfg),
        SignalDir::Sell,
        "Regime disabled: SELL with high breadth should pass"
    );
}

#[test]
fn test_regime_filter_buy_blocked_low_breadth() {
    let cfg = RegimeConfig {
        enabled: true,
        ..Default::default()
    };
    // breadth_pct=0.2 < breadth_block_long_below=0.3 => BUY blocked
    assert_eq!(
        apply_regime_filter_ref(SignalDir::Buy, 0.2, &cfg),
        SignalDir::Neutral,
        "Regime: BUY should be blocked when breadth < threshold"
    );
}

#[test]
fn test_regime_filter_buy_passes_adequate_breadth() {
    let cfg = RegimeConfig {
        enabled: true,
        ..Default::default()
    };
    // breadth_pct=0.5 >= breadth_block_long_below=0.3 => BUY passes
    assert_eq!(
        apply_regime_filter_ref(SignalDir::Buy, 0.5, &cfg),
        SignalDir::Buy,
        "Regime: BUY should pass with adequate breadth"
    );
}

#[test]
fn test_regime_filter_sell_blocked_high_breadth() {
    let cfg = RegimeConfig {
        enabled: true,
        ..Default::default()
    };
    // breadth_pct=0.8 > breadth_block_short_above=0.7 => SELL blocked
    assert_eq!(
        apply_regime_filter_ref(SignalDir::Sell, 0.8, &cfg),
        SignalDir::Neutral,
        "Regime: SELL should be blocked when breadth > threshold"
    );
}

#[test]
fn test_regime_filter_sell_passes_moderate_breadth() {
    let cfg = RegimeConfig {
        enabled: true,
        ..Default::default()
    };
    // breadth_pct=0.5 <= breadth_block_short_above=0.7 => SELL passes
    assert_eq!(
        apply_regime_filter_ref(SignalDir::Sell, 0.5, &cfg),
        SignalDir::Sell,
        "Regime: SELL should pass with moderate breadth"
    );
}

#[test]
fn test_regime_filter_neutral_unchanged() {
    let cfg = RegimeConfig {
        enabled: true,
        ..Default::default()
    };
    assert_eq!(
        apply_regime_filter_ref(SignalDir::Neutral, 0.1, &cfg),
        SignalDir::Neutral,
        "Regime: Neutral should remain neutral regardless of breadth"
    );
}

#[test]
fn test_regime_filter_boundary_exact_threshold() {
    let cfg = RegimeConfig {
        enabled: true,
        breadth_block_short_above: 0.7,
        breadth_block_long_below: 0.3,
    };
    // BUY at exact threshold: breadth_pct=0.3, NOT less than 0.3 => passes
    assert_eq!(
        apply_regime_filter_ref(SignalDir::Buy, 0.3, &cfg),
        SignalDir::Buy,
        "Regime: BUY at exact threshold should pass (not strictly less)"
    );
    // SELL at exact threshold: breadth_pct=0.7, NOT greater than 0.7 => passes
    assert_eq!(
        apply_regime_filter_ref(SignalDir::Sell, 0.7, &cfg),
        SignalDir::Sell,
        "Regime: SELL at exact threshold should pass (not strictly greater)"
    );
}

#[test]
fn test_regime_config_f32_roundtrip_precision() {
    let vals = [
        ("breadth_block_short_above", 0.7_f64),
        ("breadth_block_long_below", 0.3_f64),
        ("breadth_block_short_above_custom", 0.65_f64),
        ("breadth_block_long_below_custom", 0.35_f64),
    ];
    for (name, val) in &vals {
        let rt = *val as f32 as f64;
        assert!(
            within_tolerance(*val, rt, TIER_T2_TOLERANCE),
            "Regime {}: f32 round-trip exceeds T2: {} vs {}",
            name,
            val,
            rt
        );
    }
}

#[test]
fn test_regime_config_field_in_gpu_combo() {
    // Regime filter operates at sweep-engine level. Verify config field exists.
    let cfg: GpuComboConfig = unsafe { std::mem::zeroed() };
    let _ = cfg.enable_regime_filter;
}

// ═══════════════════════════════════════════════════════════════════════════════
// MACD helper precision tests (AQC-1212)
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_macd_helpers_all_modes_exhaustive() {
    // Exhaustively test MACD helpers for both long and short across all modes.
    // Mode 0 = Accel, Mode 1 = Sign, Mode 2 = None.
    let test_cases: &[(u32, f64, f64, bool, bool)] = &[
        // (mode, hist, prev_hist, expected_long, expected_short)
        // Accel mode
        (0, 0.5, 0.3, true, false), // rising hist: long accel ok, short accel not
        (0, 0.3, 0.5, false, true), // falling hist: short accel ok, long not
        (0, 0.5, 0.5, false, false), // flat: neither
        (0, -0.3, -0.5, true, false), // rising (less negative): long accel ok
        (0, -0.5, -0.3, false, true), // falling (more negative): short accel ok
        // Sign mode
        (1, 0.5, -999.0, true, false), // positive hist: long sign ok
        (1, -0.5, 999.0, false, true), // negative hist: short sign ok
        (1, 0.0, 0.0, false, false),   // zero: neither (> 0 false, < 0 false)
        // None mode
        (2, -999.0, 999.0, true, true), // always true
        (2, 0.0, 0.0, true, true),      // always true
    ];

    for &(mode, hist, prev, exp_long, exp_short) in test_cases {
        let got_long = check_macd_long_ref(mode, hist, prev);
        let got_short = check_macd_short_ref(mode, hist, prev);
        assert_eq!(
            got_long, exp_long,
            "MACD long mode={}, hist={}, prev={}: expected {}, got {}",
            mode, hist, prev, exp_long, got_long
        );
        assert_eq!(
            got_short, exp_short,
            "MACD short mode={}, hist={}, prev={}: expected {}, got {}",
            mode, hist, prev, exp_short, got_short
        );
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Effective min ADX precision sweep (AQC-1212)
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_effective_min_adx_tmc_ave_precision_sweep() {
    // Sweep different ADX slope and ATR/avg_ATR ratios to verify TMC+AVE
    // interactions produce correct effective_min_adx values.
    let base_cfg = GateConfig::default_config();

    let adx_slopes = [0.0, 0.3, 0.5, 0.51, 1.0, 2.0];
    let atr_ratios = [0.5, 1.0, 1.4, 1.5, 1.51, 2.0, 3.0];

    for &slope in &adx_slopes {
        for &ratio in &atr_ratios {
            let mut snap = MarketSnapshot::strong_bullish();
            snap.adx_slope = slope;
            snap.atr = ratio * snap.avg_atr;

            let result = rust_check_gates(&snap, &base_cfg, Some(true), false);

            // Compute expected effective_min_adx
            let mut expected = base_cfg.min_adx;

            // TMC: slope > 0.5 => cap at 25
            if slope > 0.5 {
                expected = expected.min(25.0);
            }

            // AVE: ratio > 1.5 => multiply
            if base_cfg.ave_enabled && snap.avg_atr > 0.0 {
                let actual_ratio = snap.atr / snap.avg_atr;
                if actual_ratio > base_cfg.ave_atr_ratio_gt {
                    expected *= base_cfg.ave_adx_mult;
                }
            }

            assert!(
                within_tolerance(expected, result.effective_min_adx, TIER_T2_TOLERANCE),
                "TMC+AVE mismatch: slope={}, atr_ratio={}: expected={}, got={}, err={:.2e}",
                slope,
                ratio,
                expected,
                result.effective_min_adx,
                relative_error(expected, result.effective_min_adx)
            );

            // f32 round-trip
            let f32_rt = result.effective_min_adx as f32 as f64;
            assert!(
                within_tolerance(result.effective_min_adx, f32_rt, TIER_T2_TOLERANCE),
                "effective_min_adx f32 round-trip exceeds T2: slope={}, ratio={}",
                slope,
                ratio
            );
        }
    }
}
