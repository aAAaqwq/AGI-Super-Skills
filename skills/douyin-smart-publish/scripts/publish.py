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
STORAGE_STATE_FILE = COOKIE_DIR / "storage_state.json"  # cookies + localStorage/sessionStorage

RETRY_DELAYS = [10, 30, 90]  # 重试退避秒数

# ── 工具函数 ──────────────────────────────────────

def log(emoji: str, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {emoji} {msg}")


async def save_auth_state(context):
    """保存登录态（cookies + localStorage/sessionStorage）"""
    COOKIE_DIR.mkdir(parents=True, exist_ok=True)
    cookies = await context.cookies()
    COOKIE_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2))
    await context.storage_state(path=str(STORAGE_STATE_FILE))
    log("🍪", f"Auth state 已保存 → {COOKIE_FILE} + {STORAGE_STATE_FILE}")


async def load_auth_state(context) -> bool:
    """加载登录态（优先 storage_state，其次 cookies）"""
    if STORAGE_STATE_FILE.exists():
        log("🍪", f"检测到 storage_state: {STORAGE_STATE_FILE}（建议复用）")

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
    # 经验：抖音上传/转码有时会慢；先等到“描述区可编辑”或“草稿/发布按钮出现且可点击”
    for _ in range(96):  # 最多等8分钟
        await asyncio.sleep(5)

        # 1) 描述输入区域出现（常见完成信号）
        desc_area = page.locator("[contenteditable='true'], textarea[placeholder*='描述'], textarea[placeholder*='添加']")
        if await desc_area.count() > 0:
            log("✅", "检测到描述区，认为上传已完成")
            break

        # 2) 草稿/发布按钮出现（兜底信号）
        draft_btn = page.locator("button:has-text('存草稿'), button:has-text('草稿')").first
        pub_btn = page.locator("button:has-text('发布')").first
        if (await draft_btn.count() > 0) or (await pub_btn.count() > 0):
            try:
                if (await draft_btn.count() > 0) and (await draft_btn.is_enabled()):
                    log("✅", "检测到可用的草稿按钮，认为上传已完成")
                    break
                if (await pub_btn.count() > 0) and (await pub_btn.is_enabled()):
                    log("✅", "检测到可用的发布按钮，认为上传已完成")
                    break
            except Exception:
                pass
    else:
        log("❌", "视频上传/转码超时（8分钟）")
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
            await asyncio.sleep(0.2)
            # contenteditable 下 fill 有时不触发事件；用 Ctrl+A + Backspace 清空更稳
            try:
                await elem.first.press("Control+A")
                await elem.first.press("Backspace")
            except Exception:
                try:
                    await elem.first.fill("")
                except Exception:
                    pass
            await asyncio.sleep(0.2)
            # 使用 type 而非 fill 以触发话题搜索/联想
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


async def _wait_for_post_submit(page, mode: str) -> bool:
    """等待提交后的成功信号或跳转。"""
    for _ in range(18):  # ~18s
        await asyncio.sleep(1)
        url = page.url
        if any(key in url for key in ["draft", "content/manage", "content"]):
            return True

        success_texts = ["保存成功", "草稿已保存", "发布成功", "处理中"]
        for text in success_texts:
            try:
                if await page.locator(f":text('{text}')").count() > 0:
                    return True
            except Exception:
                pass
    return False


async def _submit(page, mode: str) -> bool:
    """提交：发布或存草稿"""
    await asyncio.sleep(2)

    if mode == "publish":
        log("🚀", "正在发布...")
        btn = page.locator("button:has-text('发布')")
        if await btn.count() > 0:
            await btn.first.click()
            ok = await _wait_for_post_submit(page, mode)
            if ok:
                log("✅", "发布流程已触发")
                return True
    else:
        log("💾", "保存草稿...")
        btn = page.locator("button:has-text('存草稿'), button:has-text('草稿')")
        if await btn.count() > 0:
            await btn.first.click()
            ok = await _wait_for_post_submit(page, mode)
            if ok:
                log("✅", "草稿已保存/已进入后续页面")
                return True

    log("❌", f"未找到{'发布' if mode == 'publish' else '草稿'}按钮，或提交后无成功信号")
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

        # 加载登录态（cookies/状态文件）
        _ = await load_auth_state(context)
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
            await save_auth_state(context)

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

        # 保存最新登录态
        await save_auth_state(context)

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
