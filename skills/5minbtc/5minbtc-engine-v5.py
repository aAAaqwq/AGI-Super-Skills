#!/usr/bin/env python3
"""5minbtc Engine v5.0 — 正交因子体系 + Regime感知 + 微结构

升级要点(基于R14审查14项修复):
- C-1: 正交因子替代共线指标(momentum t-stat, Z-score, vol ratio)
- C-2: 所有阈值ATR归一化
- C-3: 条件化volume信号(区分突破vs衰竭)
- C-4: 订单簿深度信号(imbalance + microprice)
- H-1: Sigmoid压缩替代ad-hoc压制
- H-3: 百分比化信号(不再用绝对价格差)
- H-4: 波动率Regime检测(4态)
- M-1: BB样本std(÷n-1)
- M-2: 200根K线
- M-3: Volume投影
- M-5: RSI动量模式(非反转)
- M-6: Wilder ATR(RMA)
- H-2: O(n) MACD计算
"""
import json, math, urllib.request
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
BINANCE_KLINES = "https://data-api.binance.vision/api/v3/klines"
BINANCE_DEPTH = "https://data-api.binance.vision/api/v3/depth"

# ======================== Data Fetching ========================

def fetch_klines(symbol="BTCUSDT", interval="5m", limit=200):
    url = f"{BINANCE_KLINES}?symbol={symbol}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "5minbtc/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = json.loads(resp.read())
    return [{"o": float(c[1]), "h": float(c[2]), "l": float(c[3]), "c": float(c[4]),
             "v": float(c[5]), "ct": int(c[6])} for c in raw]

