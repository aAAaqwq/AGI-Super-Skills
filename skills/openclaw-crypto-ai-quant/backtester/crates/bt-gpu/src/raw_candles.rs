//! Raw candle preparation for GPU upload.
//!
//! Builds a flat `Vec<GpuRawCandle>` in [bar_idx × num_symbols + sym_idx] layout
//! from the CandleData HashMap. This is pure data layout — no indicator computation.
//! The resulting buffer is ~14 MB for 5000 bars × 51 symbols and is uploaded to GPU once.

use bt_core::candle::{CandleData, FundingRateData};
use bytemuck::Zeroable;
use rustc_hash::FxHashMap;

use crate::buffers::{GpuFundingSpan, GpuRawCandle};

/// Result of sub-bar candle preparation for GPU upload.
pub struct SubBarResult {
    /// Flat candle array: `candles[(bar_idx * max_sub + sub_idx) * num_symbols + sym_idx]`
    /// Missing slots have close=0.
    pub candles: Vec<GpuRawCandle>,
    /// Per (bar, symbol) count of packed sub-bar slots: `sub_counts[bar_idx * num_symbols + sym_idx]`.
    ///
    /// This is the per-bar union tick count (same value for every symbol). Symbols that have
    /// no candle for a given tick are padded with a zeroed `GpuRawCandle` (close=0).
    pub sub_counts: Vec<u32>,
    /// Maximum number of sub-bars per main bar (rectangle width).
    pub max_sub_per_bar: u32,
    /// Number of main bars.
    pub num_bars: usize,
    /// Number of symbols.
    pub num_symbols: usize,
}

/// Result of raw candle preparation.
pub struct RawCandleResult {
    /// Flat candle array: `candles[bar_idx * num_symbols + sym_idx]`
    /// Missing bars have close=0.
    pub candles: Vec<GpuRawCandle>,
    /// Number of unique timestamps (bars).
    pub num_bars: usize,
    /// Number of symbols.
    pub num_symbols: usize,
    /// Sorted unique timestamps (ms).
    pub timestamps: Vec<i64>,
}

/// Flat funding-event representation aligned to `(bar, symbol)` slots.
///
/// For each `(bar_idx, sym_idx)` pair, `spans[bar_idx * num_symbols + sym_idx]`
/// points into `rates`, which stores the funding rates for all hourly boundaries
/// crossed in that bar interval.
pub struct FundingEventBuffers {
    pub spans: Vec<GpuFundingSpan>,
    pub rates: Vec<f64>,
}

fn to_gpu_t_sec(ts_ms: i64) -> u32 {
    let ts_sec = (ts_ms / 1000).max(0);
    u32::try_from(ts_sec).unwrap_or(u32::MAX)
}

fn lookup_funding_rate(rates: &[(i64, f64)], target_ts: i64) -> Option<f64> {
    match rates.binary_search_by_key(&target_ts, |(t, _)| *t) {
        Ok(i) => Some(rates[i].1),
        Err(i) => {
            if i > 0 {
                Some(rates[i - 1].1)
            } else {
                None
            }
        }
    }
}

fn saturating_u32(value: usize, label: &str) -> u32 {
    match u32::try_from(value) {
        Ok(v) => v,
        Err(_) => {
            eprintln!(
                "[funding] {label}={value} exceeds u32::MAX; clamping to {}",
                u32::MAX
            );
            u32::MAX
        }
    }
}

/// Precompute funding settlements for GPU trade kernel parity with CPU engine.
///
/// CPU engine logic settles funding at every hourly boundary crossed between
/// `prev_ts` (exclusive) and `ts` (inclusive). This helper encodes those per-bar
/// boundary rates into flat spans for GPU consumption.
pub fn prepare_funding_event_buffers(
    funding_rates: &FundingRateData,
    timestamps: &[i64],
    symbols: &[String],
) -> FundingEventBuffers {
    let num_bars = timestamps.len();
    let num_symbols = symbols.len();
    let mut spans = vec![
        GpuFundingSpan {
            offset: 0,
            len: 0,
        };
        num_bars * num_symbols
    ];
    let mut flat_rates: Vec<f64> = Vec::new();

    if num_bars == 0 || num_symbols == 0 || funding_rates.is_empty() {
        return FundingEventBuffers {
            spans,
            rates: flat_rates,
        };
    }

    const HOUR_MS: i64 = 3_600_000;

    for (bar_idx, &ts) in timestamps.iter().enumerate() {
        let prev_ts = if bar_idx > 0 { timestamps[bar_idx - 1] } else { ts };
        let first_boundary = ((prev_ts / HOUR_MS) + 1) * HOUR_MS;
        if first_boundary > ts {
            continue;
        }

        for (sym_idx, sym) in symbols.iter().enumerate() {
            let Some(series) = funding_rates.get(sym.as_str()) else {
                continue;
            };
            let slot = bar_idx * num_symbols + sym_idx;
            let offset = flat_rates.len();
            let mut event_count: usize = 0;
            let mut boundary = first_boundary;
            while boundary <= ts {
                if let Some(rate) = lookup_funding_rate(series, boundary) {
                    flat_rates.push(rate);
                    event_count += 1;
                }
                boundary += HOUR_MS;
            }
            if event_count > 0 {
                spans[slot] = GpuFundingSpan {
                    offset: saturating_u32(offset, "funding_offset"),
                    len: saturating_u32(event_count, "funding_len"),
                };
            }
        }
    }

    FundingEventBuffers {
        spans,
        rates: flat_rates,
    }
}

