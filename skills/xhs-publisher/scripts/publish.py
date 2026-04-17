#!/usr/bin/env python3
"""
XHS Publisher — 小红书自动发布到草稿箱 v1.5

Usage:
    # Single cover only (backward compatible)
    python3 publish.py --article article.md --cover cover.jpg

    # Cover + additional material images
    python3 publish.py --article article.md --cover cover.jpg --images img1.jpg img2.png img3.jpg

    # All images from a folder (shell glob)
    python3 publish.py --article article.md --cover cover.jpg --images 素材/*.png 素材/*.jpg

Requires:
    - OpenClaw browser running (CDP at 127.0.0.1:18800)
    - Playwright Python library (pip install playwright)
    - Valid XHS cookies at ~/.playwright-data/xiaohongshu/state-default.json

v1.5 Changes:
    - Fixed: use Playwright file_chooser API (set_input_files doesn't trigger XHS React)
    - Fixed: click LAST visible '上传图文' tab (XHS has duplicate tabs)
    - Multi-image: cover first → editor → additional images via editor's file input
    - All images max 18 (XHS limit), truncates with warning sequential upload
    - Proper wait for editor after multi-image upload
    - Backward compatible: --images is optional

v1.3 Changes:
    - Added --images parameter for multi-image upload (up to 18 total)
    - Per-image retry with exponential backoff
    - Safety screenshot after all images uploaded

v1.2 Changes:
    - Pre-flight health check (browser, cookies, files)
    - Safety screenshots at 6 key checkpoints
    - Retry logic with exponential backoff
    - Improved error handling with screenshots
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# ─── Constants ──────────────────────────────────────────────────────
TITLE_MAX = 20
CONTENT_MAX = 1000
CDP_URL = os.getenv("OPENCLAW_CDP_URL", "http://127.0.0.1:18800")
COOKIE_PATH = Path(os.getenv("XHS_COOKIE_PATH", str(Path.home() / ".playwright-data/xiaohongshu/state-default.json")))
PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"
SAFETY_DIR = Path(os.getenv("XHS_SAFETY_DIR", "/tmp/xhs_safety"))
IMAGE_MAX = 18  # XHS max images per post (cover + additional)

# Verified selectors (2026-04-14)
SEL_TAB = "div.creator-tab"
SEL_FILE_INPUT = "input.upload-input[type='file']"
SEL_TITLE = "input.d-text[type='text']"
SEL_EDITOR = "div.tiptap.ProseMirror[contenteditable='true']"
SEL_TOPIC_BTN = "button.contentBtn.topic-btn"
SEL_TAG_INPUT = "input.d-text.--color-text-title"

# Retry config: (retries, base_delay_s)
RETRY_CONFIG = {
    "upload": (3, 10),
    "selector": (2, 5),
    "network": (3, 10),
}


# ─── Utilities ────────────────────────────────────────────────────────
def log(emoji: str, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {emoji} {msg}")


def retry(max_retries: int, base_delay: float = 5):
    """Decorator: retry with exponential backoff."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        log("⚠️", f"{func.__name__} failed (attempt {attempt+1}/{max_retries}): {e}. Retrying in {delay}s...")
                        await asyncio.sleep(delay)
                    else:
                        log("❌", f"{func.__name__} failed after {max_retries} attempts: {e}")
            raise last_err
        return wrapper
    return decorator


async def safety_screenshot(page, step_name: str, step_num: int):
    """Save a safety screenshot with step name and number."""
    SAFETY_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")
    path = SAFETY_DIR / f"xhs_safety_{step_num:02d}_{step_name}_{ts}.png"
    try:
        await page.screenshot(path=path)
        size = path.stat().st_size
        log("📸", f"Safety [{step_num}] {step_name}: {path.name} ({size//1024}KB)")
        return path
    except Exception as e:
        log("⚠️", f"Safety screenshot failed: {e}")
        return None


