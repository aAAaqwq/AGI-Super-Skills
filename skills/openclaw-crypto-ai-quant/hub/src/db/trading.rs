use crate::error::HubError;
use rusqlite::{params, Connection};
use serde::Serialize;
use serde_json::Value;

// ── Types ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize)]
pub struct OpenPosition {
    pub symbol: String,
    #[serde(rename = "type")]
    pub pos_type: String,
    pub open_trade_id: i64,
    pub open_timestamp: Option<String>,
    pub entry_price: f64,
    pub size: f64,
    pub confidence: Option<String>,
    pub entry_atr: f64,
    pub leverage: f64,
    pub margin_used: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct RecentTrade {
    pub timestamp: Option<String>,
    pub symbol: String,
    #[serde(rename = "type")]
    pub trade_type: Option<String>,
    pub action: Option<String>,
    pub price: Option<f64>,
    pub size: Option<f64>,
    pub notional: Option<f64>,
    pub pnl: Option<f64>,
    pub fee_usd: Option<f64>,
    pub reason: Option<String>,
    pub confidence: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct RecentSignal {
    pub timestamp: Option<String>,
    pub symbol: String,
    pub signal: Option<String>,
    pub confidence: Option<String>,
    pub price: Option<f64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct LastSignal {
    pub timestamp: Option<String>,
    pub signal: Option<String>,
    pub confidence: Option<String>,
    pub price: Option<f64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct LastTrade {
    pub timestamp: Option<String>,
    #[serde(rename = "type")]
    pub trade_type: Option<String>,
    pub action: Option<String>,
    pub price: Option<f64>,
    pub size: Option<f64>,
    pub pnl: Option<f64>,
    pub reason: Option<String>,
    pub confidence: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct BalanceInfo {
    pub balance_source: String,
    pub realised_usd: Option<f64>,
    pub equity_est_usd: Option<f64>,
    pub unreal_pnl_est_usd: f64,
    pub est_close_fees_usd: f64,
    pub fee_rate: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct DailyMetrics {
    pub utc_day: String,
    pub trades: i64,
    pub start_balance: Option<f64>,
    pub end_balance: Option<f64>,
    pub pnl_usd: f64,
    pub fees_usd: f64,
    pub net_pnl_usd: f64,
    pub peak_realised_balance: Option<f64>,
    pub drawdown_pct: f64,
}

// ── Journey types ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize)]
pub struct TradeJourney {
    pub id: i64, // open_trade_id
    pub symbol: String,
    #[serde(rename = "type")]
    pub pos_type: String, // LONG / SHORT
    pub open_ts: String,
    pub close_ts: Option<String>,
    pub entry_price: f64,
    pub exit_price: Option<f64>,
    pub peak_size: f64,
    pub total_pnl: f64,
    pub total_fees: f64,
    pub is_open: bool,
    pub legs: Vec<JourneyLeg>,
}

#[derive(Debug, Clone, Serialize)]
pub struct JourneyLeg {
    pub id: i64,
    pub timestamp: String,
    pub action: String,
    pub price: f64,
    pub size: f64,
    pub pnl: f64,
    pub reason: String,
    pub confidence: String,
}

// ── Queries ──────────────────────────────────────────────────────────────

/// Compute all open positions from the trades table.
pub fn compute_open_positions(conn: &Connection) -> Result<Vec<OpenPosition>, HubError> {
    // Find the latest OPEN trade per symbol that is not closed.
    let mut stmt = conn.prepare(
        "SELECT t.id, t.timestamp, t.symbol, t.type, t.price, t.size, t.confidence,
                t.entry_atr, t.leverage, t.margin_used
         FROM trades t
         JOIN (
             SELECT symbol, MAX(id) AS open_id
             FROM trades WHERE action = 'OPEN' GROUP BY symbol
         ) lo ON lo.symbol = t.symbol AND lo.open_id = t.id
         LEFT JOIN (
             SELECT symbol, MAX(id) AS close_id
             FROM trades WHERE action = 'CLOSE' GROUP BY symbol
         ) lc ON lc.symbol = t.symbol
         WHERE lc.close_id IS NULL OR t.id > lc.close_id",
    )?;

    let rows: Vec<_> = stmt
        .query_map([], |row| {
            Ok((
                row.get::<_, i64>(0)?,            // id
                row.get::<_, Option<String>>(1)?, // timestamp
                row.get::<_, String>(2)?,         // symbol
                row.get::<_, String>(3)?,         // type
                row.get::<_, f64>(4)?,            // price
                row.get::<_, f64>(5)?,            // size
                row.get::<_, Option<String>>(6)?, // confidence
                row.get::<_, Option<f64>>(7)?,    // entry_atr
                row.get::<_, Option<f64>>(8)?,    // leverage
                row.get::<_, Option<f64>>(9)?,    // margin_used
            ))
        })?
        .collect::<Result<Vec<_>, _>>()?;

    let mut positions = Vec::new();

    for (
        open_id,
        ts,
        symbol,
        pos_type,
        mut avg_entry,
        mut net_size,
        confidence,
        entry_atr_opt,
        leverage_opt,
        margin_used_opt,
    ) in rows
    {
        let pos_type_upper = pos_type.to_uppercase();
        if pos_type_upper != "LONG" && pos_type_upper != "SHORT" {
            continue;
        }
        if avg_entry <= 0.0 || net_size <= 0.0 {
            continue;
        }

        let mut entry_atr = entry_atr_opt.unwrap_or(0.0);

        // Replay ADD/REDUCE to rebuild position
        let mut add_reduce_stmt = conn.prepare(
            "SELECT action, price, size, entry_atr FROM trades
             WHERE symbol = ? AND id > ? AND action IN ('ADD', 'REDUCE')
             ORDER BY id ASC",
        )?;

        let adjustments: Vec<_> = add_reduce_stmt
            .query_map(params![symbol, open_id], |row| {
                Ok((
                    row.get::<_, String>(0)?,
                    row.get::<_, f64>(1)?,
                    row.get::<_, f64>(2)?,
                    row.get::<_, Option<f64>>(3)?,
                ))
            })?
            .collect::<Result<Vec<_>, _>>()?;

        let mut closed = false;
        for (action, px, sz, fill_atr) in &adjustments {
            if *px <= 0.0 || *sz <= 0.0 {
                continue;
            }
            if action == "ADD" {
                let new_total = net_size + sz;
                if new_total > 0.0 {
                    avg_entry = (avg_entry * net_size + px * sz) / new_total;
                    if let Some(fa) = fill_atr {
                        if *fa > 0.0 {
                            entry_atr = if entry_atr > 0.0 {
                                (entry_atr * net_size + fa * sz) / new_total
                            } else {
                                *fa
                            };
                        }
                    }
                    net_size = new_total;
                }
            } else if action == "REDUCE" {
                net_size -= sz;
                if net_size <= 0.0 {
                    closed = true;
                    break;
                }
            }
        }

        if closed || net_size <= 0.0 {
            continue;
        }

        let leverage = leverage_opt.unwrap_or(1.0).max(0.01);
        let margin_used = margin_used_opt.unwrap_or_else(|| net_size.abs() * avg_entry / leverage);

        positions.push(OpenPosition {
            symbol: symbol.to_uppercase(),
            pos_type: pos_type_upper,
            open_trade_id: open_id,
            open_timestamp: ts,
            entry_price: avg_entry,
            size: net_size,
            confidence,
            entry_atr,
            leverage,
            margin_used,
        });
    }

    Ok(positions)
}

/// Fetch recent trades (most recent first).
pub fn recent_trades(conn: &Connection, limit: u32) -> Result<Vec<RecentTrade>, HubError> {
    let mut stmt = conn.prepare(
        "SELECT timestamp, symbol, type, action, price, size, notional, pnl, fee_usd, reason, confidence
         FROM trades ORDER BY id DESC LIMIT ?",
    )?;
    let rows = stmt
        .query_map(params![limit], |row| {
            Ok(RecentTrade {
                timestamp: row.get(0)?,
                symbol: row.get::<_, String>(1).unwrap_or_default(),
                trade_type: row.get(2)?,
                action: row.get(3)?,
                price: row.get(4)?,
                size: row.get(5)?,
                notional: row.get(6)?,
                pnl: row.get(7)?,
                fee_usd: row.get(8)?,
                reason: row.get(9)?,
                confidence: row.get(10)?,
            })
        })?
        .collect::<Result<Vec<_>, _>>()?;
    Ok(rows)
}

/// Fetch recent signals.
pub fn recent_signals(conn: &Connection, limit: u32) -> Result<Vec<RecentSignal>, HubError> {
    let mut stmt = conn.prepare(
        "SELECT timestamp, symbol, signal, confidence, price
         FROM signals ORDER BY id DESC LIMIT ?",
    )?;
    let rows = stmt
        .query_map(params![limit], |row| {
            Ok(RecentSignal {
                timestamp: row.get(0)?,
                symbol: row.get::<_, String>(1).unwrap_or_default(),
                signal: row.get(2)?,
                confidence: row.get(3)?,
                price: row.get(4)?,
            })
        })?
        .collect::<Result<Vec<_>, _>>()?;
    Ok(rows)
}

/// Fetch the last signal per symbol.
pub fn last_signals_by_symbol(
    conn: &Connection,
    symbols: &[String],
) -> Result<std::collections::HashMap<String, LastSignal>, HubError> {
    if symbols.is_empty() {
        return Ok(Default::default());
    }
    let placeholders = symbols.iter().map(|_| "?").collect::<Vec<_>>().join(",");
    let sql = format!(
        "SELECT t.symbol, t.timestamp, t.signal, t.confidence, t.price
         FROM signals t
         JOIN (SELECT symbol, MAX(id) AS max_id FROM signals WHERE symbol IN ({placeholders}) GROUP BY symbol) m
           ON m.symbol = t.symbol AND m.max_id = t.id"
    );
    let mut stmt = conn.prepare(&sql)?;
    let params: Vec<&dyn rusqlite::types::ToSql> = symbols
        .iter()
        .map(|s| s as &dyn rusqlite::types::ToSql)
        .collect();
    let rows = stmt
        .query_map(params.as_slice(), |row| {
            Ok((
                row.get::<_, String>(0)?,
                LastSignal {
                    timestamp: row.get(1)?,
                    signal: row.get(2)?,
                    confidence: row.get(3)?,
                    price: row.get(4)?,
                },
            ))
        })?
        .collect::<Result<Vec<_>, _>>()?;

    Ok(rows.into_iter().collect())
}

/// Fetch the last trade per symbol.
pub fn last_trades_by_symbol(
    conn: &Connection,
    symbols: &[String],
) -> Result<std::collections::HashMap<String, LastTrade>, HubError> {
    if symbols.is_empty() {
        return Ok(Default::default());
    }
    let placeholders = symbols.iter().map(|_| "?").collect::<Vec<_>>().join(",");
    let sql = format!(
        "SELECT t.symbol, t.timestamp, t.type, t.action, t.price, t.size, t.pnl, t.reason, t.confidence
         FROM trades t
         JOIN (SELECT symbol, MAX(id) AS max_id FROM trades WHERE symbol IN ({placeholders}) GROUP BY symbol) m
           ON m.symbol = t.symbol AND m.max_id = t.id"
    );
    let mut stmt = conn.prepare(&sql)?;
    let params: Vec<&dyn rusqlite::types::ToSql> = symbols
        .iter()
        .map(|s| s as &dyn rusqlite::types::ToSql)
        .collect();
    let rows = stmt
        .query_map(params.as_slice(), |row| {
            Ok((
                row.get::<_, String>(0)?,
                LastTrade {
                    timestamp: row.get(1)?,
                    trade_type: row.get(2)?,
                    action: row.get(3)?,
                    price: row.get(4)?,
                    size: row.get(5)?,
                    pnl: row.get(6)?,
                    reason: row.get(7)?,
                    confidence: row.get(8)?,
                },
            ))
        })?
        .collect::<Result<Vec<_>, _>>()?;

    Ok(rows.into_iter().collect())
}

/// Fetch the latest balance from trades table.
pub fn latest_balance(conn: &Connection) -> Result<Option<(f64, Option<String>)>, HubError> {
    let mut stmt = conn.prepare(
        "SELECT balance, timestamp FROM trades WHERE balance IS NOT NULL ORDER BY id DESC LIMIT 1",
    )?;
    let result = stmt.query_row([], |row| {
        Ok((row.get::<_, f64>(0)?, row.get::<_, Option<String>>(1)?))
    });
    match result {
        Ok(v) => Ok(Some(v)),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(e) => Err(e.into()),
    }
}

/// Check if a table exists in the database.
pub fn has_table(conn: &Connection, table: &str) -> bool {
    conn.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name=?")
        .and_then(|mut s| s.query_row(params![table], |_| Ok(())))
        .is_ok()
}

/// List recent symbols from candles + trades.
pub fn list_recent_symbols(
    conn: &Connection,
    candles_conn: Option<&Connection>,
    interval: &str,
    now_ms: i64,
    limit: usize,
) -> Result<Vec<String>, HubError> {
    let mut symbols: Vec<String> = Vec::new();
    let mut seen = std::collections::HashSet::new();

    // From candles
    let cconn = candles_conn.unwrap_or(conn);
    let candle_cutoff = now_ms - 6 * 60 * 60 * 1000;
    if let Ok(mut stmt) = cconn.prepare(
        "SELECT symbol FROM candles WHERE interval = ? AND COALESCE(t_close, t) >= ?
         GROUP BY symbol ORDER BY MAX(COALESCE(t_close, t)) DESC LIMIT ?",
    ) {
        if let Ok(rows) = stmt.query_map(params![interval, candle_cutoff, limit as u32], |row| {
            row.get::<_, String>(0)
        }) {
            for row in rows.flatten() {
                let s = row.to_uppercase();
                if seen.insert(s.clone()) {
                    symbols.push(s);
                }
            }
        }
    }

    // From trades
    if let Ok(mut stmt) = conn.prepare(
        "SELECT DISTINCT symbol FROM trades WHERE timestamp >= datetime('now', '-24 hours') ORDER BY symbol"
    ) {
        if let Ok(rows) = stmt.query_map([], |row| row.get::<_, String>(0)) {
            for row in rows.flatten() {
                let s = row.to_uppercase();
                if seen.insert(s.clone()) {
                    symbols.push(s);
                }
            }
        }
    }

    symbols.truncate(200);
    Ok(symbols)
}

// ── Marks ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize)]
pub struct TradeEntry {
    pub id: i64,
    pub timestamp: Option<String>,
    pub action: Option<String>,
    #[serde(rename = "type")]
    pub trade_type: Option<String>,
    pub price: Option<f64>,
    pub size: Option<f64>,
    pub confidence: Option<String>,
}

/// Compute open position for a single symbol.
pub fn open_position_for_symbol(
    conn: &Connection,
    symbol: &str,
) -> Result<Option<OpenPosition>, HubError> {
    let positions = compute_open_positions(conn)?;
    Ok(positions.into_iter().find(|p| p.symbol == symbol))
}

/// Fetch entry trades for a position (OPEN + ADD since open_trade_id).
pub fn position_entries(
    conn: &Connection,
    symbol: &str,
    open_trade_id: i64,
) -> Result<Vec<TradeEntry>, HubError> {
    let mut stmt = conn.prepare(
        "SELECT id, timestamp, action, type, price, size, confidence
         FROM trades
         WHERE symbol = ? AND id >= ? AND action IN ('OPEN', 'ADD')
         ORDER BY id ASC",
    )?;
    let rows = stmt
        .query_map(params![symbol, open_trade_id], |row| {
            Ok(TradeEntry {
                id: row.get(0)?,
                timestamp: row.get(1)?,
                action: row.get(2)?,
                trade_type: row.get(3)?,
                price: row.get(4)?,
                size: row.get(5)?,
                confidence: row.get(6)?,
            })
        })?
        .collect::<Result<Vec<_>, _>>()?;
    Ok(rows)
}

// ── Trade Journeys ──────────────────────────────────────────────────────

/// Enrich generic "Signal Trigger" entry reasons using audit tags from meta_json.
fn enrich_entry_reason(reason: &str, meta_json: &str) -> String {
    if reason != "Signal Trigger" || meta_json.is_empty() {
        return reason.to_string();
    }
    let Ok(meta) = serde_json::from_str::<serde_json::Value>(meta_json) else {
        return reason.to_string();
    };
    let Some(tags) = meta.pointer("/audit/tags").and_then(|v| v.as_array()) else {
        return reason.to_string();
    };
    let tags: Vec<&str> = tags.iter().filter_map(|v| v.as_str()).collect();
    let has = |t: &str| tags.iter().any(|&s| s == t);

    // Determine entry mode
    let mode = if has("mode:pullback") {
        "Pullback"
    } else if has("mode:slow_drift") {
        "Slow Drift"
    } else {
        "Trend"
    };

    // Collect modifiers
    let mut mods = Vec::new();
    if has("filter:macro_required") {
        mods.push("Macro");
    }
    if has("conf:high_volume") {
        mods.push("Vol+");
    }

    if mods.is_empty() {
        format!("{mode} Entry")
    } else {
        format!("{mode} Entry ({})", mods.join("+"))
    }
}

/// Reconstruct trade journeys (OPEN→…→CLOSE lifecycles) from the trades table.
/// Returns most-recent journeys first (open ones at the top, then closed by close_ts DESC).
///
/// NOTE: This loads all matching trades into memory and reconstructs journeys in Rust.
/// For tables with <10k trades this is fine; for larger datasets consider a materialized
/// journeys table populated on write.
pub fn trade_journeys(
    conn: &Connection,
    limit: u32,
    offset: u32,
    symbol_filter: Option<&str>,
) -> Result<Vec<TradeJourney>, HubError> {
    let sql = if symbol_filter.is_some() {
        "SELECT id, timestamp, symbol, type, action, price, size, pnl, fee_usd, reason, confidence, meta_json
         FROM trades
         WHERE action IN ('OPEN','ADD','REDUCE','CLOSE') AND symbol = ?
         ORDER BY id ASC"
    } else {
        "SELECT id, timestamp, symbol, type, action, price, size, pnl, fee_usd, reason, confidence, meta_json
         FROM trades
         WHERE action IN ('OPEN','ADD','REDUCE','CLOSE')
         ORDER BY id ASC"
    };

    let mut stmt = conn.prepare(sql)?;

    let rows: Vec<(i64, String, String, String, String, f64, f64, f64, f64, String, String, String)> =
        if let Some(sym) = symbol_filter {
            stmt.query_map(params![sym], |row| {
                Ok((
                    row.get::<_, i64>(0)?,
                    row.get::<_, Option<String>>(1)?.unwrap_or_default(),
                    row.get::<_, String>(2)?,
                    row.get::<_, Option<String>>(3)?.unwrap_or_default(),
                    row.get::<_, Option<String>>(4)?.unwrap_or_default(),
                    row.get::<_, f64>(5).unwrap_or(0.0),
                    row.get::<_, f64>(6).unwrap_or(0.0),
                    row.get::<_, f64>(7).unwrap_or(0.0),
                    row.get::<_, f64>(8).unwrap_or(0.0),
                    row.get::<_, Option<String>>(9)?.unwrap_or_default(),
                    row.get::<_, Option<String>>(10)?.unwrap_or_default(),
                    row.get::<_, Option<String>>(11)?.unwrap_or_default(),
                ))
            })?
            .collect::<Result<Vec<_>, _>>()?
        } else {
            stmt.query_map([], |row| {
                Ok((
                    row.get::<_, i64>(0)?,
                    row.get::<_, Option<String>>(1)?.unwrap_or_default(),
                    row.get::<_, String>(2)?,
                    row.get::<_, Option<String>>(3)?.unwrap_or_default(),
                    row.get::<_, Option<String>>(4)?.unwrap_or_default(),
                    row.get::<_, f64>(5).unwrap_or(0.0),
                    row.get::<_, f64>(6).unwrap_or(0.0),
                    row.get::<_, f64>(7).unwrap_or(0.0),
                    row.get::<_, f64>(8).unwrap_or(0.0),
                    row.get::<_, Option<String>>(9)?.unwrap_or_default(),
                    row.get::<_, Option<String>>(10)?.unwrap_or_default(),
                    row.get::<_, Option<String>>(11)?.unwrap_or_default(),
                ))
            })?
            .collect::<Result<Vec<_>, _>>()?
        };

    // Walk chronologically, building journeys keyed by symbol.
    // current_size tracks live position size for weighted avg entry calc;
    // peak_size records the high-water mark for display.
    struct InProgress {
        journey: TradeJourney,
        current_size: f64,
    }

    let mut in_progress: std::collections::HashMap<String, InProgress> =
        std::collections::HashMap::new();
    let mut completed: Vec<TradeJourney> = Vec::new();

    for (id, ts, symbol, pos_type, action, price, size, pnl, fee, reason, confidence, meta_json) in rows {
        let reason = enrich_entry_reason(&reason, &meta_json);
        let action_upper = action.to_uppercase();
        let sym_upper = symbol.to_uppercase();

        match action_upper.as_str() {
            "OPEN" => {
                // Flush any orphaned previous journey for this symbol
                if let Some(orphan) = in_progress.remove(&sym_upper) {
                    completed.push(orphan.journey);
                }
                in_progress.insert(
                    sym_upper.clone(),
                    InProgress {
                        journey: TradeJourney {
                            id,
                            symbol: sym_upper,
                            pos_type: pos_type.to_uppercase(),
                            open_ts: ts.clone(),
                            close_ts: None,
                            entry_price: price,
                            exit_price: None,
                            peak_size: size,
                            total_pnl: pnl,
                            total_fees: fee.abs(),
                            is_open: true,
                            legs: vec![JourneyLeg {
                                id,
                                timestamp: ts,
                                action: action_upper,
                                price,
                                size,
                                pnl,
                                reason: reason.clone(),
                                confidence: confidence.clone(),
                            }],
                        },
                        current_size: size,
                    },
                );
            }
            "ADD" => {
                if let Some(ip) = in_progress.get_mut(&sym_upper) {
                    // Recalculate weighted avg entry using current (not peak) size
                    let prev_notional = ip.journey.entry_price * ip.current_size;
                    let new_size = ip.current_size + size;
                    if new_size > 0.0 {
                        ip.journey.entry_price = (prev_notional + price * size) / new_size;
                    }
                    ip.current_size = new_size;
                    if new_size > ip.journey.peak_size {
                        ip.journey.peak_size = new_size;
                    }
                    ip.journey.total_pnl += pnl;
                    ip.journey.total_fees += fee.abs();
                    ip.journey.legs.push(JourneyLeg {
                        id,
                        timestamp: ts,
                        action: action_upper,
                        price,
                        size,
                        pnl,
                        reason: reason.clone(),
                        confidence: confidence.clone(),
                    });
                }
                // Ignore ADD without a preceding OPEN
            }
            "REDUCE" => {
                if let Some(ip) = in_progress.get_mut(&sym_upper) {
                    ip.current_size = (ip.current_size - size).max(0.0);
                    ip.journey.total_pnl += pnl;
                    ip.journey.total_fees += fee.abs();
                    ip.journey.legs.push(JourneyLeg {
                        id,
                        timestamp: ts,
                        action: action_upper,
                        price,
                        size,
                        pnl,
                        reason: reason.clone(),
                        confidence: confidence.clone(),
                    });
                }
            }
            "CLOSE" => {
                if let Some(ip) = in_progress.remove(&sym_upper) {
                    let mut j = ip.journey;
                    j.close_ts = Some(ts.clone());
                    j.exit_price = Some(price);
                    j.is_open = false;
                    j.total_pnl += pnl;
                    j.total_fees += fee.abs();
                    j.legs.push(JourneyLeg {
                        id,
                        timestamp: ts,
                        action: action_upper,
                        price,
                        size,
                        pnl,
                        reason,
                        confidence,
                    });
                    completed.push(j);
                }
                // Orphaned CLOSE (no preceding OPEN) is silently dropped.
                // This can happen when the OPEN predates the DB or data was truncated.
            }
            _ => {}
        }
    }

    // Collect: open ones first, then closed by close_ts DESC
    let mut result: Vec<TradeJourney> = Vec::new();

    // Open journeys (still in progress)
    let mut open_journeys: Vec<TradeJourney> =
        in_progress.into_values().map(|ip| ip.journey).collect();
    open_journeys.sort_by(|a, b| b.open_ts.cmp(&a.open_ts));
    result.extend(open_journeys);

    // Closed journeys, most recent close_ts first
    completed.sort_by(|a, b| b.close_ts.cmp(&a.close_ts));
    result.extend(completed);

    // Apply offset + limit
    let start = offset as usize;
    if start >= result.len() {
        return Ok(Vec::new());
    }
    let end = (start + limit as usize).min(result.len());
    Ok(result[start..end].to_vec())
}

// ── Daily Metrics ────────────────────────────────────────────────────────

/// Compute daily metrics for the current UTC day.
pub fn daily_metrics(conn: &Connection, now_ms: i64) -> Result<DailyMetrics, HubError> {
    let ts_secs = now_ms / 1000;
    let day = chrono::DateTime::from_timestamp(ts_secs, 0)
        .map(|dt| dt.format("%Y-%m-%d").to_string())
        .unwrap_or_default();

    let mut daily = DailyMetrics {
        utc_day: day.clone(),
        trades: 0,
        start_balance: None,
        end_balance: None,
        pnl_usd: 0.0,
        fees_usd: 0.0,
        net_pnl_usd: 0.0,
        peak_realised_balance: None,
        drawdown_pct: 0.0,
    };

    if day.is_empty() {
        return Ok(daily);
    }

    // Use range query (index-friendly) instead of LIKE.
    let day_start = format!("{day}T00:00:00");
    let day_end = format!("{day}T23:59:59.999");

    // Start balance
    if let Ok(mut stmt) = conn.prepare(
        "SELECT balance FROM trades WHERE timestamp >= ? AND timestamp <= ? AND balance IS NOT NULL ORDER BY id ASC LIMIT 1"
    ) {
        if let Ok(b) = stmt.query_row(params![day_start, day_end], |row| row.get::<_, f64>(0)) {
            daily.start_balance = Some(b);
        }
    }

    // End balance
    if let Ok(mut stmt) = conn.prepare(
        "SELECT balance FROM trades WHERE timestamp >= ? AND timestamp <= ? AND balance IS NOT NULL ORDER BY id DESC LIMIT 1"
    ) {
        if let Ok(b) = stmt.query_row(params![day_start, day_end], |row| row.get::<_, f64>(0)) {
            daily.end_balance = Some(b);
        }
    }

    // Peak balance
    if let Ok(mut stmt) = conn.prepare(
        "SELECT MAX(balance) FROM trades WHERE timestamp >= ? AND timestamp <= ? AND balance IS NOT NULL"
    ) {
        if let Ok(b) = stmt.query_row(params![day_start, day_end], |row| row.get::<_, Option<f64>>(0)) {
            daily.peak_realised_balance = b;
        }
    }

    // Trade count
    if let Ok(mut stmt) =
        conn.prepare("SELECT COUNT(*) FROM trades WHERE timestamp >= ? AND timestamp <= ?")
    {
        if let Ok(n) = stmt.query_row(params![day_start, day_end], |row| row.get::<_, i64>(0)) {
            daily.trades = n;
        }
    }

    // Fees
    if let Ok(mut stmt) = conn.prepare(
        "SELECT SUM(COALESCE(fee_usd, 0)) FROM trades WHERE timestamp >= ? AND timestamp <= ?",
    ) {
        if let Ok(f) = stmt.query_row(params![day_start, day_end], |row| {
            row.get::<_, Option<f64>>(0)
        }) {
            daily.fees_usd = f.unwrap_or(0.0);
        }
    }

    // PnL
    if let (Some(start), Some(end)) = (daily.start_balance, daily.end_balance) {
        daily.pnl_usd = end - start;
        daily.net_pnl_usd = daily.pnl_usd - daily.fees_usd;
    }

    // Drawdown
    if let (Some(peak), Some(end)) = (daily.peak_realised_balance, daily.end_balance) {
        if peak > 0.0 {
            daily.drawdown_pct = ((peak - end) / peak) * 100.0;
        }
    }

    Ok(daily)
}

// ── Range Metrics ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize)]
pub struct RangeMetrics {
    pub from_ts: Option<String>,
    pub trades: i64,
    pub start_balance: Option<f64>,
    pub end_balance: Option<f64>,
    pub pnl_usd: f64,
    pub fees_usd: f64,
    pub net_pnl_usd: f64,
    pub peak_balance: Option<f64>,
    pub drawdown_pct: f64,
}

/// Compute metrics over an arbitrary time range.
/// If `from_iso` is `Some(ts)`, only trades with `timestamp >= ts` are included.
/// If `None`, all trades are included (all-time).
pub fn range_metrics(conn: &Connection, from_iso: Option<&str>) -> Result<RangeMetrics, HubError> {
    let mut metrics = RangeMetrics {
        from_ts: from_iso.map(|s| s.to_string()),
        trades: 0,
        start_balance: None,
        end_balance: None,
        pnl_usd: 0.0,
        fees_usd: 0.0,
        net_pnl_usd: 0.0,
        peak_balance: None,
        drawdown_pct: 0.0,
    };

    if let Some(ts) = from_iso {
        // Start balance
        if let Ok(mut stmt) = conn.prepare(
            "SELECT balance FROM trades WHERE timestamp >= ? AND balance IS NOT NULL ORDER BY id ASC LIMIT 1",
        ) {
            if let Ok(b) = stmt.query_row(params![ts], |row| row.get::<_, f64>(0)) {
                metrics.start_balance = Some(b);
            }
        }
        // End balance
        if let Ok(mut stmt) = conn.prepare(
            "SELECT balance FROM trades WHERE timestamp >= ? AND balance IS NOT NULL ORDER BY id DESC LIMIT 1",
        ) {
            if let Ok(b) = stmt.query_row(params![ts], |row| row.get::<_, f64>(0)) {
                metrics.end_balance = Some(b);
            }
        }
        // Peak balance
        if let Ok(mut stmt) = conn.prepare(
            "SELECT MAX(balance) FROM trades WHERE timestamp >= ? AND balance IS NOT NULL",
        ) {
            if let Ok(b) = stmt.query_row(params![ts], |row| row.get::<_, Option<f64>>(0)) {
                metrics.peak_balance = b;
            }
        }
        // Trade count
        if let Ok(mut stmt) = conn.prepare("SELECT COUNT(*) FROM trades WHERE timestamp >= ?") {
            if let Ok(n) = stmt.query_row(params![ts], |row| row.get::<_, i64>(0)) {
                metrics.trades = n;
            }
        }
        // Fees
        if let Ok(mut stmt) = conn.prepare(
            "SELECT SUM(COALESCE(fee_usd, 0)) FROM trades WHERE timestamp >= ?",
        ) {
            if let Ok(f) = stmt.query_row(params![ts], |row| row.get::<_, Option<f64>>(0)) {
                metrics.fees_usd = f.unwrap_or(0.0);
            }
        }
    } else {
        // All-time: no lower bound
        if let Ok(mut stmt) = conn.prepare(
            "SELECT balance FROM trades WHERE balance IS NOT NULL ORDER BY id ASC LIMIT 1",
        ) {
            if let Ok(b) = stmt.query_row([], |row| row.get::<_, f64>(0)) {
                metrics.start_balance = Some(b);
            }
        }
        if let Ok(mut stmt) = conn.prepare(
            "SELECT balance FROM trades WHERE balance IS NOT NULL ORDER BY id DESC LIMIT 1",
        ) {
            if let Ok(b) = stmt.query_row([], |row| row.get::<_, f64>(0)) {
                metrics.end_balance = Some(b);
            }
        }
        if let Ok(mut stmt) = conn.prepare(
            "SELECT MAX(balance) FROM trades WHERE balance IS NOT NULL",
        ) {
            if let Ok(b) = stmt.query_row([], |row| row.get::<_, Option<f64>>(0)) {
                metrics.peak_balance = b;
            }
        }
        if let Ok(mut stmt) = conn.prepare("SELECT COUNT(*) FROM trades") {
            if let Ok(n) = stmt.query_row([], |row| row.get::<_, i64>(0)) {
                metrics.trades = n;
            }
        }
        if let Ok(mut stmt) = conn.prepare("SELECT SUM(COALESCE(fee_usd, 0)) FROM trades") {
            if let Ok(f) = stmt.query_row([], |row| row.get::<_, Option<f64>>(0)) {
                metrics.fees_usd = f.unwrap_or(0.0);
            }
        }
    }

    // PnL
    if let (Some(start), Some(end)) = (metrics.start_balance, metrics.end_balance) {
        metrics.pnl_usd = end - start;
        metrics.net_pnl_usd = metrics.pnl_usd - metrics.fees_usd;
    }

    // Drawdown
    if let (Some(peak), Some(end)) = (metrics.peak_balance, metrics.end_balance) {
        if peak > 0.0 {
            metrics.drawdown_pct = ((peak - end) / peak) * 100.0;
        }
    }

    Ok(metrics)
}

// ── OMS Queries ──────────────────────────────────────────────────────────

/// Fetch recent OMS intents.
pub fn recent_oms_intents(conn: &Connection, limit: u32) -> Result<Vec<Value>, HubError> {
    if !has_table(conn, "oms_intents") {
        return Ok(Vec::new());
    }
    let mut stmt = conn.prepare(
        "SELECT created_ts_ms, symbol, action, side, status, confidence, reason,
                dedupe_key, client_order_id, exchange_order_id, last_error
         FROM oms_intents ORDER BY created_ts_ms DESC LIMIT ?",
    )?;
    let rows = stmt
        .query_map(params![limit], |row| {
            Ok(serde_json::json!({
                "created_ts_ms": row.get::<_, Option<i64>>(0)?,
                "symbol": row.get::<_, Option<String>>(1)?,
                "action": row.get::<_, Option<String>>(2)?,
                "side": row.get::<_, Option<String>>(3)?,
                "status": row.get::<_, Option<String>>(4)?,
                "confidence": row.get::<_, Option<String>>(5)?,
                "reason": row.get::<_, Option<String>>(6)?,
                "dedupe_key": row.get::<_, Option<String>>(7)?,
                "client_order_id": row.get::<_, Option<String>>(8)?,
                "exchange_order_id": row.get::<_, Option<String>>(9)?,
                "last_error": row.get::<_, Option<String>>(10)?,
            }))
        })?
        .filter_map(|r| r.ok())
        .collect();
    Ok(rows)
}

/// Fetch recent OMS fills.
pub fn recent_oms_fills(conn: &Connection, limit: u32) -> Result<Vec<Value>, HubError> {
    if !has_table(conn, "oms_fills") {
        return Ok(Vec::new());
    }
    let mut stmt = conn.prepare(
        "SELECT ts_ms, symbol, intent_id, action, side, price, size, notional, fee_usd, pnl_usd, matched_via
         FROM oms_fills ORDER BY ts_ms DESC LIMIT ?"
    )?;
    let rows = stmt
        .query_map(params![limit], |row| {
            Ok(serde_json::json!({
                "ts_ms": row.get::<_, Option<i64>>(0)?,
                "symbol": row.get::<_, Option<String>>(1)?,
                "intent_id": row.get::<_, Option<String>>(2)?,
                "action": row.get::<_, Option<String>>(3)?,
                "side": row.get::<_, Option<String>>(4)?,
                "price": row.get::<_, Option<f64>>(5)?,
                "size": row.get::<_, Option<f64>>(6)?,
                "notional": row.get::<_, Option<f64>>(7)?,
                "fee_usd": row.get::<_, Option<f64>>(8)?,
                "pnl_usd": row.get::<_, Option<f64>>(9)?,
                "matched_via": row.get::<_, Option<String>>(10)?,
            }))
        })?
        .filter_map(|r| r.ok())
        .collect();
    Ok(rows)
}

/// Fetch recent OMS open orders.
pub fn recent_oms_open_orders(conn: &Connection, limit: u32) -> Result<Vec<Value>, HubError> {
    if !has_table(conn, "oms_open_orders") {
        return Ok(Vec::new());
    }
    let mut stmt = conn.prepare(
        "SELECT last_seen_ts_ms, symbol, side, price, remaining_size, reduce_only,
                client_order_id, exchange_order_id, intent_id
         FROM oms_open_orders ORDER BY last_seen_ts_ms DESC LIMIT ?",
    )?;
    let rows = stmt
        .query_map(params![limit], |row| {
            Ok(serde_json::json!({
                "last_seen_ts_ms": row.get::<_, Option<i64>>(0)?,
                "symbol": row.get::<_, Option<String>>(1)?,
                "side": row.get::<_, Option<String>>(2)?,
                "price": row.get::<_, Option<f64>>(3)?,
                "remaining_size": row.get::<_, Option<f64>>(4)?,
                "reduce_only": row.get::<_, Option<bool>>(5)?,
                "client_order_id": row.get::<_, Option<String>>(6)?,
                "exchange_order_id": row.get::<_, Option<String>>(7)?,
                "intent_id": row.get::<_, Option<String>>(8)?,
            }))
        })?
        .filter_map(|r| r.ok())
        .collect();
    Ok(rows)
}

/// Fetch recent OMS reconcile events.
pub fn recent_oms_reconcile(conn: &Connection, limit: u32) -> Result<Vec<Value>, HubError> {
    if !has_table(conn, "oms_reconcile_events") {
        return Ok(Vec::new());
    }
    let mut stmt = conn.prepare(
        "SELECT ts_ms, kind, symbol, result
         FROM oms_reconcile_events ORDER BY ts_ms DESC LIMIT ?",
    )?;
    let rows = stmt
        .query_map(params![limit], |row| {
            Ok(serde_json::json!({
                "ts_ms": row.get::<_, Option<i64>>(0)?,
                "kind": row.get::<_, Option<String>>(1)?,
                "symbol": row.get::<_, Option<String>>(2)?,
                "result": row.get::<_, Option<String>>(3)?,
            }))
        })?
        .filter_map(|r| r.ok())
        .collect();
    Ok(rows)
}

/// Fetch recent audit events.
pub fn recent_audit_events(conn: &Connection, limit: u32) -> Result<Vec<Value>, HubError> {
    if !has_table(conn, "audit_events") {
        return Ok(Vec::new());
    }
    let mut stmt = conn.prepare(
        "SELECT timestamp, symbol, event, level, data_json
         FROM audit_events ORDER BY id DESC LIMIT ?",
    )?;
    let rows = stmt
        .query_map(params![limit], |row| {
            Ok(serde_json::json!({
                "timestamp": row.get::<_, Option<String>>(0)?,
                "symbol": row.get::<_, Option<String>>(1)?,
                "event": row.get::<_, Option<String>>(2)?,
                "level": row.get::<_, Option<String>>(3)?,
                "data_json": row.get::<_, Option<String>>(4)?,
            }))
        })?
        .filter_map(|r| r.ok())
        .collect();
    Ok(rows)
}

/// Fetch last OMS intent per symbol.
pub fn last_intents_by_symbol(
    conn: &Connection,
    symbols: &[String],
) -> Result<std::collections::HashMap<String, Value>, HubError> {
    if symbols.is_empty() || !has_table(conn, "oms_intents") {
        return Ok(Default::default());
    }
    let placeholders = symbols.iter().map(|_| "?").collect::<Vec<_>>().join(",");
    let sql = format!(
        "SELECT i.symbol, i.created_ts_ms, i.action, i.side, i.status, i.confidence,
                i.reason, i.dedupe_key, i.client_order_id
         FROM oms_intents i
         JOIN (SELECT symbol, MAX(rowid) AS max_id FROM oms_intents WHERE symbol IN ({placeholders}) GROUP BY symbol) m
           ON m.symbol = i.symbol AND m.max_id = i.rowid"
    );
    let mut stmt = conn.prepare(&sql)?;
    let params: Vec<&dyn rusqlite::types::ToSql> = symbols
        .iter()
        .map(|s| s as &dyn rusqlite::types::ToSql)
        .collect();
    let rows = stmt
        .query_map(params.as_slice(), |row| {
            Ok((
                row.get::<_, String>(0)?,
                serde_json::json!({
                    "created_ts_ms": row.get::<_, Option<i64>>(1)?,
                    "action": row.get::<_, Option<String>>(2)?,
                    "side": row.get::<_, Option<String>>(3)?,
                    "status": row.get::<_, Option<String>>(4)?,
                    "confidence": row.get::<_, Option<String>>(5)?,
                    "reason": row.get::<_, Option<String>>(6)?,
                    "dedupe_key": row.get::<_, Option<String>>(7)?,
                    "client_order_id": row.get::<_, Option<String>>(8)?,
                }),
            ))
        })?
        .filter_map(|r| r.ok())
        .collect::<Vec<_>>();

    Ok(rows.into_iter().collect())
}

/// Compute metrics counters (orders, fills, kill events).
pub fn metrics_counters(conn: &Connection) -> Result<Value, HubError> {
    let has_oms = has_table(conn, "oms_intents");
    let mut counters = serde_json::Map::new();

    if has_oms {
        if let Ok(mut stmt) = conn.prepare("SELECT COUNT(*) FROM oms_intents") {
            if let Ok(n) = stmt.query_row([], |row| row.get::<_, i64>(0)) {
                counters.insert("orders_total".into(), serde_json::json!(n));
            }
        }
        if let Ok(mut stmt) = conn.prepare("SELECT COUNT(*) FROM oms_fills") {
            if let Ok(n) = stmt.query_row([], |row| row.get::<_, i64>(0)) {
                counters.insert("fills_total".into(), serde_json::json!(n));
            }
        }
    } else {
        if let Ok(mut stmt) = conn.prepare("SELECT COUNT(*) FROM trades") {
            if let Ok(n) = stmt.query_row([], |row| row.get::<_, i64>(0)) {
                counters.insert("orders_total".into(), serde_json::json!(n));
                counters.insert("fills_total".into(), serde_json::json!(n));
            }
        }
    }

    // Kill events
    if has_table(conn, "audit_events") {
        if let Ok(mut stmt) =
            conn.prepare("SELECT COUNT(*) FROM audit_events WHERE event LIKE 'RISK_KILL_%'")
        {
            if let Ok(n) = stmt.query_row([], |row| row.get::<_, i64>(0)) {
                counters.insert("kill_events_total".into(), serde_json::json!(n));
            }
        }
    }

    Ok(Value::Object(counters))
}