/// Find the bar index range `[start, end)` that falls within `[from_ts, to_ts]`.
///
/// Uses `partition_point` (binary search on sorted timestamps).
/// When both bounds are `None`, returns `(0, len)` — full range (backwards compatible).
pub fn find_trade_bar_range(
    timestamps: &[i64],
    from_ts: Option<i64>,
    to_ts: Option<i64>,
) -> (u32, u32) {
    let start = match from_ts {
        Some(ft) => {
            let p = timestamps.partition_point(|&t| t < ft);
            if p > 0 && p < timestamps.len() && timestamps[p] > ft {
                (p - 1) as u32
            } else {
                p as u32
            }
        }
        None => 0,
    };
    let end = match to_ts {
        Some(tt) => timestamps.partition_point(|&t| t <= tt) as u32,
        None => timestamps.len() as u32,
    };
    (start, end)
}

/// Build flat raw candle buffer for GPU upload.
///
/// This is O(bars × symbols) data layout with zero computation.
/// Missing (bar, symbol) pairs get close=0 (indicator kernel skips them).
pub fn prepare_raw_candles(candles: &CandleData, symbols: &[String]) -> RawCandleResult {
    let num_symbols = symbols.len();

    // Build unified timeline from all symbols
    let mut all_ts: Vec<i64> = candles
        .values()
        .flat_map(|bars| bars.iter().map(|b| b.t))
        .collect();
    all_ts.sort_unstable();
    all_ts.dedup();
    let num_bars = all_ts.len();

    // Build per-symbol bar index: symbol → (timestamp → bar_index_in_source)
    let mut bar_indices: FxHashMap<&str, FxHashMap<i64, usize>> = FxHashMap::default();
    for (sym, bars) in candles {
        let mut idx = FxHashMap::default();
        for (i, bar) in bars.iter().enumerate() {
            idx.insert(bar.t, i);
        }
        bar_indices.insert(sym.as_str(), idx);
    }

    // Allocate flat buffer
    let total_slots = num_bars * num_symbols;
    let mut raw = vec![GpuRawCandle::zeroed(); total_slots];

    // Fill: for each (bar, symbol), copy OHLCV. If missing, keep OHLCV=0 but
    // still stamp t_sec to the unified timeline.
    for (bar_idx, &ts) in all_ts.iter().enumerate() {
        for (sym_idx, sym) in symbols.iter().enumerate() {
            let bar = bar_indices
                .get(sym.as_str())
                .and_then(|idx| idx.get(&ts))
                .and_then(|&i| candles.get(sym).and_then(|bars| bars.get(i)));

            let t_sec = to_gpu_t_sec(ts);

            if let Some(bar) = bar {
                raw[bar_idx * num_symbols + sym_idx] = GpuRawCandle {
                    open: bar.o,
                    high: bar.h,
                    low: bar.l,
                    close: bar.c,
                    volume: bar.v,
                    t_sec,
                    _pad: [0; 3],
                };
            } else {
                // Preserve timeline time for missing bars (close=0 still signals "missing").
                raw[bar_idx * num_symbols + sym_idx].t_sec = t_sec;
            }
        }
    }

    RawCandleResult {
        candles: raw,
        num_bars,
        num_symbols,
        timestamps: all_ts,
    }
}

