/// Exponential Moving Average — incremental computation.
///
/// Matches Python `ta.trend.ema_indicator()` which uses pandas
/// `ewm(span=window, adjust=False).mean()`.
///
/// Behaviour:
///   bar 0  → value = price (first observation)
///   bar 1+ → value = α·price + (1−α)·prev   where α = 2/(window+1)
///
/// `is_warm()` returns true once `window` bars have been seen, so callers
/// can skip the warmup region.
#[derive(Debug, Clone)]
pub struct Ema {
    alpha: f64,
    pub value: f64,
    window: usize,
    count: usize,
    warm: bool,
}

impl Ema {
    pub fn new(window: usize) -> Self {
        let window = window.max(1);
        Self {
            alpha: 2.0 / (window as f64 + 1.0),
            value: 0.0,
            window,
            count: 0,
            warm: false,
        }
    }

    /// Feed one price, return the current EMA value.
    pub fn update(&mut self, price: f64) -> f64 {
        if self.count == 0 {
            // First bar: seed with the observation itself (adjust=False)
            self.value = price;
        } else {
            self.value = self.alpha * price + (1.0 - self.alpha) * self.value;
        }
        self.count += 1;
        if !self.warm && self.count >= self.window {
            self.warm = true;
        }
        self.value
    }

    pub fn is_warm(&self) -> bool {
        self.warm
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ema_matches_pandas_ewm_adjust_false() {
        // Matches: pd.Series([10,11,12,13]).ewm(span=3, adjust=False).mean()
        let mut ema = Ema::new(3);
        // alpha = 2/(3+1) = 0.5

        // bar 0: seed = 10.0
        let v = ema.update(10.0);
        assert!((v - 10.0).abs() < 1e-10);
        assert!(!ema.is_warm());

        // bar 1: 0.5*11 + 0.5*10 = 10.5
        let v = ema.update(11.0);
        assert!((v - 10.5).abs() < 1e-10);
        assert!(!ema.is_warm());

        // bar 2: 0.5*12 + 0.5*10.5 = 11.25 — warm after 3 bars
        let v = ema.update(12.0);
        assert!((v - 11.25).abs() < 1e-10);
        assert!(ema.is_warm());

        // bar 3: 0.5*13 + 0.5*11.25 = 12.125
        let v = ema.update(13.0);
        assert!((v - 12.125).abs() < 1e-10);
    }

    #[test]
    fn test_ema_zero_window_is_clamped_to_one() {
        let mut ema = Ema::new(0);

        // With window=1 clamp, alpha=1.0 and warmup completes after first sample.
        let v = ema.update(10.0);
        assert!((v - 10.0).abs() < 1e-10);
        assert!(ema.is_warm());

        let v = ema.update(12.5);
        assert!((v - 12.5).abs() < 1e-10);
    }
}
