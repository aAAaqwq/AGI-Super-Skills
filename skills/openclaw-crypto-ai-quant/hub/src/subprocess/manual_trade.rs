use std::process::Stdio;
use std::sync::Arc;
use tokio::process::Command;

use crate::ws::broadcast::BroadcastHub;

use super::{run_subprocess, JobId, JobStore};

/// Manual trade action.
pub enum ManualTradeAction {
    Preview,
    Execute,
    Close,
    Cancel,
    OpenOrders,
}

impl ManualTradeAction {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Preview => "preview",
            Self::Execute => "execute",
            Self::Close => "close",
            Self::Cancel => "cancel",
            Self::OpenOrders => "open-orders",
        }
    }
}

/// Arguments for spawning a manual trade subprocess.
pub struct ManualTradeArgs {
    pub action: ManualTradeAction,
    pub symbol: String,
    pub side: Option<String>,
    pub notional_usd: Option<f64>,
    pub leverage: Option<u32>,
    pub order_type: Option<String>,
    pub limit_price: Option<f64>,
    pub close_pct: Option<f64>,
    pub oid: Option<String>,
    pub intent_id: Option<String>,
    pub db_path: Option<String>,
    pub secrets_path: Option<String>,
}

/// Spawn a manual trade as a subprocess.
///
/// Runs `uv run tools/manual_trade.py --action ...` in the project root
/// directory. Stdout captures JSON result, stderr streams progress lines.
pub async fn spawn_manual_trade(
    job_id: JobId,
    args: ManualTradeArgs,
    aiq_root: String,
    store: Arc<JobStore>,
    broadcast: BroadcastHub,
) {
    let mut cmd = Command::new("uv");
    cmd.arg("run")
        .arg("tools/manual_trade.py")
        .arg("--action")
        .arg(args.action.as_str())
        .arg("--symbol")
        .arg(&args.symbol);

    if let Some(ref side) = args.side {
        cmd.arg("--side").arg(side);
    }
    if let Some(notional) = args.notional_usd {
        cmd.arg("--notional").arg(notional.to_string());
    }
    if let Some(leverage) = args.leverage {
        cmd.arg("--leverage").arg(leverage.to_string());
    }
    if let Some(ref order_type) = args.order_type {
        cmd.arg("--order-type").arg(order_type);
    }
    if let Some(limit_price) = args.limit_price {
        cmd.arg("--limit-price").arg(limit_price.to_string());
    }
    if let Some(close_pct) = args.close_pct {
        cmd.arg("--close-pct").arg(close_pct.to_string());
    }
    if let Some(ref oid) = args.oid {
        cmd.arg("--oid").arg(oid);
    }
    if let Some(ref intent_id) = args.intent_id {
        cmd.arg("--intent-id").arg(intent_id);
    }
    if let Some(ref db_path) = args.db_path {
        cmd.arg("--db-path").arg(db_path);
    }
    if let Some(ref secrets_path) = args.secrets_path {
        cmd.arg("--secrets-path").arg(secrets_path);
        cmd.env("AI_QUANT_SECRETS_PATH", secrets_path);
    }

    cmd.current_dir(&aiq_root)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let jid = job_id.clone();
    tokio::spawn(async move {
        run_subprocess(jid, "manual_trade", cmd, store, broadcast).await;
    });
}
