#!/usr/bin/env python3
"""Quick diagnostic: check if market data loads and analyze() fires."""
import sys, os, traceback, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load env from .env if exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from engine import market_data
from strategy import mei_alpha_v1

INTERVAL = os.getenv("AI_QUANT_ENTRY_INTERVAL", "5m") or "5m"
LOOKBACK = int(os.getenv("AI_QUANT_LOOKBACK_BARS", "100") or 100)
TEST_SYMS = ["BTC", "ETH", "SOL", "DOGE", "XRP"]

db_path = os.getenv("AI_QUANT_MARKET_DB_PATH", mei_alpha_v1.DB_PATH)
print(f"=== Signal Diagnostic ===")
print(f"interval={INTERVAL}  lookback={LOOKBACK}  db_path={db_path}")

# 1) Try to load MarketDataHub
try:
    mdhub = market_data.MarketDataHub(db_path=db_path)
    print(f"\n[1] MarketDataHub created: {type(mdhub)}")
except Exception as e:
    print(f"\n[1] FAIL: MarketDataHub creation: {e}")
    traceback.print_exc()
    sys.exit(1)

# 2) Ensure candles
try:
    mdhub.ensure(symbols=TEST_SYMS, interval=INTERVAL, candle_limit=LOOKBACK + 50)
    print(f"[2] ensure() OK")
except Exception as e:
    print(f"[2] FAIL ensure(): {e}")
    traceback.print_exc()

# 3) candles_ready?
try:
    ready, not_ready = mdhub.candles_ready(symbols=TEST_SYMS, interval=INTERVAL)
    print(f"[3] ready={ready}  not_ready={not_ready}")
except Exception as e:
    print(f"[3] FAIL candles_ready(): {e}")
    traceback.print_exc()

# 4) Get candle DF for each sym
for sym in TEST_SYMS:
    try:
        df = mdhub.get_candles_df(sym, interval=INTERVAL, min_rows=LOOKBACK)
        if df is None:
            print(f"[4] {sym}: get_candles_df -> None")
        elif df.empty:
            print(f"[4] {sym}: get_candles_df -> empty")
        else:
            print(f"[4] {sym}: rows={len(df)} cols={list(df.columns)[:8]} last_close={df['Close'].iloc[-1] if 'Close' in df.columns else '?'}")
    except Exception as e:
        print(f"[4] {sym}: FAIL get_candles_df: {e}")

# 5) BTC EMA for btc_bullish
btc_bullish = None
try:
    btc_df = mdhub.get_candles_df("BTC", interval=INTERVAL, min_rows=LOOKBACK)
    if btc_df is not None and len(btc_df) >= LOOKBACK:
        import ta
        ema50 = ta.trend.ema_indicator(btc_df["Close"], window=50).iloc[-1]
        btc_bullish = bool(btc_df["Close"].iloc[-1] > ema50)
        print(f"[5] btc_bullish={btc_bullish}  ema50={ema50:.2f}  price={btc_df['Close'].iloc[-1]:.2f}")
    else:
        print(f"[5] BTC df insufficient: {len(btc_df) if btc_df is not None else None}")
except Exception as e:
    print(f"[5] FAIL btc context: {e}")

# 6) Run analyze() on test symbols
for sym in TEST_SYMS:
    try:
        df = mdhub.get_candles_df(sym, interval=INTERVAL, min_rows=LOOKBACK)
        if df is None or df.empty or len(df) < LOOKBACK:
            print(f"[6] {sym}: SKIP (no data)")
            continue
        df = df.tail(LOOKBACK).copy()
        t0 = time.time()
        sig, conf, now_series = mei_alpha_v1.analyze(df, sym, btc_bullish=btc_bullish)
        elapsed = time.time() - t0
        ns_type = type(now_series).__name__
        ns_keys = list(now_series.keys())[:10] if isinstance(now_series, dict) else "N/A"
        if hasattr(now_series, 'keys') and not isinstance(now_series, dict):
            ns_keys = list(now_series.keys())[:10]
        print(f"[6] {sym}: sig={sig}  conf={conf}  elapsed={elapsed:.3f}s  now_type={ns_type}  keys={ns_keys}")
    except Exception as e:
        print(f"[6] {sym}: FAIL analyze(): {e}")
        traceback.print_exc()

print("\n=== Done ===")
