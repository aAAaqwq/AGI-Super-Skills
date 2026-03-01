import sqlite3
import json
import time

paper_db_path = '/home/fol2hk/.openclaw/workspace/dev/ai_quant/trading_engine.db'
live_db_path = '/home/fol2hk/.openclaw/workspace/dev/ai_quant/trading_engine_live.db'
candles_db_path = '/home/fol2hk/.openclaw/workspace/dev/ai_quant/candles_dbs/candles_1m.db'

def get_heartbeat(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT message FROM runtime_logs WHERE message LIKE '🫀 engine ok%' ORDER BY ts_ms DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            msg = row[0]
            # Parse the message: "🫀 engine ok. symbols=44 open_pos=1 loop=0.04s ws_restarts=0 strategy_sha1=e9a0e63 version=v5.089"
            data = {}
            parts = msg.split()
            for part in parts:
                if '=' in part:
                    k, v = part.split('=', 1)
                    data[k] = v
            return data
        return None
    except Exception as e:
        return {"error": str(e)}

def get_performance(db_path):
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get trades from last 1 hour
        # timestamp is TEXT ISO8601 e.g. '2026-02-10T05:00:00.123456'
        cursor.execute("SELECT * FROM trades WHERE timestamp >= datetime('now', '-1 hour') AND action IN ('CLOSE', 'STOP_LOSS', 'TAKE_PROFIT')")
        trades = [dict(row) for row in cursor.fetchall()]

        stats = {
            "count": len(trades),
            "pnl": sum(t['pnl'] for t in trades if t['pnl'] is not None),
            "fees": sum(t['fee_usd'] for t in trades if t['fee_usd'] is not None),
            "wins": len([t for t in trades if t['pnl'] is not None and t['pnl'] > 0]),
            "losses": len([t for t in trades if t['pnl'] is not None and t['pnl'] <= 0]),
            "reasons": {},
            "top_winners": [],
            "top_losers": []
        }

        if stats['count'] > 0:
            stats['win_rate'] = (stats['wins'] / stats['count']) * 100
        else:
            stats['win_rate'] = 0.0

        for t in trades:
            r = t['reason'] or 'UNKNOWN'
            stats['reasons'][r] = stats['reasons'].get(r, 0) + 1

        sorted_trades = sorted(trades, key=lambda x: x['pnl'] if x['pnl'] is not None else 0, reverse=True)
        stats['top_winners'] = [{'s': t['symbol'], 'p': t['pnl']} for t in sorted_trades[:3] if t['pnl'] > 0]
        stats['top_losers'] = [{'s': t['symbol'], 'p': t['pnl']} for t in sorted_trades[-3:] if t['pnl'] < 0]

        conn.close()
        return stats
    except Exception as e:
        return {"error": str(e)}

def get_open_positions_live():
    try:
        conn = sqlite3.connect(live_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

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
        positions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return positions
    except Exception as e:
        return {"error": str(e)}

def get_current_prices(symbols):
    prices = {}
    try:
        conn = sqlite3.connect(candles_db_path)
        cursor = conn.cursor()
        for sym in symbols:
            cursor.execute("SELECT c FROM candles WHERE symbol = ? AND interval = '1m' ORDER BY t DESC LIMIT 1", (sym,))
            row = cursor.fetchone()
            if row:
                prices[sym] = row[0]
        conn.close()
    except Exception:
        pass
    return prices

def get_oms_health(db_path):
    stats = {}
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        now_ms = int(time.time() * 1000)
        start_ms = now_ms - 3600000 # 1 hour

        # OMS Intents count by status
        cursor.execute("SELECT status, COUNT(*) as cnt FROM oms_intents WHERE created_ts_ms >= ? GROUP BY status", (start_ms,))
        stats['intents_status'] = {row['status']: row['cnt'] for row in cursor.fetchall()}

        # Unmatched fills
        cursor.execute("SELECT COUNT(*) as cnt FROM oms_fills WHERE ts_ms >= ? AND intent_id IS NULL", (start_ms,))
        stats['unmatched_fills'] = cursor.fetchone()['cnt']

        # Open orders
        cursor.execute("SELECT COUNT(*) as cnt FROM oms_open_orders")
        stats['open_orders'] = cursor.fetchone()['cnt']

        # Reconcile events (cancels) - 'kind' instead of 'type' in schema? Schema says 'kind'.
        cursor.execute("SELECT COUNT(*) as cnt FROM oms_reconcile_events WHERE ts_ms >= ? AND kind='CANCEL_LOOP'", (start_ms,))
        stats['cancel_loops'] = cursor.fetchone()['cnt']

        # Latest cancels
        cursor.execute("SELECT symbol, result FROM oms_reconcile_events WHERE ts_ms >= ? ORDER BY ts_ms DESC LIMIT 5", (start_ms,))
        stats['latest_cancels'] = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return stats
    except Exception as e:
        return {"error": str(e)}

results = {
    "paper_hb": get_heartbeat(paper_db_path),
    "live_hb": get_heartbeat(live_db_path),
    "paper_perf": get_performance(paper_db_path),
    "live_perf": get_performance(live_db_path),
    "oms": get_oms_health(live_db_path),
    "positions": []
}

# Process positions
pos_data = get_open_positions_live()
if isinstance(pos_data, list):
    symbols = [p['symbol'] for p in pos_data]
    prices = get_current_prices(symbols)

    total_unrealized_pnl = 0
    total_margin = 0

    for p in pos_data:
        sym = p['symbol']
        cp = prices.get(sym)
        if cp:
            if p['type'] == 'LONG':
                upnl = (cp - p['entry_price']) * p['size']
            else:
                upnl = (p['entry_price'] - cp) * p['size']

            p['current_price'] = cp
            p['unrealized_pnl'] = upnl
            p['pnl_pct_margin'] = (upnl / p['margin_used'] * 100) if p['margin_used'] else 0

            total_unrealized_pnl += upnl
            total_margin += p['margin_used']
        else:
            p['current_price'] = None
            p['unrealized_pnl'] = 0
            p['pnl_pct_margin'] = 0

    results['positions'] = pos_data
    results['positions_summary'] = {
        'count': len(pos_data),
        'total_margin': total_margin,
        'total_unrealized_pnl': total_unrealized_pnl
    }
else:
    results['positions_error'] = pos_data

print(json.dumps(results, default=str))
