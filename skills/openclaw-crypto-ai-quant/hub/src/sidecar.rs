use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::UnixStream;
use tokio::sync::Mutex;

/// Async Unix-socket JSON-RPC client for the WS sidecar.
///
/// Protocol: newline-delimited JSON, one request → one response.
/// Compatible with `exchange/sidecar.py` `SidecarWSClient`.
pub struct SidecarClient {
    sock_path: PathBuf,
    conn: Mutex<Option<SidecarConn>>,
    next_id: AtomicU64,
}

struct SidecarConn {
    reader: BufReader<tokio::io::ReadHalf<UnixStream>>,
    writer: tokio::io::WriteHalf<UnixStream>,
}

#[derive(Debug, Serialize)]
struct RpcRequest {
    id: u64,
    method: String,
    params: Value,
}

#[derive(Debug, Deserialize)]
struct RpcResponse {
    id: u64,
    ok: bool,
    result: Option<Value>,
    error: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct BboQuote {
    pub bid: f64,
    pub ask: f64,
    pub mid: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct MidsSnapshot {
    pub mids: HashMap<String, f64>,
    pub mids_age_s: Option<f64>,
    pub mids_seq: Option<u64>,
    pub bbo: HashMap<String, BboQuote>,
    pub bbo_age_s: Option<f64>,
    pub bbo_seq: Option<u64>,
    pub changed: bool,
    pub timed_out: bool,
    pub seq_reset: bool,
}

fn parse_f64_value(v: &Value) -> Option<f64> {
    v.as_f64()
        .or_else(|| v.as_str().and_then(|s| s.trim().parse::<f64>().ok()))
}

fn parse_u64_value(v: &Value) -> Option<u64> {
    if let Some(u) = v.as_u64() {
        return Some(u);
    }
    v.as_i64()
        .and_then(|i| if i >= 0 { Some(i as u64) } else { None })
}

fn parse_bbo_quotes(result: &Value) -> HashMap<String, BboQuote> {
    let mut out = HashMap::new();
    let bbo_raw = result.get("bbo").and_then(|v| v.as_object());
    if let Some(map) = bbo_raw {
        for (sym, raw) in map {
            let Some(obj) = raw.as_object() else {
                continue;
            };
            let bid = obj.get("bid").and_then(parse_f64_value);
            let ask = obj.get("ask").and_then(parse_f64_value);
            let mid = obj.get("mid").and_then(parse_f64_value);
            if let (Some(bid), Some(ask), Some(mid)) = (bid, ask, mid) {
                out.insert(sym.to_uppercase(), BboQuote { bid, ask, mid });
            }
        }
    }
    out
}

impl SidecarClient {
    pub fn new(sock_path: PathBuf) -> Self {
        Self {
            sock_path,
            conn: Mutex::new(None),
            next_id: AtomicU64::new(1),
        }
    }

    async fn connect(&self) -> Result<SidecarConn, String> {
        let stream = UnixStream::connect(&self.sock_path)
            .await
            .map_err(|e| format!("sidecar connect failed: {e}"))?;
        let (read_half, write_half) = tokio::io::split(stream);
        Ok(SidecarConn {
            reader: BufReader::new(read_half),
            writer: write_half,
        })
    }

    async fn rpc(&self, method: &str, params: Value) -> Result<Value, String> {
        let rid = self.next_id.fetch_add(1, Ordering::Relaxed);
        let req = RpcRequest {
            id: rid,
            method: method.to_string(),
            params,
        };
        let mut line = serde_json::to_string(&req).map_err(|e| e.to_string())?;
        line.push('\n');

        let mut guard = self.conn.lock().await;

        // Ensure connection.
        if guard.is_none() {
            *guard = Some(self.connect().await?);
        }

        // Take the connection out so we have exclusive ownership (no split borrows).
        let mut conn = guard.take().unwrap();

        // Send request.
        if let Err(e) = conn.writer.write_all(line.as_bytes()).await {
            return Err(format!("sidecar write failed: {e}"));
        }
        if let Err(e) = conn.writer.flush().await {
            return Err(format!("sidecar flush failed: {e}"));
        }

        // Read response.
        let mut resp_line = String::new();
        if let Err(e) = conn.reader.read_line(&mut resp_line).await {
            return Err(format!("sidecar read failed: {e}"));
        }

        if resp_line.is_empty() {
            return Err("sidecar closed connection".to_string());
        }

        let resp: RpcResponse = match serde_json::from_str(&resp_line) {
            Ok(r) => r,
            Err(e) => return Err(format!("sidecar response parse failed: {e}")),
        };

        // Put connection back for reuse.
        *guard = Some(conn);

        if resp.id != rid {
            *guard = None;
            return Err("sidecar response id mismatch".to_string());
        }

        if !resp.ok {
            return Err(resp.error.unwrap_or_else(|| "sidecar error".to_string()));
        }

        Ok(resp.result.unwrap_or(Value::Null))
    }

    /// Health check.
    pub async fn health(&self) -> Result<Value, String> {
        self.rpc("health", serde_json::json!({})).await
    }

    /// Get mid prices for symbols.
    pub async fn get_mids(&self, symbols: &[String]) -> Result<MidsSnapshot, String> {
        let result = self
            .rpc(
                "get_mids",
                serde_json::json!({
                    "symbols": symbols,
                    "max_age_s": null
                }),
            )
            .await?;

        let mids_raw = result.get("mids").and_then(|v| v.as_object());
        let mut mids = HashMap::new();
        if let Some(m) = mids_raw {
            for (k, v) in m {
                if let Some(f) = parse_f64_value(v) {
                    mids.insert(k.to_uppercase(), f);
                }
            }
        }
        let mids_age_s = result.get("mids_age_s").and_then(parse_f64_value);
        let bbo = parse_bbo_quotes(&result);
        Ok(MidsSnapshot {
            mids,
            mids_age_s,
            mids_seq: result.get("mids_seq").and_then(parse_u64_value),
            bbo,
            bbo_age_s: result.get("bbo_age_s").and_then(parse_f64_value),
            bbo_seq: result.get("bbo_seq").and_then(parse_u64_value),
            changed: true,
            timed_out: false,
            seq_reset: false,
        })
    }

    /// Wait for a sidecar mids change and return the latest snapshot.
    pub async fn wait_mids(
        &self,
        symbols: &[String],
        after_seq: Option<u64>,
        after_bbo_seq: Option<u64>,
        timeout_ms: u64,
    ) -> Result<MidsSnapshot, String> {
        let timeout_ms = timeout_ms.clamp(50, 120_000);
        let result = match self
            .rpc(
                "wait_mids",
                serde_json::json!({
                    "symbols": symbols,
                    "after_seq": after_seq.unwrap_or(0),
                    "after_bbo_seq": after_bbo_seq.unwrap_or(0),
                    "max_age_s": null,
                    "timeout_ms": timeout_ms
                }),
            )
            .await
        {
            Ok(v) => v,
            Err(e) => {
                // Backward-compatible fallback for sidecars that do not expose wait_mids yet.
                if e.to_ascii_lowercase().contains("unknown method") {
                    return self.get_mids(symbols).await;
                }
                return Err(e);
            }
        };

        let mids_raw = result.get("mids").and_then(|v| v.as_object());
        let mut mids = HashMap::new();
        if let Some(m) = mids_raw {
            for (k, v) in m {
                if let Some(f) = parse_f64_value(v) {
                    mids.insert(k.to_uppercase(), f);
                }
            }
        }
        let bbo = parse_bbo_quotes(&result);
        Ok(MidsSnapshot {
            mids,
            mids_age_s: result.get("mids_age_s").and_then(parse_f64_value),
            mids_seq: result.get("mids_seq").and_then(parse_u64_value),
            bbo,
            bbo_age_s: result.get("bbo_age_s").and_then(parse_f64_value),
            bbo_seq: result.get("bbo_seq").and_then(parse_u64_value),
            changed: result
                .get("changed")
                .and_then(|v| v.as_bool())
                .unwrap_or(true),
            timed_out: result
                .get("timed_out")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
            seq_reset: result
                .get("seq_reset")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
        })
    }

    /// Get a single mid price.
    pub async fn get_mid(&self, symbol: &str) -> Result<Option<f64>, String> {
        let result = self
            .rpc(
                "get_mid",
                serde_json::json!({
                    "symbol": symbol.to_uppercase(),
                    "max_age_s": null
                }),
            )
            .await?;
        Ok(result.as_f64())
    }
}
