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

TITLE_MAX = 55
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
    """加载登录态（context 已创建时可通过 storage_state 自动加载；这里保留 cookies 兜底）"""
    if STORAGE_STATE_FILE.exists():
        log("🍪", f"检测到 storage_state: {STORAGE_STATE_FILE}")

    if COOKIE_FILE.exists():
        cookies = json.loads(COOKIE_FILE.read_text())
        await context.add_cookies(cookies)
        log("🍪", f"Cookies 已加载 ← {COOKIE_FILE}")
        return True
    return False


async def is_login_page(page) -> bool:
    """更稳的登录页判断：不仅看 URL，也看扫码/验证码登录 UI。"""
    if ("login" in page.url) or ("passport" in page.url):
        return True

    markers = [
        ":text('扫码登录')",
        ":text('验证码登录')",
        ":text('我是创作者')",
        "img[alt*='二维码']",
    ]
    for sel in markers:
        try:
            if await page.locator(sel).count() > 0:
                return True
        except Exception:
            pass
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

async def publish_video(page, file_path: str, title: str, desc: str, cover: str = None,
                        schedule: str = None, mode: str = "draft"):
    """视频发布流程"""
    log("🎬", f"视频发布: {Path(file_path).name}")

    title = (title or "").strip()
    if len(title) > TITLE_MAX:
        log("⚠️", f"标题 {len(title)}字 超过 {TITLE_MAX}字 上限，已截断")
        title = title[:TITLE_MAX]

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

    # 填写标题（如果页面存在独立标题区）
    if title:
        await _fill_title(page, title)

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


async def publish_image(page, file_paths: list, title: str, desc: str, mode: str = "draft"):
    """图文发布流程"""
    log("🖼️", f"图文发布: {len(file_paths)} 张图片")

    title = (title or "").strip()
    if len(title) > TITLE_MAX:
        log("⚠️", f"标题 {len(title)}字 超过 {TITLE_MAX}字 上限，已截断")
        title = title[:TITLE_MAX]

    if len(file_paths) < 2:
        log("❌", "抖音图文至少需要 2 张图片")
        return False

    # 导航到图文上传页
    await page.goto(IMAGE_UPLOAD, wait_until="domcontentloaded", timeout=30000)
    # 等待页面加载完成（抖音是重度SPA，需要等待file input出现）
    try:
        await page.wait_for_selector("input[type='file']", timeout=30000)
    except Exception:
        log("❌", "页面加载超时，file input未出现")
        await page.screenshot(path="/tmp/douyin_load_timeout.png")
        return False
    await asyncio.sleep(2)

    # 处理"上次未发布图文"弹窗（如果有）
    # 抖音弹窗的"继续编辑"和"放弃"是文本链接，不是button
    for _ in range(3):
        dismissed = await page.evaluate("""() => {
            const els = document.querySelectorAll('*');
            for (const el of els) {
                const t = el.textContent.trim();
                if ((t === '放弃' || t === '不再提醒' || t === '新建图文')
                    && el.offsetParent !== null && el.children.length === 0) {
                    el.click();
                    return t;
                }
            }
            return null;
        }""")
        if dismissed:
            log("ℹ️", f"检测到未发布图文弹窗，点击 [{dismissed}]")
            await asyncio.sleep(2)
        else:
            break

    # 上传图片（支持多选）
    file_input = page.locator("input[type='file']").first
    try:
        await file_input.set_input_files(file_paths)
        log("📤", f"已上传 {len(file_paths)} 张图片")
        # 等待图片上传处理完成（检查是否有草稿/发布按钮出现）
        try:
            await page.wait_for_selector("button:has-text('存草稿'), button:has-text('发布'), button:has-text('暂存离开')", timeout=60000)
            log("✅", "图片上传完成，编辑器已就绪")
        except Exception:
            log("❌", "图片上传超时，编辑器未就绪")
            await page.screenshot(path="/tmp/douyin_upload_timeout.png")
            return False
    except Exception as e:
        log("❌", f"图片上传失败: {e}")
        return False

    # 等待图片处理
    await asyncio.sleep(5)

    # 填写标题（如果页面存在独立标题区）
    if title:
        await _fill_title(page, title)

    # 填写描述
    await _fill_description(page, desc)

    # 发布/草稿
    return await _submit(page, mode)


