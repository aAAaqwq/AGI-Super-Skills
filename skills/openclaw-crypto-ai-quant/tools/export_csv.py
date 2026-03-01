#!/usr/bin/env python3
"""
Export a single consolidated CSV for LIVE (only) covering the last N hours:
  - trades (OPEN/CLOSE/ADD)
  - audit_events (ENTRY_SKIP_*, LIVE_ORDER_*, ANALYZE_NEUTRAL_SAMPLE, etc.)
  - signals (BUY/SELL signals logged by the engine)

Each row is keyed at minute granularity (HHMM UTC) plus symbol plus open/close plus a transaction id.
Rows include:
  - OMS fields (intent/fill) where available
  - candle OHLCV from the sidecar candle DB (1m by default)
  - "signal measures" from stored audit payloads (RSI/EMA/MACD/ATR/etc.)

Usage:
  python tools/export_csv.py --hours 4

Outputs:
  - exports/live_consolidated_last{hours}h_<timestamp>.csv
  - exports/live_rules_last{hours}h_<timestamp>.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import sys
from bisect import bisect_left
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


AIQ_ROOT = Path(__file__).resolve().parents[1]

if str(AIQ_ROOT) not in sys.path:
    sys.path.insert(0, str(AIQ_ROOT))


def _parse_iso_utc(ts: str | None) -> datetime | None:
    if not ts:
        return None
    s = str(ts).strip()
    if not s:
        return None
    # Support both "...+00:00" and "...Z".
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None
    if dt.tzinfo is None:
        # Treat naive timestamps as UTC (should not happen in our DBs).
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _dt_minute(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0, tzinfo=timezone.utc)


def _hhmm(dt: datetime) -> str:
    return dt.strftime("%H%M")


def _sha1_file(path: Path) -> str | None:
    try:
        h = hashlib.sha1()
        with path.open("rb") as f:
            while True:
                b = f.read(1024 * 1024)
                if not b:
                    break
                h.update(b)
        return h.hexdigest()
    except Exception:
        return None


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path), timeout=10.0)
    con.row_factory = sqlite3.Row
    return con


def _safe_json_loads(s: str | None) -> Any:
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def _safe_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _json_dumps(v: Any) -> str:
    try:
        return json.dumps(v, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    except Exception:
        return ""


def _build_signal_index(signal_rows: list[sqlite3.Row]) -> dict[str, list[tuple[float, dict[str, Any]]]]:
    """
    Index signals by symbol -> sorted list[(ts_s, row_dict)] for nearest lookups.
    """
    idx: dict[str, list[tuple[float, dict[str, Any]]]] = {}
    for r in signal_rows:
        d = dict(r)
        dt = _parse_iso_utc(d.get("timestamp"))
        if dt is None:
            continue
        ts_s = dt.timestamp()
        sym = str(d.get("symbol") or "").strip().upper()
        if not sym:
            continue
        idx.setdefault(sym, []).append((ts_s, d))
    for sym in list(idx.keys()):
        idx[sym].sort(key=lambda x: x[0])
    return idx


def _nearest_signal(
    idx: dict[str, list[tuple[float, dict[str, Any]]]],
    *,
    symbol: str,
    ts_s: float,
    max_abs_s: float = 10.0,
) -> dict[str, Any] | None:
    sym = str(symbol or "").strip().upper()
    if not sym or sym not in idx:
        return None
    arr = idx[sym]
    xs = [x[0] for x in arr]
    i = bisect_left(xs, ts_s)
    cand: list[tuple[float, dict[str, Any]]] = []
    if 0 <= i < len(arr):
        cand.append(arr[i])
    if i - 1 >= 0:
        cand.append(arr[i - 1])
    if i + 1 < len(arr):
        cand.append(arr[i + 1])
    best = None
    best_abs = None
    for t, row in cand:
        a = abs(float(t) - float(ts_s))
        if best is None or (best_abs is not None and a < best_abs):
            best = row
            best_abs = a
    if best is None or best_abs is None or best_abs > float(max_abs_s):
        return None
    return best


def _load_candles(
    *,
    candles_db_path: Path,
    interval: str,
    symbols: list[str],
    t_min_ms: int,
    t_max_ms: int,
) -> dict[tuple[str, int], dict[str, Any]]:
    out: dict[tuple[str, int], dict[str, Any]] = {}
    if not candles_db_path.exists():
        return out
    if not symbols:
        return out
    syms = [s.strip().upper() for s in symbols if str(s or "").strip()]
    syms = sorted(set(syms))
    con = _connect(candles_db_path)
    try:
        cur = con.cursor()
        # SQLite parameter limit is high enough for <= 50 symbols.
        ph = ",".join(["?"] * len(syms))
        rows = cur.execute(
            f"""
            SELECT symbol, t, t_close, o, h, l, c, v, n, updated_at
            FROM candles
            WHERE interval = ?
              AND t BETWEEN ? AND ?
              AND symbol IN ({ph})
            """,
            [interval, int(t_min_ms), int(t_max_ms), *syms],
        ).fetchall()
        for r in rows:
            d = dict(r)
            sym = str(d.get("symbol") or "").strip().upper()
            t = int(d.get("t") or 0)
            if not sym or t <= 0:
                continue
            out[(sym, t)] = d
    finally:
        con.close()
    return out


def _extract_audit_fields(audit: dict[str, Any] | None) -> dict[str, Any]:
    """
    Normalize audit payload shape:
      {"signal","confidence","tags","gates","values","strategy","quote"}
    """
    if not isinstance(audit, dict):
        return {}
    out: dict[str, Any] = {}
    out["audit_signal"] = str(audit.get("signal") or "").upper() or None
    out["audit_confidence"] = str(audit.get("confidence") or "").lower() or None
    tags = audit.get("tags")
    if isinstance(tags, list):
        out["audit_tags"] = ";".join([str(x) for x in tags if x is not None])
    else:
        out["audit_tags"] = None

    gates = audit.get("gates")
    values = audit.get("values")
    if isinstance(gates, dict):
        out["audit_gates_json"] = _json_dumps(gates)
        # Pull a few common gates into dedicated columns.
        for k in [
            "adx",
            "effective_min_adx",
            "is_ranging",
            "is_anomaly",
            "is_extended",
            "vol_confirm",
            "is_trending_up",
            "dist_ema_fast",
            "max_dist_ema_fast",
            "macd_hist_entry_mode",
            "ave_enabled",
            "ave_avg_atr_window",
            "ave_atr_ratio",
            "ave_atr_ratio_gt",
            "ave_adx_mult",
            "vol_spike_mult",
            "require_macro_alignment",
            "require_btc_alignment",
            "btc_bullish",
            "btc_ok_long",
            "btc_ok_short",
            "pullback_enabled",
            "pullback_used",
            "slow_drift_enabled",
            "slow_drift_used",
        ]:
            if k in gates:
                out[f"gate_{k}"] = gates.get(k)

    if isinstance(values, dict):
        out["audit_values_json"] = _json_dumps(values)
        for k in [
            "close",
            "ema_fast",
            "ema_slow",
            "ema_macro",
            "rsi",
            "rsi_long_limit",
            "rsi_short_limit",
            "macd_hist",
            "prev_macd_hist",
            "bb_width_ratio",
            "tp_mult",
            "stoch_k",
            "stoch_d",
            "adx_slope",
            "atr",
            "atr_slope",
            "slow_drift_used",
            "ema_slow_slope_pct",
        ]:
            if k in values:
                out[f"val_{k}"] = values.get(k)
    return out


def _derive_open_close(row_kind: str, *, trade_action: str | None, audit_event: str | None, signal: str | None) -> str | None:
    if row_kind == "TRADE":
        a = str(trade_action or "").strip().upper()
        # Normalize trade actions into OPEN/CLOSE buckets so keys/grouping are stable.
        if a in {"OPEN", "ADD"}:
            return "OPEN"
        if a in {"CLOSE", "REDUCE"}:
            return "CLOSE"
        return a or None
    if row_kind == "SIGNAL":
        # A signal is an entry direction (BUY/SELL) not an order action, but treat as "OPEN" for keying.
        return "OPEN"
    if row_kind == "AUDIT":
        ev = str(audit_event or "").strip().upper()
        if not ev:
            return None
        if "EXIT" in ev or "CLOSE" in ev:
            return "CLOSE"
        if "OPEN" in ev or ev.startswith("ENTRY_") or "WOULD_OPEN" in ev:
            return "OPEN"
        return None
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=4.0)
    ap.add_argument("--live-db", default=str(os.getenv("AI_QUANT_LIVE_DB_PATH", str(AIQ_ROOT / "trading_engine_live.db"))))
    ap.add_argument("--interval", default=str(os.getenv("AI_QUANT_INTERVAL", "1m") or "1m"))
    ap.add_argument("--candles-db", default=str(os.getenv("AI_QUANT_CANDLES_DB_PATH", "")))
    ap.add_argument("--out", default="")
    ap.add_argument("--rules-out", default="")
    args = ap.parse_args()

    hours = float(args.hours)
    if hours <= 0:
        raise SystemExit("--hours must be > 0")

    live_db_path = Path(str(args.live_db))
    if not live_db_path.exists():
        raise SystemExit(f"live db missing: {live_db_path}")

    interval = str(args.interval or "1m").strip() or "1m"

    candles_db_path = Path(str(args.candles_db or "").strip()) if str(args.candles_db or "").strip() else None
    if candles_db_path is None or not candles_db_path.exists():
        # Default: candles_dbs/candles_1m.db
        cand = AIQ_ROOT / "candles_dbs" / f"candles_{interval}.db"
        if cand.exists():
            candles_db_path = cand
        else:
            # Fallback to market_data.db if present (older mode).
            cand2 = AIQ_ROOT / "market_data.db"
            candles_db_path = cand2 if cand2.exists() else cand

    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours)
    start_s = start.isoformat()
    end_s = now.isoformat()

    start_min = _dt_minute(start)
    end_min = _dt_minute(now)
    t_min_ms = int(start_min.timestamp() * 1000)
    t_max_ms = int(end_min.timestamp() * 1000)

    con = _connect(live_db_path)
    try:
        cur = con.cursor()
        # Load trades, audit events, signals within the window.
        trades = cur.execute(
            """
            SELECT *
            FROM trades
            WHERE datetime(timestamp) >= datetime('now', ?)
            ORDER BY id ASC
            """,
            (f"-{hours} hours",),
        ).fetchall()

        audits = cur.execute(
            """
            SELECT *
            FROM audit_events
            WHERE datetime(timestamp) >= datetime('now', ?)
            ORDER BY id ASC
            """,
            (f"-{hours} hours",),
        ).fetchall()

        signals = cur.execute(
            """
            SELECT *
            FROM signals
            WHERE datetime(timestamp) >= datetime('now', ?)
            ORDER BY id ASC
            """,
            (f"-{hours} hours",),
        ).fetchall()

        # Load OMS intents/fills for enrichment (within same wall-clock window).
        start_ms = int(start.timestamp() * 1000)
        intents = cur.execute(
            """
            SELECT *
            FROM oms_intents
            WHERE created_ts_ms >= ?
            ORDER BY created_ts_ms ASC
            """,
            (start_ms,),
        ).fetchall()
        fills = cur.execute(
            """
            SELECT *
            FROM oms_fills
            WHERE ts_ms >= ?
            ORDER BY ts_ms ASC
            """,
            (start_ms,),
        ).fetchall()

    finally:
        con.close()

    # Build OMS indexes.
    intents_by_id: dict[str, dict[str, Any]] = {}
    for r in intents:
        d = dict(r)
        iid = str(d.get("intent_id") or "").strip()
        if iid:
            intents_by_id[iid] = d

    fills_by_hash: dict[str, dict[str, Any]] = {}
    fills_by_tid: dict[int, dict[str, Any]] = {}
    for r in fills:
        d = dict(r)
        h = str(d.get("fill_hash") or "").strip()
        if h:
            fills_by_hash[h] = d
        try:
            tid = int(d.get("fill_tid") or 0)
        except Exception:
            tid = 0
        if tid:
            fills_by_tid[tid] = d

    # Build signal index (symbol + nearest-time).
    sig_idx = _build_signal_index(signals)

    # Determine symbols involved (trades + audits + signals).
    syms: set[str] = set()
    for r in trades:
        s = str(r["symbol"] or "").strip().upper()
        if s:
            syms.add(s)
    for r in audits:
        s = str(r["symbol"] or "").strip().upper()
        if s:
            syms.add(s)
    for r in signals:
        s = str(r["symbol"] or "").strip().upper()
        if s:
            syms.add(s)

    # Load candles for involved symbols (minute resolution).
    candles = _load_candles(
        candles_db_path=Path(candles_db_path),
        interval=interval,
        symbols=sorted(syms),
        t_min_ms=t_min_ms,
        t_max_ms=t_max_ms,
    )

    rows_out: list[dict[str, Any]] = []

    def attach_candle(row: dict[str, Any], *, symbol: str, dt_min: datetime) -> None:
        t_ms = int(dt_min.timestamp() * 1000)
        c = candles.get((symbol, t_ms))
        row["candle_interval"] = interval
        row["candle_t_ms"] = t_ms
        row["candle_t_utc"] = dt_min.isoformat()
        if not c:
            return
        row["candle_o"] = c.get("o")
        row["candle_h"] = c.get("h")
        row["candle_l"] = c.get("l")
        row["candle_c"] = c.get("c")
        row["candle_v"] = c.get("v")
        row["candle_n"] = c.get("n")
        row["candle_updated_at"] = c.get("updated_at")

    def attach_from_signal(row: dict[str, Any], sig_row: dict[str, Any] | None) -> None:
        if not sig_row:
            return
        row["nearest_signal_id"] = sig_row.get("id")
        row["nearest_signal_ts_utc"] = sig_row.get("timestamp")
        row["nearest_signal"] = sig_row.get("signal")
        row["nearest_signal_confidence"] = sig_row.get("confidence")
        meta = _safe_json_loads(sig_row.get("meta_json"))
        if isinstance(meta, dict):
            row.update(_extract_audit_fields(meta))
            # strategy snapshot (if present)
            strat = meta.get("strategy")
            if isinstance(strat, dict):
                row["strategy_version"] = strat.get("version")
                row["strategy_overrides_sha1"] = strat.get("overrides_sha1")

    # ---- Trades rows ----
    for r in trades:
        d = dict(r)
        dt = _parse_iso_utc(d.get("timestamp"))
        if dt is None:
            continue
        dtm = _dt_minute(dt)
        sym = str(d.get("symbol") or "").strip().upper()
        if not sym:
            continue

        meta = _safe_json_loads(d.get("meta_json"))
        audit = None
        strat_meta = None
        order_meta = None
        oms_meta = None
        exit_meta = None
        if isinstance(meta, dict):
            audit = meta.get("audit")
            strat_meta = meta.get("strategy")
            order_meta = meta.get("order")
            oms_meta = meta.get("oms")
            exit_meta = meta.get("exit")

        row: dict[str, Any] = {
            "mode": "live",
            "row_kind": "TRADE",
            "ts_utc": dt.isoformat(),
            "ts_minute_utc": dtm.isoformat(),
            "hhmm_utc": _hhmm(dtm),
            "symbol": sym,
            "transaction_id": int(d.get("id") or 0),
            "trade_id": int(d.get("id") or 0),
            "trade_action": d.get("action"),
            "trade_type": d.get("type"),
            "trade_price": d.get("price"),
            "trade_size": d.get("size"),
            "trade_notional": d.get("notional"),
            "trade_reason": d.get("reason"),
            "trade_confidence": d.get("confidence"),
            "trade_pnl": d.get("pnl"),
            "trade_fee_usd": d.get("fee_usd"),
            "trade_fee_rate": d.get("fee_rate"),
            "trade_fee_token": d.get("fee_token"),
            # In live mode, `trades.balance` stores withdrawable cash (not account value).
            "withdrawable_usd": d.get("balance"),
            "trade_entry_atr": d.get("entry_atr"),
            "trade_leverage": d.get("leverage"),
            "trade_margin_used_usd": d.get("margin_used"),
            "trade_fill_hash": d.get("fill_hash"),
            "trade_fill_tid": d.get("fill_tid"),
            "order_kind": (order_meta or {}).get("kind") if isinstance(order_meta, dict) else None,
            "order_px_est": (order_meta or {}).get("px_est") if isinstance(order_meta, dict) else None,
            "order_notional_est": (order_meta or {}).get("notional_est") if isinstance(order_meta, dict) else None,
            "order_leverage": (order_meta or {}).get("leverage") if isinstance(order_meta, dict) else None,
            "order_margin_est": (order_meta or {}).get("margin_est") if isinstance(order_meta, dict) else None,
            "exit_kind": (exit_meta or {}).get("kind") if isinstance(exit_meta, dict) else None,
            "exit_reason": (exit_meta or {}).get("reason") if isinstance(exit_meta, dict) else None,
        }

        # strategy snapshot (prefer meta.strategy; fall back to intent.strategy_version/sha1)
        if isinstance(strat_meta, dict):
            row["strategy_version"] = strat_meta.get("version")
            row["strategy_overrides_sha1"] = strat_meta.get("overrides_sha1")

        # audit measures (signals/indicators/gates)
        if isinstance(audit, dict):
            row.update(_extract_audit_fields(audit))

        # OMS enrichment
        intent_id = None
        if isinstance(oms_meta, dict):
            intent_id = str(oms_meta.get("intent_id") or "").strip() or None
            row["oms_intent_id"] = intent_id
            row["oms_matched_via"] = oms_meta.get("matched_via")
            row["oms_client_order_id"] = oms_meta.get("client_order_id")
            row["oms_exchange_order_id"] = oms_meta.get("exchange_order_id")

        if intent_id and intent_id in intents_by_id:
            it = intents_by_id[intent_id]
            row["oms_action"] = it.get("action")
            row["oms_side"] = it.get("side")
            row["oms_status"] = it.get("status")
            row["oms_reason"] = it.get("reason")
            row["oms_confidence"] = it.get("confidence")
            row["oms_strategy_version"] = it.get("strategy_version")
            row["oms_strategy_sha1"] = it.get("strategy_sha1")
            row["oms_dedupe_key"] = it.get("dedupe_key")
            row["oms_requested_size"] = it.get("requested_size")
            row["oms_requested_notional"] = it.get("requested_notional")
            row["oms_entry_atr"] = it.get("entry_atr")
            row["oms_leverage"] = it.get("leverage")
            row["oms_last_error"] = it.get("last_error")

        # Fill enrichment (if present)
        fill_hash = str(d.get("fill_hash") or "").strip() or None
        fill_tid = None
        try:
            fill_tid = int(d.get("fill_tid") or 0) or None
        except Exception:
            fill_tid = None
        fill_row = None
        if fill_hash and fill_hash in fills_by_hash:
            fill_row = fills_by_hash[fill_hash]
        elif fill_tid and fill_tid in fills_by_tid:
            fill_row = fills_by_tid[fill_tid]
        if fill_row:
            row["fill_fee_usd"] = fill_row.get("fee_usd")
            row["fill_fee_rate"] = fill_row.get("fee_rate")
            row["fill_pnl_usd"] = fill_row.get("pnl_usd")
            row["fill_matched_via"] = fill_row.get("matched_via")

        open_close = _derive_open_close("TRADE", trade_action=row.get("trade_action"), audit_event=None, signal=None)
        row["open_close"] = open_close
        row["key"] = f"{row['hhmm_utc']}_{sym}_{open_close or "NA"}_{row['transaction_id']}"
        attach_candle(row, symbol=sym, dt_min=dtm)
        rows_out.append(row)

    # ---- Signals rows ----
    for r in signals:
        d = dict(r)
        dt = _parse_iso_utc(d.get("timestamp"))
        if dt is None:
            continue
        dtm = _dt_minute(dt)
        sym = str(d.get("symbol") or "").strip().upper()
        if not sym:
            continue
        meta = _safe_json_loads(d.get("meta_json"))
        row: dict[str, Any] = {
            "mode": "live",
            "row_kind": "SIGNAL",
            "ts_utc": dt.isoformat(),
            "ts_minute_utc": dtm.isoformat(),
            "hhmm_utc": _hhmm(dtm),
            "symbol": sym,
            "transaction_id": int(d.get("id") or 0),
            "signal_id": int(d.get("id") or 0),
            "signal": d.get("signal"),
            "signal_confidence": d.get("confidence"),
            "signal_price": d.get("price"),
            "signal_rsi": d.get("rsi"),
            "signal_ema_fast": d.get("ema_fast"),
            "signal_ema_slow": d.get("ema_slow"),
        }
        if isinstance(meta, dict):
            row.update(_extract_audit_fields(meta))
            strat = meta.get("strategy")
            if isinstance(strat, dict):
                row["strategy_version"] = strat.get("version")
                row["strategy_overrides_sha1"] = strat.get("overrides_sha1")

        open_close = _derive_open_close("SIGNAL", trade_action=None, audit_event=None, signal=row.get("signal"))
        row["open_close"] = open_close
        row["key"] = f"{row['hhmm_utc']}_{sym}_{open_close or "NA"}_{row['transaction_id']}"
        attach_candle(row, symbol=sym, dt_min=dtm)
        rows_out.append(row)

    # ---- Audit rows ----
    for r in audits:
        d = dict(r)
        dt = _parse_iso_utc(d.get("timestamp"))
        if dt is None:
            continue
        dtm = _dt_minute(dt)
        sym = str(d.get("symbol") or "").strip().upper()
        if not sym:
            continue

        ev = str(d.get("event") or "").strip()
        level = str(d.get("level") or "").strip()
        data_json = str(d.get("data_json") or "")
        data = _safe_json_loads(data_json)

        row: dict[str, Any] = {
            "mode": "live",
            "row_kind": "AUDIT",
            "ts_utc": dt.isoformat(),
            "ts_minute_utc": dtm.isoformat(),
            "hhmm_utc": _hhmm(dtm),
            "symbol": sym,
            "transaction_id": int(d.get("id") or 0),
            "audit_id": int(d.get("id") or 0),
            "audit_event": ev,
            "audit_level": level,
            "audit_data_json": data_json,
        }

        # Common parsed audit fields.
        if isinstance(data, dict):
            for k_src, k_dst in [
                ("signal", "audit_data_signal"),
                ("confidence", "audit_data_confidence"),
                ("reason", "audit_data_reason"),
                ("kind", "audit_data_kind"),
                ("px_est", "audit_px_est"),
                ("size", "audit_size"),
                ("notional_est", "audit_notional_est"),
                ("leverage", "audit_leverage"),
                ("margin_est", "audit_margin_est"),
                ("adx", "audit_adx"),
                ("cooldown_mins", "audit_cooldown_mins"),
                ("diff_mins", "audit_diff_mins"),
                ("last_type", "audit_last_type"),
                ("last_reason", "audit_last_reason"),
                ("open_symbols", "audit_open_symbols"),
                ("pending_open_symbols", "audit_pending_open_symbols"),
            ]:
                if k_src in data:
                    row[k_dst] = data.get(k_src)

            # If an embedded audit payload exists, extract measures.
            embedded_audit = data.get("audit")
            if isinstance(embedded_audit, dict):
                row.update(_extract_audit_fields(embedded_audit))
            else:
                # For entry-skip style events, attach nearest signal's audit.
                if ev.startswith("ENTRY_SKIP_") or ev in {"LIVE_ORDER_WOULD_OPEN", "LIVE_ORDER_SENT_OPEN", "LIVE_ORDER_SENT_ADD"}:
                    sig = _nearest_signal(sig_idx, symbol=sym, ts_s=dt.timestamp(), max_abs_s=10.0)
                    attach_from_signal(row, sig)

        open_close = _derive_open_close("AUDIT", trade_action=None, audit_event=ev, signal=None)
        row["open_close"] = open_close
        row["key"] = f"{row['hhmm_utc']}_{sym}_{open_close or "NA"}_{row['transaction_id']}"
        attach_candle(row, symbol=sym, dt_min=dtm)
        rows_out.append(row)

    # Sort rows by timestamp then by kind for readability.
    def _sort_key(x: dict[str, Any]) -> tuple:
        return (x.get("ts_utc") or "", x.get("row_kind") or "", str(x.get("symbol") or ""), int(x.get("transaction_id") or 0))

    rows_out.sort(key=_sort_key)

    # Output paths
    ts_tag = now.strftime("%Y%m%d_%H%M%SUTC")
    out_path = Path(str(args.out).strip()) if str(args.out).strip() else (AIQ_ROOT / "exports" / f"live_consolidated_last{hours:g}h_{ts_tag}.csv")
    rules_out_path = (
        Path(str(args.rules_out).strip())
        if str(args.rules_out).strip()
        else (AIQ_ROOT / "exports" / f"live_rules_last{hours:g}h_{ts_tag}.json")
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    rules_out_path.parent.mkdir(parents=True, exist_ok=True)

    # Header (stable order; include any extra keys appended at end).
    header = [
        "key",
        "mode",
        "row_kind",
        "ts_utc",
        "ts_minute_utc",
        "hhmm_utc",
        "symbol",
        "open_close",
        "transaction_id",
        # Candle
        "candle_interval",
        "candle_t_ms",
        "candle_t_utc",
        "candle_o",
        "candle_h",
        "candle_l",
        "candle_c",
        "candle_v",
        "candle_n",
        "candle_updated_at",
        # Strategy snapshot
        "strategy_version",
        "strategy_overrides_sha1",
        "oms_strategy_version",
        "oms_strategy_sha1",
        # Trades
        "trade_id",
        "trade_action",
        "trade_type",
        "trade_price",
        "trade_size",
        "trade_notional",
        "trade_reason",
        "trade_confidence",
        "trade_pnl",
        "trade_fee_usd",
        "trade_fee_rate",
        "trade_fee_token",
        "withdrawable_usd",
        "trade_entry_atr",
        "trade_leverage",
        "trade_margin_used_usd",
        "trade_fill_hash",
        "trade_fill_tid",
        "order_kind",
        "order_px_est",
        "order_notional_est",
        "order_leverage",
        "order_margin_est",
        "exit_kind",
        "exit_reason",
        # OMS
        "oms_intent_id",
        "oms_status",
        "oms_action",
        "oms_side",
        "oms_reason",
        "oms_confidence",
        "oms_dedupe_key",
        "oms_requested_size",
        "oms_requested_notional",
        "oms_entry_atr",
        "oms_leverage",
        "oms_matched_via",
        "oms_client_order_id",
        "oms_exchange_order_id",
        "oms_last_error",
        # Fill enrichment
        "fill_fee_usd",
        "fill_fee_rate",
        "fill_pnl_usd",
        "fill_matched_via",
        # Signals
        "signal_id",
        "signal",
        "signal_confidence",
        "signal_price",
        "signal_rsi",
        "signal_ema_fast",
        "signal_ema_slow",
        # Audit rows
        "audit_id",
        "audit_event",
        "audit_level",
        "audit_data_json",
        "audit_data_signal",
        "audit_data_confidence",
        "audit_data_reason",
        "audit_data_kind",
        "audit_px_est",
        "audit_size",
        "audit_notional_est",
        "audit_leverage",
        "audit_margin_est",
        "audit_adx",
        "audit_cooldown_mins",
        "audit_diff_mins",
        "audit_last_type",
        "audit_last_reason",
        "audit_open_symbols",
        "audit_pending_open_symbols",
        # Attached nearest signal (for skip rows)
        "nearest_signal_id",
        "nearest_signal_ts_utc",
        "nearest_signal",
        "nearest_signal_confidence",
        # Audit measures
        "audit_signal",
        "audit_confidence",
        "audit_tags",
        "audit_gates_json",
        "audit_values_json",
        # Common gates/values columns (denormalized)
        "gate_adx",
        "gate_effective_min_adx",
        "gate_is_ranging",
        "gate_is_anomaly",
        "gate_is_extended",
        "gate_vol_confirm",
        "gate_is_trending_up",
        "gate_dist_ema_fast",
        "gate_max_dist_ema_fast",
        "gate_macd_hist_entry_mode",
        "gate_ave_enabled",
        "gate_ave_avg_atr_window",
        "gate_ave_atr_ratio",
        "gate_ave_atr_ratio_gt",
        "gate_ave_adx_mult",
        "gate_vol_spike_mult",
        "gate_require_macro_alignment",
        "gate_require_btc_alignment",
        "gate_btc_bullish",
        "gate_btc_ok_long",
        "gate_btc_ok_short",
        "gate_pullback_enabled",
        "gate_pullback_used",
        "gate_slow_drift_enabled",
        "gate_slow_drift_used",
        "val_close",
        "val_ema_fast",
        "val_ema_slow",
        "val_ema_macro",
        "val_rsi",
        "val_rsi_long_limit",
        "val_rsi_short_limit",
        "val_macd_hist",
        "val_prev_macd_hist",
        "val_bb_width_ratio",
        "val_tp_mult",
        "val_stoch_k",
        "val_stoch_d",
        "val_adx_slope",
        "val_atr",
        "val_atr_slope",
        "val_slow_drift_used",
        "val_ema_slow_slope_pct",
    ]
    all_keys: set[str] = set()
    for r in rows_out:
        all_keys.update(r.keys())
    for k in sorted(all_keys):
        if k not in header:
            header.append(k)

    # Write CSV
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        for r in rows_out:
            w.writerow(r)

    # Rules snapshot (what config/rules were in effect).
    rules: dict[str, Any] = {
        "window_start_utc": start_s,
        "window_end_utc": end_s,
        "hours": hours,
        "mode": "live",
        "live_db_path": str(live_db_path),
        "candles_db_path": str(candles_db_path),
        "interval": interval,
        "symbols_included": sorted(syms),
    }

    # StrategyManager snapshot (best-effort).
    try:
        from engine.strategy_manager import StrategyManager

        sm = StrategyManager.get()
        snap = sm.snapshot
        rules["strategy_manager"] = {
            "yaml_path": getattr(snap, "yaml_path", None),
            "overrides_sha1": getattr(snap, "overrides_sha1", None),
            "version": getattr(snap, "version", None),
        }
        # Include a tiny config excerpt for BTC (represents global merge).
        try:
            cfg_btc = sm.get_config("BTC") or {}
            rules["strategy_cfg_excerpt_BTC"] = {
                "thresholds_entry": (cfg_btc.get("thresholds") or {}).get("entry"),
                "thresholds_ranging": (cfg_btc.get("thresholds") or {}).get("ranging"),
                "filters": cfg_btc.get("filters"),
                "trade": {
                    k: (cfg_btc.get("trade") or {}).get(k)
                    for k in [
                        "enable_ssf_filter",
                        "enable_breakeven_stop",
                        "breakeven_start_atr",
                        "breakeven_buffer_atr",
                        "reentry_cooldown_min_mins",
                        "reentry_cooldown_max_mins",
                        "trailing_start_atr",
                        "trailing_distance_atr",
                        "enable_reef_filter",
                        "reef_long_rsi_block_gt",
                        "reef_short_rsi_block_lt",
                        "reef_long_rsi_extreme_gt",
                        "reef_short_rsi_extreme_lt",
                    ]
                },
            }
        except Exception:
            pass
    except Exception as e:
        rules["strategy_manager_error"] = str(e)

    # Local strategy files (paths + sha1) so the expert can line up config.
    for sp in [AIQ_ROOT / "config" / "strategy_overrides.yaml", AIQ_ROOT / "strategy_changelog.json"]:
        if sp.exists():
            rules.setdefault("local_strategy_files", []).append({"path": str(sp), "sha1": _sha1_file(sp)})

    # Live env (non-sensitive subset).
    env_path = Path.home() / ".config" / "openclaw" / "ai-quant-live.env"
    if env_path.exists():
        keep = {
            "AI_QUANT_MODE",
            "AI_QUANT_DB_PATH",
            "AI_QUANT_TOP_N",
            "AI_QUANT_INTERVAL",
            "AI_QUANT_LOOKBACK_BARS",
            "AI_QUANT_SIGNAL_ON_CANDLE_CLOSE",
            "AI_QUANT_NEUTRAL_AUDIT_SAMPLE_EVERY_S",
            "AI_QUANT_NEUTRAL_AUDIT_SAMPLE_SYMBOLS",
            "AI_QUANT_DEBUG_GATES_SYMBOLS",
            "AI_QUANT_DEBUG_GATES_EVERY_S",
            "AI_QUANT_ENTRY_MAX_DELAY_S",
            "AI_QUANT_ENTRY_RETRY_ON_CAPACITY",
            "AI_QUANT_LIVE_ENABLE",
            "AI_QUANT_KILL_SWITCH",
            "AI_QUANT_HARD_KILL_SWITCH",
            "AI_QUANT_LIVE_MAX_OPEN_POSITIONS",
            "AI_QUANT_LIVE_MAX_NOTIONAL_USD_PER_ORDER",
            "AI_QUANT_LIVE_MIN_MARGIN_USD",
            "AI_QUANT_LIVE_STATE_SYNC_SECS",
            "AI_QUANT_HL_TIMEOUT_S",
            "HL_LIVE_MARKET_SLIPPAGE_PCT",
        }
        env_vals: dict[str, str] = {}
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k in keep:
                env_vals[k] = v
        rules["live_env_subset"] = env_vals

    rules_out_path.write_text(json.dumps(rules, indent=2, sort_keys=True), encoding="utf-8")

    print(str(out_path))
    print(str(rules_out_path))


if __name__ == "__main__":
    main()