def fetch_depth(symbol="BTCUSDT", limit=20):
    try:
        url = f"{BINANCE_DEPTH}?symbol={symbol}&limit={limit}"
        req = urllib.request.Request(url, headers={"User-Agent": "5minbtc/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        bids = [(float(b[0]), float(b[1])) for b in data["bids"][:limit]]
        asks = [(float(a[0]), float(a[1])) for a in data["asks"][:limit]]
        return {"bids": bids, "asks": asks}
    except Exception:
        return None

# ======================== O(n) Indicators ========================

def ema(data, period):
    """Single-point EMA"""
    if len(data) < period:
        return sum(data) / len(data) if data else 0
    k = 2 / (period + 1)
    e = sum(data[:period]) / period
    for v in data[period:]:
        e = v * k + e * (1 - k)
    return e

def ema_series(data, period):
    """Full EMA series O(n) — 所有EMA基于同一初始化"""
    n = len(data)
    if n < period:
        avg = sum(data) / n if n > 0 else 0
        return [avg] * n
    k = 2 / (period + 1)
    result = [0.0] * n
    init = sum(data[:period]) / period
    for i in range(period):
        result[i] = init
    result[period - 1] = init
    for i in range(period, n):
        result[i] = data[i] * k + result[i - 1] * (1 - k)
    return result

def rsi(data, period=14):
    """Wilder's RSI"""
    if len(data) < period + 1:
        return 50
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

def compute_macd(data, fast=12, slow=26, sig=9):
    """O(n) MACD — 统一EMA初始化"""
    ema_f = ema_series(data, fast)
    ema_s = ema_series(data, slow)
    macd_vals = [ema_f[i] - ema_s[i] for i in range(len(data))]
    valid = macd_vals[slow - 1:]
    if len(valid) < sig:
        return macd_vals[-1], 0, macd_vals[-1]
    k = 2 / (sig + 1)
    sv = sum(valid[:sig]) / sig
    for v in valid[sig:]:
        sv = v * k + sv * (1 - k)
    return macd_vals[-1], sv, macd_vals[-1] - sv

def bollinger(data, period=20, std_mult=2):
    """BB with sample std (÷n-1)"""
    if len(data) < period:
        return data[-1], data[-1], data[-1]
    subset = data[-period:]
    sma = sum(subset) / period
    var = sum((x - sma) ** 2 for x in subset) / (period - 1)
    std = math.sqrt(var)
    return sma + std_mult * std, sma, sma - std_mult * std

def atr_wilder(candles, period=14):
    """Wilder's ATR (RMA-based)"""
    if len(candles) < 2:
        return 0
    trs = []
    for i in range(1, len(candles)):
        c = candles[i]
        prev_c = candles[i - 1]["c"]
        tr = max(c["h"] - c["l"], abs(c["h"] - prev_c), abs(c["l"] - prev_c))
        trs.append(tr)
    if len(trs) < period:
        return sum(trs) / len(trs) if trs else 0
    rma = sum(trs[:period]) / period
    for tr in trs[period:]:
        rma = (rma * (period - 1) + tr) / period
    return rma

# ======================== 6 Orthogonal Factors ========================

def momentum_tstat(closes, window=15):
    """因子1: 动量t-stat — 线性回归斜率统计显著性
    v5.1修复: window 30→15防止饱和; 自适应归一化
    正交于均值回归；scale-invariant(log price)
    返回 [-1, 1]
    """
    if len(closes) < window:
        return 0
    prices = closes[-window:]
    n = len(prices)
    log_p = [math.log(p) for p in prices]
    x_mean = (n - 1) / 2
    x_sq = sum((i - x_mean) ** 2 for i in range(n))
    if x_sq == 0:
        return 0
    y_mean = sum(log_p) / n
    xy = sum((i - x_mean) * (log_p[i] - y_mean) for i in range(n))
    slope = xy / x_sq
    intercept = y_mean - slope * x_mean
    resid = [log_p[i] - (intercept + slope * i) for i in range(n)]
    se = math.sqrt(sum(r ** 2 for r in resid) / max(1, n - 2) / max(1, x_sq))
    if se == 0:
        return 0
    t = slope / se
    # v5.1: softer saturation with tanh instead of hard cap
    return max(-1, min(1, math.tanh(t / 2.5)))

def zscore_meanrev(closes, period=20):
    """因子2: 均值回归 — 高Z=超买=看空, 低Z=超卖=看多
    ★ 关键: 方向反转! 高Z → 返回负值(bearish)
    正交于动量: 提供counter-trend信号
    返回 [-1, 1]
    """
    if len(closes) < period:
        return 0
    subset = closes[-period:]
    sma = sum(subset) / period
    std = math.sqrt(sum((x - sma) ** 2 for x in subset) / (period - 1))
    if std == 0:
        return 0
    z = (closes[-1] - sma) / std
    # ★ 反转: 高Z(超买)→负值(bearish), 低Z(超卖)→正值(bullish)
    return max(-1, min(1, -z / 2.5))

def vol_regime_ratio(closes, short=20, long=60):
    """因子3: 波动率比率 → regime检测
    返回 raw ratio
    """
    if len(closes) < long + 1:
        return 1.0
    def rvol(prices):
        if len(prices) < 2:
            return 0
        lr = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
        m = sum(lr) / len(lr)
        return math.sqrt(sum((r - m) ** 2 for r in lr) / len(lr))
    sv = rvol(closes[-short:])
    lv = rvol(closes[-long:])
    return sv / lv if lv > 0 else 1.0

def rsi_momentum(rsi_val):
    """因子4: RSI动量模式 — 5min频率下动量>反转
    Connors & Alvarez (2012): RSI>70继续看涨
    返回 [-1, 1]
    """
    return (rsi_val - 50) / 50

def volume_conditional(vol_now, vol_avg, progress, candles):
    """因子5: 条件化volume信号
    投影未完成K线; 区分突破放量vs衰竭放量
    返回 [-1, 1]
    """
    if vol_avg <= 0 or progress <= 0:
        return 0
    projected = vol_now / progress if progress < 1.0 else vol_now
    vr = projected / vol_avg

    if vr < 0.5:
        return 0.1
    elif vr < 0.8:
        return 0.15
    elif vr < 1.3:
        return 0
    elif vr < 2.0:
        if len(candles) >= 2:
            cur_r = candles[-1]["h"] - candles[-1]["l"]
            prev_r = candles[-2]["h"] - candles[-2]["l"]
            d = 1 if candles[-1]["c"] > candles[-1]["o"] else -1
            return 0.3 * d if cur_r > prev_r * 1.2 else -0.2 * d
        return 0
    else:
        if candles:
            d = 1 if candles[-1]["c"] > candles[-1]["o"] else -1
            return -0.25 * d
        return 0

def consecutive_fatigue(candles):
    """因子6: 连续K线疲劳
    返回 [-1, 1] (正=看bullish reversal)
    """
    bull = bear = 0
    for c in reversed(candles[:-1]):
        if c["c"] > c["o"]:
            if bear > 0: break
            bull += 1
        else:
            if bull > 0: break
            bear += 1
    if bull >= 5: return -0.8
    if bull >= 3: return -0.5
    if bear >= 5: return 0.8
    if bear >= 3: return 0.5
    return 0

def momentum_deceleration(closes):
    """因子7: 动量减速 — 短期vs中期动量差
    捕获趋势内拐点: 短期动量<长期动量 → 减速 → 可能回调
    返回 [-1, 1]
    """
    if len(closes) < 20:
        return 0
    short_mom = momentum_tstat(closes[-8:], 5) if len(closes) >= 8 else 0
    long_mom = momentum_tstat(closes[-20:], 15) if len(closes) >= 20 else 0
    decel = short_mom - long_mom
    return max(-1, min(1, decel * 2.5))

def price_position(candles):
    """因子8: 价格在近期区间的位置 (类Stochastic)
    接近高点 → 可能回调; 接近低点 → 可能反弹
    返回 [-1, 1] (正=接近高点=看空; 负=接近低点=看多)
    """
    if len(candles) < 20:
        return 0
    highs = [c["h"] for c in candles[-20:]]
    lows = [c["l"] for c in candles[-20:]]
    hh = max(highs)
    ll = min(lows)
    if hh == ll:
        return 0
    pos = (candles[-1]["c"] - ll) / (hh - ll)
    # 反转: 高位=看空, 低位=看多
    return -(pos * 2 - 1)  # [-1, 1], 正=bullish(低位), 负=bearish(高位)

def orderbook_signals(depth_data, mid_price):
    """因子7+8: 订单簿 imbalance + microprice"""
    if not depth_data or not depth_data.get("bids") or not depth_data.get("asks"):
        return 0, 0
    bids, asks = depth_data["bids"], depth_data["asks"]
    bq = sum(b[1] for b in bids[:5])
    aq = sum(a[1] for a in asks[:5])
    total = bq + aq
    imb = (bq - aq) / total if total > 0 else 0
    bb, ba = bids[0][0], asks[0][0]
    bbq, baq = bids[0][1], asks[0][1]
    spread = ba - bb
    if spread > 0 and (bbq + baq) > 0:
        mp = bb + spread * bbq / (bbq + baq)
        mid = (bb + ba) / 2
        dev = (mp - mid) / spread * 2
    else:
        dev = 0
    return max(-1, min(1, imb)), max(-1, min(1, dev))

# ======================== Regime Detection ========================

def detect_regime(vol_ratio, candles):
    """4态: HIGH_VOL / TREND / RANGE / LOW_VOL"""
    if vol_ratio > 2.0:
        return "HIGH_VOL"
    closes = [c["c"] for c in candles]
    if len(closes) >= 30:
        e9 = ema(closes, 9)
        e9_prev = ema(closes[:-10], 9) if len(closes) > 10 else e9
        atr_v = atr_wilder(candles)
        if atr_v > 0 and closes[-1] > 0:
            norm_slope = (e9 - e9_prev) / closes[-1] / (atr_v / closes[-1])
        else:
            norm_slope = 0
        if vol_ratio < 0.6:
            return "LOW_VOL"
        if abs(norm_slope) > 0.5:
            return "TREND"
    return "RANGE"

# ======================== Factor Combination ========================

BASE_W = {'momentum': 1.0, 'meanrev': 0.5, 'rsi': 0.4,
          'volume': 0.3, 'fatigue': 0.5, 'imbalance': 0.8, 'microprice': 0.6,
          'decel': 0.7, 'position': 0.5}

REGIME_ADJ = {
    'HIGH_VOL': {'momentum': 0.4, 'meanrev': 0.3, 'rsi': 0.3,
                 'volume': 0.2, 'fatigue': 0.5, 'imbalance': 0.6, 'microprice': 0.5,
                 'decel': 0.8, 'position': 0.6},
    'TREND':    {'momentum': 1.0, 'meanrev': 0.4, 'rsi': 0.5,
                 'volume': 0.4, 'fatigue': 0.4, 'imbalance': 0.7, 'microprice': 0.5,
                 'decel': 0.9, 'position': 0.6},
    'RANGE':    {'momentum': 0.4, 'meanrev': 1.5, 'rsi': 0.2,
                 'volume': 0.3, 'fatigue': 0.6, 'imbalance': 0.9, 'microprice': 0.7,
                 'decel': 0.5, 'position': 0.8},
    'LOW_VOL':  {'momentum': 0.5, 'meanrev': 1.2, 'rsi': 0.3,
                 'volume': 0.2, 'fatigue': 0.4, 'imbalance': 0.8, 'microprice': 0.6,
                 'decel': 0.6, 'position': 0.7},
}

def combine_factors(factors, regime):
    adj = REGIME_ADJ.get(regime, BASE_W)
    score = total_w = 0
    for name, value in factors.items():
        w = BASE_W.get(name, 0) * adj.get(name, 1.0)
        score += w * value
        total_w += w
    if total_w > 0:
        score = score / total_w * 3
    return score

def sigmoid_compress(score, max_score=45, sensitivity=1.5):
    """Smooth sigmoid: [-∞,+∞] → [-45, +45]"""
    return max_score * (2 / (1 + math.exp(-score / sensitivity)) - 1)

# ======================== Direction Decision ========================

def direction_rule_v5(candles, closes, atr_val, vol_ratio,
                      depth_data=None, candle_progress=1.0):
    """v5.0 正交因子 + Regime感知"""
    mom = momentum_tstat(closes)
    mr = zscore_meanrev(closes)
    rsi_val = rsi(closes)
    rsi_m = rsi_momentum(rsi_val)

    vols = [c["v"] for c in candles]
    vol_now = vols[-1]
    vol_avg = sum(vols[-21:-1]) / 20 if len(vols) >= 21 else vol_now
    vol = volume_conditional(vol_now, vol_avg, candle_progress, candles)
    fat = consecutive_fatigue(candles)

    imb, mpd = orderbook_signals(depth_data, closes[-1])

    factors = {'momentum': mom, 'meanrev': mr, 'rsi': rsi_m,
               'volume': vol, 'fatigue': fat,
               'imbalance': imb, 'microprice': mpd,
               'decel': momentum_deceleration(closes),
               'position': price_position(candles)}

    regime = detect_regime(vol_ratio, candles)
    raw = combine_factors(factors, regime)
    score = sigmoid_compress(raw)

    # ---- Regime-aware score adjustment ----
    if regime == "TREND":
        ts = 1 if factors["momentum"] > 0 else -1
        ss = 1 if score > 0 else -1
        if ss != ts:
            score *= 0.25  # dampen counter-trend (keep 25% for extreme cases)
        if factors.get("decel", 0) * ts < -0.5:
            score *= 0.5   # decel → reduce confidence, not direction
    elif regime == "HIGH_VOL":
        score *= 0.6

    nz = 12 if regime == "HIGH_VOL" else 6
    if score > nz:
        bias = "bull"; strength = "strong" if score > 25 else "medium"
    elif score > 2:
        bias = "bull"; strength = "weak"
    elif score > -2:
        bias = "neutral"; strength = "weak"
    elif score > -nz:
        bias = "bear"; strength = "weak"
    else:
        bias = "bear"; strength = "strong" if score < -25 else "medium"

    confidence = min(80, 40 + int(abs(score)))
    if bias == "neutral":
        confidence = min(confidence, 50)

    return bias, strength, confidence, int(score), factors, regime

# ======================== Price Prediction ========================

def predict_close_v5(candles, closes, atr_val, bbu, bbm, bbl, bias, strength):
    """v5.0 — ATR校准 + 历史分位range"""
    pred = candles[-1]["c"]

    if bias == "bull":
        pred += atr_val * (0.20 if strength == "strong" else 0.12)
    elif bias == "bear":
        pred -= atr_val * (0.20 if strength == "strong" else 0.12)

    e9 = ema(closes[-30:], 9) if len(closes) >= 30 else ema(closes, min(9, len(closes)))
    pred += (e9 - pred) * 0.15

    pred = max(bbl + atr_val * 0.05, min(bbu - atr_val * 0.05, pred))
    pred = round(pred)

    # v5.1: 历史range/ATR P75校准 + 更宽half_range
    ratios = []
    for c in candles[-50:]:
        r = c["h"] - c["l"]
        if atr_val > 0:
            ratios.append(r / atr_val)
    if ratios:
        sorted_r = sorted(ratios)
        p75 = sorted_r[int(len(sorted_r) * 0.75)]  # P75覆盖多数场景
    else:
        p75 = 1.0
    half = atr_val * p75 * 0.65  # 0.5→0.65 扩宽覆盖

    return pred, round(pred + half), round(pred - half)

# ======================== Candle Info ========================

def current_candle_info():
    now = datetime.now(CST)
    minute = (now.minute // 5) * 5
    cs = now.replace(minute=minute, second=0, microsecond=0)
    ce = cs + timedelta(minutes=5)
    elapsed = (now - cs).total_seconds()
    remain = 300 - elapsed
    return {
        "now": now.strftime("%H:%M:%S"),
        "candle_start": cs.strftime("%H:%M"),
        "candle_end": ce.strftime("%H:%M"),
        "progress_pct": round(elapsed / 300 * 100, 1),
        "remaining_sec": round(remain),
        "iso": cs.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    }

# ======================== Main ========================

def run():
    info = current_candle_info()
    candles = fetch_klines(limit=200)
    closes = [c["c"] for c in candles]

    e9 = ema(closes, 9)
    e21 = ema(closes, 21)
    rsi_val = rsi(closes)
    macd_val, sig_val, macd_hist = compute_macd(closes)
    bbu, bbm, bbl = bollinger(closes)
    atr_val = atr_wilder(candles)
    vr = vol_regime_ratio(closes)
    depth = fetch_depth()

    progress = min(info["progress_pct"] / 100, 1.0)
    bias, strength, confidence, score, factors, regime = direction_rule_v5(
        candles, closes, atr_val, vr, depth, progress)

    pred_close, pred_high, pred_low = predict_close_v5(
        candles, closes, atr_val, bbu, bbm, bbl, bias, strength)

    recent = [{"O": round(c["o"]), "H": round(c["h"]),
               "L": round(c["l"]), "C": round(c["c"])} for c in candles[-4:-1]]
    cur = candles[-1]

    fng = {"value": None, "label": None}
    try:
        req = urllib.request.Request("https://api.alternative.me/fng/?limit=1",
                                     headers={"User-Agent": "5minbtc/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            fd = json.loads(resp.read())["data"][0]
            fng = {"value": int(fd["value"]), "label": fd["value_classification"]}
    except Exception:
        pass

    result = {
        "version": "5.0",
        "candle": info,
        "price": {
            "current": cur["c"], "open": cur["o"],
            "high": cur["h"], "low": cur["l"],
            "body": round(cur["c"] - cur["o"]),
            "body_pct": round((cur["c"] - cur["o"]) / cur["o"] * 100, 3)
        },
        "recent_candles": recent,
        "indicators": {
            "ema9": round(e9, 1), "ema21": round(e21, 1),
            "ema_delta": round(e9 - e21, 1), "rsi": round(rsi_val, 1),
            "macd": round(macd_val, 2), "macd_signal": round(sig_val, 2),
            "macd_hist": round(macd_hist, 2),
            "bb_upper": round(bbu, 1), "bb_mid": round(bbm, 1), "bb_lower": round(bbl, 1),
            "atr": round(atr_val, 1),
            "vol_pct": round(cur["v"] / (sum(c["v"] for c in candles[-21:-1]) / 20) * 100, 0)
                        if len(candles) >= 21 else 0
        },
        "fng": fng,
        "factors": {k: round(v, 3) if isinstance(v, float) else v for k, v in factors.items()},
        "regime": regime,
        "prediction": {
            "bias": bias, "strength": strength,
            "confidence": confidence, "score": score,
            "pred_close": pred_close, "pred_high": pred_high, "pred_low": pred_low
        }
    }
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    run()
