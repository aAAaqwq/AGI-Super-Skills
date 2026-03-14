#!/usr/bin/env python3
"""Weather Trader v3 - Dynamic sizing + Optimal entry timing + Trade journal logging

Updates:
- v3: Dynamic position sizing based on forecast confidence
- v3: Optimal entry timing (24-48h before resolution)
- v3: Uses shared library
- v3: Logs to trade journal for performance tracking
"""
import sys
sys.path.insert(0, "/home/han/clawd")

import os
import json
import argparse
import requests
from datetime import datetime, timezone
from pathlib import Path

# Import shared libraries
try:
    from polymarket_trading.lib.price_client import get_btc_price
    from polymarket_trading.lib.unified_trade_executor import execute_trade
    from polymarket_trading.lib.simmer_client_wrapper import SimmerClientWithTimeout
    from polymarket_trading.lib.dynamic_sizing import calculate_weather_position_size
    from polymarket_trading.lib.optimal_entry import should_enter_weather_trader
    LIBS_AVAILABLE = True
except ImportError as e:
    print(f"   ⚠️  Library import error: {e}")
    LIBS_AVAILABLE = False

# Configuration
API_KEY = None
LOG_DIR = Path("/home/han/clawd/logs")
TRADE_JOURNAL = Path("/home/han/clawd/trade_journal.json")

def load_api_key():
    """Load API key from credentials file."""
    global API_KEY
    creds_file = os.path.expanduser("~/.config/simmer/credentials.json")
    if os.path.exists(creds_file):
        with open(creds_file) as f:
            API_KEY = json.load(f).get('api_key', '')
    return API_KEY

def log_activity(message):
    """Log activity with timestamp."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    print(f"   [{timestamp}] {message}")

def write_log_file(content):
    """Write detailed log file for this run."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"weather_{timestamp}.json"
    
    with open(log_file, 'w') as f:
        json.dump(content, f, indent=2, default=str)
    
    return log_file

def log_to_trade_journal(trade_data):
    """Log trade to centralized trade journal."""
    try:
        journal_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "strategy": "weather",
            "market_id": trade_data.get('market_id'),
            "market_question": trade_data.get('market_question'),
            "side": trade_data.get('side'),
            "amount_usd": trade_data.get('amount_usd'),
            "price": trade_data.get('price'),
            "confidence": trade_data.get('confidence'),
            "reasoning": trade_data.get('reasoning'),
            "sizing_method": trade_data.get('sizing_method', 'fixed'),
            "entry_timing": trade_data.get('entry_timing', 'standard'),
            "status": "paper"  # All trades are paper until explicitly set to live
        }
        
        # Append to journal
        if TRADE_JOURNAL.exists():
            with open(TRADE_JOURNAL, 'r') as f:
                journal = json.load(f)
        else:
            journal = {"trades": []}
        
        journal["trades"].append(journal_entry)
        
        with open(TRADE_JOURNAL, 'w') as f:
            json.dump(journal, f, indent=2)
        
        return True
    except Exception as e:
        log_activity(f"⚠️  Failed to log to trade journal: {e}")
        return False

def simmer_request(endpoint, params=None):
    """Make API request to Simmer."""
    url = f"https://api.simmer.markets{endpoint}"
    resp = requests.get(url, headers={'Authorization': f'Bearer {API_KEY}'}, params=params, timeout=30)
    return resp.json()

def fetch_weather_markets(venue='simmer'):
    """Fetch weather markets using Simmer SDK with timeout protection."""
    if not LIBS_AVAILABLE:
        # Fallback to direct API
        log_activity("Using direct API (SDK libraries not available)")
        try:
            data = simmer_request('/api/sdk/markets', {'venue': venue, 'limit': 100})
            markets = data.get('markets', []) if isinstance(data, dict) else data or []
            return [m for m in markets if 'weather' in m.get('question', '').lower() 
                    or 'temperature' in m.get('question', '').lower()]
        except Exception as e:
            log_activity(f"⚠️  API error: {e}")
            return []
    
    try:
        client = SimmerClientWithTimeout(api_key=API_KEY, venue=venue)
        all_markets = client.get_markets(
            timeout=45,
            limit=100,
            on_timeout="fallback_to_api",
            progress_callback=lambda msg: log_activity(msg)
        )
        
        result = []
        for m in all_markets:
            if hasattr(m, 'question'):
                q = m.question.lower()
                market_data = {
                    'id': m.id,
                    'question': m.question,
                    'current_probability': float(m.current_probability) if hasattr(m, 'current_probability') else 0.5,
                    'description': getattr(m, 'description', ''),
                    'end_date': getattr(m, 'end_date', None)
                }
            else:
                q = m.get('question', '').lower()
                market_data = m
            
            if 'weather' in q or 'temperature' in q:
                result.append(market_data)
        
        return result
    except Exception as e:
        log_activity(f"⚠️  SDK error: {e}, falling back to REST API")
        try:
            data = simmer_request('/api/sdk/markets', {'venue': venue})
            markets = data.get('markets', []) if isinstance(data, dict) else data or []
            return [m for m in markets if 'weather' in m.get('question', '').lower() 
                    or 'temperature' in m.get('question', '').lower()]
        except Exception as e2:
            log_activity(f"⚠️  Fallback API error: {e2}")
            return []

def get_dtr_hours(market):
    """Calculate Days To Resolution (DTR) in hours."""
    try:
        end_date_str = market.get('end_date') or market.get('resolution_date')
        if not end_date_str:
            return None
        
        # Parse end date
        if isinstance(end_date_str, str):
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        else:
            end_date = end_date_str
        
        now = datetime.now(timezone.utc)
        dtr = (end_date - now).total_seconds() / 3600  # hours
        return dtr
    except Exception as e:
        log_activity(f"⚠️  Could not calculate DTR: {e}")
        return None

