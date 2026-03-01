#!/usr/bin/env python3
"""Manual trade CLI — spawned by the hub as a subprocess.

Accepts JSON-compatible CLI args, loads secrets, initialises executor + OMS,
and returns a single JSON object on stdout.  All progress/log info goes to
stderr so the Rust parent can reliably parse stdout.

Actions:
    preview      — fetch mid price, validate, compute estimated size/margin/fees
    execute      — create OMS intent, set leverage, submit order
    close        — fetch exchange position, submit reduce-only order
    cancel       — cancel a GTC order by intent_id (via executor.cancel_order)
    open-orders  — list current open GTC orders from exchange for a symbol
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Bootstrap: ensure project root is importable
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

# Configure logging to stderr only — stdout is reserved for JSON output.
logging.basicConfig(
    level=logging.INFO,
    format="[manual_trade] %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("manual_trade")

# ---------------------------------------------------------------------------
# Lazy imports (deferred so --help is fast and syntax-check doesn't need deps)
# ---------------------------------------------------------------------------

_executor_mod = None
_meta_mod = None
_oms_mod = None


def _load_modules() -> None:
    global _executor_mod, _meta_mod, _oms_mod
    if _executor_mod is None:
        from exchange import executor as _ex, meta as _me  # type: ignore
        from engine import oms as _om  # type: ignore

        _executor_mod = _ex
        _meta_mod = _me
        _oms_mod = _om


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_SECRETS_PATH = Path(
    os.getenv("AI_QUANT_SECRETS_PATH") or "~/.config/openclaw/ai-quant-secrets.json"
).expanduser()

# Hyperliquid taker fee (worst-case estimate for preview).
_HL_TAKER_FEE_BPS = 3.5  # 0.035%

# Manual-trade CLOID prefix (distinct from automated "aiq_").
_CLOID_PREFIX = "man_"

# Manual-trade OMS intent_id prefix.
_INTENT_PREFIX = "manual_"

# Default market-order slippage.
_DEFAULT_SLIPPAGE_PCT = 0.01  # 1%

# Maximum notional per manual trade (env-configurable safety cap).
_MAX_NOTIONAL_USD = float(os.getenv("AI_QUANT_MANUAL_MAX_NOTIONAL_USD", "5000"))


def _check_hard_kill_switch() -> str | None:
    """Return error message if hard kill switch is active, else None."""
    if os.getenv("AI_QUANT_HARD_KILL_SWITCH", "").strip().lower() in ("1", "true", "yes"):
        return "Live trading halted: AI_QUANT_HARD_KILL_SWITCH is active"
    return None


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ok(payload: dict[str, Any]) -> dict[str, Any]:
    payload.setdefault("ok", True)
    return payload


def _err(msg: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": str(msg), **extra}


def _emit(result: dict[str, Any]) -> None:
    """Write JSON result to stdout and exit."""
    json.dump(result, sys.stdout, separators=(",", ":"), default=str)
    sys.stdout.write("\n")
    sys.stdout.flush()


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------


def _ensure_audit_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            event TEXT,
            level TEXT,
            data_json TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_ts ON audit_events(timestamp)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_events_symbol_ts ON audit_events(symbol, timestamp)"
    )
    conn.commit()


def _write_audit(db_path: str, *, event: str, symbol: str, details: dict[str, Any]) -> None:
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        try:
            _ensure_audit_table(conn)
            conn.execute(
                "INSERT INTO audit_events (timestamp, symbol, event, level, data_json) VALUES (?, ?, ?, ?, ?)",
                (
                    _utc_iso(),
                    symbol,
                    event,
                    "INFO",
                    json.dumps(details, separators=(",", ":"), default=str),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("failed to write audit event: %s", exc)


# ---------------------------------------------------------------------------
# Fill polling + record writing
# ---------------------------------------------------------------------------

# Map HL direction string → (pos_type, action).
_DIR_MAP: dict[str, tuple[str, str]] = {
    "open long": ("LONG", "OPEN"),
    "close long": ("LONG", "CLOSE"),
    "open short": ("SHORT", "OPEN"),
    "close short": ("SHORT", "CLOSE"),
}


def _dir_to_pos_action(dir_s: str, start_pos: float) -> tuple[str, str]:
    """Convert HL fill direction to (pos_type, action).

    Handles HL formats: "Open Long", "openLong", "close short", etc.
    """
    # Split camelCase ("openLong" → "open Long"), then lowercase + normalise whitespace.
    key = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", dir_s.strip()).lower()
    key = " ".join(key.split())

    base = _DIR_MAP.get(key)
    if base is None:
        return ("UNKNOWN", "UNKNOWN")
    pt, act = base
    # Distinguish OPEN/ADD and CLOSE/REDUCE based on existing position.
    if act == "OPEN" and abs(start_pos) > 1e-12:
        return (pt, "ADD")
    if act == "CLOSE" and abs(start_pos) > 1e-12:
        return (pt, "REDUCE")
    return (pt, act)


def _action_side(pos_type: str, action: str) -> str:
    if pos_type == "LONG":
        return "BUY" if action in ("OPEN", "ADD") else "SELL"
    else:
        return "SELL" if action in ("OPEN", "ADD") else "BUY"


def _poll_fill(
    executor: Any,
    cloid: str,
    symbol: str,
    start_ms: int,
    *,
    max_wait_s: float = 8.0,
    poll_interval_s: float = 0.8,
) -> dict[str, Any] | None:
    """Poll exchange for a fill matching our CLOID.  Returns raw fill dict or None."""
    import time as _time

    deadline = _time.monotonic() + max_wait_s
    while _time.monotonic() < deadline:
        _time.sleep(poll_interval_s)
        now_ms = int(_time.time() * 1000)
        try:
            fills = executor._info.user_fills_by_time(
                executor.main_address, start_ms, now_ms,
                aggregate_by_time=False,
            ) or []
        except Exception as exc:
            logger.warning("fill poll error: %s", exc)
            continue
        for f in fills:
            if not isinstance(f, dict):
                continue
            f_cloid = str(f.get("cloid") or "").strip()
            if f_cloid and f_cloid == cloid:
                return f
            # Also match by coin if cloid not present in fill
            f_coin = str(f.get("coin") or "").strip().upper()
            f_oid = str(f.get("oid") or "")
            if f_coin == symbol and f_oid:
                # Check order status by oid to see if it matches our cloid
                # (fallback for exchanges that don't echo cloid in fills)
                pass
        # For market/IOC orders, if we see ANY fill for the symbol after our
        # submission time, it's very likely ours — but we only trust cloid match.
    return None


def _ensure_oms_fills_table(conn: sqlite3.Connection) -> None:
    conn.execute(
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
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_oms_fills_hash_tid ON oms_fills(fill_hash, fill_tid)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_oms_fills_intent ON oms_fills(intent_id)"
    )
    conn.commit()


def _ensure_trades_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            type TEXT,
            action TEXT,
            price REAL,
            size REAL,
            notional REAL,
            reason TEXT,
            confidence TEXT,
            pnl REAL,
            fee_usd REAL,
            fee_token TEXT,
            fee_rate REAL,
            balance REAL,
            entry_atr REAL,
            leverage REAL,
            margin_used REAL,
            meta_json TEXT,
            fill_hash TEXT,
            fill_tid INTEGER
        )
        """
    )
    conn.commit()


