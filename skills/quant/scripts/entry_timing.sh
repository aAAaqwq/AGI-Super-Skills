#!/bin/bash
# 入场时机分析 v2: Binance RSI/MA + Polymarket赔率趋势 + 结算时间感知
# 用法: bash entry_timing.sh <symbol> [token_id] [buffer_pct] [hours_to_settle] [market_type]
#   symbol: btc|eth|sol|gold
#   token_id: Polymarket token_id (可选，有则分析赔率趋势)
#   buffer_pct: 价格距阈值的缓冲百分比 (可选，如 5.48)
#   hours_to_settle: 距结算剩余小时数 (可选，如 48)
#   market_type: threshold|updown (可选，默认threshold)
#
# 输出: ENTRY_NOW / ENTRY_WAIT / ENTRY_SKIP + 详细信号
#
# v2更新 (3/15): 阈值盘(above/below)结合buffer+结算时间判断
#   - buffer充足+结算近 → RSI超买/高位惩罚大幅减弱
#   - 核心问题从"现在是不是高点"变成"结算前能跌破阈值吗"

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

# Binance API endpoint — data-api.binance.vision bypasses geo-restrictions
BINANCE_API="https://data-api.binance.vision/api/v3"

SYMBOL="${1:-btc}"
TOKEN_ID="${2:-}"
BUFFER_PCT="${3:-}"
HOURS_TO_SETTLE="${4:-}"
MARKET_TYPE="${5:-threshold}"

# 映射symbol到Binance交易对
case $(echo "$SYMBOL" | tr '[:upper:]' '[:lower:]') in
    btc) PAIR="BTCUSDT"; NAME="BTC" ;;
    eth) PAIR="ETHUSDT"; NAME="ETH" ;;
    sol) PAIR="SOLUSDT"; NAME="SOL" ;;
    gold) PAIR="PAXGUSDT"; NAME="GOLD" ;;
    *) echo "ERROR|Unknown symbol: $SYMBOL"; exit 1 ;;
esac

# === Part 1: Binance 1h K线 (30根) ===
K1H=$(curl -s --max-time 8 "$BINANCE_API/klines?symbol=$PAIR&interval=1h&limit=30" 2>/dev/null)
if [ -z "$K1H" ] || echo "$K1H" | grep -q '"code"'; then
    K1H=$(curl -s --max-time 8 "https://api.binance.us/api/v3/klines?symbol=$PAIR&interval=1h&limit=30" 2>/dev/null)
fi

if [ -z "$K1H" ] || echo "$K1H" | grep -q '"code"'; then
    echo "ENTRY_SKIP|${NAME}|API_ERROR|无法获取K线数据"
    exit 0
fi

# === Part 2: Polymarket赔率趋势 (如有token_id) ===
ODDS_DATA=""
if [ -n "$TOKEN_ID" ]; then
    ODDS_DATA=$(curl -s --max-time 8 "https://clob.polymarket.com/prices-history?market=$TOKEN_ID&interval=1h&fidelity=60" 2>/dev/null)
fi

# === 综合分析 ===
python3 - "$NAME" "$K1H" "$ODDS_DATA" "$BUFFER_PCT" "$HOURS_TO_SETTLE" "$MARKET_TYPE" << 'PYEOF'
import json, sys

name = sys.argv[1]
buffer_pct_str = sys.argv[4] if len(sys.argv) > 4 else ""
hours_str = sys.argv[5] if len(sys.argv) > 5 else ""
market_type = sys.argv[6] if len(sys.argv) > 6 else "threshold"

# 解析buffer和结算时间
buffer_pct = float(buffer_pct_str) if buffer_pct_str else None
hours_to_settle = float(hours_str) if hours_str else None

# --- Binance 1h K线分析 ---
try:
    k1h = json.loads(sys.argv[2])
except:
    print(f"ENTRY_SKIP|{name}|PARSE_ERROR")
    sys.exit(0)

closes = [float(k[4]) for k in k1h]
highs = [float(k[2]) for k in k1h]
lows = [float(k[3]) for k in k1h]
volumes = [float(k[5]) for k in k1h]

if len(closes) < 20:
    print(f"ENTRY_SKIP|{name}|INSUFFICIENT_DATA|K线不足20根")
    sys.exit(0)

price = closes[-1]

# RSI-14
def calc_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50
    gains = []
    losses = []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(max(0, diff))
        losses.append(max(0, -diff))
    gains = gains[-(period):]
    losses = losses[-(period):]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

rsi = calc_rsi(closes)

# MA20 & MA5
ma20 = sum(closes[-20:]) / 20
ma5 = sum(closes[-5:]) / 5
ma_pos = "ABOVE" if price > ma20 else "BELOW"
ma_dist = (price - ma20) / ma20 * 100

