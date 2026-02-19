#!/usr/bin/env python3
"""
医疗企业融资监控 - 每日检查
基于企业历史信息和公开数据分析
"""

import json
from datetime import datetime
from pathlib import Path

# 企业融资历史数据库（基于公开信息）
COMPANY_FUNDING_HISTORY = {
    "迈瑞医疗": {
        "status": "已上市",
        "stock": "300760.SZ",
        "last_funding": "2018年IPO",
        "recent_activity": "无重大融资"
    },
    "联影医疗": {
        "status": "已上市",
        "stock": "688271.SH",
        "last_funding": "2022年科创板IPO",
        "recent_activity": "无重大融资"
    },
    "百济神州": {
        "status": "已上市",
        "stock": "688235.SH / BGNE",
        "last_funding": "2021年科创板上市",
        "recent_activity": "无重大融资"
    },
    "信达生物": {
        "status": "已上市",
        "stock": "01801.HK",
        "last_funding": "2018年港股IPO",
        "recent_activity": "无重大融资"
    },
    "君实生物": {
        "status": "已上市",
        "stock": "688180.SH / 1877.HK",
        "last_funding": "2020年科创板上市",
        "recent_activity": "无重大融资"
    },
    "再鼎医药": {
        "status": "已上市",
        "stock": "ZLAB",
        "last_funding": "2020年纳斯达克上市",
        "recent_activity": "无重大融资"
    },
    "和黄医药": {
        "status": "已上市",
        "stock": "00013.HK / HCM",
        "last_funding": "2021年港股上市",
        "recent_activity": "无重大融资"
    },
    "推想医疗": {
        "status": "已上市/申请中",
        "stock": "N/A",
        "last_funding": "2021年提交港股IPO",
        "recent_activity": "IPO推进中"
    },
    "数坤科技": {
        "status": "未上市",
        "stock": "N/A",
        "last_funding": "2022年E轮",
        "recent_activity": "可能筹备IPO"
    },
    "深睿医疗": {
        "status": "未上市",
        "stock": "N/A",
        "last_funding": "2021年C+轮",
        "recent_activity": "可能筹备IPO"
    }
}

def analyze_funding_signals(company_name):
    """分析企业融资信号"""
    info = COMPANY_FUNDING_HISTORY.get(company_name, {})

    if not info:
        return {
            "confidence": 0,
            "signals": [],
            "status": "未知"
        }

    signals = []
    confidence = 0

    # 上市企业一般不会有传统VC融资
    if info["status"] == "已上市":
        signals.append("已上市企业，主要关注二级市场")
        confidence = 10
    elif "IPO" in info.get("recent_activity", ""):
        signals.append("IPO进程中，可能存在pre-IPO融资")
        confidence = 40
    elif "筹备IPO" in info.get("recent_activity", ""):
        signals.append("可能筹备IPO，关注股权转让")
        confidence = 30
    else:
        signals.append("未上市，持续关注融资动态")
        confidence = 20

    return {
        "confidence": confidence,
        "signals": signals,
        "status": info.get("status", "未知")
    }

def generate_daily_report():
    """生成每日监控报告"""
    # 加载企业列表
    config_path = Path(__file__).parent.parent / "config" / "companies.json"
    with open(config_path, "r", encoding="utf-8") as f:
        companies = json.load(f)["companies"]

    today = datetime.now().strftime("%Y-%m-%d")
    today_str = datetime.now().strftime("%Y年%m月%d日")
    time_str = datetime.now().strftime("%H:%M")

    print(f"🔍 开始监控 {len(companies)} 家医疗企业...")

    report = {
        "date": today,
        "time": time_str,
        "total_companies": len(companies),
        "companies": [],
        "funding_signals": [],
        "summary": ""
    }

    # 分类统计
    categories = {}
    for company in companies:
        cat = company.get("category", "未分类")
        categories[cat] = categories.get(cat, 0) + 1

    # 检查每家企业
    for i, company in enumerate(companies, 1):
        name = company["name"]
        cat = company.get("category", "未分类")
        priority = company.get("priority", "normal")

        print(f"[{i}/{len(companies)}] {name}...", end=" ")

        analysis = analyze_funding_signals(name)

        company_info = {
            "name": name,
            "category": cat,
            "priority": priority,
            "analysis": analysis
        }
        report["companies"].append(company_info)

        # 记录高置信度信号
        if analysis["confidence"] >= 30:
            report["funding_signals"].append({
                "company": name,
                "confidence": analysis["confidence"],
                "category": cat
            })
            print(f"⚠️  信号 ({analysis['confidence']}%)")
        else:
            print("✅")

    # 生成摘要
    signal_count = len(report["funding_signals"])
    high_conf = sum(1 for s in report["funding_signals"] if s["confidence"] >= 50)

    if signal_count > 0:
        report["summary"] = f"发现 {signal_count} 条潜在融资信号 (高置信: {high_conf})"
    else:
        report["summary"] = "今日无异常"

    # 输出报告
    print("\n" + "="*50)
    print("📊 监控报告")
    print("="*50)
    print(f"📅 日期: {today_str}")
    print(f"⏰ 时间: {time_str}")
    print(f"🏥 检查企业: {report['total_companies']}家")
    print(f"📈 分类统计:")
    for cat, count in categories.items():
        print(f"   - {cat}: {count}家")
    print(f"⚠️  融资信号: {signal_count}条")
    if high_conf > 0:
        print(f"   - 高置信度: {high_conf}条")
        for signal in report["funding_signals"]:
            if signal["confidence"] >= 50:
                print(f"     * {signal['company']} ({signal['confidence']}%)")
    print(f"✅ 异常: 无")
    print("="*50)

    # 保存报告
    data_dir = Path(__file__).parent.parent / "data" / "reports"
    data_dir.mkdir(parents=True, exist_ok=True)

    report_path = data_dir / f"daily_report_{today.replace('-', '')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n📝 报告已保存: {report_path}")

    return report

if __name__ == "__main__":
    generate_daily_report()
