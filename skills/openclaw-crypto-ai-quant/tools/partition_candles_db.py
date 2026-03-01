#!/usr/bin/env python3
"""Partition a candle SQLite DB into monthly archive files (AQC-204).

This tool is intended to keep the "hot" candle DBs small (for faster reads and
to avoid unbounded single-file growth) while retaining long history in
partitioned monthly SQLite files.

It copies rows older than a cutoff into monthly partition DBs and (optionally)
deletes them from the source DB.

Defaults:
- Source DB: `candles_dbs/candles_{interval}.db`
- Output dir: `<src_dir>/partitions/<interval>/`
- Cutoff: `now - keep_days` (default: 90 days)

Safety:
- By default this is a dry-run (no writes). Use `--apply` to perform changes.
- For best results, stop the WS sidecar before running `--apply` on its DB.

Usage:
  uv run python tools/partition_candles_db.py --interval 5m
  uv run python tools/partition_candles_db.py --interval 5m --keep-days 120 --apply --delete

Backtester usage (after partitioning):
  mei-backtester replay --candles-db candles_dbs/candles_5m.db,candles_dbs/partitions/5m
"""

from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import sys
import time
from pathlib import Path


CANDLES_SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    t INTEGER NOT NULL,
    t_close INTEGER,
    o REAL,
    h REAL,
    l REAL,
    c REAL,
    v REAL,
    n INTEGER,
    updated_at TEXT,
    PRIMARY KEY (symbol, interval, t)
);
CREATE INDEX IF NOT EXISTS idx_candles_symbol_interval_t
    ON candles(symbol, interval, t);
