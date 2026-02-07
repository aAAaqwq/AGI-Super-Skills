#!/usr/bin/env python3
"""
医疗企业融资监控 - 日常快速检查
使用 web_search 检查企业最新动态
"""

import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
CONFIG_DIR = SKILL_DIR / "config"
DATA_DIR = SKILL_DIR / "data"

def load_companies():
    """加载监控企业列表"""
    with open(CONFIG_DIR / "companies.json", "r", encoding="utf-8") as f:
        return json.load(f)["companies"]

def generate_daily_report():
    """生成日报"""
    companies = load_companies()
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    report = {
        "date": today,
        "total_companies": len(companies),
        "categories": {},
        "companies_checked": [],
        "funding_signals": [],
        "notes": []
    }

    # 按类别统计
    for company in companies:
        cat = company.get("category", "未分类")
        if cat not in report["categories"]:
            report["categories"][cat] = 0
        report["categories"][cat] += 1

        report["companies_checked"].append({
            "name": company["name"],
            "full_name": company["full_name"],
            "category": cat,
            "priority": company["priority"]
        })

    # 检查快照目录，查看是否有变更
    changes_dir = DATA_DIR / "changes"
    if changes_dir.exists():
        for change_file in changes_dir.glob(f"{yesterday}_*.json"):
            with open(change_file, "r", encoding="utf-8") as f:
                change_data = json.load(f)
                report["funding_signals"].append(change_data)

    # 生成报告
    report_dir = DATA_DIR / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    report_file = report_dir / f"daily_{today}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report

def format_report_markdown(report):
    """格式化为 Markdown 报告"""
    md = f"""# 医疗企业融资监控日报

**日期**: {report['date']}
**监控企业数**: {report['total_companies']} 家

## 📊 监控概览

"""

    # 按类别展示
    for cat, count in report['categories'].items():
        md += f"- **{cat}**: {count} 家\n"

    md += f"""
## 🏢 监控企业列表

"""

    # 按类别分组展示
    companies_by_cat = {}
    for company in report['companies_checked']:
        cat = company['category']
        if cat not in companies_by_cat:
            companies_by_cat[cat] = []
        companies_by_cat[cat].append(company)

    for cat, companies in companies_by_cat.items():
        md += f"\n### {cat}\n\n"
        for company in companies:
            priority_icon = "🔴" if company['priority'] == "high" else "🟡"
            md += f"- {priority_icon} **{company['name']}** ({company['full_name']})\n"

    # 融资信号
    if report['funding_signals']:
        md += f"""
## 🚨 融资信号

发现 {len(report['funding_signals'])} 个融资信号：

"""
        for signal in report['funding_signals']:
            md += f"### {signal['company']}\n"
            md += f"- **置信度**: {signal['analysis']['confidence']}%\n"
            md += f"- **融资轮次**: {signal['analysis'].get('round', '未知')}\n"
            md += f"- **变更内容**: {json.dumps(signal['changes'], ensure_ascii=False)}\n\n"
    else:
        md += """
## 🚨 融资信号

暂无融资信号

"""

    md += f"""
## 📝 说明

- 本报告由医疗企业融资监控系统自动生成
- 监控时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 下次检查: { (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d') }

---
*系统 powered by OpenClaw*
"""

    return md

if __name__ == "__main__":
    # 生成日报
    report = generate_daily_report()

    # 格式化输出
    md = format_report_markdown(report)

    # 保存 Markdown
    report_dir = DATA_DIR / "reports"
    today = datetime.now().strftime("%Y-%m-%d")
    md_file = report_dir / f"daily_{today}.md"

    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md)

    # 输出到标准输出
    print(md)

    # 同时保存 JSON
    print(f"\n✅ 日报已生成: {md_file}", file=sys.stderr)
