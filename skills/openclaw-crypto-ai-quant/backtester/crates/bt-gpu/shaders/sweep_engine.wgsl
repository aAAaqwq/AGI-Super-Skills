// ═══════════════════════════════════════════════════════════════════════════
// DEPRECATED (AQC-1241): This WGSL shader is no longer maintained.
// The production GPU sweep uses CUDA (sweep_engine.cu) with codegen'd
// decision functions. This file is retained for reference only.
// Known divergences from CUDA: hardcoded params, inverted RSI logic,
// missing BTC alignment, struct field name bugs, no codegen integration.
// ═══════════════════════════════════════════════════════════════════════════
//
// GPU Sweep Engine — WGSL Compute Shader (DEPRECATED)
// ═══════════════════════════════════════════════════════════════════════════
//
// Mirrors the Rust backtester trade logic for parameter sweep.
// Indicators are precomputed on CPU; this shader only runs trade decisions.
//
// Buffer layout:
//   @binding(0) params    — uniform GpuParams
//   @binding(1) snapshots — read-only storage, [num_bars × num_symbols]
//   @binding(2) breadth   — read-only storage, [num_bars]
//   @binding(3) btc_bull  — read-only storage, [num_bars]
//   @binding(4) configs   — read-only storage, [num_combos]
//   @binding(5) states    — read-write storage, [num_combos]
//   @binding(6) results   — read-write storage, [num_combos]

// ── Constants ───────────────────────────────────────────────────────────────
const MAX_SYMBOLS: u32 = 52u;
const MAX_CANDIDATES: u32 = 8u;

// Position type constants
const POS_EMPTY: u32 = 0u;
const POS_LONG: u32 = 1u;
const POS_SHORT: u32 = 2u;

// Signal constants
const SIG_NEUTRAL: u32 = 0u;
const SIG_BUY: u32 = 1u;
const SIG_SELL: u32 = 2u;

// Confidence constants
const CONF_LOW: u32 = 0u;
const CONF_MEDIUM: u32 = 1u;
const CONF_HIGH: u32 = 2u;

// MACD mode
const MACD_ACCEL: u32 = 0u;
const MACD_SIGN: u32 = 1u;
const MACD_NONE: u32 = 2u;

// PESC close reasons
const PESC_NONE: u32 = 0u;
const PESC_SIGNAL_FLIP: u32 = 1u;
const PESC_OTHER: u32 = 2u;

// ── Structs ─────────────────────────────────────────────────────────────────

struct GpuParams {
    num_combos: u32,
    num_symbols: u32,
    num_bars: u32,
    btc_sym_idx: u32,
    chunk_start: u32,
    chunk_end: u32,
    initial_balance_bits: u32,
    maker_fee_rate_bits: u32,
    taker_fee_rate_bits: u32,
    max_sub_per_bar: u32,
    trade_end_bar: u32,
}

struct GpuSnapshot {
    close: f32, high: f32, low: f32, open: f32,
    volume: f32, t_sec: u32,
    ema_fast: f32, ema_slow: f32, ema_macro: f32,
    adx: f32, adx_slope: f32, adx_pos: f32, adx_neg: f32,
    atr: f32, atr_slope: f32, avg_atr: f32,
    bb_upper: f32, bb_lower: f32, bb_width: f32, bb_width_ratio: f32,
    rsi: f32, stoch_k: f32, stoch_d: f32,
    macd_hist: f32, prev_macd_hist: f32, prev2_macd_hist: f32, prev3_macd_hist: f32,
    vol_sma: f32, vol_trend: u32,
    prev_close: f32, prev_ema_fast: f32, prev_ema_slow: f32,
    ema_slow_slope_pct: f32,
    bar_count: u32, valid: u32,
    funding_rate: f32,
    _pad: array<u32, 4>,
}

struct GpuPosition {
    active: u32,
    entry_price: f32, size: f32, confidence: u32,
    entry_atr: f32, entry_adx_threshold: f32,
    trailing_sl: f32, leverage: f32,
    margin_used: f32, adds_count: u32, tp1_taken: u32,
    open_time_sec: u32, last_add_time_sec: u32,
    _pad: array<u32, 3>,
}

