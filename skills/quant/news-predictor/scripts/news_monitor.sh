#!/bin/bash
# news_monitor.sh — Scan crypto/macroeconomic news for price-moving signals
# Output: JSON array of signals

set -euo pipefail
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

# DANGER keywords (bearish, crash-predicting)
DANGER_WORDS="hawkish|rate hike|higher for longer|inflation rises|war escalat|military|sanctions|hack|exploit|flash crash|bankrupt|insolvent|SEC charg|regulatory crackdown|recession|slowdown|contraction|crisis|sell-off|bloodbath|capitulation|plunge|miner capitul|whale dump|large transfer to exchange| Powell |rate cut hopes fade|cheap money is over"

# OPPORTUNITY keywords (bullish)
OPP_WORDS="dovish|rate cut|easing|stimulus|ceasefire|peace talk|ETF approved|inflow record|institutional adoption|regulatory clarity|pro-crypto|legalized|breakout|ATH|rally|surge|partnership|adopted by|hash rate ATH|miner accumulation"

# CAUTION keywords (uncertain/elevated risk)
CAUTION_WORDS="Fed meeting|CPI release|PPI data|NFP|awaiting|pending|uncertain|mixed signals|volatile|resistance level|support test|consolidation"

COINDESK="https://www.coindesk.com/arc/outboundfeeds/rss/"
HEADLINES=""

# Fetch CoinDesk RSS
curl -sL --max-time 15 "$COINDESK" -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64)" > "$TMPDIR/coindesk.xml" 2>/dev/null || true

if [ -s "$TMPDIR/coindesk.xml" ]; then
    HEADLINES=$(python3 -c "
import sys, re
from datetime import datetime, timezone, timedelta

xml = open('$TMPDIR/coindesk.xml').read()
items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)

BJ = timezone(timedelta(hours=8))
now = datetime.now(BJ)
cutoff = now - timedelta(hours=24)

results = []
for item in items[:30]:
    title = re.search(r'<title><!\[CDATA\[([^\]]+)\]\]></title>', item)
    date_s = re.search(r'<pubDate>([^<]+)</pubDate>', item)
    desc = re.search(r'<description><!\[CDATA\[([^\]]*)\]\]></description>', item)
    
    if not title: continue
    t = title.group(1).strip()
    
    # Parse date
    if date_s:
        try:
            # RSS dates: 'Wed, 18 Mar 2026 20:19:04 +0000'
            dt = datetime.strptime(date_s.group(1).strip(), '%a, %d %b %Y %H:%M:%S %z')
            dt = dt.astimezone(BJ)
        except:
            dt = now
    else:
        dt = now
    
    if dt < cutoff: continue
    
    d = desc.group(1).strip()[:200] if desc else ''
    combined = (t + ' ' + d).lower()
    
    # Classify
    danger_w = [w for w in ['hawkish','rate hike','higher for longer','inflation ris','war escalat','military conflict','sanction','hack','exploit','flash crash','bankrupt','insolvent','sec charg','regulatory crackdown','recession','slowdown','contraction','crisis','sell-off','bloodbath','capitulation','plunge','miner capitul','whale dump','rate cut hopes fade','cheap money is over','powell'] if w in combined]
    opp_w = [w for w in ['dovish','rate cut','easing','stimulus','ceasefire','peace talk','etf approved','inflow record','institutional adoption','regulatory clarity','pro-crypto','legalized','breakout','ath','rally','surge','partnership','adopted by','hash rate ath','miner accumulation'] if w in combined]
    caution_w = [w for w in ['fed meeting','cpi release','ppi data','nfp','awaiting','pending','uncertain','mixed signal','volatile','resistance','support test','consolidation'] if w in combined]
    
    if danger_w and len(danger_w) >= len(opp_w) and len(danger_w) >= len(caution_w):
        sentiment = 'bearish'
        impact = min(10, 5 + len(danger_w))
    elif opp_w and len(opp_w) > len(danger_w):
        sentiment = 'bullish'
        impact = min(10, 4 + len(opp_w))
    elif caution_w:
        sentiment = 'caution'
        impact = min(10, 3 + len(caution_w))
    else:
        sentiment = 'neutral'
        impact = 1
    
    # Determine affected assets
    assets = []
    asset_map = {
        'bitcoin': ['BTC'], 'btc': ['BTC'], 'ethereum': ['ETH'], 'eth': ['ETH'],
        'solana': ['SOL'], 'sol': ['SOL'], 'crypto': ['BTC','ETH','SOL'],
        'gold': ['GOLD'], 'oil': ['OIL'], 'energy': ['OIL','GOLD'],
        'fed': ['BTC','ETH','SOL'], 'inflation': ['BTC','ETH','SOL'],
        'iran': ['BTC','ETH','SOL','GOLD','OIL'],
    }
    for key, vals in asset_map.items():
        if key in combined:
            assets.extend(vals)
    assets = list(dict.fromkeys(assets))  # dedupe
    
    # Fed multiplier
    if 'fed' in combined or 'powell' in combined:
        impact = min(10, int(impact * 1.5))
    # Geopolitical multiplier
    if 'iran' in combined or 'war' in combined:
        impact = min(10, int(impact * 1.3))
    
    if sentiment != 'neutral':
        results.append({
            'ts': dt.strftime('%Y-%m-%dT%H:%M:%S+08:00'),
            'headline': t[:150],
            'source': 'coindesk',
            'sentiment': sentiment,
            'impact': impact,
            'signal': 'DANGER' if impact >= 7 else ('OPPORTUNITY' if sentiment == 'bullish' and impact >= 5 else 'CAUTION'),
            'assets': assets
        })

print(results.__repr__())
" 2>/dev/null) || HEADLINES="[]"
fi

if [ -z "$HEADLINES" ] || [ "$HEADLINES" = "[]" ]; then
    echo "[]"
else
    echo "$HEADLINES"
fi