def analyze_weather(market, use_optimal_timing=True, use_dynamic_sizing=True):
    """Analyze weather market and generate trading signal."""
    # Extract market data
    if isinstance(market, dict):
        yes_p = float(market.get('current_probability', 0.5))
        question = market.get('question', '')
        market_id = market.get('id', '')
    else:
        yes_p = float(getattr(market, 'current_probability', 0.5))
        question = getattr(market, 'question', '')
        market_id = getattr(market, 'id', '')
    
    # Calculate DTR for optimal timing
    dtr_hours = get_dtr_hours(market)
    
    # Optimal timing check: only trade if DTR is 24-48 hours
    if use_optimal_timing and dtr_hours is not None:
        if not (24 <= dtr_hours <= 48):
            return None  # Skip - not in optimal entry window
    
    # Weather logic: between 0.42-0.62 is uncertain
    if not (0.42 <= yes_p <= 0.62):
        return None  # Skip - not uncertain enough
    
    # Calculate confidence (distance from 0.5)
    confidence = abs(0.5 - yes_p) * 2  # 0.0 to 1.0
    
    # Dynamic sizing
    if use_dynamic_sizing and LIBS_AVAILABLE:
        try:
            size_result = calculate_weather_position_size(
                conviction=confidence,
                forecast_confidence=0.6,  # Weather forecasts ~60% reliable
                implied_edge=abs(0.5 - yes_p)
            )
            amount_usd = size_result['size_usd']
            sizing_method = size_result['method']
        except Exception as e:
            log_activity(f"⚠️  Dynamic sizing failed: {e}, using fixed")
            amount_usd = 5.0
            sizing_method = 'fixed'
    else:
        amount_usd = 5.0
        sizing_method = 'fixed'
    
    side = 'yes' if yes_p < 0.5 else 'no'
    
    return {
        'market_id': market_id,
        'market_question': question,
        'side': side,
        'price': yes_p,
        'confidence': confidence,
        'amount_usd': amount_usd,
        'sizing_method': sizing_method,
        'entry_timing': 'optimal' if use_optimal_timing else 'standard',
        'dtr_hours': dtr_hours,
        'reasoning': f"Weather uncertainty: {yes_p:.1%} | DTR: {dtr_hours:.1f}h | Size: ${amount_usd:.2f}"
    }

def run(venue='simmer', dynamic_sizing=True, use_optimal_timing=True, dry_run=True):
    """Main execution function."""
    print(f"🌤️ Weather Trader v3 - {venue}")
    print(f"   Dynamic sizing: {dynamic_sizing} | Optimal timing: {use_optimal_timing} | Dry run: {dry_run}")
    
    # Load API key
    load_api_key()
    if not API_KEY:
        log_activity("❌ No API key found")
        return []
    
    # Get BTC reference price
    if LIBS_AVAILABLE:
        try:
            btc = get_btc_price()
            log_activity(f"BTC ref: ${btc:,.2f}")
        except:
            log_activity("⚠️  Could not fetch BTC price")
    
    # Fetch weather markets
    log_activity("Fetching weather markets...")
    markets = fetch_weather_markets(venue)
    log_activity(f"Found {len(markets)} weather markets")
    
    # Analyze and generate signals
    signals = []
    trades_executed = []
    
    for market in markets:
        result = analyze_weather(market, use_optimal_timing, dynamic_sizing)
        if result:
            signals.append(result)
            log_activity(f"Signal: {result['market_question'][:50]}...")
            log_activity(f"   Side: {result['side'].upper()} | Amount: ${result['amount_usd']:.2f} | Method: {result['sizing_method']}")
            
            if not dry_run and LIBS_AVAILABLE:
                # Execute trade via unified executor
                try:
                    execute_trade({
                        'market_id': result['market_id'],
                        'market_question': result['market_question'],
                        'side': result['side'],
                        'amount_usd': result['amount_usd'],
                        'price': result['price'],
                        'reasoning': result['reasoning']
                    }, 'weather', 'sdk:weather', log_to_simmer_api=True)
                    trades_executed.append(result)
                except Exception as e:
                    log_activity(f"⚠️  Trade execution failed: {e}")
            
            # Always log to trade journal
            log_to_trade_journal(result)
    
    # Summary
    log_activity(f"Signals generated: {len(signals)}")
    log_activity(f"Trades executed: {len(trades_executed)}")
    
    # Write detailed log file
    log_content = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "3.0",
        "venue": venue,
        "config": {
            "dynamic_sizing": dynamic_sizing,
            "use_optimal_timing": use_optimal_timing,
            "dry_run": dry_run
        },
        "markets_found": len(markets),
        "signals": signals,
        "trades_executed": len(trades_executed),
        "total_amount_usd": sum(s['amount_usd'] for s in signals)
    }
    
    log_file = write_log_file(log_content)
    log_activity(f"Log saved: {log_file}")
    
    return signals

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Weather Trader v3')
    parser.add_argument('--venue', default='simmer', help='Trading venue')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Paper trading mode')
    parser.add_argument('--live', action='store_true', help='Live trading mode (requires explicit flag)')
    args = parser.parse_args()
    
    # Environment variable overrides
    dynamic = os.getenv('WEATHER_DYNAMIC_SIZING', '1') == '1'
    optimal = os.getenv('WEATHER_OPTIMAL_TIMING', '1') == '1'
    
    # Live mode only if explicitly requested
    dry_run = not args.live
    
    run(
        venue=args.venue,
        dynamic_sizing=dynamic,
        use_optimal_timing=optimal,
        dry_run=dry_run
    )
