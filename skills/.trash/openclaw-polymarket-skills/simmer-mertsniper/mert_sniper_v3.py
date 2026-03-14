import sys
sys.path.insert(0, "/home/han/clawd/polymarket-trading")
#!/usr/bin/env python3
"""Mert Sniper v3 - Dynamic position sizing with shared library

Updates:
- v3: Dynamic position sizing based on conviction + time urgency + implied edge
- v3: Uses polymarket_trading.lib.dynamic_sizing (shared library)
- v3: Opt-in via MERT_DYNAMIC_SIZING=1 environment variable
- v3: $5-$50 range (updated Simmer Pro Plan limit)
- v2: Refactored to use polymarket_trading_lib with timeout protection
"""

import os, json, argparse, requests
from datetime import datetime, timezone
from polymarket_trading.lib.price_client import get_btc_price
from polymarket_trading.lib.unified_trade_executor import execute_trade
from polymarket_trading.lib.simmer_client_wrapper import SimmerClientWithTimeout
from polymarket_trading.lib.dynamic_sizing import calculate_mert_position_size

API_KEY = None
def load_api_key():
    global API_KEY
    creds_file = os.path.expanduser("~/.config/simmer/credentials.json")
    if os.path.exists(creds_file):
        with open(creds_file) as f:
            API_KEY = json.load(f).get('api_key', '')
    return API_KEY

def simmer_request(endpoint, params=None):
    url = f"https://api.simmer.markets{endpoint}"
    resp = requests.get(url, headers={'Authorization': f'Bearer {API_KEY}'}, params=params, timeout=30)
    return resp.json()

def fetch_markets(venue='simmer'):
    """Fetch markets using Simmer SDK with timeout protection."""
    try:
        client = SimmerClientWithTimeout(api_key=API_KEY, venue=venue)
        return client.get_markets(
            timeout=30,
            limit=100,
            on_timeout="fallback_to_api"
        )
    except Exception as e:
        print(f"   ⚠️ SDK error: {e}, falling back to REST API")
        data = simmer_request('/api/sdk/markets', {'venue': venue})
        return data.get('markets', []) if isinstance(data, dict) else data or []

def calculate_odds_deviation(confidence, side):
    """
    Estimate odds deviation from fair value.
    
    For a binary market, fair value = 50%.
    If confidence is 70% on Yes side, deviation = 20% (70% - 50%).
    This serves as a proxy for edge in the absence of a reference model.
    """
    fair_value = 0.50
    if side == 'yes':
        return confidence - fair_value
    else:
        return confidence - fair_value  # Same calculation for NO (just inverted)

def find_mert_opportunities(markets, max_mins=240, min_confidence=0.55):
    """Find near-expiry high-confidence markets."""
    now = datetime.now(timezone.utc)
    opportunities = []
    
    for m in markets:
        # Get end time
        if hasattr(m, 'resolves_at'):
            end = m.resolves_at
        elif hasattr(m, 'endDate'):
            end = m.endDate
        else:
            end = m.get('endDate') if isinstance(m, dict) else None
        
        if not end:
            continue
        try:
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
        except:
            continue
        
        mins_left = (end_dt - now).total_seconds() / 60
        if mins_left <= 0 or mins_left > max_mins:
            continue
        
        # Get prices
        if hasattr(m, 'current_probability'):
            p1 = float(m.current_probability) if m.current_probability else 0.5
            p2_raw = getattr(m, 'external_price_yes', None)
            p2 = float(p2_raw) if p2_raw is not None else (1.0 - p1)
        elif hasattr(m, 'outcomePrices'):
            prices = m.outcomePrices
            p1 = float(prices[0]) if prices else 0.5
            p2 = float(prices[1]) if len(prices) > 1 else 0.5
        else:
            prices = m.get('outcomePrices', [])
            p1 = float(prices[0]) if prices else 0.5
            p2 = float(prices[1]) if len(prices) > 1 else 0.5
        
        # High confidence: one side > min_confidence
        if p1 > min_confidence:
            if hasattr(m, 'id'):
                market_id = m.id
                question = m.question
            else:
                market_id = m.get('id')
                question = m.get('question')
            
            opportunities.append({
                'market_id': market_id,
                'question': question,
                'side': 'yes',
                'price': p1,
                'confidence': p1,
                'mins_left': mins_left
            })
        elif p2 > min_confidence:
            if hasattr(m, 'id'):
                market_id = m.id
                question = m.question
            else:
                market_id = m.get('id')
                question = m.get('question')
            
            opportunities.append({
                'market_id': market_id,
                'question': question,
                'side': 'no',
                'price': p2,
                'confidence': p2,
                'mins_left': mins_left
            })
    
    return opportunities

