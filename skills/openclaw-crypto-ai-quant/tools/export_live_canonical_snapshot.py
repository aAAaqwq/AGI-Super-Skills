#!/usr/bin/env python3
"""Export a live-canonical snapshot for paper/backtester state sync.

This tool produces a JSON payload that is directly usable as backtester
`--init-state` input (v2 schema) while carrying extra canonical metadata.

Examples:
    python tools/export_live_canonical_snapshot.py --source live --output /tmp/live_init_state.json
    python tools/export_live_canonical_snapshot.py --source paper --output /tmp/paper_init_state.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_LIVE_DB = PROJECT_DIR / "trading_engine_live.db"
DEFAULT_PAPER_DB = PROJECT_DIR / "trading_engine.db"

ENTRY_ATTEMPT_ACTIONS = ("OPEN", "ADD")
EXIT_ATTEMPT_ACTIONS = ("CLOSE", "REDUCE")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(value: str) -> str:
    ident = str(value or "").strip()
    if not _IDENTIFIER_RE.fullmatch(ident):
        raise ValueError(f"Invalid SQL identifier: {value!r}")
    return ident


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def _table_has_column(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    try:
        rows = conn.execute(f"PRAGMA table_info({_validate_identifier(table_name)})").fetchall()
    except Exception:
        return False
    wanted = str(column_name or "").strip().lower()
    if not wanted:
        return False
    for row in rows:
        try:
            if str(row[1]).strip().lower() == wanted:
                return True
        except Exception:
            continue
    return False


def _parse_timestamp_ms(value: Any) -> int:
    if value is None:
        return 0

    if isinstance(value, (int, float)):
        iv = int(value)
        if iv > 10_000_000_000:
            return iv
        if iv > 0:
            return iv * 1000
        return 0

    raw = str(value).strip()
    if not raw:
        return 0

    if raw.isdigit():
        iv = int(raw)
        if iv > 10_000_000_000:
            return iv
        return iv * 1000

    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return int(parsed.timestamp() * 1000)
    except Exception:
        return 0


def _as_json_value(value: Any) -> Any:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _load_position_state_history_as_of(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    open_trade_id: int,
    as_of_ts: int,
) -> sqlite3.Row | None:
    if as_of_ts <= 0:
        return None
    if not _table_exists(conn, "position_state_history"):
        return None
    has_event_ts = _table_has_column(conn, "position_state_history", "event_ts_ms")
    has_updated_at = _table_has_column(conn, "position_state_history", "updated_at")
    if not has_event_ts and not has_updated_at:
        return None

    symbol_norm = str(symbol).strip().upper()
    order_col = "event_ts_ms" if has_event_ts else "updated_at"
    cutoff_expr = "event_ts_ms <= ?" if has_event_ts else "CAST(strftime('%s', updated_at) AS INTEGER) * 1000 <= ?"

    # Query exact open_trade_id first to keep index usage predictable.
    for include_null_open_trade_id in (False, True):
        where_parts = ["symbol = ?"]
        params: list[Any] = [symbol_norm]
        if include_null_open_trade_id:
            where_parts.append("open_trade_id IS NULL")
        else:
            where_parts.append("open_trade_id = ?")
            params.append(int(open_trade_id))
        where_parts.append(cutoff_expr)
        params.append(int(as_of_ts))

        q = (
            "SELECT open_trade_id, trailing_sl, adds_count, tp1_taken, last_add_time, "
            "entry_adx_threshold, updated_at "
            "FROM position_state_history "
            f"WHERE {' AND '.join(where_parts)} "
            f"ORDER BY {order_col} DESC, id DESC LIMIT 1"
        )
        row = conn.execute(q, tuple(params)).fetchone()
        if row is not None:
            return row
    return None


def _max_id(conn: sqlite3.Connection, table_name: str) -> int | None:
    safe_table = _validate_identifier(table_name)
    if not _table_exists(conn, safe_table):
        return None
    try:
        row = conn.execute(f"SELECT MAX(id) AS max_id FROM {safe_table}").fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    value = row["max_id"]
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _rows_to_json(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append({k: _as_json_value(row[k]) for k in row.keys()})
    return out


def _load_seed_history_rows(
    conn: sqlite3.Connection,
    *,
    window_from_ts: int,
    window_to_ts: int,
) -> dict[str, list[dict[str, Any]]]:
    rows_by_table: dict[str, list[dict[str, Any]]] = {}

    decision_rows: list[dict[str, Any]] = []
    decision_ids: list[str] = []
    if _table_exists(conn, "decision_events"):
        rows = conn.execute(
            """
            SELECT * FROM decision_events
            WHERE timestamp_ms >= ? AND timestamp_ms <= ?
            ORDER BY timestamp_ms ASC, id ASC
            """,
            (int(window_from_ts), int(window_to_ts)),
        ).fetchall()
        decision_rows = _rows_to_json(rows)
        if decision_rows:
            rows_by_table["decision_events"] = decision_rows
            decision_ids = [str(r.get("id") or "").strip() for r in decision_rows if str(r.get("id") or "").strip()]

    if decision_ids and _table_exists(conn, "decision_context"):
        acc: list[dict[str, Any]] = []
        chunk_size = 400
        for start in range(0, len(decision_ids), chunk_size):
            chunk = decision_ids[start : start + chunk_size]
            q = "SELECT * FROM decision_context WHERE decision_id IN ({}) ORDER BY decision_id ASC".format(
                ",".join("?" for _ in chunk)
            )
            acc.extend(_rows_to_json(conn.execute(q, tuple(chunk)).fetchall()))
        if acc:
            rows_by_table["decision_context"] = acc

    if decision_ids and _table_exists(conn, "gate_evaluations"):
        acc = []
        chunk_size = 400
        for start in range(0, len(decision_ids), chunk_size):
            chunk = decision_ids[start : start + chunk_size]
            q = "SELECT * FROM gate_evaluations WHERE decision_id IN ({}) ORDER BY id ASC".format(
                ",".join("?" for _ in chunk)
            )
            acc.extend(_rows_to_json(conn.execute(q, tuple(chunk)).fetchall()))
        if acc:
            rows_by_table["gate_evaluations"] = acc

    if _table_exists(conn, "signals"):
        ts_expr = _sqlite_ts_ms_expr("timestamp")
        rows = conn.execute(
            f"SELECT * FROM signals WHERE {ts_expr} >= ? AND {ts_expr} <= ? ORDER BY id ASC",
            (int(window_from_ts), int(window_to_ts)),
        ).fetchall()
        payload = _rows_to_json(rows)
        if payload:
            rows_by_table["signals"] = payload

    if _table_exists(conn, "audit_events"):
        ts_expr = _sqlite_ts_ms_expr("timestamp")
        rows = conn.execute(
            f"SELECT * FROM audit_events WHERE {ts_expr} >= ? AND {ts_expr} <= ? ORDER BY id ASC",
            (int(window_from_ts), int(window_to_ts)),
        ).fetchall()
        payload = _rows_to_json(rows)
        if payload:
            rows_by_table["audit_events"] = payload

    if _table_exists(conn, "oms_intents"):
        rows = conn.execute(
            """
            SELECT * FROM oms_intents
            WHERE created_ts_ms >= ? AND created_ts_ms <= ?
            ORDER BY created_ts_ms ASC, intent_id ASC
            """,
            (int(window_from_ts), int(window_to_ts)),
        ).fetchall()
        payload = _rows_to_json(rows)
        if payload:
            rows_by_table["oms_intents"] = payload

    if _table_exists(conn, "oms_orders"):
        rows = conn.execute(
            """
            SELECT * FROM oms_orders
            WHERE created_ts_ms >= ? AND created_ts_ms <= ?
            ORDER BY created_ts_ms ASC, id ASC
            """,
            (int(window_from_ts), int(window_to_ts)),
        ).fetchall()
        payload = _rows_to_json(rows)
        if payload:
            rows_by_table["oms_orders"] = payload

    if _table_exists(conn, "oms_fills"):
        rows = conn.execute(
            """
            SELECT * FROM oms_fills
            WHERE ts_ms >= ? AND ts_ms <= ?
            ORDER BY ts_ms ASC, id ASC
            """,
            (int(window_from_ts), int(window_to_ts)),
        ).fetchall()
        payload = _rows_to_json(rows)
        if payload:
            rows_by_table["oms_fills"] = payload

    if _table_exists(conn, "ws_events"):
        rows = conn.execute(
            """
            SELECT * FROM ws_events
            WHERE ts >= ? AND ts <= ?
            ORDER BY ts ASC, id ASC
            """,
            (int(window_from_ts), int(window_to_ts)),
        ).fetchall()
        payload = _rows_to_json(rows)
        if payload:
            rows_by_table["ws_events"] = payload

    return rows_by_table


def _sqlite_ts_ms_expr(column_name: str = "timestamp") -> str:
    # Use integer epoch arithmetic to avoid float rounding drift on boundary cut-offs.
    return (
        f"(CAST(strftime('%s', {column_name}) AS INTEGER) * 1000 + "
        f"CAST(substr(strftime('%f', {column_name}), 4, 3) AS INTEGER))"
    )


def _reconstruct_positions_and_balance(
    conn: sqlite3.Connection,
    *,
    as_of_ts: int | None = None,
) -> tuple[float, list[dict[str, Any]], dict[str, int], dict[str, str]]:
    balance_q = "SELECT balance FROM trades"
    balance_params: list[Any] = []
    if as_of_ts is not None:
        balance_q += f" WHERE {_sqlite_ts_ms_expr('timestamp')} <= ?"
        balance_params.append(int(as_of_ts))
    balance_q += " ORDER BY id DESC LIMIT 1"
    row = conn.execute(balance_q, tuple(balance_params)).fetchone()
    balance = float(row["balance"] or 0.0) if row else 0.0

    open_where = "action = 'OPEN'"
    close_where = "action = 'CLOSE'"
    open_close_params: list[Any] = []
    if as_of_ts is not None:
        cutoff_expr = _sqlite_ts_ms_expr("timestamp")
        open_where += f" AND {cutoff_expr} <= ?"
        close_where += f" AND {cutoff_expr} <= ?"
        open_close_params.extend([int(as_of_ts), int(as_of_ts)])

    sql_open = """
    SELECT t.id AS open_id, t.timestamp AS open_ts, t.symbol, t.type AS pos_type,
           t.price AS open_px, t.size AS open_sz, t.confidence,
           t.entry_atr, t.leverage, t.margin_used
    FROM trades t
    INNER JOIN (
        SELECT symbol, MAX(id) AS open_id
        FROM trades WHERE {open_where} GROUP BY symbol
    ) lo ON t.id = lo.open_id
    LEFT JOIN (
        SELECT symbol, MAX(id) AS close_id
        FROM trades WHERE {close_where} GROUP BY symbol
    ) lc ON t.symbol = lc.symbol
    WHERE lc.close_id IS NULL OR t.id > lc.close_id
    """.format(open_where=open_where, close_where=close_where)

    positions: list[dict[str, Any]] = []
    state_source_counts: dict[str, int] = {
        "trades_only": 0,
        "position_state": 0,
        "position_state_history": 0,
    }
    state_source_by_symbol: dict[str, str] = {}
    for row in conn.execute(sql_open, tuple(open_close_params)).fetchall():
        symbol = str(row["symbol"] or "").strip().upper()
        if not symbol:
            continue

        pos_type = str(row["pos_type"] or "").strip().upper()
        if pos_type not in {"LONG", "SHORT"}:
            continue

        open_id = int(row["open_id"])
        avg_entry = float(row["open_px"] or 0.0)
        net_size = float(row["open_sz"] or 0.0)
        if avg_entry <= 0.0 or net_size <= 0.0:
            continue

        entry_atr = float(row["entry_atr"] or 0.0)
        confidence = str((row["confidence"] or "medium")).strip().lower() or "medium"
        leverage = float(row["leverage"] or 1.0)
        if leverage <= 0.0:
            leverage = 1.0

        margin_used = float(row["margin_used"] or 0.0)
        if margin_used <= 0.0:
            margin_used = abs(net_size) * avg_entry / leverage

        trailing_sl = None
        adds_count = 0
        tp1_taken = False
        last_add_time_ms = 0
        entry_adx_threshold = 0.0
        state_source = "trades_only"

        fills_q = (
            "SELECT action, price, size, entry_atr, timestamp, reason FROM trades "
            "WHERE symbol = ? AND id > ? AND action IN ('ADD', 'REDUCE')"
        )
        fills_params: list[Any] = [symbol, open_id]
        if as_of_ts is not None:
            fills_q += f" AND {_sqlite_ts_ms_expr('timestamp')} <= ?"
            fills_params.append(int(as_of_ts))
        fills_q += " ORDER BY id ASC"
        fills = conn.execute(fills_q, tuple(fills_params)).fetchall()

        for fill in fills:
            action = str(fill["action"] or "").strip().upper()
            px = float(fill["price"] or 0.0)
            sz = float(fill["size"] or 0.0)
            fill_atr = float(fill["entry_atr"] or 0.0)
            fill_ts_ms = _parse_timestamp_ms(fill["timestamp"])
            reason_text = str(fill["reason"] or "").strip().lower()
            if px <= 0.0 or sz <= 0.0:
                continue

            if action == "ADD":
                adds_count += 1
                if fill_ts_ms > 0:
                    last_add_time_ms = max(last_add_time_ms, int(fill_ts_ms))
                new_total = net_size + sz
                if new_total > 0:
                    avg_entry = ((avg_entry * net_size) + (px * sz)) / new_total
                    if fill_atr > 0 and entry_atr > 0:
                        entry_atr = ((entry_atr * net_size) + (fill_atr * sz)) / new_total
                    elif fill_atr > 0:
                        entry_atr = fill_atr
                    net_size = new_total
            elif action == "REDUCE":
                if "take profit (partial)" in reason_text:
                    tp1_taken = True
                net_size -= sz
                if net_size <= 0:
                    net_size = 0.0
                    break

        if net_size <= 0.0:
            continue

        reconstructed_margin = abs(net_size) * avg_entry / leverage if leverage > 0.0 else 0.0
        if reconstructed_margin > 0.0:
            margin_used = reconstructed_margin

        if _table_exists(conn, "position_state"):
            has_updated_at = _table_has_column(conn, "position_state", "updated_at")
            select_cols = (
                "open_trade_id, trailing_sl, adds_count, tp1_taken, last_add_time, "
                "entry_adx_threshold"
            )
            if has_updated_at:
                select_cols += ", updated_at"
            ps_row = conn.execute(
                f"SELECT {select_cols} FROM position_state WHERE symbol = ? LIMIT 1",
                (symbol,),
            ).fetchone()
            if ps_row:
                open_trade_id = ps_row["open_trade_id"]
                if open_trade_id is None or int(open_trade_id) == open_id:
                    if as_of_ts is not None:
                        if not has_updated_at:
                            ps_row = None
                        else:
                            updated_at_ms = _parse_timestamp_ms(ps_row["updated_at"])
                            if updated_at_ms <= 0 or updated_at_ms > int(as_of_ts):
                                ps_row = None

                    if ps_row is not None:
                        trailing_sl = (
                            float(ps_row["trailing_sl"]) if ps_row["trailing_sl"] is not None else None
                        )
                        adds_count = int(ps_row["adds_count"] or 0)
                        tp1_taken = bool(ps_row["tp1_taken"] or 0)
                        last_add_time_ms = int(ps_row["last_add_time"] or 0)
                        if as_of_ts is not None and last_add_time_ms > int(as_of_ts):
                            last_add_time_ms = 0
                        entry_adx_threshold = float(ps_row["entry_adx_threshold"] or 0.0)
                        state_source = "position_state"
                    elif as_of_ts is not None:
                        # Strict as-of mode: avoid consuming position_state without
                        # timestamp guarantees.
                        trailing_sl = None
                        tp1_taken = False
                        entry_adx_threshold = 0.0
                        if last_add_time_ms > int(as_of_ts):
                            last_add_time_ms = 0

                    if ps_row is None and as_of_ts is not None:
                        hist_row = _load_position_state_history_as_of(
                            conn,
                            symbol=symbol,
                            open_trade_id=open_id,
                            as_of_ts=int(as_of_ts),
                        )
                        if hist_row is not None:
                            trailing_sl = (
                                float(hist_row["trailing_sl"])
                                if hist_row["trailing_sl"] is not None
                                else None
                            )
                            adds_count = int(hist_row["adds_count"] or 0)
                            tp1_taken = bool(hist_row["tp1_taken"] or 0)
                            last_add_time_ms = int(hist_row["last_add_time"] or 0)
                            if last_add_time_ms > int(as_of_ts):
                                last_add_time_ms = 0
                            entry_adx_threshold = float(hist_row["entry_adx_threshold"] or 0.0)
                            state_source = "position_state_history"

        side = "long" if pos_type == "LONG" else "short"
        state_source_counts[state_source] = int(state_source_counts.get(state_source, 0)) + 1
        state_source_by_symbol[symbol] = state_source
        positions.append(
            {
                "symbol": symbol,
                "side": side,
                "size": round(net_size, 10),
                "entry_price": round(avg_entry, 10),
                "entry_atr": round(entry_atr, 10),
                "trailing_sl": round(trailing_sl, 10) if trailing_sl is not None else None,
                "confidence": confidence,
                "leverage": float(leverage),
                "margin_used": round(margin_used, 10),
                "adds_count": int(adds_count),
                "tp1_taken": bool(tp1_taken),
                "open_time_ms": _parse_timestamp_ms(row["open_ts"]),
                "last_add_time_ms": int(last_add_time_ms),
                "entry_adx_threshold": float(entry_adx_threshold),
            }
        )

    positions.sort(key=lambda p: str(p.get("symbol") or ""))
    return balance, positions, state_source_counts, state_source_by_symbol


def _load_attempt_markers(
    conn: sqlite3.Connection,
    *,
    as_of_ts: int | None = None,
) -> tuple[dict[str, int], dict[str, int]]:
    entry_attempt_ms: dict[str, int] = {}
    exit_attempt_ms: dict[str, int] = {}

    if not _table_exists(conn, "trades"):
        return entry_attempt_ms, exit_attempt_ms

    entry_where = "action IN ({})".format(",".join("?" for _ in ENTRY_ATTEMPT_ACTIONS))
    entry_params: list[Any] = list(ENTRY_ATTEMPT_ACTIONS)
    if as_of_ts is not None:
        entry_where += f" AND {_sqlite_ts_ms_expr('timestamp')} <= ?"
        entry_params.append(int(as_of_ts))
    entry_q = f"SELECT symbol, MAX(timestamp) AS ts FROM trades WHERE {entry_where} GROUP BY symbol"
    for row in conn.execute(entry_q, tuple(entry_params)).fetchall():
        symbol = str(row["symbol"] or "").strip().upper()
        if not symbol:
            continue
        ts_ms = _parse_timestamp_ms(row["ts"])
        if ts_ms > 0:
            entry_attempt_ms[symbol] = ts_ms

    exit_where = "action IN ({})".format(",".join("?" for _ in EXIT_ATTEMPT_ACTIONS))
    exit_params: list[Any] = list(EXIT_ATTEMPT_ACTIONS)
    if as_of_ts is not None:
        exit_where += f" AND {_sqlite_ts_ms_expr('timestamp')} <= ?"
        exit_params.append(int(as_of_ts))
    exit_q = f"SELECT symbol, MAX(timestamp) AS ts FROM trades WHERE {exit_where} GROUP BY symbol"
    for row in conn.execute(exit_q, tuple(exit_params)).fetchall():
        symbol = str(row["symbol"] or "").strip().upper()
        if not symbol:
            continue
        ts_ms = _parse_timestamp_ms(row["ts"])
        if ts_ms > 0:
            exit_attempt_ms[symbol] = ts_ms

    return entry_attempt_ms, exit_attempt_ms


def _load_open_orders(
    conn: sqlite3.Connection,
    *,
    as_of_ts: int | None = None,
) -> list[dict[str, Any]]:
    if not _table_exists(conn, "oms_open_orders"):
        return []

    if as_of_ts is not None:
        rows = conn.execute(
            "SELECT * FROM oms_open_orders "
            "WHERE (first_seen_ts_ms IS NULL OR first_seen_ts_ms <= ?) "
            "AND (last_seen_ts_ms IS NULL OR last_seen_ts_ms >= ?) "
            "ORDER BY symbol ASC",
            (int(as_of_ts), int(as_of_ts)),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM oms_open_orders ORDER BY symbol ASC").fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append({k: _as_json_value(row[k]) for k in row.keys()})
    return out


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export a live-canonical snapshot for paper/backtester sync. "
            "The output can be passed directly to mei-backtester --init-state."
        )
    )
    parser.add_argument(
        "--source",
        choices=("live", "paper"),
        default="live",
        help="Source mode used to select default DB path.",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Optional explicit SQLite DB path. Overrides --source default.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON file path.",
    )
    parser.add_argument(
        "--as-of-ts",
        type=int,
        default=None,
        help="Optional snapshot cutoff timestamp in milliseconds (inclusive).",
    )
    parser.add_argument(
        "--seed-history-lookback-minutes",
        type=int,
        default=360,
        help=(
            "Lookback window (minutes) for exporting seed_history rows "
            "for decision/audit/OMS replay context."
        ),
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.db_path:
        db_path = Path(args.db_path).expanduser().resolve()
    else:
        db_path = (DEFAULT_LIVE_DB if args.source == "live" else DEFAULT_PAPER_DB).resolve()

    if not db_path.exists():
        parser.error(f"DB path not found: {db_path}")

    now_ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    warnings: list[str] = []
    as_of_ts = int(args.as_of_ts) if args.as_of_ts is not None else None
    if as_of_ts is not None and as_of_ts <= 0:
        parser.error("--as-of-ts must be a positive epoch millisecond value")

    conn = _connect_ro(db_path)
    try:
        (
            balance,
            positions,
            state_source_counts,
            state_source_by_symbol,
        ) = _reconstruct_positions_and_balance(conn, as_of_ts=as_of_ts)
        entry_attempt_ms, exit_attempt_ms = _load_attempt_markers(conn, as_of_ts=as_of_ts)
        open_orders = _load_open_orders(conn, as_of_ts=args.as_of_ts)
        lookback_minutes = max(0, int(args.seed_history_lookback_minutes))
        seed_history_window_to = int(as_of_ts) if as_of_ts is not None else int(now_ms)
        seed_history_window_from = max(0, int(seed_history_window_to - lookback_minutes * 60_000))
        seed_history_rows = _load_seed_history_rows(
            conn,
            window_from_ts=int(seed_history_window_from),
            window_to_ts=int(seed_history_window_to),
        )
        seed_history_counts = {table: len(rows) for table, rows in seed_history_rows.items()}

        cursors = {
            "trades_max_id": _max_id(conn, "trades"),
            "decision_events_max_id": _max_id(conn, "decision_events"),
            "ws_events_max_id": _max_id(conn, "ws_events"),
            "oms_intents_max_id": _max_id(conn, "oms_intents"),
            "oms_orders_max_id": _max_id(conn, "oms_orders"),
            "oms_fills_max_id": _max_id(conn, "oms_fills"),
        }

        if balance <= 0.0:
            warnings.append("balance_non_positive")
        if as_of_ts is not None and int(state_source_counts.get("trades_only", 0)) > 0:
            warnings.append(
                f"position_state_as_of_fallback_trades_only:{int(state_source_counts.get('trades_only', 0))}"
            )

        snapshot = {
            "version": 2,
            "source": f"{args.source}_db",
            "exported_at_ms": now_ms,
            "balance": float(balance),
            "positions": positions,
            "runtime": {
                "entry_attempt_ms_by_symbol": entry_attempt_ms,
                "exit_attempt_ms_by_symbol": exit_attempt_ms,
            },
            "canonical": {
                "db_path": str(db_path),
                "as_of_ts": as_of_ts,
                "position_state_provenance": {
                    "counts": state_source_counts,
                    "by_symbol": state_source_by_symbol,
                },
                "open_orders": open_orders,
                "cursors": cursors,
                "seed_history": {
                    "window_from_ts": int(seed_history_window_from),
                    "window_to_ts": int(seed_history_window_to),
                    "lookback_minutes": int(lookback_minutes),
                    "row_counts": seed_history_counts,
                    "rows": seed_history_rows,
                },
                "warnings": warnings,
                "notes": [
                    "This snapshot is live-canonical for deterministic replay seeding.",
                    "Non-simulatable exchange effects must be tracked separately in audit reports.",
                ],
            },
        }
    finally:
        conn.close()

    out_path = Path(args.output).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
