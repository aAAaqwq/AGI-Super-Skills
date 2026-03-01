"""Live trading adapter.

Used by the unified daemon (`python -m engine.daemon`) when
`AI_QUANT_MODE` is `live` or `dry_live`.

This module is intentionally NOT a standalone daemon entrypoint.
"""

import datetime
import json
import logging
import os
import queue
import sqlite3
import threading
import time
import atexit

import exchange.meta as hyperliquid_meta
import exchange.ws as hyperliquid_ws

from engine.alerting import send_openclaw_message
import strategy.mei_alpha_v1 as mei_alpha_v1

try:
    _DB_TIMEOUT_S = min(float(os.getenv("AI_QUANT_DB_TIMEOUT_S", "5")), 5.0)
except Exception:
    _DB_TIMEOUT_S = 5.0

from exchange.executor import (
    HyperliquidLiveExecutor,
    live_entries_enabled,
    live_mode,
    live_orders_enabled,
    load_live_secrets,  # noqa: F401  (re-exported for engine.daemon)
    utc_iso,
)

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_float(val, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        return float(val)
    except Exception:
        return default


def _current_run_fingerprint() -> str:
    try:
        return str(mei_alpha_v1.get_run_fingerprint() or "unknown")
    except Exception:
        raw = str(os.getenv("AI_QUANT_RUN_FINGERPRINT", "") or "").strip()
        return raw or "unknown"


def _ensure_position_state_history_table(cur: sqlite3.Cursor) -> bool:
    try:
        cur.execute(
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
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_position_state_history_symbol_ts ON position_state_history(symbol, event_ts_ms)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_position_state_history_open_trade_ts ON position_state_history(open_trade_id, event_ts_ms)"
        )
        return True
    except sqlite3.Error as exc:
        logger.debug("position_state_history schema ensure skipped: %s", exc)
        return False


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


def _configure_live_db_connection(conn: sqlite3.Connection) -> None:
    """Apply SQLite pragmas for low-latency live-path reads/writes."""
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception as exc:
        logger.debug("failed to apply live DB pragmas: %s", exc, exc_info=True)


def _env_str(name: str, default: str = "") -> str:
    raw = os.getenv(name)
    return default if raw is None else str(raw)


def _pct_str_from_baseline(value_usd: float, *, baseline_usd: float, is_return: bool) -> str:
    try:
        b = float(baseline_usd)
    except Exception:
        b = 0.0
    if b <= 1e-9:
        return "n/a"
    try:
        v = float(value_usd)
    except Exception:
        v = 0.0
    if is_return:
        p = ((v - b) / b) * 100.0
    else:
        p = (v / b) * 100.0
    return f"{p:+.2f}%"


def _discord_label() -> str:
    label = _env_str("AI_QUANT_DISCORD_LABEL", "").strip()
    if label:
        return label
    return _env_str("AI_QUANT_INSTANCE_TAG", "").strip()


def _decorate_discord_message(message: str) -> str:
    msg = str(message)
    label = _discord_label()
    if not label:
        return msg
    prefix = f"[{label}]"
    if msg.startswith(prefix):
        return msg
    return f"{prefix} {msg}"


def _live_discord_target() -> str | None:
    target = _env_str("AI_QUANT_DISCORD_CHANNEL_LIVE", "").strip()
    return target or None


def _live_notify_enabled() -> bool:
    return _env_bool("AI_QUANT_NOTIFY_DISCORD_LIVE", False) and bool(_live_discord_target())


def _send_discord_message_sync(*, target: str, message: str) -> None:
    try:
        try:
            timeout_s = float(os.getenv("AI_QUANT_DISCORD_SEND_TIMEOUT_S", "6"))
        except Exception:
            timeout_s = 6.0
        timeout_s = max(1.0, min(30.0, timeout_s))
        send_openclaw_message(
            channel="discord",
            target=str(target),
            message=_decorate_discord_message(str(message)),
            timeout_s=timeout_s,
        )
    except Exception as e:
        print(f"⚠️ Failed to send Discord message (target={target}): {e}")


_DISCORD_QUEUE_LOCK = threading.RLock()
_DISCORD_QUEUE_MAX = 200
try:
    _DISCORD_QUEUE_MAX = int(float(os.getenv("AI_QUANT_DISCORD_QUEUE_MAX", "200") or 200))
except Exception:
    _DISCORD_QUEUE_MAX = 200
_DISCORD_QUEUE_MAX = max(10, min(5000, int(_DISCORD_QUEUE_MAX)))

# NOTE(L4): This global queue is shared across all instances in the same process.
# Multi-instance deployments should use separate processes to avoid queue contention.
_DISCORD_QUEUE: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=_DISCORD_QUEUE_MAX)
_DISCORD_WORKER_STARTED = False
_DISCORD_WORKER_THREAD: threading.Thread | None = None
_DISCORD_WORKER_STOP = threading.Event()


def _discord_worker() -> None:
    while not _DISCORD_WORKER_STOP.is_set():
        try:
            target, message = _DISCORD_QUEUE.get(timeout=0.5)
        except queue.Empty:
            continue
        try:
            _send_discord_message_sync(target=target, message=message)
        except Exception as e:
            logger.debug("failed to send discord message (target=%s): %s", target, e, exc_info=True)
        finally:
            try:
                _DISCORD_QUEUE.task_done()
            except Exception as e:
                logger.debug("failed to mark discord queue task done: %s", e, exc_info=True)

    with _DISCORD_QUEUE_LOCK:
        global _DISCORD_WORKER_STARTED, _DISCORD_WORKER_THREAD
        _DISCORD_WORKER_STARTED = False
        _DISCORD_WORKER_THREAD = None


def _ensure_discord_worker_started() -> None:
    global _DISCORD_WORKER_STARTED, _DISCORD_WORKER_THREAD
    with _DISCORD_QUEUE_LOCK:
        if _DISCORD_WORKER_THREAD is not None and _DISCORD_WORKER_THREAD.is_alive():
            _DISCORD_WORKER_STARTED = True
            return
        _DISCORD_WORKER_STOP.clear()
        t = threading.Thread(target=_discord_worker, name="aiq_discord_sender", daemon=True)
        t.start()
        _DISCORD_WORKER_THREAD = t
        _DISCORD_WORKER_STARTED = True


def _stop_discord_worker(*, timeout_s: float = 2.0) -> None:
    global _DISCORD_WORKER_STARTED, _DISCORD_WORKER_THREAD
    with _DISCORD_QUEUE_LOCK:
        t = _DISCORD_WORKER_THREAD
        if t is None:
            _DISCORD_WORKER_STARTED = False
            return
        _DISCORD_WORKER_STOP.set()

    try:
        t.join(timeout=max(0.0, float(timeout_s)))
    except Exception:
        pass

    with _DISCORD_QUEUE_LOCK:
        if _DISCORD_WORKER_THREAD is t and not t.is_alive():
            _DISCORD_WORKER_THREAD = None
            _DISCORD_WORKER_STARTED = False


atexit.register(_stop_discord_worker)


def _send_discord_message(*, target: str, message: str) -> None:
    """Best-effort Discord send that must NOT stall the trading loop."""
    try:
        async_enabled = _env_bool("AI_QUANT_DISCORD_ASYNC", True)
    except Exception:
        async_enabled = True

    if not async_enabled:
        _send_discord_message_sync(target=target, message=message)
        return

    _ensure_discord_worker_started()
    try:
        _DISCORD_QUEUE.put_nowait((str(target), str(message)))
    except Exception:
        # Drop when overloaded; trading correctness > notifications.
        try:
            print("⚠️ Discord queue full; dropping message")
        except Exception as e:
            logger.debug("failed to print discord queue overflow warning: %s", e, exc_info=True)


def _notify_live_fill(
    *,
    symbol: str,
    action: str,
    pos_type: str,
    price: float,
    size: float,
    notional: float,
    leverage: float | None,
    margin_used_usd: float | None,
    fee_usd: float,
    fee_rate: float | None,
    fee_token: str | None,
    pnl_usd: float,
    reason: str,
    confidence: str,
    account_value_usd: float,
    withdrawable_usd: float,
    breadth_pct: float | None = None,
) -> None:
    if not _live_notify_enabled():
        return
    target = _live_discord_target()
    if not target:
        return

    # Baseline for percentage display in notifications.
    # Priority: explicit notification baseline -> paper balance env -> current account value.
    baseline_usd = _safe_float(_env_str("AI_QUANT_NOTIFY_BASELINE_USD", ""), 0.0)
    if baseline_usd <= 1e-9:
        baseline_usd = _safe_float(_env_str("AI_QUANT_PAPER_BALANCE", ""), 0.0)
    if baseline_usd <= 1e-9:
        baseline_usd = _safe_float(account_value_usd, 0.0)
    unrealised_usd = float(account_value_usd or 0.0) - float(withdrawable_usd or 0.0)

    action_map = {"OPEN": "開倉", "ADD": "加倉", "REDUCE": "部分平倉", "CLOSE": "平倉"}
    emoji = "🟦"
    if action in {"OPEN", "ADD"}:
        emoji = "🚀" if action == "OPEN" else "➕"
    elif action in {"REDUCE", "CLOSE"}:
        emoji = "💰" if pnl_usd >= 0 else "🛑"

    action_hk = action_map.get(action, action)
    fee_rate_str = "" if fee_rate is None else f" ({fee_rate * 100:.4f}%)"
    fee_token_str = f" {fee_token}" if fee_token else ""

    msg = f"{emoji} **LIVE：{action_hk}** | {symbol}\n"
    msg += f"• 類型: `{pos_type}`\n"
    msg += f"• 價格: `${price:,.4f}`\n"
    msg += f"• 規模: `{size:.6f}` (`${notional:,.2f} USD`)\n"
    try:
        lev_f = None if leverage is None else float(leverage)
    except Exception:
        lev_f = None
    if lev_f is not None and lev_f > 0:
        msg += f"• 槓桿 (Lev): `{lev_f:.0f}x`\n"
    else:
        msg += "• 槓桿 (Lev): `NA`\n"
    try:
        margin_f = None if margin_used_usd is None else float(margin_used_usd)
    except Exception:
        margin_f = None
    if margin_f is not None and abs(margin_f) > 1e-9:
        msg += f"• 保證金 (Margin est.): `${margin_f:,.2f}`\n"
    else:
        msg += "• 保證金 (Margin est.): `NA`\n"
    if fee_usd:
        msg += f"• 手續費 (Fee): `${fee_usd:,.4f}`{fee_rate_str}{fee_token_str}\n"
    if action in {"REDUCE", "CLOSE"}:
        msg += f"• 損益 (PnL): **${pnl_usd:,.2f}**\n"
    if reason:
        msg += f"• 原因: *{reason}*\n"
    if confidence and confidence != "N/A":
        msg += f"• 信心 (Conf): `{confidence}`\n"
    if breadth_pct is not None:
        msg += f"• 廣度 (Breadth): `{breadth_pct:.1f}%`\n"
    msg += (
        f"• **AccountValue:** `${account_value_usd:,.2f}` "
        f"({_pct_str_from_baseline(float(account_value_usd or 0.0), baseline_usd=baseline_usd, is_return=True)})\n"
    )
    msg += (
        f"• **Unrealised (est.):** `${unrealised_usd:,.2f}` "
        f"({_pct_str_from_baseline(float(unrealised_usd or 0.0), baseline_usd=baseline_usd, is_return=False)})\n"
    )
    msg += (
        f"• **Withdrawable (realised):** `${withdrawable_usd:,.2f}` "
        f"({_pct_str_from_baseline(float(withdrawable_usd or 0.0), baseline_usd=baseline_usd, is_return=True)})"
    )

    _send_discord_message(target=target, message=msg)


