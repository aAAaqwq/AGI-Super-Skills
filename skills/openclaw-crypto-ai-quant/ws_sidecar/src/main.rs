use anyhow::{Context, Result, anyhow};
use chrono::Utc;
use futures_util::{SinkExt, StreamExt};
use reqwest::Client;
use rusqlite::Connection;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet, VecDeque};
use std::env;
use std::fs;
use std::os::unix::net::UnixDatagram;
use std::path::Path;
use std::sync::{Arc, Mutex, mpsc};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tokio::io::{AsyncBufReadExt, AsyncWrite, AsyncWriteExt, BufReader};
use tokio::net::{UnixListener, UnixStream};
use tokio::sync::{Notify, RwLock, Semaphore, mpsc as tokio_mpsc};
use tokio_tungstenite::tungstenite::Message;
use tokio_tungstenite::tungstenite::client::IntoClientRequest;
use tokio_tungstenite::tungstenite::http::HeaderValue;
use url::Url;

#[derive(Clone)]
struct Config {
    ws_url: String,
    info_url: String,
    sock_path: String,
    // Candle DBs live here; DB file is selected by interval.
    candles_db_dir: String,
    enable_meta: bool,
    enable_candle_ws: bool,
    enable_bbo: bool,
    // Optional: drive mids sequence and values from BBO mid ticks for lower latency UI updates.
    mids_from_bbo: bool,
    // In BBO-driven mode, fall back to allMids for a symbol when BBO is older than this threshold.
    mids_from_bbo_fallback_age_s: f64,
    // Optional BBO snapshot storage for slippage modelling.
    bbo_snapshots_enable: bool,
    bbo_snapshots_db_path: String,
    bbo_snapshots_sample_ms: u64,
    bbo_snapshots_retention_hours: u64,
    bbo_snapshots_retention_sweep_secs: u64,
    bbo_snapshots_max_queue: usize,
    reconnect_secs: u64,
    ping_secs: u64,
    sub_send_ms: u64,

    // Candle pipeline (REST + DB).
    candles_enable: bool,
    candle_verify_secs: u64,
    rest_timeout_s: u64,
    rest_min_gap_ms: u64,
    rest_max_inflight: usize,
    rest_chunk_bars: usize,
    candle_horizon_ms: HashMap<String, i64>,
    // Prune control: disable time-based deletes for selected intervals to build an append-only
    // history beyond Hyperliquid's last-5,000-bar API retention window.
    candle_prune_disable_intervals: HashSet<String>,

    candle_persist_secs: u64,
    max_event_queue: usize,
    max_incoming_queue: usize,
    db_timeout_s: u64,

    // Candle WS safeguards.
    ws_candle_reset_window_secs: u64,
    ws_candle_max_resets_in_window: usize,
    ws_candle_disable_secs: u64,

    // Multi-client.
    client_ttl_secs: u64,

    // Optional warm universe: keep candles fresh even if no client requests them.
    always_symbols: HashSet<String>,
    always_intervals: Vec<String>,
    always_candle_limit: usize,
}

fn env_string(key: &str, default: &str) -> String {
    env::var(key).unwrap_or_else(|_| default.to_string())
}

fn env_bool(key: &str, default: bool) -> bool {
    match env::var(key) {
        Ok(v) => matches!(
            v.trim().to_ascii_lowercase().as_str(),
            "1" | "true" | "yes" | "y" | "on"
        ),
        Err(_) => default,
    }
}

fn env_u64(key: &str, default: u64) -> u64 {
    match env::var(key)
        .ok()
        .and_then(|v| v.trim().parse::<u64>().ok())
    {
        Some(v) => v,
        None => default,
    }
}

fn env_usize(key: &str, default: usize) -> usize {
    match env::var(key)
        .ok()
        .and_then(|v| v.trim().parse::<usize>().ok())
    {
        Some(v) => v,
        None => default,
    }
}

fn env_f64(key: &str, default: f64) -> f64 {
    match env::var(key)
        .ok()
        .and_then(|v| v.trim().parse::<f64>().ok())
    {
        Some(v) => v,
        None => default,
    }
}

fn systemd_notify(state: &str) {
    let notify_socket = match env::var("NOTIFY_SOCKET") {
        Ok(v) => v,
        Err(_) => return,
    };
    let notify_socket = notify_socket.trim();
    if notify_socket.is_empty() {
        return;
    }
    if notify_socket.starts_with('@') {
        // Abstract namespace sockets are uncommon in our user-unit setup and not
        // directly supported by std::os::unix::net::UnixDatagram::connect.
        return;
    }

    let sock = match UnixDatagram::unbound() {
        Ok(v) => v,
        Err(_) => return,
    };
    if sock.connect(notify_socket).is_err() {
        return;
    }
    let _ = sock.send(state.as_bytes());
}

fn watchdog_interval_from_env() -> Option<Duration> {
    let watchdog_pid = env::var("WATCHDOG_PID").ok();
    if let Some(pid_raw) = watchdog_pid {
        if let Ok(pid) = pid_raw.trim().parse::<u32>() {
            if pid != std::process::id() {
                return None;
            }
        } else {
            return None;
        }
    }

    let watchdog_usec = env::var("WATCHDOG_USEC").ok()?;
    let usec = watchdog_usec.trim().parse::<u64>().ok()?;
    if usec == 0 {
        return None;
    }

    let micros = (usec / 2).max(1_000_000);
    Some(Duration::from_micros(micros))
}

fn default_sock_path() -> String {
    if let Ok(xdg) = env::var("XDG_RUNTIME_DIR") {
        let xdg = xdg.trim();
        if !xdg.is_empty() {
            return format!("{}/openclaw-ai-quant-ws.sock", xdg.trim_end_matches('/'));
        }
    }
    eprintln!(
        "[WARN] XDG_RUNTIME_DIR not set — falling back to /tmp (world-writable, less secure)"
    );
    "/tmp/openclaw-ai-quant-ws.sock".to_string()
}

fn default_candles_db_dir(market_db_path: &str) -> String {
    let p = Path::new(market_db_path);
    if let Some(parent) = p.parent() {
        return parent.join("candles_dbs").to_string_lossy().to_string();
    }
    "candles_dbs".to_string()
}

fn interval_to_ms(interval: &str) -> i64 {
    let s = interval.trim().to_ascii_lowercase();
    if s.is_empty() {
        return 60 * 60 * 1000;
    }
    let unit = s.chars().last().unwrap_or('h');
    let num_s = &s[..s.len().saturating_sub(1)];
    let n: f64 = num_s.parse::<f64>().unwrap_or(1.0);
    match unit {
        'm' => (n * 60.0 * 1000.0) as i64,
        'h' => (n * 60.0 * 60.0 * 1000.0) as i64,
        'd' => (n * 24.0 * 60.0 * 60.0 * 1000.0) as i64,
        _ => (n * 1000.0) as i64,
    }
}

fn load_config() -> Config {
    let ws_url =
        env::var("HL_WS_URL").unwrap_or_else(|_| "wss://api.hyperliquid.xyz/ws".to_string());
    let info_url = env_string("AI_QUANT_INFO_URL", "https://api.hyperliquid.xyz/info");

    let sock_path = env::var("AI_QUANT_WS_SIDECAR_SOCK").unwrap_or_else(|_| default_sock_path());

    // Used only to derive a default candle DB directory when AI_QUANT_CANDLES_DB_DIR is not set.
    let market_db_path = env::var("AI_QUANT_MARKET_DB_PATH")
        .or_else(|_| env::var("AI_QUANT_DB_PATH"))
        .unwrap_or_else(|_| "market_data.db".to_string());
    let candles_db_dir = env::var("AI_QUANT_CANDLES_DB_DIR")
        .unwrap_or_else(|_| default_candles_db_dir(&market_db_path));

    let enable_meta = env_bool("AI_QUANT_WS_ENABLE_META", true);
    let enable_candle_ws = env_bool("AI_QUANT_WS_ENABLE_CANDLE", true);
    let enable_bbo = env_bool("AI_QUANT_WS_ENABLE_BBO", true);
    let mids_from_bbo = env_bool("AI_QUANT_MIDS_FROM_BBO", false);
    let mids_from_bbo_fallback_age_s =
        env_f64("AI_QUANT_MIDS_FROM_BBO_FALLBACK_AGE_S", 5.0).max(0.1);

    let bbo_snapshots_enable = env_bool("AI_QUANT_BBO_SNAPSHOTS_ENABLE", false);
    let default_bbo_snapshots_db_path =
        format!("{}/bbo_snapshots.db", candles_db_dir.trim_end_matches('/'));
    let bbo_snapshots_db_path = env_string(
        "AI_QUANT_BBO_SNAPSHOTS_DB_PATH",
        &default_bbo_snapshots_db_path,
    );
    // Per-symbol insert throttle. Values <= 0 are clamped to 1ms.
    let bbo_snapshots_sample_ms = env_u64("AI_QUANT_BBO_SNAPSHOTS_SAMPLE_MS", 1000).max(1);
    // Storage is bounded by time-based retention. Values <= 0 are clamped to 1 hour.
    let bbo_snapshots_retention_hours =
        env_u64("AI_QUANT_BBO_SNAPSHOTS_RETENTION_HOURS", 24).max(1);
    // Retention sweeps run on a timer. Values <= 0 are clamped to 30s.
    let bbo_snapshots_retention_sweep_secs =
        env_u64("AI_QUANT_BBO_SNAPSHOTS_RETENTION_SWEEP_SECS", 600).max(30);
    let bbo_snapshots_max_queue = env_usize("AI_QUANT_BBO_SNAPSHOTS_MAX_QUEUE", 20000).max(1);

    let reconnect_secs = env_u64("HL_WS_RECONNECT_SECS", 5);
    let ping_secs = env_u64("HL_WS_PING_SECS", 50);
    // Throttle subscription requests to avoid starving reads and to reduce server-side flood risk.
    let sub_send_ms = env_u64("HL_WS_SUB_SEND_MS", 10);

    let candles_enable = env_bool("AI_QUANT_CANDLES_ENABLE", true);
    let candle_verify_secs = env_u64("AI_QUANT_CANDLE_VERIFY_SECS", 10);
    let rest_timeout_s = env_u64("AI_QUANT_CANDLE_REST_TIMEOUT_S", 10);
    // Basic pacing to avoid /info rate limits during aggressive multi-symbol backfills.
    let rest_min_gap_ms = env_u64("AI_QUANT_CANDLE_REST_MIN_GAP_MS", 500);
    let rest_max_inflight = env_usize("AI_QUANT_CANDLE_REST_MAX_INFLIGHT", 4);
    let rest_chunk_bars = env_usize("AI_QUANT_CANDLE_REST_CHUNK_BARS", 1500);

    // Balanced defaults (selected in plan).
    let h_1m_d = env_u64("AI_QUANT_CANDLE_HORIZON_1m_D", 1);
    let h_3m_d = env_u64("AI_QUANT_CANDLE_HORIZON_3m_D", 7);
    let h_5m_d = env_u64("AI_QUANT_CANDLE_HORIZON_5m_D", 7);
    let h_15m_d = env_u64("AI_QUANT_CANDLE_HORIZON_15m_D", 30);
    let h_30m_d = env_u64("AI_QUANT_CANDLE_HORIZON_30m_D", 30);
    let h_1h_d = env_u64("AI_QUANT_CANDLE_HORIZON_1h_D", 120);
    let mut candle_horizon_ms: HashMap<String, i64> = HashMap::new();
    candle_horizon_ms.insert("1m".to_string(), (h_1m_d as i64) * 24 * 60 * 60 * 1000);
    candle_horizon_ms.insert("3m".to_string(), (h_3m_d as i64) * 24 * 60 * 60 * 1000);
    candle_horizon_ms.insert("5m".to_string(), (h_5m_d as i64) * 24 * 60 * 60 * 1000);
    candle_horizon_ms.insert("15m".to_string(), (h_15m_d as i64) * 24 * 60 * 60 * 1000);
    candle_horizon_ms.insert("30m".to_string(), (h_30m_d as i64) * 24 * 60 * 60 * 1000);
    candle_horizon_ms.insert("1h".to_string(), (h_1h_d as i64) * 24 * 60 * 60 * 1000);

    // Retention: by default we keep 3m/5m append-only so the local SQLite DB can grow beyond
    // Hyperliquid's last-5,000-bar backfill window. Set an empty value to re-enable pruning:
    //   AI_QUANT_CANDLE_PRUNE_DISABLE_INTERVALS=
    let prune_disable_raw = env_string("AI_QUANT_CANDLE_PRUNE_DISABLE_INTERVALS", "3m,5m");
    let candle_prune_disable_intervals: HashSet<String> = parse_intervals_csv(&prune_disable_raw)
        .into_iter()
        .collect();

    let candle_persist_secs = env_u64("HL_WS_CANDLE_PERSIST_SECS", 60);
    let max_event_queue = env_usize("HL_WS_MAX_EVENT_QUEUE", 5000);
    // Incoming message queue between the WS reader and the JSON processor. When full, new messages
    // are dropped to keep the socket healthy; state is self-healing since we only need the latest
    // market data and user queues are bounded.
    let max_incoming_queue = env_usize("HL_WS_MAX_INCOMING_QUEUE", 2000);
    let db_timeout_s = env_u64("AI_QUANT_DB_TIMEOUT_S", 30);

    let ws_candle_reset_window_secs = env_u64("AI_QUANT_WS_CANDLE_RESET_WINDOW_SECS", 300);
    let ws_candle_max_resets_in_window = env_usize("AI_QUANT_WS_CANDLE_MAX_RESETS_IN_WINDOW", 3);
    let ws_candle_disable_secs = env_u64("AI_QUANT_WS_CANDLE_DISABLE_SECS", 600);

    let client_ttl_secs = env_u64("AI_QUANT_WS_CLIENT_TTL_SECS", 90);

    let always_symbols: HashSet<String> =
        parse_symbols_csv(&env_string("AI_QUANT_SIDECAR_SYMBOLS", ""))
            .into_iter()
            .collect();
    let always_intervals: Vec<String> =
        parse_intervals_csv(&env_string("AI_QUANT_SIDECAR_INTERVALS", ""));
    let always_candle_limit: usize = env_usize("AI_QUANT_SIDECAR_CANDLE_LIMIT", 2000);

    Config {
        ws_url,
        info_url,
        sock_path,
        candles_db_dir,
        enable_meta,
        enable_candle_ws,
        enable_bbo,
        mids_from_bbo,
        mids_from_bbo_fallback_age_s,
        bbo_snapshots_enable,
        bbo_snapshots_db_path,
        bbo_snapshots_sample_ms,
        bbo_snapshots_retention_hours,
        bbo_snapshots_retention_sweep_secs,
        bbo_snapshots_max_queue,
        reconnect_secs,
        ping_secs,
        sub_send_ms,

        candles_enable,
        candle_verify_secs,
        rest_timeout_s,
        rest_min_gap_ms,
        rest_max_inflight,
        rest_chunk_bars,
        candle_horizon_ms,
        candle_prune_disable_intervals,

        candle_persist_secs,
        max_event_queue,
        max_incoming_queue,
        db_timeout_s,

        ws_candle_reset_window_secs,
        ws_candle_max_resets_in_window,
        ws_candle_disable_secs,

        client_ttl_secs,

        always_symbols,
        always_intervals,
        always_candle_limit,
    }
}

