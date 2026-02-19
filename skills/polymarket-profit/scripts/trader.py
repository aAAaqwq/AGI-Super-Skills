#!/usr/bin/env python3
"""
Polymarket 交易执行模块
真正的下单、持仓管理、止盈止损
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# 配置路径
BASE_DIR = Path("/home/aa/clawd/skills/polymarket-profit")
DATA_DIR = BASE_DIR / "data"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"
TRADE_LOG_FILE = DATA_DIR / "trade_log.json"
CONFIG_FILE = BASE_DIR / "config" / "trading_config.json"

sys.path.insert(0, str(BASE_DIR / "scripts"))


def get_api_key():
    """从 pass 获取 Polymarket 私钥"""
    import subprocess
    try:
        result = subprocess.run(
            ["pass", "show", "api/polymarket-key"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def get_funder_address():
    """从 pass 获取 funder 地址"""
    import subprocess
    try:
        result = subprocess.run(
            ["pass", "show", "api/polymarket-funder"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def create_client(read_only=False):
    """创建 Polymarket CLOB 客户端"""
    from py_clob_client.client import ClobClient

    HOST = "https://clob.polymarket.com"
    CHAIN_ID = 137  # Polygon

    if read_only:
        return ClobClient(HOST)

    private_key = get_api_key()
    funder = get_funder_address()

    if not private_key:
        raise ValueError("未找到 Polymarket 私钥，请运行: pass insert api/polymarket-key")
    if not funder:
        raise ValueError("未找到 funder 地址，请运行: pass insert api/polymarket-funder")

    client = ClobClient(
        HOST,
        key=private_key,
        chain_id=CHAIN_ID,
        signature_type=1,
        funder=funder,
    )
    client.set_api_creds(client.create_or_derive_api_creds())
    return client


# ─── 持仓管理 ───

def load_portfolio():
    """加载持仓数据"""
    if PORTFOLIO_FILE.exists():
        with open(PORTFOLIO_FILE) as f:
            return json.load(f)
    return {
        "positions": [],
        "total_invested": 0,
        "total_realized_pnl": 0,
        "last_updated": None,
    }


def save_portfolio(portfolio):
    """保存持仓数据"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    portfolio["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=2, ensure_ascii=False)