class LiveTrader(mei_alpha_v1.PaperTrader):
    """
    Live trader that reuses the same strategy logic as PaperTrader:
    - analyze() + check_exit_conditions() are shared with paper
    - entry/scale/exit sizing logic mirrors PaperTrader but execution is real orders

    IMPORTANT: This class does NOT simulate balances/fees. Source of truth is exchange account state.
    """

    def __init__(self, *, executor: HyperliquidLiveExecutor):
        self.executor = executor
        self._account_value_usd = 0.0
        self._withdrawable_usd = 0.0
        self._total_margin_used_usd = 0.0
        # Best-effort leverage cache to avoid redundant updateLeverage calls.
        self._last_leverage_set: dict[str, int] = {}
        # Per-loop entry budget (set by LivePlugin). None/unset means unlimited.
        self._entry_budget_remaining: int | None = None
        self._pending_context: dict[str, list[dict]] = {}
        # Track OPEN intents we sent but haven't seen in exchange state yet.
        # This prevents exceeding max_open_positions within a single decision loop without forcing REST syncs.
        self._pending_open_sent_at_s: dict[str, float] = {}
        self._pending_open_lock = threading.Lock()
        # PESC (post-exit cooldown) needs a real-time close marker because fills are only
        # persisted after we drain WS/REST events (which can lag the decision loop).
        self._last_full_close_sent_at_s: dict[str, float] = {}
        self._last_full_close_sent_type: dict[str, str] = {}
        self._last_full_close_sent_reason: dict[str, str] = {}
        # Entry/add attempts can be rejected (min notional, leverage tier, etc). Prevent tight-loop spam.
        self._last_entry_attempt_at_s: dict[str, float] = {}
        self._last_entry_fail_at_s: dict[str, float] = {}
        self._last_entry_fail_reason: dict[str, str] = {}
        # Exit attempts can also be rejected transiently; avoid close-spam when state is stale.
        self._last_exit_attempt_at_s: dict[str, float] = {}
        try:
            self._submit_unknown_reconcile_cooldown_s = min(
                float(os.getenv("AI_QUANT_LIVE_SUBMIT_UNKNOWN_RECONCILE_COOLDOWN_S", "5")),
                120.0,
            )
        except Exception:
            self._submit_unknown_reconcile_cooldown_s = 5.0
        self._last_submit_unknown_reconcile_s = 0.0
        self._live_balance_usd = 0.0
        super().__init__()

    @property
    def balance(self) -> float:
        """Override PaperTrader's kernel-backed balance with exchange withdrawable USD."""
        return self._live_balance_usd

    @balance.setter
    def balance(self, value: float) -> None:
        # Keep PaperTrader-facing balance assignment compatible for tests/tools.
        self._live_balance_usd = _safe_float(value, default=self._live_balance_usd)

    def _pending_open_ttl_s(self) -> float:
        try:
            return float(os.getenv("AI_QUANT_LIVE_PENDING_OPEN_TTL_S", "120"))
        except Exception:
            return 120.0

    def _prune_pending_opens(self) -> None:
        ttl = float(max(0.0, self._pending_open_ttl_s()))
        if ttl <= 0:
            return
        now_s = time.time()
        with self._pending_open_lock:
            for sym, ts in list((self._pending_open_sent_at_s or {}).items()):
                try:
                    if (now_s - float(ts)) >= ttl:
                        self._pending_open_sent_at_s.pop(sym, None)
                except Exception:
                    self._pending_open_sent_at_s.pop(sym, None)

    def _exit_cooldown_s(self) -> float:
        try:
            return float(os.getenv("AI_QUANT_LIVE_EXIT_COOLDOWN_S", "15"))
        except Exception:
            return 15.0

    def _can_attempt_exit(self, symbol: str) -> bool:
        sym = str(symbol or "").strip().upper()
        if not sym:
            return False
        now_s = time.time()
        last_try = _safe_float(self._last_exit_attempt_at_s.get(sym), 0.0)
        cooldown = max(0.0, self._exit_cooldown_s())
        if cooldown > 0 and (now_s - last_try) < cooldown:
            return False
        return True

    def load_state(self):
        # Replace the default DB-based paper reconstruction with a live exchange sync.
        self.positions = {}
        self.sync_from_exchange(force=True)

    def _reconcile_after_submit_unknown(self, *, symbol: str, action: str) -> None:
        """Best-effort reconciliation after ambiguous submit outcomes (timeout/transport errors)."""
        now_s = time.time()
        cooldown = max(0.0, float(self._submit_unknown_reconcile_cooldown_s or 0.0))
        if cooldown > 0 and (now_s - float(self._last_submit_unknown_reconcile_s or 0.0)) < cooldown:
            return
        self._last_submit_unknown_reconcile_s = now_s
        try:
            self.sync_from_exchange(force=True)
        except Exception:
            logger.warning(
                "post-timeout reconciliation failed for %s %s",
                action,
                symbol,
                exc_info=True,
            )

    def sync_from_exchange(self, *, force: bool = False) -> None:
        snap = self.executor.account_snapshot(force=force)
        self._account_value_usd = float(snap.account_value_usd)
        self._withdrawable_usd = float(snap.withdrawable_usd)
        try:
            self._total_margin_used_usd = float(snap.total_margin_used_usd)
        except Exception:
            self._total_margin_used_usd = float(self._total_margin_used_usd or 0.0)
        # In live mode, balance is sourced from the exchange, not the Rust kernel.
        # PaperTrader.balance is a read-only @property (AQC-755), so we store
        # the exchange value in _live_balance_usd and override the property below.
        self._live_balance_usd = self._withdrawable_usd

        live_positions = self.executor.get_positions(force=force)
        old_positions = dict(self.positions or {})

        now_ms = int(time.time() * 1000)
        now_iso = utc_iso()

        # For live, we allow strategy state persistence via `position_state`, but do not require open_trade_id matching.
        # Also: we must recover entry_atr for exits, since the exchange doesn't provide it and fills may be ingested
        # before positions are synced into memory (common on fast fills).
        db_conn = None
        db_cur = None
        try:
            db_conn = sqlite3.connect(mei_alpha_v1.DB_PATH, timeout=_DB_TIMEOUT_S)
            _configure_live_db_connection(db_conn)
            db_cur = db_conn.cursor()
        except sqlite3.Error as exc:
            logger.warning(
                "sync_from_exchange: position_state DB unavailable, continuing without state recovery: %s", exc
            )
            db_cur = None
            if db_conn is not None:
                try:
                    db_conn.close()
                except sqlite3.Error as close_exc:
                    logger.debug(
                        "sync_from_exchange: failed to close DB after setup error: %s", close_exc, exc_info=True
                    )
                finally:
                    db_conn = None

        def load_pos_state(symbol: str) -> dict:
            if db_cur is None:
                return {}
            try:
                db_cur.execute(
                    """
                    SELECT open_trade_id, trailing_sl, last_funding_time, adds_count, tp1_taken, last_add_time, entry_adx_threshold
                    FROM position_state
                    WHERE symbol = ?
                    """,
                    (symbol,),
                )
                row = db_cur.fetchone()
            except (sqlite3.Error, OSError) as exc:
                logger.debug("load_pos_state(%s): DB read failed: %s", symbol, exc, exc_info=True)
                row = None
            if not row:
                return {}
            return {
                "open_trade_id": row[0],
                "trailing_sl": row[1],
                "last_funding_time": row[2],
                "adds_count": row[3],
                "tp1_taken": row[4],
                "last_add_time": row[5],
                "entry_adx_threshold": float(row[6] or 0) if len(row) > 6 else 0.0,
            }

        def load_last_entry_atr(symbol: str) -> float | None:
            if db_cur is None:
                return None
            try:
                db_cur.execute(
                    """
                    SELECT entry_atr
                    FROM trades
                    WHERE symbol = ?
                      AND action IN ('OPEN', 'ADD')
                      AND entry_atr IS NOT NULL
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (symbol,),
                )
                row = db_cur.fetchone()
            except Exception:
                row = None
            if not row or row[0] is None:
                return None
            try:
                v = float(row[0])
            except Exception:
                return None
            return v if v > 0 else None

        try:
            new_positions: dict[str, dict] = {}
            for sym, lp in live_positions.items():
                prev = old_positions.get(sym) or {}
                st = load_pos_state(sym)

                # Crash recovery warning: if no in-memory state exists (cold start) and
                # DB position_state has trailing_sl / adds_count, log it for visibility.
                if not prev and st:
                    _db_tsl = st.get("trailing_sl")
                    _db_adds = st.get("adds_count")
                    if _db_tsl is not None or (_db_adds is not None and int(_db_adds or 0) > 0):
                        print(
                            f"⚠️ [{sym}] crash recovery: restoring trailing_sl={_db_tsl}, "
                            f"adds_count={_db_adds} from position_state DB"
                        )

                entry_atr = _safe_float(prev.get("entry_atr"), 0.0)
                if entry_atr <= 0:
                    entry_atr2 = load_last_entry_atr(sym)
                    if entry_atr2 is not None and entry_atr2 > 0:
                        entry_atr = float(entry_atr2)

                new_positions[sym] = {
                    "open_trade_id": prev.get("open_trade_id") or st.get("open_trade_id"),
                    "open_timestamp": prev.get("open_timestamp") or now_iso,
                    "type": lp.get("type") or prev.get("type"),
                    "entry_price": float(lp.get("entry_price") or prev.get("entry_price") or 0.0),
                    "size": float(lp.get("size") or prev.get("size") or 0.0),
                    "confidence": prev.get("confidence") or "N/A",
                    "entry_atr": float(entry_atr),
                    "entry_adx_threshold": float(prev.get("entry_adx_threshold") or st.get("entry_adx_threshold") or 0),
                    "trailing_sl": prev.get("trailing_sl")
                    if prev.get("trailing_sl") is not None
                    else st.get("trailing_sl"),
                    "last_funding_time": int(prev.get("last_funding_time") or st.get("last_funding_time") or now_ms),
                    "leverage": float(lp.get("leverage") or prev.get("leverage") or 1.0),
                    "margin_used": float(lp.get("margin_used") or prev.get("margin_used") or 0.0),
                    "adds_count": int(prev.get("adds_count") or st.get("adds_count") or 0),
                    "tp1_taken": int(prev.get("tp1_taken") or st.get("tp1_taken") or 0),
                    "last_add_time": int(prev.get("last_add_time") or st.get("last_add_time") or 0),
                }
        finally:
            try:
                if db_conn is not None:
                    db_conn.close()
            except Exception as e:
                logger.debug("failed to close db connection: %s", e, exc_info=True)

        self.positions = new_positions
        # Clear pending OPEN intents once we see the position in exchange state.
        try:
            self._prune_pending_opens()
            with self._pending_open_lock:
                for sym in list((self._pending_open_sent_at_s or {}).keys()):
                    if sym in self.positions:
                        self._pending_open_sent_at_s.pop(sym, None)
        except Exception as e:
            logger.warning("failed to prune pending opens: %s", e, exc_info=True)
        # Refresh leverage cache from exchange state (open positions only).
        try:
            for sym, p in (self.positions or {}).items():
                try:
                    lev_i = int(round(float((p or {}).get("leverage") or 1.0)))
                except Exception:
                    lev_i = 1
                self._last_leverage_set[str(sym).upper()] = max(1, lev_i)
        except Exception as e:
            logger.warning("failed to refresh leverage cache from exchange state: %s", e, exc_info=True)
        for sym in self.positions.keys():
            try:
                self.upsert_position_state(sym)
            except Exception as e:
                logger.warning("failed to upsert position state for %s: %s", sym, e, exc_info=True)
        # Reconcile position_state: delete any rows not in current open positions.
        # Self-healing: if a previous clear failed, the next loop fixes it.
        try:
            self._reconcile_position_state(set(self.positions.keys()))
        except Exception as e:
            logger.warning("failed to reconcile position state: %s", e, exc_info=True)

    def get_live_balance(self):
        # In live mode, "equity" is exchange accountValue. Avoid REST calls in hot paths:
        # `LivePlugin.before_iteration()` syncs periodically and after fills.
        try:
            return float(self._account_value_usd or self.balance or 0.0)
        except Exception:
            return 0.0

    def upsert_position_state(self, symbol):
        """Live override: position_state is observability/persistence only; never stall on sqlite locks."""
        pos = (self.positions or {}).get(symbol)
        if not pos:
            return
        try:
            timeout_s = float(
                os.getenv("AI_QUANT_POSITION_STATE_DB_TIMEOUT_S", os.getenv("AI_QUANT_AUDIT_DB_TIMEOUT_S", "0.2"))
            )
        except Exception:
            timeout_s = 0.2
        timeout_s = float(max(0.01, min(2.0, timeout_s)))

        conn = None
        try:
            conn = sqlite3.connect(mei_alpha_v1.DB_PATH, timeout=timeout_s)
            _configure_live_db_connection(conn)
            cur = conn.cursor()
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            now_iso = now_dt.isoformat()
            now_ms = int(now_dt.timestamp() * 1000)
            sym = str(symbol).strip().upper()
            history_ready = _ensure_position_state_history_table(cur)
            cur.execute(
                """
                INSERT INTO position_state (
                    symbol, open_trade_id, trailing_sl, last_funding_time, adds_count, tp1_taken, last_add_time, entry_adx_threshold, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    open_trade_id = excluded.open_trade_id,
                    trailing_sl = excluded.trailing_sl,
                    last_funding_time = excluded.last_funding_time,
                    adds_count = excluded.adds_count,
                    tp1_taken = excluded.tp1_taken,
                    last_add_time = excluded.last_add_time,
                    entry_adx_threshold = excluded.entry_adx_threshold,
                    updated_at = excluded.updated_at
                """,
                (
                    sym,
                    pos.get("open_trade_id"),
                    pos.get("trailing_sl"),
                    pos.get("last_funding_time"),
                    pos.get("adds_count"),
                    pos.get("tp1_taken"),
                    pos.get("last_add_time"),
                    pos.get("entry_adx_threshold"),
                    now_iso,
                ),
            )
            if history_ready:
                cur.execute(
                    """
                    INSERT INTO position_state_history (
                        event_ts_ms, updated_at, symbol, open_trade_id, trailing_sl,
                        last_funding_time, adds_count, tp1_taken, last_add_time, entry_adx_threshold,
                        event_type, run_fingerprint
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        now_ms,
                        now_iso,
                        sym,
                        pos.get("open_trade_id"),
                        pos.get("trailing_sl"),
                        pos.get("last_funding_time"),
                        pos.get("adds_count"),
                        1 if bool(pos.get("tp1_taken")) else 0,
                        pos.get("last_add_time"),
                        pos.get("entry_adx_threshold"),
                        "upsert",
                        _current_run_fingerprint(),
                    ),
                )
            conn.commit()
        except sqlite3.Error as exc:
            if "locked" not in str(exc).lower():
                logger.warning("upsert_position_state failed for %s: %s", symbol, exc)
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception as e:
                logger.debug("failed to close sqlite connection: %s", e, exc_info=True)

    def clear_position_state(self, symbol):
        try:
            timeout_s = float(
                os.getenv("AI_QUANT_POSITION_STATE_DB_TIMEOUT_S", os.getenv("AI_QUANT_AUDIT_DB_TIMEOUT_S", "0.2"))
            )
        except Exception:
            timeout_s = 0.2
        timeout_s = float(max(0.01, min(2.0, timeout_s)))

        conn = None
        try:
            conn = sqlite3.connect(mei_alpha_v1.DB_PATH, timeout=timeout_s)
            _configure_live_db_connection(conn)
            cur = conn.cursor()
            history_ready = _ensure_position_state_history_table(cur)
            sym = str(symbol).strip().upper()
            row = cur.execute(
                """
                SELECT open_trade_id, trailing_sl, last_funding_time, adds_count, tp1_taken, last_add_time, entry_adx_threshold
                FROM position_state
                WHERE symbol = ?
                LIMIT 1
                """,
                (sym,),
            ).fetchone()
            if row:
                now_dt = datetime.datetime.now(datetime.timezone.utc)
                now_iso = now_dt.isoformat()
                now_ms = int(now_dt.timestamp() * 1000)
                if history_ready:
                    cur.execute(
                        """
                        INSERT INTO position_state_history (
                            event_ts_ms, updated_at, symbol, open_trade_id, trailing_sl,
                            last_funding_time, adds_count, tp1_taken, last_add_time, entry_adx_threshold,
                            event_type, run_fingerprint
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            now_ms,
                            now_iso,
                            sym,
                            row[0],
                            row[1],
                            row[2],
                            row[3],
                            row[4],
                            row[5],
                            row[6],
                            "clear",
                            _current_run_fingerprint(),
                        ),
                    )
            cur.execute("DELETE FROM position_state WHERE symbol = ?", (sym,))
            conn.commit()
        except sqlite3.Error as exc:
            if "locked" not in str(exc).lower():
                logger.warning("clear_position_state failed for %s: %s", symbol, exc)
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception as e:
                logger.debug("failed to close sqlite connection: %s", e, exc_info=True)

    def _reconcile_position_state(self, open_symbols: set):
        """Delete position_state rows for symbols NOT currently open on exchange.

        Idempotent & self-healing: runs every sync loop so a single failure
        doesn't leave stale rows forever (unlike the old transition-based clear).
        """
        try:
            timeout_s = float(
                os.getenv("AI_QUANT_POSITION_STATE_DB_TIMEOUT_S", os.getenv("AI_QUANT_AUDIT_DB_TIMEOUT_S", "0.2"))
            )
        except Exception:
            timeout_s = 0.2
        timeout_s = float(max(0.01, min(2.0, timeout_s)))

        conn = None
        try:
            conn = sqlite3.connect(mei_alpha_v1.DB_PATH, timeout=timeout_s)
            _configure_live_db_connection(conn)
            cur = conn.cursor()
            history_ready = _ensure_position_state_history_table(cur)
            if open_symbols:
                sym_list = [s.strip().upper() for s in open_symbols]
                # Safety: `placeholders` contains only '?' chars — no user input in SQL structure.
                placeholders = ",".join("?" for _ in open_symbols)
                stale_rows = cur.execute(
                    f"""
                    SELECT symbol, open_trade_id, trailing_sl, last_funding_time, adds_count, tp1_taken, last_add_time, entry_adx_threshold
                    FROM position_state
                    WHERE symbol NOT IN ({placeholders})
                    """,
                    sym_list,
                ).fetchall()
                if stale_rows:
                    now_dt = datetime.datetime.now(datetime.timezone.utc)
                    now_iso = now_dt.isoformat()
                    now_ms = int(now_dt.timestamp() * 1000)
                    if history_ready:
                        cur.executemany(
                            """
                            INSERT INTO position_state_history (
                                event_ts_ms, updated_at, symbol, open_trade_id, trailing_sl,
                                last_funding_time, adds_count, tp1_taken, last_add_time, entry_adx_threshold,
                                event_type, run_fingerprint
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            [
                                (
                                    now_ms,
                                    now_iso,
                                    str(r[0]).strip().upper(),
                                    r[1],
                                    r[2],
                                    r[3],
                                    r[4],
                                    r[5],
                                    r[6],
                                    r[7],
                                    "reconcile_clear",
                                    _current_run_fingerprint(),
                                )
                                for r in stale_rows
                            ],
                        )
                cur.execute(
                    f"DELETE FROM position_state WHERE symbol NOT IN ({placeholders})",
                    sym_list,
                )
            else:
                stale_rows = cur.execute(
                    """
                    SELECT symbol, open_trade_id, trailing_sl, last_funding_time, adds_count, tp1_taken, last_add_time, entry_adx_threshold
                    FROM position_state
                    """
                ).fetchall()
                if stale_rows:
                    now_dt = datetime.datetime.now(datetime.timezone.utc)
                    now_iso = now_dt.isoformat()
                    now_ms = int(now_dt.timestamp() * 1000)
                    if history_ready:
                        cur.executemany(
                            """
                            INSERT INTO position_state_history (
                                event_ts_ms, updated_at, symbol, open_trade_id, trailing_sl,
                                last_funding_time, adds_count, tp1_taken, last_add_time, entry_adx_threshold,
                                event_type, run_fingerprint
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            [
                                (
                                    now_ms,
                                    now_iso,
                                    str(r[0]).strip().upper(),
                                    r[1],
                                    r[2],
                                    r[3],
                                    r[4],
                                    r[5],
                                    r[6],
                                    r[7],
                                    "reconcile_clear_all",
                                    _current_run_fingerprint(),
                                )
                                for r in stale_rows
                            ],
                        )
                cur.execute("DELETE FROM position_state")
            conn.commit()
        except sqlite3.Error as exc:
            if "locked" not in str(exc).lower():
                logger.warning("reconcile_position_state failed: %s", exc)
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception as e:
                logger.debug("failed to close sqlite connection: %s", e, exc_info=True)

    def _estimate_margin_used(self, symbol: str, pos: dict, *, mark_price: float | None = None) -> float:
        """Live override: warns when WS price is stale and entry price fallback is used."""
        try:
            lev = float(pos.get("leverage") or 1.0)
        except Exception:
            lev = 1.0
        if lev <= 0:
            lev = 1.0

        try:
            sz = float(pos.get("size") or 0.0)
        except Exception:
            sz = 0.0
        if sz <= 0:
            return 0.0

        px = None
        mid_age_s = None
        ws_disconnect_age_s = None
        if mark_price is not None:
            px = mark_price
        else:
            mid = hyperliquid_ws.hl_ws.get_mid(symbol, max_age_s=10.0)
            if mid is not None:
                px = float(mid)
            else:
                try:
                    mid_age_s = hyperliquid_ws.hl_ws.get_mid_age_s(symbol)
                except Exception:
                    mid_age_s = None
                try:
                    ws_disconnect_age_s = hyperliquid_ws.hl_ws.get_ws_disconnect_age_s()
                except Exception:
                    ws_disconnect_age_s = None
                bbo = hyperliquid_ws.hl_ws.get_bbo(symbol, max_age_s=15.0)
                if bbo is not None:
                    bid, ask = bbo
                    if bid > 0 and ask > 0:
                        px = (bid + ask) / 2.0
        if px is None:
            entry_price = 0.0
            try:
                entry_price = float(pos.get("entry_price") or 0.0)
            except Exception:
                entry_price = 0.0
            if mid_age_s is None:
                logger.warning("[%s] margin estimate using entry price (WS mid unavailable)", symbol)
            elif ws_disconnect_age_s is None:
                logger.warning(
                    "[%s] margin estimate using entry price (WS mid stale age=%.1fs)",
                    symbol,
                    float(mid_age_s),
                )
            else:
                logger.warning(
                    "[%s] margin estimate using entry price (WS mid stale age=%.1fs, ws_disconnect_age=%.1fs)",
                    symbol,
                    float(mid_age_s),
                    float(ws_disconnect_age_s),
                )
            px = entry_price

        if px <= 0:
            return 0.0
        return abs(sz) * float(px) / lev

    def _push_pending(self, symbol: str, ctx: dict) -> None:
        sym = str(symbol or "").strip().upper()
        if not sym:
            return
        item = dict(ctx or {})
        item["_created_at_s"] = time.time()
        self._pending_context.setdefault(sym, []).append(item)

    def pop_pending(self, symbol: str) -> dict | None:
        sym = str(symbol or "").strip().upper()
        if not sym:
            return None
        q = self._pending_context.get(sym) or []
        if not q:
            return None
        try:
            ttl_s = float(os.getenv("AI_QUANT_LIVE_PENDING_CTX_TTL_S", "600"))
        except Exception:
            ttl_s = 600.0
        now_s = time.time()
        # Drop stale pending contexts (e.g., IOC order placed but no fill).
        while q:
            try:
                ctx = q[0]
            except Exception:
                break
            raw_created = ctx.get("_created_at_s")
            created = _safe_float(raw_created, -1.0)
            has_created = raw_created is not None
            is_stale = False
            if has_created and created < 0.0:
                is_stale = True
            elif created >= 0.0 and ttl_s > 0 and (now_s - float(created)) > ttl_s:
                is_stale = True
            if is_stale:
                try:
                    q.pop(0)
                except Exception:
                    break
                continue
            break
        try:
            return q.pop(0)
        except Exception:
            return None

    def _entry_cooldown_s(self) -> float:
        try:
            return float(os.getenv("AI_QUANT_LIVE_ENTRY_COOLDOWN_S", "20"))
        except Exception:
            return 20.0

    def _entry_fail_backoff_s(self) -> float:
        try:
            return float(os.getenv("AI_QUANT_LIVE_ENTRY_FAIL_BACKOFF_S", "120"))
        except Exception:
            return 120.0

    def _can_attempt_entry(self, symbol: str) -> bool:
        sym = str(symbol or "").strip().upper()
        if not sym:
            return False
        now_s = time.time()

        last_try = _safe_float(self._last_entry_attempt_at_s.get(sym), 0.0)
        cooldown = max(0.0, self._entry_cooldown_s())
        if cooldown > 0 and (now_s - last_try) < cooldown:
            return False

        last_fail = _safe_float(self._last_entry_fail_at_s.get(sym), 0.0)
        backoff = max(0.0, self._entry_fail_backoff_s())
        if backoff > 0 and (now_s - last_fail) < backoff:
            return False

        return True

    def _note_entry_attempt(self, symbol: str) -> None:
        sym = str(symbol or "").strip().upper()
        if not sym:
            return
        self._last_entry_attempt_at_s[sym] = time.time()

    def _note_entry_fail(self, symbol: str, reason: str) -> None:
        sym = str(symbol or "").strip().upper()
        if not sym:
            return
        self._last_entry_fail_at_s[sym] = time.time()
        self._last_entry_fail_reason[sym] = str(reason or "unknown")

    def _min_notional_usd(self, symbol: str) -> float:
        trade_cfg = self._live_trade_cfg(symbol)
        try:
            return float(trade_cfg.get("min_notional_usd", 10.0))
        except Exception:
            return 10.0

    def _size_bounds_for_notional(
        self,
        symbol: str,
        *,
        price: float,
        desired_notional: float,
        min_notional: float,
        max_notional: float | None,
    ) -> float:
        """
        Computes an order size that:
        - is rounded to szDecimals
        - is >= min_notional (by notional, after rounding)
        - is <= max_notional (if provided)
        Preference: stay close to desired_notional without violating constraints.
        """
        sym = str(symbol or "").strip().upper()
        if not sym:
            return 0.0
        if price <= 0:
            return 0.0

        # Minimum size to satisfy min_notional.
        min_sz = hyperliquid_meta.min_size_for_notional(sym, min_notional, price)
        if min_sz <= 0:
            return 0.0

        max_ntl = None if max_notional is None else float(max_notional)
        if max_ntl is not None and max_ntl > 0:
            # Largest size that stays <= max_notional.
            max_sz = hyperliquid_meta.round_size(sym, max_ntl / price)
            if max_sz <= 0 or min_sz - max_sz > 1e-12:
                return 0.0

            target_sz = hyperliquid_meta.round_size(sym, float(desired_notional) / price)
            sz = max(min_sz, min(target_sz, max_sz))
            return float(sz)

        target_sz = hyperliquid_meta.round_size(sym, float(desired_notional) / price)
        return float(max(min_sz, target_sz))

    def _live_slippage_pct(self) -> float:
        try:
            return float(os.getenv("HL_LIVE_MARKET_SLIPPAGE_PCT", "0.01"))
        except Exception:
            return 0.01

    def _live_trade_cfg(self, symbol: str) -> dict:
        trade_cfg = dict((mei_alpha_v1.get_strategy_config(symbol).get("trade") or {}))
        mode = live_mode()
        # Safe live defaults (override via YAML `live:` or env vars).
        if mode in {"live", "dry_live"}:
            if "max_open_positions" not in trade_cfg:
                try:
                    trade_cfg["max_open_positions"] = min(
                        int(os.getenv("AI_QUANT_LIVE_MAX_OPEN_POSITIONS", "1")),
                        100,
                    )
                except Exception:
                    trade_cfg["max_open_positions"] = 1
            if "max_notional_usd_per_order" not in trade_cfg:
                try:
                    trade_cfg["max_notional_usd_per_order"] = min(
                        float(os.getenv("AI_QUANT_LIVE_MAX_NOTIONAL_USD_PER_ORDER", "15.0")),
                        1_000_000.0,
                    )
                except Exception:
                    trade_cfg["max_notional_usd_per_order"] = 15.0
            if "min_margin_usd" not in trade_cfg:
                try:
                    trade_cfg["min_margin_usd"] = min(
                        float(os.getenv("AI_QUANT_LIVE_MIN_MARGIN_USD", "6.0")),
                        100_000.0,
                    )
                except Exception:
                    trade_cfg["min_margin_usd"] = 6.0
        return trade_cfg

    def _can_send_orders(self) -> bool:
        mode = live_mode()
        if mode == "dry_live":
            return False
        return live_orders_enabled()

    def _can_send_entries(self) -> bool:
        mode = live_mode()
        if mode == "dry_live":
            return False
        return live_entries_enabled()

    def add_to_position(
        self,
        symbol,
        price,
        timestamp,
        confidence,
        *,
        atr=0.0,
        indicators=None,
        target_size: float | None = None,
        reason: str | None = None,
    ) -> bool:
        sym = str(symbol or "").strip().upper()
        if sym not in (self.positions or {}):
            return False

        if not self._can_send_entries():
            return False
        if not self._can_attempt_entry(sym):
            return False

        pos = self.positions[sym]
        pos_type = str(pos.get("type") or "").upper()
        if pos_type not in {"LONG", "SHORT"}:
            return False

        cfg = mei_alpha_v1.get_strategy_config(sym)
        trade_cfg = self._live_trade_cfg(sym)
        thr = cfg.get("thresholds") or {}

        if not bool(trade_cfg.get("enable_pyramiding", True)):
            return False

        adds_count = int(pos.get("adds_count") or 0)
        try:
            max_adds = int(trade_cfg.get("max_adds_per_symbol", 2))
        except Exception:
            max_adds = 2
        if adds_count >= max(0, max_adds):
            return False

        min_conf = str(trade_cfg.get("add_min_confidence", "medium"))
        if not mei_alpha_v1._conf_ok(confidence, min_confidence=min_conf):
            return False

        now_ms = int(time.time() * 1000)
        cooldown_m = float(trade_cfg.get("add_cooldown_minutes", 60))
        last_add_time = int(pos.get("last_add_time") or 0)
        if last_add_time > 0 and cooldown_m > 0 and (now_ms - last_add_time) < (cooldown_m * 60_000):
            return False

        # v5.007: 分批止盈後的加倉禁令 (PPEB) — align with PaperTrader.
        if int(pos.get("tp1_taken") or 0) > 0:
            return False

        entry = float(pos.get("entry_price") or 0.0)
        if entry <= 0:
            return False

        current_atr = float(indicators.get("ATR", atr) or atr or 0.0) if indicators is not None else float(atr or 0.0)
        if current_atr <= 0:
            current_atr = float(pos.get("entry_atr") or 0.0) or (entry * 0.005)
        if current_atr <= 0:
            return False

        mid = hyperliquid_ws.hl_ws.get_mid(sym, max_age_s=10.0)
        mark = float(mid) if mid is not None else float(price)

        min_profit_atr = float(trade_cfg.get("add_min_profit_atr", 0.5))

        # v5.008: 加倉距離止損過濾 (PSPF) — align with PaperTrader.
        sl_price = float(pos.get("trailing_sl") or 0.0)
        if sl_price <= 0:
            sl_mult = float(trade_cfg.get("sl_atr_mult", 1.5))
            sl_price = entry - (current_atr * sl_mult) if pos_type == "LONG" else entry + (current_atr * sl_mult)
        dist_to_sl_atr = abs(mark - sl_price) / current_atr if current_atr > 0 else 0.0
        if dist_to_sl_atr < 0.5:
            return False

        # v5.009: 加倉動量過濾 (PMF) — only add while momentum is still expanding in our direction.
        momentum_expanding = None
        if indicators is not None:
            try:
                macd_h = float(indicators.get("MACD_hist", 0) or 0.0)
            except Exception:
                macd_h = 0.0
            try:
                prev_macd_h = float(indicators.get("prev_MACD_hist", 0) or 0.0)
            except Exception:
                prev_macd_h = 0.0
            momentum_expanding = (pos_type == "LONG" and macd_h > prev_macd_h) or (
                pos_type == "SHORT" and macd_h < prev_macd_h
            )
            if not momentum_expanding:
                return False

        # v5.005/v5.006: DPS + PVF — if trend accelerates but vol isn't expanding, allow earlier adds.
        if indicators is not None:
            try:
                adx_slope = float(indicators.get("ADX_slope", 0) or 0.0)
            except Exception:
                adx_slope = 0.0
            if adx_slope > 0.75:
                try:
                    atr_slope = float(indicators.get("ATR_slope", 0) or 0.0)
                except Exception:
                    atr_slope = 0.0
                if atr_slope <= 0:
                    min_profit_atr *= 0.5

        profit_atr = (mark - entry) / current_atr if pos_type == "LONG" else (entry - mark) / current_atr
        if profit_atr < min_profit_atr:
            return False

        equity_base = _safe_float(self.get_live_balance(), self.balance) or self.balance

        allocation_pct = float(trade_cfg.get("allocation_pct", mei_alpha_v1.ALLOCATION_PCT))
        add_frac = float(trade_cfg.get("add_fraction_of_base_margin", 0.5))
        add_frac = max(0.0, min(2.0, add_frac))

        leverage = float(pos.get("leverage") or trade_cfg.get("leverage") or mei_alpha_v1.HL_DEFAULT_LEVERAGE)
        leverage = max(1.0, leverage)

        base_margin = equity_base * allocation_pct
        margin_target = base_margin * add_frac

        # Apply dynamic sizing scalars consistent with PaperTrader.
        if bool(trade_cfg.get("enable_dynamic_sizing", True)):
            conf_s = str(confidence or "").strip().lower()
            if conf_s.startswith("h"):
                conf_mult = float(trade_cfg.get("confidence_mult_high", 1.0))
            elif conf_s.startswith("m"):
                conf_mult = float(trade_cfg.get("confidence_mult_medium", 0.7))
            else:
                conf_mult = float(trade_cfg.get("confidence_mult_low", 0.5))
            margin_target *= max(0.0, conf_mult)

            adx_val = _safe_float(indicators.get("ADX"), None) if indicators is not None else None
            min_adx = _safe_float(((thr.get("entry") or {}).get("min_adx")), 0.0) or 0.0
            full_adx = float(trade_cfg.get("adx_sizing_full_adx", 40.0))
            min_mult = float(trade_cfg.get("adx_sizing_min_mult", 0.6))
            if adx_val is not None and full_adx > min_adx:
                t = (float(adx_val) - float(min_adx)) / (float(full_adx) - float(min_adx))
                t = max(0.0, min(1.0, t))
                adx_mult = min_mult + t * (1.0 - min_mult)
                margin_target *= max(0.0, adx_mult)

        if current_atr > 0:
            baseline_vol = float(price) * float(trade_cfg.get("vol_baseline_pct", 0.01))
            vol_scalar = baseline_vol / float(current_atr)
            vol_min = float(trade_cfg.get("vol_scalar_min", 0.5))
            vol_max = float(trade_cfg.get("vol_scalar_max", 1.0))
            vol_scalar = max(vol_min, min(vol_max, vol_scalar))
            margin_target *= max(0.0, vol_scalar)

        # Optional size multiplier (used for live rollout ramps, etc).
        try:
            size_mult = float(trade_cfg.get("size_multiplier", 1.0))
        except Exception:
            size_mult = 1.0
        size_mult = max(0.0, float(size_mult))
        margin_target *= float(size_mult)

        # Live-specific clamps
        min_margin_usd = _safe_float(trade_cfg.get("min_margin_usd"), 0.0)
        if min_margin_usd > 0:
            margin_target = max(margin_target, min_margin_usd)

        min_notional = float(self._min_notional_usd(sym))
        max_notional = _safe_float(trade_cfg.get("max_notional_usd_per_order"), 0.0)
        if max_notional > 0 and max_notional < min_notional:
            return False

        try:
            explicit_notional = float(target_size) if target_size is not None else None
        except Exception:
            explicit_notional = None

        desired_notional = margin_target * leverage
        if explicit_notional is not None and explicit_notional > 0:
            desired_notional = explicit_notional

        # Boost small adds up to the minimum notional (if within max_notional).
        if desired_notional < min_notional:
            desired_notional = min_notional
        if max_notional > 0 and desired_notional > max_notional:
            desired_notional = max_notional
        if desired_notional < min_notional:
            return False

        approx_total_notional = (abs(float(pos.get("size") or 0.0)) * mark) + desired_notional
        max_lev = hyperliquid_meta.max_leverage(sym, approx_total_notional)
        if max_lev is not None and leverage > float(max_lev):
            return False

        side = "BUY" if pos_type == "LONG" else "SELL"
        fill_price_est = mei_alpha_v1._get_fill_price(
            sym,
            side,
            float(price),
            slippage_bps=float(trade_cfg.get("slippage_bps", mei_alpha_v1.HL_SLIPPAGE_BPS)),
            use_bbo_for_fills=bool(trade_cfg.get("use_bbo_for_fills", True)),
        )
        add_size = self._size_bounds_for_notional(
            sym,
            price=fill_price_est,
            desired_notional=desired_notional,
            min_notional=min_notional,
            max_notional=max_notional if max_notional > 0 else None,
        )
        if add_size <= 0:
            return False

        notional = abs(add_size) * fill_price_est
        if notional < min_notional:
            return False

        # Margin checks (wallet availability + global cap) based on the actual rounded order notional.
        # Avoid REST calls in the hot path: `sync_from_exchange()` updates these periodically and after fills.
        try:
            available_margin = max(0.0, float(self._account_value_usd) - float(self._total_margin_used_usd))
        except Exception:
            available_margin = 0.0
        if available_margin <= 0:
            available_margin = max(0.0, float(equity_base or 0.0))

        margin_add = (notional / leverage) if leverage > 0 else notional
        if margin_add > available_margin:
            return False

        max_total_margin_pct = float(trade_cfg.get("max_total_margin_pct", 0.60))
        # Prefer exchange-reported total margin when available (more accurate than estimate).
        exchange_margin = _safe_float(getattr(self, "_total_margin_used_usd", None), 0.0)
        if exchange_margin > 0:
            current_margin = exchange_margin
        else:
            current_margin = 0.0
            for s, p in (self.positions or {}).items():
                current_margin += self._estimate_margin_used(s, p)
        if (current_margin + margin_add) > (equity_base * max_total_margin_pct):
            return False

        audit_for_oms = None
        if indicators is not None:
            try:
                audit_for_oms = indicators.get("audit")
            except Exception:
                audit_for_oms = None
        kernel_reason_code = ""
        try:
            kernel_reason_code = str(
                (indicators if indicators is not None else {}).get("_kernel_reason_code") or ""
            ).strip().lower()
        except Exception:
            kernel_reason_code = ""

        _add_reason = str(reason or "Pyramid Add")
        oms = getattr(self, "oms", None)
        oms_intent = None
        order_meta = {
            "kind": "ADD",
            "confidence": str(confidence or "").lower(),
            "px_est": float(fill_price_est),
            "size": float(add_size),
            "notional_est": float(notional),
            "leverage": float(leverage),
            "margin_est": float((notional / leverage) if leverage > 0 else 0.0),
            "adds_count_before": int(adds_count),
            "adds_count_after": int(adds_count + 1),
            "max_adds_per_symbol": int(max_adds),
            "profit_atr": float(profit_atr),
            "min_profit_atr": float(min_profit_atr),
            "dist_to_sl_atr": float(dist_to_sl_atr),
            "momentum_expanding": None if momentum_expanding is None else bool(momentum_expanding),
        }
        if oms is not None:
            try:
                add_meta = {
                    "audit": audit_for_oms if isinstance(audit_for_oms, dict) else None,
                    "order": order_meta,
                }
                if kernel_reason_code:
                    add_meta["reason_code"] = kernel_reason_code
                oms_intent = oms.create_intent(
                    symbol=sym,
                    action="ADD",
                    side=side,
                    requested_size=float(add_size),
                    requested_notional=float(notional),
                    leverage=float(leverage),
                    decision_ts=timestamp,
                    reason=_add_reason,
                    confidence=str(confidence or ""),
                    entry_atr=float(current_atr or 0.0),
                    meta=add_meta,
                    dedupe_open=False,
                )
            except Exception as _oms_exc:
                logger.debug("OMS create_intent failed for ADD %s: %s", sym, _oms_exc, exc_info=True)
                oms_intent = None

        if oms is not None and oms_intent is None and _env_bool("AI_QUANT_OMS_REQUIRE_INTENT_FOR_ENTRY", True):
            # Fail-closed for entry orders if we cannot create an OMS intent (prevents untracked duplicates).
            self._note_entry_fail(sym, "oms_intent_create_failed")
            mei_alpha_v1.log_audit_event(
                sym,
                "OMS_INTENT_CREATE_FAILED",
                level="warn",
                data={
                    "kind": "ADD",
                    "confidence": str(confidence or "").lower(),
                    "px_est": float(fill_price_est),
                    "size": float(add_size),
                    "notional_est": float(notional),
                    "leverage": float(leverage),
                },
            )
            return False

        # Risk guardrails (kill-switch + rate limits). Best-effort.
        risk = getattr(self, "risk", None)
        if risk is not None:
            try:
                dec = risk.allow_order(
                    symbol=sym,
                    action="ADD",
                    side=side,
                    notional_usd=float(notional),
                    leverage=float(leverage),
                    equity_usd=float(equity_base or 0.0),
                    entry_price=float(fill_price_est),
                    entry_atr=float(current_atr or 0.0),
                    sl_atr_mult=float(trade_cfg.get("sl_atr_mult", 1.5)),
                    positions=getattr(self, "positions", None),
                    intent_id=getattr(oms_intent, "intent_id", None),
                    reduce_risk=False,
                )
                if not getattr(dec, "allowed", False):
                    why = str(getattr(dec, "reason", "risk_block"))
                    self._note_entry_fail(sym, f"risk blocked: {why}")
                    if oms_intent is not None and oms is not None:
                        try:
                            oms.mark_failed(oms_intent, error=f"risk blocked: {why}")
                        except Exception as e:
                            logger.debug("failed to mark oms intent as risk-blocked: %s", e, exc_info=True)
                    mei_alpha_v1.log_audit_event(
                        sym,
                        "LIVE_ORDER_BLOCKED_RISK",
                        level="warn",
                        data={
                            "kind": "ADD",
                            "confidence": str(confidence or "").lower(),
                            "notional_est": float(notional),
                            "leverage": float(leverage),
                            "reason": str(why),
                            "oms_intent_id": getattr(oms_intent, "intent_id", None) if oms_intent is not None else None,
                        },
                    )
                    return False
            except Exception:
                logger.error("risk.allow_order() raised for ADD %s, BLOCKING order as fail-closed", sym, exc_info=True)
                return False

        # Per-loop entry budget (OPEN/ADD): prevent burst order submits from stalling the loop.
        try:
            bud = getattr(self, "_entry_budget_remaining", None)
            if bud is not None and int(bud) <= 0:
                mei_alpha_v1.log_audit_event(
                    sym,
                    "ENTRY_SKIP_LOOP_BUDGET",
                    data={
                        "mode": "live",
                        "kind": "ADD",
                        "confidence": str(confidence or "").lower(),
                        "budget": int(bud),
                    },
                )
                return False
        except Exception as e:
            logger.debug("failed to check entry loop budget (ADD): %s", e, exc_info=True)

        # Ensure leverage on exchange (cross margin). Avoid redundant calls when possible.
        lev_i = 1
        try:
            lev_i = int(round(float(leverage)))
        except Exception:
            lev_i = 1
        lev_i = max(1, lev_i)

        self._note_entry_attempt(sym)
        try:
            cached_lev = int(self._last_leverage_set.get(sym, 0) or 0)
        except Exception:
            cached_lev = 0

        if cached_lev != lev_i:
            if not self.executor.update_leverage(sym, leverage, is_cross=True):
                self._note_entry_fail(sym, f"update_leverage failed ({leverage}x)")
                if oms_intent is not None and oms is not None:
                    try:
                        oms.mark_failed(oms_intent, error=f"update_leverage failed ({float(leverage):.0f}x)")
                    except Exception as e:
                        logger.debug("failed to mark oms intent as leverage-failed: %s", e, exc_info=True)
                mei_alpha_v1.log_audit_event(
                    sym,
                    "LIVE_ORDER_FAIL_UPDATE_LEVERAGE",
                    level="warn",
                    data={
                        "kind": "ADD",
                        "confidence": str(confidence or "").lower(),
                        "leverage": float(leverage),
                    },
                )
                return False
            try:
                self._last_leverage_set[sym] = int(lev_i)
            except Exception as e:
                logger.debug("failed to cache leverage for %s: %s", sym, e, exc_info=True)
        cloid = getattr(oms_intent, "client_order_id", None)
        try:
            result = self.executor.market_open(
                sym,
                is_buy=(pos_type == "LONG"),
                sz=add_size,
                px=float(price),
                slippage_pct=self._live_slippage_pct(),
                cloid=cloid,
            )
        except TypeError as _te:
            # Fallback for older executor builds that lack `cloid` kwarg.
            logger.debug("market_open TypeError (likely missing cloid kwarg): %s", _te)
            result = self.executor.market_open(
                sym,
                is_buy=(pos_type == "LONG"),
                sz=add_size,
                px=float(price),
                slippage_pct=self._live_slippage_pct(),
            )
        if not result:
            exec_err = getattr(self.executor, "last_order_error", None) or {}
            err_kind = str(exec_err.get("kind") or "").strip().lower()
            err_detail = exec_err.get("error") or exec_err.get("response")
            err_s = None
            try:
                err_s = json.dumps(err_detail, separators=(",", ":"), sort_keys=True, default=str)
            except Exception:
                err_s = str(err_detail) if err_detail is not None else None
            err_s = (err_s[:800] if isinstance(err_s, str) else None) or None

            if err_kind in {"timeout", "exception"}:
                # Transport errors are ambiguous: the order may have been accepted even if the response timed out.
                logger.warning("order timeout/exception for ADD %s — exchange state may diverge", sym)
                self._note_entry_fail(sym, f"market_open {err_kind}")
                if risk is not None:
                    try:
                        risk.note_order_sent(
                            symbol=sym,
                            action="ADD",
                            notional_usd=float(notional),
                            reduce_risk=False,
                        )
                    except Exception as e:
                        logger.debug("failed to note ADD order sent to risk tracker: %s", e, exc_info=True)
                try:
                    bud = getattr(self, "_entry_budget_remaining", None)
                    if bud is not None:
                        setattr(self, "_entry_budget_remaining", max(0, int(bud) - 1))
                except Exception as e:
                    logger.debug("failed to decrement entry budget (ADD timeout): %s", e, exc_info=True)
                if oms_intent is not None and oms is not None:
                    try:
                        oms.mark_submit_unknown(
                            oms_intent,
                            symbol=sym,
                            side=side,
                            order_type="market_open",
                            reduce_only=False,
                            requested_size=float(add_size),
                            error=err_s or err_kind,
                        )
                    except Exception as e:
                        logger.debug("failed to mark oms intent as submit-unknown (ADD): %s", e, exc_info=True)
                self._reconcile_after_submit_unknown(symbol=sym, action="ADD")
            else:
                self._note_entry_fail(sym, "market_open rejected")
                if oms_intent is not None and oms is not None:
                    try:
                        oms.mark_failed(oms_intent, error="market_open rejected")
                    except Exception as e:
                        logger.debug("failed to mark oms intent as market_open rejected: %s", e, exc_info=True)
            mei_alpha_v1.log_audit_event(
                sym,
                "LIVE_ORDER_SUBMIT_UNKNOWN" if err_kind in {"timeout", "exception"} else "LIVE_ORDER_FAIL_MARKET_OPEN",
                level="warn",
                data={
                    "kind": "ADD",
                    "confidence": str(confidence or "").lower(),
                    "px_est": float(fill_price_est),
                    "size": float(add_size),
                    "notional_est": float(notional),
                    "leverage": float(leverage),
                    "margin_est": float(margin_add),
                    "submit_err_kind": err_kind or None,
                    "submit_err": err_s,
                },
            )
            return False

        if risk is not None:
            try:
                risk.note_order_sent(
                    symbol=sym,
                    action="ADD",
                    notional_usd=float(notional),
                    reduce_risk=False,
                )
            except Exception as exc:
                # Best-effort risk tracking; failures here must not block live trading.
                mei_alpha_v1.log_audit_event(
                    sym,
                    "LIVE_RISK_NOTE_ORDER_SENT_ERROR",
                    level="error",
                    data={
                        "action": "ADD",
                        "notional_usd": float(notional),
                        "reduce_risk": False,
                        "error": repr(exc),
                    },
                )

        try:
            bud = getattr(self, "_entry_budget_remaining", None)
            if bud is not None:
                setattr(self, "_entry_budget_remaining", max(0, int(bud) - 1))
        except Exception as e:
            logger.debug("failed to decrement entry budget after ADD send: %s", e, exc_info=True)

        if oms_intent is not None and oms is not None:
            try:
                oms.mark_sent(
                    oms_intent,
                    symbol=sym,
                    side=side,
                    order_type="market_open",
                    reduce_only=False,
                    requested_size=float(add_size),
                    result=result,
                )
            except Exception as e:
                logger.debug("failed to mark oms intent as sent (ADD): %s", e, exc_info=True)

        print(
            f"➕ LIVE ORDER sent: ADD {pos_type} {sym} "
            f"px~={float(fill_price_est):.4f} size={add_size:.6f} notional~=${notional:.2f} "
            f"lev={leverage:.0f} margin~=${margin_add:.2f} conf={confidence}"
        )
        mei_alpha_v1.log_audit_event(
            sym,
            "LIVE_ORDER_SENT_ADD",
            data={
                "confidence": str(confidence or "").lower(),
                "px_est": float(fill_price_est),
                "size": float(add_size),
                "notional_est": float(notional),
                "leverage": float(leverage),
                "margin_est": float(margin_add),
                "size_multiplier": float(size_mult),
            },
        )

        # Update local strategy state (position size/entry will be resynced from exchange).
        pos["adds_count"] = adds_count + 1
        pos["last_add_time"] = now_ms
        pos["tp1_taken"] = 0
        if pos.get("entry_atr") and current_atr > 0:
            try:
                old_sz = float(pos.get("size") or 0.0)
            except Exception:
                old_sz = 0.0
            new_total = old_sz + add_size
            if new_total > 0:
                pos["entry_atr"] = (
                    (float(pos.get("entry_atr") or 0.0) * old_sz) + (current_atr * add_size)
                ) / new_total
        elif current_atr > 0:
            pos["entry_atr"] = current_atr

        audit = None
        if indicators is not None:
            try:
                audit = indicators.get("audit")
            except Exception:
                audit = None

        _breadth_pct_add = None
        try:
            _breadth_pct_add = (indicators if indicators is not None else {}).get("_market_breadth_pct")
            if _breadth_pct_add is not None:
                _breadth_pct_add = float(_breadth_pct_add)
        except Exception:
            _breadth_pct_add = None

        self._push_pending(
            sym,
            {
                "action": "ADD",
                "confidence": confidence,
                "entry_atr": current_atr,
                "leverage": leverage,
                "reason": _add_reason,
                "reason_code": kernel_reason_code or None,
                "breadth_pct": _breadth_pct_add,
                "meta": {
                    "audit": audit if isinstance(audit, dict) else None,
                    "breadth_pct": _breadth_pct_add,
                    "reason_code": kernel_reason_code or None,
                    "oms": (
                        {
                            "intent_id": getattr(oms_intent, "intent_id", None),
                            "client_order_id": getattr(oms_intent, "client_order_id", None),
                        }
                        if oms_intent is not None
                        else None
                    ),
                    "order": {
                        "kind": "ADD",
                        "confidence": str(confidence or "").lower(),
                        "px_est": float(fill_price_est),
                        "size": float(add_size),
                        "notional_est": float(notional),
                        "leverage": float(leverage),
                        "margin_est": float((notional / leverage) if leverage > 0 else 0.0),
                        "adds_count_before": int(adds_count),
                        "adds_count_after": int(adds_count + 1),
                        "max_adds_per_symbol": int(max_adds),
                        "profit_atr": float(profit_atr),
                        "min_profit_atr": float(min_profit_atr),
                        "dist_to_sl_atr": float(dist_to_sl_atr),
                        "momentum_expanding": None if momentum_expanding is None else bool(momentum_expanding),
                    },
                },
            },
        )
        self.upsert_position_state(sym)

        return True

    def reduce_position(
        self, symbol, reduce_size, price, timestamp, reason, *, confidence="N/A", meta: dict | None = None
    ) -> bool:
        sym = str(symbol or "").strip().upper()
        if sym not in (self.positions or {}):
            return False

        if not self._can_attempt_exit(sym):
            return False

        pos = self.positions[sym]
        pos_type = str(pos.get("type") or "").upper()

        try:
            size = float(pos.get("size") or 0.0)
        except Exception:
            return False
        if size <= 0:
            return False

        try:
            reduce_size_f = float(reduce_size)
        except Exception:
            reduce_size_f = size
        reduce_size_f = max(0.0, min(size, reduce_size_f))
        if reduce_size_f <= 0:
            return False

        trade_cfg = self._live_trade_cfg(sym)
        min_notional = float(self._min_notional_usd(sym))

        exit_side = "SELL" if pos_type == "LONG" else "BUY"
        fill_price_est = mei_alpha_v1._get_fill_price(
            sym,
            exit_side,
            float(price),
            slippage_bps=float(trade_cfg.get("slippage_bps", mei_alpha_v1.HL_SLIPPAGE_BPS)),
            use_bbo_for_fills=bool(trade_cfg.get("use_bbo_for_fills", True)),
        )
        if fill_price_est <= 0:
            fill_price_est = float(price)

        intended_full_close = reduce_size_f >= (size - 1e-12)

        # For full closes:
        # - We can safely round UP (reduce-only IOC) to avoid leaving dust.
        # - HL enforces a $10 min trade notional even for reduce-only closes, so when the position
        #   notional is < min_notional, we boost the close size to meet the min and let reduceOnly
        #   clamp the executed size to the actual position.
        if intended_full_close:
            close_sz = hyperliquid_meta.round_size_up(sym, size)
            min_sz = hyperliquid_meta.min_size_for_notional(sym, min_notional, float(fill_price_est))
            if min_sz > close_sz:
                close_sz = min_sz
            reduce_size_f = float(close_sz)
            if reduce_size_f <= 0:
                return False
            is_full_close = True
        else:
            # Start with a conservative rounding DOWN (never reduce more than requested).
            reduce_size_f = hyperliquid_meta.round_size(sym, reduce_size_f)
            if reduce_size_f <= 0:
                return False

            is_full_close = False
            notional_est = abs(reduce_size_f) * float(fill_price_est)
            if notional_est < min_notional:
                boosted = hyperliquid_meta.min_size_for_notional(sym, min_notional, float(fill_price_est))
                if boosted <= 0:
                    return False

                # If boosting would close the position (or leave dust under min-notional), close fully instead.
                if boosted >= (size - 1e-12):
                    close_sz = hyperliquid_meta.round_size_up(sym, size)
                    if boosted > close_sz:
                        close_sz = boosted
                    reduce_size_f = float(close_sz)
                    if reduce_size_f <= 0:
                        return False
                    is_full_close = True
                else:
                    remaining_sz = max(0.0, size - boosted)
                    remaining_ntl = remaining_sz * float(fill_price_est)
                    if remaining_ntl < min_notional:
                        close_sz = hyperliquid_meta.round_size_up(sym, size)
                        if boosted > close_sz:
                            close_sz = boosted
                        reduce_size_f = float(close_sz)
                        if reduce_size_f <= 0:
                            return False
                        is_full_close = True
                    else:
                        reduce_size_f = boosted

        action_kind = "CLOSE" if is_full_close else "REDUCE"
        reason_code = ""
        if isinstance(meta, dict):
            reason_code = str(meta.get("reason_code") or "").strip().lower()
        lev = float(pos.get("leverage") or 1.0)
        lev = max(1.0, lev)
        notional_est2 = abs(reduce_size_f) * float(fill_price_est)
        margin_est2 = (notional_est2 / lev) if lev > 0 else 0.0

        oms = getattr(self, "oms", None)
        oms_intent = None
        if oms is not None:
            try:
                meta_for_oms: dict = {}
                if isinstance(meta, dict):
                    meta_for_oms.update(meta)
                order_meta = {
                    "kind": action_kind,
                    "reason": str(reason or ""),
                    "confidence": str(confidence or "").lower(),
                    "px_est": float(fill_price_est),
                    "size": float(reduce_size_f),
                    "notional_est": float(notional_est2),
                    "leverage": float(lev),
                    "margin_est": float(margin_est2),
                }
                if isinstance(meta_for_oms.get("order"), dict):
                    meta_for_oms["order"] = {**meta_for_oms["order"], **order_meta}
                else:
                    meta_for_oms["order"] = order_meta
                if reason_code:
                    meta_for_oms["reason_code"] = reason_code
                oms_intent = oms.create_intent(
                    symbol=sym,
                    action=action_kind,
                    side=exit_side,
                    requested_size=float(reduce_size_f),
                    requested_notional=float(notional_est2),
                    leverage=float(lev),
                    decision_ts=timestamp,
                    reason=str(reason or ""),
                    confidence=str(confidence or ""),
                    entry_atr=None,
                    meta=meta_for_oms or None,
                    dedupe_open=False,
                )
            except Exception:
                oms_intent = None

        # Risk guardrails (kill-switch + rate limits). Best-effort.
        risk = getattr(self, "risk", None)
        if risk is not None:
            try:
                dec = risk.allow_order(
                    symbol=sym,
                    action=action_kind,
                    side=exit_side,
                    notional_usd=float(notional_est2),
                    leverage=float(lev),
                    intent_id=getattr(oms_intent, "intent_id", None),
                    reduce_risk=True,
                )
                if not getattr(dec, "allowed", False):
                    why = str(getattr(dec, "reason", "risk_block"))
                    if oms_intent is not None and oms is not None:
                        try:
                            oms.mark_failed(oms_intent, error=f"risk blocked: {why}")
                        except Exception as e:
                            logger.debug("failed to mark oms intent as risk-blocked: %s", e, exc_info=True)
                    mei_alpha_v1.log_audit_event(
                        sym,
                        "LIVE_ORDER_BLOCKED_RISK",
                        level="warn",
                        data={
                            "kind": action_kind,
                            "size": float(reduce_size_f),
                            "leverage": float(lev),
                            "reason": str(why),
                            "oms_intent_id": getattr(oms_intent, "intent_id", None) if oms_intent is not None else None,
                        },
                    )
                    return False
            except Exception:
                logger.error("risk.allow_order() raised for exit %s, BLOCKING order as fail-closed", sym, exc_info=True)
                return False

        if not self._can_send_orders():
            if oms_intent is not None and oms is not None:
                try:
                    why = "DRY LIVE" if live_mode() == "dry_live" else "DISABLED"
                    oms.mark_would(oms_intent, note=why)
                except Exception as e:
                    logger.debug("failed to mark oms intent as would-send (exit): %s", e, exc_info=True)
            print(
                f"🟡 LIVE ORDERS DISABLED: would {('CLOSE' if is_full_close else 'REDUCE')} "
                f"{sym} size={reduce_size_f:.6f} lev={float(pos.get('leverage') or 1.0):.0f} reason={reason}"
            )
            mei_alpha_v1.log_audit_event(
                sym,
                "LIVE_ORDER_WOULD_EXIT",
                data={
                    "kind": "CLOSE" if is_full_close else "REDUCE",
                    "size": float(reduce_size_f),
                    "leverage": float(pos.get("leverage") or 1.0),
                    "reason": str(reason or ""),
                    "confidence": str(confidence or "").lower(),
                },
            )
            return False

        cloid = getattr(oms_intent, "client_order_id", None)
        is_buy_exit = bool(exit_side == "BUY")
        try:
            result = self.executor.market_close(
                sym,
                is_buy=is_buy_exit,
                sz=reduce_size_f,
                px=float(price),
                slippage_pct=self._live_slippage_pct(),
                cloid=cloid,
            )
        except TypeError:
            result = self.executor.market_close(
                sym,
                is_buy=is_buy_exit,
                sz=reduce_size_f,
                px=float(price),
                slippage_pct=self._live_slippage_pct(),
            )
        if not result:
            exec_err = getattr(self.executor, "last_order_error", None) or {}
            err_kind = str(exec_err.get("kind") or "").strip().lower()
            err_detail = exec_err.get("error") or exec_err.get("response")
            err_s = None
            try:
                err_s = json.dumps(err_detail, separators=(",", ":"), sort_keys=True, default=str)
            except Exception:
                err_s = str(err_detail) if err_detail is not None else None
            err_s = (err_s[:800] if isinstance(err_s, str) else None) or None

            if err_kind in {"timeout", "exception"}:
                # Transport errors are ambiguous: the order may have been accepted even if the response timed out.
                try:
                    self._last_exit_attempt_at_s[sym] = time.time()
                except Exception as e:
                    logger.debug("failed to record exit attempt timestamp for %s: %s", sym, e, exc_info=True)
                if risk is not None:
                    try:
                        risk.note_order_sent(
                            symbol=sym,
                            action=str(action_kind),
                            notional_usd=float(notional_est2),
                            reduce_risk=True,
                        )
                    except Exception as e:
                        logger.debug("failed to note exit order sent to risk tracker: %s", e, exc_info=True)
                if oms_intent is not None and oms is not None:
                    try:
                        oms.mark_submit_unknown(
                            oms_intent,
                            symbol=sym,
                            side=exit_side,
                            order_type="market_close",
                            reduce_only=True,
                            requested_size=float(reduce_size_f),
                            error=err_s or err_kind,
                        )
                    except Exception as e:
                        logger.debug("failed to mark oms intent as submit-unknown (exit): %s", e, exc_info=True)
                self._reconcile_after_submit_unknown(symbol=sym, action=str(action_kind))
            else:
                if oms_intent is not None and oms is not None:
                    try:
                        oms.mark_failed(oms_intent, error="market_close rejected")
                    except Exception as e:
                        logger.debug("failed to mark oms intent as market_close rejected: %s", e, exc_info=True)
            mei_alpha_v1.log_audit_event(
                sym,
                "LIVE_ORDER_SUBMIT_UNKNOWN" if err_kind in {"timeout", "exception"} else "LIVE_ORDER_FAIL_MARKET_CLOSE",
                level="warn",
                data={
                    "kind": "CLOSE" if is_full_close else "REDUCE",
                    "size": float(reduce_size_f),
                    "reason": str(reason or ""),
                    "confidence": str(confidence or "").lower(),
                    "submit_err_kind": err_kind or None,
                    "submit_err": err_s,
                },
            )
            return False

        if risk is not None:
            try:
                risk.note_order_sent(
                    symbol=sym,
                    action=str(action_kind),
                    notional_usd=float(notional_est2),
                    reduce_risk=True,
                )
            except Exception as exc:
                # Best-effort risk tracking; failures here must not block live trading.
                mei_alpha_v1.log_audit_event(
                    sym,
                    "LIVE_RISK_NOTE_ORDER_SENT_ERROR",
                    level="error",
                    data={
                        "action": str(action_kind),
                        "notional_usd": float(notional_est2),
                        "reduce_risk": True,
                        "error": repr(exc),
                    },
                )

        # Successful send: rate-limit future exit attempts for this symbol for a short cooldown window.
        try:
            self._last_exit_attempt_at_s[sym] = time.time()
        except Exception as e:
            logger.debug("failed to record exit cooldown timestamp for %s: %s", sym, e, exc_info=True)

        if oms_intent is not None and oms is not None:
            try:
                oms.mark_sent(
                    oms_intent,
                    symbol=sym,
                    side=exit_side,
                    order_type="market_close",
                    reduce_only=True,
                    requested_size=float(reduce_size_f),
                    result=result,
                )
            except Exception as e:
                logger.debug("failed to mark oms intent as sent (exit): %s", e, exc_info=True)

        if is_full_close:
            try:
                self._last_full_close_sent_at_s[sym] = time.time()
                self._last_full_close_sent_type[sym] = str(pos_type or "").upper()
                self._last_full_close_sent_reason[sym] = str(reason or "")
            except Exception as e:
                logger.debug("failed to record full close metadata for %s: %s", sym, e, exc_info=True)

        notional = abs(reduce_size_f) * float(fill_price_est)
        margin_est = notional / lev if lev > 0 else 0.0
        print(
            f"✅ LIVE ORDER sent: {('CLOSE' if is_full_close else 'REDUCE')} {pos_type} {sym} "
            f"px~={float(fill_price_est):.4f} size={reduce_size_f:.6f} notional~=${notional:.2f} "
            f"lev={lev:.0f} margin~=${margin_est:.2f} reason={reason}"
        )
        mei_alpha_v1.log_audit_event(
            sym,
            "LIVE_ORDER_SENT_EXIT",
            data={
                "kind": "CLOSE" if is_full_close else "REDUCE",
                "pos_type": str(pos_type),
                "px_est": float(fill_price_est),
                "size": float(reduce_size_f),
                "notional_est": float(notional),
                "leverage": float(lev),
                "margin_est": float(margin_est),
                "reason": str(reason or ""),
                "confidence": str(confidence or "").lower(),
            },
        )

        meta_final = {}
        if isinstance(meta, dict):
            try:
                meta_final = dict(meta)
            except Exception:
                meta_final = {}
        try:
            order_meta = {
                "kind": "CLOSE" if is_full_close else "REDUCE",
                "reason": str(reason or ""),
                "confidence": str(confidence or "").lower(),
                "px_est": float(fill_price_est),
                "size": float(reduce_size_f),
                "notional_est": float(notional),
                "leverage": float(lev),
                "margin_est": float(margin_est),
            }
            if isinstance(meta_final.get("order"), dict):
                meta_final["order"] = {**meta_final["order"], **order_meta}
            else:
                meta_final["order"] = order_meta
        except Exception as e:
            logger.debug("failed to build order meta for exit: %s", e, exc_info=True)

        if oms_intent is not None:
            try:
                meta_final["oms"] = {
                    "intent_id": getattr(oms_intent, "intent_id", None),
                    "client_order_id": getattr(oms_intent, "client_order_id", None),
                }
            except Exception as e:
                logger.debug("failed to attach oms metadata to exit meta: %s", e, exc_info=True)

        self._push_pending(
            sym,
            {
                "action": "CLOSE" if is_full_close else "REDUCE",
                "confidence": confidence,
                "reason": reason,
                "reason_code": reason_code or None,
                "leverage": float(pos.get("leverage") or 1.0),
                "meta": meta_final or None,
            },
        )
        return True

    def close_position(self, symbol, price, timestamp, reason, *, meta: dict | None = None):
        sym = str(symbol or "").strip().upper()
        if sym not in (self.positions or {}):
            return
        try:
            sz = float(((self.positions or {}).get(sym) or {}).get("size") or 0.0)
        except Exception:
            return
        if sz <= 0:
            return
        self.reduce_position(sym, sz, price, timestamp, reason, confidence="N/A", meta=meta)

    def execute_trade(
        self,
        symbol,
        signal,
        price,
        timestamp,
        confidence,
        atr=0.0,
        indicators=None,
        *,
        action: str | None = None,
        target_size: float | None = None,
        reason: str | None = None,
        _from_kernel_open: bool = False,
        mode: str | None = None,
    ):
        sym = str(symbol or "").strip().upper()
        if not sym:
            return
        del mode
        # Runtime SSOT hardening: entry decisions come from Rust kernel intents.
        # Keep execution/risk rails and audit logging, but disable legacy
        # Python entry-gate decision filters (confidence/PESC/SSF/REEF).
        python_entry_gates_enabled = False

        audit = None
        if indicators is not None:
            try:
                audit = indicators.get("audit")
            except Exception:
                audit = None
        kernel_reason_code = ""
        try:
            kernel_reason_code = str(
                (indicators if indicators is not None else {}).get("_kernel_reason_code") or ""
            ).strip().lower()
        except Exception:
            kernel_reason_code = ""

        # Persist the strategy decision for live monitoring (signals are not orders).
        # This keeps the monitor UI "SIGNAL" column populated for live mode.
        log_live_signal(
            symbol=sym,
            signal=str(signal or "").strip().upper(),
            confidence=confidence,
            price=price,
            indicators=indicators,
        )

        act = str(action or "").strip().upper()
        if act not in {"OPEN", "ADD", "CLOSE", "REDUCE"}:
            logger.debug(
                "execute_trade: skip legacy signal-only path for %s (action=%r)",
                sym,
                action,
            )
            return

        if act == "OPEN":
            if sym in (self.positions or {}):
                # OPEN action only maps to new-entry flow when no position exists.
                return
        elif act == "ADD":
            return self.add_to_position(
                sym,
                price,
                timestamp,
                confidence,
                atr=atr,
                indicators=indicators,
                target_size=target_size,
                reason=reason,
            )
        elif act == "CLOSE":
            close_meta = {"reason_code": kernel_reason_code} if kernel_reason_code else None
            return self.close_position(
                sym,
                price,
                timestamp,
                reason=str(reason or "Kernel CLOSE"),
                meta=close_meta,
            )
        elif act == "REDUCE":
            if sym not in (self.positions or {}):
                return
            if target_size is not None:
                try:
                    reduce_size = float(target_size)
                except Exception:
                    reduce_size = None
            else:
                reduce_size = None
            if reduce_size is None:
                try:
                    reduce_size = float((self.positions or {}).get(sym, {}).get("size") or 0.0)
                except Exception:
                    reduce_size = 0.0
            reduce_meta = {"reason_code": kernel_reason_code} if kernel_reason_code else None
            return self.reduce_position(
                sym,
                reduce_size,
                price,
                timestamp,
                reason=str(reason or "Kernel REDUCE"),
                confidence=confidence,
                meta=reduce_meta,
            )

        # OPEN path is kernel-action driven; do not run legacy signal flip/add logic.
        if sym in (self.positions or {}):
            return

        if signal == "NEUTRAL":
            return

        # New position open
        trade_cfg = self._live_trade_cfg(sym)
        self._prune_pending_opens()
        try:
            max_open_positions = int(trade_cfg.get("max_open_positions", 1))
        except Exception:
            max_open_positions = 1
        open_syms = sorted(
            [str(s or "").strip().upper() for s in (self.positions or {}).keys() if str(s or "").strip()]
        )
        with self._pending_open_lock:
            pending_syms = sorted(
                [
                    str(s or "").strip().upper()
                    for s in (self._pending_open_sent_at_s or {}).keys()
                    if str(s or "").strip()
                ]
            )
        open_n = int(len(open_syms))
        pending_n = int(len(pending_syms))
        total_n = open_n + pending_n
        if max_open_positions > 0 and total_n >= max_open_positions:
            print(f"🟡 LIVE SKIP {sym} entry: max_open_positions={max_open_positions} reached")
            mei_alpha_v1.log_audit_event(
                sym,
                # Normalize skip events across paper + live so queries like:
                #   WHERE event LIKE 'ENTRY_SKIP_%'
                # work the same in both DBs.
                "ENTRY_SKIP_MAX_OPEN_POSITIONS",
                data={
                    "mode": "live",
                    "signal": str(signal or "").upper(),
                    "confidence": str(confidence or "").lower(),
                    "max_open_positions": int(max_open_positions),
                    # NOTE: "open_positions" means real positions (synced from exchange),
                    # not "open + pending". Pending opens are tracked separately so the audit
                    # record matches the live heartbeat's `open_pos` field.
                    "open_positions": int(open_n),
                    "pending_open_positions": int(pending_n),
                    "open_plus_pending_positions": int(total_n),
                    "open_symbols": open_syms,
                    "pending_open_symbols": pending_syms,
                },
            )
            return

        # v5.035: Entry confidence gate.
        min_entry_conf = str(trade_cfg.get("entry_min_confidence", "high"))
        if python_entry_gates_enabled and not mei_alpha_v1._conf_ok(confidence, min_confidence=min_entry_conf):
            print(f"🟡 LIVE SKIP {sym} entry: confidence '{confidence}' < '{min_entry_conf}'")
            mei_alpha_v1.log_audit_event(
                sym,
                "ENTRY_SKIP_LOW_CONFIDENCE",
                data={
                    "mode": "live",
                    "signal": str(signal or "").upper(),
                    "confidence": str(confidence or "").lower(),
                    "min_entry_confidence": str(min_entry_conf).lower(),
                },
            )
            return

        if not self._can_attempt_entry(sym):
            return

        # v5.014: 同向平倉後進場冷卻 (Post-Exit Same-Direction Cooldown - PESC)
        # v5.015: ADX 自適應冷卻 (ADX-Adaptive PESC)
        # 根據趨勢強度動態調整冷卻時間：強趨勢 (ADX >= 40) 縮短至 min_cd，弱趨勢 (ADX <= 25) 延長至 max_cd。
        base_cooldown = float(trade_cfg.get("reentry_cooldown_minutes", 30))
        if python_entry_gates_enabled and base_cooldown > 0:
            adx_val = indicators.get("ADX", 30) if indicators is not None else 30
            min_cd = float(trade_cfg.get("reentry_cooldown_min_mins", 45))
            max_cd = float(trade_cfg.get("reentry_cooldown_max_mins", 180))

            # 線性插值：ADX 25->40 對應 CD 60->15
            if adx_val >= 40:
                reentry_cooldown = min_cd
            elif adx_val <= 25:
                reentry_cooldown = max_cd
            else:
                t = (adx_val - 25) / (40 - 25)
                reentry_cooldown = max_cd - t * (max_cd - min_cd)

            last_ts_s = None
            last_type = None
            last_reason = None
            try:
                with sqlite3.connect(mei_alpha_v1.DB_PATH, timeout=_DB_TIMEOUT_S) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT timestamp, type, reason
                        FROM trades
                        WHERE symbol = ? AND action = 'CLOSE'
                        ORDER BY id DESC LIMIT 1
                        """,
                        (sym,),
                    )
                    row = cursor.fetchone()

                if row:
                    last_ts, last_type, last_reason = row
                    try:
                        ts_s = str(last_ts or "").strip()
                        if ts_s.endswith("Z"):
                            ts_s = ts_s[:-1] + "+00:00"
                        dt = datetime.datetime.fromisoformat(ts_s)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=datetime.timezone.utc)
                        last_ts_s = float(dt.timestamp())
                        last_type = str(last_type or "").upper()
                        last_reason = str(last_reason or "")
                    except Exception:
                        last_ts_s = None
            except Exception as e:
                print(f"⚠️ LIVE PESC db query failed for {sym}: {e}")

            mem_ts_s = _safe_float(self._last_full_close_sent_at_s.get(sym), None)
            mem_type = str(self._last_full_close_sent_type.get(sym) or "").upper() or None
            mem_reason = str(self._last_full_close_sent_reason.get(sym) or "")

            chosen_ts_s = last_ts_s
            chosen_type = last_type
            chosen_reason = last_reason

            if mem_ts_s is not None and (chosen_ts_s is None or float(mem_ts_s) > float(chosen_ts_s)):
                chosen_ts_s = float(mem_ts_s)
                chosen_type = mem_type
                chosen_reason = mem_reason

            if chosen_ts_s is not None and chosen_type:
                diff_mins = max(0.0, (time.time() - float(chosen_ts_s)) / 60.0)
                target_type = "LONG" if signal == "BUY" else "SHORT"
                if (
                    diff_mins < reentry_cooldown
                    and str(chosen_type).upper() == target_type
                    and "Signal Flip" not in (chosen_reason or "")
                ):
                    print(
                        f"⏳ LIVE PESC: Skipping {sym} {target_type} re-entry. Cooldown active "
                        f"({diff_mins:.1f}/{reentry_cooldown:.1f}m, ADX: {float(adx_val):.1f})"
                    )
                    mei_alpha_v1.log_audit_event(
                        sym,
                        "ENTRY_SKIP_PESC",
                        data={
                            "mode": "live",
                            "signal": str(signal or "").upper(),
                            "confidence": str(confidence or "").lower(),
                            "target_type": str(target_type),
                            "adx": float(adx_val),
                            "cooldown_mins": float(reentry_cooldown),
                            "diff_mins": float(diff_mins),
                            "last_type": str(chosen_type or ""),
                            "last_reason": str(chosen_reason or ""),
                        },
                    )
                    return

        # v5.017: 信號穩定性過濾 (Signal Stability Filter - SSF)
        # Align with PaperTrader: block entries if MACD momentum sign contradicts the direction.
        # v5.037: Make SSF configurable via YAML (`trade.enable_ssf_filter`).
        enable_ssf = bool(trade_cfg.get("enable_ssf_filter", True))
        if python_entry_gates_enabled and enable_ssf and indicators is not None:
            try:
                macd_h = float(indicators.get("MACD_hist", 0) or 0.0)
            except Exception:
                macd_h = 0.0
            if signal == "BUY" and macd_h < 0:
                print(f"⏳ LIVE SSF: Skipping {sym} BUY. MACD_hist ({macd_h:.6f}) is negative.")
                mei_alpha_v1.log_audit_event(
                    sym,
                    "ENTRY_SKIP_SSF",
                    data={
                        "mode": "live",
                        "signal": "BUY",
                        "confidence": str(confidence or "").lower(),
                        "macd_hist": float(macd_h),
                    },
                )
                return
            if signal == "SELL" and macd_h > 0:
                print(f"⏳ LIVE SSF: Skipping {sym} SELL. MACD_hist ({macd_h:.6f}) is positive.")
                mei_alpha_v1.log_audit_event(
                    sym,
                    "ENTRY_SKIP_SSF",
                    data={
                        "mode": "live",
                        "signal": "SELL",
                        "confidence": str(confidence or "").lower(),
                        "macd_hist": float(macd_h),
                    },
                )
                return

        # v5.018: RSI 進場極端過濾 (REEF) — entry-only.
        if python_entry_gates_enabled and bool(trade_cfg.get("enable_reef_filter", True)) and indicators is not None:
            rsi_v = _safe_float(indicators.get("RSI"), None)
            if rsi_v is not None:
                long_block = _safe_float(trade_cfg.get("reef_long_rsi_block_gt"), 70.0) or 70.0
                short_block = _safe_float(trade_cfg.get("reef_short_rsi_block_lt"), 30.0) or 30.0
                if signal == "BUY" and float(rsi_v) > float(long_block):
                    print(f"⛔ LIVE REEF: Skipping {sym} BUY. RSI ({float(rsi_v):.1f}) > {float(long_block):.1f}")
                    mei_alpha_v1.log_audit_event(
                        sym,
                        "ENTRY_SKIP_REEF",
                        data={
                            "mode": "live",
                            "signal": "BUY",
                            "confidence": str(confidence or "").lower(),
                            "rsi": float(rsi_v),
                            "threshold_gt": float(long_block),
                        },
                    )
                    return
                if signal == "SELL" and float(rsi_v) < float(short_block):
                    print(f"⛔ LIVE REEF: Skipping {sym} SELL. RSI ({float(rsi_v):.1f}) < {float(short_block):.1f}")
                    mei_alpha_v1.log_audit_event(
                        sym,
                        "ENTRY_SKIP_REEF",
                        data={
                            "mode": "live",
                            "signal": "SELL",
                            "confidence": str(confidence or "").lower(),
                            "rsi": float(rsi_v),
                            "threshold_lt": float(short_block),
                        },
                    )
                    return

        equity_base = _safe_float(self.get_live_balance(), self.balance) or self.balance

        cfg = mei_alpha_v1.get_strategy_config(sym)
        thr = cfg.get("thresholds") or {}

        sizing = mei_alpha_v1.compute_entry_sizing(
            symbol=sym,
            equity_base=equity_base,
            price=float(price),
            confidence=confidence,
            atr=float(atr or 0.0),
            indicators=indicators,
            trade_cfg=trade_cfg,
            thresholds=thr,
        )
        leverage = float(sizing.leverage)

        # Live clamps: per-order notional cap to avoid over-sizing small accounts.
        max_notional_cfg = _safe_float(trade_cfg.get("max_notional_usd_per_order"), 0.0)
        min_notional = float(self._min_notional_usd(sym))
        if max_notional_cfg > 0 and max_notional_cfg < min_notional:
            return

        # Margin availability / global cap.
        max_total_margin_pct = float(trade_cfg.get("max_total_margin_pct", 0.60))
        # Prefer exchange-reported total margin when available (more accurate than estimate).
        exchange_margin = _safe_float(getattr(self, "_total_margin_used_usd", None), 0.0)
        if exchange_margin > 0:
            current_margin = exchange_margin
        else:
            current_margin = 0.0
            for s, p in (self.positions or {}).items():
                current_margin += self._estimate_margin_used(s, p)
        try:
            available_margin = max(0.0, float(self._account_value_usd) - float(self._total_margin_used_usd))
        except Exception:
            available_margin = 0.0
        if available_margin <= 0:
            available_margin = max(0.0, float(equity_base or 0.0))

        remaining_margin_cap = min(available_margin, max(0.0, (equity_base * max_total_margin_pct) - current_margin))
        if remaining_margin_cap <= 0:
            return

        # Desired notional (boost to min-notional; clamp to order cap + margin cap).
        max_notional = remaining_margin_cap * leverage
        if max_notional_cfg > 0:
            max_notional = min(max_notional, max_notional_cfg)
        if max_notional < min_notional:
            return

        desired_notional = float(sizing.desired_notional_usd)
        try:
            explicit_notional = float(target_size) if target_size is not None else None
        except Exception:
            explicit_notional = None
        if explicit_notional is not None and explicit_notional > 0:
            desired_notional = explicit_notional
        if desired_notional < min_notional:
            desired_notional = min_notional
        desired_notional = min(desired_notional, max_notional)
        if desired_notional < min_notional:
            return

        # Respect HL leverage tiers (may reduce leverage, which also reduces max notional under the same margin cap).
        max_lev = hyperliquid_meta.max_leverage(sym, desired_notional)
        if max_lev is not None and leverage > float(max_lev):
            leverage = float(max_lev)
            max_notional = remaining_margin_cap * leverage
            if max_notional_cfg > 0:
                max_notional = min(max_notional, max_notional_cfg)
            if max_notional < min_notional:
                return
            desired_notional = min(desired_notional, max_notional)
            if desired_notional < min_notional:
                return

        fill_price_est = mei_alpha_v1._get_fill_price(
            sym,
            "BUY" if signal == "BUY" else "SELL",
            float(price),
            slippage_bps=float(trade_cfg.get("slippage_bps", mei_alpha_v1.HL_SLIPPAGE_BPS)),
            use_bbo_for_fills=bool(trade_cfg.get("use_bbo_for_fills", True)),
        )
        size = self._size_bounds_for_notional(
            sym,
            price=fill_price_est,
            desired_notional=desired_notional,
            min_notional=min_notional,
            max_notional=max_notional if max_notional > 0 else None,
        )
        if size <= 0:
            return

        notional = abs(size) * fill_price_est
        if notional < min_notional:
            return

        margin_need = (notional / leverage) if leverage > 0 else notional
        if margin_need > remaining_margin_cap:
            return

        entry_side = "BUY" if signal == "BUY" else "SELL"
        default_open_reason = (
            "Signal Trigger [REVERSED]"
            if (indicators if indicators is not None else {}).get("_reversed_entry") is True
            else "Signal Trigger"
        )
        open_reason = str(reason or default_open_reason).strip() or default_open_reason
        oms = getattr(self, "oms", None)
        oms_intent = None
        if oms is not None:
            try:
                order_meta = {
                    "kind": "OPEN",
                    "signal": str(signal or "").upper(),
                    "confidence": str(confidence or "").lower(),
                    "px_est": float(fill_price_est),
                    "size": float(size),
                    "notional_est": float(notional),
                    "leverage": float(leverage),
                    "margin_est": float(margin_need),
                }
                open_meta = {
                    "audit": audit if isinstance(audit, dict) else None,
                    "order": order_meta,
                }
                if kernel_reason_code:
                    open_meta["reason_code"] = kernel_reason_code
                oms_intent = oms.create_intent(
                    symbol=sym,
                    action="OPEN",
                    side=entry_side,
                    requested_size=float(size),
                    requested_notional=float(notional),
                    leverage=float(leverage),
                    decision_ts=timestamp,
                    reason=open_reason,
                    confidence=str(confidence or ""),
                    entry_atr=float(atr or 0.0),
                    meta=open_meta,
                    dedupe_open=True,
                )
            except Exception:
                oms_intent = None

        if oms is not None and oms_intent is None and _env_bool("AI_QUANT_OMS_REQUIRE_INTENT_FOR_ENTRY", True):
            # Fail-closed for entry orders if we cannot create an OMS intent (prevents untracked duplicates).
            self._note_entry_fail(sym, "oms_intent_create_failed")
            mei_alpha_v1.log_audit_event(
                sym,
                "OMS_INTENT_CREATE_FAILED",
                level="warn",
                data={
                    "kind": "OPEN",
                    "signal": str(signal or "").upper(),
                    "confidence": str(confidence or "").lower(),
                    "px_est": float(fill_price_est),
                    "size": float(size),
                    "notional_est": float(notional),
                    "leverage": float(leverage),
                    "margin_est": float(margin_need),
                },
            )
            return

        if oms_intent is not None and getattr(oms_intent, "duplicate", False):
            mei_alpha_v1.log_audit_event(
                sym,
                "OMS_DUPLICATE_OPEN_INTENT",
                level="warn",
                data={
                    "signal": str(signal or "").upper(),
                    "confidence": str(confidence or "").lower(),
                    "candle_key": str(timestamp),
                },
            )
            return

        # Risk guardrails (kill-switch + rate limits). Best-effort.
        risk = getattr(self, "risk", None)
        if risk is not None:
            try:
                dec = risk.allow_order(
                    symbol=sym,
                    action="OPEN",
                    side=entry_side,
                    notional_usd=float(notional),
                    leverage=float(leverage),
                    equity_usd=float(equity_base or 0.0),
                    entry_price=float(fill_price_est),
                    entry_atr=float(atr or 0.0),
                    sl_atr_mult=float(trade_cfg.get("sl_atr_mult", 1.5)),
                    positions=getattr(self, "positions", None),
                    intent_id=getattr(oms_intent, "intent_id", None),
                    reduce_risk=False,
                )
                if not getattr(dec, "allowed", False):
                    why = str(getattr(dec, "reason", "risk_block"))
                    self._note_entry_fail(sym, f"risk blocked: {why}")
                    if oms_intent is not None and oms is not None:
                        try:
                            oms.mark_failed(oms_intent, error=f"risk blocked: {why}")
                        except Exception as e:
                            logger.debug("failed to mark oms intent as risk-blocked: %s", e, exc_info=True)
                    mei_alpha_v1.log_audit_event(
                        sym,
                        "LIVE_ORDER_BLOCKED_RISK",
                        level="warn",
                        data={
                            "kind": "OPEN",
                            "signal": str(signal or "").upper(),
                            "confidence": str(confidence or "").lower(),
                            "px_est": float(fill_price_est),
                            "size": float(size),
                            "notional_est": float(notional),
                            "leverage": float(leverage),
                            "reason": str(why),
                            "oms_intent_id": getattr(oms_intent, "intent_id", None) if oms_intent is not None else None,
                        },
                    )
                    return
            except Exception:
                logger.error("risk.allow_order() raised for OPEN %s, BLOCKING order as fail-closed", sym, exc_info=True)
                return

        if not self._can_send_entries():
            why = "DRY LIVE" if live_mode() == "dry_live" else ("CLOSE-ONLY" if self._can_send_orders() else "DISABLED")
            if oms_intent is not None and oms is not None:
                try:
                    oms.mark_would(oms_intent, note=str(why))
                except Exception as e:
                    logger.debug("failed to mark oms intent as would-send (OPEN): %s", e, exc_info=True)
            print(
                f"🟡 LIVE {why}: would OPEN {sym} {('LONG' if signal == 'BUY' else 'SHORT')} "
                f"size={size:.6f} notional~=${notional:.2f} margin~=${margin_need:.2f} lev={leverage:.0f} conf={confidence}"
            )
            mei_alpha_v1.log_audit_event(
                sym,
                "LIVE_ORDER_WOULD_OPEN",
                data={
                    "why": str(why),
                    "signal": str(signal or "").upper(),
                    "confidence": str(confidence or "").lower(),
                    "px_est": float(fill_price_est),
                    "size": float(size),
                    "notional_est": float(notional),
                    "leverage": float(leverage),
                    "margin_est": float(margin_need),
                },
            )
            return

        try:
            bud = getattr(self, "_entry_budget_remaining", None)
            if bud is not None and int(bud) <= 0:
                mei_alpha_v1.log_audit_event(
                    sym,
                    "ENTRY_SKIP_LOOP_BUDGET",
                    data={
                        "mode": "live",
                        "kind": "OPEN",
                        "signal": str(signal or "").upper(),
                        "confidence": str(confidence or "").lower(),
                        "budget": int(bud),
                    },
                )
                return
        except Exception as e:
            logger.debug("failed to check entry loop budget (OPEN): %s", e, exc_info=True)

        lev_i = 1
        try:
            lev_i = int(round(float(leverage)))
        except Exception:
            lev_i = 1
        lev_i = max(1, lev_i)

        self._note_entry_attempt(sym)
        try:
            cached_lev = int(self._last_leverage_set.get(sym, 0) or 0)
        except Exception:
            cached_lev = 0

        if cached_lev != lev_i:
            if not self.executor.update_leverage(sym, leverage, is_cross=True):
                self._note_entry_fail(sym, f"update_leverage failed ({leverage}x)")
                if oms_intent is not None and oms is not None:
                    try:
                        oms.mark_failed(oms_intent, error=f"update_leverage failed ({float(leverage):.0f}x)")
                    except Exception as e:
                        logger.debug("failed to mark oms intent as leverage-failed: %s", e, exc_info=True)
                mei_alpha_v1.log_audit_event(
                    sym,
                    "LIVE_ORDER_FAIL_UPDATE_LEVERAGE",
                    level="warn",
                    data={
                        "signal": str(signal or "").upper(),
                        "confidence": str(confidence or "").lower(),
                        "leverage": float(leverage),
                    },
                )
                return
            try:
                self._last_leverage_set[sym] = int(lev_i)
            except Exception as e:
                logger.debug("failed to cache leverage for %s: %s", sym, e, exc_info=True)
        cloid = getattr(oms_intent, "client_order_id", None)
        try:
            result = self.executor.market_open(
                sym,
                is_buy=(signal == "BUY"),
                sz=size,
                px=float(price),
                slippage_pct=self._live_slippage_pct(),
                cloid=cloid,
            )
        except TypeError:
            result = self.executor.market_open(
                sym,
                is_buy=(signal == "BUY"),
                sz=size,
                px=float(price),
                slippage_pct=self._live_slippage_pct(),
            )
        if not result:
            exec_err = getattr(self.executor, "last_order_error", None) or {}
            err_kind = str(exec_err.get("kind") or "").strip().lower()
            err_detail = exec_err.get("error") or exec_err.get("response")
            err_s = None
            try:
                err_s = json.dumps(err_detail, separators=(",", ":"), sort_keys=True, default=str)
            except Exception:
                err_s = str(err_detail) if err_detail is not None else None
            err_s = (err_s[:800] if isinstance(err_s, str) else None) or None

            if err_kind in {"timeout", "exception"}:
                # Transport errors are ambiguous: the order may have been accepted even if the response timed out.
                logger.warning("order timeout/exception for OPEN %s — exchange state may diverge", sym)
                self._note_entry_fail(sym, f"market_open {err_kind}")
                if risk is not None:
                    try:
                        risk.note_order_sent(
                            symbol=sym,
                            action="OPEN",
                            notional_usd=float(notional),
                            reduce_risk=False,
                        )
                    except Exception as e:
                        logger.debug("failed to note OPEN order sent to risk tracker: %s", e, exc_info=True)
                try:
                    bud = getattr(self, "_entry_budget_remaining", None)
                    if bud is not None:
                        setattr(self, "_entry_budget_remaining", max(0, int(bud) - 1))
                except Exception as e:
                    logger.debug("failed to decrement entry budget (OPEN timeout): %s", e, exc_info=True)
                if oms_intent is not None and oms is not None:
                    try:
                        oms.mark_submit_unknown(
                            oms_intent,
                            symbol=sym,
                            side=entry_side,
                            order_type="market_open",
                            reduce_only=False,
                            requested_size=float(size),
                            error=err_s or err_kind,
                        )
                    except Exception as e:
                        logger.debug("failed to mark oms intent as submit-unknown (OPEN): %s", e, exc_info=True)
                # Conservatively count this as a pending open so we don't exceed capacity in-loop.
                try:
                    with self._pending_open_lock:
                        self._pending_open_sent_at_s[sym] = time.time()
                except Exception as e:
                    logger.debug("failed to record pending open timestamp for %s (timeout): %s", sym, e, exc_info=True)
                self._reconcile_after_submit_unknown(symbol=sym, action="OPEN")
            else:
                self._note_entry_fail(sym, "market_open rejected")
                if oms_intent is not None and oms is not None:
                    try:
                        oms.mark_failed(oms_intent, error="market_open rejected")
                    except Exception as e:
                        logger.debug("failed to mark oms intent as market_open rejected: %s", e, exc_info=True)
            mei_alpha_v1.log_audit_event(
                sym,
                "LIVE_ORDER_SUBMIT_UNKNOWN" if err_kind in {"timeout", "exception"} else "LIVE_ORDER_FAIL_MARKET_OPEN",
                level="warn",
                data={
                    "signal": str(signal or "").upper(),
                    "confidence": str(confidence or "").lower(),
                    "px_est": float(fill_price_est),
                    "size": float(size),
                    "notional_est": float(notional),
                    "leverage": float(leverage),
                    "margin_est": float(margin_need),
                    "submit_err_kind": err_kind or None,
                    "submit_err": err_s,
                },
            )
            return

        if risk is not None:
            try:
                risk.note_order_sent(
                    symbol=sym,
                    action="OPEN",
                    notional_usd=float(notional),
                    reduce_risk=False,
                )
            except Exception as exc:
                # Best-effort risk tracking; failures here must not block live trading.
                mei_alpha_v1.log_audit_event(
                    sym,
                    "LIVE_RISK_NOTE_ORDER_SENT_ERROR",
                    level="error",
                    data={
                        "action": "OPEN",
                        "notional_usd": float(notional),
                        "reduce_risk": False,
                        "error": repr(exc),
                    },
                )

        try:
            bud = getattr(self, "_entry_budget_remaining", None)
            if bud is not None:
                setattr(self, "_entry_budget_remaining", max(0, int(bud) - 1))
        except Exception as e:
            logger.debug("failed to decrement entry budget after OPEN send: %s", e, exc_info=True)

        if oms_intent is not None and oms is not None:
            try:
                oms.mark_sent(
                    oms_intent,
                    symbol=sym,
                    side=entry_side,
                    order_type="market_open",
                    reduce_only=False,
                    requested_size=float(size),
                    result=result,
                )
            except Exception as e:
                logger.debug("failed to mark oms intent as sent (OPEN): %s", e, exc_info=True)

        try:
            size_mult = float(trade_cfg.get("size_multiplier", 1.0))
        except Exception:
            size_mult = 1.0

        print(
            f"🚀 LIVE ORDER sent: OPEN {('LONG' if signal == 'BUY' else 'SHORT')} {sym} "
            f"px~={float(fill_price_est):.4f} size={size:.6f} notional~=${notional:.2f} "
            f"lev={leverage:.0f} margin~=${margin_need:.2f} conf={confidence}"
        )
        mei_alpha_v1.log_audit_event(
            sym,
            "LIVE_ORDER_SENT_OPEN",
            data={
                "signal": str(signal or "").upper(),
                "confidence": str(confidence or "").lower(),
                "px_est": float(fill_price_est),
                "size": float(size),
                "notional_est": float(notional),
                "leverage": float(leverage),
                "margin_est": float(margin_need),
                "size_multiplier": float(size_mult),
            },
        )

        _breadth_pct = None
        try:
            _breadth_pct = (indicators if indicators is not None else {}).get("_market_breadth_pct")
            if _breadth_pct is not None:
                _breadth_pct = float(_breadth_pct)
        except Exception:
            _breadth_pct = None

        self._push_pending(
            sym,
            {
                "action": "OPEN",
                "confidence": confidence,
                "entry_atr": float(atr or 0.0),
                "leverage": leverage,
                "reason": open_reason,
                "reason_code": kernel_reason_code or None,
                "breadth_pct": _breadth_pct,
                "meta": {
                    "audit": audit if isinstance(audit, dict) else None,
                    "breadth_pct": _breadth_pct,
                    "reason_code": kernel_reason_code or None,
                    "oms": (
                        {
                            "intent_id": getattr(oms_intent, "intent_id", None),
                            "client_order_id": getattr(oms_intent, "client_order_id", None),
                        }
                        if oms_intent is not None
                        else None
                    ),
                    "order": {
                        "kind": "OPEN",
                        "signal": str(signal or "").upper(),
                        "confidence": str(confidence or "").lower(),
                        "px_est": float(fill_price_est),
                        "size": float(size),
                        "notional_est": float(notional),
                        "leverage": float(leverage),
                        "margin_est": float(margin_need),
                    },
                },
            },
        )
        # Do not force a REST sync here: it can stall the decision loop. We rely on:
        # - WS fill ingestion (which triggers a forced sync), and
        # - periodic sync (AI_QUANT_LIVE_STATE_SYNC_SECS)
        # to pick up the position. Meanwhile, count this as a pending open so we don't exceed capacity.
        try:
            with self._pending_open_lock:
                self._pending_open_sent_at_s[sym] = time.time()
        except Exception as e:
            logger.debug("failed to record pending open timestamp for %s: %s", sym, e, exc_info=True)


_LIVE_TABLES_ENSURED = False


def _ensure_live_tables():
    """Ensure DB schema required for live audit tables.

    `mei_alpha_v1.ensure_db()` already creates `ws_events` and indexes, so avoid
    repeating DDL in hot paths (orderUpdates, ledger updates, etc).
    """
    global _LIVE_TABLES_ENSURED
    if _LIVE_TABLES_ENSURED:
        return
    mei_alpha_v1.ensure_db()
    _LIVE_TABLES_ENSURED = True


def _dir_to_action(dir_s: str, start_pos: float, sz: float) -> tuple[str | None, str]:
    d = str(dir_s or "").strip()
    dl = d.lower()
    if "long" in dl:
        pos_type = "LONG"
    elif "short" in dl:
        pos_type = "SHORT"
    else:
        pos_type = None

    action = "SYSTEM"
    if dl.startswith("open"):
        action = "OPEN" if abs(start_pos) < 1e-12 else "ADD"
    elif dl.startswith("close"):
        # Approx end position to decide CLOSE vs REDUCE.
        end_pos = start_pos
        if pos_type == "LONG":
            end_pos = start_pos - sz
        elif pos_type == "SHORT":
            end_pos = start_pos + sz
        action = "CLOSE" if abs(end_pos) < 1e-9 else "REDUCE"
    return pos_type, action


def process_user_fills(trader: LiveTrader, fills: list[dict]) -> int:
    """
    Persist live fills into the `trades` table (deduped by fill_hash+fill_tid when columns exist),
    and capture raw fill payload in `ws_events` for debugging.
    """
    if not fills:
        return 0

    _ensure_live_tables()

    inserted = 0
    run_fingerprint = _current_run_fingerprint()
    conn = sqlite3.connect(mei_alpha_v1.DB_PATH, timeout=_DB_TIMEOUT_S)
    try:
        cur = conn.cursor()

        # Best-effort: snapshot account value once to avoid repeated REST calls per fill.
        try:
            account_value = float(trader.get_live_balance() or 0.0)
        except Exception:
            account_value = 0.0

        # Best-effort: snapshot positions once for leverage fallback (helps when pending ctx is missing after restarts).
        try:
            pos_snap = trader.executor.get_positions(force=False) or {}
        except Exception:
            pos_snap = {}

        for _fill_i, f in enumerate(fills):
            if not isinstance(f, dict):
                continue

            try:
                sym = str(f.get("coin") or "").strip().upper()
            except Exception:
                sym = ""
            if not sym:
                continue

            try:
                tid = int(f.get("tid")) if f.get("tid") is not None else None
            except Exception:
                tid = None
            fill_hash = str(f.get("hash") or "").strip() or None

            try:
                t_ms = int(f.get("time"))
            except Exception:
                t_ms = int(time.time() * 1000)

            # Always capture raw events (useful for unknown schema variants).
            try:
                cur.execute(
                    "INSERT INTO ws_events (ts, channel, data_json) VALUES (?, ?, ?)",
                    (t_ms, "userFills", json.dumps(f, separators=(",", ":"), sort_keys=True)),
                )
            except Exception as e:
                logger.debug("failed to insert ws_events row for fill %s: %s", sym, e, exc_info=True)

            try:
                px = float(f.get("px") or 0.0)
                sz = float(f.get("sz") or 0.0)
            except Exception:
                continue
            if px <= 0 or sz <= 0:
                logger.warning("fill skipped: invalid px=%s sz=%s for %s", f.get("px"), f.get("sz"), sym)
                continue

            dir_s = str(f.get("dir") or "")
            try:
                start_pos = float(f.get("startPosition") or 0.0)
            except Exception:
                start_pos = 0.0

            pos_type, action = _dir_to_action(dir_s, start_pos, sz)
            if pos_type is None:
                # Unknown direction: still keep raw ws_events; skip trades row.
                logger.warning("fill skipped: unknown direction dir=%r for %s (px=%s sz=%s)", dir_s, sym, px, sz)
                continue

            fee = _safe_float(f.get("fee"), 0.0)
            closed_pnl = _safe_float(f.get("closedPnl"), 0.0)
            # Live: never simulate PnL. Persist the raw `closedPnl` reported by Hyperliquid,
            # and persist `fee` separately. (Different frontends may present "net" differently.)
            pnl = closed_pnl

            ctx = trader.pop_pending(sym) or {}
            conf = str(ctx.get("confidence") or "N/A")
            _ctx_breadth_pct = _safe_float(ctx.get("breadth_pct"), None)
            entry_atr = _safe_float(ctx.get("entry_atr"), None)
            lev = _safe_float(ctx.get("leverage"), None)
            if lev is None or lev <= 0:
                # Some HL fill payloads include leverage; accept both dict {value:..} and scalar.
                lev_raw = f.get("leverage")
                if isinstance(lev_raw, dict):
                    lev = _safe_float(lev_raw.get("value"), None)
                else:
                    lev = _safe_float(lev_raw, None)
            if lev is None or lev <= 0:
                try:
                    lev = _safe_float(((trader.positions or {}).get(sym) or {}).get("leverage"), None)
                except Exception:
                    lev = None
            if lev is None or lev <= 0:
                try:
                    lev = _safe_float((pos_snap.get(sym) or {}).get("leverage"), None)
                except Exception:
                    lev = None
            if lev is None or lev <= 0:
                # Fallback: best-effort from recent trades (helps when fills are backfilled after WS disconnect).
                try:
                    cur.execute(
                        """
                        SELECT leverage
                        FROM trades
                        WHERE symbol = ? AND leverage IS NOT NULL
                        ORDER BY id DESC
                        LIMIT 1
                        """,
                        (sym,),
                    )
                    row = cur.fetchone()
                    if row and row[0] is not None:
                        lev = _safe_float(row[0], None)
                except Exception:
                    lev = None

            notional = abs(sz) * px
            fee_token = str(f.get("feeToken") or "").strip() or None
            fee_rate = (fee / notional) if notional > 0 else None
            margin_used = (notional / lev) if lev and lev > 0 else None

            ts_iso = datetime.datetime.fromtimestamp(t_ms / 1000.0, tz=datetime.timezone.utc).isoformat()
            reason = str(ctx.get("reason") or f"LIVE_FILL {dir_s}").strip()
            meta = ctx.get("meta")
            reason_code = str(ctx.get("reason_code") or "").strip().lower()
            if not reason_code and isinstance(meta, dict):
                reason_code = str(meta.get("reason_code") or "").strip().lower()
            if not reason_code:
                reason_code = _canonical_reason_code(action, pos_type, reason)
            meta_json = mei_alpha_v1._json_dumps_safe(meta) if meta else None

            # Insert into trades if schema supports fill_hash/tid; otherwise best-effort insert (may duplicate).
            try:
                cur.execute("PRAGMA table_info(trades)")
                cols = {r[1] for r in cur.fetchall()}
            except Exception:
                cols = set()

            has_meta = "meta_json" in cols

            # Secondary dedup guard: REST backfill fills may have a different fill_hash than
            # the WS fill for the same logical execution.  Check if a trade with the same
            # (symbol, action, size, price) within a 1-second window already exists.
            try:
                ts_lo = datetime.datetime.fromtimestamp((t_ms - 1000) / 1000.0, tz=datetime.timezone.utc).isoformat()
                ts_hi = datetime.datetime.fromtimestamp((t_ms + 1000) / 1000.0, tz=datetime.timezone.utc).isoformat()
                cur.execute(
                    """
                    SELECT 1 FROM trades
                    WHERE symbol = ? AND action = ? AND ABS(size - ?) < 1e-12
                      AND ABS(price - ?) < 1e-8
                      AND timestamp >= ? AND timestamp <= ?
                    LIMIT 1
                    """,
                    (sym, action, sz, px, ts_lo, ts_hi),
                )
                if cur.fetchone() is not None:
                    continue
            except Exception as e:
                logger.debug("secondary fill dedup check failed for %s, falling through: %s", sym, e, exc_info=True)

            if {"fill_hash", "fill_tid"}.issubset(cols):
                # Dedup at DB level via a unique index (added by mei_alpha_v1.ensure_db() migration).
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
                            px,
                            sz,
                            notional,
                            reason,
                            conf,
                            reason_code,
                            pnl,
                            fee,
                            fee_token,
                            fee_rate,
                            account_value,
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
                            px,
                            sz,
                            notional,
                            reason,
                            conf,
                            reason_code,
                            pnl,
                            fee,
                            fee_token,
                            fee_rate,
                            account_value,
                            entry_atr,
                            lev,
                            margin_used,
                            run_fingerprint,
                            fill_hash,
                            tid,
                        ),
                    )
                if cur.rowcount and cur.rowcount > 0:
                    inserted += 1
                    _notify_live_fill(
                        symbol=sym,
                        action=action,
                        pos_type=pos_type,
                        price=px,
                        size=sz,
                        notional=notional,
                        leverage=lev,
                        margin_used_usd=margin_used,
                        fee_usd=fee,
                        fee_rate=fee_rate,
                        fee_token=fee_token,
                        pnl_usd=pnl,
                        reason=reason,
                        confidence=conf,
                        account_value_usd=float(account_value or 0.0),
                        withdrawable_usd=float(trader.balance or 0.0),
                        breadth_pct=_ctx_breadth_pct,
                    )
                    # Best-effort risk update (daily loss tracking, etc).
                    try:
                        risk = getattr(trader, "risk", None)
                        note = getattr(risk, "note_fill", None) if risk is not None else None
                        if callable(note):
                            fill_side = None
                            try:
                                dl = str(dir_s or "").strip().lower()
                                if dl.startswith("open") and "long" in dl:
                                    fill_side = "BUY"
                                elif dl.startswith("open") and "short" in dl:
                                    fill_side = "SELL"
                                elif dl.startswith("close") and "long" in dl:
                                    fill_side = "SELL"
                                elif dl.startswith("close") and "short" in dl:
                                    fill_side = "BUY"
                            except Exception:
                                fill_side = None

                            ref_mid = None
                            ref_bid = None
                            ref_ask = None
                            try:
                                bbo = hyperliquid_ws.hl_ws.get_bbo(sym, max_age_s=10.0)
                                if bbo is not None:
                                    ref_bid, ref_ask = float(bbo[0]), float(bbo[1])
                                ref_mid = hyperliquid_ws.hl_ws.get_mid(sym, max_age_s=10.0)
                                if ref_mid is not None:
                                    ref_mid = float(ref_mid)
                            except Exception:
                                ref_mid = None
                                ref_bid = None
                                ref_ask = None

                            note(
                                ts_ms=int(t_ms),
                                symbol=str(sym),
                                action=str(action),
                                pnl_usd=float(pnl or 0.0),
                                fee_usd=float(fee or 0.0),
                                fill_price=float(px),
                                side=str(fill_side or ""),
                                ref_mid=ref_mid,
                                ref_bid=ref_bid,
                                ref_ask=ref_ask,
                            )
                    except Exception as e:
                        logger.debug("failed to call risk.note_fill for %s (deduped path): %s", sym, e, exc_info=True)
                    try:
                        lev_s = "NA" if lev is None or lev <= 0 else f"{float(lev):.0f}x"
                    except Exception:
                        lev_s = "NA"
                    try:
                        margin_s = "NA" if margin_used is None else f"${float(margin_used):.2f}"
                    except Exception:
                        margin_s = "NA"
                    print(
                        f"📥 LIVE FILL {action} {pos_type} {sym} px={px:.4f} size={sz:.6f} notional=${notional:.2f} "
                        f"lev={lev_s} margin~={margin_s} fee=${fee:.4f} pnl=${pnl:.2f} conf={conf} reason={reason}"
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
                            px,
                            sz,
                            notional,
                            reason,
                            conf,
                            reason_code,
                            pnl,
                            fee,
                            fee_token,
                            fee_rate,
                            account_value,
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
                            px,
                            sz,
                            notional,
                            reason,
                            conf,
                            reason_code,
                            pnl,
                            fee,
                            fee_token,
                            fee_rate,
                            account_value,
                            entry_atr,
                            lev,
                            margin_used,
                            run_fingerprint,
                        ),
                    )
                inserted += 1
                _notify_live_fill(
                    symbol=sym,
                    action=action,
                    pos_type=pos_type,
                    price=px,
                    size=sz,
                    notional=notional,
                    leverage=lev,
                    margin_used_usd=margin_used,
                    fee_usd=fee,
                    fee_rate=fee_rate,
                    fee_token=fee_token,
                    pnl_usd=pnl,
                    reason=reason,
                    confidence=conf,
                    account_value_usd=float(account_value or 0.0),
                    withdrawable_usd=float(trader.balance or 0.0),
                    breadth_pct=_ctx_breadth_pct,
                )
                # Best-effort risk update (daily loss tracking, etc).
                try:
                    risk = getattr(trader, "risk", None)
                    note = getattr(risk, "note_fill", None) if risk is not None else None
                    if callable(note):
                        fill_side = None
                        try:
                            dl = str(dir_s or "").strip().lower()
                            if dl.startswith("open") and "long" in dl:
                                fill_side = "BUY"
                            elif dl.startswith("open") and "short" in dl:
                                fill_side = "SELL"
                            elif dl.startswith("close") and "long" in dl:
                                fill_side = "SELL"
                            elif dl.startswith("close") and "short" in dl:
                                fill_side = "BUY"
                        except Exception:
                            fill_side = None

                        ref_mid = None
                        ref_bid = None
                        ref_ask = None
                        try:
                            bbo = hyperliquid_ws.hl_ws.get_bbo(sym, max_age_s=10.0)
                            if bbo is not None:
                                ref_bid, ref_ask = float(bbo[0]), float(bbo[1])
                            ref_mid = hyperliquid_ws.hl_ws.get_mid(sym, max_age_s=10.0)
                            if ref_mid is not None:
                                ref_mid = float(ref_mid)
                        except Exception:
                            ref_mid = None
                            ref_bid = None
                            ref_ask = None

                        note(
                            ts_ms=int(t_ms),
                            symbol=str(sym),
                            action=str(action),
                            pnl_usd=float(pnl or 0.0),
                            fee_usd=float(fee or 0.0),
                            fill_price=float(px),
                            side=str(fill_side or ""),
                            ref_mid=ref_mid,
                            ref_bid=ref_bid,
                            ref_ask=ref_ask,
                        )
                except Exception as e:
                    logger.debug("failed to call risk.note_fill for %s (insert path): %s", sym, e, exc_info=True)
                try:
                    lev_s = "NA" if lev is None or lev <= 0 else f"{float(lev):.0f}x"
                except Exception:
                    lev_s = "NA"
                try:
                    margin_s = "NA" if margin_used is None else f"${float(margin_used):.2f}"
                except Exception:
                    margin_s = "NA"
                print(
                    f"📥 LIVE FILL {action} {pos_type} {sym} px={px:.4f} size={sz:.6f} notional=${notional:.2f} "
                    f"lev={lev_s} margin~={margin_s} fee=${fee:.4f} pnl=${pnl:.2f} conf={conf} reason={reason}"
                )

            # Update in-memory strategy state on opens (so exits have correct entry_atr/confidence immediately).
            if action == "OPEN" and sym in (trader.positions or {}):
                pos = trader.positions[sym]
                pos["confidence"] = conf
                if entry_atr is not None and entry_atr > 0:
                    pos["entry_atr"] = entry_atr
                pos["open_timestamp"] = ts_iso
                try:
                    cur.execute("SELECT id FROM trades WHERE fill_hash = ? AND fill_tid = ? LIMIT 1", (fill_hash, tid))
                    row = cur.fetchone()
                    if row and row[0]:
                        pos["open_trade_id"] = int(row[0])
                        trader.upsert_position_state(sym)
                except Exception as e:
                    logger.debug("failed to update open_trade_id for %s: %s", sym, e, exc_info=True)

            if (_fill_i + 1) % 100 == 0:
                conn.commit()

        conn.commit()
    finally:
        conn.close()
    return inserted


