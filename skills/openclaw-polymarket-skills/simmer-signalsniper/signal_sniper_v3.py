#!/usr/bin/env python3
"""
Signal Sniper v3.0 - Automated Signal Trading with Risk Controls

Features:
- Multi-feed RSS monitoring
- Automatic market matching
- Simmer context endpoint integration
- Comprehensive risk controls
- Automatic trade execution
- Detailed logging
"""

import sys
sys.path.insert(0, "/home/han/clawd")

import os
import json
import argparse
import requests
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from xml.etree import ElementTree as ET

# Import trading library
from polymarket_trading.lib.price_client import get_btc_price
from polymarket_trading.lib.unified_trade_executor import execute_trade
from polymarket_trading.lib.simmer_client_wrapper import SimmerClientWithTimeout

# Configuration
CONFIG_PATH = Path(__file__).parent / "config.json"
SIGNALS_FILE = Path(__file__).parent / "state" / "signals.json"
TRADES_FILE = Path(__file__).parent / "state" / "signal_trades.json"
LOG_FILE = Path(__file__).parent / "state" / "sniper_log.jsonl"

# API
SIMMER_API_BASE = "https://api.simmer.markets"

class SignalSniperV3:
    """Automated signal detection and trading with risk controls."""
    
    def __init__(self):
        self.config = self.load_config()
        self.api_key = self.load_api_key()
        self.client = SimmerClientWithTimeout(self.api_key)
        self.signals_today = 0
        self.volume_today = 0.0
        self.processed_articles = set()
        
    def load_config(self) -> Dict:
        """Load configuration from config.json."""
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                return json.load(f)
        return self.default_config()
    
    def default_config(self) -> Dict:
        """Default configuration."""
        return {
            "enabled": True,
            "venue": "polymarket",
            "mode": "auto",
            "feeds": [],
            "keywords": {"general": ["bitcoin", "crypto"]},
            "risk_controls": {
                "max_trades_per_day": 5,
                "max_volume_per_day_usd": 100,
                "min_confidence": 0.75,
                "max_slippage_percent": 5.0,
                "position_size_usd": 10,
                "min_position_size": 5,
                "flip_flop_cooldown_hours": 24,
                "market_expiry_min_hours": 24,
                "max_spread_percent": 10,
                "require_simmer_context": True
            },
            "market_matching": {"enabled": True, "min_keyword_match": 2}
        }
    
    def load_api_key(self) -> str:
        """Load Simmer API key."""
        creds_file = Path.home() / ".config" / "simmer" / "credentials.json"
        if creds_file.exists():
            with open(creds_file) as f:
                return json.load(f).get('api_key', '')
        return ''
    
    # =========================================================================
    # RSS Feed Processing
    # =========================================================================
    
    def fetch_rss_feeds(self) -> List[Dict]:
        """Fetch all configured RSS feeds."""
        articles = []
        feeds = self.config.get('feeds', [])
        
        print(f"   Fetching {len(feeds)} RSS feeds...")
        
        for url in feeds:
            try:
                resp = requests.get(url, timeout=15, headers={
                    'User-Agent': 'Mozilla/5.0 (SignalSniper/3.0)'
                })
                if resp.status_code != 200:
                    print(f"   ⚠️ Feed failed ({resp.status_code}): {url[:50]}...")
                    continue
                
                feed_articles = self.parse_rss(resp.text)
                articles.extend(feed_articles)
                print(f"   ✓ {url[:40]}...: {len(feed_articles)} articles")
                
            except Exception as e:
                print(f"   ⚠️ Feed error: {url[:40]}... - {e}")
        
        return articles
    
    def parse_rss(self, xml_text: str) -> List[Dict]:
        """Parse RSS/Atom XML."""
        articles = []
        try:
            root = ET.fromstring(xml_text)
            
            # RSS format
            for item in root.findall(".//item"):
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                desc = item.findtext("description", "")[:300].strip()
                pub_date = item.findtext("pubDate", "")
                
                if title and link:
                    articles.append({
                        "title": title,
                        "link": link,
                        "description": desc,
                        "published": pub_date,
                        "source": "rss"
                    })
            
            # Atom format
            for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
                title = entry.findtext("{http://www.w3.org/2005/Atom}title", "").strip()
                link_elem = entry.find("{http://www.w3.org/2005/Atom}link")
                link = link_elem.get("href", "") if link_elem is not None else ""
                summary = entry.findtext("{http://www.w3.org/2005/Atom}summary", "")[:300]
                published = entry.findtext("{http://www.w3.org/2005/Atom}published", "")
                
                if title and link:
                    articles.append({
                        "title": title,
                        "link": link,
                        "description": summary,
                        "published": published,
                        "source": "atom"
                    })
                    
        except ET.ParseError as e:
            print(f"   ⚠️ RSS parse error: {e}")
        
        return articles
    
    def match_keywords(self, text: str) -> Tuple[List[str], str]:
        """
        Match text against keyword categories.
        Returns: (matched_keywords, category)
        """
        text = text.lower()
        keywords_config = self.config.get('keywords', {})
        
        all_matches = []
        best_category = "general"
        max_matches = 0
        
        for category, keywords in keywords_config.items():
            matches = [kw for kw in keywords if kw.lower() in text]
            if len(matches) > max_matches:
                max_matches = len(matches)
                best_category = category
                all_matches = matches
        
        return all_matches, best_category
    
    # =========================================================================
    # Market Matching
    # =========================================================================
    
    def search_markets(self, keywords: List[str], category: str = None, limit: int = 50) -> List[Dict]:
        """Search Polymarket for markets matching keywords using Gamma API."""
        try:
            # Fetch recent markets (most reliable approach)
            url = "https://gamma-api.polymarket.com/markets"
            params = {"active": "true", "closed": "false", "limit": 100}
            
            resp = requests.get(url, params=params, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            if resp.status_code != 200:
                return []
            
            data = resp.json()
            markets = data if isinstance(data, list) else data.get('markets', [])
            
            if not markets:
                return []
            
            # Filter by keywords
            keyword_set = set(kw.lower() for kw in keywords)
            matching = []
            
            for market in markets:
                question = market.get('question', '').lower()
                desc = market.get('description', '').lower()
                text = f"{question} {desc}"
                
                matches = sum(1 for kw in keyword_set if kw in text)
                if matches >= 2:
                    market['_keyword_matches'] = matches
                    matching.append(market)
            
            # Sort by match count
            matching.sort(key=lambda x: x.get('_keyword_matches', 0), reverse=True)
            return matching[:20]
            
        except Exception as e:
            print(f"   ⚠️ Market search error: {e}")
        
        return []
    
    def search_markets(self, keywords: List[str], category: str = None, limit: int = 50) -> List[Dict]:
        """Search Polymarket for markets matching keywords."""
        try:
            url = "https://gamma-api.polymarket.com/markets"
            params = {"active": "true", "closed": "false", "limit": 100}
            
            resp = requests.get(url, params=params, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            if resp.status_code != 200:
                return []
            
            data = resp.json()
            markets = data if isinstance(data, list) else data.get('markets', [])
            
            if not markets:
                return []
            
            # Filter by keywords
            keyword_set = set(kw.lower() for kw in keywords)
            matching = []
            
            for market in markets:
                question = market.get('question', '').lower()
                desc = market.get('description', '').lower()
                text = f"{question} {desc}"
                
                matches = sum(1 for kw in keyword_set if kw in text)
                if matches >= 2:
                    market['_keyword_matches'] = matches
                    matching.append(market)
            
            # Sort by match count
            matching.sort(key=lambda x: x.get('_keyword_matches', 0), reverse=True)
            return matching[:20]
            
        except Exception as e:
            print(f"   ⚠️ Market search error: {e}")
        
        return []
    
    def score_market_relevance(self, market: Dict, keywords: List[str], article: Dict) -> float:
        """Score how relevant a market is to the article."""
        score = 0.0
        market_text = f"{market.get('question', '')} {market.get('description', '')}".lower()
        article_text = f"{article['title']} {article['description']}".lower()
        
        # Keyword matches in market
        for kw in keywords:
            if kw.lower() in market_text:
                score += 0.2
        
        # Check if article and market share keywords
        article_words = set(article_text.split())
        market_words = set(market_text.split())
        overlap = len(article_words & market_words)
        score += min(overlap * 0.05, 0.3)  # Cap at 0.3
        
        # Time relevance (markets expiring soon get bonus)
        end_date = market.get('endDate')
        if end_date:
            try:
                expiry = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                hours_to_expiry = (expiry - datetime.now(expiry.tzinfo)).total_seconds() / 3600
                if 24 < hours_to_expiry < 168:  # 1 day to 1 week
                    score += 0.1
            except:
                pass
        
        return min(score, 1.0)
    
    def find_best_market(self, article: Dict, keywords: List[str], category: str = None) -> Optional[Dict]:
        """Find the best matching market for an article."""
        if not self.config.get('market_matching', {}).get('enabled', True):
            return None
        
        min_match = self.config.get('market_matching', {}).get('min_keyword_match', 2)
        if len(keywords) < min_match:
            return None
        
        markets = self.search_markets(keywords)
        if not markets:
            print(f"      ⚠️ No markets found for keywords: {keywords[:3]}...")
            return None
        
        # Score each market
        scored = []
        for market in markets:
            relevance = self.score_market_relevance(market, keywords, article)
            scored.append((market, relevance))
        
        # Sort by relevance
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Return best match if above threshold
        if scored and scored[0][1] >= 0.3:
            return scored[0][0]
        
        return None
    
    # =========================================================================
    # Risk Controls
    # =========================================================================
    
    def check_daily_limits(self) -> Tuple[bool, str]:
        """Check if we've hit daily trade/volume limits."""
        risk = self.config.get('risk_controls', {})
        max_trades = risk.get('max_trades_per_day', 5)
        max_volume = risk.get('max_volume_per_day_usd', 100)
        
        if self.signals_today >= max_trades:
            return False, f"Daily trade limit reached ({max_trades})"
        
        if self.volume_today >= max_volume:
            return False, f"Daily volume limit reached (${max_volume})"
        
        return True, "OK"
    
    def get_simmer_context(self, market_id: str) -> Optional[Dict]:
        """Get context from Simmer API for safeguards."""
        if not self.api_key:
            return None
        
        if not self.config.get('risk_controls', {}).get('require_simmer_context', True):
            return {"bypass": True}
        
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            url = f"{SIMMER_API_BASE}/v1/markets/{market_id}/context"
            
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            
        except Exception as e:
            print(f"   ⚠️ Context fetch error: {e}")
        
        return None
    
    def evaluate_context_warnings(self, context: Dict) -> Tuple[bool, str, float]:
        """
        Evaluate Simmer context warnings.
        Returns: (should_trade, reason, confidence_adjustment)
        """
        if not context or context.get('bypass'):
            return True, "No context required", 0.0
        
        risk = self.config.get('risk_controls', {})
        
        # Check market resolved
        if context.get('resolved'):
            return False, "Market already resolved", 0.0
        
        # Check expiry
        hours_to_expiry = context.get('hours_to_expiry', 999)
        min_hours = risk.get('market_expiry_min_hours', 24)
        if hours_to_expiry < min_hours:
            return False, f"Market expires in {hours_to_expiry:.0f}h (< {min_hours}h min)", 0.0
        
        # Check spread
        spread = context.get('spread_percent', 0)
        max_spread = risk.get('max_spread_percent', 10)
        if spread > max_spread:
            return False, f"Spread too wide ({spread:.1f}% > {max_spread}%)", 0.0
        
        # Check flip-flop warning
        flip_flop = context.get('flip_flop_warning', 'NONE')
        if flip_flop == 'SEVERE':
            return False, "Severe flip-flop warning", 0.0
        elif flip_flop == 'CAUTION':
            # Reduce confidence but still allow
            return True, "Flip-flop caution", -0.15
        
        # Check position already held
        if context.get('current_position'):
            pos = context['current_position']
            # Already holding - skip or reduce size
            return False, f"Already holding {pos.get('side')} position", 0.0
        
        # Check slippage estimate
        slippage = context.get('estimated_slippage_percent', 0)
        max_slippage = risk.get('max_slippage_percent', 5)
        if slippage > max_slippage:
            return False, f"Slippage too high ({slippage:.1f}% > {max_slippage}%)", 0.0
        
        return True, "All checks passed", 0.0
    
    def calculate_confidence(self, article: Dict, keywords: List[str], 
                            market: Dict, context: Dict) -> float:
        """Calculate overall confidence score for the trade."""
        base_confidence = 0.5
        
        # Keyword strength
        keyword_score = min(len(keywords) * 0.1, 0.3)
        base_confidence += keyword_score
        
        # Source credibility (can be enhanced)
        if 'coindesk' in article.get('link', '') or 'reuters' in article.get('link', ''):
            base_confidence += 0.1
        
        # Market relevance
        relevance = self.score_market_relevance(market, keywords, article)
        base_confidence += relevance * 0.2
        
        # Context adjustment
        _, _, adjustment = self.evaluate_context_warnings(context)
        base_confidence += adjustment
        
        return min(max(base_confidence, 0.0), 1.0)
    
    # =========================================================================
    # Trade Execution
    # =========================================================================
    
    def execute_signal_trade(self, article: Dict, market: Dict, 
                            confidence: float, dry_run: bool = True) -> Dict:
        """Execute a trade based on signal."""
        risk = self.config.get('risk_controls', {})
        
        result = {
            'signal_id': f"sig_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(article['link']) % 10000}",
            'timestamp': datetime.now().isoformat(),
            'article_title': article['title'][:100],
            'article_link': article['link'],
            'market_id': market.get('id'),
            'market_question': market.get('question', '')[:80],
            'confidence': confidence,
            'status': 'pending',
            'dry_run': dry_run
        }
        
        # Determine direction based on keywords
        text = f"{article['title']} {article['description']}".lower()
        bullish_terms = ['approval', 'pass', 'win', 'agreement', 'success', 'launch', 'bullish', 'up']
        bearish_terms = ['reject', 'fail', 'loss', 'ban', 'crash', 'delay', 'bearish', 'down', 'hack']
        
        bullish_score = sum(1 for term in bullish_terms if term in text)
        bearish_score = sum(1 for term in bearish_terms if term in text)
        
        side = 'YES' if bullish_score >= bearish_score else 'NO'
        result['side'] = side
        
        # Calculate position size
        size_usd = risk.get('position_size_usd', 10)
        if confidence < 0.8:
            size_usd *= 0.5  # Reduce size for lower confidence
        
        result['size_usd'] = size_usd
        
        if dry_run:
            result['status'] = 'dry_run'
            print(f"   💡 DRY RUN: Would {side} ${size_usd} on '{market.get('question', 'N/A')[:40]}...'")
            return result
        
        # Execute actual trade
        try:
            print(f"   🎯 Executing: {side} ${size_usd} on {market.get('question', 'N/A')[:40]}...")
            
            trade_result = execute_trade(
                market_id=market.get('id'),
                side=side,
                size=size_usd,
                venue=self.config.get('venue', 'polymarket'),
                dry_run=False
            )
            
            result['status'] = 'executed'
            result['trade_result'] = trade_result
            result['venue'] = self.config.get('venue', 'polymarket')
            
            # Update daily counters
            self.signals_today += 1
            self.volume_today += size_usd
            
            print(f"   ✅ Trade executed: {trade_result.get('status', 'unknown')}")
            
        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)
            print(f"   ❌ Trade failed: {e}")
        
        return result
    
    # =========================================================================
    # Main Loop
    # =========================================================================
    
    def run(self, dry_run: bool = True):
        """Main signal sniper loop."""
        if not self.config.get('enabled', True):
            print("   Signal Sniper disabled in config")
            return
        
        venue = self.config.get('venue', 'polymarket')
        mode = self.config.get('mode', 'auto')
        
        print(f"🎯 Signal Sniper v3.0 - {venue} (mode={mode}, dry_run={dry_run})")
        print(f"   Risk controls: {self.config.get('risk_controls', {})}")
        
        # Check daily limits
        can_trade, limit_reason = self.check_daily_limits()
        if not can_trade:
            print(f"   ⚠️ {limit_reason}")
            return
        
        # Fetch articles
        articles = self.fetch_rss_feeds()
        print(f"\n   Total articles fetched: {len(articles)}")
        
        signals_detected = 0
        trades_executed = 0
        
        for article in articles[:50]:  # Process top 50
            # Deduplicate
            if article['link'] in self.processed_articles:
                continue
            self.processed_articles.add(article['link'])
            
            # Match keywords
            keywords, category = self.match_keywords(
                article['title'] + ' ' + article['description']
            )
            
            if not keywords:
                continue
            
            print(f"\n   🔔 Signal detected: {article['title'][:60]}...")
            print(f"      Keywords: {keywords} (category: {category})")
            
            signals_detected += 1
            
            # Find matching market
            market = self.find_best_market(article, keywords, category)
            if not market:
                print(f"      ⚠️ No matching market found")
                continue
            
            print(f"      📊 Matched market: {market.get('question', 'N/A')[:50]}...")
            
            # Get Simmer context
            context = self.get_simmer_context(market.get('id'))
            
            # Evaluate risk controls
            should_trade, reason, _ = self.evaluate_context_warnings(context)
            if not should_trade:
                print(f"      ⛔ Blocked: {reason}")
                continue
            
            # Calculate confidence
            confidence = self.calculate_confidence(article, keywords, market, context)
            min_conf = self.config.get('risk_controls', {}).get('min_confidence', 0.75)
            
            print(f"      📈 Confidence: {confidence:.2f} (min: {min_conf})")
            
            if confidence < min_conf:
                print(f"      ⛔ Confidence too low")
                continue
            
            # Execute trade
            if mode == 'auto' or not dry_run:
                trade_result = self.execute_signal_trade(article, market, confidence, dry_run)
                
                if trade_result['status'] in ('executed', 'dry_run'):
                    trades_executed += 1
                    
                    # Save to trade log
                    self.log_trade(trade_result)
            else:
                print(f"      💡 Manual mode - signal logged for review")
        
        print(f"\n✅ Scan complete: {signals_detected} signals, {trades_executed} trades")
    
    def log_trade(self, trade: Dict):
        """Log trade to file."""
        TRADES_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        trades = []
        if TRADES_FILE.exists():
            try:
                with open(TRADES_FILE) as f:
                    trades = json.load(f)
            except:
                trades = []
        
        trades.append(trade)
        
        with open(TRADES_FILE, 'w') as f:
            json.dump(trades, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description='Signal Sniper v3.0')
    parser.add_argument('--run', action='store_true', help='Run signal detection')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Dry run mode')
    parser.add_argument('--live', action='store_true', help='Execute real trades')
    
    args = parser.parse_args()
    
    if args.live:
        args.dry_run = False
        print("🚨 LIVE MODE - Real trades will be executed!")
        # Add confirmation delay
        import time
        time.sleep(2)
    
    sniper = SignalSniperV3()
    sniper.run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
