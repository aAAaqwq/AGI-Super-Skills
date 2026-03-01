use std::env;
use std::path::PathBuf;

/// Hub configuration derived from environment variables.
///
/// Variable names are kept compatible with the Python monitor so that the
/// existing `ai-quant-monitor-v8.env` file can be reused as-is.
#[derive(Debug, Clone)]
pub struct HubConfig {
    pub bind: String,
    pub port: u16,
    /// Bearer token for API auth.  Empty ⇒ auth disabled.
    pub token: String,

    // ── Database paths per mode ────────────────────────────────────
    pub live_db: PathBuf,
    pub live_log: PathBuf,
    pub paper1_db: PathBuf,
    pub paper1_log: PathBuf,
    pub paper2_db: PathBuf,
    pub paper2_log: PathBuf,
    pub paper3_db: PathBuf,
    pub paper3_log: PathBuf,

    // ── Candle DBs ─────────────────────────────────────────────────
    pub candles_db_dir: PathBuf,

    // ── WS sidecar ─────────────────────────────────────────────────
    pub sidecar_sock: PathBuf,

    // ── Project root (for relative paths) ──────────────────────────
    pub aiq_root: PathBuf,

    // ── Config directory (for strategy_overrides YAML management) ──
    pub config_dir: PathBuf,

    // ── Misc ───────────────────────────────────────────────────────
    pub trader_interval: String,
    pub monitor_interval: String,
    pub fee_rate: f64,
    pub hl_balance_enable: bool,
    pub hl_main_address: Option<String>,
    /// Fallback cadence used when sidecar does not support blocking `wait_mids`.
    pub mids_poll_ms: u64,
    /// Blocking wait timeout for sidecar `wait_mids` calls.
    pub mids_wait_timeout_ms: u64,
    /// Emit per-publish mids debug logs (seq + changed symbols) for monitor tracing.
    pub mids_debug_log: bool,
    /// Accept and emit frontend flash-trigger debug logs from the monitor UI.
    pub flash_debug_log: bool,

    // ── Manual trade ────────────────────────────────────────────────
    /// Enable manual trading API endpoints.
    pub manual_trade_enabled: bool,
    /// Path to secrets file (for exchange credentials).
    pub secrets_path: Option<String>,
}

fn env_str(name: &str, default: &str) -> String {
    env::var(name)
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| default.to_string())
}

fn env_u16(name: &str, default: u16) -> u16 {
    env::var(name)
        .ok()
        .and_then(|s| s.trim().parse().ok())
        .unwrap_or(default)
}

fn env_u64(name: &str, default: u64) -> u64 {
    env::var(name)
        .ok()
        .and_then(|s| s.trim().parse().ok())
        .unwrap_or(default)
}

fn env_f64(name: &str, default: f64) -> f64 {
    env::var(name)
        .ok()
        .and_then(|s| s.trim().parse().ok())
        .unwrap_or(default)
}

fn env_bool(name: &str, default: bool) -> bool {
    env::var(name)
        .ok()
        .map(|s| {
            matches!(
                s.trim().to_lowercase().as_str(),
                "1" | "true" | "yes" | "y" | "on"
            )
        })
        .unwrap_or(default)
}

fn env_path(name: &str, default: &str) -> PathBuf {
    PathBuf::from(env_str(name, default))
}

fn default_sock_path() -> PathBuf {
    if let Ok(xdg) = env::var("XDG_RUNTIME_DIR") {
        let xdg = xdg.trim();
        if !xdg.is_empty() {
            return PathBuf::from(xdg).join("openclaw-ai-quant-ws.sock");
        }
    }
    PathBuf::from("/tmp/openclaw-ai-quant-ws.sock")
}

