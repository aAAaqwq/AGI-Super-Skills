#!/usr/bin/env python3
"""Signal Sniper v2.1 - Signal detection and logging (no fake trades)

Monitors RSS feeds for trading signals and logs them for potential action.
Signal logging is separate from trade logging - this strategy only identifies
opportunities, it does NOT execute trades unless explicitly configured.
"""
import sys
sys.path.insert(0, "/home/han/clawd")

import os, json, argparse, requests, re
from datetime import datetime
from pathlib import Path
from polymarket_trading.lib.price_client import get_btc_price

API_KEY = None
KEYWORDS = ['bitcoin', 'btc', 'eth', 'crypto', 'trump', 'musk', 'fed', 'rate']
FEEDS = []

# Signal log file (separate from paper_trades.json)
SIGNALS_FILE = Path("/home/han/clawd/skills/simmer-signalsniper/state/signals.json")

def load_api_key():
    global API_KEY
    creds_file = os.path.expanduser("~/.config/simmer/credentials.json")
    if os.path.exists(creds_file):
        with open(creds_file) as f:
            API_KEY = json.load(f).get('api_key', '')
    return API_KEY

def load_config():
    """Load feeds and keywords from config."""
    global KEYWORDS, FEEDS
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
        # Load keywords
        if config.get('keywords'):
            KEYWORDS = [k.strip() for k in config.get('keywords', '').split(',')]
        # Load feeds
        feed_url = config.get('feeds', '')
        if feed_url:
            FEEDS = [feed_url]
        else:
            FEEDS = []

def load_signals():
    """Load existing signals from signals.json."""
    if SIGNALS_FILE.exists():
        try:
            with open(SIGNALS_FILE) as f:
                return json.load(f)
        except:
            return []
    return []

def save_signals(signals):
    """Save signals to signals.json."""
    SIGNALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SIGNALS_FILE, 'w') as f:
        json.dump(signals, f, indent=2)

def log_signal(article, keywords_matched):
    """Log a signal to signals.json (NOT a trade)."""
    signals = load_signals()
    
    # Check for duplicates (by link)
    existing_links = {s.get('link') for s in signals}
    if article.get('link') in existing_links:
        return False
    
    signal_record = {
        'timestamp': datetime.now().isoformat(),
        'title': article.get('title', ''),
        'link': article.get('link', ''),
        'description': article.get('description', '')[:200],
        'published': article.get('published', ''),
        'keywords_matched': keywords_matched,
        'source': 'rss',
        'status': 'detected',  # detected, analyzing, traded, ignored
        'market_id': None,  # Filled in if matched to a market
        'strategy': 'signal_sniper'
    }
    
    signals.append(signal_record)
    save_signals(signals)
    return True

def fetch_rss():
    """Fetch RSS feeds for signals."""
    from xml.etree import ElementTree as ET
    articles = []
    
    if not FEEDS:
        print(f"   ⚠️ No RSS feeds configured")
        return articles
    
    for url in FEEDS:
        try:
            req = requests.get(url, timeout=15)
            if req.status_code != 200:
                continue
                
            root = ET.fromstring(req.text)
            
            # Handle RSS
            for item in root.findall(".//item"):
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                description = item.findtext("description", "")
                pub_date = item.findtext("pubDate", "")
                
                if title and link:
                    articles.append({
                        "title": title,
                        "link": link,
                        "description": description[:200] if description else "",
                        "published": pub_date,
                    })
            
            # Handle Atom
            for entry in root.findall(".//entry"):
                title = entry.findtext("title", "")
                link = entry.findtext("link", "")
                summary = entry.findtext("summary", "")
                published = entry.findtext("published", "")
                
                if title and link:
                    articles.append({
                        "title": title,
                        "link": link.get("href", "") if hasattr(link, 'get') else link,
                        "description": summary[:200] if summary else "",
                        "published": published,
                    })
                    
        except Exception as e:
            print(f"   ⚠️ Feed error: {e}")
    
    return articles

def match_keywords(text):
    """Find which keywords match the text."""
    text = text.lower()
    return [kw for kw in KEYWORDS if kw in text]

def run(venue='simmer', dry_run=True):
    """
    Run signal detection.
    
    Args:
        venue: 'simmer', 'polymarket', etc. (not used in signal detection)
        dry_run: If True, only log signals, don't attempt trades
    """
    load_config()
    print(f" Signal Sniper v2.1 - {venue} (dry_run={dry_run})")
    btc = get_btc_price()
    print(f"   BTC ref: ${btc:,.2f}")
    
    articles = fetch_rss()
    print(f"   Fetched {len(articles)} articles")
    
    signals_logged = 0
    for a in articles:
        text = (a.get('title', '') + ' ' + a.get('description', '')).lower()
        matched = match_keywords(text)
        if matched:
            if log_signal(a, matched):
                signals_logged += 1
                print(f"   🔔 New signal: {a.get('title', '')[:60]}...")
    
    total_signals = len(load_signals())
    print(f"   ✓ Logged: {signals_logged} new signals ({total_signals} total in database)")
    
    return signals_logged

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--venue', default='simmer')
    parser.add_argument('--dry-run', action='store_true', default=True,
                        help='Only detect signals, do not trade')
    args = parser.parse_args()
    load_api_key()
    run(venue=args.venue, dry_run=args.dry_run)