#[derive(Clone, Debug)]
struct Candle {
    t: i64,
    t_close: Option<i64>,
    o: Option<f64>,
    h: Option<f64>,
    l: Option<f64>,
    c: Option<f64>,
    v: Option<f64>,
    n: Option<i64>,
}

#[derive(Clone, Debug)]
struct ClientDesired {
    symbols: HashSet<String>,
    interval: String,
    candle_limit: usize,
    user: Option<String>,
    last_seen: Instant,
}

#[derive(Clone, Debug, Default)]
struct CandleHealth {
    checked_at_ms: i64,
    ready: bool,
    have_count: i64,
    expected_count: i64,
    min_t: Option<i64>,
    max_t: Option<i64>,
    max_t_close: Option<i64>,
    last_ok_backfill_ms: Option<i64>,
    last_err_backfill: Option<String>,
}

#[derive(Default)]
struct State {
    // Desired sets are the union across clients.
    desired_symbols: HashSet<String>,
    desired_candles: HashSet<(String, String)>, // (symbol, interval)
    desired_candle_limit: HashMap<(String, String), usize>,
    desired_user: Option<String>,
    clients: HashMap<String, ClientDesired>,

    candle_health: HashMap<(String, String), CandleHealth>,

    ws_candle_disabled_until: Option<Instant>,
    ws_candle_resets: VecDeque<Instant>,

    mids: HashMap<String, f64>,
    mids_updated_at: Option<Instant>,
    mids_seq: u64,

    bbo: HashMap<String, (f64, f64)>,
    bbo_updated_at: HashMap<String, Instant>,
    bbo_seq: u64,

    candles: HashMap<(String, String), VecDeque<Candle>>,
    candle_updated_at: HashMap<(String, String), Instant>,
    last_t_seen: HashMap<(String, String), i64>,
    candle_last_persist_at: HashMap<(String, String), Instant>,

    user_fills: VecDeque<Value>,
    order_updates: VecDeque<Value>,
    user_fundings: VecDeque<Value>,
    user_ledger_updates: VecDeque<Value>,

    connected: bool,

    // WS observability.
    ws_connect_attempt: u64,
    ws_connected_at_ms: Option<i64>,
    ws_disconnect_count: u64,
    ws_last_disconnect_ms: Option<i64>,
    ws_last_close: Option<String>,
    ws_last_close_ms: Option<i64>,
    ws_last_error: Option<String>,
    ws_last_error_ms: Option<i64>,
    ws_incoming_drops_full: u64,
    ws_incoming_drops_closed: u64,
    ws_last_incoming_drop_ms: Option<i64>,
}

#[derive(Clone, Hash, PartialEq, Eq)]
enum SubKey {
    AllMids,
    Meta,
    Candle { coin: String, interval: String },
    Bbo { coin: String },
    UserFills { user: String },
    OrderUpdates { user: String },
    UserFundings { user: String },
    UserNonFundingLedgerUpdates { user: String },
}

impl SubKey {
    fn to_subscription_json(&self) -> Value {
        match self {
            SubKey::AllMids => json!({"type":"allMids"}),
            SubKey::Meta => json!({"type":"meta"}),
            SubKey::Candle { coin, interval } => {
                json!({"type":"candle","coin":coin,"interval":interval})
            }
            SubKey::Bbo { coin } => json!({"type":"bbo","coin":coin}),
            SubKey::UserFills { user } => json!({"type":"userFills","user":user}),
            SubKey::OrderUpdates { user } => json!({"type":"orderUpdates","user":user}),
            SubKey::UserFundings { user } => json!({"type":"userFundings","user":user}),
            SubKey::UserNonFundingLedgerUpdates { user } => {
                json!({"type":"userNonFundingLedgerUpdates","user":user})
            }
        }
    }
}

fn enqueue_sub_if_needed(
    sub: SubKey,
    subscribed: &HashSet<SubKey>,
    pending: &mut HashSet<SubKey>,
    pending_q: &mut VecDeque<SubKey>,
) {
    if subscribed.contains(&sub) || pending.contains(&sub) {
        return;
    }
    pending.insert(sub.clone());
    pending_q.push_back(sub);
}

fn build_desired_subs(st: &State, cfg: &Config) -> Vec<SubKey> {
    let mut out: Vec<SubKey> = Vec::new();
    out.push(SubKey::AllMids);
    if cfg.enable_meta {
        out.push(SubKey::Meta);
    }
    let candle_ws_enabled = cfg.candles_enable
        && cfg.enable_candle_ws
        && st
            .ws_candle_disabled_until
            .map(|t| t <= Instant::now())
            .unwrap_or(true);
    if candle_ws_enabled {
        for (sym, interval) in st.desired_candles.iter() {
            out.push(SubKey::Candle {
                coin: sym.clone(),
                interval: interval.clone(),
            });
        }
    }
    if cfg.enable_bbo {
        for sym in st.desired_symbols.iter() {
            out.push(SubKey::Bbo { coin: sym.clone() });
        }
    }
    if let Some(user) = st.desired_user.as_ref() {
        out.push(SubKey::UserFills { user: user.clone() });
        out.push(SubKey::OrderUpdates { user: user.clone() });
        out.push(SubKey::UserFundings { user: user.clone() });
        out.push(SubKey::UserNonFundingLedgerUpdates { user: user.clone() });
    }
    out
}

enum WsCommand {
    RefreshSubs,
    Restart,
}

#[derive(Clone)]
struct DbJob {
    symbol: String,
    interval: String,
    t: i64,
    t_close: Option<i64>,
    o: Option<f64>,
    h: Option<f64>,
    l: Option<f64>,
    c: Option<f64>,
    v: Option<f64>,
    n: Option<i64>,
}

fn ensure_db(conn: &Connection) -> Result<()> {
    // Pragmas (best-effort).
    let _ = conn.execute_batch("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;");

    conn.execute_batch(
        r#"
        CREATE TABLE IF NOT EXISTS candles (
            symbol TEXT NOT NULL,
            interval TEXT NOT NULL,
            t INTEGER NOT NULL,
            t_close INTEGER,
            o REAL,
            h REAL,
            l REAL,
            c REAL,
            v REAL,
            n INTEGER,
            updated_at TEXT,
            PRIMARY KEY (symbol, interval, t)
        );
        CREATE INDEX IF NOT EXISTS idx_candles_symbol_interval_t
        ON candles(symbol, interval, t);
        "#,
    )?;
    Ok(())
}

fn ensure_bbo_snapshots_db(conn: &Connection) -> Result<()> {
    // Pragmas (best-effort).
    let _ = conn.execute_batch("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;");

    conn.execute_batch(
        r#"
        CREATE TABLE IF NOT EXISTS bbo_snapshots (
            symbol TEXT NOT NULL,
            ts_ms INTEGER NOT NULL,
            bid REAL NOT NULL,
            ask REAL NOT NULL,
            mid REAL NOT NULL,
            updated_at TEXT,
            PRIMARY KEY (symbol, ts_ms)
        );
        CREATE INDEX IF NOT EXISTS idx_bbo_snapshots_ts_ms
        ON bbo_snapshots(ts_ms);
        "#,
    )?;
    Ok(())
}

#[derive(Clone, Debug)]
struct BboSnapshotJob {
    symbol: String,
    ts_ms: i64,
    bid: f64,
    ask: f64,
    mid: f64,
}

#[derive(Debug)]
enum BboSnapshotMsg {
    Insert(BboSnapshotJob),
    Sweep,
}

#[derive(Clone)]
struct BboSnapshotStore {
    tx: tokio_mpsc::Sender<BboSnapshotMsg>,
}

impl BboSnapshotStore {
    fn start(cfg: &Config) -> Self {
        let max_queue = cfg.bbo_snapshots_max_queue.max(1);
        let (tx, mut rx) = tokio_mpsc::channel::<BboSnapshotMsg>(max_queue);

        let db_path = cfg.bbo_snapshots_db_path.clone();
        let timeout = Duration::from_secs(cfg.db_timeout_s.max(1));
        let retention_hours = cfg.bbo_snapshots_retention_hours.max(1);

        std::thread::spawn(move || {
            if let Some(parent) = Path::new(&db_path).parent() {
                let _ = fs::create_dir_all(parent);
            }

            let conn = match Connection::open(&db_path) {
                Ok(c) => c,
                Err(e) => {
                    eprintln!("bbo snapshots db open failed: {e}");
                    return;
                }
            };
            let _ = conn.busy_timeout(timeout);
            if let Err(e) = ensure_bbo_snapshots_db(&conn) {
                eprintln!("bbo snapshots db init failed: {e}");
                return;
            }

            let mut stmt = match conn.prepare(
                r#"
                INSERT INTO bbo_snapshots (symbol, ts_ms, bid, ask, mid, updated_at)
                VALUES (?1, ?2, ?3, ?4, ?5, ?6)
                ON CONFLICT(symbol, ts_ms) DO UPDATE SET
                    bid = excluded.bid,
                    ask = excluded.ask,
                    mid = excluded.mid,
                    updated_at = excluded.updated_at
                "#,
            ) {
                Ok(s) => s,
                Err(e) => {
                    eprintln!("bbo snapshots db prepare failed: {e}");
                    return;
                }
            };

            while let Some(msg) = rx.blocking_recv() {
                match msg {
                    BboSnapshotMsg::Insert(job) => {
                        let updated_at =
                            Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
                        let res = stmt.execute((
                            job.symbol, job.ts_ms, job.bid, job.ask, job.mid, updated_at,
                        ));
                        if let Err(e) = res {
                            if !e.to_string().to_ascii_lowercase().contains("locked") {
                                eprintln!("bbo snapshots db write failed: {e}");
                            }
                        }
                    }
                    BboSnapshotMsg::Sweep => {
                        let retention_ms = (retention_hours as i64).saturating_mul(3_600_000);
                        let cutoff_ts_ms = now_ms_i64().saturating_sub(retention_ms);
                        match sweep_bbo_snapshots_db(&conn, cutoff_ts_ms) {
                            Ok(n) => {
                                if n > 0 {
                                    eprintln!("bbo snapshots retention sweep deleted_rows={n}");
                                }
                            }
                            Err(e) => {
                                if !e.to_string().to_ascii_lowercase().contains("locked") {
                                    eprintln!("bbo snapshots retention sweep failed: {e}");
                                }
                            }
                        }
                    }
                }
            }
        });

        Self { tx }
    }
}

struct BboSnapshotSampler {
    tx: tokio_mpsc::Sender<BboSnapshotMsg>,
    sample_every: Duration,
    last_sampled_at: HashMap<String, Instant>,
    drops_full: u64,
    drops_closed: u64,
}

impl BboSnapshotSampler {
    fn new(sample_ms: u64, tx: tokio_mpsc::Sender<BboSnapshotMsg>) -> Self {
        Self {
            tx,
            sample_every: Duration::from_millis(sample_ms.max(1)),
            last_sampled_at: HashMap::new(),
            drops_full: 0,
            drops_closed: 0,
        }
    }

    fn on_bbo(&mut self, symbol: &str, bid: f64, ask: f64, now: Instant) {
        if let Some(prev) = self.last_sampled_at.get_mut(symbol) {
            if now.duration_since(*prev) < self.sample_every {
                return;
            }
            *prev = now;
        } else {
            self.last_sampled_at.insert(symbol.to_string(), now);
        }

        let ts_ms = now_ms_i64();
        let mid = (bid + ask) / 2.0;
        let msg = BboSnapshotMsg::Insert(BboSnapshotJob {
            symbol: symbol.to_string(),
            ts_ms,
            bid,
            ask,
            mid,
        });

        match self.tx.try_send(msg) {
            Ok(_) => {}
            Err(tokio_mpsc::error::TrySendError::Full(_)) => {
                self.drops_full = self.drops_full.saturating_add(1);
            }
            Err(tokio_mpsc::error::TrySendError::Closed(_)) => {
                self.drops_closed = self.drops_closed.saturating_add(1);
            }
        }
    }
}

fn sweep_bbo_snapshots_db(conn: &Connection, cutoff_ts_ms: i64) -> Result<usize> {
    Ok(conn.execute(
        "DELETE FROM bbo_snapshots WHERE ts_ms < ?1",
        (cutoff_ts_ms,),
    )?)
}

fn sanitize_interval(interval: &str) -> String {
    let mut out = String::new();
    for ch in interval.chars() {
        if ch.is_ascii_alphanumeric() {
            out.push(ch.to_ascii_lowercase());
        } else {
            out.push('_');
        }
    }
    if out.is_empty() {
        "unknown".to_string()
    } else {
        out
    }
}

fn db_path_for_interval(cfg: &Config, interval: &str) -> String {
    let dir = cfg.candles_db_dir.trim_end_matches('/').to_string();
    let name = sanitize_interval(interval);
    format!("{}/candles_{}.db", dir, name)
}

fn cli_usage() -> &'static str {
    "Usage:\n  openclaw-ai-quant-ws-sidecar stat --interval <1m|5m|30m|1h> --symbols <BTC,ETH,...> [--bars N] [--db-dir PATH] [--json]\n\n\
Examples:\n  openclaw-ai-quant-ws-sidecar stat --interval 1m --symbols BTC,ETH --bars 1500\n  AI_QUANT_CANDLES_DB_DIR=./candles_dbs openclaw-ai-quant-ws-sidecar stat --interval 1h --symbols BTC\n"
}

fn parse_cli_kv(args: &[String]) -> HashMap<String, String> {
    let mut out = HashMap::new();
    let mut i = 0usize;
    while i < args.len() {
        let a = args[i].as_str();
        if a.starts_with("--") {
            let k = a.trim_start_matches("--").to_string();
            if i + 1 < args.len() && !args[i + 1].starts_with("--") {
                out.insert(k, args[i + 1].clone());
                i += 2;
                continue;
            }
            out.insert(k, "true".to_string());
            i += 1;
            continue;
        }
        i += 1;
    }
    out
}

fn parse_symbols_csv(raw: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut seen: HashSet<String> = HashSet::new();
    for part in raw.split(',') {
        let s = part.trim().to_ascii_uppercase();
        if s.is_empty() {
            continue;
        }
        if seen.insert(s.clone()) {
            out.push(s);
        }
    }
    out
}

fn canonical_interval(raw: &str) -> String {
    let mut s = raw.trim().to_ascii_lowercase();
    // Common alias: "1hr" -> "1h".
    if s.ends_with("hr") {
        let base = s.trim_end_matches("hr");
        if !base.is_empty() {
            s = format!("{base}h");
        }
    }
    s
}

fn parse_intervals_csv(raw: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut seen: HashSet<String> = HashSet::new();
    for part in raw.split(',') {
        let s = canonical_interval(part);
        if s.is_empty() {
            continue;
        }
        if seen.insert(s.clone()) {
            out.push(s);
        }
    }
    out
}

