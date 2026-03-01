use super::RingBuf;

/// Bollinger Bands — rolling SMA + population std dev (ddof=0).
/// Matches Python `ta.volatility.BollingerBands`.
#[derive(Debug, Clone)]
pub struct BollingerBands {
    ring: RingBuf,
    num_std: f64,
    last: BbOutput,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct BbOutput {
    pub upper: f64,
    pub middle: f64,
    pub lower: f64,
}

impl BollingerBands {
    pub fn new(window: usize) -> Self {
        Self {
            ring: RingBuf::new(window),
            num_std: 2.0,
            last: BbOutput {
                upper: 0.0,
                middle: 0.0,
                lower: 0.0,
            },
        }
    }

    pub fn update(&mut self, close: f64) -> BbOutput {
        // R-M6: reject non-finite closes so rolling stats remain valid.
        if !close.is_finite() {
            return self.last;
        }

        self.ring.push(close);
        if !self.ring.full() {
            let mean = self.ring.mean();
            self.last = BbOutput {
                upper: mean,
                middle: mean,
                lower: mean,
            };
            return self.last;
        }
        let middle = self.ring.mean();
        let std = self.ring.std_pop();
        self.last = BbOutput {
            upper: middle + self.num_std * std,
            middle,
            lower: middle - self.num_std * std,
        };
        self.last
    }
}

#[cfg(test)]
mod tests {
    use super::BollingerBands;

    #[test]
    fn non_finite_close_is_skipped_without_poisoning_state() {
        let mut bb = BollingerBands::new(2);
        let _ = bb.update(100.0);
        let prev = bb.update(102.0);

        let after_nan = bb.update(f64::NAN);
        assert_eq!(after_nan, prev);

        let after_inf = bb.update(f64::INFINITY);
        assert_eq!(after_inf, prev);

        let after_valid = bb.update(104.0);
        assert!(after_valid.upper.is_finite());
        assert!(after_valid.middle.is_finite());
        assert!(after_valid.lower.is_finite());
        assert_ne!(after_valid, prev);
    }
}
