//! Statistics and JSON reporting for simulation results.
//!
//! Computes summary statistics (win rate, profit factor, Sharpe, drawdown)
//! and breakdowns by confidence / exit reason / symbol / side from the
//! trade log produced by the simulation engine.

use serde::Serialize;
use std::collections::BTreeMap;

use crate::config::Confidence;
use crate::engine::DecisionKernelTrace;
use crate::engine::GateStats;
use crate::position::{SignalRecord, TradeRecord};
use crate::reason_codes::{classify_reason_code, ReasonCode};

// ---------------------------------------------------------------------------
// Report types (all Serialize for JSON output)
// ---------------------------------------------------------------------------

/// Full simulation report, serializable to JSON.
#[derive(Debug, Clone, Serialize)]
pub struct SimReport {
    pub config_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub config_fingerprint: Option<String>,

    // Summary
    pub initial_balance: f64,
    pub final_balance: f64,
    pub total_pnl: f64,
    pub total_trades: u32,
    pub total_wins: u32,
    pub total_losses: u32,
    pub win_rate: f64,
    pub profit_factor: f64,
    pub sharpe_ratio: f64,
    pub max_drawdown_usd: f64,
    pub max_drawdown_pct: f64,
    pub avg_trade_pnl: f64,
    pub avg_win: f64,
    pub avg_loss: f64,
    pub total_fees: f64,
    pub total_signals: u32,
    pub neutral_pct: f64,

    // Breakdowns
    pub by_confidence: Vec<ConfidenceBucket>,
    pub by_exit_reason: Vec<ExitBucket>,
    pub by_reason_code: Vec<ReasonCodeBucket>,
    pub by_symbol: Vec<SymbolBucket>,
    pub by_side: Vec<SideBucket>,

    // Gate stats
    pub gate_stats: GateStatsReport,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub decision_diagnostics: Option<Vec<DecisionKernelTrace>>,

