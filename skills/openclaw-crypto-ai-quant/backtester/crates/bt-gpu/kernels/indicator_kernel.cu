// =============================================================================
// GPU Indicator Computation + Market Breadth Kernel
// =============================================================================
//
// Ports all 17 indicators from bt-core/src/indicators/ to CUDA.
// Each thread computes indicators for one (indicator_combo, symbol) pair
// across all bars. Output: GpuSnapshot buffer in VRAM (same layout as
// CPU precompute, consumed by sweep_engine kernel).
//
// Also includes breadth_kernel: reduces across symbols to compute
// market breadth % and BTC bullish flag per (indicator_combo, bar).

#include <cstdint>
#include <cfloat>
#include <cmath>

// -- Constants ----------------------------------------------------------------

#define MAX_RING 256u   // max rolling window size (covers all practical configs)
#define MAX_SYMBOLS 52u
#define BTC_BULL_UNKNOWN 2u

// -- Structs (match Rust #[repr(C)] exactly) ----------------------------------

struct GpuRawCandle {
    double open;  double high;  double low;  double close;
    double volume;  unsigned int t_sec;
    unsigned int _pad[3];
};

struct GpuIndicatorConfig {
    unsigned int ema_fast_window;
    unsigned int ema_slow_window;
    unsigned int ema_macro_window;
    unsigned int adx_window;
    unsigned int bb_window;
    unsigned int bb_width_avg_window;
    unsigned int atr_window;
    unsigned int rsi_window;
    unsigned int vol_sma_window;
    unsigned int vol_trend_window;
    unsigned int stoch_rsi_window;
    unsigned int stoch_rsi_smooth1;
    unsigned int stoch_rsi_smooth2;
    unsigned int avg_atr_window;
    unsigned int slow_drift_slope_window;
    unsigned int lookback;
    unsigned int use_stoch_rsi;
    unsigned int _pad[3];
};

struct IndicatorParams {
    unsigned int num_ind_combos;
    unsigned int num_symbols;
    unsigned int num_bars;
    unsigned int btc_sym_idx;
    unsigned int _pad[4];
};

struct __align__(16) GpuSnapshot {
    float close;  float high;  float low;  float open;
    float volume;  unsigned int t_sec;
    float ema_fast;  float ema_slow;  float ema_macro;
    float adx;  float adx_slope;  float adx_pos;  float adx_neg;
    float atr;  float atr_slope;  float avg_atr;
    float bb_upper;  float bb_lower;  float bb_width;  float bb_width_ratio;
    float rsi;  float stoch_k;  float stoch_d;
    float macd_hist;  float prev_macd_hist;  float prev2_macd_hist;  float prev3_macd_hist;
    float vol_sma;  unsigned int vol_trend;
    float prev_close;  float prev_ema_fast;  float prev_ema_slow;
    float ema_slow_slope_pct;
    unsigned int bar_count;  unsigned int valid;
    float funding_rate;
    unsigned int _pad[4];
};

// -- Ring buffer helpers (operate on thread-local arrays) ---------------------

__device__ void ring_push(float* buf, unsigned int& pos, unsigned int& len, unsigned int cap, float val) {
    buf[pos] = val;
    pos = (pos + 1) % cap;
    if (len < cap) len++;
}

__device__ float ring_mean(const float* buf, unsigned int pos, unsigned int len, unsigned int cap) {
    if (len == 0) return 0.0f;
    double sum = 0.0;
    unsigned int start = (len < cap) ? 0 : pos;
    for (unsigned int i = 0; i < len; i++) {
        sum += (double)buf[(start + i) % cap];
    }
    return (float)(sum / (double)len);
}

__device__ float ring_std_pop(const float* buf, unsigned int pos, unsigned int len, unsigned int cap) {
    if (len == 0) return 0.0f;
    float mean_f = ring_mean(buf, pos, len, cap);
    double mean = (double)mean_f;
    double var_sum = 0.0;
    unsigned int start = (len < cap) ? 0 : pos;
    for (unsigned int i = 0; i < len; i++) {
        float v = buf[(start + i) % cap];
        double d = (double)v - mean;
        var_sum += d * d;
    }
    return sqrtf((float)(var_sum / (double)len));
}