/// Prepare sub-bar candles aligned to main bar ranges for GPU upload.
///
/// For each main bar `i`, sub-bars fall in the half-open range `(ts[i], ts[i+1]]`,
/// where `ts[last+1]` is treated as `+inf`.
///
/// This matches CPU semantics used by the backtest engine:
/// - Sub-bars with `t <= ts[0]` are dropped (no "previous" main bar exists).
/// - Sub-bars with `t > ts[last]` are assigned to the last main bar.
///
/// Within each main bar, we build the **union** of sub-bar timestamps across all symbols.
/// The buffer is packed so `sub_idx` refers to the same timestamp for every symbol.
/// Missing (bar, symbol, tick) slots are padded with a zeroed `GpuRawCandle` (close=0).
///
/// Layout: `candles[(bar_idx * max_sub + sub_idx) * num_symbols + sym_idx]`
///
/// This uses the same `GpuRawCandle` struct as main candles — only OHLCV + t_sec
/// are meaningful; the kernel reads just price fields for SL/TP checks.
pub fn prepare_sub_bar_candles(
    main_timestamps: &[i64],
    sub_candles: &CandleData,
    symbols: &[String],
) -> SubBarResult {
    let num_bars = main_timestamps.len();
    let num_symbols = symbols.len();

    if num_bars == 0 || num_symbols == 0 {
        return SubBarResult {
            candles: Vec::new(),
            sub_counts: vec![0u32; num_bars * num_symbols],
            max_sub_per_bar: 0,
            num_bars,
            num_symbols,
        };
    }

    // For each (bar, symbol), collect sorted sub-bars.
    //
    // CPU semantics: main bar i covers (main_ts[i], next_ts] in ms, where next_ts is
    // main_ts[i+1] or +inf for the last bar. This means:
    // - t == main_ts[i] belongs to bar (i-1)
    // - t <= main_ts[0] is dropped
    // - t > main_ts[last] is assigned to the last bar
    //
    // Step 1: For each symbol, sort sub-bars by timestamp and assign to main bars.
    // sub_bars_by_bar_sym[bar_idx][sym_idx] = Vec<&Bar>
    let mut sub_bars_by_bar_sym: Vec<Vec<Vec<&bt_core::candle::OhlcvBar>>> =
        vec![vec![Vec::new(); num_symbols]; num_bars];

    for (sym_idx, sym) in symbols.iter().enumerate() {
        if let Some(bars) = sub_candles.get(sym) {
            for bar in bars {
                // Assign sub-bar at time `t` to the previous main bar index:
                // Find the first main timestamp >= t, then subtract 1.
                //
                // Example: main_ts = [100, 200, 300]
                // - t in (100, 200] -> bar 0
                // - t in (200, 300] -> bar 1
                // - t > 300         -> bar 2
                //
                // Drop t <= main_ts[0] (no previous bar exists).
                let p = main_timestamps.partition_point(|&ts| ts < bar.t); // 0..=num_bars
                if p == 0 {
                    continue;
                }
                let main_idx = if p >= num_bars { num_bars - 1 } else { p - 1 };
                sub_bars_by_bar_sym[main_idx][sym_idx].push(bar);
            }
        }
    }

    // Sort per (bar, symbol) slice once up-front (needed for deterministic packing).
    for bar_idx in 0..num_bars {
        for sym_idx in 0..num_symbols {
            sub_bars_by_bar_sym[bar_idx][sym_idx].sort_by_key(|b| b.t);
        }
    }

    // Step 2: For each bar, build the union of sub-bar timestamps across all symbols.
    // This defines the per-bar "tick timeline" used by the GPU kernel for ranked entry processing.
    let mut union_ts_by_bar: Vec<Vec<i64>> = vec![Vec::new(); num_bars];
    let mut max_sub: usize = 0;
    for bar_idx in 0..num_bars {
        let mut union_ts: Vec<i64> = Vec::new();
        for sym_idx in 0..num_symbols {
            union_ts.extend(sub_bars_by_bar_sym[bar_idx][sym_idx].iter().map(|b| b.t));
        }
        union_ts.sort_unstable();
        union_ts.dedup();
        max_sub = max_sub.max(union_ts.len());
        union_ts_by_bar[bar_idx] = union_ts;
    }

    if max_sub == 0 {
        return SubBarResult {
            candles: Vec::new(),
            sub_counts: vec![0u32; num_bars * num_symbols],
            max_sub_per_bar: 0,
            num_bars,
            num_symbols,
        };
    }

    // Step 3: Allocate rectangular buffer and fill
    let total_slots = num_bars * max_sub * num_symbols;
    let mut flat = vec![GpuRawCandle::zeroed(); total_slots];
    let mut sub_counts = vec![0u32; num_bars * num_symbols];

    for bar_idx in 0..num_bars {
        let union_ts = &union_ts_by_bar[bar_idx];
        let union_len = union_ts.len() as u32;

        for sym_idx in 0..num_symbols {
            // Replicate union tick count across all symbols for this bar.
            sub_counts[bar_idx * num_symbols + sym_idx] = union_len;

            // Fill only the union timeline; remaining slots up to max_sub stay zeroed.
            let subs = &sub_bars_by_bar_sym[bar_idx][sym_idx];
            if subs.is_empty() || union_ts.is_empty() {
                continue;
            }

            // Two-pointer merge: both `union_ts` and `subs` are sorted by timestamp.
            let mut p = 0usize;
            for (sub_idx, &t) in union_ts.iter().enumerate() {
                while p < subs.len() && subs[p].t < t {
                    p += 1;
                }
                if p < subs.len() && subs[p].t == t {
                    let bar = subs[p];
                    let flat_idx = (bar_idx * max_sub + sub_idx) * num_symbols + sym_idx;
                    flat[flat_idx] = GpuRawCandle {
                        open: bar.o,
                        high: bar.h,
                        low: bar.l,
                        close: bar.c,
                        volume: bar.v,
                        t_sec: to_gpu_t_sec(bar.t),
                        _pad: [0; 3],
                    };
                    p += 1;
                }
            }
        }
    }

    eprintln!(
        "[sub-bar] Prepared {} bars × {} max_sub × {} symbols = {} slots ({:.1} MB)",
        num_bars,
        max_sub,
        num_symbols,
        total_slots,
        (total_slots * std::mem::size_of::<GpuRawCandle>()) as f64 / 1e6,
    );

    SubBarResult {
        candles: flat,
        sub_counts,
        max_sub_per_bar: max_sub as u32,
        num_bars,
        num_symbols,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use bt_core::candle::{FundingRateData, OhlcvBar};

    #[test]
    fn prepare_raw_candles_stamps_t_sec_for_missing_bars() {
        let symbols = vec!["AAA".to_string(), "BBB".to_string()];

        // AAA has a bar at t=1000ms, BBB only at t=2000ms.
        let mut candles: CandleData = CandleData::default();
        candles.insert(
            "AAA".to_string(),
            vec![OhlcvBar {
                t: 1_000,
                t_close: 1_000,
                o: 1.0,
                h: 1.0,
                l: 1.0,
                c: 1.0,
                v: 1.0,
                n: 1,
            }],
        );
        candles.insert(
            "BBB".to_string(),
            vec![OhlcvBar {
                t: 2_000,
                t_close: 2_000,
                o: 2.0,
                h: 2.0,
                l: 2.0,
                c: 2.0,
                v: 2.0,
                n: 1,
            }],
        );

        let out = prepare_raw_candles(&candles, &symbols);
        assert_eq!(out.num_bars, 2);
        assert_eq!(out.num_symbols, 2);
        assert_eq!(out.timestamps, vec![1_000, 2_000]);

        // Missing slot: BBB at bar0 has close=0 but t_sec should still be stamped.
        let bbb_bar0 = out.candles[0 * out.num_symbols + 1];
        assert_eq!(bbb_bar0.close, 0.0);
        assert_eq!(bbb_bar0.t_sec, 1u32);

        // Missing slot: AAA at bar1 has close=0 but t_sec should still be stamped.
        let aaa_bar1 = out.candles[1 * out.num_symbols + 0];
        assert_eq!(aaa_bar1.close, 0.0);
        assert_eq!(aaa_bar1.t_sec, 2u32);
    }

    #[test]
    fn prepare_sub_bars_matches_cpu_exit_windows() {
        let main_timestamps = vec![1_000, 2_000, 3_000];
        let symbols = vec!["ETH".to_string()];

        // Regression guard for AQC-168:
        // if these windows drift from bt-core, GPU sub-bar exits evaluate SL using
        // the wrong indicator snapshot and can flip sl_atr_mult directional behaviour.
        // Include boundary cases: <= first ts (ignored), exact boundaries, between boundaries,
        // and beyond the last timestamp (should map to last bar).
        let sub_times = vec![900_i64, 1_000, 1_500, 2_000, 2_500, 3_000, 3_500];
        let mut sub: CandleData = CandleData::default();
        sub.insert(
            "ETH".to_string(),
            sub_times
                .iter()
                .map(|&t| OhlcvBar {
                    t,
                    t_close: t,
                    o: t as f64,
                    h: t as f64,
                    l: t as f64,
                    c: t as f64,
                    v: 1.0,
                    n: 1,
                })
                .collect(),
        );

        let out = prepare_sub_bar_candles(&main_timestamps, &sub, &symbols);

        // Expected CPU-parity assignment:
        // bar0 (1000,2000] -> 1500,2000
        // bar1 (2000,3000] -> 2500,3000
        // bar2 (3000,+inf) -> 3500
        assert_eq!(out.sub_counts, vec![2, 2, 1]);

        let max_sub = out.max_sub_per_bar as usize;
        let ns = symbols.len();
        let close_at = |bar_idx: usize, sub_idx: usize| -> i64 {
            let idx = (bar_idx * max_sub + sub_idx) * ns;
            out.candles[idx].close as i64
        };

        assert_eq!(close_at(0, 0), 1_500);
        assert_eq!(close_at(0, 1), 2_000);
        assert_eq!(close_at(1, 0), 2_500);
        assert_eq!(close_at(1, 1), 3_000);
        assert_eq!(close_at(2, 0), 3_500);
    }

    #[test]
    fn to_gpu_t_sec_clamps_negative_and_saturates_u32_max() {
        assert_eq!(to_gpu_t_sec(-1), 0);
        assert_eq!(to_gpu_t_sec(-9_999), 0);
        assert_eq!(to_gpu_t_sec(1_234), 1);

        let overflow_ms = (u32::MAX as i64 + 42) * 1000;
        assert_eq!(to_gpu_t_sec(overflow_ms), u32::MAX);
    }

    #[test]
    fn prepare_funding_event_buffers_tracks_per_bar_per_symbol_spans() {
        let timestamps = vec![1_000_i64, 3_600_000, 10_800_000];
        let symbols = vec!["ETH".to_string(), "BTC".to_string()];

        let mut funding: FundingRateData = FundingRateData::default();
        funding.insert(
            "ETH".to_string(),
            vec![(3_600_000, 0.01), (7_200_000, 0.02), (10_800_000, 0.03)],
        );

        let out = prepare_funding_event_buffers(&funding, &timestamps, &symbols);
        assert_eq!(out.spans.len(), timestamps.len() * symbols.len());

        // bar0 has no crossed hour boundary.
        assert_eq!(out.spans[0].len, 0);
        assert_eq!(out.spans[1].len, 0);

        // bar1 crosses 3_600_000 exactly -> one ETH funding event.
        let b1_eth = out.spans[2];
        assert_eq!(b1_eth.offset, 0);
        assert_eq!(b1_eth.len, 1);
        assert_eq!(out.spans[3].len, 0); // BTC has no funding series.

        // bar2 crosses 7_200_000 and 10_800_000 -> two ETH funding events.
        let b2_eth = out.spans[4];
        assert_eq!(b2_eth.offset, 1);
        assert_eq!(b2_eth.len, 2);
        assert_eq!(out.spans[5].len, 0);

        assert_eq!(out.rates, vec![0.01, 0.02, 0.03]);
    }

    #[test]
    fn prepare_funding_event_buffers_uses_latest_prior_rate_when_boundary_missing() {
        let timestamps = vec![1_000_i64, 7_200_000];
        let symbols = vec!["ETH".to_string()];

        let mut funding: FundingRateData = FundingRateData::default();
        // Missing 7_200_000 exact record: second boundary should fallback to the latest prior rate.
        funding.insert("ETH".to_string(), vec![(3_600_000, 0.11)]);

        let out = prepare_funding_event_buffers(&funding, &timestamps, &symbols);
        assert_eq!(out.spans.len(), 2);
        let b1 = out.spans[1];
        assert_eq!(b1.offset, 0);
        assert_eq!(b1.len, 2);
        assert_eq!(out.rates, vec![0.11, 0.11]);
    }

    #[test]
    fn find_trade_bar_range_includes_leading_partial_bar_for_from_inside_bar() {
        let ts = vec![1_000_i64, 2_000, 3_000];
        // from=1_500 falls inside bar [1_000,2_000] -> include bar 1_000.
        let (start, end) = find_trade_bar_range(&ts, Some(1_500), Some(2_500));
        assert_eq!((start, end), (0, 2));
    }

    #[test]
    fn find_trade_bar_range_keeps_exact_from_alignment() {
        let ts = vec![1_000_i64, 2_000, 3_000];
        let (start, end) = find_trade_bar_range(&ts, Some(2_000), Some(2_500));
        assert_eq!((start, end), (1, 2));
    }

    #[test]
    fn find_trade_bar_range_keeps_empty_when_from_is_past_tail() {
        let ts = vec![1_000_i64, 2_000, 3_000];
        let (start, end) = find_trade_bar_range(&ts, Some(4_000), Some(5_000));
        assert_eq!((start, end), (3, 3));
    }
}