struct GpuComboConfig {
    allocation_pct: f32, sl_atr_mult: f32, tp_atr_mult: f32, leverage: f32,
    enable_reef_filter: u32, reef_long_rsi_block_gt: f32, reef_short_rsi_block_lt: f32,
    reef_adx_threshold: f32, reef_long_rsi_extreme_gt: f32, reef_short_rsi_extreme_lt: f32,
    _reserved10: u32, leverage_low: f32, leverage_medium: f32,
    leverage_high: f32, _reserved14: f32, _p0: u32,
    slippage_bps: f32, min_notional_usd: f32, bump_to_min_notional: u32,
    max_total_margin_pct: f32, _p1: u32, _p2: u32,
    enable_dynamic_sizing: u32, confidence_mult_high: f32, confidence_mult_medium: f32,
    confidence_mult_low: f32, adx_sizing_min_mult: f32, adx_sizing_full_adx: f32,
    vol_baseline_pct: f32, vol_scalar_min: f32,
    vol_scalar_max: f32, _p3: u32,
    enable_pyramiding: u32, max_adds_per_symbol: u32, add_fraction_of_base_margin: f32,
    add_cooldown_minutes: u32, add_min_profit_atr: f32, add_min_confidence: u32,
    entry_min_confidence: u32, enable_slow_drift_entries: u32,
    enable_partial_tp: u32, tp_partial_pct: f32, tp_partial_min_notional_usd: f32,
    trailing_start_atr: f32, trailing_distance_atr: f32, tp_partial_atr_mult: f32,
    enable_ssf_filter: u32, enable_breakeven_stop: u32, breakeven_start_atr: f32,
    breakeven_buffer_atr: f32,
    trailing_start_atr_low_conf: f32, trailing_distance_atr_low_conf: f32,
    smart_exit_adx_exhaustion_lt: f32, smart_exit_adx_exhaustion_lt_low_conf: f32,
    enable_rsi_overextension_exit: u32, rsi_exit_profit_atr_switch: f32,
    rsi_exit_ub_lo_profit: f32, rsi_exit_ub_hi_profit: f32,
    rsi_exit_lb_lo_profit: f32, rsi_exit_lb_hi_profit: f32,
    rsi_exit_ub_lo_profit_low_conf: f32, rsi_exit_ub_hi_profit_low_conf: f32,
    rsi_exit_lb_lo_profit_low_conf: f32, rsi_exit_lb_hi_profit_low_conf: f32,
    reentry_cooldown_minutes: u32, reentry_cooldown_min_mins: u32,
    reentry_cooldown_max_mins: u32, _p6: u32,
    enable_vol_buffered_trailing: u32, tsme_min_profit_atr: f32,
    tsme_require_adx_slope_negative: u32, _p7: u32,
    min_atr_pct: f32, reverse_entry_signal: u32, block_exits_on_extreme_dev: u32,
    glitch_price_dev_pct: f32, glitch_atr_mult: f32, _p8: u32,
    max_open_positions: u32, max_entry_orders_per_loop: u32, _p9: u32, _p10: u32,
    enable_ranging_filter: u32, enable_anomaly_filter: u32, enable_extension_filter: u32,
    require_adx_rising: u32, adx_rising_saturation: f32, require_volume_confirmation: u32,
    vol_confirm_include_prev: u32, use_stoch_rsi_filter: u32,
    require_btc_alignment: u32, require_macro_alignment: u32,
    enable_regime_filter: u32, enable_auto_reverse: u32,
    auto_reverse_breadth_low: f32, auto_reverse_breadth_high: f32,
    breadth_block_short_above: f32, breadth_block_long_below: f32,
    min_adx: f32, high_conf_volume_mult: f32, btc_adx_override: f32,
    max_dist_ema_fast: f32, ave_atr_ratio_gt: f32, ave_adx_mult: f32,
    dre_min_adx: f32, dre_max_adx: f32,
    dre_long_rsi_limit_low: f32, dre_long_rsi_limit_high: f32,
    dre_short_rsi_limit_low: f32, dre_short_rsi_limit_high: f32,
    macd_mode: u32, pullback_min_adx: f32, pullback_rsi_long_min: f32,
    pullback_rsi_short_max: f32, pullback_require_macd_sign: u32, pullback_confidence: u32,
    slow_drift_min_slope_pct: f32, slow_drift_min_adx: f32,
    slow_drift_rsi_long_min: f32, slow_drift_rsi_short_max: f32,
    ranging_adx_lt: f32, ranging_bb_width_ratio_lt: f32,
    anomaly_bb_width_ratio_gt: f32, slow_drift_ranging_slope_override: f32,
    _p11: u32, _p12: u32,
    tp_strong_adx_gt: f32, tp_weak_adx_lt: f32,
    // === Decision codegen fields (AQC-1250) ===
    enable_pullback_entries: u32,
    anomaly_price_change_pct: f32, anomaly_ema_dev_pct: f32,
    ranging_rsi_low: f32, ranging_rsi_high: f32, ranging_min_signals: u32,
    stoch_rsi_block_long_gt: f32, stoch_rsi_block_short_lt: f32,
    ave_enabled: u32,
    tp_mult_strong: f32, tp_mult_weak: f32,
    entry_cooldown_s: u32,
}

struct GpuComboState {
    balance: f32, num_open: u32, entries_this_bar: u32, _sp: u32,
    positions: array<GpuPosition, 52>,
    pesc_close_time_sec: array<u32, 52>,
    pesc_close_type: array<u32, 52>,
    pesc_close_reason: array<u32, 52>,
    total_pnl: f32, total_fees: f32, total_trades: u32, total_wins: u32,
    gross_profit: f32, gross_loss: f32, max_drawdown: f32, peak_equity: f32,
}

struct GpuResult {
    final_balance: f32, total_pnl: f32, total_fees: f32,
    total_trades: u32, total_wins: u32, total_losses: u32,
    gross_profit: f32, gross_loss: f32, max_drawdown_pct: f32,
    _pad: array<u32, 3>,
}

struct EntryCandidate {
    sym_idx: u32,
    signal: u32,
    confidence: u32,
    score: i32,
    adx: f32,
    atr: f32,
    entry_adx_threshold: f32,
}

// ── Bindings ────────────────────────────────────────────────────────────────

@group(0) @binding(0) var<uniform> params: GpuParams;
@group(0) @binding(1) var<storage, read> snapshots: array<GpuSnapshot>;
@group(0) @binding(2) var<storage, read> breadth: array<f32>;
@group(0) @binding(3) var<storage, read> btc_bullish: array<u32>;
@group(0) @binding(4) var<storage, read> configs: array<GpuComboConfig>;
@group(0) @binding(5) var<storage, read_write> states: array<GpuComboState>;
@group(0) @binding(6) var<storage, read_write> results: array<GpuResult>;

// ── Helper functions ────────────────────────────────────────────────────────

fn get_taker_fee_rate() -> f32 {
    return bitcast<f32>(params.taker_fee_rate_bits);
}

fn profit_atr(pos: GpuPosition, price: f32) -> f32 {
    let atr = select(pos.entry_price * 0.005, pos.entry_atr, pos.entry_atr > 0.0);
    if atr <= 0.0 { return 0.0; }
    if pos.pos_type == POS_LONG {
        return (price - pos.entry_price) / atr;
    } else {
        return (pos.entry_price - price) / atr;
    }
}

fn profit_usd(pos: GpuPosition, price: f32) -> f32 {
    if pos.pos_type == POS_LONG {
        return (price - pos.entry_price) * pos.size;
    } else {
        return (pos.entry_price - price) * pos.size;
    }
}

fn apply_atr_floor(atr: f32, price: f32, min_atr_pct: f32) -> f32 {
    if min_atr_pct > 0.0 {
        let floor = price * min_atr_pct;
        if atr < floor { return floor; }
    }
    return atr;
}

fn conf_meets_min(conf: u32, min_conf: u32) -> bool {
    return conf >= min_conf;
}

// ── Signal Reversal & Regime Filter ─────────────────────────────────────────

fn apply_reverse(signal: u32, cfg: ptr<function, GpuComboConfig>, breadth_pct: f32) -> u32 {
    var should_reverse = (*cfg).reverse_entry_signal != 0u;

    if (*cfg).enable_auto_reverse != 0u {
        let low = (*cfg).auto_reverse_breadth_low;
        let high = (*cfg).auto_reverse_breadth_high;
        if breadth_pct >= low && breadth_pct <= high {
            should_reverse = true;
        } else {
            should_reverse = false;
        }
    }

    if should_reverse {
        if signal == SIG_BUY { return SIG_SELL; }
        if signal == SIG_SELL { return SIG_BUY; }
    }
    return signal;
}

