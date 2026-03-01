use futures_util::{SinkExt, StreamExt};
use serde_json::json;
use std::time::{Duration, Instant};
use tokio_tungstenite::tungstenite::Message;
use tokio_tungstenite::tungstenite::client::IntoClientRequest;
use tokio_tungstenite::tungstenite::http::HeaderValue;

#[tokio::main(flavor = "current_thread")]
async fn main() -> anyhow::Result<()> {
    // rustls 0.23+ requires selecting a crypto provider at process start.
    let _ =
        rustls::crypto::CryptoProvider::install_default(rustls::crypto::ring::default_provider());

    let ws_url =
        std::env::var("HL_WS_URL").unwrap_or_else(|_| "wss://api.hyperliquid.xyz/ws".to_string());

    let mut req = ws_url.as_str().into_client_request()?;
    req.headers_mut().insert(
        "Origin",
        HeaderValue::from_static("https://api.hyperliquid.xyz"),
    );

    let (ws, _resp) = tokio_tungstenite::connect_async(req).await?;
    let (mut w, mut r) = ws.split();

    w.send(Message::Text(
        json!({"method":"subscribe","subscription":{"type":"allMids"}})
            .to_string()
            .into(),
    ))
    .await?;
    w.send(Message::Text(
        json!({"method":"subscribe","subscription":{"type":"meta"}})
            .to_string()
            .into(),
    ))
    .await?;
    w.send(Message::Text(
        json!({"method":"subscribe","subscription":{"type":"candle","coin":"BTC","interval":"1h"}})
            .to_string()
            .into(),
    ))
    .await?;

    let started = Instant::now();
    let mut count = 0u64;
    while started.elapsed() < Duration::from_secs(20) {
        match tokio::time::timeout(Duration::from_secs(5), r.next()).await {
            Ok(Some(Ok(Message::Text(_)))) => count += 1,
            Ok(Some(Ok(Message::Ping(p)))) => {
                let _ = w.send(Message::Pong(p)).await;
            }
            Ok(Some(Ok(Message::Close(_)))) => break,
            Ok(Some(Ok(_))) => {}
            Ok(Some(Err(e))) => {
                eprintln!("read_err: {e}");
                break;
            }
            Ok(None) => break,
            Err(_) => {
                // no message within timeout
            }
        }
    }

    println!("ok count={count}");
    Ok(())
}
