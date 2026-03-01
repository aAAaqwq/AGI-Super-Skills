#!/usr/bin/env python3
"""Audit alignment across live DB, paper DB, and optional canonical snapshot.

The report is intended for financial-grade state-sync tracing before replay/parity runs.
"""

from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_TOL = 1e-9


def _connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro"
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
    if not _table_exists(conn, table_name):
        return False
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    wanted = str(column_name or "").strip().lower()
    return any(str(row["name"] if isinstance(row, sqlite3.Row) else row[1]).strip().lower() == wanted for row in rows)


def _parse_timestamp_ms(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        iv = int(value)
        if iv > 10_000_000_000:
            return iv
        return max(0, iv * 1000)

    raw = str(value).strip()
    if not raw:
        return 0
    if raw.isdigit():
        iv = int(raw)
        if iv > 10_000_000_000:
            return iv
        return iv * 1000

    try:
        ts = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return int(ts.timestamp() * 1000)
    except Exception:
        return 0


def _sqlite_ts_ms_expr(column_name: str = "timestamp") -> str:
    # Use integer epoch arithmetic to avoid float rounding drift on boundary cut-offs.
    return (
        f"(CAST(strftime('%s', {column_name}) AS INTEGER) * 1000 + "
        f"CAST(substr(strftime('%f', {column_name}), 4, 3) AS INTEGER))"
    )


def _reconstruct_positions(
    conn: sqlite3.Connection,
    *,
    as_of_ts: int | None = None,
    use_position_state_as_of: bool = False,
) -> list[dict[str, Any]]:
    if not _table_exists(conn, "trades"):
        return []

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
    for row in conn.execute(sql_open, tuple(open_close_params)).fetchall():
        symbol = str(row["symbol"] or "").strip().upper()
        pos_type = str(row["pos_type"] or "").strip().upper()
        if not symbol or pos_type not in {"LONG", "SHORT"}:
            continue

        open_id = int(row["open_id"])
        avg_entry = float(row["open_px"] or 0.0)
        net_size = float(row["open_sz"] or 0.0)
        if avg_entry <= 0.0 or net_size <= 0.0:
            continue

        entry_atr = float(row["entry_atr"] or 0.0)
        leverage = float(row["leverage"] or 1.0)
        if leverage <= 0.0:
            leverage = 1.0
        margin_used = float(row["margin_used"] or (abs(net_size) * avg_entry / leverage))
        adds_count = 0
        tp1_taken = False
        last_add_time_ms = 0
        entry_adx_threshold = 0.0

        fills_q = (
            "SELECT action, price, size, entry_atr, timestamp FROM trades "
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
            if px <= 0.0 or sz <= 0.0:
                continue
            if action == "ADD":
                new_total = net_size + sz
                if new_total > 0.0:
                    avg_entry = ((avg_entry * net_size) + (px * sz)) / new_total
                    if fill_atr > 0 and entry_atr > 0:
                        entry_atr = ((entry_atr * net_size) + (fill_atr * sz)) / new_total
                    elif fill_atr > 0:
                        entry_atr = fill_atr
                    net_size = new_total
                    adds_count += 1
                    fill_ts = _parse_timestamp_ms(fill["timestamp"])
                    if fill_ts > 0:
                        last_add_time_ms = max(last_add_time_ms, int(fill_ts))
            elif action == "REDUCE":
                net_size -= sz
                if net_size <= 0.0:
                    net_size = 0.0
                    break

        if net_size <= 0.0:
            continue

        margin_used = abs(net_size) * avg_entry / leverage if leverage > 0 else 0.0
        trailing_sl = None

        should_use_position_state = _table_exists(conn, "position_state") and (
            as_of_ts is None or bool(use_position_state_as_of)
        )
        if should_use_position_state:
            has_updated_at = _table_has_column(conn, "position_state", "updated_at")
            select_cols = "open_trade_id, trailing_sl, adds_count, tp1_taken, last_add_time, entry_adx_threshold"
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
                        trailing_sl = float(ps_row["trailing_sl"]) if ps_row["trailing_sl"] is not None else None
                        adds_count = int(ps_row["adds_count"] or 0)
                        tp1_taken = bool(ps_row["tp1_taken"] or 0)
                        last_add_time_ms = int(ps_row["last_add_time"] or 0)
                        if as_of_ts is not None and last_add_time_ms > int(as_of_ts):
                            last_add_time_ms = 0
                        entry_adx_threshold = float(ps_row["entry_adx_threshold"] or 0.0)

                    if as_of_ts is not None and ps_row is None:
                        # Strict as-of mode: do not consume position_state without
                        # timestamp guarantees.
                        trailing_sl = None
                        tp1_taken = False
                        entry_adx_threshold = 0.0
                        if last_add_time_ms > int(as_of_ts):
                            last_add_time_ms = 0

                    if as_of_ts is not None and ps_row is not None:
                        # Keep scalar state coherent with as-of cutoff.
                        if last_add_time_ms > int(as_of_ts):
                            last_add_time_ms = 0
                else:
                    ps_row = None
                    if as_of_ts is not None:
                        # Ensure we do not leak unrelated position_state rows.
                        trailing_sl = None
                        tp1_taken = False
                        entry_adx_threshold = 0.0
                        if last_add_time_ms > int(as_of_ts):
                            last_add_time_ms = 0

        positions.append(
            {
                "symbol": symbol,
                "side": "long" if pos_type == "LONG" else "short",
                "size": round(net_size, 10),
                "entry_price": round(avg_entry, 10),
                "entry_atr": round(entry_atr, 10),
                "trailing_sl": round(trailing_sl, 10) if trailing_sl is not None else None,
                "confidence": str(row["confidence"] or "medium").strip().lower() or "medium",
                "leverage": float(leverage),
                "margin_used": round(margin_used, 10),
                "adds_count": int(adds_count),
                "tp1_taken": bool(tp1_taken),
                "open_time_ms": _parse_timestamp_ms(row["open_ts"]),
                "last_add_time_ms": int(last_add_time_ms),
                "entry_adx_threshold": float(entry_adx_threshold),
            }
        )

    positions.sort(key=lambda x: x["symbol"])
    return positions


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
        out.append({k: row[k] for k in row.keys()})
    return out


def _index_positions(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r.get("symbol") or "").upper(): r for r in rows if str(r.get("symbol") or "").strip()}


def _almost_equal(left: float, right: float, tol: float) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=tol)


