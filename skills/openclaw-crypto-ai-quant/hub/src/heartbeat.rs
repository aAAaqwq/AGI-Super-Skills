use regex::Regex;
use serde::Serialize;
use std::sync::LazyLock;

/// Parsed heartbeat fields from the engine's `🫀 engine ok ...` line.
#[derive(Debug, Clone, Default, Serialize)]
pub struct Heartbeat {
    pub ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ts_ms: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub line: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,

    // Parsed fields
    #[serde(skip_serializing_if = "Option::is_none")]
    pub loop_s: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub errors: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub symbols: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub open_pos: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ws_connected: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ws_thread_alive: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ws_restarts: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub kill_mode: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub kill_reason: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub strategy_mode: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub regime_gate: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub regime_reason: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub config_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slip_enabled: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slip_n: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slip_win: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slip_thr_bps: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slip_last_bps: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slip_median_bps: Option<f64>,
}

macro_rules! re {
    ($pat:expr) => {
        LazyLock::new(|| Regex::new($pat).unwrap())
    };
}

static RE_LOOP: LazyLock<Regex> = re!(r"(?i)(?:wall|loop)=([0-9.]+)s");
static RE_ERRORS: LazyLock<Regex> = re!(r"(?i)errors=([0-9]+)");
static RE_SYMBOLS: LazyLock<Regex> = re!(r"(?i)symbols=([0-9]+)");
static RE_OPEN_POS: LazyLock<Regex> = re!(r"(?i)open_pos=([0-9]+)");
static RE_WS_CONNECTED: LazyLock<Regex> = re!(r"(?i)ws_connected=(True|False)");
static RE_WS_THREAD: LazyLock<Regex> = re!(r"(?i)ws_thread_alive=(True|False)");
static RE_WS_RESTARTS: LazyLock<Regex> = re!(r"(?i)ws_restarts=([0-9]+)");
static RE_KILL_MODE: LazyLock<Regex> = re!(r"(?i)kill=(off|close_only|halt_all)");
static RE_KILL_REASON: LazyLock<Regex> = re!(r"(?i)kill_reason=(\S+)");
static RE_STRATEGY_MODE: LazyLock<Regex> = re!(r"(?i)strategy_mode=(\S+)");
static RE_REGIME_GATE: LazyLock<Regex> = re!(r"(?i)regime_gate=(on|off)");
static RE_REGIME_REASON: LazyLock<Regex> = re!(r"(?i)regime_reason=(\S+)");
static RE_CONFIG_ID: LazyLock<Regex> = re!(r"(?i)config_id=([0-9a-f]{8,64}|none)");
static RE_SLIP_ENABLED: LazyLock<Regex> = re!(r"(?i)slip_enabled=([01])");
static RE_SLIP_N: LazyLock<Regex> = re!(r"(?i)slip_n=([0-9]+)");
static RE_SLIP_WIN: LazyLock<Regex> = re!(r"(?i)slip_win=([0-9]+)");
static RE_SLIP_THR: LazyLock<Regex> = re!(r"(?i)slip_thr_bps=([0-9.]+)");
static RE_SLIP_LAST: LazyLock<Regex> = re!(r"(?i)slip_last_bps=([0-9.]+|none)");
static RE_SLIP_MED: LazyLock<Regex> = re!(r"(?i)slip_median_bps=([0-9.]+|none)");

fn extract_f64(re: &Regex, line: &str) -> Option<f64> {
    re.captures(line)
        .and_then(|c| c.get(1))
        .and_then(|m| m.as_str().parse().ok())
}

fn extract_i64(re: &Regex, line: &str) -> Option<i64> {
    re.captures(line)
        .and_then(|c| c.get(1))
        .and_then(|m| m.as_str().parse().ok())
}

fn extract_bool_tf(re: &Regex, line: &str) -> Option<bool> {
    re.captures(line)
        .and_then(|c| c.get(1))
        .map(|m| m.as_str().eq_ignore_ascii_case("true"))
}

fn extract_str(re: &Regex, line: &str) -> Option<String> {
    re.captures(line)
        .and_then(|c| c.get(1))
        .map(|m| m.as_str().to_lowercase())
}

fn extract_opt_f64(re: &Regex, line: &str) -> Option<f64> {
    re.captures(line).and_then(|c| c.get(1)).and_then(|m| {
        let s = m.as_str().to_lowercase();
        if s == "none" {
            None
        } else {
            s.parse().ok()
        }
    })
}

/// Parse a heartbeat line into structured fields.
pub fn parse_heartbeat_line(line: &str, ts_ms: Option<i64>, source: &str) -> Heartbeat {
    let mut hb = Heartbeat {
        ok: true,
        source: Some(source.to_string()),
        ts_ms,
        line: Some(line.to_string()),
        ..Default::default()
    };

    hb.loop_s = extract_f64(&RE_LOOP, line);
    hb.errors = extract_i64(&RE_ERRORS, line);
    hb.symbols = extract_i64(&RE_SYMBOLS, line);
    hb.open_pos = extract_i64(&RE_OPEN_POS, line);
    hb.ws_connected = extract_bool_tf(&RE_WS_CONNECTED, line);
    hb.ws_thread_alive = extract_bool_tf(&RE_WS_THREAD, line);
    hb.ws_restarts = extract_i64(&RE_WS_RESTARTS, line);
    hb.kill_mode = extract_str(&RE_KILL_MODE, line);
    hb.kill_reason = extract_str(&RE_KILL_REASON, line);
    hb.strategy_mode = extract_str(&RE_STRATEGY_MODE, line);
    hb.regime_gate = RE_REGIME_GATE
        .captures(line)
        .and_then(|c| c.get(1))
        .map(|m| m.as_str().eq_ignore_ascii_case("on"));
    hb.regime_reason = extract_str(&RE_REGIME_REASON, line);

    hb.config_id = RE_CONFIG_ID
        .captures(line)
        .and_then(|c| c.get(1))
        .and_then(|m| {
            let s = m.as_str().to_lowercase();
            if s == "none" {
                None
            } else {
                Some(s)
            }
        });

    hb.slip_enabled = RE_SLIP_ENABLED
        .captures(line)
        .and_then(|c| c.get(1))
        .map(|m| m.as_str() == "1");
    hb.slip_n = extract_i64(&RE_SLIP_N, line);
    hb.slip_win = extract_i64(&RE_SLIP_WIN, line);
    hb.slip_thr_bps = extract_f64(&RE_SLIP_THR, line);
    hb.slip_last_bps = extract_opt_f64(&RE_SLIP_LAST, line);
    hb.slip_median_bps = extract_opt_f64(&RE_SLIP_MED, line);

    hb
}