# 动量
momentum_4h = (closes[-1] - closes[-5]) / closes[-5] * 100 if len(closes) >= 5 else 0

# 成交量趋势
vol_recent = sum(volumes[-4:]) / 4
vol_prev = sum(volumes[-8:-4]) / 4 if len(volumes) >= 8 else vol_recent
vol_ratio = vol_recent / vol_prev if vol_prev > 0 else 1

# 24h高低点位置
high_24 = max(highs[-24:]) if len(highs) >= 24 else max(highs)
low_24 = min(lows[-24:]) if len(lows) >= 24 else min(lows)
range_24 = high_24 - low_24
pos_in_range = (price - low_24) / range_24 * 100 if range_24 > 0 else 50

# 回踩MA20
pullback_to_ma = abs(ma_dist) < 0.5 and price >= ma20

# 24h最大回撤 (用于评估buffer是否安全)
max_drawdown_24h = 0
if len(closes) >= 24:
    peak = closes[-24]
    for p in closes[-24:]:
        if p > peak:
            peak = p
        dd = (peak - p) / peak * 100
        if dd > max_drawdown_24h:
            max_drawdown_24h = dd

# --- 结算感知: Buffer安全度 ---
# 核心思想: 阈值盘的真正风险是"buffer被吃穿"，不是"短期是否高点"
buffer_safety = None  # None=未提供buffer信息
settlement_context = ""

if buffer_pct is not None and market_type == "threshold":
    # 计算buffer安全比: buffer / 历史最大回撤
    # 如果buffer远大于历史回撤，RSI超买根本不重要
    if max_drawdown_24h > 0:
        safety_ratio = buffer_pct / max_drawdown_24h
    else:
        safety_ratio = 10  # 无回撤=极安全

    # 结合结算时间: 时间越短越安全(来不及跌那么多)
    if hours_to_settle is not None:
        # 经验法则: 每24h最大可能回撤 ≈ max_drawdown_24h
        # 剩余时间越短，实际可能回撤越小
        time_factor = min(hours_to_settle / 24.0, 3.0)  # cap at 3天
        adjusted_risk = max_drawdown_24h * (time_factor ** 0.5)  # 平方根缩放
        if adjusted_risk > 0:
            safety_ratio = buffer_pct / adjusted_risk
        settlement_context = f"结算{hours_to_settle:.0f}h"
    else:
        settlement_context = "结算未知"

    # 安全度分级
    if safety_ratio >= 3:
        buffer_safety = "VERY_SAFE"    # buffer是潜在回撤的3倍+
    elif safety_ratio >= 1.5:
        buffer_safety = "SAFE"         # buffer是潜在回撤的1.5倍+
    elif safety_ratio >= 0.8:
        buffer_safety = "MODERATE"     # buffer勉强覆盖
    else:
        buffer_safety = "RISKY"        # buffer不够覆盖回撤

# --- Polymarket赔率趋势 ---
odds_trend = "N/A"
odds_momentum = 0
odds_signal = "NO_DATA"

odds_raw = sys.argv[3] if len(sys.argv) > 3 else ""
if odds_raw and odds_raw.strip():
    try:
        odds_data = json.loads(odds_raw)
        history = []
        if isinstance(odds_data, dict) and 'history' in odds_data:
            history = odds_data['history']
        elif isinstance(odds_data, list):
            history = odds_data

        if len(history) >= 4:
            recent_prices = []
            for h in history[-12:]:
                if isinstance(h, dict):
                    p = float(h.get('p', h.get('price', 0)))
                elif isinstance(h, (list, tuple)):
                    p = float(h[1]) if len(h) > 1 else 0
                else:
                    p = float(h)
                if p > 0:
                    recent_prices.append(p)

            if len(recent_prices) >= 4:
                odds_momentum = (recent_prices[-1] - recent_prices[-4]) / recent_prices[-4] * 100
                if odds_momentum > 2:
                    odds_trend = "RISING"
                elif odds_momentum < -2:
                    odds_trend = "FALLING"
                else:
                    odds_trend = "FLAT"

                current_odds = recent_prices[-1]
                odds_high = max(recent_prices)
                odds_low = min(recent_prices)

                if odds_high > 0 and (odds_high - current_odds) / odds_high * 100 > 3:
                    odds_signal = "ODDS_DIP"
                elif odds_low > 0 and (current_odds - odds_low) / odds_low * 100 > 5 and odds_momentum > 1:
                    odds_signal = "ODDS_CHASE"
                else:
                    odds_signal = "ODDS_NEUTRAL"
    except:
        pass

# === 综合打分 ===
signals_bull = 0
signals_bear = 0
reasons = []

