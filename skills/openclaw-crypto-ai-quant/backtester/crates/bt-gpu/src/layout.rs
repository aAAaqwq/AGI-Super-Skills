//! Combo generation, VRAM batching, and result collection.

/// High-level result for one sweep combo.
#[derive(Debug, Clone)]
pub struct GpuSweepResult {
    pub config_id: String,
    pub output_mode: String,
    pub total_pnl: f64,
    pub final_balance: f64,
    pub total_trades: u32,
    pub total_wins: u32,
    pub win_rate: f64,
    pub profit_factor: f64,
    pub max_drawdown_pct: f64,
    pub overrides: Vec<(String, f64)>,
}

/// Wrapper for BinaryHeap min-heap ordering by PnL.
/// BinaryHeap is a max-heap; reversed comparison puts lowest PnL at root
/// so we can evict the worst result when capacity is exceeded.
#[derive(Debug, Clone)]
pub struct MinPnlHeapEntry(pub GpuSweepResult);

#[inline]
fn pnl_key(v: f64) -> f64 {
    if v.is_nan() {
        f64::NEG_INFINITY
    } else {
        v
    }
}

impl Eq for MinPnlHeapEntry {}

impl PartialEq for MinPnlHeapEntry {
    fn eq(&self, other: &Self) -> bool {
        pnl_key(self.0.total_pnl) == pnl_key(other.0.total_pnl)
    }
}

impl PartialOrd for MinPnlHeapEntry {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for MinPnlHeapEntry {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        // Reversed: lowest PnL = greatest in heap ordering (evicted first by pop)
        // NaN treated as NEG_INFINITY (worst possible)
        let a = pnl_key(self.0.total_pnl);
        let b = pnl_key(other.0.total_pnl);
        b.partial_cmp(&a).unwrap_or(std::cmp::Ordering::Equal)
    }
}

#[cfg(test)]
mod tests {
    use std::collections::BinaryHeap;

    use super::{GpuSweepResult, MinPnlHeapEntry};

    fn result_with_pnl(pnl: f64) -> GpuSweepResult {
        GpuSweepResult {
            config_id: "cfg".to_string(),
            output_mode: "summary".to_string(),
            total_pnl: pnl,
            final_balance: 0.0,
            total_trades: 0,
            total_wins: 0,
            win_rate: 0.0,
            profit_factor: 0.0,
            max_drawdown_pct: 0.0,
            overrides: Vec::new(),
        }
    }

    #[test]
    fn min_pnl_entry_eq_is_reflexive_for_nan() {
        let a = MinPnlHeapEntry(result_with_pnl(f64::NAN));
        assert_eq!(a, a);
    }

    #[test]
    fn heap_peek_returns_lowest_pnl_entry() {
        let mut heap: BinaryHeap<MinPnlHeapEntry> = BinaryHeap::new();
        heap.push(MinPnlHeapEntry(result_with_pnl(20.0)));
        heap.push(MinPnlHeapEntry(result_with_pnl(10.0)));
        heap.push(MinPnlHeapEntry(result_with_pnl(15.0)));

        let top = heap.peek().expect("heap should not be empty");
        assert_eq!(top.0.total_pnl, 10.0);
    }

    #[test]
    fn nan_is_treated_as_worst_pnl() {
        let mut heap: BinaryHeap<MinPnlHeapEntry> = BinaryHeap::new();
        heap.push(MinPnlHeapEntry(result_with_pnl(10.0)));
        heap.push(MinPnlHeapEntry(result_with_pnl(f64::NAN)));

        let top = heap.peek().expect("heap should not be empty");
        assert!(top.0.total_pnl.is_nan());
    }
}
