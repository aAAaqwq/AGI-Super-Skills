#!/usr/bin/env python3
"""
Polymarket 每日报告推送
推送到 DailyNews 群，包含持仓、盈亏、胜率等
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path("/home/aa/clawd/skills/polymarket-profit/data")
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"
TRADE_LOG_FILE = DATA_DIR / "trade_log.json"

# Telegram 推送配置
DAILYNEWS_CHAT_ID = "-1003824568687"
BOT_TOKEN_CMD = ["pass", "show", "api/telegram-xiaom-bot"]


def load_json(path):
    if path.exists():
        with open(path, 'r') as f:
            return json.load(f)
    return None


def get_portfolio():
    return load_json(PORTFOLIO_FILE) or {
        "positions": [],
        "total_invested": 0,
        "total_realized_pnl": 0,
        "mode": "live",
        "capital": 3.0
    }


def get_trade_log():
    return load_json(TRADE_LOG_FILE) or []


def calculate_stats(trade_log, portfolio):
    """计算统计数据"""
    total_trades = len([t for t in trade_log if t.get("status") == "filled"])
    winning_trades = len([t for t in trade_log if t.get("status") == "filled" and t.get("realized_pnl", 0) > 0])
    losing_trades = len([t for t in trade_log if t.get("status") == "filled" and t.get("realized_pnl", 0) < 0])
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    total_pnl = portfolio.get("total_realized_pnl", 0)
    unrealized_pnl = sum(
        p.get("unrealized_pnl", 0) 
        for p in portfolio.get("positions", []) 
        if p.get("status") == "open"
    )
    
    return {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "unrealized_pnl": unrealized_pnl,
        "total_pnl": total_pnl + unrealized_pnl
    }


def format_position(pos):
    """格式化持仓信息"""
    status_emoji = "🟢" if pos.get("status") == "open" else "🔴"
    outcome = pos.get("outcome", "N/A")
    amount = pos.get("amount_usd", 0)
    entry = pos.get("entry_price", 0)
    market = pos.get("market", pos.get("question", "Unknown"))[:30]
    
    pnl_str = ""
    if "unrealized_pnl" in pos:
        pnl = pos["unrealized_pnl"]
        pnl_emoji = "📈" if pnl >= 0 else "📉"
        pnl_str = f" | {pnl_emoji} ${pnl:+.2f}"
    
    return f"{status_emoji} {market}\n   {outcome} @ {entry:.1f}¢ | ${amount:.2f}{pnl_str}"


def generate_report():
    """生成每日报告"""
    portfolio = get_portfolio()
    trade_log = get_trade_log()
    stats = calculate_stats(trade_log, portfolio)
    
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    lines = [
        f"📊 Polymatrix 每日报告 | {date_str}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "💰 **账户概览**",
        f"• 模式: {portfolio.get('mode', 'live').upper()}",
        f"• 本金: ${portfolio.get('capital', 3.0):.2f}",
        f"• 已投入: ${portfolio.get('total_invested', 0):.2f}",
        f"• 已实现盈亏: ${stats['total_pnl']:+.2f}",
        "",
    ]
    
    # 持仓
    positions = portfolio.get("positions", [])
    open_positions = [p for p in positions if p.get("status") == "open"]
    
    if open_positions:
        lines.append("📈 **当前持仓**")
        for pos in open_positions[:5]:
            lines.append(format_position(pos))
        lines.append("")
    
    # 统计
    lines.extend([
        "📊 **交易统计**",
        f"• 总交易: {stats['total_trades']} 笔",
        f"• 胜/负: {stats['winning_trades']}/{stats['losing_trades']}",
        f"• 胜率: {stats['win_rate']:.1f}%",
        "",
    ])
    
    # 最近交易
    recent_trades = [t for t in trade_log if t.get("status") == "filled"][-3:]
    if recent_trades:
        lines.append("📜 **最近交易**")
        for t in recent_trades:
            side = t.get("side", "BUY")
            market = t.get("market", "Unknown")[:25]
            amount = t.get("amount_usd", 0)
            pnl = t.get("realized_pnl", 0)
            pnl_emoji = "✅" if pnl >= 0 else "❌"
            lines.append(f"• {side} {market} | ${amount:.2f} | {pnl_emoji} ${pnl:+.2f}")
        lines.append("")
    
    # 策略说明
    lines.extend([
        "🎯 **当前策略**",
        "• 高确定性 No (60%仓位)",
        "• CME 套利 (20%仓位)",
        "• 事件驱动 (20%仓位)",
        "",
    ])
    
    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🕐 更新时间: {datetime.now().strftime('%H:%M')}",
    ])
    
    return "\n".join(lines)


def send_to_telegram(message):
    """发送到 Telegram"""
    # 获取 bot token
    result = subprocess.run(BOT_TOKEN_CMD, capture_output=True, text=True)
    bot_token = result.stdout.strip()
    
    if not bot_token:
        print("错误: 无法获取 bot token")
        return False
    
    # 发送消息
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    import urllib.request
    import urllib.parse
    
    # 移除 Markdown 格式，使用纯文本
    plain_message = message.replace("**", "").replace("━", "─")
    
    data = urllib.parse.urlencode({
        "chat_id": DAILYNEWS_CHAT_ID,
        "text": plain_message
    }).encode()
    
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            if result.get("ok"):
                print(f"✅ 推送成功")
                return True
            else:
                print(f"❌ 推送失败: {result}")
                return False
    except Exception as e:
        print(f"❌ 推送异常: {e}")
        return False


def main():
    print("生成 Polymatrix 每日报告...")
    report = generate_report()
    
    print("\n" + report)
    print("\n推送到 DailyNews 群...")
    
    success = send_to_telegram(report)
    
    # 保存报告
    report_dir = DATA_DIR / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / f"daily_{datetime.now().strftime('%Y%m%d')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n报告已保存: {report_file}")
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
