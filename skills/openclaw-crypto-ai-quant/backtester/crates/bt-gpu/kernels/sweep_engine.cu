// =============================================================================
// GPU Sweep Engine -- CUDA Compute Kernel
// =============================================================================
//
// Originally ported from sweep_engine.wgsl; now the sole production kernel.
// The WGSL shader is deprecated (AQC-1241) and no longer maintained.
// Mirrors the Rust backtester trade logic for parameter sweep.
// Indicators are precomputed on CPU; this kernel only runs trade decisions.
//
// Buffer layout (kernel parameters):
//   params     -- const GpuParams*          (uniform equivalent)
//   snapshots  -- const GpuSnapshot*        [num_bars * num_symbols]
//   breadth    -- const float*              [num_bars]
//   btc_bull   -- const unsigned int*       [num_bars]
//   configs    -- const GpuComboConfig*     [num_combos]
//   states     -- GpuComboState*            [num_combos]  (read-write)
//   results    -- GpuResult*                [num_combos]  (read-write)

#include <cstdint>
#include <cmath>

// Bounds-checked array access macro (H10: prevent out-of-bounds GPU reads)
#define SAFE_IDX(arr, idx, max_idx, fallback) \
    ((idx) < (max_idx) ? (arr)[(idx)] : (fallback))
#define SUB_COUNT_INDEX(bar, sym, ns) \
    (((unsigned long long)(bar) * (unsigned long long)(ns)) + (unsigned long long)(sym))
#define SUB_CANDLE_INDEX(bar, sub_i, max_sub, ns, sym) \
    ((((unsigned long long)(bar) * (unsigned long long)(max_sub) + (unsigned long long)(sub_i)) \
      * (unsigned long long)(ns)) + (unsigned long long)(sym))

#define MAX_SYMBOLS      52u
// Candidate buffer must cover the full project symbol universe to keep
// ranking parity with CPU (no early truncation while scanning symbols).
#define MAX_CANDIDATES   64u

// Position type constants
#define POS_EMPTY   0u
#define POS_LONG    1u
#define POS_SHORT   2u

// Signal constants
#define SIG_NEUTRAL 0u
#define SIG_BUY     1u
#define SIG_SELL    2u

// Confidence constants
#define CONF_LOW    0u
#define CONF_MEDIUM 1u
#define CONF_HIGH   2u

// MACD mode
#define MACD_ACCEL  0u
#define MACD_SIGN   1u
#define MACD_NONE   2u

// BTC alignment state (from breadth kernel)
#define BTC_BULL_BEARISH 0u
#define BTC_BULL_BULLISH 1u
#define BTC_BULL_UNKNOWN 2u

// Decision-kernel cash model notional clamp (CPU SSOT defaults).
#define KERNEL_MIN_NOTIONAL_USD 10.0
#define KERNEL_MAX_NOTIONAL_USD 100000.0

// PESC close reasons
#define PESC_NONE        0u
#define PESC_SIGNAL_FLIP 1u
#define PESC_OTHER       2u

// Trace capture
#define TRACE_SYMBOL_ALL        0xFFFFFFFFu
#define TRACE_CAPACITY          1024u
#define TRACE_KIND_OPEN         1u
#define TRACE_KIND_ADD          2u
#define TRACE_KIND_CLOSE        3u
#define TRACE_KIND_PARTIAL      4u
#define TRACE_KIND_FUNDING      5u
#define TRACE_REASON_ENTRY      1u
#define TRACE_REASON_PYRAMID    2u
#define TRACE_REASON_EXIT_STOP  3u
#define TRACE_REASON_EXIT_TRAILING 4u
#define TRACE_REASON_EXIT_TP    5u
#define TRACE_REASON_EXIT_SMART 6u
#define TRACE_REASON_SIGNAL_FLIP 7u
#define TRACE_REASON_PARTIAL    8u
#define TRACE_REASON_EXIT_EOB   9u
#define TRACE_REASON_FUNDING    10u

// -- Structs (match Rust #[repr(C)] exactly) ----------------------------------

struct GpuRawCandle {
    double open;
    double high;
    double low;
    double close;
    double volume;
    unsigned int t_sec;
    unsigned int _pad[3];
};

struct GpuParams {
    unsigned int num_combos;
    unsigned int num_symbols;
    unsigned int num_bars;
    unsigned int btc_sym_idx;
    unsigned int paxg_sym_idx;
    unsigned int chunk_start;
    unsigned int chunk_end;
    unsigned int initial_balance_bits;
    unsigned int maker_fee_rate_bits;
    unsigned int taker_fee_rate_bits;
    unsigned int max_sub_per_bar;
    unsigned int trade_end_bar;
    unsigned int debug_t_sec;
    unsigned int funding_enabled;
    unsigned int entry_interval_sec;
    unsigned int signal_on_candle_close;
};

struct __align__(16) GpuSnapshot {
    float close;  float high;  float low;  float open;             // 16
    float volume;  unsigned int t_sec;                              // 24
    float ema_fast;  float ema_slow;  float ema_macro;             // 36
    float adx;  float adx_slope;  float adx_pos;  float adx_neg;  // 52
    float atr;  float atr_slope;  float avg_atr;                   // 64
    float bb_upper;  float bb_lower;  float bb_width;  float bb_width_ratio; // 80
    float rsi;  float stoch_k;  float stoch_d;                    // 92
    float macd_hist;  float prev_macd_hist;  float prev2_macd_hist;  float prev3_macd_hist; // 108
    float vol_sma;  unsigned int vol_trend;                        // 116
    float prev_close;  float prev_ema_fast;  float prev_ema_slow;  // 128
    float ema_slow_slope_pct;                                      // 132
    unsigned int bar_count;  unsigned int valid;                   // 140
    float funding_rate;                                            // 144
    unsigned int _pad[4];                                          // 160
};

struct __align__(16) GpuPosition {
    unsigned int active;                                           // replaces pos_type
    unsigned int _pad0;
    double entry_price;  double size;                              // 24
    unsigned int confidence;  unsigned int _pad1;                  // 32
    double entry_atr;  double entry_adx_threshold;                 // 48
    double trailing_sl;  double leverage;                          // 64
    double margin_used;  unsigned int adds_count;  unsigned int tp1_taken; // 80
    unsigned int open_time_sec;  unsigned int last_add_time_sec;   // 88
    double kernel_margin_used;                                     // 96
};
static_assert(sizeof(GpuPosition) == 96, "GpuPosition layout mismatch");

struct GpuTraceEvent {
    unsigned int t_sec;
    unsigned int sym;
    unsigned int kind;
    unsigned int side;
    unsigned int reason;
    float price;
    float size;
    double pnl;
};

struct GpuComboConfig {
    float allocation_pct;  float sl_atr_mult;  float tp_atr_mult;  float leverage;
    unsigned int enable_reef_filter;  float reef_long_rsi_block_gt;  float reef_short_rsi_block_lt;
    float reef_adx_threshold;  float reef_long_rsi_extreme_gt;  float reef_short_rsi_extreme_lt;
    unsigned int _reserved10;  float leverage_low;  float leverage_medium;
    float leverage_high;  float _reserved14;  float trailing_rsi_floor_default;
    float slippage_bps;  float min_notional_usd;  unsigned int bump_to_min_notional;
    float max_total_margin_pct;  float trailing_rsi_floor_trending;  float trailing_vbts_bb_threshold;
    unsigned int enable_dynamic_sizing;  float confidence_mult_high;  float confidence_mult_medium;
    float confidence_mult_low;  float adx_sizing_min_mult;  float adx_sizing_full_adx;
    float vol_baseline_pct;  float vol_scalar_min;
    float vol_scalar_max;  float trailing_vbts_mult;
    unsigned int enable_pyramiding;  unsigned int max_adds_per_symbol;  float add_fraction_of_base_margin;
    unsigned int add_cooldown_minutes;  float add_min_profit_atr;  unsigned int add_min_confidence;
    unsigned int entry_min_confidence;  float trailing_high_profit_atr;
    unsigned int enable_partial_tp;  float tp_partial_pct;  float tp_partial_min_notional_usd;
    float trailing_start_atr;  float trailing_distance_atr;  float tp_partial_atr_mult;
    unsigned int enable_ssf_filter;  unsigned int enable_breakeven_stop;  float breakeven_start_atr;
    float breakeven_buffer_atr;
    float trailing_start_atr_low_conf;  float trailing_distance_atr_low_conf;
    float smart_exit_adx_exhaustion_lt;  float smart_exit_adx_exhaustion_lt_low_conf;
    unsigned int enable_rsi_overextension_exit;  float rsi_exit_profit_atr_switch;
    float rsi_exit_ub_lo_profit;  float rsi_exit_ub_hi_profit;
    float rsi_exit_lb_lo_profit;  float rsi_exit_lb_hi_profit;
    float rsi_exit_ub_lo_profit_low_conf;  float rsi_exit_ub_hi_profit_low_conf;
    float rsi_exit_lb_lo_profit_low_conf;  float rsi_exit_lb_hi_profit_low_conf;
    unsigned int reentry_cooldown_minutes;  unsigned int reentry_cooldown_min_mins;
    unsigned int reentry_cooldown_max_mins;  float trailing_tighten_default;
    unsigned int enable_vol_buffered_trailing;  float tsme_min_profit_atr;
    unsigned int tsme_require_adx_slope_negative;  float trailing_tighten_tspv;
    float min_atr_pct;  unsigned int reverse_entry_signal;  unsigned int block_exits_on_extreme_dev;
    float glitch_price_dev_pct;  float glitch_atr_mult;  float trailing_weak_trend_mult;
    unsigned int max_open_positions;  unsigned int max_entry_orders_per_loop;
    unsigned int enable_slow_drift_entries;  unsigned int slow_drift_require_macd_sign;
    unsigned int enable_ranging_filter;  unsigned int enable_anomaly_filter;  unsigned int enable_extension_filter;
    unsigned int require_adx_rising;  float adx_rising_saturation;  unsigned int require_volume_confirmation;
    unsigned int vol_confirm_include_prev;  unsigned int use_stoch_rsi_filter;
    unsigned int require_btc_alignment;  unsigned int require_macro_alignment;
    unsigned int enable_regime_filter;  unsigned int enable_auto_reverse;
    float auto_reverse_breadth_low;  float auto_reverse_breadth_high;
    float breadth_block_short_above;  float breadth_block_long_below;
    float min_adx;  float high_conf_volume_mult;  float btc_adx_override;
    float max_dist_ema_fast;  float ave_atr_ratio_gt;  float ave_adx_mult;
    float dre_min_adx;  float dre_max_adx;
    float dre_long_rsi_limit_low;  float dre_long_rsi_limit_high;
    float dre_short_rsi_limit_low;  float dre_short_rsi_limit_high;
    unsigned int macd_mode;  float pullback_min_adx;  float pullback_rsi_long_min;
    float pullback_rsi_short_max;  unsigned int pullback_require_macd_sign;  unsigned int pullback_confidence;
    float slow_drift_min_slope_pct;  float slow_drift_min_adx;
    float slow_drift_rsi_long_min;  float slow_drift_rsi_short_max;
    float ranging_adx_lt;  float ranging_bb_width_ratio_lt;
    float anomaly_bb_width_ratio_gt;  float slow_drift_ranging_slope_override;
    unsigned int snapshot_offset;  unsigned int breadth_offset;
    float tp_strong_adx_gt;  float tp_weak_adx_lt;
    // === Decision codegen fields (AQC-1250) ===
    unsigned int enable_pullback_entries;
    float anomaly_price_change_pct;  float anomaly_ema_dev_pct;
    float ranging_rsi_low;  float ranging_rsi_high;  unsigned int ranging_min_signals;
    float stoch_rsi_block_long_gt;  float stoch_rsi_block_short_lt;
    unsigned int ave_enabled;
    float tp_mult_strong;  float tp_mult_weak;
    unsigned int entry_cooldown_s;  unsigned int exit_cooldown_s;
};
static_assert(sizeof(GpuComboConfig) == 564, "GpuComboConfig layout mismatch");

struct GpuComboState {
    double balance;  unsigned int num_open;  unsigned int entries_this_bar;
    GpuPosition positions[52];
    unsigned int pesc_close_time_sec[52];
    unsigned int pesc_close_type[52];
    unsigned int pesc_close_reason[52];
    unsigned int last_entry_attempt_sec[52];
    unsigned int last_exit_attempt_sec[52];
    unsigned int trace_enabled;
    unsigned int trace_symbol;
    unsigned int trace_count;
    unsigned int trace_head;
    GpuTraceEvent trace_events[1024];
    double total_pnl;  double total_fees;  unsigned int total_trades;  unsigned int total_wins;
    double gross_profit;  double gross_loss;  double max_drawdown;  double peak_equity;
    double kernel_cash;
};
static_assert(sizeof(GpuComboState) == 47088, "GpuComboState layout mismatch");

struct __align__(16) GpuResult {
    double final_balance;  double total_pnl;  double total_fees;
    unsigned int total_trades;  unsigned int total_wins;  unsigned int total_losses;
    unsigned int _pad0;
    double gross_profit;  double gross_loss;  double max_drawdown_pct;
};
static_assert(sizeof(GpuResult) == 64, "GpuResult layout mismatch");

struct GpuFundingSpan {
    unsigned int offset;
    unsigned int len;
};
static_assert(sizeof(GpuFundingSpan) == 8, "GpuFundingSpan layout mismatch");

struct EntryCandidate {
    unsigned int sym_idx;
    unsigned int signal;
    unsigned int confidence;
    int score;
    double adx;
    double atr;
    double entry_adx_threshold;
};

// -- Codegen'd decision functions (AQC-1213) ----------------------------------
// Structs defined here: GateResultD, SignalResult, TpResult, SmartExitResult,
// SizingResultD.  Device functions: check_gates_codegen, generate_signal_codegen,
// compute_sl_price_codegen, compute_trailing_codegen, check_tp_codegen,
// check_smart_exits_codegen, compute_entry_size_codegen, is_pesc_blocked_codegen.
#include "generated_decision.cu"

