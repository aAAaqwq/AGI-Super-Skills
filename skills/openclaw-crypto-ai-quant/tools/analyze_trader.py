import sqlite3
import json
import time
import os
from datetime import datetime, timedelta

PAPER_DB = "/home/fol2hk/.openclaw/workspace/dev/ai_quant/trading_engine.db"
LIVE_DB = "/home/fol2hk/.openclaw/workspace/dev/ai_quant/trading_engine_live.db"
CANDLES_DB = "/home/fol2hk/.openclaw/workspace/dev/ai_quant/candles_dbs/candles_1m.db"

def get_db_connection(db_file):
    if not os.path.exists(db_file):
        return None
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    return conn

def get_heartbeat(conn):
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM runtime_logs WHERE message LIKE '🫀 engine ok%' ORDER BY ts_ms DESC LIMIT 1")
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        return {"error": str(e)}

def get_performance(conn, minutes=60):
    if not conn:
        return None
    try:
        cutoff_dt = datetime.utcnow() - timedelta(minutes=minutes)
        cutoff_iso = cutoff_dt.isoformat()

        cursor = conn.cursor()
        cursor.execute("SELECT count(*) as count, sum(pnl) as total_pnl, sum(fee_usd) as total_fee, sum(case when pnl > 0 then 1 else 0 end) as wins FROM trades WHERE timestamp > ? AND action = 'CLOSE'", (cutoff_iso,))
        stats = dict(cursor.fetchone())

        cursor.execute("SELECT symbol, pnl FROM trades WHERE timestamp > ? AND action = 'CLOSE' ORDER BY pnl DESC LIMIT 3", (cutoff_iso,))
        winners = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT symbol, pnl FROM trades WHERE timestamp > ? AND action = 'CLOSE' ORDER BY pnl ASC LIMIT 3", (cutoff_iso,))
        losers = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT reason, count(*) as c FROM trades WHERE timestamp > ? AND action = 'CLOSE' GROUP BY reason", (cutoff_iso,))
        reasons = {r['reason']: r['c'] for r in cursor.fetchall()}

        return {"stats": stats, "winners": winners, "losers": losers, "reasons": reasons}
    except Exception as e:
        return {"error": str(e)}

def get_open_positions(live_conn, candles_conn):
    if not live_conn:
        return None
    try:
        cursor = live_conn.cursor()
        query = """
        SELECT ps.symbol, t.type, t.price AS entry_price, t.size, t.notional,
               t.leverage, t.margin_used, t.timestamp AS entry_time, t.confidence, t.reason,
               ps.trailing_sl, ps.adds_count, ps.tp1_taken,
               json_extract(t.meta_json, '$.breadth_pct') AS entry_breadth_pct
        FROM position_state ps
        JOIN trades t ON t.id = ps.open_trade_id
        WHERE ps.open_trade_id IS NOT NULL
        ORDER BY t.timestamp ASC
        """
        cursor.execute(query)
        positions = [dict(r) for r in cursor.fetchall()]

        enriched_positions = []
        if candles_conn:
            c_cursor = candles_conn.cursor()
            for p in positions:
                c_cursor.execute("SELECT c, t FROM candles WHERE symbol = ? AND interval = '1m' ORDER BY t DESC LIMIT 1", (p['symbol'],))
                candle = c_cursor.fetchone()
                if candle:
                    current_price = candle['c']
                    entry_price = p['entry_price']
                    size = p['size']

                    pnl = 0
                    direction = str(p['type']).upper()
                    if 'LONG' in direction or 'BUY' in direction:
                        pnl = (current_price - entry_price) * size
                    elif 'SHORT' in direction or 'SELL' in direction:
                        pnl = (entry_price - current_price) * size

                    p['current_price'] = current_price
                    p['unrealized_pnl'] = pnl
                    p['pnl_pct'] = (pnl / p['margin_used'] * 100) if p['margin_used'] else 0
                    p['candle_ts'] = candle['t']
                enriched_positions.append(p)
        else:
            enriched_positions = positions

        return enriched_positions
    except Exception as e:
        return {"error": str(e)}

def get_oms_health(conn, minutes=60):
    if not conn:
        return None
    try:
        cutoff_ms = (time.time() - minutes * 60) * 1000
        cursor = conn.cursor()

        # Intents status counts
        # oms_intents uses created_ts_ms (INTEGER)
        cursor.execute("SELECT status, count(*) as c FROM oms_intents WHERE created_ts_ms > ? GROUP BY status", (cutoff_ms,))
        intents_status = {r['status']: r['c'] for r in cursor.fetchall()}

        # Unmatched fills
        # oms_fills uses ts_ms (INTEGER)
        cursor.execute("SELECT count(*) as c FROM oms_fills WHERE ts_ms > ? AND intent_id IS NULL", (cutoff_ms,))
        unmatched_fills = cursor.fetchone()['c']

        # Open orders
        # oms_open_orders doesn't track history well, just current snapshot
        cursor.execute("SELECT count(*) as c FROM oms_open_orders")
        open_orders = cursor.fetchone()['c']

        # Cancels/Reconciles
        # oms_reconcile_events uses ts_ms (INTEGER) and kind (TEXT)
        cursor.execute("SELECT count(*) as c FROM oms_reconcile_events WHERE ts_ms > ? AND kind LIKE '%CANCEL%'", (cutoff_ms,))
        cancels = cursor.fetchone()['c']

        return {
            "intents_status": intents_status,
            "unmatched_fills": unmatched_fills,
            "open_orders": open_orders,
            "cancels": cancels
        }
    except Exception as e:
        return {"error": str(e)}

results = {}

# Paper
p_conn = get_db_connection(PAPER_DB)
results['paper_heartbeat'] = get_heartbeat(p_conn)
results['paper_perf'] = get_performance(p_conn)
if p_conn:
    p_conn.close()

# Live
l_conn = get_db_connection(LIVE_DB)
c_conn = get_db_connection(CANDLES_DB)

results['live_heartbeat'] = get_heartbeat(l_conn)
results['live_perf'] = get_performance(l_conn)
results['oms_health'] = get_oms_health(l_conn)
results['positions'] = get_open_positions(l_conn, c_conn)

if l_conn:
    l_conn.close()
if c_conn:
    c_conn.close()

print(json.dumps(results, indent=2, default=str))