def _record_fill(
    db_path: str,
    *,
    fill: dict[str, Any],
    intent_id: str,
    cloid: str,
    leverage: float,
    account_value: float,
) -> None:
    """Write oms_fills + trades records from a raw exchange fill."""
    sym = str(fill.get("coin") or "").strip().upper()
    t_ms = int(fill.get("time") or 0)
    tid = fill.get("tid")
    fill_hash = str(fill.get("hash") or "").strip() or None
    px = _safe_float(fill.get("px"))
    sz = _safe_float(fill.get("sz"))
    fee = _safe_float(fill.get("fee"))
    fee_token = str(fill.get("feeToken") or "").strip() or None
    closed_pnl = _safe_float(fill.get("closedPnl"))
    dir_s = str(fill.get("dir") or "")
    start_pos = _safe_float(fill.get("startPosition"))
    oid = fill.get("oid")

    pos_type, action = _dir_to_pos_action(dir_s, start_pos)
    side = _action_side(pos_type, action)
    notional = abs(sz) * px if px > 0 else 0.0
    fee_rate = (fee / notional) if notional > 0 else 0.0
    margin_used = (notional / leverage) if leverage > 0 else None

    ts_iso = datetime.fromtimestamp(t_ms / 1000, tz=timezone.utc).isoformat() if t_ms else _utc_iso()

    meta = json.dumps(
        {
            "source": "manual_trade",
            "intent_id": intent_id,
            "cloid": cloid,
            "fill": fill,
        },
        separators=(",", ":"),
        default=str,
    )

    try:
        conn = sqlite3.connect(db_path, timeout=5)
        try:
            _ensure_oms_fills_table(conn)
            conn.execute(
                """INSERT OR IGNORE INTO oms_fills
                   (ts_ms, symbol, intent_id, order_id, action, side, pos_type,
                    price, size, notional, fee_usd, fee_token, fee_rate, pnl_usd,
                    fill_hash, fill_tid, matched_via, raw_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    t_ms, sym, intent_id, oid, action, side, pos_type,
                    px, sz, notional, fee, fee_token, fee_rate, closed_pnl,
                    fill_hash, tid, "cloid", meta,
                ),
            )

            _ensure_trades_table(conn)
            if fill_hash is not None and tid is not None:
                conn.execute(
                    """INSERT OR IGNORE INTO trades
                       (timestamp, symbol, type, action, price, size, notional,
                        reason, confidence, pnl, fee_usd, fee_token, fee_rate,
                        balance, entry_atr, leverage, margin_used,
                        meta_json, fill_hash, fill_tid)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        ts_iso, sym, pos_type, action, px, sz, notional,
                        "manual_trade", "MANUAL", closed_pnl, fee, fee_token, fee_rate,
                        account_value, None, leverage, margin_used,
                        meta, fill_hash, tid,
                    ),
                )
            else:
                conn.execute(
                    """INSERT INTO trades
                       (timestamp, symbol, type, action, price, size, notional,
                        reason, confidence, pnl, fee_usd, fee_token, fee_rate,
                        balance, entry_atr, leverage, margin_used, meta_json)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        ts_iso, sym, pos_type, action, px, sz, notional,
                        "manual_trade", "MANUAL", closed_pnl, fee, fee_token, fee_rate,
                        account_value, None, leverage, margin_used, meta,
                    ),
                )
            conn.commit()
            logger.info("Recorded fill: %s %s %s sz=%.6f px=%.4f pnl=%.2f", sym, pos_type, action, sz, px, closed_pnl)
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("failed to record fill: %s", exc)


# ---------------------------------------------------------------------------
# Build executor + OMS helpers
# ---------------------------------------------------------------------------


def _build_executor(secrets_path: str) -> Any:
    _load_modules()
    secrets = _executor_mod.load_live_secrets(secrets_path)
    return _executor_mod.HyperliquidLiveExecutor(
        secret_key=secrets.secret_key,
        main_address=secrets.main_address,
    )


def _build_oms_store(db_path: str) -> Any:
    _load_modules()
    store = _oms_mod.OmsStore(db_path=db_path)
    store.ensure()
    return store


# ---------------------------------------------------------------------------
# Action: preview
# ---------------------------------------------------------------------------


def _action_preview(args: argparse.Namespace) -> dict[str, Any]:
    _load_modules()
    executor = _build_executor(args.secrets_path)

    symbol = str(args.symbol).strip().upper()
    side = str(args.side).strip().upper()
    notional = float(args.notional)
    leverage = int(args.leverage)
    order_type = str(args.order_type).strip().lower()

    # Validate
    if side not in ("BUY", "SELL"):
        return _err(f"Invalid side: {side}")
    if notional < 10:
        return _err("Minimum notional is $10 USD")
    if leverage < 1 or leverage > 50:
        return _err("Leverage must be between 1 and 50")

    # Check max leverage for this symbol
    max_lev = _meta_mod.max_leverage(symbol, notional)
    if max_lev is not None and leverage > max_lev:
        return _err(
            f"Leverage {leverage}x exceeds max {max_lev:.0f}x for {symbol} at ${notional:.0f} notional"
        )

    # Fetch mid price
    mids = executor._info.all_mids() or {}
    mid_price = _safe_float(mids.get(symbol), 0.0)
    if mid_price <= 0:
        return _err(f"Could not fetch mid price for {symbol}")

    # Compute size
    sz_decimals = _meta_mod.get_sz_decimals(symbol)
    raw_size = notional / mid_price
    est_size = _meta_mod.round_size(symbol, raw_size)
    if est_size <= 0:
        # Try rounding up (for small notionals at szDecimals boundary)
        est_size = _meta_mod.round_size_up(symbol, raw_size)
    if est_size <= 0:
        return _err(f"Computed size is zero for {symbol} at ${notional:.2f} / ${mid_price:.4f}")

    est_notional = est_size * mid_price
    est_margin = est_notional / leverage
    est_fee = est_notional * (_HL_TAKER_FEE_BPS / 10_000)

    # Account value
    snap = executor.account_snapshot(force=True)
    account_value = snap.account_value_usd

    # Direction
    direction = "LONG" if side == "BUY" else "SHORT"

    # If limit order, include the limit_price in preview
    result: dict[str, Any] = {
        "action": "preview",
        "symbol": symbol,
        "side": side,
        "direction": direction,
        "order_type": order_type,
        "mid_price": mid_price,
        "est_size": est_size,
        "est_notional_usd": round(est_notional, 2),
        "est_margin_usd": round(est_margin, 2),
        "est_fee_usd": round(est_fee, 2),
        "leverage": leverage,
        "max_leverage": max_lev,
        "account_value_usd": round(account_value, 2),
        "sz_decimals": sz_decimals,
    }

    if order_type in ("limit_ioc", "limit_gtc") and args.limit_price is not None:
        result["limit_price"] = float(args.limit_price)

    return _ok(result)


# ---------------------------------------------------------------------------
# Action: execute
# ---------------------------------------------------------------------------


def _action_execute(args: argparse.Namespace) -> dict[str, Any]:
    # Safety: check hard kill switch before any exchange interaction.
    kill = _check_hard_kill_switch()
    if kill:
        return _err(kill)

    _load_modules()
    executor = _build_executor(args.secrets_path)
    store = _build_oms_store(args.db_path)

    symbol = str(args.symbol).strip().upper()
    side = str(args.side).strip().upper()
    notional = float(args.notional)
    leverage = int(args.leverage)
    order_type = str(args.order_type).strip().lower()

    # Validate
    if side not in ("BUY", "SELL"):
        return _err(f"Invalid side: {side}")
    if notional < 10:
        return _err("Minimum notional is $10 USD")
    if notional > _MAX_NOTIONAL_USD:
        return _err(f"Notional ${notional:.0f} exceeds max ${_MAX_NOTIONAL_USD:.0f} (AI_QUANT_MANUAL_MAX_NOTIONAL_USD)")
    if leverage < 1 or leverage > 50:
        return _err("Leverage must be between 1 and 50")

    max_lev = _meta_mod.max_leverage(symbol, notional)
    if max_lev is not None and leverage > max_lev:
        return _err(
            f"Leverage {leverage}x exceeds max {max_lev:.0f}x for {symbol} at ${notional:.0f} notional"
        )

    # Fetch mid price
    mids = executor._info.all_mids() or {}
    mid_price = _safe_float(mids.get(symbol), 0.0)
    if mid_price <= 0:
        return _err(f"Could not fetch mid price for {symbol}")

    # Compute size
    raw_size = notional / mid_price
    est_size = _meta_mod.round_size(symbol, raw_size)
    if est_size <= 0:
        est_size = _meta_mod.round_size_up(symbol, raw_size)
    if est_size <= 0:
        return _err(f"Computed size is zero for {symbol}")

    direction = "LONG" if side == "BUY" else "SHORT"
    is_buy = side == "BUY"

    # Create OMS intent
    intent_id = _INTENT_PREFIX + uuid.uuid4().hex
    cloid = _oms_mod._make_hl_cloid(seed_hex=intent_id.replace(_INTENT_PREFIX, ""), prefix=_CLOID_PREFIX)
    created_ms = int(time.time() * 1000)

    meta_json = json.dumps(
        {
            "source": "manual_trade",
            "order_type": order_type,
            "confirm_token": getattr(args, "confirm_token", None),
        },
        separators=(",", ":"),
        default=str,
    )

    store.insert_intent(
        intent_id=intent_id,
        client_order_id=cloid,
        created_ts_ms=created_ms,
        symbol=symbol,
        action="OPEN",
        side=side,
        requested_size=est_size,
        requested_notional=notional,
        entry_atr=None,
        leverage=float(leverage),
        decision_ts_ms=created_ms,
        strategy_version=None,
        strategy_sha1=None,
        reason="manual_trade",
        confidence="MANUAL",
        status="NEW",
        dedupe_key=None,
        meta_json=meta_json,
    )

    logger.info("Created OMS intent %s for %s %s %s sz=%.6f", intent_id, side, symbol, order_type, est_size)

    # Set leverage
    lev_ok = executor.update_leverage(symbol, leverage)
    if not lev_ok:
        store.update_intent(intent_id, status="REJECTED", last_error="leverage update failed")
        return _err(f"Failed to set leverage to {leverage}x for {symbol}", intent_id=intent_id)

    # Submit order
    result_raw: dict | None = None
    oms_status = "SENT"
    submit_ms = int(time.time() * 1000)

    if order_type == "market":
        result_raw = executor.market_open(
            symbol,
            is_buy=is_buy,
            sz=est_size,
            slippage_pct=_DEFAULT_SLIPPAGE_PCT,
            cloid=cloid,
        )
    elif order_type == "limit_ioc":
        if args.limit_price is None:
            store.update_intent(intent_id, status="REJECTED", last_error="limit_price required for limit_ioc")
            return _err("limit_price is required for limit_ioc orders", intent_id=intent_id)
        limit_px = float(args.limit_price)
        cloid_obj = _make_cloid_obj(cloid)
        result_raw = executor._exchange.order(
            symbol,
            is_buy=is_buy,
            sz=est_size,
            limit_px=limit_px,
            order_type={"limit": {"tif": "Ioc"}},
            reduce_only=False,
            cloid=cloid_obj,
        )
    elif order_type == "limit_gtc":
        if args.limit_price is None:
            store.update_intent(intent_id, status="REJECTED", last_error="limit_price required for limit_gtc")
            return _err("limit_price is required for limit_gtc orders", intent_id=intent_id)
        limit_px = float(args.limit_price)
        cloid_obj = _make_cloid_obj(cloid)
        result_raw = executor._exchange.order(
            symbol,
            is_buy=is_buy,
            sz=est_size,
            limit_px=limit_px,
            order_type={"limit": {"tif": "Gtc"}},
            reduce_only=False,
            cloid=cloid_obj,
        )
    else:
        store.update_intent(intent_id, status="REJECTED", last_error=f"unknown order_type: {order_type}")
        return _err(f"Unknown order_type: {order_type}", intent_id=intent_id)

    if result_raw is None or not _executor_mod._is_ok_response(result_raw):
        err_msg = "Order rejected by exchange"
        if result_raw is not None:
            err_msg += f": {result_raw}"
        store.update_intent(intent_id, status="REJECTED", last_error=err_msg[:500])
        return _err(err_msg, intent_id=intent_id, action="execute")

    # Extract exchange order id
    exchange_order_id = _extract_exchange_oid(result_raw)

    # Update OMS
    store.update_intent(
        intent_id,
        status="SENT",
        sent_ts_ms=int(time.time() * 1000),
        exchange_order_id=exchange_order_id,
    )

    # Write audit event
    _write_audit(
        args.db_path,
        event="MANUAL_OPEN",
        symbol=symbol,
        details={
            "intent_id": intent_id,
            "side": side,
            "direction": direction,
            "order_type": order_type,
            "notional_usd": notional,
            "size": est_size,
            "leverage": leverage,
            "mid_price": mid_price,
            "exchange_order_id": exchange_order_id,
            "cloid": cloid,
        },
    )

    # Poll for fill confirmation
    # Market/IOC: should fill immediately — poll up to 8s
    # GTC: may not fill — brief 3s check, leave as SENT if unfilled
    is_gtc = order_type == "limit_gtc"
    poll_wait = 3.0 if is_gtc else 8.0
    fill = _poll_fill(executor, cloid, symbol, submit_ms, max_wait_s=poll_wait)

    filled_size = est_size
    filled_price: float | None = None
    if fill:
        filled_price = _safe_float(fill.get("px"))
        filled_size = _safe_float(fill.get("sz")) or est_size
        oms_status = "FILLED"
        store.update_intent(intent_id, status="FILLED")
        # Write oms_fills + trades records
        try:
            snap = executor.account_snapshot(force=True)
            acct_val = snap.account_value_usd
        except Exception:
            acct_val = 0.0
        _record_fill(
            args.db_path,
            fill=fill,
            intent_id=intent_id,
            cloid=cloid,
            leverage=float(leverage),
            account_value=acct_val,
        )
        logger.info("Fill confirmed for %s: sz=%.6f px=%.4f", symbol, filled_size, filled_price or 0)
    elif not is_gtc:
        logger.warning("No fill found for %s after %.1fs polling (cloid=%s)", symbol, poll_wait, cloid)

    return _ok(
        {
            "action": "execute",
            "symbol": symbol,
            "side": side,
            "direction": direction,
            "order_type": order_type,
            "intent_id": intent_id,
            "client_order_id": cloid,
            "exchange_order_id": exchange_order_id,
            "requested_notional_usd": notional,
            "filled_size": filled_size,
            "filled_price": filled_price,
            "leverage": leverage,
            "oms_status": oms_status,
            "error": None,
        }
    )


# ---------------------------------------------------------------------------
# Action: close
# ---------------------------------------------------------------------------


def _action_close(args: argparse.Namespace) -> dict[str, Any]:
    # Safety: check hard kill switch before any exchange interaction.
    kill = _check_hard_kill_switch()
    if kill:
        return _err(kill)

    _load_modules()
    executor = _build_executor(args.secrets_path)
    store = _build_oms_store(args.db_path)

    symbol = str(args.symbol).strip().upper()
    close_pct = float(args.close_pct)
    order_type = str(args.order_type).strip().lower()

    if close_pct <= 0 or close_pct > 100:
        return _err("close_pct must be between 0 (exclusive) and 100 (inclusive)")

    # Fetch fresh position from exchange (not DB)
    positions = executor.get_positions(force=True)
    pos = positions.get(symbol)
    if not pos:
        return _err(f"No open position for {symbol}")

    pos_type = str(pos["type"])  # LONG or SHORT
    pos_size = float(pos["size"])
    pos_leverage = float(pos.get("leverage", 1.0))

    # Compute close size
    close_size_raw = pos_size * (close_pct / 100.0)
    close_size = _meta_mod.round_size(symbol, close_size_raw)
    if close_size <= 0:
        close_size = _meta_mod.round_size_up(symbol, close_size_raw)
    if close_size <= 0:
        return _err(f"Computed close size is zero for {symbol}")

    # Don't exceed actual position
    if close_size > pos_size:
        close_size = _meta_mod.round_size(symbol, pos_size)

    # To close: sell if LONG, buy if SHORT
    is_buy = pos_type == "SHORT"
    side = "BUY" if is_buy else "SELL"
    direction = pos_type

    # Create OMS intent
    intent_id = _INTENT_PREFIX + uuid.uuid4().hex
    cloid = _oms_mod._make_hl_cloid(seed_hex=intent_id.replace(_INTENT_PREFIX, ""), prefix=_CLOID_PREFIX)
    created_ms = int(time.time() * 1000)

    # Fetch mid price for notional estimate
    mids = executor._info.all_mids() or {}
    mid_price = _safe_float(mids.get(symbol), 0.0)
    est_notional = close_size * mid_price if mid_price > 0 else 0.0

    meta_json = json.dumps(
        {
            "source": "manual_trade",
            "action": "close",
            "close_pct": close_pct,
            "order_type": order_type,
        },
        separators=(",", ":"),
        default=str,
    )

    store.insert_intent(
        intent_id=intent_id,
        client_order_id=cloid,
        created_ts_ms=created_ms,
        symbol=symbol,
        action="CLOSE",
        side=side,
        requested_size=close_size,
        requested_notional=est_notional,
        entry_atr=None,
        leverage=pos_leverage,
        decision_ts_ms=created_ms,
        strategy_version=None,
        strategy_sha1=None,
        reason="manual_close",
        confidence="MANUAL",
        status="NEW",
        dedupe_key=None,
        meta_json=meta_json,
    )

    logger.info(
        "Created OMS close intent %s for %s %s sz=%.6f (%.1f%%)",
        intent_id, symbol, side, close_size, close_pct,
    )

    # Submit order
    result_raw: dict | None = None
    submit_ms = int(time.time() * 1000)

    if order_type == "market":
        result_raw = executor.market_close(
            symbol,
            is_buy=is_buy,
            sz=close_size,
            slippage_pct=_DEFAULT_SLIPPAGE_PCT,
            cloid=cloid,
        )
    elif order_type == "limit_ioc":
        if args.limit_price is None:
            store.update_intent(intent_id, status="REJECTED", last_error="limit_price required for limit_ioc close")
            return _err("limit_price is required for limit_ioc orders", intent_id=intent_id)
        limit_px = float(args.limit_price)
        cloid_obj = _make_cloid_obj(cloid)
        result_raw = executor._exchange.order(
            symbol,
            is_buy=is_buy,
            sz=close_size,
            limit_px=limit_px,
            order_type={"limit": {"tif": "Ioc"}},
            reduce_only=True,
            cloid=cloid_obj,
        )
    elif order_type == "limit_gtc":
        if args.limit_price is None:
            store.update_intent(intent_id, status="REJECTED", last_error="limit_price required for limit_gtc close")
            return _err("limit_price is required for limit_gtc orders", intent_id=intent_id)
        limit_px = float(args.limit_price)
        cloid_obj = _make_cloid_obj(cloid)
        result_raw = executor._exchange.order(
            symbol,
            is_buy=is_buy,
            sz=close_size,
            limit_px=limit_px,
            order_type={"limit": {"tif": "Gtc"}},
            reduce_only=True,
            cloid=cloid_obj,
        )
    else:
        store.update_intent(intent_id, status="REJECTED", last_error=f"unknown order_type: {order_type}")
        return _err(f"Unknown order_type: {order_type}", intent_id=intent_id)

    if result_raw is None or not _executor_mod._is_ok_response(result_raw):
        err_msg = "Close order rejected by exchange"
        if result_raw is not None:
            err_msg += f": {result_raw}"
        store.update_intent(intent_id, status="REJECTED", last_error=err_msg[:500])
        return _err(err_msg, intent_id=intent_id, action="close")

    exchange_order_id = _extract_exchange_oid(result_raw)

    store.update_intent(
        intent_id,
        status="SENT",
        sent_ts_ms=int(time.time() * 1000),
        exchange_order_id=exchange_order_id,
    )

    # Audit
    _write_audit(
        args.db_path,
        event="MANUAL_CLOSE",
        symbol=symbol,
        details={
            "intent_id": intent_id,
            "side": side,
            "direction": direction,
            "order_type": order_type,
            "close_pct": close_pct,
            "close_size": close_size,
            "pos_size": pos_size,
            "mid_price": mid_price,
            "exchange_order_id": exchange_order_id,
            "cloid": cloid,
        },
    )

    # Poll for fill confirmation
    is_gtc = order_type == "limit_gtc"
    poll_wait = 3.0 if is_gtc else 8.0
    fill = _poll_fill(executor, cloid, symbol, submit_ms, max_wait_s=poll_wait)

    oms_status = "SENT"
    filled_size = close_size
    filled_price: float | None = None
    closed_pnl: float | None = None
    if fill:
        filled_price = _safe_float(fill.get("px"))
        filled_size = _safe_float(fill.get("sz")) or close_size
        closed_pnl = _safe_float(fill.get("closedPnl"))
        oms_status = "FILLED"
        store.update_intent(intent_id, status="FILLED")
        try:
            snap = executor.account_snapshot(force=True)
            acct_val = snap.account_value_usd
        except Exception:
            acct_val = 0.0
        _record_fill(
            args.db_path,
            fill=fill,
            intent_id=intent_id,
            cloid=cloid,
            leverage=pos_leverage,
            account_value=acct_val,
        )
        logger.info("Close fill confirmed for %s: sz=%.6f px=%.4f pnl=%.2f", symbol, filled_size, filled_price or 0, closed_pnl or 0)
    elif not is_gtc:
        logger.warning("No close fill found for %s after %.1fs polling (cloid=%s)", symbol, poll_wait, cloid)

    return _ok(
        {
            "action": "close",
            "symbol": symbol,
            "side": side,
            "direction": direction,
            "order_type": order_type,
            "intent_id": intent_id,
            "client_order_id": cloid,
            "exchange_order_id": exchange_order_id,
            "close_pct": close_pct,
            "close_size": filled_size,
            "filled_price": filled_price,
            "closed_pnl": closed_pnl,
            "pos_size": pos_size,
            "leverage": pos_leverage,
            "oms_status": oms_status,
            "error": None,
        }
    )


# ---------------------------------------------------------------------------
# Action: cancel
# ---------------------------------------------------------------------------


def _action_cancel(args: argparse.Namespace) -> dict[str, Any]:
    _load_modules()
    executor = _build_executor(args.secrets_path)

    symbol = str(args.symbol).strip().upper()
    oid = str(getattr(args, "oid", "") or "").strip()
    intent_id = str(getattr(args, "intent_id", "") or "").strip()

    if not oid and not intent_id:
        return _err("oid or intent_id is required for cancel action")

    client_order_id: str | None = None
    exchange_order_id: str | None = oid or None

    # If intent_id provided, look up in OMS for cloid / exchange_order_id
    if intent_id:
        try:
            store = _build_oms_store(args.db_path)
            conn = store._connect()
            try:
                row = conn.execute(
                    "SELECT client_order_id, exchange_order_id FROM oms_intents WHERE intent_id = ?",
                    (intent_id,),
                ).fetchone()
            finally:
                store._close(conn)
            if row:
                client_order_id = row[0]
                if not exchange_order_id:
                    exchange_order_id = row[1]
        except Exception as exc:
            logger.warning("OMS lookup for intent %s failed: %s", intent_id, exc)

    # Cancel via exchange_order_id first, fall back to cloid
    result_raw = None
    if exchange_order_id:
        result_raw = executor.cancel_order(symbol=symbol, oid=exchange_order_id)
    if result_raw is None and client_order_id:
        result_raw = executor.cancel_order(symbol=symbol, cloid=client_order_id)

    if result_raw is None:
        cancel_ref = intent_id or oid
        return _err(f"Cancel failed for {cancel_ref}", intent_id=intent_id or None, oid=oid or None, action="cancel")

    # Best-effort update OMS intent status
    if intent_id:
        try:
            store = _build_oms_store(args.db_path)
            store.update_intent(intent_id, status="CANCELLED")
        except Exception as exc:
            logger.warning("OMS update for cancelled intent %s failed: %s", intent_id, exc)

    # Audit
    _write_audit(
        args.db_path,
        event="MANUAL_CANCEL",
        symbol=symbol,
        details={
            "oid": oid or None,
            "intent_id": intent_id or None,
            "client_order_id": client_order_id,
            "exchange_order_id": exchange_order_id,
        },
    )

    return _ok(
        {
            "action": "cancel",
            "symbol": symbol,
            "oid": oid or None,
            "intent_id": intent_id or None,
            "client_order_id": client_order_id,
            "exchange_order_id": exchange_order_id,
            "error": None,
        }
    )


# ---------------------------------------------------------------------------
# Action: open-orders
# ---------------------------------------------------------------------------


def _action_open_orders(args: argparse.Namespace) -> dict[str, Any]:
    _load_modules()
    executor = _build_executor(args.secrets_path)

    symbol = str(args.symbol).strip().upper()

    # Fetch open orders from exchange via Info API
    try:
        raw = executor._info.open_orders(executor.main_address) or []
    except Exception as exc:
        return _err(f"Failed to fetch open orders: {exc}")

    # Filter by symbol
    orders: list[dict[str, Any]] = []
    for o in raw:
        if not isinstance(o, dict):
            continue
        coin = str(o.get("coin") or "").strip().upper()
        if coin != symbol:
            continue
        # HL side: "A" = ask (sell), "B" = bid (buy)
        hl_side = str(o.get("side") or "").upper()
        friendly_side = "BUY" if hl_side == "B" else "SELL"
        orders.append(
            {
                "oid": o.get("oid"),
                "coin": coin,
                "side": friendly_side,
                "size": _safe_float(o.get("sz")),
                "price": _safe_float(o.get("limitPx")),
                "sz": str(o.get("sz") or ""),
                "limit_px": str(o.get("limitPx") or ""),
                "timestamp": o.get("timestamp"),
            }
        )

    return _ok(
        {
            "action": "open-orders",
            "symbol": symbol,
            "orders": orders,
        }
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_cloid_obj(cloid: str | None) -> Any:
    """Convert a cloid hex string to a Hyperliquid Cloid object."""
    if not cloid:
        return None
    try:
        from hyperliquid.utils import types
        return types.Cloid(str(cloid))
    except Exception:
        return None


def _extract_exchange_oid(result: dict | None) -> str | None:
    """Extract exchange order ID from HL SDK order response."""
    if result is None or not isinstance(result, dict):
        return None

    # HL: {"status":"ok","response":{"type":"order","data":{"statuses":[...]}}}
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
            for key in ("filled", "resting"):
                payload = st.get(key)
                if isinstance(payload, dict) and payload.get("oid") is not None:
                    return str(payload["oid"])

    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Manual trade CLI for Hyperliquid (spawned by hub).",
    )
    ap.add_argument(
        "--action",
        required=True,
        choices=["preview", "execute", "close", "cancel", "open-orders"],
        help="Action to perform.",
    )
    ap.add_argument("--symbol", default="", help="Trading symbol (e.g. ETH, BTC).")
    ap.add_argument("--side", default="", help="BUY or SELL (for preview/execute).")
    ap.add_argument("--notional", type=float, default=0.0, help="Notional USD amount.")
    ap.add_argument("--leverage", type=int, default=1, help="Leverage (1-50).")
    ap.add_argument(
        "--order-type",
        default="market",
        choices=["market", "limit_ioc", "limit_gtc"],
        help="Order type.",
    )
    ap.add_argument("--limit-price", type=float, default=None, help="Limit price (for limit orders).")
    ap.add_argument("--close-pct", type=float, default=100.0, help="Percentage of position to close (for close action).")
    ap.add_argument("--oid", default="", help="Exchange order ID (for cancel action).")
    ap.add_argument("--intent-id", default="", help="OMS intent_id (for cancel action).")
    ap.add_argument("--confirm-token", default="", help="Confirm token from preview (for execute action).")
    ap.add_argument(
        "--db-path",
        default=str(PROJECT_DIR / "trading_engine_live.db"),
        help="Path to trading engine SQLite DB.",
    )
    ap.add_argument(
        "--secrets-path",
        default=str(DEFAULT_SECRETS_PATH),
        help="Path to secrets JSON file.",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = _build_parser()
    args = ap.parse_args(argv)

    action = str(args.action).strip().lower()

    try:
        if action == "preview":
            result = _action_preview(args)
        elif action == "execute":
            result = _action_execute(args)
        elif action == "close":
            result = _action_close(args)
        elif action == "cancel":
            result = _action_cancel(args)
        elif action == "open-orders":
            result = _action_open_orders(args)
        else:
            result = _err(f"Unknown action: {action}")
    except Exception as exc:
        logger.exception("Unhandled error in action=%s", action)
        result = _err(f"Internal error: {exc}", action=action)

    _emit(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
