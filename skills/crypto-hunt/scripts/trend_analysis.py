#!/usr/bin/env python3
"""
Trend Analyzer v1.0
从 trend_raw.json 读取原始K线数据，做趋势分析+入场判断。

输出: data/trend_analysis.json — 每币种的趋势指标和入场评估

分析内容:
1. 均线趋势 (SMA5/SMA10/SMA20)
2. 动量 (4h/12h/24h变化率)
3. RSI (14周期)
4. 趋势强度评分
5. 入场时机: 结合趋势方向+均值偏离度判断
6. 结算预测: 基于当前趋势预测N小时后的价格走向

用法: python3 trend_analysis.py [--predict-hours 14]
"""
import json, sys, os, math
from pathlib import Path
from datetime import datetime, timezone, timedelta

SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / "data"

def sma(data: list, period: int) -> list:
    """简单移动平均"""
    result = []
    for i in range(len(data)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(sum(data[i-period+1:i+1]) / period)
    return result

def rsi(closes: list, period: int = 14) -> float:
    """RSI计算"""
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0 for d in deltas[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def volatility(closes: list, period: int = 24) -> float:
    """年化波动率(基于小时收益率)"""
    if len(closes) < period + 1:
        return 0.0
    returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(-period, 0)]
    mean_r = sum(returns) / len(returns)
    var = sum((r - mean_r) ** 2 for r in returns) / len(returns)
    return math.sqrt(var) * math.sqrt(8760) * 100  # 年化

def predict_price(closes: list, hours_ahead: float) -> dict:
    """
    基于趋势外推预测价格。
    用最近12h的线性回归斜率外推，结合波动率给置信区间。
    """
    if len(closes) < 12:
        return {"predicted": closes[-1], "low": closes[-1], "high": closes[-1], "confidence": 0}
    
    recent = closes[-12:]
    n = len(recent)
    # 线性回归
    x_mean = (n - 1) / 2
    y_mean = sum(recent) / n
    num = sum((i - x_mean) * (recent[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    slope = num / den if den != 0 else 0
    
    predicted = closes[-1] + slope * hours_ahead
    
    # 置信区间: 1个标准差 × sqrt(hours)
    vol = 0
    if len(closes) > 2:
        returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
        vol = math.sqrt(sum(r**2 for r in returns) / len(returns))
    
    uncertainty = closes[-1] * vol * math.sqrt(hours_ahead)
    
    return {
        "predicted": round(predicted, 4),
        "low": round(predicted - uncertainty, 4),
        "high": round(predicted + uncertainty, 4),
        "slope_per_hour": round(slope, 6),
        "confidence": round(min(1.0, 1.0 - uncertainty / closes[-1] if closes[-1] > 0 else 0), 2),
    }

def classify_trend(closes: list) -> dict:
    """
    综合判断趋势: 均线排列 + 动量 + RSI
    """
    if len(closes) < 20:
        return {"trend": "NEUTRAL", "strength": 0, "details": "insufficient data"}
    
    sma5 = sma(closes, 5)
    sma10 = sma(closes, 10)
    sma20 = sma(closes, 20)
    
    current = closes[-1]
    s5 = sma5[-1]
    s10 = sma10[-1]
    s20 = sma20[-1]
    
    # 均线排列得分 (-3 to +3)
    ma_score = 0
    if s5 and s10 and s20:
        if s5 > s10 > s20:
            ma_score = 3  # 完美多头
        elif s5 > s10:
            ma_score = 2
        elif s5 > s20:
            ma_score = 1
        elif s5 < s10 < s20:
            ma_score = -3  # 完美空头
        elif s5 < s10:
            ma_score = -2
        elif s5 < s20:
            ma_score = -1
    
    # 动量得分 (4h, 12h, 24h)
    chg_4h = (closes[-1] - closes[-5]) / closes[-5] * 100 if len(closes) >= 5 else 0
    chg_12h = (closes[-1] - closes[-13]) / closes[-13] * 100 if len(closes) >= 13 else 0
    chg_24h = (closes[-1] - closes[-25]) / closes[-25] * 100 if len(closes) >= 25 else 0
    
    mom_score = chg_4h * 0.5 + chg_12h * 0.3 + chg_24h * 0.2
    
    # RSI
    rsi_val = rsi(closes, 14)
    
    # 综合得分
    total = ma_score * 0.4 + max(-3, min(3, mom_score)) * 0.35 + ((rsi_val - 50) / 16.67) * 0.25
    
    if total > 1.5:
        trend = "STRONG_UP"
    elif total > 0.5:
        trend = "UP"
    elif total < -1.5:
        trend = "STRONG_DOWN"
    elif total < -0.5:
        trend = "DOWN"
    else:
        trend = "NEUTRAL"
    
    return {
        "trend": trend,
        "strength": round(total, 2),
        "ma_score": ma_score,
        "mom_4h": round(chg_4h, 2),
        "mom_12h": round(chg_12h, 2),
        "mom_24h": round(chg_24h, 2),
        "rsi": round(rsi_val, 1),
        "sma5": round(s5, 4) if s5 else None,
        "sma10": round(s10, 4) if s10 else None,
        "sma20": round(s20, 4) if s20 else None,
        "price": current,
    }

def entry_signal(trend_info: dict, side: str) -> dict:
    """
    判断是否适合入场。
    side: YES(押涨) 或 NO(押跌)
    
    逻辑:
    - 趋势方向和side一致 → 适合入场
    - 趋势方向和side相反 → 需要更强的buffer保护
    - 均值偏离度大 → 可能均值回归，但风险也大
    """
    trend = trend_info["trend"]
    strength = trend_info["strength"]
    rsi = trend_info["rsi"]
    
    is_bullish_side = side.upper() == "YES"
    
    # 趋势一致性
    if is_bullish_side:
        trend_aligned = trend in ("STRONG_UP", "UP")
        trend_opposed = trend in ("STRONG_DOWN", "DOWN")
    else:
        trend_aligned = trend in ("STRONG_DOWN", "DOWN")
        trend_opposed = trend in ("STRONG_UP", "UP")
    
    # RSI辅助
    rsi_favorable = (is_bullish_side and rsi < 65) or (not is_bullish_side and rsi > 35)
    rsi_extreme = rsi > 80 or rsi < 20
    
    if trend_aligned and rsi_favorable:
        signal = "FAVORABLE"
        multiplier = 1.0
    elif trend_aligned:
        signal = "OK"
        multiplier = 0.75
    elif trend == "NEUTRAL":
        signal = "NEUTRAL"
        multiplier = 0.5
    elif trend_opposed and not rsi_extreme:
        signal = "UNFAVORABLE"
        multiplier = 0.25
    else:
        signal = "DANGEROUS"
        multiplier = 0.1
    
    return {
        "signal": signal,
        "multiplier": multiplier,
        "trend_aligned": trend_aligned,
        "trend_opposed": trend_opposed,
        "rsi_favorable": rsi_favorable,
    }

def main():
    predict_hours = 14.0
    if "--predict-hours" in sys.argv:
        idx = sys.argv.index("--predict-hours")
        predict_hours = float(sys.argv[idx + 1])
    
    raw_path = DATA_DIR / "trend_raw.json"
    if not raw_path.exists():
        print("❌ trend_raw.json not found. Run trend_data.py first.")
        return 1
    
    with open(raw_path) as f:
        raw = json.load(f)
    
    cst = datetime.now(timezone(timedelta(hours=8)))
    print(f"Trend Analysis v1.0 — {cst.strftime('%Y-%m-%d %H:%M')} CST")
    print("━" * 50)
    
    analysis = {}
    for coin, d in raw.items():
        closes = [k["close"] for k in d["klines"]]
        if len(closes) < 20:
            print(f"  ⚠ {coin}: insufficient data ({len(closes)} candles)")
            continue
        
        trend_info = classify_trend(closes)
        vol = volatility(closes)
        pred = predict_price(closes, predict_hours)
        
        yes_entry = entry_signal(trend_info, "YES")
        no_entry = entry_signal(trend_info, "NO")
        
        analysis[coin] = {
            **trend_info,
            "volatility_ann": round(vol, 1),
            "predict_hours": predict_hours,
            "prediction": pred,
            "entry_YES": yes_entry,
            "entry_NO": no_entry,
        }
        
        print(f"  {coin}: ${trend_info['price']:,.2f} | {trend_info['trend']} (str={trend_info['strength']:.1f})")
        print(f"    RSI={trend_info['rsi']:.0f} | Vol={vol:.0f}% | 4h={trend_info['mom_4h']:+.2f}%")
        print(f"    SMA5/10/20: {trend_info['sma5']:.2f} / {trend_info['sma10']:.2f} / {trend_info['sma20']:.2f}")
        print(f"    Predict({predict_hours}h): ${pred['predicted']:,.2f} [{pred['low']:,.2f} ~ {pred['high']:,.2f}] conf={pred['confidence']}")
        print(f"    Entry: YES={yes_entry['signal']}({yes_entry['multiplier']}) | NO={no_entry['signal']}({no_entry['multiplier']})")
    
    out_path = DATA_DIR / "trend_analysis.json"
    with open(out_path, "w") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    print(f"\nSaved → {out_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