fn apply_regime_filter(signal: u32, cfg: ptr<function, GpuComboConfig>, breadth_pct: f32) -> u32 {
    if (*cfg).enable_regime_filter == 0u { return signal; }
    if signal == SIG_SELL && breadth_pct > (*cfg).breadth_block_short_above { return SIG_NEUTRAL; }
    if signal == SIG_BUY && breadth_pct < (*cfg).breadth_block_long_below { return SIG_NEUTRAL; }
    return signal;
}

// ── Gate Checks ─────────────────────────────────────────────────────────────

fn check_gates(snap: GpuSnapshot, cfg: ptr<function, GpuComboConfig>,
               btc_bull: u32, ema_slope: f32) -> bool {
    // ADX minimum
    if snap.adx < (*cfg).min_adx { return false; }

    // Ranging filter (vote system simplified: ADX + BB width)
    if (*cfg).enable_ranging_filter != 0u {
        var votes = 0u;
        if snap.adx < (*cfg).ranging_adx_lt { votes += 1u; }
        if snap.bb_width_ratio < (*cfg).ranging_bb_width_ratio_lt { votes += 1u; }
        if snap.rsi > 47.0 && snap.rsi < 53.0 { votes += 1u; }
        if votes >= 2u {
            // Check slow-drift ranging override
            if abs(ema_slope) < (*cfg).slow_drift_ranging_slope_override {
                return false;
            }
        }
    }

    // Anomaly filter
    if (*cfg).enable_anomaly_filter != 0u {
        if snap.bb_width_ratio > (*cfg).anomaly_bb_width_ratio_gt { return false; }
    }

    // Extension filter
    if (*cfg).enable_extension_filter != 0u {
        if snap.close > 0.0 && snap.ema_fast > 0.0 {
            let dist = abs(snap.close - snap.ema_fast) / snap.ema_fast;
            if dist > (*cfg).max_dist_ema_fast { return false; }
        }
    }

    // Volume confirmation
    if (*cfg).require_volume_confirmation != 0u {
        if snap.vol_sma > 0.0 {
            var vol_ok = snap.volume > snap.vol_sma;
            if (*cfg).vol_confirm_include_prev != 0u {
                vol_ok = vol_ok || (snap.volume > snap.vol_sma * 0.8);
            }
            if !vol_ok { return false; }
        }
    }

    // ADX rising (trend direction)
    if (*cfg).require_adx_rising != 0u {
        if snap.adx < (*cfg).adx_rising_saturation {
            if snap.adx_slope <= 0.0 { return false; }
        }
    }

    // BTC alignment
    if (*cfg).require_btc_alignment != 0u {
        // Skip if symbol is BTC itself (handled at engine level)
    }

    // Macro EMA alignment
    if (*cfg).require_macro_alignment != 0u {
        if snap.close < snap.ema_macro { return false; }
    }

    return true;
}

// ── Signal Generation ───────────────────────────────────────────────────────

fn generate_signal(snap: GpuSnapshot, cfg: ptr<function, GpuComboConfig>,
                   gates_pass: bool, ema_slope: f32) -> vec3<u32> {
    // Returns (signal, confidence, entry_adx_threshold)
    // encoded in vec3<u32>

    // Mode 1: Standard trend
    if gates_pass {
        var signal = SIG_NEUTRAL;
        var confidence = CONF_MEDIUM;
        // Mirror bt-core: use the ADX threshold that gated the entry, not the current ADX value.
        let adx_threshold = (*cfg).min_adx;

        // EMA crossover direction
        let ema_bullish = snap.ema_fast > snap.ema_slow;
        let ema_bearish = snap.ema_fast < snap.ema_slow;

        if ema_bullish { signal = SIG_BUY; }
        if ema_bearish { signal = SIG_SELL; }
        if signal == SIG_NEUTRAL { return vec3<u32>(SIG_NEUTRAL, 0u, 0u); }

        // DRE (Dynamic RSI Elasticity)
        let adx_min = (*cfg).dre_min_adx;
        var adx_max = (*cfg).dre_max_adx;
        if adx_max <= adx_min { adx_max = adx_min + 1.0; }
        let weight = clamp((snap.adx - adx_min) / (adx_max - adx_min), 0.0, 1.0);
        let rsi_long_limit = (*cfg).dre_long_rsi_limit_low + weight * ((*cfg).dre_long_rsi_limit_high - (*cfg).dre_long_rsi_limit_low);
        let rsi_short_limit = (*cfg).dre_short_rsi_limit_low + weight * ((*cfg).dre_short_rsi_limit_high - (*cfg).dre_short_rsi_limit_low);

        // RSI gate
        if signal == SIG_BUY && snap.rsi > rsi_long_limit { return vec3<u32>(SIG_NEUTRAL, 0u, 0u); }
        if signal == SIG_SELL && snap.rsi < rsi_short_limit { return vec3<u32>(SIG_NEUTRAL, 0u, 0u); }

        // MACD gate
        if (*cfg).macd_mode == MACD_ACCEL {
            if signal == SIG_BUY && snap.macd_hist <= snap.prev_macd_hist { return vec3<u32>(SIG_NEUTRAL, 0u, 0u); }
            if signal == SIG_SELL && snap.macd_hist >= snap.prev_macd_hist { return vec3<u32>(SIG_NEUTRAL, 0u, 0u); }
        } else if (*cfg).macd_mode == MACD_SIGN {
            if signal == SIG_BUY && snap.macd_hist <= 0.0 { return vec3<u32>(SIG_NEUTRAL, 0u, 0u); }
            if signal == SIG_SELL && snap.macd_hist >= 0.0 { return vec3<u32>(SIG_NEUTRAL, 0u, 0u); }
        }

        // StochRSI filter
        if (*cfg).use_stoch_rsi_filter != 0u {
            if signal == SIG_BUY && snap.stoch_k > 0.85 { return vec3<u32>(SIG_NEUTRAL, 0u, 0u); }
            if signal == SIG_SELL && snap.stoch_k < 0.15 { return vec3<u32>(SIG_NEUTRAL, 0u, 0u); }
        }

        // Volume-based confidence upgrade
        if snap.vol_sma > 0.0 && snap.volume > snap.vol_sma * (*cfg).high_conf_volume_mult {
            confidence = CONF_HIGH;
        }

        return vec3<u32>(signal, confidence, bitcast<u32>(adx_threshold));
    }

    // Mode 2: Pullback (simplified — disabled in most sweeps)
    // Mode 3: Slow drift
    if abs(ema_slope) >= (*cfg).slow_drift_min_slope_pct && snap.adx >= (*cfg).slow_drift_min_adx {
        var signal = SIG_NEUTRAL;
        if ema_slope > 0.0 {
            if snap.rsi >= (*cfg).slow_drift_rsi_long_min { signal = SIG_BUY; }
        } else {
            if snap.rsi <= (*cfg).slow_drift_rsi_short_max { signal = SIG_SELL; }
        }
        if signal != SIG_NEUTRAL {
            return vec3<u32>(signal, CONF_LOW, bitcast<u32>((*cfg).slow_drift_min_adx));
        }
    }

    return vec3<u32>(SIG_NEUTRAL, 0u, 0u);
}