def log_trade(trade):
    """记录交易日志"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logs = []
    if TRADE_LOG_FILE.exists():
        with open(TRADE_LOG_FILE) as f:
            logs = json.load(f)
    trade["timestamp"] = datetime.now(timezone.utc).isoformat()
    logs.append(trade)
    with open(TRADE_LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)


# ─── 市场分析 ───

def get_orderbook_depth(client, token_id):
    """获取订单簿深度，评估流动性"""
    try:
        book = client.get_order_book(token_id)
        bids = book.bids if hasattr(book, 'bids') else []
        asks = book.asks if hasattr(book, 'asks') else []

        bid_depth = sum(float(b.size) * float(b.price) for b in bids[:5]) if bids else 0
        ask_depth = sum(float(a.size) * float(a.price) for a in asks[:5]) if asks else 0
        spread = 0
        if bids and asks:
            best_bid = float(bids[0].price)
            best_ask = float(asks[0].price)
            spread = best_ask - best_bid

        return {
            "bid_depth_usd": round(bid_depth, 2),
            "ask_depth_usd": round(ask_depth, 2),
            "spread": round(spread, 4),
            "spread_pct": round(spread * 100, 2),
            "liquid": bid_depth > 50 and ask_depth > 50,
        }
    except Exception as e:
        return {"error": str(e), "liquid": False}


def evaluate_market(client, token_id, market_info):
    """综合评估一个市场的交易价值"""
    depth = get_orderbook_depth(client, token_id)

    score = 0
    reasons = []

    # 流动性评分
    if depth.get("liquid"):
        score += 20
        reasons.append("流动性充足")
    else:
        score -= 30
        reasons.append("⚠️ 流动性不足")

    # 价差评分
    spread_pct = depth.get("spread_pct", 99)
    if spread_pct < 1:
        score += 15
        reasons.append(f"价差极小 ({spread_pct}%)")
    elif spread_pct < 3:
        score += 5
        reasons.append(f"价差可接受 ({spread_pct}%)")
    else:
        score -= 10
        reasons.append(f"⚠️ 价差过大 ({spread_pct}%)")

    # 交易量评分
    volume = market_info.get("volume", 0)
    if volume > 1_000_000:
        score += 20
        reasons.append(f"高交易量 (${volume:,.0f})")
    elif volume > 100_000:
        score += 10
    else:
        score -= 5

    # 时间评分（临近结算的市场更有确定性）
    days_left = market_info.get("days_left")
    if days_left is not None:
        if 1 <= days_left <= 7:
            score += 15
            reasons.append(f"即将结算 ({days_left}天)")
        elif days_left <= 0:
            score -= 50
            reasons.append("⚠️ 已过期")

    # 概率评分（极端概率 = 低风险机会）
    outcomes = market_info.get("outcomes", {})
    for outcome, pct in outcomes.items():
        if pct >= 90:
            score += 25
            reasons.append(f"高确定性: {outcome} {pct}%")
        elif pct >= 80:
            score += 15
            reasons.append(f"较确定: {outcome} {pct}%")

    return {
        "score": score,
        "reasons": reasons,
        "depth": depth,
        "tradeable": score >= 30,
    }


# ─── 策略引擎 ───

def strategy_high_certainty(markets, capital_usd):
    """
    高确定性策略：买入概率 >= 80% 的结果
    预期收益: 5-25%，风险低
    """
    config = load_trading_config()
    sc = config.get("strategies", {}).get("high_certainty", {})
    min_prob = sc.get("min_probability", 80)
    max_days = sc.get("max_days_left", 120)
    min_return = sc.get("min_return_pct", 5)
    min_vol = sc.get("min_volume", 50000)

    opportunities = []

    for m in markets:
        days_left = m.get("days_left")
        if days_left is None or days_left < 1 or days_left > max_days:
            continue
        if m.get("volume", 0) < min_vol:
            continue

        outcomes = m.get("outcomes", {})
        for outcome, pct in outcomes.items():
            if pct >= min_prob and pct <= 97:  # 不买 >97% 的（利润太薄）
                buy_price = pct / 100
                potential_return = (1 / buy_price - 1) * 100
                if potential_return >= min_return:
                    max_bet = min(capital_usd * 0.2, 2)
                    opportunities.append({
                        "strategy": "high_certainty",
                        "market": m["question"],
                        "token_id": m.get("id"),
                        "slug": m.get("slug"),
                        "outcome": outcome,
                        "probability": pct,
                        "buy_price": buy_price,
                        "potential_return_pct": round(potential_return, 1),
                        "suggested_amount": round(max_bet, 2),
                        "days_left": days_left,
                        "volume": m.get("volume", 0),
                        "risk": "low",
                    })

    opportunities.sort(key=lambda x: x["potential_return_pct"], reverse=True)
    return opportunities[:10]


def strategy_arbitrage(markets, capital_usd):
    """
    套利策略：找到 Yes + No 价格之和 < $1 的市场
    无风险利润
    """
    opportunities = []

    for m in markets:
        outcomes = m.get("outcomes", {})
        if "Yes" in outcomes and "No" in outcomes:
            yes_price = outcomes["Yes"] / 100
            no_price = outcomes["No"] / 100
            total = yes_price + no_price

            if total < 0.98:  # 存在套利空间 (>2%)
                profit_pct = (1 / total - 1) * 100
                opportunities.append({
                    "strategy": "arbitrage",
                    "market": m["question"],
                    "token_id": m.get("id"),
                    "slug": m.get("slug"),
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "total_cost": round(total, 4),
                    "profit_pct": round(profit_pct, 2),
                    "suggested_amount": round(min(capital_usd * 0.3, 3), 2),
                    "risk": "very_low",
                })

    opportunities.sort(key=lambda x: x["profit_pct"], reverse=True)
    return opportunities[:5]


def strategy_momentum(markets, capital_usd):
    """
    动量策略：找到近期概率大幅变动的市场
    跟随趋势方向下注
    """
    # 需要历史数据对比，先返回框架
    # TODO: 接入历史赔率数据
    return []


def strategy_event_driven(markets, capital_usd):
    """
    事件驱动策略：基于即将发生的已知事件
    利用信息优势在事件前布局
    """
    config = load_trading_config()
    sc = config.get("strategies", {}).get("event_driven", {})
    prob_range = sc.get("probability_range", [35, 65])
    max_days = sc.get("max_days_left", 30)
    min_vol = sc.get("min_volume", 200000)

    opportunities = []

    for m in markets:
        days_left = m.get("days_left")
        if days_left is None or days_left < 1:
            continue
        volume = m.get("volume", 0)
        outcomes = m.get("outcomes", {})

        if days_left <= max_days and volume > min_vol:
            for outcome, pct in outcomes.items():
                if prob_range[0] <= pct <= prob_range[1]:
                    opportunities.append({
                        "strategy": "event_driven",
                        "market": m["question"],
                        "token_id": m.get("id"),
                        "slug": m.get("slug"),
                        "outcome": outcome,
                        "probability": pct,
                        "days_left": days_left,
                        "volume": volume,
                        "suggested_amount": round(min(capital_usd * 0.1, 1), 2),
                        "risk": "medium",
                        "note": "需要结合新闻/信息判断方向",
                    })

    return opportunities[:5]


# ─── 风控系统 ───

def check_risk_limits(portfolio, new_trade_amount, config=None):
    """检查风控限制"""
    if config is None:
        config = load_trading_config()

    limits = config.get("risk_limits", {})
    max_single_bet = limits.get("max_single_bet_usd", 2)
    max_total_exposure = limits.get("max_total_exposure_usd", 10)
    max_positions = limits.get("max_positions", 5)
    max_loss_pct = limits.get("max_daily_loss_pct", 20)

    current_exposure = sum(
        p.get("amount", 0) for p in portfolio.get("positions", [])
        if p.get("status") == "open"
    )

    errors = []

    if new_trade_amount > max_single_bet:
        errors.append(f"单笔下注 ${new_trade_amount} 超过限制 ${max_single_bet}")

    if current_exposure + new_trade_amount > max_total_exposure:
        errors.append(f"总敞口将达 ${current_exposure + new_trade_amount}，超过限制 ${max_total_exposure}")

    open_positions = len([p for p in portfolio.get("positions", []) if p.get("status") == "open"])
    if open_positions >= max_positions:
        errors.append(f"持仓数 {open_positions} 已达上限 {max_positions}")

    return {"ok": len(errors) == 0, "errors": errors}


def load_trading_config():
    """加载交易配置"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    # 默认配置
    default = {
        "capital_usd": 3,
        "mode": "paper",  # paper = 模拟, live = 实盘
        "risk_limits": {
            "max_single_bet_usd": 2,
            "max_total_exposure_usd": 10,
            "max_positions": 5,
            "max_daily_loss_pct": 20,
            "stop_loss_pct": 30,
            "take_profit_pct": 50,
        },
        "strategies": {
            "high_certainty": {"enabled": True, "capital_pct": 50},
            "arbitrage": {"enabled": True, "capital_pct": 30},
            "event_driven": {"enabled": True, "capital_pct": 20},
            "momentum": {"enabled": False, "capital_pct": 0},
        },
        "auto_trade": False,  # 自动交易开关（需要你明确开启）
    }
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(default, f, indent=2)
    return default


