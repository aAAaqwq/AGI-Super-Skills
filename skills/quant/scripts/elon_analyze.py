#!/usr/bin/env python3
"""Elon Tweet Market Analyzer v2.0 — Pure API, no browser needed."""
import json, re, sys, os
from datetime import datetime, timezone

def analyze(json_path):
    if not os.path.exists(json_path):
        print("ERROR: JSON file not found")
        return

    with open(json_path) as f:
        data = json.load(f)

    for e in data:
        end = datetime.fromisoformat(e['endDate'].replace('Z','+00:00'))
        start = datetime.fromisoformat(e['startDate'].replace('Z','+00:00'))
        now = datetime.now(timezone.utc)
        remain = (end - now).total_seconds() / 3600
        total = (end - start).total_seconds() / 3600
        days = total / 24

        print(f"Period: {start.strftime('%b%d')}→{end.strftime('%b%d %H:%M')}ET | {remain:.1f}h left | {days:.1f}d")

        intervals = []
        for m in e['markets']:
            q = m['question']
            try: p = json.loads(m['outcomePrices'])
            except: continue
            if not p or len(p)<2 or float(p[0])<0.01: continue
            match = re.search(r'post\s+(.+?)\s+tweets', q)
            if not match: continue
            nums = re.findall(r'\d+', match.group(1))
            if len(nums)>=2:
                lo,hi=int(nums[0]),int(nums[1])
                intervals.append((f"{lo}-{hi}",lo,hi,float(p[0]),m.get('volumeNum',0),m.get('liquidityNum',0)))
            elif len(nums)==1:
                lo=int(nums[0])
                intervals.append((f">{lo}",lo,lo+25,float(p[0]),m.get('volumeNum',0),m.get('liquidityNum',0)))

        for label,lo,hi,yes,vol,liq in sorted(intervals, key=lambda x:-x[3]):
            bar = '█' * int(yes*20)
            print(f"  {label:>10} {yes:>5.1%} {bar} V${vol:>7,.0f} L${liq:>7,.0f}")

        implied = sum(((lo+hi)/2)*yes for _,lo,hi,yes,_,_ in intervals)
        tp = sum(yes for _,_,_,yes,_,_ in intervals)
        print(f"\n🔮 Market implied: {implied:.0f} tweets (coverage {tp:.0%})")
        for rate in [15,20,25,30]:
            proj = rate*days
            hit = next((f"{a[0]}@{a[3]:.0%}" for a in intervals if a[1]<=proj<=a[2]), "—")
            print(f"  {rate}/d × {days:.1f}d = {proj:.0f} → {hit}")

        print(f"\n⚡ Edges:")
        found = False
        for label,lo,hi,yes,vol,liq in intervals:
            for rate in [20,25]:
                proj = rate*days
                if lo<=proj<=hi and yes<0.45:
                    print(f"  ⬆️ {label} @{yes:.0%} — {rate}/d projects {proj:.0f} in range, underpriced")
                    found = True
        if not found:
            print(f"  ❌ No edge")

        if remain > 12:
            print(f"\n🎯 SKIP: {remain:.0f}h remaining")
        elif remain > 6:
            print(f"\n🎯 WATCH: {remain:.0f}h remaining")
        else:
            print(f"\n🎯 TRADE WINDOW: {remain:.0f}h remaining")
            if found:
                print(f"   🟢 Has edge, trade allowed (≤4%, ≤$5, hold to settlement)")
            else:
                print(f"   🔴 No edge, do not trade")

if __name__ == '__main__':
    analyze(sys.argv[1] if len(sys.argv) > 1 else '/tmp/elon_v2test.json')
