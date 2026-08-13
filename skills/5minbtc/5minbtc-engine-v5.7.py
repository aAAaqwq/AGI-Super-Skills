#!/usr/bin/env python3
"""5minbtc Engine v5.8 -- 半K线预测策略 + 正交因子体系 + Regime感知

v5.8 优化 -- taker buy量能因子(区分主动买/主动卖) + 订单簿多时刻采样去噪

v5.7 优化 -- 半K线预测策略 (Daniel提议 2026-05-28):
- S1: 半K线body动量因子(half_body_momentum) -- K线过半后,已形成的body方向在剩余时间内延续
      核心逻辑: 在progress>=45%时激活,body方向用ATR归一化到[-1,1]
      这是实盘edge的正式建模:回测证明 11因子无预测力(47-49%),但实盘 66%的edge来自
      progress=0.9+ 时"确认已有走势">现在把这个逻辑变成显式因子
- S2: 预测范围收窄 -- ATR乘数 *0.55(只预测剩余~55%时间),half_range 0.65>0.40
- S3: Cron调度从每根K线第 2分钟改为第 4分钟(progress~60%>80%)
      给前半K线充分形成信号,再预测后半段

v5.6 优化 (基于v5.5 3轮方向错误复盘):
- R1: 趋势衰竭检测 -- momentum/decel方向冲突时动态降权
- R2: volume因子修复 -- vol_breakout_signal用已完成K线
- R3: V型反转因子 -- 低点抬高 + 收>开反转模式
- R4: Chainlink价格对齐 -- Coinbase BTC-USD参考

v5.5 优化 (基于 116轮v5.4实战复盘):
- P0-1: 置信度Platt Scaling校准 -- sigmoid(score)替代线性 40+abs(score)
- P0-2: 新闻因子移除 -- 98%NEUTRAL死代码
- P1-1: Bull bias惩罚 -- bear 69.1% > bull 63.5%, bull*0.92
- P1-2: 高vol惩罚增强 -- HIGH_VOL score衰减 0.45
- P1-3: neutral区收缩 [-1,1]

v5.0 基础(基于R14审查 14项修复):
- C-1: 正交因子替代共线指标(momentum t-stat, Z-score, vol ratio)
- C-2: 所有阈值ATR归一化
- C-3: 条件化volume信号(区分突破vs衰竭)
- C-4: 订单簿深度信号(imbalance + microprice)
- H-1: Sigmoid压缩替代ad-hoc压制
- H-3: 百分比化信号(不再用绝对价格差)
- H-4: 波动率Regime检测(4态)
- M-1~M-6: 数学修正(BB std, 200K线, vol投影, RSI动量, Wilder ATR, O(n) MACD)
"""
import json, math, os, time, urllib.request
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
from concurrent.futures import ThreadPoolExecutor, as_completed
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
             "v": float(c[5]), "ct": int(c[6]),
             "tb": float(c[9]) if len(c) > 9 else 0.0} for c in raw]

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

def fetch_depth_avg(symbol="BTCUSDT", limit=20, samples=3, interval_s=1.0):
    """v5.8 -- 订单簿多时刻采样去噪
    循环 samples 次调用 fetch_depth, 每次间隔 interval_s,
    同价位 bids/asks 取平均合并, 降低单次快照的瞬时报单噪声.
    全部失败返回 None, 单次失败跳过.
    """
    acc = {"bids": {}, "asks": {}}
    got = 0
    for i in range(samples):
        snap = fetch_depth(symbol, limit)
        if snap is not None:
            got += 1
            for side in ("bids", "asks"):
                for price, qty in snap[side]:
                    acc[side][price] = acc[side].get(price, 0.0) + qty
        if i < samples - 1:
            time.sleep(interval_s)
    if got == 0:
        return None
    bids = sorted(((p, q / got) for p, q in acc["bids"].items()), reverse=True)[:limit]
    asks = sorted(((p, q / got) for p, q in acc["asks"].items()))[:limit]
    return {"bids": bids, "asks": asks}

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
    """Full EMA series O(n) -- 所有EMA基于同一初始化"""
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
    """O(n) MACD -- 统一EMA初始化"""
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
    """BB with sample std (/n-1)"""
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
    """因子 1: 动量t-stat -- 线性回归斜率统计显著性
    v5.1修复: window 30>15防止饱和; 自适应归一化
    正交于均值回归;scale-invariant(log price)
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
    """因子 2: 均值回归 -- 高Z=超买=看空, 低Z=超卖=看多
    * 关键: 方向反转! 高Z > 返回负值(bearish)
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
    # * 反转: 高Z(超买)>负值(bearish), 低Z(超卖)>正值(bullish)
    return max(-1, min(1, -z / 2.5))

