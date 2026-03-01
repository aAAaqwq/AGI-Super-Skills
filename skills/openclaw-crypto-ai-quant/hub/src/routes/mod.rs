pub mod backtest;
pub mod config;
pub mod decisions;
pub mod factory;
pub mod monitor;
pub mod sweep;
pub mod system;
pub mod trade;

use axum::Router;
use std::sync::Arc;

use crate::state::AppState;

/// Assemble the API router.
pub fn api_router() -> Router<Arc<AppState>> {
    Router::new()
        .merge(monitor::routes())
        .merge(decisions::routes())
        .merge(config::routes())
        .merge(backtest::routes())
        .merge(sweep::routes())
        .merge(factory::routes())
        .merge(system::routes())
        .merge(trade::routes())
}
