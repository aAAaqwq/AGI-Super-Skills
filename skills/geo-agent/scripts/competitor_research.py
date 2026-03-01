#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实竞品搜索模块
通过搜索引擎获取目标行业的真实竞品信息，绝不编造。
"""

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger

try:
    import httpx
    from bs4 import BeautifulSoup
except ImportError:
    print("请安装依赖: pip install httpx beautifulsoup4")
    sys.exit(1)

DATA_DIR = Path(__file__).parent.parent / "data"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


async def search_baidu(query: str, num_results: int = 20) -> List[Dict]:
    """百度搜索获取结果（使用Playwright渲染JS）"""
    results = []
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(f"https://www.baidu.com/s?wd={query}&rn={num_results}", wait_until="networkidle", timeout=15000)
            await asyncio.sleep(2)
            
            # 提取搜索结果
            items = await page.query_selector_all("#content_left .c-container, #content_left .result")
            for item in items[:num_results]:
                try:
                    title_el = await item.query_selector("h3 a")
                    abstract_el = await item.query_selector(".c-abstract, .content-right_8Zs40, [class*='content']")
                    if title_el:
                        title = await title_el.inner_text()
                        href = await title_el.get_attribute("href") or ""
                        abstract = await abstract_el.inner_text() if abstract_el else ""
                        results.append({"title": title.strip(), "url": href, "abstract": abstract.strip()})
                except Exception:
                    continue
            
            await browser.close()
    except Exception as e:
        logger.error(f"百度搜索失败: {e}")
    
    # Fallback: 使用Bing搜索（不需要JS渲染）
    if not results:
        results = await search_bing(query, num_results)
    
    return results


async def search_bing(query: str, num_results: int = 10) -> List[Dict]:
    """Bing搜索（备选，不需要JS渲染）"""
    results = []
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
        try:
            resp = await client.get("https://www.bing.com/search", params={"q": query, "count": num_results})
            soup = BeautifulSoup(resp.text, "html.parser")
            for item in soup.select("#b_results .b_algo"):
                title_el = item.select_one("h2 a")
                abstract_el = item.select_one(".b_caption p")
                if title_el:
                    results.append({
                        "title": title_el.get_text(strip=True),
                        "url": title_el.get("href", ""),
                        "abstract": abstract_el.get_text(strip=True) if abstract_el else "",
                    })
        except Exception as e:
            logger.error(f"Bing搜索失败: {e}")
    return results


async def search_competitors(industry: str, keyword: str, top_n: int = 10) -> List[Dict]:
    """
    搜索行业真实竞品公司
    
    策略：用多个搜索query交叉验证，提取出真实出现频率高的公司名
    使用单个浏览器实例完成所有搜索，提高效率。
    """
    queries = [
        f"{industry}排行榜",
        f"{industry}十大品牌",
        f"{industry}哪家好 推荐",
        f"{keyword} 公司排名",
        f"{industry}头部企业",
        f"{industry}市场份额",
    ]
    
    # 使用单个浏览器实例完成所有搜索
    all_results = []
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            for q in queries:
                try:
                    await page.goto(f"https://www.baidu.com/s?wd={q}", wait_until="domcontentloaded", timeout=10000)
                    # 等待搜索结果出现而非完全加载
                    try:
                        await page.wait_for_selector("#content_left", timeout=5000)
                    except Exception:
                        pass
                    await asyncio.sleep(1)
                    
                    items = await page.query_selector_all("#content_left .c-container, #content_left .result")
                    for item in items[:10]:
                        try:
                            h3 = await item.query_selector("h3 a")
                            abstract_el = await item.query_selector(".c-abstract, [class*='content-right'], span[class*='content']")
                            if h3:
                                title = await h3.inner_text()
                                href = await h3.get_attribute("href") or ""
                                abstract = await abstract_el.inner_text() if abstract_el else ""
                                all_results.append({"title": title.strip(), "url": href, "abstract": abstract.strip(), "query": q})
                        except Exception:
                            continue
                except Exception as e:
                    logger.warning(f"搜索 '{q}' 失败: {e}")
                
                await asyncio.sleep(1)
            
            await browser.close()
    except Exception as e:
        logger.error(f"Playwright搜索失败: {e}")
    
    # Fallback: Bing
    if not all_results:
        for q in queries[:3]:
            results = await search_bing(q)
            all_results.extend(results)
            await asyncio.sleep(1)
    
    logger.info(f"共获取 {len(all_results)} 条搜索结果")
    
    # 从标题和摘要中提取公司名（这里返回原始结果供LLM进一步提取）
    return {
        "industry": industry,
        "keyword": keyword,
        "search_queries": queries,
        "raw_results": all_results[:50],  # 最多50条
        "result_count": len(all_results),
    }


async def research_competitor_details(company_name: str) -> Dict:
    """搜索单个竞品的详细信息"""
    queries = [
        f"{company_name} 产品 优势",
        f"{company_name} 怎么样 评价",
    ]
    
    details = {"company": company_name, "info": []}
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
        for q in queries:
            try:
                resp = await client.get("https://www.baidu.com/s", params={"wd": q, "rn": 5})
                soup = BeautifulSoup(resp.text, "html.parser")
                for item in soup.select(".result.c-container"):
                    abstract = item.select_one(".c-abstract, .content-right_8Zs40")
                    if abstract:
                        details["info"].append(abstract.get_text(strip=True))
            except Exception as e:
                logger.error(f"搜索 {q} 失败: {e}")
            await asyncio.sleep(1)
    
    return details


def save_research(project_id: str, data: Dict):
    """保存调研结果"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    filepath = DATA_DIR / f"research_{project_id}.json"
    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    logger.info(f"调研结果已保存: {filepath}")


async def main():
    """CLI入口"""
    import argparse
    parser = argparse.ArgumentParser(description="真实竞品搜索")
    parser.add_argument("--industry", required=True, help="行业名称")
    parser.add_argument("--keyword", default="", help="核心关键词")
    parser.add_argument("--top", type=int, default=10, help="Top N")
    parser.add_argument("--project-id", default="default", help="项目ID")
    args = parser.parse_args()
    
    result = await search_competitors(args.industry, args.keyword or args.industry, args.top)
    save_research(args.project_id, result)
    print(json.dumps(result, ensure_ascii=False, indent=2)[:3000])


if __name__ == "__main__":
    asyncio.run(main())
