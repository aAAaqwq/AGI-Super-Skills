//! Canonical, enumerated reason codes for trade log records.
//!
//! These codes are intended to be stable across releases and suitable for downstream analytics
//! (JSON reports, CSV exports, dashboards). They intentionally do not encode strategy-specific
//! free-form text.

use serde::Serialize;

/// Canonical reason code for a trade log record.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ReasonCode {
    // Entries / position changes
    EntrySignal,
    EntrySignalSubBar,
    EntryPyramid,

    // Exits
    ExitStopLoss,
    ExitTakeProfit,
    ExitTrailingStop,
    ExitSignalFlip,
    ExitFilter,
    ExitFunding,
    ExitForceClose,
    ExitEndOfBacktest,

    // Non-trade balance events
    FundingPayment,

    Unknown,
}

/// Classify a (action, reason) pair into a stable [`ReasonCode`].
pub fn classify_reason_code(action: &str, reason: &str) -> ReasonCode {
    if action == "FUNDING" {
        return ReasonCode::FundingPayment;
    }

    // Entries
    if action.starts_with("OPEN_") {
        if reason.contains("sub-bar") {
            return ReasonCode::EntrySignalSubBar;
        }
        return ReasonCode::EntrySignal;
    }
    if action.starts_with("ADD_") {
        return ReasonCode::EntryPyramid;
    }

    // Exits (includes partial exits via REDUCE_*)
    if action.starts_with("CLOSE_") || action.starts_with("REDUCE_") {
        if reason.contains("Stop Loss") {
            return ReasonCode::ExitStopLoss;
        }
        if reason.contains("Trailing Stop") {
            return ReasonCode::ExitTrailingStop;
        }
        if reason.contains("Take Profit") {
            return ReasonCode::ExitTakeProfit;
        }
        if reason.contains("Signal Flip") {
            return ReasonCode::ExitSignalFlip;
        }
        if reason.contains("Funding") {
            return ReasonCode::ExitFunding;
        }
        if reason.contains("Force Close") {
            return ReasonCode::ExitForceClose;
        }
        if reason.contains("End of Backtest") {
            return ReasonCode::ExitEndOfBacktest;
        }
        return ReasonCode::ExitFilter;
    }

    ReasonCode::Unknown
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn classify_entries() {
        assert_eq!(
            classify_reason_code("OPEN_LONG", "High entry"),
            ReasonCode::EntrySignal
        );
        assert_eq!(
            classify_reason_code("OPEN_SHORT", "High entry (sub-bar)"),
            ReasonCode::EntrySignalSubBar
        );
        assert_eq!(
            classify_reason_code("ADD_LONG", "Pyramid #1"),
            ReasonCode::EntryPyramid
        );
    }

    #[test]
    fn classify_exits() {
        assert_eq!(
            classify_reason_code("CLOSE_LONG", "Stop Loss"),
            ReasonCode::ExitStopLoss
        );
        assert_eq!(
            classify_reason_code("CLOSE_LONG", "Trailing Stop"),
            ReasonCode::ExitTrailingStop
        );
        assert_eq!(
            classify_reason_code("REDUCE_LONG", "Take Profit (Partial)"),
            ReasonCode::ExitTakeProfit
        );
        assert_eq!(
            classify_reason_code("CLOSE_SHORT", "Signal Flip"),
            ReasonCode::ExitSignalFlip
        );
        assert_eq!(
            classify_reason_code("CLOSE_SHORT", "Funding Headwind"),
            ReasonCode::ExitFunding
        );
        assert_eq!(
            classify_reason_code("CLOSE_SHORT", "End of Backtest"),
            ReasonCode::ExitEndOfBacktest
        );
        assert_eq!(
            classify_reason_code("CLOSE_SHORT", "Trend Breakdown"),
            ReasonCode::ExitFilter
        );
    }

    #[test]
    fn classify_funding_payment() {
        assert_eq!(
            classify_reason_code("FUNDING", "Funding rate=0.0001"),
            ReasonCode::FundingPayment
        );
    }
}
