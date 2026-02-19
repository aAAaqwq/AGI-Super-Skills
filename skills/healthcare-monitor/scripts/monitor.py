#!/usr/bin/env python3
"""
医疗企业融资监控系统
检查监控企业的工商变更，识别融资信号
"""

import json
import os
from datetime import datetime
from pathlib import Path
import sys

# 路径配置
SKILL_DIR = Path(__file__).parent.parent
CONFIG_DIR = SKILL_DIR / "config"
DATA_DIR = SKILL_DIR / "data"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
CHANGES_DIR = DATA_DIR / "changes"

def load_companies():
    """加载监控企业列表"""
    companies_file = CONFIG_DIR / "companies.json"
    with open(companies_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    all_companies = []
    for priority in ['priority_high', 'priority_normal', 'priority_low']:
        if priority in data:
            all_companies.extend(data[priority])

    return all_companies

def load_snapshot(company_name):
    """加载企业上次快照"""
    snapshot_file = SNAPSHOTS_DIR / f"{company_name}.json"
    if snapshot_file.exists():
        with open(snapshot_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def save_snapshot(company_name, data):
    """保存企业快照"""
    snapshot_file = SNAPSHOTS_DIR / f"{company_name}.json"
    with open(snapshot_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_change_record(company_name, change_data):
    """保存变更记录"""
    changes_file = CHANGES_DIR / f"{company_name}_changes.jsonl"
    with open(changes_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(change_data, ensure_ascii=False) + '\n')

def analyze_funding_signals(company_name, old_data, new_data):
    """
    分析融资信号
    返回: (置信度, 信号列表)
    """
    signals = []
    confidence = 0

    if not old_data:
        # 首次监控，无对比
        return 0, [{"type": "initial", "strength": "info", "detail": "首次监控，建立基线"}]

    # 1. 检查注册资本变更
    old_cap = old_data.get('registered_capital', '')
    new_cap = new_data.get('registered_capital', '')

    if old_cap and new_cap and old_cap != new_cap:
        # 提取数字进行比较
        def extract_amount(cap_str):
            import re
            match = re.search(r'([\d.]+)', str(cap_str).replace(',', ''))
            return float(match.group(1)) if match else 0

        old_amount = extract_amount(old_cap)
        new_amount = extract_amount(new_cap)

        if old_amount > 0 and new_amount > old_amount:
            change_percent = ((new_amount - old_amount) / old_amount) * 100
            if change_percent > 10:
                confidence += 30
                signals.append({
                    'type': 'capital_increase',
                    'strength': 'strong',
                    'detail': f'注册资本增加: {old_cap} → {new_cap} (+{change_percent:.1f}%)'
                })
            else:
                confidence += 10
                signals.append({
                    'type': 'capital_increase',
                    'strength': 'weak',
                    'detail': f'注册资本小幅增加: {old_cap} → {new_cap}'
                })

    # 2. 检查股东变更
    old_shareholders = old_data.get('shareholders', [])
    new_shareholders = new_data.get('shareholders', [])

    old_sh_names = {s.get('name', '') for s in old_shareholders}
    new_sh_names = {s.get('name', '') for s in new_shareholders}

    added_shareholders = new_sh_names - old_sh_names

    if added_shareholders:
        for sh in added_shareholders:
            # 检查是否为机构投资者
            if any(keyword in sh for keyword in ['投资', '资本', '基金', '创投', '资产', '合伙']):
                confidence += 40
                signals.append({
                    'type': 'new_institutional_shareholder',
                    'strength': 'strong',
                    'detail': f'新增机构股东: {sh}'
                })
            else:
                confidence += 15
                signals.append({
                    'type': 'new_shareholder',
                    'strength': 'medium',
                    'detail': f'新增股东: {sh}'
                })

    # 3. 检查法人变更
    if old_data.get('legal_person') != new_data.get('legal_person'):
        confidence += 5
        signals.append({
            'type': 'legal_person_change',
            'strength': 'weak',
            'detail': f'法人变更: {old_data.get("legal_person")} → {new_data.get("legal_person")}'
        })

    # 4. 检查经营范围变更
    old_scope = old_data.get('business_scope', '')
    new_scope = new_data.get('business_scope', '')

    if old_scope and new_scope and len(new_scope) > len(old_scope):
        confidence += 10
        signals.append({
            'type': 'business_scope_expand',
            'strength': 'weak',
            'detail': '经营范围扩大'
        })

    return min(confidence, 100), signals

def fetch_company_data_tianyancha(company_name):
    """
    从天眼查获取企业数据
    注意: 当前无API权限，返回模拟数据
    """
    # TODO: 实现真实的天眼查爬虫或API调用
    # 当前返回模拟数据用于演示

    return {
        "company_name": company_name,
        "registered_capital": "10000万人民币",
        "legal_person": "示例法人",
        "establish_date": "2010-01-01",
        "business_scope": "医疗器械研发、生产、销售",
        "shareholders": [
            {"name": "创始股东A", "ratio": "60%"},
            {"name": "创始股东B", "ratio": "40%"}
        ],
        "status": "在业",
        "fetch_time": datetime.now().isoformat()
    }

def estimate_funding_round(company_name, signals, confidence):
    """估算融资轮次"""
    if confidence < 50:
        return "未知"

    # 检查是否有机构股东
    has_inst = any(s['type'] == 'new_institutional_shareholder' for s in signals)

    if has_inst:
        return "A轮或后续"
    else:
        return "天使轮/种子轮"

def format_report(results, total_companies):
    """格式化监控报告"""
    high_confidence = sum(1 for r in results if r['confidence'] >= 70)
    medium_confidence = sum(1 for r in results if 50 <= r['confidence'] < 70)
    total_signals = len([r for r in results if r['signals']])

    report_lines = [
        f"🏥 医疗融资监控 [{datetime.now().strftime('%H:%M')}]",
        f"检查企业: {total_companies}家",
        f"融资信号: {total_signals}条 (高置信: {high_confidence}, 中置信: {medium_confidence})",
        ""
    ]

    if total_signals > 0:
        for result in sorted(results, key=lambda x: x['confidence'], reverse=True):
            if result['signals']:
                conf_emoji = "🔴" if result['confidence'] >= 70 else "🟡" if result['confidence'] >= 50 else "🟢"
                report_lines.append(f"{conf_emoji} **{result['company']}** (置信度: {result['confidence']}%)")

                for signal in result['signals']:
                    report_lines.append(f"  • {signal['detail']}")

                round_estimate = estimate_funding_round(result['company'], result['signals'], result['confidence'])
                report_lines.append(f"  💡 估算: {round_estimate}")
                report_lines.append("")
    else:
        report_lines.append("✅ 未发现融资信号")
        report_lines.append("")
        report_lines.append("监控状态: 正常运行")

    return "\n".join(report_lines)

def main():
    """主函数"""
    print(f"开始执行医疗企业融资监控...")

    # 确保目录存在
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    CHANGES_DIR.mkdir(parents=True, exist_ok=True)

    # 加载监控企业
    companies = load_companies()
    print(f"加载企业列表: {len(companies)}家")

    results = []

    for company in companies:
        company_name = company['name']
        industry = company['industry']
        focus = company.get('focus', '')

        print(f"检查: {company_name} ({industry})")

        # 获取当前数据
        current_data = fetch_company_data_tianyancha(company_name)

        # 加载历史快照
        old_snapshot = load_snapshot(company_name)

        # 分析变化
        confidence, signals = analyze_funding_signals(company_name, old_snapshot, current_data)

        # 保存结果
        result = {
            'company': company_name,
            'industry': industry,
            'confidence': confidence,
            'signals': signals,
            'check_time': datetime.now().isoformat()
        }
        results.append(result)

        # 保存快照
        save_snapshot(company_name, current_data)

        # 如果有变化，保存变更记录
        if signals and any(s['type'] != 'initial' for s in signals):
            change_record = {
                'company_name': company_name,
                'confidence': confidence,
                'signals': signals,
                'timestamp': datetime.now().isoformat()
            }
            save_change_record(company_name, change_record)

    # 生成报告
    report = format_report(results, len(companies))

    # 保存报告
    report_file = DATA_DIR / "reports" / f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print("\n" + "="*50)
    print(report)
    print("="*50)

    # 返回报告用于推送
    return report

if __name__ == "__main__":
    main()