    // Optional (large payloads, gated by flags)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub equity_curve: Option<Vec<(i64, f64)>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trades: Option<Vec<TradeReportEntry>>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ConfidenceBucket {
    pub confidence: String,
    pub trades: u32,
    pub pnl: f64,
    pub win_rate: f64,
    pub avg_pnl: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct ExitBucket {
    pub reason: String,
    pub trades: u32,
    pub pnl: f64,
    pub win_rate: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct ReasonCodeBucket {
    pub reason_code: ReasonCode,
    pub trades: u32,
    pub pnl: f64,
    pub win_rate: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct SymbolBucket {
    pub symbol: String,
    pub trades: u32,
    pub pnl: f64,
    pub win_rate: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct SideBucket {
    pub side: String, // "LONG" or "SHORT"
    pub trades: u32,
    pub pnl: f64,
    pub win_rate: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct TradeReportEntry {
    pub timestamp: i64,
    pub symbol: String,
    pub action: String,
    pub price: f64,
    pub size: f64,
    pub pnl: f64,
    pub fee: f64,
    pub reason: String,
    pub reason_code: ReasonCode,
    pub confidence: String,
    pub balance: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct GateStatsReport {
    pub total_checks: u64,
    pub signals_generated: u64,
    pub signal_pct: f64,
    pub blocked_by_ranging: u64,
    pub blocked_by_anomaly: u64,
    pub blocked_by_extension: u64,
    pub blocked_by_adx_low: u64,
    pub blocked_by_adx_not_rising: u64,
    pub blocked_by_volume: u64,
    pub blocked_by_btc: u64,
    pub blocked_by_confidence: u64,
    pub blocked_by_max_positions: u64,
    pub blocked_by_pesc: u64,
    pub blocked_by_ssf: u64,
    pub blocked_by_reef: u64,
    pub blocked_by_margin: u64,
}

// ---------------------------------------------------------------------------
// build_report
// ---------------------------------------------------------------------------

/// Build a full simulation report from trade log, signal log, and equity curve.
///
/// # Arguments
/// * `trades`               — All trade records (opens, closes, adds, reduces).
/// * `signals`              — Raw signal audit trail.
/// * `equity_curve`         — `(timestamp_ms, balance)` pairs sampled per bar.
/// * `gate_stats`           — Accumulated gate-filter counters.
/// * `initial_balance`      — Starting USD balance.
/// * `final_balance`        — Ending USD balance.
/// * `config_id`            — Identifier string for this config variant.
/// * `include_trades`       — If true, embed per-trade detail in the report.
/// * `include_equity_curve` — If true, embed the full equity curve.
pub struct BuildReportInput<'a> {
    pub trades: &'a [TradeRecord],
    pub signals: &'a [SignalRecord],
    pub equity_curve: &'a [(i64, f64)],
    pub gate_stats: &'a GateStats,
    pub initial_balance: f64,
    pub final_balance: f64,
    pub config_id: &'a str,
    pub include_trades: bool,
    pub include_equity_curve: bool,
}

pub fn build_report(input: BuildReportInput<'_>) -> SimReport {
    let BuildReportInput {
        trades,
        signals,
        equity_curve,
        gate_stats,
        initial_balance,
        final_balance,
        config_id,
        include_trades,
        include_equity_curve,
    } = input;
    // ── Separate closes from all trade records ───────────────────────────
    let closes: Vec<&TradeRecord> = trades.iter().filter(|t| t.is_close()).collect();
    let total_trades = closes.len() as u32;

    // ── Win/loss counts and gross profit/loss ────────────────────────────
    let mut total_wins: u32 = 0;
    let mut total_losses: u32 = 0;
    let mut gross_profit: f64 = 0.0;
    let mut gross_loss: f64 = 0.0;

    for tr in &closes {
        if tr.pnl > 0.0 {
            total_wins += 1;
            gross_profit += tr.pnl;
        } else if tr.pnl < 0.0 {
            total_losses += 1;
            gross_loss += tr.pnl; // negative
        }
    }

    let total_fees: f64 = trades.iter().map(|t| t.fee_usd).sum();
    let total_pnl = final_balance - initial_balance;

    let win_rate = if total_trades > 0 {
        total_wins as f64 / total_trades as f64
    } else {
        0.0
    };

    let profit_factor = if gross_loss.abs() > 1e-12 {
        gross_profit / gross_loss.abs()
    } else if gross_profit > 0.0 {
        f64::INFINITY
    } else {
        0.0
    };

    let avg_trade_pnl = if total_trades > 0 {
        closes.iter().map(|t| t.pnl).sum::<f64>() / total_trades as f64
    } else {
        0.0
    };
    let avg_win = if total_wins > 0 {
        gross_profit / total_wins as f64
    } else {
        0.0
    };
    let avg_loss = if total_losses > 0 {
        gross_loss / total_losses as f64 // negative
    } else {
        0.0
    };

    // ── Sharpe ratio (annualised, daily returns) ─────────────────────────
    let sharpe_ratio = compute_sharpe(equity_curve);

    // ── Max drawdown ─────────────────────────────────────────────────────
    let (max_dd_usd, max_dd_pct) = compute_max_drawdown(equity_curve);

    // ── Signal stats ─────────────────────────────────────────────────────
    let total_signals = signals.len() as u32;
    let neutral_count = signals
        .iter()
        .filter(|s| s.signal == crate::config::Signal::Neutral)
        .count() as u32;
    let neutral_pct = if total_signals > 0 {
        neutral_count as f64 / total_signals as f64
    } else {
        0.0
    };

    // ── Breakdowns ───────────────────────────────────────────────────────
    let by_confidence = build_confidence_breakdown(&closes);
    let by_exit_reason = build_exit_reason_breakdown(&closes);
    let by_reason_code = build_reason_code_breakdown(&closes);
    let by_symbol = build_symbol_breakdown(&closes);
    let by_side = build_side_breakdown(&closes);

    // ── Gate stats report ────────────────────────────────────────────────
    let signals_generated = gate_stats.buy_count + gate_stats.sell_count;
    let gate_report = GateStatsReport {
        total_checks: gate_stats.total_checks,
        signals_generated,
        signal_pct: if gate_stats.total_checks > 0 {
            signals_generated as f64 / gate_stats.total_checks as f64
        } else {
            0.0
        },
        blocked_by_ranging: gate_stats.blocked_by_ranging,
        blocked_by_anomaly: gate_stats.blocked_by_anomaly,
        blocked_by_extension: gate_stats.blocked_by_extension,
        blocked_by_adx_low: gate_stats.blocked_by_adx_low,
        blocked_by_adx_not_rising: gate_stats.blocked_by_adx_not_rising,
        blocked_by_volume: gate_stats.blocked_by_volume,
        blocked_by_btc: gate_stats.blocked_by_btc,
        blocked_by_confidence: gate_stats.blocked_by_confidence,
        blocked_by_max_positions: gate_stats.blocked_by_max_positions,
        blocked_by_pesc: gate_stats.blocked_by_pesc,
        blocked_by_ssf: gate_stats.blocked_by_ssf,
        blocked_by_reef: gate_stats.blocked_by_reef,
        blocked_by_margin: gate_stats.blocked_by_margin,
    };

    // ── Optional per-trade detail ────────────────────────────────────────
    let trade_entries = if include_trades {
        Some(
            trades
                .iter()
                .map(|tr| TradeReportEntry {
                    timestamp: tr.timestamp_ms,
                    symbol: tr.symbol.clone(),
                    action: tr.action.clone(),
                    price: tr.price,
                    size: tr.size,
                    pnl: tr.pnl,
                    fee: tr.fee_usd,
                    reason: tr.reason.clone(),
                    reason_code: classify_reason_code(&tr.action, &tr.reason),
                    confidence: tr.confidence.to_string(),
                    balance: tr.balance,
                })
                .collect(),
        )
    } else {
        None
    };

    let eq_curve = if include_equity_curve {
        Some(equity_curve.to_vec())
    } else {
        None
    };

    SimReport {
        config_id: config_id.to_string(),
        config_fingerprint: None,
        initial_balance,
        final_balance,
        total_pnl,
        total_trades,
        total_wins,
        total_losses,
        win_rate,
        profit_factor,
        sharpe_ratio,
        max_drawdown_usd: max_dd_usd,
        max_drawdown_pct: max_dd_pct,
        avg_trade_pnl,
        avg_win,
        avg_loss,
        total_fees,
        total_signals,
        neutral_pct,
        by_confidence,
        by_exit_reason,
        by_reason_code,
        by_symbol,
        by_side,
        gate_stats: gate_report,
        decision_diagnostics: None,
        equity_curve: eq_curve,
        trades: trade_entries,
    }
}

// ---------------------------------------------------------------------------
// Sharpe ratio
// ---------------------------------------------------------------------------

/// Annualised Sharpe ratio from an equity curve.
///
/// Uses daily returns: `mean(daily) / std(daily) * sqrt(365)`.
/// Returns 0.0 if fewer than 2 data points or zero variance.
fn compute_sharpe(equity_curve: &[(i64, f64)]) -> f64 {
    if equity_curve.len() < 2 {
        return 0.0;
    }

    // Bucket equity snapshots by calendar day (ms → day index).
    let ms_per_day: i64 = 86_400_000;
    let mut daily_balances: Vec<(i64, f64)> = Vec::new();

    for &(ts, bal) in equity_curve {
        let day = ts / ms_per_day;
        match daily_balances.last_mut() {
            Some(last) if last.0 == day => {
                last.1 = bal; // keep last balance of each day
            }
            _ => {
                daily_balances.push((day, bal));
            }
        }
    }

    if daily_balances.len() < 2 {
        return 0.0;
    }

    let returns: Vec<f64> = daily_balances
        .windows(2)
        .map(|w| {
            let prev = w[0].1;
            if prev.abs() > 1e-12 {
                (w[1].1 - prev) / prev
            } else {
                0.0
            }
        })
        .collect();

    if returns.is_empty() {
        return 0.0;
    }

    let n = returns.len() as f64;
    let mean = returns.iter().sum::<f64>() / n;
    let variance = returns.iter().map(|r| (r - mean).powi(2)).sum::<f64>() / n;
    let std_dev = variance.sqrt();

    if std_dev < 1e-12 {
        return 0.0;
    }

    (mean / std_dev) * 365.0_f64.sqrt()
}

// ---------------------------------------------------------------------------
// Max drawdown
// ---------------------------------------------------------------------------

/// Maximum drawdown in USD and as a fraction of peak equity.
fn compute_max_drawdown(equity_curve: &[(i64, f64)]) -> (f64, f64) {
    if equity_curve.is_empty() {
        return (0.0, 0.0);
    }

    let mut peak = equity_curve[0].1;
    let mut max_dd_usd: f64 = 0.0;
    let mut max_dd_pct: f64 = 0.0;

    for &(_ts, bal) in equity_curve {
        if bal > peak {
            peak = bal;
        }
        let dd = peak - bal;
        if dd > max_dd_usd {
            max_dd_usd = dd;
        }
        let dd_pct = if peak > 1e-12 { dd / peak } else { 0.0 };
        if dd_pct > max_dd_pct {
            max_dd_pct = dd_pct;
        }
    }

    (max_dd_usd, max_dd_pct)
}

// ---------------------------------------------------------------------------
// Breakdown builders
// ---------------------------------------------------------------------------

fn build_confidence_breakdown(closes: &[&TradeRecord]) -> Vec<ConfidenceBucket> {
    let mut map: BTreeMap<u8, (String, u32, f64, u32)> = BTreeMap::new();

    for tr in closes {
        let key = confidence_sort_key(&tr.confidence);
        let entry = map
            .entry(key)
            .or_insert_with(|| (tr.confidence.to_string(), 0, 0.0, 0));
        entry.1 += 1;
        entry.2 += tr.pnl;
        if tr.pnl > 0.0 {
            entry.3 += 1;
        }
    }

    map.into_values()
        .map(|(conf, count, pnl, wins)| ConfidenceBucket {
            confidence: conf,
            trades: count,
            pnl,
            win_rate: if count > 0 {
                wins as f64 / count as f64
            } else {
                0.0
            },
            avg_pnl: if count > 0 { pnl / count as f64 } else { 0.0 },
        })
        .collect()
}

fn confidence_sort_key(c: &Confidence) -> u8 {
    match c {
        Confidence::Low => 0,
        Confidence::Medium => 1,
        Confidence::High => 2,
    }
}

fn build_exit_reason_breakdown(closes: &[&TradeRecord]) -> Vec<ExitBucket> {
    let mut map: BTreeMap<String, (u32, f64, u32)> = BTreeMap::new();

    for tr in closes {
        let reason = categorize_exit(&tr.reason);
        let entry = map.entry(reason).or_insert((0, 0.0, 0));
        entry.0 += 1;
        entry.1 += tr.pnl;
        if tr.pnl > 0.0 {
            entry.2 += 1;
        }
    }

    map.into_iter()
        .map(|(reason, (count, pnl, wins))| ExitBucket {
            reason,
            trades: count,
            pnl,
            win_rate: if count > 0 {
                wins as f64 / count as f64
            } else {
                0.0
            },
        })
        .collect()
}

fn build_reason_code_breakdown(closes: &[&TradeRecord]) -> Vec<ReasonCodeBucket> {
    let mut map: BTreeMap<ReasonCode, (u32, f64, u32)> = BTreeMap::new();

    for tr in closes {
        let code = classify_reason_code(&tr.action, &tr.reason);
        let entry = map.entry(code).or_insert((0, 0.0, 0));
        entry.0 += 1;
        entry.1 += tr.pnl;
        if tr.pnl > 0.0 {
            entry.2 += 1;
        }
    }

    map.into_iter()
        .map(|(reason_code, (trades, pnl, wins))| ReasonCodeBucket {
            reason_code,
            trades,
            pnl,
            win_rate: if trades > 0 {
                wins as f64 / trades as f64
            } else {
                0.0
            },
        })
        .collect()
}

/// Normalise exit reason strings into canonical categories.
fn categorize_exit(reason: &str) -> String {
    if reason.contains("Stop Loss") {
        return "Stop Loss".to_string();
    }
    if reason.contains("Trailing Stop") {
        return "Trailing Stop".to_string();
    }
    if reason.contains("Take Profit") {
        return "Take Profit".to_string();
    }
    if reason.contains("Signal Flip") {
        return "Signal Flip".to_string();
    }
    if reason.contains("Trend Breakdown") {
        return "Trend Breakdown".to_string();
    }
    if reason.contains("Trend Exhaustion") {
        return "Trend Exhaustion".to_string();
    }
    if reason.contains("EMA Macro") {
        return "EMA Macro Breakdown".to_string();
    }
    if reason.contains("Stagnation") {
        return "Stagnation Exit".to_string();
    }
    if reason.contains("RSI Over") {
        return "RSI Overextension".to_string();
    }
    if reason.contains("TSME") || reason.contains("Saturation") {
        return "TSME".to_string();
    }
    if reason.contains("MMDE") || reason.contains("Divergence") {
        return "MMDE".to_string();
    }
    if reason.contains("Funding") {
        return "Funding Headwind".to_string();
    }
    if reason.contains("Force Close") {
        return "Force Close (EOD)".to_string();
    }
    reason.to_string()
}

fn build_symbol_breakdown(closes: &[&TradeRecord]) -> Vec<SymbolBucket> {
    let mut map: BTreeMap<String, (u32, f64, u32)> = BTreeMap::new();

    for tr in closes {
        let entry = map.entry(tr.symbol.clone()).or_insert((0, 0.0, 0));
        entry.0 += 1;
        entry.1 += tr.pnl;
        if tr.pnl > 0.0 {
            entry.2 += 1;
        }
    }

    map.into_iter()
        .map(|(symbol, (count, pnl, wins))| SymbolBucket {
            symbol,
            trades: count,
            pnl,
            win_rate: if count > 0 {
                wins as f64 / count as f64
            } else {
                0.0
            },
        })
        .collect()
}

fn build_side_breakdown(closes: &[&TradeRecord]) -> Vec<SideBucket> {
    let mut map: BTreeMap<String, (u32, f64, u32)> = BTreeMap::new();

    for tr in closes {
        let side = if tr.action.contains("LONG") {
            "LONG"
        } else if tr.action.contains("SHORT") {
            "SHORT"
        } else {
            "UNKNOWN"
        };
        let entry = map.entry(side.to_string()).or_insert((0, 0.0, 0));
        entry.0 += 1;
        entry.1 += tr.pnl;
        if tr.pnl > 0.0 {
            entry.2 += 1;
        }
    }

    map.into_iter()
        .map(|(side, (count, pnl, wins))| SideBucket {
            side,
            trades: count,
            pnl,
            win_rate: if count > 0 {
                wins as f64 / count as f64
            } else {
                0.0
            },
        })
        .collect()
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{Confidence, Signal};
    use crate::engine::GateStats;

    fn make_close(
        symbol: &str,
        pnl: f64,
        reason: &str,
        conf: Confidence,
        action: &str,
    ) -> TradeRecord {
        TradeRecord {
            timestamp_ms: 1_000_000,
            symbol: symbol.to_string(),
            action: action.to_string(),
            price: 100.0,
            size: 0.1,
            notional: 10.0,
            reason: reason.to_string(),
            confidence: conf,
            pnl,
            fee_usd: 0.01,
            balance: 10000.0 + pnl,
            entry_atr: 1.0,
            leverage: 3.0,
            margin_used: 3.33,
            mae_usd: 0.0,
            mfe_usd: 0.0,
            exit_context: None,
        }
    }

    fn make_signal(signal: Signal) -> SignalRecord {
        SignalRecord {
            timestamp_ms: 0,
            symbol: "ETH".to_string(),
            signal,
            confidence: Confidence::Medium,
            price: 100.0,
            adx: 30.0,
            rsi: 55.0,
            atr: 1.5,
        }
    }

    #[test]
    fn test_empty_report() {
        let report = build_report(BuildReportInput {
            trades: &[],
            signals: &[],
            equity_curve: &[],
            gate_stats: &GateStats::default(),
            initial_balance: 10000.0,
            final_balance: 10000.0,
            config_id: "test",
            include_trades: false,
            include_equity_curve: false,
        });
        assert_eq!(report.total_trades, 0);
        assert_eq!(report.win_rate, 0.0);
        assert_eq!(report.total_pnl, 0.0);
        assert!(report.by_confidence.is_empty());
        assert!(report.by_side.is_empty());
    }

    #[test]
    fn test_win_rate_and_profit_factor() {
        let trades = vec![
            make_close("ETH", 10.0, "Take Profit", Confidence::High, "CLOSE_LONG"),
            make_close("ETH", 5.0, "Take Profit", Confidence::Medium, "CLOSE_LONG"),
            make_close("BTC", -3.0, "Stop Loss", Confidence::Low, "CLOSE_SHORT"),
            make_close("BTC", -2.0, "Stop Loss", Confidence::Low, "CLOSE_SHORT"),
        ];
        let report = build_report(BuildReportInput {
            trades: &trades,
            signals: &[],
            equity_curve: &[],
            gate_stats: &GateStats::default(),
            initial_balance: 10000.0,
            final_balance: 10010.0,
            config_id: "test",
            include_trades: false,
            include_equity_curve: false,
        });
        assert_eq!(report.total_trades, 4);
        assert_eq!(report.total_wins, 2);
        assert_eq!(report.total_losses, 2);
        assert!((report.win_rate - 0.5).abs() < 1e-9);
        // profit_factor = 15.0 / 5.0 = 3.0
        assert!((report.profit_factor - 3.0).abs() < 1e-9);
    }

    #[test]
    fn test_avg_win_and_avg_loss() {
        let trades = vec![
            make_close("ETH", 10.0, "TP", Confidence::High, "CLOSE_LONG"),
            make_close("ETH", 6.0, "TP", Confidence::High, "CLOSE_LONG"),
            make_close("ETH", -4.0, "SL", Confidence::Low, "CLOSE_SHORT"),
        ];
        let report = build_report(BuildReportInput {
            trades: &trades,
            signals: &[],
            equity_curve: &[],
            gate_stats: &GateStats::default(),
            initial_balance: 10000.0,
            final_balance: 10012.0,
            config_id: "test",
            include_trades: false,
            include_equity_curve: false,
        });
        assert!((report.avg_win - 8.0).abs() < 1e-9);
        assert!((report.avg_loss - (-4.0)).abs() < 1e-9);
    }

    #[test]
    fn test_max_drawdown() {
        let curve = vec![
            (0, 10000.0),
            (1, 10500.0), // peak
            (2, 9800.0),  // trough: dd = 700
            (3, 10200.0),
            (4, 10600.0), // new peak
            (5, 10100.0), // dd = 500
        ];
        let (dd_usd, dd_pct) = compute_max_drawdown(&curve);
        assert!((dd_usd - 700.0).abs() < 1e-9);
        assert!((dd_pct - 700.0 / 10500.0).abs() < 1e-9);
    }

    #[test]
    fn test_sharpe_flat_curve() {
        let curve = vec![(0, 10000.0), (86_400_000, 10000.0), (172_800_000, 10000.0)];
        let sharpe = compute_sharpe(&curve);
        assert_eq!(sharpe, 0.0);
    }

    #[test]
    fn test_sharpe_positive() {
        // Increasing curve with varying daily returns to avoid zero std_dev.
        // Day 0->1: +1%, Day 1->2: +2%, Day 2->3: +0.5%
        // All positive returns -> positive mean, nonzero std -> positive Sharpe.
        let curve = vec![
            (0, 10000.0),
            (86_400_000, 10100.0),
            (172_800_000, 10302.0),
            (259_200_000, 10353.51),
        ];
        let sharpe = compute_sharpe(&curve);
        assert!(
            sharpe > 0.0,
            "Steadily increasing curve should have positive Sharpe"
        );
    }

    #[test]
    fn test_neutral_pct() {
        let signals = vec![
            make_signal(Signal::Buy),
            make_signal(Signal::Neutral),
            make_signal(Signal::Neutral),
            make_signal(Signal::Sell),
        ];
        let report = build_report(BuildReportInput {
            trades: &[],
            signals: &signals,
            equity_curve: &[],
            gate_stats: &GateStats::default(),
            initial_balance: 10000.0,
            final_balance: 10000.0,
            config_id: "test",
            include_trades: false,
            include_equity_curve: false,
        });
        assert!((report.neutral_pct - 0.5).abs() < 1e-9);
        assert_eq!(report.total_signals, 4);
    }

    #[test]
    fn test_confidence_breakdown() {
        let trades = vec![
            make_close("ETH", 10.0, "TP", Confidence::High, "CLOSE_LONG"),
            make_close("ETH", -3.0, "SL", Confidence::High, "CLOSE_LONG"),
            make_close("ETH", 2.0, "TP", Confidence::Low, "CLOSE_LONG"),
        ];
        let report = build_report(BuildReportInput {
            trades: &trades,
            signals: &[],
            equity_curve: &[],
            gate_stats: &GateStats::default(),
            initial_balance: 10000.0,
            final_balance: 10009.0,
            config_id: "test",
            include_trades: false,
            include_equity_curve: false,
        });
        assert_eq!(report.by_confidence.len(), 2);
        // low (sort key 0) first, then high (sort key 2)
        assert_eq!(report.by_confidence[0].confidence, "low");
        assert_eq!(report.by_confidence[0].trades, 1);
        assert!((report.by_confidence[0].win_rate - 1.0).abs() < 1e-9);
        assert_eq!(report.by_confidence[1].confidence, "high");
        assert_eq!(report.by_confidence[1].trades, 2);
        assert!((report.by_confidence[1].win_rate - 0.5).abs() < 1e-9);
    }

    #[test]
    fn test_side_breakdown() {
        let trades = vec![
            make_close("ETH", 10.0, "TP", Confidence::High, "CLOSE_LONG"),
            make_close("ETH", -3.0, "SL", Confidence::High, "CLOSE_SHORT"),
        ];
        let report = build_report(BuildReportInput {
            trades: &trades,
            signals: &[],
            equity_curve: &[],
            gate_stats: &GateStats::default(),
            initial_balance: 10000.0,
            final_balance: 10007.0,
            config_id: "test",
            include_trades: false,
            include_equity_curve: false,
        });
        assert_eq!(report.by_side.len(), 2);
        // BTreeMap: LONG < SHORT alphabetically
        assert_eq!(report.by_side[0].side, "LONG");
        assert_eq!(report.by_side[1].side, "SHORT");
    }

    #[test]
    fn test_symbol_breakdown() {
        let trades = vec![
            make_close("BTC", 5.0, "TP", Confidence::High, "CLOSE_LONG"),
            make_close("ETH", -2.0, "SL", Confidence::High, "CLOSE_LONG"),
            make_close("ETH", 3.0, "TP", Confidence::High, "CLOSE_LONG"),
        ];
        let report = build_report(BuildReportInput {
            trades: &trades,
            signals: &[],
            equity_curve: &[],
            gate_stats: &GateStats::default(),
            initial_balance: 10000.0,
            final_balance: 10006.0,
            config_id: "test",
            include_trades: false,
            include_equity_curve: false,
        });
        assert_eq!(report.by_symbol.len(), 2);
        assert_eq!(report.by_symbol[0].symbol, "BTC");
        assert_eq!(report.by_symbol[0].trades, 1);
        assert_eq!(report.by_symbol[1].symbol, "ETH");
        assert_eq!(report.by_symbol[1].trades, 2);
    }

    #[test]
    fn test_exit_reason_categorization() {
        let trades = vec![
            make_close("ETH", -5.0, "Stop Loss Hit", Confidence::High, "CLOSE_LONG"),
            make_close(
                "ETH",
                8.0,
                "Take Profit Full",
                Confidence::High,
                "CLOSE_LONG",
            ),
            make_close("ETH", 3.0, "Trailing Stop", Confidence::High, "CLOSE_LONG"),
        ];
        let report = build_report(BuildReportInput {
            trades: &trades,
            signals: &[],
            equity_curve: &[],
            gate_stats: &GateStats::default(),
            initial_balance: 10000.0,
            final_balance: 10006.0,
            config_id: "test",
            include_trades: false,
            include_equity_curve: false,
        });
        assert_eq!(report.by_exit_reason.len(), 3);
        // BTreeMap alphabetical: "Stop Loss", "Take Profit", "Trailing Stop"
        assert_eq!(report.by_exit_reason[0].reason, "Stop Loss");
        assert_eq!(report.by_exit_reason[1].reason, "Take Profit");
        assert_eq!(report.by_exit_reason[2].reason, "Trailing Stop");
    }

    #[test]
    fn test_include_trades_flag() {
        let trades = vec![make_close(
            "ETH",
            10.0,
            "TP",
            Confidence::High,
            "CLOSE_LONG",
        )];
        let report_no = build_report(BuildReportInput {
            trades: &trades,
            signals: &[],
            equity_curve: &[],
            gate_stats: &GateStats::default(),
            initial_balance: 10000.0,
            final_balance: 10010.0,
            config_id: "test",
            include_trades: false,
            include_equity_curve: false,
        });
        assert!(report_no.trades.is_none());
        assert!(report_no.equity_curve.is_none());

        let report_yes = build_report(BuildReportInput {
            trades: &trades,
            signals: &[],
            equity_curve: &[],
            gate_stats: &GateStats::default(),
            initial_balance: 10000.0,
            final_balance: 10010.0,
            config_id: "test",
            include_trades: true,
            include_equity_curve: true,
        });
        assert!(report_yes.trades.is_some());
        assert_eq!(report_yes.trades.unwrap().len(), 1);
        // equity_curve was empty but still Some([])
        assert!(report_yes.equity_curve.is_some());
    }

    #[test]
    fn test_gate_stats_report() {
        let gs = GateStats {
            total_checks: 1000,
            neutral_count: 800,
            buy_count: 120,
            sell_count: 80,
            blocked_by_ranging: 100,
            blocked_by_anomaly: 50,
            blocked_by_extension: 30,
            blocked_by_adx_low: 120,
            blocked_by_adx_not_rising: 10,
            blocked_by_volume: 5,
            blocked_by_btc: 3,
            blocked_by_confidence: 80,
            blocked_by_max_positions: 20,
            blocked_by_pesc: 0,
            blocked_by_ssf: 0,
            blocked_by_reef: 0,
            blocked_by_margin: 0,
        };
        let report = build_report(BuildReportInput {
            trades: &[],
            signals: &[],
            equity_curve: &[],
            gate_stats: &gs,
            initial_balance: 10000.0,
            final_balance: 10000.0,
            config_id: "test",
            include_trades: false,
            include_equity_curve: false,
        });
        assert_eq!(report.gate_stats.total_checks, 1000);
        // signals_generated = buy_count + sell_count = 200
        assert_eq!(report.gate_stats.signals_generated, 200);
        assert!((report.gate_stats.signal_pct - 0.2).abs() < 1e-9);
        assert_eq!(report.gate_stats.blocked_by_ranging, 100);
    }

    #[test]
    fn test_profit_factor_no_losses() {
        let trades = vec![make_close(
            "ETH",
            10.0,
            "TP",
            Confidence::High,
            "CLOSE_LONG",
        )];
        let report = build_report(BuildReportInput {
            trades: &trades,
            signals: &[],
            equity_curve: &[],
            gate_stats: &GateStats::default(),
            initial_balance: 10000.0,
            final_balance: 10010.0,
            config_id: "test",
            include_trades: false,
            include_equity_curve: false,
        });
        assert!(report.profit_factor.is_infinite());
    }

    #[test]
    fn test_json_serialization() {
        let trades = vec![make_close("ETH", 5.0, "TP", Confidence::High, "CLOSE_LONG")];
        let report = build_report(BuildReportInput {
            trades: &trades,
            signals: &[],
            equity_curve: &[],
            gate_stats: &GateStats::default(),
            initial_balance: 10000.0,
            final_balance: 10005.0,
            config_id: "json_test",
            include_trades: false,
            include_equity_curve: false,
        });
        let json = serde_json::to_string(&report).expect("report should serialize to JSON");
        assert!(json.contains("\"config_id\":\"json_test\""));
        assert!(json.contains("\"total_wins\":1"));
        // equity_curve and per-trade detail array should be absent (skip_serializing_if)
        assert!(!json.contains("\"equity_curve\""));
        // The SimReport.trades field (Option<Vec<TradeReportEntry>>) should be skipped
        // when None. Note: the string "trades" still appears in ConfidenceBucket sub-objects
        // as a u32 field, so we check specifically for the trade detail array pattern.
        assert!(!json.contains("\"trades\":[{"));
    }
}