def _compare_positions(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    *,
    left_name: str,
    right_name: str,
    tol: float,
) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    lidx = _index_positions(left)
    ridx = _index_positions(right)
    symbols = sorted(set(lidx.keys()) | set(ridx.keys()))

    numeric_fields = (
        "size",
        "entry_price",
        "entry_atr",
        "trailing_sl",
        "leverage",
        "margin_used",
        "entry_adx_threshold",
    )
    scalar_fields = (
        "side",
        "confidence",
        "adds_count",
        "tp1_taken",
        "open_time_ms",
        "last_add_time_ms",
    )

    for symbol in symbols:
        lrow = lidx.get(symbol)
        rrow = ridx.get(symbol)
        if lrow is None:
            diffs.append(
                {
                    "classification": "state_initialisation_gap",
                    "kind": "position_missing",
                    "symbol": symbol,
                    "left": left_name,
                    "right": right_name,
                    "detail": "missing_on_left",
                }
            )
            continue
        if rrow is None:
            diffs.append(
                {
                    "classification": "state_initialisation_gap",
                    "kind": "position_missing",
                    "symbol": symbol,
                    "left": left_name,
                    "right": right_name,
                    "detail": "missing_on_right",
                }
            )
            continue

        for field in scalar_fields:
            if lrow.get(field) != rrow.get(field):
                diffs.append(
                    {
                        "classification": "state_initialisation_gap",
                        "kind": "position_field_mismatch",
                        "symbol": symbol,
                        "field": field,
                        "left": lrow.get(field),
                        "right": rrow.get(field),
                        "left_source": left_name,
                        "right_source": right_name,
                    }
                )

        for field in numeric_fields:
            lv = lrow.get(field)
            rv = rrow.get(field)
            if lv is None and rv is None:
                continue
            if lv is None or rv is None:
                diffs.append(
                    {
                        "classification": "state_initialisation_gap",
                        "kind": "position_field_mismatch",
                        "symbol": symbol,
                        "field": field,
                        "left": lv,
                        "right": rv,
                        "left_source": left_name,
                        "right_source": right_name,
                    }
                )
                continue
            if not _almost_equal(float(lv), float(rv), tol):
                diffs.append(
                    {
                        "classification": "numeric_policy_divergence",
                        "kind": "position_numeric_mismatch",
                        "symbol": symbol,
                        "field": field,
                        "left": float(lv),
                        "right": float(rv),
                        "left_source": left_name,
                        "right_source": right_name,
                        "abs_delta": abs(float(lv) - float(rv)),
                    }
                )

    return diffs


