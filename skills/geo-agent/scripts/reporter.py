#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GEO数据报表模块
生成各维度的GEO效果报表。
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

DATA_DIR = Path(__file__).parent.parent / "data"


def load_json(filename: str) -> list:
    f = DATA_DIR / filename
    return json.loads(f.read_text()) if f.exists() else []


def weekly_report(project_id: str = None) -> str:
    """生成周报"""
    articles = load_json("articles.json")
    checks = load_json("checks.json")
    keywords = load_json("keywords.json")
    
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    
    # 本周文章
    week_articles = [a for a in articles if a.get("created_at", "") >= week_ago]
    if project_id:
        week_articles = [a for a in week_articles if a.get("project_id") == project_id]
    
    published = [a for a in week_articles if a.get("status") == "published"]
    
    # 本周检测
    week_checks = [c for c in checks if c.get("checked_at", "") >= week_ago]
    
    # 命中率
    total_checks = len(week_checks)
    kw_hits = sum(1 for c in week_checks if c.get("keyword_found"))
    co_hits = sum(1 for c in week_checks if c.get("company_found"))
    
    # 平台分布
    platform_stats = defaultdict(lambda: {"total": 0, "kw_hit": 0, "co_hit": 0})
    for c in week_checks:
        pid = c.get("platform_id", c.get("platform", "unknown"))
        platform_stats[pid]["total"] += 1
        if c.get("keyword_found"):
            platform_stats[pid]["kw_hit"] += 1
        if c.get("company_found"):
            platform_stats[pid]["co_hit"] += 1
    
    report = f"""📊 GEO 周报 ({datetime.now().strftime('%Y-%m-%d')})

📝 文章
- 本周生成: {len(week_articles)} 篇
- 已发布: {len(published)} 篇
- 待发布: {len(week_articles) - len(published)} 篇

🔍 收录检测
- 总检测次数: {total_checks}
- 关键词命中: {kw_hits} ({round(kw_hits/max(total_checks,1)*100, 1)}%)
- 公司名命中: {co_hits} ({round(co_hits/max(total_checks,1)*100, 1)}%)

📈 各平台详情"""
    
    for pid, stats in platform_stats.items():
        kw_rate = round(stats["kw_hit"] / max(stats["total"], 1) * 100, 1)
        co_rate = round(stats["co_hit"] / max(stats["total"], 1) * 100, 1)
        report += f"\n- {pid}: 检测{stats['total']}次, 关键词{kw_rate}%, 公司{co_rate}%"
    
    report += f"""

📋 关键词库
- 总关键词数: {len(keywords)}
"""
    
    return report


def keyword_trend(keyword: str) -> str:
    """某关键词的收录趋势"""
    checks = load_json("checks.json")
    relevant = [c for c in checks if keyword.lower() in c.get("question", "").lower()]
    
    if not relevant:
        return f"暂无关键词 '{keyword}' 的检测数据"
    
    # 按日期分组
    daily = defaultdict(lambda: {"total": 0, "kw_hit": 0, "co_hit": 0})
    for c in relevant:
        date = c.get("checked_at", "")[:10]
        daily[date]["total"] += 1
        if c.get("keyword_found"):
            daily[date]["kw_hit"] += 1
        if c.get("company_found"):
            daily[date]["co_hit"] += 1
    
    report = f"📈 关键词 '{keyword}' 收录趋势\n\n"
    for date in sorted(daily.keys()):
        d = daily[date]
        report += f"{date}: 检测{d['total']}次 | 关键词{d['kw_hit']}次 | 公司{d['co_hit']}次\n"
    
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["weekly", "keyword-trend"], default="weekly")
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--keyword", default=None)
    args = parser.parse_args()
    
    if args.type == "weekly":
        print(weekly_report(args.project_id))
    elif args.type == "keyword-trend":
        if not args.keyword:
            print("需要 --keyword 参数")
        else:
            print(keyword_trend(args.keyword))
