#!/usr/bin/env python3
"""Settlement Farmer v3.1 - Refactored to use shared dynamic sizing library

Updates:
- v3.1: Now uses polymarket_trading.lib.dynamic_sizing (shared library)
- v3.1: Updated max cap to $50 (new Simmer Pro Plan limit)
- v3.1: Backward-compatible environment variable configuration
- v3: Dynamic position sizing based on implied probability
- v3: Live execution mode (dry-run by default)
- v3: Kelly criterion-inspired sizing (higher certainty = larger position)
"""
import sys
sys.path.insert(0, "/home/han/clawd")

import os, json, argparse, requests
from datetime import datetime, timezone
from polymarket_trading.lib.price_client import get_btc_price
from polymarket_trading.lib.unified_trade_executor import execute_trade
from polymarket_trading.lib.simmer_client_wrapper import SimmerClientWithTimeout
from polymarket_trading.lib.dynamic_sizing import calculate_settlement_position_size

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

def find_settlement_opportunities(venue='simmer', limit=100, max_price=0.99, min_implied=0.95):
    """Find markets about to resolve where price < max_price but implied prob > min_implied."""
    try:
        client = SimmerClientWithTimeout(api_key=API_KEY, venue=venue)
        markets = client.get_markets(
            timeout=60,
            limit=limit,
            on_timeout="fallback_to_api"
        )
    except Exception as e:
        print(f"   ⚠️ SDK error: {e}, falling back to REST API")
        data = simmer_request('/api/sdk/markets', {'venue': venue, 'limit': limit})
        markets = data.get('markets', []) if isinstance(data, dict) else data or []
    
    opportunities = []
    total_markets = len(markets)
    markets_scanned = 0
    markets_meeting_criteria = 0
    
    print(f"   📊 Scanning {total_markets} markets...")
    
    for m in markets:
        markets_scanned += 1
        
        if hasattr(m, 'current_probability'):
            yes_p = float(m.current_probability) if m.current_probability else 0.5
        elif hasattr(m, 'outcomePrices'):
            prices = m.outcomePrices
            yes_p = float(prices[0]) if prices else 0.5
        else:
            prices = m.get('outcomePrices', [])
            yes_p = float(prices[0]) if prices else 0.5
        
        if markets_scanned <= 5:
            market_q = m.question if hasattr(m, 'question') else m.get('question', 'Unknown')[:50]
            print(f"      {market_q}... | Price: {yes_p:.2%}")
        
        if min_implied <= yes_p < max_price:
            markets_meeting_criteria += 1
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
                'price': yes_p,
                'implied_prob': yes_p,
                'reasoning': f"Settlement farming: {yes_p:.0%} vs {min_implied:.0%}+ implied"
            })
    
    print(f"   📈 Data Collection Summary:")
    print(f"      Total markets fetched: {total_markets}")
    print(f"      Markets scanned: {markets_scanned}")
    print(f"      Meeting criteria (>{min_implied:.0%}): {markets_meeting_criteria}")
    print(f"      Final opportunities: {len(opportunities)}")
    
    return opportunities

def run(venue='simmer', dry_run=True):
    # Load configuration
    limit = int(os.environ.get('SIMMER_SETTLEMENT_LIMIT', '20'))
    max_price = float(os.environ.get('SIMMER_SETTLEMENT_MAX_PRICE', '0.99'))
    min_implied = float(os.environ.get('SIMMER_SETTLEMENT_MIN_IMPLIED', '0.95'))
    # Note: max_bet/min_bet now handled by shared library ($5-$50)
    
    mode = "DRY RUN (observation)" if dry_run else "LIVE EXECUTION"
    print(f"🌾 Settlement Farmer v3.1 - {venue} | {mode}")
    print(f"   Config: limit={limit}, max_price={max_price:.0%}, min_implied={min_implied:.0%}")
    print(f"   Sizing: Dynamic $5-$50 based on certainty (shared library)")
    
    btc = get_btc_price()
    print(f"   BTC ref: ${btc:,.2f}")
    
    opps = find_settlement_opportunities(venue, limit=limit, max_price=max_price, min_implied=min_implied)
    print(f"   Found {len(opps)} opportunities")
    
    if not opps:
        print("   No opportunities to execute.")
        return opps
    
    for o in opps:
        # Calculate dynamic position size using shared library
        position_size = calculate_settlement_position_size(o['implied_prob'], min_implied)
        expected_profit = (1.0 - o['price']) * position_size  # Buy at price, redeem at $1
        profit_pct = (1.0 - o['price']) / o['price'] * 100
        
        print(f"\n   📊 Opportunity: {o['question'][:60]}...")
        print(f"      Price: {o['price']:.2%} | Implied: {o['implied_prob']:.2%}")
        print(f"      Position: ${position_size:.2f} | Expected profit: ${expected_profit:.2f} ({profit_pct:.1f}%)")
        
        if dry_run:
            print(f"      📝 DRY RUN - Would execute trade (no funds moved)")
            # Log to paper trades only
            execute_trade({
                'market_id': o['market_id'],
                'market_question': o['question'],
                'side': o['side'],
                'amount_usd': position_size,
                'price': o['price'],
                'reasoning': o['reasoning'] + f" [DRY RUN - Size: ${position_size}]"
            }, 'settlement_farming', 'sdk:settlement', log_to_simmer_api=False)
        else:
            print(f"      🚀 LIVE EXECUTION - Submitting order...")
            result = execute_trade({
                'market_id': o['market_id'],
                'market_question': o['question'],
                'side': o['side'],
                'amount_usd': position_size,
                'price': o['price'],
                'reasoning': o['reasoning'] + f" [LIVE - Size: ${position_size}]"
            }, 'settlement_farming', 'sdk:settlement', log_to_simmer_api=True)
            
            if result:
                if result.success:
                    print(f"      ✅ Order submitted: {result.trade_id or 'N/A'}")
                else:
                    print(f"      ❌ Order failed: {result.error or 'Unknown error'}")
            else:
                print(f"      ❌ Order failed - check logs")
    
    return opps

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--venue', default='simmer')
    parser.add_argument('--live', action='store_true', help='Enable live execution (default: dry-run)')
    args = parser.parse_args()
    load_api_key()
    run(venue=args.venue, dry_run=not args.live)