def _normalise_open_order(row: dict[str, Any]) -> tuple[str, str, float, float, str]:
    symbol = str(row.get("symbol") or row.get("coin") or "").strip().upper()
    if not symbol:
        symbol = "UNKNOWN"

    side_raw = row.get("side")
    if side_raw is None:
        side_raw = row.get("order_side")
    if side_raw is None and row.get("is_buy") is not None:
        side_raw = "buy" if bool(row.get("is_buy")) else "sell"
    side = str(side_raw or "").strip().lower()
    if side not in {"buy", "sell", "long", "short"}:
        side = "unknown"

    size_val = row.get("size")
    if size_val is None:
        size_val = row.get("sz")
    if size_val is None:
        size_val = row.get("remaining")
    try:
        size = round(float(size_val or 0.0), 10)
    except Exception:
        size = 0.0

    price_val = row.get("price")
    if price_val is None:
        price_val = row.get("limit_px")
    try:
        price = round(float(price_val or 0.0), 10)
    except Exception:
        price = 0.0

    oid = row.get("oid")
    if oid is None:
        oid = row.get("order_id")
    if oid is None:
        oid = row.get("cloid")
    oid_str = str(oid or "")

    return symbol, side, size, price, oid_str


def _compare_open_orders(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    *,
    left_name: str,
    right_name: str,
) -> list[dict[str, Any]]:
    l_counter = Counter(_normalise_open_order(r) for r in left if isinstance(r, dict))
    r_counter = Counter(_normalise_open_order(r) for r in right if isinstance(r, dict))

    diffs: list[dict[str, Any]] = []
    for sig in set(l_counter.keys()) | set(r_counter.keys()):
        l_count = int(l_counter.get(sig, 0))
        r_count = int(r_counter.get(sig, 0))
        if l_count == r_count:
            continue
        symbol, side, size, price, oid = sig
        diffs.append(
            {
                "classification": "state_initialisation_gap",
                "kind": "open_order_mismatch",
                "left_source": left_name,
                "right_source": right_name,
                "symbol": symbol,
                "side": side,
                "size": size,
                "price": price,
                "oid": oid,
                "left_count": l_count,
                "right_count": r_count,
            }
        )

    return diffs


def _load_balance(conn: sqlite3.Connection, *, as_of_ts: int | None = None) -> float:
    if not _table_exists(conn, "trades"):
        return 0.0
    balance_q = "SELECT balance FROM trades"
    balance_params: list[Any] = []
    if as_of_ts is not None:
        balance_q += f" WHERE {_sqlite_ts_ms_expr('timestamp')} <= ?"
        balance_params.append(int(as_of_ts))
    balance_q += " ORDER BY id DESC LIMIT 1"
    row = conn.execute(balance_q, tuple(balance_params)).fetchone()
    return float(row["balance"] or 0.0) if row else 0.0


