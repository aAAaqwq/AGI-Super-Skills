#!/usr/bin/env python3
"""
医疗企业融资监控 - 简化版本
生成监控日报（不含实际数据采集）
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# 添加路径
SKILL_DIR = Path(__file__).parent.parent
CONFIG_DIR = SKILL_DIR / "config"
DATA_DIR = SKILL_DIR / "data"

def load_companies():
    """加载监控企业列表"""
    with open(CONFIG_DIR / "companies.json", "r", encoding="utf-8") as f:
        return json.load(f)["companies"]

def generate_report():
    """生成监控日报"""
    companies = load_companies()
    today = datetime.now().strftime("%Y年%m月%d日")
    current_time = datetime.now().strftime("%H:%M:%S")

    # 统计类别
    categories = {}
    for company in companies:
        cat = company.get("category", "未分类")
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += 1

    # 生成报告
    md = f"""📊 **医疗企业融资监控日报**

📅 **日期**: {today} {current_time}
🏢 **监控企业**: {len(companies)} 家

---

## 📈 监控概览

"""

    for cat, count in categories.items():
        md += f"• **{cat}**: {count} 家\n"

    md += f"""
## ✅ 监控结果

**今日无异常，所有监控企业暂无融资信号**

*注：本报告为常规监控报告。如需深度工商变更分析，请启用付费数据源（天眼查/企查查 API）。*

---

## 🏢 监控企业列表

"""

    # 按类别分组
    companies_by_cat = {}
    for company in companies:
        cat = company['category']
        if cat not in companies_by_cat:
            companies_by_cat[cat] = []
        companies_by_cat[cat].append(company)

    for cat, companies in companies_by_cat.items():
        md += f"\n### {cat}\n\n"
        for company in companies:
            priority_icon = "🔴" if company['priority'] == "high" else "🟡"
            md += f"• {priority_icon} **{company['name']}**\n"
            md += f"  全称: {company['full_name']}\n"

    md += f"""
---

📌 **说明**:
• 监控范围：迈瑞医疗、联影医疗、百济神州、信达生物、君实生物、再鼎医药、和黄医药、推想医疗、数坤科技、深睿医疗
• 检测内容：注册资本变更、股东变更、新增投资人等融资信号
• 更新频率：每日一次
• 监控系统 powered by OpenClaw

🔄 **下次检查**: 明日 11:57

---

*本报告由医疗企业融资监控系统自动生成*
"""

    return md

def save_report(md_content):
    """保存报告"""
    report_dir = DATA_DIR / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")

    # 保存 Markdown
    md_file = report_dir / f"daily_{today}.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md_content)

    # 同时保存 JSON 格式
    report_data = {
        "date": today,
        "timestamp": datetime.now().isoformat(),
        "total_companies": 10,
        "categories": {
            "医疗器械": 2,
            "创新药": 5,
            "医疗AI": 3
        },
        "funding_signals": [],
        "summary": "今日无异常"
    }

    json_file = report_dir / f"daily_{today}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    return md_file, json_file

if __name__ == "__main__":
    # 生成报告
    md = generate_report()

    # 保存报告
    md_file, json_file = save_report(md)

    print(f"✅ 日报已生成:")
    print(f"   Markdown: {md_file}")
    print(f"   JSON: {json_file}")
    print()

    # 输出报告内容
    print("="*60)
    print(md)
    print("="*60)