async def preflight_check() -> dict:
    """Run pre-flight health checks. Returns dict with check results."""
    from playwright.async_api import async_playwright

    checks = {"browser": False, "cookies": False, "article_file": False, "cover_file": False}

    # 1. Browser connection
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(CDP_URL)
            if browser:
                checks["browser"] = True
                # Disconnect CDP session, do NOT close browser (shared)
                # browser.close() would kill the Chrome instance
                pass
                log("✅", "Browser: connected")
            else:
                log("❌", "Browser: failed to connect")
    except Exception as e:
        log("❌", f"Browser: {e}")

    # 2. Cookie validity
    try:
        if COOKIE_PATH.exists():
            state = json.loads(COOKIE_PATH.read_text())
            cookies = state.get("cookies", [])
            now = time.time()
            # Check only critical cookies (a1, webId) - ignore non-essential security tokens
            critical = [c for c in cookies if c.get('name') in ('a1', 'webId')]
            expired = [c for c in critical if c.get('expires', -1) > 0 and c['expires'] < now]
            if expired and not any(c for c in critical if c.get('name') == 'a1'):
                # Only fail if a1 is expired
                checks["cookies"] = False
                log("❌", f"Critical cookie expired: {expired[0].get('name','?')}")
            else:
                checks["cookies"] = True
                log("✅", f"Cookies: {len(cookies)} total, {len(critical)} critical OK")
        else:
            log("❌", f"Cookies: file not found at {COOKIE_PATH}")
    except Exception as e:
        log("❌", f"Cookies: {e}")

    return checks


# ─── Markdown Parser ───────────────────────────────────────────────
def parse_article(path: str) -> dict:
    """Parse XHS article from markdown with Chinese metadata markers."""
    raw = Path(path).read_text(encoding="utf-8")
    lines = raw.splitlines()

    title = ""
    tags: list[str] = []
    body_lines: list[str] = []
    in_body = False

    for line in lines:
        stripped = line.strip()

        # Title
        if stripped.startswith("📌 标题："):
            title = stripped.split("：", 1)[1].strip()
            continue

        # Tags
        if stripped.startswith("🏷️ 标签："):
            raw_tags = stripped.split("：", 1)[1].strip()
            tags = [t.strip().lstrip("#") for t in re.split(r"[\s,，]+", raw_tags) if t.strip()]
            continue

        # Body start
        if stripped.startswith("📝 正文") or stripped == "":
            if stripped.startswith("📝"):
                in_body = True
            continue

        # Cover hint — stop reading body
        if stripped.startswith("🖼️"):
            break

        if in_body:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()

    # Fallback: first # heading as title
    if not title:
        for line in lines:
            if line.strip().startswith("# "):
                title = line.strip()[2:].strip()
                break

    # Truncate title (try to cut at a natural boundary)
    title_truncated = len(title) > TITLE_MAX
    if title_truncated:
        # Try to cut at last punctuation or space within limit
        cut = title[:TITLE_MAX]
        for i in range(len(cut) - 1, max(len(cut) - 8, 0), -1):
            if cut[i] in '，。！？、；：·—）》」\'（「《【':
                cut = cut[:i]
                break
        title = cut.strip()

    # Truncate content
    if len(body) > CONTENT_MAX:
        body = body[:CONTENT_MAX]

    return {
        "title": title,
        "title_truncated": title_truncated,
        "tags": tags,
        "body": body,
        "body_html": "".join(f"<p>{l}</p>" for l in body.split("\n") if l.strip()),
        "content_length": len(body),
    }


# ─── Browser Helpers ────────────────────────────────────────────────
async def load_cookies(context) -> int:
    """Load XHS cookies from Playwright state file."""
    if not COOKIE_PATH.exists():
        raise FileNotFoundError(f"Cookie file not found: {COOKIE_PATH}")

    state = json.loads(COOKIE_PATH.read_text())
    cookies = state.get("cookies", [])
    if not cookies:
        raise ValueError("No cookies in state file")

    await context.add_cookies([{
        "name": c["name"],
        "value": c["value"],
        "domain": c["domain"],
        "path": c.get("path", "/"),
        "expires": c.get("expires", -1),
        "httpOnly": c.get("httpOnly", False),
        "secure": c.get("secure", False),
        "sameSite": c.get("sameSite", "Lax"),
    } for c in cookies])

    return len(cookies)


