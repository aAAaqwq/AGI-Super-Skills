#!/usr/bin/env python3
"""
医疗企业融资检测器 v2.0
多数据源版本：
1. Firecrawl API - 搜索引擎聚合
2. 36氪 - 创投新闻
3. 动脉网 - 医疗垂直媒体
4. IT桔子 - 投融资数据库
5. 爱企查 - 工商信息 (百度)
6. 新浪财经 - 财经新闻
"""

import json
import os
import re
import subprocess
import sys
import time
import random
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("⚠️ 请安装 requests 和 beautifulsoup4: pip install requests beautifulsoup4", file=sys.stderr)

# 配置
SKILL_DIR = Path(__file__).parent.parent
CONFIG_DIR = SKILL_DIR / "config"
DATA_DIR = SKILL_DIR / "data"

# User-Agent 池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# 融资关键词
FUNDING_KEYWORDS = [
    "融资", "投资", "获投", "完成融资", "宣布融资",
    "A轮", "B轮", "C轮", "D轮", "E轮", "F轮",
    "Pre-A", "Pre-B", "天使轮", "种子轮",
    "战略投资", "股权融资", "增资", "入股",
    "领投", "跟投", "估值", "IPO"
]

# 投资机构关键词
INVESTOR_KEYWORDS = [
    "资本", "投资", "基金", "创投", "风投", "VC", "PE",
    "红杉", "高瓴", "IDG", "经纬", "启明", "软银", "腾讯投资",
    "阿里健康", "百度风投", "字节跳动", "美团龙珠",
    "君联", "达晨", "深创投", "同创伟业", "北极光",
    "GGV", "源码", "五源", "云锋", "淡马锡"
]

# 噪音关键词 (需排除)
NOISE_KEYWORDS = [
    "融资融券", "融资余额", "融资买入", "融资净买入",
    "融资净偿还", "两融", "融资客", "融资盘",
    "涨停", "跌停", "股价", "市值蒸发", "股票"
]

# 医疗行业关键词 (用于验证相关性)
HEALTHCARE_KEYWORDS = [
    "医疗", "医药", "生物", "基因", "诊断", "器械",
    "制药", "创新药", "医院", "健康", "临床", "FDA"
]


def get_headers():
    """获取随机请求头"""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }


def load_companies():
    """加载监控企业列表"""
    with open(CONFIG_DIR / "companies.json", "r", encoding="utf-8") as f:
        return json.load(f)["companies"]


# ==================== 数据源 1: Firecrawl API ====================

def search_firecrawl(company_name: str) -> list:
    """Firecrawl API 搜索"""
    try:
        result = subprocess.run(
            ["pass", "show", "api/firecrawl"],
            capture_output=True, text=True
        )
        api_key = result.stdout.strip()
        
        if not api_key:
            return []
        
        query = f"{company_name} 融资"
        
        response = requests.post(
            "https://api.firecrawl.dev/v1/search",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={"query": query, "limit": 10, "lang": "zh"},
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
                    "source": "Firecrawl",
                    "source_type": "search_engine"
                })
            return results
    except Exception as e:
        print(f"⚠️ Firecrawl 错误: {e}", file=sys.stderr)
    return []


# ==================== 数据源 2: 36氪 ====================

