/// ADX (Average Directional Index) — Wilder smoothing, matching Python `ta.trend.ADXIndicator`.
///
/// Algorithm:
/// 1. Compute +DM, -DM from consecutive bars
/// 2. Wilder-smooth +DM, -DM, and True Range over `window` periods
/// 3. +DI = smoothed_plus_dm / smoothed_tr * 100
/// 4. -DI = smoothed_minus_dm / smoothed_tr * 100
/// 5. DX = |+DI - -DI| / (+DI + -DI) * 100
/// 6. ADX = Wilder-smoothed DX over `window` periods
#[derive(Debug, Clone)]
pub struct AdxIndicator {
    window: usize,
    prev_high: f64,
    prev_low: f64,
    prev_close: f64,
    smoothed_plus_dm: f64,
    smoothed_minus_dm: f64,
    smoothed_tr: f64,
    adx_sum: f64,
    adx_value: f64,
    count: usize,
    dx_count: usize,
    phase: Phase,
}

#[derive(Debug, Clone, Copy, PartialEq)]
enum Phase {
    /// Need first bar to set prev_high/low/close.
    Init,
    /// Accumulating first `window` bars for initial SMA of +DM/-DM/TR.
    Accumulate,
    /// Accumulating first `window` DX values for initial ADX SMA.
    DxAccumulate,
    /// Fully warm — Wilder smoothing active.
    Warm,
}

#[derive(Debug, Clone, Copy)]
pub struct AdxOutput {
    pub adx: f64,
    pub adx_pos: f64, // +DI
    pub adx_neg: f64, // -DI
}

impl AdxIndicator {
    pub fn new(window: usize) -> Self {
        Self {
            window,
            prev_high: 0.0,
            prev_low: 0.0,
            prev_close: 0.0,
            smoothed_plus_dm: 0.0,
            smoothed_minus_dm: 0.0,
            smoothed_tr: 0.0,
            adx_sum: 0.0,
            adx_value: 0.0,
            count: 0,
            dx_count: 0,
            phase: Phase::Init,
        }
    }

    pub fn update(&mut self, high: f64, low: f64, close: f64) -> AdxOutput {
        if self.window == 0 {
            return AdxOutput {
                adx: 0.0,
                adx_pos: 0.0,
                adx_neg: 0.0,
            };
        }

        // R-M5: reject non-finite inputs to avoid poisoning Wilder accumulators.
        if !high.is_finite() || !low.is_finite() || !close.is_finite() {
            let (di_pos, di_neg, _) = self.compute_di_dx();
            return AdxOutput {
                adx: self.adx_value,
                adx_pos: di_pos,
                adx_neg: di_neg,
            };
        }

        match self.phase {
            Phase::Init => {
                self.prev_high = high;
                self.prev_low = low;
                self.prev_close = close;
                self.phase = Phase::Accumulate;
                self.count = 0;
                AdxOutput {
                    adx: 0.0,
                    adx_pos: 0.0,
                    adx_neg: 0.0,
                }
            }
            Phase::Accumulate => {
                let (plus_dm, minus_dm, tr) = self.compute_dm_tr(high, low);
                self.smoothed_plus_dm += plus_dm;
                self.smoothed_minus_dm += minus_dm;
                self.smoothed_tr += tr;
                self.count += 1;

                self.prev_high = high;
                self.prev_low = low;
                self.prev_close = close;

                if self.count >= self.window {
                    // First smoothed values are just the sums (will be divided below)
                    self.phase = Phase::DxAccumulate;
                    let (di_p, di_n, dx) = self.compute_di_dx();
                    self.adx_sum = dx;
                    self.dx_count = 1;
                    AdxOutput {
                        adx: dx,
                        adx_pos: di_p,
                        adx_neg: di_n,
                    }
                } else {
                    AdxOutput {
                        adx: 0.0,
                        adx_pos: 0.0,
                        adx_neg: 0.0,
                    }
                }
            }
            Phase::DxAccumulate => {
                self.wilder_step(high, low);
                let (di_p, di_n, dx) = self.compute_di_dx();
                self.adx_sum += dx;
                self.dx_count += 1;

                self.prev_high = high;
                self.prev_low = low;
                self.prev_close = close;

                if self.dx_count >= self.window {
                    self.adx_value = self.adx_sum / self.window as f64;
                    self.phase = Phase::Warm;
                    AdxOutput {
                        adx: self.adx_value,
                        adx_pos: di_p,
                        adx_neg: di_n,
                    }
                } else {
                    AdxOutput {
                        adx: self.adx_sum / self.dx_count as f64,
                        adx_pos: di_p,
                        adx_neg: di_n,
                    }
                }
            }
            Phase::Warm => {
                self.wilder_step(high, low);
                let (di_p, di_n, dx) = self.compute_di_dx();
                // Wilder smooth the ADX itself
                self.adx_value =
                    (self.adx_value * (self.window as f64 - 1.0) + dx) / self.window as f64;

                self.prev_high = high;
                self.prev_low = low;
                self.prev_close = close;

                AdxOutput {
                    adx: self.adx_value,
                    adx_pos: di_p,
                    adx_neg: di_n,
                }
            }
        }
    }

