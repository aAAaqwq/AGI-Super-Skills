#!/usr/bin/env python3
"""Settlement Farmer v2 - Refactored to use polymarket_trading_lib

Updated 2026-02-15: Now uses SimmerClientWithTimeout for SDK timeout protection.
"""
import sys
sys.path.insert(0, "/home/han/clawd")

import os, json, argparse, requests
from datetime import datetime, timezone
from polymarket_trading.lib.price_client import get_btc_price
from polymarket_trading.lib.unified_trade_executor import execute_trade
from polymarket_trading.lib.simmer_client_wrapper import SimmerClientWithTimeout

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
    # Use Simmer SDK with timeout protection
    try:
        client = SimmerClientWithTimeout(api_key=API_KEY, venue=venue)
        
        # Settlement Farmer: 60s timeout, fallback to API
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
    now = datetime.now(timezone.utc)
    
    # Data collection logging
    total_markets = len(markets)
    markets_scanned = 0
    markets_meeting_criteria = 0
    
    print(f"   📊 Scanning {total_markets} markets...")
    
    for m in markets:
        markets_scanned += 1
        
        # Get prices - SDK uses current_probability
        if hasattr(m, 'current_probability'):
            yes_p = float(m.current_probability) if m.current_probability else 0.5
        elif hasattr(m, 'outcomePrices'):
            prices = m.outcomePrices
            yes_p = float(prices[0]) if prices else 0.5
        else:
            prices = m.get('outcomePrices', [])
            yes_p = float(prices[0]) if prices else 0.5
        
        # Debug: show first few market prices
        if markets_scanned <= 5:
            market_q = m.question if hasattr(m, 'question') else m.get('question', 'Unknown')[:50]
            print(f"      {market_q}... | Price: {yes_p:.2%}")
        
        # Settlement farmer: buy >min_implied implied but priced <max_price
        if min_implied <= yes_p < max_price:
            markets_meeting_criteria += 1
            # Handle both Market objects and dicts
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
    
    # Summary logging
    print(f"   📈 Data Collection Summary:")
    print(f"      Total markets fetched: {total_markets}")
    print(f"      Markets scanned: {markets_scanned}")
    print(f"      Meeting criteria (>{min_implied:.0%}): {markets_meeting_criteria}")
    print(f"      Final opportunities: {len(opportunities)}")
    
    return opportunities

def run(venue='simmer'):
    # Load configuration from environment variables (unified architecture)
    limit = int(os.environ.get('SIMMER_SETTLEMENT_LIMIT', '100'))
    max_price = float(os.environ.get('SIMMER_SETTLEMENT_MAX_PRICE', '0.99'))
    min_implied = float(os.environ.get('SIMMER_SETTLEMENT_MIN_IMPLIED', '0.95'))
    bet_size = float(os.environ.get('SIMMER_SETTLEMENT_BET_SIZE', '10.0'))
    
    print(f"🌾 Settlement Farmer v2 - {venue}")
    print(f"   Config: limit={limit}, max_price={max_price:.0%}, min_implied={min_implied:.0%}, bet_size=${bet_size}")
    
    btc = get_btc_price()
    print(f"   BTC ref: ${btc:,.2f}")
    
    opps = find_settlement_opportunities(venue, limit=limit, max_price=max_price, min_implied=min_implied)
    print(f"   Found {len(opps)} opportunities")
    
    for o in opps:
        execute_trade({
            'market_id': o['market_id'],
            'market_question': o['question'],
            'side': o['side'],
            'amount_usd': bet_size,
            'price': o['price'],
            'reasoning': o['reasoning']
        }, 'settlement_farming', 'sdk:settlement', log_to_simmer_api=True)
    
    return opps

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--venue', default='simmer')
    args = parser.parse_args()
    load_api_key()
    run(venue=args.venue)
