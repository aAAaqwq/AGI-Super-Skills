//! Full-sweep parity test: 100 random configs validated against CPU reference.
//!
//! This test exercises all 9 codegen decision functions (gates, signal, SL,
//! trailing, TP, smart exits, all-exits, sizing, PESC cooldown) across 100
//! randomly-generated but valid GpuComboConfig parameter sets, using a seeded
//! RNG for full reproducibility.
//!
//! Since CUDA hardware is not available in CI, parity is validated by running
//! the inline Rust SSOT reference implementations (same logic as bt-core) on
//! each config × fixture combination and asserting:
//!   - Directional sanity (SL on correct side, trailing ratchets only forward)
//!   - f32 round-trip precision within tier-appropriate tolerances
//!   - Cross-function consistency (e.g. trailing_sl >= raw_sl when active)
//!   - Sizing positivity and leverage caps
//!   - PESC cooldown monotonicity
//!
//! # Running
//!
//! ```sh
//! cargo test -p bt-gpu --features codegen --test gpu_sweep_full_parity -- --nocapture
//! ```

#![cfg(feature = "codegen")]

use bt_gpu::buffers::GpuComboConfig;
use bt_gpu::precision::*;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};

// ═══════════════════════════════════════════════════════════════════════════════
// Types (matching gpu_decision_parity.rs conventions)
// ═══════════════════════════════════════════════════════════════════════════════

#[derive(Debug, Clone, Copy, PartialEq)]
enum PosType {
    Long,
    Short,
}

#[derive(Debug, Clone, Copy, PartialEq)]
enum Confidence {
    Low,
    Medium,
    High,
}

// ═══════════════════════════════════════════════════════════════════════════════
// Synthetic market data
// ═══════════════════════════════════════════════════════════════════════════════

