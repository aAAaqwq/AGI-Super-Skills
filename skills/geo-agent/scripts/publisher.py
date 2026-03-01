#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多平台文章发布模块
使用Playwright自动化发布文章到各内容平台。
需要预先保存各平台的登录态cookie。
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
from loguru import logger

DATA_DIR = Path(__file__).parent.parent / "data"
COOKIE_BASE = Path.home() / ".playwright-data"

PLATFORMS = {
    "zhihu": {
        "name": "知乎",
        "publish_url": "https://zhuanlan.zhihu.com/write",
        "title_selector": "textarea[placeholder*='请输入标题']",
        "editor_selector": ".public-DraftEditor-content",
        "publish_btn": "button:has-text('发布')",
    },
    "baijiahao": {
        "name": "百家号",
        "publish_url": "https://baijiahao.baidu.com/builder/rc/edit?type=news",
        "title_selector": "#title",
        "editor_selector": ".ql-editor",
        "publish_btn": "button:has-text('发布')",
    },
    "sohu": {
        "name": "搜狐号",
        "publish_url": "https://mp.sohu.com/mpfe/v3/main/new-article",
        "title_selector": "input[placeholder*='标题']",
        "editor_selector": ".ql-editor",
        "publish_btn": "button:has-text('发布')",
    },
    "toutiao": {
        "name": "头条号",
        "publish_url": "https://mp.toutiao.com/profile_v4/graphic/publish",
        "title_selector": "textarea[placeholder*='标题']",
        "editor_selector": ".ProseMirror, .ql-editor",
        "publish_btn": "button:has-text('发布')",
    },
}


async def publish_article(
    platform: str,
    title: str,
    content: str,
    headless: bool = True,
) -> Dict:
    """
    发布文章到指定平台
    
    Args:
        platform: 平台ID (zhihu/baijiahao/sohu/toutiao)
        title: 文章标题
        content: 文章内容(纯文本或Markdown)
        headless: 是否无头模式
    
    Returns:
        {"success": bool, "url": str, "error": str}
    """
    from playwright.async_api import async_playwright
    
    config = PLATFORMS.get(platform)
    if not config:
        return {"success": False, "url": None, "error": f"不支持的平台: {platform}"}
    
    cookie_dir = COOKIE_BASE / platform
    if not cookie_dir.exists():
        return {"success": False, "url": None, "error": f"未找到 {config['name']} 的登录态，请先运行登录脚本"}
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(storage_state=str(cookie_dir / "state.json"))
            page = await context.new_page()
            
            # 1. 导航到发布页
            await page.goto(config["publish_url"], wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
            
            # 2. 检查登录状态
            if "login" in page.url.lower() or "signin" in page.url.lower():
                await browser.close()
                return {"success": False, "url": None, "error": f"{config['name']} 登录态已过期"}
            
            # 3. 填标题
            try:
                await page.fill(config["title_selector"], title, timeout=10000)
            except Exception:
                # fallback: JS方式
                await page.evaluate(f"""
                    document.querySelector("{config['title_selector']}").value = {json.dumps(title)};
                    document.querySelector("{config['title_selector']}").dispatchEvent(new Event('input', {{bubbles: true}}));
                """)
            await asyncio.sleep(1)
            
            # 4. 填内容
            try:
                await page.click(config["editor_selector"])
                await asyncio.sleep(0.5)
                # 用剪贴板粘贴内容（保留格式更好）
                await page.evaluate(f"navigator.clipboard.writeText({json.dumps(content)})")
                await page.keyboard.press("Control+A")
                await asyncio.sleep(0.2)
                await page.keyboard.press("Control+V")
            except Exception:
                await page.fill(config["editor_selector"], content)
            await asyncio.sleep(2)
            
            # 5. 点发布
            try:
                await page.click(config["publish_btn"], timeout=5000)
                await asyncio.sleep(5)
            except Exception as e:
                await browser.close()
                return {"success": False, "url": None, "error": f"发布按钮点击失败: {e}"}
            
            result_url = page.url
            await browser.close()
            
            logger.info(f"✅ {config['name']} 发布完成: {result_url}")
            return {"success": True, "url": result_url, "error": None}
    
    except Exception as e:
        logger.error(f"{platform} 发布失败: {e}")
        return {"success": False, "url": None, "error": str(e)}


async def login_platform(platform: str):
    """交互式登录保存cookie"""
    from playwright.async_api import async_playwright
    
    config = PLATFORMS.get(platform)
    if not config:
        print(f"不支持的平台: {platform}")
        return
    
    cookie_dir = COOKIE_BASE / platform
    cookie_dir.mkdir(parents=True, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto(config["publish_url"])
        print(f"\n请在浏览器中登录 {config['name']}，登录完成后按 Enter 继续...")
        input()
        
        await context.storage_state(path=str(cookie_dir / "state.json"))
        print(f"✅ {config['name']} 登录态已保存到 {cookie_dir}")
        await browser.close()


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="多平台发布")
    sub = parser.add_subparsers(dest="command")
    
    p_pub = sub.add_parser("publish")
    p_pub.add_argument("--platform", required=True, choices=list(PLATFORMS.keys()))
    p_pub.add_argument("--title", required=True)
    p_pub.add_argument("--content-file", required=True, help="内容文件路径")
    p_pub.add_argument("--no-headless", action="store_true")
    
    p_login = sub.add_parser("login")
    p_login.add_argument("--platform", required=True, choices=list(PLATFORMS.keys()))
    
    args = parser.parse_args()
    
    if args.command == "publish":
        content = Path(args.content_file).read_text()
        result = await publish_article(args.platform, args.title, content, not args.no_headless)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "login":
        await login_platform(args.platform)


if __name__ == "__main__":
    asyncio.run(main())
