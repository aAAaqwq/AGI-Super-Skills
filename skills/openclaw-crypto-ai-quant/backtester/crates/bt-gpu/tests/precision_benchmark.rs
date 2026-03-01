//! f32 vs f64 precision benchmark for GPU decision kernel operations.
//!
//! Each test performs the same computation in f64 (CPU reference) and f32
//! (GPU equivalent), measures the relative error, and asserts it falls
//! within the corresponding precision tier tolerance.
//!
//! These tests do NOT require a GPU — they simulate the f32 truncation
//! that occurs when values are cast from f64 → f32 for GPU upload and
//! arithmetic.

use bt_gpu::precision::*;

// ═══════════════════════════════════════════════════════════════════════════
// T0 — Exact match: booleans, enums, gate pass/fail
// ═══════════════════════════════════════════════════════════════════════════

#[test]
fn t0_boolean_gate_pass_fail() {
    // Gate: close > ema_fast (trend-following entry condition).
    // Even at f32 precision, the boolean result must be identical when
    // the gap is large enough to survive rounding.
    let close_f64 = 50123.45_f64;
    let ema_fast_f64 = 50100.00_f64;

    let close_f32 = close_f64 as f32;
    let ema_fast_f32 = ema_fast_f64 as f32;

    let gate_f64 = close_f64 > ema_fast_f64;
    let gate_f32 = close_f32 > ema_fast_f32;

    assert!(
        exact_match(gate_f64, gate_f32),
        "T0 boolean gate (close > ema_fast) diverged: f64={gate_f64}, f32={gate_f32}"
    );
}

#[test]
fn t0_enum_direction_long_short() {
    // Direction enum: 1 = long, -1 = short, 0 = flat.
    // Determined by sign(ema_fast - ema_slow). Must be identical.
    let ema_fast_f64 = 50200.0_f64;
    let ema_slow_f64 = 50100.0_f64;

    let dir_f64: i32 = if ema_fast_f64 > ema_slow_f64 {
        1
    } else if ema_fast_f64 < ema_slow_f64 {
        -1
    } else {
        0
    };

    let ema_fast_f32 = ema_fast_f64 as f32;
    let ema_slow_f32 = ema_slow_f64 as f32;

    let dir_f32: i32 = if ema_fast_f32 > ema_slow_f32 {
        1
    } else if ema_fast_f32 < ema_slow_f32 {
        -1
    } else {
        0
    };

    assert!(
        exact_match(dir_f64, dir_f32),
        "T0 direction enum diverged: f64={dir_f64}, f32={dir_f32}"
    );
}

#[test]
fn t0_rsi_overbought_gate() {
    // RSI overbought gate: rsi > 70.0. Both f32 and f64 must agree
    // when RSI is clearly above or below the threshold.
    let test_values = [30.0_f64, 50.0, 69.5, 70.5, 85.0, 95.0];

    for rsi_f64 in test_values {
        let rsi_f32 = rsi_f64 as f32;
        let gate_f64 = rsi_f64 > 70.0;
        let gate_f32 = rsi_f32 > 70.0_f32;

        assert!(
            exact_match(gate_f64, gate_f32),
            "T0 RSI overbought gate diverged at RSI={rsi_f64}: f64={gate_f64}, f32={gate_f32}"
        );
    }
}

