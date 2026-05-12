#!/usr/bin/env python3
"""Elon Market Scanner — 发现活跃Elon推文盘，输出JSON供后续分析"""
import json, sys, os, urllib.request, urllib.error
from datetime import datetime, timezone

def fetch(slug):
    url = f"https://gamma-api.polymarket.com/events?slug={slug}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    except:
        return []

def main():
    # Clear proxy
    for k in ['http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY','all_proxy','ALL_PROXY']:
        os.environ.pop(k, None)

    now = datetime.now(timezone.utc)
    
    # Get ET date info
    import subprocess
    def et_cmd(fmt):
        env = dict(os.environ, LC_ALL='C', TZ='America/New_York')
        return subprocess.check_output(['date', f'+{fmt}'], env=env).decode().strip().lower()
    
    month = et_cmd('%B')        # "april" (full name, lowercase)
    day = int(et_cmd('%-d'))    # 21
    year = et_cmd('%Y')         # "2026"
    
    # Previous month
    env = dict(os.environ, LC_ALL='C', TZ='America/New_York')
    first_of_month = subprocess.check_output(['date', '+%Y-%m-01'], env=env).decode().strip()
    prev_env = dict(os.environ, LC_ALL='C')
    prev_month_raw = subprocess.check_output(
        ['date', '-d', f'{first_of_month} -1 day', '+%B'], env=prev_env
    ).decode().strip().lower()
    prev_days_raw = int(subprocess.check_output(
        ['date', '-d', f'{first_of_month} -1 day', '+%-d'], env=prev_env
    ).decode().strip())

    slugs = set()
    
    # Current month same-month - only add valid dates
    for s in range(max(1, day-4), day+6):
        for e_delta in [2, 7, 8]:
            e = s + e_delta
            if e <= 31:  # Only add if end date is valid
                slug = f"elon-musk-of-tweets-{month}-{s}-{month}-{e}"
                slugs.add(slug)
                print(f'Adding slug: {slug}')
    
    # Cross-month (early in month)
    if day <= 10:
        for s in range(max(1, prev_days_raw-5), prev_days_raw+1):
            for e in range(1, day+6):
                if e <= 31:  # Only add if end date is valid
                    slugs.add(f"elon-musk-of-tweets-{prev_month_raw}-{s}-{month}-{e}")
    
    # Month slug
    slugs.add(f"elon-musk-of-tweets-{month}-{year}")
    
    # Scan
    events = []
    for slug in sorted(slugs):
        results = fetch(slug)
        if not results:
            continue
        ev = results[0]
        end_str = ev.get('endDate', '9999')
        try:
            end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
            hours_left = (end_dt - now).total_seconds() / 3600
        except:
            hours_left = 9999
        
        if hours_left <= 0:
            continue  # already settled
        
        events.append({
            'slug': slug,
            'title': ev.get('title', ''),
            'endDate': end_str,
            'hoursLeft': round(hours_left, 1),
            'volume': ev.get('volume', 0),
            'liquidity': ev.get('liquidity', 0),
            'markets': ev.get('markets', [])
        })
    
    # Sort by hoursLeft ascending (nearest settlement first)
    events.sort(key=lambda x: x['hoursLeft'])
    
    output = {
        'scanTime': now.isoformat(),
        'etDate': f"{month} {day}",
        'slugsChecked': len(slugs),
        'eventsFound': len(events),
        'events': events
    }
    
    print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
