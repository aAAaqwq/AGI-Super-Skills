#!/usr/bin/env python3
"""Candle window provenance helpers for deterministic replay bundles."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


def _connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _normalise_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def build_candles_window_provenance(
    candles_db: Path,
    *,
    interval: str,
    from_ts: int,
    to_ts: int,
) -> dict[str, Any]:
    """Build a deterministic provenance fingerprint for one candle window."""
    conn = _connect_ro(candles_db)
    hasher = hashlib.sha256()
    symbols: set[str] = set()
    row_count = 0
    min_t: int | None = None
    max_t: int | None = None

    try:
        rows = conn.execute(
            "SELECT symbol, t, t_close, o, h, l, c, v, n "
            "FROM candles "
            "WHERE interval = ? AND t >= ? AND t <= ? "
            "ORDER BY symbol ASC, t ASC",
            (str(interval), int(from_ts), int(to_ts)),
        )
        for row in rows:
            symbol = str(row["symbol"] or "").strip().upper()
            t_val = int(row["t"])
            payload = {
                "symbol": symbol,
                "t": t_val,
                "t_close": int(row["t_close"]) if row["t_close"] is not None else None,
                "o": _normalise_float(row["o"]),
                "h": _normalise_float(row["h"]),
                "l": _normalise_float(row["l"]),
                "c": _normalise_float(row["c"]),
                "v": _normalise_float(row["v"]),
                "n": int(row["n"]) if row["n"] is not None else None,
            }
            encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
            hasher.update(encoded)
            hasher.update(b"\n")

            symbols.add(symbol)
            row_count += 1
            min_t = t_val if min_t is None else min(min_t, t_val)
            max_t = t_val if max_t is None else max(max_t, t_val)
    finally:
        conn.close()

    symbol_list = sorted(s for s in symbols if s)
    universe_hasher = hashlib.sha256()
    for symbol in symbol_list:
        universe_hasher.update(symbol.encode("utf-8"))
        universe_hasher.update(b"\n")

    return {
        "interval": str(interval),
        "from_ts": int(from_ts),
        "to_ts": int(to_ts),
        "window_hash_sha256": hasher.hexdigest(),
        "universe_hash_sha256": universe_hasher.hexdigest(),
        "symbols": symbol_list,
        "symbol_count": len(symbol_list),
        "row_count": int(row_count),
        "min_t": int(min_t) if min_t is not None else None,
        "max_t": int(max_t) if max_t is not None else None,
    }
