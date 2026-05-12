#!/usr/bin/env python3
import json
from datetime import datetime, timezone

# Parse the JSON data from the latest scan result
with open('/home/aa/.openclaw/workspace-cqo/skills/elon-tweets/el_scan_result.json', 'r') as f:
    data = json.load(f)

markets = data.get('events', [])
if not markets:
    print('No events found')
    exit()

# Current time is 2026-05-01 18:00 UTC
current_time = datetime(2026, 5, 1, 18, 0, tzinfo=timezone.utc)

print(f'Current time: {current_time.strftime("%Y-%m-%d %H:%M:%S %Z")}')
print()
print('Elon Musk Tweet Markets Analysis:')
print('=' * 80)

active_markets = []
for event in markets:
    event_slug = event.get('slug', '')
    event_end_date = event.get('endDate', '')
    event_hours_left = float(event.get('hoursLeft', 0))
    
    print(f'📊 Event: {event_slug}')
    print(f'   End: {event_end_date}')
    print(f'   Hours left: {event_hours_left:.1f}')
    print(f'   Volume: ${float(event.get("volume", 0)):,.0f}')
    print()
    
    # Check individual markets within this event
    for market in event.get('markets', []):
        market_info = {
            'slug': market.get('slug', ''),
            'question': market.get('question', ''),
            'end_date': event_end_date,
            'hours_left': event_hours_left,
            'last_trade_price': float(market.get('lastTradePrice', 0)),
            'volume': float(market.get('volume', 0)),
            'active': market.get('active', False),
            'closed': market.get('closed', False),
            'best_ask': float(market.get('bestAsk', 0)),
            'best_bid': float(market.get('bestBid', 0))
        }
        active_markets.append(market_info)

# Sort by hours left (closest to expiration first)
active_markets.sort(key=lambda x: x['hours_left'])

print('Individual Markets:')
print('-' * 60)

for i, market in enumerate(active_markets[:15]):  # Show top 15
    status = 'CLOSED' if market['closed'] else 'ACTIVE'
    spread = market['best_ask'] - market['best_bid'] if market['best_ask'] and market['best_bid'] else 0
    emoji = '🔥' if not market['closed'] and market['hours_left'] < 24 else '⏰' if not market['closed'] else '❌'
    
    print(f'{emoji} {i+1:2d}. {market["slug"]}')
    print(f'    Q: {market["question"][:60]}...')
    print(f'    Status: {status} | Spread: ${spread:.3f}')
    print(f'    Time: {market["hours_left"]:+.1f}h | Price: ${market["last_trade_price"]}')
    print(f'    Vol: ${market["volume"]:,.0f}')
    print()

# Find the best candidate for analysis
candidate = None
for market in active_markets:
    if not market['closed'] and market['hours_left'] > 0:
        candidate = market
        break

if candidate:
    print(f'🎯 SELECTED MARKET for analysis:')
    print(f'Slug: {candidate["slug"]}')
    print(f'Question: {candidate["question"]}')
    print(f'Hours left: {candidate["hours_left"]:.1f}')
    
    # Determine analysis depth
    if candidate['hours_left'] > 12:
        depth = 'Lightweight (record only)'
        proceed = False
    elif candidate['hours_left'] > 6:
        depth = 'Moderate (odds analysis)'
        proceed = True
    else:
        depth = 'Deep (full analysis with tweet counting)'
        proceed = True
    
    print(f'Analysis depth: {depth}')
    print(f'Proceed with analysis: {proceed}')
    
    if proceed:
        print()
        print('✅ PROCEEDING WITH ODDS ANALYSIS')
        # Save candidate for next step
        with open('/home/aa/.openclaw/workspace-cqo/skills/elon-tweets/best_market.json', 'w') as f:
            json.dump(candidate, f, indent=2)
        print('Candidate market saved for odds analysis')
    else:
        print()
        print('❌ SKIPPING DEEP ANALYSIS - too far from expiration')
else:
    print('❌ No suitable active markets found')