#!/usr/bin/env python3
"""Direct DB read test — replicate _read_candles_from_db exactly."""
import sqlite3, os, sys, time, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB_DIR = "/home/fol2hk/.openclaw/workspace/dev/ai_quant/candles_dbs"
INTERVAL = "30m"
SYMBOL = "BTC"
LIMIT = 250

db_path = os.path.join(DB_DIR, f"candles_{INTERVAL}.db")
print(f"DB: {db_path}")
print(f"exists: {os.path.exists(db_path)}")

# Test 1: exact query from market_data.py
conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
cur = conn.cursor()
try:
    cur.execute("""
        SELECT t, T, o, h, l, c, v, n
        FROM candles
        WHERE symbol = ? AND interval = ?
        ORDER BY t DESC
        LIMIT ?
    """, (SYMBOL, INTERVAL, LIMIT))
    rows = cur.fetchall()
    print(f"\nQuery 'SELECT t, T, ...': returned {len(rows)} rows")
    if rows:
        print(f"  First row: {rows[0]}")
        print(f"  Note: T value = {rows[0][1]} (same as t = {rows[0][0]}? {rows[0][0]==rows[0][1]})")
except Exception as e:
    print(f"Query 'SELECT t, T, ...' FAILED: {e}")
    traceback.print_exc()

# Test 2: correct query using t_close
try:
    cur.execute("""
        SELECT t, t_close, o, h, l, c, v, n
        FROM candles
        WHERE symbol = ? AND interval = ?
        ORDER BY t DESC
        LIMIT ?
    """, (SYMBOL, INTERVAL, LIMIT))
    rows2 = cur.fetchall()
    print(f"\nQuery 'SELECT t, t_close, ...': returned {len(rows2)} rows")
    if rows2:
        print(f"  First row: {rows2[0]}")
        print(f"  t_close = {rows2[0][1]} (different from t = {rows2[0][0]}? {rows2[0][0]!=rows2[0][1]})")
except Exception as e:
    print(f"Query 'SELECT t, t_close, ...' FAILED: {e}")
    traceback.print_exc()

conn.close()

# Test 3: test WS module
print("\n--- WS module test ---")
try:
    os.environ.setdefault("AI_QUANT_WS_SOURCE", "sidecar")
    os.environ.setdefault("AI_QUANT_WS_SIDECAR_SOCK", f"/run/user/{os.getuid()}/openclaw-ai-quant-ws.sock")
    import exchange.ws as ws
    candles = ws.hl_ws.get_candles_df(SYMBOL, INTERVAL, min_rows=200)
    if candles is None:
        print("WS get_candles_df: None")
    elif candles.empty:
        print("WS get_candles_df: empty")
    else:
        print(f"WS get_candles_df: {len(candles)} rows, cols={list(candles.columns)[:8]}")
except Exception as e:
    print(f"WS test failed: {e}")
    traceback.print_exc()

# Test 4: Full MarketDataHub
print("\n--- MarketDataHub test ---")
try:
    os.environ["AI_QUANT_CANDLES_SOURCE"] = "sidecar"
    os.environ["AI_QUANT_CANDLES_DB_DIR"] = DB_DIR
    from engine.market_data import MarketDataHub
    mdhub = MarketDataHub(db_path="/home/fol2hk/openclaw-plugins/ai_quant_wt/major-v8-runtime/market_data_v8_livepaper.db")
    print(f"_use_interval_candle_dbs: {mdhub._use_interval_candle_dbs}")
    print(f"_candles_db_dir: {mdhub._candles_db_dir}")
    
    candle_path = mdhub._candle_db_path(INTERVAL)
    print(f"_candle_db_path('{INTERVAL}'): {candle_path}")
    
    df = mdhub.get_candles_df(SYMBOL, interval=INTERVAL, min_rows=200)
    if df is None:
        print(f"get_candles_df: None")
    elif df.empty:
        print(f"get_candles_df: empty")
    else:
        print(f"get_candles_df: {len(df)} rows")
        print(f"  columns: {list(df.columns)}")
        print(f"  last row: {df.iloc[-1].to_dict()}")
except Exception as e:
    print(f"MarketDataHub test failed: {e}")
    traceback.print_exc()