fn prune_enabled_for_interval_key(
    prune_disable_intervals: &HashSet<String>,
    interval_key: &str,
) -> bool {
    !interval_key.is_empty() && !prune_disable_intervals.contains(interval_key)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    static ENV_LOCK: Mutex<()> = Mutex::new(());

    fn set_env(key: &str, val: &str) -> Option<String> {
        let prev = env::var(key).ok();
        unsafe {
            env::set_var(key, val);
        }
        prev
    }

    fn restore_env(key: &str, prev: Option<String>) {
        match prev {
            Some(v) => unsafe {
                env::set_var(key, v);
            },
            None => unsafe {
                env::remove_var(key);
            },
        }
    }

    #[test]
    fn canonical_interval_lowercases_and_normalises_hr() {
        assert_eq!(canonical_interval("3M"), "3m");
        assert_eq!(canonical_interval(" 1HR "), "1h");
        assert_eq!(canonical_interval("15m"), "15m");
    }

    #[test]
    fn parse_intervals_csv_dedupes_and_canonicalises() {
        assert_eq!(
            parse_intervals_csv("1h,1HR, 5m ,5M"),
            vec!["1h".to_string(), "5m".to_string()]
        );
        assert_eq!(parse_intervals_csv(""), Vec::<String>::new());
    }

    #[test]
    fn prune_enabled_for_interval_key_respects_disable_list() {
        let mut disabled: HashSet<String> = HashSet::new();
        disabled.insert("3m".to_string());

        assert!(!prune_enabled_for_interval_key(&disabled, ""));
        assert!(!prune_enabled_for_interval_key(&disabled, "3m"));
        assert!(prune_enabled_for_interval_key(&disabled, "5m"));
    }

    #[test]
    fn load_config_clamps_bbo_snapshot_env_vars() {
        let _guard = ENV_LOCK.lock().unwrap();

        let prev_sample = set_env("AI_QUANT_BBO_SNAPSHOTS_SAMPLE_MS", "0");
        let prev_retention = set_env("AI_QUANT_BBO_SNAPSHOTS_RETENTION_HOURS", "0");
        let prev_sweep = set_env("AI_QUANT_BBO_SNAPSHOTS_RETENTION_SWEEP_SECS", "1");
        let prev_queue = set_env("AI_QUANT_BBO_SNAPSHOTS_MAX_QUEUE", "0");

        let cfg = load_config();

        assert_eq!(cfg.bbo_snapshots_sample_ms, 1);
        assert_eq!(cfg.bbo_snapshots_retention_hours, 1);
        assert_eq!(cfg.bbo_snapshots_retention_sweep_secs, 30);
        assert_eq!(cfg.bbo_snapshots_max_queue, 1);

        restore_env("AI_QUANT_BBO_SNAPSHOTS_SAMPLE_MS", prev_sample);
        restore_env("AI_QUANT_BBO_SNAPSHOTS_RETENTION_HOURS", prev_retention);
        restore_env("AI_QUANT_BBO_SNAPSHOTS_RETENTION_SWEEP_SECS", prev_sweep);
        restore_env("AI_QUANT_BBO_SNAPSHOTS_MAX_QUEUE", prev_queue);
    }

    #[test]
    fn apply_all_mids_snapshot_bumps_seq_only_on_value_change() {
        let now = Instant::now();
        let mut st = State::default();
        let mut mids = serde_json::Map::new();
        mids.insert("BTC".to_string(), json!("100.0"));

        assert!(apply_all_mids_snapshot(&mut st, &mids, now, false, 5.0));
        assert_eq!(st.mids.get("BTC").copied(), Some(100.0));
        assert_eq!(st.mids_seq, 1);

        assert!(!apply_all_mids_snapshot(
            &mut st,
            &mids,
            now + Duration::from_secs(1),
            false,
            5.0
        ));
        assert_eq!(st.mids_seq, 1);
    }

    #[test]
    fn apply_all_mids_snapshot_prefers_fresh_bbo_when_bbo_mode_enabled() {
        let now = Instant::now();
        let mut st = State::default();
        st.bbo.insert("BTC".to_string(), (99.0, 101.0));
        st.bbo_updated_at.insert("BTC".to_string(), now);

        let mut mids = serde_json::Map::new();
        mids.insert("BTC".to_string(), json!("123.0"));

        assert!(!apply_all_mids_snapshot(&mut st, &mids, now, true, 5.0));
        assert_eq!(st.mids.get("BTC"), None);
        assert_eq!(st.mids_seq, 0);

        let later = now + Duration::from_secs(6);
        assert!(apply_all_mids_snapshot(&mut st, &mids, later, true, 5.0));
        assert_eq!(st.mids.get("BTC").copied(), Some(123.0));
        assert_eq!(st.mids_seq, 1);
    }

    #[test]
    fn apply_bbo_mid_tick_updates_seq_when_enabled_and_mid_changes() {
        let now = Instant::now();
        let mut st = State::default();
        st.mids.insert("BTC".to_string(), 100.0);

        assert!(!apply_bbo_mid_tick(&mut st, "BTC", 99.0, 101.0, now, true));
        assert_eq!(st.mids_seq, 0);

        assert!(apply_bbo_mid_tick(
            &mut st,
            "BTC",
            100.0,
            102.0,
            now + Duration::from_millis(10),
            true
        ));
        assert_eq!(st.mids.get("BTC").copied(), Some(101.0));
        assert_eq!(st.mids_seq, 1);

        assert!(!apply_bbo_mid_tick(
            &mut st,
            "BTC",
            100.0,
            102.0,
            now + Duration::from_millis(20),
            false
        ));
        assert_eq!(st.mids_seq, 1);
    }

    #[test]
    fn sweep_bbo_snapshots_db_deletes_old_rows() {
        let conn = Connection::open_in_memory().unwrap();
        ensure_bbo_snapshots_db(&conn).unwrap();

        for (sym, ts_ms) in [
            ("BTC", 1000i64),
            ("BTC", 2000),
            ("BTC", 3000),
            ("ETH", 1500),
        ] {
            conn.execute(
                "INSERT INTO bbo_snapshots (symbol, ts_ms, bid, ask, mid) VALUES (?1, ?2, 1.0, 2.0, 1.5)",
                (sym, ts_ms),
            )
            .unwrap();
        }

        let deleted = sweep_bbo_snapshots_db(&conn, 2500).unwrap();
        assert_eq!(deleted, 3);

        let remaining: i64 = conn
            .query_row("SELECT COUNT(*) FROM bbo_snapshots", [], |row| row.get(0))
            .unwrap();
        assert_eq!(remaining, 1);

        let ts: i64 = conn
            .query_row("SELECT ts_ms FROM bbo_snapshots", [], |row| row.get(0))
            .unwrap();
        assert_eq!(ts, 3000);
    }
}

#[derive(Default)]
struct CandleDbStat {
    symbol: String,
    interval: String,
    db_path: String,
    bars_wanted: usize,

    rows: usize,
    null_ohlcv: usize,
    min_t: Option<i64>,
    max_t: Option<i64>,
    max_t_close: Option<i64>,

    gap_bars: i64,
    max_gap_bars: i64,
    out_of_order: bool,

    last_close_age_s: Option<f64>,
    close_span_ms_mode: Option<i64>,
}

fn compute_db_stat(
    db_path: &str,
    symbol: &str,
    interval: &str,
    bars_wanted: usize,
) -> Result<CandleDbStat> {
    let sym_u = symbol.trim().to_ascii_uppercase();
    let interval_s = canonical_interval(interval);
    if interval_s.is_empty() {
        return Err(anyhow!("interval is empty"));
    }

    let mut st = CandleDbStat::default();
    st.symbol = sym_u.clone();
    st.interval = interval_s.clone();
    st.db_path = db_path.to_string();
    st.bars_wanted = bars_wanted;

    let interval_ms = interval_to_ms(&interval_s).max(1);
    let now_ms = now_ms_i64();

    let timeout_s = env_u64("AI_QUANT_DB_TIMEOUT_S", 30).max(1);
    let timeout = Duration::from_secs(timeout_s);

    let conn = Connection::open(db_path).context("open candles db")?;
    let _ = conn.busy_timeout(timeout);
    ensure_db(&conn)?;

    let limit = (bars_wanted.saturating_add(500)).max(100);
    let mut stmt = conn.prepare(
        r#"
        SELECT t, t_close, o, h, l, c, v
        FROM candles
        WHERE symbol = ?1 AND interval = ?2
        ORDER BY t DESC
        LIMIT ?3
        "#,
    )?;

    let mut rows: Vec<(
        i64,
        Option<i64>,
        Option<f64>,
        Option<f64>,
        Option<f64>,
        Option<f64>,
        Option<f64>,
    )> = Vec::new();
    let mut iter = stmt.query((sym_u.clone(), interval_s.clone(), limit as i64))?;
    while let Some(row) = iter.next()? {
        let t: i64 = row.get(0)?;
        let t_close: Option<i64> = row.get(1)?;
        let o: Option<f64> = row.get(2)?;
        let h: Option<f64> = row.get(3)?;
        let l: Option<f64> = row.get(4)?;
        let c: Option<f64> = row.get(5)?;
        let v: Option<f64> = row.get(6)?;
        rows.push((t, t_close, o, h, l, c, v));
    }

    if rows.is_empty() {
        return Ok(st);
    }

    // The query is newest-first. Reverse to chronological.
    rows.reverse();

    st.rows = rows.len();
    st.min_t = rows.first().map(|r| r.0);
    st.max_t = rows.last().map(|r| r.0);
    st.max_t_close = rows.last().and_then(|r| r.1);

    // Null checks + close-span mode.
    let mut span_freq: HashMap<i64, i64> = HashMap::new();
    for (t, t_close, o, h, l, c, v) in rows.iter() {
        if o.is_none() || h.is_none() || l.is_none() || c.is_none() || v.is_none() {
            st.null_ohlcv += 1;
        }
        if let Some(tc) = t_close {
            span_freq
                .entry(tc.saturating_sub(*t))
                .and_modify(|n| *n += 1)
                .or_insert(1);
        }
    }
    if !span_freq.is_empty() {
        let mut best: Option<(i64, i64)> = None;
        for (span, n) in span_freq.into_iter() {
            best = match best {
                None => Some((span, n)),
                Some((bspan, bn)) => {
                    if n > bn {
                        Some((span, n))
                    } else {
                        Some((bspan, bn))
                    }
                }
            };
        }
        st.close_span_ms_mode = best.map(|(span, _)| span);
    }

    // Gap stats.
    let tol_ms = (interval_ms / 10).max(1_000).min(2_000);
    let mut prev_t: Option<i64> = None;
    for (t, _t_close, _o, _h, _l, _c, _v) in rows.iter() {
        if let Some(pt) = prev_t {
            if *t <= pt {
                st.out_of_order = true;
            } else {
                let diff = t.saturating_sub(pt);
                if diff > interval_ms.saturating_add(tol_ms) {
                    let steps = diff / interval_ms;
                    if steps > 1 {
                        let missing = (steps - 1).max(0);
                        st.gap_bars = st.gap_bars.saturating_add(missing);
                        if missing > st.max_gap_bars {
                            st.max_gap_bars = missing;
                        }
                    }
                }
            }
        }
        prev_t = Some(*t);
    }

    // Freshness.
    let last_close = st.max_t_close.or_else(|| st.max_t.map(|t| t + interval_ms));
    if let Some(lc) = last_close {
        st.last_close_age_s = Some(((now_ms - lc).max(0) as f64) / 1000.0);
    }

    Ok(st)
}

fn print_db_stat_human(st: &CandleDbStat) {
    let rows = st.rows;
    let bars_ok = rows >= st.bars_wanted;
    let gaps_ok = st.gap_bars == 0 && !st.out_of_order;
    let null_ok = st.null_ohlcv == 0;
    let age_s = st.last_close_age_s.unwrap_or(f64::INFINITY);

    println!(
        "{} {} rows={} want>={} bars_ok={} gaps={} max_gap={} null_ohlcv={} null_ok={} last_close_age_s={:.1} min_t={:?} max_t={:?} max_t_close={:?} close_span_ms_mode={:?}",
        st.symbol,
        st.interval,
        rows,
        st.bars_wanted,
        if bars_ok { "yes" } else { "no" },
        st.gap_bars,
        st.max_gap_bars,
        st.null_ohlcv,
        if null_ok { "yes" } else { "no" },
        age_s,
        st.min_t,
        st.max_t,
        st.max_t_close,
        st.close_span_ms_mode
    );
    if !bars_ok || !gaps_ok || !null_ok {
        println!(
            "  quality: bars_ok={} gaps_ok={} null_ok={} (db={})",
            if bars_ok { "yes" } else { "no" },
            if gaps_ok { "yes" } else { "no" },
            if null_ok { "yes" } else { "no" },
            st.db_path
        );
    }
}

#[derive(Clone)]
struct DbWorkers {
    cfg: Config,
    senders: Arc<Mutex<HashMap<String, mpsc::Sender<DbJob>>>>,
}