def process_ws_events(channel: str, events: list[dict]) -> int:
    if not events:
        return 0
    _ensure_live_tables()
    conn = sqlite3.connect(mei_alpha_v1.DB_PATH, timeout=_DB_TIMEOUT_S)
    try:
        cur = conn.cursor()
        n = 0
        for ev in events:
            if not isinstance(ev, dict):
                continue
            ts = int((ev.get("t") or time.time()) * 1000)
            data = ev.get("data")
            try:
                cur.execute(
                    "INSERT INTO ws_events (ts, channel, data_json) VALUES (?, ?, ?)",
                    (ts, channel, json.dumps(data, separators=(",", ":"), sort_keys=True)),
                )
                n += 1
            except Exception:
                continue
        conn.commit()
    finally:
        conn.close()
    return n


def process_user_fundings(trader: LiveTrader, events: list[dict]) -> int:
    """
    Persist live perps funding cashflows into `trades` as action='FUNDING' (deduped via fill_hash+fill_tid),
    and capture raw payloads in `ws_events` via process_ws_events().

    Hyperliquid funding (perps) is paid hourly. The WS payload includes the realized USDC delta, so we do NOT
    simulate funding amounts here.
    """
    if not events:
        return 0

    # First capture the raw events for debugging/audit.
    process_ws_events("userFundings", events)

    _ensure_live_tables()
    conn = sqlite3.connect(mei_alpha_v1.DB_PATH, timeout=_DB_TIMEOUT_S)
    try:
        cur = conn.cursor()

        try:
            cur.execute("PRAGMA table_info(trades)")
            cols = {r[1] for r in cur.fetchall()}
        except Exception:
            cols = set()

        supports_dedupe = {"fill_hash", "fill_tid"}.issubset(cols)
        has_meta = "meta_json" in cols

        # Snapshot account value once.
        try:
            account_value = float(trader.get_live_balance() or 0.0)
        except Exception:
            account_value = 0.0

        inserted = 0
        run_fingerprint = _current_run_fingerprint()

        def _iter_funding_items() -> list[dict]:
            items: list[dict] = []
            for ev in events:
                if not isinstance(ev, dict):
                    continue
                data = ev.get("data")
                if data is None:
                    continue

                # Expected shape: { user, isSnapshot?, fundings: [...] }
                if isinstance(data, dict):
                    fundings = data.get("fundings")
                    if isinstance(fundings, list):
                        for f in fundings:
                            if isinstance(f, dict):
                                items.append(f)
                        continue
                    # Fallback: data itself might be a single funding item.
                    if {"time", "coin", "usdc"}.issubset(set(data.keys())):
                        items.append(data)
                        continue

                # Fallback: raw list of funding items.
                if isinstance(data, list):
                    for f in data:
                        if isinstance(f, dict):
                            items.append(f)

            return items

        for f in _iter_funding_items():
            try:
                sym = str(f.get("coin") or "").strip().upper()
            except Exception:
                sym = ""
            if not sym:
                continue

            try:
                t_ms = int(f.get("time"))
            except Exception:
                t_ms = int(time.time() * 1000)

            usdc_delta = _safe_float(f.get("usdc"), None)
            if usdc_delta is None:
                continue

            szi = _safe_float(f.get("szi"), 0.0) or 0.0
            pos_type = "LONG" if szi > 0 else ("SHORT" if szi < 0 else "N/A")
            size = abs(float(szi))

            rate = _safe_float(f.get("fundingRate"), None)
            rate_s = "NA" if rate is None else f"{rate:+.10f}"
            reason = f"Live Funding (rate={rate_s})"
            reason_code = _canonical_reason_code("FUNDING", pos_type, reason)

            # Best-effort price/notional (optional). This does NOT affect pnl because pnl is the realized USDC delta.
            mid = hyperliquid_ws.hl_ws.get_mid(sym, max_age_s=60.0)
            px = float(mid) if mid is not None else 0.0
            notional = (size * px) if (size > 0 and px > 0) else 0.0

            ts_iso = datetime.datetime.fromtimestamp(t_ms / 1000.0, tz=datetime.timezone.utc).isoformat()
            meta_json = None
            if has_meta:
                meta_json = mei_alpha_v1._json_dumps_safe(
                    {
                        "funding_rate": None if rate is None else float(rate),
                        "delta_usdc": float(usdc_delta),
                        "szi": float(szi),
                        "event_time_ms": int(t_ms),
                    }
                )

            if supports_dedupe:
                fill_hash = f"funding:{sym}:{t_ms}"
                fill_tid = 0
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
                            "FUNDING",
                            px,
                            size,
                            notional,
                            reason,
                            "N/A",
                            reason_code,
                            usdc_delta,
                            0.0,
                            "USDC",
                            0.0,
                            account_value,
                            None,
                            None,
                            None,
                            meta_json,
                            run_fingerprint,
                            fill_hash,
                            fill_tid,
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
                            "FUNDING",
                            px,
                            size,
                            notional,
                            reason,
                            "N/A",
                            reason_code,
                            usdc_delta,
                            0.0,
                            "USDC",
                            0.0,
                            account_value,
                            None,
                            None,
                            None,
                            run_fingerprint,
                            fill_hash,
                            fill_tid,
                        ),
                    )
                if cur.rowcount and cur.rowcount > 0:
                    inserted += 1
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
                            "FUNDING",
                            px,
                            size,
                            notional,
                            reason,
                            "N/A",
                            reason_code,
                            usdc_delta,
                            0.0,
                            "USDC",
                            0.0,
                            account_value,
                            None,
                            None,
                            None,
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
                            "FUNDING",
                            px,
                            size,
                            notional,
                            reason,
                            "N/A",
                            reason_code,
                            usdc_delta,
                            0.0,
                            "USDC",
                            0.0,
                            account_value,
                            None,
                            None,
                            None,
                            run_fingerprint,
                        ),
                    )
                inserted += 1

            # Keep local state in sync (useful for funding-duration heuristics in shared exit logic).
            if sym in (trader.positions or {}):
                try:
                    trader.positions[sym]["last_funding_time"] = int(t_ms)
                    trader.upsert_position_state(sym)
                except Exception as e:
                    logger.debug("failed to update last_funding_time for %s: %s", sym, e, exc_info=True)

        conn.commit()
    finally:
        conn.close()
    return inserted


