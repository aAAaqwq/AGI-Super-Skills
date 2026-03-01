use super::RingBuf;

/// Volume SMA — simple moving average of volume.
#[derive(Debug, Clone)]
pub struct VolSma {
    ring: RingBuf,
}

impl VolSma {
    pub fn new(window: usize) -> Self {
        Self {
            ring: RingBuf::new(window),
        }
    }

    pub fn update(&mut self, volume: f64) -> f64 {
        self.ring.push(volume);
        self.ring.mean()
    }
}

/// Volume Trend — true if short-window SMA of volume > long-window SMA of volume.
///
/// Matches Python: `df["Volume"].rolling(vol_trend_window).mean() > df["vol_sma"]`
/// where vol_sma = Volume.rolling(vol_sma_window).mean().
#[derive(Debug, Clone)]
pub struct VolTrend {
    ring: RingBuf,
}

impl VolTrend {
    pub fn new(window: usize) -> Self {
        Self {
            ring: RingBuf::new(window),
        }
    }

    /// Feed current volume, return short-window SMA (to be compared against vol_sma by caller).
    pub fn update(&mut self, volume: f64) -> f64 {
        self.ring.push(volume);
        self.ring.mean()
    }
}