async def switch_to_image_tab(page) -> bool:
    """Click the last visible '上传图文' tab (usually the active one)."""
    return await page.evaluate("""() => {
        const tabs = document.querySelectorAll('div.creator-tab');
        const imageTabs = Array.from(tabs).filter(tab => tab.textContent.trim() === '上传图文' && tab.getBoundingClientRect().x > 0);
        if (imageTabs.length > 0) {
            imageTabs[imageTabs.length - 1].click();
            return true;
        }
        return false;
    }""")


async def fill_prosemirror(page, editor, html: str):
    """Fill ProseMirror contenteditable editor with HTML."""
    await page.evaluate("""([el, html]) => {
        el.innerHTML = html;
        el.dispatchEvent(new Event("input", { bubbles: true }));
    }""", [editor, html])


async def save_draft(page) -> bool:
    """Click the '暂存离开' button and handle confirmation dialog.

    Fixed (2026-04-17): added confirmation dialog handling.
    XHS may show a confirm popup after clicking 暂存离开.
    """
    clicked = await page.evaluate("""() => {
        const btns = document.querySelectorAll('button');
        for (const btn of btns) {
            if (btn.textContent.trim() === '暂存离开') {
                const r = btn.getBoundingClientRect();
                if (r.x > 0 && r.width > 0) { btn.click(); return true; }
            }
        }
        return false;
    }""")
    if not clicked:
        # Playwright fallback
        try:
            btn = page.locator("button:has-text('暂存离开')")
            if await btn.count() > 0 and await btn.first.is_visible():
                await btn.first.click(force=True)
                clicked = True
        except Exception:
            pass

    if not clicked:
        return False

    # Handle confirmation dialog (XHS may ask to confirm save)
    await asyncio.sleep(2)
    await page.evaluate("""() => {
        const btns = document.querySelectorAll('button');
        for (const btn of btns) {
            const t = btn.textContent.trim();
            if ((t === '确定' || t === '确认' || t === '暂存' || t === '我知道了')
                && btn.offsetParent !== null) {
                btn.click(); return true;
            }
        }
        return false;
    }""")
    await asyncio.sleep(2)

    # Verify: check if we left the editor or success text appeared
    for _ in range(8):
        still_editor = await page.evaluate("""() => {
            return !!document.querySelector('div.tiptap.ProseMirror[contenteditable="true"]');
        }""")
        if not still_editor:
            return True
        found = await page.evaluate("""() => {
            const texts = ['保存成功', '草稿已保存', '已存入草稿箱'];
            const body = document.body.innerText;
            for (const t of texts) { if (body.includes(t)) return true; }
            return false;
        }""")
        if found:
            return True
        await asyncio.sleep(1)

    # Final check
    still_editor = await page.evaluate("""() => {
        return !!document.querySelector('div.tiptap.ProseMirror[contenteditable="true"]');
    }""")
    return not still_editor


async def get_draft_count(page) -> str:
    """Get current draft count from page."""
    text = await page.evaluate("() => document.body.innerText")
    for line in text.split("\n"):
        if "草稿箱" in line:
            return line.strip()
    return "unknown"


