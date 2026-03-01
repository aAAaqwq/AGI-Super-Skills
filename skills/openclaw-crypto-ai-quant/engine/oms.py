from __future__ import annotations

import datetime
import json
import logging
import math
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

from .utils import json_dumps_safe, now_ms

logger = logging.getLogger(__name__)

_EPOCH_MS_MIN_ABS = 100_000_000_000  # ~= 1973-03 in milliseconds


def _current_run_fingerprint() -> str:
    raw = str(os.getenv("AI_QUANT_RUN_FINGERPRINT", "") or "").strip()
    if raw:
        return raw
    try:
        import strategy.mei_alpha_v1 as mei_alpha_v1

        return str(mei_alpha_v1.get_run_fingerprint() or "unknown")
    except Exception:
        return "unknown"


def _canonical_reason_code(action: str, pos_type: str | None, reason: str | None) -> str:
    action_code = str(action or "").strip().upper()
    side = str(pos_type or "").strip().upper()
    if action_code in {"OPEN", "ADD", "CLOSE", "REDUCE"} and side in {"LONG", "SHORT"}:
        action_code = f"{action_code}_{side}"
    elif action_code == "FUNDING":
        action_code = "FUNDING"
    if not action_code:
        return "unknown"
    try:
        from tools.reason_codes import classify_reason_code

        code = str(classify_reason_code(action_code, str(reason or "")) or "").strip().lower()
    except Exception:
        code = ""
    return code or "unknown"


