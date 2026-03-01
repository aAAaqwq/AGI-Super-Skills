import json
import logging
import os
import sqlite3
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass

import pandas as pd
import websocket

logger = logging.getLogger(__name__)

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
# Candle cache DB:
# - Prefer a shared market DB when configured (used by the WS sidecar).
# - Fall back to the per-daemon trading DB for the direct WS client.
DB_PATH = os.getenv(
    "AI_QUANT_MARKET_DB_PATH",
    os.getenv("AI_QUANT_DB_PATH", os.path.join(_THIS_DIR, "..", "trading_engine.db")),
)
HL_WS_URL = os.getenv("HL_WS_URL", "wss://api.hyperliquid.xyz/ws")

_DB_TIMEOUT_S = float(os.getenv("AI_QUANT_DB_TIMEOUT_S", "30"))

HL_WS_RECONNECT_SECS = int(os.getenv("HL_WS_RECONNECT_SECS", "5"))
HL_WS_PING_SECS = int(os.getenv("HL_WS_PING_SECS", "50"))

# Candle persistence is throttled (candle updates are frequent).
HL_WS_CANDLE_PERSIST_SECS = int(os.getenv("HL_WS_CANDLE_PERSIST_SECS", "60"))

# User event queues are bounded to avoid unbounded memory growth.
HL_WS_MAX_EVENT_QUEUE = int(os.getenv("HL_WS_MAX_EVENT_QUEUE", "5000"))


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


# Optional WS channel toggles. Helpful when monitoring 100+ symbols.
# For live trading, user channels (fills/orderUpdates) should remain enabled.
HL_WS_ENABLE_META = _env_bool("AI_QUANT_WS_ENABLE_META", True)
HL_WS_ENABLE_CANDLE = _env_bool("AI_QUANT_WS_ENABLE_CANDLE", True)
HL_WS_ENABLE_BBO = _env_bool("AI_QUANT_WS_ENABLE_BBO", True)


def _ensure_db():
    conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        logger.debug("PRAGMA setup failed for candle DB", exc_info=True)
    cursor = conn.cursor()
    cursor.execute(
        """
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
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_candles_symbol_interval_t
        ON candles(symbol, interval, t)
        """
    )
    conn.commit()
    try:
        os.chmod(DB_PATH, 0o600)
    except OSError as _perm_exc:
        import logging as _logging

        _logging.getLogger(__name__).warning("Failed to set DB permissions on %s: %s", DB_PATH, _perm_exc)
    conn.close()


@dataclass(frozen=True)
class WsHealth:
    mids_age_s: float | None
    candle_age_s: float | None
    bbo_age_s: float | None