__device__ float ring_min(const float* buf, unsigned int pos, unsigned int len, unsigned int cap) {
    if (len == 0) return 0.0f;
    float result = FLT_MAX;
    unsigned int start = (len < cap) ? 0 : pos;
    for (unsigned int i = 0; i < len; i++) {
        float v = buf[(start + i) % cap];
        if (v < result) result = v;
    }
    return result;
}

__device__ float ring_max(const float* buf, unsigned int pos, unsigned int len, unsigned int cap) {
    if (len == 0) return 0.0f;
    float result = -FLT_MAX;
    unsigned int start = (len < cap) ? 0 : pos;
    for (unsigned int i = 0; i < len; i++) {
        float v = buf[(start + i) % cap];
        if (v > result) result = v;
    }
    return result;
}

// Access element at index from oldest (0) to newest (len-1)
__device__ float ring_at(const float* buf, unsigned int pos, unsigned int len, unsigned int cap, unsigned int idx) {
    unsigned int start = (len < cap) ? 0 : pos;
    return buf[(start + idx) % cap];
}

// =============================================================================
// Indicator Kernel
// =============================================================================
//
// Grid: ceil((num_ind_combos * num_symbols) / block_size)
// Each thread: one (ind_combo, symbol) pair → iterate all bars
//
// Output: snapshots[ind_idx * num_bars * num_symbols + bar * num_symbols + sym]

