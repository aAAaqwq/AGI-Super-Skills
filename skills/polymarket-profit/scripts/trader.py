#!/usr/bin/env python3
"""
Polymarket 真实交易执行模块
通过 CLOB API 下单，支持限价单和市价单
需要: pip install py-clob-client
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path("/home/aa/clawd/skills/polymarket-profit/data")
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"
TRADE_LOG_FILE = DATA_DIR / "trade_log.json"

# ── 配置 ──────────────────────────────────────────
CLOB_API = "https://clob.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
CHAIN_ID = 137  # Polygon

# 风控参数
MAX_BET_USD = 1.0       # 单笔最大 $1
MIN_MARKETS = 3          # 最少分散 3 个市场
TOTAL_CAPITAL = 3.0      # 总本金 $3
STOP_LOSS_PCT = 15       # 止损线 15%


def load_json(path):
    if path.exists():
        with open(path, 'r') as f:
            return json.load(f)
    return None


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def get_portfolio():
    data = load_json(PORTFOLIO_FILE)
    if not data:
        return {"positions": [], "total_invested": 0, "total_realized_pnl": 0, "mode": "live", "last_updated": None}
    return data


def get_trade_log():
    data = load_json(TRADE_LOG_FILE)
    if not data:
        return []
    return data


def check_risk(amount_usd, portfolio):
    """风控检查"""
    errors = []
    if amount_usd > MAX_BET_USD:
        errors.append(f"单笔 ${amount_usd} 超过上限 ${MAX_BET_USD}")
    if portfolio["total_invested"] + amount_usd > TOTAL_CAPITAL:
        remaining = TOTAL_CAPITAL - portfolio["total_invested"]
        errors.append(f"总投入将超过本金 ${TOTAL_CAPITAL}，剩余可用 ${remaining:.2f}")
    return errors


def record_trade(trade_type, token_id, side, amount_usd, price, market, outcome, status="pending", order_id=None, tx_hash=None):
    """记录交易"""
    log = get_trade_log()
    entry = {
        "type": trade_type,  # "live" or "paper"
        "token_id": token_id,
        "side": side,
        "amount_usd": amount_usd,
        "price": price,
        "market": market,
        "outcome": outcome,
        "status": status,
        "order_id": order_id,
        "tx_hash": tx_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    log.append(entry)
    save_json(TRADE_LOG_FILE, log)
    return entry


def update_portfolio(token_id, market, outcome, side, price, amount_usd, shares, status="open"):
    """更新持仓"""
    portfolio = get_portfolio()
    portfolio["mode"] = "live"

    # 检查是否已有该持仓
    existing = None
    for pos in portfolio["positions"]:
        if pos["token_id"] == token_id:
            existing = pos
            break

    if existing:
        # 加仓
        old_cost = existing["entry_price"] * existing["shares"]
        new_cost = price * shares
        total_shares = existing["shares"] + shares
        existing["entry_price"] = (old_cost + new_cost) / total_shares
        existing["shares"] = total_shares
        existing["amount_usd"] = existing["amount_usd"] + amount_usd
    else:
        portfolio["positions"].append({
            "token_id": token_id,
            "market": market,
            "outcome": outcome,
            "side": side,
            "entry_price": price,
            "amount_usd": amount_usd,
            "shares": shares,
            "status": status,
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "strategy": "high_certainty",
        })

    portfolio["total_invested"] = sum(p["amount_usd"] for p in portfolio["positions"] if p["status"] == "open")
    portfolio["last_updated"] = datetime.now(timezone.utc).isoformat()
    save_json(PORTFOLIO_FILE, portfolio)
    return portfolio


def close_position(token_id, sell_price, realized_pnl):
    """平仓"""
    portfolio = get_portfolio()
    for pos in portfolio["positions"]:
        if pos["token_id"] == token_id:
            pos["status"] = "closed"
            pos["closed_at"] = datetime.now(timezone.utc).isoformat()
            pos["sell_price"] = sell_price
            pos["realized_pnl"] = realized_pnl
            break

    portfolio["total_invested"] = sum(p["amount_usd"] for p in portfolio["positions"] if p["status"] == "open")
    portfolio["total_realized_pnl"] = sum(p.get("realized_pnl", 0) for p in portfolio["positions"] if p["status"] == "closed")
    portfolio["last_updated"] = datetime.now(timezone.utc).isoformat()
    save_json(PORTFOLIO_FILE, portfolio)
    return portfolio


def generate_order_instruction(market_slug, outcome, side, amount_usd, limit_price=None):
    """
    生成交易指令（供人工执行或 API 执行）
    返回结构化指令，可以直接在 Polymarket 网页操作
    """
    instruction = {
        "action": f"{side} {outcome}",
        "market": f"https://polymarket.com/event/{market_slug}",
        "amount": f"${amount_usd:.2f}",
        "limit_price": f"{limit_price}¢" if limit_price else "市价",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return instruction


def check_positions_health():
    """检查持仓健康度"""
    portfolio = get_portfolio()
    alerts = []
    for pos in portfolio["positions"]:
        if pos["status"] != "open":
            continue
        # 这里需要实时赔率来判断，先返回基本信息
        alerts.append({
            "token_id": pos["token_id"],
            "market": pos["market"],
            "outcome": pos["outcome"],
            "entry_price": pos["entry_price"],
            "amount_usd": pos["amount_usd"],
            "status": "需要实时赔率数据来评估",
        })
    return alerts


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Polymarket 交易执行")
    parser.add_argument("action", choices=["status", "health", "instruction"],
                        help="status=查看持仓, health=健康检查, instruction=生成交易指令")
    parser.add_argument("--market", help="市场 slug")
    parser.add_argument("--outcome", help="Yes/No")
    parser.add_argument("--side", default="BUY", help="BUY/SELL")
    parser.add_argument("--amount", type=float, help="金额 USD")
    parser.add_argument("--price", type=float, help="限价 (0-1)")
    args = parser.parse_args()

    if args.action == "status":
        p = get_portfolio()
        print(json.dumps(p, indent=2, ensure_ascii=False, default=str))

    elif args.action == "health":
        alerts = check_positions_health()
        print(json.dumps(alerts, indent=2, ensure_ascii=False, default=str))

    elif args.action == "instruction":
        if not all([args.market, args.outcome, args.amount]):
            print("需要 --market, --outcome, --amount 参数")
            sys.exit(1)
        risk_errors = check_risk(args.amount, get_portfolio())
        if risk_errors:
            print("⚠️ 风控拦截:")
            for e in risk_errors:
                print(f"  - {e}")
            sys.exit(1)
        inst = generate_order_instruction(args.market, args.outcome, args.side, args.amount, args.price)
        print(json.dumps(inst, indent=2, ensure_ascii=False, default=str))