def vol_regime_ratio(closes, short=20, long=60):
    """因子 3: 波动率比率 > regime检测
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
    """因子 4: RSI动量模式 -- 5min频率下动量>反转
    Connors & Alvarez (2012): RSI>70继续看涨
    返回 [-1, 1]
    """
    return (rsi_val - 50) / 50

def volume_conditional(vol_now, vol_avg, progress, candles):
    """因子 5: 条件化volume信号
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
    """因子 6: 连续K线疲劳
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
    """因子 7: 动量减速 -- 短期vs中期动量差
    捕获趋势内拐点: 短期动量<长期动量 > 减速 > 可能回调
    返回 [-1, 1]
    """
    if len(closes) < 20:
        return 0
    short_mom = momentum_tstat(closes[-8:], 5) if len(closes) >= 8 else 0
    long_mom = momentum_tstat(closes[-20:], 15) if len(closes) >= 20 else 0
    decel = short_mom - long_mom
    return max(-1, min(1, decel * 2.5))

def price_position(candles):
    """因子 8: 价格在近期区间的位置 (类Stochastic)
    接近高点 > 可能回调; 接近低点 > 可能反弹
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
    """因子 7+8: 订单簿 imbalance + microprice"""
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

def v_reversal_detect(candles):
    """因子 10: V型反转检测 -- 捕获急跌后快速反转
    检测逻辑: 最近 3根K线低点逐渐抬高 + 当前K线收>开
    返回 [-1, 1] (正=看bullish reversal)
    v5.6新增: 解决Case#1 momentum=-0.98但实盘bull的根因
    """
    if len(candles) < 4:
        return 0
    # 取最近 3根完成的K线 (不含当前未完成的)
    recent = candles[-4:-1]  # -4, -3, -2 (3根完成的)
    cur = candles[-1]        # 当前未完成的

    # 条件 1: 最近 3根低点逐渐抬高 (V底)
    lows = [c["l"] for c in recent]
    ascending_lows = all(lows[i] <= lows[i+1] for i in range(len(lows)-1))

    # 条件 2: 当前K线是阳线 (收>开)
    cur_bull = cur["c"] > cur["o"]

    # 条件 3: 最近 3根中有至少 2根是阴线 (先下跌)
    bear_count = sum(1 for c in recent if c["c"] < c["o"])

    if ascending_lows and cur_bull and bear_count >= 2:
        # 强V反转
        return 1.0
    elif ascending_lows and cur_bull:
        # 弱V反转
        return 0.6
    # 对称检测: 高点降低 + 阴线 = 倒V (bearish reversal)
    highs = [c["h"] for c in recent]
    descending_highs = all(highs[i] >= highs[i+1] for i in range(len(highs)-1))
    cur_bear = cur["c"] < cur["o"]
    bull_count = sum(1 for c in recent if c["c"] > c["o"])
    if descending_highs and cur_bear and bull_count >= 2:
        return -1.0
    elif descending_highs and cur_bear:
        return -0.6
    return 0

def vol_breakout_signal(candles):
    """因子 11: 突破放量信号 -- 用已完成K线判断方向
    v5.6新增: 解决volume因子用未完成K线的bug
    逻辑: 最近 3根完成K线中,量最大的一根的方向决定信号
    """
    if len(candles) < 4:
        return 0
    recent = candles[-4:-1]  # 3根完成的K线
    vols = [(c["v"], 1 if c["c"] > c["o"] else -1) for c in recent]
    # 找最大量的一根
    max_vol_bar = max(vols, key=lambda x: x[0])
    vol_max, direction = max_vol_bar
    avg_vol = sum(v for v, _ in vols) / len(vols)
    if avg_vol == 0:
        return 0
    ratio = vol_max / avg_vol
    if ratio > 1.5:
        # 突破放量: 方向跟随最大量K线
        return direction * min(1.0, (ratio - 1.0) * 0.5)
    return 0

