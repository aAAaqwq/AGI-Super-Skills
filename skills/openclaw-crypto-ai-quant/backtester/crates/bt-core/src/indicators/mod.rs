pub mod adx;
pub mod atr;
pub mod bollinger;
pub mod ema;
pub mod macd;
pub mod rsi;
pub mod volume;

use crate::candle::OhlcvBar;
use serde::{Deserialize, Serialize};

/// Ring buffer for rolling-window computations (BB, StochRSI, vol SMA, etc.).
#[derive(Debug, Clone)]
pub struct RingBuf {
    buf: Vec<f64>,
    pos: usize,
    len: usize,
    cap: usize,
}

impl RingBuf {
    pub fn new(capacity: usize) -> Self {
        assert!(capacity > 0, "RingBuf capacity must be > 0");
        Self {
            buf: vec![0.0; capacity],
            pos: 0,
            len: 0,
            cap: capacity,
        }
    }

    pub fn push(&mut self, val: f64) {
        self.buf[self.pos] = val;
        self.pos = (self.pos + 1) % self.cap;
        if self.len < self.cap {
            self.len += 1;
        }
    }

    pub fn full(&self) -> bool {
        self.len == self.cap
    }

    pub fn len(&self) -> usize {
        self.len
    }

    pub fn is_empty(&self) -> bool {
        self.len == 0
    }

    /// Iterate over values in insertion order (oldest first).
    pub fn iter(&self) -> RingBufIter<'_> {
        RingBufIter {
            buf: &self.buf,
            start: if self.len < self.cap { 0 } else { self.pos },
            count: 0,
            total: self.len,
            cap: self.cap,
        }
    }

    pub fn mean(&self) -> f64 {
        if self.len == 0 {
            return 0.0;
        }
        self.iter().sum::<f64>() / self.len as f64
    }

    /// Population standard deviation (ddof=0, matching pandas default for BB).
    pub fn std_pop(&self) -> f64 {
        if self.len == 0 {
            return 0.0;
        }
        let mean = self.mean();
        let var = self.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / self.len as f64;
        var.sqrt()
    }

    /// Min value in the buffer.
    pub fn min(&self) -> f64 {
        self.iter().fold(f64::INFINITY, f64::min)
    }

    /// Max value in the buffer.
    pub fn max(&self) -> f64 {
        self.iter().fold(f64::NEG_INFINITY, f64::max)
    }
}

pub struct RingBufIter<'a> {
    buf: &'a [f64],
    start: usize,
    count: usize,
    total: usize,
    cap: usize,
}

impl<'a> Iterator for RingBufIter<'a> {
    type Item = f64;
    fn next(&mut self) -> Option<f64> {
        if self.count >= self.total {
            return None;
        }
        let idx = (self.start + self.count) % self.cap;
        self.count += 1;
        Some(self.buf[idx])
    }
}

/// Aggregated indicator state for one symbol.
/// All indicators update incrementally bar-by-bar.
pub struct IndicatorBank {
    pub ema_slow: ema::Ema,
    pub ema_fast: ema::Ema,
    pub ema_macro: ema::Ema,
    pub adx: adx::AdxIndicator,
    pub bb: bollinger::BollingerBands,
    pub bb_width_avg: RingBuf,
    pub atr: atr::AtrIndicator,
    pub rsi: rsi::RsiIndicator,
    pub stoch_rsi: Option<rsi::StochRsi>,
    pub macd: macd::MacdIndicator,
    pub vol_sma: volume::VolSma,
    pub vol_trend: volume::VolTrend,
    pub avg_atr: RingBuf, // for AVE (Adaptive Volatility Entry)

    // Derived / lagged values
    pub prev_close: f64,
    pub prev_adx: f64,
    pub prev_atr: f64,
    pub prev_macd_hist: f64,
    pub prev2_macd_hist: f64,
    pub prev3_macd_hist: f64,
    pub prev_ema_fast: f64,
    pub prev_ema_slow: f64,
    pub bar_count: usize,

    /// Cached copy of the most recent snapshot (for sub-bar exit checks).
    latest_snap_cache: Option<IndicatorSnapshot>,
}