impl DbWorkers {
    fn new(cfg: &Config) -> Self {
        Self {
            cfg: cfg.clone(),
            senders: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    fn sender_for(&self, interval: &str) -> mpsc::Sender<DbJob> {
        let key = interval.trim().to_ascii_lowercase();
        {
            let guard = self.senders.lock().unwrap();
            if let Some(tx) = guard.get(&key) {
                return tx.clone();
            }
        }

        // Start a new worker lazily.
        let db_path = db_path_for_interval(&self.cfg, &key);
        let timeout = Duration::from_secs(self.cfg.db_timeout_s);
        let (tx, rx) = mpsc::channel::<DbJob>();

        {
            let mut guard = self.senders.lock().unwrap();
            // Double-check (another thread may have created it).
            if let Some(existing) = guard.get(&key) {
                return existing.clone();
            }
            guard.insert(key.clone(), tx.clone());
        }

        std::thread::spawn(move || {
            if let Some(parent) = Path::new(&db_path).parent() {
                let _ = fs::create_dir_all(parent);
            }

            let conn = match Connection::open(&db_path) {
                Ok(c) => c,
                Err(e) => {
                    eprintln!("db open failed: {e}");
                    return;
                }
            };
            let _ = conn.busy_timeout(timeout);
            if let Err(e) = ensure_db(&conn) {
                eprintln!("db init failed: {e}");
                return;
            }

            let mut stmt = match conn.prepare(
                r#"
                INSERT INTO candles (symbol, interval, t, t_close, o, h, l, c, v, n, updated_at)
                VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11)
                ON CONFLICT(symbol, interval, t) DO UPDATE SET
                    t_close = excluded.t_close,
                    o = excluded.o,
                    h = excluded.h,
                    l = excluded.l,
                    c = excluded.c,
                    v = excluded.v,
                    n = excluded.n,
                    updated_at = excluded.updated_at
                "#,
            ) {
                Ok(s) => s,
                Err(e) => {
                    eprintln!("db prepare failed: {e}");
                    return;
                }
            };

            while let Ok(job) = rx.recv() {
                let updated_at = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
                let res = stmt.execute((
                    job.symbol,
                    job.interval,
                    job.t,
                    job.t_close,
                    job.o,
                    job.h,
                    job.l,
                    job.c,
                    job.v,
                    job.n,
                    updated_at,
                ));
                if let Err(e) = res {
                    // Keep non-fatal: a later persist will repair.
                    if !e.to_string().to_ascii_lowercase().contains("locked") {
                        eprintln!("db write failed: {e}");
                    }
                }
            }
        });

        tx
    }

    fn send(&self, job: DbJob) {
        let tx = self.sender_for(&job.interval);
        let _ = tx.send(job);
    }
}

fn now_epoch_s_f64() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

fn now_ms_i64() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

fn parse_f64(v: &Value) -> Option<f64> {
    if let Some(f) = v.as_f64() {
        return Some(f);
    }
    if let Some(s) = v.as_str() {
        return s.parse::<f64>().ok();
    }
    None
}

fn parse_i64(v: &Value) -> Option<i64> {
    if let Some(i) = v.as_i64() {
        return Some(i);
    }
    if let Some(u) = v.as_u64() {
        return Some(u as i64);
    }
    if let Some(s) = v.as_str() {
        return s.parse::<i64>().ok();
    }
    None
}

fn valid_price(px: f64) -> bool {
    px.is_finite() && px > 0.0
}

fn apply_all_mids_snapshot(
    st: &mut State,
    mids: &serde_json::Map<String, Value>,
    now: Instant,
    mids_from_bbo: bool,
    mids_from_bbo_fallback_age_s: f64,
) -> bool {
    let mut changed = false;
    for (sym, mid_val) in mids.iter() {
        let sym_u = sym.to_ascii_uppercase();
        if mids_from_bbo {
            if let Some(ts) = st.bbo_updated_at.get(&sym_u) {
                let bbo_age_s = now.duration_since(*ts).as_secs_f64();
                if bbo_age_s <= mids_from_bbo_fallback_age_s {
                    // Fresh BBO takes precedence in BBO-driven mode.
                    continue;
                }
            }
        }
        let Some(px) = parse_f64(mid_val) else {
            continue;
        };
        if !valid_price(px) {
            continue;
        }
        if st.mids.get(&sym_u).copied() != Some(px) {
            st.mids.insert(sym_u, px);
            changed = true;
        }
    }
    if changed {
        st.mids_updated_at = Some(now);
        st.mids_seq = st.mids_seq.wrapping_add(1);
    }
    changed
}

fn apply_bbo_mid_tick(
    st: &mut State,
    symbol: &str,
    bid: f64,
    ask: f64,
    now: Instant,
    mids_from_bbo: bool,
) -> bool {
    if !mids_from_bbo || !valid_price(bid) || !valid_price(ask) {
        return false;
    }
    let mid = (bid + ask) / 2.0;
    if !valid_price(mid) {
        return false;
    }
    let sym_u = symbol.to_ascii_uppercase();
    if st.mids.get(&sym_u).copied() == Some(mid) {
        return false;
    }
    st.mids.insert(sym_u, mid);
    st.mids_updated_at = Some(now);
    st.mids_seq = st.mids_seq.wrapping_add(1);
    true
}

fn horizon_ms_for_interval(cfg: &Config, interval: &str) -> i64 {
    let k = interval.trim().to_ascii_lowercase();
    if let Some(v) = cfg.candle_horizon_ms.get(&k) {
        return *v;
    }
    // Fallback: 24h.
    24 * 60 * 60 * 1000
}

fn buffer_ms_for_horizon(horizon_ms: i64) -> i64 {
    let h = horizon_ms.max(0);
    let ten_pct = h / 10;
    let min_ms = 6 * 60 * 60 * 1000; // 6h
    let max_ms = 7 * 24 * 60 * 60 * 1000; // 7d
    ten_pct.max(min_ms).min(max_ms)
}

async fn rest_pace(pacer: &Arc<tokio::sync::Mutex<Instant>>, cfg: &Config) {
    let gap_ms = cfg.rest_min_gap_ms;
    if gap_ms == 0 {
        return;
    }
    let gap = Duration::from_millis(gap_ms.max(1));

    // `pacer` stores the earliest time the next request is allowed to start.
    let sleep_until = {
        let mut guard = pacer.lock().await;
        let now = Instant::now();
        let when = if *guard > now { *guard } else { now };
        *guard = when + gap;
        when
    };

    let now = Instant::now();
    if sleep_until > now {
        tokio::time::sleep(sleep_until - now).await;
    }
}

async fn fetch_candle_snapshot(
    http: &Client,
    cfg: &Config,
    pacer: &Arc<tokio::sync::Mutex<Instant>>,
    symbol: &str,
    interval: &str,
    start_ms: i64,
    end_ms: i64,
) -> Result<Vec<Value>> {
    let coin = symbol.trim().to_ascii_uppercase();
    let interval_s = canonical_interval(interval);
    if interval_s.is_empty() {
        return Err(anyhow!("interval is empty"));
    }
    let payload = json!({
        "type": "candleSnapshot",
        "req": {
            "coin": coin,
            "interval": interval_s,
            "startTime": start_ms,
            "endTime": end_ms
        }
    });

    let timeout = Duration::from_secs(cfg.rest_timeout_s.max(1));
    let max_retries: usize = 3;
    let mut last_err: Option<anyhow::Error> = None;

    for attempt in 1..=max_retries {
        rest_pace(pacer, cfg).await;
        let res = http
            .post(cfg.info_url.as_str())
            .json(&payload)
            .timeout(timeout)
            .send()
            .await;

        let mut backoff: Option<Duration> = None;
        match res {
            Ok(resp) => {
                let status = resp.status();
                if !status.is_success() {
                    last_err = Some(anyhow!("REST candleSnapshot HTTP {status}"));
                    let is_429 = status.as_u16() == 429;
                    if is_429 {
                        // Respect Retry-After when present; otherwise do a larger backoff on rate limit.
                        let retry_after = resp
                            .headers()
                            .get("retry-after")
                            .and_then(|v| v.to_str().ok())
                            .and_then(|s| s.parse::<u64>().ok());
                        backoff = Some(
                            retry_after
                                .map(Duration::from_secs)
                                .unwrap_or_else(|| {
                                    Duration::from_secs((attempt as u64).saturating_mul(2).max(1))
                                })
                                .min(Duration::from_secs(60)),
                        );
                    }
                } else {
                    let v: Value = resp.json().await.context("REST candleSnapshot json")?;
                    if let Some(arr) = v.as_array() {
                        return Ok(arr.clone());
                    }
                    return Err(anyhow!("REST candleSnapshot bad response type"));
                }
            }
            Err(e) => {
                last_err = Some(anyhow!("REST candleSnapshot request failed: {e}"));
            }
        }

        if attempt < max_retries {
            // Simple backoff (or longer on 429).
            let d = backoff.unwrap_or_else(|| Duration::from_millis(200 * (attempt as u64).pow(2)));
            tokio::time::sleep(d).await;
        }
    }

    Err(last_err.unwrap_or_else(|| anyhow!("REST candleSnapshot failed")))
}

async fn rest_backfill_range(
    http: &Client,
    cfg: &Config,
    pacer: &Arc<tokio::sync::Mutex<Instant>>,
    state: &Arc<RwLock<State>>,
    db: &DbWorkers,
    symbol: &str,
    interval: &str,
    start_ms: i64,
    end_ms: i64,
) -> Result<usize> {
    let sym_u = symbol.trim().to_ascii_uppercase();
    let interval_s = canonical_interval(interval);
    if interval_s.is_empty() {
        return Err(anyhow!("interval is empty"));
    }
    let interval_ms = interval_to_ms(&interval_s).max(1);
    let chunk_bars = cfg.rest_chunk_bars.max(100);
    let chunk_ms = interval_ms
        .saturating_mul(chunk_bars as i64)
        .max(interval_ms);

    let mut cur = start_ms;
    let mut total: usize = 0;
    let mut tail: Vec<Candle> = Vec::new();

    while cur < end_ms {
        let chunk_end = (cur + chunk_ms).min(end_ms);
        let candles =
            fetch_candle_snapshot(http, cfg, pacer, &sym_u, &interval_s, cur, chunk_end).await?;

        for item in candles.iter() {
            let obj = match item.as_object() {
                Some(o) => o,
                None => continue,
            };
            let t = obj.get("t").and_then(parse_i64).unwrap_or(0);
            if t == 0 {
                continue;
            }
            let candle = Candle {
                t,
                t_close: obj.get("T").and_then(parse_i64),
                o: obj.get("o").and_then(parse_f64),
                h: obj.get("h").and_then(parse_f64),
                l: obj.get("l").and_then(parse_f64),
                c: obj.get("c").and_then(parse_f64),
                v: obj.get("v").and_then(parse_f64),
                n: obj.get("n").and_then(parse_i64),
            };

            db.send(DbJob {
                symbol: sym_u.clone(),
                interval: interval_s.clone(),
                t: candle.t,
                t_close: candle.t_close,
                o: candle.o,
                h: candle.h,
                l: candle.l,
                c: candle.c,
                v: candle.v,
                n: candle.n,
            });

            tail.push(candle);
            if tail.len() > 4 {
                tail.remove(0);
            }
            total += 1;
        }

        // Overlap one bar to avoid boundary gaps, but guarantee forward progress.
        let next_cur = chunk_end.saturating_sub(interval_ms);
        cur = if next_cur <= cur { chunk_end } else { next_cur };
        if chunk_end == end_ms {
            break;
        }
    }

    // Update in-memory tail cache so candle key hints work even with REST-only ingestion.
    if !tail.is_empty() {
        let mut st = state.write().await;
        let key = (sym_u.clone(), interval_s.clone());
        let q = st.candles.entry(key.clone()).or_insert_with(VecDeque::new);
        q.clear();
        for c in tail {
            q.push_back(c);
        }
        st.candle_updated_at.insert(key, Instant::now());
    }

    Ok(total)
}

async fn compute_db_health(
    cfg: &Config,
    symbol: &str,
    interval: &str,
    required_start_ms: i64,
    interval_ms: i64,
    now_ms: i64,
    min_required_count: i64,
) -> CandleHealth {
    let interval_s = canonical_interval(interval);
    let db_path = db_path_for_interval(cfg, &interval_s);
    let sym_u = symbol.trim().to_ascii_uppercase();
    let timeout = Duration::from_secs(cfg.db_timeout_s.max(1));

    let res = tokio::task::spawn_blocking(move || -> Result<(Option<i64>, Option<i64>, i64, Option<i64>)> {
        if let Some(parent) = Path::new(&db_path).parent() {
            let _ = fs::create_dir_all(parent);
        }
        let conn = Connection::open(&db_path)?;
        let _ = conn.busy_timeout(timeout);
        ensure_db(&conn)?;
        let mut stmt = conn.prepare(
            "SELECT MIN(t), MAX(t), COUNT(*), MAX(t_close) FROM candles WHERE symbol = ?1 AND interval = ?2 AND t >= ?3",
        )?;
        let row = stmt.query_row((sym_u, interval_s, required_start_ms), |row| {
            let min_t: Option<i64> = row.get(0)?;
            let max_t: Option<i64> = row.get(1)?;
            let cnt: i64 = row.get(2)?;
            let max_t_close: Option<i64> = row.get(3)?;
            Ok((min_t, max_t, cnt, max_t_close))
        })?;
        Ok(row)
    })
    .await;

    let mut h = CandleHealth::default();
    h.checked_at_ms = now_ms_i64();
    h.expected_count = ((now_ms - required_start_ms).max(0) / interval_ms.max(1)) + 1;

    match res {
        Ok(Ok((min_t, max_t, cnt, max_t_close))) => {
            h.min_t = min_t;
            h.max_t = max_t;
            h.have_count = cnt;
            h.max_t_close = max_t_close;

            let mut ok = true;

            // Start coverage.
            if let Some(min_t) = min_t {
                if min_t > (required_start_ms + interval_ms.saturating_mul(2)) {
                    ok = false;
                }
            } else {
                ok = false;
            }

            // Count coverage.
            if cnt < min_required_count {
                ok = false;
            }

            // Gap heuristic: count vs implied count in [min,max].
            if let (Some(min_t), Some(max_t)) = (min_t, max_t) {
                let implied = ((max_t - min_t).max(0) / interval_ms.max(1)) + 1;
                if implied > 0 {
                    let ratio = (cnt as f64) / (implied as f64);
                    if ratio < 0.98 {
                        ok = false;
                    }
                }
            }

            // Freshness: last close time should be near now (within ~2 intervals).
            let last_close = max_t_close.or_else(|| max_t.map(|t| t + interval_ms));
            if let Some(lc) = last_close {
                if lc < (now_ms - interval_ms.saturating_mul(2)) {
                    ok = false;
                }
            }

            h.ready = ok;
        }
        Ok(Err(e)) => {
            h.ready = false;
            h.last_err_backfill = Some(format!("db health query failed: {e}"));
        }
        Err(e) => {
            h.ready = false;
            h.last_err_backfill = Some(format!("db health join failed: {e}"));
        }
    }

    h
}

async fn candle_manager_loop(cfg: Config, state: Arc<RwLock<State>>, db: DbWorkers) -> Result<()> {
    if !cfg.candles_enable {
        return Ok(());
    }

    let http = Client::builder()
        .user_agent("openclaw-ai-quant-ws-sidecar")
        .build()
        .context("build reqwest client")?;

    let pacer = Arc::new(tokio::sync::Mutex::new(Instant::now()));
    let sem = Arc::new(Semaphore::new(cfg.rest_max_inflight.max(1)));
    let (done_tx, mut done_rx) = tokio_mpsc::unbounded_channel::<(String, String)>();
    let mut inflight: HashSet<(String, String)> = HashSet::new();

    let mut tick = tokio::time::interval(Duration::from_secs(cfg.candle_verify_secs.max(1)));

    let mut prune_every = 0u64;

    loop {
        tokio::select! {
            _ = tick.tick() => {
                prune_every = prune_every.wrapping_add(1);
                let keys: Vec<(String, String, usize)> = {
                    let st = state.read().await;
                    st.desired_candles
                        .iter()
                        .map(|(s, i)| {
                            let lim = st.desired_candle_limit.get(&(s.clone(), i.clone())).copied().unwrap_or(0);
                            (s.clone(), i.clone(), lim)
                        })
                        .collect()
                };

                let now_ms = now_ms_i64();

                // Periodic prune (best-effort).
                if prune_every % 6 == 0 {
                    // IMPORTANT:
                    // Prune must respect the largest requested candle_limit for each interval.
                    // Otherwise, longer-interval clients (e.g. 15m with 1500 lookback) can end up in a
                    // perpetual state where we backfill long horizons but immediately delete the old bars.
                    let mut interval_max_lim: HashMap<String, usize> = HashMap::new();
                    for (_sym, interval, lim) in keys.iter() {
                        let e = interval_max_lim.entry(interval.clone()).or_insert(0);
                        if *lim > *e {
                            *e = *lim;
                        }
                    }

                    for (interval, lim_max) in interval_max_lim {
                        let interval_k = canonical_interval(&interval);
                        if !prune_enabled_for_interval_key(&cfg.candle_prune_disable_intervals, &interval_k) {
                            continue;
                        }
                        let interval_ms = interval_to_ms(&interval_k).max(1);
                        let horizon_cfg = horizon_ms_for_interval(&cfg, &interval_k);
                        let lim_ms: i64 = if lim_max > 0 {
                            interval_ms.saturating_mul(lim_max as i64)
                        } else {
                            0
                        };
                        let horizon = horizon_cfg.max(lim_ms);
                        let buffer = buffer_ms_for_horizon(horizon);
                        let cutoff = now_ms.saturating_sub(horizon.saturating_add(buffer.saturating_mul(2)));
                        let db_path = db_path_for_interval(&cfg, &interval_k);
                        let interval_s = interval_k.clone();
                        let timeout = Duration::from_secs(cfg.db_timeout_s.max(1));
                        let _ = tokio::task::spawn_blocking(move || {
                            if let Some(parent) = Path::new(&db_path).parent() {
                                let _ = fs::create_dir_all(parent);
                            }
                            if let Ok(conn) = Connection::open(&db_path) {
                                let _ = conn.busy_timeout(timeout);
                                let _ = ensure_db(&conn);
                                let _ = conn.execute("DELETE FROM candles WHERE interval = ?1 AND t < ?2", (interval_s, cutoff));
                            }
                        }).await;
                    }
                }

                for (sym, interval_raw, lim) in keys {
                    let interval = canonical_interval(&interval_raw);
                    if interval.is_empty() {
                        continue;
                    }
                    let interval_ms = interval_to_ms(&interval).max(1);
                    let horizon_cfg = horizon_ms_for_interval(&cfg, &interval);

                    // IMPORTANT:
                    // Candle readiness must be feasible for longer intervals (e.g. 15m, 2h) and
                    // must scale with `candle_limit` (bars) requested by the Python engine.
                    //
                    // Previously, we used a fixed `expected + 50` slack based on the horizon only.
                    // For longer intervals where the default horizon is small (fallback 24h) this
                    // could make `min_required` exceed the maximum possible bars in the window
                    // (horizon + buffer), causing `ready=false` forever and flooding
                    // `CANDLES_NOT_READY_SAMPLE`.
                    let lim_i64 = lim as i64;
                    let lim_ms: i64 = if lim_i64 > 0 {
                        interval_ms.saturating_mul(lim_i64)
                    } else {
                        0
                    };
                    let horizon = horizon_cfg.max(lim_ms);
                    let buffer = buffer_ms_for_horizon(horizon);
                    let required_start = now_ms.saturating_sub(horizon.saturating_add(buffer));

                    // `expected` is based on the requested horizon (not including buffer).
                    let expected = (horizon / interval_ms).max(1) + 1;
                    // Slack bars must never exceed what the buffer can actually provide, otherwise
                    // min_required can become impossible to satisfy for longer intervals.
                    let buffer_bars = (buffer / interval_ms).max(0);
                    let slack_bars = buffer_bars.min(50);
                    let min_required = (expected + slack_bars).max(lim_i64);

                    let mut health =
                        compute_db_health(&cfg, &sym, &interval, required_start, interval_ms, now_ms, min_required).await;
                    let hk = (sym.clone(), interval.clone());
                    {
                        let mut st = state.write().await;
                        if let Some(prev) = st.candle_health.get(&hk) {
                            health.last_ok_backfill_ms = prev.last_ok_backfill_ms;
                            health.last_err_backfill = prev.last_err_backfill.clone();
                        }
                        st.candle_health.insert(hk.clone(), health.clone());
                    }

                    let last_close = health
                        .max_t_close
                        .or_else(|| health.max_t.map(|t| t + interval_ms));

                    // In REST-only candle mode (WS candle disabled), we also need a small tail refresh
                    // after the candle closes to ensure final OHLCV values are persisted (close-signal).
                    let close_refresh_grace_ms: i64 = 2000;
                    let tail_refresh_due = (!cfg.enable_candle_ws)
                        && last_close
                            .map(|lc| {
                                let last_ok = health.last_ok_backfill_ms.unwrap_or(0);
                                now_ms >= (lc + close_refresh_grace_ms) && last_ok < (lc + close_refresh_grace_ms)
                            })
                            .unwrap_or(false);

                    if health.ready && !tail_refresh_due {
                        continue;
                    }

                    // Backfill range selection:
                    // - When coverage is incomplete, backfill the full horizon.
                    // - When coverage exists but freshness is lacking (e.g. WS candle is disabled),
                    //   only backfill from the last known close time onward to avoid repeatedly
                    //   downloading the entire horizon for short intervals (1m/5m).
                    let mut start_ms = required_start;
                    let end_ms = now_ms + interval_ms.saturating_mul(2);

                    if health.ready && tail_refresh_due {
                        if let Some(lc) = last_close {
                            start_ms = (lc - interval_ms.saturating_mul(2)).max(required_start);
                        }
                    } else {
                        let start_ok = health
                            .min_t
                            .map(|t| t <= (required_start + interval_ms.saturating_mul(2)))
                            .unwrap_or(false);
                        let count_ok = health.have_count >= min_required;
                        let ratio_ok = match (health.min_t, health.max_t) {
                            (Some(min_t), Some(max_t)) => {
                                let implied = ((max_t - min_t).max(0) / interval_ms.max(1)) + 1;
                                if implied > 0 {
                                    ((health.have_count as f64) / (implied as f64)) >= 0.98
                                } else {
                                    true
                                }
                            }
                            _ => false,
                        };
                        let freshness_ok = last_close
                            .map(|lc| lc >= (now_ms - interval_ms.saturating_mul(2)))
                            .unwrap_or(false);

                        if start_ok && count_ok && ratio_ok && !freshness_ok {
                            if let Some(lc) = last_close {
                                start_ms = (lc - interval_ms.saturating_mul(2)).max(required_start);
                            } else if let Some(max_t) = health.max_t {
                                start_ms = (max_t - interval_ms.saturating_mul(5)).max(required_start);
                            }
                        }
                    }
                    let k = hk.clone();
                    if inflight.contains(&k) {
                        continue;
                    }
                    inflight.insert(k.clone());

                    let cfg2 = cfg.clone();
                    let state2 = state.clone();
                    let db2 = db.clone();
                    let http2 = http.clone();
                    let pacer2 = pacer.clone();
                    let sem2 = sem.clone();
                    let done_tx2 = done_tx.clone();
                    let start_ms2 = start_ms;
                    let end_ms2 = end_ms;

                    tokio::spawn(async move {
                        let _permit = sem2.acquire().await;
                        let res = rest_backfill_range(
                            &http2,
                            &cfg2,
                            &pacer2,
                            &state2,
                            &db2,
                            &sym,
                            &interval,
                            start_ms2,
                            end_ms2,
                        )
                        .await;
                        {
                            let mut st = state2.write().await;
                            let entry = st.candle_health.entry((sym.clone(), interval.clone())).or_default();
                            match res {
                                Ok(_) => {
                                    entry.last_ok_backfill_ms = Some(now_ms_i64());
                                    entry.last_err_backfill = None;
                                }
                                Err(e) => {
                                    entry.last_err_backfill = Some(format!("{e}"));
                                }
                            }
                        }

                        let _ = done_tx2.send((sym, interval));
                    });
                }
            }
            done = done_rx.recv() => {
                if let Some(k) = done {
                    inflight.remove(&k);
                }
            }
        }
    }
}

async fn note_ws_reset(cfg: &Config, state: &Arc<RwLock<State>>, reason: &str) {
    if !cfg.candles_enable || !cfg.enable_candle_ws {
        return;
    }

    let now = Instant::now();
    let window = Duration::from_secs(cfg.ws_candle_reset_window_secs.max(1));
    let disable_for = Duration::from_secs(cfg.ws_candle_disable_secs.max(1));
    let max_resets = cfg.ws_candle_max_resets_in_window.max(1);

    let mut st = state.write().await;
    st.ws_candle_resets.push_back(now);
    while st
        .ws_candle_resets
        .front()
        .map(|t| now.duration_since(*t) > window)
        .unwrap_or(false)
    {
        let _ = st.ws_candle_resets.pop_front();
    }

    if st
        .ws_candle_disabled_until
        .map(|t| t > now)
        .unwrap_or(false)
    {
        return;
    }

    if st.ws_candle_resets.len() >= max_resets {
        st.ws_candle_disabled_until = Some(now + disable_for);
        st.ws_candle_resets.clear();
        eprintln!(
            "ws candle disabled for {}s due to resets (reason={})",
            disable_for.as_secs(),
            reason
        );
    }
}

async fn ws_loop(
    cfg: Config,
    state: Arc<RwLock<State>>,
    db: DbWorkers,
    bbo_snapshots: Option<BboSnapshotStore>,
    mut cmd_rx: tokio_mpsc::UnboundedReceiver<WsCommand>,
    mids_notify: Arc<Notify>,
) -> Result<()> {
    // Validate URL early (connect_async takes &str; this is just a sanity check).
    let _ = Url::parse(&cfg.ws_url).context("bad HL_WS_URL")?;
    let ws_url = cfg.ws_url.clone();

    let mut attempt: u64 = 0;

    loop {
        attempt = attempt.wrapping_add(1);
        {
            let mut st = state.write().await;
            st.connected = false;
            st.ws_connect_attempt = attempt;
        }

        eprintln!("ws connect: attempt={attempt} url={ws_url}");

        let mut req = ws_url
            .as_str()
            .into_client_request()
            .context("build ws request")?;
        // Match the python websocket-client default Origin to avoid edge-proxy quirks.
        req.headers_mut().insert(
            "Origin",
            HeaderValue::from_static("https://api.hyperliquid.xyz"),
        );

        let connect_res = tokio_tungstenite::connect_async(req).await;
        let (ws_stream, resp) = match connect_res {
            Ok(v) => v,
            Err(e) => {
                eprintln!("ws connect failed: {e}");
                {
                    let mut st = state.write().await;
                    st.ws_last_error = Some(format!("ws connect failed: {e}"));
                    st.ws_last_error_ms = Some(now_ms_i64());
                }
                tokio::time::sleep(Duration::from_secs(cfg.reconnect_secs)).await;
                continue;
            }
        };

        eprintln!("ws connected: attempt={attempt} status={}", resp.status());

        {
            let mut st = state.write().await;
            st.connected = true;
            st.ws_connected_at_ms = Some(now_ms_i64());
        }

        let (mut w, mut r) = ws_stream.split();

        // Offload JSON parsing + state updates to a dedicated task so the WS reader can stay responsive.
        let (msg_tx, mut msg_rx) = tokio_mpsc::channel::<String>(cfg.max_incoming_queue.max(1));
        let cfg_proc = cfg.clone();
        let state_proc = state.clone();
        let db_proc = db.clone();
        let bbo_tx = bbo_snapshots.as_ref().map(|s| s.tx.clone());
        let mids_notify_proc = mids_notify.clone();
        let processor = tokio::spawn(async move {
            let mut bbo_sampler =
                bbo_tx.map(|tx| BboSnapshotSampler::new(cfg_proc.bbo_snapshots_sample_ms, tx));
            while let Some(txt) = msg_rx.recv().await {
                let _ = handle_ws_message(
                    &cfg_proc,
                    &state_proc,
                    &db_proc,
                    bbo_sampler.as_mut(),
                    &txt,
                    &mids_notify_proc,
                )
                .await;
            }
        });

        // Subscription tracking is per-connection.
        let mut subscribed: HashSet<SubKey> = HashSet::new();
        let mut pending: HashSet<SubKey> = HashSet::new();
        let mut pending_q: VecDeque<SubKey> = VecDeque::new();

        // Enqueue the current desired set. Actual sends are throttled and interleaved with reads.
        let desired_now = {
            let st = state.read().await;
            build_desired_subs(&st, &cfg)
        };
        for sub in desired_now {
            enqueue_sub_if_needed(sub, &subscribed, &mut pending, &mut pending_q);
        }

        let (sym_n, candle_n, has_user) = {
            let st = state.read().await;
            (
                st.desired_symbols.len(),
                st.desired_candles.len(),
                st.desired_user.is_some(),
            )
        };
        eprintln!(
            "ws desired: attempt={attempt} symbols={} candles={} user={} pending_subs={}",
            sym_n,
            candle_n,
            if has_user { "yes" } else { "no" },
            pending_q.len()
        );

        let mut ping = tokio::time::interval(Duration::from_secs(cfg.ping_secs.max(5)));
        ping.tick().await; // arm

        let mut sub_send = tokio::time::interval(Duration::from_millis(cfg.sub_send_ms.max(1)));
        sub_send.tick().await; // arm

        // Incoming queue drop counters (only incremented when overloaded).
        let mut drops_full: u64 = 0;
        let mut drops_closed: u64 = 0;
        let mut drops_last_ms: Option<i64> = None;
        let mut drops_flush = tokio::time::interval(Duration::from_secs(5));
        drops_flush.tick().await; // arm

        let mut restart_requested = false;

        loop {
            tokio::select! {
                biased;
                _ = drops_flush.tick(), if drops_full > 0 || drops_closed > 0 => {
                    let mut st = state.write().await;
                    st.ws_incoming_drops_full = st.ws_incoming_drops_full.saturating_add(drops_full);
                    st.ws_incoming_drops_closed = st.ws_incoming_drops_closed.saturating_add(drops_closed);
                    st.ws_last_incoming_drop_ms = drops_last_ms.or(st.ws_last_incoming_drop_ms);
                    drops_full = 0;
                    drops_closed = 0;
                }
                msg = r.next() => {
                    let msg = match msg {
                        Some(Ok(m)) => m,
                        Some(Err(e)) => {
                            eprintln!("ws read error: {e}");
                            {
                                let mut st = state.write().await;
                                st.ws_last_error = Some(format!("ws read error: {e}"));
                                st.ws_last_error_ms = Some(now_ms_i64());
                            }
                            note_ws_reset(&cfg, &state, &e.to_string()).await;
                            break;
                        }
                        None => break,
                    };

                    if restart_requested {
                        break;
                    }

                    match msg {
                        Message::Ping(payload) => {
                            // Some servers expect explicit Pong frames.
                            let _ = w.send(Message::Pong(payload)).await;
                        }
                        Message::Pong(_) => {}
                        Message::Close(frame) => {
                            let detail = match frame {
                                Some(cf) => format!("code={:?} reason={}", cf.code, cf.reason),
                                None => "no_close_frame".to_string(),
                            };
                            eprintln!("ws close: {detail}");
                            {
                                let mut st = state.write().await;
                                st.ws_last_close = Some(detail);
                                st.ws_last_close_ms = Some(now_ms_i64());
                            }
                            break;
                        }
                        Message::Text(txt) => {
                            // Drop if overwhelmed; the processor self-heals by applying the latest state.
                            if let Err(e) = msg_tx.try_send(txt.to_string()) {
                                use tokio::sync::mpsc::error::TrySendError;
                                drops_last_ms = Some(now_ms_i64());
                                match e {
                                    TrySendError::Full(_) => drops_full = drops_full.saturating_add(1),
                                    TrySendError::Closed(_) => drops_closed = drops_closed.saturating_add(1),
                                }
                            }
                        }
                        _ => {}
                    };
                }
                cmd = cmd_rx.recv() => {
                    match cmd {
                        Some(WsCommand::Restart) => {
                            eprintln!("ws restart requested by client");
                            restart_requested = true;
                        }
                        Some(WsCommand::RefreshSubs) => {
                            let desired = {
                                let st = state.read().await;
                                build_desired_subs(&st, &cfg)
                            };
                            for sub in desired {
                                enqueue_sub_if_needed(sub, &subscribed, &mut pending, &mut pending_q);
                            }
                        }
                        None => {
                            // all senders dropped; exit
                            processor.abort();
                            return Ok(());
                        }
                    }
                }
                _ = sub_send.tick(), if !pending_q.is_empty() => {
                    if let Some(sub) = pending_q.pop_front() {
                        let _ = pending.remove(&sub);
                        let msg = json!({"method":"subscribe","subscription": sub.to_subscription_json()}).to_string();
                        match w.send(Message::Text(msg.into())).await {
                            Ok(_) => { subscribed.insert(sub); }
                            Err(e) => {
                                eprintln!("ws send error: {e}");
                                {
                                    let mut st = state.write().await;
                                    st.ws_last_error = Some(format!("ws send error: {e}"));
                                    st.ws_last_error_ms = Some(now_ms_i64());
                                }
                                break;
                            }
                        }
                    }
                }
                _ = ping.tick() => {
                    let _ = w.send(Message::Text(json!({"method":"ping"}).to_string().into())).await;
                }
            }

            if restart_requested {
                break;
            }
        }

        processor.abort();

        // Best-effort flush of drop counters (in case the interval tick never fired).
        if drops_full > 0 || drops_closed > 0 {
            let mut st = state.write().await;
            st.ws_incoming_drops_full = st.ws_incoming_drops_full.saturating_add(drops_full);
            st.ws_incoming_drops_closed = st.ws_incoming_drops_closed.saturating_add(drops_closed);
            st.ws_last_incoming_drop_ms = drops_last_ms.or(st.ws_last_incoming_drop_ms);
        }

        {
            let mut st = state.write().await;
            st.connected = false;
            st.ws_disconnect_count = st.ws_disconnect_count.saturating_add(1);
            st.ws_last_disconnect_ms = Some(now_ms_i64());
        }

        // Reconnect loop.
        tokio::time::sleep(Duration::from_secs(cfg.reconnect_secs)).await;
    }
}

async fn handle_ws_message(
    cfg: &Config,
    state: &Arc<RwLock<State>>,
    db: &DbWorkers,
    bbo_sampler: Option<&mut BboSnapshotSampler>,
    txt: &str,
    mids_notify: &Arc<Notify>,
) -> Result<()> {
    let v: Value = serde_json::from_str(txt).context("ws json parse")?;
    let channel = v.get("channel").and_then(|c| c.as_str()).unwrap_or("");
    if channel == "subscriptionResponse" || channel == "pong" {
        return Ok(());
    }

    let now = Instant::now();

    match channel {
        "allMids" => {
            let mids = v
                .get("data")
                .and_then(|d| d.get("mids"))
                .and_then(|m| m.as_object())
                .ok_or_else(|| anyhow!("bad allMids"))?;
            let mut st = state.write().await;
            let changed = apply_all_mids_snapshot(
                &mut st,
                mids,
                now,
                cfg.mids_from_bbo,
                cfg.mids_from_bbo_fallback_age_s,
            );
            if changed {
                mids_notify.notify_waiters();
            }
        }
        "bbo" => {
            if !cfg.enable_bbo {
                return Ok(());
            }
            let data = v.get("data").ok_or_else(|| anyhow!("bad bbo"))?;
            let sym = data
                .get("coin")
                .and_then(|s| s.as_str())
                .unwrap_or("")
                .to_ascii_uppercase();
            if sym.is_empty() {
                return Ok(());
            }
            let bbo = match data.get("bbo").and_then(|b| b.as_array()) {
                Some(arr) => arr,
                None => return Ok(()),
            };
            if bbo.len() < 2 {
                return Ok(());
            }
            let bid = bbo.get(0).and_then(|x| x.get("px")).and_then(parse_f64);
            let ask = bbo.get(1).and_then(|x| x.get("px")).and_then(parse_f64);
            if let (Some(bid), Some(ask)) = (bid, ask) {
                if cfg.bbo_snapshots_enable {
                    if let Some(s) = bbo_sampler {
                        s.on_bbo(&sym, bid, ask, now);
                    }
                }
                let mut st = state.write().await;
                let bbo_changed = st
                    .bbo
                    .get(&sym)
                    .map(|(pbid, pask)| *pbid != bid || *pask != ask)
                    .unwrap_or(true);
                st.bbo.insert(sym.clone(), (bid, ask));
                st.bbo_updated_at.insert(sym.clone(), now);
                if bbo_changed {
                    st.bbo_seq = st.bbo_seq.wrapping_add(1);
                }
                let mids_changed =
                    apply_bbo_mid_tick(&mut st, &sym, bid, ask, now, cfg.mids_from_bbo);
                if mids_changed || bbo_changed {
                    mids_notify.notify_waiters();
                }
            }
        }
        "candle" => {
            if !cfg.candles_enable || !cfg.enable_candle_ws {
                return Ok(());
            }
            // If WS candles are temporarily disabled due to instability, drop candle updates.
            if state
                .read()
                .await
                .ws_candle_disabled_until
                .map(|t| t > now)
                .unwrap_or(false)
            {
                return Ok(());
            }
            let data = v.get("data").ok_or_else(|| anyhow!("bad candle"))?;
            let sym = data
                .get("s")
                .and_then(|s| s.as_str())
                .unwrap_or("")
                .to_ascii_uppercase();
            let interval = data
                .get("i")
                .and_then(|s| s.as_str())
                .map(canonical_interval)
                .unwrap_or_default();
            let t = data.get("t").and_then(parse_i64).unwrap_or(0);
            if sym.is_empty() || interval.is_empty() || t == 0 {
                return Ok(());
            }

            let candle = Candle {
                t,
                t_close: data.get("T").and_then(parse_i64),
                o: data.get("o").and_then(parse_f64),
                h: data.get("h").and_then(parse_f64),
                l: data.get("l").and_then(parse_f64),
                c: data.get("c").and_then(parse_f64),
                v: data.get("v").and_then(parse_f64),
                n: data.get("n").and_then(parse_i64),
            };

            let key = (sym.clone(), interval.clone());
            let should_persist = {
                let mut st = state.write().await;

                let q = st.candles.entry(key.clone()).or_insert_with(VecDeque::new);
                // Update existing last candle if the timestamp matches; else append.
                if let Some(back) = q.back_mut() {
                    if back.t == candle.t {
                        *back = candle.clone();
                    } else {
                        q.push_back(candle.clone());
                    }
                } else {
                    q.push_back(candle.clone());
                }
                while q.len() > 4 {
                    let _ = q.pop_front();
                }

                st.candle_updated_at.insert(key.clone(), now);

                let last_t = st.last_t_seen.get(&key).copied();
                st.last_t_seen.insert(key.clone(), candle.t);

                let last_persist = st.candle_last_persist_at.get(&key).copied();
                let persist_interval = Duration::from_secs(cfg.candle_persist_secs.max(1));
                let changed_t = last_t.map(|x| x != candle.t).unwrap_or(true);
                let due = last_persist
                    .map(|p| now.duration_since(p) >= persist_interval)
                    .unwrap_or(true);
                let sp = changed_t || due;
                if sp {
                    st.candle_last_persist_at.insert(key.clone(), now);
                }
                sp
            };

            if should_persist {
                db.send(DbJob {
                    symbol: sym,
                    interval,
                    t: candle.t,
                    t_close: candle.t_close,
                    o: candle.o,
                    h: candle.h,
                    l: candle.l,
                    c: candle.c,
                    v: candle.v,
                    n: candle.n,
                });
            }
        }
        "userFills" => {
            let data = v.get("data").unwrap_or(&Value::Null);
            let fills = match data.get("fills").and_then(|f| f.as_array()) {
                Some(arr) => arr,
                None => return Ok(()),
            };
            let is_snapshot = data
                .get("isSnapshot")
                .and_then(|b| b.as_bool())
                .unwrap_or(false);
            if fills.is_empty() {
                return Ok(());
            }
            let mut st = state.write().await;
            for fill in fills {
                if !fill.is_object() {
                    continue;
                }
                let mut item = fill.clone();
                if let Some(obj) = item.as_object_mut() {
                    obj.insert("_is_snapshot".to_string(), Value::Bool(is_snapshot));
                }
                while st.user_fills.len() >= cfg.max_event_queue {
                    let _ = st.user_fills.pop_front();
                }
                st.user_fills.push_back(item);
            }
        }
        "orderUpdates" => {
            let data = v.get("data").cloned().unwrap_or(Value::Null);
            let mut st = state.write().await;
            while st.order_updates.len() >= cfg.max_event_queue {
                let _ = st.order_updates.pop_front();
            }
            st.order_updates
                .push_back(json!({"t": now_epoch_s_f64(), "data": data}));
        }
        "userFundings" => {
            let data = v.get("data").cloned().unwrap_or(Value::Null);
            let mut st = state.write().await;
            while st.user_fundings.len() >= cfg.max_event_queue {
                let _ = st.user_fundings.pop_front();
            }
            st.user_fundings
                .push_back(json!({"t": now_epoch_s_f64(), "data": data}));
        }
        "userNonFundingLedgerUpdates" => {
            let data = v.get("data").cloned().unwrap_or(Value::Null);
            let mut st = state.write().await;
            while st.user_ledger_updates.len() >= cfg.max_event_queue {
                let _ = st.user_ledger_updates.pop_front();
            }
            st.user_ledger_updates
                .push_back(json!({"t": now_epoch_s_f64(), "data": data}));
        }
        _ => {}
    }

    Ok(())
}

#[derive(Deserialize)]
struct RpcRequest {
    id: u64,
    method: String,
    #[serde(default)]
    params: Value,
}

#[derive(Serialize)]
struct RpcResponse {
    id: u64,
    ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

async fn write_resp<W: AsyncWrite + Unpin>(w: &mut W, resp: &RpcResponse) -> Result<()> {
    let line = serde_json::to_string(resp)? + "\n";
    w.write_all(line.as_bytes()).await?;
    Ok(())
}

fn get_param_string(params: &Value, key: &str) -> Option<String> {
    params
        .get(key)
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
}

fn get_param_f64(params: &Value, key: &str) -> Option<f64> {
    params.get(key).and_then(|v| v.as_f64())
}

fn get_param_i64(params: &Value, key: &str) -> Option<i64> {
    params.get(key).and_then(|v| v.as_i64())
}

fn get_param_usize(params: &Value, key: &str) -> Option<usize> {
    params.get(key).and_then(|v| v.as_u64()).map(|u| u as usize)
}

fn get_param_u64(params: &Value, key: &str) -> Option<u64> {
    params.get(key).and_then(|v| {
        if let Some(u) = v.as_u64() {
            Some(u)
        } else {
            v.as_i64()
                .and_then(|i| if i >= 0 { Some(i as u64) } else { None })
        }
    })
}

fn collect_mids_result(
    st: &State,
    symbols: &[String],
    max_age: Option<f64>,
) -> serde_json::Map<String, Value> {
    let age = st.mids_updated_at.map(|t| t.elapsed().as_secs_f64());
    let age_for_cmp = age.unwrap_or(f64::INFINITY);
    let allow = max_age.map(|limit| age_for_cmp <= limit).unwrap_or(true);

    let mut mids_out = serde_json::Map::new();
    if allow {
        for sym in symbols.iter() {
            if let Some(px) = st.mids.get(sym) {
                mids_out.insert(sym.clone(), json!(px));
            }
        }
    }

    let mut bbo_out = serde_json::Map::new();
    let mut bbo_age_s: Option<f64> = None;
    for sym in symbols.iter() {
        let Some((bid, ask)) = st.bbo.get(sym).copied() else {
            continue;
        };
        let age_s = st
            .bbo_updated_at
            .get(sym)
            .map(|t| t.elapsed().as_secs_f64())
            .unwrap_or(f64::INFINITY);
        if max_age.map(|limit| age_s <= limit).unwrap_or(true) {
            bbo_out.insert(
                sym.clone(),
                json!({
                    "bid": bid,
                    "ask": ask,
                    "mid": (bid + ask) / 2.0,
                }),
            );
            bbo_age_s = Some(bbo_age_s.map(|x| x.max(age_s)).unwrap_or(age_s));
        }
    }

    let mut out = serde_json::Map::new();
    out.insert("mids".to_string(), Value::Object(mids_out));
    out.insert(
        "mids_age_s".to_string(),
        age.map(Value::from).unwrap_or(Value::Null),
    );
    out.insert("mids_seq".to_string(), json!(st.mids_seq));
    out.insert("bbo".to_string(), Value::Object(bbo_out));
    out.insert(
        "bbo_age_s".to_string(),
        bbo_age_s.map(Value::from).unwrap_or(Value::Null),
    );
    out.insert("bbo_seq".to_string(), json!(st.bbo_seq));
    out
}

async fn handle_client(
    stream: UnixStream,
    cfg: Config,
    state: Arc<RwLock<State>>,
    cmd_tx: tokio_mpsc::UnboundedSender<WsCommand>,
    mids_notify: Arc<Notify>,
) -> Result<()> {
    let (r, mut w) = stream.into_split();
    let mut lines = BufReader::new(r).lines();

    while let Some(line) = lines.next_line().await? {
        let req: RpcRequest = match serde_json::from_str(&line) {
            Ok(r) => r,
            Err(e) => {
                let resp = RpcResponse {
                    id: 0,
                    ok: false,
                    result: None,
                    error: Some(format!("bad json: {e}")),
                };
                let _ = write_resp(&mut w, &resp).await;
                continue;
            }
        };

        let method = req.method.trim().to_string();
        let params = req.params;

        let resp = match method.as_str() {
            "ensure_started" => {
                let symbols = params
                    .get("symbols")
                    .and_then(|v| v.as_array())
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|x| x.as_str())
                            .map(|s| s.trim().to_ascii_uppercase())
                            .filter(|s| !s.is_empty())
                            .collect::<Vec<_>>()
                    })
                    .unwrap_or_else(Vec::new);

                let interval_raw =
                    get_param_string(&params, "interval").unwrap_or_else(|| "1h".to_string());
                let interval = canonical_interval(&interval_raw);
                let interval = if interval.is_empty() {
                    "1h".to_string()
                } else {
                    interval
                };
                let candle_limit = params
                    .get("candle_limit")
                    .and_then(|v| v.as_u64())
                    .map(|u| u as usize)
                    .unwrap_or(0);

                let client_id = get_param_string(&params, "client_id")
                    .unwrap_or_else(|| "default".to_string())
                    .trim()
                    .to_string();
                let client_id = if client_id.is_empty() {
                    "default".to_string()
                } else {
                    client_id
                };

                // Optional user: only update when a non-null string is provided (do not clear on null).
                let user_str = params
                    .get("user")
                    .and_then(|v| v.as_str())
                    .map(|s| s.trim().to_ascii_lowercase());

                let mut changed = false;
                {
                    let now = Instant::now();
                    let ttl = Duration::from_secs(cfg.client_ttl_secs.max(1));
                    let mut st = state.write().await;

                    // Purge stale clients.
                    let stale_ids: Vec<String> = st
                        .clients
                        .iter()
                        .filter(|(_, c)| now.duration_since(c.last_seen) > ttl)
                        .map(|(id, _)| id.clone())
                        .collect();
                    for id in stale_ids {
                        st.clients.remove(&id);
                        changed = true;
                    }

                    // Update this client.
                    let mut sym_set: HashSet<String> = HashSet::new();
                    for sym in symbols.iter() {
                        sym_set.insert(sym.clone());
                    }

                    let entry =
                        st.clients
                            .entry(client_id.clone())
                            .or_insert_with(|| ClientDesired {
                                symbols: HashSet::new(),
                                interval: interval.clone(),
                                candle_limit,
                                user: None,
                                last_seen: now,
                            });
                    entry.last_seen = now;

                    if entry.interval != interval {
                        entry.interval = interval.clone();
                        changed = true;
                    }
                    if entry.candle_limit != candle_limit {
                        entry.candle_limit = candle_limit;
                        changed = true;
                    }
                    if entry.symbols != sym_set {
                        entry.symbols = sym_set;
                        changed = true;
                    }
                    if let Some(u) = user_str {
                        let next = if u.is_empty() { None } else { Some(u) };
                        if entry.user != next {
                            entry.user = next;
                            changed = true;
                        }
                    }

                    // Recompute union desired sets.
                    let mut new_symbols: HashSet<String> = HashSet::new();
                    let mut new_candles: HashSet<(String, String)> = HashSet::new();
                    let mut new_limits: HashMap<(String, String), usize> = HashMap::new();
                    let mut new_user: Option<String> = None;

                    for c in st.clients.values() {
                        for sym in c.symbols.iter() {
                            new_symbols.insert(sym.clone());
                            if cfg.candles_enable {
                                new_candles.insert((sym.clone(), c.interval.clone()));
                                let k = (sym.clone(), c.interval.clone());
                                let e = new_limits.entry(k).or_insert(0);
                                if c.candle_limit > *e {
                                    *e = c.candle_limit;
                                }
                            }
                        }
                        if new_user.is_none() {
                            if let Some(u) = c.user.as_ref() {
                                if !u.is_empty() {
                                    new_user = Some(u.clone());
                                }
                            }
                        }
                    }

                    // Sidecar warm universe (optional): always keep these candles fresh.
                    if !cfg.always_symbols.is_empty() {
                        for sym in cfg.always_symbols.iter() {
                            new_symbols.insert(sym.clone());
                            if cfg.candles_enable && !cfg.always_intervals.is_empty() {
                                for interval in cfg.always_intervals.iter() {
                                    new_candles.insert((sym.clone(), interval.clone()));
                                    let k = (sym.clone(), interval.clone());
                                    let e = new_limits.entry(k).or_insert(0);
                                    if cfg.always_candle_limit > *e {
                                        *e = cfg.always_candle_limit;
                                    }
                                }
                            }
                        }
                    }

                    if new_symbols != st.desired_symbols
                        || new_candles != st.desired_candles
                        || new_limits != st.desired_candle_limit
                        || new_user != st.desired_user
                    {
                        st.desired_symbols = new_symbols;
                        st.desired_candles = new_candles;
                        st.desired_candle_limit = new_limits;
                        st.desired_user = new_user;
                        changed = true;
                    }
                }

                if changed {
                    let _ = cmd_tx.send(WsCommand::RefreshSubs);
                }
                RpcResponse {
                    id: req.id,
                    ok: true,
                    result: Some(json!({"ok":true})),
                    error: None,
                }
            }
            "restart" => {
                let _ = cmd_tx.send(WsCommand::Restart);
                RpcResponse {
                    id: req.id,
                    ok: true,
                    result: Some(json!({"ok":true})),
                    error: None,
                }
            }
            "health" => {
                let symbols = params
                    .get("symbols")
                    .and_then(|v| v.as_array())
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|x| x.as_str())
                            .map(|s| s.trim().to_ascii_uppercase())
                            .filter(|s| !s.is_empty())
                            .collect::<Vec<_>>()
                    })
                    .unwrap_or_else(Vec::new);
                let interval_raw =
                    get_param_string(&params, "interval").unwrap_or_else(|| "1h".to_string());
                let interval = canonical_interval(&interval_raw);
                let interval = if interval.is_empty() {
                    "1h".to_string()
                } else {
                    interval
                };

                let st = state.read().await;
                let mids_age_s = st.mids_updated_at.map(|t| t.elapsed().as_secs_f64());

                let mut candle_age_s: Option<f64> = None;
                for sym in symbols.iter() {
                    let key = (sym.clone(), interval.clone());
                    if let Some(ts) = st.candle_updated_at.get(&key) {
                        let age = ts.elapsed().as_secs_f64();
                        candle_age_s = Some(candle_age_s.map(|x| x.max(age)).unwrap_or(age));
                    }
                }

                let mut bbo_age_s: Option<f64> = None;
                for sym in symbols.iter() {
                    if let Some(ts) = st.bbo_updated_at.get(sym) {
                        let age = ts.elapsed().as_secs_f64();
                        bbo_age_s = Some(bbo_age_s.map(|x| x.max(age)).unwrap_or(age));
                    }
                }

                RpcResponse {
                    id: req.id,
                    ok: true,
                    result: Some(json!({
                        "connected": st.connected,
                        "ws_connect_attempt": st.ws_connect_attempt,
                        "ws_disconnect_count": st.ws_disconnect_count,
                        "ws_last_error": st.ws_last_error,
                        "ws_last_error_ms": st.ws_last_error_ms,
                        "ws_last_close": st.ws_last_close,
                        "ws_last_close_ms": st.ws_last_close_ms,
                        "ws_incoming_drops_full": st.ws_incoming_drops_full,
                        "ws_incoming_drops_closed": st.ws_incoming_drops_closed,
                        "ws_last_incoming_drop_ms": st.ws_last_incoming_drop_ms,
                        "mids_age_s": mids_age_s,
                        "candle_age_s": candle_age_s,
                        "bbo_age_s": bbo_age_s,
                    })),
                    error: None,
                }
            }
            "ws_stats" => {
                let st = state.read().await;
                let mids_age_s = st.mids_updated_at.map(|t| t.elapsed().as_secs_f64());
                RpcResponse {
                    id: req.id,
                    ok: true,
                    result: Some(json!({
                        "connected": st.connected,
                        "ws_connect_attempt": st.ws_connect_attempt,
                        "ws_connected_at_ms": st.ws_connected_at_ms,
                        "ws_disconnect_count": st.ws_disconnect_count,
                        "ws_last_disconnect_ms": st.ws_last_disconnect_ms,
                        "ws_last_close": st.ws_last_close,
                        "ws_last_close_ms": st.ws_last_close_ms,
                        "ws_last_error": st.ws_last_error,
                        "ws_last_error_ms": st.ws_last_error_ms,
                        "ws_incoming_drops_full": st.ws_incoming_drops_full,
                        "ws_incoming_drops_closed": st.ws_incoming_drops_closed,
                        "ws_last_incoming_drop_ms": st.ws_last_incoming_drop_ms,
                        "mids_age_s": mids_age_s,
                        "clients": st.clients.len(),
                        "desired_symbols": st.desired_symbols.len(),
                        "desired_candles": st.desired_candles.len(),
                        "desired_user": st.desired_user.is_some(),
                    })),
                    error: None,
                }
            }
            "candles_ready" => {
                let symbols = params
                    .get("symbols")
                    .and_then(|v| v.as_array())
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|x| x.as_str())
                            .map(|s| s.trim().to_ascii_uppercase())
                            .filter(|s| !s.is_empty())
                            .collect::<Vec<_>>()
                    })
                    .unwrap_or_else(Vec::new);
                let interval_raw =
                    get_param_string(&params, "interval").unwrap_or_else(|| "1h".to_string());
                let interval = canonical_interval(&interval_raw);
                let interval = if interval.is_empty() {
                    "1h".to_string()
                } else {
                    interval
                };

                let st = state.read().await;
                let mut not_ready: Vec<String> = Vec::new();
                for sym in symbols.iter() {
                    let key = (sym.clone(), interval.clone());
                    let ready = st.candle_health.get(&key).map(|h| h.ready).unwrap_or(false);
                    if !ready {
                        not_ready.push(sym.clone());
                    }
                }
                RpcResponse {
                    id: req.id,
                    ok: true,
                    result: Some(json!({"ready": not_ready.is_empty(), "not_ready": not_ready})),
                    error: None,
                }
            }
            "candles_health" => {
                let symbols = params
                    .get("symbols")
                    .and_then(|v| v.as_array())
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|x| x.as_str())
                            .map(|s| s.trim().to_ascii_uppercase())
                            .filter(|s| !s.is_empty())
                            .collect::<Vec<_>>()
                    })
                    .unwrap_or_else(Vec::new);
                let interval_raw =
                    get_param_string(&params, "interval").unwrap_or_else(|| "1h".to_string());
                let interval = canonical_interval(&interval_raw);
                let interval = if interval.is_empty() {
                    "1h".to_string()
                } else {
                    interval
                };

                let st = state.read().await;
                let mut out: Vec<Value> = Vec::new();
                for sym in symbols.iter() {
                    let key = (sym.clone(), interval.clone());
                    if let Some(h) = st.candle_health.get(&key) {
                        out.push(json!({
                            "symbol": sym,
                            "interval": interval,
                            "ready": h.ready,
                            "have_count": h.have_count,
                            "expected_count": h.expected_count,
                            "min_t": h.min_t,
                            "max_t": h.max_t,
                            "max_t_close": h.max_t_close,
                            "checked_at_ms": h.checked_at_ms,
                            "last_ok_backfill_ms": h.last_ok_backfill_ms,
                            "last_err_backfill": h.last_err_backfill,
                        }));
                    } else {
                        out.push(json!({
                            "symbol": sym,
                            "interval": interval,
                            "ready": false,
                            "have_count": 0,
                            "expected_count": 0,
                            "min_t": Value::Null,
                            "max_t": Value::Null,
                            "max_t_close": Value::Null,
                            "checked_at_ms": Value::Null,
                            "last_ok_backfill_ms": Value::Null,
                            "last_err_backfill": Value::Null,
                        }));
                    }
                }

                let ws_candle_disabled_s = st.ws_candle_disabled_until.map(|t| {
                    if t > Instant::now() {
                        (t - Instant::now()).as_secs_f64()
                    } else {
                        0.0
                    }
                });

                RpcResponse {
                    id: req.id,
                    ok: true,
                    result: Some(
                        json!({"ws_candle_disabled_s": ws_candle_disabled_s, "items": out}),
                    ),
                    error: None,
                }
            }
            "get_mid" => {
                let sym = get_param_string(&params, "symbol")
                    .unwrap_or_default()
                    .trim()
                    .to_ascii_uppercase();
                let max_age = get_param_f64(&params, "max_age_s");
                let st = state.read().await;
                let px = st.mids.get(&sym).copied();
                if px.is_none() {
                    RpcResponse {
                        id: req.id,
                        ok: true,
                        result: Some(Value::Null),
                        error: None,
                    }
                } else if let Some(max_age) = max_age {
                    let age = st
                        .mids_updated_at
                        .map(|t| t.elapsed().as_secs_f64())
                        .unwrap_or(f64::INFINITY);
                    if age > max_age {
                        RpcResponse {
                            id: req.id,
                            ok: true,
                            result: Some(Value::Null),
                            error: None,
                        }
                    } else {
                        RpcResponse {
                            id: req.id,
                            ok: true,
                            result: Some(json!(px.unwrap())),
                            error: None,
                        }
                    }
                } else {
                    RpcResponse {
                        id: req.id,
                        ok: true,
                        result: Some(json!(px.unwrap())),
                        error: None,
                    }
                }
            }
            "get_mids" => {
                let symbols = params
                    .get("symbols")
                    .and_then(|v| v.as_array())
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|x| x.as_str())
                            .map(|s| s.trim().to_ascii_uppercase())
                            .filter(|s| !s.is_empty())
                            .collect::<Vec<_>>()
                    })
                    .unwrap_or_else(Vec::new);
                let max_age = get_param_f64(&params, "max_age_s");

                let st = state.read().await;
                let out = collect_mids_result(&st, &symbols, max_age);
                RpcResponse {
                    id: req.id,
                    ok: true,
                    result: Some(Value::Object(out)),
                    error: None,
                }
            }
            "wait_mids" => {
                let symbols = params
                    .get("symbols")
                    .and_then(|v| v.as_array())
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|x| x.as_str())
                            .map(|s| s.trim().to_ascii_uppercase())
                            .filter(|s| !s.is_empty())
                            .collect::<Vec<_>>()
                    })
                    .unwrap_or_else(Vec::new);
                let max_age = get_param_f64(&params, "max_age_s");
                let after_seq = get_param_u64(&params, "after_seq").unwrap_or(0);
                let after_bbo_seq = get_param_u64(&params, "after_bbo_seq").unwrap_or(0);
                let timeout_ms = get_param_u64(&params, "timeout_ms")
                    .unwrap_or(25_000)
                    .clamp(50, 120_000);
                let deadline = Instant::now() + Duration::from_millis(timeout_ms);

                loop {
                    let notified = mids_notify.notified();

                    {
                        let st = state.read().await;
                        if st.mids_seq > after_seq || st.bbo_seq > after_bbo_seq {
                            let mut out = collect_mids_result(&st, &symbols, max_age);
                            out.insert("changed".to_string(), Value::Bool(true));
                            out.insert("timed_out".to_string(), Value::Bool(false));
                            out.insert("seq_reset".to_string(), Value::Bool(false));
                            break RpcResponse {
                                id: req.id,
                                ok: true,
                                result: Some(Value::Object(out)),
                                error: None,
                            };
                        }
                        // Sidecar restart can rewind mids_seq to a smaller value. Return
                        // immediately so clients can resynchronise without waiting for timeout.
                        if st.mids_seq < after_seq || st.bbo_seq < after_bbo_seq {
                            let mut out = collect_mids_result(&st, &symbols, max_age);
                            out.insert("changed".to_string(), Value::Bool(true));
                            out.insert("timed_out".to_string(), Value::Bool(false));
                            out.insert("seq_reset".to_string(), Value::Bool(true));
                            break RpcResponse {
                                id: req.id,
                                ok: true,
                                result: Some(Value::Object(out)),
                                error: None,
                            };
                        }
                    }

                    let now = Instant::now();
                    if now >= deadline {
                        let st = state.read().await;
                        let mut out = collect_mids_result(&st, &symbols, max_age);
                        out.insert("changed".to_string(), Value::Bool(false));
                        out.insert("timed_out".to_string(), Value::Bool(true));
                        out.insert("seq_reset".to_string(), Value::Bool(false));
                        break RpcResponse {
                            id: req.id,
                            ok: true,
                            result: Some(Value::Object(out)),
                            error: None,
                        };
                    }

                    let remaining = deadline.saturating_duration_since(now);
                    if tokio::time::timeout(remaining, notified).await.is_err() {
                        let st = state.read().await;
                        let mut out = collect_mids_result(&st, &symbols, max_age);
                        out.insert("changed".to_string(), Value::Bool(false));
                        out.insert("timed_out".to_string(), Value::Bool(true));
                        out.insert("seq_reset".to_string(), Value::Bool(false));
                        break RpcResponse {
                            id: req.id,
                            ok: true,
                            result: Some(Value::Object(out)),
                            error: None,
                        };
                    }
                }
            }
            "get_bbo" => {
                let sym = get_param_string(&params, "symbol")
                    .unwrap_or_default()
                    .trim()
                    .to_ascii_uppercase();
                let max_age = get_param_f64(&params, "max_age_s");
                let st = state.read().await;
                let bbo = st.bbo.get(&sym).copied();
                if bbo.is_none() {
                    RpcResponse {
                        id: req.id,
                        ok: true,
                        result: Some(Value::Null),
                        error: None,
                    }
                } else if let Some(max_age) = max_age {
                    let age = st
                        .bbo_updated_at
                        .get(&sym)
                        .map(|t| t.elapsed().as_secs_f64())
                        .unwrap_or(f64::INFINITY);
                    if age > max_age {
                        RpcResponse {
                            id: req.id,
                            ok: true,
                            result: Some(Value::Null),
                            error: None,
                        }
                    } else {
                        let (bid, ask) = bbo.unwrap();
                        RpcResponse {
                            id: req.id,
                            ok: true,
                            result: Some(json!([bid, ask])),
                            error: None,
                        }
                    }
                } else {
                    let (bid, ask) = bbo.unwrap();
                    RpcResponse {
                        id: req.id,
                        ok: true,
                        result: Some(json!([bid, ask])),
                        error: None,
                    }
                }
            }
            "get_latest_candle_times" => {
                let sym = get_param_string(&params, "symbol")
                    .unwrap_or_default()
                    .trim()
                    .to_ascii_uppercase();
                let interval_raw =
                    get_param_string(&params, "interval").unwrap_or_else(|| "1h".to_string());
                let interval = canonical_interval(&interval_raw);
                let interval = if interval.is_empty() {
                    "1h".to_string()
                } else {
                    interval
                };
                let st = state.read().await;
                let key = (sym.clone(), interval.clone());
                let q = st.candles.get(&key);
                if let Some(q) = q {
                    if let Some(last) = q.back() {
                        RpcResponse {
                            id: req.id,
                            ok: true,
                            result: Some(json!([last.t, last.t_close])),
                            error: None,
                        }
                    } else {
                        RpcResponse {
                            id: req.id,
                            ok: true,
                            result: Some(json!([Value::Null, Value::Null])),
                            error: None,
                        }
                    }
                } else {
                    RpcResponse {
                        id: req.id,
                        ok: true,
                        result: Some(json!([Value::Null, Value::Null])),
                        error: None,
                    }
                }
            }
            "get_last_closed_candle_times" => {
                let sym = get_param_string(&params, "symbol")
                    .unwrap_or_default()
                    .trim()
                    .to_ascii_uppercase();
                let interval_raw =
                    get_param_string(&params, "interval").unwrap_or_else(|| "1h".to_string());
                let interval = canonical_interval(&interval_raw);
                let interval = if interval.is_empty() {
                    "1h".to_string()
                } else {
                    interval
                };
                let grace_ms = get_param_i64(&params, "grace_ms").unwrap_or(2000).max(0);
                let st = state.read().await;
                let key = (sym.clone(), interval.clone());
                let q = st.candles.get(&key);
                if q.is_none() || q.unwrap().is_empty() {
                    RpcResponse {
                        id: req.id,
                        ok: true,
                        result: Some(json!([Value::Null, Value::Null])),
                        error: None,
                    }
                } else {
                    let q = q.unwrap();
                    let now_ms = now_ms_i64();
                    let last = q.back().unwrap();
                    let mut chosen = last;
                    if let Some(tclose) = last.t_close {
                        if now_ms < (tclose - grace_ms) && q.len() >= 2 {
                            chosen = &q[q.len() - 2];
                        }
                    }
                    RpcResponse {
                        id: req.id,
                        ok: true,
                        result: Some(json!([chosen.t, chosen.t_close])),
                        error: None,
                    }
                }
            }
            "drain_user_fills" => {
                let max_items = get_param_usize(&params, "max_items");
                let mut st = state.write().await;
                let mut out: Vec<Value> = Vec::new();
                while let Some(v) = st.user_fills.pop_front() {
                    out.push(v);
                    if let Some(m) = max_items {
                        if out.len() >= m {
                            break;
                        }
                    }
                }
                RpcResponse {
                    id: req.id,
                    ok: true,
                    result: Some(json!(out)),
                    error: None,
                }
            }
            "drain_order_updates" => {
                let max_items = get_param_usize(&params, "max_items");
                let mut st = state.write().await;
                let mut out: Vec<Value> = Vec::new();
                while let Some(v) = st.order_updates.pop_front() {
                    out.push(v);
                    if let Some(m) = max_items {
                        if out.len() >= m {
                            break;
                        }
                    }
                }
                RpcResponse {
                    id: req.id,
                    ok: true,
                    result: Some(json!(out)),
                    error: None,
                }
            }
            "drain_user_fundings" => {
                let max_items = get_param_usize(&params, "max_items");
                let mut st = state.write().await;
                let mut out: Vec<Value> = Vec::new();
                while let Some(v) = st.user_fundings.pop_front() {
                    out.push(v);
                    if let Some(m) = max_items {
                        if out.len() >= m {
                            break;
                        }
                    }
                }
                RpcResponse {
                    id: req.id,
                    ok: true,
                    result: Some(json!(out)),
                    error: None,
                }
            }
            "drain_user_ledger_updates" => {
                let max_items = get_param_usize(&params, "max_items");
                let mut st = state.write().await;
                let mut out: Vec<Value> = Vec::new();
                while let Some(v) = st.user_ledger_updates.pop_front() {
                    out.push(v);
                    if let Some(m) = max_items {
                        if out.len() >= m {
                            break;
                        }
                    }
                }
                RpcResponse {
                    id: req.id,
                    ok: true,
                    result: Some(json!(out)),
                    error: None,
                }
            }
            _ => RpcResponse {
                id: req.id,
                ok: false,
                result: None,
                error: Some(format!("unknown method: {method}")),
            },
        };

        let _ = write_resp(&mut w, &resp).await;
    }

    Ok(())
}

