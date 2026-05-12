#!/usr/bin/env python3
"""
Decision Engine v6.1

核心: Polymarket概率 + Binance广场最新新闻(6h内) → 综合判断
- 稳健层(80-96¢): 价格对就买，只怕重大反转新闻
- 风投层(60-80¢): 需要新闻支持方向
- 新闻权重 > 趋势权重
- 趋势仅辅助参考

输入: data/actionable/ + web搜索Binance广场最新消息 + data/trend_analysis.json
输出: data/decisions.json
"""
import json, sys, re
from pathlib import Path
from datetime import datetime, timezone, timedelta

SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / "data"

# ━━━ 常量 ━━━
FEE = 0.02
MIN_POSITION = 5.0  # Polymarket最小5 shares
MAX_POSITION_STABLE = 4.0
MAX_POSITION_RISK = 2.5
MAX_TOTAL_RISK = 8.0
BANKROLL = 28.0

STABLE_YES_MIN = 0.80
STABLE_YES_MAX = 0.96
RISK_YES_MIN = 0.60
RISK_YES_MAX = 0.80
NO_YES_MIN = 0.04
NO_YES_MAX = 0.40


# ━━━ 工具 ━━━
def load_json(path, default=None):
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except:
            pass
    return default if default is not None else {}


def parse_threshold(raw) -> float:
    """解析阈值，兼容各种格式"""
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip().replace(',', '').replace('$', '')
    # "1pt40" → "1.40" (XRP格式)
    s = s.replace('pt', '.')
    # "78k" → 78000
    if s.lower().endswith('k'):
        try:
            return float(s[:-1]) * 1000
        except:
            pass
    try:
        return float(s)
    except:
        return 0.0


def classify_layer(yes_price: float, direction: str) -> tuple:
    """分层: 稳健/风投/禁止"""
    if direction == "YES":
        if STABLE_YES_MIN <= yes_price <= STABLE_YES_MAX:
            return "稳健", "YES"
        elif RISK_YES_MIN <= yes_price < STABLE_YES_MIN:
            return "风投", "YES"
        elif yes_price > STABLE_YES_MAX:
            return "禁止", "YES"
        else:
            return "禁止", "YES"
    else:  # NO
        no_price = 1 - yes_price
        if NO_YES_MIN <= yes_price <= 0.20:
            return "稳健", "NO"
        elif 0.20 < yes_price <= NO_YES_MAX:
            return "风投", "NO"
        else:
            return "禁止", "NO"


def fetch_latest_news() -> list:
    """
    从web搜索Binance广场最新6h内的加密新闻
    返回: [{title, time, direction, coin, impact}]
    """
    # 这里在实际运行时会由hunt.sh调用web搜索
    # decision_engine自己不做网络请求，依赖调用方注入
    # 从news_direction.json读取(如果有)
    news_data = load_json(DATA_DIR / "news_direction.json", {})
    if news_data:
        score = float(news_data.get("score", 0))
        direction = "BULLISH" if score > 0.1 else ("BEARISH" if score < -0.1 else "NEUTRAL")
        return [{
            'direction': direction,
            'confidence': min(1.0, abs(score)),
            'source': 'news_direction.json',
        }]
    return [{'direction': 'NEUTRAL', 'confidence': 0.0, 'source': 'default'}]


def get_trend_info(trend_data: dict, coin: str) -> tuple:
    """获取趋势 (direction, price)"""
    d = trend_data.get(coin, {})
    if not d:
        return "NEUTRAL", 0
    trend = d.get("trend", "NEUTRAL")
    price = d.get("price", 0)
    if trend in ("STRONG_UP", "UP"):
        return "UP", price
    elif trend in ("STRONG_DOWN", "DOWN"):
        return "DOWN", price
    return "NEUTRAL", price