async def _fill_title(page, title: str):
    """填写标题（若页面存在独立标题输入区）"""
    if not title:
        return

    log("🏷️", f"填写标题 ({len(title)}字)...")
    title_selectors = [
        "input[placeholder*='标题']",
        "textarea[placeholder*='标题']",
        "[class*='title'] input",
        "[class*='title'] textarea",
    ]

    for sel in title_selectors:
        elem = page.locator(sel)
        if await elem.count() > 0:
            try:
                await elem.first.click()
                await asyncio.sleep(0.2)
                await elem.first.press("Control+A")
                await elem.first.press("Backspace")
                await asyncio.sleep(0.1)
                await elem.first.type(title, delay=15)
                log("✅", "标题已填写")
                await asyncio.sleep(0.5)
                return
            except Exception:
                pass

    log("ℹ️", "未找到独立标题输入区（可能抖音该模式仅有描述区）")


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
    upload_url = page.url  # 记录提交前的URL
    for i in range(24):  # ~24s
        await asyncio.sleep(1)
        # 关闭可能的弹窗（共创中心推广等）
        await page.evaluate("""() => {
            const els = document.querySelectorAll('*');
            for (const el of els) {
                if (el.textContent.trim() === '我知道了'
                    && el.offsetParent !== null && el.children.length === 0) {
                    el.click();
                }
            }
        }""")
        url = page.url
        # 严格匹配：URL必须变化且跳转到管理页/草稿确认页
        if url != upload_url and any(key in url for key in ["draft", "content/manage", "publish/success"]):
            return True

        success_texts = ["保存成功", "草稿已保存", "发布成功", "处理中", "暂存成功"]
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
        # Debug: list all buttons
        all_btns = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('button, [role="button"]'))
                .filter(b => b.offsetParent !== null)
                .map(b => b.textContent.trim().substring(0, 30))
                .filter(t => t.length > 0);
        }""")
        log("🔍", f"Visible buttons: {all_btns}")
        # 先关闭遮挡弹窗（共创中心推广等）
        await page.evaluate("""() => {
            const els = document.querySelectorAll('*');
            for (const el of els) {
                const t = el.textContent.trim();
                if ((t === '我知道了' || t === '确认' || t === '关闭')
                    && el.offsetParent !== null && el.children.length === 0) {
                    el.click();
                }
            }
        }""")
        await asyncio.sleep(1)
        # 再点击草稿按钮
        btn = page.locator("button:has-text('存草稿'), button:has-text('草稿'), button:has-text('暂存离开')")
        if await btn.count() > 0:
            await btn.first.click()
            await asyncio.sleep(3)
            # 点击后可能还有确认弹窗
            await page.evaluate("""() => {
                const els = document.querySelectorAll('*');
                for (const el of els) {
                    const t = el.textContent.trim();
                    if ((t === '我知道了' || t === '确认' || t === '暂存')
                        && el.offsetParent !== null && el.children.length === 0) {
                        el.click();
                    }
                }
            }""")
            await asyncio.sleep(1)
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


def _parse_daily_content(path: str, pick: int = 1) -> dict:
    """解析 daily-content 里的 douyin 产物，抽取第 pick 条。

    兼容格式：
    - `douyin-content-YYYY-MM-DD.md`（含 `## 1/2/3`）
    - `douyin-3posts-YYYY-MM-DD.txt`（含 `## 内容 1/2/3`）
    返回：{title, desc, tags}
    """
    text = Path(path).read_text(encoding="utf-8")

    # 支持两种分段锚点
    anchors = [f"## {pick}\n", f"## 内容 {pick}\n"]
    start = -1
    used_anchor = None
    for a in anchors:
        start = text.find(a)
        if start != -1:
            used_anchor = a
            break
    if start == -1:
        raise ValueError(f"未找到第 {pick} 条内容分段：{anchors}")

    rest = text[start + len(used_anchor):]

    # 截到下一段
    next_pos = rest.find("## ")
    block = rest if next_pos == -1 else rest[:next_pos]

    def _extract_after(label: str) -> str:
        idx = block.find(label)
        if idx == -1:
            return ""
        sub = block[idx + len(label):]
        # 截到空行双换行（或下一个 emoji label）
        parts = sub.split("\n\n", 1)
        return parts[0].strip()

    title = _extract_after("📌 标题：")
    # 优先取图文描述（更适合抖音描述区），否则取脚本
    desc = _extract_after("📝 图文描述：") or _extract_after("📝 视频脚本（60秒）：")
    tags_line = _extract_after("🏷️ 话题：")
    tags = [t.strip().lstrip("#") for t in tags_line.split() if t.strip()]

    if not title:
        # 兜底：用第一行
        title = (desc.split("\n", 1)[0] if desc else "").strip()[:TITLE_MAX]

    # 拼回 hashtags（如果原 desc 里没有）
    if tags and ("#" not in desc):
        desc = desc.rstrip() + "\n\n" + " ".join(f"#{t}" for t in tags[:5])

    return {"title": title.strip(), "desc": desc.strip(), "tags": tags}


async def doctor(args):
    """冒烟检查：打开上传页、截图、输出关键信号（不上传）。"""
    headless = not args.no_headless

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context_kwargs = {"viewport": {"width": 1280, "height": 900}}
        if STORAGE_STATE_FILE.exists():
            context_kwargs["storage_state"] = str(STORAGE_STATE_FILE)
        context = await browser.new_context(**context_kwargs)
        _ = await load_auth_state(context)
        page = await context.new_page()

        await page.goto(args.url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        needs_login = await is_login_page(page)

        counts = {
            "file_inputs": await page.locator("input[type='file']").count(),
            "desc_editables": await page.locator("[contenteditable='true'], textarea[placeholder*='描述']").count(),
            "draft_btn": await page.locator("button:has-text('存草稿'), button:has-text('草稿')").count(),
            "publish_btn": await page.locator("button:has-text('发布')").count(),
        }

        await page.screenshot(path=args.screenshot, full_page=True)
        log("📸", f"doctor screenshot: {args.screenshot}")
        log("🔎", f"url={page.url} needs_login={needs_login} counts={counts}")

        await save_auth_state(context)
        await browser.close()


async def main(args):
    # doctor 独立执行
    if args.command == "doctor":
        await doctor(args)
        return

    headless = not args.no_headless

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context_kwargs = {
            "viewport": {"width": 1280, "height": 900},
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        if STORAGE_STATE_FILE.exists():
            context_kwargs["storage_state"] = str(STORAGE_STATE_FILE)
        context = await browser.new_context(**context_kwargs)

        # 加载登录态（cookies/状态文件）
        _ = await load_auth_state(context)
        page = await context.new_page()

        # 检查登录态
        await page.goto(CREATOR_HOME, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # 如果仍处于登录页，等待手动登录
        if await is_login_page(page):
            if headless:
                await page.screenshot(path="/tmp/douyin_login_required.png", full_page=True)
                log("❌", "需要登录！已截图 /tmp/douyin_login_required.png；请使用 --no-headless 参数手动登录")
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
                page, args.file, args.title, args.desc,
                cover=args.cover, schedule=args.schedule, mode=args.mode
            )
        elif args.command == "image":
            files = [f.strip() for f in args.files.split(",")]
            success = await publish_image(page, files, args.title, args.desc, mode=args.mode)
        elif args.command == "daily":
            item = _parse_daily_content(args.source, pick=args.pick)
            title = item["title"]
            desc = item["desc"]

            if args.type == "image":
                files = [f.strip() for f in args.files.split(",")]
                success = await publish_image(page, files, title, desc, mode=args.mode)
            else:
                success = await publish_video(
                    page, args.file, title, desc,
                    cover=args.cover, schedule=args.schedule, mode=args.mode
                )

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

    # doctor: 不上传，只检查页面/截图
    d = sub.add_parser("doctor", help="冒烟检查（打开页面+截图+输出关键信号）")
    d.add_argument("--url", default=VIDEO_UPLOAD, help="检查的页面URL")
    d.add_argument("--screenshot", default="/tmp/douyin_doctor.png", help="截图输出路径")

    # video 子命令
    vid = sub.add_parser("video", help="发布视频")
    vid.add_argument("--file", "-f", required=True, help="视频文件路径")
    vid.add_argument("--title", "-t", default="", help="标题（可选，≤55字；部分模式仅描述区）")
    vid.add_argument("--desc", "-d", required=True, help="描述（含#话题）")
    vid.add_argument("--cover", help="封面图路径")
    vid.add_argument("--schedule", help="定时发布 (格式: 2026-03-20 20:00)")
    vid.add_argument("--mode", choices=["draft", "publish"], default="draft")

    # image 子命令
    img = sub.add_parser("image", help="发布图文")
    img.add_argument("--files", required=True, help="图片路径，逗号分隔（≥2张）")
    img.add_argument("--title", "-t", default="", help="标题（可选，≤55字；部分模式仅描述区）")
    img.add_argument("--desc", "-d", required=True, help="描述（含#话题）")
    img.add_argument("--mode", choices=["draft", "publish"], default="draft")

    # daily: 直接吃 daily-content 文件
    dl = sub.add_parser("daily", help="从 daily-content 产物读取标题/描述并发布")
    dl.add_argument("--source", required=True, help="daily-content douyin 文件路径（md/txt）")
    dl.add_argument("--pick", type=int, default=1, help="选择第几条（1/2/3）")
    dl.add_argument("--type", choices=["video", "image"], default="video", help="发布类型")
    dl.add_argument("--mode", choices=["draft", "publish"], default="draft")
    # 资源参数（按 type 使用）
    dl.add_argument("--file", "-f", help="视频文件路径（type=video 必填）")
    dl.add_argument("--files", help="图片路径（type=image 必填，逗号分隔）")
    dl.add_argument("--cover", help="封面图路径（可选）")
    dl.add_argument("--schedule", help="定时发布 (格式: 2026-03-20 20:00)")

    args = parser.parse_args()
    asyncio.run(main(args))
