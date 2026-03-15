#!/bin/bash
# Fetch crypto prices + 4h trend from Binance
# Usage: bash price_check.sh [btc|eth|sol|all]
# Output: structured price + trend data

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

TARGET="${1:-all}"
SYMBOLS=("BTCUSDT" "ETHUSDT" "SOLUSDT")
NAMES=("BTC" "ETH" "SOL")

check_symbol() {
    local SYM="$1" NAME="$2"
    local PRICE=$(curl -s --max-time 8 "https://api.binance.com/api/v3/ticker/price?symbol=$SYM" 2>/dev/null)
    local K4H=$(curl -s --max-time 5 "https://api.binance.com/api/v3/klines?symbol=$SYM&interval=4h&limit=3" 2>/dev/null)

    python3 -c "
import json,sys
try:
    p = json.loads('''$PRICE''')
    k = json.loads('''$K4H''')
    price = float(p['price'])
    down = sum(1 for c in k if float(c[4]) < float(c[1]))
    candles = ' '.join(f'{'↓' if float(c[4])<float(c[1]) else '↑'}{(float(c[4])-float(c[1]))/float(c[1])*100:+.2f}%' for c in k)
    print(f'$NAME|\${price:,.2f}|4h:{3-down}↑{down}↓|{candles}')
except Exception as e:
    print(f'$NAME|ERROR|{e}')
" 2>/dev/null
}

if [ "$TARGET" = "all" ]; then
    for i in "${!SYMBOLS[@]}"; do
        check_symbol "${SYMBOLS[$i]}" "${NAMES[$i]}"
    done
else
    T=$(echo "$TARGET" | tr '[:lower:]' '[:upper:]')
    for i in "${!SYMBOLS[@]}"; do
        [ "${NAMES[$i]}" = "$T" ] && check_symbol "${SYMBOLS[$i]}" "${NAMES[$i]}"
    done
fi
