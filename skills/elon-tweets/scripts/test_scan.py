#!/usr/bin/env python3
"""Test Elon Market Scanner"""
import json, sys, os, urllib.request, urllib.error
from datetime import datetime, timezone

def fetch(slug):
    url = f"https://gamma-api.polymarket.com/events?slug={slug}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"Error fetching {slug}: {e}")
        return []

def main():
    # Clear proxy
    for k in ['http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY','all_proxy','ALL_PROXY']:
        os.environ.pop(k, None)

    now = datetime.now(timezone.utc)
    print(f"Current UTC time: {now}")
    
    # Test only recent slugs
    slugs = [
        "elon-musk-of-tweets-may-1-may-3",
        "elon-musk-of-tweets-may-2-may-4", 
        "elon-musk-of-tweets-may-3-may-5"
    ]
    
    events = []
    for slug in slugs:
        print(f"Testing slug: {slug}")
        results = fetch(slug)
        if results:
            ev = results[0]
            end_str = ev.get('endDate', '9999')
            print(f"Found event: {ev.get('title', 'N/A')} - {end_str}")
            events.append({
                'slug': slug,
                'title': ev.get('title', ''),
                'endDate': end_str,
                'hoursLeft': 24.0,  # placeholder
                'volume': ev.get('volume', 0),
                'liquidity': ev.get('liquidity', 0),
                'markets': ev.get('markets', [])
            })
        else:
            print(f"No results for {slug}")
    
    output = {
        'scanTime': now.isoformat(),
        'slugsChecked': len(slugs),
        'eventsFound': len(events),
        'events': events
    }
    
    print("\nFinal output:")
    print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()