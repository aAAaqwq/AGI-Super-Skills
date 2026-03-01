#!/usr/bin/env python3
"""
Generate a small, fixed candle fixture for GPU/CPU parity tests.

This script is intended for maintainers only (it reads the local SQLite candle DBs).

Usage:
  python3 backtester/testdata/gpu_cpu_parity/generate_candles_fixture.py \
    --db candles_dbs/candles_1h.db \
    --interval 1h \
    --symbols BTC ETH SOL \
    --limit 600 \
    --out backtester/testdata/gpu_cpu_parity/candles_1h.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _fetch_bars(conn: sqlite3.Connection, symbol: str, interval: str, limit: int) -> list[dict]:
    cur = conn.execute(
        """
        SELECT t, t_close, o, h, l, c, v, n
        FROM candles
        WHERE symbol = ? AND interval = ?
        ORDER BY t DESC
        LIMIT ?
        """,
        (symbol, interval, limit),
    )
    rows = cur.fetchall()
    rows.reverse()

    out: list[dict] = []
    for (t, t_close, o, h, l, c, v, n) in rows:
        out.append(
            {
                "t": int(t),
                "t_close": int(t_close) if t_close is not None else None,
                "o": float(o),
                "h": float(h),
                "l": float(l),
                "c": float(c),
                "v": float(v),
                "n": int(n),
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="Path to candles SQLite DB (e.g. candles_dbs/candles_1h.db)")
    ap.add_argument("--interval", required=True, help="Interval string stored in DB (e.g. 1h)")
    ap.add_argument("--symbols", nargs="+", required=True, help="Symbols to extract (e.g. BTC ETH SOL)")
    ap.add_argument("--limit", type=int, default=600, help="Bars per symbol (default: 600)")
    ap.add_argument("--out", required=True, help="Output JSON path")
    args = ap.parse_args()

    root = _project_root()
    db_path = (root / args.db).resolve()
    out_path = (root / args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, list[dict]] = {}
    with sqlite3.connect(str(db_path)) as conn:
        for sym in args.symbols:
            bars = _fetch_bars(conn, sym, args.interval, args.limit)
            if not bars:
                raise SystemExit(f"No bars found for symbol={sym} interval={args.interval}")
            data[sym] = bars

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")

    # Print basic metadata for reproducibility.
    meta = {}
    for sym, bars in data.items():
        meta[sym] = {
            "count": len(bars),
            "start_t": bars[0]["t"],
            "end_t": bars[-1]["t"],
        }
    print(json.dumps({"db": str(db_path), "interval": args.interval, "symbols": args.symbols, "meta": meta}, indent=2))


if __name__ == "__main__":
    main()