"""


def canonical_interval(raw: str) -> str:
    s = str(raw or "").strip().lower()
    if s.endswith("hr"):
        base = s.removesuffix("hr").strip()
        if base:
            s = f"{base}h"
    return s


def _default_src_db(interval: str) -> Path:
    here = Path(__file__).resolve().parents[1]
    return here / "candles_dbs" / f"candles_{interval}.db"


def _default_out_dir(src_db: Path, interval: str) -> Path:
    return src_db.parent / "partitions" / interval


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(CANDLES_SCHEMA)
    conn.commit()


def _month_str_from_ts_ms(ts_ms: int) -> str:
    d = dt.datetime.utcfromtimestamp(ts_ms / 1000.0)
    return f"{d.year:04d}-{d.month:02d}"


def _list_months_to_partition(conn: sqlite3.Connection, *, interval: str, cutoff_ts_ms: int) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT strftime('%Y-%m', t/1000, 'unixepoch') AS ym "
        "FROM candles WHERE interval = ?1 AND t < ?2 "
        "ORDER BY ym ASC",
        (interval, int(cutoff_ts_ms)),
    ).fetchall()
    out: list[str] = []
    for (ym,) in rows:
        if isinstance(ym, str) and ym:
            out.append(ym)
    return out


def _count_rows_for_month(
    conn: sqlite3.Connection,
    *,
    interval: str,
    ym: str,
    cutoff_ts_ms: int,
) -> int:
    (n,) = conn.execute(
        "SELECT COUNT(*) FROM candles "
        "WHERE interval = ?1 AND t < ?2 AND strftime('%Y-%m', t/1000, 'unixepoch') = ?3",
        (interval, int(cutoff_ts_ms), ym),
    ).fetchone()
    return int(n)


def _partition_month_apply(
    conn: sqlite3.Connection,
    *,
    interval: str,
    ym: str,
    cutoff_ts_ms: int,
    out_db: Path,
    delete_from_src: bool,
) -> tuple[int, int]:
    """Copy one month into out_db; optionally delete from src. Returns (copied, deleted)."""
    out_db.parent.mkdir(parents=True, exist_ok=True)
    out_conn = sqlite3.connect(str(out_db), timeout=30.0)
    try:
        out_conn.execute("PRAGMA journal_mode = WAL;")
        out_conn.execute("PRAGMA synchronous = NORMAL;")
        ensure_schema(out_conn)
    finally:
        out_conn.close()

    # Attach, insert, optionally delete.
    conn.execute("ATTACH DATABASE ? AS out", (str(out_db),))
    try:
        conn.execute("BEGIN")
        before_changes = conn.total_changes

        conn.execute(
            "INSERT OR IGNORE INTO out.candles (symbol, interval, t, t_close, o, h, l, c, v, n, updated_at) "
            "SELECT symbol, interval, t, t_close, o, h, l, c, v, n, updated_at "
            "FROM main.candles "
            "WHERE interval = ?1 AND t < ?2 AND strftime('%Y-%m', t/1000, 'unixepoch') = ?3",
            (interval, int(cutoff_ts_ms), ym),
        )
        copied = conn.total_changes - before_changes

        deleted = 0
        if delete_from_src:
            before_del = conn.total_changes
            conn.execute(
                "DELETE FROM main.candles "
                "WHERE interval = ?1 AND t < ?2 AND strftime('%Y-%m', t/1000, 'unixepoch') = ?3",
                (interval, int(cutoff_ts_ms), ym),
            )
            deleted = conn.total_changes - before_del

        conn.execute("COMMIT")
        return int(copied), int(deleted)
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.execute("DETACH DATABASE out")


def main() -> int:
    ap = argparse.ArgumentParser(description="Partition candles SQLite DB into monthly archive files (AQC-204).")
    ap.add_argument("--interval", required=True, help="Candle interval (e.g. 3m, 5m, 1h).")
    ap.add_argument(
        "--src-db",
        default="",
        help="Source candles DB path (default: candles_dbs/candles_{interval}.db).",
    )
    ap.add_argument(
        "--out-dir",
        default="",
        help="Output directory for monthly partitions (default: <src_dir>/partitions/<interval>/).",
    )
    ap.add_argument(
        "--keep-days",
        type=int,
        default=90,
        help="Keep this many recent days in the source DB (default: 90).",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Perform writes (default: dry-run).",
    )
    ap.add_argument(
        "--delete",
        action="store_true",
        help="After copying, delete archived rows from the source DB (requires --apply).",
    )
    ap.add_argument(
        "--vacuum",
        action="store_true",
        help="Run VACUUM on the source DB after deletion (requires --apply --delete).",
    )
    args = ap.parse_args()

    interval = canonical_interval(args.interval)
    if not interval:
        print("[partition] ERROR: empty --interval", file=sys.stderr)
        return 2

    src_db = Path(args.src_db).expanduser() if args.src_db else _default_src_db(interval)
    out_dir = Path(args.out_dir).expanduser() if args.out_dir else _default_out_dir(src_db, interval)

    keep_days = int(args.keep_days)
    if keep_days < 1:
        print("[partition] ERROR: --keep-days must be >= 1", file=sys.stderr)
        return 2

    now_ms = int(time.time() * 1000)
    cutoff_ts_ms = now_ms - keep_days * 86_400_000
    cutoff_ym = _month_str_from_ts_ms(cutoff_ts_ms)

    mode = "apply" if args.apply else "dry_run"
    print(
        f"[partition] mode={mode} interval={interval} src_db={src_db} out_dir={out_dir} keep_days={keep_days} cutoff_ts_ms={cutoff_ts_ms} (cutoff_month={cutoff_ym})"
    )

    if args.delete and not args.apply:
        print("[partition] ERROR: --delete requires --apply", file=sys.stderr)
        return 2
    if args.vacuum and not (args.apply and args.delete):
        print("[partition] ERROR: --vacuum requires --apply --delete", file=sys.stderr)
        return 2

    if not src_db.exists():
        print(f"[partition] ERROR: source DB does not exist: {src_db}", file=sys.stderr)
        return 3

    conn = sqlite3.connect(str(src_db), timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")

        months = _list_months_to_partition(conn, interval=interval, cutoff_ts_ms=cutoff_ts_ms)
        if not months:
            print("[partition] No months to partition (nothing older than cutoff).")
            return 0

        total_to_copy = 0
        for ym in months:
            n = _count_rows_for_month(conn, interval=interval, ym=ym, cutoff_ts_ms=cutoff_ts_ms)
            total_to_copy += n
            print(f"[partition] month={ym} rows={n}")

        if not args.apply:
            print(f"[partition] Dry-run complete. rows_to_archive={total_to_copy}")
            return 0

        copied_total = 0
        deleted_total = 0
        for ym in months:
            out_db = out_dir / f"candles_{interval}_{ym}.db"
            copied, deleted = _partition_month_apply(
                conn,
                interval=interval,
                ym=ym,
                cutoff_ts_ms=cutoff_ts_ms,
                out_db=out_db,
                delete_from_src=bool(args.delete),
            )
            copied_total += copied
            deleted_total += deleted
            print(f"[partition] month={ym} out_db={out_db} copied={copied} deleted={deleted}")

        if args.vacuum:
            print("[partition] VACUUM starting (may take a while)...")
            conn.execute("VACUUM")
            print("[partition] VACUUM done.")

        print(
            f"[partition] Done. copied_total={copied_total} deleted_total={deleted_total} out_dir={out_dir}"
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