# --- 结算感知模式 (阈值盘 + 有buffer信息) ---
if buffer_safety is not None and market_type == "threshold":
    reasons.append(f"Buf:{buffer_pct:.1f}%|MaxDD:{max_drawdown_24h:.1f}%|{buffer_safety}|{settlement_context}")

    if buffer_safety == "VERY_SAFE":
        # buffer远超风险 → RSI超买完全不重要，直接看趋势方向
        signals_bull += 3
        reasons.append("Buffer远超回撤风险→强入场✅")
        # RSI超买在这里反而是好事(说明趋势强)
        if rsi > 60:
            signals_bull += 1; reasons.append(f"RSI{rsi:.0f}趋势强")
        if ma_pos == "ABOVE":
            signals_bull += 1; reasons.append(f"MA20上方+{ma_dist:.1f}%")

    elif buffer_safety == "SAFE":
        # buffer够用 → RSI惩罚减半
        signals_bull += 2
        reasons.append("Buffer充足→可入场✅")
        if rsi > 70:
            signals_bear += 1; reasons.append(f"RSI超买{rsi:.0f}(减半)")
        elif rsi > 60:
            reasons.append(f"RSI{rsi:.0f}(忽略)")
        if ma_pos == "ABOVE":
            signals_bull += 1

    elif buffer_safety == "MODERATE":
        # buffer勉强 → 正常评估，略加分
        signals_bull += 1
        reasons.append("Buffer勉强→谨慎入场")
        # 正常RSI惩罚
        if rsi > 70:
            signals_bear += 2; reasons.append(f"RSI超买{rsi:.0f}")
        elif rsi > 60:
            signals_bear += 1; reasons.append(f"RSI偏高{rsi:.0f}")

    else:  # RISKY
        # buffer不足 → 加重惩罚
        signals_bear += 2
        reasons.append("Buffer不足⚠️回撤可能吃穿")
        if rsi > 70:
            signals_bear += 2; reasons.append(f"RSI超买{rsi:.0f}+buffer不足=危险")

    # 趋势方向仍然重要（不管buffer多大，逆势都要扣分）
    if momentum_4h < -1:
        signals_bear += 1; reasons.append(f"4h动量{momentum_4h:+.1f}%逆势⚠️")
    elif momentum_4h > 0.5:
        signals_bull += 1; reasons.append(f"4h动量{momentum_4h:+.1f}%顺势")

else:
    # --- 传统模式 (涨跌日盘/无buffer信息) ---
    # RSI
    if rsi < 30:
        signals_bull += 2; reasons.append(f"RSI超卖{rsi:.0f}")
    elif rsi < 40:
        signals_bull += 1; reasons.append(f"RSI偏低{rsi:.0f}")
    elif rsi > 70:
        signals_bear += 2; reasons.append(f"RSI超买{rsi:.0f}")
    elif rsi > 60:
        signals_bear += 1; reasons.append(f"RSI偏高{rsi:.0f}")
    else:
        reasons.append(f"RSI中性{rsi:.0f}")

    # MA位置
    if pullback_to_ma:
        signals_bull += 2; reasons.append("回踩MA20✅")
    elif ma_pos == "ABOVE" and ma_dist < 1.5:
        signals_bull += 1; reasons.append(f"MA20上方{ma_dist:+.1f}%")
    elif ma_pos == "BELOW":
        signals_bear += 1; reasons.append(f"MA20下方{ma_dist:+.1f}%")

    # 价格区间位置
    if pos_in_range < 25:
        signals_bull += 1; reasons.append(f"近24h低位{pos_in_range:.0f}%")
    elif pos_in_range > 80:
        signals_bear += 1; reasons.append(f"近24h高位{pos_in_range:.0f}%")

# 成交量 (两种模式都看)
if vol_ratio > 1.5:
    reasons.append(f"放量{vol_ratio:.1f}x")
elif vol_ratio < 0.5:
    reasons.append(f"缩量{vol_ratio:.1f}x")

# 赔率 (两种模式都看)
if odds_signal == "ODDS_DIP":
    signals_bull += 2; reasons.append("赔率回调✅")
elif odds_signal == "ODDS_CHASE":
    signals_bear += 2; reasons.append("赔率追高⚠️")

# === 最终判定 ===
score = signals_bull - signals_bear
if score >= 3:
    entry = "ENTRY_NOW"
elif score >= 1:
    entry = "ENTRY_WAIT"
else:
    entry = "ENTRY_SKIP"

# 构建模式标签
mode_tag = f"[{market_type.upper()}]" if buffer_safety else "[CLASSIC]"
detail = " | ".join(reasons)
print(f"{entry}|{name}|${price:,.1f}|RSI:{rsi:.0f}|MA20:{ma_pos}({ma_dist:+.1f}%)|4hMom:{momentum_4h:+.2f}%|Vol:{vol_ratio:.1f}x|Range:{pos_in_range:.0f}%|Odds:{odds_trend}({odds_momentum:+.1f}%)|Score:{score}|{mode_tag} {detail}")
PYEOF
