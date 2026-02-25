#!/usr/bin/env python3
"""Polymarket Portfolio Report Generator.

Reads portfolio.json + trade_log.json, queries CLOB for order status
and Gamma API for current prices, then outputs a concise P&L report.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent / "data"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"
TRADE_LOG_FILE = DATA_DIR / "trade_log.json"

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

ADDRESS = "0xd91eF877D04ACB06a9dE22e536765D2Ace246A9b"


def load_json(path):
    if not path.exists():
        return {} if "portfolio" in str(path) else []
    with open(path) as f:
        return json.load(f)


def get_wallet_key():
    """Get private key from pass store."""
    try:
        result = subprocess.run(
            ["pass", "show", "api/polymarket-wallet"],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip().split("\n")[0]
    except Exception:
        return None


def get_gamma_price(market_slug):
    """Fetch current market price from Gamma API."""
    try:
        resp = requests.get(f"{GAMMA_API}/markets", params={"slug": market_slug}, timeout=10)
        if resp.ok and resp.json():
            market = resp.json()[0] if isinstance(resp.json(), list) else resp.json()
            return market
    except Exception as e:
        print(f"  ⚠️ Gamma API error for {market_slug}: {e}", file=sys.stderr)
    return None


def get_order_status(order_id):
    """Check order status via CLOB API."""
    try:
        resp = requests.get(f"{CLOB_API}/order/{order_id}", timeout=10)
        if resp.ok:
            return resp.json()
    except Exception as e:
        print(f"  ⚠️ CLOB API error: {e}", file=sys.stderr)
    return None


def generate_report():
    portfolio = load_json(PORTFOLIO_FILE)
    trade_log = load_json(TRADE_LOG_FILE)
    positions = portfolio.get("positions", [])

    if not positions:
        return "📊 **Polymarket 持仓报告**\n\n无持仓。"

    lines = [
        f"📊 **Polymarket 持仓报告**",
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"💰 总资金: ${portfolio.get('capital', 0):.2f}",
        "",
    ]

    total_cost = 0
    total_market_value = 0
    wins = 0
    total_closed = 0

    for pos in positions:
        market_slug = pos.get("market", "")
        shares = pos.get("shares", 0)
        entry = pos.get("entry_price", 0)
        cost = pos.get("cost_usd", shares * entry)
        total_cost += cost

        # Try to get current price
        current_price = entry  # fallback
        gamma = get_gamma_price(market_slug)
        if gamma:
            # Try to extract outcome price
            outcome = pos.get("outcome", "Yes")
            if outcome == "Yes":
                current_price = float(gamma.get("outcomePrices", "[]").strip("[]").split(",")[0] or entry)
            else:
                prices = gamma.get("outcomePrices", "[]").strip("[]").split(",")
                current_price = float(prices[1] if len(prices) > 1 else entry)

        market_value = shares * current_price
        total_market_value += market_value
        pnl = market_value - cost
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0

        # Check order status
        order_id = pos.get("order_id", "")
        status_str = pos.get("status", "unknown")
        if order_id:
            order_info = get_order_status(order_id)
            if order_info:
                status_str = order_info.get("status", status_str)

        emoji = "🟢" if pnl >= 0 else "🔴"
        lines.append(f"**{pos.get('question', market_slug)}**")
        lines.append(f"  {pos.get('outcome', '?')} × {shares} @ ${entry:.2f}")
        lines.append(f"  现价: ${current_price:.3f} | 市值: ${market_value:.2f}")
        lines.append(f"  {emoji} P&L: ${pnl:+.2f} ({pnl_pct:+.1f}%)")
        lines.append(f"  📋 状态: {status_str} | 类型: {pos.get('type', 'market')}")
        lines.append("")

    # Realized P&L from closed trades
    realized_pnl = portfolio.get("total_realized_pnl", 0)

    unrealized_pnl = total_market_value - total_cost
    lines.append("─" * 30)
    lines.append(f"📥 总投入: ${total_cost:.2f}")
    lines.append(f"📈 当前市值: ${total_market_value:.2f}")
    lines.append(f"📊 未实现盈亏: ${unrealized_pnl:+.2f}")
    lines.append(f"✅ 已实现盈亏: ${realized_pnl:+.2f}")
    lines.append(f"💵 可用资金: ${portfolio.get('capital', 0) - total_cost:.2f}")

    # Win rate from trade log
    for t in trade_log:
        if t.get("status") in ("won", "settled_win"):
            wins += 1
            total_closed += 1
        elif t.get("status") in ("lost", "settled_loss"):
            total_closed += 1

    if total_closed > 0:
        lines.append(f"🎯 胜率: {wins}/{total_closed} ({wins/total_closed*100:.0f}%)")

    return "\n".join(lines)


if __name__ == "__main__":
    report = generate_report()
    print(report)

    # If --send flag, push to Telegram
    if "--send" in sys.argv:
        newsbot = Path.home() / "clawd/scripts/newsbot_send.py"
        if newsbot.exists():
            subprocess.run([sys.executable, str(newsbot), report], timeout=30)
            print("\n✅ 已推送到 Telegram")
        else:
            print(f"\n⚠️ newsbot not found: {newsbot}", file=sys.stderr)