/// Snapshot of indicator values for the current bar (passed to signal logic).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct IndicatorSnapshot {
    pub close: f64,
    pub high: f64,
    pub low: f64,
    pub open: f64,
    pub volume: f64,
    pub t: i64,

    pub ema_slow: f64,
    pub ema_fast: f64,
    pub ema_macro: f64,

    pub adx: f64,
    pub adx_pos: f64,
    pub adx_neg: f64,
    pub adx_slope: f64, // current - previous

    pub bb_upper: f64,
    pub bb_lower: f64,
    pub bb_width: f64,
    pub bb_width_avg: f64,
    pub bb_width_ratio: f64,

    pub atr: f64,
    pub atr_slope: f64,
    pub avg_atr: f64,

    pub rsi: f64,
    pub stoch_rsi_k: f64,
    pub stoch_rsi_d: f64,

    pub macd_hist: f64,
    pub prev_macd_hist: f64,
    pub prev2_macd_hist: f64,
    pub prev3_macd_hist: f64, // needed by MMDE (4-bar persistent divergence)

    pub vol_sma: f64,
    pub vol_trend: bool,

    pub prev_close: f64,
    pub prev_ema_fast: f64,
    pub prev_ema_slow: f64,

    pub bar_count: usize,

    /// Funding rate (always 0.0 in backtester v1 — no funding data).
    pub funding_rate: f64,
}

impl IndicatorBank {
    pub fn new(cfg: &crate::config::IndicatorsConfig, use_stoch_rsi: bool) -> Self {
        Self::new_with_ave_window(cfg, use_stoch_rsi, cfg.ave_avg_atr_window)
    }

    pub fn new_with_ave_window(
        cfg: &crate::config::IndicatorsConfig,
        use_stoch_rsi: bool,
        ave_avg_atr_window: usize,
    ) -> Self {
        Self {
            ema_slow: ema::Ema::new(cfg.ema_slow_window),
            ema_fast: ema::Ema::new(cfg.ema_fast_window),
            ema_macro: ema::Ema::new(cfg.ema_macro_window),
            adx: adx::AdxIndicator::new(cfg.adx_window),
            bb: bollinger::BollingerBands::new(cfg.bb_window),
            bb_width_avg: RingBuf::new(cfg.bb_width_avg_window),
            atr: atr::AtrIndicator::new(cfg.atr_window),
            rsi: rsi::RsiIndicator::new(cfg.rsi_window),
            stoch_rsi: if use_stoch_rsi {
                Some(rsi::StochRsi::new(
                    cfg.stoch_rsi_window,
                    cfg.stoch_rsi_smooth1,
                    cfg.stoch_rsi_smooth2,
                ))
            } else {
                None
            },
            macd: macd::MacdIndicator::new(12, 26, 9),
            vol_sma: volume::VolSma::new(cfg.vol_sma_window),
            vol_trend: volume::VolTrend::new(cfg.vol_trend_window),
            avg_atr: RingBuf::new(ave_avg_atr_window),
            prev_close: 0.0,
            prev_adx: 0.0,
            prev_atr: 0.0,
            prev_macd_hist: 0.0,
            prev2_macd_hist: 0.0,
            prev3_macd_hist: 0.0,
            prev_ema_fast: 0.0,
            prev_ema_slow: 0.0,
            bar_count: 0,
            latest_snap_cache: None,
        }
    }

    /// Return the most recently computed IndicatorSnapshot.
    /// Panics if update() has never been called.
    pub fn latest_snap(&self) -> IndicatorSnapshot {
        self.latest_snap_cache
            .clone()
            .unwrap_or_else(|| IndicatorSnapshot {
                close: self.prev_close,
                high: self.prev_close,
                low: self.prev_close,
                open: self.prev_close,
                volume: 0.0,
                t: 0,
                ema_slow: self.prev_ema_slow,
                ema_fast: self.prev_ema_fast,
                ema_macro: 0.0,
                adx: self.prev_adx,
                adx_pos: 0.0,
                adx_neg: 0.0,
                adx_slope: 0.0,
                bb_upper: 0.0,
                bb_lower: 0.0,
                bb_width: 0.0,
                bb_width_avg: 0.0,
                bb_width_ratio: 1.0,
                atr: self.prev_atr,
                atr_slope: 0.0,
                avg_atr: 0.0,
                rsi: 50.0,
                stoch_rsi_k: 0.0,
                stoch_rsi_d: 0.0,
                macd_hist: self.prev_macd_hist,
                prev_macd_hist: self.prev2_macd_hist,
                prev2_macd_hist: self.prev3_macd_hist,
                prev3_macd_hist: 0.0,
                vol_sma: 0.0,
                vol_trend: false,
                prev_close: self.prev_close,
                prev_ema_fast: self.prev_ema_fast,
                prev_ema_slow: self.prev_ema_slow,
                bar_count: self.bar_count,
                funding_rate: 0.0,
            })
    }

