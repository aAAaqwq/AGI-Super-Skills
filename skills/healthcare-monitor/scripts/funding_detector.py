#!/usr/bin/env python3
"""
医疗企业融资检测器
使用多种免费数据源检测融资信号：
1. 新闻搜索 - 36氪、动脉网、投资界等
2. 公开工商信息 - 爱企查（百度）
3. 投融资数据库 - IT桔子、烯牛数据等公开信息
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

# 配置
SKILL_DIR = Path(__file__).parent.parent
CONFIG_DIR = SKILL_DIR / "config"
DATA_DIR = SKILL_DIR / "data"

# 融资关键词
FUNDING_KEYWORDS = [
    "融资", "投资", "获投", "完成融资", "宣布融资",
    "A轮", "B轮", "C轮", "D轮", "Pre-A", "天使轮", "种子轮",
    "战略投资", "股权融资", "增资", "入股",
    "领投", "跟投", "估值"
]

# 投资机构关键词
INVESTOR_KEYWORDS = [
    "资本", "投资", "基金", "创投", "风投", "VC", "PE",
    "红杉", "高瓴", "IDG", "经纬", "启明", "软银", "腾讯投资",
    "阿里健康", "百度风投", "字节跳动", "美团龙珠"
]

# 噪音关键词 (需排除)
NOISE_KEYWORDS = [
    "融资融券", "融资余额", "融资买入", "融资净买入",
    "融资净偿还", "两融", "融资客", "融资盘",
    "涨停", "跌停", "股价", "市值蒸发"
]

# 新闻源
NEWS_SOURCES = [
    {"name": "36氪", "search_url": "https://36kr.com/search/articles/{query}"},
    {"name": "动脉网", "search_url": "https://vcbeat.top/search?q={query}"},
    {"name": "投资界", "search_url": "https://www.pedaily.cn/search?q={query}"},
    {"name": "亿欧", "search_url": "https://www.iyiou.com/search?q={query}"},
]


def load_companies():
    """加载监控企业列表"""
    with open(CONFIG_DIR / "companies.json", "r", encoding="utf-8") as f:
        return json.load(f)["companies"]


def search_news_firecrawl(company_name: str, days: int = 7) -> list:
    """
    使用 Firecrawl API 搜索新闻
    """
    try:
        # 获取 API key
        result = subprocess.run(
            ["pass", "show", "api/firecrawl"],
            capture_output=True, text=True
        )
        api_key = result.stdout.strip()
        
        if not api_key:
            print(f"⚠️ Firecrawl API key 未配置", file=sys.stderr)
            return []
        
        # 构建搜索查询
        query = f"{company_name} 融资"
        
        import requests
        
        # Firecrawl search API
        response = requests.post(
            "https://api.firecrawl.dev/v1/search",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "query": query,
                "limit": 10,
                "lang": "zh"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            results = []
            for item in data.get("data", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("description", ""),
                    "source": "firecrawl"
                })
            return results
        else:
            print(f"⚠️ Firecrawl 搜索失败: {response.status_code}", file=sys.stderr)
            return []
            
    except Exception as e:
        print(f"⚠️ Firecrawl 搜索异常: {e}", file=sys.stderr)
        return []


def search_news_web(company_name: str) -> list:
    """
    使用 web_fetch 抓取新闻
    """
    results = []
    
    # 36氪搜索
    try:
        import requests
        from bs4 import BeautifulSoup
        
        url = f"https://36kr.com/search/articles/{quote(company_name + ' 融资')}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            articles = soup.select("article, .article-item, .search-result-item")[:5]
            
            for article in articles:
                title_elem = article.select_one("h3, .title, a")
                if title_elem:
                    results.append({
                        "title": title_elem.get_text(strip=True),
                        "url": title_elem.get("href", ""),
                        "source": "36氪"
                    })
    except Exception as e:
        print(f"⚠️ 36氪搜索失败: {e}", file=sys.stderr)
    
    return results


def analyze_funding_signal(company_name: str, news_items: list) -> dict:
    """
    分析融资信号
    """
    signals = []
    confidence = 0
    
    for item in news_items:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        text = f"{title} {snippet}"
        
        # 检查噪音关键词 - 排除融资融券等
        is_noise = any(noise in text for noise in NOISE_KEYWORDS)
        if is_noise:
            continue  # 跳过噪音新闻
        
        # 检查融资关键词
        funding_matches = [kw for kw in FUNDING_KEYWORDS if kw in text]
        investor_matches = [kw for kw in INVESTOR_KEYWORDS if kw in text]
        
        if funding_matches:
            signal = {
                "source": item.get("source", "unknown"),
                "title": title,
                "url": item.get("url", ""),
                "keywords": funding_matches,
                "investors": investor_matches
            }
            signals.append(signal)
            
            # 计算置信度
            confidence += len(funding_matches) * 15
            confidence += len(investor_matches) * 10
            
            # 检查融资轮次
            round_match = re.search(r"(Pre-[A-Z]|[A-Z]轮|天使轮|种子轮|战略)", text)
            if round_match:
                signal["round"] = round_match.group(1)
                confidence += 20
            
            # 检查金额
            amount_match = re.search(r"(\d+(?:\.\d+)?)\s*(亿|万|美元|人民币|元)", text)
            if amount_match:
                signal["amount"] = f"{amount_match.group(1)}{amount_match.group(2)}"
                confidence += 15
    
    # 限制置信度最大值
    confidence = min(confidence, 95)
    
    return {
        "company": company_name,
        "has_signal": len(signals) > 0,
        "confidence": confidence,
        "signals": signals,
        "checked_at": datetime.now().isoformat()
    }


def check_company(company: dict) -> dict:
    """
    检查单个企业的融资信号
    """
    name = company["name"]
    full_name = company.get("full_name", name)
    
    print(f"🔍 检查: {name}", file=sys.stderr)
    
    # 搜索新闻
    news_items = []
    
    # 1. 尝试 Firecrawl
    firecrawl_results = search_news_firecrawl(name)
    news_items.extend(firecrawl_results)
    
    # 2. 尝试直接抓取
    if len(news_items) < 3:
        web_results = search_news_web(name)
        news_items.extend(web_results)
    
    # 分析信号
    analysis = analyze_funding_signal(name, news_items)
    analysis["category"] = company.get("category", "未分类")
    analysis["priority"] = company.get("priority", "normal")
    
    return analysis


def run_daily_check():
    """
    执行每日检查
    """
    companies = load_companies()
    today = datetime.now().strftime("%Y-%m-%d")
    
    results = {
        "date": today,
        "total": len(companies),
        "checked": 0,
        "signals_found": 0,
        "companies": []
    }
    
    for company in companies:
        try:
            analysis = check_company(company)
            results["companies"].append(analysis)
            results["checked"] += 1
            
            if analysis["has_signal"]:
                results["signals_found"] += 1
                
        except Exception as e:
            print(f"❌ 检查 {company['name']} 失败: {e}", file=sys.stderr)
    
    # 保存结果
    results_dir = DATA_DIR / "funding_checks"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    results_file = results_dir / f"check_{today}.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    return results


def format_telegram_report(results: dict) -> str:
    """
    格式化 Telegram 报告
    """
    report = f"""🏥 **医疗企业融资监控日报**