impl HubConfig {
    pub fn from_env() -> Self {
        let aiq_root = env_path("AIQ_ROOT", ".");

        let live_db = env_path(
            "AIQ_MONITOR_LIVE_DB",
            aiq_root
                .join("trading_engine_live.db")
                .to_str()
                .unwrap_or("trading_engine_live.db"),
        );
        let live_log = env_path(
            "AIQ_MONITOR_LIVE_LOG",
            aiq_root
                .join("live_daemon_log.txt")
                .to_str()
                .unwrap_or("live_daemon_log.txt"),
        );

        let paper1_db_default = aiq_root.join("trading_engine.db");
        let paper1_db = env_path(
            "AIQ_MONITOR_PAPER1_DB",
            &env_str(
                "AIQ_MONITOR_PAPER_DB",
                paper1_db_default.to_str().unwrap_or("trading_engine.db"),
            ),
        );
        let paper1_log_default = aiq_root.join("daemon_log.txt");
        let paper1_log = env_path(
            "AIQ_MONITOR_PAPER1_LOG",
            &env_str(
                "AIQ_MONITOR_PAPER_LOG",
                paper1_log_default.to_str().unwrap_or("daemon_log.txt"),
            ),
        );

        let paper2_db = env_path(
            "AIQ_MONITOR_PAPER2_DB",
            aiq_root
                .join("trading_engine_paper2.db")
                .to_str()
                .unwrap_or("trading_engine_paper2.db"),
        );
        let paper2_log = env_path(
            "AIQ_MONITOR_PAPER2_LOG",
            aiq_root
                .join("paper2_daemon_log.txt")
                .to_str()
                .unwrap_or("paper2_daemon_log.txt"),
        );

        let paper3_db = env_path(
            "AIQ_MONITOR_PAPER3_DB",
            aiq_root
                .join("trading_engine_paper3.db")
                .to_str()
                .unwrap_or("trading_engine_paper3.db"),
        );
        let paper3_log = env_path(
            "AIQ_MONITOR_PAPER3_LOG",
            aiq_root
                .join("paper3_daemon_log.txt")
                .to_str()
                .unwrap_or("paper3_daemon_log.txt"),
        );

        let config_dir = env_path(
            "AIQ_CONFIG_DIR",
            aiq_root.join("config").to_str().unwrap_or("config"),
        );

        let candles_db_dir_default = env_str(
            "AI_QUANT_CANDLES_DB_DIR",
            aiq_root
                .join("candles_dbs")
                .to_str()
                .unwrap_or("candles_dbs"),
        );
        let candles_db_dir = PathBuf::from(candles_db_dir_default);

        let sidecar_sock = env::var("AI_QUANT_WS_SIDECAR_SOCK")
            .ok()
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .map(PathBuf::from)
            .unwrap_or_else(default_sock_path);

        let trader_interval = env_str("AI_QUANT_INTERVAL", "1h");
        let monitor_interval = {
            let v = env_str("AIQ_MONITOR_INTERVAL", "");
            if v.is_empty() {
                env_str("AI_QUANT_INTERVAL", "1m")
            } else {
                v
            }
        };

        // Fee rate logic ported from Python.
        let fee_rate = {
            let explicit = env_f64("AIQ_MONITOR_FEE_RATE", -1.0);
            if explicit >= 0.0 {
                explicit
            } else {
                let taker = env_f64("HL_PERP_TAKER_FEE_RATE", 0.00045);
                let maker = env_f64("HL_PERP_MAKER_FEE_RATE", 0.00015);
                let mode = env_str("HL_FEE_MODE", "taker");
                let protocol = if mode == "maker" { maker } else { taker };
                let ref_pct = env_f64("HL_REFERRAL_DISCOUNT_PCT", 0.0).clamp(0.0, 100.0);
                let discount_mult = 1.0 - (ref_pct / 100.0);
                let builder = env_f64("HL_BUILDER_FEE_RATE", 0.0);
                (protocol * discount_mult + builder).max(0.0)
            }
        };

        Self {
            bind: env_str("AIQ_MONITOR_BIND", "127.0.0.1"),
            port: env_u16("AIQ_MONITOR_PORT", 61010),
            token: env_str("AIQ_MONITOR_TOKEN", ""),
            live_db,
            live_log,
            paper1_db,
            paper1_log,
            paper2_db,
            paper2_log,
            paper3_db,
            paper3_log,
            candles_db_dir,
            sidecar_sock,
            aiq_root,
            config_dir,
            trader_interval,
            monitor_interval,
            fee_rate,
            hl_balance_enable: env_bool("AIQ_MONITOR_HL_BALANCE_ENABLE", true),
            hl_main_address: env::var("AIQ_MONITOR_HL_MAIN_ADDRESS")
                .ok()
                .or_else(|| env::var("AIQ_MONITOR_MAIN_ADDRESS").ok())
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty()),
            mids_poll_ms: env_u64("AIQ_MONITOR_MIDS_POLL_MS", 100),
            mids_wait_timeout_ms: env_u64("AIQ_MONITOR_MIDS_WAIT_TIMEOUT_MS", 25_000),
            mids_debug_log: env_bool("AIQ_MONITOR_MIDS_DEBUG_LOG", false),
            flash_debug_log: env_bool("AIQ_MONITOR_FLASH_DEBUG_LOG", false),
            manual_trade_enabled: env_bool("AIQ_MANUAL_TRADE_ENABLE", false),
            secrets_path: env::var("AI_QUANT_SECRETS_PATH")
                .ok()
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty()),
        }
    }

    /// Return (db_path, log_path) for the given mode.
    pub fn mode_paths(&self, mode: &str) -> (&PathBuf, &PathBuf) {
        match mode {
            "live" => (&self.live_db, &self.live_log),
            "paper2" => (&self.paper2_db, &self.paper2_log),
            "paper3" => (&self.paper3_db, &self.paper3_log),
            _ => (&self.paper1_db, &self.paper1_log), // "paper" | "paper1" | unknown
        }
    }
}