def search_36kr(company_name: str) -> list:
    """36氪搜索"""
    results = []
    try:
        url = f"https://36kr.com/search/articles/{quote(company_name)}"
        response = requests.get(url, headers=get_headers(), timeout=15)
        
        if response.status_code == 200:
            # 36氪使用 JavaScript 渲染，尝试从 script 标签提取数据
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 尝试找到文章列表
            scripts = soup.find_all("script")
            for script in scripts:
                if script.string and "articleList" in script.string:
                    # 提取 JSON 数据
                    match = re.search(r'"articleList":\s*(\[.*?\])', script.string)
                    if match:
                        try:
                            articles = json.loads(match.group(1))
                            for article in articles[:5]:
                                results.append({
                                    "title": article.get("title", ""),
                                    "url": f"https://36kr.com/p/{article.get('id', '')}",
                                    "snippet": article.get("summary", ""),
                                    "source": "36氪",
                                    "source_type": "tech_media",
                                    "publish_time": article.get("publishTime", "")
                                })
                        except:
                            pass
            
            # 备用方案：直接解析 HTML
            if not results:
                articles = soup.select("article, .article-item, .search-item")[:5]
                for article in articles:
                    title_elem = article.select_one("h3, .title, a")
                    if title_elem:
                        results.append({
                            "title": title_elem.get_text(strip=True),
                            "url": title_elem.get("href", ""),
                            "source": "36氪",
                            "source_type": "tech_media"
                        })
        
        time.sleep(random.uniform(1, 3))
    except Exception as e:
        print(f"⚠️ 36氪 错误: {e}", file=sys.stderr)
    return results


# ==================== 数据源 3: 动脉网 ====================