def judge_trade(
    yes_price, direction, layer,
    news_items, trend_dir,
    market_type, price, threshold, hours_left
) -> tuple:
    """
    综合判断
    
    稳健层: 价格对就直接买，除非有重大利空反转信号
    风投层: 需要新闻支持
    
    权重: 新闻60% > 趋势20% > 价格位置20%
    
    Returns: (should_trade, reason, confidence)
    """
    is_above = market_type == "ABOVE"
    price_above = price > threshold if threshold > 0 else False
    
    # 取最强的新闻信号
    news_dir = "NEUTRAL"
    news_conf = 0.0
    for n in news_items:
        if abs(n.get('confidence', 0)) > news_conf:
            news_dir = n.get('direction', 'NEUTRAL')
            news_conf = n.get('confidence', 0)
    
    # ── 判断新闻是否支持/反对交易方向 ──
    if direction == "YES":
        news_supports = (is_above and news_dir == "BULLISH") or (not is_above and news_dir == "BEARISH")
        news_opposes = (is_above and news_dir == "BEARISH") or (not is_above and news_dir == "BULLISH")
        trend_supports = (is_above and trend_dir == "UP") or (not is_above and trend_dir == "DOWN")
        price_supports = (is_above and price_above) or (not is_above and not price_above)
    else:  # NO
        news_supports = (is_above and news_dir == "BEARISH") or (not is_above and news_dir == "BULLISH")
        news_opposes = (is_above and news_dir == "BULLISH") or (not is_above and news_dir == "BEARISH")
        trend_supports = (is_above and trend_dir == "DOWN") or (not is_above and trend_dir == "UP")
        price_supports = not ((is_above and price_above) or (not is_above and not price_above))
    
    score = 0
    reasons = []
    
    # 新闻权重60%
    if news_supports:
        score += news_conf * 0.60
        reasons.append(f"新闻{news_dir}支持")
    elif news_opposes:
        score -= 0.30
        reasons.append(f"⚠️新闻{news_dir}反对")
    else:
        # NEUTRAL: 不加分也不扣分
        pass
    
    # 趋势权重20% (辅助)
    if trend_supports:
        score += 0.20
        reasons.append(f"趋势{trend_dir}辅助")
    
    # 价格位置20%
    if price_supports:
        score += 0.20
        reasons.append("价格位置支持")
    
    # ── 层级判断 ──
    if layer == "稳健":
        # 稳健层: 价格大概率对，直接买
        # 唯一拦路虎: 重大利空反转
        if news_opposes and news_conf > 0.3:
            return False, f"⚠️重大反转信号: {news_dir} conf={news_conf:.2f} | " + " | ".join(reasons), score
        # 价格位置不对也拦
        if not price_supports:
            return False, f"价格位置不支持(价格{'<低于阈值' if is_above else '>高于阈值'}) | " + " | ".join(reasons), score
        # 通过
        return True, " | ".join(reasons) if reasons else "稳健层直接通过", max(score, 0.3)
    
    else:  # 风投
        # 风投层: 需要新闻或趋势支持
        if score >= 0.35:
            return True, " | ".join(reasons), score
        else:
            return False, f"评分{score:.2f}<0.35: " + " | ".join(reasons), score


def calc_position(layer, yes_price, direction, confidence):
    if layer == "稳健":
        base = MAX_POSITION_STABLE
    else:
        base = MAX_POSITION_RISK
    pos = base * max(confidence, 0.4)  # 最低40%仓位
    pos = min(pos, BANKROLL * 0.15)
    return max(MIN_POSITION, round(pos, 1))


