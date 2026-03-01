use axum::extract::Request;
use axum::http::StatusCode;
use axum::middleware::Next;
use axum::response::{IntoResponse, Response};
use serde_json::json;

/// Axum middleware: require `Authorization: Bearer <token>` when a token is configured.
///
/// When `AIQ_MONITOR_TOKEN` is empty the middleware is a no-op (backwards compat).
pub async fn require_auth(request: Request, next: Next) -> Response {
    let token = request
        .extensions()
        .get::<AuthToken>()
        .map(|t| t.0.clone())
        .unwrap_or_default();

    // No token configured ⇒ allow all.
    if token.is_empty() {
        return next.run(request).await;
    }

    let auth_header = request
        .headers()
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");

    let expected = format!("Bearer {token}");
    if constant_time_eq(auth_header.as_bytes(), expected.as_bytes()) {
        return next.run(request).await;
    }

    let body = json!({"error": "unauthorized"});
    (StatusCode::UNAUTHORIZED, axum::Json(body)).into_response()
}

/// Extension type injected into every request so the middleware can read the token.
#[derive(Clone)]
pub struct AuthToken(pub String);

/// Constant-time comparison to prevent timing attacks.
fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    let mut diff = 0u8;
    for (x, y) in a.iter().zip(b.iter()) {
        diff |= x ^ y;
    }
    diff == 0
}
