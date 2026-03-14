#!/usr/bin/env python3
"""Mert Sniper v2 - Refactored to use polymarket_trading_lib

Updated 2026-02-15: Now uses SimmerClientWithTimeout for SDK timeout protection.
"""
import sys
sys.path.insert(0, "/home/han/clawd")

import os, json, argparse, requests
from datetime import datetime, timezone
from polymarket_trading.lib.price_client import get_btc_price, get_btc_klines
from polymarket_trading.lib.technical_analysis import get_ta_signals
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

def fetch_markets(venue='simmer'):
    """Fetch markets using Simmer SDK with timeout protection."""
    try:
        # Use wrapped client with timeout protection
        client = SimmerClientWithTimeout(api_key=API_KEY, venue=venue)
        
        # Mert Sniper: 30s timeout (frequent runs, aggressive)
        return client.get_markets(
            timeout=30,
            limit=100,
            on_timeout="fallback_to_api"
        )
    except Exception as e:
        print(f"   ⚠️ SDK error: {e}, falling back to REST API")
        data = simmer_request('/api/sdk/markets', {'venue': venue})
        return data.get('markets', []) if isinstance(data, dict) else data or []

def find_mert_opportunities(markets, max_mins=240, min_confidence=0.55):
    """Find near-expiry high-confidence markets - handles both Market objects and dicts."""
    now = datetime.now(timezone.utc)
    opportunities = []
    
    for m in markets:
        # Handle both Market objects and dicts
        # SDK uses resolves_at, API uses endDate
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
        
        # Get prices - SDK uses current_probability + external_price_yes
        if hasattr(m, 'current_probability'):
            # SDK Market object
            p1 = float(m.current_probability)
            p2 = float(m.external_price_yes) if hasattr(m, 'external_price_yes') else (1.0 - p1)
        elif hasattr(m, 'outcomePrices'):
            prices = m.outcomePrices
            p1 = float(prices[0]) if prices else 0.5
            p2 = float(prices[1]) if len(prices) > 1 else 0.5
        else:
            prices = m.get('outcomePrices', [])
            p1 = float(prices[0]) if prices else 0.5
            p2 = float(prices[1]) if len(prices) > 1 else 0.5
        
        # High confidence: one side > min_confidence (default 55%)
        if p1 > min_confidence:
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
                'price': p1,
                'confidence': p1,
                'mins_left': mins_left
            })
        elif p2 > min_confidence:
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
                'side': 'no',
                'price': p2,
                'confidence': p2,
                'mins_left': mins_left
            })
    
    return opportunities

def run(venue='simmer', max_mins=240, min_confidence=0.55, max_bet=5.0):
    """Run Mert Sniper strategy."""
    print(f"🎯 Mert Sniper v2 - {venue}")
    print(f"   Config: max_mins={max_mins}, min_confidence={min_confidence:.0%}, max_bet=${max_bet}")
    
    btc = get_btc_price()
    print(f"   BTC ref: ${btc:,.2f}")
    
    markets = fetch_markets(venue)
    print(f"   Scanned {len(markets)} markets")
    
    opportunities = find_mert_opportunities(markets, max_mins, min_confidence)
    print(f"   Opportunities: {len(opportunities)}")
    
    for opp in opportunities:
        execute_trade({
            'market_id': opp['market_id'],
            'market_question': opp['question'],
            'side': opp['side'],
            'amount_usd': max_bet,
            'price': opp['price'],
            'reasoning': f"Mert: {opp['confidence']:.0%} confidence, {opp['mins_left']:.0f}m left"
        }, 'mert_sniper', 'sdk:mert-sniper', log_to_simmer_api=True)
    
    return opportunities

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--venue', default='simmer')
    parser.add_argument('--max-mins', type=int, default=240)
    parser.add_argument('--min-confidence', type=float, default=0.55)
    parser.add_argument('--max-bet', type=float, default=5.0)
    args = parser.parse_args()
    load_api_key()
    run(venue=args.venue, max_mins=args.max_mins, min_confidence=args.min_confidence, max_bet=args.max_bet)
