use super::RingBuf;

/// RSI (Relative Strength Index) — Wilder smoothing of avg gain/loss.
/// Matches Python `ta.momentum.rsi`.
#[derive(Debug, Clone)]
pub struct RsiIndicator {
    window: usize,
    prev_close: f64,
    avg_gain: f64,
    avg_loss: f64,
    pub value: f64,
    count: usize,
    gain_sum: f64,
    loss_sum: f64,
    warm: bool,
    has_prev: bool,
}

impl RsiIndicator {
    pub fn new(window: usize) -> Self {
        Self {
            window,
            prev_close: 0.0,
            avg_gain: 0.0,
            avg_loss: 0.0,
            value: 50.0,
            count: 0,
            gain_sum: 0.0,
            loss_sum: 0.0,
            warm: false,
            has_prev: false,
        }
    }

    pub fn update(&mut self, close: f64) -> f64 {
        if self.window == 0 {
            self.prev_close = close;
            self.has_prev = true;
            self.value = 50.0;
            return 50.0;
        }

        // R-M6: reject non-finite closes to keep RSI accumulators stable.
        if !close.is_finite() {
            return self.value;
        }

        if !self.has_prev {
            self.prev_close = close;
            self.has_prev = true;
            return 50.0;
        }

        let change = close - self.prev_close;
        let gain = if change > 0.0 { change } else { 0.0 };
        let loss = if change < 0.0 { -change } else { 0.0 };
        self.prev_close = close;

        if !self.warm {
            self.gain_sum += gain;
            self.loss_sum += loss;
            self.count += 1;
            if self.count >= self.window {
                self.avg_gain = self.gain_sum / self.window as f64;
                self.avg_loss = self.loss_sum / self.window as f64;
                self.warm = true;
            } else {
                self.value = 50.0;
                return 50.0;
            }
        } else {
            // Wilder smoothing
            let w = self.window as f64;
            self.avg_gain = (self.avg_gain * (w - 1.0) + gain) / w;
            self.avg_loss = (self.avg_loss * (w - 1.0) + loss) / w;
        }

        if self.avg_loss == 0.0 {
            self.value = 100.0;
        } else {
            let rs = self.avg_gain / self.avg_loss;
            self.value = 100.0 - 100.0 / (1.0 + rs);
        }
        self.value
    }
}

/// Stochastic RSI — StochRSI K and D lines.
/// Matches Python `ta.momentum.StochRSIIndicator`.
///
/// 1. Collect RSI values in a rolling window
/// 2. K = (RSI - min(RSI, window)) / (max(RSI, window) - min(RSI, window))
/// 3. Smooth K with SMA(smooth1) → StochRSI_K
/// 4. Smooth StochRSI_K with SMA(smooth2) → StochRSI_D
#[derive(Debug, Clone)]
pub struct StochRsi {
    rsi_ring: RingBuf,
    k_ring: RingBuf, // smooth1 window for K
    d_ring: RingBuf, // smooth2 window for D
}

impl StochRsi {
    pub fn new(window: usize, smooth1: usize, smooth2: usize) -> Self {
        Self {
            rsi_ring: RingBuf::new(window),
            k_ring: RingBuf::new(smooth1),
            d_ring: RingBuf::new(smooth2),
        }
    }

    /// Feed an RSI value, return (K, D) in range [0, 1].
    pub fn update(&mut self, rsi: f64) -> (f64, f64) {
        self.rsi_ring.push(rsi);
        if !self.rsi_ring.full() {
            return (0.5, 0.5);
        }

        let min_rsi = self.rsi_ring.min();
        let max_rsi = self.rsi_ring.max();
        let range = max_rsi - min_rsi;

        let raw_k = if range > 0.0 {
            (rsi - min_rsi) / range
        } else {
            0.5
        };

        self.k_ring.push(raw_k);
        let k = self.k_ring.mean();

        self.d_ring.push(k);
        let d = self.d_ring.mean();

        (k, d)
    }
}

#[cfg(test)]
mod tests {
    use super::RsiIndicator;

    #[test]
    fn zero_window_returns_neutral_and_stays_not_warm() {
        let mut rsi = RsiIndicator::new(0);
        for close in [100.0, 101.5, 99.0, 102.0, 98.0] {
            let out = rsi.update(close);
            assert_eq!(out, 50.0);
            assert!(out.is_finite());
        }
        assert!(!rsi.warm);
        assert_eq!(rsi.count, 0);
    }

    #[test]
    fn non_finite_close_is_skipped_without_poisoning_state() {
        let mut rsi = RsiIndicator::new(2);
        let _ = rsi.update(100.0);
        let prev = rsi.update(101.0);

        let after_nan = rsi.update(f64::NAN);
        assert_eq!(after_nan, prev);
        assert!(after_nan.is_finite());

        let after_inf = rsi.update(f64::INFINITY);
        assert_eq!(after_inf, prev);
        assert!(after_inf.is_finite());

        let after_valid = rsi.update(102.0);
        assert!(after_valid.is_finite());
        assert!(after_valid > prev);
    }
}