def log_live_signal(*, symbol: str, signal: str, confidence: str, price: float, indicators: dict | None) -> None:
    """
    Live-only audit trail: persist non-neutral signals into the live DB.

    Why:
    - Live trades may be rare, and without signal logging it's hard to verify the bot is evaluating correctly.
    - This table already exists in `mei_alpha_v1.ensure_db()`; we only write when signal != NEUTRAL.
    """
    try:
        sig = str(signal or "").strip().upper()
    except Exception:
        sig = ""
    if sig not in {"BUY", "SELL"}:
        return

    sym = str(symbol or "").strip().upper()
    if not sym:
        return

    try:
        px = float(price)
    except Exception:
        px = 0.0

    rsi = None
    ema_fast = None
    ema_slow = None
    if indicators is not None:
        try:
            rsi = float(indicators.get("RSI")) if indicators.get("RSI") is not None else None
        except Exception:
            rsi = None
        try:
            ema_fast = float(indicators.get("EMA_fast")) if indicators.get("EMA_fast") is not None else None
        except Exception:
            ema_fast = None
        try:
            ema_slow = float(indicators.get("EMA_slow")) if indicators.get("EMA_slow") is not None else None
        except Exception:
            ema_slow = None
    audit = None
    if indicators is not None:
        try:
            audit = indicators.get("audit")
        except Exception:
            audit = None
    meta_json = mei_alpha_v1._json_dumps_safe(audit) if isinstance(audit, dict) and audit else None

    conn = None
    try:
        # Signal logging is observability only; keep sqlite busy waits short.
        try:
            timeout_s = float(
                os.getenv("AI_QUANT_SIGNAL_DB_TIMEOUT_S", os.getenv("AI_QUANT_AUDIT_DB_TIMEOUT_S", "0.2"))
            )
        except Exception:
            timeout_s = 0.2
        timeout_s = float(max(0.01, min(2.0, timeout_s)))

        # Avoid ensure_db() here (may take schema locks). The live daemon initializes schema on startup.
        conn = sqlite3.connect(mei_alpha_v1.DB_PATH, timeout=timeout_s)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO signals (timestamp, symbol, signal, confidence, price, rsi, ema_fast, ema_slow, meta_json, run_fingerprint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utc_iso(),
                sym,
                sig,
                str(confidence or "").strip().lower() or "low",
                px,
                rsi,
                ema_fast,
                ema_slow,
                meta_json,
                _current_run_fingerprint(),
            ),
        )
        conn.commit()
    except Exception as e:
        logger.debug("failed to insert live signal into db: %s", e, exc_info=True)
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception as e:
            logger.debug("failed to close sqlite connection: %s", e, exc_info=True)


def run_trader():
    raise SystemExit("Deprecated: use `python -m engine.daemon` with AI_QUANT_MODE=live or AI_QUANT_MODE=dry_live.")
