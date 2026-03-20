#!/usr/bin/env python3
"""
掘金自动发布脚本 (Playwright + API 双通道)

用法:
  # Playwright 模式（默认）
  python publish.py --title "标题" --content-file article.md --category "人工智能" --tags "AI,Agent" --mode draft

  # API 模式（需 cookie-file）
  python publish.py --title "标题" --content-file article.md --category "后端" --tags "Python" --api --cookie-file cookies.json

前置条件:
  - pip install playwright && playwright install chromium
  - pip install httpx  (API 模式)
"""

import asyncio
import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

try:
    from playwright.async_api import async_playwright, TimeoutError as PwTimeout
except ImportError:
    print("❌ 需要安装 playwright: pip install playwright && playwright install chromium")
    sys.exit(1)

# ── 常量 ─────────────────────────────────────────
EDITOR_URL = "https://juejin.cn/editor/drafts/new"
DRAFTS_URL = "https://juejin.cn/editor/drafts"
LOGIN_URL = "https://juejin.cn/login"

CATEGORIES = {
    "后端": "backend", "前端": "frontend", "Android": "android",
    "iOS": "ios", "人工智能": "ai", "开发工具": "freeform",
    "代码人生": "career", "阅读": "article",
}

COOKIE_DIR = Path.home() / ".juejin_cookies"
COOKIE_FILE = COOKIE_DIR / "cookies.json"

# API endpoints
API_BASE = "https://api.juejin.cn"
API_DRAFT_CREATE = f"{API_BASE}/content_api/v1/article_draft/create_offline"
API_PUBLISH = f"{API_BASE}/content_api/v1/article/publish"


def log(emoji: str, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {emoji} {msg}")


async def save_cookies(context):
    COOKIE_DIR.mkdir(parents=True, exist_ok=True)
    cookies = await context.cookies()
    COOKIE_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2))
    log("🍪", f"Cookies 已保存 → {COOKIE_FILE}")


async def load_cookies(context):
    if COOKIE_FILE.exists():
        cookies = json.loads(COOKIE_FILE.read_text())
        await context.add_cookies(cookies)
        log("🍪", f"Cookies 已加载 ← {COOKIE_FILE}")
        return True
    return False


# ── Playwright 模式 ──────────────────────────────

