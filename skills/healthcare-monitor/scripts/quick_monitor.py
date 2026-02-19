#!/usr/bin/env python3
"""
医疗企业融资监控 - 快速检查版本
通过公开数据和新闻检测融资信号
"""

import json
import sys
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# 添加路径
SKILL_DIR = Path(__file__).parent.parent
CONFIG_DIR = SKILL_DIR / "config"
DATA_DIR = SKILL_DIR / "data"

def load_companies():
    """加载监控企业列表"""
    with open(CONFIG_DIR / "companies.json", "r", encoding="utf-8") as f:
        return json.load(f)["companies"]

def search_company_news(company_name):
    """使用 web_search 搜索企业新闻"""
    try:
        # 构建搜索查询
        queries = [
            f"{company_name} 融资",
            f"{company_name} 融资轮",
            f"{company_name} 投资",
            f"{company_name} 工商变更"
        ]

        results = []
        for query in queries[:2]:  # 只搜索前两个查询以节省时间
            cmd = ["openclaw", "web", "search", "--query", query, "--count", "3"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                results.append({
                    "query": query,
                    "results": result.stdout
                })

        return results
    except Exception as e:
        return {"error": str(e)}

def analyze_funding_signals(company_name, news_results):
    """分析融资信号"""
    if not news_results or isinstance(news_results, dict) and "error" in news_results:
        return {"confidence": 0, "signals": []}

    signals = []
    confidence = 0

    # 关键词匹配
    funding_keywords = [
        "融资", "完成融资", "获得融资", "投资", "新一轮", "A轮", "B轮", "C轮",
        "战略投资", "股权融资", "注册资本", "股东变更", "增资", "注资"
    ]

    for result in news_results:
        if "results" in result:
            content = result["results"]
            for keyword in funding_keywords:
                if keyword in content:
                    signals.append({
                        "keyword": keyword,
                        "source": "news_search"
                    })
                    confidence += 5

    # 限制置信度最高为 100
    confidence = min(confidence, 100)

    return {
        "confidence": confidence,
        "signals": signals,
        "has_signals": len(signals) > 0
    }

def generate_daily_report():
    """生成日报"""
    companies = load_companies()
    today = datetime.now().strftime("%Y-%m-%d")
    today_str = datetime.now().strftime("%Y年%m月%d日")

    report = {
        "date": today,
        "total_companies": len(companies),
        "categories": {},
        "companies_checked": [],
        "funding_signals": [],
        "summary": ""
    }

    print(f"🔍 开始监控 {len(companies)} 家医疗企业...")
    print(f"📅 监控日期: {today_str}\n")

    # 按类别统计
    for company in companies:
        cat = company.get("category", "未分类")
        if cat not in report["categories"]:
            report["categories"][cat] = 0
        report["categories"][cat] += 1

    # 检查每家公司
    for i, company in enumerate(companies, 1):
        name = company["name"]
        full_name = company["full_name"]
        cat = company.get("category", "未分类")

        print(f"[{i}/{len(companies)}] 检查 {name}...")

        # 搜索新闻
        news_results = search_company_news(name)

        # 分析信号
        analysis = analyze_funding_signals(name, news_results)

        company_report = {
            "name": name,
            "full_name": full_name,
            "category": cat,
            "priority": company["priority"],
            "checked": True,
            "analysis": analysis
        }

        report["companies_checked"].append(company_report)

        # 如果有信号，添加到融资信号列表
        if analysis.get("has_signals", False):
            report["funding_signals"].append({
                "company": name,
                "confidence": analysis["confidence"],
                "signals": analysis["signals"],
                "category": cat
            })
            print(f"  ⚠️  发现信号 (置信度: {analysis['confidence']}%)")
        else:
            print(f"  ✅ 无异常")

    # 生成摘要
    if report["funding_signals"]:
        report["summary"] = f"发现 {len(report['funding_signals'])} 家企业可能存在融资信号"
    else:
        report["summary"] = "今日无异常，所有监控企业无融资信号"

    return report

def format_report_markdown(report):
    """格式化为 Markdown 报告"""
    today_str = datetime.now().strftime("%Y年%m月%d日")
    current_time = datetime.now().strftime("%H:%M:%S")

    md = f"""📊 **医疗企业融资监控日报**

📅 **日期**: {today_str} {current_time}
🏢 **监控企业**: {report['total_companies']} 家

---

## 📈 监控概览

"""

    # 按类别展示
    for cat, count in report['categories'].items():
        md += f"• **{cat}**: {count} 家\n"

    md += f"""
## ✅ 监控结果

**{report['summary']}**

"""

    # 融资信号详情
    if report['funding_signals']:
        md += f"""
## 🚨 融资信号详情

发现 {len(report['funding_signals'])} 家企业存在融资信号：

"""

        for signal in report['funding_signals']:
            confidence_icon = "🔴" if signal['confidence'] >= 70 else "🟡" if signal['confidence'] >= 40 else "🟢"
            md += f"""
### {confidence_icon} {signal['company']} ({signal['category']})

• **置信度**: {signal['confidence']}%
• **检测信号**: {', '.join([s['keyword'] for s in signal['signals'][:5]])}

"""

    # 企业列表
    md += f"""
## 🏢 监控企业列表

"""

    # 按类别分组
    companies_by_cat = {}
    for company in report['companies_checked']:
        cat = company['category']
        if cat not in companies_by_cat:
            companies_by_cat[cat] = []
        companies_by_cat[cat].append(company)

    for cat, companies in companies_by_cat.items():
        md += f"\n**{cat}**\n\n"
        for company in companies:
            status = "✅" if not company['analysis']['has_signals'] else f"⚠️ ({company['analysis']['confidence']}%)"
            md += f"• {status} **{company['name']}**\n"

    md += f"""
---

📌 **说明**:
• 本报告通过公开新闻搜索检测融资信号
• 置信度基于关键词频率和相关性
• 高置信度(≥70%)建议人工核实
• 监控系统 powered by OpenClaw

🔄 **下次检查**: 明日同一时间
"""

    return md

def save_report(report, md_content):
    """保存报告"""
    report_dir = DATA_DIR / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")

    # 保存 JSON
    json_file = report_dir / f"daily_{today}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 保存 Markdown
    md_file = report_dir / f"daily_{today}.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md_content)

    return json_file, md_file

if __name__ == "__main__":
    # 生成日报
    report = generate_daily_report()

    # 格式化输出
    md = format_report_markdown(report)

    # 保存报告
    json_file, md_file = save_report(report, md)

    print(f"\n✅ 日报已保存:")
    print(f"   JSON: {json_file}")
    print(f"   Markdown: {md_file}")

    # 输出到标准输出（用于发送）
    print("\n" + "="*60)
    print(md)
    print("="*60)