// -- Helper functions ---------------------------------------------------------

__device__ float get_taker_fee_rate(const GpuParams* params) {
    return __uint_as_float(params->taker_fee_rate_bits);
}

__device__ __forceinline__ double quantize12(double value) {
    const double q = 1000000000000.0;
    // CPU parity: Rust f64::round rounds half away from zero.
    // C/CUDA nearbyint() uses the current rounding mode (typically bankers),
    // which can diverge at half-quantum boundaries.
    double scaled = value * q;
    double rounded = (scaled >= 0.0) ? floor(scaled + 0.5) : ceil(scaled - 0.5);
    return rounded / q;
}

__device__ __forceinline__ double resolve_main_close(
    const GpuRawCandle* main_candles,
    unsigned int bar,
    unsigned int ns,
    unsigned int sym,
    const GpuSnapshot& snap
) {
    const GpuRawCandle& mc = main_candles[bar * ns + sym];
    double c = mc.close;
    if (isfinite(c) && c > 0.0) { return c; }
    return (double)snap.close;
}

__device__ __forceinline__ double resolve_mark_price_for_funding(
    const GpuRawCandle* main_candles,
    const GpuSnapshot* snapshots,
    const GpuComboConfig* cfg,
    unsigned int bar,
    unsigned int ns,
    unsigned int sym,
    double fallback_price
) {
    (void)fallback_price;
    // CPU parity: funding mark price resolves to the latest known close.
    // With missing-bar carry-forward snapshots, we can resolve this in O(1).
    const GpuSnapshot& s = snapshots[cfg->snapshot_offset + bar * ns + sym];
    return resolve_main_close(main_candles, bar, ns, sym, s);
}

__device__ double profit_atr(const GpuPosition& pos, double price) {
    double atr = (pos.entry_atr > 0.0f) ? (double)pos.entry_atr : ((double)pos.entry_price * 0.005);
    if (atr <= 0.0) { return 0.0; }
    double result;
    if (pos.active == POS_LONG) {
        result = (price - (double)pos.entry_price) / atr;
    } else {
        result = ((double)pos.entry_price - price) / atr;
    }
    return isfinite(result) ? result : 0.0;
}

__device__ double profit_usd(const GpuPosition& pos, double price) {
    if (pos.active == POS_LONG) {
        return (price - (double)pos.entry_price) * (double)pos.size;
    } else {
        return ((double)pos.entry_price - price) * (double)pos.size;
    }
}

__device__ __forceinline__ double funding_delta(double size, bool is_long, double mark_price, double rate) {
    double signed_size = is_long ? size : -size;
    return quantize12(-signed_size * mark_price * rate);
}

__device__ double apply_atr_floor(double atr, double price, double min_atr_pct) {
    if (min_atr_pct > 0.0) {
        double floor_val = price * min_atr_pct;
        if (atr < floor_val) { return floor_val; }
    }
    return atr;
}

__device__ bool conf_meets_min(unsigned int conf, unsigned int min_conf) {
    return conf >= min_conf;
}

__device__ __forceinline__ double clamp_kernel_notional(double notional) {
    if (notional < KERNEL_MIN_NOTIONAL_USD) { return KERNEL_MIN_NOTIONAL_USD; }
    if (notional > KERNEL_MAX_NOTIONAL_USD) { return KERNEL_MAX_NOTIONAL_USD; }
    return notional;
}

// -- Signal Reversal & Regime Filter ------------------------------------------

__device__ unsigned int apply_reverse(unsigned int signal, const GpuComboConfig* cfg, float breadth_pct) {
    bool should_reverse = (cfg->reverse_entry_signal != 0u);

    if (cfg->enable_auto_reverse != 0u) {
        float low = cfg->auto_reverse_breadth_low;
        float high = cfg->auto_reverse_breadth_high;
        if (breadth_pct >= low && breadth_pct <= high) {
            should_reverse = true;
        } else {
            should_reverse = false;
        }
    }

    if (should_reverse) {
        if (signal == SIG_BUY) { return SIG_SELL; }
        if (signal == SIG_SELL) { return SIG_BUY; }
    }
    return signal;
}

__device__ unsigned int apply_regime_filter(unsigned int signal, const GpuComboConfig* cfg, float breadth_pct) {
    if (cfg->enable_regime_filter == 0u) { return signal; }
    if (signal == SIG_SELL && breadth_pct > cfg->breadth_block_short_above) { return SIG_NEUTRAL; }
    if (signal == SIG_BUY && breadth_pct < cfg->breadth_block_long_below) { return SIG_NEUTRAL; }
    return signal;
}

// -- Gate Checks (AQC-1213: delegated to check_gates_codegen) -----------------
//
// The GateResult struct is a lightweight facade used by the sweep kernel.
// The actual gate evaluation is performed by check_gates_codegen() from
// generated_decision.cu which operates in double precision (AQC-734).
// Thin wrapper over codegen: float->double on inputs, GateResultD->GateResult on output.

struct GateResult {
    bool all_gates_pass;
    bool is_ranging;
    bool is_anomaly;
    bool is_extended;
    bool vol_confirm;
    bool bullish_alignment;
    bool bearish_alignment;
    double effective_min_adx;
};

__device__ GateResult check_gates(const GpuSnapshot& snap, const GpuComboConfig* cfg,
                                   float ema_slope, unsigned int btc_bull,
                                   bool is_btc_symbol) {
    // AQC-1213: replaced by codegen — delegates to check_gates_codegen()
    GateResultD gd = check_gates_codegen(
        *cfg,
        (double)snap.rsi,
        (double)snap.adx,
        (double)snap.adx_slope,
        (double)snap.bb_width_ratio,
        (double)snap.ema_fast,
        (double)snap.ema_slow,
        (double)snap.ema_macro,
        (double)snap.close,
        (double)snap.prev_close,
        (double)snap.volume,
        (double)snap.vol_sma,
        snap.vol_trend,
        (double)snap.atr,
        (double)snap.avg_atr,
        (double)snap.stoch_k,
        (double)ema_slope,
        btc_bull,
        is_btc_symbol ? 1u : 0u
    );

    // Convert GateResultD -> GateResult (facade for downstream kernel code)
    GateResult result;
    result.all_gates_pass   = gd.all_gates_pass;
    result.is_ranging       = gd.is_ranging;
    result.is_anomaly       = gd.is_anomaly;
    result.is_extended      = gd.is_extended;
    result.vol_confirm      = gd.vol_confirm;
    result.bullish_alignment = gd.bullish_alignment;
    result.bearish_alignment = gd.bearish_alignment;
    result.effective_min_adx = gd.effective_min_adx;
    return result;
}

// -- Signal Generation (AQC-1213: delegated to generate_signal_codegen) -------
//
// Thin wrapper over codegen: float->double on inputs, int->unsigned int + double->float on output.
// The codegen SignalResult (from generated_decision.cu) uses:
//   int signal, int confidence, double effective_min_adx
// The sweep kernel expects unsigned int signal/confidence and float entry_adx_threshold.
// This wrapper struct + function bridges the two.

struct SignalResultLegacy {
    unsigned int signal;
    unsigned int confidence;
    double entry_adx_threshold;
};

__device__ SignalResultLegacy generate_signal(const GpuSnapshot& snap, const GpuComboConfig* cfg,
                                              const GateResult& gates, unsigned int btc_bull,
                                              bool is_btc_symbol, float ema_slope) {
    // AQC-1213: replaced by codegen — delegates to generate_signal_codegen()
    SignalResult sr = generate_signal_codegen(
        *cfg,
        (double)snap.close,
        (double)snap.ema_fast,
        (double)snap.ema_slow,
        (double)snap.adx,
        (double)gates.effective_min_adx,
        (double)snap.rsi,
        (double)snap.macd_hist,
        (double)snap.prev_macd_hist,
        (double)snap.volume,
        (double)snap.vol_sma,
        (double)snap.atr,
        (double)snap.avg_atr,
        (double)snap.stoch_k,
        (double)snap.prev_close,
        (double)snap.prev_ema_fast,
        (double)ema_slope,
        gates.all_gates_pass,
        gates.bullish_alignment,
        gates.bearish_alignment,
        gates.is_anomaly,
        gates.is_extended,
        gates.is_ranging,
        gates.vol_confirm,
        btc_bull,
        is_btc_symbol
    );

    // Convert SignalResult (codegen) -> SignalResultLegacy (kernel facade)
    SignalResultLegacy result;
    result.signal = (unsigned int)sr.signal;
    result.confidence = (unsigned int)sr.confidence;
    result.entry_adx_threshold = sr.effective_min_adx;
    return result;
}

// -- Stop Loss ----------------------------------------------------------------
// AQC-1226: Thin wrapper over codegen — float->double on inputs, double->float on output.

__device__ double compute_sl_price(const GpuPosition& pos, const GpuSnapshot& snap, const GpuComboConfig* cfg) {
    // AQC-1226: delegate to double-precision codegen
    double sl = compute_sl_price_codegen(
        *cfg,
        (int)pos.active,
        (double)pos.entry_price,
        (double)pos.entry_atr,
        (double)snap.close,
        (double)snap.adx,
        (double)snap.adx_slope
    );
    return sl;
}

__device__ bool stop_loss_hit(unsigned int pos_type, double price, double sl_price,
                              double entry_atr, unsigned int adds_count) {
    // Mirrors bt-core::exits::stop_loss::check_stop_loss:
    // LONG exits when price <= SL, SHORT exits when price >= SL.
    (void)entry_atr;
    (void)adds_count;
    if (pos_type == POS_LONG) { return price <= sl_price; }
    return price >= sl_price;
}

__device__ bool check_stop_loss(const GpuPosition& pos, const GpuSnapshot& snap, const GpuComboConfig* cfg) {
    double sl = compute_sl_price(pos, snap, cfg);
    return stop_loss_hit(pos.active, (double)snap.close, sl, (double)pos.entry_atr, pos.adds_count);
}

// -- Trailing Stop ------------------------------------------------------------
// AQC-1226: Thin wrapper over codegen — float->double on inputs, double->float on output.

__device__ double compute_trailing(const GpuPosition& pos, const GpuSnapshot& snap,
                                   const GpuComboConfig* cfg, double p_atr) {
    // AQC-1226: delegate to double-precision codegen
    double tsl = compute_trailing_codegen(
        *cfg,
        (int)pos.active,
        (double)pos.entry_price,
        (double)snap.close,
        (double)pos.entry_atr,
        (double)pos.trailing_sl,
        (int)pos.confidence,
        (double)snap.rsi,
        (double)snap.adx,
        (double)snap.adx_slope,
        (double)snap.atr_slope,
        (double)snap.bb_width_ratio,
        (double)p_atr
    );
    return tsl;
}

__device__ bool check_trailing_exit(const GpuPosition& pos, const GpuSnapshot& snap) {
    if (pos.trailing_sl <= 0.0f) { return false; }
    if (pos.active == POS_LONG) { return snap.close <= pos.trailing_sl; }
    return snap.close >= pos.trailing_sl;
}

// -- Take Profit --------------------------------------------------------------
// AQC-1226: Thin wrapper over codegen — float->double on inputs, TpResult.action->unsigned int.
// Returns: 0 = hold, 1 = partial, 2 = full close
__device__ unsigned int check_tp(const GpuPosition& pos, const GpuSnapshot& snap,
                                 const GpuComboConfig* cfg, float tp_mult) {
    // AQC-1226: delegate to double-precision codegen
    TpResult tp = check_tp_codegen(
        *cfg,
        (int)pos.active,
        (double)pos.entry_price,
        (double)pos.entry_atr,
        (double)snap.close,
        (double)pos.size,
        pos.tp1_taken,
        (double)tp_mult
    );
    return (unsigned int)tp.action;
}

// -- Smart Exits --------------------------------------------------------------
// AQC-1226: Thin wrapper over codegen — float->double on inputs, SmartExitResult.should_exit->bool.

__device__ bool check_smart_exits(const GpuPosition& pos, const GpuSnapshot& snap,
                                  const GpuComboConfig* cfg, double p_atr,
                                  unsigned int sym_idx, const GpuParams* params) {
    // AQC-1226: delegate to double-precision codegen
    SmartExitResult se = check_smart_exits_codegen(
        *cfg,
        (int)pos.active,
        (double)pos.entry_price,
        (double)pos.entry_atr,
        (double)snap.close,
        (double)snap.ema_fast,
        (double)snap.ema_slow,
        (double)snap.ema_macro,
        (double)snap.adx,
        (double)snap.adx_slope,
        (double)snap.atr,
        (double)snap.avg_atr,
        (double)snap.rsi,
        (double)snap.macd_hist,
        (double)snap.prev_macd_hist,
        (double)snap.prev2_macd_hist,
        (double)snap.prev3_macd_hist,
        p_atr,
        (int)pos.confidence,
        (double)pos.entry_adx_threshold
    );
    // CPU parity: PAXG excludes only stagnation exit.
    // Important: when stagnation is skipped we must continue evaluating later
    // smart-exit checks (TSME/MMDE/RSI overextension), not force HOLD.
    if (se.should_exit
        && se.exit_code == 4
        && params->paxg_sym_idx != 0xFFFFFFFFu
        && sym_idx == params->paxg_sym_idx) {
        double eff_atr = (pos.entry_atr > 0.0) ? (double)pos.entry_atr : ((double)pos.entry_price * 0.005);
        // Stagnation gate is `atr < eff_atr * 0.70`; set atr to boundary so gate is false.
        double atr_no_stagnation = eff_atr * 0.70;
        SmartExitResult se_no_stagnation = check_smart_exits_codegen(
            *cfg,
            (int)pos.active,
            (double)pos.entry_price,
            (double)pos.entry_atr,
            (double)snap.close,
            (double)snap.ema_fast,
            (double)snap.ema_slow,
            (double)snap.ema_macro,
            (double)snap.adx,
            (double)snap.adx_slope,
            atr_no_stagnation,
            (double)snap.avg_atr,
            (double)snap.rsi,
            (double)snap.macd_hist,
            (double)snap.prev_macd_hist,
            (double)snap.prev2_macd_hist,
            (double)snap.prev3_macd_hist,
            p_atr,
            (int)pos.confidence,
            (double)pos.entry_adx_threshold
        );
        return se_no_stagnation.should_exit && se_no_stagnation.exit_code != 4;
    }
    return se.should_exit;
}

