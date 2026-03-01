#!/usr/bin/env python3
"""Export live or paper trading state to JSON for backtester --init-state.

Usage:
    python export_state.py --source paper --output state.json
    python export_state.py --source live  --output state.json
"""

import argparse
import json
import os
import sqlite3
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DEFAULT_SECRETS_PATH = os.path.expanduser("~/.config/openclaw/ai-quant-secrets.json")

# ---------------------------------------------------------------------------
# Paper state export (reconstruct from SQLite — mirrors PaperTrader.load_state)
# ---------------------------------------------------------------------------

def _paper_db_path() -> str:
    return os.path.join(PROJECT_DIR, "trading_engine.db")


def _live_db_path() -> str:
    return os.path.join(PROJECT_DIR, "trading_engine_live.db")


def _reconstruct_positions_from_db(db_path: str) -> tuple[float, list[dict]]:
    """Reconstruct open positions + latest balance from a trading DB.

    Logic mirrors PaperTrader.load_state() in mei_alpha_v1.py.
    Returns (balance, [position_dicts]).
    """
    if not os.path.exists(db_path):
        print(f"[export] DB not found: {db_path}", file=sys.stderr)
        return 0.0, []

    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row

    # Stage 1: latest balance
    row = conn.execute("SELECT balance FROM trades ORDER BY id DESC LIMIT 1").fetchone()
    balance = float(row["balance"]) if row else 0.0

    # Stage 2: identify open positions
    # Last OPEN per symbol vs last CLOSE per symbol; positions where OPEN > CLOSE
    sql_open = """
    SELECT t.id AS open_id, t.timestamp AS open_ts, t.symbol, t.type AS pos_type,
           t.price AS open_px, t.size AS open_sz, t.confidence,
           t.entry_atr, t.leverage, t.margin_used
    FROM trades t
    INNER JOIN (
        SELECT symbol, MAX(id) AS open_id
        FROM trades WHERE action = 'OPEN' GROUP BY symbol
    ) lo ON t.id = lo.open_id
    LEFT JOIN (
        SELECT symbol, MAX(id) AS close_id
        FROM trades WHERE action = 'CLOSE' GROUP BY symbol
    ) lc ON t.symbol = lc.symbol
    WHERE lc.close_id IS NULL OR t.id > lc.close_id
    """
    open_rows = conn.execute(sql_open).fetchall()

    positions: list[dict] = []
    for orow in open_rows:
        open_id = orow["open_id"]
        symbol = orow["symbol"]
        pos_type = orow["pos_type"]
        avg_entry = float(orow["open_px"])
        net_size = float(orow["open_sz"])
        entry_atr = float(orow["entry_atr"] or 0.0)
        confidence = orow["confidence"] or "medium"
        leverage = float(orow["leverage"] or 1.0)
        margin_used = float(orow["margin_used"] or 0.0)
        open_ts = orow["open_ts"]

        # Stage 3: replay ADD / REDUCE fills to get net position
        fills = conn.execute(
            "SELECT action, price, size, entry_atr FROM trades "
            "WHERE symbol = ? AND id > ? AND action IN ('ADD', 'REDUCE') ORDER BY id ASC",
            (symbol, open_id),
        ).fetchall()

        for fill in fills:
            action = fill["action"]
            px = float(fill["price"])
            sz = float(fill["size"])
            fill_atr = float(fill["entry_atr"] or entry_atr)

            if action == "ADD":
                new_total = net_size + sz
                if new_total > 0:
                    avg_entry = (avg_entry * net_size + px * sz) / new_total
                    entry_atr = (entry_atr * net_size + fill_atr * sz) / new_total
                net_size = new_total
            elif action == "REDUCE":
                net_size -= sz
                if net_size <= 0:
                    break

        if net_size <= 0:
            continue

        # Stage 4: position_state metadata
        ps_row = conn.execute(
            "SELECT open_trade_id, trailing_sl, adds_count, tp1_taken, last_add_time, entry_adx_threshold "
            "FROM position_state WHERE symbol = ?",
            (symbol,),
        ).fetchone()

        trailing_sl = None
        adds_count = 0
        tp1_taken = False
        last_add_time_ms = 0
        entry_adx_threshold = 0.0

        # Parse open_ts to ms (best-effort). position_state rows may be missing in older DBs.
        open_time_ms = 0
        if open_ts:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(open_ts.replace("Z", "+00:00"))
                open_time_ms = int(dt.timestamp() * 1000)
            except Exception:
                # If timestamp parsing fails, leave open_time_ms as 0 and continue export.
                pass

        if ps_row and ps_row["open_trade_id"] == open_id:
            trailing_sl = float(ps_row["trailing_sl"]) if ps_row["trailing_sl"] is not None else None
            adds_count = int(ps_row["adds_count"] or 0)
            tp1_taken = bool(ps_row["tp1_taken"])
            last_add_time_ms = int(ps_row["last_add_time"] or 0)
            entry_adx_threshold = float(ps_row["entry_adx_threshold"] or 0)

        side = "long" if pos_type == "LONG" else "short"

        positions.append({
            "symbol": symbol,
            "side": side,
            "size": round(net_size, 10),
            "entry_price": round(avg_entry, 10),
            "entry_atr": round(entry_atr, 10),
            "trailing_sl": round(trailing_sl, 10) if trailing_sl is not None else None,
            "confidence": confidence.lower(),
            "leverage": leverage,
            "margin_used": round(margin_used, 4),
            "adds_count": adds_count,
            "tp1_taken": tp1_taken,
            "open_time_ms": open_time_ms,
            "last_add_time_ms": last_add_time_ms,
            "entry_adx_threshold": round(entry_adx_threshold, 4),
        })

    conn.close()
    return balance, positions


