#!/usr/bin/env python3
"""
Score and rank multiple Polymarket wallets for copy trading.
Usage: python copy_score.py wallet1 wallet2 wallet3 ...
   or: python copy_score.py --file wallets.txt
"""

import argparse
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from analyze_wallet import fetch_trades, fetch_positions, analyze_trades

def score_wallet(address):
    """Score a single wallet. Returns (address, score, details)."""
    try:
        trades = fetch_trades(address, limit=100)
        stats = analyze_trades(trades)
        
        if not stats or stats["total_trades"] < 3:
            return (address, 0, {"reason": "insufficient_trades"})
        
        ts = stats
        
        # Scoring components (out of 100)
        score = 0
        details = {
            "total_trades": ts["total_trades"],
            "win_rate": ts["win_rate"],
            "total_pnl": ts["total_pnl"],
            "avg_trade": ts["total_pnl"] / ts["total_trades"] if ts["total_trades"] > 0 else 0,
            "risk_score": ts["risk_score"],
            "recent_wins": 0,
            "recent_trades": 0
        }
        
        # Win rate score (40 points max)
        if ts["win_rate"] >= 70:
            score += 40
        elif ts["win_rate"] >= 60:
            score += 30
        elif ts["win_rate"] >= 55:
            score += 20
        elif ts["win_rate"] >= 50:
            score += 10
        
        # PnL score (30 points max)
        if ts["total_pnl"] >= 5000:
            score += 30
        elif ts["total_pnl"] >= 1000:
            score += 25
        elif ts["total_pnl"] >= 500:
            score += 18
        elif ts["total_pnl"] >= 100:
            score += 10
        elif ts["total_pnl"] > 0:
            score += 5
        
        # Risk score (20 points max)
        if ts["risk_score"] < 0.5:
            score += 20
        elif ts["risk_score"] < 0.8:
            score += 15
        elif ts["risk_score"] < 1.0:
            score += 10
        elif ts["risk_score"] < 1.5:
            score += 5
        
        # Consistency/sample size (10 points max)
        if ts["total_trades"] >= 50:
            score += 10
        elif ts["total_trades"] >= 20:
            score += 7
        elif ts["total_trades"] >= 10:
            score += 4
        elif ts["total_trades"] >= 5:
            score += 2
        
        # Check recent activity (last 7 days)
        recent_trades = [t for t in trades if is_recent(t.get("timestamp", ""), days=7)]
        details["recent_trades"] = len(recent_trades)
        details["recent_wins"] = sum(1 for t in recent_trades if t.get("realizedPnl", 0) > 0)
        
        if len(recent_trades) >= 3:
            score += 10  # Bonus for active trading
        elif len(recent_trades) >= 1:
            score += 5
        
        return (address, score, details)
        
    except Exception as e:
        return (address, 0, {"reason": str(e)})

def is_recent(timestamp_str, days=7):
    """Check if timestamp is within last N days."""
    if not timestamp_str:
        return False
    try:
        from datetime import datetime
        if isinstance(timestamp_str, (int, float)):
            dt = datetime.fromtimestamp(timestamp_str)
        else:
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return (datetime.now(dt.tzinfo) - dt).days < days
    except:
        return False

def load_wallets(args):
    """Load wallet addresses from args or file."""
    wallets = []
    
    if args.file:
        try:
            with open(args.file) as f:
                wallets = [line.strip() for line in f if line.strip().startswith("0x")]
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        wallets = [w.strip() for w in args.wallets if w.strip().startswith("0x")]
    
    if not wallets:
        print("No valid wallets provided", file=sys.stderr)
        sys.exit(1)
    
    return wallets

def main():
    parser = argparse.ArgumentParser(description="Score Polymarket wallets for copy trading")
    parser.add_argument("wallets", nargs="*", help="Wallet addresses to score")
    parser.add_argument("--file", help="File containing wallet addresses (one per line)")
    parser.add_argument("--min-score", type=int, default=50, help="Minimum score filter")
    parser.add_argument("--min-winrate", type=float, default=0, help="Minimum win rate %%")
    parser.add_argument("--min-pnl", type=float, default=0, help="Minimum total PnL $")
    parser.add_argument("--threads", type=int, default=5, help="Parallel threads")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()
    
    wallets = load_wallets(args)
    print(f"Scoring {len(wallets)} wallets...\n")
    
    results = []
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = {executor.submit(score_wallet, w): w for w in wallets}
        for i, future in enumerate(as_completed(futures), 1):
            addr, score, details = future.result()
            results.append((addr, score, details))
            short = f"{addr[:6]}...{addr[-4:]}"
            print(f"[{i}/{len(wallets)}] {short}: score={score} winrate={details.get('win_rate',0):.0f}% pnl=${details.get('total_pnl',0):.0f}")
    
    # Filter
    filtered = [
        (a, s, d) for a, s, d in results
        if s >= args.min_score
        and d.get("win_rate", 0) >= args.min_winrate
        and d.get("total_pnl", 0) >= args.min_pnl
    ]
    
    # Sort by score
    filtered.sort(key=lambda x: x[1], reverse=True)
    
    if args.json:
        output = [{"address": a, "score": s, **d} for a, s, d in filtered]
        print(json.dumps(output, indent=2))
        return
    
    # Report
    print(f"\n{'='*80}")
    print(f"{'RANK':<5} {'WALLET':<14} {'SCORE':>6} {'WINRATE':>8} {'TOTALPNL':>10} {'AVGTRADE':>9} {'RISK':>6} {'RECENT':>7}")
    print(f"{'='*80}")
    
    for i, (addr, score, details) in enumerate(filtered, 1):
        short = f"{addr[:6]}...{addr[-4:]}"
        wr = details.get("win_rate", 0)
        pnl = details.get("total_pnl", 0)
        avg = details.get("avg_trade", 0)
        risk = details.get("risk_score", 999)
        recent = f"{details.get('recent_wins',0)}/{details.get('recent_trades',0)}"
        
        pnl_str = f"+${pnl:.0f}" if pnl >= 0 else f"-${abs(pnl):.0f}"
        avg_str = f"+${avg:.2f}" if avg >= 0 else f"-${abs(avg):.2f}"
        risk_str = f"{risk:.2f}"
        
        verdict = "✅" if score >= 70 else "⚠️" if score >= 45 else "❌"
        print(f"{verdict}{i:<4} {short:<14} {score:>5}  {wr:>6.1f}% {pnl_str:>10} {avg_str:>9} {risk_str:>6} {recent:>7}")
    
    if filtered:
        best = filtered[0]
        print(f"\n🏆 BEST FOR COPY: {best[0][:8]}...{best[0][-4:]} (score {best[1]})")
        print(f"   Win rate: {best[2].get('win_rate',0):.0f}% | PnL: ${best[2].get('total_pnl',0):.0f} | Risk: {best[2].get('risk_score',0):.2f}")
    else:
        print("\n❌ No wallets passed filters")

if __name__ == "__main__":
    main()
