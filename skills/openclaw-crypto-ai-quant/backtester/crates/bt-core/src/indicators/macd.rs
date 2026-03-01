use super::ema::Ema;

/// MACD — histogram = MACD_line - Signal_line.
/// Matches Python `ta.trend.MACD`.
#[derive(Debug, Clone)]
pub struct MacdIndicator {
    ema_fast: Ema,
    ema_slow: Ema,
    ema_signal: Ema,
    pub histogram: f64,
}

impl MacdIndicator {
    pub fn new(fast: usize, slow: usize, signal: usize) -> Self {
        Self {
            ema_fast: Ema::new(fast),
            ema_slow: Ema::new(slow),
            ema_signal: Ema::new(signal),
            histogram: 0.0,
        }
    }

    /// Feed one close price, return the MACD histogram value.
    pub fn update(&mut self, close: f64) -> f64 {
        let fast = self.ema_fast.update(close);
        let slow = self.ema_slow.update(close);
        let macd_line = fast - slow;
        let signal = self.ema_signal.update(macd_line);
        self.histogram = macd_line - signal;
        self.histogram
    }
}