// ── Stop Loss ───────────────────────────────────────────────────────────────

fn compute_sl_price(pos: GpuPosition, snap: GpuSnapshot, cfg: ptr<function, GpuComboConfig>) -> f32 {
    let entry = pos.entry_price;
    let atr = select(entry * 0.005, pos.entry_atr, pos.entry_atr > 0.0);
    var sl_mult = (*cfg).sl_atr_mult;

    // ASE
    let is_underwater = select(snap.close > entry, snap.close < entry, pos.pos_type == POS_LONG);
    if snap.adx_slope < 0.0 && is_underwater { sl_mult *= 0.8; }

    // DASE
    if snap.adx > 40.0 {
        let p_atr = profit_atr(pos, snap.close);
        if p_atr > 0.5 { sl_mult *= 1.15; }
    }

    // SLB
    if snap.adx > 45.0 { sl_mult *= 1.10; }

    var sl_price: f32;
    if pos.pos_type == POS_LONG {
        sl_price = entry - (atr * sl_mult);
    } else {
        sl_price = entry + (atr * sl_mult);
    }

    // Breakeven
    if (*cfg).enable_breakeven_stop != 0u && (*cfg).breakeven_start_atr > 0.0 {
        let be_start = atr * (*cfg).breakeven_start_atr;
        let be_buffer = atr * (*cfg).breakeven_buffer_atr;
        if pos.pos_type == POS_LONG {
            if (snap.close - entry) >= be_start {
                sl_price = max(sl_price, entry + be_buffer);
            }
        } else {
            if (entry - snap.close) >= be_start {
                sl_price = min(sl_price, entry - be_buffer);
            }
        }
    }

    return sl_price;
}

fn stop_loss_hit(pos_type: u32, price: f32, sl_price: f32) -> bool {
    // Mirrors bt-core::exits::stop_loss::check_stop_loss:
    // LONG exits when price <= SL, SHORT exits when price >= SL.
    if pos_type == POS_LONG { return price <= sl_price; }
    return price >= sl_price;
}

fn check_stop_loss(pos: GpuPosition, snap: GpuSnapshot, cfg: ptr<function, GpuComboConfig>) -> bool {
    let sl = compute_sl_price(pos, snap, cfg);
    return stop_loss_hit(pos.pos_type, snap.close, sl);
}

// ── Trailing Stop ───────────────────────────────────────────────────────────

fn compute_trailing(pos: GpuPosition, snap: GpuSnapshot, cfg: ptr<function, GpuComboConfig>,
                    p_atr: f32) -> f32 {
    let entry = pos.entry_price;
    let atr = select(entry * 0.005, pos.entry_atr, pos.entry_atr > 0.0);

    var trailing_start = (*cfg).trailing_start_atr;
    var trailing_dist = (*cfg).trailing_distance_atr;
    if pos.confidence == CONF_LOW {
        if (*cfg).trailing_start_atr_low_conf > 0.0 { trailing_start = (*cfg).trailing_start_atr_low_conf; }
        if (*cfg).trailing_distance_atr_low_conf > 0.0 { trailing_dist = (*cfg).trailing_distance_atr_low_conf; }
    }

    // RSI Trend-Guard floor
    var min_dist = 0.5;
    if pos.pos_type == POS_LONG && snap.rsi > 60.0 { min_dist = 0.7; }
    if pos.pos_type == POS_SHORT && snap.rsi < 40.0 { min_dist = 0.7; }

    var eff_dist = trailing_dist;

    // VBTS
    if (*cfg).enable_vol_buffered_trailing != 0u && snap.bb_width_ratio > 1.2 {
        eff_dist *= 1.25;
    }

    // High-profit tightening
    if p_atr > 2.0 {
        if snap.adx > 35.0 && snap.adx_slope > 0.0 {
            eff_dist = trailing_dist * 1.0; // TATP: don't tighten
        } else if snap.atr_slope > 0.0 {
            eff_dist = trailing_dist * 0.75; // TSPV
        } else {
            eff_dist = trailing_dist * 0.5;
        }
    } else if snap.adx < 25.0 {
        eff_dist = trailing_dist * 0.7;
    }

    eff_dist = max(eff_dist, min_dist);

    if p_atr < trailing_start {
        return pos.trailing_sl; // Not active yet, preserve existing
    }

    var candidate: f32;
    if pos.pos_type == POS_LONG {
        candidate = snap.close - (atr * eff_dist);
    } else {
        candidate = snap.close + (atr * eff_dist);
    }

    // Ratchet
    if pos.trailing_sl > 0.0 {
        if pos.pos_type == POS_LONG {
            candidate = max(candidate, pos.trailing_sl);
        } else {
            candidate = min(candidate, pos.trailing_sl);
        }
    }

    return candidate;
}

fn check_trailing_exit(pos: GpuPosition, snap: GpuSnapshot) -> bool {
    if pos.trailing_sl <= 0.0 { return false; }
    if pos.pos_type == POS_LONG { return snap.close <= pos.trailing_sl; }
    return snap.close >= pos.trailing_sl;
}

// ── Take Profit ─────────────────────────────────────────────────────────────

// Returns: 0 = hold, 1 = partial, 2 = full close
fn check_tp(pos: GpuPosition, snap: GpuSnapshot, cfg: ptr<function, GpuComboConfig>,
            tp_mult: f32) -> u32 {
    let entry = pos.entry_price;
    let atr = select(entry * 0.005, pos.entry_atr, pos.entry_atr > 0.0);

    var tp_price: f32;
    if pos.pos_type == POS_LONG {
        tp_price = entry + (atr * tp_mult);
    } else {
        tp_price = entry - (atr * tp_mult);
    }

    var tp_hit = false;
    if pos.pos_type == POS_LONG { tp_hit = snap.close >= tp_price; }
    else { tp_hit = snap.close <= tp_price; }

    if !tp_hit { return 0u; }

    if (*cfg).enable_partial_tp != 0u {
        if pos.tp1_taken == 0u {
            let pct = clamp((*cfg).tp_partial_pct, 0.0, 1.0);
            if pct > 0.0 && pct < 1.0 {
                let remaining = pos.size * (1.0 - pct) * snap.close;
                if remaining < (*cfg).tp_partial_min_notional_usd { return 0u; }
                return 1u; // Partial
            }
        } else {
            return 0u; // tp1 already taken, let trailing manage
        }
    }

    return 2u; // Full close
}

