#!/bin/bash
# 入场时机分析: Binance RSI/MA + Polymarket赔率趋势
# 用法: bash entry_timing.sh <symbol> [token_id]
#   symbol: btc|eth|sol|gold
#   token_id: Polymarket token_id (可选，有则分析赔率趋势)
# 输出: ENTRY_NOW / ENTRY_WAIT / ENTRY_SKIP + 详细信号

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

SYMBOL="${1:-btc}"
TOKEN_ID="${2:-}"

# 映射symbol到Binance交易对
case $(echo "$SYMBOL" | tr '[:upper:]' '[:lower:]') in
    btc) PAIR="BTCUSDT"; NAME="BTC" ;;
    eth) PAIR="ETHUSDT"; NAME="ETH" ;;
    sol) PAIR="SOLUSDT"; NAME="SOL" ;;
    gold) PAIR="PAXGUSDT"; NAME="GOLD" ;;
    *) echo "ERROR|Unknown symbol: $SYMBOL"; exit 1 ;;
esac

# === Part 1: Binance 1h K线 (30根) ===
K1H=$(curl -s --max-time 8 "https://api.binance.com/api/v3/klines?symbol=$PAIR&interval=1h&limit=30" 2>/dev/null)

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
python3 - "$NAME" "$K1H" "$ODDS_DATA" << 'PYEOF'
import json, sys

name = sys.argv[1]

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

# 成交量
if vol_ratio > 1.5:
    reasons.append(f"放量{vol_ratio:.1f}x")
elif vol_ratio < 0.5:
    reasons.append(f"缩量{vol_ratio:.1f}x")

# 赔率
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

detail = " | ".join(reasons)
print(f"{entry}|{name}|${price:,.1f}|RSI:{rsi:.0f}|MA20:{ma_pos}({ma_dist:+.1f}%)|4hMom:{momentum_4h:+.2f}%|Vol:{vol_ratio:.1f}x|Range:{pos_in_range:.0f}%|Odds:{odds_trend}({odds_momentum:+.1f}%)|Score:{score}|{detail}")
PYEOF