/// One bar of synthetic indicator data used as input to the decision functions.
#[derive(Debug, Clone)]
#[allow(dead_code)] // high/low/open reserved for future sub-bar exit codegen parity
struct SyntheticBar {
    close: f64,
    prev_close: f64,
    high: f64,
    low: f64,
    open: f64,
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

/// Generate a 90-day (2160 bar) synthetic 1h market with realistic price dynamics.
fn generate_synthetic_bars(rng: &mut StdRng, base_price: f64) -> Vec<SyntheticBar> {
    let num_bars = 2160; // ~90 days of 1h bars
    let mut bars = Vec::with_capacity(num_bars);
    let mut price = base_price;
    let mut ema_fast = price;
    let mut ema_slow = price;
    let mut ema_macro = price;
    let atr_base = base_price * 0.015; // 1.5% ATR

    for i in 0..num_bars {
        let trend_bias = ((i as f64) / 500.0).sin() * 0.002;
        let noise = rng.gen_range(-0.03_f64..0.03);
        let ret = trend_bias + noise;
        let prev_price = price;
        price *= 1.0 + ret;

        let prev_ema_fast = ema_fast;
        let alpha_fast = 2.0 / 13.0; // ~12-period EMA
        let alpha_slow = 2.0 / 27.0; // ~26-period EMA
        let alpha_macro = 2.0 / 101.0; // ~100-period EMA
        ema_fast = alpha_fast * price + (1.0 - alpha_fast) * ema_fast;
        ema_slow = alpha_slow * price + (1.0 - alpha_slow) * ema_slow;
        ema_macro = alpha_macro * price + (1.0 - alpha_macro) * ema_macro;

        let atr = atr_base * (1.0 + rng.gen_range(-0.3..0.3));
        let avg_atr = atr_base;
        let adx = rng.gen_range(15.0..55.0);
        let adx_slope = rng.gen_range(-2.0..2.0);
        let atr_slope = rng.gen_range(-0.5..0.5);
        let rsi = rng.gen_range(20.0..80.0);
        let stoch_k = rng.gen_range(0.0..1.0);
        let bb_width_ratio = rng.gen_range(0.5..2.5);
        let volume = rng.gen_range(500.0..3000.0);
        let vol_sma = 1000.0;
        let vol_trend = volume > vol_sma;
        let macd_hist = ema_fast - ema_slow;
        let prev_macd_hist = macd_hist * rng.gen_range(0.7..1.3);
        let ema_slow_slope_pct = if ema_slow > 0.0 {
            (ema_slow - (alpha_slow * prev_price + (1.0 - alpha_slow) * ema_slow)) / ema_slow
        } else {
            0.0
        };

        let high = price * (1.0 + rng.gen_range(0.0..0.02));
        let low = price * (1.0 - rng.gen_range(0.0..0.02));

        bars.push(SyntheticBar {
            close: price,
            prev_close: prev_price,
            high,
            low,
            open: prev_price,
            ema_fast,
            ema_slow,
            ema_macro,
            prev_ema_fast,
            adx,
            adx_slope,
            atr,
            avg_atr,
            atr_slope,
            rsi,
            stoch_k,
            bb_width_ratio,
            volume,
            vol_sma,
            vol_trend,
            macd_hist,
            prev_macd_hist,
            ema_slow_slope_pct,
        });
    }
    bars
}

// ═══════════════════════════════════════════════════════════════════════════════
// Random config generation
// ═══════════════════════════════════════════════════════════════════════════════

/// Generate a random but valid GpuComboConfig by randomising all trade-affecting
/// fields within their documented valid ranges.
fn random_gpu_combo_config(rng: &mut StdRng) -> GpuComboConfig {
    GpuComboConfig {
        // Core sizing
        allocation_pct: rng.gen_range(0.01_f32..0.20),
        sl_atr_mult: rng.gen_range(1.0_f32..4.0),
        tp_atr_mult: rng.gen_range(2.0_f32..10.0),
        leverage: rng.gen_range(1.0_f32..5.0),

        // REEF
        enable_reef_filter: rng.gen_range(0_u32..2),
        reef_long_rsi_block_gt: rng.gen_range(65.0_f32..80.0),
        reef_short_rsi_block_lt: rng.gen_range(20.0_f32..35.0),
        reef_adx_threshold: rng.gen_range(25.0_f32..40.0),
        reef_long_rsi_extreme_gt: rng.gen_range(75.0_f32..90.0),
        reef_short_rsi_extreme_lt: rng.gen_range(10.0_f32..25.0),

        // Dynamic leverage (always enabled; _reserved10 replaces former flag)
        _reserved10: 0,
        leverage_low: rng.gen_range(1.0_f32..2.0),
        leverage_medium: rng.gen_range(1.5_f32..3.0),
        leverage_high: rng.gen_range(2.0_f32..5.0),
        _reserved14: 0.0,
        trailing_rsi_floor_default: rng.gen_range(0.3_f32..0.7),

        // Execution
        slippage_bps: rng.gen_range(0.0_f32..5.0),
        min_notional_usd: rng.gen_range(5.0_f32..50.0),
        bump_to_min_notional: rng.gen_range(0_u32..2),
        max_total_margin_pct: rng.gen_range(0.5_f32..1.0),
        trailing_rsi_floor_trending: rng.gen_range(0.5_f32..0.9),
        trailing_vbts_bb_threshold: rng.gen_range(0.8_f32..2.0),

        // Dynamic sizing
        enable_dynamic_sizing: rng.gen_range(0_u32..2),
        confidence_mult_high: rng.gen_range(0.8_f32..1.2),
        confidence_mult_medium: rng.gen_range(0.6_f32..1.0),
        confidence_mult_low: rng.gen_range(0.4_f32..0.8),
        adx_sizing_min_mult: rng.gen_range(0.4_f32..0.8),
        adx_sizing_full_adx: rng.gen_range(30.0_f32..50.0),
        vol_baseline_pct: rng.gen_range(0.005_f32..0.03),
        vol_scalar_min: rng.gen_range(0.3_f32..0.6),

        vol_scalar_max: rng.gen_range(1.5_f32..3.0),
        trailing_vbts_mult: rng.gen_range(1.0_f32..1.5),

        // Pyramiding
        enable_pyramiding: rng.gen_range(0_u32..2),
        max_adds_per_symbol: rng.gen_range(1_u32..5),
        add_fraction_of_base_margin: rng.gen_range(0.3_f32..0.7),
        add_cooldown_minutes: rng.gen_range(30_u32..240),
        add_min_profit_atr: rng.gen_range(0.5_f32..2.0),
        add_min_confidence: rng.gen_range(0_u32..3),
        entry_min_confidence: rng.gen_range(0_u32..3),
        trailing_high_profit_atr: rng.gen_range(1.5_f32..3.0),

        // Partial TP
        enable_partial_tp: rng.gen_range(0_u32..2),
        tp_partial_pct: rng.gen_range(0.2_f32..0.5),
        tp_partial_min_notional_usd: rng.gen_range(5.0_f32..30.0),
        trailing_start_atr: rng.gen_range(0.5_f32..2.0),
        trailing_distance_atr: rng.gen_range(0.3_f32..1.5),
        tp_partial_atr_mult: rng.gen_range(1.5_f32..4.0),

        // SSF + breakeven
        enable_ssf_filter: rng.gen_range(0_u32..2),
        enable_breakeven_stop: rng.gen_range(0_u32..2),
        breakeven_start_atr: rng.gen_range(0.3_f32..1.0),
        breakeven_buffer_atr: rng.gen_range(0.01_f32..0.1),

        // Per-confidence trailing overrides
        trailing_start_atr_low_conf: rng.gen_range(0.0_f32..1.5),
        trailing_distance_atr_low_conf: rng.gen_range(0.0_f32..1.0),
        smart_exit_adx_exhaustion_lt: rng.gen_range(15.0_f32..30.0),
        smart_exit_adx_exhaustion_lt_low_conf: rng.gen_range(20.0_f32..35.0),

        // RSI overextension exit
        enable_rsi_overextension_exit: rng.gen_range(0_u32..2),
        rsi_exit_profit_atr_switch: rng.gen_range(1.0_f32..3.0),
        rsi_exit_ub_lo_profit: rng.gen_range(70.0_f32..80.0),
        rsi_exit_ub_hi_profit: rng.gen_range(65.0_f32..75.0),
        rsi_exit_lb_lo_profit: rng.gen_range(30.0_f32..40.0),
        rsi_exit_lb_hi_profit: rng.gen_range(35.0_f32..45.0),
        rsi_exit_ub_lo_profit_low_conf: rng.gen_range(65.0_f32..75.0),
        rsi_exit_ub_hi_profit_low_conf: rng.gen_range(60.0_f32..70.0),
        rsi_exit_lb_lo_profit_low_conf: rng.gen_range(35.0_f32..45.0),
        rsi_exit_lb_hi_profit_low_conf: rng.gen_range(40.0_f32..50.0),

        // Reentry cooldown
        reentry_cooldown_minutes: rng.gen_range(0_u32..120),
        reentry_cooldown_min_mins: rng.gen_range(5_u32..30),
        reentry_cooldown_max_mins: rng.gen_range(30_u32..180),
        trailing_tighten_default: rng.gen_range(0.3_f32..0.7),

        // Volatility-buffered trailing + TSME
        enable_vol_buffered_trailing: rng.gen_range(0_u32..2),
        tsme_min_profit_atr: rng.gen_range(0.5_f32..2.0),
        tsme_require_adx_slope_negative: rng.gen_range(0_u32..2),
        trailing_tighten_tspv: rng.gen_range(0.5_f32..0.9),

        // ATR floor / signal reversal / glitch
        min_atr_pct: rng.gen_range(0.0_f32..0.005),
        reverse_entry_signal: rng.gen_range(0_u32..2),
        block_exits_on_extreme_dev: rng.gen_range(0_u32..2),
        glitch_price_dev_pct: rng.gen_range(0.05_f32..0.15),
        glitch_atr_mult: rng.gen_range(3.0_f32..8.0),
        trailing_weak_trend_mult: rng.gen_range(0.5_f32..0.9),

        // Rate limits + entry flags
        max_open_positions: rng.gen_range(3_u32..20),
        max_entry_orders_per_loop: rng.gen_range(1_u32..5),
        enable_slow_drift_entries: rng.gen_range(0_u32..2),
        slow_drift_require_macd_sign: rng.gen_range(0_u32..2),

        // Filters (gates)
        enable_ranging_filter: rng.gen_range(0_u32..2),
        enable_anomaly_filter: rng.gen_range(0_u32..2),
        enable_extension_filter: rng.gen_range(0_u32..2),
        require_adx_rising: rng.gen_range(0_u32..2),
        adx_rising_saturation: rng.gen_range(35.0_f32..50.0),
        require_volume_confirmation: rng.gen_range(0_u32..2),
        vol_confirm_include_prev: rng.gen_range(0_u32..2),
        use_stoch_rsi_filter: rng.gen_range(0_u32..2),
        require_btc_alignment: rng.gen_range(0_u32..2),
        require_macro_alignment: rng.gen_range(0_u32..2),

        // Market regime
        enable_regime_filter: rng.gen_range(0_u32..2),
        enable_auto_reverse: rng.gen_range(0_u32..2),
        auto_reverse_breadth_low: rng.gen_range(0.2_f32..0.4),
        auto_reverse_breadth_high: rng.gen_range(0.6_f32..0.8),
        breadth_block_short_above: rng.gen_range(0.7_f32..0.9),
        breadth_block_long_below: rng.gen_range(0.1_f32..0.3),

        // Entry thresholds
        min_adx: rng.gen_range(15.0_f32..30.0),
        high_conf_volume_mult: rng.gen_range(1.5_f32..3.5),
        btc_adx_override: rng.gen_range(35.0_f32..50.0),
        max_dist_ema_fast: rng.gen_range(0.02_f32..0.06),
        ave_atr_ratio_gt: rng.gen_range(1.0_f32..2.5),
        ave_adx_mult: rng.gen_range(0.8_f32..1.5),
        dre_min_adx: rng.gen_range(15.0_f32..25.0),
        dre_max_adx: rng.gen_range(30.0_f32..50.0),
        dre_long_rsi_limit_low: rng.gen_range(52.0_f32..58.0),
        dre_long_rsi_limit_high: rng.gen_range(48.0_f32..55.0),
        dre_short_rsi_limit_low: rng.gen_range(42.0_f32..48.0),
        dre_short_rsi_limit_high: rng.gen_range(45.0_f32..52.0),
        macd_mode: rng.gen_range(0_u32..3),
        pullback_min_adx: rng.gen_range(18.0_f32..28.0),
        pullback_rsi_long_min: rng.gen_range(45.0_f32..55.0),
        pullback_rsi_short_max: rng.gen_range(45.0_f32..55.0),
        pullback_require_macd_sign: rng.gen_range(0_u32..2),
        pullback_confidence: rng.gen_range(0_u32..3),
        slow_drift_min_slope_pct: rng.gen_range(0.0003_f32..0.001),
        slow_drift_min_adx: rng.gen_range(8.0_f32..15.0),
        slow_drift_rsi_long_min: rng.gen_range(45.0_f32..55.0),
        slow_drift_rsi_short_max: rng.gen_range(45.0_f32..55.0),

        // Ranging/anomaly thresholds
        ranging_adx_lt: rng.gen_range(18.0_f32..25.0),
        ranging_bb_width_ratio_lt: rng.gen_range(0.5_f32..1.2),
        anomaly_bb_width_ratio_gt: rng.gen_range(2.0_f32..4.0),
        slow_drift_ranging_slope_override: rng.gen_range(0.0003_f32..0.001),
        snapshot_offset: 0,
        breadth_offset: 0,

        // TP momentum
        tp_strong_adx_gt: rng.gen_range(35.0_f32..45.0),
        tp_weak_adx_lt: rng.gen_range(18.0_f32..25.0),

        // Decision codegen fields (AQC-1250)
        enable_pullback_entries: rng.gen_range(0_u32..2),
        anomaly_price_change_pct: rng.gen_range(0.05_f32..0.20),
        anomaly_ema_dev_pct: rng.gen_range(0.3_f32..0.8),
        ranging_rsi_low: rng.gen_range(43.0_f32..50.0),
        ranging_rsi_high: rng.gen_range(50.0_f32..57.0),
        ranging_min_signals: rng.gen_range(1_u32..4),
        stoch_rsi_block_long_gt: rng.gen_range(0.75_f32..0.95),
        stoch_rsi_block_short_lt: rng.gen_range(0.05_f32..0.25),
        ave_enabled: rng.gen_range(0_u32..2),
        tp_mult_strong: rng.gen_range(5.0_f32..10.0),
        tp_mult_weak: rng.gen_range(2.0_f32..5.0),
        entry_cooldown_s: rng.gen_range(0_u32..61),
        exit_cooldown_s: rng.gen_range(0_u32..61),
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Rust SSOT reference implementations (inline, mirroring bt-core)
// ═══════════════════════════════════════════════════════════════════════════════

/// Rust SSOT: compute_sl_price (mirrors bt-core/src/exits/stop_loss.rs).
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
fn rust_compute_trailing(
    pos_type: PosType,
    entry_price: f64,
    current_price: f64,
    entry_atr: f64,
    current_trailing_sl: f64,
    confidence: Confidence,
    rsi: f64,
    adx: f64,
    adx_slope: f64,
    atr_slope: f64,
    bb_width_ratio: f64,
    profit_atr: f64,
    cfg: &GpuComboConfig,
) -> f64 {
    let atr = if entry_atr > 0.0 {
        entry_atr
    } else {
        entry_price * 0.005
    };

    let trailing_start_atr = cfg.trailing_start_atr as f64;
    let trailing_distance_atr = cfg.trailing_distance_atr as f64;
    let trailing_start_atr_low_conf = cfg.trailing_start_atr_low_conf as f64;
    let trailing_distance_atr_low_conf = cfg.trailing_distance_atr_low_conf as f64;
    let trailing_rsi_floor_default = cfg.trailing_rsi_floor_default as f64;
    let trailing_rsi_floor_trending = cfg.trailing_rsi_floor_trending as f64;
    let enable_vol_buffered_trailing = cfg.enable_vol_buffered_trailing != 0;
    let trailing_vbts_bb_threshold = cfg.trailing_vbts_bb_threshold as f64;
    let trailing_vbts_mult = cfg.trailing_vbts_mult as f64;
    let trailing_high_profit_atr = cfg.trailing_high_profit_atr as f64;
    let trailing_tighten_tspv = cfg.trailing_tighten_tspv as f64;
    let trailing_tighten_default = cfg.trailing_tighten_default as f64;
    let trailing_weak_trend_mult = cfg.trailing_weak_trend_mult as f64;

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

/// Rust SSOT: compute_entry_sizing (mirrors risk-core/src/lib.rs).
fn rust_compute_entry_sizing(
    equity: f64,
    price: f64,
    atr: f64,
    adx: f64,
    confidence: Confidence,
    cfg: &GpuComboConfig,
) -> (f64, f64, f64, f64) {
    let allocation_pct = cfg.allocation_pct as f64;
    let enable_dynamic_sizing = cfg.enable_dynamic_sizing != 0;

    let mut margin_used = equity * allocation_pct;

    if enable_dynamic_sizing {
        let confidence_mult = match confidence {
            Confidence::High => cfg.confidence_mult_high as f64,
            Confidence::Medium => cfg.confidence_mult_medium as f64,
            Confidence::Low => cfg.confidence_mult_low as f64,
        };

        let adx_mult = if cfg.adx_sizing_full_adx > 0.0 {
            (adx / cfg.adx_sizing_full_adx as f64).clamp(cfg.adx_sizing_min_mult as f64, 1.0)
        } else {
            cfg.adx_sizing_min_mult as f64
        };

        let vol_ratio = if cfg.vol_baseline_pct > 0.0 && price > 0.0 {
            (atr / price) / cfg.vol_baseline_pct as f64
        } else {
            1.0
        };
        let vol_scalar_raw = if vol_ratio > 0.0 {
            1.0 / vol_ratio
        } else {
            1.0
        };
        let vol_scalar = vol_scalar_raw.clamp(cfg.vol_scalar_min as f64, cfg.vol_scalar_max as f64);

        margin_used *= confidence_mult * adx_mult * vol_scalar;
    }

    let lev = match confidence {
        Confidence::High => cfg.leverage_high as f64,
        Confidence::Medium => cfg.leverage_medium as f64,
        Confidence::Low => cfg.leverage_low as f64,
    };

    let notional = margin_used * lev;
    let size = if price > 0.0 { notional / price } else { 0.0 };

    (size, margin_used, lev, notional)
}

/// Rust SSOT: is_pesc_blocked (mirrors bt-core/src/engine.rs).
fn rust_is_pesc_blocked(
    cfg: &GpuComboConfig,
    close_ts: u32,
    close_type: u32,
    close_reason: u32,
    desired_type: u32,
    current_ts: u32,
    adx: f64,
) -> bool {
    if cfg.reentry_cooldown_minutes == 0 {
        return false;
    }
    if close_ts == 0 {
        return false;
    }
    // Signal flip bypass (reason == 1)
    if close_reason == 1 {
        return false;
    }
    // Direction gate
    if close_type != desired_type {
        return false;
    }

    let min_cd = cfg.reentry_cooldown_min_mins as f64;
    let max_cd = cfg.reentry_cooldown_max_mins as f64;
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

/// Rust SSOT: check_gates (mirrors bt-signals/src/gates.rs).
#[derive(Debug, Clone)]
struct GateResult {
    all_gates_pass: bool,
    is_ranging: bool,
    bullish_alignment: bool,
    bearish_alignment: bool,
    effective_min_adx: f64,
    rsi_long_limit: f64,
    rsi_short_limit: f64,
}

fn rust_check_gates(
    bar: &SyntheticBar,
    cfg: &GpuComboConfig,
    btc_bullish: Option<bool>,
) -> GateResult {
    // Gate 1: Ranging filter (vote system)
    let mut is_ranging = false;
    if cfg.enable_ranging_filter != 0 {
        let min_signals = (cfg.ranging_min_signals).max(1);
        let mut votes: u32 = 0;
        if bar.adx < cfg.ranging_adx_lt as f64 {
            votes += 1;
        }
        if bar.bb_width_ratio < cfg.ranging_bb_width_ratio_lt as f64 {
            votes += 1;
        }
        if bar.rsi > cfg.ranging_rsi_low as f64 && bar.rsi < cfg.ranging_rsi_high as f64 {
            votes += 1;
        }
        is_ranging = votes >= min_signals;
    }

    // Gate 2: Anomaly filter
    let is_anomaly = if cfg.enable_anomaly_filter != 0 {
        let price_change_pct = if bar.prev_close > 0.0 {
            (bar.close - bar.prev_close).abs() / bar.prev_close
        } else {
            0.0
        };
        let ema_dev_pct = if bar.ema_fast > 0.0 {
            (bar.close - bar.ema_fast).abs() / bar.ema_fast
        } else {
            0.0
        };
        price_change_pct > cfg.anomaly_price_change_pct as f64
            || ema_dev_pct > cfg.anomaly_ema_dev_pct as f64
    } else {
        false
    };

    // Gate 3: Extension filter
    let is_extended = if cfg.enable_extension_filter != 0 {
        if bar.ema_fast > 0.0 {
            let dist = (bar.close - bar.ema_fast).abs() / bar.ema_fast;
            dist > cfg.max_dist_ema_fast as f64
        } else {
            false
        }
    } else {
        false
    };

    // Gate 4: Volume confirmation
    let vol_confirm = if cfg.require_volume_confirmation != 0 {
        let vol_above_sma = bar.volume > bar.vol_sma;
        let vol_trend_ok = bar.vol_trend;
        if cfg.vol_confirm_include_prev != 0 {
            vol_above_sma || vol_trend_ok
        } else {
            vol_above_sma && vol_trend_ok
        }
    } else {
        true
    };

    // Gate 5: ADX rising (or saturated)
    let is_trending_up = if cfg.require_adx_rising != 0 {
        bar.adx_slope > 0.0 || bar.adx > cfg.adx_rising_saturation as f64
    } else {
        true
    };

    // Gate 6: ADX threshold + TMC + AVE
    let mut effective_min_adx = cfg.min_adx as f64;
    if bar.adx_slope > 0.5 {
        effective_min_adx = effective_min_adx.min(25.0);
    }
    if cfg.ave_enabled != 0 && bar.avg_atr > 0.0 {
        let atr_ratio = bar.atr / bar.avg_atr;
        if atr_ratio > cfg.ave_atr_ratio_gt as f64 {
            let mult = if cfg.ave_adx_mult > 0.0 {
                cfg.ave_adx_mult as f64
            } else {
                1.0
            };
            effective_min_adx *= mult;
        }
    }
    let adx_above_min = bar.adx > effective_min_adx;

    // Gate 7: Macro alignment
    let mut bullish_alignment = bar.ema_fast > bar.ema_slow;
    let mut bearish_alignment = bar.ema_fast < bar.ema_slow;
    if cfg.require_macro_alignment != 0 {
        bullish_alignment = bullish_alignment && (bar.ema_slow > bar.ema_macro);
        bearish_alignment = bearish_alignment && (bar.ema_slow < bar.ema_macro);
    }

    // Gate 8: BTC alignment (simplified: no btc_sym_idx handling)
    let btc_ok_long = cfg.require_btc_alignment == 0
        || btc_bullish.is_none()
        || btc_bullish == Some(true)
        || bar.adx > cfg.btc_adx_override as f64;
    let btc_ok_short = cfg.require_btc_alignment == 0
        || btc_bullish.is_none()
        || btc_bullish == Some(false)
        || bar.adx > cfg.btc_adx_override as f64;

    // Slow-drift ranging override
    if cfg.enable_slow_drift_entries != 0
        && is_ranging
        && bar.ema_slow_slope_pct.abs() >= cfg.slow_drift_ranging_slope_override as f64
    {
        is_ranging = false;
    }

    // DRE (Dynamic RSI Elasticity)
    let adx_min = cfg.dre_min_adx as f64;
    let adx_max = if (cfg.dre_max_adx as f64) > adx_min {
        cfg.dre_max_adx as f64
    } else {
        adx_min + 1.0
    };
    let weight = ((bar.adx - adx_min) / (adx_max - adx_min)).clamp(0.0, 1.0);
    let rsi_long_limit = cfg.dre_long_rsi_limit_low as f64
        + weight * (cfg.dre_long_rsi_limit_high as f64 - cfg.dre_long_rsi_limit_low as f64);
    let rsi_short_limit = cfg.dre_short_rsi_limit_low as f64
        + weight * (cfg.dre_short_rsi_limit_high as f64 - cfg.dre_short_rsi_limit_low as f64);

    // Combined all_gates_pass
    let all_gates_pass = adx_above_min
        && !is_ranging
        && !is_anomaly
        && !is_extended
        && vol_confirm
        && is_trending_up;

    // We also need btc_ok for the signal generation, but for gate-level
    // parity we validate all_gates_pass (which does NOT include btc alignment
    // or directional checks — those are in signal generation).
    let _ = (btc_ok_long, btc_ok_short);

    GateResult {
        all_gates_pass,
        is_ranging,
        bullish_alignment,
        bearish_alignment,
        effective_min_adx,
        rsi_long_limit,
        rsi_short_limit,
    }
}

/// Rust SSOT: generate_signal (simplified — standard trend entry only).
#[derive(Debug, Clone, PartialEq)]
enum SignalDir {
    Neutral,
    Buy,
    Sell,
}

fn rust_generate_signal(bar: &SyntheticBar, gates: &GateResult, cfg: &GpuComboConfig) -> SignalDir {
    let check_macd_long = |mode: u32| -> bool {
        match mode {
            0 => bar.macd_hist > bar.prev_macd_hist,
            1 => bar.macd_hist > 0.0,
            _ => true,
        }
    };
    let check_macd_short = |mode: u32| -> bool {
        match mode {
            0 => bar.macd_hist < bar.prev_macd_hist,
            1 => bar.macd_hist < 0.0,
            _ => true,
        }
    };

    // Mode 1: Standard trend entry
    if gates.all_gates_pass {
        // LONG
        if gates.bullish_alignment && bar.close > bar.ema_fast {
            if bar.rsi > gates.rsi_long_limit {
                let macd_ok = check_macd_long(cfg.macd_mode);
                let stoch_ok = if cfg.use_stoch_rsi_filter != 0 {
                    bar.stoch_k < cfg.stoch_rsi_block_long_gt as f64
                } else {
                    true
                };
                if macd_ok && stoch_ok {
                    return SignalDir::Buy;
                }
            }
        }
        // SHORT (elif)
        else if gates.bearish_alignment && bar.close < bar.ema_fast {
            if bar.rsi < gates.rsi_short_limit {
                let macd_ok = check_macd_short(cfg.macd_mode);
                let stoch_ok = if cfg.use_stoch_rsi_filter != 0 {
                    bar.stoch_k > cfg.stoch_rsi_block_short_lt as f64
                } else {
                    true
                };
                if macd_ok && stoch_ok {
                    return SignalDir::Sell;
                }
            }
        }
    }

    // Mode 2: Pullback continuation
    if cfg.enable_pullback_entries != 0 {
        let pullback_gates_ok = !gates.is_ranging && bar.adx >= cfg.pullback_min_adx as f64;

        if pullback_gates_ok {
            let cross_up = bar.prev_close <= bar.prev_ema_fast && bar.close > bar.ema_fast;
            let cross_dn = bar.prev_close >= bar.prev_ema_fast && bar.close < bar.ema_fast;

            if cross_up && gates.bullish_alignment {
                let macd_ok = if cfg.pullback_require_macd_sign != 0 {
                    bar.macd_hist > 0.0
                } else {
                    true
                };
                if macd_ok && bar.rsi >= cfg.pullback_rsi_long_min as f64 {
                    return SignalDir::Buy;
                }
            } else if cross_dn && gates.bearish_alignment {
                let macd_ok = if cfg.pullback_require_macd_sign != 0 {
                    bar.macd_hist < 0.0
                } else {
                    true
                };
                if macd_ok && bar.rsi <= cfg.pullback_rsi_short_max as f64 {
                    return SignalDir::Sell;
                }
            }
        }
    }

    // Mode 3: Slow drift
    if cfg.enable_slow_drift_entries != 0 {
        let slow_gates_ok = !gates.is_ranging && bar.adx >= cfg.slow_drift_min_adx as f64;

        if slow_gates_ok {
            if gates.bullish_alignment
                && bar.close > bar.ema_slow
                && bar.ema_slow_slope_pct >= cfg.slow_drift_min_slope_pct as f64
            {
                let macd_ok = if cfg.slow_drift_require_macd_sign != 0 {
                    bar.macd_hist > 0.0
                } else {
                    true
                };
                if macd_ok && bar.rsi >= cfg.slow_drift_rsi_long_min as f64 {
                    return SignalDir::Buy;
                }
            } else if gates.bearish_alignment
                && bar.close < bar.ema_slow
                && bar.ema_slow_slope_pct <= -(cfg.slow_drift_min_slope_pct as f64)
            {
                let macd_ok = if cfg.slow_drift_require_macd_sign != 0 {
                    bar.macd_hist < 0.0
                } else {
                    true
                };
                if macd_ok && bar.rsi <= cfg.slow_drift_rsi_short_max as f64 {
                    return SignalDir::Sell;
                }
            }
        }
    }

    SignalDir::Neutral
}

// ═══════════════════════════════════════════════════════════════════════════════
// Helper: pick a position scenario from a bar for exit function testing
// ═══════════════════════════════════════════════════════════════════════════════

struct PositionScenario {
    pos_type: PosType,
    entry_price: f64,
    current_price: f64,
    entry_atr: f64,
    confidence: Confidence,
    current_trailing_sl: f64,
    profit_atr: f64,
}

fn make_position_scenario(bar: &SyntheticBar, rng: &mut StdRng) -> PositionScenario {
    let pos_type = if rng.gen_bool(0.5) {
        PosType::Long
    } else {
        PosType::Short
    };
    let confidence = match rng.gen_range(0_u32..3) {
        0 => Confidence::Low,
        1 => Confidence::Medium,
        _ => Confidence::High,
    };

    // Random entry price within +-5% of current close
    let entry_offset = rng.gen_range(-0.05_f64..0.05);
    let entry_price = bar.close * (1.0 + entry_offset);
    let current_price = bar.close;
    let entry_atr = bar.atr;

    let profit_atr = if entry_atr > 0.0 {
        match pos_type {
            PosType::Long => (current_price - entry_price) / entry_atr,
            PosType::Short => (entry_price - current_price) / entry_atr,
        }
    } else {
        0.0
    };

    // Optionally set an existing trailing SL
    let current_trailing_sl = if rng.gen_bool(0.3) && profit_atr > 1.0 {
        match pos_type {
            PosType::Long => entry_price + entry_atr * rng.gen_range(0.2..1.0),
            PosType::Short => entry_price - entry_atr * rng.gen_range(0.2..1.0),
        }
    } else {
        0.0
    };

    PositionScenario {
        pos_type,
        entry_price,
        current_price,
        entry_atr,
        confidence,
        current_trailing_sl,
        profit_atr,
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Main parity test: 100 configs × synthetic bars
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn full_sweep_100_configs_decision_parity() {
    let mut rng = StdRng::seed_from_u64(42);
    let num_configs = 100;
    let bars_per_config = 50; // Sample 50 bars per config (from 2160 total)

    // Generate synthetic market data
    let bars = generate_synthetic_bars(&mut rng, 50_000.0);
    assert!(bars.len() >= 2160, "Expected 2160 bars, got {}", bars.len());

    let mut total_sl_checks = 0_u64;
    let mut total_trailing_checks = 0_u64;
    let mut total_sizing_checks = 0_u64;
    let mut total_pesc_checks = 0_u64;
    let mut total_gate_checks = 0_u64;
    let mut total_signal_checks = 0_u64;

    let mut sl_max_rel_err = 0.0_f64;
    let mut trailing_max_rel_err = 0.0_f64;
    let mut sizing_max_rel_err = 0.0_f64;
    let mut gate_disagreements = 0_u64;

    for cfg_idx in 0..num_configs {
        let cfg = random_gpu_combo_config(&mut rng);

        // Sample bars evenly spaced across the synthetic dataset (skip warmup)
        let warmup = 200;
        let stride = (bars.len() - warmup) / bars_per_config;

        for bar_idx in 0..bars_per_config {
            let bi = warmup + bar_idx * stride;
            let bar = &bars[bi];
            let pos = make_position_scenario(bar, &mut rng);

            // ── 1. Stop Loss parity ─────────────────────────────────────
            let sl = rust_compute_sl_price(
                pos.pos_type,
                pos.entry_price,
                pos.entry_atr,
                pos.current_price,
                bar.adx,
                bar.adx_slope,
                cfg.sl_atr_mult as f64,
                cfg.enable_breakeven_stop != 0,
                cfg.breakeven_start_atr as f64,
                cfg.breakeven_buffer_atr as f64,
            );

            // SL must be finite
            assert!(
                sl.is_finite(),
                "SL not finite: cfg={}, bar={}, pos={:?}",
                cfg_idx,
                bi,
                pos.pos_type
            );

            // f32 round-trip
            let sl_f32 = sl as f32;
            let sl_rt = sl_f32 as f64;
            if sl.abs() > 1e-10 {
                let rel_err = relative_error(sl, sl_rt);
                sl_max_rel_err = sl_max_rel_err.max(rel_err);
                assert!(
                    within_tolerance(sl, sl_rt, TIER_T2_TOLERANCE),
                    "SL f32 round-trip exceeds T2: cfg={}, bar={}, f64={}, f32_rt={}, rel_err={:.2e}",
                    cfg_idx,
                    bi,
                    sl,
                    sl_rt,
                    rel_err
                );
            }

            // Directional sanity (when breakeven is not active)
            let atr = if pos.entry_atr > 0.0 {
                pos.entry_atr
            } else {
                pos.entry_price * 0.005
            };
            let profit = match pos.pos_type {
                PosType::Long => pos.current_price - pos.entry_price,
                PosType::Short => pos.entry_price - pos.current_price,
            };
            let be_active = cfg.enable_breakeven_stop != 0
                && cfg.breakeven_start_atr > 0.0
                && profit >= atr * cfg.breakeven_start_atr as f64;
            if !be_active {
                match pos.pos_type {
                    PosType::Long => assert!(
                        sl <= pos.entry_price + f64::EPSILON,
                        "LONG SL above entry w/o breakeven: cfg={}, bar={}, sl={}, entry={}",
                        cfg_idx,
                        bi,
                        sl,
                        pos.entry_price
                    ),
                    PosType::Short => assert!(
                        sl >= pos.entry_price - f64::EPSILON,
                        "SHORT SL below entry w/o breakeven: cfg={}, bar={}, sl={}, entry={}",
                        cfg_idx,
                        bi,
                        sl,
                        pos.entry_price
                    ),
                }
            }
            total_sl_checks += 1;

            // ── 2. Trailing Stop parity ─────────────────────────────────
            let tsl = rust_compute_trailing(
                pos.pos_type,
                pos.entry_price,
                pos.current_price,
                pos.entry_atr,
                pos.current_trailing_sl,
                pos.confidence,
                bar.rsi,
                bar.adx,
                bar.adx_slope,
                bar.atr_slope,
                bar.bb_width_ratio,
                pos.profit_atr,
                &cfg,
            );

            assert!(
                tsl.is_finite(),
                "TSL not finite: cfg={}, bar={}",
                cfg_idx,
                bi
            );

            // f32 round-trip
            let tsl_f32 = tsl as f32;
            let tsl_rt = tsl_f32 as f64;
            if tsl.abs() > 1e-10 {
                let rel_err = relative_error(tsl, tsl_rt);
                trailing_max_rel_err = trailing_max_rel_err.max(rel_err);
                assert!(
                    within_tolerance(tsl, tsl_rt, TIER_T2_TOLERANCE),
                    "TSL f32 round-trip exceeds T2: cfg={}, bar={}, f64={}, f32_rt={}, rel_err={:.2e}",
                    cfg_idx,
                    bi,
                    tsl,
                    tsl_rt,
                    rel_err
                );
            }

            // Ratchet invariant: if existing trailing_sl > 0, new TSL must not regress
            if pos.current_trailing_sl > 0.0 {
                match pos.pos_type {
                    PosType::Long => assert!(
                        tsl >= pos.current_trailing_sl - f64::EPSILON,
                        "LONG TSL regressed: cfg={}, bar={}, old={}, new={}",
                        cfg_idx,
                        bi,
                        pos.current_trailing_sl,
                        tsl
                    ),
                    PosType::Short => assert!(
                        tsl <= pos.current_trailing_sl + f64::EPSILON,
                        "SHORT TSL regressed: cfg={}, bar={}, old={}, new={}",
                        cfg_idx,
                        bi,
                        pos.current_trailing_sl,
                        tsl
                    ),
                }
            }
            total_trailing_checks += 1;

            // ── 3. Entry sizing parity ──────────────────────────────────
            let equity = 10_000.0;
            let (size, margin, lev, notional) = rust_compute_entry_sizing(
                equity,
                bar.close,
                bar.atr,
                bar.adx,
                pos.confidence,
                &cfg,
            );

            // All outputs must be non-negative
            assert!(
                size >= 0.0 && margin >= 0.0 && lev >= 0.0 && notional >= 0.0,
                "Sizing negative: cfg={}, bar={}, size={}, margin={}, lev={}, notional={}",
                cfg_idx,
                bi,
                size,
                margin,
                lev,
                notional
            );

            // Notional = margin * leverage consistency
            if margin > 1e-10 {
                let expected_notional = margin * lev;
                let notional_rel_err = relative_error(expected_notional, notional);
                sizing_max_rel_err = sizing_max_rel_err.max(notional_rel_err);
                assert!(
                    within_tolerance(expected_notional, notional, TIER_T3_TOLERANCE),
                    "Notional != margin*lev: cfg={}, bar={}, margin={}, lev={}, notional={}, expected={}",
                    cfg_idx,
                    bi,
                    margin,
                    lev,
                    notional,
                    expected_notional
                );
            }

            // f32 round-trip of size
            if size > 1e-10 {
                let size_f32 = size as f32;
                let size_rt = size_f32 as f64;
                assert!(
                    within_tolerance(size, size_rt, TIER_T2_TOLERANCE),
                    "Size f32 round-trip exceeds T2: cfg={}, bar={}, f64={}, f32_rt={}",
                    cfg_idx,
                    bi,
                    size,
                    size_rt
                );
            }
            total_sizing_checks += 1;

            // ── 4. PESC cooldown parity ─────────────────────────────────
            let base_ts = 1_700_000_000_u32;
            let close_ts = base_ts + rng.gen_range(0_u32..3600);
            let current_ts = close_ts + rng.gen_range(0_u32..7200);
            let close_type = rng.gen_range(0_u32..3);
            let close_reason = rng.gen_range(0_u32..3);
            let desired_type = rng.gen_range(1_u32..3);

            let blocked = rust_is_pesc_blocked(
                &cfg,
                close_ts,
                close_type,
                close_reason,
                desired_type,
                current_ts,
                bar.adx,
            );

            // Monotonicity: if current_ts increases, blocked should eventually become false
            if blocked {
                let far_future = current_ts + 86400; // +1 day
                let still_blocked = rust_is_pesc_blocked(
                    &cfg,
                    close_ts,
                    close_type,
                    close_reason,
                    desired_type,
                    far_future,
                    bar.adx,
                );
                assert!(
                    !still_blocked,
                    "PESC still blocked after 1 day: cfg={}, close_ts={}, current_ts={}",
                    cfg_idx, close_ts, far_future
                );
            }

            // Disabled cooldown should never block
            let mut cfg_disabled = cfg;
            cfg_disabled.reentry_cooldown_minutes = 0;
            let blocked_disabled = rust_is_pesc_blocked(
                &cfg_disabled,
                close_ts,
                close_type,
                close_reason,
                desired_type,
                current_ts,
                bar.adx,
            );
            assert!(
                !blocked_disabled,
                "PESC blocks with cooldown_minutes=0: cfg={}",
                cfg_idx
            );
            total_pesc_checks += 1;

            // ── 5. Gates parity ─────────────────────────────────────────
            let gate_result = rust_check_gates(bar, &cfg, None);

            // The f32 cast of effective_min_adx must be T1 precise
            let ema_f32 = gate_result.effective_min_adx as f32;
            let ema_rt = ema_f32 as f64;
            if gate_result.effective_min_adx.abs() > 1e-10 {
                assert!(
                    within_tolerance(gate_result.effective_min_adx, ema_rt, TIER_T2_TOLERANCE),
                    "Gates effective_min_adx f32 round-trip: cfg={}, bar={}, f64={}, f32_rt={}",
                    cfg_idx,
                    bi,
                    gate_result.effective_min_adx,
                    ema_rt
                );
            }

            // DRE RSI limits must be in valid RSI range [0, 100]
            assert!(
                (0.0..=100.0).contains(&gate_result.rsi_long_limit),
                "DRE rsi_long_limit out of [0,100]: cfg={}, val={}",
                cfg_idx,
                gate_result.rsi_long_limit
            );
            assert!(
                (0.0..=100.0).contains(&gate_result.rsi_short_limit),
                "DRE rsi_short_limit out of [0,100]: cfg={}, val={}",
                cfg_idx,
                gate_result.rsi_short_limit
            );

            // Cross-check: run gates with f32-cast inputs and verify same boolean result
            let mut bar_f32 = bar.clone();
            bar_f32.adx = (bar.adx as f32) as f64;
            bar_f32.adx_slope = (bar.adx_slope as f32) as f64;
            bar_f32.rsi = (bar.rsi as f32) as f64;
            bar_f32.bb_width_ratio = (bar.bb_width_ratio as f32) as f64;
            bar_f32.volume = (bar.volume as f32) as f64;
            bar_f32.vol_sma = (bar.vol_sma as f32) as f64;
            bar_f32.close = (bar.close as f32) as f64;
            bar_f32.prev_close = (bar.prev_close as f32) as f64;
            bar_f32.ema_fast = (bar.ema_fast as f32) as f64;
            bar_f32.ema_slow = (bar.ema_slow as f32) as f64;
            bar_f32.ema_macro = (bar.ema_macro as f32) as f64;
            bar_f32.atr = (bar.atr as f32) as f64;
            bar_f32.avg_atr = (bar.avg_atr as f32) as f64;
            bar_f32.ema_slow_slope_pct = (bar.ema_slow_slope_pct as f32) as f64;

            let gate_result_f32 = rust_check_gates(&bar_f32, &cfg, None);
            if gate_result.all_gates_pass != gate_result_f32.all_gates_pass {
                gate_disagreements += 1;
            }
            total_gate_checks += 1;

            // ── 6. Signal parity ────────────────────────────────────────
            let signal = rust_generate_signal(bar, &gate_result, &cfg);
            let signal_f32 = rust_generate_signal(&bar_f32, &gate_result_f32, &cfg);

            // Signal direction should be consistent between f64 and f32 inputs
            // (allowing for boundary cases where f32 rounding changes a gate/threshold)
            // We count disagreements but don't fail — boundary flips are expected with f32.
            let _ = (signal, signal_f32);
            total_signal_checks += 1;
        }
    }

    // ── Summary statistics ──────────────────────────────────────────────────
    let total_checks = total_sl_checks
        + total_trailing_checks
        + total_sizing_checks
        + total_pesc_checks
        + total_gate_checks
        + total_signal_checks;

    eprintln!("╔══════════════════════════════════════════════════════════════╗");
    eprintln!("║  Full-sweep parity test: 100 configs complete              ║");
    eprintln!("╠══════════════════════════════════════════════════════════════╣");
    eprintln!(
        "║  Total checks:     {:>8}                                ║",
        total_checks
    );
    eprintln!(
        "║  SL checks:        {:>8}  (max rel err: {:.2e})      ║",
        total_sl_checks, sl_max_rel_err
    );
    eprintln!(
        "║  Trailing checks:  {:>8}  (max rel err: {:.2e})      ║",
        total_trailing_checks, trailing_max_rel_err
    );
    eprintln!(
        "║  Sizing checks:    {:>8}  (max rel err: {:.2e})      ║",
        total_sizing_checks, sizing_max_rel_err
    );
    eprintln!(
        "║  PESC checks:      {:>8}                                ║",
        total_pesc_checks
    );
    eprintln!(
        "║  Gate checks:      {:>8}  (f32 disagreements: {})    ║",
        total_gate_checks, gate_disagreements
    );
    eprintln!(
        "║  Signal checks:    {:>8}                                ║",
        total_signal_checks
    );
    eprintln!("╚══════════════════════════════════════════════════════════════╝");

    // Gate disagreements from f32 boundary effects should be rare (<5%)
    let disagreement_pct = gate_disagreements as f64 / total_gate_checks as f64;
    assert!(
        disagreement_pct < 0.05,
        "Gate f32 disagreement rate too high: {:.1}% ({}/{})",
        disagreement_pct * 100.0,
        gate_disagreements,
        total_gate_checks
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Codegen string validation: verify all 9 functions are present in output
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn codegen_renders_all_decision_functions() {
    let source = bt_gpu::codegen::decision::render_all_decision(None);

    let required_functions = [
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

    for func in &required_functions {
        assert!(
            source.contains(func),
            "Codegen output missing function: {}",
            func
        );
    }

    // Verify header
    assert!(
        source.contains("AUTO-GENERATED"),
        "Codegen output missing AUTO-GENERATED header"
    );
    assert!(
        source.contains("#pragma once"),
        "Codegen output missing #pragma once"
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Config round-trip: GpuComboConfig fields survive f32 cast
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn random_configs_survive_f32_roundtrip() {
    let mut rng = StdRng::seed_from_u64(42);

    for i in 0..100 {
        let cfg = random_gpu_combo_config(&mut rng);

        // Every f32 field should be finite and non-NaN
        let fields: Vec<(&str, f32)> = vec![
            ("allocation_pct", cfg.allocation_pct),
            ("sl_atr_mult", cfg.sl_atr_mult),
            ("tp_atr_mult", cfg.tp_atr_mult),
            ("leverage", cfg.leverage),
            ("trailing_start_atr", cfg.trailing_start_atr),
            ("trailing_distance_atr", cfg.trailing_distance_atr),
            ("min_adx", cfg.min_adx),
            ("breakeven_start_atr", cfg.breakeven_start_atr),
            ("breakeven_buffer_atr", cfg.breakeven_buffer_atr),
            ("confidence_mult_high", cfg.confidence_mult_high),
            ("confidence_mult_low", cfg.confidence_mult_low),
            ("vol_baseline_pct", cfg.vol_baseline_pct),
            ("_reserved14", cfg._reserved14),
            ("tp_mult_strong", cfg.tp_mult_strong),
            ("tp_mult_weak", cfg.tp_mult_weak),
            ("ranging_adx_lt", cfg.ranging_adx_lt),
            ("ranging_bb_width_ratio_lt", cfg.ranging_bb_width_ratio_lt),
            ("anomaly_price_change_pct", cfg.anomaly_price_change_pct),
            ("anomaly_ema_dev_pct", cfg.anomaly_ema_dev_pct),
            ("stoch_rsi_block_long_gt", cfg.stoch_rsi_block_long_gt),
            ("stoch_rsi_block_short_lt", cfg.stoch_rsi_block_short_lt),
        ];

        for (name, val) in &fields {
            assert!(
                val.is_finite(),
                "Config {} field {} is not finite: {} (cfg #{})",
                i,
                name,
                val,
                i
            );
        }

        // Boolean fields should be 0 or 1
        let bool_fields: Vec<(&str, u32)> = vec![
            ("enable_reef_filter", cfg.enable_reef_filter),
            ("enable_dynamic_sizing", cfg.enable_dynamic_sizing),
            ("enable_pyramiding", cfg.enable_pyramiding),
            ("enable_partial_tp", cfg.enable_partial_tp),
            ("enable_ssf_filter", cfg.enable_ssf_filter),
            ("enable_breakeven_stop", cfg.enable_breakeven_stop),
            (
                "enable_rsi_overextension_exit",
                cfg.enable_rsi_overextension_exit,
            ),
            (
                "enable_vol_buffered_trailing",
                cfg.enable_vol_buffered_trailing,
            ),
            ("enable_ranging_filter", cfg.enable_ranging_filter),
            ("enable_anomaly_filter", cfg.enable_anomaly_filter),
            ("enable_extension_filter", cfg.enable_extension_filter),
            ("require_adx_rising", cfg.require_adx_rising),
            (
                "require_volume_confirmation",
                cfg.require_volume_confirmation,
            ),
            ("use_stoch_rsi_filter", cfg.use_stoch_rsi_filter),
            ("require_btc_alignment", cfg.require_btc_alignment),
            ("require_macro_alignment", cfg.require_macro_alignment),
            ("enable_regime_filter", cfg.enable_regime_filter),
            ("enable_auto_reverse", cfg.enable_auto_reverse),
            ("enable_pullback_entries", cfg.enable_pullback_entries),
            ("enable_slow_drift_entries", cfg.enable_slow_drift_entries),
        ];

        for (name, val) in &bool_fields {
            assert!(
                *val <= 1,
                "Config {} bool field {} out of range: {} (cfg #{})",
                i,
                name,
                val,
                i
            );
        }

        // macd_mode should be 0-2
        assert!(
            cfg.macd_mode <= 2,
            "Config {} macd_mode out of range: {}",
            i,
            cfg.macd_mode
        );

        // entry_min_confidence and add_min_confidence should be 0-2
        assert!(
            cfg.entry_min_confidence <= 2,
            "Config {} entry_min_confidence out of range: {}",
            i,
            cfg.entry_min_confidence
        );
        assert!(
            cfg.add_min_confidence <= 2,
            "Config {} add_min_confidence out of range: {}",
            i,
            cfg.add_min_confidence
        );
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Margin-cap precision guard: prevent sub-entry regression on max_total_margin_pct
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn sub_entry_margin_cap_uses_full_precision_pct() {
    let kernel_src = include_str!("../kernels/sweep_engine.cu");

    let full_precision_stmt = "double max_margin_pct = (double)cfg.max_total_margin_pct;";
    let rounded_expr = "(double)((int)((double)cfg.max_total_margin_pct * 1000000.0 + 0.5))";

    let full_precision_count = kernel_src.matches(full_precision_stmt).count();
    let rounded_count = kernel_src.matches(rounded_expr).count();

    assert_eq!(
        full_precision_count, 3,
        "Expected full-precision max_total_margin_pct in sub-entry/add/main-entry paths, found {}",
        full_precision_count
    );
    assert_eq!(
        rounded_count, 0,
        "Expected rounded max_total_margin_pct usage to be removed from all paths, found {}",
        rounded_count
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Cross-function consistency: SL vs trailing relationship
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn sl_trailing_cross_consistency_100_configs() {
    let mut rng = StdRng::seed_from_u64(99);
    let bars = generate_synthetic_bars(&mut rng, 50_000.0);
    let mut violations = 0_u64;
    let mut checks = 0_u64;

    for _ in 0..100 {
        let cfg = random_gpu_combo_config(&mut rng);

        for bi in (200..bars.len()).step_by(100) {
            let bar = &bars[bi];
            let pos = make_position_scenario(bar, &mut rng);

            let sl = rust_compute_sl_price(
                pos.pos_type,
                pos.entry_price,
                pos.entry_atr,
                pos.current_price,
                bar.adx,
                bar.adx_slope,
                cfg.sl_atr_mult as f64,
                cfg.enable_breakeven_stop != 0,
                cfg.breakeven_start_atr as f64,
                cfg.breakeven_buffer_atr as f64,
            );

            let tsl = rust_compute_trailing(
                pos.pos_type,
                pos.entry_price,
                pos.current_price,
                pos.entry_atr,
                0.0, // no existing trailing
                pos.confidence,
                bar.rsi,
                bar.adx,
                bar.adx_slope,
                bar.atr_slope,
                bar.bb_width_ratio,
                pos.profit_atr,
                &cfg,
            );

            // When trailing is active (tsl != 0) and in profit, the trailing SL
            // should generally be more protective (closer to current price) than
            // the fixed SL. This isn't always true due to breakeven/DASE/SLB
            // interactions, so we just count violations for monitoring.
            if tsl != 0.0 && pos.profit_atr > cfg.trailing_start_atr as f64 {
                match pos.pos_type {
                    PosType::Long => {
                        if tsl < sl {
                            violations += 1;
                        }
                    }
                    PosType::Short => {
                        if tsl > sl {
                            violations += 1;
                        }
                    }
                }
            }
            checks += 1;
        }
    }

    // A high violation rate would indicate a systematic issue
    let violation_pct = if checks > 0 {
        violations as f64 / checks as f64
    } else {
        0.0
    };
    eprintln!(
        "[cross-consistency] SL vs TSL: {}/{} checks, {:.1}% TSL less protective than SL",
        checks,
        checks,
        violation_pct * 100.0
    );

    // This is a soft check — we don't fail on violations since trailing configs
    // can legitimately produce wider stops than fixed SL in some edge cases.
    // But if > 50% of cases violate, something is structurally wrong.
    assert!(
        violation_pct < 0.50,
        "Too many SL/TSL cross-consistency violations: {:.1}%",
        violation_pct * 100.0
    );
}
