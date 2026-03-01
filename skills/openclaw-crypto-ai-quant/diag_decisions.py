#!/usr/bin/env python3
"""Simulate PythonAnalyzeDecisionProvider.get_decisions() in isolation."""
import os, sys, time, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set env to match livepaper service
os.environ.setdefault("AI_QUANT_WS_SOURCE", "sidecar")
os.environ.setdefault("AI_QUANT_WS_SIDECAR_SOCK", f"/run/user/{os.getuid()}/openclaw-ai-quant-ws.sock")
os.environ.setdefault("AI_QUANT_CANDLES_SOURCE", "sidecar")
os.environ.setdefault("AI_QUANT_CANDLES_DB_DIR", "/home/fol2hk/.openclaw/workspace/dev/ai_quant/candles_dbs")
os.environ.setdefault("AI_QUANT_INTERVAL", "30m")
os.environ.setdefault("AI_QUANT_LOOKBACK_BARS", "200")
os.environ.setdefault("AI_QUANT_STRATEGY_YAML", "/home/fol2hk/openclaw-plugins/ai_quant_wt/major-v8-runtime/config/strategy_overrides.livepaper.yaml")

from engine.market_data import MarketDataHub
from engine.strategy_manager import StrategyManager
from strategy import mei_alpha_v1

INTERVAL = "30m"
LOOKBACK = 200
DB_PATH = "/home/fol2hk/openclaw-plugins/ai_quant_wt/major-v8-runtime/market_data_v8_livepaper.db"

mdhub = MarketDataHub(db_path=DB_PATH)
print(f"MarketDataHub created, sidecar={mdhub._use_interval_candle_dbs}")

# Get watchlist
strat_mgr = StrategyManager.get()
watchlist = strat_mgr.get_watchlist()
print(f"Watchlist: {len(watchlist)} symbols")
print(f"First 10: {watchlist[:10]}")

# BTC context
btc_bullish = None
try:
    btc_df = mdhub.get_candles_df("BTC", interval=INTERVAL, min_rows=LOOKBACK)
    if btc_df is not None and not btc_df.empty and len(btc_df) >= LOOKBACK:
        import ta
        ema50 = ta.trend.ema_indicator(btc_df["Close"], window=50).iloc[-1]
        btc_bullish = bool(btc_df["Close"].iloc[-1] > ema50)
        print(f"BTC context: bullish={btc_bullish}, ema50={ema50:.2f}, price={btc_df['Close'].iloc[-1]:.2f}")
    else:
        print(f"BTC context: df is None or too short: {len(btc_df) if btc_df is not None else None}")
except Exception as e:
    print(f"BTC context error: {e}")

# candles_ready
try:
    ready_list, not_ready = mdhub.candles_ready(symbols=watchlist[:20], interval=INTERVAL)
    print(f"candles_ready: ready_list type={type(ready_list)}, not_ready={not_ready[:5] if not_ready else []}")
except Exception as e:
    print(f"candles_ready error: {e}")

not_ready_set = set()

# Test first 10 symbols
print(f"\n--- Analyzing first 10 watchlist symbols (interval={INTERVAL}, lookback={LOOKBACK}) ---")
for sym in watchlist[:10]:
    sym_u = sym.upper().strip()
    if sym_u in not_ready_set:
        print(f"  {sym_u}: SKIP (not ready)")
        continue
    try:
        t0 = time.time()
        df_raw = mdhub.get_candles_df(sym_u, interval=INTERVAL, min_rows=LOOKBACK)
        t_fetch = time.time() - t0
        
        if df_raw is None:
            print(f"  {sym_u}: df=None (fetch={t_fetch:.3f}s)")
            continue
        if df_raw.empty:
            print(f"  {sym_u}: df=empty (fetch={t_fetch:.3f}s)")
            continue
        if len(df_raw) < LOOKBACK:
            print(f"  {sym_u}: df too short ({len(df_raw)}<{LOOKBACK}) (fetch={t_fetch:.3f}s)")
            continue
            
        df = df_raw.tail(LOOKBACK).copy()
        t1 = time.time()
        sig, conf, now_series = mei_alpha_v1.analyze(df, sym_u, btc_bullish=btc_bullish)
        t_analyze = time.time() - t1
        
        ns_type = type(now_series).__name__
        print(f"  {sym_u}: sig={sig} conf={conf} (fetch={t_fetch:.3f}s analyze={t_analyze:.3f}s now_type={ns_type})")
    except Exception as e:
        print(f"  {sym_u}: ERROR: {e}")
        traceback.print_exc()