def taker_buy_signal(candles):
    """v5.8 -- 因子 13: taker buy 量能(区分主动买/主动卖)
    用最近 5根已完成K线(candles[-6:-1], 不含当前未完成K线),
    每根 ratio = tb/v (主动买入占比, 0.5=均衡), 取均值.
    映射到 [-1,1]: 2*(mean_ratio - 0.5)*3, clamp.
    正值=主动买占优=看多. v=0 或 tb 字段缺失的K线跳过, 全部跳过返回 0.
    tb=0 是有意义信号(主动买量为零=全主动卖), 不跳过.
    """
    ratios = []
    for c in candles[-6:-1]:
        v = c.get("v", 0)
        if "tb" not in c or v <= 0:
            continue
        tb = c["tb"]
        if tb > v:
            tb = v  # 数据容错: 主动买量不可能超过总成交量
        ratios.append(tb / v)
    if not ratios:
        return 0
    mean_ratio = sum(ratios) / len(ratios)
    return max(-1.0, min(1.0, 2 * (mean_ratio - 0.5) * 3))

def half_body_momentum(candles, progress, atr_val):
    """因子 12: 半K线body动量 -- v5.7核心新增
    逻辑: K线进行到 45%+ 后,已形成的body方向有延续倾向
    这是"确认已有走势"的显式建模 -- 回测证明这才是真正的edge来源
    
    返回 [-1, 1]
    - 正值=阳线body>bullish延续
    - 负值=阴线body>bearish延续
    - progress<45%时返回 0(信号不足)
    """
    if progress < 0.45 or atr_val <= 0 or not candles:
        return 0
    cur = candles[-1]
    body = cur["c"] - cur["o"]
    # ATR归一化: body/atr > 典型body约 0.3-0.8 ATR
    normalized = body / atr_val
    # 进度加权: 越接近完成,信号越强
    # progress 0.45>权重 0.4, 0.8>权重 0.85, 1.0>权重 1.0
    weight = min(1.0, (progress - 0.3) / 0.7)
    # 非线性压缩: 避免极端body主导
    signal = math.tanh(normalized * 2.0) * weight
    return max(-1.0, min(1.0, signal))

def atr_spike_detect(candles, atr_val, lookback=5, spike_threshold=1.5, consecutive=3):
    """v5.7.1 -- P0-1: ATR异常检测(黑天鹅防护)
    连续N根K线实际range > ATR * threshold > 判定为spike环境
    返回: (is_spike: bool, spike_ratio: float, consecutive_count: int)
    """
    if atr_val <= 0 or len(candles) < lookback:
        return False, 0.0, 0
    count = 0
    max_ratio = 0.0
    for c in candles[-lookback:]:
        actual_range = c["h"] - c["l"]
        ratio = actual_range / atr_val if atr_val > 0 else 0
        if ratio > spike_threshold:
            count += 1
            max_ratio = max(max_ratio, ratio)
        else:
            count = 0  # 重置连续计数
    is_spike = count >= consecutive
    return is_spike, round(max_ratio, 2), count

