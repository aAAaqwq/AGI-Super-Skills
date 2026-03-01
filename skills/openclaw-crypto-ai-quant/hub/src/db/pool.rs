use r2d2::Pool;
use r2d2_sqlite::SqliteConnectionManager;
use rusqlite::OpenFlags;
use std::path::Path;

pub type DbPool = Pool<SqliteConnectionManager>;

/// Create a read-only SQLite connection pool for the given database file.
///
/// Returns `None` if the file does not exist (non-fatal — the DB might not be
/// created yet, e.g. no paper trades have run).
pub fn open_ro_pool(path: &Path, max_size: u32) -> Option<DbPool> {
    if !path.exists() {
        tracing::warn!("DB not found (will retry on access): {}", path.display());
        return None;
    }

    let flags = OpenFlags::SQLITE_OPEN_READ_ONLY
        | OpenFlags::SQLITE_OPEN_NO_MUTEX
        | OpenFlags::SQLITE_OPEN_URI;
    let manager = SqliteConnectionManager::file(path).with_flags(flags);
    match Pool::builder().max_size(max_size).build(manager) {
        Ok(pool) => Some(pool),
        Err(e) => {
            tracing::error!("Failed to create DB pool for {}: {e}", path.display());
            None
        }
    }
}
