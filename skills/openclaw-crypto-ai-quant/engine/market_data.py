from __future__ import annotations

import os
import sqlite3
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

import pandas as pd

import logging

from .rest_client import HyperliquidRestClient
from .utils import now_ms

logger = logging.getLogger(__name__)


@dataclass
class PriceQuote:
    symbol: str
    price: float
    source: str  # ws_mid, ws_bbo, rest_mid, candle_close
    age_s: float | None = None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _interval_to_ms(interval: str) -> int:
    s = str(interval or "").strip().lower()
    if not s:
        return 60 * 60 * 1000
    unit = s[-1]
    try:
        n = float(s[:-1])
    except Exception:
        n = 1.0
    if unit == "m":
        return int(n * 60.0 * 1000.0)
    if unit == "h":
        return int(n * 60.0 * 60.0 * 1000.0)
    if unit == "d":
        return int(n * 24.0 * 60.0 * 60.0 * 1000.0)
    if unit == "w":
        return int(n * 7 * 24 * 60 * 60 * 1000)
    # Fallback: assume seconds
    try:
        return int(float(s) * 1000.0)
    except Exception:
        return 60 * 60 * 1000


def _sanitize_interval(interval: str) -> str:
    out = []
    for ch in str(interval or ""):
        if ("0" <= ch <= "9") or ("a" <= ch.lower() <= "z"):
            out.append(ch.lower())
        else:
            out.append("_")
    s = "".join(out).strip("_")
    return s if s else "unknown"


def _candles_db_dir(base_db_path: str) -> str:
    raw = str(os.getenv("AI_QUANT_CANDLES_DB_DIR", "") or "").strip()
    if raw:
        return raw
    try:
        parent = os.path.dirname(os.path.abspath(base_db_path))
        return os.path.join(parent, "candles_dbs")
    except Exception:
        return "candles_dbs"