# ━━━ 主逻辑 ━━━
def make_decisions():
    actionable = load_json(DATA_DIR / "actionable", [])
    if isinstance(actionable, dict):
        actionable = list(actionable.values())
    trend_data = load_json(DATA_DIR / "trend_analysis.json", {})
    news_items = fetch_latest_news()
    
    cst = datetime.now(timezone(timedelta(hours=8)))
    print(f"\n{'━'*60}")
    print(f"Decision Engine v6.1 — {cst.strftime('%Y-%m-%d %H:%M')} CST")
    print(f"  市场: {len(actionable)}")
    news_dir = news_items[0]['direction'] if news_items else 'NEUTRAL'
    print(f"  新闻: {news_dir}")
    print(f"{'━'*60}")
    
    trades = []
    total_risk = 0.0
    
    for raw in actionable:
        if not isinstance(raw, dict):
            continue
        coin = raw.get("coin", "?").upper()
        mtype = raw.get("type", "UNKNOWN").upper()
        yes_price = raw.get("yes_price", 0)
        threshold = parse_threshold(raw.get("threshold", ""))
        hours_left = float(raw.get("hours_left", 0))
        question = raw.get("question", "")
        market_slug = raw.get("market_slug", "")
        
        if not yes_price or mtype in ("UPDOWN", "UNKNOWN") or threshold <= 0 or hours_left < 2:
            continue
        
        trend_dir, price = get_trend_info(trend_data, coin)
        if price <= 0:
            continue
        
        # 尝试YES和NO两个方向
        candidates = []
        for direction in ["YES", "NO"]:
            layer, _ = classify_layer(yes_price, direction)
            if layer == "禁止":
                continue
            
            should, reason, confidence = judge_trade(
                yes_price, direction, layer,
                news_items, trend_dir,
                mtype, price, threshold, hours_left
            )
            if should:
                pos = calc_position(layer, yes_price, direction, confidence)
                candidates.append({
                    'direction': direction, 'layer': layer,
                    'confidence': confidence, 'reason': reason, 'position': pos,
                })
        
        if not candidates:
            print(f"  ❌ {coin} {mtype}@{threshold:,.0f} YES={yes_price:.0%} | 无通过方向")
            continue
        
        best = max(candidates, key=lambda c: c['confidence'])
        
        if total_risk + best['position'] > MAX_TOTAL_RISK:
            best['position'] = MAX_TOTAL_RISK - total_risk
            if best['position'] < MIN_POSITION:
                continue
        
        total_risk += best['position']
        
        if best['direction'] == "YES":
            payoff, cost = 1 - yes_price, yes_price
        else:
            payoff, cost = yes_price, 1 - yes_price
        rr = payoff / cost if cost > 0 else 0
        buf = abs(price - threshold) / price * 100 if price > 0 else 0
        
        trades.append({
            'market': market_slug,
            'question': question[:80],
            'coin': coin,
            'market_type': mtype,
            'threshold': threshold,
            'yes_price': yes_price,
            'direction': best['direction'],
            'layer': best['layer'],
            'news_direction': news_dir,
            'trend_direction': trend_dir,
            'position': round(best['position'], 1),
            'risk_reward': round(rr, 2),
            'buffer_pct': round(buf, 1),
            'hours_left': round(hours_left, 1),
            'confidence': round(best['confidence'], 2),
            'reason': best['reason'],
            'decision': 'TRADE',
            'current_price': round(price, 2),
        })
        
        icon = "🟢" if best['layer'] == "稳健" else "🟡"
        print(f"  {icon} {coin} {mtype}@{threshold:,.0f} {best['direction']} "
              f"${best['position']:.1f} [{best['layer']}] "
              f"RR={rr:.2f} | {best['reason'][:60]}")
    
    # 摘要
    print(f"\n{'━'*60}")
    stable = [t for t in trades if t['layer'] == "稳健"]
    risk = [t for t in trades if t['layer'] == "风投"]
    print(f"  稳健: {len(stable)}笔 ${sum(t['position'] for t in stable):.1f}")
    print(f"  风投: {len(risk)}笔 ${sum(t['position'] for t in risk):.1f}")
    print(f"  总风险: ${total_risk:.1f}/${MAX_TOTAL_RISK}")
    
    with open(DATA_DIR / "decisions.json", "w") as f:
        json.dump(trades, f, indent=2, ensure_ascii=False)
    
    if trades:
        print(f"\n  执行:")
        for t in trades:
            print(f"    python3 scripts/trade.py buy {t['coin']} "
                  f"--type {t['market_type']} --threshold {t['threshold']} "
                  f"--side {t['direction']} {t['position']}")
    
    return trades


if __name__ == "__main__":
    make_decisions()
