mod auth;
mod config;
mod db;
mod error;
mod heartbeat;
mod routes;
mod sidecar;
mod state;
mod subprocess;
mod ws;

use axum::middleware;
use axum::Router;
use chrono::Utc;
use std::collections::HashMap;
use std::net::SocketAddr;
use std::sync::Arc;
use tower_http::cors::CorsLayer;
use tower_http::services::ServeDir;
use tracing_subscriber::EnvFilter;

use auth::AuthToken;
use config::HubConfig;
use state::AppState;

#[tokio::main]
async fn main() {
    // Initialise tracing.
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .init();

    let cfg = HubConfig::from_env();
    let bind = cfg.bind.clone();
    let port = cfg.port;
    let token = cfg.token.clone();

    let state = AppState::new(cfg);

    // Start background mids poller.
    spawn_mids_poller(Arc::clone(&state));

    // Build router.
    let api = routes::api_router();

    // Static file serving: serve frontend/dist/ at root.
    // During development, you can run `npm run dev` in frontend/ instead.
    let static_dir = std::env::current_dir()
        .unwrap_or_default()
        .join("hub/frontend/dist");

    let app = Router::new()
        .merge(api)
        .route("/ws", axum::routing::get(ws::ws_handler))
        .route("/health", axum::routing::get(health))
        .fallback_service(ServeDir::new(&static_dir).append_index_html_on_directories(true))
        .layer(middleware::from_fn(auth::require_auth))
        .layer(axum::Extension(AuthToken(token)))
        .layer(CorsLayer::permissive())
        .with_state(state);

    let addr: SocketAddr = format!("{bind}:{port}")
        .parse()
        .expect("invalid bind address");

    tracing::info!("AQC Hub listening on http://{addr}");

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await
        .unwrap();
}

async fn health() -> axum::Json<serde_json::Value> {
    axum::Json(serde_json::json!({ "status": "ok" }))
}

async fn shutdown_signal() {
    tokio::signal::ctrl_c()
        .await
        .expect("failed to install Ctrl+C handler");
    tracing::info!("Shutdown signal received, gracefully stopping…");
}

/// Background task: bridge sidecar mids to frontend WS topic.
///
/// Preferred mode uses sidecar `wait_mids` so updates are push-driven instead of
/// fixed-cycle polling. If connected to an older sidecar build, it gracefully
/// falls back to `get_mids` with `mids_poll_ms` cadence.
fn spawn_mids_poller(state: Arc<AppState>) {
    let poll_ms = state.config.mids_poll_ms.max(20);
    let wait_timeout_ms = state.config.mids_wait_timeout_ms.max(100);
    let mids_debug_log = state.config.mids_debug_log;
    tokio::spawn(async move {
        let mut after_seq: Option<u64> = None;
        let mut after_bbo_seq: Option<u64> = None;
        let mut last_published_mids: HashMap<String, f64> = HashMap::new();
        let mut last_published_bbo: HashMap<String, sidecar::BboQuote> = HashMap::new();
        loop {
            // Read the symbols last seen in a snapshot query.
            // Skips until the first REST snapshot has been fetched.
            let symbols: Vec<String> = {
                let tracked = state.tracked_symbols.read().await;
                if tracked.is_empty() {
                    tokio::time::sleep(std::time::Duration::from_millis(poll_ms)).await;
                    continue;
                }
                tracked.clone()
            };

            match state
                .sidecar
                .wait_mids(&symbols, after_seq, after_bbo_seq, wait_timeout_ms)
                .await
            {
                Ok(snap) => {
                    if let Some(seq) = snap.mids_seq {
                        after_seq = Some(seq);
                    }
                    if let Some(seq) = snap.bbo_seq {
                        after_bbo_seq = Some(seq);
                    }
                    // Timeout heartbeats do not carry new price data.
                    if !snap.changed {
                        continue;
                    }
                    if snap.seq_reset {
                        tracing::debug!("sidecar mids sequence reset detected; re-synchronised");
                    }
                    let mids_changed = snap.seq_reset || snap.mids != last_published_mids;
                    let bbo_changed = snap.seq_reset || snap.bbo != last_published_bbo;
                    let mut changed_symbols: Vec<String> = Vec::new();
                    let mut changed_bbo_symbols: Vec<String> = Vec::new();
                    if mids_debug_log {
                        for (sym, mid) in &snap.mids {
                            let is_changed = match last_published_mids.get(sym) {
                                Some(prev) => *prev != *mid,
                                None => true,
                            };
                            if is_changed {
                                changed_symbols.push(sym.clone());
                            }
                        }
                        for (sym, quote) in &snap.bbo {
                            let is_changed = match last_published_bbo.get(sym) {
                                Some(prev) => *prev != *quote,
                                None => true,
                            };
                            if is_changed {
                                changed_bbo_symbols.push(sym.clone());
                            }
                        }
                        changed_symbols.sort_unstable();
                        changed_bbo_symbols.sort_unstable();
                    }
                    last_published_mids = snap.mids.clone();
                    last_published_bbo = snap.bbo.clone();
                    let mut ws_mids_receivers = 0usize;
                    let mut ws_bbo_receivers = 0usize;
                    let mut payload_data =
                        serde_json::to_value(&snap).unwrap_or_else(|_| serde_json::json!({}));
                    if let Some(obj) = payload_data.as_object_mut() {
                        obj.insert(
                            "server_ts_ms".to_string(),
                            serde_json::json!(Utc::now().timestamp_millis()),
                        );
                    }
                    if mids_changed {
                        if let Ok(json) = serde_json::to_string(&serde_json::json!({
                            "type": "mids",
                            "data": payload_data.clone(),
                        })) {
                            ws_mids_receivers =
                                state.broadcast.publish(ws::topics::TOPIC_MIDS, json);
                        }
                    }
                    if bbo_changed {
                        if let Ok(json) = serde_json::to_string(&serde_json::json!({
                            "type": "bbo",
                            "data": payload_data,
                        })) {
                            ws_bbo_receivers = state.broadcast.publish(ws::topics::TOPIC_BBO, json);
                        }
                    }
                    if mids_debug_log {
                        let sample: Vec<String> =
                            changed_symbols.iter().take(20).cloned().collect();
                        let bbo_sample: Vec<String> =
                            changed_bbo_symbols.iter().take(20).cloned().collect();
                        tracing::info!(
                            mids_seq = ?snap.mids_seq,
                            bbo_seq = ?snap.bbo_seq,
                            changed_symbols = changed_symbols.len(),
                            changed_bbo_symbols = changed_bbo_symbols.len(),
                            tracked_symbols = snap.mids.len(),
                            tracked_bbo_symbols = snap.bbo.len(),
                            ws_mids_receivers,
                            ws_bbo_receivers,
                            timed_out = snap.timed_out,
                            seq_reset = snap.seq_reset,
                            sample = ?sample,
                            bbo_sample = ?bbo_sample,
                            "mids publish"
                        );
                    }
                    // Old sidecar fallback path has no sequence support; throttle to poll cadence.
                    if after_seq.is_none() && after_bbo_seq.is_none() {
                        tokio::time::sleep(std::time::Duration::from_millis(poll_ms)).await;
                    }
                }
                Err(e) => {
                    tracing::debug!("Mids poll failed: {e}");
                    // Recover cleanly after sidecar reconnects/restarts.
                    after_seq = None;
                    after_bbo_seq = None;
                    last_published_mids.clear();
                    last_published_bbo.clear();
                    tokio::time::sleep(std::time::Duration::from_millis(poll_ms)).await;
                }
            }
        }
    });
}
