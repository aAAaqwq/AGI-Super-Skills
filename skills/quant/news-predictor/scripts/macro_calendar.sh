#!/bin/bash
# macro_calendar.sh — Check upcoming high-impact macro events
# Output: JSON array of upcoming events with risk levels

set -euo pipefail
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

python3 << 'PYEOF'
import json
from datetime import datetime, timezone, timedelta

BJ = timezone(timedelta(hours=8))
now = datetime.now(BJ)

def bj(h,m=0):
    return datetime(2026,h,m, tzinfo=BJ)

# Hardcoded 2026 Fed schedule (8 meetings)
fed_meetings = [
    (bj(1,28), bj(1,29)),
    (bj(3,18), bj(3,19)),
    (bj(5,6), bj(5,7)),
    (bj(6,17), bj(6,18)),
    (bj(7,29), bj(7,30)),
    (bj(9,16), bj(9,17)),
    (bj(10,28), bj(10,29)),
    (bj(12,9), bj(12,10)),
]

events = []

# Check Fed meetings
for start, end in fed_meetings:
    hours_until = (start - now).total_seconds() / 3600
    if -24 <= hours_until <= 72:  # Show 72h before to 24h after
        if hours_until < 0:
            risk = "ACTIVE"
            status = "happening now"
        elif hours_until <= 4:
            risk = "DANGER"
            status = "less than 4h away"
        elif hours_until <= 24:
            risk = "CAUTION"
            status = "today"
        else:
            risk = "CAUTION"
            status = f"in {int(hours_until)}h"
        events.append({
            "event": "FOMC Rate Decision",
            "datetime": start.strftime("%Y-%m-%d %H:%M"),
            "risk": risk,
            "hours_until": round(hours_until, 1),
            "status": status,
            "impact": "BTC ±3-5%, ETH ±3-5%, SOL ±3-5%",
            "action": "No new crypto buys within 4h. Reduce positions if DANGER."
        })

# Monthly recurring events (approximate — check actual dates)
monthly_events = [
    ("CPI Release", 13, 15, "08:30 ET", "BTC ±1-3%"),
    ("PPI Release", 13, 15, "08:30 ET", "BTC ±1-3%"),
    ("NFP Jobs Report", 1, 7, "08:30 ET", "BTC ±1-3%"),
]

month = now.month
year = now.year
for name, day_start, day_end, time_str, impact_str in monthly_events:
    if name == "NFP":
        # First Friday
        d = datetime(year, month, 1, tzinfo=BJ)
        while d.weekday() != 4:
            d += timedelta(days=1)
        target = d.replace(hour=20, minute=30)  # 08:30 ET = 20:30 BJ
    else:
        # Approximate mid-month
        target = datetime(year, month, 14, hour=20, minute=30, tzinfo=BJ)
    
    hours_until = (target - now).total_seconds() / 3600
    if -6 <= hours_until <= 72:
        if hours_until < 0:
            risk = "ACTIVE"
            status = "released"
        elif hours_until <= 2:
            risk = "CAUTION"
            status = "in 2h"
        elif hours_until <= 24:
            risk = "CAUTION"
            status = "today"
        else:
            risk = "LOW"
            status = f"in {int(hours_until)}h"
        events.append({
            "event": name,
            "datetime": target.strftime("%Y-%m-%d %H:%M"),
            "risk": risk,
            "hours_until": round(hours_until, 1),
            "status": status,
            "impact": impact_str,
            "action": "CAUTION 2h before. No new buys during release."
        })

# Also try to fetch ForexFactory calendar
try:
    import urllib.request
    req = urllib.request.Request(
        "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        ff_data = json.loads(resp.read())
    
    impact_map = {"High": "CAUTION", "Medium": "LOW", "Low": "IGNORE"}
    for item in ff_data:
        if item.get("impact") not in ["High"]:
            continue
        title = item.get("title", "")
        # Skip duplicates of our hardcoded events
        if any(k in title for k in ["CPI", "PPI", "Non-Farm", "FOMC", "Interest Rate"]):
            continue
        dt_str = item.get("date", "")
        if not dt_str:
            continue
        try:
            evt_dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S%z").astimezone(BJ)
        except:
            continue
        
        hours_until = (evt_dt - now).total_seconds() / 3600
        if -2 <= hours_until <= 48:
            events.append({
                "event": title,
                "datetime": evt_dt.strftime("%Y-%m-%d %H:%M"),
                "risk": "CAUTION" if hours_until <= 4 else "LOW",
                "hours_until": round(hours_until, 1),
                "status": "released" if hours_until < 0 else f"in {int(hours_until)}h",
                "impact": "Potential market volatility",
                "action": "Monitor, no new buys within 2h of high-impact events."
            })
except Exception as e:
    pass  # ForexFactory unavailable, rely on hardcoded

# Sort by hours_until
events.sort(key=lambda x: x["hours_until"])

print(json.dumps(events, indent=2))
PYEOF
