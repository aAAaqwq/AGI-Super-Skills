use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Instant;
use tokio::sync::{Mutex, RwLock};

use crate::config::HubConfig;
use crate::db::pool::{open_ro_pool, DbPool};
use crate::sidecar::SidecarClient;
use crate::subprocess::JobStore;
use crate::ws::broadcast::BroadcastHub;

/// Shared application state, passed to all route handlers via `axum::extract::State`.
pub struct AppState {
    pub config: HubConfig,
    pub broadcast: BroadcastHub,
    pub sidecar: SidecarClient,
    pub jobs: Arc<JobStore>,

    /// Symbols seen in the most recent snapshot query — updated by `api_snapshot`
    /// so the background mids poller always broadcasts real prices.
    pub tracked_symbols: Arc<RwLock<Vec<String>>>,

    // ── Manual trade state ─────────────────────────────────────────
    /// Per-symbol rate-limit timestamps (5-second cooldown).
    pub trade_rate_limits: Mutex<HashMap<String, Instant>>,
    /// Confirm tokens: token → (param_hash, created_at, preview_job_id).
    pub trade_confirm_tokens: Mutex<HashMap<String, (String, Instant, String)>>,

    // DB pools (optional — a DB might not exist yet).
    pub live_pool: Option<DbPool>,
    pub paper1_pool: Option<DbPool>,
    pub paper2_pool: Option<DbPool>,
    pub paper3_pool: Option<DbPool>,
}

impl AppState {
    pub fn new(config: HubConfig) -> Arc<Self> {
        let sidecar = SidecarClient::new(config.sidecar_sock.clone());
        let broadcast = BroadcastHub::new();
        let jobs = JobStore::new();

        let live_pool = open_ro_pool(&config.live_db, 4);
        let paper1_pool = open_ro_pool(&config.paper1_db, 4);
        let paper2_pool = open_ro_pool(&config.paper2_db, 2);
        let paper3_pool = open_ro_pool(&config.paper3_db, 2);

        Arc::new(Self {
            config,
            broadcast,
            sidecar,
            jobs,
            tracked_symbols: Arc::new(RwLock::new(Vec::new())),
            trade_rate_limits: Mutex::new(HashMap::new()),
            trade_confirm_tokens: Mutex::new(HashMap::new()),
            live_pool,
            paper1_pool,
            paper2_pool,
            paper3_pool,
        })
    }

    /// Get the DB pool for a given mode.
    pub fn db_pool(&self, mode: &str) -> Option<&DbPool> {
        match mode {
            "live" => self.live_pool.as_ref(),
            "paper2" => self.paper2_pool.as_ref(),
            "paper3" => self.paper3_pool.as_ref(),
            _ => self.paper1_pool.as_ref(), // paper, paper1, unknown
        }
    }

    /// Open a candle DB for a specific interval.
    pub fn candle_db_path(&self, interval: &str) -> PathBuf {
        let safe_iv: String = interval
            .chars()
            .map(|c| {
                if c.is_alphanumeric() {
                    c.to_ascii_lowercase()
                } else {
                    '_'
                }
            })
            .collect();
        self.config
            .candles_db_dir
            .join(format!("candles_{safe_iv}.db"))
    }
}