    /// Feed one bar and return a snapshot of all indicator values.
    pub fn update(&mut self, bar: &OhlcvBar) -> IndicatorSnapshot {
        let ema_slow = self.ema_slow.update(bar.c);
        let ema_fast = self.ema_fast.update(bar.c);
        let ema_macro = self.ema_macro.update(bar.c);

        let adx_out = self.adx.update(bar.h, bar.l, bar.c);
        let bb_out = self.bb.update(bar.c);

        // Python: bb_width = (bb_high - bb_low) / Close
        let bb_width = if bar.c > 0.0 {
            (bb_out.upper - bb_out.lower) / bar.c
        } else {
            0.0
        };
        self.bb_width_avg.push(bb_width);
        let bb_width_avg = self.bb_width_avg.mean();
        let bb_width_ratio = if bb_width_avg > 0.0 {
            bb_width / bb_width_avg
        } else {
            1.0
        };

        let atr_val = self.atr.update(bar.h, bar.l, bar.c);
        self.avg_atr.push(atr_val);
        let avg_atr = self.avg_atr.mean();

        let rsi_val = self.rsi.update(bar.c);

        let (stoch_k, stoch_d) = if let Some(ref mut sr) = self.stoch_rsi {
            sr.update(rsi_val)
        } else {
            (0.0, 0.0)
        };

        let macd_hist = self.macd.update(bar.c);

        let vol_sma_val = self.vol_sma.update(bar.v);
        let vol_short_sma = self.vol_trend.update(bar.v);
        let vol_trend_val = vol_short_sma > vol_sma_val;

        let adx_slope = adx_out.adx - self.prev_adx;
        let atr_slope = atr_val - self.prev_atr;

        let snap = IndicatorSnapshot {
            close: bar.c,
            high: bar.h,
            low: bar.l,
            open: bar.o,
            volume: bar.v,
            t: bar.t,

            ema_slow,
            ema_fast,
            ema_macro,

            adx: adx_out.adx,
            adx_pos: adx_out.adx_pos,
            adx_neg: adx_out.adx_neg,
            adx_slope,

            bb_upper: bb_out.upper,
            bb_lower: bb_out.lower,
            bb_width,
            bb_width_avg,
            bb_width_ratio,

            atr: atr_val,
            atr_slope,
            avg_atr,

            rsi: rsi_val,
            stoch_rsi_k: stoch_k,
            stoch_rsi_d: stoch_d,

            macd_hist,
            prev_macd_hist: self.prev_macd_hist,
            prev2_macd_hist: self.prev2_macd_hist,
            prev3_macd_hist: self.prev3_macd_hist,

            vol_sma: vol_sma_val,
            vol_trend: vol_trend_val,

            prev_close: self.prev_close,
            prev_ema_fast: self.prev_ema_fast,
            prev_ema_slow: self.prev_ema_slow,

            bar_count: self.bar_count,
            funding_rate: 0.0, // backtester v1: no funding data
        };

        // Save lagged values for next bar
        self.prev3_macd_hist = self.prev2_macd_hist;
        self.prev2_macd_hist = self.prev_macd_hist;
        self.prev_macd_hist = macd_hist;
        self.prev_adx = adx_out.adx;
        self.prev_atr = atr_val;
        self.prev_close = bar.c;
        self.prev_ema_fast = ema_fast;
        self.prev_ema_slow = ema_slow;
        self.bar_count += 1;

        // Cache for sub-bar exit checks
        self.latest_snap_cache = Some(snap.clone());

        snap
    }
}

#[cfg(test)]
mod tests {
    use super::RingBuf;

    #[test]
    #[should_panic(expected = "RingBuf capacity must be > 0")]
    fn ring_buf_new_zero_capacity_panics() {
        let _ = RingBuf::new(0);
    }

    #[test]
    fn ring_buf_push_and_iterate_oldest_first() {
        let mut buf = RingBuf::new(2);
        buf.push(1.0);
        buf.push(2.0);
        buf.push(3.0);
        let values: Vec<f64> = buf.iter().collect();
        assert_eq!(values, vec![2.0, 3.0]);
    }
}