def run(venue='simmer', max_mins=240, min_confidence=0.55, max_bet=5.0, dynamic_sizing=False):
    """Run Mert Sniper strategy with optional dynamic sizing."""
    mode = "DYNAMIC SIZING" if dynamic_sizing else "FIXED SIZING"
    print(f"🎯 Mert Sniper v3 - {venue} | {mode}")
    print(f"   Config: max_mins={max_mins}, min_confidence={min_confidence:.0%}")
    if dynamic_sizing:
        print(f"   Sizing: Dynamic $5-$50 based on conviction + time (shared library)")
    else:
        print(f"   Sizing: Fixed ${max_bet}")
    
    btc = get_btc_price()
    print(f"   BTC ref: ${btc:,.2f}")
    
    markets = fetch_markets(venue)
    print(f"   Scanned {len(markets)} markets")
    
    opportunities = find_mert_opportunities(markets, max_mins, min_confidence)
    print(f"   Opportunities: {len(opportunities)}")
    
    for opp in opportunities:
        if dynamic_sizing:
            # Calculate odds deviation from fair value
            odds_deviation = calculate_odds_deviation(opp['confidence'], opp['side'])
            
            # Calculate dynamic position size
            position_size = calculate_mert_position_size(
                odds_deviation=odds_deviation,
                time_to_expiry=opp['mins_left'],
                conviction=opp['confidence'],
                market_price=opp['price']
            )
            
            print(f"\n   📊 {opp['question'][:50]}...")
            print(f"      Side: {opp['side'].upper()} | Price: {opp['price']:.2%}")
            print(f"      Confidence: {opp['confidence']:.0%} | Time: {opp['mins_left']:.0f}m")
            print(f"      Deviation: {odds_deviation:.1%} | Position: ${position_size:.2f}")
        else:
            # Fixed sizing (legacy behavior)
            position_size = max_bet
            print(f"   📊 {opp['question'][:50]}... | Fixed: ${position_size:.2f}")
        
        # Execute trade
        result = execute_trade({
            'market_id': opp['market_id'],
            'market_question': opp['question'],
            'side': opp['side'],
            'amount_usd': position_size,
            'price': opp['price'],
            'reasoning': f"Mert v3: {opp['confidence']:.0%} conf, {opp['mins_left']:.0f}m left, ${position_size:.2f}"
        }, 'mert_sniper', 'sdk:mert-sniper', log_to_simmer_api=True)
        
        if result:
            print(f"      ✅ Logged trade")
        else:
            print(f"      ⚠️  Trade logging issue")
    
    return opportunities

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--venue', default='simmer')
    parser.add_argument('--max-mins', type=int, default=240)
    parser.add_argument('--min-confidence', type=float, default=0.55)
    parser.add_argument('--max-bet', type=float, default=5.0)
    parser.add_argument('--dynamic', action='store_true', help='Enable dynamic sizing')
    args = parser.parse_args()
    load_api_key()
    
    # Check environment variable for dynamic sizing (opt-in)
    dynamic_sizing = os.getenv('MERT_DYNAMIC_SIZING', '0') == '1' or args.dynamic
    
    run(
        venue=args.venue, 
        max_mins=args.max_mins, 
        min_confidence=args.min_confidence, 
        max_bet=args.max_bet,
        dynamic_sizing=dynamic_sizing
    )
