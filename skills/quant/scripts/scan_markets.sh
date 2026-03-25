#!/bin/bash
# 扫描Polymarket日盘: Above盘 + Up/Down涨跌盘
# 用法: bash scan_markets.sh
# 输出: 每行一个市场，|分隔，适合机器解析
# v2.0 — 修复slug格式和API endpoint (2026-03-24)

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

# ET time for slug generation
MONTH=$(LC_ALL=C TZ='America/New_York' date +%B | tr '[:upper:]' '[:lower:]')
TODAY=$(TZ='America/New_York' date +%-d)
TOMORROW=$(TZ='America/New_York' date -d '+1 day' +%-d)
DAY2=$(TZ='America/New_York' date -d '+2 days' +%-d)
YEAR=$(TZ='America/New_York' date +%Y)

echo "=== MARKET_SCAN ET:${MONTH}-${TODAY} $(TZ='Asia/Shanghai' date '+%H:%M') ==="

# A类: Above盘
# slug格式: {coin}-above-on-{month}-{day}  (日结算)
#          {coin}-above-on-{month}-{day}-{year}-{hour}am-et (小时盘)
# API endpoint: events/slug/{slug} (单个event)
echo "--- ABOVE ---"
for DAY in $TODAY $TOMORROW $DAY2; do
    for COIN in bitcoin ethereum solana; do
        SLUG="${COIN}-above-on-${MONTH}-${DAY}"
        R=$(curl -s --max-time 5 "https://gamma-api.polymarket.com/events/slug/${SLUG}" 2>/dev/null)
        [ -z "$R" ] && continue
        echo "$R" | python3 -c "
import json,sys,re
try:
    d = json.load(sys.stdin)
except: sys.exit(0)
if 'id' not in d: sys.exit(0)
end = d.get('endDate','')
for m in d.get('markets',[]):
    try:
        p = json.loads(m.get('outcomePrices','[]'))
        if not p: continue
        y = float(p[0]); n = float(p[1])
        vol = float(m.get('volume',0))
        liq = float(m.get('liquidity',0) or 0)
        q = m.get('question','')[:70]
        slug = d.get('slug','')
        tokens = m.get('clobTokenIds','')
        # 提取阈值价格
        nums = re.findall(r'\\\$?([\d,]+)', q)
        threshold = nums[0] if nums else '?'
        # 只显示有意义的市场(排除0和1)
        if 0.05 < y < 0.97:
            sweet = 'SWEET_YES' if 0.75 <= y <= 0.83 else ('SWEET_NO' if 0.75 <= n <= 0.83 else 'OUT')
            tids = json.loads(tokens) if tokens else []
            yes_tid = tids[0][:30] if len(tids)>0 else ''
            no_tid = tids[1][:30] if len(tids)>1 else ''
            print(f'ABOVE|{q}|YES:{y:.2f}|NO:{n:.2f}|Vol:\${vol:,.0f}|Liq:\${liq:,.0f}|End:{end[:16]}|{sweet}|\${threshold}|{yes_tid}|{no_tid}')
    except: pass
" 2>/dev/null
    done
done

# B类: Up/Down涨跌日盘
# slug格式: {ticker}-up-or-down-on-{month}-{day}-{year}
echo "--- UPDOWN ---"
for DAY in $TODAY $TOMORROW $DAY2; do
    for TICKER in bitcoin ethereum solana; do
        SLUG="${TICKER}-up-or-down-on-${MONTH}-${DAY}-${YEAR}"
        R=$(curl -s --max-time 5 "https://gamma-api.polymarket.com/events/slug/${SLUG}" 2>/dev/null)
        [ -z "$R" ] && continue
        echo "$R" | python3 -c "
import json,sys
try:
    d = json.load(sys.stdin)
except: sys.exit(0)
if 'id' not in d: sys.exit(0)
end = d.get('endDate','')
for m in d.get('markets',[]):
    try:
        p = json.loads(m.get('outcomePrices','[]'))
        if len(p) < 2: continue
        up = float(p[0]); down = float(p[1])
        vol = float(m.get('volume',0))
        liq = float(m.get('liquidity',0) or 0)
        q = m.get('question','')[:70]
        slug = d.get('slug','')
        tokens = m.get('clobTokenIds','')
        sweet_up = 'SWEET_UP' if 0.75 <= up <= 0.83 else ''
        sweet_dn = 'SWEET_DN' if 0.75 <= down <= 0.83 else ''
        sweet = sweet_up or sweet_dn or 'OUT'
        tids = json.loads(tokens) if tokens else []
        up_tid = tids[0][:30] if len(tids)>0 else ''
        dn_tid = tids[1][:30] if len(tids)>1 else ''
        print(f'UPDOWN|{q}|Up:{up:.2f}|Down:{down:.2f}|Vol:\${vol:,.0f}|Liq:\${liq:,.0f}|End:{end[:16]}|{sweet}|{up_tid}|{dn_tid}')
    except: pass
" 2>/dev/null
    done
done

echo "=== SCAN_DONE ==="
