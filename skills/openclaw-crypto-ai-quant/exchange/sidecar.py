from __future__ import annotations

import json
import os
import socket
import sqlite3
import threading
from dataclasses import dataclass
from typing import Any

import logging

import pandas as pd

logger = logging.getLogger(__name__)

_NO_RETRY_RPC_METHODS = {
    "drain_user_fills",
    "drain_order_updates",
    "drain_user_fundings",
    "drain_user_ledger_updates",
}


@dataclass(frozen=True)
class WsHealth:
    mids_age_s: float | None
    candle_age_s: float | None
    bbo_age_s: float | None


def _default_sock_path() -> str:
    xdg = os.getenv("XDG_RUNTIME_DIR", "").strip()
    if xdg:
        return os.path.join(xdg, "openclaw-ai-quant-ws.sock")
    return "/tmp/openclaw-ai-quant-ws.sock"


def _market_db_path() -> str:
    # Prefer a shared market DB when configured; fall back to the trading DB path.
    here = os.path.dirname(os.path.abspath(__file__))
    return str(
        os.getenv("AI_QUANT_MARKET_DB_PATH")
        or os.getenv("AI_QUANT_DB_PATH")
        or os.path.join(here, "..", "trading_engine.db")
    )


def _candles_db_dir() -> str:
    raw = str(os.getenv("AI_QUANT_CANDLES_DB_DIR", "") or "").strip()
    if raw:
        return raw
    base = _market_db_path()
    try:
        parent = os.path.dirname(os.path.abspath(base))
        return os.path.join(parent, "candles_dbs")
    except Exception:
        return "candles_dbs"


def _sanitize_interval(interval: str) -> str:
    out = []
    for ch in str(interval or ""):
        if ("0" <= ch <= "9") or ("a" <= ch.lower() <= "z"):
            out.append(ch.lower())
        else:
            out.append("_")
    s = "".join(out).strip("_")
    return s if s else "unknown"


def _candles_db_path(interval: str) -> str:
    name = _sanitize_interval(interval)
    return os.path.join(_candles_db_dir(), f"candles_{name}.db")


def _default_client_id() -> str:
    mode = str(os.getenv("AI_QUANT_MODE", "paper") or "paper").strip().lower() or "paper"
    return f"{mode}:{os.getpid()}"


def _client_id() -> str:
    raw = str(os.getenv("AI_QUANT_WS_CLIENT_ID", "") or "").strip()
    return raw if raw else _default_client_id()


def _db_timeout_s() -> float:
    raw = os.getenv("AI_QUANT_DB_TIMEOUT_S", "30")
    try:
        return float(raw)
    except Exception:
        return 30.0


