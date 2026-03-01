/// Average True Range — Wilder smoothing, matching Python `ta.volatility.average_true_range`.
#[derive(Debug, Clone)]
pub struct AtrIndicator {
    window: usize,
    prev_close: f64,
    atr_value: f64,
    count: usize,
    sum: f64,
    warm: bool,
    has_prev: bool,
}

impl AtrIndicator {
    pub fn new(window: usize) -> Self {
        Self {
            window,
            prev_close: 0.0,
            atr_value: 0.0,
            count: 0,
            sum: 0.0,
            warm: false,
            has_prev: false,
        }
    }

    pub fn update(&mut self, high: f64, low: f64, close: f64) -> f64 {
        if self.window == 0 {
            return 0.0;
        }

        // H7: reject non-finite inputs — return current ATR unchanged.
        if !high.is_finite() || !low.is_finite() || !close.is_finite() {
            return self.atr_value;
        }

        let tr = if self.has_prev {
            (high - low)
                .max((high - self.prev_close).abs())
                .max((low - self.prev_close).abs())
        } else {
            high - low
        };

        self.has_prev = true;
        self.prev_close = close;

        if !self.warm {
            self.sum += tr;
            self.count += 1;
            if self.count >= self.window {
                self.atr_value = self.sum / self.window as f64;
                self.warm = true;
            } else {
                self.atr_value = self.sum / self.count as f64;
            }
        } else {
            // Wilder smoothing: ATR = (prev_ATR * (N-1) + TR) / N
            self.atr_value =
                (self.atr_value * (self.window as f64 - 1.0) + tr) / self.window as f64;
        }
        self.atr_value
    }

    pub fn is_warm(&self) -> bool {
        self.warm
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_nan_skipped() {
        let mut atr = AtrIndicator::new(2);
        let v1 = atr.update(10.0, 8.0, 9.0);
        assert!(v1 > 0.0);
        let prev = atr.update(11.0, 9.0, 10.0);
        // Feed NaN — ATR should stay unchanged.
        let after_nan = atr.update(f64::NAN, 9.0, 10.0);
        assert_eq!(after_nan, prev);
        // Feed Inf — ATR should stay unchanged.
        let after_inf = atr.update(12.0, f64::NEG_INFINITY, 10.0);
        assert_eq!(after_inf, prev);
        // Normal update still works after skipped values.
        // Use a large range to guarantee a different ATR.
        let v_ok = atr.update(20.0, 5.0, 12.0);
        assert!(v_ok > 0.0);
        assert!(
            v_ok != prev,
            "ATR should change after a valid candle with different range"
        );
    }

    #[test]
    fn test_all_nan_returns_zero() {
        let mut atr = AtrIndicator::new(3);
        // All inputs are NaN — ATR should remain at initial 0.0.
        let v = atr.update(f64::NAN, f64::NAN, f64::NAN);
        assert_eq!(v, 0.0);
        assert!(!atr.is_warm());
    }

    #[test]
    fn test_inf_close_skipped() {
        let mut atr = AtrIndicator::new(2);
        atr.update(10.0, 8.0, 9.0);
        let prev = atr.update(11.0, 9.0, 10.0);
        // Inf in close should be skipped.
        let after = atr.update(11.0, 9.0, f64::INFINITY);
        assert_eq!(after, prev);
    }
}
