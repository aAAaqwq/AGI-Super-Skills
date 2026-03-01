import sqlite3
import time
import json
import datetime

DB_PAPER = "/home/fol2hk/.openclaw/workspace/dev/ai_quant/trading_engine.db"
DB_LIVE = "/home/fol2hk/.openclaw/workspace/dev/ai_quant/trading_engine_live.db"
DB_CANDLES = "/home/fol2hk/.openclaw/workspace/dev/ai_quant/candles_dbs/candles_1m.db"

results = {}


def get_heartbeat(db_path):
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT message FROM runtime_logs WHERE message LIKE '🫀 engine ok%' ORDER BY ts_ms DESC LIMIT 1")
        row = c.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        return str(e)


def get_perf_60m(db_path):
    try:
        # Calculate cutoff time (60 mins ago)
        cutoff_dt = datetime.datetime.utcnow() - datetime.timedelta(minutes=60)
        cutoff_iso = cutoff_dt.isoformat()

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # PnL Summary
        c.execute(
            """
            SELECT count(*) as count, sum(pnl) as pnl, sum(fee_usd) as fees,
                   count(CASE WHEN pnl > 0 THEN 1 END) as wins
            FROM trades
            WHERE timestamp > ? AND action IN ('OPEN', 'CLOSE', 'ADD', 'REDUCE', 'SL', 'TP', 'LIQ')
        """,
            (cutoff_iso,),
        )
        summary = dict(c.fetchone())

        # Top Winners
        c.execute(
            """
            SELECT symbol, pnl, reason as exit_reason
            FROM trades
            WHERE timestamp > ? AND pnl > 0 AND action IN ('CLOSE', 'REDUCE', 'SL', 'TP', 'LIQ')
            ORDER BY pnl DESC LIMIT 3
        """,
            (cutoff_iso,),
        )
        winners = [dict(r) for r in c.fetchall()]

        # Top Losers
        c.execute(
            """
            SELECT symbol, pnl, reason as exit_reason
            FROM trades
            WHERE timestamp > ? AND pnl < 0 AND action IN ('CLOSE', 'REDUCE', 'SL', 'TP', 'LIQ')
            ORDER BY pnl ASC LIMIT 3
        """,
            (cutoff_iso,),
        )
        losers = [dict(r) for r in c.fetchall()]

        # Exit Reasons
        c.execute(
            """
            SELECT reason, count(*) as c
            FROM trades
            WHERE timestamp > ? AND action IN ('CLOSE', 'REDUCE', 'SL', 'TP', 'LIQ')
            GROUP BY reason
        """,
            (cutoff_iso,),
        )
        reasons = {r["reason"]: r["c"] for r in c.fetchall()}

        conn.close()
        return {"summary": summary, "winners": winners, "losers": losers, "reasons": reasons}
    except Exception as e:
        return {"error": str(e)}


def get_open_positions_live():
    try:
        conn_live = sqlite3.connect(DB_LIVE)
        conn_live.row_factory = sqlite3.Row
        c = conn_live.cursor()

        # Join position_state with trades to get entry details
        c.execute("""
            SELECT ps.symbol, t.type as direction, t.price as entry_price, t.size, t.notional,
                   t.leverage, t.margin_used, t.timestamp as entry_time_iso, t.confidence, t.reason,
                   ps.trailing_sl, ps.tp1_taken, ps.adds_count,
                   json_extract(t.meta_json, '$.breadth_pct') as entry_breadth
            FROM position_state ps
            JOIN trades t ON t.id = ps.open_trade_id
            WHERE ps.open_trade_id IS NOT NULL
        """)
        positions = [dict(r) for r in c.fetchall()]
        conn_live.close()

        # Get current prices from candles DB
        conn_candles = sqlite3.connect(DB_CANDLES)
        conn_candles.row_factory = sqlite3.Row
        cc = conn_candles.cursor()

        annotated = []
        summary = {"total_pos": 0, "total_margin": 0.0, "total_unrealized_pnl": 0.0, "longs": 0, "shorts": 0}

        for p in positions:
            cc.execute(
                "SELECT c, t FROM candles WHERE symbol = ? AND interval = '1m' ORDER BY t DESC LIMIT 1", (p["symbol"],)
            )
            row = cc.fetchone()

            current_price = row["c"] if row else None
            candle_ts = row["t"] if row else None

            p["current_price"] = current_price
            p["candle_ts"] = candle_ts

            # Calculate Unrealized PnL
            if current_price and p["entry_price"]:
                diff = current_price - p["entry_price"]
                if p["direction"] == "SHORT":
                    diff = -diff

                # Size is usually positive in trades table? Need to check. Assume positive.
                unrealized_pnl = diff * p["size"]
                p["unrealized_pnl"] = unrealized_pnl

                margin = p["margin_used"] if p["margin_used"] else 0
                p["pnl_pct"] = (unrealized_pnl / margin * 100) if margin > 0 else 0

                # Duration
                try:
                    entry_dt = datetime.datetime.fromisoformat(p["entry_time_iso"])
                    duration_min = (datetime.datetime.utcnow() - entry_dt).total_seconds() / 60
                    p["duration_min"] = duration_min
                except Exception:
                    p["duration_min"] = 0
            else:
                p["unrealized_pnl"] = 0.0
                p["pnl_pct"] = 0.0
                p["duration_min"] = 0

            annotated.append(p)

            # Summary stats
            summary["total_pos"] += 1
            summary["total_margin"] += p["margin_used"] or 0
            summary["total_unrealized_pnl"] += p.get("unrealized_pnl", 0) or 0
            if p["direction"] == "LONG":
                summary["longs"] += 1
            elif p["direction"] == "SHORT":
                summary["shorts"] += 1

        conn_candles.close()
        return {"positions": annotated, "summary": summary}
    except Exception as e:
        return {"error": str(e)}


def get_oms_health():
    try:
        ts_cutoff_ms = (time.time() - 3600) * 1000
        conn = sqlite3.connect(DB_LIVE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute(
            "SELECT status, count(*) as c FROM oms_intents WHERE created_ts_ms > ? GROUP BY status", (ts_cutoff_ms,)
        )
        intents = {r["status"]: r["c"] for r in c.fetchall()}

        c.execute("SELECT count(*) as c FROM oms_fills WHERE intent_id IS NULL AND ts_ms > ?", (ts_cutoff_ms,))
        unmatched_fills = c.fetchone()["c"]

        c.execute("SELECT count(*) as c FROM oms_open_orders")
        open_orders = c.fetchone()["c"]

        c.execute(
            "SELECT count(*) as c FROM oms_reconcile_events WHERE ts_ms > ? AND action='CANCEL_STALE'", (ts_cutoff_ms,)
        )
        cancels = c.fetchone()["c"]

        conn.close()
        return {"intents": intents, "unmatched_fills": unmatched_fills, "open_orders": open_orders, "cancels": cancels}
    except Exception as e:
        return {"error": str(e)}


results["paper_heartbeat"] = get_heartbeat(DB_PAPER)
results["live_heartbeat"] = get_heartbeat(DB_LIVE)
results["paper_perf"] = get_perf_60m(DB_PAPER)
results["live_perf"] = get_perf_60m(DB_LIVE)
results["open_positions"] = get_open_positions_live()
results["oms_health"] = get_oms_health()

print(json.dumps(results, indent=2))
