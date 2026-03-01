#!/usr/bin/env python3
"""
Quick "reality check" diagnostics for AI Quant (paper + live).

Why this exists:
- sqlite3 CLI might not be available
- timestamp strings are ISO-8601 ("2026-02-06T..."), so filtering should use datetime(timestamp)

Usage:
  ./.venv/bin/python3 tools/reality_check.py --symbol BTC --hours 2

Optional:
  AI_QUANT_MARKET_DB_PATH=/path/to/market_data.db AI_QUANT_INTERVAL=1m \
    ./.venv/bin/python3 tools/reality_check.py --symbol BTC
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path


AIQ_ROOT = Path(__file__).resolve().parents[1]

if str(AIQ_ROOT) not in sys.path:
    sys.path.insert(0, str(AIQ_ROOT))


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path), timeout=3.0)
    con.row_factory = sqlite3.Row
    return con


def _print_section(title: str) -> None:
    print("\n" + title)
    print("-" * len(title))


def _audit_counts(con: sqlite3.Connection, *, symbol: str, hours: float) -> list[tuple[str, int]]:
    cur = con.cursor()
    rows = cur.execute(
        """
        SELECT event, COUNT(*) AS n
        FROM audit_events
        WHERE symbol = ?
          AND datetime(timestamp) >= datetime('now', ?)
        GROUP BY event
        ORDER BY n DESC
        """,
        (symbol, f"-{hours} hours"),
    ).fetchall()
    out: list[tuple[str, int]] = []
    for r in rows:
        ev = str(r["event"] or "")
        try:
            n = int(r["n"] or 0)
        except Exception:
            n = 0
        if ev:
            out.append((ev, n))
    return out


def _recent_trades(con: sqlite3.Connection, *, symbol: str, limit: int = 10) -> list[dict]:
    cur = con.cursor()
    rows = cur.execute(
        """
        SELECT id, timestamp, action, type, price, size, reason, confidence
        FROM trades
        WHERE symbol = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (symbol, int(limit)),
    ).fetchall()
    return [dict(r) for r in rows]


def _print_db(name: str, db_path: Path, *, symbol: str, hours: float) -> None:
    _print_section(f"{name}: {db_path}")
    if not db_path.exists():
        print("missing db")
        return

    try:
        con = _connect(db_path)
    except Exception as e:
        print(f"db_open_failed: {e}")
        return

    try:
        counts = _audit_counts(con, symbol=symbol, hours=hours)
        print(f"audit_events counts for {symbol} (last {hours:g}h):")
        if not counts:
            print("  (none)")
        else:
            for ev, n in counts[:50]:
                print(f"  {ev}: {n}")

        print(f"\nrecent trades for {symbol}:")
        trades = _recent_trades(con, symbol=symbol, limit=10)
        if not trades:
            print("  (none)")
        else:
            for t in trades:
                print(
                    f"  id={t.get('id')} ts={t.get('timestamp')} action={t.get('action')} "
                    f"type={t.get('type')} px={t.get('price')} sz={t.get('size')} conf={t.get('confidence')} "
                    f"reason={t.get('reason')}"
                )
    finally:
        try:
            con.close()
        except Exception:
            pass


def _print_candle_health(*, symbol: str) -> None:
    _print_section("Candles (Sidecar) Health")

    interval = str(os.getenv("AI_QUANT_INTERVAL", "1m") or "1m").strip() or "1m"
    db_path = Path(str(os.getenv("AI_QUANT_MARKET_DB_PATH", str(AIQ_ROOT / "market_data.db"))))

    print(f"AI_QUANT_INTERVAL={interval}")
    print(f"AI_QUANT_MARKET_DB_PATH={db_path}")

    try:
        from engine.market_data import MarketDataHub
    except Exception as e:
        print(f"import_failed: {e}")
        return

    try:
        hub = MarketDataHub(db_path=str(db_path))
    except Exception as e:
        print(f"hub_init_failed: {e}")
        return

    try:
        ready, not_ready = hub.candles_ready(symbols=[symbol], interval=interval)
        print("candles_ready:", bool(ready), "not_ready:", not_ready)
    except Exception as e:
        print(f"candles_ready_failed: {e}")

    try:
        print("ws_health:", hub.health(symbols=[symbol], interval=interval))
    except Exception as e:
        print(f"ws_health_failed: {e}")

    try:
        print("candles_health:", hub.candles_health(symbols=[symbol], interval=interval))
    except Exception as e:
        print(f"candles_health_failed: {e}")


def _bootstrap_sidecar_env_defaults() -> None:
    os.environ.setdefault("AI_QUANT_WS_SOURCE", "sidecar")
    os.environ.setdefault("AI_QUANT_CANDLES_SOURCE", "sidecar")
    if not os.getenv("AI_QUANT_WS_SIDECAR_SOCK"):
        runtime_dir = os.getenv("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
        cand = os.path.join(runtime_dir, "openclaw-ai-quant-ws.sock")
        if os.path.exists(cand):
            os.environ["AI_QUANT_WS_SIDECAR_SOCK"] = cand


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTC")
    ap.add_argument("--hours", type=float, default=2.0)
    args = ap.parse_args()

    symbol = str(args.symbol or "").strip().upper()
    if not symbol:
        raise SystemExit("missing --symbol")

    paper_db = Path(str(os.getenv("AI_QUANT_PAPER_DB_PATH", str(AIQ_ROOT / "trading_engine.db"))))
    live_db = Path(str(os.getenv("AI_QUANT_LIVE_DB_PATH", str(AIQ_ROOT / "trading_engine_live.db"))))

    _print_db("Paper", paper_db, symbol=symbol, hours=float(args.hours))
    _print_db("Live", live_db, symbol=symbol, hours=float(args.hours))
    _bootstrap_sidecar_env_defaults()
    _print_candle_health(symbol=symbol)


if __name__ == "__main__":
    main()