📅 日期: {results['date']}
📊 监控企业: {results['total']} 家
✅ 已检查: {results['checked']} 家
🚨 发现信号: {results['signals_found']} 个

"""
    
    # 有信号的企业
    signals = [c for c in results['companies'] if c['has_signal']]
    
    if signals:
        report += "**🔔 融资信号**\n\n"
        for company in signals:
            report += f"**{company['company']}** ({company['category']})\n"
            report += f"置信度: {company['confidence']}%\n"
            
            for signal in company['signals'][:2]:
                report += f"• {signal['title'][:50]}...\n"
                if signal.get('round'):
                    report += f"  轮次: {signal['round']}\n"
                if signal.get('amount'):
                    report += f"  金额: {signal['amount']}\n"
            report += "\n"
    else:
        report += "**📭 暂无融资信号**\n\n"
    
    report += f"---\n_监控时间: {datetime.now().strftime('%H:%M')}_"
    
    return report


def push_to_telegram(message: str):
    """
    推送到 Telegram
    """
    push_script = SKILL_DIR / "scripts" / ".." / ".." / "telegram-push" / "telegram-push.sh"
    if not push_script.exists():
        push_script = Path.home() / "clawd" / "skills" / "telegram-push" / "telegram-push.sh"
    
    if push_script.exists():
        subprocess.run([str(push_script), message], check=True)
        print("✅ 已推送到 Telegram", file=sys.stderr)
    else:
        print("⚠️ telegram-push.sh 不存在", file=sys.stderr)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="医疗企业融资检测")
    parser.add_argument("--check", action="store_true", help="执行检查")
    parser.add_argument("--push", action="store_true", help="推送报告")
    parser.add_argument("--company", type=str, help="检查单个企业")
    
    args = parser.parse_args()
    
    if args.company:
        # 检查单个企业
        company = {"name": args.company, "full_name": args.company}
        result = check_company(company)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
    elif args.check:
        # 执行每日检查
        results = run_daily_check()
        
        # 格式化报告
        report = format_telegram_report(results)
        print(report)
        
        if args.push:
            push_to_telegram(report)
    else:
        parser.print_help()