    fn compute_dm_tr(&self, high: f64, low: f64) -> (f64, f64, f64) {
        let up_move = high - self.prev_high;
        let down_move = self.prev_low - low;

        let plus_dm = if up_move > down_move && up_move > 0.0 {
            up_move
        } else {
            0.0
        };
        let minus_dm = if down_move > up_move && down_move > 0.0 {
            down_move
        } else {
            0.0
        };

        let tr = (high - low)
            .max((high - self.prev_close).abs())
            .max((low - self.prev_close).abs());

        (plus_dm, minus_dm, tr)
    }

    fn wilder_step(&mut self, high: f64, low: f64) {
        let (plus_dm, minus_dm, tr) = self.compute_dm_tr(high, low);
        let w = self.window as f64;
        // Wilder smoothing: new = prev - prev/N + current
        self.smoothed_plus_dm = self.smoothed_plus_dm - self.smoothed_plus_dm / w + plus_dm;
        self.smoothed_minus_dm = self.smoothed_minus_dm - self.smoothed_minus_dm / w + minus_dm;
        self.smoothed_tr = self.smoothed_tr - self.smoothed_tr / w + tr;
    }

    fn compute_di_dx(&self) -> (f64, f64, f64) {
        let di_pos = if self.smoothed_tr > 0.0 {
            self.smoothed_plus_dm / self.smoothed_tr * 100.0
        } else {
            0.0
        };
        let di_neg = if self.smoothed_tr > 0.0 {
            self.smoothed_minus_dm / self.smoothed_tr * 100.0
        } else {
            0.0
        };
        let di_sum = di_pos + di_neg;
        let dx = if di_sum > 0.0 {
            (di_pos - di_neg).abs() / di_sum * 100.0
        } else {
            0.0
        };
        (di_pos, di_neg, dx)
    }
}

#[cfg(test)]
mod tests {
    use super::AdxIndicator;

    #[test]
    fn zero_window_returns_zero_without_nan() {
        let mut adx = AdxIndicator::new(0);
        let first = adx.update(101.0, 99.0, 100.0);
        assert_eq!(first.adx, 0.0);
        assert_eq!(first.adx_pos, 0.0);
        assert_eq!(first.adx_neg, 0.0);

        for _ in 0..8 {
            let out = adx.update(102.0, 98.0, 100.0);
            assert_eq!(out.adx, 0.0);
            assert_eq!(out.adx_pos, 0.0);
            assert_eq!(out.adx_neg, 0.0);
            assert!(out.adx.is_finite());
            assert!(out.adx_pos.is_finite());
            assert!(out.adx_neg.is_finite());
        }
    }

    #[test]
    fn non_finite_inputs_are_skipped_without_poisoning_state() {
        let mut adx = AdxIndicator::new(3);
        let _ = adx.update(100.0, 99.0, 99.5);
        let _ = adx.update(101.0, 99.5, 100.5);
        let _ = adx.update(102.0, 100.0, 101.0);
        let prev = adx.update(103.0, 100.5, 102.0);

        let after_nan = adx.update(f64::NAN, 101.0, 102.0);
        assert_eq!(after_nan.adx, prev.adx);
        assert!(after_nan.adx.is_finite());
        assert!(after_nan.adx_pos.is_finite());
        assert!(after_nan.adx_neg.is_finite());

        let after_inf = adx.update(104.0, f64::INFINITY, 103.0);
        assert_eq!(after_inf.adx, prev.adx);
        assert!(after_inf.adx.is_finite());
        assert!(after_inf.adx_pos.is_finite());
        assert!(after_inf.adx_neg.is_finite());

        let after_valid = adx.update(104.0, 102.0, 103.5);
        assert!(after_valid.adx.is_finite());
        assert!(after_valid.adx_pos.is_finite());
        assert!(after_valid.adx_neg.is_finite());
    }
}
