use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use serde_json::json;

/// Unified error type for hub API responses.
#[derive(Debug)]
pub enum HubError {
    Db(String),
    Sidecar(String),
    NotFound(String),
    BadRequest(String),
    Unauthorized,
    Forbidden(String),
    Internal(String),
}

impl std::fmt::Display for HubError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Db(msg) => write!(f, "db_error: {msg}"),
            Self::Sidecar(msg) => write!(f, "sidecar_error: {msg}"),
            Self::NotFound(msg) => write!(f, "not_found: {msg}"),
            Self::BadRequest(msg) => write!(f, "bad_request: {msg}"),
            Self::Unauthorized => write!(f, "unauthorized"),
            Self::Forbidden(msg) => write!(f, "forbidden: {msg}"),
            Self::Internal(msg) => write!(f, "internal_error: {msg}"),
        }
    }
}

impl std::error::Error for HubError {}

impl IntoResponse for HubError {
    fn into_response(self) -> Response {
        let (status, error_str) = match &self {
            Self::Db(msg) => (StatusCode::INTERNAL_SERVER_ERROR, format!("db_error:{msg}")),
            Self::Sidecar(msg) => (StatusCode::BAD_GATEWAY, format!("sidecar_error:{msg}")),
            Self::NotFound(msg) => (StatusCode::NOT_FOUND, msg.clone()),
            Self::BadRequest(msg) => (StatusCode::BAD_REQUEST, msg.clone()),
            Self::Unauthorized => (StatusCode::UNAUTHORIZED, "unauthorized".to_string()),
            Self::Forbidden(msg) => (StatusCode::FORBIDDEN, msg.clone()),
            Self::Internal(msg) => (StatusCode::INTERNAL_SERVER_ERROR, msg.clone()),
        };

        let body = json!({ "error": error_str });
        (status, axum::Json(body)).into_response()
    }
}

impl From<rusqlite::Error> for HubError {
    fn from(e: rusqlite::Error) -> Self {
        Self::Db(e.to_string())
    }
}

impl From<r2d2::Error> for HubError {
    fn from(e: r2d2::Error) -> Self {
        Self::Db(e.to_string())
    }
}

impl From<serde_json::Error> for HubError {
    fn from(e: serde_json::Error) -> Self {
        Self::Internal(e.to_string())
    }
}

impl From<std::io::Error> for HubError {
    fn from(e: std::io::Error) -> Self {
        Self::Internal(e.to_string())
    }
}

impl From<serde_yaml::Error> for HubError {
    fn from(e: serde_yaml::Error) -> Self {
        Self::BadRequest(format!("invalid YAML: {e}"))
    }
}
