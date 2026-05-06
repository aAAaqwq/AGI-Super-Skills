#!/usr/bin/env python3
"""5minbtc Engine v3.0 — 脚本化指标+方向+预测，LLM只做新闻判断
输出JSON供LLM直接使用，减少推理时间从70s→20s
"""
import json, sys, math, urllib.request
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
BINANCE = "https://api.binance.me/api/v3/klines"

def fetch_klines(symbol="BTCUSDT", interval="5m", limit=100):
    url = f"{BINANCE}?symbol={symbol}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = json.loads(resp.read())
    return [{"o": float(c[1]), "h": float(c[2]), "l": float(c[3]), "c": float(c[4]),
             "v": float(c[5]), "ct": int(c[6])} for c in raw]

def ema(data, period):
    k = 2 / (period + 1)
    e = sum(data[:period]) / period
    for v in data[period:]:
        e = v * k + e * (1 - k)
    return e

def rsi(data, period=14):
    gains, losses = [], []
    for i in range(1, len(data)):
        d = data[i] - data[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
    if al == 0:
        return 100
    return 100 - 100 / (1 + ag / al)

def macd_line(data, fast=12, slow=26):
    return ema(data, fast) - ema(data, slow)

def macd_signal(data, fast=12, slow=26, sig=9):
    hist = []
    for i in range(slow, len(data) + 1):
        hist.append(ema(data[:i], fast) - ema(data[:i], slow))
    if len(hist) < sig:
        return 0, hist[-1] if hist else 0
    signal = ema(hist, sig)
    return hist[-1], signal

def bollinger(data, period=20, std_mult=2):
    sma = sum(data[-period:]) / period
    std = math.sqrt(sum((x - sma) ** 2 for x in data[-period:]) / period)
    return sma + std_mult * std, sma, sma - std_mult * std

def atr(candles, period=14):
    trs = []
    for i in range(1, len(candles)):
        c = candles[i]
        tr = max(c["h"] - c["l"], abs(c["h"] - candles[i - 1]["c"]), abs(c["l"] - candles[i - 1]["c"]))
        trs.append(tr)
    return sum(trs[-period:]) / period

def current_candle_info():
    now = datetime.now(CST)
    minute = (now.minute // 5) * 5
    cs = now.replace(minute=minute, second=0, microsecond=0)
    ce = cs + timedelta(minutes=5)
    elapsed = (now - cs).total_seconds()
    pct = elapsed / 300 * 100
    remain = 300 - elapsed
    return {
        "now": now.strftime("%H:%M:%S"),
        "candle_start": cs.strftime("%H:%M"),
        "candle_end": ce.strftime("%H:%M"),
        "progress_pct": round(pct, 1),
        "remaining_sec": round(remain),
        "iso": cs.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    }

def direction_rule(ema_delta, rsi_val, vol_pct, macd_hist, consecutive_bull, consecutive_bear):
    """纯规则方向判定"""
    score = 0  # -100 to +100
    
    # EMA delta (权重40)
    if ema_delta > 100:
        score += 40
    elif ema_delta > 50:
        score += 25
    elif ema_delta > 0:
        score += 10
    elif ema_delta > -50:
        score -= 10
    elif ema_delta > -100:
        score -= 25
    else:
        score -= 40
    
    # RSI (权重20)
    if rsi_val > 70:
        score -= 10  # 超买反向下调
    elif rsi_val > 55:
        score += 15
    elif rsi_val > 45:
        score += 0
    elif rsi_val > 30:
        score -= 15
    else:
        score += 10  # 超卖反弹可能
    
    # MACD histogram (权重25)
    if macd_hist > 50:
        score += 25
    elif macd_hist > 0:
        score += 12
    elif macd_hist > -50:
        score -= 12
    else:
        score -= 25
    
    # Volume (权重15)
    if vol_pct > 120:
        score += 10 * (1 if ema_delta > 0 else -1)  # 放量确认方向
    elif vol_pct < 40:
        score -= 5  # 缩量减弱趋势
    
    # Consecutive candles momentum
    if consecutive_bull >= 3:
        score += 10
    elif consecutive_bear >= 3:
        score -= 10
    
    # Map to direction
    if score > 30:
        bias = "bull"
        strength = "strong" if score > 60 else "medium"
    elif score > 0:
        bias = "bull"
        strength = "weak"
    elif score > -30:
        bias = "bear"
        strength = "weak"
    else:
        bias = "bear"
        strength = "strong" if score < -60 else "medium"
    
    confidence = min(80, 40 + abs(score))
    return bias, strength, confidence, score

def predict_close(candles, ema9, ema21, ema_delta, rsi_val, bb_upper, bb_mid, bb_lower, atr_val, bias, strength):
    """基于指标的收盘预测"""
    cur = candles[-1]
    recent_closes = [c["c"] for c in candles[-5:]]
    
    # Base prediction = current close (most likely anchor)
    pred = cur["c"]
    
    # Adjust by bias strength
    if bias == "bull":
        adjustment = atr_val * 0.15  # mild bullish push
        if strength == "strong":
            adjustment = atr_val * 0.25
        pred += adjustment
    elif bias == "bear":
        adjustment = atr_val * 0.15
        if strength == "strong":
            adjustment = atr_val * 0.25
        pred -= adjustment
    
    # Mean reversion pull toward EMA9
    ema_pull = (ema9 - pred) * 0.1
    pred += ema_pull
    
    # Clamp within BB
    pred = max(bb_lower + atr_val * 0.1, min(bb_upper - atr_val * 0.1, pred))
    
    # Round to nearest dollar
    pred = round(pred)
    
    # Range
    half_range = atr_val * 0.5
    pred_low = round(pred - half_range)
    pred_high = round(pred + half_range)
    
    return pred, pred_high, pred_low

def count_consecutive(candles):
    """Count consecutive bull/bear candles from recent"""
    bull = 0
    bear = 0
    for c in reversed(candles[:-1]):  # exclude current
        if c["c"] > c["o"]:
            if bear > 0:
                break
            bull += 1
        else:
            if bull > 0:
                break
            bear += 1
    return bull, bear

def fetch_fng():
    """Fetch Fear & Greed Index from alternative.me"""
    try:
        req = urllib.request.Request(
            "https://api.alternative.me/fng/?limit=1",
            headers={"User-Agent": "5minbtc-engine/3.1"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        d = data["data"][0]
        return {"value": int(d["value"]), "label": d["value_classification"]}
    except Exception:
        return {"value": None, "label": None}

def run():
    # 1. Current candle info
    info = current_candle_info()
    
    # 2. Fetch klines
    candles = fetch_klines(limit=100)
    closes = [c["c"] for c in candles]
    
    # 3. Calculate all indicators
    e9 = ema(closes, 9)
    e21 = ema(closes, 21)
    ed = e9 - e21
    r = rsi(closes)
    macd_val, sig_val = macd_signal(closes)
    macd_hist = macd_val - sig_val
    bbu, bbm, bbl = bollinger(closes)
    atr_val = atr(candles)
    vols = [c["v"] for c in candles]
    vol_now = vols[-1]
    vol_avg = sum(vols[-21:-1]) / 20
    vol_pct = vol_now / vol_avg * 100 if vol_avg > 0 else 0
    
    # 4. Consecutive candles
    con_bull, con_bear = count_consecutive(candles)
    
    # 5. Direction rule
    bias, strength, confidence, score = direction_rule(ed, r, vol_pct, macd_hist, con_bull, con_bear)
    
    # 6. Predict close
    pred_close, pred_high, pred_low = predict_close(
        candles, e9, e21, ed, r, bbu, bbm, bbl, atr_val, bias, strength
    )
    
    # 7. Recent candles summary
    recent = []
    for c in candles[-4:-1]:
        recent.append({"O": round(c["o"]), "H": round(c["h"]), "L": round(c["l"]), "C": round(c["c"])})
    
    cur = candles[-1]
    
    # 8. Output compact JSON
    result = {
        "candle": info,
        "price": {
            "current": cur["c"],
            "open": cur["o"],
            "high": cur["h"],
            "low": cur["l"],
            "body": round(cur["c"] - cur["o"]),
            "body_pct": round((cur["c"] - cur["o"]) / cur["o"] * 100, 3)
        },
        "recent_candles": recent,
        "indicators": {
            "ema9": round(e9, 1),
            "ema21": round(e21, 1),
            "ema_delta": round(ed, 1),
            "rsi": round(r, 1),
            "macd": round(macd_val, 2),
            "macd_signal": round(sig_val, 2),
            "macd_hist": round(macd_hist, 2),
            "bb_upper": round(bbu, 1),
            "bb_mid": round(bbm, 1),
            "bb_lower": round(bbl, 1),
            "atr": round(atr_val, 1),
            "vol_pct": round(vol_pct, 0),
            "vol_now": round(vol_now, 1),
            "vol_avg": round(vol_avg, 1)
        },
        "fng": fetch_fng(),
        "momentum": {
            "consecutive_bull": con_bull,
            "consecutive_bear": con_bear
        },
        "prediction": {
            "bias": bias,
            "strength": strength,
            "confidence": confidence,
            "score": score,
            "pred_close": pred_close,
            "pred_high": pred_high,
            "pred_low": pred_low
        }
    }
    
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    run()
