#!/usr/bin/env python3
"""Sync Hyperliquid universe metadata to SQLite to track listings/delistings.

This is intended to reduce survivorship bias in backtests by keeping a local record of
when symbols appear and disappear from the Hyperliquid perp universe.

The database lives alongside candle DBs by default:
  - `candles_dbs/universe_history.db` (or `$AI_QUANT_CANDLES_DB_DIR/universe_history.db`)

Schema:
  - `universe_snapshots(ts_ms, symbol)` records each sync's universe membership.
  - `universe_listings(symbol, first_seen_ms, last_seen_ms)` is derived incrementally.

Notes:
  - `first_seen_ms` / `last_seen_ms` reflect the first/last time *this script* observed
    the symbol in the live universe. They are not guaranteed to be the exchange's true
    listing/delisting timestamps.
  - To make backtest filtering meaningful, run this script on a schedule (e.g. hourly).

Usage:
  uv run python tools/sync_universe_history.py
  uv run python tools/sync_universe_history.py --db candles_dbs/universe_history.db
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path


DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS universe_snapshots (
    ts_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    PRIMARY KEY (ts_ms, symbol)
);

CREATE TABLE IF NOT EXISTS universe_listings (
    symbol TEXT NOT NULL PRIMARY KEY,
    first_seen_ms INTEGER NOT NULL,
    last_seen_ms INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_universe_snapshots_symbol_ts
    ON universe_snapshots (symbol, ts_ms);
CREATE INDEX IF NOT EXISTS idx_universe_listings_first_last
    ON universe_listings (first_seen_ms, last_seen_ms);
"""


def _default_db_path() -> Path:
    raw_dir = str(os.getenv("AI_QUANT_CANDLES_DB_DIR", "") or "").strip()
    if raw_dir:
        return Path(raw_dir) / "universe_history.db"
    return Path(__file__).resolve().parents[1] / "candles_dbs" / "universe_history.db"


def _hl_timeout_s() -> float:
    raw = os.getenv("AI_QUANT_HL_TIMEOUT_S", "10")
    try:
        v = float(raw)
    except Exception:
        v = 10.0
    return float(max(0.5, min(30.0, v)))


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(DB_SCHEMA)
    conn.commit()


def normalise_symbols(symbols: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for s in symbols:
        sym = str(s or "").strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    out.sort()
    return out


def apply_snapshot(conn: sqlite3.Connection, *, ts_ms: int, symbols: list[str]) -> None:
    """Insert a snapshot and update derived listings (idempotent).

    The derived table is updated with:
      - first_seen_ms = min(existing, ts_ms)
      - last_seen_ms  = max(existing, ts_ms)

    This makes the operation safe even if snapshots arrive out of order.
    """
    ts_ms_i = int(ts_ms)
    syms = normalise_symbols(symbols)
    if not syms:
        return

    rows = [(ts_ms_i, s) for s in syms]
    conn.executemany(
        "INSERT OR IGNORE INTO universe_snapshots (ts_ms, symbol) VALUES (?, ?)",
        rows,
    )

    conn.executemany(
        """
        INSERT INTO universe_listings (symbol, first_seen_ms, last_seen_ms)
        VALUES (?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            first_seen_ms = min(universe_listings.first_seen_ms, excluded.first_seen_ms),
            last_seen_ms  = max(universe_listings.last_seen_ms,  excluded.last_seen_ms)
        """,
        [(s, ts_ms_i, ts_ms_i) for s in syms],
    )
    conn.commit()


def fetch_hyperliquid_universe_symbols(*, timeout_s: float) -> list[str]:
    """Fetch the current perp universe symbols from Hyperliquid."""
    from hyperliquid.info import Info
    from hyperliquid.utils import constants

    info = Info(constants.MAINNET_API_URL, skip_ws=True, timeout=float(timeout_s))
    data = info.meta_and_asset_ctxs()
    if not data or len(data) < 1:
        return []

    meta = data[0] or {}
    universe = meta.get("universe") or []
    out: list[str] = []
    for u in universe:
        try:
            out.append(str(u["name"]).upper())
        except Exception:
            continue
    return normalise_symbols(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync Hyperliquid universe history to SQLite")
    ap.add_argument(
        "--db",
        type=str,
        default=str(_default_db_path()),
        help="SQLite DB path (default: derived from AI_QUANT_CANDLES_DB_DIR or ./candles_dbs/universe_history.db)",
    )
    ap.add_argument(
        "--ts-ms",
        type=int,
        default=0,
        help="Override snapshot timestamp in milliseconds (default: now)",
    )
    ap.add_argument(
        "--timeout-s",
        type=float,
        default=_hl_timeout_s(),
        help="Hyperliquid REST timeout in seconds (default: AI_QUANT_HL_TIMEOUT_S or 10)",
    )
    args = ap.parse_args()

    ts_ms = int(args.ts_ms) if int(args.ts_ms or 0) > 0 else int(time.time() * 1000)

    db_path = Path(args.db).expanduser()
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[universe] ERROR: cannot create DB directory: {db_path.parent} ({e})", file=sys.stderr)
        return 2

    try:
        symbols = fetch_hyperliquid_universe_symbols(timeout_s=float(args.timeout_s))
    except Exception as e:
        print(f"[universe] ERROR: failed to fetch HL universe: {e}", file=sys.stderr)
        return 3

    if not symbols:
        print("[universe] ERROR: fetched empty universe; refusing to write snapshot", file=sys.stderr)
        return 4

    conn = sqlite3.connect(str(db_path), timeout=10.0)
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        ensure_schema(conn)
        try:
            os.chmod(str(db_path), 0o600)
        except OSError:
            pass

        # Pre-read for simple counters
        existing = {r[0] for r in conn.execute("SELECT symbol FROM universe_listings").fetchall()}
        apply_snapshot(conn, ts_ms=ts_ms, symbols=symbols)

        after = {r[0] for r in conn.execute("SELECT symbol FROM universe_listings").fetchall()}
        new_syms = sorted(after - existing)
        print(
            f"[universe] Snapshot written: ts_ms={ts_ms}, symbols={len(symbols)}, new_symbols={len(new_syms)}, db={db_path}"
        )
        if new_syms:
            sample = ", ".join(new_syms[:20])
            suffix = " ..." if len(new_syms) > 20 else ""
            print(f"[universe] New symbols: {sample}{suffix}")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