class HyperliquidWS:
    def __init__(self):
        _ensure_db()
        self._lock = threading.RLock()
        self._ws_app: websocket.WebSocketApp | None = None
        self._thread: threading.Thread | None = None
        self._ping_thread: threading.Thread | None = None
        self._connected: bool = False
        self._restarting: bool = False

        self._subscriptions: list[dict] = []
        self._candle_limit_by_key: dict[tuple[str, str], int] = {}

        self._mids: dict[str, float] = {}
        self._mids_updated_at: dict[str, float] = {}
        self._mids_last_disconnect_at: float | None = None

        self._bbo: dict[str, tuple[float, float]] = {}
        self._bbo_updated_at: dict[str, float] = {}
        self._bbo_last_disconnect_at: float | None = None

        self._candles: dict[tuple[str, str], OrderedDict[int, dict]] = {}
        self._candle_updated_at: dict[tuple[str, str], float] = {}
        self._candle_last_persist_at: dict[tuple[str, str], float] = {}
        self._last_t_seen: dict[tuple[str, str], int] = {}

        self._funding_rates: dict[str, float] = {}
        self._funding_updated_at: float | None = None

        # User channels (optional; only subscribed when `user` is provided in ensure_started()).
        self._user: str | None = None
        self._user_fills: deque[dict] = deque()
        self._user_fills_updated_at: float | None = None
        self._order_updates: deque[dict] = deque()
        self._order_updates_updated_at: float | None = None
        self._user_fundings: deque[dict] = deque()
        self._user_fundings_updated_at: float | None = None
        self._user_ledger_updates: deque[dict] = deque()
        self._user_ledger_updated_at: float | None = None

        self._stop_event = threading.Event()

    def ensure_started(self, *, symbols: list[str], interval: str, candle_limit: int, user: str | None = None):
        with self._lock:
            if self._restarting:
                return

        def sub_key(sub: dict) -> tuple:
            t = sub.get("type")
            if t == "allMids":
                return ("allMids",)
            if t == "meta":
                return ("meta",)
            if t == "candle":
                return ("candle", sub.get("coin"), sub.get("interval"))
            if t == "bbo":
                return ("bbo", sub.get("coin"))
            if t == "userFills":
                return ("userFills", sub.get("user"))
            if t == "orderUpdates":
                return ("orderUpdates", sub.get("user"))
            if t == "userFundings":
                return ("userFundings", sub.get("user"))
            if t == "userNonFundingLedgerUpdates":
                return ("userNonFundingLedgerUpdates", sub.get("user"))
            if t == "webData2":
                return ("webData2", sub.get("user"))
            return ("other", json.dumps(sub, sort_keys=True))

        requested_symbols: list[str] = []
        seen: set[str] = set()
        for sym in symbols:
            s = str(sym or "").strip().upper()
            if not s or s in seen:
                continue
            seen.add(s)
            requested_symbols.append(s)

        # Never shrink subscriptions implicitly: keep previously requested symbols too.
        existing_symbols: set[str] = set()
        with self._lock:
            for sub in self._subscriptions:
                if sub.get("type") in {"candle", "bbo"}:
                    coin = sub.get("coin")
                    if coin:
                        existing_symbols.add(str(coin).strip().upper())

        union_symbols = list(requested_symbols)
        for sym in sorted(existing_symbols - set(requested_symbols)):
            union_symbols.append(sym)

        # Persist the user (if provided) so later ensure_started() calls without `user` won't drop user channels.
        if user is not None:
            normalized_user = str(user or "").strip().lower()
            with self._lock:
                self._user = normalized_user if normalized_user else None
        with self._lock:
            active_user = self._user

        desired_subs: list[dict] = [{"type": "allMids"}]
        if HL_WS_ENABLE_META:
            desired_subs.append({"type": "meta"})
        if HL_WS_ENABLE_CANDLE:
            for sym in union_symbols:
                desired_subs.append({"type": "candle", "coin": sym, "interval": interval})
        if HL_WS_ENABLE_BBO:
            for sym in union_symbols:
                desired_subs.append({"type": "bbo", "coin": sym})

        if active_user:
            desired_subs.append({"type": "userFills", "user": active_user})
            desired_subs.append({"type": "orderUpdates", "user": active_user})
            desired_subs.append({"type": "userFundings", "user": active_user})
            desired_subs.append({"type": "userNonFundingLedgerUpdates", "user": active_user})

        with self._lock:
            # Update candle limits + load local history for any newly-added symbols.
            for sym in union_symbols:
                key = (sym, interval)
                prev = self._candle_limit_by_key.get(key)
                self._candle_limit_by_key[key] = candle_limit if prev is None else max(int(prev), int(candle_limit))
                key = (sym, interval)
                if key not in self._candles or len(self._candles[key]) == 0:
                    self._candles[key] = self._load_candles_from_db(sym, interval, limit=self._candle_limit_by_key[key])

            existing_keys = {sub_key(s) for s in self._subscriptions}
            new_subs = [s for s in desired_subs if sub_key(s) not in existing_keys]

            # Always keep the desired subscription set for reconnects.
            self._subscriptions = desired_subs

            thread_alive = self._thread is not None and self._thread.is_alive()
            ws_app = self._ws_app

            if not thread_alive:
                self._stop_event.clear()
                self._thread = threading.Thread(target=self._run, daemon=True)
                self._thread.start()

                self._ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
                self._ping_thread.start()

        # If we're already connected, subscribe to any newly-added symbols without requiring a restart.
        if thread_alive and ws_app is not None and new_subs:
            for sub in new_subs:
                try:
                    ws_app.send(json.dumps({"method": "subscribe", "subscription": sub}))
                except Exception:
                    # A reconnect will re-send the full subscription set.
                    logger.debug("WS subscribe send failed (will retry on reconnect)", exc_info=True)

    def stop(self):
        self._stop_event.set()
        with self._lock:
            ws_app = self._ws_app
        if ws_app is not None:
            try:
                ws_app.close()
            except Exception:
                logger.debug("WS close failed during stop()", exc_info=True)

    def status(self) -> dict[str, bool]:
        with self._lock:
            running = self._thread is not None and self._thread.is_alive()
            ws_app = self._ws_app
            # Treat "connected" as "WS thread is running" for liveness purposes.
            # Actual market freshness is enforced via the age metrics in health().
            connected = running and ws_app is not None and not self._stop_event.is_set()
        return {"running": bool(running), "connected": bool(connected)}

    def restart(self, *, join_timeout_s: float = 5.0) -> None:
        """Best-effort in-process restart without swapping the global instance."""
        with self._lock:
            self._stop_event.set()
            if self._ws_app:
                try:
                    self._ws_app.close()
                except Exception:
                    logger.debug("WS close failed during restart()", exc_info=True)
            t = self._thread
            p = self._ping_thread

        # Join outside lock to avoid deadlocks.
        if t is not None:
            try:
                t.join(timeout=float(join_timeout_s))
            except Exception:
                logger.debug("WS thread join failed during restart()", exc_info=True)
        if p is not None:
            try:
                p.join(timeout=float(join_timeout_s))
            except Exception:
                logger.debug("WS ping thread join failed during restart()", exc_info=True)

        with self._lock:
            self._restarting = True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
            self._thread.start()
            self._ping_thread.start()
            self._restarting = False

    def get_latest_candle_times(self, symbol: str, interval: str) -> tuple[int | None, int | None]:
        """Return (t_open_ms, t_close_ms) for the latest candle in cache.

        This is a cheap, lock-protected peek into the candle cache. It is useful for engines that
        want to decide whether to fetch a full DataFrame, without rebuilding it every loop.
        """
        sym = str(symbol).upper()
        key = (sym, str(interval))
        with self._lock:
            od = self._candles.get(key)
            if not od:
                return None, None
            try:
                last_t = next(reversed(od))
            except Exception:
                logger.debug("candle key lookup failed for %s@%s", symbol, interval, exc_info=True)
                return None, None
            last = od.get(last_t) or {}
            t_open = last.get("timestamp") or last_t
            t_close = last.get("T")
            try:
                t_open_i = int(t_open) if t_open is not None else None
            except (TypeError, ValueError):
                t_open_i = None
            try:
                t_close_i = int(t_close) if t_close is not None else None
            except (TypeError, ValueError):
                t_close_i = None
            return t_open_i, t_close_i

    def get_last_closed_candle_times(
        self, symbol: str, interval: str, *, grace_ms: int = 2000
    ) -> tuple[int | None, int | None]:
        """Return (t_open_ms, t_close_ms) for the last *closed* candle.

        The candle stream frequently updates the in-progress candle. If the latest candle has a
        close time in the future (now < T - grace_ms), we return the previous candle instead.
        """
        sym = str(symbol).upper()
        key = (sym, str(interval))
        now = int(time.time() * 1000)
        grace = int(grace_ms)

        with self._lock:
            od = self._candles.get(key)
            if not od:
                return None, None

            keys = list(od.keys())
            if not keys:
                return None, None

            last_t = keys[-1]
            last = od.get(last_t) or {}
            t_open = last.get("timestamp") or last_t
            t_close = last.get("T")

            try:
                if t_close is not None and int(now) < (int(t_close) - grace) and len(keys) >= 2:
                    prev_t = keys[-2]
                    prev = od.get(prev_t) or {}
                    t_open2 = prev.get("timestamp") or prev_t
                    t_close2 = prev.get("T")
                    try:
                        return (
                            int(t_open2) if t_open2 is not None else None,
                            int(t_close2) if t_close2 is not None else None,
                        )
                    except (TypeError, ValueError):
                        return None, None
            except (TypeError, ValueError):
                logger.debug("candle close time comparison failed", exc_info=True)

            try:
                return int(t_open) if t_open is not None else None, int(t_close) if t_close is not None else None
            except (TypeError, ValueError):
                return None, None

    def health(self, *, symbols: list[str], interval: str) -> WsHealth:
        # Copy dicts under lock to avoid race with reconnect thread mutating them.
        with self._lock:
            mids_snap = dict(self._mids_updated_at)
            candle_snap = dict(self._candle_updated_at)
            bbo_snap = dict(self._bbo_updated_at)

        now = time.time()
        mids_age: float | None = None
        for sym in symbols:
            ts = mids_snap.get(sym)
            if ts is None:
                continue
            age = now - ts
            mids_age = age if mids_age is None else max(mids_age, age)

        candle_age: float | None = None
        for sym in symbols:
            key = (sym, interval)
            ts = candle_snap.get(key)
            if ts is None:
                continue
            age = now - ts
            candle_age = age if candle_age is None else max(candle_age, age)

        bbo_age: float | None = None
        for sym in symbols:
            ts = bbo_snap.get(sym)
            if ts is None:
                continue
            age = now - ts
            bbo_age = age if bbo_age is None else max(bbo_age, age)

        return WsHealth(mids_age_s=mids_age, candle_age_s=candle_age, bbo_age_s=bbo_age)

    def get_funding_rate(self, symbol: str) -> float | None:
        with self._lock:
            return self._funding_rates.get(symbol)

    def get_bbo(self, symbol: str, max_age_s: float | None = None) -> tuple[float, float] | None:
        now = time.time()
        with self._lock:
            bbo = self._bbo.get(symbol)
            if bbo is None:
                return None
            if max_age_s is not None:
                ts = self._bbo_updated_at.get(symbol)
                if ts is None or (now - ts) > float(max_age_s):
                    return None
            return bbo

    def get_mid(self, symbol: str, max_age_s: float | None = None) -> float | None:
        now = time.time()
        with self._lock:
            mid = self._mids.get(symbol)
            if mid is None:
                return None
            if max_age_s is not None:
                ts = self._mids_updated_at.get(symbol)
                if ts is None or (now - ts) > float(max_age_s):
                    return None
            return mid

    def get_mid_age_s(self, symbol: str) -> float | None:
        now = time.time()
        with self._lock:
            ts = self._mids_updated_at.get(symbol)
            if ts is None:
                return None
            return max(0.0, now - ts)

    def get_ws_disconnect_age_s(self) -> float | None:
        now = time.time()
        with self._lock:
            ts = self._mids_last_disconnect_at
            if ts is None:
                return None
            return max(0.0, now - ts)

    def get_candles_df(self, symbol: str, interval: str, *, min_rows: int) -> pd.DataFrame | None:
        key = (symbol, interval)
        with self._lock:
            od = self._candles.get(key)
            if od is None or len(od) < min_rows:
                return None
            rows = list(od.values())

        df = pd.DataFrame(rows)
        if df.empty:
            return None

        # Keep output compatible with the existing strategy code.
        numeric_cols: list[str] = []
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
                numeric_cols.append(col)

        if numeric_cols:
            df = df.dropna(subset=numeric_cols)

        if df.empty or len(df) < int(min_rows):
            return None

        return df.tail(int(min_rows)).copy()

    def _drain_deque(self, q: deque[dict], *, max_items: int | None) -> list[dict]:
        items: list[dict] = []
        while q and (max_items is None or len(items) < int(max_items)):
            try:
                items.append(q.popleft())
            except IndexError:
                break
        return items

    def drain_user_fills(self, *, max_items: int | None = None) -> list[dict]:
        with self._lock:
            return self._drain_deque(self._user_fills, max_items=max_items)

    def drain_order_updates(self, *, max_items: int | None = None) -> list[dict]:
        with self._lock:
            return self._drain_deque(self._order_updates, max_items=max_items)

    def drain_user_fundings(self, *, max_items: int | None = None) -> list[dict]:
        with self._lock:
            return self._drain_deque(self._user_fundings, max_items=max_items)

    def drain_user_ledger_updates(self, *, max_items: int | None = None) -> list[dict]:
        with self._lock:
            return self._drain_deque(self._user_ledger_updates, max_items=max_items)

    def _load_candles_from_db(self, symbol: str, interval: str, *, limit: int) -> OrderedDict[int, dict]:
        _ensure_db()
        conn = None
        rows = []
        try:
            conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT t, t_close, o, h, l, c, v, n
                FROM candles
                WHERE symbol = ? AND interval = ?
                ORDER BY t DESC
                LIMIT ?
                """,
                (symbol, interval, limit),
            )
            rows = cursor.fetchall()
        except sqlite3.OperationalError as e:
            # Never crash the daemon on transient SQLite contention; just start with an empty cache.
            if "locked" not in str(e).lower():
                logger.warning(f"⚠️ Candle load DB error: {e}")
            rows = []
        except Exception as e:
            logger.warning(f"⚠️ Candle load error: {e}")
            rows = []
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                logger.debug("failed to close candle DB connection (load)", exc_info=True)

        od: OrderedDict[int, dict] = OrderedDict()
        for t_ms, T_ms, o, h, l, c, v, n in reversed(rows):
            od[int(t_ms)] = {
                "timestamp": int(t_ms),
                "T": int(T_ms) if T_ms is not None else None,
                "s": symbol,
                "i": interval,
                "Open": float(o) if o is not None else None,
                "High": float(h) if h is not None else None,
                "Low": float(l) if l is not None else None,
                "Close": float(c) if c is not None else None,
                "Volume": float(v) if v is not None else None,
                "n": int(n) if n is not None else None,
            }
        return od

    def _persist_candle(self, candle: dict):
        conn = None
        try:
            _ensure_db()
            conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO candles (symbol, interval, t, t_close, o, h, l, c, v, n, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, interval, t) DO UPDATE SET
                    t_close = excluded.t_close,
                    o = excluded.o,
                    h = excluded.h,
                    l = excluded.l,
                    c = excluded.c,
                    v = excluded.v,
                    n = excluded.n,
                    updated_at = excluded.updated_at
                """,
                (
                    candle["s"],
                    candle["i"],
                    int(candle["timestamp"]),
                    candle.get("T"),
                    candle.get("Open"),
                    candle.get("High"),
                    candle.get("Low"),
                    candle.get("Close"),
                    candle.get("Volume"),
                    candle.get("n"),
                    time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
                ),
            )
            conn.commit()
        except sqlite3.OperationalError as e:
            # Never crash the WS thread on SQLite contention; skip this persist and continue.
            if "locked" not in str(e).lower():
                logger.warning(f"⚠️ Candle persist DB error: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Candle persist error: {e}")
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                logger.debug("failed to close candle DB connection (persist)", exc_info=True)

    def _on_open(self, ws):
        with self._lock:
            self._ws_app = ws
            self._connected = True
            self._mids_last_disconnect_at = None
            self._bbo_last_disconnect_at = None
            subs = list(self._subscriptions)

        for sub in subs:
            try:
                ws.send(json.dumps({"method": "subscribe", "subscription": sub}))
            except (TypeError, ValueError, OSError, websocket.WebSocketException) as exc:
                logger.warning("WS subscribe resend failed for %s: %s", sub, exc)

    def _on_message(self, _ws, message: str):
        try:
            msg = json.loads(message)
        except json.JSONDecodeError as e:
            logger.warning("WS JSON parse error: %s (message truncated: %s)", e, str(message)[:200])
            return

        channel = msg.get("channel")
        if channel == "subscriptionResponse" or channel == "pong":
            return

        # Defensive: if a channel was toggled off but we still receive messages
        # (e.g., stale subscriptions around reconnect), drop early to save CPU.
        if channel == "meta" and not HL_WS_ENABLE_META:
            return
        if channel == "bbo" and not HL_WS_ENABLE_BBO:
            return
        if channel == "candle" and not HL_WS_ENABLE_CANDLE:
            return

        now = time.time()

        if channel == "allMids":
            mids = (msg.get("data") or {}).get("mids") or {}
            with self._lock:
                for sym, mid in mids.items():
                    try:
                        self._mids[sym] = float(mid)
                        self._mids_updated_at[sym] = now
                    except (TypeError, ValueError):
                        continue
            return

        if channel == "meta":
            # We currently don't consume meta payloads (universe/funding) in python.
            # Keep a timestamp for health/diagnostics so the channel isn't treated as "dead".
            with self._lock:
                self._funding_updated_at = now
            return

        if channel == "bbo":
            data = msg.get("data") or {}
            sym = data.get("coin")
            bbo = data.get("bbo") or []
            if not sym or not isinstance(bbo, list) or len(bbo) < 2:
                return
            try:
                bid = float(bbo[0].get("px"))
                ask = float(bbo[1].get("px"))
            except (TypeError, ValueError, KeyError, IndexError):
                return
            with self._lock:
                self._bbo[sym] = (bid, ask)
                self._bbo_updated_at[sym] = now
            return

        if channel == "candle":
            data = msg.get("data") or {}
            sym = data.get("s")
            interval = data.get("i")
            t_ms = data.get("t")
            if not sym or not interval or t_ms is None:
                return

            try:
                candle = {
                    "timestamp": int(data["t"]),
                    "T": int(data["T"]) if data.get("T") is not None else None,
                    "s": sym,
                    "i": interval,
                    "Open": float(data["o"]),
                    "High": float(data["h"]),
                    "Low": float(data["l"]),
                    "Close": float(data["c"]),
                    "Volume": float(data["v"]),
                    "n": int(data["n"]) if data.get("n") is not None else None,
                }
            except (TypeError, ValueError, KeyError) as exc:
                logger.debug("candle message parse failed: %s", exc)
                return

            key = (sym, interval)
            with self._lock:
                od = self._candles.setdefault(key, OrderedDict())
                od[int(candle["timestamp"])] = candle
                # Keep candle ordering and cap memory.
                od.move_to_end(int(candle["timestamp"]))
                limit = self._candle_limit_by_key.get(key, 500)
                while len(od) > limit:
                    od.popitem(last=False)

                self._candle_updated_at[key] = now

                last_t = self._last_t_seen.get(key)
                self._last_t_seen[key] = int(candle["timestamp"])

                last_persist = self._candle_last_persist_at.get(key, 0.0)
                should_persist = (last_t is None or last_t != int(candle["timestamp"])) or (
                    now - last_persist >= HL_WS_CANDLE_PERSIST_SECS
                )
                if should_persist:
                    self._candle_last_persist_at[key] = now

            if should_persist:
                self._persist_candle(candle)

        if channel == "userFills":
            data = msg.get("data") or {}
            fills = data.get("fills") or []
            is_snapshot = bool(data.get("isSnapshot"))
            if isinstance(fills, list) and fills:
                with self._lock:
                    for f in fills:
                        if not isinstance(f, dict):
                            continue
                        # Attach snapshot flag so consumers can decide how to dedupe/backfill.
                        item = dict(f)
                        item["_is_snapshot"] = is_snapshot
                        if len(self._user_fills) >= HL_WS_MAX_EVENT_QUEUE:
                            try:
                                self._user_fills.popleft()
                            except IndexError:
                                pass
                            logger.warning(
                                "user_fills queue limit hit (%d); oldest item evicted", HL_WS_MAX_EVENT_QUEUE
                            )
                        self._user_fills.append(item)
                    self._user_fills_updated_at = now
            return

        if channel == "orderUpdates":
            data = msg.get("data")
            if data is None:
                return
            with self._lock:
                if len(self._order_updates) >= HL_WS_MAX_EVENT_QUEUE:
                    try:
                        self._order_updates.popleft()
                    except IndexError:
                        pass
                    logger.warning("order_updates queue limit hit (%d); oldest item evicted", HL_WS_MAX_EVENT_QUEUE)
                self._order_updates.append({"t": now, "data": data})
                self._order_updates_updated_at = now
            return

        if channel == "userFundings":
            data = msg.get("data")
            if data is None:
                return
            with self._lock:
                if len(self._user_fundings) >= HL_WS_MAX_EVENT_QUEUE:
                    try:
                        self._user_fundings.popleft()
                    except IndexError:
                        pass
                    logger.warning("user_fundings queue limit hit (%d); oldest item evicted", HL_WS_MAX_EVENT_QUEUE)
                self._user_fundings.append({"t": now, "data": data})
                self._user_fundings_updated_at = now
            return

        if channel == "userNonFundingLedgerUpdates":
            data = msg.get("data")
            if data is None:
                return
            with self._lock:
                if len(self._user_ledger_updates) >= HL_WS_MAX_EVENT_QUEUE:
                    try:
                        self._user_ledger_updates.popleft()
                    except IndexError:
                        pass
                    logger.warning(
                        "user_ledger_updates queue limit hit (%d); oldest item evicted", HL_WS_MAX_EVENT_QUEUE
                    )
                self._user_ledger_updates.append({"t": now, "data": data})
                self._user_ledger_updated_at = now
            return

    def _on_error(self, _ws, error):
        # Keep errors non-fatal; reconnect handles recovery.
        logger.warning(f"⚠️ HL WS error: {error}")

    def _on_close(self, _ws, status_code, msg):
        logger.info(f"🟡 HL WS closed: {status_code} {msg}")
        with self._lock:
            self._connected = False
            # Keep latest market snapshots on disconnect so callers can still use
            # bounded-staleness reads via max_age_s during reconnect windows.
            now = time.time()
            self._mids_last_disconnect_at = now
            self._bbo_last_disconnect_at = now

    def _ping_loop(self):
        while not self._stop_event.wait(HL_WS_PING_SECS):
            with self._lock:
                ws_app = self._ws_app
            if ws_app is None:
                continue
            try:
                ws_app.send(json.dumps({"method": "ping"}))
            except Exception:
                logger.debug("WS ping send failed", exc_info=True)

    def _run(self):
        ws = websocket.WebSocketApp(
            HL_WS_URL,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        with self._lock:
            self._ws_app = ws
        ws.run_forever(reconnect=HL_WS_RECONNECT_SECS)


def _make_default_ws():
    source = str(os.getenv("AI_QUANT_WS_SOURCE", "direct") or "direct").strip().lower()
    if source == "sidecar":
        # Sidecar-only means NO direct outbound WS fallback. If the sidecar client
        # cannot be constructed, fail fast so systemd can restart after a fix.
        from exchange.sidecar import SidecarWSClient

        return SidecarWSClient()

    return HyperliquidWS()


_DEFAULT_WS_LOCK = threading.Lock()
_default_ws_singleton = None


def _get_default_ws_singleton():
    global _default_ws_singleton
    ws_obj = _default_ws_singleton
    if ws_obj is not None:
        return ws_obj
    with _DEFAULT_WS_LOCK:
        ws_obj = _default_ws_singleton
        if ws_obj is None:
            ws_obj = _make_default_ws()
            _default_ws_singleton = ws_obj
    return ws_obj


def _set_default_ws_singleton(ws_obj) -> None:
    global _default_ws_singleton
    with _DEFAULT_WS_LOCK:
        _default_ws_singleton = ws_obj


class _LazyWSProxy:
    """Lazy proxy so importing this module does not construct WS clients."""

    def __getattr__(self, item):
        return getattr(_get_default_ws_singleton(), item)

    def __repr__(self) -> str:
        return repr(_get_default_ws_singleton())


hl_ws = _LazyWSProxy()