extern "C"
__global__ void indicator_kernel(
    const IndicatorParams* params,
    const GpuIndicatorConfig* ind_configs,
    const GpuRawCandle* candles,     // [num_bars * num_symbols]
    GpuSnapshot* snapshots           // [num_ind_combos * num_bars * num_symbols]
) {
    unsigned int tid = blockIdx.x * blockDim.x + threadIdx.x;
    unsigned int total_threads = params->num_ind_combos * params->num_symbols;
    if (tid >= total_threads) return;

    unsigned int ind_idx = tid / params->num_symbols;
    unsigned int sym_idx = tid % params->num_symbols;
    unsigned int ns = params->num_symbols;
    unsigned int nb = params->num_bars;

    GpuIndicatorConfig cfg = ind_configs[ind_idx];
    unsigned int snap_base = ind_idx * nb * ns;

    // === EMA state ===
    double ema_fast_val = 0.0, ema_slow_val = 0.0, ema_macro_val = 0.0;
    double alpha_fast = 2.0 / ((double)cfg.ema_fast_window + 1.0);
    double alpha_slow = 2.0 / ((double)cfg.ema_slow_window + 1.0);
    double alpha_macro = 2.0 / ((double)cfg.ema_macro_window + 1.0);
    unsigned int ema_fast_count = 0, ema_slow_count = 0, ema_macro_count = 0;

    // === ADX state ===
    double adx_prev_high = 0.0, adx_prev_low = 0.0, adx_prev_close = 0.0;
    double sm_plus_dm = 0.0, sm_minus_dm = 0.0, sm_tr = 0.0;
    double adx_value = 0.0, adx_sum = 0.0;
    unsigned int adx_count = 0, adx_dx_count = 0;
    unsigned int adx_phase = 0; // 0=init, 1=accum, 2=dx_accum, 3=warm

    // === ATR state ===
    double atr_value = 0.0, atr_sum = 0.0;
    float atr_prev_close = 0.0f;
    unsigned int atr_count = 0;
    unsigned int atr_has_prev = 0, atr_warm = 0;

    // === RSI state ===
    float rsi_prev_close = 0.0f;
    double rsi_avg_gain = 0.0, rsi_avg_loss = 0.0;
    double rsi_gain_sum = 0.0, rsi_loss_sum = 0.0;
    float rsi_value = 50.0f;
    unsigned int rsi_count = 0;
    unsigned int rsi_has_prev = 0, rsi_warm = 0;

    // === BB ring ===
    float bb_ring[MAX_RING];
    unsigned int bb_pos = 0, bb_len = 0;
    unsigned int bb_cap = (cfg.bb_window < MAX_RING) ? cfg.bb_window : MAX_RING;

    // === BB width avg ring ===
    float bb_wavg_ring[MAX_RING];
    unsigned int bb_wavg_pos = 0, bb_wavg_len = 0;
    unsigned int bb_wavg_cap = (cfg.bb_width_avg_window < MAX_RING) ? cfg.bb_width_avg_window : MAX_RING;

    // === Avg ATR ring ===
    float avg_atr_ring[MAX_RING];
    unsigned int avg_atr_pos = 0, avg_atr_len = 0;
    unsigned int avg_atr_cap = (cfg.avg_atr_window < MAX_RING) ? cfg.avg_atr_window : MAX_RING;

    // === MACD state (fixed 12/26/9) ===
    double macd_fast_val = 0.0, macd_slow_val = 0.0, macd_signal_val = 0.0;
    double macd_alpha_fast = 2.0 / 13.0;    // EMA(12)
    double macd_alpha_slow = 2.0 / 27.0;    // EMA(26)
    double macd_alpha_signal = 2.0 / 10.0;  // EMA(9)
    unsigned int macd_count = 0;

    // === Stoch RSI state ===
    float stoch_rsi_ring[MAX_RING];
    unsigned int stoch_rsi_pos = 0, stoch_rsi_len = 0;
    unsigned int stoch_rsi_cap = (cfg.stoch_rsi_window < MAX_RING) ? cfg.stoch_rsi_window : MAX_RING;
    float stoch_k_ring[MAX_RING];
    unsigned int stoch_k_pos = 0, stoch_k_len = 0;
    unsigned int stoch_k_cap = (cfg.stoch_rsi_smooth1 < MAX_RING) ? cfg.stoch_rsi_smooth1 : MAX_RING;
    float stoch_d_ring[MAX_RING];
    unsigned int stoch_d_pos = 0, stoch_d_len = 0;
    unsigned int stoch_d_cap = (cfg.stoch_rsi_smooth2 < MAX_RING) ? cfg.stoch_rsi_smooth2 : MAX_RING;

    // === Volume SMA ring ===
    float vol_sma_ring[MAX_RING];
    unsigned int vol_sma_pos = 0, vol_sma_len = 0;
    unsigned int vol_sma_cap = (cfg.vol_sma_window < MAX_RING) ? cfg.vol_sma_window : MAX_RING;

    // === Volume Trend ring ===
    float vol_trend_ring[MAX_RING];
    unsigned int vol_trend_pos = 0, vol_trend_len = 0;
    unsigned int vol_trend_cap = (cfg.vol_trend_window < MAX_RING) ? cfg.vol_trend_window : MAX_RING;

    // === EMA slow slope history ===
    float ema_slow_hist[MAX_RING];
    unsigned int ema_slow_hist_pos = 0, ema_slow_hist_len = 0;
    unsigned int ema_slow_hist_cap = (cfg.slow_drift_slope_window < MAX_RING) ? cfg.slow_drift_slope_window : MAX_RING;

    // === Lagged values ===
    float prev_close = 0.0f, prev_adx = 0.0f, prev_atr = 0.0f;
    float prev_macd_hist = 0.0f, prev2_macd_hist = 0.0f, prev3_macd_hist = 0.0f;
    float prev_ema_fast = 0.0f, prev_ema_slow = 0.0f;
    unsigned int bar_count = 0;

    // === Main bar loop ===
    for (unsigned int bar = 0; bar < nb; bar++) {
        GpuRawCandle c = candles[bar * ns + sym_idx];
        unsigned int out_idx = snap_base + bar * ns + sym_idx;

        // No candle for this (bar, symbol)
        //
        // CPU semantics (bt-core): if a bar is missing, the IndicatorBank is NOT updated,
        // but its *state* (prev_close/prev_ema_*) remains available and is still used
        // for market breadth + BTC alignment and equity/unrealised PnL (via prev_close).
        //
        // For parity, emit a snapshot that:
        //   - has valid=0 (so the trade kernel skips symbol processing)
        //   - carries forward the last known indicator state + lagged values
        //   - preserves bar_count (do NOT reset to 0)
        //   - carries forward close as the last known close (used by equity marking)
        //
        // This prevents breadth/equity from spuriously dropping to zero on sparse symbols.
        if (c.close <= 0.0f) {
            GpuSnapshot snap;
            memset(&snap, 0, sizeof(GpuSnapshot));

            // Carry forward last known mark. Keep OHLC consistent.
            snap.close = prev_close;
            snap.high = prev_close;
            snap.low = prev_close;
            snap.open = prev_close;
            snap.volume = 0.0f;
            snap.t_sec = c.t_sec;

            // Carry forward indicator state (no update).
            snap.ema_fast = (float)ema_fast_val;
            snap.ema_slow = (float)ema_slow_val;
            snap.ema_macro = (float)ema_macro_val;
            snap.adx = prev_adx;
            snap.adx_slope = 0.0f;
            snap.adx_pos = 0.0f;
            snap.adx_neg = 0.0f;
            snap.atr = prev_atr;
            snap.atr_slope = 0.0f;
            snap.avg_atr = 0.0f;
            snap.bb_upper = 0.0f;
            snap.bb_lower = 0.0f;
            snap.bb_width = 0.0f;
            snap.bb_width_ratio = 0.0f;
            snap.rsi = 0.0f;
            snap.stoch_k = 0.0f;
            snap.stoch_d = 0.0f;
            snap.macd_hist = prev_macd_hist;
            snap.prev_macd_hist = prev_macd_hist;
            snap.prev2_macd_hist = prev2_macd_hist;
            snap.prev3_macd_hist = prev3_macd_hist;
            snap.vol_sma = 0.0f;
            snap.vol_trend = 0u;

            // Lagged fields (CPU uses these even on missing-bar timestamps).
            snap.prev_close = prev_close;
            snap.prev_ema_fast = prev_ema_fast;
            snap.prev_ema_slow = prev_ema_slow;
            snap.ema_slow_slope_pct = 0.0f;

            snap.bar_count = bar_count;
            snap.valid = 0u;
            snap.funding_rate = 0.0f;
            snap._pad[0] = 0;
            snap._pad[1] = 0;
            snap._pad[2] = 0;
            snap._pad[3] = 0;

            snapshots[out_idx] = snap;
            continue;
        }

        // ─── EMA ───────────────────────────────────────────────────────
        if (ema_fast_count == 0) { ema_fast_val = (double)c.close; }
        else { ema_fast_val = alpha_fast * (double)c.close + (1.0 - alpha_fast) * ema_fast_val; }
        ema_fast_count++;

        if (ema_slow_count == 0) { ema_slow_val = (double)c.close; }
        else { ema_slow_val = alpha_slow * (double)c.close + (1.0 - alpha_slow) * ema_slow_val; }
        ema_slow_count++;

        if (ema_macro_count == 0) { ema_macro_val = (double)c.close; }
        else { ema_macro_val = alpha_macro * (double)c.close + (1.0 - alpha_macro) * ema_macro_val; }
        ema_macro_count++;

        // ─── ADX (Wilder smoothing) ────────────────────────────────────
        float cur_adx = 0.0f, cur_adx_pos = 0.0f, cur_adx_neg = 0.0f;

        if (adx_phase == 0) {
            // Init: save first bar's HLC
            adx_prev_high = c.high;
            adx_prev_low = c.low;
            adx_prev_close = c.close;
            adx_phase = 1;
            adx_count = 0;
        } else if (adx_phase == 1) {
            // Accumulate: sum +DM, -DM, TR for window bars
            double up_move = c.high - adx_prev_high;
            double down_move = adx_prev_low - c.low;
            double plus_dm = (up_move > down_move && up_move > 0.0) ? up_move : 0.0;
            double minus_dm = (down_move > up_move && down_move > 0.0) ? down_move : 0.0;
            double tr = fmax(c.high - c.low, fmax(fabs(c.high - adx_prev_close), fabs(c.low - adx_prev_close)));

            sm_plus_dm += plus_dm;
            sm_minus_dm += minus_dm;
            sm_tr += tr;
            adx_count++;

            adx_prev_high = c.high;
            adx_prev_low = c.low;
            adx_prev_close = c.close;

            if (adx_count >= cfg.adx_window) {
                // Compute first DI/DX
                double di_pos = (sm_tr > 0.0) ? (sm_plus_dm / sm_tr * 100.0) : 0.0;
                double di_neg = (sm_tr > 0.0) ? (sm_minus_dm / sm_tr * 100.0) : 0.0;
                double di_sum = di_pos + di_neg;
                double dx = (di_sum > 0.0) ? (fabs(di_pos - di_neg) / di_sum * 100.0) : 0.0;
                cur_adx_pos = (float)di_pos;
                cur_adx_neg = (float)di_neg;
                cur_adx = (float)dx;
                adx_sum = dx;
                adx_dx_count = 1;
                adx_phase = 2;
            }
        } else if (adx_phase == 2) {
            // DX accumulate: Wilder smooth +DM/-DM/TR, accumulate DX
            double up_move = c.high - adx_prev_high;
            double down_move = adx_prev_low - c.low;
            double plus_dm = (up_move > down_move && up_move > 0.0) ? up_move : 0.0;
            double minus_dm = (down_move > up_move && down_move > 0.0) ? down_move : 0.0;
            double tr = fmax(c.high - c.low, fmax(fabs(c.high - adx_prev_close), fabs(c.low - adx_prev_close)));
            double w = (double)cfg.adx_window;
            sm_plus_dm = sm_plus_dm - sm_plus_dm / w + plus_dm;
            sm_minus_dm = sm_minus_dm - sm_minus_dm / w + minus_dm;
            sm_tr = sm_tr - sm_tr / w + tr;

            double di_pos = (sm_tr > 0.0) ? (sm_plus_dm / sm_tr * 100.0) : 0.0;
            double di_neg = (sm_tr > 0.0) ? (sm_minus_dm / sm_tr * 100.0) : 0.0;
            double di_sum = di_pos + di_neg;
            double dx = (di_sum > 0.0) ? (fabs(di_pos - di_neg) / di_sum * 100.0) : 0.0;

            adx_sum += dx;
            adx_dx_count++;
            cur_adx_pos = (float)di_pos;
            cur_adx_neg = (float)di_neg;

            adx_prev_high = c.high;
            adx_prev_low = c.low;
            adx_prev_close = c.close;

            if (adx_dx_count >= cfg.adx_window) {
                adx_value = adx_sum / w;
                cur_adx = (float)adx_value;
                adx_phase = 3;
            } else {
                cur_adx = (float)(adx_sum / (double)adx_dx_count);
            }
        } else { // adx_phase == 3 (warm)
            double up_move = c.high - adx_prev_high;
            double down_move = adx_prev_low - c.low;
            double plus_dm = (up_move > down_move && up_move > 0.0) ? up_move : 0.0;
            double minus_dm = (down_move > up_move && down_move > 0.0) ? down_move : 0.0;
            double tr = fmax(c.high - c.low, fmax(fabs(c.high - adx_prev_close), fabs(c.low - adx_prev_close)));
            double w = (double)cfg.adx_window;
            sm_plus_dm = sm_plus_dm - sm_plus_dm / w + plus_dm;
            sm_minus_dm = sm_minus_dm - sm_minus_dm / w + minus_dm;
            sm_tr = sm_tr - sm_tr / w + tr;

            double di_pos = (sm_tr > 0.0) ? (sm_plus_dm / sm_tr * 100.0) : 0.0;
            double di_neg = (sm_tr > 0.0) ? (sm_minus_dm / sm_tr * 100.0) : 0.0;
            double di_sum = di_pos + di_neg;
            double dx = (di_sum > 0.0) ? (fabs(di_pos - di_neg) / di_sum * 100.0) : 0.0;

            adx_value = (adx_value * (w - 1.0) + (double)dx) / w;
            cur_adx = (float)adx_value;
            cur_adx_pos = (float)di_pos;
            cur_adx_neg = (float)di_neg;

            adx_prev_high = c.high;
            adx_prev_low = c.low;
            adx_prev_close = c.close;
        }

        float adx_slope = cur_adx - prev_adx;

        // ─── ATR (Wilder smoothing) ────────────────────────────────────
        double tr_val;
        if (atr_has_prev == 0) {
            tr_val = (double)(c.high - c.low);
            atr_has_prev = 1;
        } else {
            tr_val = (double)fmaxf(c.high - c.low, fmaxf(fabsf(c.high - atr_prev_close), fabsf(c.low - atr_prev_close)));
        }
        atr_prev_close = c.close;

        if (atr_warm == 0) {
            atr_sum += tr_val;
            atr_count++;
            if (atr_count >= cfg.atr_window) {
                atr_value = atr_sum / (double)cfg.atr_window;
                atr_warm = 1;
            } else {
                atr_value = atr_sum / (double)atr_count;
            }
        } else {
            double w = (double)cfg.atr_window;
            atr_value = (atr_value * (w - 1.0) + tr_val) / w;
        }

        float atr_slope_val = (float)atr_value - prev_atr;

        // Avg ATR (rolling mean)
        ring_push(avg_atr_ring, avg_atr_pos, avg_atr_len, avg_atr_cap, (float)atr_value);
        float avg_atr_val = ring_mean(avg_atr_ring, avg_atr_pos, avg_atr_len, avg_atr_cap);

        // ─── RSI (Wilder smoothing) ────────────────────────────────────
        if (rsi_has_prev == 0) {
            rsi_prev_close = c.close;
            rsi_has_prev = 1;
            rsi_value = 50.0f;
        } else {
            float change = c.close - rsi_prev_close;
            float gain = (change > 0.0f) ? change : 0.0f;
            float loss = (change < 0.0f) ? -change : 0.0f;
            rsi_prev_close = c.close;

            if (rsi_warm == 0) {
                rsi_gain_sum += gain;
                rsi_loss_sum += loss;
                rsi_count++;
                if (rsi_count >= cfg.rsi_window) {
                    rsi_avg_gain = rsi_gain_sum / (double)cfg.rsi_window;
                    rsi_avg_loss = rsi_loss_sum / (double)cfg.rsi_window;
                    rsi_warm = 1;
                } else {
                    rsi_value = 50.0f;
                    goto rsi_done;
                }
            } else {
                double w = (double)cfg.rsi_window;
                rsi_avg_gain = (rsi_avg_gain * (w - 1.0) + (double)gain) / w;
                rsi_avg_loss = (rsi_avg_loss * (w - 1.0) + (double)loss) / w;
            }

            if (rsi_avg_loss == 0.0) {
                rsi_value = 100.0f;
            } else {
                double rs = rsi_avg_gain / rsi_avg_loss;
                rsi_value = (float)(100.0 - 100.0 / (1.0 + rs));
            }
        }
        rsi_done:

        // ─── Bollinger Bands ───────────────────────────────────────────
        ring_push(bb_ring, bb_pos, bb_len, bb_cap, c.close);
        float bb_middle, bb_upper, bb_lower;
        if (bb_len < bb_cap) {
            bb_middle = ring_mean(bb_ring, bb_pos, bb_len, bb_cap);
            bb_upper = bb_middle;
            bb_lower = bb_middle;
        } else {
            bb_middle = ring_mean(bb_ring, bb_pos, bb_len, bb_cap);
            float bb_std = ring_std_pop(bb_ring, bb_pos, bb_len, bb_cap);
            bb_upper = bb_middle + 2.0f * bb_std;
            bb_lower = bb_middle - 2.0f * bb_std;
        }

        // bb_width = (upper - lower) / close
        float bb_width = (c.close > 0.0f) ? ((bb_upper - bb_lower) / c.close) : 0.0f;

        // BB width avg
        ring_push(bb_wavg_ring, bb_wavg_pos, bb_wavg_len, bb_wavg_cap, bb_width);
        float bb_width_avg = ring_mean(bb_wavg_ring, bb_wavg_pos, bb_wavg_len, bb_wavg_cap);
        float bb_width_ratio = (bb_width_avg > 0.0f) ? (bb_width / bb_width_avg) : 1.0f;

        // ─── MACD (fixed 12/26/9) ─────────────────────────────────────
        float macd_hist_val;
        if (macd_count == 0) {
            macd_fast_val = (double)c.close;
            macd_slow_val = (double)c.close;
            double macd_line = 0.0;
            macd_signal_val = macd_line;
            macd_hist_val = 0.0f;
        } else {
            macd_fast_val = macd_alpha_fast * (double)c.close + (1.0 - macd_alpha_fast) * macd_fast_val;
            macd_slow_val = macd_alpha_slow * (double)c.close + (1.0 - macd_alpha_slow) * macd_slow_val;
            double macd_line = macd_fast_val - macd_slow_val;
            macd_signal_val = macd_alpha_signal * macd_line + (1.0 - macd_alpha_signal) * macd_signal_val;
            macd_hist_val = (float)(macd_line - macd_signal_val);
        }
        macd_count++;

        // ─── Stochastic RSI ───────────────────────────────────────────
        float stoch_k_val = 0.0f, stoch_d_val = 0.0f;
        if (cfg.use_stoch_rsi != 0) {
            ring_push(stoch_rsi_ring, stoch_rsi_pos, stoch_rsi_len, stoch_rsi_cap, rsi_value);
            if (stoch_rsi_len < stoch_rsi_cap) {
                stoch_k_val = 0.5f;
                stoch_d_val = 0.5f;
            } else {
                float min_rsi = ring_min(stoch_rsi_ring, stoch_rsi_pos, stoch_rsi_len, stoch_rsi_cap);
                float max_rsi = ring_max(stoch_rsi_ring, stoch_rsi_pos, stoch_rsi_len, stoch_rsi_cap);
                float range = max_rsi - min_rsi;
                float raw_k = (range > 0.0f) ? ((rsi_value - min_rsi) / range) : 0.5f;

                ring_push(stoch_k_ring, stoch_k_pos, stoch_k_len, stoch_k_cap, raw_k);
                stoch_k_val = ring_mean(stoch_k_ring, stoch_k_pos, stoch_k_len, stoch_k_cap);

                ring_push(stoch_d_ring, stoch_d_pos, stoch_d_len, stoch_d_cap, stoch_k_val);
                stoch_d_val = ring_mean(stoch_d_ring, stoch_d_pos, stoch_d_len, stoch_d_cap);
            }
        }

        // ─── Volume SMA ───────────────────────────────────────────────
        ring_push(vol_sma_ring, vol_sma_pos, vol_sma_len, vol_sma_cap, c.volume);
        float vol_sma_val = ring_mean(vol_sma_ring, vol_sma_pos, vol_sma_len, vol_sma_cap);

        // ─── Volume Trend ─────────────────────────────────────────────
        ring_push(vol_trend_ring, vol_trend_pos, vol_trend_len, vol_trend_cap, c.volume);
        float vol_short_sma = ring_mean(vol_trend_ring, vol_trend_pos, vol_trend_len, vol_trend_cap);
        unsigned int vol_trend_flag = (vol_short_sma > vol_sma_val) ? 1u : 0u;

        // ─── EMA slow slope ───────────────────────────────────────────
	        ring_push(
	            ema_slow_hist,
	            ema_slow_hist_pos,
	            ema_slow_hist_len,
	            ema_slow_hist_cap,
	            (float)ema_slow_val
	        );
        float ema_slow_slope_pct = 0.0f;
        if (ema_slow_hist_len >= cfg.slow_drift_slope_window && c.close > 0.0f) {
            // current = newest value (at len-1), past = oldest in window
            float current = ring_at(ema_slow_hist, ema_slow_hist_pos, ema_slow_hist_len, ema_slow_hist_cap, ema_slow_hist_len - 1);
            float past = ring_at(ema_slow_hist, ema_slow_hist_pos, ema_slow_hist_len, ema_slow_hist_cap, ema_slow_hist_len - cfg.slow_drift_slope_window);
            ema_slow_slope_pct = (current - past) / c.close;
        }

        // ─── Write GpuSnapshot ────────────────────────────────────────
        GpuSnapshot snap;
        snap.close = c.close;
        snap.high = c.high;
        snap.low = c.low;
        snap.open = c.open;
        snap.volume = c.volume;
        snap.t_sec = c.t_sec;
        snap.ema_fast = (float)ema_fast_val;
        snap.ema_slow = (float)ema_slow_val;
        snap.ema_macro = (float)ema_macro_val;
        snap.adx = cur_adx;
        snap.adx_slope = adx_slope;
        snap.adx_pos = cur_adx_pos;
        snap.adx_neg = cur_adx_neg;
        snap.atr = (float)atr_value;
        snap.atr_slope = atr_slope_val;
        snap.avg_atr = avg_atr_val;
        snap.bb_upper = bb_upper;
        snap.bb_lower = bb_lower;
        snap.bb_width = bb_width;
        snap.bb_width_ratio = bb_width_ratio;
        snap.rsi = rsi_value;
        snap.stoch_k = stoch_k_val;
        snap.stoch_d = stoch_d_val;
        snap.macd_hist = macd_hist_val;
        snap.prev_macd_hist = prev_macd_hist;
        snap.prev2_macd_hist = prev2_macd_hist;
        snap.prev3_macd_hist = prev3_macd_hist;
        snap.vol_sma = vol_sma_val;
        snap.vol_trend = vol_trend_flag;
        snap.prev_close = prev_close;
        snap.prev_ema_fast = prev_ema_fast;
        snap.prev_ema_slow = prev_ema_slow;
        snap.ema_slow_slope_pct = ema_slow_slope_pct;
        snap.bar_count = bar_count;
        snap.valid = (bar_count >= cfg.lookback) ? 1u : 0u;
        snap.funding_rate = 0.0f;
        snap._pad[0] = 0; snap._pad[1] = 0; snap._pad[2] = 0; snap._pad[3] = 0;

        snapshots[out_idx] = snap;

        // ─── Update lagged values ─────────────────────────────────────
        prev3_macd_hist = prev2_macd_hist;
        prev2_macd_hist = prev_macd_hist;
        prev_macd_hist = macd_hist_val;
        prev_adx = cur_adx;
        prev_atr = (float)atr_value;
        prev_close = c.close;
        prev_ema_fast = (float)ema_fast_val;
        prev_ema_slow = (float)ema_slow_val;
        bar_count++;
    }
}

