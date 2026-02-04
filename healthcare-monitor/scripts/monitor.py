#!/usr/bin/env python3
"""
医疗企业融资监控主脚本
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
CONFIG_DIR = SKILL_DIR / "config"
DATA_DIR = SKILL_DIR / "data"

def load_config():
    """加载配置"""
    with open(CONFIG_DIR / "settings.json", "r", encoding="utf-8") as f:
        return json.load(f)

def load_companies():
    """加载监控企业列表"""
    with open(CONFIG_DIR / "companies.json", "r", encoding="utf-8") as f:
        return json.load(f)["companies"]

def save_companies(companies):
    """保存监控企业列表"""
    data = {"version": 1, "companies": companies}
    with open(CONFIG_DIR / "companies.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_company(name, full_name=None, category="未分类", priority="normal"):
    """添加监控企业"""
    companies = load_companies()
    
    # 检查是否已存在
    for c in companies:
        if c["name"] == name or c.get("full_name") == name:
            print(f"企业 {name} 已在监控列表中")
            return False
    
    company = {
        "name": name,
        "full_name": full_name or name,
        "category": category,
        "priority": priority,
        "tianyancha_id": None,
        "added_at": datetime.now().strftime("%Y-%m-%d")
    }
    
    companies.append(company)
    save_companies(companies)
    print(f"✅ 已添加企业: {name}")
    return True

def remove_company(name):
    """移除监控企业"""
    companies = load_companies()
    original_count = len(companies)
    
    companies = [c for c in companies if c["name"] != name and c.get("full_name") != name]
    
    if len(companies) < original_count:
        save_companies(companies)
        print(f"✅ 已移除企业: {name}")
        return True
    else:
        print(f"❌ 未找到企业: {name}")
        return False

def list_companies():
    """列出所有监控企业"""
    companies = load_companies()
    
    print(f"\n📋 监控企业列表 (共 {len(companies)} 家)\n")
    print("-" * 60)
    
    # 按类别分组
    categories = {}
    for c in companies:
        cat = c.get("category", "未分类")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(c)
    
    for cat, comps in categories.items():
        print(f"\n【{cat}】")
        for c in comps:
            priority_icon = "🔴" if c["priority"] == "high" else "🟡" if c["priority"] == "normal" else "⚪"
            print(f"  {priority_icon} {c['name']}")
    
    print("\n" + "-" * 60)

def check_company(name):
    """检查单个企业"""
    from scraper_free import FreePlatformRotator
    from analyzer import FundingAnalyzer
    from notifier import send_alert
    import asyncio
    
    print(f"🔍 检查企业: {name}")
    
    # 1. 爬取数据（使用免费轮换爬虫）
    rotator = FreePlatformRotator()
    result = asyncio.run(rotator.scrape_company(name))
    
    if not result["success"]:
        print(f"❌ 无法获取企业数据: {result.get('error', '未知错误')}")
        if "usage_report" in result:
            print("\n" + result["usage_report"])
        return None
    
    current_data = result["data"]
    print(f"✅ 数据获取成功 (来源: {result['source']})")
    
    # 2. 加载历史快照
    snapshot_file = DATA_DIR / "snapshots" / f"{name}.json"
    previous_data = None
    if snapshot_file.exists():
        with open(snapshot_file, "r", encoding="utf-8") as f:
            previous_data = json.load(f)
    
    # 3. 对比变更
    changes = []
    if previous_data:
        # 注册资本变更
        if current_data.get("capital") != previous_data.get("capital"):
            changes.append({
                "type": "capital_change",
                "old": previous_data.get("capital"),
                "new": current_data.get("capital")
            })
        
        # 股东变更
        old_shareholders = set(s["name"] for s in previous_data.get("shareholders", []))
        new_shareholders = set(s["name"] for s in current_data.get("shareholders", []))
        
        added = new_shareholders - old_shareholders
        if added:
            changes.append({
                "type": "new_shareholders",
                "shareholders": list(added)
            })
    
    # 4. 保存新快照
    snapshot_file.parent.mkdir(parents=True, exist_ok=True)
    with open(snapshot_file, "w", encoding="utf-8") as f:
        json.dump(current_data, f, ensure_ascii=False, indent=2)
    
    # 5. 分析融资信号
    if changes:
        analyzer = FundingAnalyzer()
        result = analyzer.analyze(name, changes, current_data)
        
        if result["is_funding"] and result["confidence"] >= 60:
            # 6. 发送告警
            send_alert(name, result)
            
            # 7. 记录变更
            change_file = DATA_DIR / "changes" / f"{datetime.now().strftime('%Y%m%d')}_{name}.json"
            change_file.parent.mkdir(parents=True, exist_ok=True)
            with open(change_file, "w", encoding="utf-8") as f:
                json.dump({
                    "company": name,
                    "time": datetime.now().isoformat(),
                    "changes": changes,
                    "analysis": result
                }, f, ensure_ascii=False, indent=2)
            
            return result
    
    print(f"✅ {name}: 无重大变更")
    return None

def check_all():
    """检查所有企业"""
    companies = load_companies()
    config = load_config()
    
    print(f"\n🔍 开始检查 {len(companies)} 家企业...\n")
    
    results = []
    for i, company in enumerate(companies, 1):
        print(f"[{i}/{len(companies)}] ", end="")
        result = check_company(company["name"])
        if result:
            results.append(result)
        
        # 延迟
        import time
        import random
        delay = random.uniform(
            config["scraper"]["delay_min"],
            config["scraper"]["delay_max"]
        )
        time.sleep(delay)
    
    print(f"\n✅ 检查完成，发现 {len(results)} 个融资信号")
    return results

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  python monitor.py list              - 列出监控企业")
        print("  python monitor.py add <公司名>      - 添加监控企业")
        print("  python monitor.py remove <公司名>   - 移除监控企业")
        print("  python monitor.py check             - 检查所有企业")
        print("  python monitor.py check <公司名>    - 检查单个企业")
        return
    
    command = sys.argv[1]
    
    if command == "list":
        list_companies()
    elif command == "add" and len(sys.argv) >= 3:
        add_company(sys.argv[2])
    elif command == "remove" and len(sys.argv) >= 3:
        remove_company(sys.argv[2])
    elif command == "check":
        if len(sys.argv) >= 3:
            check_company(sys.argv[2])
        else:
            check_all()
    else:
        print(f"未知命令: {command}")

if __name__ == "__main__":
    main()
