#!/usr/bin/env python3
"""
Polymatrix 每日推送脚本
抓取数据 -> 分析机会 -> 推送到 Telegram DailyNews 群
"""

import sys
import subprocess
import json
import os

# 添加 scripts 路径
sys.path.insert(0, "/home/aa/clawd/skills/polymarket-profit/scripts")
from analyzer import rank_opportunities, format_daily_report
from fetcher import get_top_markets

def get_telegram_token():
    """获取 Telegram Bot Token"""
    result = subprocess.run(
        ['pass', 'show', 'tokens/telegram-newsrobot'],
        capture_output=True, text=True
    )
    return result.stdout.strip()

def send_telegram(text):
    """发送到 Telegram DailyNews 群"""
    token = get_telegram_token()
    chat_id = -1003824568687  # DailyNews 群
    
    import urllib.request
    import urllib.parse
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }).encode('utf-8')
    
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                print("✅ 推送成功")
                return True
    except Exception as e:
        print(f"❌ 推送失败: {e}")
    
    return False

def main():
    """主函数"""
    print("🔍 Polymatrix 每日分析开始...")
    
    # 1. 获取市场数据
    print("  - 获取 Polymarket 数据...")
    markets = get_top_markets(limit=50)
    print(f"  - 获取到 {len(markets)} 个活跃市场")
    
    # 2. 分析低风险机会
    print("  - 分析低风险机会...")
    opportunities = []
    for m in markets:
        outcomes = m.get('outcomes', {})
        if 'No' in outcomes or 'no' in outcomes:
            no_pct = outcomes.get('No') or outcomes.get('no', 0)
            if no_pct >= 80 and no_pct < 100:
                potential_return = round(100 / (100 - no_pct) - 1, 2) * 100
                if potential_return >= 15:
                    opportunities.append({
                        'strategy': 'high_certainty_no',
                        'market': m['question'],
                        'slug': m['slug'],
                        'no_probability': no_pct,
                        'expected_return': potential_return,
                        'reason': '短期内不太可能发生',
                        'risk': 'low',
                        'max_bet': min(3 * 0.3, 1),
                    })
    
    # 3. 综合评分
    print("  - 综合评分...")
    low_risk = [o for o in opportunities if o.get('risk') == 'low']
    low_risk.sort(key=lambda x: x.get('expected_return', 0), reverse=True)
    rankings = {'conservative': low_risk[:3], 'moderate': [], 'aggressive': []}
    
    # 4. 生成报告
    print("  - 生成报告...")
    report = format_daily_report(rankings, capital_usd=3)
    print("\n" + report)
    
    # 5. 推送到 Telegram
    print("\n  - 推送到 Telegram...")
    success = send_telegram(report)
    
    # 6. 保存报告
    report_dir = "/home/aa/clawd/skills/polymarket-profit/data/reports"
    os.makedirs(report_dir, exist_ok=True)
    from datetime import datetime
    report_file = f"{report_dir}/daily_{datetime.now().strftime('%Y%m%d')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"  - 报告已保存: {report_file}")
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
