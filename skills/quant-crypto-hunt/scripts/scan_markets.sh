#!/bin/bash
# 扫描Polymarket日盘: Above盘 + Up/Down涨跌盘
# 用法: bash scan_markets.sh
# 输出: 每行一个市场，|分隔，适合机器解析

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

TODAY=$(TZ='America/New_York' date +%-d)
TOMORROW=$((TODAY+1))
DAY2=$((TODAY+2))
MONTH=$(LC_ALL=C TZ='America/New_York' date +%B | tr '[:upper:]' '[:lower:]')
YEAR=$(TZ='America/New_York' date +%Y)

echo "=== MARKET_SCAN ET:${MONTH}-${TODAY} $(TZ='Asia/Shanghai' date '+%H:%M') ==="

# A类: Above盘
echo "--- ABOVE ---"
for DAY in $TODAY $TOMORROW $DAY2; do
    for COIN in bitcoin ethereum solana; do
        SLUG="${COIN}-above-on-${MONTH}-${DAY}"
        R=$(curl -s --max-time 5 "https://gamma-api.polymarket.com/events?slug=$SLUG" 2>/dev/null)
        [ -z "$R" ] || [ "$R" = "[]" ] && continue
        echo "$R" | python3 -c "
import json,sys
try:
    events = json.load(sys.stdin)
except: sys.exit(0)
for e in events:
    end = e.get('endDate','')
    for m in e.get('markets',[]):
        try:
            p = json.loads(m.get('outcomePrices','[]'))
            y = float(p[0]) if p else 0
            n = 1 - y
            vol = m.get('volumeNum', 0)
            liq = m.get('liquidityNum', 0)
            q = m.get('question','')[:70]
            slug = m.get('slug','')
            # 只显示有意义的市场
            if 0.05 < y < 0.97:
                sweet = 'SWEET_YES' if 0.75 <= y <= 0.85 else ('SWEET_NO' if 0.75 <= n <= 0.85 else 'OUT')
                print(f'ABOVE|{q}|YES:{y:.1%}|NO:{n:.1%}|Vol:\${vol:,.0f}|Liq:\${liq:,.0f}|End:{end[:16]}|{sweet}|{slug}')
        except: pass
" 2>/dev/null
    done
done

# B类: Up/Down涨跌日盘
echo "--- UPDOWN ---"
for DAY in $TODAY $TOMORROW $DAY2; do
    for TICKER in gc btc eth sol; do
        SLUG="${TICKER}-up-or-down-on-${MONTH}-${DAY}-${YEAR}"
        R=$(curl -s --max-time 5 "https://gamma-api.polymarket.com/events?slug=$SLUG" 2>/dev/null)
        [ -z "$R" ] || [ "$R" = "[]" ] && continue
        C=$(echo "$R" | python3 -c "import json,sys;print(len(json.load(sys.stdin)))" 2>/dev/null)
        [ "$C" = "0" ] || [ -z "$C" ] && continue
        echo "$R" | python3 -c "
import json,sys
try:
    events = json.load(sys.stdin)
except: sys.exit(0)
for e in events:
    end = e.get('endDate','')
    for m in e.get('markets',[]):
        try:
            p = json.loads(m.get('outcomePrices','[]'))
            if len(p) < 2: continue
            up = float(p[0]); down = float(p[1])
            vol = m.get('volumeNum', 0)
            liq = m.get('liquidityNum', 0)
            q = m.get('question','')[:70]
            slug = m.get('slug','')
            sweet_up = 'SWEET_UP' if 0.75 <= up <= 0.85 else ''
            sweet_dn = 'SWEET_DN' if 0.75 <= down <= 0.85 else ''
            sweet = sweet_up or sweet_dn or 'OUT'
            print(f'UPDOWN|{q}|Up:{up:.1%}|Down:{down:.1%}|Vol:\${vol:,.0f}|Liq:\${liq:,.0f}|End:{end[:16]}|{sweet}|{slug}')
        except: pass
" 2>/dev/null
    done
done

echo "=== SCAN_DONE ==="