async def publish_playwright(title: str, content: str, category: str,
                              tags: list, cover: str = None,
                              abstract: str = None, mode: str = "draft",
                              headless: bool = True):
    """Playwright 浏览器自动化发布"""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        has_cookies = await load_cookies(context)
        page = await context.new_page()

        # 打开编辑器
        log("📌", "打开掘金编辑器...")
        await page.goto(EDITOR_URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # 检查是否需要登录
        if "login" in page.url:
            if headless:
                log("❌", "需要登录！请使用 --no-headless 手动登录")
                await browser.close()
                return False
            log("📱", "请在浏览器中完成登录...")
            try:
                await page.wait_for_url("**/editor/**", timeout=120000)
                log("✅", "登录成功")
                await save_cookies(context)
            except PwTimeout:
                log("❌", "登录超时")
                await browser.close()
                return False

        log("✅", "已进入编辑器")

        # Step 1: 填写标题
        log("📝", f"填写标题: {title[:30]}...")
        title_input = page.locator("input[placeholder*='标题'], input[class*='title']")
        if await title_input.count() > 0:
            await title_input.first.fill(title)
        else:
            # 备用：第一个大输入框
            await page.locator("input").first.fill(title)
        await asyncio.sleep(1)

        # Step 2: 填写 Markdown 正文
        log("📝", f"填写正文 ({len(content)}字)...")
        # 掘金使用 CodeMirror 或 contenteditable 编辑器
        editor_selectors = [
            ".CodeMirror textarea",
            ".CodeMirror",
            "[class*='editor'] [contenteditable='true']",
            "[contenteditable='true']",
            ".bytemd-body textarea",
        ]

        filled = False
        for sel in editor_selectors:
            elem = page.locator(sel)
            if await elem.count() > 0:
                if "CodeMirror" in sel and "textarea" not in sel:
                    # CodeMirror: 需要点击后 type
                    await elem.first.click()
                    await asyncio.sleep(0.5)
                    await page.keyboard.type(content, delay=5)
                else:
                    await elem.first.fill(content)
                filled = True
                log("✅", "正文已填写")
                break

        if not filled:
            log("⚠️", "未找到编辑器，尝试通过键盘输入...")
            await page.keyboard.press("Tab")
            await page.keyboard.type(content, delay=5)

        await asyncio.sleep(2)

        # Step 3: 点击发布按钮打开设置面板
        log("📌", "打开发布设置...")
        pub_btn = page.locator("button:has-text('发布')")
        if await pub_btn.count() > 0:
            await pub_btn.first.click()
            await asyncio.sleep(2)

        # Step 4: 选择分类
        log("📂", f"选择分类: {category}")
        cat_selector = page.locator(f":text('{category}')")
        if await cat_selector.count() > 0:
            await cat_selector.first.click()
            await asyncio.sleep(1)
        else:
            # 备用：点击分类下拉再选
            cat_dropdown = page.locator("[class*='category']")
            if await cat_dropdown.count() > 0:
                await cat_dropdown.first.click()
                await asyncio.sleep(1)
                await page.locator(f":text('{category}')").first.click()
                await asyncio.sleep(1)

        # Step 5: 添加标签
        for tag in tags[:5]:  # 最多5个
            log("🏷️", f"添加标签: {tag}")
            tag_input = page.locator("[class*='tag'] input, input[placeholder*='标签'], input[placeholder*='搜索']")
            if await tag_input.count() > 0:
                await tag_input.first.fill(tag)
                await asyncio.sleep(1)
                # 选择第一个搜索结果或按 Enter 创建
                result = page.locator("[class*='suggestion'] :first-child, [class*='option']:first-child")
                if await result.count() > 0:
                    await result.first.click()
                else:
                    await tag_input.first.press("Enter")
                await asyncio.sleep(0.5)

        # Step 6: 上传封面（可选）
        if cover and os.path.exists(cover):
            log("🖼️", f"上传封面: {cover}")
            cover_input = page.locator("[class*='cover'] input[type='file'], input[accept*='image']")
            if await cover_input.count() > 0:
                await cover_input.first.set_input_files(cover)
                await asyncio.sleep(3)

        # Step 7: 填写摘要（可选）
        if abstract:
            log("📋", f"填写摘要 ({len(abstract)}字)")
            abs_input = page.locator("[class*='abstract'] textarea, textarea[placeholder*='摘要']")
            if await abs_input.count() > 0:
                await abs_input.first.fill(abstract)
                await asyncio.sleep(1)

        # Step 8: 确认发布/保存草稿
        if mode == "publish":
            log("🚀", "确认发布...")
            confirm = page.locator("button:has-text('确认并发布'), button:has-text('确定并发布')")
            if await confirm.count() > 0:
                await confirm.first.click()
                await asyncio.sleep(5)
                log("✅", "文章已发布！")
            else:
                log("⚠️", "未找到确认发布按钮")
        else:
            log("💾", "保存草稿...")
            # 掘金编辑器有自动保存，也可手动点
            draft_btn = page.locator("button:has-text('保存草稿'), button:has-text('草稿')")
            if await draft_btn.count() > 0:
                await draft_btn.first.click()
                await asyncio.sleep(3)
            log("✅", "草稿已保存（掘金编辑器自动保存）")

        # 截图记录
        screenshot_path = f"/tmp/juejin_{'success' if mode else 'draft'}_{datetime.now():%H%M%S}.png"
        await page.screenshot(path=screenshot_path)
        log("📸", f"截图: {screenshot_path}")

        await save_cookies(context)
        await browser.close()
        return True


# ── API 模式 ─────────────────────────────────────

async def publish_api(title: str, content: str, category: str,
                      tags: list, cover: str = None,
                      abstract: str = None, mode: str = "draft",
                      cookie_file: str = None):
    """API 直接发布（需要 session token）"""
    try:
        import httpx
    except ImportError:
        log("❌", "API 模式需要 httpx: pip install httpx")
        return False

    if not cookie_file or not os.path.exists(cookie_file):
        log("❌", "API 模式需要 --cookie-file 参数")
        return False

    cookies = json.loads(Path(cookie_file).read_text())
    # 提取 session token
    session_id = ""
    for c in cookies:
        if c.get("name") == "sessionid":
            session_id = c["value"]
            break

    if not session_id:
        log("❌", "Cookie 中未找到 sessionid")
        return False

    headers = {
        "Content-Type": "application/json",
        "Cookie": f"sessionid={session_id}",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    }

    # 创建草稿
    log("📝", "通过 API 创建草稿...")
    draft_data = {
        "title": title,
        "mark_content": content,
        "category_id": "",  # 需要映射
        "tag_ids": [],  # 需要通过搜索获取
        "brief_content": abstract or content[:100],
        "cover_image": cover or "",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(API_DRAFT_CREATE, json=draft_data, headers=headers)
        result = resp.json()

        if result.get("err_no") != 0:
            log("❌", f"创建草稿失败: {result.get('err_msg', 'unknown')}")
            return False

        draft_id = result.get("data", {}).get("id", "")
        log("✅", f"草稿已创建: {draft_id}")

        if mode == "publish" and draft_id:
            log("🚀", "通过 API 发布文章...")
            pub_resp = await client.post(API_PUBLISH, json={"draft_id": draft_id}, headers=headers)
            pub_result = pub_resp.json()
            if pub_result.get("err_no") == 0:
                article_id = pub_result.get("data", {}).get("article_id", "")
                log("✅", f"文章已发布: https://juejin.cn/post/{article_id}")
            else:
                log("❌", f"发布失败: {pub_result.get('err_msg')}")
                return False

    return True


# ── 主入口 ────────────────────────────────────────

async def main(args):
    # 读取内容文件
    if args.content_file:
        content = Path(args.content_file).read_text(encoding="utf-8")
        log("📄", f"读取内容文件: {args.content_file} ({len(content)}字)")
    elif args.content:
        content = args.content
    else:
        log("❌", "需要 --content 或 --content-file 参数")
        return

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []

    if args.api:
        await publish_api(
            title=args.title, content=content,
            category=args.category, tags=tags,
            cover=args.cover, abstract=args.abstract,
            mode=args.mode, cookie_file=args.cookie_file,
        )
    else:
        await publish_playwright(
            title=args.title, content=content,
            category=args.category, tags=tags,
            cover=args.cover, abstract=args.abstract,
            mode=args.mode, headless=not args.no_headless,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="掘金自动发布 (Playwright + API)")
    parser.add_argument("--title", "-t", required=True, help="文章标题")
    parser.add_argument("--content", "-c", help="正文内容（直接传入）")
    parser.add_argument("--content-file", "-f", help="正文 Markdown 文件路径")
    parser.add_argument("--category", default="后端",
                        choices=list(CATEGORIES.keys()), help="分类（必选）")
    parser.add_argument("--tags", help="标签，逗号分隔 (1-5个)")
    parser.add_argument("--cover", help="封面图路径")
    parser.add_argument("--abstract", help="摘要 (50-150字)")
    parser.add_argument("--mode", choices=["draft", "publish"], default="draft")
    parser.add_argument("--api", action="store_true", help="使用 API 模式（需 cookie-file）")
    parser.add_argument("--cookie-file", help="Cookie JSON 文件路径 (API模式)")
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器")

    args = parser.parse_args()
    asyncio.run(main(args))