// =============================================================================
// Breadth Kernel
// =============================================================================
//
// Grid: ceil((num_ind_combos * num_bars) / block_size)
// Each thread: one (ind_combo, bar) → reads all symbols, computes breadth + btc_bullish
//
// Output:
//   breadth[ind_idx * num_bars + bar] = market breadth %
//   btc_bullish[ind_idx * num_bars + bar] = 1 bullish, 0 bearish, 2 unavailable

extern "C"
__global__ void breadth_kernel(
    const IndicatorParams* params,
    const GpuSnapshot* snapshots,  // [num_ind_combos * num_bars * num_symbols]
    float* breadth,                // [num_ind_combos * num_bars]
    unsigned int* btc_bullish      // [num_ind_combos * num_bars]
) {
    unsigned int tid = blockIdx.x * blockDim.x + threadIdx.x;
    unsigned int total = params->num_ind_combos * params->num_bars;
    if (tid >= total) return;

    unsigned int ind_idx = tid / params->num_bars;
    unsigned int bar_idx = tid % params->num_bars;
    unsigned int ns = params->num_symbols;
    unsigned int snap_base = ind_idx * params->num_bars * ns;

    unsigned int bull_count = 0, total_count = 0;
    for (unsigned int sym = 0; sym < ns; sym++) {
        GpuSnapshot s = snapshots[snap_base + bar_idx * ns + sym];
        if (s.bar_count >= 2) {
            total_count++;
            if (s.prev_ema_fast > s.prev_ema_slow) {
                bull_count++;
            }
        }
    }

    unsigned int out_idx = ind_idx * params->num_bars + bar_idx;
    breadth[out_idx] = (total_count > 0) ? ((float)bull_count / (float)total_count * 100.0f) : 50.0f;

    // BTC bullish
    unsigned int btc_idx = params->btc_sym_idx;
    if (btc_idx < ns) {
        GpuSnapshot btc = snapshots[snap_base + bar_idx * ns + btc_idx];
        // CPU parity: bt-core::compute_btc_bullish returns Some(..) once bar_count > 0.
        if (btc.bar_count > 0) {
            btc_bullish[out_idx] = (btc.prev_close > btc.prev_ema_slow) ? 1u : 0u;
        } else {
            btc_bullish[out_idx] = BTC_BULL_UNKNOWN;
        }
    } else {
        btc_bullish[out_idx] = BTC_BULL_UNKNOWN;
    }
}