// ── Smart Exits ─────────────────────────────────────────────────────────────

fn check_smart_exits(pos: GpuPosition, snap: GpuSnapshot, cfg: ptr<function, GpuComboConfig>,
                     p_atr: f32) -> bool {
    // Smart exit conditions mirror bt-core's `exits::smart_exits::check`.
    let entry = pos.entry_price;
    let entry_atr = select(entry * 0.005, pos.entry_atr, pos.entry_atr > 0.0);

    let is_long = pos.pos_type == POS_LONG;
    let is_low_conf = pos.confidence == CONF_LOW;

    // 1. Trend Breakdown (EMA Cross) with TBB buffer
    var ema_dev = 0.0;
    if snap.ema_slow > 0.0 {
        ema_dev = abs(snap.ema_fast - snap.ema_slow) / snap.ema_slow;
    }
    let is_weak_cross = (ema_dev < 0.001) && (snap.adx > 25.0);
    let ema_cross_exit = select(
        snap.ema_fast > snap.ema_slow && !is_weak_cross,  // SHORT
        snap.ema_fast < snap.ema_slow && !is_weak_cross,  // LONG
        is_long
    );

    // 2. Trend Exhaustion (ADX below threshold)
    var adx_exhaustion_lt = (*cfg).smart_exit_adx_exhaustion_lt;
    if pos.entry_adx_threshold > 0.0 {
        adx_exhaustion_lt = pos.entry_adx_threshold;
    } else if is_low_conf && (*cfg).smart_exit_adx_exhaustion_lt_low_conf > 0.0 {
        adx_exhaustion_lt = (*cfg).smart_exit_adx_exhaustion_lt_low_conf;
    }
    adx_exhaustion_lt = max(adx_exhaustion_lt, 0.0);
    let exhausted = (adx_exhaustion_lt > 0.0) && (snap.adx < adx_exhaustion_lt);

    if ema_cross_exit || exhausted { return true; }

    // 3. EMA Macro Breakdown (only if require_macro_alignment is enabled)
    if (*cfg).require_macro_alignment != 0u && snap.ema_macro > 0.0 {
        if is_long && snap.close < snap.ema_macro { return true; }
        if !is_long && snap.close > snap.ema_macro { return true; }
    }

    // 4. Stagnation Exit (low-vol + underwater)
    if snap.atr < (entry_atr * 0.70) {
        let is_underwater = select(snap.close > entry, snap.close < entry, is_long);
        if is_underwater { return true; }
    }

    // 6. TSME (Trend Saturation Momentum Exit)
    if snap.adx > 50.0 {
        let gate_profit_ok = p_atr >= (*cfg).tsme_min_profit_atr;
        var gate_slope_ok = true;
        if (*cfg).tsme_require_adx_slope_negative != 0u {
            gate_slope_ok = snap.adx_slope < 0.0;
        }
        if gate_profit_ok && gate_slope_ok {
            let is_exhausted = select(
                snap.macd_hist > snap.prev_macd_hist && snap.prev_macd_hist > snap.prev2_macd_hist,  // SHORT
                snap.macd_hist < snap.prev_macd_hist && snap.prev_macd_hist < snap.prev2_macd_hist,  // LONG
                is_long
            );
            if is_exhausted { return true; }
        }
    }

    // 7. MMDE (MACD Persistent Divergence Exit)
    if p_atr > 1.5 && snap.adx > 35.0 {
        let is_diverging = select(
            snap.macd_hist > snap.prev_macd_hist
                && snap.prev_macd_hist > snap.prev2_macd_hist
                && snap.prev2_macd_hist > snap.prev3_macd_hist, // SHORT
            snap.macd_hist < snap.prev_macd_hist
                && snap.prev_macd_hist < snap.prev2_macd_hist
                && snap.prev2_macd_hist < snap.prev3_macd_hist, // LONG
            is_long
        );
        if is_diverging { return true; }
    }

    // 8. RSI overextension
    if (*cfg).enable_rsi_overextension_exit != 0u {
        var ub: f32; var lb: f32;
        if pos.confidence == CONF_LOW && (*cfg).rsi_exit_ub_lo_profit_low_conf > 0.0 {
            if p_atr >= (*cfg).rsi_exit_profit_atr_switch {
                ub = (*cfg).rsi_exit_ub_hi_profit_low_conf;
                lb = (*cfg).rsi_exit_lb_hi_profit_low_conf;
            } else {
                ub = (*cfg).rsi_exit_ub_lo_profit_low_conf;
                lb = (*cfg).rsi_exit_lb_lo_profit_low_conf;
            }
        } else {
            if p_atr >= (*cfg).rsi_exit_profit_atr_switch {
                ub = (*cfg).rsi_exit_ub_hi_profit;
                lb = (*cfg).rsi_exit_lb_hi_profit;
            } else {
                ub = (*cfg).rsi_exit_ub_lo_profit;
                lb = (*cfg).rsi_exit_lb_lo_profit;
            }
        }
        if ub > 0.0 && lb > 0.0 {
            if is_long && snap.rsi > ub { return true; }
            if !is_long && snap.rsi < lb { return true; }
        }
    }

    return false;
}

// ── Entry Sizing ────────────────────────────────────────────────────────────

fn compute_entry_size(equity: f32, price: f32, confidence: u32, atr: f32,
                      snap: GpuSnapshot, cfg: ptr<function, GpuComboConfig>) -> vec3<f32> {
    // Returns (size, margin, leverage)
    var margin = equity * (*cfg).allocation_pct;

    if (*cfg).enable_dynamic_sizing != 0u {
        var conf_mult = (*cfg).confidence_mult_medium;
        if confidence == CONF_HIGH { conf_mult = (*cfg).confidence_mult_high; }
        if confidence == CONF_LOW { conf_mult = (*cfg).confidence_mult_low; }

        let adx_mult = clamp(snap.adx / (*cfg).adx_sizing_full_adx, (*cfg).adx_sizing_min_mult, 1.0);

        var vol_ratio = 1.0;
        if (*cfg).vol_baseline_pct > 0.0 && price > 0.0 {
            vol_ratio = (atr / price) / (*cfg).vol_baseline_pct;
        }
        var vol_scalar_raw = 1.0;
        if vol_ratio > 0.0 {
            vol_scalar_raw = 1.0 / vol_ratio;
        }
        let vol_scalar = clamp(vol_scalar_raw, (*cfg).vol_scalar_min, (*cfg).vol_scalar_max);

        margin *= conf_mult * adx_mult * vol_scalar;
    }

    // Leverage (always per-confidence-tier).
    var lev = 0.0;
    if confidence == CONF_HIGH { lev = (*cfg).leverage_high; }
    else if confidence == CONF_MEDIUM { lev = (*cfg).leverage_medium; }
    else { lev = (*cfg).leverage_low; }

    let notional = margin * lev;
    var size = 0.0;
    if price > 0.0 { size = notional / price; }

    return vec3<f32>(size, margin, lev);
}