def fetch_chainlink_ref():
    """R4: 抓取Coinbase BTC-USD作为Chainlink参考价
    Chainlink Data Streams聚合 3+CEX中位数价格
    Coinbase是其中权重最大的成分交易所之一
    返回 (price, source) 或 (None, None)
    """
    try:
        url = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
        req = urllib.request.Request(url, headers={"User-Agent": "5minbtc/5.6"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return float(data["data"]["amount"]), "coinbase"
    except Exception:
        return None, None

# ======================== Regime Detection ========================

def detect_regime(vol_ratio, candles, atr_val=None):
    """4态: HIGH_VOL / TREND / RANGE / LOW_VOL
    v5.7.1: 增加ATR spike强制HIGH_VOL路径"""
    if vol_ratio > 2.0:
        return "HIGH_VOL"
    # v5.7.1 P0-1: ATR spike检测 -- 连续K线range>ATR*1.5时强制HIGH_VOL
    if atr_val is not None and atr_val > 0:
        is_spike, _, _ = atr_spike_detect(candles, atr_val)
        if is_spike:
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

# v5.9 对抗式审查修复 (2026-08-13):
# 实测回测证伪了 11/13 因子(47-49%硬币), 且 momentum/rsi 反向。
# 权重与证据完全倒挂 —— 收敛到 3 个有证据的信号:
#   half_body(延续, 主信号) + volume(唯一独立alpha 58%) + meanrev(唯一正向价格因子 51.7%)
# 其余因子(占37%权重无信息 + 25%权重未验证)清零。
BASE_W = {'momentum': 0.0, 'meanrev': 0.3, 'rsi': 0.0,
          'volume': 0.8, 'fatigue': 0.0, 'imbalance': 0.0, 'microprice': 0.0,
          'decel': 0.0, 'position': 0.0,
          'v_reversal': 0.0, 'vol_breakout': 0.0,
          'half_body': 1.2,  # 延续主信号 (真正 edge)
          'taker_buy': 0.0}  # 未验证, 清零 (待纳入公平回测后再评估)

REGIME_ADJ = {
    'HIGH_VOL': {'momentum': 0.4, 'meanrev': 0.3, 'rsi': 0.3,
                 'volume': 0.2, 'fatigue': 0.5, 'imbalance': 0.6, 'microprice': 0.5,
                 'decel': 0.8, 'position': 0.6,
                 'v_reversal': 1.0, 'vol_breakout': 0.6,
                 'half_body': 1.0,  # v5.7: 高vol下body延续仍有效
                 'taker_buy': 0.7},  # v5.8: 高vol下主动买卖方向信息量适中
    'TREND':    {'momentum': 1.0, 'meanrev': 0.4, 'rsi': 0.5,
                 'volume': 0.4, 'fatigue': 0.4, 'imbalance': 0.7, 'microprice': 0.5,
                 'decel': 0.9, 'position': 0.6,
                 'v_reversal': 0.9, 'vol_breakout': 0.5,
                 'half_body': 1.0,  # v5.7: 趋势中body延续很强
                 'taker_buy': 0.6},  # v5.8: 趋势中主动买卖略弱于震荡(方向已由趋势表达)
    'RANGE':    {'momentum': 0.4, 'meanrev': 1.5, 'rsi': 0.2,
                 'volume': 0.3, 'fatigue': 0.6, 'imbalance': 0.9, 'microprice': 0.7,
                 'decel': 0.5, 'position': 0.8,
                 'v_reversal': 0.7, 'vol_breakout': 0.4,
                 'half_body': 0.8,  # v5.7: 震荡中body延续稍弱(可能回归)
                 'taker_buy': 0.8},  # v5.8: 震荡中主动买卖主导方向
    'LOW_VOL':  {'momentum': 0.5, 'meanrev': 1.2, 'rsi': 0.3,
                 'volume': 0.2, 'fatigue': 0.4, 'imbalance': 0.8, 'microprice': 0.6,
                 'decel': 0.6, 'position': 0.7,
                 'v_reversal': 0.5, 'vol_breakout': 0.3,
                 'half_body': 0.9,  # v5.7: 低vol下body方向信息量适中
                 'taker_buy': 0.6},  # v5.8: 低vol下主动买卖方向略弱
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
    """Smooth sigmoid: [-inf,+inf] -> [-45, +45]"""
    return max_score * (2 / (1 + math.exp(-score / sensitivity)) - 1)

# ======================== Direction Decision ========================

def calibrate_confidence(raw_score, bias, regime):
    """v5.5: Platt Scaling校准置信度

    基于v5.4 120轮复盘发现的问题:
    - 原始 40+abs(score) 导致高conf=低准确率(反比)
    - bull_40: 58%, bull_50: 83% -- 低分bull是噪声
    - bear: 所有conf档位稳定在 67-70%
    - 需要: 低score>低conf, 高score>高conf (正相关)

    校准逻辑:
    1. sigmoid映射: score>概率基数
    2. regime调整: HIGH_VOL/RANGE降低, TREND维持
    3. neutral强制<=50
    4. 置信度=映射后概率四舍五入

    校准参数 (基于历史score分布 + conf准确率交叉验证):
    - midpoint=15: 低于此认为不确定 (原 8太高,导致低score变高conf)
    - steepness=0.10: 平缓过渡
    """
    abs_s = abs(raw_score)

    # Platt Scaling: sigmoid(score) > [0, 1]
    # midpoint=15: 当|score|<15时confidence<65%
    # steepness=0.10: 平缓过渡,避免跳变
    prob = 1.0 / (1.0 + math.exp(-0.10 * (abs_s - 15)))

    # 映射到 [35, 85] 置信度区间
    # low floor=35: 弱信号不装强
    # high cap=85: 最确定时 85%
    conf = int(35 + prob * 50)

    # Regime调整
    if regime == "HIGH_VOL":
        conf = int(conf * 0.85)  # 高波动降低置信度
    elif regime == "RANGE":
        conf = int(conf * 0.92)  # 震荡市略降

    # Neutral方向强制<=50
    if bias == "neutral":
        conf = min(conf, 50)

    # 钳位
    conf = max(35, min(85, conf))

    return conf


def direction_rule_v5(candles, closes, atr_val, vol_ratio,
                      depth_data=None, candle_progress=1.0, fng_value=None):
    """v5.7.1 -- 增加fng_value参数用于黑天鹅过滤(P0-2)"""
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

    decel = momentum_deceleration(closes)

    # v5.6 R1: momentum/decel 冲突检测 -- 趋势衰竭信号
    # 当 momentum 方向绝对值大(>0.7)但 decel 方向相反且也大(>0.8),
    # 说明趋势正在衰竭(15根K线斜率还在惯性, 但近 5根已在减速/反转)
    # 此时动态降权 momentum, 升权 decel, 让反转信号穿透
    mom_val = mom  # 保留原始值用于冲突检测
    decel_val = decel
    conflict_detected = False
    if abs(mom_val) > 0.7 and abs(decel_val) > 0.8:
        # 方向相反: 乘积<0 意味着 momentum 和 decel 一个正一个负
        if mom_val * decel_val < 0:
            conflict_detected = True
            # 不修改原始因子值, 而是在 combine_factors 中用动态权重覆盖
            # 记录冲突标记, 供后续使用

    factors = {'momentum': mom, 'meanrev': mr, 'rsi': rsi_m,
               'volume': vol, 'fatigue': fat,
               'imbalance': imb, 'microprice': mpd,
               'decel': decel,
               'position': price_position(candles),
               'v_reversal': v_reversal_detect(candles),      # v5.6 R2
               'vol_breakout': vol_breakout_signal(candles),   # v5.6 R3
               'half_body': half_body_momentum(candles, candle_progress, atr_val),  # v5.7 S1
               'taker_buy': taker_buy_signal(candles)}  # v5.8 S1: 主动买卖量能因子

    regime = detect_regime(vol_ratio, candles, atr_val)  # v5.7.1: 传入atr_val

    # v5.7.1 P0-2: FNG<25 黑天鹅过滤 -- 极端恐惧时v_reversal/decel不可信
    # 黑天鹅教训(2026-05-28): 暴跌后缩量被v_reversal=0.6+decel=+1.0误判为企稳
    # 极端恐惧环境下,反转因子缺乏统计基础,大幅衰减
    fng_black_swan = False
    _saved_base_for_fng = None
    if fng_value is not None and fng_value < 25:
        fng_black_swan = True
        _saved_base_for_fng = BASE_W.copy()  # 保存全局权重
        # 动态衰减v_reversal和decel的权重
        # v_reversal: 0.8>0.4 (衰减 50%), decel: 0.7>0.49 (衰减 30%)
        BASE_W['v_reversal'] = round(BASE_W.get('v_reversal', 0.8) * 0.5, 2)
        BASE_W['decel'] = round(BASE_W.get('decel', 0.7) * 0.7, 2)

    # v5.6 R1: 冲突时动态调整因子权重
    # momentum 权重从 1.0降至 0.4, decel 权重从 0.7升至 0.9
    # 让反转信号不再是噪声, 而是主导信号
    if conflict_detected:
        saved_base = BASE_W.copy()
        saved_regime = REGIME_ADJ.get(regime, {}).copy() if regime in REGIME_ADJ else {}
        BASE_W['momentum'] = 0.4   # 1.0>0.4: 趋势惯性降权
        BASE_W['decel'] = 0.9      # 0.7>0.9: 减速信号升权
        raw = combine_factors(factors, regime)
        BASE_W.update(saved_base)   # 恢复冲突检测前的权重
        if saved_regime:
            REGIME_ADJ[regime] = saved_regime
    else:
        raw = combine_factors(factors, regime)

    # v5.7.1 P0-2: 恢复FNG修改前的全局权重(防止污染下次调用)
    if _saved_base_for_fng is not None:
        BASE_W.update(_saved_base_for_fng)

    score = sigmoid_compress(raw)

    # ---- Regime-aware score adjustment ----
    if regime == "TREND":
        ts = 1 if factors["momentum"] > 0 else -1
        ss = 1 if score > 0 else -1
        if ss != ts:
            score *= 0.25  # dampen counter-trend (keep 25% for extreme cases)
        if factors.get("decel", 0) * ts < -0.5:
            score *= 0.5   # decel > reduce confidence, not direction
    elif regime == "HIGH_VOL":
        score *= 0.6  # v5.9: 0.45>0.6 放宽 (审查: 三层惩罚去掉一层, 低conf高vol桶实测62.5%不该过度压制)

    # ---- P1-1: Bull bias惩罚 (v5.9 移除) ----
    # 原假设 "bear 69.1% > bull 63.5%" 已被最新 317 笔实测推翻 (bull 64% > bear 50%)
    # 该惩罚现在压制唯一真 edge, 移除。方向偏差改由滚动窗口经验胜率校准。
    # if score > 0:
    #     score *= 0.92

    # ---- Direction threshold (v5.5: neutral区收缩 [-2,2]>[-1,1]) ----
    nz = 12 if regime == "HIGH_VOL" else 6
    if score > nz:
        bias = "bull"; strength = "strong" if score > 25 else "medium"
    elif score > 1:  # v5.5: 2>1 收缩neutral区
        bias = "bull"; strength = "weak"
    elif score > -1:  # v5.5: -2>-1 收缩neutral区
        bias = "neutral"; strength = "weak"
    elif score > -nz:
        bias = "bear"; strength = "weak"
    else:
        bias = "bear"; strength = "strong" if score < -25 else "medium"

    # ---- v5.5: 校准置信度 (P0-1) ----
    confidence = calibrate_confidence(score, bias, regime)

    # v5.7.1 P0-1: ATR spike时confidence减半 -- 黑天鹅防护
    is_spike, spike_ratio, spike_count = atr_spike_detect(candles, atr_val)
    if is_spike:
        confidence = max(35, int(confidence * 0.5))

    return bias, strength, confidence, int(score), factors, regime, fng_black_swan

# ======================== Price Prediction ========================

def predict_close_v5(candles, closes, atr_val, bbu, bbm, bbl, bias, strength):
    """v5.7 -- ATR calib x0.55 (predict approx 2.5 min remaining) + historical percentile range"""
    pred = candles[-1]["c"]

    # v5.7: ATR乘数缩至 0.55x -- 半K线策略只需预测剩余约 55%时间
    if bias == "bull":
        pred += atr_val * (0.11 if strength == "strong" else 0.066)
    elif bias == "bear":
        pred -= atr_val * (0.11 if strength == "strong" else 0.066)

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
    half = atr_val * p75 * 0.40  # v5.7: 0.65>0.40 缩窄区间(只预测剩余~2.5min)

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

# ======================== P0-3: News Risk Loader ========================

def load_news_risk():
    """P0-3: load data/news-risk-level.json, return (risk_level, is_black_swan)"""
    try:
        news_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "data", "news-risk-level.json")
        if not os.path.exists(news_path):
            return "UNKNOWN", False
        with open(news_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        risk = data.get("risk_level", "UNKNOWN")
        # BLACK_SWAN or CRITICAL triggers the circuit breaker
        return risk, risk in ("BLACK_SWAN", "CRITICAL")
    except Exception:
        return "UNKNOWN", False

# ======================== Main ========================

def _fetch_fng():
    """P0-2黑天鹅过滤: Fetch Fear & Greed Index (parallel-safe)"""
    try:
        req = urllib.request.Request("https://api.alternative.me/fng/?limit=1",
                                     headers={"User-Agent": "5minbtc/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            fd = json.loads(resp.read())["data"][0]
        return {"value": int(fd["value"]), "label": fd["value_classification"]}
    except Exception:
        return {"value": None, "label": None}

def run():
    info = current_candle_info()

    # v5.7.3: 4路并行HTTP — klines + depth + FNG + chainlink 同时发射
    # 最大延迟 = max(各API延迟) ≈ 3s，串行版 ~11s → 提速 ~3.7x
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_klines = ex.submit(fetch_klines, limit=200)
        f_depth = ex.submit(fetch_depth_avg)  # v5.8: 多时刻采样去噪(3次x1s)
        f_fng = ex.submit(_fetch_fng)
        f_cl = ex.submit(fetch_chainlink_ref)

        candles = f_klines.result()
        depth = f_depth.result()
        fng = f_fng.result()
        chainlink_ref, cl_source = f_cl.result()

    closes = [c["c"] for c in candles]

    e9 = ema(closes, 9)
    e21 = ema(closes, 21)
    rsi_val = rsi(closes)
    macd_val, sig_val, macd_hist = compute_macd(closes)
    bbu, bbm, bbl = bollinger(closes)
    atr_val = atr_wilder(candles)
    vr = vol_regime_ratio(closes)

    progress = min(info["progress_pct"] / 100, 1.0)
    bias, strength, confidence, score, factors, regime, fng_black_swan = direction_rule_v5(
        candles, closes, atr_val, vr, depth, progress, fng_value=fng.get("value"))

    # v5.7.1 P0-3: news risk circuit breaker
    news_risk, news_black_swan = load_news_risk()
    if news_black_swan:
        bias = "neutral"
        confidence = 30
        strength = "weak"

    pred_close, pred_high, pred_low = predict_close_v5(
        candles, closes, atr_val, bbu, bbm, bbl, bias, strength)

    recent = [{"O": round(c["o"]), "H": round(c["h"]),
               "L": round(c["l"]), "C": round(c["c"])} for c in candles[-4:-1]]
    cur = candles[-1]

    # v5.6 R4: Chainlink价格对齐 — 已在并行块中获取
    binance_price = cur["c"]
    cl_offset = 0.0
    if chainlink_ref is not None and binance_price > 0:
        cl_offset = round(chainlink_ref - binance_price)
        if abs(cl_offset) > 300:
            cl_offset = 0.0
        else:
            pred_close = round(pred_close + cl_offset)
            pred_high = round(pred_high + cl_offset)
            pred_low = round(pred_low + cl_offset)

    # v5.7.1 P0-1: ATR spike检测
    is_spike, spike_ratio, spike_count = atr_spike_detect(candles, atr_val)

    result = {
        "version": "5.8.0",
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
        "chainlink_offset": cl_offset,  # v5.6: Binance>Chainlink 价格偏移
        "atr_spike": {"detected": is_spike, "ratio": round(spike_ratio, 2),
                      "consecutive": spike_count},  # v5.7.1 P0-1
        "fng_black_swan": fng_black_swan,  # v5.7.1 P0-2: FNG<25时为True
        "news_risk": news_risk,  # v5.7.1 P0-3: NORMAL/BLACK_SWAN/CRITICAL
        "black_swan_warning": "⚠ News black swan active, direction unreliable" if news_black_swan else None,
        "prediction": {
            "bias": bias, "strength": strength,
            "confidence": confidence, "score": score,
            "pred_close": pred_close, "pred_high": pred_high, "pred_low": pred_low
        }
    }
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    run()