// -- Entry Sizing (AQC-1233: delegated to compute_entry_size_codegen) ---------
// Thin wrapper over codegen: float->double on inputs, SizingResultD->SizingResult (double->float).
// The codegen SizingResultD operates in double precision (AQC-734).
// This wrapper bridges to the float-based SizingResult used by the kernel.

struct SizingResult {
    double size;
    double margin;
    double leverage;
};

__device__ SizingResult compute_entry_size(double equity, double price, unsigned int confidence,
                                           double atr, const GpuSnapshot& snap,
                                           const GpuComboConfig* cfg) {
    // AQC-1233: delegate to double-precision codegen
    SizingResultD sd = compute_entry_size_codegen(
        equity, price, confidence,
        atr, (double)snap.adx, *cfg
    );

    SizingResult result;
    result.size = sd.size;
    result.margin = sd.margin;
    result.leverage = sd.leverage;
    return result;
}

// -- Exit Application ---------------------------------------------------------

__device__ void clear_position(GpuPosition* pos) {
    pos->active = POS_EMPTY;
    pos->_pad0 = 0u;
    pos->entry_price = 0.0;
    pos->size = 0.0;
    pos->confidence = 0u;
    pos->_pad1 = 0u;
    pos->entry_atr = 0.0;
    pos->entry_adx_threshold = 0.0;
    pos->trailing_sl = 0.0;
    pos->leverage = 0.0;
    pos->margin_used = 0.0;
    pos->adds_count = 0u;
    pos->tp1_taken = 0u;
    pos->open_time_sec = 0u;
    pos->last_add_time_sec = 0u;
    pos->kernel_margin_used = 0.0;
}

__device__ __forceinline__ void trace_record(
    GpuComboState* state,
    unsigned int sym,
    unsigned int t_sec,
    unsigned int kind,
    unsigned int side,
    unsigned int reason,
    float price,
    float size,
    double pnl
) {
    if (state->trace_enabled == 0u) { return; }
    if (state->trace_symbol != TRACE_SYMBOL_ALL && state->trace_symbol != sym) { return; }

    unsigned int idx = state->trace_head % TRACE_CAPACITY;
    GpuTraceEvent ev;
    ev.t_sec = t_sec;
    ev.sym = sym;
    ev.kind = kind;
    ev.side = side;
    ev.reason = reason;
    ev.price = price;
    ev.size = size;
    ev.pnl = pnl;
    state->trace_events[idx] = ev;

    state->trace_head += 1u;
    if (state->trace_count < TRACE_CAPACITY) {
        state->trace_count += 1u;
    }
}

__device__ void apply_close(GpuComboState* state, unsigned int sym, const GpuSnapshot& snap,
                            double market_close, unsigned int close_reason,
                            float fee_rate, float slippage_bps) {
    const GpuPosition& pos = state->positions[sym];
    if (pos.active == POS_EMPTY) { return; }

    (void)slippage_bps;
    double fill_price = quantize12(market_close
                                   * ((pos.active == POS_LONG)
                                          ? (1.0 - 0.5 / 10000.0)
                                          : (1.0 + 0.5 / 10000.0)));

    // Use double for PnL/fee to prevent accumulation drift over 10K+ trades
    double pnl;
    if (pos.active == POS_LONG) {
        pnl = quantize12((fill_price - (double)pos.entry_price) * (double)pos.size);
    } else {
        pnl = quantize12(((double)pos.entry_price - fill_price) * (double)pos.size);
    }
    double notional = quantize12((double)pos.size * fill_price);
    double fee = quantize12(notional * (double)fee_rate);
    double cash_delta = quantize12(pnl - fee);

    state->balance += cash_delta;
    state->kernel_cash = quantize12(state->kernel_cash + pos.kernel_margin_used + cash_delta);
    state->total_pnl += pnl;
    state->total_fees += fee;
    state->total_trades += 1u;
    if (pnl > 0.0) {
        state->total_wins += 1u;
        state->gross_profit += pnl;
    } else {
        state->gross_loss += fabs(pnl);
    }
    state->num_open -= 1u;

    trace_record(
        state,
        sym,
        snap.t_sec,
        TRACE_KIND_CLOSE,
        pos.active,
        close_reason,
        (float)fill_price,
        (float)pos.size,
        pnl
    );

    // PESC tracking
    state->pesc_close_time_sec[sym] = snap.t_sec;
    state->pesc_close_type[sym] = pos.active;
    if (close_reason == TRACE_REASON_SIGNAL_FLIP) {
        state->pesc_close_reason[sym] = PESC_SIGNAL_FLIP;
    } else {
        state->pesc_close_reason[sym] = PESC_OTHER;
    }
    state->last_exit_attempt_sec[sym] = snap.t_sec;

    // Clear position
    clear_position(&state->positions[sym]);
}

__device__ void apply_partial_close(GpuComboState* state, unsigned int sym, const GpuSnapshot& snap,
                                    double market_close, float pct, float fee_rate, float slippage_bps) {
    const GpuPosition& pos = state->positions[sym];
    if (pos.active == POS_EMPTY) { return; }

    // CPU parity: bt-core/accounting::build_partial_close_plan quantizes the
    // closed size before applying the fraction, then derives close_frac from
    // that quantised closed size.
    double frac = fmin(fmax((double)pct, 0.0), 1.0);
    double exit_size = quantize12((double)pos.size * frac);
    if (exit_size <= 0.0) { return; }
    if (exit_size > (double)pos.size) { exit_size = (double)pos.size; }
    (void)slippage_bps;
    double fill_price = quantize12(market_close
                                   * ((pos.active == POS_LONG)
                                          ? (1.0 - 0.5 / 10000.0)
                                          : (1.0 + 0.5 / 10000.0)));

    // Use double for PnL/fee to prevent accumulation drift over 10K+ trades
    double pnl;
    if (pos.active == POS_LONG) {
        pnl = quantize12((fill_price - (double)pos.entry_price) * (double)exit_size);
    } else {
        pnl = quantize12(((double)pos.entry_price - fill_price) * (double)exit_size);
    }
    double notional = quantize12((double)exit_size * fill_price);
    double fee = quantize12(notional * (double)fee_rate);
    double cash_delta = quantize12(pnl - fee);

    state->balance += cash_delta;
    double close_frac = (pos.size > 0.0) ? (exit_size / (double)pos.size) : 0.0;
    double kernel_margin_released = quantize12(pos.kernel_margin_used * close_frac);
    state->kernel_cash = quantize12(state->kernel_cash + kernel_margin_released + cash_delta);
    state->total_pnl += pnl;
    state->total_fees += fee;
    state->total_trades += 1u;
    if (pnl > 0.0) {
        state->total_wins += 1u;
        state->gross_profit += pnl;
    } else {
        state->gross_loss += fabs(pnl);
    }

    trace_record(
        state,
        sym,
        snap.t_sec,
        TRACE_KIND_PARTIAL,
        pos.active,
        TRACE_REASON_PARTIAL,
        (float)fill_price,
        (float)exit_size,
        pnl
    );

    // Reduce position
    state->positions[sym].size -= exit_size;
    state->positions[sym].margin_used *= (1.0 - close_frac);
    state->positions[sym].kernel_margin_used =
        quantize12(state->positions[sym].kernel_margin_used - kernel_margin_released);
    state->positions[sym].tp1_taken = 1u;
    // CPU parity: partial exits also refresh PESC cooldown state.
    state->pesc_close_time_sec[sym] = snap.t_sec;
    state->pesc_close_type[sym] = pos.active;
    state->pesc_close_reason[sym] = PESC_OTHER;
    state->last_exit_attempt_sec[sym] = snap.t_sec;
    // CPU semantics: trailing SL is NOT modified on partial close.
    // compute_trailing() continues ratcheting on subsequent bars.
}

// -- PESC Check (AQC-1233: delegated to is_pesc_blocked_codegen) ---------------
// Thin wrapper over codegen: maps state arrays to codegen params, float->double on adx.

__device__ bool is_pesc_blocked(const GpuComboState* state, unsigned int sym,
                                unsigned int desired_type, unsigned int current_sec,
                                float adx, const GpuComboConfig* cfg) {
    // AQC-1233: delegate to double-precision codegen
    return is_pesc_blocked_codegen(
        *cfg,
        0,  // bars_since_exit — unused by timestamp-based cooldown
        (double)adx,
        state->pesc_close_time_sec[sym],
        state->pesc_close_reason[sym],
        state->pesc_close_type[sym],
        desired_type,
        current_sec
    );
}

__device__ __forceinline__ bool is_entry_cooldown_active(const GpuComboState* state,
                                                          unsigned int sym,
                                                          unsigned int ts_sec,
                                                          const GpuComboConfig* cfg) {
    if (cfg->entry_cooldown_s == 0u) { return false; }
    unsigned int last_sec = state->last_entry_attempt_sec[sym];
    if (last_sec == 0u) { return false; }
    if (ts_sec <= last_sec) { return true; }
    return (ts_sec - last_sec) < cfg->entry_cooldown_s;
}

__device__ __forceinline__ bool is_exit_cooldown_active(const GpuComboState* state,
                                                         unsigned int sym,
                                                         unsigned int ts_sec,
                                                         const GpuComboConfig* cfg) {
    if (cfg->exit_cooldown_s == 0u) { return false; }
    unsigned int last_sec = state->last_exit_attempt_sec[sym];
    if (last_sec == 0u) { return false; }
    if (ts_sec <= last_sec) { return true; }
    return (ts_sec - last_sec) < cfg->exit_cooldown_s;
}

// -- TP Multiplier (must mirror bt-core fixed tp_atr_mult semantics) ---------

__device__ float get_tp_mult(const GpuSnapshot& snap, const GpuComboConfig* cfg) {
    // Parity with CPU: the CPU backtester always uses the configured TP ATR multiplier.
    // Dynamic TP scaling based on ADX is intentionally disabled on GPU.
    (void)snap;
    return cfg->tp_atr_mult;
}

// =============================================================================
// Main Compute Kernel
// =============================================================================

