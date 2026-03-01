#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关键词管理和蒸馏模块
管理项目关键词，并通过搜索引擎扩展出长尾问题变体。
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger

try:
    import httpx
    from bs4 import BeautifulSoup
except ImportError:
    print("请安装依赖: pip install httpx beautifulsoup4")
    sys.exit(1)

DATA_DIR = Path(__file__).parent.parent / "data"
KEYWORDS_FILE = DATA_DIR / "keywords.json"
PROJECTS_FILE = DATA_DIR / "projects.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def load_projects() -> List[Dict]:
    if PROJECTS_FILE.exists():
        return json.loads(PROJECTS_FILE.read_text())
    return []


def save_projects(projects: List[Dict]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_FILE.write_text(json.dumps(projects, ensure_ascii=False, indent=2))


def load_keywords() -> List[Dict]:
    if KEYWORDS_FILE.exists():
        return json.loads(KEYWORDS_FILE.read_text())
    return []


def save_keywords(keywords: List[Dict]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    KEYWORDS_FILE.write_text(json.dumps(keywords, ensure_ascii=False, indent=2))


def create_project(name: str, company: str, industry: str, core_keywords: List[str]) -> Dict:
    """创建GEO项目"""
    projects = load_projects()
    project = {
        "id": str(len(projects) + 1),
        "name": name,
        "company": company,
        "industry": industry,
        "core_keywords": core_keywords,
        "created_at": datetime.now().isoformat(),
    }
    projects.append(project)
    save_projects(projects)
    logger.info(f"项目已创建: {name}")
    return project


def add_keywords(project_id: str, keywords: List[str], source: str = "manual") -> int:
    """添加关键词"""
    existing = load_keywords()
    existing_set = {k["keyword"] for k in existing if k["project_id"] == project_id}
    
    added = 0
    for kw in keywords:
        if kw not in existing_set:
            existing.append({
                "project_id": project_id,
                "keyword": kw,
                "source": source,
                "variants": [],
                "created_at": datetime.now().isoformat(),
            })
            added += 1
    
    save_keywords(existing)
    logger.info(f"添加了 {added} 个新关键词")
    return added


async def distill_keywords(keyword: str) -> List[str]:
    """
    关键词蒸馏：通过百度搜索建议和相关搜索扩展长尾关键词
    """
    variants = set()
    
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=10) as client:
        # 1. 百度搜索建议
        try:
            resp = await client.get("https://suggestion.baidu.com/su", params={"wd": keyword, "cb": "s"})
            text = resp.text
            # 解析 jsonp: s({"q":"xxx","p":false,"s":["a","b","c"]})
            match = text.split('"s":[')[1].split(']')[0] if '"s":[' in text else ""
            if match:
                for s in match.split(','):
                    s = s.strip().strip('"')
                    if s:
                        variants.add(s)
        except Exception as e:
            logger.debug(f"百度建议获取失败: {e}")
        
        # 2. 百度相关搜索
        try:
            resp = await client.get("https://www.baidu.com/s", params={"wd": keyword})
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select("#rs a, .recommend_list a"):
                text = a.get_text(strip=True)
                if text:
                    variants.add(text)
        except Exception as e:
            logger.debug(f"百度相关搜索获取失败: {e}")
        
        await asyncio.sleep(0.5)
        
        # 3. 问题变体模式
        question_patterns = [
            f"{keyword}哪家好",
            f"{keyword}推荐",
            f"{keyword}排行榜",
            f"{keyword}怎么选",
            f"{keyword}对比",
            f"最好的{keyword}",
            f"{keyword}十大品牌",
        ]
        variants.update(question_patterns)
    
    result = list(variants)
    logger.info(f"关键词 '{keyword}' 蒸馏出 {len(result)} 个变体")
    return result


async def distill_and_save(project_id: str, keyword: str):
    """蒸馏并保存关键词变体"""
    variants = await distill_keywords(keyword)
    
    keywords = load_keywords()
    for kw in keywords:
        if kw["project_id"] == project_id and kw["keyword"] == keyword:
            kw["variants"] = variants
            kw["distilled_at"] = datetime.now().isoformat()
            break
    
    save_keywords(keywords)
    return variants


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="关键词管理")
    sub = parser.add_subparsers(dest="command")
    
    p_create = sub.add_parser("create-project")
    p_create.add_argument("--name", required=True)
    p_create.add_argument("--company", required=True)
    p_create.add_argument("--industry", required=True)
    p_create.add_argument("--keywords", nargs="+", required=True)
    
    p_distill = sub.add_parser("distill")
    p_distill.add_argument("--keyword", required=True)
    p_distill.add_argument("--project-id", default="1")
    
    p_list = sub.add_parser("list")
    p_list.add_argument("--project-id", default=None)
    
    args = parser.parse_args()
    
    if args.command == "create-project":
        project = create_project(args.name, args.company, args.industry, args.keywords)
        add_keywords(project["id"], args.keywords, "core")
        print(json.dumps(project, ensure_ascii=False, indent=2))
    elif args.command == "distill":
        variants = await distill_and_save(args.project_id, args.keyword)
        print(json.dumps(variants, ensure_ascii=False, indent=2))
    elif args.command == "list":
        keywords = load_keywords()
        if args.project_id:
            keywords = [k for k in keywords if k["project_id"] == args.project_id]
        print(json.dumps(keywords, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
