/// Well-known WebSocket topic names.
pub const TOPIC_MIDS: &str = "mids";
pub const TOPIC_BBO: &str = "bbo";
pub const TOPIC_HEARTBEAT: &str = "heartbeat";
pub const TOPIC_TRADES: &str = "trades";

/// Dynamic topic for backtest progress: `backtest:{id}`.
pub fn backtest_topic(id: &str) -> String {
    format!("backtest:{id}")
}

/// Dynamic topic for sweep progress: `sweep:{id}`.
pub fn sweep_topic(id: &str) -> String {
    format!("sweep:{id}")
}
