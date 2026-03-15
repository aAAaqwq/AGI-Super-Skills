#!/bin/bash
# Search for active Elon tweet prediction markets on Polymarket
# Usage: bash elon_slug_search.sh
# Output: BEST_SLUG and BEST_END, or "NO_ACTIVE_MARKET"

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

ET_DAY=$(TZ='America/New_York' date +%-d)
ET_MONTH=$(LC_ALL=C TZ='America/New_York' date +%B | tr '[:upper:]' '[:lower:]')
NOW_UTC=$(date -u +%Y-%m-%dT%H:%M:%S)

BEST_SLUG=""
BEST_END="9999"

for START in $(seq $((ET_DAY-10)) $((ET_DAY+2))); do
  [ $START -lt 1 ] && continue
  for WINDOW in 2 7; do
    END=$((START+WINDOW))
    SLUG="elon-musk-of-tweets-${ET_MONTH}-${START}-${ET_MONTH}-${END}"
    R=$(curl -s --max-time 4 "https://gamma-api.polymarket.com/events?slug=$SLUG" 2>/dev/null)
    C=$(echo "$R" | python3 -c "import json,sys;d=json.load(sys.stdin);print(len(d))" 2>/dev/null)
    if [ "$C" != "0" ] && [ -n "$C" ]; then
      END_DATE=$(echo "$R" | python3 -c "import json,sys;print(json.load(sys.stdin)[0].get('endDate',''))" 2>/dev/null)
      if [[ "$END_DATE" > "$NOW_UTC" ]]; then
        if [[ "$END_DATE" < "$BEST_END" ]]; then
          BEST_END="$END_DATE"
          BEST_SLUG="$SLUG"
        fi
      fi
    fi
  done
done

if [ -z "$BEST_SLUG" ]; then
  echo "NO_ACTIVE_MARKET"
else
  # Get odds
  echo "SLUG|$BEST_SLUG|END|$BEST_END"
  curl -s --max-time 8 "https://gamma-api.polymarket.com/events?slug=$BEST_SLUG" | python3 -c "
import json,sys
for e in json.load(sys.stdin):
  for m in e.get('markets',[]):
    try:
      p=json.loads(m.get('outcomePrices','[]'))
      y=float(p[0])
      q=m.get('question','')[:55]
      vol=m.get('volumeNum',0)
      if y>0.01:
        print(f'OUTCOME|{q}|{y:.1%}|Vol:\${vol:,.0f}')
    except: pass
"
fi