extern "C" __global__ void sweep_engine_kernel(
    const GpuParams*      __restrict__ params,
    const GpuSnapshot*    __restrict__ snapshots,
    const float*          __restrict__ breadth,
    const unsigned int*   __restrict__ btc_bullish,
    const GpuComboConfig* __restrict__ configs,
    GpuComboState*                     states,
    GpuResult*                         results,
    const GpuRawCandle*   __restrict__ main_candles,
    const GpuRawCandle*   __restrict__ sub_candles,
    const unsigned int*   __restrict__ sub_counts,
    const GpuFundingSpan* __restrict__ funding_spans,
    const double*         __restrict__ funding_rates
) {
    unsigned int combo_id = blockIdx.x * blockDim.x + threadIdx.x;
    if (combo_id >= params->num_combos) return;

    // Load state into local memory
    GpuComboState state = states[combo_id];
    GpuComboConfig cfg  = configs[combo_id];
    float fee_rate = get_taker_fee_rate(params);
    unsigned int ns = params->num_symbols;

    unsigned int max_sub = params->max_sub_per_bar;
    unsigned long long sub_counts_cap =
        (unsigned long long)params->num_bars * (unsigned long long)ns;
    unsigned long long sub_candles_cap =
        (unsigned long long)params->num_bars * (unsigned long long)max_sub * (unsigned long long)ns;

    // H10: precompute snapshot/breadth buffer bounds for safe indexing
    unsigned int snap_buf_size = cfg.snapshot_offset + params->num_bars * ns;
    unsigned int br_buf_size = cfg.breadth_offset + params->num_bars;

    for (unsigned int bar = params->chunk_start; bar < params->chunk_end; bar++) {
        state.entries_this_bar = 0u;
        float breadth_pct = SAFE_IDX(breadth, cfg.breadth_offset + bar, br_buf_size, 0.0f);
        unsigned int btc_bull = SAFE_IDX(btc_bullish, cfg.breadth_offset + bar, br_buf_size, BTC_BULL_UNKNOWN);

        if (max_sub > 0u) {
            // ================================================================
            // SUB-BAR PATH: use sub-bar candles for exit + entry price checks
            // Indicators come from the main bar snapshot (1h resolution)
            // ================================================================

            // CPU SSOT windowing invariant:
            //   - Exit/entry sub-bar scans are strictly within (bar_ts, next_bar_ts],
            //     implemented on CPU as a lower-bound search from ts+1ms.
            //
            // Some GPU sub-bar buckets can include a candle whose t_sec equals bar_ts.
            // If we process that candle, we can trigger early exits/partials/entries that
            // CPU never sees, cascading into extra trades and state-machine divergence.
            //
            // Derive bar_ts once per indicator bar (shared across symbols) and enforce
            // the same strict lower bound in both exit + entry sub-bar loops.
            //
            // CPU SSOT bar timing is anchored on the indicator/snapshot timeline.
            // Resolve from snapshots first, then fall back to main_candles.
            // As a final fallback, infer from entry interval geometry.
            const unsigned int main_bar_sec = params->max_sub_per_bar * params->entry_interval_sec;
            unsigned int bar_t_sec = 0u;
            for (unsigned int ts = 0u; ts < ns; ts++) {
                unsigned long long s_idx =
                    (unsigned long long)cfg.snapshot_offset
                    + (unsigned long long)bar * (unsigned long long)ns
                    + (unsigned long long)ts;
                if (s_idx >= (unsigned long long)snap_buf_size) { continue; }
                unsigned int t = snapshots[s_idx].t_sec;
                if (t != 0u) {
                    bar_t_sec = t;
                    break;
                }
            }
            if (bar_t_sec == 0u) {
                for (unsigned int ts = 0u; ts < ns; ts++) {
                    unsigned int t = main_candles[bar * ns + ts].t_sec;
                    if (t != 0u) {
                        bar_t_sec = t;
                        break;
                    }
                }
            }

            // Upper bound for CPU-style (bar_ts, next_bar_ts] windowing.
            unsigned int next_bar_t_sec = 0u;
            if (bar + 1u < params->num_bars) {
                for (unsigned int ts = 0u; ts < ns; ts++) {
                    unsigned long long s_idx =
                        (unsigned long long)cfg.snapshot_offset
                        + (unsigned long long)(bar + 1u) * (unsigned long long)ns
                        + (unsigned long long)ts;
                    if (s_idx >= (unsigned long long)snap_buf_size) { continue; }
                    unsigned int t = snapshots[s_idx].t_sec;
                    if (t != 0u) {
                        next_bar_t_sec = t;
                        break;
                    }
                }
                if (next_bar_t_sec == 0u) {
                    for (unsigned int ts = 0u; ts < ns; ts++) {
                        unsigned int t = main_candles[(bar + 1u) * ns + ts].t_sec;
                        if (t != 0u) {
                            next_bar_t_sec = t;
                            break;
                        }
                    }
                }
            }
            if (next_bar_t_sec == 0u && bar_t_sec != 0u && main_bar_sec != 0u) {
                next_bar_t_sec = bar_t_sec + main_bar_sec;
            }
            if (
                bar_t_sec == 0u
                && next_bar_t_sec != 0u
                && main_bar_sec != 0u
                && next_bar_t_sec > main_bar_sec
            ) {
                bar_t_sec = next_bar_t_sec - main_bar_sec;
            }

            // ── Sub-bar exits (per symbol, chronological) ───────────────────
            for (unsigned int sym = 0u; sym < ns; sym++) {
                if (state.positions[sym].active == POS_EMPTY) { continue; }

                // CPU parity: when sub-bar exits are enabled, exit checks must use the
                // previous fully-closed indicator snapshot while scanning sub-bars inside
                // the current indicator-bar window (avoid peeking into the current bar).
                const unsigned int base_bar = (bar > 0u) ? (bar - 1u) : bar;
                const GpuSnapshot& ind_snap_prev = snapshots[cfg.snapshot_offset + base_bar * ns + sym];
                if (ind_snap_prev.valid == 0u) { continue; }

                unsigned long long count_idx = SUB_COUNT_INDEX(bar, sym, ns);
                unsigned int n_sub = (count_idx < sub_counts_cap) ? sub_counts[count_idx] : 0u;
                if (n_sub > max_sub) { n_sub = max_sub; }
                for (unsigned int sub_i = 0u; sub_i < n_sub; sub_i++) {
                    unsigned long long sc_idx = SUB_CANDLE_INDEX(bar, sub_i, max_sub, ns, sym);
                    if (sc_idx >= sub_candles_cap) { continue; }
                    const GpuRawCandle& sc = sub_candles[sc_idx];
                    if (sc.close <= 0.0f || sc.t_sec == 0u) { continue; }
                    if (bar_t_sec != 0u && sc.t_sec <= bar_t_sec) { continue; }
                    if (next_bar_t_sec != 0u && sc.t_sec > next_bar_t_sec) { break; }
                    double sub_market_close = (double)sc.close;

                    // Build hybrid snapshot for sub-bar exits:
                    // indicator values from previous indicator-bar, price/time from sub-bar.
                    GpuSnapshot hybrid = ind_snap_prev;
                    hybrid.close = sc.close;
                    hybrid.high = sc.high;
                    hybrid.low = sc.low;
                    hybrid.open = sc.open;
                    hybrid.t_sec = sc.t_sec;

                    const GpuPosition& pos = state.positions[sym];
                    if (pos.active == POS_EMPTY) { break; } // exited in earlier sub-bar
                    double p_atr = profit_atr(pos, hybrid.close);

                    // Glitch guard (CPU semantics): block ALL exit processing including trailing update.
                    bool block_exits = false;
                    if (cfg.block_exits_on_extreme_dev != 0u && hybrid.prev_close > 0.0f) {
                        float price_change_pct = fabsf(hybrid.close - hybrid.prev_close) / hybrid.prev_close;
                        block_exits = (price_change_pct > cfg.glitch_price_dev_pct)
                            || (hybrid.atr > 0.0f
                                && fabsf(hybrid.close - hybrid.prev_close) > hybrid.atr * cfg.glitch_atr_mult);
                    }
                    if (block_exits) {
                        continue;  // CPU returns Hold — skip trailing update too
                    }
                    if (is_exit_cooldown_active(&state, sym, hybrid.t_sec, &cfg)) {
                        continue;
                    }
                    // CPU parity: kernel_margin_used tracks the decision-kernel margin model
                    // (per-trade leverage) and MUST NOT be overwritten during exit evaluation.
                    // If a position was seeded without kernel_margin_used (legacy init-state),
                    // derive it once from (size * entry_price) and the position's leverage.
                    if (state.positions[sym].kernel_margin_used <= 0.0
                        && state.positions[sym].active != POS_EMPTY
                        && state.positions[sym].size > 0.0
                        && state.positions[sym].entry_price > 0.0) {
                        double kernel_lev = ((double)state.positions[sym].leverage > 1.0)
                            ? (double)state.positions[sym].leverage
                            : 1.0;
                        double seed_notional =
                            (double)state.positions[sym].size * (double)state.positions[sym].entry_price;
                        double seed_kernel_notional = clamp_kernel_notional(seed_notional);
                        state.positions[sym].kernel_margin_used =
                            quantize12(seed_kernel_notional / kernel_lev);
                    }

                    // Stop loss
                    if (check_stop_loss(pos, hybrid, &cfg)) {
                        apply_close(&state, sym, hybrid, sub_market_close, TRACE_REASON_EXIT_STOP, fee_rate, cfg.slippage_bps);
                        break;
                    }

                    // Update trailing stop
                    double new_tsl = compute_trailing(pos, hybrid, &cfg, p_atr);
                    if (new_tsl > 0.0f) {
                        state.positions[sym].trailing_sl = new_tsl;
                    }

                    // Trailing stop exit
                    if (check_trailing_exit(state.positions[sym], hybrid)) {
                        apply_close(&state, sym, hybrid, sub_market_close, TRACE_REASON_EXIT_TRAILING, fee_rate, cfg.slippage_bps);
                        break;
                    }

                    // Take profit
                    float tp_mult = get_tp_mult(hybrid, &cfg);
                    unsigned int tp_result = check_tp(pos, hybrid, &cfg, tp_mult);
                    if (tp_result == 1u) {
                        apply_partial_close(&state, sym, hybrid, sub_market_close, cfg.tp_partial_pct, fee_rate, cfg.slippage_bps);
                        // CPU sub-bar semantics keep scanning later sub-bars after a partial TP.
                        // Remaining size can still hit SL/TS/other exits within the same bar window.
                        continue;
                    }
                    if (tp_result == 2u) {
                        apply_close(&state, sym, hybrid, sub_market_close, TRACE_REASON_EXIT_TP, fee_rate, cfg.slippage_bps);
                        break;
                    }

                    // Smart exits
                    if (check_smart_exits(pos, hybrid, &cfg, p_atr, sym, params)) {
                        apply_close(&state, sym, hybrid, sub_market_close, TRACE_REASON_EXIT_SMART, fee_rate, cfg.slippage_bps);
                        break;
                    }
                }
            }

            // ── Sub-bar entries (per-tick collection + ranking) ───────────────
            // CPU parity: sub-bar entry equity is computed once per main bar
            // (engine.rs sub_equity) and reused for all sub-ticks in the bar.
            double sub_entry_equity = state.balance;
            for (unsigned int eq_s = 0u; eq_s < ns; eq_s++) {
                if (state.positions[eq_s].active != POS_EMPTY) {
                    const GpuSnapshot& eq_snap = snapshots[cfg.snapshot_offset + bar * ns + eq_s];
                    // CPU parity: unrealised PnL marks to the latest known close even if
                    // the current (bar, symbol) candle is missing.
                    double eq_close = resolve_main_close(main_candles, bar, ns, eq_s, eq_snap);
                    sub_entry_equity += profit_usd(state.positions[eq_s], eq_close);
                }
            }
            if (sub_entry_equity < 0.0) { sub_entry_equity = 0.0; }

            // CPU parity: iterate merged unique sub-bar timestamps across symbols.
            // Keep one cursor per symbol and process the smallest next timestamp.
            unsigned int sub_cursor[MAX_SYMBOLS];
            for (unsigned int sym = 0u; sym < ns; sym++) {
                sub_cursor[sym] = 0u;
            }
            while (true) {
                unsigned int tick_ts = 0xFFFFFFFFu;
                bool has_tick = false;
                for (unsigned int sym = 0u; sym < ns; sym++) {
                    unsigned long long count_idx = SUB_COUNT_INDEX(bar, sym, ns);
                    unsigned int count = (count_idx < sub_counts_cap) ? sub_counts[count_idx] : 0u;
                    if (count > max_sub) { count = max_sub; }
                    unsigned int cur = sub_cursor[sym];
                    while (cur < count) {
                        unsigned long long probe_idx = SUB_CANDLE_INDEX(bar, cur, max_sub, ns, sym);
                        if (probe_idx >= sub_candles_cap) {
                            cur = count;
                            break;
                        }
                        const GpuRawCandle& probe = sub_candles[probe_idx];
                        if (probe.close <= 0.0f || probe.t_sec == 0u) { cur += 1u; continue; }
                        if (bar_t_sec != 0u && probe.t_sec <= bar_t_sec) { cur += 1u; continue; }
                        if (next_bar_t_sec != 0u && probe.t_sec > next_bar_t_sec) {
                            cur = count;
                            break;
                        }
                        break;
                    }
                    sub_cursor[sym] = cur;
                    if (cur >= count) { continue; }
                    unsigned long long probe_idx = SUB_CANDLE_INDEX(bar, cur, max_sub, ns, sym);
                    if (probe_idx >= sub_candles_cap) { continue; }
                    const GpuRawCandle& probe = sub_candles[probe_idx];
                    if (!has_tick || probe.t_sec < tick_ts) {
                        tick_ts = probe.t_sec;
                        has_tick = true;
                    }
                }
                if (!has_tick) { break; }

                EntryCandidate candidates[MAX_CANDIDATES];
                unsigned int candidate_sub_slot[MAX_CANDIDATES];
                unsigned int num_cands = 0u;

                for (unsigned int sym = 0u; sym < ns; sym++) {
                    if (num_cands >= MAX_CANDIDATES) { break; }
                    if (state.entries_this_bar >= cfg.max_entry_orders_per_loop) { break; }

                    unsigned int sub_slot = sub_cursor[sym];
                    unsigned long long count_idx = SUB_COUNT_INDEX(bar, sym, ns);
                    unsigned int count = (count_idx < sub_counts_cap) ? sub_counts[count_idx] : 0u;
                    if (count > max_sub) { count = max_sub; }
                    if (sub_slot >= count) { continue; }

                    unsigned long long sc_idx = SUB_CANDLE_INDEX(bar, sub_slot, max_sub, ns, sym);
                    if (sc_idx >= sub_candles_cap) { continue; }
                    const GpuRawCandle& sc = sub_candles[sc_idx];
                    if (sc.close <= 0.0f || sc.t_sec == 0u || (bar_t_sec != 0u && sc.t_sec <= bar_t_sec)) { continue; }
                    if (sc.t_sec != tick_ts) { continue; }
                    unsigned int eval_t_sec = sc.t_sec;
                    if (params->signal_on_candle_close != 0u) {
                        if (params->entry_interval_sec == 0u || next_bar_t_sec == 0u) {
                            continue;
                        }
                        unsigned long long sub_close_t_sec =
                            (unsigned long long)sc.t_sec + (unsigned long long)params->entry_interval_sec;
                        if (sub_close_t_sec != (unsigned long long)next_bar_t_sec) {
                            continue;
                        }
                        eval_t_sec = next_bar_t_sec;
                    }

                    const GpuSnapshot& ind_snap_cur = snapshots[cfg.snapshot_offset + bar * ns + sym];
                    if (ind_snap_cur.valid == 0u) { continue; }

                    // CPU parity:
                    // - signal_on_candle_close == 0 => use the previous fully-closed indicator snapshot
                    //   for sub-bar entry evaluation (avoid peeking into the current bar).
                    // - signal_on_candle_close == 1 => evaluation happens at the bar boundary and
                    //   uses the current indicator snapshot.
                    const unsigned int base_bar = (params->signal_on_candle_close != 0u)
                        ? bar
                        : ((bar > 0u) ? (bar - 1u) : bar);
                    const GpuSnapshot& base_snap = snapshots[cfg.snapshot_offset + base_bar * ns + sym];
                    if (base_snap.valid == 0u) { continue; }

                    // Build hybrid: indicators from selected base snapshot, price from sub-bar
                    GpuSnapshot hybrid = base_snap;
                    hybrid.close = sc.close;
                    hybrid.high = sc.high;
                    hybrid.low = sc.low;
                    hybrid.open = sc.open;
                    hybrid.t_sec = eval_t_sec;

                    GpuPosition& pos = state.positions[sym];
                    const bool pos_open = (pos.active != POS_EMPTY);

                    // CPU SSOT parity:
                    // - Evaluate sub-bar candidates even when a position is already open (needed for same-direction pyramiding).
                    // - Entry cooldown is only an early-out for fresh OPEN candidates; pyramiding re-checks cooldown internally.
                    if (!pos_open && is_entry_cooldown_active(&state, sym, hybrid.t_sec, &cfg)) { continue; }

                    // Gates, signal generation, filters (using hybrid snapshot with indicator values)
                    // AQC-1213: gates and signal now use codegen (double precision)
                    bool is_btc_symbol = (sym == params->btc_sym_idx);
                    // CPU parity: ema_slow_slope_pct is sourced from the current indicator-bar update.
                    float ema_slope = ind_snap_cur.ema_slow_slope_pct;
                    GateResult gates = check_gates(hybrid, &cfg, ema_slope,
                                                    btc_bull, is_btc_symbol);
                    SignalResultLegacy sig_result = generate_signal(
                        hybrid,
                        &cfg,
                        gates,
                        btc_bull,
                        is_btc_symbol,
                        ema_slope
                    );
                    unsigned int signal = sig_result.signal;
                    unsigned int confidence = sig_result.confidence;
                    double entry_adx_thresh = sig_result.entry_adx_threshold;
                    const bool debug_target =
                        (state.trace_enabled != 0u)
                        && (state.trace_symbol == TRACE_SYMBOL_ALL || state.trace_symbol == sym)
                        && (params->debug_t_sec != 0u && params->debug_t_sec == hybrid.t_sec);

                    if (debug_target) {
                        printf(
                            "[gpu-sub-cand-debug] sym=%u ts=%u raw_signal=%u conf=%u breadth=%.6f btc=%u adx=%.6f adx_s=%.6f macd=%.10f rsi=%.6f\n",
                            sym, hybrid.t_sec, signal, confidence, breadth_pct, btc_bull,
                            hybrid.adx, hybrid.adx_slope, hybrid.macd_hist, hybrid.rsi
                        );
                    }

                    if (signal == SIG_NEUTRAL) {
                        if (debug_target) {
                            printf(
                                "[gpu-sub-cand-debug] sym=%u ts=%u rejected=neutral_raw breadth=%.6f\n",
                                sym, hybrid.t_sec, breadth_pct
                            );
                        }
                        continue;
                    }

                    double atr = apply_atr_floor((double)hybrid.atr, (double)hybrid.close, (double)cfg.min_atr_pct);

                    signal = apply_reverse(signal, &cfg, breadth_pct);
                    if (debug_target) {
                        printf(
                            "[gpu-sub-cand-debug] sym=%u ts=%u after_reverse=%u breadth=%.6f\n",
                            sym, hybrid.t_sec, signal, breadth_pct
                        );
                    }
                    if (signal == SIG_NEUTRAL) {
                        if (debug_target) {
                            printf(
                                "[gpu-sub-cand-debug] sym=%u ts=%u rejected=neutral_after_reverse breadth=%.6f\n",
                                sym, hybrid.t_sec, breadth_pct
                            );
                        }
                        continue;
                    }
                    signal = apply_regime_filter(signal, &cfg, breadth_pct);
                    if (debug_target) {
                        printf(
                            "[gpu-sub-cand-debug] sym=%u ts=%u after_regime=%u breadth=%.6f\n",
                            sym, hybrid.t_sec, signal, breadth_pct
                        );
                    }
                    if (signal == SIG_NEUTRAL) {
                        if (debug_target) {
                            printf(
                                "[gpu-sub-cand-debug] sym=%u ts=%u rejected=neutral_after_regime breadth=%.6f\n",
                                sym, hybrid.t_sec, breadth_pct
                            );
                        }
                        continue;
                    }

                    if (!conf_meets_min(confidence, cfg.entry_min_confidence)) {
                        if (debug_target) {
                            printf(
                                "[gpu-sub-cand-debug] sym=%u ts=%u rejected=min_conf conf=%u min=%u\n",
                                sym, hybrid.t_sec, confidence, cfg.entry_min_confidence
                            );
                        }
                        continue;
                    }

                    unsigned int desired_type = (signal == SIG_BUY) ? POS_LONG : POS_SHORT;
                    bool pesc_blocked = is_pesc_blocked(&state, sym, desired_type, hybrid.t_sec, hybrid.adx, &cfg);
                    if (pesc_blocked) {
                        if (debug_target) {
                            printf(
                                "[gpu-sub-cand-debug] sym=%u ts=%u rejected=pesc desired=%u adx=%.6f\n",
                                sym, hybrid.t_sec, desired_type, hybrid.adx
                            );
                        }
                        continue;
                    }

                    if (cfg.enable_ssf_filter != 0u) {
                        if (signal == SIG_BUY && hybrid.macd_hist <= 0.0f) {
                            if (debug_target) {
                                printf(
                                    "[gpu-sub-cand-debug] sym=%u ts=%u rejected=ssf_buy macd=%.10f\n",
                                    sym, hybrid.t_sec, hybrid.macd_hist
                                );
                            }
                            continue;
                        }
                        if (signal == SIG_SELL && hybrid.macd_hist >= 0.0f) {
                            if (debug_target) {
                                printf(
                                    "[gpu-sub-cand-debug] sym=%u ts=%u rejected=ssf_sell macd=%.10f\n",
                                    sym, hybrid.t_sec, hybrid.macd_hist
                                );
                            }
                            continue;
                        }
                    }

                    if (cfg.enable_reef_filter != 0u) {
                        if (signal == SIG_BUY) {
                            if (hybrid.adx < cfg.reef_adx_threshold) {
                                if (hybrid.rsi > cfg.reef_long_rsi_block_gt) {
                                    if (debug_target) {
                                        printf(
                                            "[gpu-sub-cand-debug] sym=%u ts=%u rejected=reef_buy adx=%.6f rsi=%.6f\n",
                                            sym, hybrid.t_sec, hybrid.adx, hybrid.rsi
                                        );
                                    }
                                    continue;
                                }
                            } else {
                                if (hybrid.rsi > cfg.reef_long_rsi_extreme_gt) {
                                    if (debug_target) {
                                        printf(
                                            "[gpu-sub-cand-debug] sym=%u ts=%u rejected=reef_buy_extreme adx=%.6f rsi=%.6f\n",
                                            sym, hybrid.t_sec, hybrid.adx, hybrid.rsi
                                        );
                                    }
                                    continue;
                                }
                            }
                        }
                        if (signal == SIG_SELL) {
                            if (hybrid.adx < cfg.reef_adx_threshold) {
                                if (hybrid.rsi < cfg.reef_short_rsi_block_lt) {
                                    if (debug_target) {
                                        printf(
                                            "[gpu-sub-cand-debug] sym=%u ts=%u rejected=reef_sell adx=%.6f rsi=%.6f\n",
                                            sym, hybrid.t_sec, hybrid.adx, hybrid.rsi
                                        );
                                    }
                                    continue;
                                }
                            } else {
                                if (hybrid.rsi < cfg.reef_short_rsi_extreme_lt) {
                                    if (debug_target) {
                                        printf(
                                            "[gpu-sub-cand-debug] sym=%u ts=%u rejected=reef_sell_extreme adx=%.6f rsi=%.6f\n",
                                            sym, hybrid.t_sec, hybrid.adx, hybrid.rsi
                                        );
                                    }
                                    continue;
                                }
                            }
                        }
                    }
                    if (debug_target) {
                        printf(
                            "[gpu-sub-cand-debug] sym=%u ts=%u accepted signal=%u conf=%u adx=%.6f atr=%.10f entry_adx=%.6f breadth=%.6f btc=%u\n",
                            sym, hybrid.t_sec, signal, confidence, hybrid.adx, atr,
                            entry_adx_thresh, breadth_pct, btc_bull
                        );
                    }

                    // CPU parity: if a same-direction signal arrives while a position is already open,
                    // route it through pyramiding checks instead of treating it as a fresh OPEN candidate.
                    if (pos_open) {
                        if (cfg.enable_pyramiding != 0u && pos.active == desired_type) {
                            // try_pyramid() — mirror CPU behaviour used in the sub-bar entry block (engine.rs).
                            if (pos.adds_count >= cfg.max_adds_per_symbol) {
                                if (debug_target) {
                                    printf(
                                        "[gpu-sub-pyr-debug] sym=%u ts=%u rejected=max_adds adds=%u max=%u\n",
                                        sym, hybrid.t_sec, pos.adds_count, cfg.max_adds_per_symbol
                                    );
                                }
                            } else if (cfg.add_min_confidence != 0u && confidence < cfg.add_min_confidence) {
                                if (debug_target) {
                                    printf(
                                        "[gpu-sub-pyr-debug] sym=%u ts=%u rejected=min_conf conf=%u min=%u\n",
                                        sym, hybrid.t_sec, confidence, cfg.add_min_confidence
                                    );
                                }
                            } else if (is_entry_cooldown_active(&state, sym, hybrid.t_sec, &cfg)) {
                                if (debug_target) {
                                    printf(
                                        "[gpu-sub-pyr-debug] sym=%u ts=%u rejected=entry_cooldown\n",
                                        sym, hybrid.t_sec
                                    );
                                }
                            } else {
                                double min_profit_atr = (double)cfg.add_min_profit_atr;
                                // Reduce min_profit_atr in a strong trend with stable ATR, unless RSI is extreme.
                                if ((double)hybrid.adx_slope > 0.75 && (double)hybrid.atr_slope <= 0.0) {
                                    bool is_rsi_extreme = (pos.active == POS_LONG)
                                        ? ((double)hybrid.rsi > 65.0)
                                        : ((double)hybrid.rsi < 35.0);
                                    if (!is_rsi_extreme) {
                                        min_profit_atr *= 0.5;
                                    }
                                }

                                double current_atr = atr;
                                if (!(current_atr > 0.0)) {
                                    current_atr = ((double)pos.entry_atr > 0.0)
                                        ? (double)pos.entry_atr
                                        : ((double)pos.entry_price * 0.005);
                                }

                                double entry_close = (double)sc.close;
                                if (current_atr > 0.0 && entry_close > 0.0) {
                                    double p_atr_pyr = (pos.active == POS_LONG)
                                        ? ((entry_close - (double)pos.entry_price) / current_atr)
                                        : (((double)pos.entry_price - entry_close) / current_atr);
                                    if (!isfinite(p_atr_pyr)) { p_atr_pyr = 0.0; }

                                    if (p_atr_pyr >= min_profit_atr) {
                                        long long elapsed_sec =
                                            (long long)hybrid.t_sec - (long long)pos.last_add_time_sec;
                                        long long min_add_cooldown_sec =
                                            (long long)cfg.add_cooldown_minutes * 60ll;
                                        if (elapsed_sec >= min_add_cooldown_sec) {
                                            // CPU parity: try_pyramid uses balance-only equity approximation.
                                            double equity = state.balance;
                                            if (equity < 0.0) { equity = 0.0; }

                                            double allocation_pct = (double)cfg.allocation_pct;
                                            if (allocation_pct < 0.0) { allocation_pct = 0.0; }

                                            double base_margin = equity * allocation_pct;
                                            double add_margin =
                                                base_margin * (double)cfg.add_fraction_of_base_margin;

                                            if (add_margin > 0.0) {
                                                // Margin cap (max_total_margin_pct)
                                                double max_margin_pct = (double)cfg.max_total_margin_pct;
                                                if (max_margin_pct > 0.0) {
                                                    double total_margin = 0.0;
                                                    for (unsigned int s = 0u; s < ns; s++) {
                                                        if (state.positions[s].active != POS_EMPTY) {
                                                            total_margin += (double)state.positions[s].margin_used;
                                                        }
                                                    }
                                                    double max_margin = equity * max_margin_pct;
                                                    if (total_margin + add_margin > max_margin) {
                                                        if (debug_target) {
                                                            printf(
                                                                "[gpu-sub-pyr-debug] sym=%u ts=%u rejected=margin total=%.12f add=%.12f max=%.12f\n",
                                                                sym, hybrid.t_sec, total_margin, add_margin, max_margin
                                                            );
                                                        }
                                                        // Do not open new positions when already open; just move on.
                                                        continue;
                                                    }
                                                }

                                                double lev = (double)pos.leverage;
                                                double add_notional = add_margin * lev;
                                                double add_size = add_notional / entry_close;

                                                if (add_notional < cfg.min_notional_usd) {
                                                    if (cfg.bump_to_min_notional != 0u && entry_close > 0.0) {
                                                        add_notional = (double)cfg.min_notional_usd;
                                                        add_size = add_notional / entry_close;
                                                    } else {
                                                        if (debug_target) {
                                                            printf(
                                                                "[gpu-sub-pyr-debug] sym=%u ts=%u rejected=min_notional add_notional=%.12f min=%.12f\n",
                                                                sym, hybrid.t_sec, add_notional, (double)cfg.min_notional_usd
                                                            );
                                                        }
                                                        continue;
                                                    }
                                                }

                                                double kernel_lev = (lev > 1.0) ? lev : 1.0;
                                                double kernel_add_notional = clamp_kernel_notional(add_notional);
                                                double kernel_margin_add =
                                                    quantize12(kernel_add_notional / kernel_lev);
                                                double add_fee =
                                                    quantize12(kernel_add_notional * (double)fee_rate);

                                                if (kernel_margin_add + add_fee > state.kernel_cash) {
                                                    if (debug_target) {
                                                        printf(
                                                            "[gpu-sub-pyr-debug] sym=%u ts=%u rejected=insufficient_cash add_notional=%.12f kernel_margin_add=%.12f kernel_cash=%.12f fee=%.12f\n",
                                                            sym, hybrid.t_sec, add_notional, kernel_margin_add, state.kernel_cash, add_fee
                                                        );
                                                    }
                                                    continue;
                                                }

                                                double fee = quantize12((double)add_notional * (double)fee_rate);
                                                state.balance -= fee;
                                                state.kernel_cash =
                                                    quantize12(state.kernel_cash - (kernel_margin_add + add_fee));
                                                state.total_fees += fee;

                                                double old_size = pos.size;
                                                double new_size = old_size + add_size;
                                                float add_slip =
                                                    (pos.active == POS_LONG) ? cfg.slippage_bps : -cfg.slippage_bps;
                                                double add_fill_price = quantize12(
                                                    entry_close * (1.0 + (double)add_slip / 10000.0));
                                                double new_entry =
                                                    ((double)pos.entry_price * old_size + (add_fill_price * add_size))
                                                    / new_size;

                                                state.positions[sym].entry_price = new_entry;
                                                state.positions[sym].size = new_size;
                                                state.positions[sym].margin_used =
                                                    state.positions[sym].margin_used + add_margin;
                                                state.positions[sym].kernel_margin_used =
                                                    quantize12(state.positions[sym].kernel_margin_used + kernel_margin_add);
                                                state.positions[sym].adds_count += 1u;
                                                state.positions[sym].last_add_time_sec = hybrid.t_sec;
                                                state.last_entry_attempt_sec[sym] = hybrid.t_sec;

                                                trace_record(
                                                    &state,
                                                    sym,
                                                    hybrid.t_sec,
                                                    TRACE_KIND_ADD,
                                                    pos.active,
                                                    TRACE_REASON_PYRAMID,
                                                    (float)add_fill_price,
                                                    (float)add_size,
                                                    0.0f
                                                );
                                            }
                                        } else if (debug_target) {
                                            printf(
                                                "[gpu-sub-pyr-debug] sym=%u ts=%u rejected=add_cooldown elapsed_sec=%lld min_sec=%lld\n",
                                                sym, hybrid.t_sec, elapsed_sec, min_add_cooldown_sec
                                            );
                                        }
                                    } else if (debug_target) {
                                        printf(
                                            "[gpu-sub-pyr-debug] sym=%u ts=%u rejected=min_profit_atr profit_atr=%.12f min=%.12f atr=%.12f\n",
                                            sym, hybrid.t_sec, p_atr_pyr, min_profit_atr, current_atr
                                        );
                                    }
                                }
                            }
                        }
                        // Regardless of whether pyramiding was accepted, do not treat this as a fresh OPEN candidate.
                        continue;
                    }
                    int score = (int)(confidence) * 100 + (int)(hybrid.adx);

                    EntryCandidate cand;
                    cand.sym_idx = sym;
                    cand.signal = signal;
                    cand.confidence = confidence;
                    cand.score = score;
                    cand.adx = hybrid.adx;
                    cand.atr = atr;
                    cand.entry_adx_threshold = entry_adx_thresh;
                    candidates[num_cands] = cand;
                    candidate_sub_slot[num_cands] = sub_slot;
                    num_cands += 1u;
                }

                // Rank candidates for this sub-bar tick
                for (unsigned int i = 1u; i < num_cands; i++) {
                    EntryCandidate key = candidates[i];
                    unsigned int key_sub_slot = candidate_sub_slot[i];
                    unsigned int j = i;
                    while (j > 0u
                           && (candidates[j - 1u].score < key.score
                               || (candidates[j - 1u].score == key.score
                                   && candidates[j - 1u].sym_idx > key.sym_idx))) {
                        candidates[j] = candidates[j - 1u];
                        candidate_sub_slot[j] = candidate_sub_slot[j - 1u];
                        j -= 1u;
                    }
                    candidates[j] = key;
                    candidate_sub_slot[j] = key_sub_slot;
                }
                // Execute ranked entries for this sub-bar tick
                for (unsigned int i = 0u; i < num_cands; i++) {
                    if (state.entries_this_bar >= cfg.max_entry_orders_per_loop) { break; }
                    if (state.num_open >= cfg.max_open_positions) { break; }

                    const EntryCandidate& cand = candidates[i];

                    // Re-read sub-bar candle for fill price
                    unsigned int cand_sub_slot = candidate_sub_slot[i];
                    const GpuRawCandle& sc = sub_candles[(bar * max_sub + cand_sub_slot) * ns + cand.sym_idx];

                    // CPU parity: entry sizing must use the same indicator snapshot selection
                    // as candidate evaluation.
                    const unsigned int base_bar = (params->signal_on_candle_close != 0u)
                        ? bar
                        : ((bar > 0u) ? (bar - 1u) : bar);
                    const GpuSnapshot& base_snap = snapshots[cfg.snapshot_offset + base_bar * ns + cand.sym_idx];

                    GpuSnapshot hybrid = base_snap;
                    hybrid.close = sc.close;
                    hybrid.high = sc.high;
                    hybrid.low = sc.low;
                    hybrid.open = sc.open;
                    hybrid.t_sec = (params->signal_on_candle_close != 0u && next_bar_t_sec != 0u)
                        ? next_bar_t_sec
                        : sc.t_sec;
                    double entry_close = (double)sc.close;
                    // Margin cap
                    double total_margin = 0.0;
                    for (unsigned int s = 0u; s < ns; s++) {
                        if (state.positions[s].active != POS_EMPTY) {
                            total_margin += (double)state.positions[s].margin_used;
                        }
                    }
                    double max_margin_pct = (double)cfg.max_total_margin_pct;
                    double headroom = sub_entry_equity * max_margin_pct - total_margin;
                    if (headroom <= 0.0) { continue; }

                    SizingResult sizing = compute_entry_size(sub_entry_equity, entry_close, cand.confidence,
                                                             cand.atr, hybrid, &cfg);
                    double size = sizing.size;
                    double margin = sizing.margin;
                    double lev = sizing.leverage;

                    if (margin > headroom) {
                        double ratio = headroom / margin;
                        size *= ratio;
                        margin = headroom;
                    }

                double notional = size * entry_close;
                if (notional < cfg.min_notional_usd) {
                    if (cfg.bump_to_min_notional != 0u && entry_close > 0.0) {
                        size = (double)cfg.min_notional_usd / entry_close;
                        margin = size * entry_close / lev;
                        notional = size * entry_close;
                        if (margin > headroom) {
                            continue;
                        }
                    } else {
                        continue;
                    }
                }

                    // CPU parity (decision kernel): require kernel cash >= margin + fee,
                    // where margin is computed using per-trade leverage (lev) from sizing.
                    double kernel_lev = (lev > 1.0) ? lev : 1.0;
                    double kernel_notional = clamp_kernel_notional(notional);
                    double kernel_margin_req = quantize12(kernel_notional / kernel_lev);
                    double open_fee = quantize12(kernel_notional * (double)fee_rate);
                    if (kernel_margin_req + open_fee > state.kernel_cash) {
                        continue;
                    }

                    float slip = (cand.signal == SIG_BUY) ? cfg.slippage_bps : -cfg.slippage_bps;
                    double fill_price = quantize12(
                        entry_close * (1.0 + (double)slip / 10000.0));
                    double fee = quantize12((double)notional * (double)fee_rate);
                    state.balance -= fee;
                    state.kernel_cash = quantize12(state.kernel_cash - (kernel_margin_req + open_fee));
                    state.total_fees += fee;

                    GpuPosition new_pos;
                    new_pos.active = (cand.signal == SIG_BUY) ? POS_LONG : POS_SHORT;
                    new_pos._pad0 = 0u;
                    new_pos.entry_price = fill_price;
                    new_pos.size = size;
                    new_pos.confidence = cand.confidence;
                    new_pos._pad1 = 0u;
                    new_pos.entry_atr = cand.atr;
                    new_pos.entry_adx_threshold = cand.entry_adx_threshold;
                    new_pos.trailing_sl = 0.0;
                    new_pos.leverage = lev;
                    new_pos.margin_used = margin;
                    new_pos.adds_count = 0u;
                    new_pos.tp1_taken = 0u;
                    new_pos.open_time_sec = hybrid.t_sec;
                    new_pos.last_add_time_sec = hybrid.t_sec;
                    new_pos.kernel_margin_used = kernel_margin_req;
                    state.positions[cand.sym_idx] = new_pos;
                    state.last_entry_attempt_sec[cand.sym_idx] = hybrid.t_sec;

                    state.num_open += 1u;
                    state.entries_this_bar += 1u;
                    trace_record(
                        &state,
                        cand.sym_idx,
                        hybrid.t_sec,
                        TRACE_KIND_OPEN,
                        new_pos.active,
                        TRACE_REASON_ENTRY,
                        (float)fill_price,
                        (float)size,
                        0.0f
                    );
                }

                for (unsigned int sym = 0u; sym < ns; sym++) {
                    unsigned int cur = sub_cursor[sym];
                    unsigned long long count_idx = SUB_COUNT_INDEX(bar, sym, ns);
                    unsigned int count = (count_idx < sub_counts_cap) ? sub_counts[count_idx] : 0u;
                    if (count > max_sub) { count = max_sub; }
                    if (cur >= count) { continue; }
                    unsigned long long probe_idx = SUB_CANDLE_INDEX(bar, cur, max_sub, ns, sym);
                    if (probe_idx >= sub_candles_cap) { continue; }
                    const GpuRawCandle& probe = sub_candles[probe_idx];
                    if (probe.t_sec == tick_ts) {
                        sub_cursor[sym] = cur + 1u;
                    }
                }

            }

        } else {
            // ================================================================
            // MAIN-BAR PATH: original behavior (backwards compatible)
            // ================================================================

            // == Phase 1: Exits (per symbol, immediate) ======================
            for (unsigned int sym = 0u; sym < ns; sym++) {
                const GpuSnapshot& snap = snapshots[cfg.snapshot_offset + bar * ns + sym];
                if (snap.valid == 0u) { continue; }
                double main_market_close = resolve_main_close(main_candles, bar, ns, sym, snap);

                const GpuPosition& pos = state.positions[sym];
                if (pos.active == POS_EMPTY) { continue; }

                double p_atr = profit_atr(pos, snap.close);

                // Glitch guard (CPU semantics): block ALL exit processing including trailing update.
                bool block_exits = false;
                if (cfg.block_exits_on_extreme_dev != 0u && snap.prev_close > 0.0f) {
                    float price_change_pct = fabsf(snap.close - snap.prev_close) / snap.prev_close;
                    block_exits = (price_change_pct > cfg.glitch_price_dev_pct)
                        || (snap.atr > 0.0f
                            && fabsf(snap.close - snap.prev_close) > snap.atr * cfg.glitch_atr_mult);
                }
                bool partial_tp_taken = false;
                if (!block_exits && !is_exit_cooldown_active(&state, sym, snap.t_sec, &cfg)) {
                    // CPU parity: kernel_margin_used tracks the decision-kernel margin model
                    // (per-trade leverage) and MUST NOT be overwritten during exit evaluation.
                    // If a position was seeded without kernel_margin_used (legacy init-state),
                    // derive it once from (size * entry_price) and the position's leverage.
                    if (state.positions[sym].kernel_margin_used <= 0.0
                        && state.positions[sym].active != POS_EMPTY
                        && state.positions[sym].size > 0.0
                        && state.positions[sym].entry_price > 0.0) {
                        double kernel_lev = ((double)state.positions[sym].leverage > 1.0)
                            ? (double)state.positions[sym].leverage
                            : 1.0;
                        double seed_notional =
                            (double)state.positions[sym].size * (double)state.positions[sym].entry_price;
                        double seed_kernel_notional = clamp_kernel_notional(seed_notional);
                        state.positions[sym].kernel_margin_used =
                            quantize12(seed_kernel_notional / kernel_lev);
                    }

                    // Stop loss
                    if (check_stop_loss(pos, snap, &cfg)) {
                        apply_close(&state, sym, snap, main_market_close, TRACE_REASON_EXIT_STOP, fee_rate, cfg.slippage_bps);
                        continue;
                    }

                    // Update trailing stop
                    double new_tsl = compute_trailing(pos, snap, &cfg, p_atr);
                    if (new_tsl > 0.0f) {
                        state.positions[sym].trailing_sl = new_tsl;
                    }

                    // Trailing stop exit
                    if (check_trailing_exit(state.positions[sym], snap)) {
                        apply_close(&state, sym, snap, main_market_close, TRACE_REASON_EXIT_TRAILING, fee_rate, cfg.slippage_bps);
                        continue;
                    }

                    // Take profit
                    float tp_mult = get_tp_mult(snap, &cfg);
                    unsigned int tp_result = check_tp(pos, snap, &cfg, tp_mult);
                    if (tp_result == 1u) {
                        apply_partial_close(&state, sym, snap, main_market_close, cfg.tp_partial_pct, fee_rate, cfg.slippage_bps);
                        partial_tp_taken = true;
                    }
                    if (tp_result == 2u) {
                        apply_close(&state, sym, snap, main_market_close, TRACE_REASON_EXIT_TP, fee_rate, cfg.slippage_bps);
                        continue;
                    }

                    // Smart exits (skip when partial TP fired this bar, same as prior flow)
                    if (!partial_tp_taken && check_smart_exits(pos, snap, &cfg, p_atr, sym, params)) {
                        apply_close(&state, sym, snap, main_market_close, TRACE_REASON_EXIT_SMART, fee_rate, cfg.slippage_bps);
                        continue;
                    }
                }

                // Signal-directed close (CPU parity: engine.rs indicator-bar-close path)
                if (state.positions[sym].active != POS_EMPTY) {
                    bool is_btc_sym_flip = (sym == params->btc_sym_idx);
                    GateResult gates_flip = check_gates(snap, &cfg, snap.ema_slow_slope_pct,
                                                        btc_bull, is_btc_sym_flip);
                    SignalResultLegacy sig_flip = generate_signal(
                        snap, &cfg, gates_flip, btc_bull, is_btc_sym_flip,
                        snap.ema_slow_slope_pct);
                    unsigned int flip_signal = sig_flip.signal;
                    if (flip_signal != SIG_NEUTRAL) {
                        flip_signal = apply_reverse(flip_signal, &cfg, breadth_pct);
                    }
                    if (flip_signal != SIG_NEUTRAL) {
                        flip_signal = apply_regime_filter(flip_signal, &cfg, breadth_pct);
                    }
                    if (flip_signal != SIG_NEUTRAL) {
                        unsigned int desired_type = (flip_signal == SIG_BUY) ? POS_LONG : POS_SHORT;
                        if (desired_type != state.positions[sym].active) {
                            apply_close(&state, sym, snap, main_market_close, TRACE_REASON_SIGNAL_FLIP, fee_rate, cfg.slippage_bps);
                        }
                    }
                }

                // Pyramiding (same-direction add) -- not ranked, immediate
                const GpuPosition& pos_after_exit = state.positions[sym];
                const bool pyr_debug_target = false;
                if (pos_after_exit.active != POS_EMPTY && cfg.enable_pyramiding != 0u) {
                    if (is_entry_cooldown_active(&state, sym, snap.t_sec, &cfg)) {
                        if (pyr_debug_target) {
                            printf("[gpu-pyr-debug] sym=%u ts=%u rejected=entry_cooldown\\n", sym, snap.t_sec);
                        }
                        continue;
                    }
                    if (pos_after_exit.adds_count < cfg.max_adds_per_symbol) {
                        bool is_btc_sym_pyr = (sym == params->btc_sym_idx);
                        GateResult gates_pyr = check_gates(snap, &cfg, snap.ema_slow_slope_pct,
                                                            btc_bull, is_btc_sym_pyr);
                        SignalResultLegacy sig_pyr = generate_signal(
                            snap, &cfg, gates_pyr, btc_bull, is_btc_sym_pyr,
                            snap.ema_slow_slope_pct);
                        unsigned int pyr_signal = sig_pyr.signal;
                        if (pyr_signal != SIG_NEUTRAL) {
                            pyr_signal = apply_reverse(pyr_signal, &cfg, breadth_pct);
                        }
                        if (pyr_signal != SIG_NEUTRAL) {
                            pyr_signal = apply_regime_filter(pyr_signal, &cfg, breadth_pct);
                        }
                        const unsigned int desired_signal =
                            (pos_after_exit.active == POS_LONG) ? SIG_BUY : SIG_SELL;
                        if (pyr_signal != desired_signal) {
                            if (pyr_debug_target) {
                                printf(
                                    "[gpu-pyr-debug] sym=%u ts=%u rejected=signal_mismatch pyr_signal=%u desired=%u conf=%u\\n",
                                    sym, snap.t_sec, pyr_signal, desired_signal, sig_pyr.confidence
                                );
                            }
                            continue;
                        }
                        if (cfg.add_min_confidence > 0u && sig_pyr.confidence < cfg.add_min_confidence) {
                            if (pyr_debug_target) {
                                printf(
                                    "[gpu-pyr-debug] sym=%u ts=%u rejected=min_conf conf=%u min=%u\\n",
                                    sym, snap.t_sec, sig_pyr.confidence, cfg.add_min_confidence
                                );
                            }
                            continue;
                        }
                        double min_profit_atr = (double)cfg.add_min_profit_atr;
                        if ((double)snap.adx_slope > 0.75 && (double)snap.atr_slope <= 0.0) {
                            bool is_rsi_extreme =
                                (pos_after_exit.active == POS_LONG)
                                    ? ((double)snap.rsi > 65.0)
                                    : ((double)snap.rsi < 35.0);
                            if (!is_rsi_extreme) {
                                min_profit_atr *= 0.5;
                            }
                        }

                        double current_atr = apply_atr_floor(
                            (double)snap.atr,
                            (double)snap.close,
                            (double)cfg.min_atr_pct
                        );
                        if (!(current_atr > 0.0)) {
                            current_atr = (pos_after_exit.entry_atr > 0.0f)
                                ? (double)pos_after_exit.entry_atr
                                : ((double)pos_after_exit.entry_price * 0.005);
                        }
                        if (!(current_atr > 0.0)) {
                            if (pyr_debug_target) {
                                printf(
                                    "[gpu-pyr-debug] sym=%u ts=%u rejected=invalid_atr atr=%.12f entry_atr=%.12f entry_price=%.12f\\n",
                                    sym, snap.t_sec, (double)snap.atr,
                                    (double)pos_after_exit.entry_atr, (double)pos_after_exit.entry_price
                                );
                            }
                            continue;
                        }

                        double p_atr_pyr =
                            (pos_after_exit.active == POS_LONG)
                                ? (((double)snap.close - (double)pos_after_exit.entry_price) / current_atr)
                                : (((double)pos_after_exit.entry_price - (double)snap.close) / current_atr);
                        if (!isfinite(p_atr_pyr)) {
                            p_atr_pyr = 0.0;
                        }
                        if (p_atr_pyr >= min_profit_atr) {
                            long long elapsed_sec =
                                (long long)snap.t_sec - (long long)pos_after_exit.last_add_time_sec;
                            long long min_add_cooldown_sec =
                                (long long)cfg.add_cooldown_minutes * 60ll;
                            if (elapsed_sec >= min_add_cooldown_sec) {
                                // CPU parity: try_pyramid uses balance-only equity approximation.
                                double equity = state.balance;
                                if (equity < 0.0) { equity = 0.0; }
                                double base_margin = equity * (double)cfg.allocation_pct;
                                double add_margin = base_margin * (double)cfg.add_fraction_of_base_margin;

                                // CPU parity: margin-cap guard for adds
                                if (cfg.max_total_margin_pct > 0.0f) {
                                    double max_margin_pct = (double)cfg.max_total_margin_pct;
                                    double total_margin = 0.0;
                                    for (unsigned int m = 0u; m < ns; m++) {
                                        if (state.positions[m].active != POS_EMPTY) {
                                            total_margin += (double)state.positions[m].margin_used;
                                        }
                                    }
                                    double max_margin = equity * max_margin_pct;
                                    if ((total_margin + add_margin) > max_margin) {
                                        if (pyr_debug_target) {
                                            printf(
                                                "[gpu-pyr-debug] sym=%u ts=%u rejected=margin_cap total_margin=%.12f add_margin=%.12f max_margin=%.12f equity=%.12f\\n",
                                                sym, snap.t_sec, total_margin, add_margin, max_margin, equity
                                            );
                                        }
                                        continue;
                                    }
                                }

                                double lev = (double)pos_after_exit.leverage;
                                double add_notional = add_margin * lev;
                                double add_size = add_notional / main_market_close;

                                if (add_notional < cfg.min_notional_usd) {
                                    if (cfg.bump_to_min_notional != 0u && main_market_close > 0.0) {
                                        add_notional = (double)cfg.min_notional_usd;
                                        add_size = add_notional / main_market_close;
                                    } else {
                                        if (pyr_debug_target) {
                                            printf(
                                                "[gpu-pyr-debug] sym=%u ts=%u rejected=min_notional add_notional=%.12f min=%.12f\\n",
                                                sym, snap.t_sec, add_notional, (double)cfg.min_notional_usd
                                            );
                                        }
                                        continue;
                                    }
                                }
                                double kernel_lev = (lev > 1.0) ? lev : 1.0;
                                double kernel_add_notional = clamp_kernel_notional(add_notional);
                                double kernel_margin_add = quantize12(kernel_add_notional / kernel_lev);
                                double add_fee = quantize12(kernel_add_notional * (double)fee_rate);
                                if (kernel_margin_add + add_fee > state.kernel_cash) {
                                    if (pyr_debug_target) {
                                        printf(
                                            "[gpu-pyr-debug] sym=%u ts=%u rejected=insufficient_cash add_notional=%.12f kernel_add_notional=%.12f kernel_margin_add=%.12f kernel_cash=%.12f fee=%.12f\\n",
                                            sym, snap.t_sec, add_notional, kernel_add_notional, kernel_margin_add, state.kernel_cash, add_fee
                                        );
                                    }
                                    continue;
                                }
                                if (pyr_debug_target) {
                                    printf(
                                        "[gpu-pyr-debug] sym=%u ts=%u accepted add_notional=%.12f add_size=%.12f add_margin=%.12f p_atr=%.12f elapsed_sec=%lld\\n",
                                        sym, snap.t_sec, add_notional, add_size, add_margin, p_atr_pyr, elapsed_sec
                                    );
                                }

                                double fee = quantize12((double)add_notional * (double)fee_rate);
                                state.balance -= fee;
                                state.kernel_cash =
                                    quantize12(state.kernel_cash - (kernel_margin_add + add_fee));
                                state.total_fees += fee;

                                double old_size = pos_after_exit.size;
                                double new_size = old_size + add_size;
                                float add_slip = (pos_after_exit.active == POS_LONG) ? cfg.slippage_bps : -cfg.slippage_bps;
                                double add_fill_price = quantize12(
                                    main_market_close * (1.0 + (double)add_slip / 10000.0));
                                double new_entry =
                                    (pos_after_exit.entry_price * old_size + (add_fill_price * add_size))
                                    / new_size;
                                state.positions[sym].entry_price = new_entry;
                                state.positions[sym].size = new_size;
                                state.positions[sym].margin_used =
                                    state.positions[sym].margin_used + add_margin;
                                state.positions[sym].kernel_margin_used =
                                    quantize12(state.positions[sym].kernel_margin_used + kernel_margin_add);
                                state.positions[sym].adds_count += 1u;
                                state.positions[sym].last_add_time_sec = snap.t_sec;
                                state.last_entry_attempt_sec[sym] = snap.t_sec;
                                trace_record(
                                    &state,
                                    sym,
                                    snap.t_sec,
                                    TRACE_KIND_ADD,
                                    pos_after_exit.active,
                                    TRACE_REASON_PYRAMID,
                                    (float)add_fill_price,
                                    (float)add_size,
                                    0.0f
                                );
                            }
                            else if (pyr_debug_target) {
                                printf(
                                    "[gpu-pyr-debug] sym=%u ts=%u rejected=add_cooldown elapsed_sec=%lld min_sec=%lld\\n",
                                    sym, snap.t_sec, elapsed_sec, min_add_cooldown_sec
                                );
                            }
                        }
                        else if (pyr_debug_target) {
                            printf(
                                "[gpu-pyr-debug] sym=%u ts=%u rejected=min_profit_atr profit_atr=%.12f min=%.12f atr=%.12f adx_slope=%.12f atr_slope=%.12f rsi=%.12f\\n",
                                sym, snap.t_sec, p_atr_pyr, min_profit_atr, current_atr,
                                (double)snap.adx_slope, (double)snap.atr_slope, (double)snap.rsi
                            );
                        }
                    }
                    else if (pyr_debug_target) {
                        printf(
                            "[gpu-pyr-debug] sym=%u ts=%u rejected=max_adds adds=%u max=%u\\n",
                            sym, snap.t_sec, pos_after_exit.adds_count, cfg.max_adds_per_symbol
                        );
                    }
                }
            }

            // == Phase 2: Entry collection ===================================
            EntryCandidate candidates[MAX_CANDIDATES];
            unsigned int num_cands = 0u;

            for (unsigned int sym = 0u; sym < ns; sym++) {
                if (num_cands >= MAX_CANDIDATES) { break; }

                const GpuSnapshot& snap = snapshots[cfg.snapshot_offset + bar * ns + sym];
                if (snap.valid == 0u) { continue; }
                const bool debug_target = false;

                const GpuPosition& pos = state.positions[sym];

                if (pos.active != POS_EMPTY) {
                    if (debug_target) {
                        printf(
                            "[gpu-cand-debug] sym=%u ts=%u rejected=already_open pos_active=%u\\n",
                            sym, snap.t_sec, pos.active
                        );
                    }
                    continue;
                }
                if (is_entry_cooldown_active(&state, sym, snap.t_sec, &cfg)) {
                    if (debug_target) {
                        printf("[gpu-cand-debug] sym=%u ts=%u rejected=cooldown\\n", sym, snap.t_sec);
                    }
                    continue;
                }

                // AQC-1213: gates and signal now use codegen (double precision)
                bool is_btc_symbol = (sym == params->btc_sym_idx);
                GateResult gates = check_gates(snap, &cfg, snap.ema_slow_slope_pct,
                                                btc_bull, is_btc_symbol);
                SignalResultLegacy sig_result = generate_signal(
                    snap,
                    &cfg,
                    gates,
                    btc_bull,
                    is_btc_symbol,
                    snap.ema_slow_slope_pct
                );
                unsigned int signal = sig_result.signal;
                unsigned int confidence = sig_result.confidence;
                double entry_adx_thresh = sig_result.entry_adx_threshold;

                if (signal == SIG_NEUTRAL) {
                    if (debug_target) {
                        printf(
                            "[gpu-cand-debug] sym=%u ts=%u rejected=neutral_raw conf=%u breadth=%.6f btc=%u adx=%.6f adx_s=%.6f macd=%.10f rsi=%.6f\\n",
                            sym, snap.t_sec, confidence, breadth_pct, btc_bull,
                            snap.adx, snap.adx_slope, snap.macd_hist, snap.rsi
                        );
                    }
                    continue;
                }

                double atr = apply_atr_floor((double)snap.atr, (double)snap.close, (double)cfg.min_atr_pct);

                signal = apply_reverse(signal, &cfg, breadth_pct);
                if (signal == SIG_NEUTRAL) {
                    if (debug_target) {
                        printf(
                            "[gpu-cand-debug] sym=%u ts=%u rejected=neutral_after_reverse breadth=%.6f\\n",
                            sym, snap.t_sec, breadth_pct
                        );
                    }
                    continue;
                }
                signal = apply_regime_filter(signal, &cfg, breadth_pct);
                if (signal == SIG_NEUTRAL) {
                    if (debug_target) {
                        printf(
                            "[gpu-cand-debug] sym=%u ts=%u rejected=neutral_after_regime breadth=%.6f\\n",
                            sym, snap.t_sec, breadth_pct
                        );
                    }
                    continue;
                }

                if (!conf_meets_min(confidence, cfg.entry_min_confidence)) {
                    if (debug_target) {
                        printf(
                            "[gpu-cand-debug] sym=%u ts=%u rejected=min_conf conf=%u min=%u\\n",
                            sym, snap.t_sec, confidence, cfg.entry_min_confidence
                        );
                    }
                    continue;
                }

                unsigned int desired_type = (signal == SIG_BUY) ? POS_LONG : POS_SHORT;
                bool pesc_blocked = is_pesc_blocked(&state, sym, desired_type, snap.t_sec, snap.adx, &cfg);
                if (pesc_blocked) {
                    if (debug_target) {
                        printf(
                            "[gpu-cand-debug] sym=%u ts=%u rejected=pesc desired=%u adx=%.6f\\n",
                            sym, snap.t_sec, desired_type, snap.adx
                        );
                    }
                    continue;
                }

                if (cfg.enable_ssf_filter != 0u) {
                    if (signal == SIG_BUY && snap.macd_hist <= 0.0f) {
                        if (debug_target) {
                            printf(
                                "[gpu-cand-debug] sym=%u ts=%u rejected=ssf_buy macd=%.10f\\n",
                                sym, snap.t_sec, snap.macd_hist
                            );
                        }
                        continue;
                    }
                    if (signal == SIG_SELL && snap.macd_hist >= 0.0f) {
                        if (debug_target) {
                            printf(
                                "[gpu-cand-debug] sym=%u ts=%u rejected=ssf_sell macd=%.10f\\n",
                                sym, snap.t_sec, snap.macd_hist
                            );
                        }
                        continue;
                    }
                }

                if (cfg.enable_reef_filter != 0u) {
                    if (signal == SIG_BUY) {
                        if (snap.adx < cfg.reef_adx_threshold) {
                            if (snap.rsi > cfg.reef_long_rsi_block_gt) { continue; }
                        } else {
                            if (snap.rsi > cfg.reef_long_rsi_extreme_gt) { continue; }
                        }
                    }
                    if (signal == SIG_SELL) {
                        if (snap.adx < cfg.reef_adx_threshold) {
                            if (snap.rsi < cfg.reef_short_rsi_block_lt) { continue; }
                        } else {
                            if (snap.rsi < cfg.reef_short_rsi_extreme_lt) { continue; }
                        }
                    }
                }
                if (cfg.enable_reef_filter != 0u && debug_target) {
                    printf(
                        "[gpu-cand-debug] sym=%u ts=%u reef_pass signal=%u adx=%.6f rsi=%.6f reef_adx=%.6f\\n",
                        sym, snap.t_sec, signal, snap.adx, snap.rsi, cfg.reef_adx_threshold
                    );
                }

                int score = (int)(confidence) * 100 + (int)(snap.adx);

                EntryCandidate cand;
                cand.sym_idx = sym;
                cand.signal = signal;
                cand.confidence = confidence;
                cand.score = score;
                cand.adx = snap.adx;
                cand.atr = atr;
                cand.entry_adx_threshold = entry_adx_thresh;
                candidates[num_cands] = cand;
                num_cands += 1u;
                if (debug_target) {
                    printf(
                        "[gpu-cand-debug] sym=%u ts=%u accepted signal=%u conf=%u score=%d adx=%.6f atr=%.10f entry_adx=%.6f breadth=%.6f btc=%u\\n",
                        sym, snap.t_sec, signal, confidence, score, snap.adx, atr,
                        entry_adx_thresh, breadth_pct, btc_bull
                    );
                }
            }

            // == Phase 3: Rank candidates ====================================
            for (unsigned int i = 1u; i < num_cands; i++) {
                EntryCandidate key = candidates[i];
                unsigned int j = i;
                while (j > 0u
                       && (candidates[j - 1u].score < key.score
                           || (candidates[j - 1u].score == key.score
                               && candidates[j - 1u].sym_idx > key.sym_idx))) {
                    candidates[j] = candidates[j - 1u];
                    j -= 1u;
                }
                candidates[j] = key;
            }

            // == Phase 4: Execute ranked entries =============================
            // Compute equity = balance + unrealized PnL (mirrors CPU engine.rs:1094-1095)
            double main_entry_equity = state.balance;
            for (unsigned int eq_s3 = 0u; eq_s3 < ns; eq_s3++) {
                if (state.positions[eq_s3].active != POS_EMPTY) {
                    const GpuSnapshot& eq_snap3 = snapshots[cfg.snapshot_offset + bar * ns + eq_s3];
                    // CPU parity: unrealised PnL marks to the latest known close even if
                    // the current (bar, symbol) candle is missing.
                    double eq_close3 = resolve_main_close(main_candles, bar, ns, eq_s3, eq_snap3);
                    main_entry_equity += profit_usd(state.positions[eq_s3], eq_close3);
                }
            }
            if (main_entry_equity < 0.0) { main_entry_equity = 0.0; }

            for (unsigned int i = 0u; i < num_cands; i++) {
                if (state.entries_this_bar >= cfg.max_entry_orders_per_loop) { break; }
                if (state.num_open >= cfg.max_open_positions) { break; }

                const EntryCandidate& cand = candidates[i];
                const GpuSnapshot& snap = snapshots[cfg.snapshot_offset + bar * ns + cand.sym_idx];
                double entry_close = resolve_main_close(main_candles, bar, ns, cand.sym_idx, snap);

                double total_margin = 0.0;
                for (unsigned int s = 0u; s < ns; s++) {
                    if (state.positions[s].active != POS_EMPTY) {
                        total_margin += (double)state.positions[s].margin_used;
                    }
                }
                double max_margin_pct = (double)cfg.max_total_margin_pct;
                double headroom = main_entry_equity * max_margin_pct - total_margin;
                if (headroom <= 0.0) { continue; }

                SizingResult sizing = compute_entry_size(main_entry_equity, entry_close, cand.confidence,
                                                         cand.atr, snap, &cfg);
                double size = sizing.size;
                double margin = sizing.margin;
                double lev = sizing.leverage;

                if (false) {
                    printf(
                        "[gpu-entry-debug] sym=%u ts=%u equity=%.12f total_margin=%.12f headroom=%.12f "
                        "price=%.12f atr=%.12f adx=%.12f conf=%u size_pre=%.12f margin_pre=%.12f lev=%.12f\\n",
                        cand.sym_idx,
                        snap.t_sec,
                        main_entry_equity,
                        total_margin,
                        headroom,
                        (double)snap.close,
                        (double)cand.atr,
                        (double)snap.adx,
                        cand.confidence,
                        size,
                        margin,
                        lev
                    );
                }
                if (false) {
                    printf(
                        "[gpu-entry2-debug] sym=%u ts=%u equity=%.12f total_margin=%.12f headroom=%.12f price=%.12f atr=%.12f adx=%.12f conf=%u size_pre=%.12f margin_pre=%.12f lev=%.12f\\n",
                        cand.sym_idx,
                        snap.t_sec,
                        main_entry_equity,
                        total_margin,
                        headroom,
                        (double)snap.close,
                        (double)cand.atr,
                        (double)snap.adx,
                        cand.confidence,
                        size,
                        margin,
                        lev
                    );
                }

                if (margin > headroom) {
                    double ratio = headroom / margin;
                    size *= ratio;
                    margin = headroom;
                    if (false) {
                        printf(
                            "[gpu-entry2-debug] sym=%u ts=%u scaled ratio=%.12f size=%.12f margin=%.12f\\n",
                            cand.sym_idx, snap.t_sec, ratio, size, margin
                        );
                    }
                }

                double notional = size * entry_close;
                if (notional < cfg.min_notional_usd) {
                    if (cfg.bump_to_min_notional != 0u && entry_close > 0.0) {
                        size = (double)cfg.min_notional_usd / entry_close;
                        margin = size * entry_close / lev;
                        notional = size * entry_close;
                        if (margin > headroom) {
                            if (false) {
                                printf(
                                    "[gpu-entry2-debug] sym=%u ts=%u reject_after_bump margin=%.12f headroom=%.12f\\n",
                                    cand.sym_idx, snap.t_sec, margin, headroom
                                );
                            }
                            continue;
                        }
                        if (false) {
                            printf(
                                "[gpu-entry2-debug] sym=%u ts=%u bump_to_min_notional size=%.12f margin=%.12f notional=%.12f min=%.12f\\n",
                                cand.sym_idx, snap.t_sec, size, margin, notional, (double)cfg.min_notional_usd
                            );
                        }
                    } else {
                        continue;
                    }
                }

                // CPU parity (decision kernel): require kernel cash >= margin + fee,
                // where margin is computed using per-trade leverage (lev) from sizing.
                double kernel_lev = (lev > 1.0) ? lev : 1.0;
                double kernel_notional = clamp_kernel_notional(notional);
                double kernel_margin_req = quantize12(kernel_notional / kernel_lev);
                double open_fee = quantize12(kernel_notional * (double)fee_rate);
                if (kernel_margin_req + open_fee > state.kernel_cash) {
                    continue;
                }

                float slip = (cand.signal == SIG_BUY) ? cfg.slippage_bps : -cfg.slippage_bps;
                double fill_price = quantize12(
                    entry_close * (1.0 + (double)slip / 10000.0));
                double fee = quantize12((double)notional * (double)fee_rate);
                state.balance -= fee;
                state.kernel_cash = quantize12(state.kernel_cash - (kernel_margin_req + open_fee));
                state.total_fees += fee;

                GpuPosition new_pos;
                new_pos.active = (cand.signal == SIG_BUY) ? POS_LONG : POS_SHORT;
                new_pos._pad0 = 0u;
                new_pos.entry_price = fill_price;
                new_pos.size = size;
                new_pos.confidence = cand.confidence;
                new_pos._pad1 = 0u;
                new_pos.entry_atr = cand.atr;
                new_pos.entry_adx_threshold = cand.entry_adx_threshold;
                new_pos.trailing_sl = 0.0;
                new_pos.leverage = lev;
                new_pos.margin_used = margin;
                new_pos.adds_count = 0u;
                new_pos.tp1_taken = 0u;
                new_pos.open_time_sec = snap.t_sec;
                new_pos.last_add_time_sec = snap.t_sec;
                new_pos.kernel_margin_used = kernel_margin_req;
                state.positions[cand.sym_idx] = new_pos;
                state.last_entry_attempt_sec[cand.sym_idx] = snap.t_sec;

                state.num_open += 1u;
                state.entries_this_bar += 1u;
                trace_record(
                    &state,
                    cand.sym_idx,
                    snap.t_sec,
                    TRACE_KIND_OPEN,
                    new_pos.active,
                    TRACE_REASON_ENTRY,
                    (float)fill_price,
                    (float)size,
                    0.0f
                );
            }
        } // end if/else max_sub

        // == Funding settlements at hourly boundaries (CPU parity) ===============
        if (params->funding_enabled != 0u) {
            unsigned long long funding_base = (unsigned long long)bar * (unsigned long long)ns;
            for (unsigned int sym = 0u; sym < ns; sym++) {
                GpuPosition& pos = state.positions[sym];
                if (pos.active == POS_EMPTY) { continue; }

                unsigned long long slot = funding_base + (unsigned long long)sym;
                GpuFundingSpan span = funding_spans[slot];
                if (span.len == 0u) { continue; }

                double mark_price = resolve_mark_price_for_funding(
                    main_candles,
                    snapshots,
                    &cfg,
                    bar,
                    ns,
                    sym,
                    (double)pos.entry_price
                );

                bool is_long = (pos.active == POS_LONG);
                unsigned int funding_t_sec = snapshots[cfg.snapshot_offset + bar * ns + sym].t_sec;
                for (unsigned int k = 0u; k < span.len; k++) {
                    double rate = funding_rates[span.offset + k];
                    double delta = funding_delta((double)pos.size, is_long, mark_price, rate);
                    state.balance += delta;
                    trace_record(
                        &state,
                        sym,
                        funding_t_sec,
                        TRACE_KIND_FUNDING,
                        0u,
                        TRACE_REASON_FUNDING,
                        (float)mark_price,
                        (float)pos.size,
                        delta
                    );
                }
            }
        }

        // == Drawdown tracking (double precision) ==================================
        // CPU report parity: max drawdown is computed from realised equity curve
        // (`state.balance`) rather than mark-to-market open-position valuation.
        double equity = state.balance;
        if (equity > state.peak_equity) { state.peak_equity = equity; }
        if (state.peak_equity > 0.0) {
            double dd = (state.peak_equity - equity) / state.peak_equity;
            if (dd > state.max_drawdown) { state.max_drawdown = dd; }
        }
    }

    // Force-close any residual open positions at the scoped terminal trade bar.
    // Mirrors CPU backtester behaviour ("End of Backtest" closes at to_ts end).
    if (params->chunk_end >= params->trade_end_bar && params->num_bars > 0u) {
        unsigned int final_bar = params->trade_end_bar - 1u;
        unsigned int terminal_t_sec = 0u;
        for (unsigned int ts = 0u; ts < ns; ts++) {
            const GpuRawCandle& term_mc = main_candles[final_bar * ns + ts];
            if (term_mc.t_sec != 0u) {
                terminal_t_sec = term_mc.t_sec;
                break;
            }
        }
        for (unsigned int s = 0u; s < ns; s++) {
            if (state.positions[s].active == POS_EMPTY) { continue; }
            unsigned int close_bar = final_bar;
            bool found_close = false;
            double final_market_close = 0.0;
            while (true) {
                const GpuSnapshot& probe_snap = snapshots[cfg.snapshot_offset + close_bar * ns + s];
                double probe_close = resolve_main_close(main_candles, close_bar, ns, s, probe_snap);
                if (isfinite(probe_close) && probe_close > 0.0) {
                    final_market_close = probe_close;
                    found_close = true;
                    break;
                }
                if (close_bar == 0u) { break; }
                close_bar -= 1u;
            }
            if (!found_close) { continue; }
            const GpuSnapshot& final_snap = snapshots[cfg.snapshot_offset + close_bar * ns + s];
            GpuSnapshot close_snap = final_snap;
            close_snap.t_sec = (terminal_t_sec != 0u) ? terminal_t_sec : final_snap.t_sec;
            apply_close(&state, s, close_snap, final_market_close, TRACE_REASON_EXIT_EOB, fee_rate, cfg.slippage_bps);
        }
    }

    // Write back state
    states[combo_id] = state;

    // Pack result (on last chunk)
    if (params->chunk_end >= params->trade_end_bar) {
        unsigned int total_losses = (state.total_trades >= state.total_wins)
                                    ? (state.total_trades - state.total_wins)
                                    : 0u;
        GpuResult res;
        res.final_balance = state.balance;
        // CPU report semantics: total_pnl = final_balance - initial_balance
        // (includes realised PnL, fees, and funding settlements).
        res.total_pnl = state.balance - (double)__uint_as_float(params->initial_balance_bits);
        res.total_fees = state.total_fees;
        res.total_trades = state.total_trades;
        res.total_wins = state.total_wins;
        res.total_losses = total_losses;
        res._pad0 = 0u;
        res.gross_profit = state.gross_profit;
        res.gross_loss = state.gross_loss;
        res.max_drawdown_pct = state.max_drawdown;
        results[combo_id] = res;
    }
}