def search_vcbeat(company_name: str) -> list:
    """动脉网搜索 (医疗垂直媒体)"""
    results = []
    try:
        url = f"https://vcbeat.top/search?q={quote(company_name + ' 融资')}"
        response = requests.get(url, headers=get_headers(), timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            articles = soup.select(".search-result-item, .article-item, article")[:5]
            
            for article in articles:
                title_elem = article.select_one("h2, h3, .title, a")
                snippet_elem = article.select_one("p, .summary, .desc")
                
                if title_elem:
                    results.append({
                        "title": title_elem.get_text(strip=True),
                        "url": title_elem.get("href", ""),
                        "snippet": snippet_elem.get_text(strip=True) if snippet_elem else "",
                        "source": "动脉网",
                        "source_type": "healthcare_media"
                    })
        
        time.sleep(random.uniform(1, 3))
    except Exception as e:
        print(f"⚠️ 动脉网 错误: {e}", file=sys.stderr)
    return results


# ==================== 数据源 4: IT桔子 ====================

def search_itjuzi(company_name: str) -> list:
    """IT桔子搜索 (投融资数据库)"""
    results = []
    try:
        url = f"https://www.itjuzi.com/search?kw={quote(company_name)}"
        response = requests.get(url, headers=get_headers(), timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 查找融资事件
            events = soup.select(".event-item, .invest-item, .company-item")[:5]
            
            for event in events:
                title_elem = event.select_one("h3, .name, .title, a")
                info_elem = event.select_one(".info, .desc, .round")
                
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    info = info_elem.get_text(strip=True) if info_elem else ""
                    
                    results.append({
                        "title": f"{title} {info}",
                        "url": title_elem.get("href", ""),
                        "snippet": info,
                        "source": "IT桔子",
                        "source_type": "funding_database"
                    })
        
        time.sleep(random.uniform(1, 3))
    except Exception as e:
        print(f"⚠️ IT桔子 错误: {e}", file=sys.stderr)
    return results


# ==================== 数据源 5: 爱企查 (百度) ====================

def search_aiqicha(company_name: str) -> list:
    """爱企查搜索 (工商信息)"""
    results = []
    try:
        url = f"https://aiqicha.baidu.com/s?q={quote(company_name)}"
        response = requests.get(url, headers=get_headers(), timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 查找公司信息
            companies = soup.select(".search-item, .company-item")[:3]
            
            for company in companies:
                name_elem = company.select_one(".name, .title, h3")
                info_elem = company.select_one(".info, .detail")
                
                if name_elem:
                    # 提取工商变更信息
                    change_info = company.select_one(".change, .update")
                    
                    results.append({
                        "title": name_elem.get_text(strip=True),
                        "url": name_elem.get("href", ""),
                        "snippet": change_info.get_text(strip=True) if change_info else "",
                        "source": "爱企查",
                        "source_type": "business_info"
                    })
        
        time.sleep(random.uniform(1, 3))
    except Exception as e:
        print(f"⚠️ 爱企查 错误: {e}", file=sys.stderr)
    return results


# ==================== 数据源 6: 新浪财经 ====================

def search_sina_finance(company_name: str) -> list:
    """新浪财经搜索"""
    results = []
    try:
        url = f"https://search.sina.com.cn/?q={quote(company_name + ' 融资')}&c=news&from=channel&ie=utf-8"
        response = requests.get(url, headers=get_headers(), timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            articles = soup.select(".result, .box-result")[:5]
            
            for article in articles:
                title_elem = article.select_one("h2 a, .title a, a")
                snippet_elem = article.select_one("p, .content")
                
                if title_elem:
                    results.append({
                        "title": title_elem.get_text(strip=True),
                        "url": title_elem.get("href", ""),
                        "snippet": snippet_elem.get_text(strip=True) if snippet_elem else "",
                        "source": "新浪财经",
                        "source_type": "finance_media"
                    })
        
        time.sleep(random.uniform(1, 3))
    except Exception as e:
        print(f"⚠️ 新浪财经 错误: {e}", file=sys.stderr)
    return results


# ==================== 数据源 7: 投资界 ====================

def search_pedaily(company_name: str) -> list:
    """投资界搜索 (PE/VC 媒体)"""
    results = []
    try:
        url = f"https://www.pedaily.cn/search/?q={quote(company_name)}"
        response = requests.get(url, headers=get_headers(), timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            articles = soup.select(".news-item, .article-item, .search-item")[:5]
            
            for article in articles:
                title_elem = article.select_one("h3, .title, a")
                snippet_elem = article.select_one("p, .desc, .summary")
                
                if title_elem:
                    results.append({
                        "title": title_elem.get_text(strip=True),
                        "url": title_elem.get("href", ""),
                        "snippet": snippet_elem.get_text(strip=True) if snippet_elem else "",
                        "source": "投资界",
                        "source_type": "vc_media"
                    })
        
        time.sleep(random.uniform(1, 3))
    except Exception as e:
        print(f"⚠️ 投资界 错误: {e}", file=sys.stderr)
    return results


# ==================== 聚合搜索 ====================

def search_all_sources(company_name: str) -> list:
    """
    并行搜索所有数据源
    """
    all_results = []
    
    # 数据源列表
    sources = [
        ("Firecrawl", search_firecrawl),
        ("36氪", search_36kr),
        ("动脉网", search_vcbeat),
        ("IT桔子", search_itjuzi),
        ("新浪财经", search_sina_finance),
        ("投资界", search_pedaily),
        # ("爱企查", search_aiqicha),  # 工商信息，可选
    ]
    
    # 并行执行
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(func, company_name): name 
            for name, func in sources
        }
        
        for future in as_completed(futures, timeout=60):
            source_name = futures[future]
            try:
                results = future.result()
                if results:
                    print(f"  ✓ {source_name}: {len(results)} 条", file=sys.stderr)
                    all_results.extend(results)
            except Exception as e:
                print(f"  ✗ {source_name}: {e}", file=sys.stderr)
    
    return all_results


# ==================== 信号分析 ====================

def is_noise(text: str) -> bool:
    """检查是否为噪音"""
    return any(noise in text for noise in NOISE_KEYWORDS)


def extract_round(text: str) -> str:
    """提取融资轮次"""
    patterns = [
        r"(种子轮|天使轮)",
        r"(Pre-[A-Z]\+?轮?)",
        r"([A-Z]\+?轮)",
        r"(战略投资|战略融资)",
        r"(IPO|上市)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def extract_amount(text: str) -> str:
    """提取融资金额"""
    patterns = [
        r"(\d+(?:\.\d+)?)\s*(亿美元)",
        r"(\d+(?:\.\d+)?)\s*(亿人民币|亿元|亿)",
        r"(\d+(?:\.\d+)?)\s*(千万美元)",
        r"(\d+(?:\.\d+)?)\s*(千万人民币|千万元|千万)",
        r"(\d+(?:\.\d+)?)\s*(百万美元|万美元)",
        r"(\d+(?:\.\d+)?)\s*(万人民币|万元|万)",
        r"\$(\d+(?:\.\d+)?)\s*(B|billion)",
        r"\$(\d+(?:\.\d+)?)\s*(M|million)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return f"{match.group(1)}{match.group(2)}"
    return None


def extract_investors(text: str) -> list:
    """提取投资方"""
    investors = []
    for keyword in INVESTOR_KEYWORDS:
        if keyword in text:
            # 尝试提取完整投资方名称
            pattern = rf"([\u4e00-\u9fa5]{{2,10}}{keyword})"
            matches = re.findall(pattern, text)
            investors.extend(matches)
    return list(set(investors))[:5]  # 去重，最多5个


def analyze_funding_signal(company_name: str, news_items: list) -> dict:
    """
    分析融资信号 (增强版)
    """
    signals = []
    total_confidence = 0
    sources_found = set()
    
    for item in news_items:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        text = f"{title} {snippet}"
        source = item.get("source", "unknown")
        source_type = item.get("source_type", "unknown")
        
        # 检查噪音
        if is_noise(text):
            continue
        
        # 检查融资关键词
        funding_matches = [kw for kw in FUNDING_KEYWORDS if kw in text]
        investor_matches = [kw for kw in INVESTOR_KEYWORDS if kw in text]
        
        if not funding_matches:
            continue
        
        # 计算单条新闻置信度
        item_confidence = 0
        item_confidence += len(funding_matches) * 10
        item_confidence += len(investor_matches) * 8
        
        # 提取详细信息
        funding_round = extract_round(text)
        amount = extract_amount(text)
        investors = extract_investors(text)
        
        if funding_round:
            item_confidence += 20
        if amount:
            item_confidence += 15
        if investors:
            item_confidence += len(investors) * 5
        
        # 数据源权重
        source_weights = {
            "funding_database": 1.5,  # IT桔子等融资数据库
            "healthcare_media": 1.3,  # 动脉网等医疗媒体
            "vc_media": 1.3,          # 投资界等VC媒体
            "tech_media": 1.2,        # 36氪等科技媒体
            "search_engine": 1.0,     # Firecrawl搜索
            "finance_media": 1.0,     # 新浪财经
            "business_info": 0.8,     # 工商信息
        }
        item_confidence *= source_weights.get(source_type, 1.0)
        
        signal = {
            "source": source,
            "source_type": source_type,
            "title": title[:100],
            "url": item.get("url", ""),
            "keywords": funding_matches[:5],
            "investors": investors,
            "confidence": min(int(item_confidence), 95)
        }
        
        if funding_round:
            signal["round"] = funding_round
        if amount:
            signal["amount"] = amount
        
        signals.append(signal)
        sources_found.add(source)
        total_confidence += item_confidence
    
    # 多源验证加分
    if len(sources_found) >= 3:
        total_confidence += 25
    elif len(sources_found) >= 2:
        total_confidence += 15
    
    # 计算最终置信度
    if signals:
        avg_confidence = total_confidence / len(signals)
        final_confidence = min(int(avg_confidence), 95)
    else:
        final_confidence = 0
    
    # 去重信号 (按标题相似度)
    unique_signals = deduplicate_signals(signals)
    
    return {
        "company": company_name,
        "has_signal": len(unique_signals) > 0 and final_confidence >= 30,
        "confidence": final_confidence,
        "sources_count": len(sources_found),
        "sources": list(sources_found),
        "signals": unique_signals[:10],  # 最多10条
        "checked_at": datetime.now().isoformat()
    }


def deduplicate_signals(signals: list) -> list:
    """去重信号"""
    seen_titles = set()
    unique = []
    
    for signal in sorted(signals, key=lambda x: x.get("confidence", 0), reverse=True):
        title = signal.get("title", "")[:50]  # 取前50字符比较
        if title not in seen_titles:
            seen_titles.add(title)
            unique.append(signal)
    
    return unique


# ==================== 主流程 ====================

def check_company(company: dict) -> dict:
    """检查单个企业"""
    name = company["name"]
    
    print(f"🔍 检查: {name}", file=sys.stderr)
    
    # 搜索所有数据源
    news_items = search_all_sources(name)
    
    # 分析信号
    analysis = analyze_funding_signal(name, news_items)
    analysis["category"] = company.get("category", "未分类")
    analysis["priority"] = company.get("priority", "normal")
    
    return analysis


def run_daily_check():
    """执行每日检查"""
    companies = load_companies()
    today = datetime.now().strftime("%Y-%m-%d")
    
    results = {
        "date": today,
        "total": len(companies),
        "checked": 0,
        "signals_found": 0,
        "high_confidence": 0,
        "companies": []
    }
    
    for company in companies:
        try:
            analysis = check_company(company)
            results["companies"].append(analysis)
            results["checked"] += 1
            
            if analysis["has_signal"]:
                results["signals_found"] += 1
                if analysis["confidence"] >= 60:
                    results["high_confidence"] += 1
                    
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
    """格式化 Telegram 报告"""
    report = f"""🏥 **医疗企业融资监控日报**

📅 日期: {results['date']}
📊 监控企业: {results['total']} 家
✅ 已检查: {results['checked']} 家
🚨 发现信号: {results['signals_found']} 个
⭐ 高置信度: {results['high_confidence']} 个

"""
    
    # 按置信度排序
    signals = [c for c in results['companies'] if c['has_signal']]
    signals.sort(key=lambda x: x['confidence'], reverse=True)
    
    if signals:
        report += "**🔔 融资信号**\n\n"
        
        for company in signals[:8]:  # 最多显示8个
            confidence_icon = "🔴" if company['confidence'] >= 70 else "🟡" if company['confidence'] >= 50 else "🟢"
            report += f"{confidence_icon} **{company['company']}** ({company['category']})\n"
            report += f"置信度: {company['confidence']}% | 数据源: {company['sources_count']}个\n"
            
            # 显示最重要的信号
            for signal in company['signals'][:2]:
                title = signal['title'][:45] + "..." if len(signal['title']) > 45 else signal['title']
                report += f"• {title}\n"
                
                details = []
                if signal.get('round'):
                    details.append(f"轮次: {signal['round']}")
                if signal.get('amount'):
                    details.append(f"金额: {signal['amount']}")
                if signal.get('investors'):
                    details.append(f"投资方: {', '.join(signal['investors'][:2])}")
                
                if details:
                    report += f"  {' | '.join(details)}\n"
            
            report += "\n"
    else:
        report += "**📭 暂无融资信号**\n\n"
    
    # 数据源统计
    all_sources = set()
    for c in results['companies']:
        all_sources.update(c.get('sources', []))
    
    report += f"**📡 数据源**: {', '.join(all_sources) if all_sources else '无'}\n"
    report += f"---\n_监控时间: {datetime.now().strftime('%H:%M')}_"
    
    return report


def push_to_telegram(message: str):
    """推送到 Telegram"""
    push_script = Path.home() / "clawd" / "skills" / "telegram-push" / "telegram-push.sh"
    
    if push_script.exists():
        subprocess.run([str(push_script), message], check=True)
        print("✅ 已推送到 Telegram", file=sys.stderr)
    else:
        print("⚠️ telegram-push.sh 不存在", file=sys.stderr)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="医疗企业融资检测 v2.0")
    parser.add_argument("--check", action="store_true", help="执行检查")
    parser.add_argument("--push", action="store_true", help="推送报告")
    parser.add_argument("--company", type=str, help="检查单个企业")
    
    args = parser.parse_args()
    
    if args.company:
        company = {"name": args.company, "full_name": args.company}
        result = check_company(company)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
    elif args.check:
        results = run_daily_check()
        report = format_telegram_report(results)
        print(report)
        
        if args.push:
            push_to_telegram(report)
    else:
        parser.print_help()