# ─── 执行交易 ───

def execute_trade(client, token_id, side, amount_usd, price=None):
    """
    执行交易
    side: "BUY" or "SELL"
    amount_usd: 下注金额
    price: 限价（None = 市价）
    """
    from py_clob_client.clob_types import MarketOrderArgs, OrderArgs, OrderType
    from py_clob_client.order_builder.constants import BUY, SELL

    side_const = BUY if side == "BUY" else SELL

    try:
        if price is None:
            # 市价单
            mo = MarketOrderArgs(
                token_id=token_id,
                amount=amount_usd,
                side=side_const,
                order_type=OrderType.FOK,
            )
            signed = client.create_market_order(mo)
            resp = client.post_order(signed, OrderType.FOK)
        else:
            # 限价单
            size = amount_usd / price
            order = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=side_const,
            )
            signed = client.create_order(order)
            resp = client.post_order(signed, OrderType.GTC)

        return {"success": True, "response": resp}
    except Exception as e:
        return {"success": False, "error": str(e)}


def paper_trade(token_id, side, amount_usd, price, market_info):
    """模拟交易（不实际下单）"""
    trade = {
        "type": "paper",
        "token_id": token_id,
        "side": side,
        "amount_usd": amount_usd,
        "price": price,
        "market": market_info.get("question", ""),
        "outcome": market_info.get("outcome", ""),
        "status": "filled",
    }
    log_trade(trade)

    # 更新模拟持仓
    portfolio = load_portfolio()
    portfolio["positions"].append({
        "token_id": token_id,
        "market": market_info.get("question", ""),
        "outcome": market_info.get("outcome", ""),
        "side": side,
        "entry_price": price,
        "amount_usd": amount_usd,
        "shares": round(amount_usd / price, 4) if price > 0 else 0,
        "status": "open",
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "strategy": market_info.get("strategy", ""),
    })
    portfolio["total_invested"] += amount_usd
    save_portfolio(portfolio)

    return trade


# ─── 主流程 ───

