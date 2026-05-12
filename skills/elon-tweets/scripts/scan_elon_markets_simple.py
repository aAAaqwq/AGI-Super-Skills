#!/usr/bin/env python3
"""Elon Market Scanner — 简化版，处理错误和超时"""
import json, sys, os, urllib.request, urllib.error, time
from datetime import datetime, timezone

def fetch(slug):
    url = f"https://gamma-api.polymarket.com/events?slug={slug}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"Error fetching {slug}: {e}", file=sys.stderr)
        return []

def main():
    # Clear proxy
    for k in ['http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY','all_proxy','ALL_PROXY']:
        os.environ.pop(k, None)

    now = datetime.now(timezone.utc)
    print(f"Scan start: {now.isoformat()}", file=sys.stderr)
    
    # Get ET date info
    import subprocess
    def et_cmd(fmt):
        env = dict(os.environ, LC_ALL='C', TZ='America/New_York')
        try:
            return subprocess.check_output(['date', f'+{fmt}'], env=env, timeout=5).decode().strip().lower()
        except subprocess.TimeoutExpired:
            return "april"
        except Exception as e:
            print(f"Date command error: {e}", file=sys.stderr)
            return "april"
    
    month = et_cmd('%B')        # "april" (full name, lowercase)
    day = 24 # Hardcode to avoid date command issues
    year = "2026"
    
    print(f"ET Date: {month} {day} {year}", file=sys.stderr)
    
    # Test slugs (simplified for testing)
    test_slugs = [
        f"elon-musk-of-tweets-{month}-{day}-{month}-{day+2}",
        f"elon-musk-of-tweets-{month}-{day}-{month}-{day+7}",
        f"elon-musk-of-tweets-april-{day}-{month}-{day+8}",
    ]
    
    events = []
    for slug in test_slugs:
        print(f"Testing slug: {slug}", file=sys.stderr)
        results = fetch(slug)
        if results:
            ev = results[0]
            end_str = ev.get('endDate', '9999')
            try:
                end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                hours_left = (end_dt - now).total_seconds() / 3600
            except:
                hours_left = 9999
            
            if hours_left <= 0:
                print(f"Skipping settled event: {slug}", file=sys.stderr)
                continue
            
            events.append({
                'slug': slug,
                'title': ev.get('title', ''),
                'endDate': end_str,
                'hoursLeft': round(hours_left, 1),
                'volume': ev.get('volume', 0),
                'liquidity': ev.get('liquidity', 0),
                'markets': ev.get('markets', [])
            })
            print(f"Found event: {slug} with {hours_left}h left", file=sys.stderr)
        time.sleep(1)  # Be nice to API
    
    # Sort by hoursLeft ascending (nearest settlement first)
    events.sort(key=lambda x: x['hoursLeft'])
    
    output = {
        'scanTime': now.isoformat(),
        'etDate': f"{month} {day}",
        'slugsChecked': len(test_slugs),
        'eventsFound': len(events),
        'events': events
    }
    
    print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()