// ── Exit Application ────────────────────────────────────────────────────────

fn apply_close(state: ptr<function, GpuComboState>, sym: u32, snap: GpuSnapshot,
               reason_is_signal_flip: bool) {
    let pos = (*state).positions[sym];
    if pos.pos_type == POS_EMPTY { return; }

    let fee_rate = get_taker_fee_rate();
    let slip = select(-0.5, 0.5, pos.pos_type == POS_LONG);
    let fill_price = snap.close * (1.0 + slip / 10000.0);
    let notional = pos.size * fill_price;
    let fee = notional * fee_rate;

    let pnl = profit_usd(pos, fill_price);
    (*state).balance += pnl - fee;
    (*state).total_pnl += pnl;
    (*state).total_fees += fee;
    (*state).total_trades += 1u;
    if pnl > 0.0 {
        (*state).total_wins += 1u;
        (*state).gross_profit += pnl;
    } else {
        (*state).gross_loss += abs(pnl);
    }
    (*state).num_open -= 1u;

    // PESC tracking
    (*state).pesc_close_time_sec[sym] = snap.t_sec;
    (*state).pesc_close_type[sym] = pos.pos_type;
    if reason_is_signal_flip {
        (*state).pesc_close_reason[sym] = PESC_SIGNAL_FLIP;
    } else {
        (*state).pesc_close_reason[sym] = PESC_OTHER;
    }

    // Clear position
    (*state).positions[sym] = GpuPosition(
        POS_EMPTY, 0.0, 0.0, 0u, 0.0, 0.0, 0.0, 0.0, 0.0, 0u, 0u, 0u, 0u,
        array<u32, 3>(0u, 0u, 0u)
    );
}

fn apply_partial_close(state: ptr<function, GpuComboState>, sym: u32, snap: GpuSnapshot, pct: f32) {
    let pos = (*state).positions[sym];
    if pos.pos_type == POS_EMPTY { return; }

    let fee_rate = get_taker_fee_rate();
    let exit_size = pos.size * pct;
    let slip = select(-0.5, 0.5, pos.pos_type == POS_LONG);
    let fill_price = snap.close * (1.0 + slip / 10000.0);
    let notional = exit_size * fill_price;
    let fee = notional * fee_rate;

    let pnl = select(
        (pos.entry_price - fill_price) * exit_size,
        (fill_price - pos.entry_price) * exit_size,
        pos.pos_type == POS_LONG
    );

    (*state).balance += pnl - fee;
    (*state).total_pnl += pnl;
    (*state).total_fees += fee;
    (*state).total_trades += 1u;
    if pnl > 0.0 {
        (*state).total_wins += 1u;
        (*state).gross_profit += pnl;
    } else {
        (*state).gross_loss += abs(pnl);
    }

    // Reduce position
    (*state).positions[sym].size -= exit_size;
    (*state).positions[sym].margin_used *= (1.0 - pct);
    (*state).positions[sym].tp1_taken = 1u;
    // Lock trailing SL to at least entry (breakeven)
    if (*state).positions[sym].trailing_sl <= 0.0 || (
        pos.pos_type == POS_LONG && (*state).positions[sym].trailing_sl < pos.entry_price
    ) || (
        pos.pos_type == POS_SHORT && (*state).positions[sym].trailing_sl > pos.entry_price
    ) {
        (*state).positions[sym].trailing_sl = pos.entry_price;
    }
}

// ── PESC Check ──────────────────────────────────────────────────────────────

fn is_pesc_blocked(state: ptr<function, GpuComboState>, sym: u32, desired_type: u32,
                   current_sec: u32, adx: f32, cfg: ptr<function, GpuComboConfig>) -> bool {
    if (*cfg).reentry_cooldown_minutes == 0u { return false; }
    let close_ts = (*state).pesc_close_time_sec[sym];
    if close_ts == 0u { return false; }
    if (*state).pesc_close_reason[sym] == PESC_SIGNAL_FLIP { return false; }
    if (*state).pesc_close_type[sym] != desired_type { return false; }

    let min_cd = f32((*cfg).reentry_cooldown_min_mins);
    let max_cd = f32((*cfg).reentry_cooldown_max_mins);
    var cooldown_mins: f32;
    if adx >= 40.0 { cooldown_mins = min_cd; }
    else if adx <= 25.0 { cooldown_mins = max_cd; }
    else {
        let t = (adx - 25.0) / 15.0;
        cooldown_mins = max_cd + t * (min_cd - max_cd);
    }

    let cooldown_sec = u32(cooldown_mins * 60.0);
    let elapsed = current_sec - close_ts;
    return elapsed < cooldown_sec;
}

// ── TP Multiplier (must mirror bt-core fixed tp_atr_mult semantics) ────────

fn get_tp_mult(snap: GpuSnapshot, cfg: ptr<function, GpuComboConfig>) -> f32 {
    // Parity with CPU: always use the configured TP ATR multiplier.
    // Dynamic TP scaling based on ADX is intentionally disabled on GPU.
    let _ = snap;
    return (*cfg).tp_atr_mult;
}

