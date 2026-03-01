#!/usr/bin/env python3
from bisect import bisect_left
import hmac
import json
import mimetypes
import os
import re
import sqlite3
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


AIQ_ROOT = Path(__file__).resolve().parents[1]
MONITOR_DIR = Path(__file__).resolve().parent
STATIC_DIR = MONITOR_DIR / "static"

if str(AIQ_ROOT) not in sys.path:
    sys.path.insert(0, str(AIQ_ROOT))
if str(MONITOR_DIR) not in sys.path:
    sys.path.insert(0, str(MONITOR_DIR))

from heartbeat import parse_last_heartbeat  # noqa: E402

try:
    import bt_runtime as _bt_runtime  # noqa: E402

    _BT_RUNTIME_OK = True
except ImportError:
    _bt_runtime = None  # type: ignore[assignment]
    _BT_RUNTIME_OK = False


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(str(raw).strip())
    except Exception:
        return int(default)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return float(default)
    try:
        return float(str(raw).strip())
    except Exception:
        return float(default)

def _env_str(name: str, default: str = "") -> str:
    raw = os.getenv(name)
    if raw is None:
        return str(default or "")
    s = str(raw).strip()
    return s if s else str(default or "")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _is_local_bind(bind: str) -> bool:
    b = str(bind or "").strip().lower()
    return b in {"127.0.0.1", "localhost", "::1"}


def _monitor_max_post_body_bytes() -> int:
    raw = _env_int("AIQ_MONITOR_MAX_POST_BODY_BYTES", 1_048_576)
    return int(max(1024, min(16 * 1024 * 1024, int(raw))))


def _monitor_bind_security_error(*, bind: str, token: str, tls_terminated: bool) -> str:
    if _is_local_bind(bind):
        return ""
    if not token:
        return ""
    if bool(tls_terminated):
        return ""
    return (
        "Refusing non-local monitor bind with AIQ_MONITOR_TOKEN without TLS termination. "
        "Use an HTTPS reverse proxy and set AIQ_MONITOR_TLS_TERMINATED=1."
    )


def _monitor_request_queue_size() -> int:
    raw = _env_int("AIQ_MONITOR_REQUEST_QUEUE_SIZE", 128)
    return int(max(1, min(1024, int(raw))))


class _PerIpTokenBucketLimiter:
    def __init__(self, *, rate_per_s: float, burst: float, max_ips: int = 10000):
        self._rate_per_s = float(max(0.001, rate_per_s))
        self._burst = float(max(1.0, burst))
        self._max_ips = int(max(128, max_ips))
        self._lock = threading.Lock()
        self._state: dict[str, tuple[float, float]] = {}

    def allow(self, ip: str, *, now_s: float | None = None) -> bool:
        now = time.monotonic() if now_s is None else float(now_s)
        key = str(ip or "").strip() or "unknown"
        with self._lock:
            if len(self._state) > self._max_ips and key not in self._state:
                oldest_key = min(self._state.items(), key=lambda kv: kv[1][1])[0]
                self._state.pop(oldest_key, None)

            tokens, updated = self._state.get(key, (self._burst, now))
            elapsed = max(0.0, now - float(updated))
            tokens = min(self._burst, float(tokens) + (elapsed * self._rate_per_s))
            allowed = tokens >= 1.0
            if allowed:
                tokens -= 1.0
            self._state[key] = (tokens, now)
            return bool(allowed)


class _ActiveRequestLimiter:
    def __init__(self, *, max_active: int):
        self._max_active = int(max(1, max_active))
        self._active = 0
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        with self._lock:
            if self._active >= self._max_active:
                return False
            self._active += 1
            return True

    def release(self) -> None:
        with self._lock:
            if self._active > 0:
                self._active -= 1


_API_RATE_LIMIT_ENABLED = _env_bool("AIQ_MONITOR_API_RATE_LIMIT_ENABLED", True)
_API_RATE_LIMIT_RPS = float(max(0.1, min(_env_float("AIQ_MONITOR_API_RATE_RPS", 10.0), 1000.0)))
_API_RATE_LIMIT_BURST = float(max(1.0, min(float(_env_int("AIQ_MONITOR_API_RATE_BURST", 10)), 1000.0)))
_API_RATE_LIMIT_MAX_IPS = int(max(128, min(_env_int("AIQ_MONITOR_API_RATE_MAX_IPS", 10000), 200000)))
_API_RATE_LIMITER = _PerIpTokenBucketLimiter(
    rate_per_s=_API_RATE_LIMIT_RPS,
    burst=_API_RATE_LIMIT_BURST,
    max_ips=_API_RATE_LIMIT_MAX_IPS,
)
_MAX_POST_BODY_BYTES = _monitor_max_post_body_bytes()
_ACTIVE_REQUEST_LIMITER = _ActiveRequestLimiter(
    max_active=int(max(1, min(_env_int("AIQ_MONITOR_MAX_ACTIVE_REQUESTS", 256), 20000)))
)