# ---------------------------------------------------------------------------
# Live state export (uses HyperliquidLiveExecutor)
# ---------------------------------------------------------------------------

def _export_live() -> tuple[float, list[dict]]:
    """Export live positions via Hyperliquid API + live DB metadata."""
    sys.path.insert(0, PROJECT_DIR)
    from exchange.executor import load_live_secrets, HyperliquidLiveExecutor

    secrets_path = os.path.expanduser(
        str(os.getenv("AI_QUANT_SECRETS_PATH") or DEFAULT_SECRETS_PATH)
    )
    if not os.path.exists(secrets_path):
        print(
            f"[export] Secrets file not found at {secrets_path} "
            f"(set AI_QUANT_SECRETS_PATH or create {DEFAULT_SECRETS_PATH})",
            file=sys.stderr,
        )
        sys.exit(1)

    secrets = load_live_secrets(secrets_path)
    executor = HyperliquidLiveExecutor(
        secret_key=secrets.secret_key,
        main_address=secrets.main_address,
    )

    # Balance from account snapshot
    snap = executor.account_snapshot(force=True)
    balance = snap.account_value_usd

    # Exchange positions
    live_positions = executor.get_positions(force=True)
    if not live_positions:
        return balance, []

    # Enrich with DB metadata
    db_path = _live_db_path()
    conn = None
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row

    positions: list[dict] = []
    for symbol, pdata in live_positions.items():
        pos_type = pdata["type"]
        side = "long" if pos_type == "LONG" else "short"
        size = pdata["size"]
        entry_price = pdata["entry_price"]
        leverage = pdata["leverage"]
        margin_used = pdata["margin_used"]

        # Recover entry_atr + metadata from live DB
        entry_atr = 0.0
        trailing_sl = None
        adds_count = 0
        tp1_taken = False
        open_time_ms = 0
        last_add_time_ms = 0
        confidence = "medium"
        entry_adx_threshold = 0.0

        if conn:
            # entry_atr from last OPEN/ADD
            atr_row = conn.execute(
                "SELECT entry_atr FROM trades "
                "WHERE symbol = ? AND action IN ('OPEN', 'ADD') AND entry_atr IS NOT NULL "
                "ORDER BY id DESC LIMIT 1",
                (symbol,),
            ).fetchone()
            if atr_row:
                entry_atr = float(atr_row["entry_atr"] or 0.0)

            # confidence from last OPEN
            conf_row = conn.execute(
                "SELECT confidence, timestamp FROM trades "
                "WHERE symbol = ? AND action = 'OPEN' ORDER BY id DESC LIMIT 1",
                (symbol,),
            ).fetchone()
            if conf_row:
                confidence = (conf_row["confidence"] or "medium").lower()
                ts_str = conf_row["timestamp"]
                if ts_str:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        open_time_ms = int(dt.timestamp() * 1000)
                    except Exception:
                        pass

            # position_state
            ps_row = conn.execute(
                "SELECT trailing_sl, adds_count, tp1_taken, last_add_time, entry_adx_threshold "
                "FROM position_state WHERE symbol = ?",
                (symbol,),
            ).fetchone()
            if ps_row:
                trailing_sl = float(ps_row["trailing_sl"]) if ps_row["trailing_sl"] is not None else None
                adds_count = int(ps_row["adds_count"] or 0)
                tp1_taken = bool(ps_row["tp1_taken"])
                last_add_time_ms = int(ps_row["last_add_time"] or 0)
                entry_adx_threshold = float(ps_row["entry_adx_threshold"] or 0)

        positions.append({
            "symbol": symbol,
            "side": side,
            "size": round(size, 10),
            "entry_price": round(entry_price, 10),
            "entry_atr": round(entry_atr, 10),
            "trailing_sl": round(trailing_sl, 10) if trailing_sl is not None else None,
            "confidence": confidence,
            "leverage": leverage,
            "margin_used": round(margin_used, 4),
            "adds_count": adds_count,
            "tp1_taken": tp1_taken,
            "open_time_ms": open_time_ms,
            "last_add_time_ms": last_add_time_ms,
            "entry_adx_threshold": round(entry_adx_threshold, 4),
        })

    if conn:
        conn.close()

    return balance, positions


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Export live/paper state for backtester --init-state")
    parser.add_argument("--source", required=True, choices=["live", "paper"],
                        help="Which trading engine to export from")
    parser.add_argument("--output", required=True, help="Output JSON file path")
    args = parser.parse_args()

    print(f"[export] Exporting from {args.source}...", file=sys.stderr)

    if args.source == "paper":
        balance, positions = _reconstruct_positions_from_db(_paper_db_path())
    else:
        balance, positions = _export_live()

    state = {
        "version": 1,
        "source": args.source,
        "exported_at_ms": int(time.time() * 1000),
        "balance": round(balance, 4),
        "positions": positions,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")

    print(f"[export] Written to {args.output}", file=sys.stderr)
    print(f"[export] Balance: ${balance:.2f}, Positions: {len(positions)}", file=sys.stderr)
    for p in positions:
        print(f"  {p['symbol']:>6} {p['side']:>5} size={p['size']:.6f} "
              f"entry=${p['entry_price']:.4f} atr={p['entry_atr']:.4f} "
              f"lev={p['leverage']:.1f}x margin=${p['margin_used']:.2f}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
