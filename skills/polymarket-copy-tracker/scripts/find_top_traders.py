#!/usr/bin/env python3
"""
Fetch top Polymarket traders from the leaderboard page.
Usage: python find_top_traders.py [--limit 20]
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.error

def fetch_leaderboard_addresses(limit=20):
    """Extract wallet addresses from polymarket.com/leaderboard HTML."""
    url = "https://polymarket.com/leaderboard"
    
    try:
        req = urllib.request.Request(url, headers={
            "Accept": "text/html",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"Error fetching leaderboard: {e}", file=sys.stderr)
        return []
    
    # Extract wallet addresses (0x + 40 hex chars)
    addresses = list(set(re.findall(r'\b0x[a-fA-F0-9]{40}\b', html)))
    
    return addresses[:limit]

def main():
    parser = argparse.ArgumentParser(description="Find top Polymarket traders")
    parser.add_argument("--limit", type=int, default=20, help="Number of addresses to fetch")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()
    
    addresses = fetch_leaderboard_addresses(limit=args.limit)
    
    if not addresses:
        print("No addresses found", file=sys.stderr)
        sys.exit(1)
    
    if args.json:
        print(json.dumps(addresses, indent=2))
    else:
        print(f"Found {len(addresses)} wallet addresses from Polymarket leaderboard:\n")
        for i, addr in enumerate(addresses, 1):
            short = f"{addr[:6]}...{addr[-4:]}"
            print(f"  {i:2}. {short}  ({addr})")
        print(f"\nUse analyze_wallet.py <address> to analyze any of these.")

if __name__ == "__main__":
    main()
