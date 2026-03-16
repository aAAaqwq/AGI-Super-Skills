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

# Clear proxy to avoid socks:// issues
import os as _os
for _k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
    _os.environ.pop(_k, None)

import subprocess as _subprocess

# ============================================================
# AI Platform Search — 从 AI 平台获取行业排行榜数据
# ============================================================

def _get_api_key(pass_name: str) -> Optional[str]:
    """从 pass 获取 API key，失败返回 None"""
    try:
        r = _subprocess.run(["pass", "show", pass_name], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


async def _query_llm_api(endpoint: str, model: str, api_key: str, prompt: str,
                         timeout: int = 20) -> Optional[str]:
    """通用 LLM API 调用 (OpenAI compatible)"""
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        try:
            r = await client.post(
                endpoint,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 2048,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"LLM API 调用失败 ({endpoint}): {type(e).__name__} {e}")
            return None


async def _query_perplexity(prompt: str) -> Optional[Dict]:
    """Query Perplexity AI for rankings (with citations)."""
    key = _get_api_key("api/perplexity")
    if not key:
        logger.info("Perplexity API key 不可用，跳过")
        return None

    async with httpx.AsyncClient(timeout=25, trust_env=False) as client:
        try:
            r = await client.post(
                "https://api.perplexity.ai/chat/completions",
                json={
                    "model": "sonar",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                },
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
            )
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])
            return {"source": "perplexity", "content": content, "citations": citations}
        except Exception as e:
            logger.warning(f"Perplexity 查询失败: {e}")
            return None


async def _query_deepseek(prompt: str) -> Optional[Dict]:
    """Query DeepSeek for rankings."""
    key = _get_api_key("api/deepseek")
    if not key:
        return None
    content = await _query_llm_api(
        "https://api.deepseek.com/chat/completions", "deepseek-chat", key, prompt, timeout=30
    )
    return {"source": "deepseek", "content": content, "citations": []} if content else None


async def _query_glm(prompt: str) -> Optional[Dict]:
    """Query GLM (via zeabur/openai-compatible) for rankings."""
    # Prefer Zeabur openai-compatible relay if configured
    relay = _get_api_key("api/zai")
    if not relay:
        return None
    # NOTE: zeabur endpoint is OpenAI compatible (not open.bigmodel native)
    content = await _query_llm_api(
        "https://open.zeabur.com/v1/chat/completions", "glm-5", relay, prompt
    )
    return {"source": "glm (zai relay)", "content": content, "citations": []} if content else None

async def search_ai_platforms(industry: str, keyword: str) -> List[Dict]:
    """
    向多个 AI 平台查询行业排行榜数据。

    Returns: list of {"source": str, "content": str, "citations": list}
    """
    prompts = [
        f"{industry}行业排行榜前10名公司及其优缺点，请列出具体公司名和简要分析",
        f"{keyword}最好的产品推荐，列出前10名并说明理由",
    ]

    results = []
    # Query each platform with the first prompt (most important)
    main_prompt = prompts[0]
    tasks = [
        _query_perplexity(main_prompt),
        _query_deepseek(main_prompt),
    ]

    # If we still have <2 platforms, fallback to AI-from-search
    if True:
        try:
            fallback = await ai_rank_from_search(industry, keyword)
            if fallback:
                tasks.append(asyncio.sleep(0, result=fallback))
        except Exception:
            pass
    try:
        responses = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=25)
    except asyncio.TimeoutError:
        logger.warning("AI 平台查询超时，返回已有结果")
        responses = []

    for resp in responses:
        if isinstance(resp, dict) and resp.get("content"):
            results.append(resp)

    # If we got at least one result, also query with the second prompt on one platform
    if results and len(prompts) > 1:
        supplementary = await _query_deepseek(prompts[1]) 
        if supplementary:
            supplementary["prompt_type"] = "product_recommendation"
            results.append(supplementary)

    logger.info(f"AI 平台查询完成: {len(results)} 个平台返回了数据 ({', '.join(r['source'] for r in results)})")
    return results


def _parse_ai_rankings(ai_results: List[Dict]) -> List[Dict]:
    """
    从 AI 平台的回答中提取结构化排行数据。
    简单解析：提取编号列表中的公司名。
    """
    rankings = []
    seen = set()

    for result in ai_results:
        content = result.get("content", "")
        source = result.get("source", "unknown")

        # 匹配常见排行格式: "1. 公司名" / "第1名：公司名" / "1）公司名"
        patterns = [
            r'(?:^|\n)\s*(?:\d+)[.、)）]\s*\*{0,2}([^*\n:：]+?)\*{0,2}(?:[:：\n—\-]|$)',
            r'(?:^|\n)\s*第\s*\d+\s*名[：:]\s*\*{0,2}([^*\n]+?)\*{0,2}(?:[:：\n—\-]|$)',
        ]
        for pat in patterns:
            for match in re.finditer(pat, content):
                name = match.group(1).strip().rstrip('*').strip()
                # Filter out noise
                if 2 <= len(name) <= 30 and name not in seen:
                    seen.add(name)
                    rankings.append({
                        "name": name,
                        "source": source,
                        "citations": result.get("citations", []),
                    })

    return rankings


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
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15, trust_env=False) as client:
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
    
    策略：
    1. 先调 AI 平台获取排行榜数据（最权威）
    2. 再调搜索引擎交叉验证
    3. 合并去重，AI 平台结果优先级更高
    """
    # === Phase 1: AI 平台排行榜 ===
    ai_results = []
    ai_rankings = []
    try:
        ai_results = await search_ai_platforms(industry, keyword)
        ai_rankings = _parse_ai_rankings(ai_results)
        logger.info(f"AI 平台提取到 {len(ai_rankings)} 个竞品: {[r['name'] for r in ai_rankings[:5]]}")
    except Exception as e:
        logger.warning(f"AI 平台搜索失败，继续使用搜索引擎: {e}")

    # === Phase 2: 搜索引擎 ===
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
        "raw_results": all_results[:50],
        "result_count": len(all_results),
        "ai_rankings": ai_rankings,
        "ai_raw_responses": [
            {"source": r["source"], "content": r["content"][:1000], "citations": r.get("citations", [])}
            for r in ai_results
        ],
    }




async def ai_rank_from_search(industry: str, keyword: str) -> Optional[Dict]:
    """Fallback AI platform: use Bing snippets + DeepSeek to synthesize a Top10 ranking."""
    try:
        raw = await search_bing(f"{industry} 排行榜 前十", num_results=8)
        snippets = "\n".join(f"- {r.get('title','')} :: {r.get('abstract','')}" for r in raw)
        prompt = (
            f"你是行业分析师。根据以下搜索结果片段，总结{industry}行业Top10公司名单，并给出每家优缺点(每家1-2条)。\n"
            f"要求：只基于片段，不要编造。输出markdown列表即可。\n\n片段：\n{snippets}"
        )
        ds = await _query_deepseek(prompt)
        if ds and ds.get('content'):
            ds['source'] = 'ai-from-search (deepseek)'
            return ds
    except Exception as e:
        logger.warning(f"ai-from-search fallback 失败: {e}")
    return None
async def research_competitor_details(company_name: str) -> Dict:
    """搜索单个竞品的详细信息"""
    queries = [
        f"{company_name} 产品 优势",
        f"{company_name} 怎么样 评价",
    ]
    
    details = {"company": company_name, "info": []}
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15, trust_env=False) as client:
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
