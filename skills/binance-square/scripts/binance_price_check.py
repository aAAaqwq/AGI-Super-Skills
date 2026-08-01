#!/usr/bin/env python3
"""Binance Price Checker — 拉取实时价格 + K线为交易信号做校验"""
import json, sys, urllib.request, ssl, os
from datetime import datetime, timezone

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(SKILL_DIR, "data")

ssl_ctx = ssl.create_default_context()

def api(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as r:
        return json.loads(r.read())

def get_ticker(symbol):
    """24hr ticker: lastPrice, priceChangePercent, high, low, volume"""
    try:
        return api(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}")
    except Exception as e:
        return {"error": str(e), "symbol": symbol}

def get_klines(symbol, interval="1h", limit=5):
    """Recent K-lines: [open, high, low, close, volume]"""
    try:
        raw = api(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}")
        return [[float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])] for x in raw]
    except:
        return []

def compute_rr(entry, sl, tp, direction="long"):
    """Risk-Reward ratio"""
    try:
        entry = float(entry)
        sl = float(sl)
        tp = float(tp)
        if direction == "long":
            risk = entry - sl
            reward = tp - entry
        else:
            risk = sl - entry
            reward = entry - tp
        if risk <= 0:
            return None
        return round(reward / risk, 2)
    except:
        return None