def scan_and_recommend(capital_usd=None):
    """扫描市场并生成推荐"""
    from fetcher import get_top_markets, get_fed_markets, get_ai_markets

    config = load_trading_config()
    if capital_usd is None:
        capital_usd = config.get("capital_usd", 3)

    print(f"📊 扫描 Polymarket 市场... (本金: ${capital_usd})")

    # 获取市场数据
    markets = get_top_markets(limit=100)
    print(f"  获取到 {len(markets)} 个活跃市场")

    # 运行各策略
    results = {}

    if config["strategies"]["high_certainty"]["enabled"]:
        hc = strategy_high_certainty(markets, capital_usd)
        results["high_certainty"] = hc
        print(f"  高确定性策略: {len(hc)} 个机会")

    if config["strategies"]["arbitrage"]["enabled"]:
        arb = strategy_arbitrage(markets, capital_usd)
        results["arbitrage"] = arb
        print(f"  套利策略: {len(arb)} 个机会")

    if config["strategies"]["event_driven"]["enabled"]:
        ed = strategy_event_driven(markets, capital_usd)
        results["event_driven"] = ed
        print(f"  事件驱动策略: {len(ed)} 个机会")

    return results


def format_recommendations(results):
    """格式化推荐报告"""
    lines = [
        f"🎯 Polymarket 交易推荐 | {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    # 套利机会（最优先）
    arb = results.get("arbitrage", [])
    if arb:
        lines.append("━━━ 🔒 无风险套利 ━━━")
        for i, o in enumerate(arb, 1):
            lines.append(f"{i}. {o['market'][:50]}")
            lines.append(f"   Yes: {o['yes_price']:.2f} + No: {o['no_price']:.2f} = {o['total_cost']:.4f}")
            lines.append(f"   利润: {o['profit_pct']:.1f}% | 建议: ${o['suggested_amount']}")
            lines.append("")

    # 高确定性
    hc = results.get("high_certainty", [])
    if hc:
        lines.append("━━━ 💎 高确定性 ━━━")
        for i, o in enumerate(hc[:5], 1):
            lines.append(f"{i}. {o['market'][:50]}")
            lines.append(f"   {o['outcome']}: {o['probability']}% | 收益: {o['potential_return_pct']}%")
            lines.append(f"   剩余: {o['days_left']}天 | 建议: ${o['suggested_amount']}")
            lines.append("")

    # 事件驱动
    ed = results.get("event_driven", [])
    if ed:
        lines.append("━━━ 🎲 事件驱动 (需人工判断) ━━━")
        for i, o in enumerate(ed[:3], 1):
            lines.append(f"{i}. {o['market'][:50]}")
            lines.append(f"   {o['outcome']}: {o['probability']}% | {o['days_left']}天")
            lines.append(f"   交易量: ${o['volume']:,.0f} | {o.get('note', '')}")
            lines.append("")

    if not any([arb, hc, ed]):
        lines.append("今日暂无合适的交易机会，继续观察。")

    return "\n".join(lines)


def get_portfolio_summary():
    """获取持仓摘要"""
    portfolio = load_portfolio()
    positions = portfolio.get("positions", [])
    open_pos = [p for p in positions if p.get("status") == "open"]
    closed_pos = [p for p in positions if p.get("status") == "closed"]

    total_invested = sum(p.get("amount_usd", 0) for p in open_pos)
    realized_pnl = portfolio.get("total_realized_pnl", 0)

    lines = [
        f"📈 持仓概览 | {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"持仓数: {len(open_pos)} | 已平仓: {len(closed_pos)}",
        f"在投资金: ${total_invested:.2f}",
        f"已实现盈亏: ${realized_pnl:+.2f}",
        "",
    ]

    if open_pos:
        lines.append("━━━ 当前持仓 ━━━")
        for p in open_pos:
            lines.append(f"• {p['market'][:40]}")
            lines.append(f"  {p['outcome']} @ {p['entry_price']:.2f} | ${p['amount_usd']:.2f}")
            lines.append(f"  策略: {p.get('strategy', 'N/A')} | 开仓: {p.get('opened_at', '')[:10]}")
            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Polymarket Trader")
    parser.add_argument("action", choices=["scan", "portfolio", "config"],
                        help="scan=扫描推荐, portfolio=查看持仓, config=查看配置")
    parser.add_argument("--capital", type=float, default=None)
    args = parser.parse_args()

    if args.action == "scan":
        results = scan_and_recommend(args.capital)
        print("\n" + format_recommendations(results))
    elif args.action == "portfolio":
        print(get_portfolio_summary())
    elif args.action == "config":
        config = load_trading_config()
        print(json.dumps(config, indent=2))