class MarketDataHub:
    """Unified market data access (WS first, REST fallback).

    This version is compatible with your current `hyperliquid_ws.HyperliquidWS` API:
    - ensure_started(symbols, interval, candle_limit, user)
    - get_mid(symbol, max_age_s)
    - get_bbo(symbol, max_age_s)
    - get_candles_df(symbol, interval, min_rows)
    - health(symbols, interval) -> WsHealth
    - stop()

    It also reads/writes the same SQLite `candles` table used by hyperliquid_ws.py.
    """

    def __init__(
        self,
        *,
        db_path: str,
        rest: HyperliquidRestClient | None = None,
        stale_mid_s: float = 60.0,
        stale_bbo_s: float = 60.0,
        stale_candle_s: float = 2 * 60 * 60,
        db_timeout_s: float = 30.0,
    ):
        self._db_path = str(db_path)
        raw_db_timeout_s = float(db_timeout_s)
        self._db_timeout_s = min(raw_db_timeout_s, 5.0)
        if self._db_timeout_s < raw_db_timeout_s:
            logger.warning(
                "MarketDataHub db_timeout_s clamped from %.2fs to %.2fs",
                raw_db_timeout_s,
                self._db_timeout_s,
            )

        self._stale_mid_s = float(stale_mid_s)
        self._stale_bbo_s = float(stale_bbo_s)
        self._stale_candle_s = float(stale_candle_s)

        import exchange.ws as hyperliquid_ws

        self._ws_mod = hyperliquid_ws
        self._ws = hyperliquid_ws.hl_ws

        self._rest_mids: dict[str, tuple[float, int]] = {}

        self._candles_source = str(os.getenv("AI_QUANT_CANDLES_SOURCE", "") or "").strip().lower()
        self._use_interval_candle_dbs = self._candles_source == "sidecar"
        self._candles_db_dir = _candles_db_dir(self._db_path)

        ws_source = str(os.getenv("AI_QUANT_WS_SOURCE", "") or "").strip().lower()
        self._sidecar_only = (ws_source == "sidecar") and (self._candles_source == "sidecar")

        self._rest_enabled = _env_bool("AI_QUANT_REST_ENABLE", True)
        if self._sidecar_only:
            self._rest_enabled = False

        self._rest = None if (not self._rest_enabled) else (rest or HyperliquidRestClient())

        # REST candleSnapshot backfill must never block the main engine loop.
        # We schedule it in the background and use DB/WS results when available.
        self._rest_candle_backfill_enabled = _env_bool("AI_QUANT_REST_CANDLE_BACKFILL", True)
        self._rest_candle_backfill_workers = max(1, int(os.getenv("AI_QUANT_REST_CANDLE_BACKFILL_WORKERS", "2")))
        self._rest_candle_backfill_max_inflight = max(
            1,
            int(os.getenv("AI_QUANT_REST_CANDLE_BACKFILL_MAX_INFLIGHT", str(self._rest_candle_backfill_workers))),
        )
        self._rest_candle_backfill_success_cooldown_s = float(
            os.getenv("AI_QUANT_REST_CANDLE_BACKFILL_SUCCESS_COOLDOWN_S", "30")
        )
        self._rest_candle_backfill_failure_cooldown_s = float(
            os.getenv("AI_QUANT_REST_CANDLE_BACKFILL_FAILURE_COOLDOWN_S", "300")
        )
        self._rest_candle_backfill_max_cooldown_s = float(
            os.getenv("AI_QUANT_REST_CANDLE_BACKFILL_MAX_COOLDOWN_S", "3600")
        )

        # When candles are sourced from the Rust sidecar, do not run a second REST candle
        # backfill from Python (avoid DB write contention and duplicated load).
        if self._use_interval_candle_dbs:
            self._rest_candle_backfill_enabled = False

        self._rest_candle_lock = threading.RLock()
        self._rest_candle_pool: ThreadPoolExecutor | None = None
        self._rest_candle_inflight: dict[tuple[str, str], Future] = {}
        self._rest_candle_failures: dict[tuple[str, str], int] = {}
        self._rest_candle_next_allowed_ms: dict[tuple[str, str], int] = {}
        self._rest_candle_last_err: dict[tuple[str, str], str] = {}

        # Per-loop candle cache: avoids repeated DB reads for the same symbol+interval
        # within a short time window (e.g. breadth EMA across 50 symbols).
        self._candle_cache: dict[str, tuple[float, pd.DataFrame | None]] = {}
        self._candle_cache_ttl_s: float = 5.0

    def ensure(self, *, symbols: list[str], interval: str, candle_limit: int, user: str | None = None) -> None:
        self._ws.ensure_started(
            symbols=list(symbols),
            interval=str(interval),
            candle_limit=int(candle_limit),
            user=user,
        )

    def ws_health(self, *, symbols: list[str], interval: str) -> Any:
        return self._ws.health(symbols=list(symbols), interval=str(interval))

    def candles_ready(self, *, symbols: list[str], interval: str, min_rows: int = 50) -> tuple[bool, list[str]]:
        # BUG-15: If we are in sidecar-only mode, candles_ready should be more permissive
        # because the sidecar itself handles backfilling and may report not_ready
        # for symbols that actually have enough data in the DB for a trade.
        required = max(int(min_rows), 50)
        fn = getattr(self._ws, "candles_ready", None)
        if not callable(fn):
            return True, []
        try:
            ready, not_ready = fn(symbols=list(symbols), interval=str(interval))
            if not isinstance(not_ready, list):
                not_ready = []

            # If the sidecar says not_ready, we check the DB directly as a second opinion.
            # This prevents the "not_ready" gate from blocking trades when data is actually present.
            if not_ready:
                truly_not_ready = []
                for sym in not_ready:
                    # If we can get a valid DF with min_rows, it's ready enough for us.
                    try:
                        df = self.get_candles_df(sym, interval=interval, min_rows=required)
                        if df is None or len(df) < required:
                            truly_not_ready.append(sym)
                    except (sqlite3.Error, OSError, ValueError, TypeError):
                        logger.warning("candle readiness check failed for %s", sym, exc_info=True)
                        truly_not_ready.append(sym)
                not_ready = truly_not_ready
                ready = len(not_ready) == 0

            return bool(ready), [str(s).upper() for s in not_ready]
        except (sqlite3.Error, OSError, RuntimeError, ValueError, TypeError):
            logger.warning("ensure_ready() fallback path triggered", exc_info=True)
            return False, [str(s).upper() for s in (symbols or [])]

    def candles_health(self, *, symbols: list[str], interval: str) -> dict[str, Any] | None:
        fn = getattr(self._ws, "candles_health", None)
        if not callable(fn):
            return None
        try:
            res = fn(symbols=list(symbols), interval=str(interval))
        except Exception:
            return None
        return res if isinstance(res, dict) else None

    def health(self, *, symbols: list[str], interval: str) -> dict[str, Any]:
        h = self.ws_health(symbols=symbols, interval=interval)
        # `h` is WsHealth(mids_age_s, candle_age_s, bbo_age_s)
        mids_age = getattr(h, "mids_age_s", None)
        candle_age = getattr(h, "candle_age_s", None)
        bbo_age = getattr(h, "bbo_age_s", None)

        thr = getattr(self._ws, "_thread", None)
        if thr is not None:
            thread_alive = bool(getattr(thr, "is_alive", lambda: False)())
        else:
            # Sidecar client (`AI_QUANT_WS_SOURCE=sidecar`) has no in-process WS thread.
            # Treat it as "alive" when the sidecar transport is connected.
            thread_alive = True
            try:
                st_fn = getattr(self._ws, "status", None)
                if callable(st_fn):
                    st = st_fn()
                    if isinstance(st, dict) and "connected" in st:
                        thread_alive = bool(st.get("connected"))
            except Exception:
                thread_alive = True

        # Best-effort connected heuristic: if we have any recent channel updates.
        connected = False
        try:
            connected = (mids_age is not None and float(mids_age) < (self._stale_mid_s * 10.0)) or (
                candle_age is not None and float(candle_age) < (self._stale_candle_s * 10.0)
            )
        except Exception:
            connected = False

        return {
            "thread_alive": thread_alive,
            "connected": connected,
            "mids_age_s": mids_age,
            "candle_age_s": candle_age,
            "bbo_age_s": bbo_age,
        }

    def restart_ws(self, *, symbols: list[str], interval: str, candle_limit: int, user: str | None = None) -> None:
        """Hard restart the WS client in-process.

        This mirrors the approach already used in your existing daemons:
        - stop the old client
        - create a new HyperliquidWS instance
        - ensure subscriptions again
        """
        # Prefer an in-place restart if the WS client supports it (avoids stale references).
        restarted_in_place = False
        try:
            restart = getattr(self._ws, "restart", None)
            if callable(restart):
                restart()
                restarted_in_place = True
        except Exception:
            restarted_in_place = False

        if not restarted_in_place:
            try:
                self._ws.stop()
            except Exception:
                logger.debug("WS stop() failed during restart", exc_info=True)

            # Recreate and publish the module-global singleton so all imports see the new client.
            new_ws = self._ws_mod.HyperliquidWS()
            set_singleton = getattr(self._ws_mod, "_set_default_ws_singleton", None)
            if callable(set_singleton):
                set_singleton(new_ws)
                self._ws = new_ws
            else:
                # Backwards-compat fallback for modules that expose a plain object singleton.
                self._ws_mod.hl_ws = new_ws
                self._ws = self._ws_mod.hl_ws

        # Re-subscribe immediately.
        self.ensure(symbols=symbols, interval=interval, candle_limit=candle_limit, user=user)

    def get_latest_candle_open_key(self, symbol: str, *, interval: str) -> int | None:
        """Cheap key for the latest candle open time (may be in-progress).

        WS-first. Falls back to DB when WS cache is empty (e.g. right after reconnect).
        """
        sym = str(symbol).upper()
        interval_s = str(interval)

        # 1) WS quick path
        key = self._ws_latest_candle_open_ms(sym, interval_s)
        if key is not None:
            return int(key)

        # 2) DB fallback
        row = self._db_tail_candles(sym, interval_s, limit=1)
        if row:
            t0, _tclose0 = row[0]
            try:
                return int(t0) if t0 is not None else None
            except Exception:
                return None

        return None

    def get_last_closed_candle_key(self, symbol: str, *, interval: str, grace_ms: int = 2000) -> int | None:
        """Cheap key for the last *closed* candle.

        In close-signal mode we want a stable per-candle key. The HL candle stream often
        updates the in-progress candle. We treat the most recent candle as "closed" only when
        now_ms >= t_close - grace_ms, otherwise we use the previous candle.
        """
        sym = str(symbol).upper()
        interval_s = str(interval)
        grace = int(grace_ms)

        # 1) WS quick path
        key = self._ws_last_closed_candle_key(sym, interval_s, grace_ms=grace)
        if key is not None:
            return int(key)

        # 2) DB fallback
        rows = self._db_tail_candles(sym, interval_s, limit=2)
        if not rows:
            return None

        now = now_ms()
        # rows are ordered DESC by t
        t0, tclose0 = rows[0]
        t1, tclose1 = rows[1] if len(rows) > 1 else (None, None)

        def _key_for(t_ms: int | None, tclose_ms: int | None) -> int | None:
            try:
                if tclose_ms is not None:
                    return int(tclose_ms)
            except (TypeError, ValueError):
                pass
            try:
                if t_ms is not None:
                    return int(t_ms)
            except (TypeError, ValueError):
                return None
            return None

        # If the latest candle closes in the future, use the previous one when available.
        try:
            if tclose0 is not None and int(now) < (int(tclose0) - int(grace)) and t1 is not None:
                return _key_for(t1, tclose1)
        except (TypeError, ValueError):
            pass

        return _key_for(t0, tclose0)

    def _ws_latest_candle_open_ms(self, symbol: str, interval: str) -> int | None:
        ws = self._ws

        # Preferred: public helper on HyperliquidWS (if patched in).
        fn = getattr(ws, "get_latest_candle_times", None)
        if callable(fn):
            try:
                t_ms, _tclose_ms = fn(symbol, interval)
                if t_ms is not None:
                    return int(t_ms)
            except Exception:
                logger.debug("get_latest_candle_times failed for %s@%s", symbol, interval, exc_info=True)

        # Fallback: read private cache (still safe, but not ideal).
        try:
            lock = getattr(ws, "_lock", None)
            candles = getattr(ws, "_candles", None)
            if lock is None or candles is None:
                return None
            with lock:
                od = candles.get((symbol, interval))
                if not od:
                    return None
                last_t = next(reversed(od))
                last = od.get(last_t) or {}
                t_ms = last.get("timestamp") or last_t
                return int(t_ms)
        except Exception:
            logger.debug("WS candle cache read failed for %s@%s", symbol, interval, exc_info=True)
            return None

    def _ws_last_closed_candle_key(self, symbol: str, interval: str, *, grace_ms: int) -> int | None:
        ws = self._ws

        # Preferred: public helper on HyperliquidWS (if patched in).
        fn = getattr(ws, "get_last_closed_candle_times", None)
        if callable(fn):
            try:
                _t_ms, tclose_ms = fn(symbol, interval, grace_ms=int(grace_ms))
                if tclose_ms is not None:
                    return int(tclose_ms)
            except Exception:
                logger.debug("get_last_closed_candle_times failed for %s@%s", symbol, interval, exc_info=True)

        # Fallback: read private cache.
        try:
            lock = getattr(ws, "_lock", None)
            candles = getattr(ws, "_candles", None)
            if lock is None or candles is None:
                return None

            now = now_ms()
            with lock:
                od = candles.get((symbol, interval))
                if not od:
                    return None
                keys = list(od.keys())
                if not keys:
                    return None

                last_t = keys[-1]
                last = od.get(last_t) or {}
                tclose = last.get("T")

                if tclose is not None:
                    try:
                        tclose_i = int(tclose)
                        if int(now) < (tclose_i - int(grace_ms)) and len(keys) >= 2:
                            prev = od.get(keys[-2]) or {}
                            tclose_prev = prev.get("T")
                            if tclose_prev is not None:
                                return int(tclose_prev)
                            return int(prev.get("timestamp") or keys[-2])
                        return int(tclose_i)
                    except (TypeError, ValueError):
                        logger.debug("candle close key parse failed for %s@%s", symbol, interval, exc_info=True)

                # No close time. Best-effort return the last open time.
                try:
                    return int(last.get("timestamp") or last_t)
                except (TypeError, ValueError):
                    return None
        except Exception:
            logger.debug("WS closed candle cache read failed for %s@%s", symbol, interval, exc_info=True)
            return None

    def _candle_db_path(self, interval: str) -> str:
        if self._use_interval_candle_dbs:
            name = _sanitize_interval(interval)
            return os.path.join(self._candles_db_dir, f"candles_{name}.db")
        return self._db_path

    def _db_tail_candles(self, symbol: str, interval: str, *, limit: int) -> list[tuple[int | None, int | None]]:
        sym = str(symbol).upper()
        interval_s = str(interval)
        lim = max(1, int(limit))

        db_path = self._candle_db_path(interval_s)
        try:
            # Read-only when candle REST backfill is disabled (sidecar owns candles).
            if not self._rest_candle_backfill_enabled:
                uri = f"file:{db_path}?mode=ro"
                with sqlite3.connect(uri, uri=True, timeout=self._db_timeout_s) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT t, t_close FROM candles WHERE symbol = ? AND interval = ? ORDER BY t DESC LIMIT ?",
                        (sym, interval_s, lim),
                    )
                    rows = cur.fetchall() or []
            else:
                with sqlite3.connect(db_path, timeout=self._db_timeout_s) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT t, t_close FROM candles WHERE symbol = ? AND interval = ? ORDER BY t DESC LIMIT ?",
                        (sym, interval_s, lim),
                    )
                    rows = cur.fetchall() or []
            out: list[tuple[int | None, int | None]] = []
            for t_ms, tc_ms in rows:
                try:
                    t_i = int(t_ms) if t_ms is not None else None
                except Exception:
                    t_i = None
                try:
                    tc_i = int(tc_ms) if tc_ms is not None else None
                except Exception:
                    tc_i = None
                out.append((t_i, tc_i))
            return out
        except (sqlite3.Error, OSError) as exc:
            logger.warning("db tail candles failed for %s@%s: %s", sym, interval_s, exc)
            return []

    def get_candles_df(self, symbol: str, *, interval: str, min_rows: int) -> pd.DataFrame | None:
        sym = str(symbol).upper()
        interval_s = str(interval)
        want = int(min_rows)

        # TTL cache: avoid repeated DB reads for the same symbol+interval within one loop.
        cache_key = f"{sym}:{interval_s}"
        now_mono = time.monotonic()

        # Periodic cache cleanup: evict entries older than 10× TTL every 60s.
        if now_mono - getattr(self, "_last_cache_cleanup", 0.0) > 60.0:
            self._last_cache_cleanup = now_mono
            expired = [k for k, (t, _) in self._candle_cache.items() if now_mono - t > self._candle_cache_ttl_s * 10]
            for k in expired:
                del self._candle_cache[k]

        cached = self._candle_cache.get(cache_key)
        if cached is not None:
            ts, df_cached = cached
            if now_mono - ts < self._candle_cache_ttl_s:
                if df_cached is not None and len(df_cached) >= want:
                    return df_cached.copy()

        # 1) WS cache first
        df = None
        try:
            df = self._ws.get_candles_df(sym, interval_s, min_rows=want)
        except Exception:
            df = None

        if self._df_is_fresh_enough(df, interval=interval_s, min_rows=want):
            self._candle_cache[cache_key] = (now_mono, df)
            return df

        # 2) DB read fallback (covers cases where WS cache is empty after reconnect)
        df_db = self._read_candles_from_db(sym, interval_s, limit=max(want, want + 50))
        if self._df_is_fresh_enough(df_db, interval=interval_s, min_rows=want):
            self._candle_cache[cache_key] = (now_mono, df_db)
            return df_db

        # 3) REST candleSnapshot backfill (async) into DB.
        # IMPORTANT: Never block the main engine loop here. If candles are missing/stale,
        # schedule a background seed and return best-effort (may be None).
        self._maybe_schedule_rest_candle_backfill(sym, interval_s, want)

        # Best-effort return: prefer larger DF if present.
        df_best = df_db if (df_db is not None and len(df_db) >= (len(df) if df is not None else 0)) else df
        if df_best is None:
            return None
        result = df_best if len(df_best) >= want else None
        if result is not None:
            self._candle_cache[cache_key] = (now_mono, result)
        return result

    def get_mid_price(
        self, symbol: str, *, max_age_s: float | None = None, interval: str | None = None
    ) -> PriceQuote | None:
        sym = str(symbol).upper()
        max_age = self._stale_mid_s if max_age_s is None else float(max_age_s)

        # WS mid
        try:
            mid = self._ws.get_mid(sym, max_age_s=max_age)
        except Exception:
            mid = None
        if mid is not None:
            return PriceQuote(symbol=sym, price=float(mid), source="ws_mid", age_s=None)

        # WS BBO
        try:
            bbo_max_age = max_age if self._stale_bbo_s <= 0 else min(max_age, self._stale_bbo_s)
            bbo = self._ws.get_bbo(sym, max_age_s=bbo_max_age)
        except Exception:
            bbo = None
        if bbo is not None:
            bid, ask = bbo
            if bid and ask and bid > 0 and ask > 0:
                return PriceQuote(symbol=sym, price=(float(bid) + float(ask)) / 2.0, source="ws_bbo", age_s=None)

        # REST mids (optional; disabled when sidecar is the only market data source).
        if self._rest_enabled:
            quote = self._get_rest_mid(sym)
            if quote is not None:
                return quote

        # Final fallback: last candle close
        interval_s = str(interval) if interval else str(os.getenv("AI_QUANT_INTERVAL", "1h"))
        df = self.get_candles_df(sym, interval=interval_s, min_rows=2)
        if df is not None and not df.empty:
            try:
                px = float(df["Close"].iloc[-1])
                if px > 0:
                    return PriceQuote(symbol=sym, price=px, source="candle_close", age_s=None)
            except Exception:
                logger.debug("candle close price extraction failed for %s", sym, exc_info=True)

        return None

    def _get_rest_mid(self, symbol: str) -> PriceQuote | None:
        if (not self._rest_enabled) or (self._rest is None):
            return None
        sym = str(symbol).upper()
        cached = self._rest_mids.get(sym)
        if cached is not None:
            px, ts = cached
            age_s = max(0.0, (now_ms() - int(ts)) / 1000.0)
            if age_s <= self._stale_mid_s:
                return PriceQuote(symbol=sym, price=float(px), source="rest_mid", age_s=age_s)

        res = self._rest.all_mids()
        if not res.ok or not isinstance(res.data, dict):
            return None

        fetched_at = int(res.fetched_at_ms or now_ms())
        for k, v in res.data.items():
            try:
                px = float(v)
            except Exception:
                continue
            self._rest_mids[str(k).upper()] = (px, fetched_at)

        cached = self._rest_mids.get(sym)
        if cached is None:
            return None
        px, ts = cached
        age_s = max(0.0, (now_ms() - int(ts)) / 1000.0)
        return PriceQuote(symbol=sym, price=float(px), source="rest_mid", age_s=age_s)

    def _df_is_fresh_enough(self, df: pd.DataFrame | None, *, interval: str, min_rows: int) -> bool:
        if df is None or df.empty or len(df) < int(min_rows):
            return False
        try:
            interval_ms = _interval_to_ms(interval)
            interval_s = interval_ms / 1000.0
            # Scale staleness with interval: 3 bars or 5 minutes, whichever is larger.
            max_stale_s = max(interval_s * 3.0, 300.0)
            now = now_ms()
            t_close = df["T"].iloc[-1] if "T" in df.columns else None
            if t_close is None or pd.isna(t_close):
                t_close = int(df["timestamp"].iloc[-1]) + int(interval_ms)
            age_s = max(0.0, (now - int(t_close)) / 1000.0)
            return age_s <= max_stale_s
        except Exception:
            # If we cannot compute freshness, treat it as unusable.
            return False

    def _read_candles_from_db(self, symbol: str, interval: str, *, limit: int) -> pd.DataFrame | None:
        """Read candles directly from SQLite into the same column names used by your strategy."""
        rows: list[tuple] = []
        try:
            db_path = self._candle_db_path(interval)
            if not self._rest_candle_backfill_enabled:
                uri = f"file:{db_path}?mode=ro"
                with sqlite3.connect(uri, uri=True, timeout=self._db_timeout_s) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT t, t_close, o, h, l, c, v, n FROM candles WHERE symbol = ? AND interval = ? ORDER BY t DESC LIMIT ?",
                        (symbol, interval, int(limit)),
                    )
                    rows = cur.fetchall()
            else:
                with sqlite3.connect(db_path, timeout=self._db_timeout_s) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT t, t_close, o, h, l, c, v, n FROM candles WHERE symbol = ? AND interval = ? ORDER BY t DESC LIMIT ?",
                        (symbol, interval, int(limit)),
                    )
                    rows = cur.fetchall()
        except Exception:
            rows = []

        if not rows:
            return None
        # We fetched newest-first (DESC). Reverse to chronological (ASC) for indicators.
        rows = list(reversed(rows))

        import math

        def _finite_or_none(val: Any) -> float | None:
            if val is None:
                return None
            f = float(val)
            return f if math.isfinite(f) else None

        out_rows: list[dict[str, Any]] = []
        nan_inf_count = 0
        for t_ms, T_ms, o, h, low_val, c, v, n in rows:
            ohlcv_raw = {"Open": o, "High": h, "Low": low_val, "Close": c, "Volume": v}
            ohlcv_clean: dict[str, float | None] = {}
            for field_name, raw_val in ohlcv_raw.items():
                cleaned = _finite_or_none(raw_val)
                if raw_val is not None and cleaned is None:
                    nan_inf_count += 1
                ohlcv_clean[field_name] = cleaned
            out_rows.append(
                {
                    "timestamp": int(t_ms),
                    "T": int(T_ms) if T_ms is not None else None,
                    "s": symbol,
                    "i": interval,
                    **ohlcv_clean,
                    "n": int(n) if n is not None else None,
                }
            )
        if nan_inf_count > 0:
            logger.warning(
                "[%s@%s] %d non-finite (NaN/Inf) candle value(s) replaced with None",
                symbol,
                interval,
                nan_inf_count,
            )

        df = pd.DataFrame(out_rows)
        if df.empty:
            return None
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Gap detection: warn when candles have missing bars (produces wrong EMA/ATR/ADX).
        if len(df) > 1:
            try:
                expected_interval_ms = _interval_to_ms(interval)
                diffs = df["timestamp"].diff().dropna()
                if not diffs.empty:
                    max_gap = diffs.max()
                    if max_gap > expected_interval_ms * 1.5:
                        gap_count = int((diffs > expected_interval_ms * 1.5).sum())
                        logger.warning(
                            "[%s] %d candle gap(s) detected (max %.0fs, expected %.0fs)",
                            symbol,
                            gap_count,
                            max_gap / 1000.0,
                            expected_interval_ms / 1000.0,
                        )
            except Exception:
                logger.debug("candle gap detection failed for %s@%s", symbol, interval, exc_info=True)

        return df

    def _ensure_rest_candle_pool(self) -> ThreadPoolExecutor:
        with self._rest_candle_lock:
            if self._rest_candle_pool is None:
                self._rest_candle_pool = ThreadPoolExecutor(
                    max_workers=int(self._rest_candle_backfill_workers),
                    thread_name_prefix="aiq_rest_candles",
                )
            return self._rest_candle_pool

    def _rest_backfill_candles_task(self, symbol: str, interval: str, want: int) -> tuple[bool, int, str | None]:
        """Fetch candles via REST and upsert into DB. Returns (ok, n_rows, err)."""
        if self._rest is None:
            return False, 0, "REST disabled"
        sym = str(symbol).upper()
        interval_s = str(interval)
        want_i = int(want)

        interval_ms = _interval_to_ms(interval_s)
        end_ms = now_ms()
        start_ms = end_ms - int(interval_ms) * int(max(want_i, 200) + 50)

        try:
            res = self._rest.candle_snapshot(symbol=sym, interval=interval_s, start_ms=start_ms, end_ms=end_ms)
        except Exception as e:
            return False, 0, str(e)

        if not res.ok:
            return False, 0, str(res.error or "rest not ok")
        if not isinstance(res.data, list) or not res.data:
            return False, 0, "no data"

        try:
            self._upsert_candles(sym, interval_s, res.data)
        except Exception as e:
            return False, 0, f"upsert failed: {e}"

        return True, int(len(res.data)), None

    def _on_rest_candle_backfill_done(self, key: tuple[str, str], fut: Future) -> None:
        now = now_ms()
        ok = False
        n_rows = 0
        err: str | None = None
        try:
            ok, n_rows, err = fut.result()
        except Exception as e:
            ok, n_rows, err = False, 0, str(e)

        with self._rest_candle_lock:
            self._rest_candle_inflight.pop(key, None)

            if ok and n_rows > 0:
                self._rest_candle_failures[key] = 0
                self._rest_candle_last_err.pop(key, None)
                delay_ms = int(max(0.0, float(self._rest_candle_backfill_success_cooldown_s)) * 1000.0)
                self._rest_candle_next_allowed_ms[key] = int(now) + delay_ms
                return

            failures = int(self._rest_candle_failures.get(key, 0)) + 1
            self._rest_candle_failures[key] = failures
            if err:
                self._rest_candle_last_err[key] = str(err)[:500]

            base_s = max(1.0, float(self._rest_candle_backfill_failure_cooldown_s))
            max_s = max(base_s, float(self._rest_candle_backfill_max_cooldown_s))
            delay_s = min(max_s, base_s * (2.0 ** max(0, failures - 1)))
            self._rest_candle_next_allowed_ms[key] = int(now) + int(delay_s * 1000.0)

    def _maybe_schedule_rest_candle_backfill(self, symbol: str, interval: str, want: int) -> None:
        if not self._rest_candle_backfill_enabled:
            return

        sym = str(symbol).upper()
        interval_s = str(interval)
        key = (sym, interval_s)
        now = now_ms()

        with self._rest_candle_lock:
            next_allowed = int(self._rest_candle_next_allowed_ms.get(key, 0) or 0)
            if int(now) < next_allowed:
                return

            fut = self._rest_candle_inflight.get(key)
            if fut is not None and not fut.done():
                return
            if fut is not None and fut.done():
                self._rest_candle_inflight.pop(key, None)

            if len(self._rest_candle_inflight) >= int(self._rest_candle_backfill_max_inflight):
                return

            pool = self._ensure_rest_candle_pool()
            fut2 = pool.submit(self._rest_backfill_candles_task, sym, interval_s, int(want))
            self._rest_candle_inflight[key] = fut2

            # Avoid rescheduling immediately while in-flight.
            self._rest_candle_next_allowed_ms[key] = int(now) + int(5_000)

            try:
                fut2.add_done_callback(lambda f, k=key: self._on_rest_candle_backfill_done(k, f))
            except Exception:
                # If callbacks are unavailable for some reason, we'll clean up on the next call.
                logger.debug("failed to attach REST candle backfill callback for %s", key, exc_info=True)

    def close(self):
        if self._rest_candle_pool is not None:
            self._rest_candle_pool.shutdown(wait=False)

    def _upsert_candles(self, symbol: str, interval: str, candles: list[dict[str, Any]]) -> None:
        import math

        db_path = self._candle_db_path(interval)
        try:
            conn = sqlite3.connect(db_path, timeout=self._db_timeout_s)
        except sqlite3.OperationalError as e:
            logger.warning("candle upsert: failed to connect for %s/%s: %s", symbol, interval, e)
            return
        try:
            cur = conn.cursor()
            cur.execute(
                "CREATE TABLE IF NOT EXISTS candles (symbol TEXT, interval TEXT, t INTEGER, t_close INTEGER, o REAL, h REAL, l REAL, c REAL, v REAL, n INTEGER, updated_at TEXT, PRIMARY KEY (symbol, interval, t))"
            )
            updated_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
            nan_inf_skipped = 0
            for c in candles:
                try:
                    ohlcv = [
                        float(c.get("o")),
                        float(c.get("h")),
                        float(c.get("l")),
                        float(c.get("c")),
                        float(c.get("v")),
                    ]
                    if not all(math.isfinite(v) for v in ohlcv):
                        nan_inf_skipped += 1
                        continue
                    cur.execute(
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
                            symbol,
                            interval,
                            int(c.get("t")),
                            int(c.get("T") if c.get("T") is not None else c.get("t_close")),
                            ohlcv[0],
                            ohlcv[1],
                            ohlcv[2],
                            ohlcv[3],
                            ohlcv[4],
                            int(c.get("n")) if c.get("n") is not None else None,
                            updated_at,
                        ),
                    )
                except (TypeError, ValueError) as e:
                    logger.warning("Skipping bad candle for %s: %s", symbol, e)
                    continue
                except sqlite3.OperationalError as e:
                    logger.warning("candle upsert: DB lock/timeout for %s/%s: %s", symbol, interval, e)
                    break
            if nan_inf_skipped > 0:
                logger.warning(
                    "[%s@%s] skipped %d candle(s) with non-finite OHLCV during REST backfill upsert",
                    symbol,
                    interval,
                    nan_inf_skipped,
                )
            conn.commit()
        except sqlite3.OperationalError as e:
            logger.warning("candle upsert: commit failed for %s/%s: %s", symbol, interval, e)
        finally:
            conn.close()