// ── Main Compute Shader ─────────────────────────────────────────────────────

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3u) {
    let combo_id = gid.x;
    if combo_id >= params.num_combos { return; }

    var state = states[combo_id];
    var cfg = configs[combo_id];
    let fee_rate = get_taker_fee_rate();
    let ns = params.num_symbols;

    for (var bar = params.chunk_start; bar < params.chunk_end; bar++) {
        state.entries_this_bar = 0u;
        let breadth_pct = breadth[bar];
        let btc_bull = btc_bullish[bar];

        // ── Phase 1: Exits (per symbol, immediate) ──────────────────────
        for (var sym = 0u; sym < ns; sym++) {
            let snap = snapshots[bar * ns + sym];
            if snap.valid == 0u { continue; }

            let pos = state.positions[sym];
            if pos.pos_type == POS_EMPTY { continue; }

            let p_atr = profit_atr(pos, snap.close);

            // Glitch guard (matches bt-core: only active when enabled)
            if cfg.block_exits_on_extreme_dev != 0u && snap.prev_close > 0.0 {
                let price_change_pct = abs(snap.close - snap.prev_close) / snap.prev_close;
                let is_glitch = price_change_pct > cfg.glitch_price_dev_pct
                    || (snap.atr > 0.0 && abs(snap.close - snap.prev_close) > snap.atr * cfg.glitch_atr_mult);
                if is_glitch {
                    continue; // Skip this bar for this symbol
                }
            }

            // Stop loss
            if check_stop_loss(pos, snap, &cfg) {
                apply_close(&state, sym, snap, false);
                continue;
            }

            // Update trailing stop
            let new_tsl = compute_trailing(pos, snap, &cfg, p_atr);
            if new_tsl > 0.0 {
                state.positions[sym].trailing_sl = new_tsl;
            }

            // Trailing stop exit
            if check_trailing_exit(state.positions[sym], snap) {
                apply_close(&state, sym, snap, false);
                continue;
            }

            // Take profit
            let tp_mult = get_tp_mult(snap, &cfg);
            let tp_result = check_tp(pos, snap, &cfg, tp_mult);
            if tp_result == 1u {
                apply_partial_close(&state, sym, snap, cfg.tp_partial_pct);
                continue;
            }
            if tp_result == 2u {
                apply_close(&state, sym, snap, false);
                continue;
            }

            // Smart exits
            if check_smart_exits(pos, snap, &cfg, p_atr) {
                apply_close(&state, sym, snap, false);
                continue;
            }
        }

        // ── Phase 2: Entry collection ───────────────────────────────────
        var candidates: array<EntryCandidate, 8>;
        var num_cands = 0u;

        for (var sym = 0u; sym < ns; sym++) {
            if num_cands >= MAX_CANDIDATES { break; }

            let snap = snapshots[bar * ns + sym];
            if snap.valid == 0u { continue; }

            let pos = state.positions[sym];

            // Pyramiding (same-direction add) — not ranked, immediate
            // Keep add eligibility aligned with CPU semantics:
            // - current signal must exist and match position direction
            // - current confidence must meet add_min_confidence
            if pos.pos_type != POS_EMPTY && cfg.enable_pyramiding != 0u {
                let gates_ok_add = check_gates(snap, &cfg, btc_bull, snap.ema_slow_slope_pct);
                let add_sig_result = generate_signal(snap, &cfg, gates_ok_add, snap.ema_slow_slope_pct);
                var add_signal = add_sig_result.x;
                let add_confidence = add_sig_result.y;

                if add_signal != SIG_NEUTRAL {
                    add_signal = apply_reverse(add_signal, &cfg, breadth_pct);
                }
                if add_signal != SIG_NEUTRAL {
                    add_signal = apply_regime_filter(add_signal, &cfg, breadth_pct);
                }

                let same_direction =
                    (pos.pos_type == POS_LONG && add_signal == SIG_BUY) ||
                    (pos.pos_type == POS_SHORT && add_signal == SIG_SELL);
                let add_conf_ok = conf_meets_min(add_confidence, cfg.add_min_confidence);

                if same_direction && add_conf_ok && pos.adds_count < cfg.max_adds_per_symbol {
                    var min_profit_atr = cfg.add_min_profit_atr;
                    if snap.adx_slope > 0.75 && snap.atr_slope <= 0.0 {
                        let is_rsi_extreme =
                            (pos.pos_type == POS_LONG && snap.rsi > 65.0) ||
                            (pos.pos_type == POS_SHORT && snap.rsi < 35.0);
                        if !is_rsi_extreme {
                            min_profit_atr *= 0.5;
                        }
                    }

                    var current_atr = apply_atr_floor(snap.atr, snap.close, cfg.min_atr_pct);
                    if !(current_atr > 0.0) {
                        current_atr = select(pos.entry_price * 0.005, pos.entry_atr, pos.entry_atr > 0.0);
                    }
                    if !(current_atr > 0.0) {
                        continue;
                    }

                    let p_atr = select(
                        (pos.entry_price - snap.close) / current_atr,
                        (snap.close - pos.entry_price) / current_atr,
                        pos.pos_type == POS_LONG
                    );
                    if p_atr >= min_profit_atr {
                        let elapsed_sec = snap.t_sec - pos.last_add_time_sec;
                        if elapsed_sec >= cfg.add_cooldown_minutes * 60u {
                            // Execute pyramid add (use equity = balance + unrealized PnL)
                            var pyr_equity = state.balance;
                            for (var eq_s2 = 0u; eq_s2 < ns; eq_s2++) {
                                let eq_p2 = state.positions[eq_s2];
                                if eq_p2.pos_type != POS_EMPTY {
                                    let eq_snap2 = snapshots[bar * ns + eq_s2];
                                    if eq_snap2.valid != 0u {
                                        pyr_equity += profit_usd(eq_p2, eq_snap2.close);
                                    }
                                }
                            }
                            if pyr_equity < 0.0 { pyr_equity = 0.0; }
                            let base_margin = pyr_equity * cfg.allocation_pct;
                            let add_margin = base_margin * cfg.add_fraction_of_base_margin;
                            let lev = pos.leverage;
                            var add_notional = add_margin * lev;
                            var add_size = add_notional / snap.close;

                            if add_notional < cfg.min_notional_usd {
                                if cfg.bump_to_min_notional != 0u && snap.close > 0.0 {
                                    add_notional = cfg.min_notional_usd;
                                    add_size = add_notional / snap.close;
                                } else {
                                    continue;
                                }
                            }

                            let fee = add_notional * fee_rate;
                            state.balance -= fee;
                            state.total_fees += fee;

                            // Update position
                            let old_size = pos.size;
                            let new_size = old_size + add_size;
                            let new_entry = (pos.entry_price * old_size + snap.close * add_size) / new_size;
                            state.positions[sym].entry_price = new_entry;
                            state.positions[sym].size = new_size;
                            state.positions[sym].margin_used += add_margin;
                            state.positions[sym].adds_count += 1u;
                            state.positions[sym].last_add_time_sec = snap.t_sec;
                        }
                    }
                }
                continue; // Skip entry evaluation for symbols with positions
            }

            if pos.pos_type != POS_EMPTY { continue; }

            // Check gates
            let gates_ok = check_gates(snap, &cfg, btc_bull, snap.ema_slow_slope_pct);

            // Generate signal
            let sig_result = generate_signal(snap, &cfg, gates_ok, snap.ema_slow_slope_pct);
            var signal = sig_result.x;
            let confidence = sig_result.y;
            let entry_adx_thresh = bitcast<f32>(sig_result.z);

            if signal == SIG_NEUTRAL { continue; }

            let atr = apply_atr_floor(snap.atr, snap.close, cfg.min_atr_pct);

            // Apply reverse + regime filter
            signal = apply_reverse(signal, &cfg, breadth_pct);
            if signal == SIG_NEUTRAL { continue; }
            signal = apply_regime_filter(signal, &cfg, breadth_pct);
            if signal == SIG_NEUTRAL { continue; }

            // Confidence gate
            if !conf_meets_min(confidence, cfg.entry_min_confidence) { continue; }

            // PESC
            let desired_type = select(POS_SHORT, POS_LONG, signal == SIG_BUY);
            if is_pesc_blocked(&state, sym, desired_type, snap.t_sec, snap.adx, &cfg) { continue; }

            // SSF
            if cfg.enable_ssf_filter != 0u {
                if signal == SIG_BUY && snap.macd_hist <= 0.0 { continue; }
                if signal == SIG_SELL && snap.macd_hist >= 0.0 { continue; }
            }

            // REEF
            if cfg.enable_reef_filter != 0u {
                if signal == SIG_BUY {
                    if snap.adx < cfg.reef_adx_threshold {
                        if snap.rsi > cfg.reef_long_rsi_block_gt { continue; }
                    } else {
                        if snap.rsi > cfg.reef_long_rsi_extreme_gt { continue; }
                    }
                }
                if signal == SIG_SELL {
                    if snap.adx < cfg.reef_adx_threshold {
                        if snap.rsi < cfg.reef_short_rsi_block_lt { continue; }
                    } else {
                        if snap.rsi < cfg.reef_short_rsi_extreme_lt { continue; }
                    }
                }
            }

            // Collect candidate
            let score = i32(confidence) * 100 + i32(snap.adx);

            candidates[num_cands] = EntryCandidate(
                sym, signal, confidence, score, snap.adx, atr, entry_adx_thresh
            );
            num_cands += 1u;
        }

        // ── Phase 3: Rank candidates (insertion sort by score desc) ─────
        for (var i = 1u; i < num_cands; i++) {
            let key = candidates[i];
            var j = i;
            while j > 0u
                && (candidates[j - 1u].score < key.score
                    || (candidates[j - 1u].score == key.score
                        && candidates[j - 1u].sym_idx > key.sym_idx)) {
                candidates[j] = candidates[j - 1u];
                j -= 1u;
            }
            candidates[j] = key;
        }

        // ── Phase 4: Execute ranked entries ─────────────────────────────
        // Compute equity = balance + unrealized PnL (mirrors CPU engine.rs:1094-1095)
        var entry_equity = state.balance;
        for (var eq_s = 0u; eq_s < ns; eq_s++) {
            let eq_p = state.positions[eq_s];
            if eq_p.pos_type != POS_EMPTY {
                let eq_snap = snapshots[bar * ns + eq_s];
                if eq_snap.valid != 0u {
                    entry_equity += profit_usd(eq_p, eq_snap.close);
                }
            }
        }
        if entry_equity < 0.0 { entry_equity = 0.0; }

        for (var i = 0u; i < num_cands; i++) {
            if state.entries_this_bar >= cfg.max_entry_orders_per_loop { break; }
            if state.num_open >= cfg.max_open_positions { break; }

            let cand = candidates[i];
            let snap = snapshots[bar * ns + cand.sym_idx];

            // Margin cap
            var total_margin = 0.0;
            for (var s = 0u; s < ns; s++) {
                if state.positions[s].pos_type != POS_EMPTY {
                    total_margin += state.positions[s].margin_used;
                }
            }
            let headroom = entry_equity * cfg.max_total_margin_pct - total_margin;
            if headroom <= 0.0 { continue; }

            // Sizing
            let sizing = compute_entry_size(entry_equity, snap.close, cand.confidence,
                                            cand.atr, snap, &cfg);
            var size = sizing.x;
            var margin = sizing.y;
            let lev = sizing.z;

            if margin > headroom {
                let ratio = headroom / margin;
                size *= ratio;
                margin = headroom;
            }

            var notional = size * snap.close;
            if notional < cfg.min_notional_usd {
                if cfg.bump_to_min_notional != 0u && snap.close > 0.0 {
                    size = cfg.min_notional_usd / snap.close;
                    margin = size * snap.close / lev;
                    notional = size * snap.close;
                } else {
                    continue;
                }
            }

            // Fill with slippage
            let slip = select(-cfg.slippage_bps, cfg.slippage_bps, cand.signal == SIG_BUY);
            let fill_price = snap.close * (1.0 + slip / 10000.0);
            let fee = notional * fee_rate;
            state.balance -= fee;
            state.total_fees += fee;

            // Open position
            state.positions[cand.sym_idx] = GpuPosition(
                select(POS_SHORT, POS_LONG, cand.signal == SIG_BUY),
                fill_price, size, cand.confidence,
                cand.atr, cand.entry_adx_threshold,
                0.0, lev, margin, 0u, 0u, snap.t_sec, snap.t_sec,
                array<u32, 3>(0u, 0u, 0u)
            );
            state.num_open += 1u;
            state.entries_this_bar += 1u;
        }

        // ── Equity tracking ─────────────────────────────────────────────
        var equity = state.balance;
        for (var s = 0u; s < ns; s++) {
            let p = state.positions[s];
            if p.pos_type != POS_EMPTY {
                let snap = snapshots[bar * ns + s];
                if snap.valid != 0u {
                    equity += profit_usd(p, snap.close);
                }
            }
        }
        if equity > state.peak_equity { state.peak_equity = equity; }
        if state.peak_equity > 0.0 {
            let dd = (state.peak_equity - equity) / state.peak_equity;
            if dd > state.max_drawdown { state.max_drawdown = dd; }
        }
    }

    // Write back state
    states[combo_id] = state;

    // Pack result (on last chunk)
    if params.chunk_end >= params.num_bars {
        let total_losses = select(0u, state.total_trades - state.total_wins, state.total_trades >= state.total_wins);
        results[combo_id] = GpuResult(
            state.balance,
            state.total_pnl,
            state.total_fees,
            state.total_trades,
            state.total_wins,
            total_losses,
            state.gross_profit,
            state.gross_loss,
            state.max_drawdown,
            array<u32, 3>(0u, 0u, 0u)
        );
    }
}
