//! Confidence level utilities.

use crate::Confidence;

impl Confidence {
    /// Ordering value used for min-confidence gating.
    ///
    /// `Low < Medium < High`
    #[inline]
    pub fn rank(self) -> u8 {
        match self {
            Confidence::Low => 0,
            Confidence::Medium => 1,
            Confidence::High => 2,
        }
    }

    /// Returns `true` if `self` meets or exceeds the required minimum.
    #[inline]
    pub fn meets_min(self, min: Confidence) -> bool {
        self.rank() >= min.rank()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rank_ordering() {
        assert!(Confidence::Low.rank() < Confidence::Medium.rank());
        assert!(Confidence::Medium.rank() < Confidence::High.rank());
    }

    #[test]
    fn test_meets_min() {
        assert!(Confidence::High.meets_min(Confidence::Low));
        assert!(Confidence::High.meets_min(Confidence::Medium));
        assert!(Confidence::High.meets_min(Confidence::High));
        assert!(Confidence::Medium.meets_min(Confidence::Low));
        assert!(Confidence::Medium.meets_min(Confidence::Medium));
        assert!(!Confidence::Medium.meets_min(Confidence::High));
        assert!(Confidence::Low.meets_min(Confidence::Low));
        assert!(!Confidence::Low.meets_min(Confidence::Medium));
    }
}
