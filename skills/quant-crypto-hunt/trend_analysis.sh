#!/bin/bash
# 趋势分析: BTC/ETH/SOL/GOLD 4h K线 + 24h涨跌 + 支撑阻力
# 用法: bash trend_analysis.sh [btc|eth|sol|gold|all]
# 输出: 结构化文本，直接可读

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

SYMBOLS=("BTCUSDT" "ETHUSDT" "SOLUSDT" "PAXGUSDT")
NAMES=("BTC" "ETH" "SOL" "GOLD")
TARGET="${1:-all}"

analyze_symbol() {
    local SYM="$1" NAME="$2"
    
    # 24h ticker
    local T24=$(curl -s --max-time 6 "https://api.binance.com/api/v3/ticker/24hr?symbol=$SYM" 2>/dev/null)
    if [ -z "$T24" ] || echo "$T24" | grep -q '"code"'; then
        echo "$NAME: API_ERROR"
        return
    fi
    
    # 4h K线
    local K4H=$(curl -s --max-time 6 "https://api.binance.com/api/v3/klines?symbol=$SYM&interval=4h&limit=4" 2>/dev/null)
    
    python3 -c "
import json,sys

try:
    t24 = json.loads('''$T24''')
    k4h = json.loads('''$K4H''')
except:
    print('$NAME: PARSE_ERROR')
    sys.exit(0)

name = '$NAME'
price = float(t24.get('lastPrice', 0))
chg24 = float(t24.get('priceChangePercent', 0))
high24 = float(t24.get('highPrice', 0))
low24 = float(t24.get('lowPrice', 0))

# 4h分析
up = 0; down = 0
candle_info = []
for k in k4h:
    o, h, l, c = float(k[1]), float(k[2]), float(k[3]), float(k[4])
    chg = (c - o) / o * 100
    if chg < 0:
        down += 1
        candle_info.append(f'↓{chg:.1f}%')
    else:
        up += 1
        candle_info.append(f'↑+{chg:.1f}%')

# 趋势判定
if down >= 3:
    trend = 'STRONG_DOWN'
    action = 'BAN_YES_UP'
elif down >= 2 and chg24 < -1:
    trend = 'DOWN'
    action = 'BAN_YES_UP'
elif up >= 3:
    trend = 'STRONG_UP'
    action = 'OK_YES_UP'
elif up >= 2 and chg24 > 1:
    trend = 'UP'
    action = 'OK_YES_UP'
else:
    trend = 'NEUTRAL'
    action = 'CAUTION'

# 距支撑/阻力
buf_support = (price - low24) / low24 * 100 if low24 > 0 else 0
buf_resist = (high24 - price) / high24 * 100 if high24 > 0 else 0

print(f'{name}|{price:.2f}|24h:{chg24:+.2f}%|4h:{up}↑{down}↓|{trend}|{action}|Support:{low24:.2f}({buf_support:.1f}%)|Resist:{high24:.2f}({buf_resist:.1f}%)|Candles:{\" \".join(candle_info)}')
" 2>/dev/null
}

echo "=== TREND_ANALYSIS $(TZ='Asia/Shanghai' date '+%Y-%m-%d %H:%M') ==="

if [ "$TARGET" = "all" ]; then
    for i in "${!SYMBOLS[@]}"; do
        analyze_symbol "${SYMBOLS[$i]}" "${NAMES[$i]}"
    done
else
    TARGET_UPPER=$(echo "$TARGET" | tr '[:lower:]' '[:upper:]')
    for i in "${!SYMBOLS[@]}"; do
        if [ "${NAMES[$i]}" = "$TARGET_UPPER" ]; then
            analyze_symbol "${SYMBOLS[$i]}" "${NAMES[$i]}"
            break
        fi
    done
fi
