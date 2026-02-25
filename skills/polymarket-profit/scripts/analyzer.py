#!/usr/bin/env python3
"""
Polymarket 机会分析模块
基于多源数据识别高盈利机会
"""

import sys
sys.path.insert(0, "/home/aa/clawd/skills/polymarket-profit/scripts")

from fetcher import get_top_markets
import json
from datetime import datetime

def analyze_low_risk_opportunities(markets, capital_usd=3):
    """分析低风险机会（适合本金 < $5）"""
    opportunities = []
    
    for m in markets:
        # 策略1: 高确定性 No（短期内不太可能发生）
        outcomes = m.get('outcomes', {})
        if 'No' in outcomes or 'no' in outcomes:
            no_pct = outcomes.get('No') or outcomes.get('no', 0)
            if no_pct >= 80:  # No 概率 >= 80%
                # 防止除零：No >= 99.5% 时，收益封顶 200%
                diff = 100 - no_pct
                if diff < 0.5:
                    potential_return = 200  # 封顶高收益
                else:
                    potential_return = round(100 / diff - 1, 2) * 100
                if potential_return >= 15:  # 期望收益 >= 15%
                    opportunities.append({
                        'strategy': 'high_certainty_no',
                        'market': m['question'],
                        'slug': m['slug'],
                        'no_probability': no_pct,
                        'expected_return': potential_return,
                        'reason': '短期内不太可能发生',
                        'risk': 'low',
                        'max_bet': min(capital_usd * 0.3, 1),  # 最多 30% 本金或 $1
                    })
        
        # 策略2: 流动性做市（本金 $3 太小，跳过）
        # 策略3: Holding Rewards（需要 $100+ 本金，跳过）
    
    return opportunities[:5]  # 返回 top 5

def analyze_cme_arbitrage(markets):
    """分析 CME FedWatch 套利机会"""
    # 这里需要抓取 CME FedWatch 数据进行对比
    # 暂时返回空列表，后续可以用 web_fetch 实现
    return []

def analyze_odds_swing(markets):
    """分析赔率波动机会（适合中风险）"""
    opportunities = []
    
    for m in markets:
        days_left = m.get('days_left')
        if days_left and days_left <= 7:  # 7天内结算
            volume = m.get('volume', 0)
            if volume > 100000:  # 高流动性
                opportunities.append({
                    'strategy': 'odds_swing',
                    'market': m['question'],
                    'slug': m['slug'],
                    'days_left': days_left,
                    'volume': volume,
                    'reason': f'即将结算（{days_left}天），高流动性',
                    'risk': 'medium',
                })
    
    return opportunities[:3]

def rank_opportunities(opportunities, capital_usd=3):
    """综合评分并排序机会"""
    # 本金 $3 只考虑低风险
    low_risk = [o for o in opportunities if o.get('risk') == 'low']
    
    # 按期望收益排序
    low_risk.sort(key=lambda x: x.get('expected_return', 0), reverse=True)
    
    return {
        'conservative': low_risk[:3],  # 保守策略 top 3
        'moderate': [],  # 本金 $3 不推荐中风险
        'aggressive': [],  # 本金 $3 不推荐高风险
    }

def format_daily_report(rankings, capital_usd=3):
    """格式化每日报告"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    lines = [
        f"📊 Polymatrix 每日机会 | {date_str}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"💰 **低风险机会**（本金 ${capital_usd}）",
        "",
    ]
    
    conservative = rankings.get('conservative', [])
    if conservative:
        for i, opp in enumerate(conservative, 1):
            lines.append(f"{i}. {opp['market'][:60]}")
            lines.append(f"   当前 No: {opp['no_probability']}% | 收益: {opp['expected_return']:.0f}%")
            lines.append(f"   理由: {opp['reason']}")
            lines.append(f"   建议下注: ${opp['max_bet']:.2f}")
            lines.append("")
    else:
        lines.append("今日暂无合适的低风险机会")
        lines.append("")
    
    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "⚠️ **风险提示**",
        "- 预测有风险，下注需谨慎",
        "- 本金 $3，分散下注",
        "- 仅用能承受损失的资金",
        "",
        f"📊 数据来源: Polymarket + CME FedWatch",
        f"🕐 生成时间: {datetime.now().strftime('%H:%M')}",
    ])
    
    return "\n".join(lines)

if __name__ == "__main__":
    # 获取热门市场
    print("正在获取 Polymarket 数据...")
    markets = get_top_markets(limit=50)
    print(f"获取到 {len(markets)} 个活跃市场")
    
    # 分析机会
    low_risk = analyze_low_risk_opportunities(markets)
    odds_swing = analyze_odds_swing(markets)
    
    # 综合评分
    rankings = rank_opportunities(low_risk + odds_swing)
    
    # 生成报告
    report = format_daily_report(rankings)
    print("\n" + report)
    
    # 保存报告
    report_dir = "/home/aa/clawd/skills/polymarket-profit/data/reports"
    import os
    os.makedirs(report_dir, exist_ok=True)
    report_file = f"{report_dir}/daily_{datetime.now().strftime('%Y%m%d')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n报告已保存: {report_file}")
