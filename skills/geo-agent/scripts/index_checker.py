#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI搜索引擎收录检测模块
检测目标关键词/公司在AI搜索引擎回答中的出现情况。
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger

DATA_DIR = Path(__file__).parent.parent / "data"
CHECKS_FILE = DATA_DIR / "checks.json"
COOKIE_BASE = Path.home() / ".playwright-data"

AI_PLATFORMS = {
    "doubao": {
        "name": "豆包",
        "url": "https://www.doubao.com/chat/",
        "input_selector": "textarea",
        "submit_method": "enter",  # enter or click
    },
    "qianwen": {
        "name": "通义千问",
        "url": "https://tongyi.aliyun.com/qianwen/",
        "input_selector": "textarea",
        "submit_method": "enter",
    },
    "deepseek": {
        "name": "DeepSeek",
        "url": "https://chat.deepseek.com/",
        "input_selector": "textarea",
        "submit_method": "enter",
    },
}


def load_checks() -> List[Dict]:
    if CHECKS_FILE.exists():
        return json.loads(CHECKS_FILE.read_text())
    return []


def save_checks(checks: List[Dict]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHECKS_FILE.write_text(json.dumps(checks, ensure_ascii=False, indent=2))


async def check_platform(
    platform_id: str,
    question: str,
    keyword: str,
    company: str,
    headless: bool = True,
) -> Dict:
    """
    检测单个AI平台的收录情况
    
    Returns:
        {
            "platform": str,
            "question": str,
            "answer": str,
            "keyword_found": bool,
            "company_found": bool,
            "success": bool,
            "error": str
        }
    """
    from playwright.async_api import async_playwright
    
    config = AI_PLATFORMS.get(platform_id)
    if not config:
        return {"platform": platform_id, "success": False, "error": "不支持的平台"}
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            
            # 尝试加载登录态
            cookie_file = COOKIE_BASE / platform_id / "state.json"
            if cookie_file.exists():
                context = await browser.new_context(storage_state=str(cookie_file))
            else:
                context = await browser.new_context()
            
            page = await context.new_page()
            
            # 1. 导航
            await page.goto(config["url"], wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
            
            # 2. 输入问题
            try:
                await page.fill(config["input_selector"], question, timeout=10000)
            except Exception:
                # fallback
                textarea = await page.query_selector("textarea")
                if textarea:
                    await textarea.fill(question)
                else:
                    await browser.close()
                    return {"platform": config["name"], "success": False, "error": "输入框未找到"}
            
            await asyncio.sleep(0.5)
            
            # 3. 提交
            await page.keyboard.press("Enter")
            
            # 4. 等待回答（最多60秒）
            logger.info(f"等待 {config['name']} 回答...")
            await asyncio.sleep(15)
            
            # 额外等待：检查是否还在生成
            for _ in range(9):
                # 检查是否有"停止生成"按钮（说明还在生成中）
                stop_btn = await page.query_selector("button:has-text('停止'), button:has-text('Stop')")
                if not stop_btn:
                    break
                await asyncio.sleep(5)
            
            # 5. 获取回答文本
            answer_text = ""
            # 尝试多种选择器获取回答
            selectors = [
                "[class*='answer']",
                "[class*='message']",
                "[class*='response']",
                "[class*='content']",
                "[class*='bubble']",
                "[class*='markdown']",
            ]
            
            for sel in selectors:
                try:
                    elements = await page.query_selector_all(sel)
                    if elements:
                        # 取最后一个（通常是最新的回答）
                        text = await elements[-1].inner_text()
                        if len(text) > len(answer_text):
                            answer_text = text
                except Exception:
                    continue
            
            if not answer_text:
                answer_text = await page.inner_text("body")
            
            await browser.close()
            
            # 6. 检测关键词
            answer_lower = answer_text.lower()
            keyword_found = keyword.lower() in answer_lower
            company_found = company.lower() in answer_lower
            
            logger.info(f"{config['name']}: keyword={keyword_found}, company={company_found}")
            
            return {
                "platform": config["name"],
                "platform_id": platform_id,
                "question": question,
                "answer": answer_text[:2000],
                "keyword_found": keyword_found,
                "company_found": company_found,
                "success": True,
                "error": None,
                "checked_at": datetime.now().isoformat(),
            }
    
    except Exception as e:
        logger.error(f"{platform_id} 检测失败: {e}")
        return {
            "platform": config.get("name", platform_id),
            "platform_id": platform_id,
            "question": question,
            "success": False,
            "keyword_found": False,
            "company_found": False,
            "error": str(e),
            "checked_at": datetime.now().isoformat(),
        }


async def check_all_platforms(
    question: str,
    keyword: str,
    company: str,
    platforms: List[str] = None,
    headless: bool = True,
) -> List[Dict]:
    """检测所有AI平台"""
    if platforms is None:
        platforms = list(AI_PLATFORMS.keys())
    
    results = []
    for pid in platforms:
        result = await check_platform(pid, question, keyword, company, headless)
        results.append(result)
        save_check_record(result)
        await asyncio.sleep(2)
    
    return results


def save_check_record(record: Dict):
    """保存检测记录"""
    checks = load_checks()
    checks.append(record)
    save_checks(checks)


def get_hit_rate(keyword: str = None, company: str = None) -> Dict:
    """计算命中率统计"""
    checks = load_checks()
    if keyword:
        checks = [c for c in checks if c.get("question", "").find(keyword) >= 0]
    
    total = len(checks)
    if total == 0:
        return {"total": 0, "keyword_hit": 0, "company_hit": 0, "rate": 0}
    
    kw_hit = sum(1 for c in checks if c.get("keyword_found"))
    co_hit = sum(1 for c in checks if c.get("company_found"))
    
    return {
        "total": total,
        "keyword_hit": kw_hit,
        "company_hit": co_hit,
        "keyword_rate": round(kw_hit / total * 100, 1),
        "company_rate": round(co_hit / total * 100, 1),
    }


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="AI搜索收录检测")
    parser.add_argument("--keyword", required=True, help="目标关键词")
    parser.add_argument("--company", required=True, help="目标公司名")
    parser.add_argument("--question", help="自定义问题（默认自动生成）")
    parser.add_argument("--platforms", nargs="+", choices=list(AI_PLATFORMS.keys()))
    parser.add_argument("--no-headless", action="store_true")
    parser.add_argument("--stats", action="store_true", help="显示统计")
    args = parser.parse_args()
    
    if args.stats:
        stats = get_hit_rate(args.keyword, args.company)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return
    
    question = args.question or f"{args.keyword}哪家好？推荐一下"
    results = await check_all_platforms(
        question, args.keyword, args.company,
        args.platforms, not args.no_headless
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