#[test]
fn t0_adx_trend_strength_gate() {
    // ADX trend strength gate: adx > 25.0 (strong trend).
    let test_values = [10.0_f64, 20.0, 24.5, 25.5, 30.0, 50.0, 80.0];

    for adx_f64 in test_values {
        let adx_f32 = adx_f64 as f32;
        let gate_f64 = adx_f64 > 25.0;
        let gate_f32 = adx_f32 > 25.0_f32;

        assert!(
            exact_match(gate_f64, gate_f32),
            "T0 ADX gate diverged at ADX={adx_f64}: f64={gate_f64}, f32={gate_f32}"
        );
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// T1 — f32 round-trip: f64 → f32 → f64 (≤1.2e-7 relative)
// ═══════════════════════════════════════════════════════════════════════════

#[test]
fn t1_config_value_round_trip() {
    // Typical config values that get uploaded to GPU as f32 and read back.
    let config_values: &[(&str, f64)] = &[
        ("tp_atr_mult", 3.5),
        ("sl_atr_mult", 1.2),
        ("margin_pct", 0.15),
        ("ema_fast_window", 12.0),
        ("ema_slow_window", 26.0),
        ("adx_window", 14.0),
        ("rsi_window", 14.0),
        ("bb_window", 20.0),
        ("bb_std_dev", 2.0),
        ("initial_balance", 1000.0),
        ("max_position_pct", 0.25),
    ];

    for (name, value) in config_values {
        let round_tripped = (*value as f32) as f64;
        let rel_err = relative_error(*value, round_tripped);

        assert!(
            within_tolerance(*value, round_tripped, TIER_T1_TOLERANCE),
            "T1 config round-trip failed for {name}={value}: \
             round_tripped={round_tripped}, rel_err={rel_err:.2e} > {TIER_T1_TOLERANCE:.2e}"
        );
    }
}

#[test]
fn t1_price_round_trip() {
    // BTC-scale prices: ~50000. f32 has ~7 significant digits, so
    // 50000.xx loses sub-cent precision, but relative error is tiny.
    let prices = [
        49_876.54_f64,
        50_000.00,
        50_123.45,
        51_234.56,
        100_000.00,
        0.001234, // sub-penny altcoin
        1.2345,   // stablecoin region
    ];

    for price in prices {
        let round_tripped = (price as f32) as f64;
        let rel_err = relative_error(price, round_tripped);

        assert!(
            within_tolerance(price, round_tripped, TIER_T1_TOLERANCE),
            "T1 price round-trip failed for price={price}: \
             round_tripped={round_tripped}, rel_err={rel_err:.2e}"
        );
    }
}

#[test]
fn t1_indicator_value_round_trip() {
    // Typical indicator values.
    let indicator_values: &[(&str, f64)] = &[
        ("rsi", 65.4321),
        ("adx", 28.765),
        ("atr", 523.456),
        ("ema_fast", 50_123.456),
        ("ema_slow", 50_098.123),
        ("bb_upper", 51_234.567),
        ("bb_lower", 48_765.432),
        ("macd_hist", -12.345),
        ("stoch_k", 78.9),
        ("stoch_d", 75.4),
        ("vol_sma", 1_234_567.89),
    ];

    for (name, value) in indicator_values {
        let round_tripped = (*value as f32) as f64;
        let rel_err = relative_error(*value, round_tripped);

        assert!(
            within_tolerance(*value, round_tripped, TIER_T1_TOLERANCE),
            "T1 indicator round-trip failed for {name}={value}: \
             round_tripped={round_tripped}, rel_err={rel_err:.2e}"
        );
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// T2 — Single arithmetic op (≤1e-6 relative)
// ═══════════════════════════════════════════════════════════════════════════

#[test]
fn t2_price_times_atr_mult() {
    // TP target = close + atr * tp_atr_mult (the most common single-op
    // pattern in the trade kernel).
    let close = 50_000.0_f64;
    let atr = 523.45_f64;
    let tp_mult = 3.5_f64;

    let expected = close + atr * tp_mult;
    let actual = (close as f32 + (atr as f32) * (tp_mult as f32)) as f64;

    let rel_err = relative_error(expected, actual);
    assert!(
        within_tolerance(expected, actual, TIER_T2_TOLERANCE),
        "T2 price*atr_mult: expected={expected}, actual={actual}, rel_err={rel_err:.2e}"
    );
}

#[test]
fn t2_balance_times_margin_pct() {
    // Position size = balance * margin_pct.
    let balance = 10_000.0_f64;
    let margin_pct = 0.15_f64;

    let expected = balance * margin_pct;
    let actual = ((balance as f32) * (margin_pct as f32)) as f64;

    let rel_err = relative_error(expected, actual);
    assert!(
        within_tolerance(expected, actual, TIER_T2_TOLERANCE),
        "T2 balance*margin: expected={expected}, actual={actual}, rel_err={rel_err:.2e}"
    );
}

#[test]
fn t2_sl_distance() {
    // SL distance = atr * sl_atr_mult.
    let atr = 523.45_f64;
    let sl_mult = 1.2_f64;

    let expected = atr * sl_mult;
    let actual = ((atr as f32) * (sl_mult as f32)) as f64;

    let rel_err = relative_error(expected, actual);
    assert!(
        within_tolerance(expected, actual, TIER_T2_TOLERANCE),
        "T2 SL distance: expected={expected}, actual={actual}, rel_err={rel_err:.2e}"
    );
}

#[test]
fn t2_pnl_single_trade() {
    // Single trade PnL = (exit_price - entry_price) * position_size.
    let entry = 50_000.0_f64;
    let exit = 51_500.0_f64;
    let size = 0.02_f64; // 0.02 BTC

    let expected = (exit - entry) * size;
    let actual = (((exit as f32) - (entry as f32)) * (size as f32)) as f64;

    let rel_err = relative_error(expected, actual);
    assert!(
        within_tolerance(expected, actual, TIER_T2_TOLERANCE),
        "T2 single trade PnL: expected={expected}, actual={actual}, rel_err={rel_err:.2e}"
    );
}

#[test]
fn t2_bb_width_ratio() {
    // Bollinger Band width ratio = (bb_upper - bb_lower) / close.
    let bb_upper = 51_234.56_f64;
    let bb_lower = 48_765.43_f64;
    let close = 50_000.0_f64;

    let expected = (bb_upper - bb_lower) / close;
    let actual = (((bb_upper as f32) - (bb_lower as f32)) / (close as f32)) as f64;

    let rel_err = relative_error(expected, actual);
    assert!(
        within_tolerance(expected, actual, TIER_T2_TOLERANCE),
        "T2 BB width ratio: expected={expected}, actual={actual}, rel_err={rel_err:.2e}"
    );
}

#[test]
fn t2_percent_return() {
    // Percent return = (close - open) / open.
    let open = 49_876.54_f64;
    let close = 50_123.45_f64;

    let expected = (close - open) / open;
    let actual = (((close as f32) - (open as f32)) / (open as f32)) as f64;

    let rel_err = relative_error(expected, actual);
    assert!(
        within_tolerance(expected, actual, TIER_T2_TOLERANCE),
        "T2 percent return: expected={expected}, actual={actual}, rel_err={rel_err:.2e}"
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// T3 — Multi-step chains (≤1e-5 relative)
// ═══════════════════════════════════════════════════════════════════════════

#[test]
fn t3_ema_value_chain() {
    // EMA value computed over 8 bars: each step chains a multiply + add.
    // We compare the EMA value itself (not the deviation, which involves
    // catastrophic cancellation on large correlated values and is T4-level).
    let closes = [
        50_100.0_f64,
        50_250.0,
        50_180.0,
        50_320.0,
        50_450.0,
        50_380.0,
        50_500.0,
        50_420.0,
    ];
    let ema_period = 5;
    let k = 2.0 / (ema_period as f64 + 1.0);
    let k_f32 = k as f32;

    // Compute EMA in f64
    let mut ema_f64 = closes[0];
    for &c in &closes[1..] {
        ema_f64 = c * k + ema_f64 * (1.0 - k);
    }

    // Compute EMA in f32
    let mut ema_f32 = closes[0] as f32;
    for &c in &closes[1..] {
        ema_f32 = (c as f32) * k_f32 + ema_f32 * (1.0_f32 - k_f32);
    }

    let rel_err = relative_error(ema_f64, ema_f32 as f64);
    assert!(
        within_tolerance(ema_f64, ema_f32 as f64, TIER_T3_TOLERANCE),
        "T3 EMA value chain: f64={ema_f64:.10}, f32={ema_f32:.10}, \
         rel_err={rel_err:.2e}"
    );
}

#[test]
fn t3_ema_deviation_chain() {
    // EMA deviation = (close - ema) / ema. This subtracts two large
    // correlated values (~50000), amplifying f32 rounding via catastrophic
    // cancellation. The result is a small fraction (~0.05%) so relative
    // error is amplified. This is T4-level due to cancellation, not T3.
    let closes = [
        50_100.0_f64,
        50_250.0,
        50_180.0,
        50_320.0,
        50_450.0,
        50_380.0,
        50_500.0,
        50_420.0,
    ];
    let ema_period = 5;
    let k = 2.0 / (ema_period as f64 + 1.0);
    let k_f32 = k as f32;

    let mut ema_f64 = closes[0];
    for &c in &closes[1..] {
        ema_f64 = c * k + ema_f64 * (1.0 - k);
    }
    let deviation_f64 = (closes[closes.len() - 1] - ema_f64) / ema_f64;

    let mut ema_f32 = closes[0] as f32;
    for &c in &closes[1..] {
        ema_f32 = (c as f32) * k_f32 + ema_f32 * (1.0_f32 - k_f32);
    }
    let deviation_f32 = ((closes[closes.len() - 1] as f32) - ema_f32) / ema_f32;

    // Catastrophic cancellation pushes this to T4 territory (~1.3e-4)
    let rel_err = relative_error(deviation_f64, deviation_f32 as f64);
    assert!(
        within_tolerance(deviation_f64, deviation_f32 as f64, TIER_T4_TOLERANCE),
        "T4 EMA deviation (catastrophic cancellation): f64={deviation_f64:.10}, \
         f32={deviation_f32:.10}, rel_err={rel_err:.2e}"
    );
}

#[test]
fn t3_adx_smoothing_chain() {
    // Simplified ADX computation: smooth +DI and -DI, then
    // adx = |+DI - -DI| / (+DI + -DI) * 100, smoothed over N bars.
    // This is 6+ chained ops.
    let plus_di_raw = [
        25.0_f64, 27.0, 23.0, 30.0, 28.0, 32.0, 26.0, 29.0, 31.0, 24.0,
    ];
    let minus_di_raw = [
        18.0_f64, 20.0, 22.0, 16.0, 19.0, 15.0, 21.0, 17.0, 14.0, 23.0,
    ];
    let period = 5;
    let smooth = 1.0 / period as f64;
    let smooth_f32 = smooth as f32;

    // f64 path
    let mut plus_di_f64 = plus_di_raw[0];
    let mut minus_di_f64 = minus_di_raw[0];
    let mut adx_f64 = 0.0_f64;
    for i in 1..plus_di_raw.len() {
        plus_di_f64 = plus_di_f64 * (1.0 - smooth) + plus_di_raw[i] * smooth;
        minus_di_f64 = minus_di_f64 * (1.0 - smooth) + minus_di_raw[i] * smooth;
        let dx = (plus_di_f64 - minus_di_f64).abs() / (plus_di_f64 + minus_di_f64) * 100.0;
        adx_f64 = adx_f64 * (1.0 - smooth) + dx * smooth;
    }

    // f32 path
    let mut plus_di_f32 = plus_di_raw[0] as f32;
    let mut minus_di_f32 = minus_di_raw[0] as f32;
    let mut adx_f32 = 0.0_f32;
    for i in 1..plus_di_raw.len() {
        plus_di_f32 = plus_di_f32 * (1.0_f32 - smooth_f32) + (plus_di_raw[i] as f32) * smooth_f32;
        minus_di_f32 =
            minus_di_f32 * (1.0_f32 - smooth_f32) + (minus_di_raw[i] as f32) * smooth_f32;
        let dx = (plus_di_f32 - minus_di_f32).abs() / (plus_di_f32 + minus_di_f32) * 100.0_f32;
        adx_f32 = adx_f32 * (1.0_f32 - smooth_f32) + dx * smooth_f32;
    }

    let rel_err = relative_error(adx_f64, adx_f32 as f64);
    assert!(
        within_tolerance(adx_f64, adx_f32 as f64, TIER_T3_TOLERANCE),
        "T3 ADX smoothing chain: f64={adx_f64:.10}, f32={adx_f32:.10}, rel_err={rel_err:.2e}"
    );
}

#[test]
fn t3_rsi_computation() {
    // RSI = 100 - 100/(1 + avg_gain/avg_loss) — chains division, addition,
    // subtraction over smoothed gain/loss averages.
    let closes = [
        50_000.0_f64,
        50_150.0,
        50_080.0,
        50_220.0,
        50_180.0,
        50_350.0,
        50_300.0,
        50_420.0,
        50_390.0,
        50_500.0,
        50_480.0,
        50_550.0,
        50_520.0,
        50_600.0,
        50_570.0,
    ];
    let period = 14;

    // f64 path
    let mut gains_f64 = Vec::new();
    let mut losses_f64 = Vec::new();
    for i in 1..closes.len() {
        let change = closes[i] - closes[i - 1];
        if change > 0.0 {
            gains_f64.push(change);
            losses_f64.push(0.0);
        } else {
            gains_f64.push(0.0);
            losses_f64.push(change.abs());
        }
    }
    let avg_gain_f64: f64 = gains_f64.iter().take(period).sum::<f64>() / period as f64;
    let avg_loss_f64: f64 = losses_f64.iter().take(period).sum::<f64>() / period as f64;
    let rs_f64 = if avg_loss_f64 > 0.0 {
        avg_gain_f64 / avg_loss_f64
    } else {
        100.0
    };
    let rsi_f64 = 100.0 - 100.0 / (1.0 + rs_f64);

    // f32 path
    let mut gains_f32 = Vec::new();
    let mut losses_f32 = Vec::new();
    for i in 1..closes.len() {
        let change = (closes[i] as f32) - (closes[i - 1] as f32);
        if change > 0.0_f32 {
            gains_f32.push(change);
            losses_f32.push(0.0_f32);
        } else {
            gains_f32.push(0.0_f32);
            losses_f32.push(change.abs());
        }
    }
    let avg_gain_f32: f32 = gains_f32.iter().take(period).sum::<f32>() / period as f32;
    let avg_loss_f32: f32 = losses_f32.iter().take(period).sum::<f32>() / period as f32;
    let rs_f32 = if avg_loss_f32 > 0.0_f32 {
        avg_gain_f32 / avg_loss_f32
    } else {
        100.0_f32
    };
    let rsi_f32 = 100.0_f32 - 100.0_f32 / (1.0_f32 + rs_f32);

    let rel_err = relative_error(rsi_f64, rsi_f32 as f64);
    assert!(
        within_tolerance(rsi_f64, rsi_f32 as f64, TIER_T3_TOLERANCE),
        "T3 RSI computation: f64={rsi_f64:.10}, f32={rsi_f32:.10}, rel_err={rel_err:.2e}"
    );
}

#[test]
fn t3_bollinger_band_position() {
    // BB %B = (close - bb_lower) / (bb_upper - bb_lower)
    // Chains: 2 subtracts + 1 divide on correlated large values.
    let close = 50_234.56_f64;
    let bb_upper = 51_000.00_f64;
    let bb_lower = 49_000.00_f64;

    let pct_b_f64 = (close - bb_lower) / (bb_upper - bb_lower);
    let pct_b_f32 = ((close as f32) - (bb_lower as f32)) / ((bb_upper as f32) - (bb_lower as f32));

    let rel_err = relative_error(pct_b_f64, pct_b_f32 as f64);
    assert!(
        within_tolerance(pct_b_f64, pct_b_f32 as f64, TIER_T3_TOLERANCE),
        "T3 BB %B: f64={pct_b_f64:.10}, f32={pct_b_f32:.10}, rel_err={rel_err:.2e}"
    );
}

#[test]
fn t3_macd_line_short_chain_is_t4() {
    // MACD line = EMA_12(close) - EMA_26(close) over 10 bars.
    // Despite only 10 iterations, this subtracts two ~50000 EMAs to get
    // a ~86 result — catastrophic cancellation amplifies relative error
    // to ~1.3e-4, firmly in T4 territory.
    let closes = [
        50_000.0_f64,
        50_120.0,
        50_080.0,
        50_200.0,
        50_150.0,
        50_280.0,
        50_220.0,
        50_350.0,
        50_310.0,
        50_400.0,
    ];

    let k12 = 2.0 / 13.0_f64;
    let k26 = 2.0 / 27.0_f64;

    // f64
    let mut ema12_f64 = closes[0];
    let mut ema26_f64 = closes[0];
    for &c in &closes[1..] {
        ema12_f64 = c * k12 + ema12_f64 * (1.0 - k12);
        ema26_f64 = c * k26 + ema26_f64 * (1.0 - k26);
    }
    let macd_f64 = ema12_f64 - ema26_f64;

    // f32
    let k12_f32 = k12 as f32;
    let k26_f32 = k26 as f32;
    let mut ema12_f32 = closes[0] as f32;
    let mut ema26_f32 = closes[0] as f32;
    for &c in &closes[1..] {
        let c_f32 = c as f32;
        ema12_f32 = c_f32 * k12_f32 + ema12_f32 * (1.0_f32 - k12_f32);
        ema26_f32 = c_f32 * k26_f32 + ema26_f32 * (1.0_f32 - k26_f32);
    }
    let macd_f32 = ema12_f32 - ema26_f32;

    let rel_err = relative_error(macd_f64, macd_f32 as f64);
    assert!(
        within_tolerance(macd_f64, macd_f32 as f64, TIER_T4_TOLERANCE),
        "T4 MACD line (catastrophic cancellation): f64={macd_f64:.10}, \
         f32={macd_f32:.10}, rel_err={rel_err:.2e}"
    );
}

#[test]
fn t3_macd_histogram_30_bars_is_t4() {
    // Full MACD histogram = (EMA_12 - EMA_26) - signal_EMA_9 over 30 bars.
    // This chains 30 iterations of 3 EMA updates + 2 subtractions each,
    // and the final histogram is a small number (difference of differences),
    // causing catastrophic cancellation. Empirically ~3.8e-4 relative error.
    // This documents that MACD histogram over 30 bars is T4-level.
    let closes = [
        50_000.0_f64,
        50_120.0,
        50_080.0,
        50_200.0,
        50_150.0,
        50_280.0,
        50_220.0,
        50_350.0,
        50_310.0,
        50_400.0,
        50_380.0,
        50_450.0,
        50_420.0,
        50_500.0,
        50_470.0,
        50_550.0,
        50_520.0,
        50_600.0,
        50_580.0,
        50_650.0,
        50_620.0,
        50_700.0,
        50_680.0,
        50_750.0,
        50_720.0,
        50_800.0,
        50_780.0,
        50_850.0,
        50_830.0,
        50_900.0,
    ];

    let k12 = 2.0 / 13.0_f64;
    let k26 = 2.0 / 27.0_f64;
    let k9 = 2.0 / 10.0_f64;

    // f64
    let mut ema12_f64 = closes[0];
    let mut ema26_f64 = closes[0];
    let mut signal_f64 = 0.0_f64;
    let mut macd_hist_f64 = 0.0_f64;
    for (i, &c) in closes.iter().enumerate() {
        if i > 0 {
            ema12_f64 = c * k12 + ema12_f64 * (1.0 - k12);
            ema26_f64 = c * k26 + ema26_f64 * (1.0 - k26);
        }
        let macd_line = ema12_f64 - ema26_f64;
        if i == 0 {
            signal_f64 = macd_line;
        } else {
            signal_f64 = macd_line * k9 + signal_f64 * (1.0 - k9);
        }
        macd_hist_f64 = macd_line - signal_f64;
    }

    // f32
    let k12_f32 = k12 as f32;
    let k26_f32 = k26 as f32;
    let k9_f32 = k9 as f32;
    let mut ema12_f32 = closes[0] as f32;
    let mut ema26_f32 = closes[0] as f32;
    let mut signal_f32 = 0.0_f32;
    let mut macd_hist_f32 = 0.0_f32;
    for (i, &c) in closes.iter().enumerate() {
        let c_f32 = c as f32;
        if i > 0 {
            ema12_f32 = c_f32 * k12_f32 + ema12_f32 * (1.0_f32 - k12_f32);
            ema26_f32 = c_f32 * k26_f32 + ema26_f32 * (1.0_f32 - k26_f32);
        }
        let macd_line = ema12_f32 - ema26_f32;
        if i == 0 {
            signal_f32 = macd_line;
        } else {
            signal_f32 = macd_line * k9_f32 + signal_f32 * (1.0_f32 - k9_f32);
        }
        macd_hist_f32 = macd_line - signal_f32;
    }

    let rel_err = relative_error(macd_hist_f64, macd_hist_f32 as f64);
    assert!(
        within_tolerance(macd_hist_f64, macd_hist_f32 as f64, TIER_T4_TOLERANCE),
        "T4 MACD histogram (30 bars): f64={macd_hist_f64:.10}, f32={macd_hist_f32:.10}, \
         rel_err={rel_err:.2e}"
    );
}

#[test]
fn t3_atr_computation() {
    // ATR = smoothed average of true_range over N bars.
    // true_range = max(high-low, |high-prev_close|, |low-prev_close|)
    let bars: Vec<(f64, f64, f64)> = vec![
        // (high, low, close)
        (50_200.0, 49_800.0, 50_100.0),
        (50_350.0, 49_950.0, 50_200.0),
        (50_500.0, 50_050.0, 50_300.0),
        (50_450.0, 49_900.0, 50_000.0),
        (50_300.0, 49_850.0, 50_150.0),
        (50_400.0, 49_950.0, 50_250.0),
        (50_550.0, 50_100.0, 50_400.0),
        (50_600.0, 50_050.0, 50_300.0),
        (50_500.0, 49_900.0, 50_100.0),
        (50_350.0, 49_950.0, 50_200.0),
        (50_450.0, 50_000.0, 50_300.0),
        (50_550.0, 50_050.0, 50_350.0),
        (50_400.0, 49_900.0, 50_100.0),
        (50_300.0, 49_850.0, 50_050.0),
    ];
    let period = 14;

    // f64
    let mut atr_f64 = 0.0_f64;
    for i in 0..bars.len() {
        let (h, l, _c) = bars[i];
        let prev_c = if i == 0 { bars[0].2 } else { bars[i - 1].2 };
        let tr = (h - l).max((h - prev_c).abs()).max((l - prev_c).abs());
        if i == 0 {
            atr_f64 = tr;
        } else {
            atr_f64 = (atr_f64 * (period as f64 - 1.0) + tr) / period as f64;
        }
    }

    // f32
    let mut atr_f32 = 0.0_f32;
    for i in 0..bars.len() {
        let (h, l, _c) = bars[i];
        let h_f32 = h as f32;
        let l_f32 = l as f32;
        let prev_c_f32 = if i == 0 {
            bars[0].2 as f32
        } else {
            bars[i - 1].2 as f32
        };
        let tr = (h_f32 - l_f32)
            .max((h_f32 - prev_c_f32).abs())
            .max((l_f32 - prev_c_f32).abs());
        if i == 0 {
            atr_f32 = tr;
        } else {
            atr_f32 = (atr_f32 * (period as f32 - 1.0_f32) + tr) / period as f32;
        }
    }

    let rel_err = relative_error(atr_f64, atr_f32 as f64);
    assert!(
        within_tolerance(atr_f64, atr_f32 as f64, TIER_T3_TOLERANCE),
        "T3 ATR computation: f64={atr_f64:.10}, f32={atr_f32:.10}, rel_err={rel_err:.2e}"
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// T4 — Accumulated error: running sums, equity curves (≤1e-4 relative)
// ═══════════════════════════════════════════════════════════════════════════

#[test]
fn t4_cumulative_pnl_1000_trades() {
    // Accumulate PnL over 1000 trades. Each trade has a small PnL relative
    // to price, so f32 rounding accumulates over many additions.
    let num_trades = 1000;
    let base_price = 50_000.0_f64;

    // Deterministic pseudo-random PnL per trade:
    // trade_pnl[i] = base_price * sin(i * 0.1) * 0.001  (range: ~±50)
    let mut sum_f64 = 0.0_f64;
    let mut sum_f32 = 0.0_f32;

    for i in 0..num_trades {
        let pnl_f64 = base_price * (i as f64 * 0.1).sin() * 0.001;
        sum_f64 += pnl_f64;
        sum_f32 += pnl_f64 as f32;
    }

    let rel_err = relative_error(sum_f64, sum_f32 as f64);
    assert!(
        within_tolerance(sum_f64, sum_f32 as f64, TIER_T4_TOLERANCE),
        "T4 cumulative PnL (1000 trades): f64={sum_f64:.6}, f32={sum_f32:.6}, \
         rel_err={rel_err:.2e}"
    );
}

#[test]
fn t4_equity_curve_500_bars() {
    // Track equity curve: balance += trade_pnl each bar.
    // Starting at 10_000, accumulating small changes over 500 bars.
    let num_bars = 500;
    let initial_balance = 10_000.0_f64;

    let mut balance_f64 = initial_balance;
    let mut balance_f32 = initial_balance as f32;

    for i in 0..num_bars {
        // Alternating wins and losses with slight positive bias
        let pnl_f64 = if i % 3 == 0 {
            -15.0 + (i as f64 * 0.01)
        } else {
            25.0 - (i as f64 * 0.005)
        };
        balance_f64 += pnl_f64;
        balance_f32 += pnl_f64 as f32;
    }

    let rel_err = relative_error(balance_f64, balance_f32 as f64);
    assert!(
        within_tolerance(balance_f64, balance_f32 as f64, TIER_T4_TOLERANCE),
        "T4 equity curve (500 bars): f64={balance_f64:.6}, f32={balance_f32:.6}, \
         rel_err={rel_err:.2e}"
    );
}

#[test]
fn t4_max_drawdown_tracking() {
    // Track max drawdown % over an equity curve with 300 bars.
    // peak tracking + division = accumulated comparison error.
    let num_bars = 300;
    let initial_balance = 10_000.0_f64;

    let mut balance_f64 = initial_balance;
    let mut peak_f64 = initial_balance;
    let mut max_dd_f64 = 0.0_f64;

    let mut balance_f32 = initial_balance as f32;
    let mut peak_f32 = initial_balance as f32;
    let mut max_dd_f32 = 0.0_f32;

    for i in 0..num_bars {
        // Simulate volatile equity: up 30 on good bars, down 20 on bad bars,
        // with a drawdown valley around bar 100-150.
        let pnl = if i > 80 && i < 160 {
            -25.0 + (i as f64 - 120.0) * 0.3
        } else {
            20.0 + (i as f64 * 0.05).sin() * 10.0
        };

        // f64
        balance_f64 += pnl;
        if balance_f64 > peak_f64 {
            peak_f64 = balance_f64;
        }
        let dd_f64 = (peak_f64 - balance_f64) / peak_f64;
        if dd_f64 > max_dd_f64 {
            max_dd_f64 = dd_f64;
        }

        // f32
        balance_f32 += pnl as f32;
        if balance_f32 > peak_f32 {
            peak_f32 = balance_f32;
        }
        let dd_f32 = (peak_f32 - balance_f32) / peak_f32;
        if dd_f32 > max_dd_f32 {
            max_dd_f32 = dd_f32;
        }
    }

    let rel_err = relative_error(max_dd_f64, max_dd_f32 as f64);
    assert!(
        within_tolerance(max_dd_f64, max_dd_f32 as f64, TIER_T4_TOLERANCE),
        "T4 max drawdown: f64={max_dd_f64:.8}, f32={max_dd_f32:.8}, rel_err={rel_err:.2e}"
    );
}

#[test]
fn t4_running_atr_1000_bars() {
    // ATR smoothed over 1000 bars — each bar adds one multiply + one add
    // to the running average, so error accumulates.
    let num_bars = 1000;
    let period = 14;

    let mut atr_f64 = 500.0_f64; // starting ATR
    let mut atr_f32 = 500.0_f32;

    for i in 0..num_bars {
        // Synthetic true range varying around 400-600
        let tr_f64 = 500.0 + 100.0 * ((i as f64) * 0.07).sin();
        let tr_f32 = tr_f64 as f32;

        atr_f64 = (atr_f64 * (period as f64 - 1.0) + tr_f64) / period as f64;
        atr_f32 = (atr_f32 * (period as f32 - 1.0_f32) + tr_f32) / period as f32;
    }

    let rel_err = relative_error(atr_f64, atr_f32 as f64);
    assert!(
        within_tolerance(atr_f64, atr_f32 as f64, TIER_T4_TOLERANCE),
        "T4 running ATR (1000 bars): f64={atr_f64:.6}, f32={atr_f32:.6}, \
         rel_err={rel_err:.2e}"
    );
}

#[test]
fn t4_win_rate_over_many_trades() {
    // Win rate = wins / total. After 500 trades, the integer division
    // itself is exact, but the accumulation of which trades "win"
    // may differ between f32 and f64 in edge cases. Here we test
    // the pure accumulation.
    let num_trades = 500;
    let mut wins_f64 = 0u32;
    let mut wins_f32 = 0u32;
    let mut total_pnl_f64 = 0.0_f64;
    let mut total_pnl_f32 = 0.0_f32;

    for i in 0..num_trades {
        // Generate trades with a positive bias so the sum doesn't hover near zero
        // (near-zero sums amplify relative error beyond any useful tier).
        let pnl_f64 = 50.0 + 30.0 * (i as f64 * 2.3).cos();

        total_pnl_f64 += pnl_f64;
        total_pnl_f32 += pnl_f64 as f32;

        if pnl_f64 > 0.0 {
            wins_f64 += 1;
        }
        if (pnl_f64 as f32) > 0.0_f32 {
            wins_f32 += 1;
        }
    }

    // Win counts should agree when trades are well above zero
    let win_diff = (wins_f64 as i32 - wins_f32 as i32).unsigned_abs();
    assert!(
        win_diff <= 2,
        "T4 win count divergence too large: f64_wins={wins_f64}, f32_wins={wins_f32}, \
         diff={win_diff}"
    );

    // Total PnL should be within T4 tolerance
    let rel_err = relative_error(total_pnl_f64, total_pnl_f32 as f64);
    assert!(
        within_tolerance(total_pnl_f64, total_pnl_f32 as f64, TIER_T4_TOLERANCE),
        "T4 accumulated PnL (500 trades): f64={total_pnl_f64:.6}, f32={total_pnl_f32:.6}, \
         rel_err={rel_err:.2e}"
    );
}

#[test]
fn t4_profit_factor_accumulated() {
    // profit_factor = gross_profit / gross_loss over 200 trades.
    let num_trades = 200;
    let mut gross_profit_f64 = 0.0_f64;
    let mut gross_loss_f64 = 0.0_f64;
    let mut gross_profit_f32 = 0.0_f32;
    let mut gross_loss_f32 = 0.0_f32;

    for i in 0..num_trades {
        let pnl_f64 = 50.0 * ((i as f64) * 0.37).sin() + 5.0; // slight positive bias

        if pnl_f64 > 0.0 {
            gross_profit_f64 += pnl_f64;
            gross_profit_f32 += pnl_f64 as f32;
        } else {
            gross_loss_f64 += pnl_f64.abs();
            gross_loss_f32 += (pnl_f64 as f32).abs();
        }
    }

    let pf_f64 = if gross_loss_f64 > 0.0 {
        gross_profit_f64 / gross_loss_f64
    } else {
        999.0
    };
    let pf_f32 = if gross_loss_f32 > 0.0_f32 {
        gross_profit_f32 / gross_loss_f32
    } else {
        999.0_f32
    };

    let rel_err = relative_error(pf_f64, pf_f32 as f64);
    assert!(
        within_tolerance(pf_f64, pf_f32 as f64, TIER_T4_TOLERANCE),
        "T4 profit factor: f64={pf_f64:.6}, f32={pf_f32:.6}, rel_err={rel_err:.2e}"
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// Cross-tier: document observed error magnitudes for each tier
// ═══════════════════════════════════════════════════════════════════════════

#[test]
fn cross_tier_error_magnitude_report() {
    // This test documents actual error magnitudes to verify the tier
    // boundaries are sensible. It prints a summary and asserts each
    // value falls within its declared tier.

    struct Sample {
        tier: &'static str,
        name: &'static str,
        tolerance: f64,
        expected: f64,
        actual: f64,
    }

    let mut samples: Vec<Sample> = Vec::new();

    // T1: round-trip
    let v = 50_123.45_f64;
    let rt = (v as f32) as f64;
    samples.push(Sample {
        tier: "T1",
        name: "price round-trip",
        tolerance: TIER_T1_TOLERANCE,
        expected: v,
        actual: rt,
    });

    // T2: single op
    let expected_t2 = 50_000.0_f64 + 523.45 * 3.5;
    let actual_t2 = (50_000.0_f32 + 523.45_f32 * 3.5_f32) as f64;
    samples.push(Sample {
        tier: "T2",
        name: "TP target (price + atr*mult)",
        tolerance: TIER_T2_TOLERANCE,
        expected: expected_t2,
        actual: actual_t2,
    });

    // T3: EMA chain (8 bars)
    let closes = [
        50_100.0_f64,
        50_250.0,
        50_180.0,
        50_320.0,
        50_450.0,
        50_380.0,
        50_500.0,
        50_420.0,
    ];
    let k = 2.0 / 6.0_f64;
    let mut ema_f64 = closes[0];
    for &c in &closes[1..] {
        ema_f64 = c * k + ema_f64 * (1.0 - k);
    }
    let mut ema_f32 = closes[0] as f32;
    let k_f32 = k as f32;
    for &c in &closes[1..] {
        ema_f32 = (c as f32) * k_f32 + ema_f32 * (1.0_f32 - k_f32);
    }
    samples.push(Sample {
        tier: "T3",
        name: "EMA(5) over 8 bars",
        tolerance: TIER_T3_TOLERANCE,
        expected: ema_f64,
        actual: ema_f32 as f64,
    });

    // T4: cumulative sum (1000 values)
    let mut sum_f64 = 0.0_f64;
    let mut sum_f32 = 0.0_f32;
    for i in 0..1000 {
        let v = 50_000.0 * (i as f64 * 0.1).sin() * 0.001;
        sum_f64 += v;
        sum_f32 += v as f32;
    }
    samples.push(Sample {
        tier: "T4",
        name: "cumulative PnL (1000 trades)",
        tolerance: TIER_T4_TOLERANCE,
        expected: sum_f64,
        actual: sum_f32 as f64,
    });

    // Print report
    eprintln!("\n╔══════════════════════════════════════════════════════════════╗");
    eprintln!("║          f32/f64 Precision Tier Error Report                ║");
    eprintln!("╠══════╦══════════════════════════════╦═══════════╦═══════════╣");
    eprintln!("║ Tier ║ Operation                    ║ Rel Error ║ Tolerance ║");
    eprintln!("╠══════╬══════════════════════════════╬═══════════╬═══════════╣");

    for s in &samples {
        let rel_err = relative_error(s.expected, s.actual);
        let status = if within_tolerance(s.expected, s.actual, s.tolerance) {
            "PASS"
        } else {
            "FAIL"
        };
        eprintln!(
            "║ {:<4} ║ {:<28} ║ {:<9.2e} ║ {:<9.2e} ║ {}",
            s.tier, s.name, rel_err, s.tolerance, status
        );
    }
    eprintln!("╚══════╩══════════════════════════════╩═══════════╩═══════════╝\n");

    // Assert all pass
    for s in &samples {
        assert!(
            within_tolerance(s.expected, s.actual, s.tolerance),
            "Cross-tier report: {} ({}) failed: rel_err={:.2e} > tolerance={:.2e}",
            s.name,
            s.tier,
            relative_error(s.expected, s.actual),
            s.tolerance,
        );
    }
}
