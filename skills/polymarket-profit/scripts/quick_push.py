#!/usr/bin/env python3
"""
Polymatrix 简化版 - 每日快速赚钱机会
专注于能立即执行的简单方案
"""

import json
import urllib.request
from datetime import datetime
import subprocess

# ==================== 快速机会（5分钟内可执行）================

def get_quick_opportunities():
    """获取快速执行的赚钱机会"""
    opportunities = []
    
    # 1. Aave USDC 存款（最简单）
    opportunities.append({
        "name": "Aave USDC 稳定收益",
        "difficulty": "⭐ 极简",
        "time": "2 分钟",
        "steps": [
            "1. 打开 https://app.aave.com",
            "2. 连接钱包 (MetaMask)",
            "3. 存入 USDC",
            "4. 完成！自动赚取 6-8% APY"
        ],
        "apy": "6-8%",
        "risk": "低",
        "min_capital": "$10",
        "url": "https://app.aave.com"
    })
    
    # 2. Lido ETH 质押
    opportunities.append({
        "name": "Lido ETH 质押",
        "difficulty": "⭐ 极简",
        "time": "3 分钟",
        "steps": [
            "1. 打开 https://stake.lido.fi",
            "2. 连接钱包",
            "3. 质押 ETH",
            "4. 获得 stETH，自动赚取 4-5%"
        ],
        "apy": "4-5%",
        "risk": "低",
        "min_capital": "0.01 ETH",
        "url": "https://stake.lido.fi"
    })
    
    # 3. Layer3 任务（免费）
    opportunities.append({
        "name": "Layer3 完成任务",
        "difficulty": "⭐ 极简",
        "time": "5 分钟",
        "steps": [
            "1. 打开 https://layer3.xyz",
            "2. 创建智能钱包（免费）",
            "3. 完成 1-2 个简单任务",
            "4. 赚取 CUBEs 积分"
        ],
        "apy": "不确定（可能空投）",
        "risk": "极低",
        "min_capital": "$0",
        "url": "https://layer3.xyz"
    })
    
    # 4. Polymarket 高确定性 No
    try:
        url = "https://gamma-api.polymarket.com/markets?limit=20&active=true&closed=false&order=volumeNum&ascending=false"
        req = urllib.request.Request(url, headers={"User-Agent": "PolyMatrix/Quick"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            markets = json.loads(resp.read().decode())
        
        for m in markets[:20]:
            outcomes = json.loads(m.get("outcomePrices", "[]")) if isinstance(m.get("outcomePrices"), str) else m.get("outcomePrices", [])
            if len(outcomes) >= 2:
                no_pct = round(outcomes[1] * 100, 1)
                if 85 <= no_pct < 95:
                    potential = round(100 / (100 - no_pct) - 1, 2) * 100
                    if potential >= 20:
                        opportunities.append({
                            "name": f"Polymarket: {m['question'][:40]}...",
                            "difficulty": "⭐ 简单",
                            "time": "3 分钟",
                            "steps": [
                                f"1. 打开 Polymarket",
                                f"2. 搜索事件或点击链接",
                                f"3. 买 No (当前 {no_pct}%)",
                                f"4. 等待结算"
                            ],
                            "apy": f"{potential:.0f}% 期望",
                            "risk": "低",
                            "min_capital": "$1",
                            "url": f"https://polymarket.com/event/{m.get('slug', '')}"
                        })
                        break
    except:
        pass
    
    return opportunities[:5]

# ==================== 格式化推送 ====================

def format_quick_report(opportunities, period="早报"):
    """格式化快速报告"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H:%M")
    
    lines = [
        f"💰 {period} | {date_str}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"🚀 **5 分钟快速赚钱方案**",
        "",
    ]
    
    for i, opp in enumerate(opportunities, 1):
        lines.append(f"{i}. **{opp['name']}**")
        lines.append(f"   难度: {opp['difficulty']} | 时间: {opp['time']}")
        lines.append(f"   收益: {opp.get('apy', 'N/A')} | 风险: {opp['risk']}")
        lines.append(f"   最少本金: {opp['min_capital']}")
        lines.append(f"   链接: {opp['url']}")
        lines.append("")
        
        # 显示步骤
        lines.append("   📝 操作步骤:")
        for step in opp['steps'][:4]:
            lines.append(f"   {step}")
        lines.append("")
    
    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "💡 **新手推荐**",
        "",
        "1. **极低风险**: Aave USDC (6-8% APY)",
        "   - 本金 $10 起步",
        "   - 2 分钟完成",
        "   - 稳定收益，随时可取",
        "",
        "2. **零成本**: Layer3 任务",
        "   - 完全免费",
        "   - 5 分钟完成",
        "   - 可能空投",
        "",
        "⚠️ **风险提示**",
        "- 所有投资有风险",
        "- 只用能承受损失的资金",
        "- DYOR（自己研究）",
        "",
        f"🕐 生成时间: {time_str}",
    ])
    
    return "\n".join(lines)

# ==================== 推送 ====================

def send_telegram(text):
    """发送到 Telegram"""
    token = subprocess.check_output(['pass', 'show', 'tokens/telegram-newsrobot'], text=True).strip()
    chat_id = -1003824568687
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text}).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                print("✅ 推送成功")
                return True
    except Exception as e:
        print(f"❌ 推送失败: {e}")
    
    return False

# ==================== 主函数 ====================

def main():
    import os
    
    # 获取当前时间判断早报/晚报
    hour = datetime.now().hour
    if hour < 12:
        period = "早报"
    else:
        period = "晚报"
    
    print(f"💰 Polymatrix {period}生成...")
    
    # 获取快速机会
    opportunities = get_quick_opportunities()
    
    # 格式化报告
    report = format_quick_report(opportunities, period)
    print("\n" + report)
    
    # 推送
    success = send_telegram(report)
    
    # 保存
    report_dir = "/home/aa/clawd/skills/polymarket-profit/data/reports"
    os.makedirs(report_dir, exist_ok=True)
    period_key = "morning" if period == "早报" else "evening"
    report_file = f"{report_dir}/quick_{period_key}_{datetime.now().strftime('%Y%m%d')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"✅ 报告已保存: {report_file}")
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