def analyze_signal(signal, price_data, klines):
    """综合判断信号是否合理"""
    assessments = []
    
    if "error" in price_data:
        return {"verdict": "⚠️ 无法获取价格", "assessments": [], "price_data": price_data}
    
    current = float(price_data["lastPrice"])
    entry_str = signal.get("entry", "")
    sl_str = signal.get("sl", "")
    tp_str = signal.get("tp", "")
    direction = signal.get("direction", "long")
    
    # Try to parse entry range
    entries = []
    for part in entry_str.replace("–", "-").replace("~", "-").split("/"):
        part = part.strip().replace("$", "").replace("Entry:", "").replace("entry:", "").replace("入场:", "")
        # "0.065-0.070" or "0.065" or "Around current price"
        try:
            if "-" in part:
                a, b = part.split("-", 1)
                entries.append(float(a.strip()))
                entries.append(float(b.strip()))
            else:
                entries.append(float(part.strip()))
        except:
            pass
    
    if entries:
        entry_min = min(entries)
        entry_max = max(entries)
    else:
        entry_min = entry_max = None
    
    # Parse SL
    sl_val = None
    try:
        for p in sl_str.replace("$", "").replace("Below ", "").replace("below ", "").split("/"):
            p = p.strip().replace("SL:", "").replace("Stoploss:", "").replace("❌", "").strip()
            if p:
                sl_val = float(p)
                break
    except:
        pass
    
    # Parse first TP
    tp_val = None
    try:
        for p in tp_str.replace("$", "").split("→")[0].split("/")[0].split("-")[0].split("→")[0].split("|")[0].split():
            p = p.strip().replace("TP:", "").replace("TP1:", "").strip()
            if p:
                tp_val = float(p)
                break
    except:
        pass
    
    # 1. Check current price vs entry zone
    if entry_min is not None and entry_max is not None:
        if current < entry_min:
            gap_pct = round((entry_min - current) / entry_min * 100, 2)
            if direction == "long":
                assessments.append(f"✅ 现价 ${current} 低于入场区 ${entry_min}-{entry_max}（低 {gap_pct}%），若结构未破可更优入场")
            else:
                assessments.append(f"⚠️ 现价 ${current} 低于入场区，做空信号可能已失效")
        elif current > entry_max:
            gap_pct = round((current - entry_max) / entry_max * 100, 2)
            if direction == "long":
                assessments.append(f"⚠️ 现价 ${current} 已超过入场区 ${entry_min}-{entry_max}（+{gap_pct}%），追高风险较大")
            else:
                assessments.append(f"✅ 现价 ${current} 高于入场区 ${entry_min}-{entry_max}（高 {gap_pct}%），做空可入场")
        else:
            assessments.append(f"✅ 现价 ${current} 在入场区 ${entry_min}-{entry_max} 内，可执行")
    else:
        assessments.append(f"📌 现价 ${current}")
    
    # 2. SL sanity check
    if sl_val is not None and entry_min is not None:
        if direction == "long" and sl_val >= entry_min:
            assessments.append(f"🚫 SL ${sl_val} ≥ 入场 ${entry_min}，止损设置错误（做多SL应<入场）")
        elif direction == "short" and sl_val <= entry_max:
            assessments.append(f"🚫 SL ${sl_val} ≤ 入场 ${entry_max}，止损设置错误（做空SL应>入场）")
        else:
            sl_dist = abs(sl_val - entry_min) / entry_min * 100 if entry_min > 0 else 0
            if sl_dist < 1:
                assessments.append(f"⚠️ SL距离仅 {round(sl_dist,2)}%，止损过紧易被扫")
            elif sl_dist > 15:
                assessments.append(f"⚠️ SL距离 {round(sl_dist,2)}%，止损过宽")
            else:
                assessments.append(f"✅ SL距离 {round(sl_dist,2)}%，合理")
    
    # 3. RR ratio
    if entry_min is not None and sl_val is not None and tp_val is not None:
        rr = compute_rr(entry_min, sl_val, tp_val, direction)
        if rr is not None:
            if rr < 1:
                assessments.append(f"🚫 盈亏比 {rr}:1，不值得做")
            elif rr < 2:
                assessments.append(f"⚠️ 盈亏比 {rr}:1，偏低")
            else:
                assessments.append(f"✅ 盈亏比 {rr}:1")
    
    # 4. 24h price change
    try:
        change = float(price_data.get("priceChangePercent", 0))
        assessments.append(f"📊 24h: {change:+.2f}% | 量: {float(price_data['volume']):,.0f} USDT")
    except:
        pass
    
    # 5. K-line trend check
    if klines and len(klines) >= 3:
        closes = [k[3] for k in klines]
        trend = "📈 上行" if closes[-1] > closes[-3] else "📉 下行"
        high_vol = any(k[4] > 1.5 * sum(k2[4] for k2 in klines[:-1]) / (len(klines)-1) for k in klines[-2:])
        vol_note = " ⚡ 放量" if high_vol else ""
        assessments.append(f"{trend}{vol_note} (近{len(klines)}h K线)")
    
    # Final verdict
    dangers = [a for a in assessments if a.startswith("🚫")]
    warnings = [a for a in assessments if a.startswith("⚠️")]
    goods = [a for a in assessments if a.startswith("✅")]
    
    if dangers:
        verdict = "🔴 高风险"
    elif warnings:
        verdict = "🟡 需谨慎"
    elif goods:
        verdict = "🟢 可执行"
    else:
        verdict = "⚪ 数据不足"
    
    return {
        "verdict": verdict,
        "assessments": assessments,
        "price_data": {
            "current": current,
            "change_24h": float(price_data.get("priceChangePercent", 0)),
            "high_24h": float(price_data.get("highPrice", 0)),
            "low_24h": float(price_data.get("lowPrice", 0)),
            "volume": float(price_data.get("volume", 0)),
        }
    }

def main():
    signals_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join(DATA_DIR, "signal_check_input.json")
    
    with open(signals_file) as f:
        signals = json.load(f)
    
    results = []
    seen_symbols = set()
    
    for sig in signals:
        symbol = sig.get("symbol", "").upper().replace("$", "").strip()
        if not symbol or symbol in seen_symbols:
            continue
        seen_symbols.add(symbol)
        
        pair = f"{symbol}USDT"
        print(f"[*] Fetching {pair}...", file=sys.stderr)
        
        ticker = get_ticker(pair)
        klines = []
        if "error" not in ticker:
            klines = get_klines(pair, "1h", 5)
        
        analysis = analyze_signal(sig, ticker, klines)
        analysis["symbol"] = symbol
        analysis["pair"] = pair
        results.append(analysis)
    
    output = {
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "results": results
    }
    
    os.makedirs(DATA_DIR, exist_ok=True)
    output_path = os.path.join(DATA_DIR, "binance_price_checks.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"[OK] {len(results)} symbols checked → {output_path}", file=sys.stderr)
    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()
