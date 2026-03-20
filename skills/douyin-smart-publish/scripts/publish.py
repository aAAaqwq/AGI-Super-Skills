#!/usr/bin/env python3
"""
抖音创作者平台自动发布脚本 (Playwright)

支持: 视频发布 / 图文发布
用法:
  # 视频
  python publish.py video --file video.mp4 --desc "描述 #话题" --mode draft
  # 图文
  python publish.py image --files "img1.jpg,img2.jpg" --desc "描述" --mode draft

前置条件:
  - pip install playwright && playwright install chromium
  - 首次使用需 --no-headless 手动扫码登录
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
CREATOR_HOME = "https://creator.douyin.com/creator-micro/home"
VIDEO_UPLOAD = "https://creator.douyin.com/creator-micro/content/upload"
IMAGE_UPLOAD = "https://creator.douyin.com/creator-micro/content/upload?default-tab=3"

DESC_MAX = 200
COOKIE_DIR = Path.home() / ".douyin_cookies"
COOKIE_FILE = COOKIE_DIR / "cookies.json"

RETRY_DELAYS = [10, 30, 90]  # 重试退避秒数

# ── 工具函数 ──────────────────────────────────────

def log(emoji: str, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {emoji} {msg}")


async def save_cookies(context):
    """保存 cookies 到文件"""
    COOKIE_DIR.mkdir(parents=True, exist_ok=True)
    cookies = await context.cookies()
    COOKIE_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2))
    log("🍪", f"Cookies 已保存 → {COOKIE_FILE}")


async def load_cookies(context):
    """从文件加载 cookies"""
    if COOKIE_FILE.exists():
        cookies = json.loads(COOKIE_FILE.read_text())
        await context.add_cookies(cookies)
        log("🍪", f"Cookies 已加载 ← {COOKIE_FILE}")
        return True
    return False


async def wait_for_login(page, timeout_s=120):
    """等待用户手动登录（扫码/验证码）"""
    log("📱", f"请在 {timeout_s} 秒内完成登录（扫码或验证码）...")
    try:
        await page.wait_for_url("**/creator-micro/**", timeout=timeout_s * 1000)
        log("✅", "登录成功！")
        return True
    except PwTimeout:
        log("❌", "登录超时")
        return False


async def retry_upload(page, file_input, file_path: str, max_retries=3):
    """带重试的文件上传"""
    for i in range(max_retries):
        try:
            await file_input.set_input_files(file_path)
            log("📤", f"文件上传中: {Path(file_path).name}")
            await asyncio.sleep(3)
            return True
        except Exception as e:
            delay = RETRY_DELAYS[min(i, len(RETRY_DELAYS) - 1)]
            log("⚠️", f"上传失败 (尝试 {i+1}/{max_retries}): {e}")
            if i < max_retries - 1:
                log("⏳", f"等待 {delay}s 后重试...")
                await asyncio.sleep(delay)
    return False


# ── 核心发布逻辑 ──────────────────────────────────

async def publish_video(page, file_path: str, desc: str, cover: str = None,
                        schedule: str = None, mode: str = "draft"):
    """视频发布流程"""
    log("🎬", f"视频发布: {Path(file_path).name}")

    # 导航到视频上传页
    await page.goto(VIDEO_UPLOAD, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)

    # 上传视频文件
    file_input = page.locator("input[type='file']").first
    success = await retry_upload(page, file_input, file_path)
    if not success:
        log("❌", "视频上传失败，已达最大重试次数")
        return False

    # 等待上传+转码（视频可能需要较长时间）
    log("⏳", "等待视频上传和转码...")
    for _ in range(60):  # 最多等5分钟
        await asyncio.sleep(5)
        # 检查是否出现描述输入区域（表示上传完成）
        desc_area = page.locator("[contenteditable='true'], textarea[placeholder*='描述'], textarea[placeholder*='添加']")
        if await desc_area.count() > 0:
            log("✅", "视频上传完成")
            break
    else:
        log("❌", "视频转码超时（5分钟）")
        return False

    # 填写描述
    await _fill_description(page, desc)

    # 上传自定义封面（可选）
    if cover and os.path.exists(cover):
        log("🖼️", f"上传封面: {cover}")
        cover_area = page.locator("[class*='cover']").first
        if await cover_area.count() > 0:
            await cover_area.click()
            await asyncio.sleep(1)
            cover_input = page.locator("input[type='file']")
            if await cover_input.count() > 1:
                await cover_input.last.set_input_files(cover)
                await asyncio.sleep(3)

    # 定时发布（可选）
    if schedule:
        await _set_schedule(page, schedule)

    # 发布/草稿
    return await _submit(page, mode)


async def publish_image(page, file_paths: list, desc: str, mode: str = "draft"):
    """图文发布流程"""
    log("🖼️", f"图文发布: {len(file_paths)} 张图片")

    if len(file_paths) < 2:
        log("❌", "抖音图文至少需要 2 张图片")
        return False

    # 导航到图文上传页
    await page.goto(IMAGE_UPLOAD, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)

    # 上传图片（支持多选）
    file_input = page.locator("input[type='file']").first
    try:
        await file_input.set_input_files(file_paths)
        log("📤", f"已上传 {len(file_paths)} 张图片")
        await asyncio.sleep(3)
    except Exception as e:
        log("❌", f"图片上传失败: {e}")
        return False

    # 等待图片处理
    await asyncio.sleep(5)

    # 填写描述
    await _fill_description(page, desc)

    # 发布/草稿
    return await _submit(page, mode)


async def _fill_description(page, desc: str):
    """填写描述（含话题标签）"""
    if len(desc) > DESC_MAX:
        log("⚠️", f"描述 {len(desc)}字 超过 {DESC_MAX}字 上限，已截断")
        desc = desc[:DESC_MAX]

    log("📝", f"填写描述 ({len(desc)}字)...")

    # 抖音描述区域：contenteditable div 或 textarea
    desc_selectors = [
        "[contenteditable='true']",
        "textarea[placeholder*='描述']",
        "textarea[placeholder*='添加作品描述']",
        "[class*='desc'] [contenteditable]",
    ]

    for sel in desc_selectors:
        elem = page.locator(sel)
        if await elem.count() > 0:
            await elem.first.click()
            await asyncio.sleep(0.5)
            await elem.first.fill("")
            await asyncio.sleep(0.3)
            # 使用 type 而非 fill 以触发话题搜索
            await elem.first.type(desc, delay=20)
            log("✅", "描述已填写")
            await asyncio.sleep(1)
            return

    log("⚠️", "未找到描述输入区域")


async def _set_schedule(page, schedule_str: str):
    """设置定时发布"""
    log("⏰", f"设置定时发布: {schedule_str}")
    # 尝试找到定时开关
    schedule_toggle = page.locator("[class*='schedule'], :text('定时发布')")
    if await schedule_toggle.count() > 0:
        await schedule_toggle.first.click()
        await asyncio.sleep(1)
        # 填写时间 — 具体实现取决于UI，这里是框架
        log("⚠️", "定时发布UI交互需要根据实际页面调整")
    else:
        log("⚠️", "未找到定时发布开关")


async def _submit(page, mode: str) -> bool:
    """提交：发布或存草稿"""
    await asyncio.sleep(2)

    if mode == "publish":
        log("🚀", "正在发布...")
        btn = page.locator("button:has-text('发布')")
        if await btn.count() > 0:
            await btn.first.click()
            await asyncio.sleep(5)
            log("✅", "发布成功！")
            return True
    else:
        log("💾", "保存草稿...")
        btn = page.locator("button:has-text('存草稿'), button:has-text('草稿')")
        if await btn.count() > 0:
            await btn.first.click()
            await asyncio.sleep(3)
            log("✅", "草稿已保存")
            return True

    log("❌", f"未找到{'发布' if mode == 'publish' else '草稿'}按钮")
    return False


# ── 主入口 ────────────────────────────────────────

async def main(args):
    headless = not args.no_headless

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # 加载 cookies
        has_cookies = await load_cookies(context)
        page = await context.new_page()

        # 检查登录态
        await page.goto(CREATOR_HOME, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # 如果跳转到登录页，等待手动登录
        if "login" in page.url or "passport" in page.url:
            if headless:
                log("❌", "需要登录！请使用 --no-headless 参数手动登录")
                await browser.close()
                return
            if not await wait_for_login(page):
                await browser.close()
                return
            await save_cookies(context)

        log("✅", "已登录抖音创作者平台")

        # 根据子命令执行
        success = False
        if args.command == "video":
            success = await publish_video(
                page, args.file, args.desc,
                cover=args.cover, schedule=args.schedule, mode=args.mode
            )
        elif args.command == "image":
            files = [f.strip() for f in args.files.split(",")]
            success = await publish_image(page, files, args.desc, mode=args.mode)

        # 保存最新 cookies
        await save_cookies(context)

        if success:
            await page.screenshot(path="/tmp/douyin_success.png")
            log("📸", "成功截图: /tmp/douyin_success.png")
        else:
            await page.screenshot(path="/tmp/douyin_error.png")
            log("📸", "错误截图: /tmp/douyin_error.png")

        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="抖音创作者平台自动发布")
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器（登录/调试）")

    sub = parser.add_subparsers(dest="command", required=True)

    # video 子命令
    vid = sub.add_parser("video", help="发布视频")
    vid.add_argument("--file", "-f", required=True, help="视频文件路径")
    vid.add_argument("--desc", "-d", required=True, help="描述（含#话题）")
    vid.add_argument("--cover", help="封面图路径")
    vid.add_argument("--schedule", help="定时发布 (格式: 2026-03-20 20:00)")
    vid.add_argument("--mode", choices=["draft", "publish"], default="draft")

    # image 子命令
    img = sub.add_parser("image", help="发布图文")
    img.add_argument("--files", required=True, help="图片路径，逗号分隔（≥2张）")
    img.add_argument("--desc", "-d", required=True, help="描述（含#话题）")
    img.add_argument("--mode", choices=["draft", "publish"], default="draft")

    args = parser.parse_args()
    asyncio.run(main(args))