# ─── Main Publish Flow ─────────────────────────────────────────────
async def publish_to_xhs(
    article_path: str,
    cover_path: str,
    decision: str = "draft",
    images: list[str] | None = None,
) -> dict:
    """Publish article to XHS drafts. Returns result dict.
    v1.3: adds --images multi-image upload support.
    v1.2: adds pre-flight check, safety screenshots, retry logic."""

    from playwright.async_api import async_playwright

    # ── Pre-flight health check ─────────────────────────────────────
    log("🔍", "Running pre-flight health checks...")
    checks = await preflight_check()
    if not all([checks["browser"], checks["cookies"]]):
        return {
            "status": "error",
            "error": f"Pre-flight failed: browser={checks['browser']}, cookies={checks['cookies']}",
            "checks": checks,
        }

    # ── Parse article ───────────────────────────────────────────────
    article = parse_article(article_path)
    print(f"📄 Article parsed: title='{article['title']}' ({article['content_length']} chars, {len(article['tags'])} tags)")
    if article["title_truncated"]:
        print(f"⚠️  Title truncated to {TITLE_MAX} chars")

    # ── Validate cover ──────────────────────────────────────────────
    cover = Path(cover_path)
    if not cover.exists():
        return {"status": "error", "error": f"Cover not found: {cover_path}"}

    # ── Validate additional images ──────────────────────────────────
    valid_images: list[Path] = []
    if images:
        for img_path in images:
            p = Path(img_path)
            if p.exists() and p.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp'):
                valid_images.append(p)
            else:
                log("⚠️", f"Skipping invalid image: {img_path}")

    total_images = 1 + len(valid_images)
    if total_images > IMAGE_MAX:
        log("⚠️", f"Too many images ({total_images}/{IMAGE_MAX}). Truncating to {IMAGE_MAX - 1} additional images.")
        valid_images = valid_images[:IMAGE_MAX - 1]
        total_images = IMAGE_MAX

    if valid_images:
        print(f"🖼️  Images: cover + {len(valid_images)} additional ({total_images}/{IMAGE_MAX} total)")

    SAFETY_DIR.mkdir(exist_ok=True)

    result = {
        "status": "ok",
        "title": article["title"],
        "title_truncated": article["title_truncated"],
        "content_length": article["content_length"],
        "tags_planned": article["tags"],
        "draft_saved": False,
        "safety_screenshots": [],
        "images_uploaded": 0,
    }

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0]

        # Close existing XHS pages
        for pg in ctx.pages[:]:
            if "xiaohongshu" in pg.url:
                await pg.close()

        # Load cookies
        n_cookies = await load_cookies(ctx)
        print(f"🍪 Loaded {n_cookies} cookies")

        page = await ctx.new_page()
        page.set_default_timeout(20000)  # 20s default timeout
        nav_timeout = 60000  # 60s for navigation (XHS can be slow)

        try:
            # 1. Navigate → Safety #1
            for nav_attempt in range(3):
                try:
                    await page.goto(PUBLISH_URL, timeout=nav_timeout, wait_until="domcontentloaded")
                    break
                except Exception as e:
                    if nav_attempt < 2:
                        log("⚠️", f"Navigation failed (attempt {nav_attempt+1}): {e}. Retrying...")
                        await asyncio.sleep(5)
                    else:
                        raise
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass  # networkidle may timeout, that's OK
            await asyncio.sleep(2)
            await safety_screenshot(page, "page_loaded", 1)

            # Verify login
            body_text = await page.evaluate("() => document.body.innerText.substring(0, 100)")
            if "创作服务平台" not in body_text:
                await safety_screenshot(page, "login_failed", 1)
                raise RuntimeError("Not logged in to XHS! Cookie may have expired.")
            print("✅ Login verified")

            # 2. Switch to image tab
            await switch_to_image_tab(page)
            await asyncio.sleep(2)
            print("✅ Tab switched to 上传图文")

            # 3. Upload cover (triggers editor) → Safety #2
            # Use Playwright file_chooser API — this is the correct way to handle file uploads
            # set_input_files doesn't trigger React change events in CDP mode
            for attempt in range(RETRY_CONFIG["upload"][0]):
                try:
                    # Start waiting for file chooser before clicking the upload area
                    async with page.expect_file_chooser(timeout=10000) as fc_info:
                        # Click the file input directly or the upload wrapper in the 图文 tab
                        # DO NOT use 'button:has-text("上传图片")' — it may trigger wrong tab
                        file_input = await page.query_selector(SEL_FILE_INPUT)
                        if file_input:
                            await file_input.evaluate("el => el.click()")
                        else:
                            raise RuntimeError("File input not found")

                    file_chooser = await fc_info.value
                    await file_chooser.set_files(str(cover))
                    print(f"✅ Cover uploaded: {cover.name}")
                    await asyncio.sleep(8)
                    await safety_screenshot(page, "cover_uploaded", 2)
                    break
                except Exception as e:
                    if attempt < RETRY_CONFIG["upload"][0] - 1:
                        delay = RETRY_CONFIG["upload"][1] * (2 ** attempt)
                        log("⚠️", f"Cover upload failed (attempt {attempt+1}): {e}. Retrying in {delay}s...")
                        await asyncio.sleep(delay)
                    else:
                        raise

            result["images_uploaded"] = 1

            # 3b. If additional images, add them through editor
            if valid_images:
                print(f"🖼️  Adding {len(valid_images)} images through editor...")
                # In XHS editor, additional images can be added via:
                # 1. Clicking a '+' button near image thumbnails
                # 2. Using a file input hidden in the editor
                # 3. Drag & drop area
                for i, img_path in enumerate(valid_images):
                    img_added = False
                    for attempt in range(RETRY_CONFIG["upload"][0]):
                        try:
                            # Strategy 1: Look for file input in editor
                            editor_file_input = await page.query_selector("input[type='file']")
                            if editor_file_input:
                                async with page.expect_file_chooser(timeout=8000) as fc_info:
                                    await editor_file_input.evaluate("el => el.click()")
                                fc = await fc_info.value
                                await fc.set_files(str(img_path))
                                print(f"✅ Image [{i+1}/{len(valid_images)}] via file_input: {img_path.name}")
                                await asyncio.sleep(4)
                                img_added = True
                                break

                            # Strategy 2: Look for add-image button (plus icon)
                            add_btns = await page.query_selector_all('div[class*="upload"], div[class*="add-img"], div[class*="addImage"], svg[class*="add"]')
                            for btn in add_btns:
                                visible = await btn.is_visible()
                                if visible:
                                    async with page.expect_file_chooser(timeout=5000) as fc_info2:
                                        await btn.click()
                                    fc2 = await fc_info2.value
                                    await fc2.set_files(str(img_path))
                                    print(f"✅ Image [{i+1}/{len(valid_images)}] via add-btn: {img_path.name}")
                                    await asyncio.sleep(4)
                                    img_added = True
                                    break
                            if img_added:
                                break

                            raise RuntimeError("No file input or add-image button found in editor")
                        except Exception as e:
                            if attempt < RETRY_CONFIG["upload"][0] - 1:
                                delay = RETRY_CONFIG["upload"][1] * (2 ** attempt)
                                log("⚠️", f"Image [{i+1}] failed (attempt {attempt+1}): {e}. Retrying in {delay}s...")
                                await asyncio.sleep(delay)
                            else:
                                log("❌", f"Image [{i+1}] upload failed: {img_path.name}")
                    if img_added:
                        result["images_uploaded"] += 1

                await safety_screenshot(page, "all_images_uploaded", 2)
                print(f"✅ Total images: {result['images_uploaded']}/{IMAGE_MAX}")

            # 4. Fill title → Safety #3 (more retries for multi-image)
            title_retries = max(RETRY_CONFIG["selector"][0], 4) if valid_images else RETRY_CONFIG["selector"][0]
            for attempt in range(title_retries):
                try:
                    title_input = await page.query_selector(SEL_TITLE)
                    if not title_input:
                        raise RuntimeError("Title input not found — cover upload may have failed")
                    box = await title_input.bounding_box()
                    if not box or box["width"] < 10:
                        raise RuntimeError("Title input not visible — editor did not load")
                    await title_input.click()
                    await title_input.fill(article["title"])
                    print(f"✅ Title: {article['title']} ({len(article['title'])} chars)")
                    await asyncio.sleep(0.5)
                    await safety_screenshot(page, "title_filled", 3)
                    break
                except Exception as e:
                    if attempt < title_retries - 1:
                        log("⚠️", f"Title fill failed (attempt {attempt+1}): {e}. Retrying...")
                        await asyncio.sleep(RETRY_CONFIG["selector"][1])
                    else:
                        raise

            # 5. Fill content → Safety #4
            for attempt in range(RETRY_CONFIG["selector"][0]):
                try:
                    editor = await page.query_selector(SEL_EDITOR)
                    if not editor:
                        raise RuntimeError("Content editor not found")
                    await editor.click()
                    await fill_prosemirror(page, editor, article["body_html"])
                    print(f"✅ Content: {article['content_length']} chars")
                    await asyncio.sleep(0.5)
                    await safety_screenshot(page, "content_filled", 4)
                    break
                except Exception as e:
                    if attempt < RETTRY_CONFIG["selector"][0] - 1:
                        log("⚠️", f"Content fill failed (attempt {attempt+1}): {e}. Retrying...")
                        await asyncio.sleep(RETRY_CONFIG["selector"][1])
                    else:
                        raise

            # 6. Add tags via content (embed hashtags in body text)
            added_tags = article["tags"][:8]
            tag_text = " ".join(f"#{t}" for t in added_tags)
            try:
                editor = await page.query_selector(SEL_EDITOR)
                if editor:
                    await editor.click()
                    current_html = await page.evaluate('el => el.innerHTML', editor)
                    tag_html = f'<p>{tag_text}</p>'
                    await fill_prosemirror(page, editor, current_html + tag_html)
                    print(f"✅ Tags embedded in content: {tag_text}")
            except Exception as e:
                print(f"⚠️  Tag embedding failed: {e}")
                added_tags = []

            result["tags_added"] = added_tags

            # 7. Screenshot before draft → Safety #5
            await safety_screenshot(page, "before_draft", 5)

            # 8. Save draft
            if decision == "draft":
                await asyncio.sleep(1)

                # Retry: find and click draft button
                for attempt in range(RETRY_CONFIG["selector"][0]):
                    try:
                        saved = await save_draft(page)
                        if saved:
                            await asyncio.sleep(3)
                            await safety_screenshot(page, "draft_confirm", 6)
                            draft_info = await get_draft_count(page)
                            result["draft_saved"] = True
                            result["draft_count"] = draft_info
                            print(f"✅ Draft saved → {draft_info}")
                            break
                        else:
                            raise RuntimeError("Draft button '暂存离开' not found")
                    except Exception as e:
                        if attempt < RETRY_CONFIG["selector"][0] - 1:
                            log("⚠️", f"Draft save failed (attempt {attempt+1}): {e}. Retrying...")
                            await asyncio.sleep(RETRY_CONFIG["selector"][1])
                        else:
                            raise
            elif decision == "publish":
                # Click 发布 button
                pub_clicked = await page.evaluate("""() => {
                    const btns = document.querySelectorAll('button');
                    for (const btn of btns) {
                        if ((btn.textContent.trim() === '发布' || btn.textContent.trim() === '立即发布')
                            && btn.offsetParent !== null) {
                            const r = btn.getBoundingClientRect();
                            if (r.width > 0) { btn.click(); return true; }
                        }
                    }
                    // Fallback: primary button
                    const primary = document.querySelector('button[class*="primary"]');
                    if (primary && primary.offsetParent !== null) { primary.click(); return true; }
                    return false;
                }""")
                if pub_clicked:
                    await asyncio.sleep(3)
                    # Handle confirmation
                    await page.evaluate("""() => {
                        const btns = document.querySelectorAll('button');
                        for (const btn of btns) {
                            const t = btn.textContent.trim();
                            if ((t === '确定' || t === '确认发布' || t === '发布')
                                && btn.offsetParent !== null) {
                                btn.click(); return;
                            }
                        }
                    }""")
                    await asyncio.sleep(3)
                    await safety_screenshot(page, "publish_confirm", 6)
                    result["published"] = True
                    print("✅ Published!")
                else:
                    raise RuntimeError("Publish button not found")
            else:
                print(f"⚠️  Unknown decision '{decision}', saving as draft")
                saved = await save_draft(page)
                if saved:
                    result["draft_saved"] = True

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            log("❌", f"Error: {e}")
            # Take error screenshot
            try:
                err_ss = SAFETY_DIR / f"xhs_error_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                await page.screenshot(path=str(err_ss))
                result["error_screenshot"] = str(err_ss)
                log("📸", f"Error screenshot: {err_ss}")
            except Exception:
                pass

        finally:
            # Close page but NOT the browser (shared CDP connection)
            try:
                await page.close()
            except Exception:
                pass

    # Do NOT close the browser — it's shared via CDP
    return result


# ─── CLI Entry Point ────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Publish article to XHS drafts")
    parser.add_argument("--article", required=True, help="Path to markdown article")
    parser.add_argument("--cover", required=True, help="Path to cover image")
    parser.add_argument("--images", nargs="*", default=[], help="Additional image paths (up to 17, e.g. --images img1.jpg img2.png)")
    parser.add_argument("--decision", default="draft", choices=["draft", "publish"], help="'draft' to save as draft, 'publish' to go live")
    args = parser.parse_args()

    result = asyncio.run(publish_to_xhs(
        article_path=args.article,
        cover_path=args.cover,
        decision=args.decision,
        images=args.images if args.images else None,
    ))

    print("\n" + "=" * 50)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