class SidecarWSClient:
    """Client shim that mimics the `HyperliquidWS` API but delegates to a local sidecar.

    Transport: Unix domain socket with newline-delimited JSON (one request -> one response).

    The goal is to let existing code continue calling `hyperliquid_ws.hl_ws.*` even when
    `AI_QUANT_WS_SOURCE=sidecar`, without opening a direct outbound WS connection.
    """

    def __init__(self, *, sock_path: str | None = None):
        self._sock_path = str(sock_path or os.getenv("AI_QUANT_WS_SIDECAR_SOCK") or _default_sock_path())
        self._lock = threading.RLock()
        self._sock: socket.socket | None = None
        self._f = None
        self._next_id = 1

        self._market_db_path = _market_db_path()
        self._candles_db_dir = _candles_db_dir()
        self._db_timeout_s = float(_db_timeout_s())
        self._client_id = _client_id()

        # Best-effort connectivity indicator.
        self._connected = False
        self._was_connected = False  # Track previous state for reconnection detection
        self._disconnect_ts: float | None = None  # Monotonic time of last disconnect

    def _connect(self, *, timeout_s: float) -> None:
        if self._sock is not None:
            return
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(float(timeout_s))
        s.connect(self._sock_path)
        # Use a buffered file for line I/O.
        f = s.makefile("rwb")
        self._sock = s
        self._f = f
        self._rpc_timeout_s = float(timeout_s)

        # Detect reconnection after a previous disconnect.
        reconnected = self._was_connected and not self._connected
        self._connected = True
        self._was_connected = True

        if reconnected and self._disconnect_ts is not None:
            import time as _time

            gap_s = _time.monotonic() - self._disconnect_ts
            if gap_s > 5.0:
                logger.warning(
                    "sidecar reconnected after %.0fs disconnect — candle gaps possible, signals may use stale data until backfill completes",
                    gap_s,
                )
            self._disconnect_ts = None

    def _close(self) -> None:
        try:
            if self._f is not None:
                try:
                    self._f.close()
                except Exception:
                    pass
        finally:
            self._f = None

        try:
            if self._sock is not None:
                try:
                    self._sock.close()
                except Exception:
                    pass
        finally:
            self._sock = None
            if self._connected:
                import time as _time

                self._disconnect_ts = _time.monotonic()
            self._connected = False

    @staticmethod
    def _is_retryable_rpc_exception(err: Exception) -> bool:
        if isinstance(err, (ConnectionError, TimeoutError, socket.timeout, OSError, json.JSONDecodeError)):
            return True
        if isinstance(err, RuntimeError):
            msg = str(err).strip().lower()
            if "connection broken" in msg or "sidecar closed" in msg:
                return True
        return False

    def _rpc(self, method: str, params: dict[str, Any] | None = None, *, timeout_s: float = 2.0) -> Any:
        # Single-flight RPC (locked) keeps client logic simple and avoids response demuxing.
        with self._lock:
            for attempt in (1, 2):
                raw = b""
                try:
                    self._connect(timeout_s=float(timeout_s))
                    # Re-assert socket timeout before each RPC to guard against
                    # partial reads that could block indefinitely.
                    if self._sock is not None:
                        self._sock.settimeout(getattr(self, "_rpc_timeout_s", float(timeout_s)))
                    rid = int(self._next_id)
                    self._next_id += 1
                    req = {"id": rid, "method": str(method), "params": params or {}}
                    line = (json.dumps(req, separators=(",", ":")) + "\n").encode("utf-8")
                    if self._f is None:
                        raise RuntimeError("sidecar connection broken")
                    self._f.write(line)
                    self._f.flush()

                    raw = self._f.readline()
                    if not raw:
                        raise ConnectionError("sidecar closed")
                    resp = json.loads(raw.decode("utf-8", errors="strict"))
                    if int(resp.get("id", -1)) != rid:
                        raise RuntimeError("sidecar response id mismatch")
                    if not bool(resp.get("ok", False)):
                        raise RuntimeError(str(resp.get("error") or "sidecar error"))
                    return resp.get("result")
                except UnicodeDecodeError:
                    preview_hex = raw[:64].hex() if raw else ""
                    logger.error(
                        "sidecar RPC decode failed: method=%s bytes=%d preview_hex=%s",
                        method,
                        len(raw or b""),
                        preview_hex,
                        exc_info=True,
                    )
                    self._close()
                    if attempt == 1 and str(method) not in _NO_RETRY_RPC_METHODS:
                        logger.warning("sidecar RPC reconnect retry: method=%s reason=decode_error", method)
                        continue
                    raise
                except Exception as e:
                    logger.error("sidecar RPC failed: method=%s error=%s", method, e)
                    self._close()
                    if (
                        attempt == 1
                        and str(method) not in _NO_RETRY_RPC_METHODS
                        and self._is_retryable_rpc_exception(e)
                    ):
                        logger.warning("sidecar RPC reconnect retry: method=%s reason=%s", method, type(e).__name__)
                        continue
                    raise

    def ensure_started(self, *, symbols: list[str], interval: str, candle_limit: int, user: str | None = None):
        self._rpc(
            "ensure_started",
            {
                "client_id": self._client_id,
                "symbols": [str(s) for s in (symbols or [])],
                "interval": str(interval),
                "candle_limit": int(candle_limit),
                "user": (str(user).strip() if user is not None else None),
            },
            timeout_s=2.0,
        )

    def restart(self, *, join_timeout_s: float = 5.0) -> None:
        _ = join_timeout_s
        try:
            self._rpc("restart", {}, timeout_s=2.0)
        except Exception:
            # If the sidecar is down, restart is best-effort.
            pass

    def stop(self) -> None:
        # No-op: the sidecar owns the real WS connection.
        self._close()

    def status(self) -> dict[str, bool]:
        running = False
        try:
            self._rpc("health", {}, timeout_s=1.0)
            running = True
        except Exception:
            pass
        return {"running": running, "connected": bool(self._connected)}

    def health(self, *, symbols: list[str], interval: str) -> WsHealth:
        res = self._rpc(
            "health",
            {"symbols": [str(s) for s in (symbols or [])], "interval": str(interval)},
            timeout_s=2.0,
        )
        if not isinstance(res, dict):
            return WsHealth(mids_age_s=None, candle_age_s=None, bbo_age_s=None)
        return WsHealth(
            mids_age_s=res.get("mids_age_s"),
            candle_age_s=res.get("candle_age_s"),
            bbo_age_s=res.get("bbo_age_s"),
        )

    def candles_ready(self, *, symbols: list[str], interval: str) -> tuple[bool, list[str]]:
        res = self._rpc(
            "candles_ready",
            {"symbols": [str(s) for s in (symbols or [])], "interval": str(interval)},
            timeout_s=2.0,
        )
        if not isinstance(res, dict):
            return False, [str(s).upper() for s in (symbols or [])]
        ready = bool(res.get("ready", False))
        not_ready = res.get("not_ready") or []
        if not isinstance(not_ready, list):
            not_ready = []
        return ready, [str(s).upper() for s in not_ready]

    def candles_health(self, *, symbols: list[str], interval: str) -> dict[str, Any] | None:
        res = self._rpc(
            "candles_health",
            {"symbols": [str(s) for s in (symbols or [])], "interval": str(interval)},
            timeout_s=2.0,
        )
        return res if isinstance(res, dict) else None

    def get_mid(self, symbol: str, *, max_age_s: float | None = None) -> float | None:
        res = self._rpc(
            "get_mid",
            {"symbol": str(symbol).upper(), "max_age_s": (float(max_age_s) if max_age_s is not None else None)},
            timeout_s=1.0,
        )
        try:
            return float(res) if res is not None else None
        except Exception:
            return None

    def get_mids(self, *, symbols: list[str], max_age_s: float | None = None) -> tuple[dict[str, float], float | None]:
        res = self._rpc(
            "get_mids",
            {
                "symbols": [str(s).upper() for s in (symbols or [])],
                "max_age_s": (float(max_age_s) if max_age_s is not None else None),
            },
            timeout_s=1.0,
        )
        if not isinstance(res, dict):
            return {}, None
        raw_mids = res.get("mids") or {}
        out: dict[str, float] = {}
        if isinstance(raw_mids, dict):
            for k, v in raw_mids.items():
                try:
                    out[str(k).upper()] = float(v)
                except Exception:
                    continue
        age = res.get("mids_age_s")
        try:
            age_s = float(age) if age is not None else None
        except Exception:
            age_s = None
        return out, age_s

    def wait_mids(
        self,
        *,
        symbols: list[str],
        after_seq: int | None = None,
        max_age_s: float | None = None,
        timeout_s: float = 25.0,
    ) -> tuple[dict[str, float], float | None, int | None, bool, bool]:
        timeout_v = float(timeout_s)
        timeout_ms = int(max(50, min(120_000, round(timeout_v * 1000.0))))
        try:
            res = self._rpc(
                "wait_mids",
                {
                    "symbols": [str(s).upper() for s in (symbols or [])],
                    "after_seq": (int(after_seq) if after_seq is not None else 0),
                    "max_age_s": (float(max_age_s) if max_age_s is not None else None),
                    "timeout_ms": timeout_ms,
                },
                timeout_s=max(1.0, timeout_v + 2.0),
            )
        except RuntimeError as e:
            # Backwards-compatibility: older sidecar versions may not expose wait_mids yet.
            if "unknown method" in str(e).strip().lower():
                mids, age_s = self.get_mids(symbols=symbols, max_age_s=max_age_s)
                return mids, age_s, None, True, False
            raise

        if not isinstance(res, dict):
            return {}, None, None, False, True

        raw_mids = res.get("mids") or {}
        out: dict[str, float] = {}
        if isinstance(raw_mids, dict):
            for k, v in raw_mids.items():
                try:
                    out[str(k).upper()] = float(v)
                except Exception:
                    continue

        age = res.get("mids_age_s")
        try:
            age_s = float(age) if age is not None else None
        except Exception:
            age_s = None

        seq_raw = res.get("mids_seq")
        try:
            seq = int(seq_raw) if seq_raw is not None else None
        except Exception:
            seq = None

        changed = bool(res.get("changed", True))
        timed_out = bool(res.get("timed_out", False))
        return out, age_s, seq, changed, timed_out

    def get_bbo(self, symbol: str, *, max_age_s: float | None = None) -> tuple[float, float] | None:
        res = self._rpc(
            "get_bbo",
            {"symbol": str(symbol).upper(), "max_age_s": (float(max_age_s) if max_age_s is not None else None)},
            timeout_s=1.0,
        )
        if not isinstance(res, list) or len(res) < 2:
            return None
        try:
            bid = float(res[0])
            ask = float(res[1])
            return bid, ask
        except Exception:
            return None

    def get_latest_candle_times(self, symbol: str, interval: str) -> tuple[int | None, int | None]:
        res = self._rpc(
            "get_latest_candle_times",
            {"symbol": str(symbol).upper(), "interval": str(interval)},
            timeout_s=1.0,
        )
        if not isinstance(res, list) or len(res) < 2:
            return None, None
        t_open, t_close = res[0], res[1]
        try:
            t_open_i = int(t_open) if t_open is not None else None
        except Exception:
            t_open_i = None
        try:
            t_close_i = int(t_close) if t_close is not None else None
        except Exception:
            t_close_i = None
        return t_open_i, t_close_i

    def get_last_closed_candle_times(
        self, symbol: str, interval: str, *, grace_ms: int = 2000
    ) -> tuple[int | None, int | None]:
        res = self._rpc(
            "get_last_closed_candle_times",
            {"symbol": str(symbol).upper(), "interval": str(interval), "grace_ms": int(grace_ms)},
            timeout_s=1.0,
        )
        if not isinstance(res, list) or len(res) < 2:
            return None, None
        t_open, t_close = res[0], res[1]
        try:
            t_open_i = int(t_open) if t_open is not None else None
        except Exception:
            t_open_i = None
        try:
            t_close_i = int(t_close) if t_close is not None else None
        except Exception:
            t_close_i = None
        return t_open_i, t_close_i

    def get_candles_df(self, symbol: str, interval: str, *, min_rows: int) -> pd.DataFrame | None:
        sym = str(symbol).upper()
        interval_s = str(interval)
        want = int(min_rows)

        conn = None
        best_rows: list[tuple] = []
        for db_path in (_candles_db_path(interval_s), self._market_db_path):
            conn = None
            try:
                # Read-only connection: do not create/modify DB files from the client.
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=self._db_timeout_s)
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT t, t_close, o, h, l, c, v, n
                    FROM candles
                    WHERE symbol = ? AND interval = ?
                    ORDER BY t DESC
                    LIMIT ?
                    """,
                    (sym, interval_s, want),
                )
                rows_iter = cur.fetchall() or []
                if len(rows_iter) > len(best_rows):
                    best_rows = rows_iter
                if len(best_rows) >= want:
                    break
            except Exception:
                pass
            finally:
                try:
                    if conn is not None:
                        conn.close()
                except Exception:
                    pass
        rows = best_rows

        if len(rows) < want:
            return None

        data: list[dict[str, Any]] = []
        for t_ms, t_close_ms, o, h, l, c, v, n in reversed(rows):
            data.append(
                {
                    "timestamp": int(t_ms),
                    "T": (int(t_close_ms) if t_close_ms is not None else None),
                    "s": sym,
                    "i": interval_s,
                    "Open": o,
                    "High": h,
                    "Low": l,
                    "Close": c,
                    "Volume": v,
                    "n": n,
                }
            )

        df = pd.DataFrame(data)
        if df.empty:
            return None
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def drain_user_fills(self, *, max_items: int | None = None) -> list[dict]:
        res = self._rpc("drain_user_fills", {"max_items": max_items}, timeout_s=1.0)
        return res if isinstance(res, list) else []

    def drain_order_updates(self, *, max_items: int | None = None) -> list[dict]:
        res = self._rpc("drain_order_updates", {"max_items": max_items}, timeout_s=1.0)
        return res if isinstance(res, list) else []

    def drain_user_fundings(self, *, max_items: int | None = None) -> list[dict]:
        res = self._rpc("drain_user_fundings", {"max_items": max_items}, timeout_s=1.0)
        return res if isinstance(res, list) else []

    def drain_user_ledger_updates(self, *, max_items: int | None = None) -> list[dict]:
        res = self._rpc("drain_user_ledger_updates", {"max_items": max_items}, timeout_s=1.0)
        return res if isinstance(res, list) else []
