#!/usr/bin/env python3
"""
Deep analyze a single Polymarket wallet.
Usage: python analyze_wallet.py 0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B [--days 30]
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from collections import defaultdict

def fetch_positions(address, limit=50):
    """Fetch current positions for a wallet."""
    url = f"https://data-api.polymarket.com/positions?user={address}&limit={limit}"
    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return data if isinstance(data, list) else data.get("positions", [])
    except Exception as e:
        print(f"  [WARN] Positions fetch failed: {e}", file=sys.stderr)
        return []

def fetch_trades(address, limit=100):
    """Fetch trade history for a wallet."""
    url = f"https://data-api.polymarket.com/trades?user={address}&limit={limit}"
    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return data if isinstance(data, list) else data.get("trades", [])
    except Exception as e:
        print(f"  [WARN] Trades fetch failed: {e}", file=sys.stderr)
        return []

def fetch_closed_positions(address, limit=50):
    """Fetch closed positions for a wallet."""
    url = f"https://data-api.polymarket.com/closed-positions?user={address}&limit={limit}"
    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return data if isinstance(data, list) else data.get("positions", [])
    except Exception as e:
        print(f"  [WARN] Closed positions fetch failed: {e}", file=sys.stderr)
        return []

def analyze_positions(positions):
    """Analyze current (open) positions."""
    if not positions:
        return {"count": 0, "total_value": 0, "total_pnl": 0, "positions": []}
    
    total_value = sum(float(p.get("currentValue", 0)) for p in positions)
    total_pnl = sum(float(p.get("cashPnl", 0)) for p in positions)
    
    return {
        "count": len(positions),
        "total_value": total_value,
        "total_pnl": total_pnl,
        "positions": positions[:10]
    }

def analyze_closed_positions(closed):
    """Analyze closed/resolved positions for win rate and PnL."""
    if not closed:
        return None
    
    wins = 0
    losses = 0
    total_pnl = 0
    win_amounts = []
    loss_amounts = []
    by_market = defaultdict(lambda: {"count": 0, "pnl": 0})
    
    for p in closed:
        # closed-positions uses realizedPnl, open positions uses cashPnl
        pnl = float(p.get("realizedPnl", p.get("cashPnl", 0)))
        total_pnl += pnl
        
        if pnl > 0:
            wins += 1
            win_amounts.append(pnl)
        elif pnl < 0:
            losses += 1
            loss_amounts.append(abs(pnl))
        
        market = p.get("title", "Unknown")
        by_market[market]["count"] += 1
        by_market[market]["pnl"] += pnl
    
    total = wins + losses
    win_rate = (wins / total * 100) if total > 0 else 0
    avg_win = sum(win_amounts) / len(win_amounts) if win_amounts else 0
    avg_loss = sum(loss_amounts) / len(loss_amounts) if loss_amounts else 0
    risk_score = avg_loss / avg_win if avg_win > 0 else 999
    
    # Market breakdown
    market_stats = sorted(by_market.items(), key=lambda x: x[1]["pnl"], reverse=True)[:5]
    
    return {
        "total_closed": total,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "risk_score": risk_score,
        "best_trade": max(closed, key=lambda x: float(x.get("realizedPnl", x.get("cashPnl", 0)))) if closed else None,
        "worst_trade": min(closed, key=lambda x: float(x.get("realizedPnl", x.get("cashPnl", 0)))) if closed else None,
        "top_markets": market_stats
    }

def analyze_trades(trades):
    """Analyze recent trade activity."""
    if not trades:
        return None
    
    # Group by market
    by_market = defaultdict(lambda: {"count": 0, "volume": 0, "last_time": 0})
    
    for t in trades:
        market = t.get("title", "Unknown")
        size = float(t.get("size", 0))
        price = float(t.get("price", 0))
        ts = int(t.get("timestamp", 0))
        
        by_market[market]["count"] += 1
        by_market[market]["volume"] += size * price
        if ts > by_market[market]["last_time"]:
            by_market[market]["last_time"] = ts
    
    return {
        "total_trades": len(trades),
        "total_volume": sum(float(t.get("size", 0)) * float(t.get("price", 0)) for t in trades),
        "recent_markets": sorted(by_market.items(), key=lambda x: x[1]["last_time"], reverse=True)[:5]
    }

def main():
    parser = argparse.ArgumentParser(description="Analyze a Polymarket wallet")
    parser.add_argument("address", help="Wallet address to analyze")
    parser.add_argument("--days", type=int, default=30, help="Analyze trades in last N days")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()
    
    address = args.address.strip()
    short = f"{address[:6]}...{address[-4:]}"
    print(f"=== Analyzing Wallet: {short} ===\n")
    
    # Fetch data
    print("[1/3] Fetching open positions...")
    positions = fetch_positions(address)
    print(f"      Found {len(positions)} open positions")
    
    print("[2/3] Fetching closed positions...")
    closed = fetch_closed_positions(address)
    print(f"      Found {len(closed)} closed positions")
    
    print("[3/3] Fetching trade history...")
    trades = fetch_trades(address)
    print(f"      Found {len(trades)} trades")
    
    if not trades and not positions and not closed:
        print("\n❌ No data found for this wallet. It may be new or private.")
        sys.exit(1)
    
    # Analyze
    position_stats = analyze_positions(positions)
    closed_stats = analyze_closed_positions(closed)
    trade_stats = analyze_trades(trades)
    
    if args.json:
        output = {
            "address": address,
            "open_positions": position_stats,
            "closed_positions": closed_stats,
            "recent_trades": trade_stats
        }
        print(json.dumps(output, indent=2))
        return
    
    # Print report
    print("\n" + "=" * 50)
    print("CLOSED POSITIONS (Win Rate & PnL)")
    print("=" * 50)
    
    if closed_stats:
        cs = closed_stats
        pnl_str = f"+${cs['total_pnl']:.2f}" if cs['total_pnl'] >= 0 else f"-${abs(cs['total_pnl']):.2f}"
        print(f"Total Closed:    {cs['total_closed']}")
        print(f"Win Rate:        {cs['win_rate']:.1f}%  ({cs['wins']}W / {cs['losses']}L)")
        print(f"Total PnL:       {pnl_str}")
        print(f"Avg Win:         ${cs['avg_win']:.2f}")
        print(f"Avg Loss:        ${cs['avg_loss']:.2f}")
        print(f"Risk Score:      {cs['risk_score']:.2f}  {'✅ GOOD (<1.0)' if cs['risk_score'] < 1.0 else '⚠️ HIGH (>1.0)'}")
        
        if cs['best_trade']:
            bt = cs['best_trade']
            pnl = float(bt.get("realizedPnl", bt.get("cashPnl", 0)))
            pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
            print(f"\nBest Trade:      {pnl_str} | {bt.get('title', 'N/A')[:50]}")
        
        if cs['worst_trade']:
            wt = cs['worst_trade']
            pnl = float(wt.get("realizedPnl", wt.get("cashPnl", 0)))
            pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
            print(f"Worst Trade:     {pnl_str} | {wt.get('title', 'N/A')[:50]}")
        
        if cs['top_markets']:
            print("\nTop Markets by PnL:")
            for market, stats in cs['top_markets']:
                pnl_str = f"+${stats['pnl']:.2f}" if stats['pnl'] >= 0 else f"-${abs(stats['pnl']):.2f}"
                print(f"  {market[:45]:<45} {stats['count']:>3} trades  {pnl_str}")
    else:
        print("No closed position data available")
    
    print("\n" + "=" * 50)
    print("OPEN POSITIONS")
    print("=" * 50)
    
    if position_stats["count"] > 0:
        ps = position_stats
        val_str = f"${ps['total_value']:.2f}" if ps['total_value'] > 0 else "$0.00"
        pnl_str = f"+${ps['total_pnl']:.2f}" if ps['total_pnl'] >= 0 else f"-${abs(ps['total_pnl']):.2f}"
        print(f"Open Positions:  {ps['count']}")
        print(f"Total Value:     {val_str}")
        print(f"Unrealized PnL:  {pnl_str}")
        print("\nPosition Details:")
        for p in ps["positions"][:8]:
            side = p.get("side", "")
            market = p.get("title", "Unknown")[:35]
            size = float(p.get("size", 0))
            avg = float(p.get("avgPrice", 0)) * 100
            current = float(p.get("curPrice", 0)) * 100
            pnl = float(p.get("cashPnl", 0))
            pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
            outcome = p.get("outcome", "")
            print(f"  [{outcome:<3}] {market:<35} {size:.1f} @ {avg:.0f}¢ cur:{current:.0f}¢  {pnl_str}")
    else:
        print("No open positions")
    
    print("\n" + "=" * 50)
    print("RECENT TRADE ACTIVITY")
    print("=" * 50)
    
    if trade_stats and trade_stats["recent_markets"]:
        print(f"Total Trades (all time): {trade_stats['total_trades']}")
        print(f"Estimated Volume: ${trade_stats['total_volume']:.2f}")
        print("\nRecent Markets Traded:")
        for market, info in trade_stats["recent_markets"]:
            dt = datetime.fromtimestamp(info["last_time"]) if info["last_time"] else None
            time_str = dt.strftime("%m-%d %H:%M") if dt else "Unknown"
            vol_str = f"${info['volume']:.2f}"
            print(f"  {time_str} | {market[:40]:<40} | {info['count']} trades | vol:{vol_str}")
    else:
        print("No trade data available")
    
    # Overall verdict
    print("\n" + "=" * 50)
    print("COPY ASSESSMENT")
    print("=" * 50)
    
    score = 0
    reasons = []
    
    if closed_stats:
        cs = closed_stats
        
        # Win rate (40 points)
        if cs["win_rate"] >= 65:
            score += 40
            reasons.append(f"✅ High win rate ({cs['win_rate']:.0f}%)")
        elif cs["win_rate"] >= 55:
            score += 25
            reasons.append(f"⚠️ Decent win rate ({cs['win_rate']:.0f}%)")
        elif cs["win_rate"] >= 45:
            score += 10
            reasons.append(f"⚠️ Low win rate ({cs['win_rate']:.0f}%)")
        else:
            reasons.append(f"❌ Very low win rate ({cs['win_rate']:.0f}%)")
        
        # PnL (30 points)
        if cs["total_pnl"] >= 5000:
            score += 30
            reasons.append(f"✅ Excellent PnL (${cs['total_pnl']:,.0f})")
        elif cs["total_pnl"] >= 1000:
            score += 25
            reasons.append(f"✅ Strong PnL (${cs['total_pnl']:,.0f})")
        elif cs["total_pnl"] >= 200:
            score += 15
            reasons.append(f"⚠️ Moderate PnL (${cs['total_pnl']:,.0f})")
        elif cs["total_pnl"] >= 0:
            score += 5
            reasons.append(f"⚠️ Break-even PnL (${cs['total_pnl']:,.0f})")
        else:
            reasons.append(f"❌ Negative PnL (${cs['total_pnl']:,.0f})")
        
        # Risk score (20 points)
        if cs["risk_score"] < 0.6:
            score += 20
            reasons.append(f"✅ Very low risk (score {cs['risk_score']:.2f})")
        elif cs["risk_score"] < 0.8:
            score += 15
            reasons.append(f"✅ Low risk (score {cs['risk_score']:.2f})")
        elif cs["risk_score"] < 1.0:
            score += 8
            reasons.append(f"⚠️ Moderate risk (score {cs['risk_score']:.2f})")
        else:
            reasons.append(f"❌ High risk (score {cs['risk_score']:.2f})")
        
        # Sample size (10 points)
        if cs["total_closed"] >= 50:
            score += 10
            reasons.append(f"✅ Large sample ({cs['total_closed']} trades)")
        elif cs["total_closed"] >= 20:
            score += 7
            reasons.append(f"✅ Good sample ({cs['total_closed']} trades)")
        elif cs["total_closed"] >= 10:
            score += 4
            reasons.append(f"⚠️ Small sample ({cs['total_closed']} trades)")
        elif cs["total_closed"] >= 3:
            score += 2
            reasons.append(f"⚠️ Very small sample ({cs['total_closed']} trades)")
        else:
            reasons.append(f"❌ Insufficient data ({cs['total_closed']} trades)")
        
        verdict = "✅ COPYABLE" if score >= 70 else "⚠️ CAUTION" if score >= 45 else "❌ NOT RECOMMENDED"
        
        print(f"\nScore: {score}/100  {verdict}\n")
        for r in reasons:
            print(f"  {r}")
    else:
        print("\n❌ Insufficient closed position data")
        if trade_stats and trade_stats["total_trades"] > 0:
            print(f"  Only {trade_stats['total_trades']} trades found (no closed positions resolved)")
            print(f"  Cannot assess win rate without resolved positions")

if __name__ == "__main__":
    main()
