#!/usr/bin/env python3
"""Apply a canonical snapshot JSON to a paper database.

This creates synthetic seed rows so `PaperTrader.load_state()` reconstructs positions
from the target DB in the same shape as live-canonical state.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Any


def _validate_identifier(name: str) -> None:
    if not name or not all(ch.isalnum() or ch == "_" for ch in name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def _get_table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    _validate_identifier(table_name)
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [str(r[1]) for r in rows]


def _insert_projection(conn: sqlite3.Connection, table_name: str, row: dict[str, Any]) -> int:
    columns = _get_table_columns(conn, table_name)
    keys = [k for k in row.keys() if k in columns]
    if not keys:
        return 0

    placeholders = ",".join("?" for _ in keys)
    sql = f"INSERT INTO {table_name} ({','.join(keys)}) VALUES ({placeholders})"
    values = [row[k] for k in keys]
    cur = conn.cursor()
    cur.execute(sql, values)
    return int(cur.lastrowid or 0)


def _iso_from_ms(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000.0, tz=dt.timezone.utc).isoformat()


def _load_snapshot(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Snapshot must be a JSON object")
    version = int(payload.get("version") or 0)
    if version not in (1, 2):
        raise ValueError(f"Unsupported snapshot version: {version}")
    return payload


def _ensure_position_state_history_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS position_state_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_ts_ms INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            symbol TEXT NOT NULL,
            open_trade_id INTEGER,
            trailing_sl REAL,
            last_funding_time INTEGER,
            adds_count INTEGER,
            tp1_taken INTEGER,
            last_add_time INTEGER,
            entry_adx_threshold REAL,
            event_type TEXT NOT NULL,
            run_fingerprint TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_position_state_history_symbol_ts ON position_state_history(symbol, event_ts_ms)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_position_state_history_open_trade_ts ON position_state_history(open_trade_id, event_ts_ms)"
    )


def _seed_history_rows(
    conn: sqlite3.Connection,
    *,
    seed_history: dict[str, Any],
    strict_replace: bool,
) -> dict[str, int]:
    if not strict_replace:
        return {}
    if not isinstance(seed_history, dict):
        return {}

    rows_by_table = seed_history.get("rows")
    if not isinstance(rows_by_table, dict):
        return {}

    inserted: dict[str, int] = {}
    load_order = (
        "ws_events",
        "oms_intents",
        "oms_orders",
        "oms_fills",
        "signals",
        "audit_events",
        "decision_events",
        "decision_context",
        "gate_evaluations",
    )
    for table_name in load_order:
        if not _table_exists(conn, table_name):
            continue
        raw_rows = rows_by_table.get(table_name)
        if not isinstance(raw_rows, list) or not raw_rows:
            continue
        count = 0
        for row in raw_rows:
            if not isinstance(row, dict):
                continue
            insert_row = dict(row)
            if table_name == "decision_events" and "trade_id" in insert_row:
                insert_row["trade_id"] = None
            _insert_projection(conn, table_name, insert_row)
            count += 1
        if count > 0:
            inserted[table_name] = count

    return inserted


def _seed_trades_and_positions(
    conn: sqlite3.Connection,
    *,
    balance: float,
    seed_ts_ms: int,
    positions: list[dict[str, Any]],
    strict_replace: bool,
) -> tuple[int, int]:
    if not _table_exists(conn, "trades"):
        return 0, 0

    seed_iso = _iso_from_ms(seed_ts_ms)
    _ensure_position_state_history_table(conn)

    open_symbol_type: dict[str, str] = {}
    if strict_replace:
        conn.execute("DELETE FROM trades")
        for table_name in (
            "decision_events",
            "decision_context",
            "gate_evaluations",
            "decision_lineage",
            "signals",
            "audit_events",
            "oms_intents",
            "oms_orders",
            "oms_fills",
            "ws_events",
            "position_state_history",
        ):
            if _table_exists(conn, table_name):
                conn.execute(f"DELETE FROM {table_name}")
    else:
        # Keep real history; remove only previous synthetic seed rows.
        conn.execute(
            "DELETE FROM trades WHERE reason IN ('state_sync_seed', 'state_sync_balance_seed', 'state_sync_seed_close')"
        )

        open_rows = conn.execute(
            """
            SELECT t.symbol, t.type AS pos_type
            FROM trades t
            INNER JOIN (
                SELECT symbol, MAX(id) AS open_id
                FROM trades WHERE action = 'OPEN' GROUP BY symbol
            ) lo ON t.id = lo.open_id
            LEFT JOIN (
                SELECT symbol, MAX(id) AS close_id
                FROM trades WHERE action = 'CLOSE' GROUP BY symbol
            ) lc ON t.symbol = lc.symbol
            WHERE lc.close_id IS NULL OR lo.open_id > lc.close_id
            """
        ).fetchall()
        for row in open_rows:
            symbol = str(row["symbol"] or "").strip().upper()
            pos_type = str(row["pos_type"] or "").strip().upper()
            if symbol and pos_type in {"LONG", "SHORT"}:
                open_symbol_type[symbol] = pos_type

    # Ensure latest balance seed exists in trades so PaperTrader loads this balance.
    _insert_projection(
        conn,
        "trades",
        {
            "timestamp": seed_iso,
            "action": "SYSTEM",
            "type": "SYSTEM",
            "symbol": "SYSTEM",
            "price": 0.0,
            "size": 0.0,
            "reason": "state_sync_balance_seed",
            "confidence": "medium",
            "balance": float(balance),
            "pnl": 0.0,
            "entry_atr": 0.0,
            "fee_usd": 0.0,
            "fee_rate": 0.0,
            "leverage": 1.0,
            "margin_used": 0.0,
            "meta_json": json.dumps({"source": "canonical_snapshot"}, separators=(",", ":")),
        },
    )

    seeded_trades = 0
    seeded_positions = 0
    seeded_symbols: set[str] = set()

    if _table_exists(conn, "position_state"):
        conn.execute("DELETE FROM position_state")

    for idx, pos in enumerate(positions):
        symbol = str(pos.get("symbol") or "").strip().upper()
        side = str(pos.get("side") or "").strip().lower()
        if not symbol or side not in {"long", "short"}:
            continue

        ts_ms = int(pos.get("open_time_ms") or seed_ts_ms)
        ts_iso = _iso_from_ms(ts_ms)
        pos_type = "LONG" if side == "long" else "SHORT"
        size = float(pos.get("size") or 0.0)
        entry_price = float(pos.get("entry_price") or 0.0)
        if size <= 0.0 or entry_price <= 0.0:
            continue

        entry_atr = float(pos.get("entry_atr") or 0.0)
        confidence = str(pos.get("confidence") or "medium").strip().lower() or "medium"
        leverage = float(pos.get("leverage") or 1.0)
        if leverage <= 0.0:
            leverage = 1.0
        margin_used = float(pos.get("margin_used") or (abs(size) * entry_price / leverage))

        trade_id = _insert_projection(
            conn,
            "trades",
            {
                "timestamp": ts_iso,
                "symbol": symbol,
                "action": "OPEN",
                "type": pos_type,
                "price": entry_price,
                "size": size,
                "reason": "state_sync_seed",
                "confidence": confidence,
                "balance": float(balance),
                "pnl": 0.0,
                "entry_atr": entry_atr,
                "fee_usd": 0.0,
                "fee_rate": 0.0,
                "leverage": leverage,
                "margin_used": margin_used,
                "meta_json": json.dumps({"source": "canonical_snapshot", "seed_idx": idx}, separators=(",", ":")),
            },
        )
        seeded_trades += 1
        seeded_symbols.add(symbol)

        if _table_exists(conn, "position_state"):
            _insert_projection(
                conn,
                "position_state",
                {
                    "symbol": symbol,
                    "open_trade_id": int(trade_id),
                    "trailing_sl": pos.get("trailing_sl"),
                    "last_funding_time": int(pos.get("open_time_ms") or ts_ms),
                    "adds_count": int(pos.get("adds_count") or 0),
                    "tp1_taken": 1 if bool(pos.get("tp1_taken")) else 0,
                    "last_add_time": int(pos.get("last_add_time_ms") or 0),
                    "entry_adx_threshold": float(pos.get("entry_adx_threshold") or 0.0),
                    "updated_at": seed_iso,
                },
            )
            seeded_positions += 1
            if _table_exists(conn, "position_state_history"):
                _insert_projection(
                    conn,
                    "position_state_history",
                    {
                        "event_ts_ms": int(ts_ms),
                        "updated_at": seed_iso,
                        "symbol": symbol,
                        "open_trade_id": int(trade_id),
                        "trailing_sl": pos.get("trailing_sl"),
                        "last_funding_time": int(pos.get("open_time_ms") or ts_ms),
                        "adds_count": int(pos.get("adds_count") or 0),
                        "tp1_taken": 1 if bool(pos.get("tp1_taken")) else 0,
                        "last_add_time": int(pos.get("last_add_time_ms") or 0),
                        "entry_adx_threshold": float(pos.get("entry_adx_threshold") or 0.0),
                        "event_type": "state_sync_seed",
                        "run_fingerprint": "state_sync_seed",
                    },
                )

    if not strict_replace:
        for symbol, pos_type in sorted(open_symbol_type.items()):
            if symbol in seeded_symbols:
                continue
            _insert_projection(
                conn,
                "trades",
                {
                    "timestamp": seed_iso,
                    "symbol": symbol,
                    "action": "CLOSE",
                    "type": pos_type,
                    "price": 0.0,
                    "size": 0.0,
                    "reason": "state_sync_seed_close",
                    "confidence": "medium",
                    "balance": float(balance),
                    "pnl": 0.0,
                    "entry_atr": 0.0,
                    "fee_usd": 0.0,
                    "fee_rate": 0.0,
                    "leverage": 1.0,
                    "margin_used": 0.0,
                    "meta_json": json.dumps({"source": "canonical_snapshot", "seed_close": True}, separators=(",", ":")),
                },
            )
            seeded_trades += 1

    return seeded_trades, seeded_positions


def _replace_open_orders(conn: sqlite3.Connection, open_orders: list[dict[str, Any]]) -> int:
    if not _table_exists(conn, "oms_open_orders"):
        return 0

    conn.execute("DELETE FROM oms_open_orders")
    inserted = 0
    for row in open_orders:
        if not isinstance(row, dict):
            continue
        _insert_projection(conn, "oms_open_orders", row)
        inserted += 1
    return inserted


def _seed_runtime_cooldowns(
    conn: sqlite3.Connection,
    *,
    runtime: dict[str, Any],
    seed_ts_ms: int,
) -> int:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runtime_cooldowns (
            symbol TEXT PRIMARY KEY,
            last_entry_attempt_s REAL,
            last_exit_attempt_s REAL,
            updated_at TEXT
        )
        """
    )

    conn.execute("DELETE FROM runtime_cooldowns")
    entry_map = runtime.get("entry_attempt_ms_by_symbol") or {}
    exit_map = runtime.get("exit_attempt_ms_by_symbol") or {}
    if not isinstance(entry_map, dict):
        entry_map = {}
    if not isinstance(exit_map, dict):
        exit_map = {}

    symbols = set()
    symbols.update(str(k or "").strip().upper() for k in entry_map.keys())
    symbols.update(str(k or "").strip().upper() for k in exit_map.keys())
    symbols.discard("")

    seed_iso = _iso_from_ms(seed_ts_ms)
    inserted = 0

    for symbol in sorted(symbols):
        entry_ms = entry_map.get(symbol) if symbol in entry_map else entry_map.get(symbol.lower())
        exit_ms = exit_map.get(symbol) if symbol in exit_map else exit_map.get(symbol.lower())
        entry_s = None
        exit_s = None
        try:
            if entry_ms is not None:
                entry_s = float(entry_ms) / 1000.0
        except Exception:
            entry_s = None
        try:
            if exit_ms is not None:
                exit_s = float(exit_ms) / 1000.0
        except Exception:
            exit_s = None

        _insert_projection(
            conn,
            "runtime_cooldowns",
            {
                "symbol": symbol,
                "last_entry_attempt_s": entry_s,
                "last_exit_attempt_s": exit_s,
                "updated_at": seed_iso,
            },
        )
        inserted += 1

    return inserted


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply a canonical snapshot JSON to a paper DB for deterministic state seeding."
    )
    parser.add_argument("--snapshot", required=True, help="Path to canonical snapshot JSON")
    parser.add_argument("--target-db", required=True, help="Target paper SQLite DB path")
    parser.add_argument(
        "--strict-replace",
        action="store_true",
        help=(
            "Replace current paper state strictly from snapshot "
            "(clears trades plus deterministic replay projection tables before seeding)."
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="Show plan without writing")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot).expanduser().resolve()
    target_db_path = Path(args.target_db).expanduser().resolve()

    if not snapshot_path.exists():
        parser.error(f"Snapshot file not found: {snapshot_path}")
    if not target_db_path.exists():
        parser.error(f"Target DB not found: {target_db_path}")

    snapshot = _load_snapshot(snapshot_path)
    balance = float(snapshot.get("balance") or 0.0)
    exported_at_ms = int(snapshot.get("exported_at_ms") or int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000))
    canonical = snapshot.get("canonical") or {}
    snapshot_as_of_ts = canonical.get("as_of_ts")
    seed_ts_ms = exported_at_ms
    try:
        if snapshot_as_of_ts is not None and int(snapshot_as_of_ts) > 0:
            seed_ts_ms = int(snapshot_as_of_ts)
    except Exception:
        seed_ts_ms = exported_at_ms
    positions = snapshot.get("positions") or []
    if not isinstance(positions, list):
        raise ValueError("snapshot.positions must be a list")

    open_orders = canonical.get("open_orders") or []
    if not isinstance(open_orders, list):
        open_orders = []
    seed_history = canonical.get("seed_history") or {}
    if not isinstance(seed_history, dict):
        seed_history = {}
    runtime = snapshot.get("runtime") or {}
    if not isinstance(runtime, dict):
        runtime = {}

    if args.dry_run:
        print("--- DRY RUN ---")
        print(f"snapshot: {snapshot_path}")
        print(f"target_db: {target_db_path}")
        print(f"balance: {balance:.8f}")
        print(f"positions: {len(positions)}")
        print(f"open_orders: {len(open_orders)}")
        dry_seed_history_counts = (seed_history.get("row_counts") or {}) if isinstance(seed_history, dict) else {}
        if isinstance(dry_seed_history_counts, dict):
            dry_seed_history_total = sum(
                int(v or 0) for v in dry_seed_history_counts.values() if isinstance(v, (int, float))
            )
        else:
            dry_seed_history_total = 0
        print(f"seed_history_rows: {int(dry_seed_history_total)}")
        print(
            "runtime_cooldown_symbols: "
            f"{len((runtime.get('entry_attempt_ms_by_symbol') or {})) + len((runtime.get('exit_attempt_ms_by_symbol') or {}))}"
        )
        print("--- END DRY RUN ---")
        return 0

    conn = sqlite3.connect(target_db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN")
        seeded_trades, seeded_positions = _seed_trades_and_positions(
            conn,
            balance=balance,
            seed_ts_ms=seed_ts_ms,
            positions=positions,
            strict_replace=bool(args.strict_replace),
        )
        seeded_history_rows = _seed_history_rows(
            conn,
            seed_history=seed_history,
            strict_replace=bool(args.strict_replace),
        )
        seeded_open_orders = _replace_open_orders(conn, open_orders)
        seeded_runtime_cooldowns = _seed_runtime_cooldowns(
            conn,
            runtime=runtime,
            seed_ts_ms=seed_ts_ms,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(json.dumps(
        {
            "ok": True,
            "snapshot": str(snapshot_path),
            "target_db": str(target_db_path),
            "seeded_trades": int(seeded_trades),
            "seeded_positions": int(seeded_positions),
            "seeded_history_rows": seeded_history_rows,
            "seeded_history_rows_total": int(sum(int(v or 0) for v in seeded_history_rows.values())),
            "seeded_open_orders": int(seeded_open_orders),
            "seeded_runtime_cooldowns": int(seeded_runtime_cooldowns),
            "seed_timestamp_ms": int(seed_ts_ms),
            "strict_replace": bool(args.strict_replace),
        },
        indent=2,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