def _coerce_ts_ms(ts: Any) -> int | None:
    """Best-effort convert an arbitrary timestamp-like value to epoch milliseconds."""
    if ts is None:
        return None

    # Fast path: epoch seconds/ms.
    if isinstance(ts, (int, float)):
        try:
            v = float(ts)
        except Exception:
            return None
        if not math.isfinite(v):
            return None
        # Heuristic:
        # - >= 1e11 absolute is interpreted as epoch milliseconds (covers pre-2001 ms values).
        # - otherwise interpreted as epoch seconds.
        if abs(v) >= _EPOCH_MS_MIN_ABS:
            return int(v)
        return int(v * 1000.0)

    # pandas.Timestamp
    try:
        import pandas as pd

        if isinstance(ts, pd.Timestamp):
            # .value is ns
            return int(ts.value // 1_000_000)
    except Exception:
        pass

    # datetime
    if isinstance(ts, datetime.datetime):
        try:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            return int(ts.timestamp() * 1000.0)
        except Exception:
            return None

    # ISO string
    if isinstance(ts, str):
        s = ts.strip()
        if not s:
            return None
        try:
            # Python's fromisoformat does not accept Z.
            if s.endswith("Z"):
                s2 = s[:-1] + "+00:00"
            else:
                s2 = s
            dt = datetime.datetime.fromisoformat(s2)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return int(dt.timestamp() * 1000.0)
        except Exception:
            return None

    # pandas index timestamps sometimes come as numpy datetime64
    try:
        import numpy as np

        if isinstance(ts, np.datetime64):
            return int(ts.astype("datetime64[ms]").astype(int))
    except Exception:
        pass

    return None


def _safe_float(x: Any, default: float | None) -> float | None:
    try:
        if x is None:
            return default
        v = float(x)
        return v
    except Exception:
        return default


def _safe_int(x: Any, default: int | None) -> int | None:
    try:
        if x is None:
            return default
        return int(x)
    except Exception:
        return default


def _dir_to_action(dir_s: str, start_pos: float, fill_sz: float) -> tuple[str | None, str | None]:
    """Map Hyperliquid fill direction to (pos_type, action)."""
    d = str(dir_s or "").strip().lower()
    if not d:
        return None, None

    if "long" in d:
        pos_type = "LONG"
    elif "short" in d:
        pos_type = "SHORT"
    else:
        return None, None

    if d.startswith("open"):
        # OPEN if starting from ~0 position, else ADD.
        if abs(float(start_pos or 0.0)) < 1e-9:
            return pos_type, "OPEN"
        return pos_type, "ADD"

    if d.startswith("close"):
        # CLOSE if the remaining position would be ~0.
        end_pos = float(start_pos or 0.0)
        try:
            sp = float(start_pos or 0.0)
            fs = float(fill_sz or 0.0)
            # HL reports startPosition as signed (LONG>0, SHORT<0), but sz is positive.
            # Closing a SHORT moves the signed position towards 0 by +sz.
            end_pos = (sp - fs) if pos_type == "LONG" else (sp + fs)
        except Exception:
            end_pos = float(start_pos or 0.0)
        if abs(end_pos) < 1e-9:
            return pos_type, "CLOSE"
        return pos_type, "REDUCE"

    # Fallback
    return pos_type, None


def _action_side(pos_type: str, action: str) -> str | None:
    """Infer BUY/SELL from (pos_type, action)."""
    pt = str(pos_type or "").upper()
    ac = str(action or "").upper()
    if pt not in {"LONG", "SHORT"}:
        return None
    if ac in {"OPEN", "ADD"}:
        return "BUY" if pt == "LONG" else "SELL"
    if ac in {"CLOSE", "REDUCE"}:
        return "SELL" if pt == "LONG" else "BUY"
    return None


def _is_valid_hl_cloid(cloid: str | None) -> bool:
    """Return True if the string looks like a Hyperliquid Cloid (16-byte hex with 0x prefix)."""
    if not cloid:
        return False
    s = str(cloid).strip()
    if not s.startswith("0x"):
        return False
    if len(s) != 34:
        return False
    try:
        bytes.fromhex(s[2:])
    except Exception:
        return False
    return True


def _make_hl_cloid(*, seed_hex: str, prefix: str) -> str:
    """Generate a valid Hyperliquid `cloid` string.

    Hyperliquid's Python SDK validates `cloid` as a 16-byte hex string with a `0x` prefix.
    We encode an ASCII prefix (default: `aiq_`) into the first bytes for easy identification,
    and fill the remainder deterministically from `seed_hex` (typically `intent_id`).

    The `prefix` may be:
    - an ASCII string (e.g. `aiq_`)
    - a hex string representing raw bytes (e.g. `0x6169715f` for `aiq_`)
    """
    try:
        seed_b = bytes.fromhex(str(seed_hex or "").strip())
    except Exception:
        seed_b = uuid.uuid4().bytes
    # `seed_hex` is expected to be 32 hex chars (16 bytes); truncate/pad defensively.
    if len(seed_b) < 16:
        seed_b = (seed_b + (b"\x00" * 16))[:16]
    elif len(seed_b) > 16:
        seed_b = seed_b[:16]

    prefix_s = str(prefix or "").strip()
    prefix_b = b""
    if prefix_s.startswith("0x"):
        try:
            hx = prefix_s[2:]
            if hx and (len(hx) % 2 == 0):
                prefix_b = bytes.fromhex(hx)
        except Exception:
            prefix_b = b""
    if not prefix_b:
        try:
            prefix_b = prefix_s.encode("ascii", errors="ignore")
        except Exception:
            prefix_b = b""
    # Keep some entropy for uniqueness (avoid letting a too-long prefix consume all 16 bytes).
    prefix_b = prefix_b[:8]

    need = 16 - len(prefix_b)
    out_b = prefix_b + (seed_b[:need] if need > 0 else b"")
    if len(out_b) != 16:
        out_b = (out_b + (b"\x00" * 16))[:16]
    return "0x" + out_b.hex()


@dataclass(frozen=True)
class IntentHandle:
    intent_id: str
    client_order_id: str | None
    dedupe_key: str | None
    duplicate: bool = False


_OMS_INTENTS_MUTABLE_COLUMNS = frozenset(
    {
        "status",
        "sent_ts_ms",
        "client_order_id",
        "exchange_order_id",
        "last_error",
    }
)


class OmsStore:
    def __init__(self, *, db_path: str, timeout_s: float = 30.0):
        self._db_path = str(db_path)
        self._timeout_s = float(timeout_s)
        self._thread_local = threading.local()
        raw = str(os.getenv("AI_QUANT_OMS_PERSISTENT_CONN", "1") or "1").strip().lower()
        self._persistent_conn = raw not in {"0", "false", "no", "off"}

    def _connect(self, *, timeout_s: float | None = None) -> sqlite3.Connection:
        timeout = self._timeout_s if timeout_s is None else float(timeout_s)
        if self._persistent_conn and timeout_s is None:
            conn = getattr(self._thread_local, "conn", None)
            if isinstance(conn, sqlite3.Connection):
                return conn
        conn = sqlite3.connect(self._db_path, timeout=timeout)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            logger.debug("PRAGMA setup failed for OMS DB", exc_info=True)
        if self._persistent_conn and timeout_s is None:
            self._thread_local.conn = conn
        return conn

    def _close(self, conn: sqlite3.Connection | None) -> None:
        if conn is None:
            return
        if self._persistent_conn and conn is getattr(self._thread_local, "conn", None):
            return
        try:
            conn.close()
        except Exception:
            logger.debug("failed to close OMS DB connection", exc_info=True)

    def close(self) -> None:
        conn = getattr(self._thread_local, "conn", None)
        if conn is None:
            return
        try:
            conn.close()
        except Exception:
            logger.debug("failed to close persistent OMS DB connection", exc_info=True)
        finally:
            self._thread_local.conn = None

    def ensure(self) -> None:
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS oms_intents (
                    intent_id TEXT PRIMARY KEY,
                    created_ts_ms INTEGER NOT NULL,
                    sent_ts_ms INTEGER,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    side TEXT NOT NULL,
                    requested_size REAL,
                    requested_notional REAL,
                    entry_atr REAL,
                    leverage REAL,
                    decision_ts_ms INTEGER,
                    strategy_version TEXT,
                    strategy_sha1 TEXT,
                    reason TEXT,
                    confidence TEXT,
                    status TEXT,
                    dedupe_key TEXT,
                    client_order_id TEXT,
                    exchange_order_id TEXT,
                    last_error TEXT,
                    meta_json TEXT
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS oms_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    intent_id TEXT,
                    created_ts_ms INTEGER NOT NULL,
                    symbol TEXT,
                    side TEXT,
                    order_type TEXT,
                    requested_size REAL,
                    reduce_only INTEGER,
                    client_order_id TEXT,
                    exchange_order_id TEXT,
                    status TEXT,
                    raw_json TEXT
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_oms_orders_intent ON oms_orders(intent_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_oms_orders_symbol ON oms_orders(symbol, created_ts_ms)")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS oms_fills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_ms INTEGER,
                    symbol TEXT,
                    intent_id TEXT,
                    order_id INTEGER,
                    action TEXT,
                    side TEXT,
                    pos_type TEXT,
                    price REAL,
                    size REAL,
                    notional REAL,
                    fee_usd REAL,
                    fee_token TEXT,
                    fee_rate REAL,
                    pnl_usd REAL,
                    fill_hash TEXT,
                    fill_tid INTEGER,
                    matched_via TEXT,
                    raw_json TEXT
                )
                """
            )
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_oms_fills_hash_tid ON oms_fills(fill_hash, fill_tid)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_oms_fills_intent ON oms_fills(intent_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_oms_fills_symbol_ts ON oms_fills(symbol, ts_ms)")

            # Dedupe open intents across restarts per candle (dedupe_key is NULL for most intents).
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_oms_intents_dedupe ON oms_intents(dedupe_key)")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_oms_intents_symbol_status ON oms_intents(symbol, status, sent_ts_ms)"
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_oms_intents_client_order_id ON oms_intents(client_order_id)")

            # Open order snapshots (reconcile loop). This is an upsert table (1 row per exch order id).
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS oms_open_orders (
                    exchange_order_id TEXT PRIMARY KEY,
                    first_seen_ts_ms INTEGER,
                    last_seen_ts_ms INTEGER,
                    symbol TEXT,
                    side TEXT,
                    price REAL,
                    orig_size REAL,
                    remaining_size REAL,
                    reduce_only INTEGER,
                    client_order_id TEXT,
                    intent_id TEXT,
                    raw_json TEXT
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_oms_open_orders_symbol ON oms_open_orders(symbol, last_seen_ts_ms)"
            )

            # Reconcile actions log (append-only, small).
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS oms_reconcile_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_ms INTEGER,
                    kind TEXT,
                    symbol TEXT,
                    intent_id TEXT,
                    client_order_id TEXT,
                    exchange_order_id TEXT,
                    result TEXT,
                    detail_json TEXT
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_oms_reconcile_events_ts ON oms_reconcile_events(ts_ms)")
            conn.commit()
            try:
                os.chmod(str(self._db_path), 0o600)
            except OSError:
                pass
        finally:
            self._close(conn)

    def get_intent_by_dedupe_key(self, dedupe_key: str) -> tuple[str, str | None] | None:
        if not dedupe_key:
            return None
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT intent_id, client_order_id FROM oms_intents WHERE dedupe_key = ? LIMIT 1",
                (dedupe_key,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return str(row[0]), (str(row[1]) if row[1] else None)
        finally:
            self._close(conn)

    def insert_intent(
        self,
        *,
        intent_id: str,
        client_order_id: str | None,
        created_ts_ms: int,
        symbol: str,
        action: str,
        side: str,
        requested_size: float | None,
        requested_notional: float | None,
        entry_atr: float | None,
        leverage: float | None,
        decision_ts_ms: int | None,
        strategy_version: str | None,
        strategy_sha1: str | None,
        reason: str | None,
        confidence: str | None,
        status: str,
        dedupe_key: str | None,
        meta_json: str | None,
    ) -> bool:
        """Returns True if inserted, False if ignored (duplicate)."""
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT OR IGNORE INTO oms_intents (
                    intent_id, created_ts_ms, symbol, action, side,
                    requested_size, requested_notional, entry_atr, leverage,
                    decision_ts_ms, strategy_version, strategy_sha1,
                    reason, confidence, status, dedupe_key, client_order_id, meta_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    intent_id,
                    int(created_ts_ms),
                    str(symbol),
                    str(action),
                    str(side),
                    requested_size,
                    requested_notional,
                    entry_atr,
                    leverage,
                    decision_ts_ms,
                    strategy_version,
                    strategy_sha1,
                    reason,
                    confidence,
                    status,
                    dedupe_key,
                    client_order_id,
                    meta_json,
                ),
            )
            conn.commit()
            return bool(cur.rowcount and cur.rowcount > 0)
        finally:
            self._close(conn)

    def update_intent(
        self,
        intent_id: str,
        *,
        status: str | None = None,
        sent_ts_ms: int | None = None,
        client_order_id: str | None = None,
        exchange_order_id: str | None = None,
        last_error: str | None = None,
    ) -> None:
        sets: list[str] = []
        vals: list[Any] = []
        if status is not None:
            sets.append("status = ?")
            vals.append(str(status))
        if sent_ts_ms is not None:
            sets.append("sent_ts_ms = ?")
            vals.append(int(sent_ts_ms))
        if client_order_id is not None:
            sets.append("client_order_id = ?")
            vals.append(str(client_order_id))
        if exchange_order_id is not None:
            sets.append("exchange_order_id = ?")
            vals.append(str(exchange_order_id))
        if last_error is not None:
            sets.append("last_error = ?")
            vals.append(str(last_error))

        if not sets:
            return

        # Validate column names against allowlist (defence-in-depth).
        used_cols = {s.split(" = ?")[0] for s in sets}
        invalid = used_cols - _OMS_INTENTS_MUTABLE_COLUMNS
        if invalid:
            raise ValueError(f"Invalid OMS column names: {invalid}")

        vals.append(str(intent_id))

        conn = self._connect()
        cur = conn.cursor()
        try:
            # Safety: column names in `sets` are compile-time constants (hardcoded
            # above), not external input.  The allowlist check above is defence-in-depth.
            cur.execute(
                f"UPDATE oms_intents SET {', '.join(sets)} WHERE intent_id = ?",
                tuple(vals),
            )
            conn.commit()
        finally:
            self._close(conn)

    def insert_order(
        self,
        *,
        intent_id: str,
        created_ts_ms: int,
        symbol: str,
        side: str,
        order_type: str,
        requested_size: float | None,
        reduce_only: bool,
        client_order_id: str | None,
        exchange_order_id: str | None,
        status: str,
        raw_json: str | None,
    ) -> None:
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO oms_orders (
                    intent_id, created_ts_ms, symbol, side, order_type, requested_size, reduce_only,
                    client_order_id, exchange_order_id, status, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(intent_id),
                    int(created_ts_ms),
                    str(symbol),
                    str(side),
                    str(order_type),
                    requested_size,
                    1 if reduce_only else 0,
                    client_order_id,
                    exchange_order_id,
                    str(status),
                    raw_json,
                ),
            )
            conn.commit()
        finally:
            self._close(conn)

    def find_intent_by_client_order_id(self, client_order_id: str) -> str | None:
        if not client_order_id:
            return None
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT intent_id FROM oms_intents WHERE client_order_id = ? ORDER BY created_ts_ms DESC LIMIT 1",
                (str(client_order_id),),
            )
            row = cur.fetchone()
            return str(row[0]) if row and row[0] else None
        finally:
            self._close(conn)

    def find_intent_by_exchange_order_id(self, exchange_order_id: str) -> str | None:
        if not exchange_order_id:
            return None
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT intent_id FROM oms_intents WHERE exchange_order_id = ? ORDER BY created_ts_ms DESC LIMIT 1",
                (str(exchange_order_id),),
            )
            row = cur.fetchone()
            return str(row[0]) if row and row[0] else None
        finally:
            self._close(conn)

    def find_intent_by_fill_hash(self, fill_hash: str) -> str | None:
        """Find intent via a sibling fill that shares the same fill_hash (partial fill from same order)."""
        if not fill_hash:
            return None
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT intent_id FROM oms_fills WHERE fill_hash = ? AND intent_id IS NOT NULL ORDER BY ts_ms DESC LIMIT 1",
                (str(fill_hash),),
            )
            row = cur.fetchone()
            return str(row[0]) if row and row[0] else None
        finally:
            self._close(conn)

    def list_active_intents(
        self, *, statuses: tuple[str, ...] = ("SENT", "PARTIAL"), limit: int = 5000
    ) -> list[dict[str, Any]]:
        conn = self._connect()
        cur = conn.cursor()
        try:
            marks = ",".join(["?"] * len(statuses))
            cur.execute(
                f"""
                SELECT intent_id, symbol, action, side, requested_size, requested_notional,
                       leverage, sent_ts_ms, status, client_order_id, exchange_order_id
                FROM oms_intents
                WHERE status IN ({marks})
                ORDER BY COALESCE(sent_ts_ms, created_ts_ms) ASC
                LIMIT ?
                """,
                tuple([str(s) for s in statuses] + [int(limit)]),
            )
            rows = cur.fetchall() or []
            out: list[dict[str, Any]] = []
            for r in rows:
                out.append(
                    {
                        "intent_id": r[0],
                        "symbol": r[1],
                        "action": r[2],
                        "side": r[3],
                        "requested_size": r[4],
                        "requested_notional": r[5],
                        "leverage": r[6],
                        "sent_ts_ms": r[7],
                        "status": r[8],
                        "client_order_id": r[9],
                        "exchange_order_id": r[10],
                    }
                )
            return out
        finally:
            self._close(conn)

    def upsert_open_order(
        self,
        *,
        exchange_order_id: str,
        first_seen_ts_ms: int,
        last_seen_ts_ms: int,
        symbol: str,
        side: str | None,
        price: float | None,
        orig_size: float | None,
        remaining_size: float | None,
        reduce_only: bool,
        client_order_id: str | None,
        intent_id: str | None,
        raw_json: str | None,
    ) -> None:
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO oms_open_orders (
                    exchange_order_id, first_seen_ts_ms, last_seen_ts_ms,
                    symbol, side, price, orig_size, remaining_size, reduce_only,
                    client_order_id, intent_id, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(exchange_order_id) DO UPDATE SET
                    last_seen_ts_ms=excluded.last_seen_ts_ms,
                    symbol=excluded.symbol,
                    side=excluded.side,
                    price=excluded.price,
                    orig_size=excluded.orig_size,
                    remaining_size=excluded.remaining_size,
                    reduce_only=excluded.reduce_only,
                    client_order_id=excluded.client_order_id,
                    intent_id=excluded.intent_id,
                    raw_json=excluded.raw_json
                """,
                (
                    str(exchange_order_id),
                    int(first_seen_ts_ms),
                    int(last_seen_ts_ms),
                    str(symbol),
                    (str(side) if side is not None else None),
                    (None if price is None else float(price)),
                    (None if orig_size is None else float(orig_size)),
                    (None if remaining_size is None else float(remaining_size)),
                    1 if reduce_only else 0,
                    client_order_id,
                    intent_id,
                    raw_json,
                ),
            )
            conn.commit()
        finally:
            self._close(conn)

    def prune_open_orders(self, *, older_than_ms: int) -> int:
        """Delete open-order snapshots that haven't been seen recently."""
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "DELETE FROM oms_open_orders WHERE last_seen_ts_ms IS NOT NULL AND last_seen_ts_ms < ?",
                (int(older_than_ms),),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            self._close(conn)

    def insert_reconcile_event(
        self,
        *,
        ts_ms: int,
        kind: str,
        symbol: str | None,
        intent_id: str | None,
        client_order_id: str | None,
        exchange_order_id: str | None,
        result: str | None,
        detail_json: str | None,
    ) -> None:
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO oms_reconcile_events (
                    ts_ms, kind, symbol, intent_id, client_order_id, exchange_order_id, result, detail_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(ts_ms),
                    str(kind),
                    (str(symbol) if symbol else None),
                    (str(intent_id) if intent_id else None),
                    (str(client_order_id) if client_order_id else None),
                    (str(exchange_order_id) if exchange_order_id else None),
                    (str(result) if result else None),
                    detail_json,
                ),
            )
            conn.commit()
        finally:
            self._close(conn)

    def find_pending_intent(
        self,
        *,
        symbol: str,
        action: str,
        side: str,
        t_ms: int,
        ttl_ms: int,
    ) -> str | None:
        """Best-effort match fill -> intent using symbol/action/side and time proximity."""
        sym = str(symbol)
        ac = str(action)
        sd = str(side)
        t = int(t_ms)
        ttl = int(ttl_ms)
        start = t - ttl
        end = t + ttl
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT intent_id
                FROM oms_intents
                WHERE symbol = ?
                  AND action = ?
                  AND side = ?
                  AND status IN ('SENT', 'PARTIAL', 'UNKNOWN')
                  AND sent_ts_ms IS NOT NULL
                  AND sent_ts_ms BETWEEN ? AND ?
                ORDER BY ABS(sent_ts_ms - ?) ASC
                LIMIT 1
                """,
                (sym, ac, sd, int(start), int(end), int(t)),
            )
            row = cur.fetchone()
            return str(row[0]) if row and row[0] else None
        finally:
            self._close(conn)

    def get_intent_fields(self, intent_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT intent_id, symbol, action, side, requested_size, requested_notional,
                       entry_atr, leverage, reason, confidence, meta_json
                FROM oms_intents
                WHERE intent_id = ?
                LIMIT 1
                """,
                (str(intent_id),),
            )
            row = cur.fetchone()
            if not row:
                return None
            keys = [
                "intent_id",
                "symbol",
                "action",
                "side",
                "requested_size",
                "requested_notional",
                "entry_atr",
                "leverage",
                "reason",
                "confidence",
                "meta_json",
            ]
            out = {k: row[i] for i, k in enumerate(keys)}
            return out
        finally:
            self._close(conn)

    def insert_fill(
        self,
        *,
        ts_ms: int,
        symbol: str,
        intent_id: str | None,
        action: str | None,
        side: str | None,
        pos_type: str | None,
        price: float,
        size: float,
        notional: float,
        fee_usd: float | None,
        fee_token: str | None,
        fee_rate: float | None,
        pnl_usd: float | None,
        fill_hash: str | None,
        fill_tid: int | None,
        matched_via: str | None,
        raw_json: str | None,
    ) -> bool:
        """Insert fill. Returns True if inserted, False if deduped."""
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT OR IGNORE INTO oms_fills (
                    ts_ms, symbol, intent_id, action, side, pos_type,
                    price, size, notional,
                    fee_usd, fee_token, fee_rate, pnl_usd,
                    fill_hash, fill_tid,
                    matched_via, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(ts_ms),
                    str(symbol),
                    intent_id,
                    action,
                    side,
                    pos_type,
                    float(price),
                    float(size),
                    float(notional),
                    fee_usd,
                    fee_token,
                    fee_rate,
                    pnl_usd,
                    fill_hash,
                    fill_tid,
                    matched_via,
                    raw_json,
                ),
            )
            conn.commit()
            return bool(cur.rowcount and cur.rowcount > 0)
        finally:
            self._close(conn)

    def sum_filled_size(self, intent_id: str) -> float:
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("SELECT COALESCE(SUM(size), 0) FROM oms_fills WHERE intent_id = ?", (str(intent_id),))
            row = cur.fetchone()
            return float(row[0] or 0.0) if row else 0.0
        finally:
            self._close(conn)

    def expire_old_sent_intents(self, *, older_than_ms: int) -> int:
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE oms_intents
                SET status = 'EXPIRED'
                WHERE status IN ('SENT', 'PARTIAL', 'UNKNOWN')
                  AND sent_ts_ms IS NOT NULL
                  AND sent_ts_ms < ?
                """,
                (int(older_than_ms),),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            self._close(conn)


class LiveOms:
    """Minimal OMS layer.

    What it gives you immediately:
    - persistent OrderIntent ledger with dedupe for OPEN intents (restart-safe)
    - persistent Orders + Fills ledger (fills deduped by hash+tid)
    - fill-to-intent matching via client_order_id when available, with a time-proximity fallback
    - enrichment of trades.meta_json with OMS intent_id for better strategy debugging

    It is intentionally conservative: it does not change your strategy logic.
    It wraps order submission + fill ingestion to remove the most common live-trading failure modes.
    """

    def __init__(
        self,
        *,
        db_path: str,
        match_ttl_ms: int | None = None,
        expire_sent_after_ms: int | None = None,
    ):
        # OMS writes should be fast and never stall the live engine loop.
        # Use a dedicated timeout knob (defaults to the fill-ingest timeout).
        try:
            timeout_s = float(
                os.getenv("AI_QUANT_OMS_STORE_DB_TIMEOUT_S", os.getenv("AI_QUANT_OMS_DB_TIMEOUT_S", "1.0"))
            )
        except Exception:
            timeout_s = 1.0
        timeout_s = float(max(0.05, min(5.0, timeout_s)))

        self.store = OmsStore(db_path=str(db_path), timeout_s=timeout_s)
        self.store.ensure()

        # Ensure base schema once (trades/audit tables). Avoid calling ensure_db() in hot paths.
        try:
            import strategy.mei_alpha_v1 as mei_alpha_v1

            mei_alpha_v1.ensure_db()
        except Exception:
            logger.debug("mei_alpha_v1.ensure_db() failed during OMS init", exc_info=True)

        # Exposed to the daemon for health checks / alerts.
        self.last_ingest_stats: dict[str, Any] = {}

        self.match_ttl_ms = int(match_ttl_ms or int(os.getenv("AI_QUANT_OMS_MATCH_TTL_MS", str(10 * 60 * 1000))))
        if expire_sent_after_ms is not None:
            self.expire_sent_after_ms = int(expire_sent_after_ms)
        else:
            # Prefer the clearer name, but accept the older env var too.
            raw = os.getenv("AI_QUANT_OMS_EXPIRE_SENT_AFTER_MS")
            if raw is None:
                raw = os.getenv("AI_QUANT_OMS_EXPIRE_SENT_MS")
            try:
                self.expire_sent_after_ms = int(float(raw)) if raw is not None else int(6 * 60 * 60 * 1000)
            except Exception:
                self.expire_sent_after_ms = int(6 * 60 * 60 * 1000)

        # Orphan/unmatched fill reconciliation (best-effort; for manual fills or legacy gaps).
        try:
            self._unmatched_reconcile_every_s = float(
                os.getenv("AI_QUANT_OMS_UNMATCHED_RECONCILE_SECS", "300") or 300.0
            )
        except Exception:
            self._unmatched_reconcile_every_s = 300.0
        self._unmatched_reconcile_every_s = float(max(30.0, min(self._unmatched_reconcile_every_s, 6 * 60 * 60.0)))
        self._last_unmatched_reconcile_s: float = 0.0
        try:
            self._unmatched_reconcile_max = int(float(os.getenv("AI_QUANT_OMS_UNMATCHED_RECONCILE_MAX", "200") or 200))
        except Exception:
            self._unmatched_reconcile_max = 200
        self._unmatched_reconcile_max = int(max(1, min(self._unmatched_reconcile_max, 5000)))
        try:
            self._unmatched_grace_ms = int(float(os.getenv("AI_QUANT_OMS_UNMATCHED_GRACE_MS", "60000") or 60000))
        except Exception:
            self._unmatched_grace_ms = 60000
        self._unmatched_grace_ms = int(max(0, min(self._unmatched_grace_ms, 24 * 60 * 60 * 1000)))

        self._manual_intent_prefix = (
            str(os.getenv("AI_QUANT_OMS_MANUAL_INTENT_PREFIX", "manual_") or "manual_").strip() or "manual_"
        )

        # Optional kernel provider for fill reconciliation (set externally).
        # When set to a KernelDecisionRustBindingProvider, confirmed fills are
        # fed to the kernel via step_full() and positions are reconciled.
        # Fill dedup: INSERT OR IGNORE on oms_fills (fill_hash + fill_tid unique
        # index) ensures each fill is processed at most once, preventing
        # double-counting in the kernel.
        self.kernel_provider: Any | None = None

    def create_intent(
        self,
        *,
        symbol: str,
        action: str,
        side: str,
        requested_size: float | None,
        requested_notional: float | None,
        leverage: float | None,
        decision_ts: Any | None,
        reason: str | None,
        confidence: str | None,
        entry_atr: float | None = None,
        meta: dict[str, Any] | None = None,
        dedupe_open: bool = True,
    ) -> IntentHandle:
        sym = str(symbol).strip().upper()
        ac = str(action).strip().upper()
        sd = str(side).strip().upper()

        created_ms = now_ms()
        decision_ms = _coerce_ts_ms(decision_ts)

        # Hyperliquid validates cloid as a 16-byte hex string with a 0x prefix.
        # We encode an ASCII prefix (default: aiq_) into the first bytes for identification.
        intent_id = uuid.uuid4().hex
        cloid_prefix = str(os.getenv("AI_QUANT_OMS_CLOID_PREFIX", "aiq_") or "aiq_").strip() or "aiq_"
        client_order_id = _make_hl_cloid(seed_hex=intent_id, prefix=cloid_prefix)

        dedupe_key: str | None = None
        if dedupe_open and ac == "OPEN" and decision_ms is not None:
            dedupe_key = f"OPEN:{sym}:{sd}:{int(decision_ms)}"

        # Strategy snapshot (best-effort)
        strategy_version = None
        strategy_sha1 = None
        try:
            from .strategy_manager import StrategyManager

            snap = StrategyManager.get().snapshot
            strategy_version = snap.version
            strategy_sha1 = snap.overrides_sha1
        except Exception:
            logger.debug("failed to get strategy snapshot for OMS intent", exc_info=True)

        meta2 = dict(meta or {})
        # Inject strategy snapshot even if caller didn't.
        try:
            meta2.setdefault("strategy", {})
            if isinstance(meta2.get("strategy"), dict):
                meta2["strategy"].setdefault("version", strategy_version)
                meta2["strategy"].setdefault("overrides_sha1", strategy_sha1)
        except Exception:
            logger.debug("failed to inject strategy snapshot into OMS intent meta", exc_info=True)

        meta_json = json_dumps_safe(meta2) if meta2 else None

        inserted = self.store.insert_intent(
            intent_id=intent_id,
            client_order_id=client_order_id,
            created_ts_ms=created_ms,
            symbol=sym,
            action=ac,
            side=sd,
            requested_size=requested_size,
            requested_notional=requested_notional,
            entry_atr=entry_atr,
            leverage=leverage,
            decision_ts_ms=decision_ms,
            strategy_version=strategy_version,
            strategy_sha1=strategy_sha1,
            reason=reason,
            confidence=confidence,
            status="NEW",
            dedupe_key=dedupe_key,
            meta_json=meta_json,
        )

        if not inserted and dedupe_key:
            existing = self.store.get_intent_by_dedupe_key(dedupe_key)
            if existing is not None:
                existing_id, existing_client = existing
                # Best-effort: older DB rows may contain non-HL cloids. Upgrade in place so future
                # submissions can pass a valid cloid to the SDK.
                if not _is_valid_hl_cloid(existing_client):
                    upgraded = _make_hl_cloid(seed_hex=str(existing_id), prefix=cloid_prefix)
                    try:
                        self.store.update_intent(str(existing_id), client_order_id=upgraded)
                        existing_client = upgraded
                    except Exception:
                        # If we cannot update, keep the stored value to avoid lying to the caller.
                        logger.debug("failed to upgrade cloid for intent %s", existing_id, exc_info=True)
                return IntentHandle(
                    intent_id=str(existing_id),
                    client_order_id=existing_client,
                    dedupe_key=dedupe_key,
                    duplicate=True,
                )

        return IntentHandle(
            intent_id=intent_id, client_order_id=client_order_id, dedupe_key=dedupe_key, duplicate=False
        )

    def mark_would(self, intent: IntentHandle, *, note: str | None = None) -> None:
        # Used for dry_live mode.
        msg = str(note or "dry_live")
        self.store.update_intent(intent.intent_id, status="WOULD", last_error=msg)

    def mark_failed(self, intent: IntentHandle, *, error: str) -> None:
        self.store.update_intent(intent.intent_id, status="REJECTED", last_error=str(error or ""))

    def mark_submit_unknown(
        self,
        intent: IntentHandle,
        *,
        symbol: str,
        side: str,
        order_type: str,
        reduce_only: bool,
        requested_size: float | None = None,
        error: str | None = None,
    ) -> None:
        """Record an ambiguous submit outcome (for example, a REST timeout).

        This keeps the intent matchable by fill time-proximity even when the exchange order id
        is unknown. Downstream fill ingestion can then attach the fill to the correct intent and
        repair `exchange_order_id` from the fill payload.
        """
        sent_ms = now_ms()
        msg = str(error or "submit_unknown")

        sym = str(symbol or "").strip().upper()
        sd = str(side or "").strip().upper()

        raw_json = json_dumps_safe(
            {
                "kind": "submit_unknown",
                "error": msg,
            }
        )

        self.store.update_intent(intent.intent_id, status="UNKNOWN", sent_ts_ms=sent_ms, last_error=msg)
        self.store.insert_order(
            intent_id=intent.intent_id,
            created_ts_ms=sent_ms,
            symbol=sym,
            side=sd,
            order_type=str(order_type),
            requested_size=None if requested_size is None else float(requested_size),
            reduce_only=bool(reduce_only),
            client_order_id=intent.client_order_id,
            exchange_order_id=None,
            status="UNKNOWN",
            raw_json=raw_json,
        )

    def mark_sent(
        self,
        intent: IntentHandle,
        *,
        symbol: str,
        side: str,
        order_type: str,
        reduce_only: bool,
        requested_size: float | None = None,
        result: Any | None = None,
        exchange_order_id: str | None = None,
    ) -> None:
        sent_ms = now_ms()

        exch = exchange_order_id
        # Try to infer an exchange order id from the result if not explicitly provided.
        # Hyperliquid's SDK wraps order responses under response.data.statuses.
        if exch is None and isinstance(result, dict):
            # Fast path: common flat keys.
            for k in ("oid", "orderId", "order_id", "id"):
                if k in result and result.get(k) is not None:
                    try:
                        exch = str(result.get(k))
                        break
                    except Exception:
                        pass

        if exch is None and isinstance(result, dict):
            # HL order response: {"status":"ok","response":{"type":"order","data":{"statuses":[...]}}}
            try:
                resp = result.get("response") or {}
                data = resp.get("data") or {}
                statuses = data.get("statuses") or []
            except (AttributeError, TypeError):
                statuses = []
            if isinstance(statuses, list):
                for st in statuses:
                    if not isinstance(st, dict):
                        continue
                    # Prefer a filled oid, then resting oid.
                    for key in ("filled", "resting"):
                        payload = st.get(key)
                        if isinstance(payload, dict) and payload.get("oid") is not None:
                            try:
                                exch = str(payload.get("oid"))
                                break
                            except Exception:
                                pass
                    if exch is not None:
                        break

        raw_json = None
        try:
            raw_json = json.dumps(result, separators=(",", ":"), sort_keys=True, default=str)
        except Exception:
            raw_json = None

        sym = str(symbol or "").strip().upper()
        sd = str(side or "").strip().upper()

        self.store.update_intent(
            intent.intent_id, status="SENT", sent_ts_ms=sent_ms, exchange_order_id=exch, last_error=""
        )
        self.store.insert_order(
            intent_id=intent.intent_id,
            created_ts_ms=sent_ms,
            symbol=sym,
            side=sd,
            order_type=str(order_type),
            requested_size=None if requested_size is None else float(requested_size),
            reduce_only=bool(reduce_only),
            client_order_id=intent.client_order_id,
            exchange_order_id=exch,
            status="SENT",
            raw_json=raw_json,
        )

    def reconcile(self, *, trader: Any | None = None) -> None:
        """OMS maintenance tasks.

        - expire old SENT/PARTIAL intents so the pending set can't grow forever
        - best-effort reconcile of legacy/manual fills that were ingested without an intent_id
        """
        try:
            cutoff = now_ms() - int(self.expire_sent_after_ms)
            n = self.store.expire_old_sent_intents(older_than_ms=cutoff)
        except Exception:
            n = 0

        if n <= 0:
            # Still run orphan reconcile on schedule.
            self._maybe_reconcile_unmatched_fills(trader=trader)
            return

        # Best-effort audit event.
        try:
            import strategy.mei_alpha_v1 as mei_alpha_v1

            mei_alpha_v1.log_audit_event(
                symbol="SYSTEM",
                event="OMS_EXPIRE_INTENTS",
                level="warn",
                data={"expired": int(n), "cutoff_ms": int(cutoff)},
            )
        except Exception:
            logger.debug("failed to log OMS_EXPIRE_INTENTS audit event", exc_info=True)

        self._maybe_reconcile_unmatched_fills(trader=trader)

    def _maybe_reconcile_unmatched_fills(self, *, trader: Any | None) -> None:
        now_s = time.time()
        if self._last_unmatched_reconcile_s and (now_s - self._last_unmatched_reconcile_s) < float(
            self._unmatched_reconcile_every_s
        ):
            return
        self._last_unmatched_reconcile_s = now_s
        try:
            self.reconcile_unmatched_fills(trader=trader)
        except Exception:
            # Never let reconciliation break the main loop.
            logger.warning("reconcile_unmatched_fills failed", exc_info=True)

    def reconcile_unmatched_fills(self, *, trader: Any | None = None) -> dict[str, Any]:
        """Best-effort: resolve fills that were ingested without an OMS intent.

        Why this exists:
        - WS fill events do not include client_order_id (cloid) in our current schema.
        - Legacy/manual fills can appear on the account; we still ingest them into trades/oms_fills.
        - Monitoring that counts `intent_id IS NULL` will otherwise stay non-zero forever.

        Strategy:
        1) Try to match by exchange_order_id (oid) against existing intents.
        2) Try to match by time-proximity against any intent for the same symbol/action/side.
        3) If still unmatched, create a synthetic "manual" intent and attach the fill to it.
        """
        now_ms_i = now_ms()
        grace_ms = int(self._unmatched_grace_ms)
        max_n = int(self._unmatched_reconcile_max)

        # Keep this non-blocking.
        try:
            timeout_s = float(os.getenv("AI_QUANT_OMS_DB_TIMEOUT_S", "1.0"))
        except Exception:
            timeout_s = 1.0
        timeout_s = float(max(0.05, min(5.0, timeout_s)))

        conn: sqlite3.Connection | None = None
        cur: sqlite3.Cursor | None = None

        matched = 0
        manual = 0
        scanned = 0
        samples: list[dict[str, Any]] = []
        _t0 = time.monotonic()

        try:
            conn = self.store._connect(timeout_s=timeout_s)
            cur = conn.cursor()

            cutoff_ms = int(now_ms_i - grace_ms)
            cur.execute(
                """
                SELECT id, ts_ms, symbol, action, side, price, size, notional, fill_hash, fill_tid, raw_json
                FROM oms_fills
                WHERE intent_id IS NULL AND ts_ms IS NOT NULL AND ts_ms <= ?
                ORDER BY ts_ms ASC
                LIMIT ?
                """,
                (int(cutoff_ms), int(max_n)),
            )
            rows = cur.fetchall() or []

            # Cache trades schema once.
            try:
                cur.execute("PRAGMA table_info(trades)")
                trade_cols = {r[1] for r in cur.fetchall()}
            except Exception:
                trade_cols = set()
            has_trade_meta = "meta_json" in trade_cols

            for r in rows:
                scanned += 1
                (
                    fill_row_id,
                    ts_ms,
                    sym,
                    action,
                    side,
                    px,
                    sz,
                    notional,
                    fill_hash,
                    fill_tid,
                    raw_json,
                ) = r

                sym_u = str(sym or "").strip().upper()
                action_u = str(action or "").strip().upper()
                side_u = str(side or "").strip().upper()
                oid = None
                fill_obj: dict[str, Any] | None = None
                try:
                    fill_obj = json.loads(raw_json) if raw_json else None
                    if isinstance(fill_obj, dict):
                        oid = self._extract_exchange_order_id_from_fill(fill_obj)
                except Exception:
                    fill_obj = None

                intent_id = None
                matched_via = None

                # 1) Match by exchange order id
                if oid:
                    try:
                        cur.execute(
                            "SELECT intent_id FROM oms_intents WHERE exchange_order_id = ? ORDER BY created_ts_ms DESC LIMIT 1",
                            (str(oid),),
                        )
                        row = cur.fetchone()
                        if row and row[0]:
                            intent_id = str(row[0])
                            matched_via = "exchange_order_id_reconcile"
                    except Exception:
                        intent_id = None

                # 2) Match by time proximity against any intent (not just SENT/PARTIAL)
                if not intent_id:
                    try:
                        ttl = int(self.match_ttl_ms)
                        start = int(ts_ms) - ttl
                        end = int(ts_ms) + ttl
                        cur.execute(
                            """
                            SELECT intent_id
                            FROM oms_intents
                            WHERE symbol = ? AND action = ? AND side = ?
                              AND sent_ts_ms IS NOT NULL AND sent_ts_ms BETWEEN ? AND ?
                            ORDER BY ABS(sent_ts_ms - ?) ASC
                            LIMIT 1
                            """,
                            (sym_u, action_u, side_u, int(start), int(end), int(ts_ms)),
                        )
                        row = cur.fetchone()
                        if row and row[0]:
                            intent_id = str(row[0])
                            matched_via = "time_proximity_reconcile"
                    except Exception:
                        intent_id = None

                # 3) Create synthetic manual intent
                if not intent_id:
                    # Stable id so reruns are idempotent.
                    intent_id = f"{self._manual_intent_prefix}{str(fill_hash)[:12]}_{int(fill_tid)}"
                    matched_via = "manual_orphan"

                    reason = "MANUAL_FILL"
                    conf = "n/a"
                    # Best-effort leverage from fill.
                    lev = None
                    try:
                        if isinstance(fill_obj, dict):
                            lev_raw = fill_obj.get("leverage")
                            if isinstance(lev_raw, dict):
                                lev = _safe_float(lev_raw.get("value"), None)
                            else:
                                lev = _safe_float(lev_raw, None)
                    except Exception:
                        lev = None

                    meta = {"manual": True, "source": "reconcile_unmatched_fills"}
                    if isinstance(fill_obj, dict):
                        meta["fill"] = fill_obj
                    meta_json = json_dumps_safe(meta)

                    # IMPORTANT: Use the SAME sqlite connection/cursor throughout this function.
                    # Nested store.* calls open new connections and can deadlock under WAL.
                    try:
                        cur.execute(
                            """
                            INSERT OR IGNORE INTO oms_intents (
                                intent_id, created_ts_ms, sent_ts_ms, symbol, action, side,
                                requested_size, requested_notional, entry_atr, leverage,
                                decision_ts_ms, strategy_version, strategy_sha1,
                                reason, confidence, status, dedupe_key, client_order_id, exchange_order_id, last_error, meta_json
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                str(intent_id),
                                int(ts_ms),
                                int(ts_ms),
                                sym_u,
                                action_u,
                                side_u,
                                (None if sz is None else float(sz)),
                                (None if notional is None else float(notional)),
                                None,
                                lev,
                                int(ts_ms),
                                "manual",
                                None,
                                reason,
                                conf,
                                "FILLED",
                                None,
                                None,
                                (str(oid) if oid else None),
                                "",
                                meta_json,
                            ),
                        )
                        # Ensure sent_ts_ms/exchange_order_id aren't empty if the row existed already.
                        cur.execute(
                            """
                            UPDATE oms_intents
                            SET sent_ts_ms = COALESCE(sent_ts_ms, ?),
                                exchange_order_id = COALESCE(exchange_order_id, ?),
                                last_error = COALESCE(last_error, '')
                            WHERE intent_id = ?
                            """,
                            (int(ts_ms), (str(oid) if oid else None), str(intent_id)),
                        )
                    except Exception:
                        logger.debug("failed to update OMS intent for manual reconcile", exc_info=True)

                    manual += 1

                else:
                    matched += 1

                # Update the fill row.
                try:
                    cur.execute(
                        "UPDATE oms_fills SET intent_id = ?, matched_via = COALESCE(matched_via, ?) WHERE id = ?",
                        (str(intent_id), str(matched_via), int(fill_row_id)),
                    )
                except Exception:
                    logger.debug("failed to update OMS fill row for reconcile", exc_info=True)

                # Best-effort update corresponding trades.meta_json.
                if has_trade_meta:
                    try:
                        cur.execute(
                            "SELECT id, meta_json FROM trades WHERE fill_hash = ? AND fill_tid = ? ORDER BY id DESC LIMIT 1",
                            (str(fill_hash), int(fill_tid)),
                        )
                        tr = cur.fetchone()
                        if tr and tr[0]:
                            trade_id = int(tr[0])
                            mj = tr[1]
                            obj = None
                            try:
                                obj = json.loads(mj) if mj else {}
                            except Exception:
                                obj = {}
                            if not isinstance(obj, dict):
                                obj = {}
                            obj.setdefault("oms", {})
                            if isinstance(obj.get("oms"), dict):
                                obj["oms"].update(
                                    {"intent_id": intent_id, "matched_via": matched_via, "exchange_order_id": oid}
                                )
                            obj.setdefault("reconcile", {})
                            if isinstance(obj.get("reconcile"), dict):
                                obj["reconcile"].update({"unmatched_fill": True})
                            cur.execute(
                                "UPDATE trades SET meta_json = ? WHERE id = ?",
                                (json_dumps_safe(obj), int(trade_id)),
                            )
                    except Exception:
                        logger.debug("failed to update trades.meta_json for reconcile", exc_info=True)

                if len(samples) < 5:
                    try:
                        samples.append(
                            {
                                "symbol": sym_u,
                                "action": action_u,
                                "side": side_u,
                                "t_ms": int(ts_ms),
                                "intent_id": str(intent_id),
                                "matched_via": matched_via,
                            }
                        )
                    except Exception:
                        logger.debug("failed to build reconcile sample entry", exc_info=True)

            conn.commit()

            # Record a single reconcile event for observability.
            try:
                if scanned:
                    cur.execute(
                        """
                        INSERT INTO oms_reconcile_events (
                            ts_ms, kind, symbol, intent_id, client_order_id, exchange_order_id, result, detail_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            int(now_ms_i),
                            "RECONCILE_UNMATCHED_FILLS",
                            "SYSTEM",
                            None,
                            None,
                            None,
                            "ok",
                            json_dumps_safe(
                                {"scanned": scanned, "matched": matched, "manual": manual, "samples": samples}
                            ),
                        ),
                    )
                    conn.commit()
            except Exception:
                logger.debug("failed to record reconcile event", exc_info=True)

        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                logger.debug("failed to close OMS DB after reconcile", exc_info=True)

        _elapsed = time.monotonic() - _t0
        if _elapsed > 2.0:
            logger.warning("reconcile_unmatched_fills took %.2fs (scanned=%d)", _elapsed, scanned)

        return {"scanned": int(scanned), "matched": int(matched), "manual": int(manual), "samples": samples}

    def _extract_client_order_id_from_fill(self, f: dict) -> str | None:
        # Hyperliquid schemas vary; keep this permissive.
        for k in ("cloid", "clientOrderId", "client_oid", "clientOrder", "client_order_id"):
            v = f.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        # Sometimes nested.
        try:
            order = f.get("order")
            if isinstance(order, dict):
                for k in ("cloid", "clientOrderId", "client_order_id"):
                    v = order.get(k)
                    if isinstance(v, str) and v.strip():
                        return v.strip()
        except Exception:
            pass
        return None

    def _extract_exchange_order_id_from_fill(self, f: dict) -> str | None:
        # Hyperliquid fills include `oid`.
        v = f.get("oid")
        if v is None:
            return None
        try:
            s = str(v).strip()
            return s or None
        except Exception:
            return None

    def match_intent_for_fill(
        self, *, fill: dict, symbol: str, action: str, side: str, t_ms: int
    ) -> tuple[str | None, str | None]:
        """Returns (intent_id, matched_via)."""
        # Layer 1: Exchange Order ID
        oid = self._extract_exchange_order_id_from_fill(fill)
        if oid:
            intent_id = self.store.find_intent_by_exchange_order_id(oid)
            if intent_id:
                return intent_id, "exchange_order_id"

        # Layer 1.5: Fill hash sibling — another partial fill from the same order
        # was already matched in a previous batch (committed).
        fh = str(fill.get("hash") or "").strip() or None
        if fh:
            intent_id = self.store.find_intent_by_fill_hash(fh)
            if intent_id:
                return intent_id, "fill_hash_sibling"

        # Layer 2: Client Order ID
        cloid = self._extract_client_order_id_from_fill(fill)
        if cloid:
            intent_id = self.store.find_intent_by_client_order_id(cloid)
            if intent_id:
                return intent_id, "client_order_id"

        # Layer 3: Time Proximity
        intent_id = self.store.find_pending_intent(
            symbol=symbol, action=action, side=side, t_ms=int(t_ms), ttl_ms=int(self.match_ttl_ms)
        )
        if intent_id:
            return intent_id, "time_proximity"

        return None, None

    def _signal_backfill_dedup_ms(self) -> int:
        """Time window (ms) for de-duping signals near a fill/trade timestamp."""
        raw = os.getenv("AI_QUANT_SIGNAL_BACKFILL_DEDUP_S", "600")
        try:
            v = float(raw)
        except Exception:
            v = 600.0
        return int(max(0.0, min(v, 6 * 60 * 60.0)) * 1000.0)

    def _maybe_insert_signal(
        self,
        *,
        cur: sqlite3.Cursor,
        sym: str,
        ts_iso: str,
        t_ms: int,
        signal: str,
        confidence: str,
        price: float,
        reason: str,
        intent_id: str | None,
        matched_via: str | None,
        meta: dict[str, Any] | None,
    ) -> bool:
        """Best-effort: ensure a strategy signal exists for live monitoring.

        This is a self-heal/backfill path for when strategy signal logging is missed
        (e.g., older versions, transient DB lock, or rest-only ingestion).
        """
        sig = str(signal or "").strip().upper()
        if sig not in {"BUY", "SELL"}:
            return False

        sym_u = str(sym or "").strip().upper()
        if not sym_u:
            return False

        # Only backfill signals we believe came from the bot (avoid manual orders).
        reason_s = str(reason or "")
        meta2 = meta if isinstance(meta, dict) else {}
        bot_likely = (
            bool(intent_id) or reason_s.lower().startswith("signal") or ("order" in meta2) or ("audit" in meta2)
        )
        if not bot_likely:
            return False

        dedup_ms = int(self._signal_backfill_dedup_ms())
        if dedup_ms > 0:
            try:
                cur.execute(
                    "SELECT timestamp, signal FROM signals WHERE symbol = ? ORDER BY id DESC LIMIT 10",
                    (sym_u,),
                )
                for ts0, sig0 in cur.fetchall() or []:
                    ms0 = _coerce_ts_ms(ts0)
                    if ms0 is None:
                        continue
                    try:
                        if abs(int(ms0) - int(t_ms)) <= dedup_ms and str(sig0 or "").strip().upper() == sig:
                            return False
                    except Exception:
                        continue
            except Exception:
                # If signals table isn't readable for some reason, still avoid failing fill ingestion.
                pass

        # Keep signal meta compact (monitor uses timestamp/signal/confidence/price; meta is for debugging).
        meta_sig: dict[str, Any] = {}
        try:
            if isinstance(meta2.get("audit"), dict):
                meta_sig["audit"] = meta2.get("audit")
        except Exception:
            logger.debug("failed to extract audit from meta for signal backfill", exc_info=True)
        try:
            if isinstance(meta2.get("order"), dict):
                meta_sig["order"] = meta2.get("order")
        except Exception:
            logger.debug("failed to extract order from meta for signal backfill", exc_info=True)
        meta_sig["backfill"] = {
            "source": "oms_fill_ingest",
            "reason": reason_s,
            "intent_id": intent_id,
            "matched_via": matched_via,
            "t_ms": int(t_ms),
        }
        meta_json = json_dumps_safe(meta_sig) if meta_sig else None

        try:
            cur.execute(
                """
                INSERT INTO signals (timestamp, symbol, signal, confidence, price, rsi, ema_fast, ema_slow, meta_json, run_fingerprint)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(ts_iso),
                    sym_u,
                    sig,
                    str(confidence or "").strip().lower() or "n/a",
                    float(price),
                    None,
                    None,
                    None,
                    meta_json,
                    _current_run_fingerprint(),
                ),
            )
            return bool(cur.rowcount and cur.rowcount > 0)
        except Exception:
            return False

    def backfill_signals_from_trades(
        self,
        *,
        lookback_h: float | None = None,
        max_trades: int | None = None,
        dedup_s: float | None = None,
    ) -> int:
        """Backfill missing signals using recent trades rows.

        This is a lightweight repair tool for older live DBs where signals were not persisted.
        """
        try:
            lb_h = (
                float(os.getenv("AI_QUANT_SIGNAL_BACKFILL_LOOKBACK_H", "48"))
                if lookback_h is None
                else float(lookback_h)
            )
        except Exception:
            lb_h = 48.0
        try:
            max_n = (
                int(os.getenv("AI_QUANT_SIGNAL_BACKFILL_MAX_TRADES", "2000")) if max_trades is None else int(max_trades)
            )
        except Exception:
            max_n = 2000
        max_n = int(max(0, min(max_n, 200000)))

        if lb_h <= 0 or max_n <= 0:
            return 0

        dedup_ms = int(self._signal_backfill_dedup_ms() if dedup_s is None else max(0.0, float(dedup_s)) * 1000.0)

        now = now_ms()
        cutoff_ms = int(now - (lb_h * 60.0 * 60.0 * 1000.0))
        keep_from_ms = int(cutoff_ms - max(0, dedup_ms))

        # Keep this non-blocking.
        try:
            timeout_s = float(os.getenv("AI_QUANT_OMS_DB_TIMEOUT_S", "1.0"))
        except Exception:
            timeout_s = 1.0
        timeout_s = float(max(0.05, min(5.0, timeout_s)))

        inserted = 0
        conn = sqlite3.connect(self.store._db_path, timeout=timeout_s)
        cur = conn.cursor()
        try:
            # Build an in-memory view of recent signals for de-dupe.
            existing: dict[str, list[tuple[int, str]]] = {}
            try:
                cur.execute("SELECT timestamp, symbol, signal FROM signals ORDER BY id DESC LIMIT 20000")
                for ts0, sym0, sig0 in cur.fetchall() or []:
                    ms0 = _coerce_ts_ms(ts0)
                    if ms0 is None or int(ms0) < keep_from_ms:
                        continue
                    su = str(sym0 or "").strip().upper()
                    sg = str(sig0 or "").strip().upper()
                    if not su or sg not in {"BUY", "SELL"}:
                        continue
                    existing.setdefault(su, []).append((int(ms0), sg))
            except Exception:
                existing = {}

            cur.execute(
                """
                SELECT id, timestamp, symbol, type, action, price, confidence, reason, meta_json
                FROM trades
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(max_n),),
            )
            rows = cur.fetchall() or []

            for _id, ts_iso, sym, pos_type, action, price, conf, reason, meta_json in rows:
                t_ms = _coerce_ts_ms(ts_iso)
                if t_ms is None:
                    continue
                t_ms_i = int(t_ms)
                if t_ms_i < cutoff_ms:
                    break

                sym_u = str(sym or "").strip().upper()
                if not sym_u:
                    continue

                ac = str(action or "").strip().upper()
                pt = str(pos_type or "").strip().upper()
                rs = str(reason or "")

                # Only backfill entries (and optional flip exits).
                if ac in {"OPEN", "ADD"}:
                    sig = "BUY" if pt == "LONG" else ("SELL" if pt == "SHORT" else "")
                elif ac in {"CLOSE", "REDUCE"} and ("signal flip" in rs.lower()):
                    sig = "SELL" if pt == "LONG" else ("BUY" if pt == "SHORT" else "")
                else:
                    continue

                if sig not in {"BUY", "SELL"}:
                    continue

                # Avoid backfilling obvious manual fills.
                bot_likely = rs.lower().startswith("signal")
                meta_obj = None
                if not bot_likely and meta_json:
                    try:
                        meta_obj = json.loads(meta_json)
                        if isinstance(meta_obj, dict) and (meta_obj.get("order") or meta_obj.get("audit")):
                            bot_likely = True
                    except Exception:
                        meta_obj = None
                if not bot_likely:
                    continue

                # De-dupe vs any nearby existing signal of the same direction.
                if dedup_ms > 0:
                    lst = existing.get(sym_u) or []
                    if any((abs(ms0 - t_ms_i) <= dedup_ms and sg0 == sig) for ms0, sg0 in lst):
                        continue

                # Compact meta: keep audit/order when present.
                meta_sig: dict[str, Any] = {"backfill": {"source": "trades_scan", "trade_id": int(_id)}}
                if isinstance(meta_obj, dict):
                    if isinstance(meta_obj.get("audit"), dict):
                        meta_sig["audit"] = meta_obj.get("audit")
                    if isinstance(meta_obj.get("order"), dict):
                        meta_sig["order"] = meta_obj.get("order")
                meta_json2 = json_dumps_safe(meta_sig) if meta_sig else None

                try:
                    cur.execute(
                        """
                        INSERT INTO signals (timestamp, symbol, signal, confidence, price, rsi, ema_fast, ema_slow, meta_json, run_fingerprint)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(ts_iso),
                            sym_u,
                            sig,
                            str(conf or "").strip().lower() or "n/a",
                            float(price or 0.0),
                            None,
                            None,
                            None,
                            meta_json2,
                            _current_run_fingerprint(),
                        ),
                    )
                    if cur.rowcount and cur.rowcount > 0:
                        inserted += 1
                        existing.setdefault(sym_u, []).append((t_ms_i, sig))
                except Exception:
                    continue

            conn.commit()
            return int(inserted)
        finally:
            try:
                conn.close()
            except Exception:
                logger.debug("failed to close DB connection after signal backfill", exc_info=True)

    def process_user_fills(self, *, trader: Any, fills: list[dict]) -> int:
        """Persist live fills into trades + OMS tables.

        Returns the number of NEW fills inserted into trades (deduped).
        """
        if not fills:
            self.last_ingest_stats = {
                "success": True,
                "total_in": 0,
                "considered": 0,
                "inserted_trades": 0,
                "unmatched_new": 0,
            }
            return 0

        inserted = 0
        unmatched_new = 0
        deduped_trades = 0
        inserted_oms_fills = 0
        deduped_oms_fills = 0
        considered = 0
        run_fingerprint = _current_run_fingerprint()
        unmatched_samples: list[dict[str, Any]] = []
        # Buffer notifications until AFTER the sqlite commit succeeds.
        notify_rows: list[dict[str, Any]] = []

        # Snapshot account value once.
        try:
            account_value = float(getattr(trader, "get_live_balance", lambda: 0.0)() or 0.0)
        except Exception:
            account_value = 0.0

        # Snapshot positions once for leverage fallback.
        try:
            pos_snap = trader.executor.get_positions(force=False) or {}
        except Exception:
            pos_snap = {}

        # Keep this fast: the daemon buffers WS fills on failure and REST backfill can recover.
        # A large sqlite timeout here can stall the main loop for 10s+ under lock contention.
        try:
            timeout_s = float(os.getenv("AI_QUANT_OMS_DB_TIMEOUT_S", "1.0"))
        except Exception:
            timeout_s = 1.0
        timeout_s = float(max(0.05, min(5.0, timeout_s)))
        conn = None
        cur = None
        live_trader = None
        try:
            try:
                import live.trader as _lt

                live_trader = _lt
            except Exception:
                live_trader = None

            conn = sqlite3.connect(self.store._db_path, timeout=timeout_s)
            cur = conn.cursor()

            # Cache trades schema once.
            try:
                cur.execute("PRAGMA table_info(trades)")
                cols = {r[1] for r in cur.fetchall()}
            except Exception:
                cols = set()
            has_dedupe = {"fill_hash", "fill_tid"}.issubset(cols)
            has_meta = "meta_json" in cols

            # In-memory cache: map exchange_order_id → intent_id within this batch.
            # Handles partial fills in the same batch where the oid backfill is uncommitted.
            _oid_intent_cache: dict[str, str] = {}

            for f in fills:
                if not isinstance(f, dict):
                    continue

                try:
                    sym = str(f.get("coin") or "").strip().upper()
                except Exception:
                    sym = ""
                if not sym:
                    continue

                tid = _safe_int(f.get("tid"), None)
                fill_hash = str(f.get("hash") or "").strip() or None

                t_ms = _safe_int(f.get("time"), None)
                if t_ms is None or t_ms <= 0:
                    t_ms = int(time.time() * 1000)

                # Capture raw ws event for audit/debug.
                try:
                    cur.execute(
                        "INSERT INTO ws_events (ts, channel, data_json) VALUES (?, ?, ?)",
                        (int(t_ms), "userFills", json.dumps(f, separators=(",", ":"), sort_keys=True, default=str)),
                    )
                except Exception:
                    logger.debug("failed to insert ws_events row for fill %s", sym, exc_info=True)

                px = _safe_float(f.get("px"), None)
                sz = _safe_float(f.get("sz"), None)
                if px is None or sz is None or px <= 0 or sz <= 0:
                    continue

                considered += 1

                dir_s = str(f.get("dir") or "")
                start_pos = _safe_float(f.get("startPosition"), 0.0) or 0.0
                pos_type, action = _dir_to_action(dir_s, float(start_pos), float(sz))
                if pos_type is None or action is None:
                    continue

                side = _action_side(pos_type, action)
                if side is None:
                    continue

                fee = _safe_float(f.get("fee"), 0.0) or 0.0
                closed_pnl = _safe_float(f.get("closedPnl"), 0.0) or 0.0
                pnl = closed_pnl

                # OMS intent matching — check batch cache first (partial fills with same oid).
                _oid = self._extract_exchange_order_id_from_fill(f)
                if _oid and _oid in _oid_intent_cache:
                    intent_id = _oid_intent_cache[_oid]
                    matched_via = "exchange_order_id_batch"
                else:
                    intent_id, matched_via = self.match_intent_for_fill(
                        fill=f, symbol=sym, action=action, side=side, t_ms=int(t_ms)
                    )
                    # Populate cache for subsequent partial fills in this batch.
                    if intent_id and _oid:
                        _oid_intent_cache[_oid] = intent_id

                # Context for trade enrichment.
                ctx: dict[str, Any] = {}
                if intent_id:
                    intent_fields = self.store.get_intent_fields(intent_id) or {}
                    ctx["confidence"] = intent_fields.get("confidence")
                    ctx["reason"] = intent_fields.get("reason")
                    ctx["entry_atr"] = intent_fields.get("entry_atr")
                    ctx["leverage"] = intent_fields.get("leverage")
                    # Merge intent meta_json into ctx.meta for downstream audit.
                    try:
                        mj = intent_fields.get("meta_json")
                        if mj:
                            ctx_meta = json.loads(mj)
                            if isinstance(ctx_meta, dict):
                                ctx["meta"] = ctx_meta
                                rc = str(ctx_meta.get("reason_code") or "").strip().lower()
                                if rc:
                                    ctx["reason_code"] = rc
                    except (json.JSONDecodeError, TypeError):
                        logger.debug("failed to parse intent meta_json for fill context", exc_info=True)

                # Fallback to the in-memory pending ctx (best for immediate fills).
                if (not ctx.get("confidence")) or (not ctx.get("reason")) or (not ctx.get("reason_code")):
                    try:
                        pop = getattr(trader, "pop_pending", None)
                        if callable(pop):
                            ctx2 = pop(sym) or {}
                            if isinstance(ctx2, dict):
                                for k in ("confidence", "reason", "reason_code", "entry_atr", "leverage", "meta"):
                                    if ctx.get(k) is None and ctx2.get(k) is not None:
                                        ctx[k] = ctx2.get(k)
                    except Exception:
                        logger.debug("failed to pop pending context for %s", sym, exc_info=True)

                conf = str(ctx.get("confidence") or "N/A")
                entry_atr = _safe_float(ctx.get("entry_atr"), None)
                lev = _safe_float(ctx.get("leverage"), None)
                if lev is None or lev <= 0:
                    lev_raw = f.get("leverage")
                    if isinstance(lev_raw, dict):
                        lev = _safe_float(lev_raw.get("value"), None)
                    else:
                        lev = _safe_float(lev_raw, None)
                if lev is None or lev <= 0:
                    try:
                        lev = _safe_float(
                            ((getattr(trader, "positions", {}) or {}).get(sym) or {}).get("leverage"), None
                        )
                    except Exception:
                        lev = None
                if lev is None or lev <= 0:
                    try:
                        lev = _safe_float((pos_snap.get(sym) or {}).get("leverage"), None)
                    except Exception:
                        lev = None

                notional = abs(float(sz)) * float(px)
                fee_token = str(f.get("feeToken") or "").strip() or None
                fee_rate = (fee / notional) if notional > 0 else None
                margin_used = (notional / lev) if lev and lev > 0 else None

                ts_iso = datetime.datetime.fromtimestamp(int(t_ms) / 1000.0, tz=datetime.timezone.utc).isoformat()
                reason = str(ctx.get("reason") or f"LIVE_FILL {dir_s}").strip()
                reason_code = str(ctx.get("reason_code") or "").strip().lower()
                if not reason_code:
                    try:
                        ctx_meta = ctx.get("meta")
                        if isinstance(ctx_meta, dict):
                            reason_code = str(ctx_meta.get("reason_code") or "").strip().lower()
                    except Exception:
                        reason_code = ""
                if not reason_code:
                    reason_code = _canonical_reason_code(action, pos_type, reason)

                # Enrich meta_json. Always include the raw fill and OMS correlation.
                meta: dict[str, Any] = {}
                try:
                    if isinstance(ctx.get("meta"), dict):
                        meta.update(ctx.get("meta") or {})
                except Exception:
                    logger.debug("failed to merge pending ctx meta for %s", sym, exc_info=True)
                if reason_code and not str(meta.get("reason_code") or "").strip():
                    meta["reason_code"] = reason_code

                meta.setdefault("fill", f)
                meta.setdefault("oms", {})
                if isinstance(meta.get("oms"), dict):
                    meta["oms"].update(
                        {
                            "intent_id": intent_id,
                            "matched_via": matched_via,
                            "client_order_id": self._extract_client_order_id_from_fill(f),
                            "exchange_order_id": self._extract_exchange_order_id_from_fill(f),
                        }
                    )

                meta_json = json_dumps_safe(meta) if meta else None

                # Insert into OMS fills (deduped separately from trades) using the same cursor.
                oms_fill_inserted = False
                try:
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO oms_fills (
                            ts_ms, symbol, intent_id, action, side, pos_type,
                            price, size, notional,
                            fee_usd, fee_token, fee_rate, pnl_usd,
                            fill_hash, fill_tid,
                            matched_via, raw_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            int(t_ms),
                            str(sym),
                            intent_id,
                            action,
                            side,
                            pos_type,
                            float(px),
                            float(sz),
                            float(notional),
                            float(fee),
                            fee_token,
                            fee_rate,
                            float(pnl),
                            fill_hash,
                            tid,
                            matched_via,
                            json_dumps_safe(f),
                        ),
                    )
                    if cur.rowcount and cur.rowcount > 0:
                        oms_fill_inserted = True
                        inserted_oms_fills += 1
                    else:
                        deduped_oms_fills += 1
                except Exception:
                    logger.debug("OMS fill insert/dedupe failed for %s", sym, exc_info=True)

                # Best-effort: if we matched an intent, attach the exchange order id from the fill (oid).
                try:
                    oid = self._extract_exchange_order_id_from_fill(f)
                    if intent_id and oid:
                        cur.execute(
                            "UPDATE oms_intents SET exchange_order_id = COALESCE(exchange_order_id, ?) WHERE intent_id = ?",
                            (str(oid), str(intent_id)),
                        )
                except Exception:
                    logger.debug("failed to attach exchange_order_id to OMS intent for %s", sym, exc_info=True)

                # Insert into trades (dedupe if schema supports it).
                if has_dedupe:
                    if has_meta:
                        cur.execute(
                            """
                            INSERT OR IGNORE INTO trades (
                                timestamp, symbol, type, action, price, size, notional, reason, confidence,
                                reason_code, pnl, fee_usd, fee_token, fee_rate, balance, entry_atr, leverage, margin_used,
                                meta_json, run_fingerprint, fill_hash, fill_tid
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                ts_iso,
                                sym,
                                pos_type,
                                action,
                                float(px),
                                float(sz),
                                float(notional),
                                reason,
                                conf,
                                reason_code,
                                float(pnl),
                                float(fee),
                                fee_token,
                                fee_rate,
                                float(account_value),
                                entry_atr,
                                lev,
                                margin_used,
                                meta_json,
                                run_fingerprint,
                                fill_hash,
                                tid,
                            ),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT OR IGNORE INTO trades (
                                timestamp, symbol, type, action, price, size, notional, reason, confidence,
                                reason_code, pnl, fee_usd, fee_token, fee_rate, balance, entry_atr, leverage, margin_used,
                                run_fingerprint, fill_hash, fill_tid
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                ts_iso,
                                sym,
                                pos_type,
                                action,
                                float(px),
                                float(sz),
                                float(notional),
                                reason,
                                conf,
                                reason_code,
                                float(pnl),
                                float(fee),
                                fee_token,
                                fee_rate,
                                float(account_value),
                                entry_atr,
                                lev,
                                margin_used,
                                run_fingerprint,
                                fill_hash,
                                tid,
                            ),
                        )
                else:
                    if has_meta:
                        cur.execute(
                            """
                            INSERT INTO trades (
                                timestamp, symbol, type, action, price, size, notional, reason, confidence,
                                reason_code, pnl, fee_usd, fee_token, fee_rate, balance, entry_atr, leverage, margin_used, meta_json, run_fingerprint
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                ts_iso,
                                sym,
                                pos_type,
                                action,
                                float(px),
                                float(sz),
                                float(notional),
                                reason,
                                conf,
                                reason_code,
                                float(pnl),
                                float(fee),
                                fee_token,
                                fee_rate,
                                float(account_value),
                                entry_atr,
                                lev,
                                margin_used,
                                meta_json,
                                run_fingerprint,
                            ),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO trades (
                                timestamp, symbol, type, action, price, size, notional, reason, confidence,
                                reason_code, pnl, fee_usd, fee_token, fee_rate, balance, entry_atr, leverage, margin_used, run_fingerprint
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                ts_iso,
                                sym,
                                pos_type,
                                action,
                                float(px),
                                float(sz),
                                float(notional),
                                reason,
                                conf,
                                reason_code,
                                float(pnl),
                                float(fee),
                                fee_token,
                                fee_rate,
                                float(account_value),
                                entry_atr,
                                lev,
                                margin_used,
                                run_fingerprint,
                            ),
                        )

                trade_inserted = bool(cur.rowcount and cur.rowcount > 0)
                if trade_inserted:
                    inserted += 1
                    if intent_id is None:
                        unmatched_new += 1
                        _unmatched_oid = self._extract_exchange_order_id_from_fill(f)
                        _unmatched_cloid = self._extract_client_order_id_from_fill(f)
                        print(
                            f"OMS WARN unmatched fill: {sym} {action} {side} "
                            f"oid={_unmatched_oid} cloid={_unmatched_cloid} "
                            f"hash={fill_hash} tid={tid} t_ms={t_ms}"
                        )
                        if len(unmatched_samples) < 5:
                            try:
                                unmatched_samples.append(
                                    {
                                        "symbol": sym,
                                        "action": action,
                                        "side": side,
                                        "t_ms": int(t_ms),
                                        "fill_hash": fill_hash,
                                        "fill_tid": tid,
                                        "exchange_order_id": _unmatched_oid,
                                        "client_order_id": _unmatched_cloid,
                                    }
                                )
                            except Exception:
                                logger.debug("unmatched_fills audit event failed for %s", sym, exc_info=True)
                else:
                    deduped_trades += 1

                # Backfill a strategy signal for live monitoring when applicable.
                # This is safe to run even on REST replays because we de-dupe within a time window.
                if action in {"OPEN", "ADD"}:
                    # Prefer the explicit strategy signal if present in meta.order, else infer from side.
                    sig2 = None
                    try:
                        if isinstance(meta.get("order"), dict):
                            sig2 = meta.get("order", {}).get("signal")
                    except (TypeError, KeyError):
                        sig2 = None
                    sig2_u = str(sig2 or side or "").strip().upper()
                    try:
                        self._maybe_insert_signal(
                            cur=cur,
                            sym=sym,
                            ts_iso=ts_iso,
                            t_ms=int(t_ms),
                            signal=sig2_u,
                            confidence=conf,
                            price=float(px),
                            reason=reason,
                            intent_id=intent_id,
                            matched_via=matched_via,
                            meta=meta,
                        )
                    except Exception:
                        logger.debug("failed to backfill signal for %s", sym, exc_info=True)

                # If we matched an intent, update its status.
                if intent_id:
                    try:
                        cur.execute(
                            "SELECT requested_size FROM oms_intents WHERE intent_id = ? LIMIT 1",
                            (str(intent_id),),
                        )
                        row = cur.fetchone()
                        req_sz = _safe_float(row[0], None) if row else None
                        cur.execute(
                            "SELECT COALESCE(SUM(size), 0) FROM oms_fills WHERE intent_id = ?",
                            (str(intent_id),),
                        )
                        row2 = cur.fetchone()
                        filled = float(row2[0] or 0.0) if row2 else 0.0
                        if action == "CLOSE":
                            cur.execute(
                                "UPDATE oms_intents SET status = 'FILLED', last_error = '' WHERE intent_id = ?",
                                (str(intent_id),),
                            )
                        elif req_sz is not None and req_sz > 0 and filled >= (req_sz * 0.999):
                            cur.execute(
                                "UPDATE oms_intents SET status = 'FILLED', last_error = '' WHERE intent_id = ?",
                                (str(intent_id),),
                            )
                        else:
                            cur.execute(
                                "UPDATE oms_intents SET status = 'PARTIAL', last_error = '' WHERE intent_id = ?",
                                (str(intent_id),),
                            )
                    except Exception:
                        logger.debug("failed to update OMS intent status for %s", sym, exc_info=True)

                # Notifications/logging should be idempotent. REST backfill replays fills.
                # Only announce when the fill was newly persisted (OMS or trades).
                if trade_inserted or oms_fill_inserted:
                    notify_rows.append(
                        {
                            "symbol": sym,
                            "action": action,
                            "pos_type": pos_type,
                            "t_ms": int(t_ms),
                            "side": side,
                            "price": float(px),
                            "size": float(sz),
                            "notional": float(notional),
                            "leverage": lev,
                            "margin_used": margin_used,
                            "fee": float(fee),
                            "fee_rate": fee_rate,
                            "fee_token": fee_token,
                            "pnl": float(pnl),
                            "reason": reason,
                            "confidence": conf,
                            "account_value": float(account_value or 0.0),
                            "withdrawable": float(getattr(trader, "balance", 0.0) or 0.0),
                        }
                    )

                # Update in-memory strategy state on opens.
                try:
                    if (
                        (trade_inserted or oms_fill_inserted)
                        and action == "OPEN"
                        and sym in (getattr(trader, "positions", {}) or {})
                    ):
                        pos = trader.positions[sym]
                        pos["confidence"] = conf
                        if entry_atr is not None and entry_atr > 0:
                            pos["entry_atr"] = float(entry_atr)
                        pos["open_timestamp"] = ts_iso
                        if fill_hash is not None and tid is not None:
                            cur.execute(
                                "SELECT id FROM trades WHERE fill_hash = ? AND fill_tid = ? LIMIT 1", (fill_hash, tid)
                            )
                            row = cur.fetchone()
                            if row and row[0]:
                                pos["open_trade_id"] = int(row[0])
                                upsert = getattr(trader, "upsert_position_state", None)
                                if callable(upsert):
                                    upsert(sym)
                except Exception:
                    logger.debug("failed to update in-memory position state for %s", sym, exc_info=True)

            conn.commit()

            # After commit: update in-memory risk state. This must never throw and must only
            # run for newly-ingested fills (notify_rows is deduped alongside DB inserts).
            try:
                risk = getattr(trader, "risk", None)
                note = getattr(risk, "note_fill", None) if risk is not None else None
                if callable(note):
                    for row in notify_rows:
                        ref_mid = None
                        ref_bid = None
                        ref_ask = None
                        try:
                            import exchange.ws as hyperliquid_ws

                            sym_u = str(row.get("symbol") or "").strip().upper()
                            bbo = hyperliquid_ws.hl_ws.get_bbo(sym_u, max_age_s=10.0)
                            if bbo is not None:
                                ref_bid, ref_ask = float(bbo[0]), float(bbo[1])
                            ref_mid = hyperliquid_ws.hl_ws.get_mid(sym_u, max_age_s=10.0)
                            if ref_mid is not None:
                                ref_mid = float(ref_mid)
                        except Exception:
                            ref_mid = None
                            ref_bid = None
                            ref_ask = None
                        try:
                            note(
                                ts_ms=int(row.get("t_ms") or 0),
                                symbol=str(row.get("symbol") or ""),
                                action=str(row.get("action") or ""),
                                pnl_usd=float(row.get("pnl") or 0.0),
                                fee_usd=float(row.get("fee") or 0.0),
                                fill_price=float(row.get("price") or 0.0),
                                side=str(row.get("side") or ""),
                                ref_mid=ref_mid,
                                ref_bid=ref_bid,
                                ref_ask=ref_ask,
                            )
                        except Exception:
                            logger.debug("risk.note_fill failed for %s", row.get("symbol"), exc_info=True)
                            continue
            except Exception:
                logger.debug("post-commit risk state update failed", exc_info=True)

            # After commit: send notifications and console logs once per new fill.
            if notify_rows:
                for row in notify_rows:
                    # Notifications (reuse existing live notifier if present).
                    if live_trader is not None:
                        try:
                            live_trader._notify_live_fill(
                                symbol=row["symbol"],
                                action=row["action"],
                                pos_type=row["pos_type"],
                                price=float(row["price"]),
                                size=float(row["size"]),
                                notional=float(row["notional"]),
                                leverage=row.get("leverage"),
                                margin_used_usd=row.get("margin_used"),
                                fee_usd=float(row["fee"]),
                                fee_rate=row.get("fee_rate"),
                                fee_token=row.get("fee_token"),
                                pnl_usd=float(row["pnl"]),
                                reason=str(row.get("reason") or ""),
                                confidence=str(row.get("confidence") or "N/A"),
                                account_value_usd=float(row.get("account_value") or 0.0),
                                withdrawable_usd=float(row.get("withdrawable") or 0.0),
                            )
                        except Exception:
                            logger.debug("fill notification send failed for %s", row.get("symbol"), exc_info=True)

                    # Console
                    lev = row.get("leverage")
                    margin_used = row.get("margin_used")
                    try:
                        lev_s = "NA" if lev is None or float(lev) <= 0 else f"{float(lev):.0f}x"
                    except (TypeError, ValueError):
                        lev_s = "NA"
                    try:
                        margin_s = "NA" if margin_used is None else f"${float(margin_used):.2f}"
                    except (TypeError, ValueError):
                        margin_s = "NA"
                    try:
                        print(
                            f"📥 LIVE FILL {row['action']} {row['pos_type']} {row['symbol']} px={float(row['price']):.4f} "
                            f"size={float(row['size']):.6f} notional=${float(row['notional']):.2f} "
                            f"lev={lev_s} margin~={margin_s} fee=${float(row['fee']):.4f} pnl=${float(row['pnl']):.2f} "
                            f"conf={row.get('confidence', 'N/A')} reason={row.get('reason', '')}"
                        )
                    except Exception:
                        logger.debug("fill console print failed", exc_info=True)

            # After commit: update kernel state from confirmed fills and reconcile positions.
            # Only newly-inserted fills (notify_rows) are processed — OMS fill_hash dedup
            # (INSERT OR IGNORE) prevents double-counting in the kernel.
            if notify_rows:
                try:
                    self._update_kernel_for_fills(notify_rows, trader)
                except Exception:
                    logger.warning("_update_kernel_for_fills failed", exc_info=True)

        except Exception as e:
            try:
                if conn is not None:
                    conn.rollback()
            except Exception:
                logger.debug("rollback failed after fill processing error", exc_info=True)
            self.last_ingest_stats = {
                "success": False,
                "error": str(e),
                "total_in": len(fills),
                "considered": int(considered),
                "inserted_trades": int(inserted),
                "deduped_trades": int(deduped_trades),
                "unmatched_new": int(unmatched_new),
                "inserted_oms_fills": int(inserted_oms_fills),
                "deduped_oms_fills": int(deduped_oms_fills),
                "unmatched_samples": unmatched_samples,
            }
            raise
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                logger.debug("failed to close OMS DB connection after fill processing", exc_info=True)

        self.last_ingest_stats = {
            "success": True,
            "total_in": len(fills),
            "considered": int(considered),
            "inserted_trades": int(inserted),
            "deduped_trades": int(deduped_trades),
            "unmatched_new": int(unmatched_new),
            "inserted_oms_fills": int(inserted_oms_fills),
            "deduped_oms_fills": int(deduped_oms_fills),
            "unmatched_samples": unmatched_samples,
        }
        return inserted

    # ------------------------------------------------------------------
    # Kernel fill reconciliation
    # ------------------------------------------------------------------

    def _update_kernel_for_fills(self, notify_rows: list[dict], trader: Any) -> None:
        """Update kernel state from confirmed fills and reconcile positions.

        For each newly-inserted fill, a MarketEvent is constructed and fed to
        the kernel via ``bt_runtime.step_full()``.  After all fills are
        processed the kernel state is persisted and positions are compared
        with the trader's live positions.

        Dedup safety: this method is only called for fills that passed the
        INSERT OR IGNORE dedup (``notify_rows``), so the kernel is updated at
        most once per fill.
        """
        kp = self.kernel_provider
        if kp is None:
            return
        runtime = getattr(kp, "_runtime", None)
        state_json = getattr(kp, "_state_json", None)
        params_json = getattr(kp, "_params_json", None)
        if runtime is None or state_json is None or params_json is None:
            return

        step_full_fn = getattr(runtime, "step_full", None)
        if not callable(step_full_fn):
            return

        updated = False
        for row in notify_rows:
            try:
                symbol = str(row.get("symbol") or "").strip().upper()
                if not symbol:
                    continue
                price = float(row.get("price") or 0)
                if price <= 0:
                    continue
                side = str(row.get("side") or "").strip().upper()
                if side not in ("BUY", "SELL"):
                    continue
                t_ms = int(row.get("t_ms") or 0)
                if t_ms <= 0:
                    t_ms = int(time.time() * 1000)

                event = {
                    "schema_version": 1,
                    "event_id": t_ms,
                    "timestamp_ms": t_ms,
                    "symbol": symbol,
                    "signal": side,
                    "price": price,
                }
                result_json = step_full_fn(
                    state_json,
                    json.dumps(event),
                    params_json,
                    "{}",
                )
                result = json.loads(result_json)
                if result.get("ok") and "decision" in result:
                    new_state = result["decision"].get("state")
                    if new_state is not None:
                        state_json = json.dumps(new_state) if isinstance(new_state, dict) else str(new_state)
                        updated = True
                else:
                    err = result.get("error", {})
                    logger.debug(
                        "[kernel-reconcile] step rejected for %s: %s",
                        symbol,
                        err.get("message", str(result_json)[:200]),
                    )
            except Exception as exc:
                logger.warning("[kernel-reconcile] step_full failed for fill: %s", exc)

        if updated:
            kp._state_json = state_json
            try:
                persist = getattr(kp, "_persist_state", None)
                if callable(persist):
                    persist(state_json)
            except Exception as exc:
                logger.warning("[kernel-reconcile] failed to persist kernel state: %s", exc)

        # Reconcile kernel positions with trader/exchange positions.
        try:
            self._reconcile_kernel_positions(state_json, trader)
        except Exception as exc:
            logger.warning("[kernel-reconcile] position reconciliation failed: %s", exc)

    def _reconcile_kernel_positions(self, state_json: str, trader: Any) -> None:
        """Compare kernel positions with trader's live positions and log discrepancies."""
        try:
            state = json.loads(state_json)
        except Exception:
            return
        kernel_positions = state.get("positions")
        if not isinstance(kernel_positions, dict):
            return

        trader_positions = getattr(trader, "positions", None)
        if not isinstance(trader_positions, dict):
            return

        # Collect all symbols from both sides.
        all_symbols = set(kernel_positions.keys()) | set(trader_positions.keys())

        for sym in sorted(all_symbols):
            kp = kernel_positions.get(sym)
            tp = trader_positions.get(sym)

            # Kernel has position, trader doesn't.
            if kp and not tp:
                k_qty = float(kp.get("quantity") or 0)
                k_side = str(kp.get("side") or "").upper()
                if k_qty > 1e-9:
                    logger.warning(
                        "[kernel-reconcile] MISMATCH %s: kernel has %s qty=%.6f but trader has no position",
                        sym,
                        k_side,
                        k_qty,
                    )
                continue

            # Trader has position, kernel doesn't.
            if tp and not kp:
                t_qty = float(tp.get("size") or 0)
                t_side = str(tp.get("type") or "").upper()
                if t_qty > 1e-9:
                    logger.warning(
                        "[kernel-reconcile] MISMATCH %s: trader has %s qty=%.6f but kernel has no position",
                        sym,
                        t_side,
                        t_qty,
                    )
                continue

            # Both have positions — compare qty, entry price, and side.
            if kp and tp:
                k_qty = float(kp.get("quantity") or 0)
                k_entry = float(kp.get("avg_entry_price") or 0)
                k_side = str(kp.get("side") or "").strip().lower()

                t_qty = float(tp.get("size") or 0)
                t_entry = float(tp.get("entry_price") or 0)
                t_side = str(tp.get("type") or "").strip().lower()

                qty_diff = abs(k_qty - t_qty)
                entry_diff = abs(k_entry - t_entry) if (k_entry > 0 and t_entry > 0) else 0

                # Tolerance: 0.1% for qty, 0.5% for entry price.
                qty_tol = max(k_qty, t_qty) * 0.001 if max(k_qty, t_qty) > 0 else 1e-9
                entry_tol = max(k_entry, t_entry) * 0.005 if max(k_entry, t_entry) > 0 else 0

                side_mismatch = k_side != t_side
                qty_mismatch = qty_diff > qty_tol
                entry_mismatch = entry_diff > entry_tol

                if side_mismatch or qty_mismatch or entry_mismatch:
                    logger.warning(
                        "[kernel-reconcile] MISMATCH %s: kernel(%s qty=%.6f entry=%.2f) vs "
                        "trader(%s qty=%.6f entry=%.2f)",
                        sym,
                        k_side,
                        k_qty,
                        k_entry,
                        t_side,
                        t_qty,
                        t_entry,
                    )
