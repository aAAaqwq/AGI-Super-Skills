#!/usr/bin/env python3
"""Weather Trader v2 - Refactored to use polymarket_trading_lib

Updated 2026-02-15: Now uses SimmerClientWithTimeout for SDK timeout protection.
"""
import sys
sys.path.insert(0, "/home/han/clawd")

import os, json, argparse, requests
from datetime import datetime
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

def fetch_weather_markets(venue='simmer'):
    """Fetch weather markets using Simmer SDK with timeout protection."""
    try:
        # Use wrapped client with timeout protection
        client = SimmerClientWithTimeout(api_key=API_KEY, venue=venue)
        
        # Weather markets: 45s timeout, fallback to API on timeout
        all_markets = client.get_markets(
            timeout=45,
            limit=100,
            on_timeout="fallback_to_api",
            progress_callback=lambda msg: print(f"   {msg}")
        )
        
        # Filter for weather markets - handle both Market objects and dicts
        result = []
        for m in all_markets:
            if hasattr(m, 'question'):
                q = m.question.lower()
            else:
                q = m.get('question', '').lower()
            if 'weather' in q or 'temperature' in q:
                result.append(m)
        return result
    except Exception as e:
        print(f"   ⚠️ SDK error: {e}, falling back to REST API")
        data = simmer_request('/api/sdk/markets', {'venue': venue})
        markets = data.get('markets', []) if isinstance(data, dict) else data or []
        return [m for m in markets if 'weather' in m.get('question', '').lower() or 'temperature' in m.get('question', '').lower()]

def analyze_weather(market):
    """Simple weather market analysis - handles both Market objects and dicts."""
    # Handle both Market objects and dicts
    if hasattr(market, 'current_probability'):
        # SDK Market object
        yes_p = float(market.current_probability)
        question = market.question
        market_id = market.id
    elif hasattr(market, 'outcomePrices'):
        prices = market.outcomePrices
        yes_p = float(prices[0]) if prices else 0.5
        question = getattr(market, 'question', '')
        market_id = getattr(market, 'id', '')
    else:
        prices = market.get('outcomePrices', [])
        yes_p = float(prices[0]) if prices else 0.5
        question = market.get('question', '')
        market_id = market.get('id', '')
    
    # Weather logic: between 0.42-0.62 is uncertain
    if 0.42 <= yes_p <= 0.62:
        return {
            'market_id': market_id,
            'question': question,
            'side': 'yes' if yes_p < 0.5 else 'no',
            'price': yes_p,
            'confidence': 0.5,
            'reasoning': f"Weather uncertainty: {yes_p:.0%}"
        }
    return None

def run(venue='simmer'):
    print(f"🌤️ Weather Trader v2 - {venue}")
    btc = get_btc_price()
    print(f"   BTC ref: ${btc:,.2f}")
    
    markets = fetch_weather_markets(venue)
    print(f"   Found {len(markets)} weather markets")
    
    signals = []
    for m in markets:
        result = analyze_weather(m)
        if result:
            signals.append(result)
            # Use unified executor - logs to both paper_trades.json AND Simmer (venue=simmer)
            execute_trade({
                'market_id': result['market_id'],
                'market_question': result['question'],
                'side': result['side'],
                'amount_usd': 5.0,
                'price': result['price'],
                'reasoning': result['reasoning']
            }, 'weather', 'sdk:weather', log_to_simmer_api=True)
    
    print(f"   Signals: {len(signals)}")
    return signals

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--venue', default='simmer')
    args = parser.parse_args()
    load_api_key()
    run(venue=args.venue)