def _build_state(
    db_path: Path,
    *,
    as_of_ts: int | None = None,
    use_position_state_as_of: bool = False,
) -> dict[str, Any]:
    conn = _connect_ro(db_path)
    try:
        return {
            "db_path": str(db_path),
            "as_of_ts": as_of_ts,
            "balance": _load_balance(conn, as_of_ts=as_of_ts),
            "positions": _reconstruct_positions(
                conn,
                as_of_ts=as_of_ts,
                use_position_state_as_of=use_position_state_as_of,
            ),
            "open_orders": _load_open_orders(conn, as_of_ts=as_of_ts),
        }
    finally:
        conn.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit live/paper/snapshot state alignment.")
    parser.add_argument("--live-db", required=True, help="Path to live SQLite DB")
    parser.add_argument("--paper-db", required=True, help="Path to paper SQLite DB")
    parser.add_argument("--snapshot", help="Optional canonical snapshot JSON path")
    parser.add_argument("--as-of-ts", type=int, default=None, help="Optional state cutoff timestamp (ms, inclusive)")
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOL, help="Absolute numeric tolerance")
    parser.add_argument("--output", help="Optional output JSON path")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    live_db = Path(args.live_db).expanduser().resolve()
    paper_db = Path(args.paper_db).expanduser().resolve()
    if not live_db.exists():
        parser.error(f"live DB not found: {live_db}")
    if not paper_db.exists():
        parser.error(f"paper DB not found: {paper_db}")

    snapshot_state: dict[str, Any] | None = None
    snapshot_as_of_ts: int | None = None
    if args.snapshot:
        snapshot_path = Path(args.snapshot).expanduser().resolve()
        if not snapshot_path.exists():
            parser.error(f"snapshot not found: {snapshot_path}")
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        raw_snapshot_as_of = (payload.get("canonical") or {}).get("as_of_ts")
        if raw_snapshot_as_of is not None:
            try:
                snapshot_as_of_ts = int(raw_snapshot_as_of)
            except Exception:
                snapshot_as_of_ts = None
        snapshot_state = {
            "snapshot_path": str(snapshot_path),
            "balance": float(payload.get("balance") or 0.0),
            "positions": payload.get("positions") or [],
            "open_orders": (payload.get("canonical") or {}).get("open_orders") or [],
        }

    effective_as_of_ts: int | None = int(args.as_of_ts) if args.as_of_ts is not None else snapshot_as_of_ts
    if effective_as_of_ts is not None and effective_as_of_ts <= 0:
        parser.error("--as-of-ts must be a positive epoch millisecond value")

    live_state = _build_state(
        live_db,
        as_of_ts=effective_as_of_ts,
        use_position_state_as_of=False,
    )
    paper_state = _build_state(
        paper_db,
        as_of_ts=effective_as_of_ts,
        use_position_state_as_of=True,
    )

    diffs: list[dict[str, Any]] = []

    if not _almost_equal(live_state["balance"], paper_state["balance"], args.tolerance):
        diffs.append(
            {
                "classification": "numeric_policy_divergence",
                "kind": "balance_mismatch",
                "left_source": "live_db",
                "right_source": "paper_db",
                "left": float(live_state["balance"]),
                "right": float(paper_state["balance"]),
                "abs_delta": abs(float(live_state["balance"]) - float(paper_state["balance"])),
            }
        )

    diffs.extend(
        _compare_positions(
            live_state["positions"],
            paper_state["positions"],
            left_name="live_db",
            right_name="paper_db",
            tol=float(args.tolerance),
        )
    )
    diffs.extend(
        _compare_open_orders(
            live_state["open_orders"],
            paper_state["open_orders"],
            left_name="live_db",
            right_name="paper_db",
        )
    )

    if snapshot_state is not None:
        if not _almost_equal(live_state["balance"], snapshot_state["balance"], args.tolerance):
            diffs.append(
                {
                    "classification": "state_initialisation_gap",
                    "kind": "snapshot_balance_mismatch",
                    "left_source": "live_db",
                    "right_source": "snapshot",
                    "left": float(live_state["balance"]),
                    "right": float(snapshot_state["balance"]),
                    "abs_delta": abs(float(live_state["balance"]) - float(snapshot_state["balance"])),
                }
            )

        diffs.extend(
            _compare_positions(
                live_state["positions"],
                snapshot_state["positions"],
                left_name="live_db",
                right_name="snapshot",
                tol=float(args.tolerance),
            )
        )
        diffs.extend(
            _compare_open_orders(
                live_state["open_orders"],
                snapshot_state["open_orders"],
                left_name="live_db",
                right_name="snapshot",
            )
        )

    report = {
        "ok": len(diffs) == 0,
        "generated_at_ms": int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000),
        "tolerance": float(args.tolerance),
        "as_of_ts": effective_as_of_ts,
        "summary": {
            "live_balance": float(live_state["balance"]),
            "paper_balance": float(paper_state["balance"]),
            "live_positions": len(live_state["positions"]),
            "paper_positions": len(paper_state["positions"]),
            "live_open_orders": len(live_state["open_orders"]),
            "paper_open_orders": len(paper_state["open_orders"]),
            "diff_count": len(diffs),
        },
        "diffs": diffs,
    }

    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        out_path = Path(args.output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")
        print(out_path.as_posix())
    else:
        print(payload)

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
