#!/usr/bin/env python3
"""
Polymatrix Web3 每日机会分析
涵盖 Polymarket、DeFi、空投、新币等多维度机会
"""

import json
import urllib.request
from datetime import datetime
import subprocess

# ==================== Polymarket 机会 ====================

def get_polymarket_opportunities():
    """获取 Polymarket 机会"""
    opportunities = {
        "low_risk": [],
        "medium_risk": [],
        "high_risk": []
    }
    
    try:
        # 获取热门市场
        url = "https://gamma-api.polymarket.com/markets?limit=30&active=true&closed=false&order=volumeNum&ascending=false"
        req = urllib.request.Request(url, headers={"User-Agent": "PolyMatrix/2.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            markets = json.loads(resp.read().decode())
        
        for m in markets[:30]:
            outcomes = json.loads(m.get("outcomePrices", "[]")) if isinstance(m.get("outcomePrices"), str) else m.get("outcomePrices", [])
            question = m.get("question", "")
            slug = m.get("slug", "")
            volume = m.get("volumeNum", 0)
            
            # 检查 No 概率
            if len(outcomes) >= 2:
                no_pct = round(outcomes[1] * 100, 1) if outcomes[1] else 0
                
                # 低风险：高确定性 No
                if 80 <= no_pct < 99:
                    potential_return = round(100 / (100 - no_pct) - 1, 2) * 100
                    if potential_return >= 15:
                        opportunities["low_risk"].append({
                            "type": "Polymarket 高确定性 No",
                            "title": question[:60],
                            "no_probability": no_pct,
                            "expected_return": f"{potential_return:.0f}%",
                            "url": f"https://polymarket.com/event/{slug}",
                            "max_bet": 0.50
                        })
                
                # 中风险：事件预测（50-80% 概率）
                elif 50 <= no_pct < 80:
                    opportunities["medium_risk"].append({
                        "type": "Polymarket 事件预测",
                        "title": question[:60],
                        "no_probability": no_pct,
                        "volume": volume,
                        "url": f"https://polymarket.com/event/{slug}",
                        "max_bet": 0.30
                    })
    
    except Exception as e:
        print(f"  ⚠️ Polymarket 抓取失败: {e}")
    
    return opportunities

# ==================== DeFi 收益机会 ====================

def get_defi_opportunities():
    """获取 DeFi 收益机会"""
    opportunities = {
        "low_risk": [],
        "medium_risk": []
    }
    
    # Aave USDC（稳定收益）
    opportunities["low_risk"].append({
        "type": "Aave USDC 存款",
        "title": "USDC 稳定收益",
        "apy": "6-8%",
        "platform": "Aave",
        "url": "https://app.aave.com",
        "risk": "低风险",
        "notes": "稳定币存款，赚取利息"
    })
    
    # Lido stETH
    opportunities["low_risk"].append({
        "type": "Lido ETH 质押",
        "title": "ETH 流动性质押",
        "apy": "4-5%",
        "platform": "Lido",
        "url": "https://stake.lido.fi",
        "risk": "低风险",
        "notes": "去中心化 ETH 质押"
    })
    
    # Uniswap LP（中风险）
    opportunities["medium_risk"].append({
        "type": "Uniswap 流动性挖矿",
        "title": "ETH/USDC LP",
        "apy": "15-30%",
        "platform": "Uniswap",
        "url": "https://app.uniswap.org/pools",
        "risk": "中风险（无常损失）",
        "notes": "提供流动性，赚取交易费"
    })
    
    return opportunities

# ==================== 空投机会 ====================

def get_airdrop_opportunities():
    """获取空投机会"""
    opportunities = {
        "medium_risk": []
    }
    
    # Layer3
    opportunities["medium_risk"].append({
        "type": "Layer3 空投狩猎",
        "title": "完成任务赚取 CUBEs",
        "platform": "Layer3",
        "url": "https://layer3.xyz",
        "cost": "<$0.5 (Gas)",
        "expected": "不确定，可能 10-1000%",
        "notes": "每日任务，积分兑换奖励"
    })
    
    # Galxe
    opportunities["medium_risk"].append({
        "type": "Galxe 任务",
        "title": "Web3 任务积分",
        "platform": "Galxe",
        "url": "https://galxe.com",
        "cost": "免费",
        "expected": "不确定",
        "notes": "完成品牌任务赚取 OAT"
    })
    
    return opportunities

# ==================== 新币机会 ====================

def get_new_token_opportunities():
    """获取新币机会（高风险）"""
    opportunities = {
        "high_risk": []
    }
    
    try:
        # DexScreener 新币
        url = "https://api.dexscreener.com/latest/dex/search/?query=WETH"
        req = urllib.request.Request(url, headers={"User-Agent": "PolyMatrix/2.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        
        if data.get("pairs"):
            for pair in data["pairs"][:10]:
                # 只看 24h 内创建的
                age_hours = pair.get("age", 0)
                if age_hours < 24:
                    price_change = pair.get("priceChange", {}).get("h24", 0)
                    if price_change and price_change > 50:  # 24h 涨幅 >50%
                        opportunities["high_risk"].append({
                            "type": "新币狙击",
                            "title": f"{pair.get('baseToken', {}).get('symbol', '')} ({pair.get('dexId', '')})",
                            "price_change_24h": f"{price_change:.0f}%",
                            "liquidity": pair.get("liquidity", {}).get("usd", 0),
                            "url": pair.get("url", ""),
                            "age_hours": age_hours,
                            "risk": "⚠️ 极高风险",
                            "notes": "可能是 Rug Pull，谨慎参与"
                        })
    
    except Exception as e:
        print(f"  ⚠️ DexScreener 抓取失败: {e}")
    
    return opportunities

# ==================== 格式化报告 ====================

def format_daily_report(poly_ops, defi_ops, airdrop_ops, token_ops):
    """格式化每日报告"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H:%M")
    
    lines = [
        f"🚀 Polymatrix Web3 机会 | {date_str}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    
    # 低风险
    if defi_ops.get("low_risk") or poly_ops.get("low_risk"):
        lines.append("💎 **低风险**（本金 $1.5 | 预期 5-20%）")
        lines.append("")
        
        for op in defi_ops.get("low_risk", [])[:2]:
            lines.append(f"1. {op['title']} → {op.get('apy', op.get('expected_return', 'N/A'))}")
            lines.append(f"   平台: {op['platform']} | {op['url']}")
            lines.append("")
        
        for op in poly_ops.get("low_risk", [])[:1]:
            lines.append(f"2. {op['title']}")
            lines.append(f"   No: {op['no_probability']}% | 收益: {op['expected_return']}")
            lines.append(f"   链接: {op['url']}")
            lines.append("")
    
    # 中风险
    if defi_ops.get("medium_risk") or airdrop_ops.get("medium_risk") or poly_ops.get("medium_risk"):
        lines.append("🚀 **中风险**（本金 $1 | 预期 20-100%）")
        lines.append("")
        
        for op in airdrop_ops.get("medium_risk", [])[:2]:
            lines.append(f"1. {op['title']}")
            lines.append(f"   平台: {op['platform']} | {op['url']}")
            lines.append(f"   成本: {op.get('cost', 'N/A')} | 预期: {op.get('expected', 'N/A')}")
            lines.append("")
        
        for op in defi_ops.get("medium_risk", [])[:1]:
            lines.append(f"2. {op['title']}")
            lines.append(f"   APY: {op['apy']} | {op['url']}")
            lines.append("")
    
    # 高风险
    if token_ops.get("high_risk"):
        lines.append("🔥 **高风险**（本金 $0.5 | 预期 100-1000%）")
        lines.append("")
        
        for op in token_ops.get("high_risk", [])[:2]:
            lines.append(f"1. {op['title']}")
            lines.append(f"   24h: {op['price_change_24h']} | 风险: {op['risk']}")
            lines.append(f"   链接: {op['url']}")
            lines.append("")
    
    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "⚠️ **风险提示**",
        "- 高风险可能归零",
        "- 只用能承受损失的资金",
        "- DYOR（自己研究）",
        "",
        f"📊 数据来源: Polymarket + DefiLlama + DexScreener",
        f"🕐 生成时间: {time_str}",
    ])
    
    return "\n".join(lines)

# ==================== 推送到 Telegram ====================

def send_telegram(text):
    """发送到 Telegram DailyNews 群"""
    token = subprocess.check_output(['pass', 'show', 'tokens/telegram-newsrobot'], text=True).strip()
    chat_id = YOUR_NEWS_CHAT_ID
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({
        "chat_id": chat_id,
        "text": text
    }).encode('utf-8')
    
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
    print("🔍 Polymatrix Web3 每日分析开始...")
    
    # 1. Polymarket 机会
    print("  - Polymarket 机会...")
    poly_ops = get_polymarket_opportunities()
    
    # 2. DeFi 收益
    print("  - DeFi 收益机会...")
    defi_ops = get_defi_opportunities()
    
    # 3. 空投机会
    print("  - 空投机会...")
    airdrop_ops = get_airdrop_opportunities()
    
    # 4. 新币机会
    print("  - 新币机会...")
    token_ops = get_new_token_opportunities()
    
    # 5. 生成报告
    print("  - 生成报告...")
    report = format_daily_report(poly_ops, defi_ops, airdrop_ops, token_ops)
    print("\n" + report)
    
    # 6. 推送
    print("\n  - 推送到 Telegram...")
    success = send_telegram(report)
    
    # 7. 保存
    import os
    report_dir = "/home/aa/clawd/skills/polymarket-profit/data/reports"
    os.makedirs(report_dir, exist_ok=True)
    report_file = f"{report_dir}/web3_{datetime.now().strftime('%Y%m%d')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"  - 报告已保存: {report_file}")
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