def _json(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")


def _utc_now_ms() -> int:
    return int(time.time() * 1000)


_INTERVAL_RE = re.compile(r"^([0-9]+)([mhd])$", re.IGNORECASE)


def _interval_sort_key(interval: str) -> tuple[int, str]:
    s = str(interval or "").strip().lower()
    m = _INTERVAL_RE.match(s)
    if not m:
        return (10**9, s)
    n = int(m.group(1))
    unit = m.group(2).lower()
    mult = {"m": 1, "h": 60, "d": 60 * 24}.get(unit, 10**6)
    return (n * mult, s)


def effective_trader_interval() -> str:
    """Best-effort candle interval used by the live/paper trader (default 1h)."""
    return str(os.getenv("AI_QUANT_INTERVAL") or "1h").strip() or "1h"


_TRADER_INTERVAL_LOCK = threading.RLock()
_TRADER_INTERVAL_CACHE: dict[str, tuple[int, str]] = {}


def effective_trader_interval_for_mode(mode: str) -> str:
    """Infer trader candle interval per mode when AI_QUANT_INTERVAL isn't set."""
    env = str(os.getenv("AI_QUANT_INTERVAL") or "").strip()
    if env:
        return env

    mode2 = (mode or "paper").strip().lower() or "paper"
    now_ms = _utc_now_ms()
    cache_max_age_ms = 30_000
    with _TRADER_INTERVAL_LOCK:
        cached = _TRADER_INTERVAL_CACHE.get(mode2)
        if cached and (now_ms - cached[0]) < cache_max_age_ms:
            return cached[1]

    iv: str | None = None
    try:
        db_path, _log_path = mode_paths(mode2)
        if db_path.exists():
            con = connect_db_ro(db_path)
            try:
                iv = infer_interval_from_db(con)
            finally:
                con.close()
    except Exception:
        iv = None

    out = iv or "1h"
    with _TRADER_INTERVAL_LOCK:
        _TRADER_INTERVAL_CACHE[mode2] = (now_ms, out)
    return out


def effective_monitor_interval() -> str:
    """Interval used by the monitor for universe selection (may differ from trader)."""
    return str(os.getenv("AIQ_MONITOR_INTERVAL") or os.getenv("AI_QUANT_INTERVAL") or "1m").strip() or "1m"


_CANDLE_INTERVALS_LOCK = threading.RLock()
_CANDLE_INTERVALS_CACHE: tuple[int, list[str]] | None = None


def list_available_candle_intervals(*, default: str | None = None) -> list[str]:
    """Return available candle intervals (from per-interval candle DB files) with caching."""
    global _CANDLE_INTERVALS_CACHE

    now_ms = _utc_now_ms()
    cache_max_age_ms = 30_000
    with _CANDLE_INTERVALS_LOCK:
        cached = _CANDLE_INTERVALS_CACHE
        if cached and (now_ms - cached[0]) < cache_max_age_ms:
            intervals = list(cached[1])
        else:
            intervals: list[str] = []
            try:
                raw_dir = str(os.getenv("AI_QUANT_CANDLES_DB_DIR", "") or "").strip()
                candles_dir = Path(raw_dir) if raw_dir else (AIQ_ROOT / "candles_dbs")
                for p in candles_dir.glob("candles_*.db"):
                    name = p.name
                    if not name.startswith("candles_") or not name.endswith(".db"):
                        continue
                    iv = name[len("candles_") : -len(".db")]
                    iv = str(iv or "").strip().lower()
                    if iv:
                        intervals.append(iv)
            except Exception:
                intervals = []

            # De-dupe + stable sort.
            intervals = sorted({iv for iv in intervals if iv}, key=_interval_sort_key)
            _CANDLE_INTERVALS_CACHE = (now_ms, list(intervals))

    # Ensure the default interval is offered even if the DB file isn't present yet.
    d = str(default or "").strip().lower()
    if d and d not in intervals:
        intervals = [d] + intervals
    if not intervals:
        intervals = ["1m", "1h"]
    return intervals

def effective_fee_rate() -> float:
    """Best-effort all-in fee rate (single fill). Used for equity estimation only."""
    raw = os.getenv("AIQ_MONITOR_FEE_RATE")
    if raw:
        try:
            return max(0.0, float(str(raw).strip()))
        except Exception:
            pass

    try:
        taker = float(os.getenv("HL_PERP_TAKER_FEE_RATE", "0.00045"))
    except Exception:
        taker = 0.00045
    try:
        maker = float(os.getenv("HL_PERP_MAKER_FEE_RATE", "0.00015"))
    except Exception:
        maker = 0.00015

    mode = os.getenv("HL_FEE_MODE", "taker").strip().lower()
    protocol = maker if mode == "maker" else taker

    try:
        ref = float(os.getenv("HL_REFERRAL_DISCOUNT_PCT", "0"))
    except Exception:
        ref = 0.0
    ref = max(0.0, min(100.0, ref))
    discount_mult = 1.0 - (ref / 100.0)

    try:
        builder = float(os.getenv("HL_BUILDER_FEE_RATE", "0.0"))
    except Exception:
        builder = 0.0

    rate = (protocol * discount_mult) + builder
    try:
        return max(0.0, float(rate))
    except Exception:
        return 0.00045


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _utc_day(now_ms: int) -> str:
    try:
        return datetime.fromtimestamp(int(now_ms) / 1000.0, tz=timezone.utc).date().isoformat()
    except Exception:
        return ""


def _parse_iso_ts_ms(ts: str | None) -> int | None:
    """Best-effort parse ISO timestamp to epoch milliseconds."""
    raw = str(ts or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        # datetime.fromisoformat() does not accept a bare Z suffix.
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


_KERNEL_STATE_HOME = Path("~/.mei/kernel_state.json").expanduser()


def _find_kernel_state_path(db_path: Path) -> Path | None:
    """Locate the kernel state JSON — next to the trading DB, or ~/.mei fallback."""
    beside_db = db_path.parent / "kernel_state.json"
    if beside_db.exists():
        return beside_db
    if _KERNEL_STATE_HOME.exists():
        return _KERNEL_STATE_HOME
    return None


def get_kernel_equity(
    db_path: Path,
    mids: dict[str, float],
) -> dict[str, Any]:
    """Compute mark-to-market equity via the Rust kernel.

    Returns a dict with ``ok``, ``equity_usd``, ``cash_usd``, ``state_path``, and
    optionally ``error``.
    """
    if not _BT_RUNTIME_OK:
        return {"ok": False, "error": "bt_runtime_not_available"}

    state_path = _find_kernel_state_path(db_path)
    if state_path is None:
        return {"ok": False, "error": "kernel_state_not_found"}

    try:
        state_json = _bt_runtime.load_state(str(state_path))
    except Exception as e:
        return {"ok": False, "error": f"load_state_failed:{e}", "state_path": str(state_path)}

    # Extract cash_usd from the state for reference.
    cash_usd: float | None = None
    try:
        state = json.loads(state_json)
        cash_usd = float(state.get("cash_usd", 0.0))
    except Exception:
        pass

    # Build prices dict from mids (kernel expects symbol -> price).
    prices_json = json.dumps(mids) if mids else "{}"

    try:
        equity = _bt_runtime.get_equity(state_json, prices_json)
        return {
            "ok": True,
            "equity_usd": float(equity),
            "cash_usd": cash_usd,
            "state_path": str(state_path),
        }
    except Exception as e:
        return {"ok": False, "error": f"get_equity_failed:{e}", "state_path": str(state_path)}


_HL_ADDR_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_HL_BAL_LOCK = threading.RLock()
_HL_BAL_CACHE: tuple[int, dict[str, Any]] | None = None
_HL_ADDR_CACHE: tuple[int, str] | None = None


def _infer_hl_main_address() -> str | None:
    """Infer the Hyperliquid main address for balance reads (best-effort, read-only)."""
    # Prefer explicit env to avoid reading any local secrets file.
    raw = _env_str("AIQ_MONITOR_HL_MAIN_ADDRESS", "") or _env_str("AIQ_MONITOR_MAIN_ADDRESS", "")
    if raw and _HL_ADDR_RE.match(raw):
        return raw

    # Fall back to a secrets file path (we only read main_address).
    secrets_path = _env_str("AIQ_MONITOR_SECRETS_PATH", "") or _env_str("AI_QUANT_SECRETS_PATH", "")
    if not secrets_path:
        secrets_path = str(Path("~/.config/openclaw/ai-quant-secrets.json").expanduser())
    secrets_path = os.path.expanduser(str(secrets_path))

    try:
        p = Path(secrets_path)
    except Exception:
        return None
    if not p.exists():
        return None

    try:
        data = json.loads(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    addr = str((data or {}).get("main_address") or "").strip()
    return addr if _HL_ADDR_RE.match(addr) else None


def fetch_hl_balance() -> dict[str, Any] | None:
    """Fetch Hyperliquid balances via REST (cached)."""
    global _HL_BAL_CACHE, _HL_ADDR_CACHE

    if not _env_bool("AIQ_MONITOR_HL_BALANCE_ENABLE", True):
        return None

    now_ms = _utc_now_ms()

    ttl_s = _env_float("AIQ_MONITOR_HL_BALANCE_TTL_S", 5.0)
    ttl_ms = int(max(0.5, float(ttl_s)) * 1000.0)

    with _HL_BAL_LOCK:
        cached = _HL_BAL_CACHE
        if cached and (now_ms - cached[0]) < ttl_ms:
            return dict(cached[1])

        addr_cached = _HL_ADDR_CACHE
        if addr_cached and (now_ms - addr_cached[0]) < 30_000:
            main_address = addr_cached[1]
        else:
            main_address = _infer_hl_main_address()
            if main_address:
                _HL_ADDR_CACHE = (now_ms, main_address)

    if not main_address:
        return None

    timeout_s = _env_float("AIQ_MONITOR_HL_TIMEOUT_S", 4.0)
    base_url = _env_str("AIQ_MONITOR_HL_BASE_URL", "") or _env_str("HL_INFO_BASE_URL", "") or ""

    try:
        from hyperliquid.info import Info  # type: ignore
        from hyperliquid.utils import constants  # type: ignore

        info = Info(base_url or constants.MAINNET_API_URL, skip_ws=True, timeout=float(timeout_s))
        st = info.user_state(main_address) or {}
        margin = st.get("marginSummary") or {}
        account_value = float(margin.get("accountValue") or 0.0)
        total_margin_used = float(margin.get("totalMarginUsed") or 0.0)
        withdrawable = float(st.get("withdrawable") or 0.0)
        out = {
            "ok": True,
            "source": "hyperliquid_rest",
            "account_value_usd": account_value,
            "withdrawable_usd": withdrawable,
            "total_margin_used_usd": total_margin_used,
            "ts_ms": now_ms,
        }
    except Exception as e:
        out = {
            "ok": False,
            "source": "hyperliquid_rest",
            "error": str(e),
            "ts_ms": now_ms,
        }

    with _HL_BAL_LOCK:
        _HL_BAL_CACHE = (now_ms, dict(out))
    return dict(out)


def connect_db_ro(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=1.0)
    con.row_factory = sqlite3.Row
    return con


def _fetchall(con: sqlite3.Connection, q: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cur = con.cursor()
    cur.execute(q, params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def _fetchone(con: sqlite3.Connection, q: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    cur = con.cursor()
    cur.execute(q, params)
    row = cur.fetchone()
    return dict(row) if row else None


def infer_interval_from_db(con: sqlite3.Connection) -> str | None:
    """Best-effort infer candle interval from the local trading DB."""
    try:
        row = _fetchone(con, "SELECT interval FROM candles LIMIT 1")
        iv = str(row.get("interval") or "").strip().lower() if row else ""
        return iv or None
    except Exception:
        return None


def _placeholders(n: int) -> str:
    return ",".join(["?"] * n) if n > 0 else ""


def list_recent_symbols(
    con: sqlite3.Connection,
    *,
    candles_con: sqlite3.Connection | None = None,
    interval: str,
    now_ms: int,
    candle_window_ms: int = 6 * 60 * 60 * 1000,
    trades_window_h: int = 24,
    oms_window_h: int = 24,
    limit: int = 200,
    has_oms: bool,
) -> list[str]:
    symbols: list[str] = []

    ccon = candles_con or con
    candle_cutoff = now_ms - int(candle_window_ms)
    rows = _fetchall(
        ccon,
        """
        SELECT symbol, MAX(COALESCE(t_close, t)) AS last_t
        FROM candles
        WHERE interval = ?
          AND COALESCE(t_close, t) >= ?
        GROUP BY symbol
        ORDER BY last_t DESC
        LIMIT ?
        """,
        (interval, candle_cutoff, int(limit)),
    )
    symbols.extend([str(r["symbol"]).upper() for r in rows if r.get("symbol")])

    trades_cutoff_iso = _iso_utc(datetime.now(timezone.utc) - timedelta(hours=int(trades_window_h)))
    trade_syms = _fetchall(
        con,
        """
        SELECT DISTINCT symbol
        FROM trades
        WHERE timestamp >= ?
        ORDER BY symbol
        """,
        (trades_cutoff_iso,),
    )
    symbols.extend([str(r["symbol"]).upper() for r in trade_syms if r.get("symbol")])

    if has_oms:
        oms_cutoff_ms = now_ms - int(oms_window_h * 60 * 60 * 1000)
        oms_syms = _fetchall(
            con,
            """
            SELECT DISTINCT symbol
            FROM oms_intents
            WHERE created_ts_ms >= ?
            ORDER BY symbol
            """,
            (oms_cutoff_ms,),
        )
        symbols.extend([str(r["symbol"]).upper() for r in oms_syms if r.get("symbol")])

    out: list[str] = []
    seen: set[str] = set()
    for s in symbols:
        s2 = (s or "").strip().upper()
        if not s2 or s2 in seen:
            continue
        seen.add(s2)
        out.append(s2)
    return out


def compute_open_positions(con: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    positions: dict[str, dict[str, Any]] = {}
    rows = _fetchall(
        con,
        """
        SELECT t.id, t.timestamp, t.symbol, t.type, t.price, t.size, t.confidence, t.entry_atr, t.leverage, t.margin_used
        FROM trades t
        JOIN (
            SELECT symbol, MAX(id) AS open_id
            FROM trades
            WHERE action = 'OPEN'
            GROUP BY symbol
        ) lo ON lo.symbol = t.symbol AND lo.open_id = t.id
        LEFT JOIN (
            SELECT symbol, MAX(id) AS close_id
            FROM trades
            WHERE action = 'CLOSE'
            GROUP BY symbol
        ) lc ON lc.symbol = t.symbol
        WHERE lc.close_id IS NULL OR t.id > lc.close_id
        """,
    )

    cur = con.cursor()
    for r in rows:
        symbol = str(r.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        pos_type = str(r.get("type") or "").strip().upper()
        if pos_type not in {"LONG", "SHORT"}:
            continue

        try:
            open_trade_id = int(r["id"])
            avg_entry = float(r["price"])
            net_size = float(r["size"])
        except Exception:
            continue
        if avg_entry <= 0 or net_size <= 0:
            continue

        entry_atr = 0.0
        try:
            entry_atr = float(r.get("entry_atr") or 0.0)
        except Exception:
            entry_atr = 0.0

        # Replay ADD/REDUCE to rebuild net position size + avg entry.
        cur.execute(
            """
            SELECT action, price, size, entry_atr
            FROM trades
            WHERE symbol = ?
              AND id > ?
              AND action IN ('ADD', 'REDUCE')
            ORDER BY id ASC
            """,
            (symbol, open_trade_id),
        )
        for act, px, sz, fill_atr in cur.fetchall():
            try:
                px = float(px)
                sz = float(sz)
            except Exception:
                continue
            if px <= 0 or sz <= 0:
                continue
            if act == "ADD":
                new_total = net_size + sz
                if new_total > 0:
                    avg_entry = ((avg_entry * net_size) + (px * sz)) / new_total
                    try:
                        fill_atr_f = float(fill_atr) if fill_atr is not None else None
                    except Exception:
                        fill_atr_f = None
                    if fill_atr_f and fill_atr_f > 0:
                        entry_atr = ((entry_atr * net_size) + (fill_atr_f * sz)) / new_total if entry_atr > 0 else fill_atr_f
                    net_size = new_total
            elif act == "REDUCE":
                net_size -= sz
                if net_size <= 0:
                    net_size = 0.0
                    break

        if net_size <= 0:
            continue

        leverage = 1.0
        try:
            leverage = float(r.get("leverage") or 1.0)
        except Exception:
            leverage = 1.0
        if leverage <= 0:
            leverage = 1.0

        margin_used = None
        try:
            margin_used = float(r.get("margin_used")) if r.get("margin_used") is not None else None
        except Exception:
            margin_used = None
        if margin_used is None:
            try:
                margin_used = abs(net_size) * avg_entry / leverage
            except Exception:
                margin_used = 0.0

        positions[symbol] = {
            "symbol": symbol,
            "type": pos_type,
            "open_trade_id": open_trade_id,
            "open_timestamp": r.get("timestamp"),
            "entry_price": avg_entry,
            "size": net_size,
            "confidence": r.get("confidence"),
            "entry_atr": entry_atr,
            "leverage": leverage,
            "margin_used": margin_used,
        }

    return positions


def compute_open_position_for_symbol(con: sqlite3.Connection, symbol: str) -> dict[str, Any] | None:
    sym = (symbol or "").strip().upper()
    if not sym:
        return None

    close_row = _fetchone(con, "SELECT MAX(id) AS close_id FROM trades WHERE symbol = ? AND action = 'CLOSE'", (sym,))
    close_id = 0
    try:
        close_id = int(close_row["close_id"]) if close_row and close_row.get("close_id") is not None else 0
    except Exception:
        close_id = 0

    open_row = _fetchone(
        con,
        """
        SELECT id, timestamp, symbol, type, price, size, confidence, entry_atr, leverage, margin_used
        FROM trades
        WHERE symbol = ?
          AND action = 'OPEN'
          AND id > ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (sym, close_id),
    )
    if not open_row:
        return None

    pos_type = str(open_row.get("type") or "").strip().upper()
    if pos_type not in {"LONG", "SHORT"}:
        return None

    try:
        open_trade_id = int(open_row["id"])
        avg_entry = float(open_row["price"])
        net_size = float(open_row["size"])
    except Exception:
        return None
    if avg_entry <= 0 or net_size <= 0:
        return None

    entry_atr = 0.0
    try:
        entry_atr = float(open_row.get("entry_atr") or 0.0)
    except Exception:
        entry_atr = 0.0

    cur = con.cursor()
    cur.execute(
        """
        SELECT action, price, size, entry_atr
        FROM trades
        WHERE symbol = ?
          AND id > ?
          AND action IN ('ADD', 'REDUCE')
        ORDER BY id ASC
        """,
        (sym, open_trade_id),
    )
    for act, px, sz, fill_atr in cur.fetchall():
        try:
            px = float(px)
            sz = float(sz)
        except Exception:
            continue
        if px <= 0 or sz <= 0:
            continue
        if act == "ADD":
            new_total = net_size + sz
            if new_total > 0:
                avg_entry = ((avg_entry * net_size) + (px * sz)) / new_total
                try:
                    fill_atr_f = float(fill_atr) if fill_atr is not None else None
                except Exception:
                    fill_atr_f = None
                if fill_atr_f and fill_atr_f > 0:
                    entry_atr = ((entry_atr * net_size) + (fill_atr_f * sz)) / new_total if entry_atr > 0 else fill_atr_f
                net_size = new_total
        elif act == "REDUCE":
            net_size -= sz
            if net_size <= 0:
                return None

    leverage = 1.0
    try:
        leverage = float(open_row.get("leverage") or 1.0)
    except Exception:
        leverage = 1.0
    if leverage <= 0:
        leverage = 1.0

    margin_used = None
    try:
        margin_used = float(open_row.get("margin_used")) if open_row.get("margin_used") is not None else None
    except Exception:
        margin_used = None
    if margin_used is None:
        try:
            margin_used = abs(net_size) * avg_entry / leverage
        except Exception:
            margin_used = 0.0

    return {
        "symbol": sym,
        "type": pos_type,
        "open_trade_id": open_trade_id,
        "open_timestamp": open_row.get("timestamp"),
        "entry_price": avg_entry,
        "size": net_size,
        "confidence": open_row.get("confidence"),
        "entry_atr": entry_atr,
        "leverage": leverage,
        "margin_used": margin_used,
    }


def fetch_last_rows_by_symbol(
    con: sqlite3.Connection, table: str, symbol_col: str, id_col: str, symbols: list[str], columns: list[str]
) -> dict[str, dict[str, Any]]:
    if not symbols:
        return {}
    cols = ", ".join(columns)
    ph = _placeholders(len(symbols))
    q = f"""
    SELECT t.{symbol_col} AS symbol, {cols}
    FROM {table} t
    JOIN (
        SELECT {symbol_col} AS sym, MAX({id_col}) AS max_id
        FROM {table}
        WHERE {symbol_col} IN ({ph})
        GROUP BY {symbol_col}
    ) m ON m.sym = t.{symbol_col} AND m.max_id = t.{id_col}
    """
    rows = _fetchall(con, q, tuple(symbols))
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        s = str(r.get("symbol") or "").strip().upper()
        if not s:
            continue
        out[s] = {k: v for k, v in r.items() if k != "symbol"}
    return out


def fetch_last_intents_by_symbol(con: sqlite3.Connection, symbols: list[str]) -> dict[str, dict[str, Any]]:
    if not symbols:
        return {}
    ph = _placeholders(len(symbols))
    q = f"""
    SELECT i.symbol AS symbol,
           i.intent_id, i.created_ts_ms, i.action, i.side, i.status,
           i.confidence, i.reason, i.dedupe_key, i.client_order_id, i.exchange_order_id
    FROM oms_intents i
    JOIN (
        SELECT symbol AS sym, MAX(created_ts_ms) AS max_ts
        FROM oms_intents
        WHERE symbol IN ({ph})
        GROUP BY symbol
    ) m ON m.sym = i.symbol AND m.max_ts = i.created_ts_ms
    """
    rows = _fetchall(con, q, tuple(symbols))
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        s = str(r.get("symbol") or "").strip().upper()
        if not s:
            continue
        out[s] = {k: v for k, v in r.items() if k != "symbol"}
    return out


@dataclass
class MidPoint:
    px: float
    ts_ms: int


class MidsFeed:
    def __init__(self, *, hist_window_s: int = 3600, hist_sample_ms: int = 1000):
        self._lock = threading.RLock()
        self._cv = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        self._tracked: set[str] = {"BTC"}
        self._mids: dict[str, MidPoint] = {}
        self._updated_ts_ms: int | None = None
        self._seq: int = 0
        self._sidecar_seq: int | None = None

        self._hist_sample_ms = int(hist_sample_ms)
        self._hist_window_s = int(hist_window_s)
        self._hist: dict[str, deque[tuple[int, float]]] = {}
        self._last_hist_ts: dict[str, int] = {}

        # Legacy poll cadence is used only when connected to an older sidecar that
        # does not support blocking wait_mids RPC.
        self._poll_ms = max(100, _env_int("AIQ_MONITOR_MIDS_POLL_MS", int(self._hist_sample_ms)))
        self._wait_timeout_s = max(1.0, _env_float("AIQ_MONITOR_MIDS_WAIT_TIMEOUT_S", 25.0))
        self._max_age_s_ok = max(0.0, _env_float("AIQ_MONITOR_MIDS_MAX_AGE_S", 60.0))

        self._ws_ok: bool = False
        self._ws_last_err: str | None = None

        self._sidecar = None
        try:
            from exchange.sidecar import SidecarWSClient  # type: ignore

            self._sidecar = SidecarWSClient()
        except Exception as e:
            self._sidecar = None
            self._ws_ok = False
            self._ws_last_err = f"sidecar_client_init_failed: {e}"

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        t = threading.Thread(target=self._run, name="aiq-monitor-mids-sidecar", daemon=True)
        self._thread = t
        t.start()

    def stop(self) -> None:
        self._stop.set()
        with self._cv:
            self._cv.notify_all()

    def set_tracked_symbols(self, symbols: list[str]) -> None:
        with self._lock:
            self._tracked = {str(s).strip().upper() for s in symbols if str(s).strip()}
            if "BTC" not in self._tracked:
                self._tracked.add("BTC")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            mids = {s: v.px for s, v in self._mids.items()}
            updated_ts_ms = self._updated_ts_ms
            return {
                "ok": self._ws_ok,
                "last_error": self._ws_last_err,
                "updated_ts_ms": updated_ts_ms,
                "seq": int(self._seq),
                "mids": mids,
            }

    def wait_snapshot_since(self, *, after_seq: int, timeout_s: float = 15.0) -> dict[str, Any]:
        after = int(max(0, int(after_seq)))
        timeout = max(0.0, float(timeout_s))
        deadline = time.monotonic() + timeout
        with self._cv:
            while self._seq <= after and not self._stop.is_set():
                remain = deadline - time.monotonic()
                if remain <= 0:
                    break
                self._cv.wait(timeout=remain)
            mids = {s: v.px for s, v in self._mids.items()}
            updated_ts_ms = self._updated_ts_ms
            return {
                "ok": self._ws_ok,
                "last_error": self._ws_last_err,
                "updated_ts_ms": updated_ts_ms,
                "seq": int(self._seq),
                "mids": mids,
            }

    def get_mid(self, symbol: str) -> MidPoint | None:
        s = str(symbol or "").strip().upper()
        if not s:
            return None
        with self._lock:
            return self._mids.get(s)

    def history(self, symbol: str, *, window_s: int = 600) -> list[dict[str, Any]]:
        s = str(symbol or "").strip().upper()
        if not s:
            return []
        now_ms = _utc_now_ms()
        cutoff = now_ms - int(window_s * 1000)
        with self._lock:
            dq = self._hist.get(s)
            if not dq:
                return []
            return [{"ts_ms": ts, "mid": px} for (ts, px) in list(dq) if ts >= cutoff]

    def mid_near_ts(self, symbol: str, ts_ms: int, *, max_diff_ms: int = 600_000) -> float | None:
        """Return the mid nearest to the given timestamp from the in-memory history."""
        s = str(symbol or "").strip().upper()
        if not s:
            return None
        try:
            tgt = int(ts_ms)
        except Exception:
            return None
        if tgt <= 0:
            return None
        try:
            md = int(max_diff_ms)
        except Exception:
            md = 600_000
        md = max(0, md)

        with self._lock:
            dq = self._hist.get(s)
            if not dq:
                return None
            items = list(dq)
        if not items:
            return None

        ts_list = [t for (t, _px) in items]
        i = bisect_left(ts_list, tgt)
        best: tuple[int, float] | None = None
        best_diff = 10**18
        for j in (i - 1, i):
            if j < 0 or j >= len(items):
                continue
            t, px = items[j]
            diff = abs(int(t) - tgt)
            if diff < best_diff:
                best_diff = diff
                best = (int(t), float(px))
        if best is None or best_diff > md:
            return None
        return float(best[1])

    def _run(self) -> None:
        backoff_s = 1.0
        while not self._stop.is_set():
            try:
                sidecar = self._sidecar
                if sidecar is None:
                    raise RuntimeError("sidecar_unavailable")

                with self._lock:
                    tracked = set(self._tracked)
                    after_seq = self._sidecar_seq

                # Blocking wait on sidecar updates (falls back to legacy polling on older sidecars).
                mids, mids_age_s, sidecar_seq, changed, timed_out = sidecar.wait_mids(
                    symbols=sorted(tracked),
                    after_seq=after_seq,
                    max_age_s=None,
                    timeout_s=self._wait_timeout_s,
                )

                now_ms = _utc_now_ms()
                ts_ms = now_ms
                try:
                    if mids_age_s is not None:
                        ts_ms = now_ms - int(float(mids_age_s) * 1000.0)
                except Exception:
                    ts_ms = now_ms

                ok = mids_age_s is not None and float(mids_age_s) <= float(self._max_age_s_ok)
                last_err = None if ok else (f"mids_stale age_s={mids_age_s}" if mids_age_s is not None else "mids_age_s=None")

                with self._cv:
                    prev_ok = self._ws_ok
                    prev_err = self._ws_last_err
                    prev_updated_ts_ms = self._updated_ts_ms
                    self._ws_ok = bool(ok)
                    self._ws_last_err = last_err
                    self._updated_ts_ms = ts_ms
                    if sidecar_seq is not None:
                        self._sidecar_seq = int(sidecar_seq)

                    # Update tracked symbols only.
                    tracked_now = set(self._tracked)
                    px_changed = False
                    for sym in tracked_now:
                        if sym not in mids:
                            continue
                        try:
                            px = float(mids[sym])
                        except Exception:
                            continue
                        prev = self._mids.get(sym)
                        if prev is None or float(prev.px) != px:
                            px_changed = True
                        self._mids[sym] = MidPoint(px=px, ts_ms=ts_ms)

                        last_ts = self._last_hist_ts.get(sym) or 0
                        if (ts_ms - last_ts) >= self._hist_sample_ms:
                            dq = self._hist.get(sym)
                            if dq is None:
                                dq = deque(maxlen=max(30, int(self._hist_window_s * 1000 / self._hist_sample_ms)))
                                self._hist[sym] = dq
                            dq.append((ts_ms, px))
                            self._last_hist_ts[sym] = ts_ms

                    health_changed = (
                        prev_ok != self._ws_ok
                        or prev_err != self._ws_last_err
                        or prev_updated_ts_ms != self._updated_ts_ms
                    )
                    notify = bool(px_changed or health_changed or (changed and not timed_out))
                    if notify:
                        self._seq += 1
                        self._cv.notify_all()
            except Exception as e:
                with self._cv:
                    prev_ok = self._ws_ok
                    prev_err = self._ws_last_err
                    self._ws_ok = False
                    self._ws_last_err = f"sidecar_poll_error: {e}"
                    if prev_ok != self._ws_ok or prev_err != self._ws_last_err:
                        self._seq += 1
                        self._cv.notify_all()
                if self._stop.wait(backoff_s):
                    break
                backoff_s = min(60.0, backoff_s * 1.6)
                continue

            backoff_s = 1.0
            # Older sidecar without wait_mids support: throttle fallback polling.
            if sidecar_seq is None and self._stop.wait(float(self._poll_ms) / 1000.0):
                break


class DashboardState:
    def __init__(self):
        self.mids = MidsFeed(hist_window_s=_env_int("AIQ_MONITOR_HIST_WINDOW_S", 3600))
        self.mids.start()
        self._snapshot_lock = threading.RLock()
        self._snapshots: dict[str, tuple[int, dict[str, Any]]] = {}

    def get_snapshot_cached(self, mode: str, build_fn) -> dict[str, Any]:
        mode2 = (mode or "").strip().lower()
        now_ms = _utc_now_ms()
        with self._snapshot_lock:
            cached = self._snapshots.get(mode2)
            if cached and (now_ms - cached[0]) < 900:
                return cached[1]
        snap = build_fn()
        with self._snapshot_lock:
            self._snapshots[mode2] = (now_ms, snap)
        return snap


STATE = DashboardState()


def mode_paths(mode: str) -> tuple[Path, Path]:
    mode2 = (mode or "").strip().lower()
    if mode2 == "live":
        db = Path(os.getenv("AIQ_MONITOR_LIVE_DB", str(AIQ_ROOT / "trading_engine_live.db")))
        log = Path(os.getenv("AIQ_MONITOR_LIVE_LOG", str(AIQ_ROOT / "live_daemon_log.txt")))
        return db, log
    # paper1/2/3 support: "paper" is alias for "paper1"
    if mode2 in ("paper", "paper1"):
        db = Path(os.getenv("AIQ_MONITOR_PAPER1_DB", os.getenv("AIQ_MONITOR_PAPER_DB", str(AIQ_ROOT / "trading_engine.db"))))
        log = Path(os.getenv("AIQ_MONITOR_PAPER1_LOG", os.getenv("AIQ_MONITOR_PAPER_LOG", str(AIQ_ROOT / "daemon_log.txt"))))
        return db, log
    if mode2 == "paper2":
        db = Path(os.getenv("AIQ_MONITOR_PAPER2_DB", str(AIQ_ROOT / "trading_engine_paper2.db")))
        log = Path(os.getenv("AIQ_MONITOR_PAPER2_LOG", str(AIQ_ROOT / "paper2_daemon_log.txt")))
        return db, log
    if mode2 == "paper3":
        db = Path(os.getenv("AIQ_MONITOR_PAPER3_DB", str(AIQ_ROOT / "trading_engine_paper3.db")))
        log = Path(os.getenv("AIQ_MONITOR_PAPER3_LOG", str(AIQ_ROOT / "paper3_daemon_log.txt")))
        return db, log
    # fallback: treat unknown as paper1
    db = Path(os.getenv("AIQ_MONITOR_PAPER1_DB", os.getenv("AIQ_MONITOR_PAPER_DB", str(AIQ_ROOT / "trading_engine.db"))))
    log = Path(os.getenv("AIQ_MONITOR_PAPER1_LOG", os.getenv("AIQ_MONITOR_PAPER_LOG", str(AIQ_ROOT / "daemon_log.txt"))))
    return db, log


def build_marks(mode: str, symbol: str) -> dict[str, Any]:
    mode2 = (mode or "paper").strip().lower()
    sym = (symbol or "").strip().upper()
    now_ms = _utc_now_ms()
    db_path, _log_path = mode_paths(mode2)

    out: dict[str, Any] = {
        "ok": True,
        "now_ts_ms": now_ms,
        "mode": mode2,
        "db_path": str(db_path),
        "symbol": sym,
        "position": None,
        "entries": [],
        "warnings": [],
    }

    if not sym:
        out["ok"] = False
        out["error"] = "missing_symbol"
        return out

    if not db_path.exists():
        out["ok"] = False
        out["error"] = "db_missing"
        return out

    try:
        con = connect_db_ro(db_path)
    except Exception as e:
        out["ok"] = False
        out["error"] = f"db_open_failed:{e}"
        return out

    try:
        pos = compute_open_position_for_symbol(con, sym)
        if not pos:
            return out
        out["position"] = pos

        try:
            open_id = int(pos.get("open_trade_id") or 0)
        except Exception:
            open_id = 0

        if open_id > 0:
            out["entries"] = _fetchall(
                con,
                """
                SELECT id, timestamp, action, type, price, size, confidence
                FROM trades
                WHERE symbol = ?
                  AND id >= ?
                  AND action IN ('OPEN', 'ADD')
                ORDER BY id ASC
                """,
                (sym, open_id),
            )
        return out
    finally:
        try:
            con.close()
        except Exception:
            pass


def build_candles(mode: str, symbol: str, interval: str, limit: int) -> dict[str, Any]:
    mode2 = (mode or "paper").strip().lower()
    sym = (symbol or "").strip().upper()
    interval2 = (interval or effective_trader_interval_for_mode(mode2)).strip().lower()
    now_ms = _utc_now_ms()
    db_path, _log_path = mode_paths(mode2)

    lim = int(limit or 200)
    lim = max(2, min(2000, lim))

    out: dict[str, Any] = {
        "ok": True,
        "now_ts_ms": now_ms,
        "mode": mode2,
        "db_path": str(db_path),
        "symbol": sym,
        "interval": interval2,
        "limit": lim,
        "candles": [],
        "warnings": [],
    }

    if not sym:
        out["ok"] = False
        out["error"] = "missing_symbol"
        return out
    if not db_path.exists():
        out["ok"] = False
        out["error"] = "db_missing"
        return out

    # Prefer per-interval candle DB written by the Rust sidecar.
    candle_db_paths: list[Path] = []
    try:
        raw_dir = str(os.getenv("AI_QUANT_CANDLES_DB_DIR", "") or "").strip()
        candles_dir = Path(raw_dir) if raw_dir else (AIQ_ROOT / "candles_dbs")
        safe_interval = "".join([(ch.lower() if ch.isalnum() else "_") for ch in interval2]) or "unknown"
        p = candles_dir / f"candles_{safe_interval}.db"
        if p.exists():
            candle_db_paths.append(p)
    except Exception:
        pass
    candle_db_paths.append(db_path)

    try:
        rows: list[dict[str, Any]] = []
        for p in candle_db_paths:
            con = None
            try:
                con = connect_db_ro(p)
                rows = _fetchall(
                    con,
                    """
                    SELECT t, t_close, o, h, l, c, v, n, updated_at
                    FROM candles
                    WHERE symbol = ?
                      AND interval = ?
                    ORDER BY COALESCE(t_close, t) DESC
                    LIMIT ?
                    """,
                    (sym, interval2, lim),
                )
                if rows:
                    break
            except Exception:
                rows = []
            finally:
                try:
                    if con is not None:
                        con.close()
                except Exception:
                    pass

        candles: list[dict[str, Any]] = []
        for r in reversed(rows):
            try:
                candles.append(
                    {
                        "t": int(r.get("t") or 0),
                        "t_close": int(r.get("t_close") or 0),
                        "o": float(r.get("o") or 0.0),
                        "h": float(r.get("h") or 0.0),
                        "l": float(r.get("l") or 0.0),
                        "c": float(r.get("c") or 0.0),
                        "v": float(r.get("v") or 0.0),
                        "n": int(r.get("n") or 0),
                        "updated_at": r.get("updated_at"),
                    }
                )
            except Exception:
                continue
        out["candles"] = candles
        out["count"] = len(candles)
        if candles:
            out["first_t"] = candles[0].get("t")
            out["last_t_close"] = candles[-1].get("t_close") or candles[-1].get("t")
        return out
    finally:
        pass


def build_snapshot(mode: str) -> dict[str, Any]:
    mode2 = (mode or "paper").strip().lower()
    now_ms = _utc_now_ms()
    db_path, log_path = mode_paths(mode2)

    health = parse_last_heartbeat(db_path, log_path)

    snapshot: dict[str, Any] = {
        "now_ts_ms": now_ms,
        "mode": mode2,
        "health": health,
        "db_path": str(db_path),
        "symbols": [],
        "open_positions": [],
        "recent": {},
        "warnings": [],
    }

    trader_interval = effective_trader_interval()
    snapshot["config"] = {
        "trader_interval": trader_interval,
        "candle_interval_default": trader_interval,
        "candle_intervals": list_available_candle_intervals(default=trader_interval),
    }

    if not db_path.exists():
        snapshot["warnings"].append("db_missing")
        return snapshot

    # Detect OMS presence (live DB has it; paper may not).
    has_oms = False
    try:
        con0 = connect_db_ro(db_path)
        try:
            row = _fetchone(con0, "SELECT name FROM sqlite_master WHERE type='table' AND name='oms_intents'")
            has_oms = bool(row)
        finally:
            con0.close()
    except Exception:
        has_oms = False

    try:
        con = connect_db_ro(db_path)
    except Exception as e:
        snapshot["warnings"].append(f"db_open_failed:{e}")
        return snapshot

    try:
        interval = effective_monitor_interval()

        # If the monitor isn't explicitly configured, try to infer the trader interval
        # from the DB (useful when live/paper services run with their own env files).
        if not str(os.getenv("AI_QUANT_INTERVAL") or "").strip():
            inferred = infer_interval_from_db(con)
            if inferred:
                snapshot["config"]["trader_interval"] = inferred
                snapshot["config"]["candle_interval_default"] = inferred
                snapshot["config"]["candle_intervals"] = list_available_candle_intervals(default=inferred)

        candles_con = None
        try:
            # Candles are now written by the Rust sidecar into per-interval DB files.
            # Fall back to reading candles from the trading DB if the per-interval DB is missing.
            raw_dir = str(os.getenv("AI_QUANT_CANDLES_DB_DIR", "") or "").strip()
            candles_dir = Path(raw_dir) if raw_dir else (AIQ_ROOT / "candles_dbs")
            safe_interval = "".join([(ch.lower() if ch.isalnum() else "_") for ch in interval]) or "unknown"
            candles_db_path = candles_dir / f"candles_{safe_interval}.db"
            if candles_db_path.exists():
                candles_con = connect_db_ro(candles_db_path)
        except Exception:
            candles_con = None

        # Balance snapshots:
        # - Paper: trades.balance is simulated realised cash.
        # - Live: trades.balance is exchange accountValue (equity) captured at ingest time.
        # Pick the latest value by id, and choose an "as of" timestamp from the batch
        # (multiple rows can share the same balance because we snapshot once per ingest batch).
        bal_rows = _fetchall(
            con,
            """
            SELECT timestamp, balance
            FROM trades
            WHERE balance IS NOT NULL
            ORDER BY id DESC
            LIMIT 60
            """,
        )
        balance_asof_usd: float | None = None
        balance_asof_ts: str | None = None
        if bal_rows:
            try:
                if bal_rows[0].get("balance") is not None:
                    balance_asof_usd = float(bal_rows[0]["balance"])
            except Exception:
                balance_asof_usd = None

            # Best-effort: "as of" is the latest timestamp among rows sharing the same balance.
            if balance_asof_usd is not None:
                best_ms = -1
                best_ts = None
                for r in bal_rows:
                    try:
                        b = float(r.get("balance")) if r.get("balance") is not None else None
                    except Exception:
                        b = None
                    if b is None or abs(float(b) - float(balance_asof_usd)) > 1e-9:
                        continue
                    ms = _parse_iso_ts_ms(r.get("timestamp"))
                    if ms is not None and ms > best_ms:
                        best_ms = int(ms)
                        best_ts = str(r.get("timestamp") or "").strip() or None
                balance_asof_ts = best_ts or (str(bal_rows[0].get("timestamp") or "").strip() or None)
            else:
                balance_asof_ts = str(bal_rows[0].get("timestamp") or "").strip() or None

        # UI fields:
        # - Paper: realised_usd is realised cash.
        # - Live fallback: realised_usd will be set to a withdrawable estimate later; the DB snapshot stores accountValue.
        realised_usd: float | None = balance_asof_usd
        realised_asof: str | None = balance_asof_ts
        account_value_asof_usd: float | None = balance_asof_usd if mode2 == "live" else None

        if realised_usd is None and mode2 != "live":
            # Paper default if no trades yet.
            realised_usd = _env_float("AI_QUANT_PAPER_BALANCE", 10000.0)

        open_positions = compute_open_positions(con)
        open_syms = list(open_positions.keys())

        symbols = list_recent_symbols(con, candles_con=candles_con, interval=interval, now_ms=now_ms, has_oms=has_oms)
        # Always include open positions first.
        merged: list[str] = []
        seen: set[str] = set()
        for s in open_syms + symbols:
            s2 = (s or "").strip().upper()
            if not s2 or s2 in seen:
                continue
            seen.add(s2)
            merged.append(s2)
        merged = merged[:200]

        # Ensure WS feed tracks the universe we want to display.
        STATE.mids.set_tracked_symbols(merged[:120])

        last_signal = fetch_last_rows_by_symbol(
            con,
            "signals",
            "symbol",
            "id",
            merged,
            ["t.timestamp AS timestamp", "t.signal AS signal", "t.confidence AS confidence", "t.price AS price", "t.meta_json AS meta_json"],
        )
        last_trade = fetch_last_rows_by_symbol(
            con,
            "trades",
            "symbol",
            "id",
            merged,
            [
                "t.timestamp AS timestamp",
                "t.type AS type",
                "t.action AS action",
                "t.price AS price",
                "t.size AS size",
                "t.notional AS notional",
                "t.pnl AS pnl",
                "t.reason AS reason",
                "t.confidence AS confidence",
                "t.meta_json AS meta_json",
            ],
        )
        last_intent = fetch_last_intents_by_symbol(con, merged) if has_oms else {}

        hl_bal = fetch_hl_balance() if mode2 == "live" else None
        hl_bal_public: dict[str, Any] | None = None
        if isinstance(hl_bal, dict):
            # Avoid returning wallet addresses in the HTTP API response.
            hl_bal_public = {k: v for (k, v) in hl_bal.items() if k != "main_address"}
        use_hl_bal = bool(isinstance(hl_bal, dict) and bool(hl_bal.get("ok")))
        if mode2 == "live" and isinstance(hl_bal, dict) and not use_hl_bal:
            err = str(hl_bal.get("error") or "").strip()
            if err:
                snapshot["warnings"].append(f"hl_balance_error:{err}")

        symbols_out: list[dict[str, Any]] = []
        # Balances:
        # - Paper: equity estimate = realised + uPnL - estimated close fees.
        # - Live: prefer Hyperliquid REST user_state (accountValue + withdrawable). Fall back to DB snapshots.
        fee_rate = effective_fee_rate()
        unreal_total = 0.0
        margin_used_total = 0.0
        close_fee_total = 0.0
        for sym in merged:
            mp = STATE.mids.get_mid(sym)
            mid = mp.px if mp else None
            mid_age_s = (now_ms - mp.ts_ms) / 1000.0 if mp else None

            pos = open_positions.get(sym)
            pos_out = None
            if pos:
                unreal_pnl = None
                if mid and pos.get("entry_price") and pos.get("size"):
                    try:
                        entry = float(pos["entry_price"])
                        size = float(pos["size"])
                        if pos.get("type") == "LONG":
                            unreal_pnl = (mid - entry) * size
                        else:
                            unreal_pnl = (entry - mid) * size
                    except Exception:
                        unreal_pnl = None
                # Equity totals (best effort even if mid missing)
                try:
                    entry = float(pos.get("entry_price") or 0.0)
                    size = float(pos.get("size") or 0.0)
                    lev = float(pos.get("leverage") or 1.0)
                    if lev <= 0:
                        lev = 1.0
                    mark = float(mid) if mid is not None else entry
                    if entry > 0 and size > 0 and mark > 0:
                        if str(pos.get("type") or "").upper() == "LONG":
                            unreal_total += (mark - entry) * size
                        else:
                            unreal_total += (entry - mark) * size
                        close_fee_total += abs(size) * mark * float(fee_rate or 0.0)
                        margin_used_total += abs(size) * mark / float(lev or 1.0)
                except Exception:
                    pass
                pos_out = {**pos, "unreal_pnl_est": unreal_pnl}

            symbols_out.append(
                {
                    "symbol": sym,
                    "mid": mid,
                    "mid_age_s": mid_age_s,
                    "last_signal": last_signal.get(sym),
                    "last_trade": last_trade.get(sym),
                    "last_intent": last_intent.get(sym) if has_oms else None,
                    "position": pos_out,
                }
            )

        equity_est_usd: float | None = None
        balance_source = "db"
        account_value_usd: float | None = None
        withdrawable_usd: float | None = None
        total_margin_used_usd: float | None = None

        if mode2 == "live":
            if use_hl_bal and isinstance(hl_bal, dict):
                balance_source = "hyperliquid"
                try:
                    account_value_usd = float(hl_bal.get("account_value_usd") or 0.0)
                except Exception:
                    account_value_usd = None
                try:
                    withdrawable_usd = float(hl_bal.get("withdrawable_usd") or 0.0)
                except Exception:
                    withdrawable_usd = None
                try:
                    total_margin_used_usd = float(hl_bal.get("total_margin_used_usd") or 0.0)
                except Exception:
                    total_margin_used_usd = None

                equity_est_usd = account_value_usd
                realised_usd = withdrawable_usd
                realised_asof = _iso_utc(datetime.now(timezone.utc))
            else:
                # Fallback: DB snapshot stores exchange accountValue (equity) captured at ingest time.
                balance_source = "db_snapshot"
                account_value_usd = account_value_asof_usd
                equity_est_usd = account_value_usd
                # Best-effort withdrawable estimate if only accountValue is available.
                if account_value_usd is not None:
                    try:
                        withdrawable_usd = float(account_value_usd) - float(margin_used_total)
                        if withdrawable_usd < 0:
                            withdrawable_usd = 0.0
                    except Exception:
                        withdrawable_usd = None
                realised_usd = withdrawable_usd
        else:
            # Paper: realised cash + mark-to-market uPnL (minus estimated close fees).
            balance_source = "paper_estimate"
            if realised_usd is not None:
                equity_est_usd = float(realised_usd) + float(unreal_total) - float(close_fee_total)

        # --- Kernel equity (AQC-745) ---
        kernel_equity_result: dict[str, Any] | None = None
        if _BT_RUNTIME_OK:
            mid_snap = STATE.mids.snapshot()
            kernel_mids = mid_snap.get("mids") or {}
            kernel_equity_result = get_kernel_equity(db_path, kernel_mids)

            # Log discrepancy between kernel and monitor equity estimates.
            if (
                kernel_equity_result.get("ok")
                and equity_est_usd is not None
                and kernel_equity_result.get("equity_usd") is not None
            ):
                diff = abs(float(kernel_equity_result["equity_usd"]) - float(equity_est_usd))
                if diff > 0.01:
                    snapshot["warnings"].append(
                        f"kernel_equity_drift:{diff:.2f} "
                        f"(kernel={kernel_equity_result['equity_usd']:.2f} "
                        f"monitor={equity_est_usd:.2f})"
                    )

        snapshot["balances"] = {
            "balance_source": balance_source,
            "realised_usd": realised_usd,
            "realised_asof": realised_asof,
            "equity_est_usd": equity_est_usd,
            "account_value_usd": account_value_usd if mode2 == "live" else None,
            "withdrawable_usd": withdrawable_usd if mode2 == "live" else None,
            "total_margin_used_usd": total_margin_used_usd if mode2 == "live" else None,
            "unreal_pnl_est_usd": unreal_total,
            "est_close_fees_usd": close_fee_total,
            "margin_used_est_usd": margin_used_total if mode2 == "live" else None,
            "fee_rate": fee_rate,
            "account_value_asof_usd": account_value_asof_usd,
            "hl_balance": hl_bal_public if mode2 == "live" else None,
            "kernel_equity": kernel_equity_result,
        }

        # Daily metrics (UTC day) for the dashboard summary.
        day = _utc_day(now_ms)
        daily: dict[str, Any] = {
            "utc_day": day,
            "trades": 0,
            "start_balance": None,
            "end_balance": None,
            "pnl_usd": 0.0,
            "fees_usd": 0.0,
            "net_pnl_usd": 0.0,
            "peak_realised_balance": None,
            "drawdown_pct": 0.0,
        }
        if day:
            like = f"{day}%"
            row0 = _fetchone(
                con,
                "SELECT balance FROM trades WHERE timestamp LIKE ? AND balance IS NOT NULL ORDER BY id ASC LIMIT 1",
                (like,),
            )
            row1 = _fetchone(
                con,
                "SELECT balance FROM trades WHERE timestamp LIKE ? AND balance IS NOT NULL ORDER BY id DESC LIMIT 1",
                (like,),
            )
            row_peak = _fetchone(
                con,
                "SELECT MAX(balance) AS peak FROM trades WHERE timestamp LIKE ? AND balance IS NOT NULL",
                (like,),
            )
            row_cnt = _fetchone(con, "SELECT COUNT(*) AS n FROM trades WHERE timestamp LIKE ?", (like,))
            row_fees = _fetchone(
                con,
                "SELECT SUM(COALESCE(fee_usd, 0)) AS fees FROM trades WHERE timestamp LIKE ?",
                (like,),
            )

            start_bal = float(row0["balance"]) if row0 and row0.get("balance") is not None else None
            end_bal = float(row1["balance"]) if row1 and row1.get("balance") is not None else None
            peak_bal = float(row_peak["peak"]) if row_peak and row_peak.get("peak") is not None else None
            try:
                daily["trades"] = int(row_cnt["n"]) if row_cnt and row_cnt.get("n") is not None else 0
            except Exception:
                daily["trades"] = 0
            try:
                daily["fees_usd"] = float(row_fees["fees"]) if row_fees and row_fees.get("fees") is not None else 0.0
            except Exception:
                daily["fees_usd"] = 0.0

            daily["start_balance"] = start_bal
            daily["end_balance"] = end_bal
            daily["peak_realised_balance"] = peak_bal

            pnl = 0.0
            if start_bal is not None and end_bal is not None:
                pnl = float(end_bal) - float(start_bal)
            daily["pnl_usd"] = float(pnl)
            daily["net_pnl_usd"] = float(pnl) - float(daily.get("fees_usd") or 0.0)

            # Drawdown: compare current equity estimate to the daily peak realised balance.
            peak = float(peak_bal) if peak_bal is not None and peak_bal > 0 else None
            cur = float(equity_est_usd) if equity_est_usd is not None else (float(realised_usd) if realised_usd is not None else None)
            if peak is not None and cur is not None and peak > 0:
                dd = max(0.0, (peak - cur) / peak) * 100.0
                daily["drawdown_pct"] = float(dd)

        snapshot["daily"] = daily

        recent: dict[str, Any] = {}
        recent["trades"] = _fetchall(
            con,
            """
            SELECT timestamp, symbol, type, action, price, size, notional, pnl, fee_usd, reason, confidence
            FROM trades
            ORDER BY id DESC
            LIMIT 60
            """,
        )
        recent["signals"] = _fetchall(
            con,
            """
            SELECT timestamp, symbol, signal, confidence, price, rsi, ema_fast, ema_slow
            FROM signals
            ORDER BY id DESC
            LIMIT 60
            """,
        )
        recent["audit_events"] = _fetchall(
            con,
            """
            SELECT timestamp, symbol, event, level, data_json
            FROM audit_events
            ORDER BY id DESC
            LIMIT 60
            """,
        )
        if has_oms:
            recent["oms_intents"] = _fetchall(
                con,
                """
                SELECT created_ts_ms, symbol, action, side, status, confidence, reason, dedupe_key, client_order_id, exchange_order_id, last_error
                FROM oms_intents
                ORDER BY created_ts_ms DESC
                LIMIT 80
                """,
            )
            recent["oms_fills"] = _fetchall(
                con,
                """
                SELECT ts_ms, symbol, intent_id, action, side, price, size, notional, fee_usd, pnl_usd, matched_via
                FROM oms_fills
                ORDER BY ts_ms DESC
                LIMIT 80
                """,
            )
            recent["oms_open_orders"] = _fetchall(
                con,
                """
                SELECT last_seen_ts_ms, symbol, side, price, remaining_size, reduce_only, client_order_id, exchange_order_id, intent_id
                FROM oms_open_orders
                ORDER BY last_seen_ts_ms DESC
                LIMIT 80
                """,
            )
            recent["oms_reconcile_events"] = _fetchall(
                con,
                """
                SELECT ts_ms, kind, symbol, result
                FROM oms_reconcile_events
                ORDER BY ts_ms DESC
                LIMIT 80
                """,
            )

        snapshot["symbols"] = symbols_out
        snapshot["open_positions"] = list(open_positions.values())
        snapshot["recent"] = recent
        snapshot["ws"] = STATE.mids.snapshot()
        return snapshot
    finally:
        try:
            con.close()
        except Exception:
            pass
        try:
            if candles_con is not None:
                candles_con.close()
        except Exception:
            pass


def _prom_escape(v: str) -> str:
    return str(v).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _prom_labels(labels: dict[str, Any] | None) -> str:
    if not labels:
        return ""
    parts: list[str] = []
    for k, v in labels.items():
        key = str(k or "").strip()
        if not key:
            continue
        parts.append(f'{key}="{_prom_escape(str(v))}"')
    return "{" + ",".join(parts) + "}" if parts else ""


def _prom_line(name: str, value: float | int, labels: dict[str, Any] | None = None) -> str:
    return f"{name}{_prom_labels(labels)} {value}\n"


def build_metrics(mode: str) -> dict[str, Any]:
    mode2 = (mode or "paper").strip().lower()
    now_ms = _utc_now_ms()
    db_path, log_path = mode_paths(mode2)

    health = parse_last_heartbeat(db_path, log_path)
    out: dict[str, Any] = {
        "ok": True,
        "now_ts_ms": now_ms,
        "mode": mode2,
        "db_path": str(db_path),
        "health": health,
        "gauges": {},
        "counters": {},
    }

    gauges: dict[str, Any] = {}
    counters: dict[str, Any] = {}

    # Heartbeat-derived gauges.
    gauges["engine_up"] = 1 if bool(health.get("ok")) else 0
    if isinstance(health.get("ts_ms"), int) and int(health.get("ts_ms") or 0) > 0:
        gauges["heartbeat_age_s"] = max(0.0, (float(now_ms) - float(health["ts_ms"])) / 1000.0)
    if "open_pos" in health:
        gauges["open_pos"] = int(health.get("open_pos") or 0)
    if "ws_connected" in health:
        gauges["ws_connected"] = 1 if bool(health.get("ws_connected")) else 0

    kill_mode = str(health.get("kill_mode") or "off").strip().lower()
    gauges["kill_mode"] = 2 if kill_mode == "halt_all" else (1 if kill_mode == "close_only" else 0)

    # Slippage guard gauges (from heartbeat).
    if "slip_enabled" in health:
        gauges["slip_enabled"] = 1 if bool(health.get("slip_enabled")) else 0
    if "slip_n" in health:
        gauges["slip_n"] = int(health.get("slip_n") or 0)
    if "slip_win" in health:
        gauges["slip_win"] = int(health.get("slip_win") or 0)
    if "slip_thr_bps" in health:
        gauges["slip_thr_bps"] = float(health.get("slip_thr_bps") or 0.0)
    if "slip_last_bps" in health:
        gauges["slip_last_bps"] = float(health.get("slip_last_bps") or 0.0)
    if "slip_median_bps" in health:
        gauges["slip_median_bps"] = float(health.get("slip_median_bps") or 0.0)

    if not db_path.exists():
        out["ok"] = False
        out["error"] = "db_missing"
        out["gauges"] = gauges
        out["counters"] = counters
        return out

    try:
        con = connect_db_ro(db_path)
    except Exception as e:
        out["ok"] = False
        out["error"] = f"db_open_failed:{e}"
        out["gauges"] = gauges
        out["counters"] = counters
        return out

    try:
        row = _fetchone(con, "SELECT name FROM sqlite_master WHERE type='table' AND name='oms_intents'")
        has_oms = bool(row)

        # Orders + fills.
        if has_oms:
            row = _fetchone(con, "SELECT COUNT(*) AS n FROM oms_intents")
            counters["orders_total"] = int(row.get("n") or 0) if row else 0
            counters["orders_by_action"] = {str(r["action"]): int(r["n"]) for r in _fetchall(con, "SELECT action, COUNT(*) AS n FROM oms_intents GROUP BY action") if r.get("action")}

            row = _fetchone(con, "SELECT COUNT(*) AS n FROM oms_fills")
            counters["fills_total"] = int(row.get("n") or 0) if row else 0
            counters["fills_by_action"] = {str(r["action"]): int(r["n"]) for r in _fetchall(con, "SELECT action, COUNT(*) AS n FROM oms_fills GROUP BY action") if r.get("action")}
        else:
            row = _fetchone(con, "SELECT COUNT(*) AS n FROM trades")
            counters["orders_total"] = int(row.get("n") or 0) if row else 0
            counters["fills_total"] = int(row.get("n") or 0) if row else 0

        # Daily PnL + drawdown gauges.
        day = _utc_day(now_ms)
        if day:
            like = f"{day}%"
            row0 = _fetchone(
                con,
                "SELECT balance FROM trades WHERE timestamp LIKE ? AND balance IS NOT NULL ORDER BY id ASC LIMIT 1",
                (like,),
            )
            row1 = _fetchone(
                con,
                "SELECT balance FROM trades WHERE timestamp LIKE ? AND balance IS NOT NULL ORDER BY id DESC LIMIT 1",
                (like,),
            )
            row_peak = _fetchone(
                con,
                "SELECT MAX(balance) AS peak FROM trades WHERE timestamp LIKE ? AND balance IS NOT NULL",
                (like,),
            )
            row_fees = _fetchone(
                con,
                "SELECT SUM(COALESCE(fee_usd, 0)) AS fees FROM trades WHERE timestamp LIKE ?",
                (like,),
            )

            start_bal = float(row0["balance"]) if row0 and row0.get("balance") is not None else None
            end_bal = float(row1["balance"]) if row1 and row1.get("balance") is not None else None
            peak_bal = float(row_peak["peak"]) if row_peak and row_peak.get("peak") is not None else None
            fees_usd = float(row_fees["fees"]) if row_fees and row_fees.get("fees") is not None else 0.0

            pnl = float(end_bal - start_bal) if start_bal is not None and end_bal is not None else 0.0
            gauges["pnl_today_usd"] = float(pnl)
            gauges["fees_today_usd"] = float(fees_usd)
            gauges["net_pnl_today_usd"] = float(pnl) - float(fees_usd)

            if peak_bal is not None and end_bal is not None and peak_bal > 0:
                dd = max(0.0, (float(peak_bal) - float(end_bal)) / float(peak_bal)) * 100.0
                gauges["drawdown_today_pct"] = float(dd)

        # Kill events.
        row = _fetchone(con, "SELECT COUNT(*) AS n FROM audit_events WHERE event LIKE 'RISK_KILL_%'")
        counters["kill_events_total"] = int(row.get("n") or 0) if row else 0
        counters["kill_events_by_event"] = {
            str(r["event"]): int(r["n"])
            for r in _fetchall(con, "SELECT event, COUNT(*) AS n FROM audit_events WHERE event LIKE 'RISK_KILL_%' GROUP BY event")
            if r.get("event")
        }

    finally:
        try:
            con.close()
        except Exception:
            pass

    out["gauges"] = gauges
    out["counters"] = counters
    return out


def build_prometheus_metrics(mode: str) -> str:
    m = build_metrics(mode)
    mode2 = str(m.get("mode") or (mode or "paper")).strip().lower()
    gauges = m.get("gauges") if isinstance(m.get("gauges"), dict) else {}
    counters = m.get("counters") if isinstance(m.get("counters"), dict) else {}

    lines: list[str] = []

    # Gauges.
    for k, v in (gauges or {}).items():
        name = f"aiq_{str(k)}"
        try:
            val = float(v)
        except Exception:
            continue
        lines.append(_prom_line(name, val, {"mode": mode2}).rstrip("\n"))

    def _emit_counter(name_key: str, by_key: str | None, *, label_key: str) -> None:
        name = f"aiq_{name_key}"
        total = counters.get(name_key)
        if total is not None:
            try:
                val = float(total)
            except Exception:
                val = None
            if val is not None:
                lines.append(_prom_line(name, val, {"mode": mode2, label_key: "all"}).rstrip("\n"))
        if by_key:
            d = counters.get(by_key)
            if isinstance(d, dict):
                for lbl, val0 in d.items():
                    try:
                        val = float(val0)
                    except Exception:
                        continue
                    lines.append(_prom_line(name, val, {"mode": mode2, label_key: str(lbl)}).rstrip("\n"))

    _emit_counter("orders_total", "orders_by_action", label_key="action")
    _emit_counter("fills_total", "fills_by_action", label_key="action")
    _emit_counter("kill_events_total", "kill_events_by_event", label_key="event")

    # Any other counters.
    for k, v in (counters or {}).items():
        if k in {"orders_total", "orders_by_action", "fills_total", "fills_by_action", "kill_events_total", "kill_events_by_event"}:
            continue
        if isinstance(v, dict):
            continue
        name = f"aiq_{str(k)}"
        try:
            val = float(v)
        except Exception:
            continue
        lines.append(_prom_line(name, val, {"mode": mode2}).rstrip("\n"))

    return "\n".join(lines) + ("\n" if lines else "")


def _has_table(con: sqlite3.Connection, table: str) -> bool:
    """Check if a SQLite table exists."""
    row = _fetchone(con, "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return bool(row)


def _has_column(con: sqlite3.Connection, table: str, column: str) -> bool:
    """Check if a SQLite table has a specific column."""
    try:
        rows = _fetchall(con, f"PRAGMA table_info({table})")
    except Exception:
        return False
    for row in rows:
        if str(row.get("name") or "").strip() == column:
            return True
    return False


def _parse_int(val: str | None, default: int) -> int:
    """Parse an integer query-string value, returning *default* on failure."""
    raw = str(val or "").strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


# ── Decision Trace API (AQC-805) ────────────────────────────────────────


def build_decisions_list(
    mode: str,
    *,
    symbol: str | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
    event_type: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """List decision events with optional filters and pagination."""
    mode2 = (mode or "paper").strip().lower()
    db_path, _log_path = mode_paths(mode2)

    limit = max(1, min(1000, int(limit)))
    offset = max(0, int(offset))

    if not db_path.exists():
        return {"data": [], "total": 0, "limit": limit, "offset": offset, "error": "db_missing"}

    try:
        con = connect_db_ro(db_path)
    except Exception as e:
        return {"data": [], "total": 0, "limit": limit, "offset": offset, "error": f"db_open_failed:{e}"}

    try:
        if not _has_table(con, "decision_events"):
            return {"data": [], "total": 0, "limit": limit, "offset": offset}
        cfg_col = "config_fingerprint" if _has_column(con, "decision_events", "config_fingerprint") else "NULL AS config_fingerprint"

        where_clauses: list[str] = []
        params: list[Any] = []

        if symbol:
            where_clauses.append("symbol = ?")
            params.append(symbol.strip().upper())
        if start_ms is not None:
            where_clauses.append("timestamp_ms >= ?")
            params.append(int(start_ms))
        if end_ms is not None:
            where_clauses.append("timestamp_ms <= ?")
            params.append(int(end_ms))
        if event_type:
            where_clauses.append("event_type = ?")
            params.append(event_type.strip())
        if status:
            where_clauses.append("status = ?")
            params.append(status.strip())

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        count_row = _fetchone(con, f"SELECT COUNT(*) AS total FROM decision_events{where_sql}", tuple(params))
        total = int(count_row["total"]) if count_row and count_row.get("total") is not None else 0

        rows = _fetchall(
            con,
            f"""
            SELECT id, timestamp_ms, symbol, event_type, status, decision_phase,
                   parent_decision_id, trade_id, triggered_by, action_taken,
                   rejection_reason, {cfg_col}, context_json
            FROM decision_events
            {where_sql}
            ORDER BY timestamp_ms DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params) + (limit, offset),
        )

        return {"data": rows, "total": total, "limit": limit, "offset": offset}
    finally:
        try:
            con.close()
        except Exception:
            pass


def build_decision_detail(mode: str, decision_id: str) -> dict[str, Any] | None:
    """Fetch a single decision event with its context and gate evaluations."""
    mode2 = (mode or "paper").strip().lower()
    db_path, _log_path = mode_paths(mode2)

    if not db_path.exists():
        return None

    try:
        con = connect_db_ro(db_path)
    except Exception:
        return None

    try:
        if not _has_table(con, "decision_events"):
            return None
        cfg_col = "config_fingerprint" if _has_column(con, "decision_events", "config_fingerprint") else "NULL AS config_fingerprint"

        decision = _fetchone(
            con,
            f"""
            SELECT id, timestamp_ms, symbol, event_type, status, decision_phase,
                   parent_decision_id, trade_id, triggered_by, action_taken,
                   rejection_reason, {cfg_col}, context_json
            FROM decision_events WHERE id = ?
            """,
            (decision_id,),
        )
        if not decision:
            return None

        context: list[dict[str, Any]] = []
        if _has_table(con, "decision_context"):
            context = _fetchall(
                con,
                "SELECT * FROM decision_context WHERE decision_id = ?",
                (decision_id,),
            )

        gates: list[dict[str, Any]] = []
        if _has_table(con, "gate_evaluations"):
            gates = _fetchall(
                con,
                """
                SELECT id, decision_id, gate_name, gate_passed, metric_value,
                       threshold_value, operator, explanation
                FROM gate_evaluations WHERE decision_id = ?
                ORDER BY id ASC
                """,
                (decision_id,),
            )

        return {"decision": decision, "context": context, "gates": gates}
    finally:
        try:
            con.close()
        except Exception:
            pass


def build_trade_decision_trace(mode: str, trade_id: int) -> dict[str, Any]:
    """Build the entry-to-exit decision chain for a trade."""
    mode2 = (mode or "paper").strip().lower()
    db_path, _log_path = mode_paths(mode2)

    if not db_path.exists():
        return {"chain": [], "lineage": None, "error": "db_missing"}

    try:
        con = connect_db_ro(db_path)
    except Exception as e:
        return {"chain": [], "lineage": None, "error": f"db_open_failed:{e}"}

    try:
        if not _has_table(con, "decision_lineage") or not _has_table(con, "decision_events"):
            return {"chain": [], "lineage": None}
        cfg_col = "config_fingerprint" if _has_column(con, "decision_events", "config_fingerprint") else "NULL AS config_fingerprint"

        # Find lineage rows that reference this trade (as entry or exit).
        lineage_rows = _fetchall(
            con,
            """
            SELECT id, signal_decision_id, entry_trade_id, exit_decision_id,
                   exit_trade_id, exit_reason, duration_ms
            FROM decision_lineage
            WHERE entry_trade_id = ? OR exit_trade_id = ?
            """,
            (trade_id, trade_id),
        )

        # Use first lineage row as the primary lineage record.
        lineage = lineage_rows[0] if lineage_rows else None

        # Collect all decision IDs and trade IDs referenced by lineage.
        decision_ids: set[str] = set()
        trade_ids: set[int] = set()
        for row in lineage_rows:
            if row.get("signal_decision_id"):
                decision_ids.add(row["signal_decision_id"])
            if row.get("exit_decision_id"):
                decision_ids.add(row["exit_decision_id"])
            if row.get("entry_trade_id") is not None:
                trade_ids.add(int(row["entry_trade_id"]))
            if row.get("exit_trade_id") is not None:
                trade_ids.add(int(row["exit_trade_id"]))

        # Also include decision_events directly linked to these trade_ids.
        if trade_ids:
            ph = _placeholders(len(trade_ids))
            trade_linked = _fetchall(
                con,
                f"SELECT id FROM decision_events WHERE trade_id IN ({ph})",
                tuple(trade_ids),
            )
            for r in trade_linked:
                decision_ids.add(r["id"])

        if not decision_ids:
            return {"chain": [], "lineage": lineage}

        # Fetch all matching decision events, ordered chronologically.
        ph = _placeholders(len(decision_ids))
        chain = _fetchall(
            con,
            f"""
            SELECT id, timestamp_ms, symbol, event_type, status,
                   decision_phase, parent_decision_id, trade_id,
                   triggered_by, action_taken, rejection_reason, {cfg_col}, context_json
            FROM decision_events
            WHERE id IN ({ph})
            ORDER BY timestamp_ms ASC, id ASC
            """,
            tuple(decision_ids),
        )

        return {"chain": chain, "lineage": lineage}
    finally:
        try:
            con.close()
        except Exception:
            pass


def build_decision_gates(mode: str, decision_id: str) -> dict[str, Any] | None:
    """Fetch gate evaluations for a single decision."""
    mode2 = (mode or "paper").strip().lower()
    db_path, _log_path = mode_paths(mode2)

    if not db_path.exists():
        return None

    try:
        con = connect_db_ro(db_path)
    except Exception:
        return None

    try:
        if not _has_table(con, "decision_events"):
            return None

        # Verify the decision exists.
        decision = _fetchone(con, "SELECT id FROM decision_events WHERE id = ?", (decision_id,))
        if not decision:
            return None

        gates: list[dict[str, Any]] = []
        if _has_table(con, "gate_evaluations"):
            gates = _fetchall(
                con,
                """
                SELECT id, decision_id, gate_name, gate_passed, metric_value,
                       threshold_value, operator, explanation
                FROM gate_evaluations WHERE decision_id = ?
                ORDER BY id ASC
                """,
                (decision_id,),
            )

        return {"gates": gates}
    finally:
        try:
            con.close()
        except Exception:
            pass


# ── Decision Replay API (AQC-806) ───────────────────────────────────────


# Column → IndicatorSnapshot field mapping for the kernel's MarketEvent.
_CTX_TO_INDICATOR: dict[str, str] = {
    "price": "close",
    "rsi": "rsi",
    "adx": "adx",
    "adx_slope": "adx_slope",
    "macd_hist": "macd_hist",
    "ema_fast": "ema_fast",
    "ema_slow": "ema_slow",
    "ema_macro": "ema_macro",
    "bb_width_ratio": "bb_width_ratio",
    "stoch_k": "stoch_rsi_k",
    "stoch_d": "stoch_rsi_d",
    "atr": "atr",
    "atr_slope": "atr_slope",
    "volume": "volume",
    "vol_sma": "vol_sma",
}

# Gate name → GateResult field mapping.
_GATE_NAME_TO_FIELD: dict[str, str] = {
    "ranging": "is_ranging",
    "gate_ranging": "is_ranging",
    "anomaly": "is_anomaly",
    "gate_anomaly": "is_anomaly",
    "extension": "is_extended",
    "gate_extension": "is_extended",
    "volume": "vol_confirm",
    "gate_volume": "vol_confirm",
    "adx_rising": "is_trending_up",
    "gate_adx_rising": "is_trending_up",
    "adx_threshold": "adx_above_min",
    "adx": "adx_above_min",
    "gate_adx": "adx_above_min",
    "btc_alignment": "btc_ok_long",
    "gate_btc_alignment": "btc_ok_long",
}

# Inverted gates: gate_passed=1 means the condition is NOT active.
_INVERTED_GATES: set[str] = {
    "is_ranging",
    "is_anomaly",
    "is_extended",
}


def _build_indicators_from_context(ctx: dict[str, Any]) -> dict[str, Any]:
    """Build a partial IndicatorSnapshot dict from a decision_context row."""
    indicators: dict[str, Any] = {
        "close": 0.0, "high": 0.0, "low": 0.0, "open": 0.0,
        "volume": 0.0, "t": 0,
        "ema_slow": 0.0, "ema_fast": 0.0, "ema_macro": 0.0,
        "adx": 0.0, "adx_pos": 0.0, "adx_neg": 0.0, "adx_slope": 0.0,
        "bb_upper": 0.0, "bb_lower": 0.0, "bb_width": 0.0,
        "bb_width_avg": 0.0, "bb_width_ratio": 0.0,
        "atr": 0.0, "atr_slope": 0.0, "avg_atr": 0.0,
        "rsi": 50.0,
        "stoch_rsi_k": 50.0, "stoch_rsi_d": 50.0,
        "macd_hist": 0.0, "prev_macd_hist": 0.0,
        "prev2_macd_hist": 0.0, "prev3_macd_hist": 0.0,
        "vol_sma": 0.0, "vol_trend": False,
        "prev_close": 0.0, "prev_ema_fast": 0.0, "prev_ema_slow": 0.0,
        "bar_count": 100, "funding_rate": 0.0,
    }
    for ctx_col, ind_field in _CTX_TO_INDICATOR.items():
        val = ctx.get(ctx_col)
        if val is not None:
            indicators[ind_field] = float(val)
    # Also copy price → high/low/open for a minimal snapshot.
    price = ctx.get("price")
    if price is not None:
        p = float(price)
        indicators["close"] = p
        indicators["high"] = p
        indicators["low"] = p
        indicators["open"] = p
        indicators["prev_close"] = p
    return indicators


def _build_gate_result_from_evaluations(gates: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a GateResult dict from gate_evaluations rows."""
    result: dict[str, Any] = {
        "is_ranging": False, "is_anomaly": False, "is_extended": False,
        "vol_confirm": True, "is_trending_up": True, "adx_above_min": True,
        "bullish_alignment": False, "bearish_alignment": False,
        "btc_ok_long": True, "btc_ok_short": True,
        "effective_min_adx": 20.0, "bb_width_ratio": 0.0, "dynamic_tp_mult": 1.0,
        "rsi_long_limit": 70.0, "rsi_short_limit": 30.0,
        "stoch_k": 50.0, "stoch_d": 50.0, "stoch_rsi_active": False,
        "all_gates_pass": True,
    }
    for g in gates:
        gate_name = str(g.get("gate_name", "")).strip().lower()
        passed = bool(g.get("gate_passed", 0))
        field = _GATE_NAME_TO_FIELD.get(gate_name)
        if field:
            if field in _INVERTED_GATES:
                # For inverted gates: passed=True means NOT ranging/anomaly/extended.
                result[field] = not passed
            else:
                result[field] = passed
    # Recompute all_gates_pass from constituent gates.
    result["all_gates_pass"] = (
        result["adx_above_min"]
        and not result["is_ranging"]
        and not result["is_anomaly"]
        and not result["is_extended"]
        and result["vol_confirm"]
        and result["is_trending_up"]
    )
    return result


def _infer_signal(event_type: str, action_taken: str | None) -> str:
    """Map decision event_type + action_taken to a MarketSignal string."""
    et = (event_type or "").strip().lower()
    act = (action_taken or "").strip().lower()
    if et in ("entry_signal", "gate_block"):
        if "short" in act or "sell" in act:
            return "Sell"
        return "Buy"
    if et in ("exit_check", "exit_signal"):
        return "PriceUpdate"
    if et == "fill":
        if "short" in act or "sell" in act:
            return "Sell"
        return "Buy"
    # Default to Buy for unknown entry-like events.
    return "Buy"


def _compute_replay_diff(
    original_event: dict[str, Any],
    original_gates: list[dict[str, Any]],
    replayed: dict[str, Any],
) -> dict[str, Any]:
    """Compare original decision outcome vs replayed kernel result."""
    details: list[str] = []

    # --- Gate comparison ---
    replayed_diag = replayed.get("diagnostics") or {}
    replayed_thresholds = replayed_diag.get("applied_thresholds") or []
    replayed_gate_blocked = replayed_diag.get("gate_blocked", False)

    # Build original gate pass/fail map.
    orig_gate_map: dict[str, bool] = {}
    for g in original_gates:
        gn = str(g.get("gate_name", "")).strip().lower()
        orig_gate_map[gn] = bool(g.get("gate_passed", 0))

    # Build replayed gate map from applied_thresholds.
    replay_gate_map: dict[str, bool] = {}
    for t in replayed_thresholds:
        tn = str(t.get("name", "")).strip().lower()
        replay_gate_map[tn] = bool(t.get("passed", False))

    gates_match = True
    for gn, orig_passed in orig_gate_map.items():
        # Try exact match, then normalized forms.
        replay_passed = replay_gate_map.get(gn)
        if replay_passed is None:
            # Try with _gate suffix / prefix variations.
            for rn, rp in replay_gate_map.items():
                if gn in rn or rn in gn:
                    replay_passed = rp
                    break
        if replay_passed is not None and replay_passed != orig_passed:
            gates_match = False
            details.append(f"gate '{gn}': original={orig_passed}, replayed={replay_passed}")

    # --- Outcome comparison ---
    orig_status = str(original_event.get("status", "")).strip().lower()
    orig_approved = orig_status in ("executed", "approved", "filled")

    replayed_intents = replayed.get("intents") or []
    replay_approved = len(replayed_intents) > 0 and not replayed_gate_blocked

    outcome_match = orig_approved == replay_approved
    if not outcome_match:
        details.append(
            f"outcome: original={'approved' if orig_approved else 'rejected'}, "
            f"replayed={'approved' if replay_approved else 'rejected'}"
        )

    return {
        "gates_match": gates_match,
        "outcome_match": outcome_match,
        "details": details,
    }


def build_decision_replay(
    mode: str,
    decision_id: str,
    *,
    state_override_json: str | None = None,
) -> dict[str, Any]:
    """Replay a decision through the kernel and diff against the original.

    Returns a dict with ``ok``, ``decision_id``, ``original``, ``replayed``,
    and ``diff`` keys.
    """
    if not _BT_RUNTIME_OK:
        return {"ok": False, "error": "bt_runtime_not_available", "decision_id": decision_id}

    mode2 = (mode or "paper").strip().lower()
    db_path, _log_path = mode_paths(mode2)

    if not db_path.exists():
        return {"ok": False, "error": "db_missing", "decision_id": decision_id}

    try:
        con = connect_db_ro(db_path)
    except Exception as e:
        return {"ok": False, "error": f"db_open_failed:{e}", "decision_id": decision_id}

    try:
        if not _has_table(con, "decision_events"):
            return {"ok": False, "error": "table_missing", "decision_id": decision_id}

        # 1. Fetch the original decision event.
        decision = _fetchone(
            con,
            """
            SELECT id, timestamp_ms, symbol, event_type, status, decision_phase,
                   parent_decision_id, trade_id, triggered_by, action_taken,
                   rejection_reason, context_json
            FROM decision_events WHERE id = ?
            """,
            (decision_id,),
        )
        if not decision:
            return {"ok": False, "error": "not_found", "decision_id": decision_id}

        # 2. Fetch indicator context.
        ctx: dict[str, Any] = {}
        if _has_table(con, "decision_context"):
            ctx_row = _fetchone(
                con,
                "SELECT * FROM decision_context WHERE decision_id = ?",
                (decision_id,),
            )
            if ctx_row:
                ctx = ctx_row

        # 3. Fetch gate evaluations.
        gates: list[dict[str, Any]] = []
        if _has_table(con, "gate_evaluations"):
            gates = _fetchall(
                con,
                """
                SELECT id, decision_id, gate_name, gate_passed, metric_value,
                       threshold_value, operator, explanation
                FROM gate_evaluations WHERE decision_id = ?
                ORDER BY id ASC
                """,
                (decision_id,),
            )
    finally:
        try:
            con.close()
        except Exception:
            pass

    # 4. Build indicator snapshot from context.
    indicators = _build_indicators_from_context(ctx)

    # Build original response summary.
    original_indicators = {k: v for k, v in ctx.items() if k not in ("decision_id", "symbol")}
    original = {
        "event_type": decision.get("event_type"),
        "status": decision.get("status"),
        "action_taken": decision.get("action_taken"),
        "indicators": original_indicators,
        "gates": gates,
    }

    # 5. Build gate result from evaluations.
    gate_result = _build_gate_result_from_evaluations(gates)

    # Carry over alignment from context if available.
    if ctx.get("bullish_alignment") is not None:
        gate_result["bullish_alignment"] = bool(ctx["bullish_alignment"])
    if ctx.get("bearish_alignment") is not None:
        gate_result["bearish_alignment"] = bool(ctx["bearish_alignment"])

    # 6. Build the MarketEvent JSON.
    signal = _infer_signal(
        decision.get("event_type", ""),
        decision.get("action_taken"),
    )
    event_json_obj: dict[str, Any] = {
        "schema_version": 8,
        "event_id": abs(hash(decision_id)) % (2**63),
        "timestamp_ms": decision.get("timestamp_ms", 0),
        "symbol": decision.get("symbol", "BTCUSDT"),
        "signal": signal,
        "price": float(ctx.get("price", 0) or 0),
        "indicators": indicators if signal == "PriceUpdate" else None,
        "gate_result": gate_result if signal in ("Buy", "Sell") else None,
    }

    # 7. Load strategy state.
    if state_override_json:
        state_json = state_override_json
    else:
        state_path = _find_kernel_state_path(db_path)
        if state_path is None:
            return {
                "ok": False, "error": "kernel_state_not_found",
                "decision_id": decision_id, "original": original,
            }
        try:
            state_json = _bt_runtime.load_state(str(state_path))
        except Exception as e:
            return {
                "ok": False, "error": f"load_state_failed:{e}",
                "decision_id": decision_id, "original": original,
            }

    # 8. Load or default kernel params.
    params_json: str | None = None
    params_path = db_path.parent / "kernel_params.json"
    if params_path.exists():
        try:
            params_json = params_path.read_text(encoding="utf-8")
        except Exception:
            params_json = None
    if not params_json:
        try:
            params_json = _bt_runtime.default_kernel_params_json()
        except Exception:
            params_json = '{"schema_version":8}'

    # 9. Call the kernel.
    event_json_str = json.dumps(event_json_obj)
    try:
        result_json = _bt_runtime.step_decision(state_json, event_json_str, params_json)
    except Exception as e:
        return {
            "ok": False, "error": f"step_decision_failed:{e}",
            "decision_id": decision_id, "original": original,
        }

    try:
        replayed = json.loads(result_json)
    except Exception as e:
        return {
            "ok": False, "error": f"result_parse_failed:{e}",
            "decision_id": decision_id, "original": original,
        }

    # 10. Compute diff.
    diff = _compute_replay_diff(decision, gates, replayed)

    return {
        "ok": True,
        "decision_id": decision_id,
        "original": original,
        "replayed": {
            "intents": replayed.get("intents", []),
            "fills": replayed.get("fills", []),
            "diagnostics": replayed.get("diagnostics", {}),
        },
        "diff": diff,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "aiq-monitor/0.1"

    def setup(self) -> None:
        super().setup()
        self._active_request_slot = _ACTIVE_REQUEST_LIMITER.acquire()

    def finish(self) -> None:
        try:
            super().finish()
        finally:
            if getattr(self, "_active_request_slot", False):
                _ACTIVE_REQUEST_LIMITER.release()

    def _client_ip(self) -> str:
        try:
            host = self.client_address[0]
        except Exception:
            host = ""
        return str(host or "").strip() or "unknown"

    def _is_api_rate_limited(self, path: str) -> bool:
        if not str(path or "").startswith("/api/"):
            return False
        if not _API_RATE_LIMIT_ENABLED:
            return False
        return not _API_RATE_LIMITER.allow(self._client_ip())

    def _check_api_rate_limit(self, path: str, *, head: bool = False) -> bool:
        if not self._is_api_rate_limited(path):
            return True
        if head:
            self._send_headers(429, "application/json; charset=utf-8", 0)
        else:
            self._send_json(
                {
                    "error": "rate_limited",
                    "retry_after_s": 1,
                },
                status=429,
            )
        return False

    def _reject_overloaded(self, *, head: bool = False) -> bool:
        if getattr(self, "_active_request_slot", True):
            return False
        if head:
            self._send_headers(503, "text/plain; charset=utf-8", 0)
        else:
            self._send_json({"error": "server_busy", "reason": "too_many_active_requests"}, status=503)
        self.close_connection = True
        return True

    def _send_headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(length))
        self.end_headers()

    def _send_sse_headers(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self._send_headers(status, content_type, len(body))
        self.wfile.write(body)

    def _send_json(self, obj: Any, status: int = 200) -> None:
        self._send(status, _json(obj), "application/json; charset=utf-8")

    def _send_text(self, text: str, status: int = 200) -> None:
        self._send(status, text.encode("utf-8"), "text/plain; charset=utf-8")

    def _stream_mids_events(self) -> None:
        keepalive_s = max(5.0, _env_float("AIQ_MONITOR_MIDS_STREAM_KEEPALIVE_S", 15.0))
        try:
            self._send_sse_headers()
            self.close_connection = False

            snap = STATE.mids.snapshot()
            seq = int(snap.get("seq") or 0)
            self.wfile.write(b"retry: 1000\n")
            self.wfile.write(b"event: mids\n")
            self.wfile.write(b"data: " + _json(snap) + b"\n\n")
            self.wfile.flush()

            while True:
                snap = STATE.mids.wait_snapshot_since(after_seq=seq, timeout_s=keepalive_s)
                next_seq = int(snap.get("seq") or 0)
                if next_seq > seq:
                    seq = next_seq
                    self.wfile.write(b"event: mids\n")
                    self.wfile.write(b"data: " + _json(snap) + b"\n\n")
                else:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            return
        except Exception:
            return

    def _serve_static(self, rel_path: str) -> None:
        p = (STATIC_DIR / rel_path.lstrip("/")).resolve()
        if not str(p).startswith(str(STATIC_DIR.resolve())):
            self._send_text("bad path", status=400)
            return
        if not p.exists() or not p.is_file():
            self._send_text("not found", status=404)
            return
        ctype, _ = mimetypes.guess_type(str(p))
        data = p.read_bytes()
        self._send(200, data, (ctype or "application/octet-stream") + "; charset=utf-8" if (ctype or "").startswith("text/") else (ctype or "application/octet-stream"))

    def do_HEAD(self) -> None:  # noqa: N802
        if self._reject_overloaded(head=True):
            return
        parsed = urlparse(self.path)
        path = parsed.path or "/"

        if path == "/" or path == "/index.html":
            p = (STATIC_DIR / "index.html").resolve()
            if p.exists():
                self._send_headers(200, "text/html; charset=utf-8", p.stat().st_size)
            else:
                self._send_headers(404, "text/plain; charset=utf-8", 0)
            return

        if path.startswith("/static/"):
            rel = path[len("/static/") :]
            p = (STATIC_DIR / rel.lstrip("/")).resolve()
            if str(p).startswith(str(STATIC_DIR.resolve())) and p.exists() and p.is_file():
                ctype, _ = mimetypes.guess_type(str(p))
                ct = (ctype or "application/octet-stream") + "; charset=utf-8" if (ctype or "").startswith("text/") else (ctype or "application/octet-stream")
                self._send_headers(200, ct, p.stat().st_size)
            else:
                self._send_headers(404, "text/plain; charset=utf-8", 0)
            return

        if path.startswith("/api/"):
            if not self._check_api_rate_limit(path, head=True):
                return
            # API responses are dynamic; omit body but respond OK.
            self._send_headers(200, "application/json; charset=utf-8", 0)
            return

        if path == "/metrics":
            self._send_headers(200, "text/plain; charset=utf-8", 0)
            return

        self._send_headers(404, "text/plain; charset=utf-8", 0)

    def _check_api_auth(self) -> bool:
        """Return True if request is authorised for /api/ access.

        When ``AIQ_MONITOR_TOKEN`` is unset, all requests are allowed (backwards-compatible).
        """
        token = os.getenv("AIQ_MONITOR_TOKEN", "").strip()
        if not token:
            return True
        auth = str(self.headers.get("Authorization", "") or "")
        expected = f"Bearer {token}".encode("utf-8", errors="replace")
        auth_bytes = auth.encode("utf-8", errors="replace")
        if hmac.compare_digest(auth_bytes, expected):
            return True
        self._send_json({"error": "unauthorized"}, status=401)
        return False

    def do_GET(self) -> None:  # noqa: N802
        if self._reject_overloaded():
            return
        parsed = urlparse(self.path)
        path = parsed.path or "/"

        # /health — lightweight, no auth required
        if path == "/health":
            self._send_json({"status": "ok", "ts": _utc_now_ms()})
            return

        if path == "/" or path == "/index.html":
            self._serve_static("index.html")
            return
        if path.startswith("/static/"):
            self._serve_static(path[len("/static/") :])
            return

        if not self._check_api_rate_limit(path):
            return

        # All /api/ endpoints require auth when AIQ_MONITOR_TOKEN is set.
        if path.startswith("/api/") and not self._check_api_auth():
            return

        if path == "/api/health":
            self._send_json({"ok": True, "now_ts_ms": _utc_now_ms(), "ws": STATE.mids.snapshot()})
            return

        if path == "/api/mids":
            self._send_json(STATE.mids.snapshot())
            return

        if path == "/api/mids/stream":
            self._stream_mids_events()
            return

        if path == "/api/sparkline":
            qs = parse_qs(parsed.query or "")
            symbol = (qs.get("symbol") or [""])[0]
            window_s = int((qs.get("window_s") or ["600"])[0])
            self._send_json({"symbol": symbol, "window_s": window_s, "points": STATE.mids.history(symbol, window_s=window_s)})
            return

        if path == "/api/marks":
            qs = parse_qs(parsed.query or "")
            mode = (qs.get("mode") or ["paper"])[0]
            symbol = (qs.get("symbol") or [""])[0]
            self._send_json(build_marks(mode, symbol))
            return

        if path == "/api/candles":
            qs = parse_qs(parsed.query or "")
            mode = (qs.get("mode") or ["paper"])[0]
            symbol = (qs.get("symbol") or [""])[0]
            interval = (qs.get("interval") or [effective_trader_interval_for_mode(mode)])[0]
            try:
                limit = int((qs.get("limit") or ["200"])[0])
            except Exception:
                limit = 200
            self._send_json(build_candles(mode, symbol, interval, limit))
            return

        if path == "/api/snapshot":
            qs = parse_qs(parsed.query or "")
            mode = (qs.get("mode") or ["paper"])[0]
            snap = STATE.get_snapshot_cached(mode, lambda: build_snapshot(mode))
            self._send_json(snap)
            return

        # ── Decision Trace API v2 (AQC-805) ────────────────────────────
        if path == "/api/v2/decisions":
            qs = parse_qs(parsed.query or "")
            mode = (qs.get("mode") or ["paper"])[0]
            symbol = (qs.get("symbol") or [None])[0]
            start_ms = _parse_int((qs.get("start") or [None])[0], 0) or None
            end_ms = _parse_int((qs.get("end") or [None])[0], 0) or None
            event_type = (qs.get("event_type") or [None])[0]
            status = (qs.get("status") or [None])[0]
            limit = _parse_int((qs.get("limit") or ["100"])[0], 100)
            offset = _parse_int((qs.get("offset") or ["0"])[0], 0)
            result = build_decisions_list(
                mode,
                symbol=symbol,
                start_ms=start_ms,
                end_ms=end_ms,
                event_type=event_type,
                status=status,
                limit=limit,
                offset=offset,
            )
            self._send_json(result)
            return

        _m_decision_gates = re.match(r"^/api/v2/decisions/([^/]+)/gates$", path)
        if _m_decision_gates:
            qs = parse_qs(parsed.query or "")
            mode = (qs.get("mode") or ["paper"])[0]
            decision_id = _m_decision_gates.group(1)
            result = build_decision_gates(mode, decision_id)
            if result is None:
                self._send_json({"error": "not_found"}, status=404)
            else:
                self._send_json(result)
            return

        _m_decision_detail = re.match(r"^/api/v2/decisions/([^/]+)$", path)
        if _m_decision_detail:
            qs = parse_qs(parsed.query or "")
            mode = (qs.get("mode") or ["paper"])[0]
            decision_id = _m_decision_detail.group(1)
            result = build_decision_detail(mode, decision_id)
            if result is None:
                self._send_json({"error": "not_found"}, status=404)
            else:
                self._send_json(result)
            return

        _m_trade_trace = re.match(r"^/api/v2/trades/(\d+)/decision-trace$", path)
        if _m_trade_trace:
            qs = parse_qs(parsed.query or "")
            mode = (qs.get("mode") or ["paper"])[0]
            trade_id = int(_m_trade_trace.group(1))
            result = build_trade_decision_trace(mode, trade_id)
            self._send_json(result)
            return

        if path == "/api/metrics":
            qs = parse_qs(parsed.query or "")
            mode = (qs.get("mode") or ["paper"])[0]
            self._send_json(build_metrics(mode))
            return

        if path == "/metrics":
            qs = parse_qs(parsed.query or "")
            mode = (qs.get("mode") or ["paper"])[0]
            self._send_text(build_prometheus_metrics(mode))
            return

        self._send_text("not found", status=404)

    # ── POST endpoints ───────────────────────────────────────────────
    def do_POST(self) -> None:  # noqa: N802
        if self._reject_overloaded():
            return
        parsed = urlparse(self.path)
        path = parsed.path or "/"

        if not self._check_api_rate_limit(path):
            return

        # All POST endpoints require auth when AIQ_MONITOR_TOKEN is set.
        if path.startswith("/api/") and not self._check_api_auth():
            return

        # Read request body.
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            content_length = 0
        if content_length > int(_MAX_POST_BODY_BYTES):
            self._send_json(
                {"ok": False, "error": "payload_too_large", "max_bytes": int(_MAX_POST_BODY_BYTES)},
                status=413,
            )
            return
        raw_body = self.rfile.read(content_length) if content_length > 0 else b""

        if path == "/api/v2/decisions/replay":
            try:
                body = json.loads(raw_body) if raw_body else {}
            except (json.JSONDecodeError, ValueError):
                self._send_json({"ok": False, "error": "invalid_json"}, status=400)
                return

            decision_id = body.get("decision_id")
            if not decision_id:
                self._send_json({"ok": False, "error": "missing_decision_id"}, status=400)
                return

            qs = parse_qs(parsed.query or "")
            mode = (qs.get("mode") or ["paper"])[0]
            state_override_json = body.get("state_override_json")

            result = build_decision_replay(
                mode,
                str(decision_id),
                state_override_json=state_override_json,
            )

            if result.get("error") == "not_found":
                self._send_json(result, status=404)
            elif result.get("error") == "bt_runtime_not_available":
                self._send_json(result, status=503)
            elif not result.get("ok"):
                self._send_json(result, status=500)
            else:
                self._send_json(result)
            return

        self._send_text("not found", status=404)

    def log_message(self, fmt: str, *args) -> None:
        # Keep healthy traffic quiet; surface client/server errors for troubleshooting.
        status_code = 0
        try:
            status_code = int(str(args[1]))
        except Exception:
            status_code = 0
        if status_code < 400:
            return
        try:
            super().log_message(fmt, *args)
        except Exception:
            return


class MonitorHTTPServer(ThreadingHTTPServer):
    # Keep socket backlog bounded to avoid unbounded pending-connection memory growth.
    request_queue_size = _monitor_request_queue_size()


def main() -> None:
    bind = os.getenv("AIQ_MONITOR_BIND", "127.0.0.1")
    port = _env_int("AIQ_MONITOR_PORT", 61010)
    token = os.getenv("AIQ_MONITOR_TOKEN", "").strip()
    tls_terminated = _env_bool("AIQ_MONITOR_TLS_TERMINATED", False)
    bind_security_error = _monitor_bind_security_error(bind=bind, token=token, tls_terminated=tls_terminated)
    if bind_security_error:
        raise SystemExit(bind_security_error)

    if not _is_local_bind(bind) and not token:
        print(f"⚠️  WARNING: Monitor bound to {bind} without AIQ_MONITOR_TOKEN — API endpoints are unauthenticated")
    if not _is_local_bind(bind) and token and tls_terminated:
        print("AI Quant Monitor non-local bind assumes HTTPS reverse-proxy TLS termination.")

    srv = MonitorHTTPServer((bind, port), Handler)
    print(f"AI Quant Monitor listening on http://{bind}:{port}/")

    watchdog = None
    try:
        from engine.systemd_watchdog import SystemdWatchdog

        watchdog = SystemdWatchdog(service_name="ai-quant-monitor")
        watchdog.start()
    except Exception:
        watchdog = None

    try:
        srv.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if watchdog is not None:
                watchdog.stop()
        except Exception:
            pass
        try:
            srv.server_close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