#[tokio::main(flavor = "multi_thread")]
async fn main() -> Result<()> {
    let cfg = load_config();

    // CLI mode: run a single stat command and exit.
    // Server mode (systemd) runs with no args.
    let argv: Vec<String> = env::args().skip(1).collect();
    if let Some(cmd) = argv.first().map(|s| s.as_str()) {
        if cmd == "stat" {
            let kv = parse_cli_kv(&argv[1..]);
            if kv.contains_key("help") || kv.contains_key("h") {
                println!("{}", cli_usage());
                return Ok(());
            }
            let interval_raw = kv
                .get("interval")
                .or_else(|| kv.get("i"))
                .map(|s| s.to_string())
                .unwrap_or_else(|| "1h".to_string());
            let interval = canonical_interval(&interval_raw);
            let interval = if interval.is_empty() {
                "1h".to_string()
            } else {
                interval
            };
            let symbols_raw = kv
                .get("symbols")
                .or_else(|| kv.get("s"))
                .cloned()
                .unwrap_or_default();
            if symbols_raw.trim().is_empty() {
                println!("{}", cli_usage());
                return Ok(());
            }
            let symbols = parse_symbols_csv(&symbols_raw);
            let bars_wanted: usize = kv
                .get("bars")
                .or_else(|| kv.get("b"))
                .and_then(|s| s.parse::<usize>().ok())
                .or_else(|| {
                    env::var("AI_QUANT_LOOKBACK_BARS")
                        .ok()
                        .and_then(|s| s.parse::<usize>().ok())
                })
                .unwrap_or(200);
            let db_dir = kv
                .get("db-dir")
                .or_else(|| kv.get("db_dir"))
                .cloned()
                .unwrap_or_else(|| cfg.candles_db_dir.clone());
            let mut cfg2 = cfg.clone();
            cfg2.candles_db_dir = db_dir;
            let db_path = db_path_for_interval(&cfg2, &interval);
            let want_json = kv.contains_key("json");

            let mut out: Vec<Value> = Vec::new();
            for sym in symbols.iter() {
                match compute_db_stat(&db_path, sym, &interval, bars_wanted) {
                    Ok(st) => {
                        if want_json {
                            out.push(json!({
                                "symbol": st.symbol,
                                "interval": st.interval,
                                "db_path": st.db_path,
                                "bars_wanted": st.bars_wanted,
                                "rows": st.rows,
                                "null_ohlcv": st.null_ohlcv,
                                "min_t": st.min_t,
                                "max_t": st.max_t,
                                "max_t_close": st.max_t_close,
                                "gap_bars": st.gap_bars,
                                "max_gap_bars": st.max_gap_bars,
                                "out_of_order": st.out_of_order,
                                "last_close_age_s": st.last_close_age_s,
                                "close_span_ms_mode": st.close_span_ms_mode,
                            }));
                        } else {
                            print_db_stat_human(&st);
                        }
                    }
                    Err(e) => {
                        if want_json {
                            out.push(json!({"symbol": sym, "interval": interval, "error": format!("{e}")}));
                        } else {
                            println!("{} {} error: {}", sym, interval, e);
                        }
                    }
                }
            }
            if want_json {
                println!(
                    "{}",
                    serde_json::to_string_pretty(&json!({"db_path": db_path, "items": out}))?
                );
            }
            return Ok(());
        } else if cmd == "help" || cmd == "--help" || cmd == "-h" {
            println!("{}", cli_usage());
            return Ok(());
        }
    }

    // rustls 0.23+ requires selecting a crypto provider at process start.
    // This avoids a runtime panic inside tokio-tungstenite's rustls integration.
    let _ =
        rustls::crypto::CryptoProvider::install_default(rustls::crypto::ring::default_provider());
    println!(
        "ws-sidecar starting: ws_url={} info_url={} sock={} candles_db_dir={} candles_enable={} candle_ws_enable={}",
        cfg.ws_url,
        cfg.info_url,
        cfg.sock_path,
        cfg.candles_db_dir,
        cfg.candles_enable,
        cfg.enable_candle_ws
    );
    if !cfg.candle_prune_disable_intervals.is_empty() {
        let mut intervals: Vec<String> =
            cfg.candle_prune_disable_intervals.iter().cloned().collect();
        intervals.sort();
        println!(
            "ws-sidecar candle retention: pruning disabled for intervals: {} (append-only; monitor disk usage)",
            intervals.join(",")
        );
    }

    println!(
        "ws-sidecar mids source: mode={} bbo_fallback_age_s={:.1}",
        if cfg.mids_from_bbo {
            "bbo_mid"
        } else {
            "allMids"
        },
        cfg.mids_from_bbo_fallback_age_s
    );

    if cfg.bbo_snapshots_enable {
        println!(
            "ws-sidecar bbo snapshots: enabled=yes db_path={} sample_ms={} retention_hours={} retention_sweep_secs={} max_queue={}",
            cfg.bbo_snapshots_db_path,
            cfg.bbo_snapshots_sample_ms,
            cfg.bbo_snapshots_retention_hours,
            cfg.bbo_snapshots_retention_sweep_secs,
            cfg.bbo_snapshots_max_queue,
        );
        if !cfg.enable_bbo {
            eprintln!(
                "ws-sidecar warning: AI_QUANT_BBO_SNAPSHOTS_ENABLE=1 but AI_QUANT_WS_ENABLE_BBO=0; no snapshots will be written"
            );
        }
    }

    // Remove any stale socket file.
    if Path::new(&cfg.sock_path).exists() {
        let _ = fs::remove_file(&cfg.sock_path);
    }
    if let Some(parent) = Path::new(&cfg.sock_path).parent() {
        let _ = fs::create_dir_all(parent);
    }

    let db = DbWorkers::new(&cfg);

    let bbo_snapshots = if cfg.bbo_snapshots_enable {
        let store = BboSnapshotStore::start(&cfg);
        let sweep_secs = cfg.bbo_snapshots_retention_sweep_secs.max(30);
        let sweep_tx = store.tx.clone();
        tokio::spawn(async move {
            // Run an initial sweep quickly to cap any existing DB.
            let _ = sweep_tx.send(BboSnapshotMsg::Sweep).await;

            let mut tick = tokio::time::interval(Duration::from_secs(sweep_secs));
            tick.tick().await; // arm
            loop {
                tick.tick().await;
                if sweep_tx.send(BboSnapshotMsg::Sweep).await.is_err() {
                    break;
                }
            }
        });
        Some(store)
    } else {
        None
    };

    let state: Arc<RwLock<State>> = Arc::new(RwLock::new(State::default()));
    let mids_notify = Arc::new(Notify::new());
    let (cmd_tx, cmd_rx) = tokio_mpsc::unbounded_channel::<WsCommand>();

    // Seed warm universe desired sets so candles start backfilling even before any clients connect.
    {
        let mut st = state.write().await;
        for sym in cfg.always_symbols.iter() {
            st.desired_symbols.insert(sym.clone());
            if cfg.candles_enable && !cfg.always_intervals.is_empty() {
                for interval in cfg.always_intervals.iter() {
                    st.desired_candles.insert((sym.clone(), interval.clone()));
                    let k = (sym.clone(), interval.clone());
                    let e = st.desired_candle_limit.entry(k).or_insert(0);
                    if cfg.always_candle_limit > *e {
                        *e = cfg.always_candle_limit;
                    }
                }
            }
        }
    }

    // Start the candle verifier/backfill task.
    {
        let cfg2 = cfg.clone();
        let state2 = state.clone();
        let db2 = db.clone();
        tokio::spawn(async move {
            let _ = candle_manager_loop(cfg2, state2, db2).await;
        });
    }

    // Start the websocket task.
    {
        let cfg2 = cfg.clone();
        let state2 = state.clone();
        let db2 = db.clone();
        let bbo_snapshots2 = bbo_snapshots.clone();
        let mids_notify2 = mids_notify.clone();
        tokio::spawn(async move {
            let _ = ws_loop(cfg2, state2, db2, bbo_snapshots2, cmd_rx, mids_notify2).await;
        });
    }

    let listener = UnixListener::bind(&cfg.sock_path).context("bind unix socket")?;

    if let Some(interval) = watchdog_interval_from_env() {
        tokio::spawn(async move {
            let mut tick = tokio::time::interval(interval);
            tick.tick().await; // arm
            loop {
                tick.tick().await;
                systemd_notify("WATCHDOG=1");
            }
        });
    }
    systemd_notify("READY=1");
    systemd_notify("STATUS=ws-sidecar ready");

    loop {
        let (stream, _addr) = listener.accept().await?;
        let cfg2 = cfg.clone();
        let state2 = state.clone();
        let cmd_tx2 = cmd_tx.clone();
        let mids_notify2 = mids_notify.clone();
        tokio::spawn(async move {
            let _ = handle_client(stream, cfg2, state2, cmd_tx2, mids_notify2).await;
        });
    }
}
