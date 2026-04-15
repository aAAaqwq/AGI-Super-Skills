#!/usr/bin/env python3
"""
Douyin Publisher — 抖音自动发布图文到草稿箱

Usage:
    python3 publish.py --article article.md --cover cover.jpg [--decision draft]

Requires:
    - OpenClaw browser running (CDP at 127.0.0.1:18800)
    - Playwright Python library (pip install playwright)
    - Valid Douyin cookies at ~/.playwright-data/douyin/state-default.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# ─── Constants ──────────────────────────────────────────────────────
TITLE_MAX = 20
CONTENT_MAX = 1000
CDP_URL = "http://127.0.0.1:18800"
COOKIE_PATH = Path.home() / ".playwright-data/douyin/state-default.json"
PUBLISH_URL = "https://creator.douyin.com/creator-micro/content/upload"

# Verified selectors (2026-04-14, post-login)
SEL_TAB_ITEM = "div[class*='tab-item']"  # text: 发布视频/发布图文/发布全景视频/发布文章
SEL_IMAGE_INPUT = 'input[type="file"][accept*="image"]'
SEL_VIDEO_INPUT = 'input[type="file"][accept*="video"]'
SEL_TITLE = 'input[placeholder="添加作品标题"]'
SEL_EDITOR = 'div.editor-comp-publish[contenteditable="true"]'
SEL_PUBLISH = "button[class*='primary']"  # text: 发布
SEL_DRAFT = "button[class*='cancel-btn']"  # text: 暂存离开


# ─── Markdown Parser ───────────────────────────────────────────────
def parse_article(path: str) -> dict:
    """Parse article from markdown with Chinese metadata markers."""
    raw = Path(path).read_text(encoding="utf-8")
    lines = raw.splitlines()

    title = ""
    tags: list[str] = []
    body_lines: list[str] = []
    in_body = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("📌 标题："):
            title = stripped.split("：", 1)[1].strip()
            continue
        if stripped.startswith("🏷️ 标签："):
            raw_tags = stripped.split("：", 1)[1].strip()
            tags = [t.strip().lstrip("#") for t in re.split(r"[\s,，]+", raw_tags) if t.strip()]
            continue
        if stripped.startswith("📝 正文") or stripped == "":
            if stripped.startswith("📝"):
                in_body = True
            continue
        if stripped.startswith("🖼️"):
            break

        if in_body:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()

    if not title:
        for line in lines:
            if line.strip().startswith("# "):
                title = line.strip()[2:].strip()
                break

    # Truncate title at natural boundary
    title_truncated = len(title) > TITLE_MAX
    if title_truncated:
        cut = title[:TITLE_MAX]
        for i in range(len(cut) - 1, max(len(cut) - 8, 0), -1):
            if cut[i] in '，。！？、；：·—）》」\'（「《【':
                cut = cut[:i]
                break
        title = cut.strip()

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
    if not COOKIE_PATH.exists():
        raise FileNotFoundError(f"Cookie file not found: {COOKIE_PATH}")
    state = json.loads(COOKIE_PATH.read_text())
    cookies = state.get("cookies", [])
    if not cookies:
        raise ValueError("No cookies in state file")
    await context.add_cookies([{
        "name": c["name"], "value": c["value"],
        "domain": c["domain"], "path": c.get("path", "/"),
        "expires": c.get("expires", -1),
        "httpOnly": c.get("httpOnly", False),
        "secure": c.get("secure", False),
        "sameSite": c.get("sameSite", "Lax"),
    } for c in cookies])
    return len(cookies)


async def switch_to_image_tab(page) -> bool:
    return await page.evaluate("""() => {
        const tabs = document.querySelectorAll('div[class*="tab-item"]');
        for (const t of tabs) {
            if (t.textContent.trim() === '发布图文') { t.click(); return true; }
        }
        return false;
    }""")


async def fill_contenteditable(page, editor, html: str):
    await page.evaluate("""([el, html]) => {
        el.innerHTML = html;
        el.dispatchEvent(new Event("input", { bubbles: true }));
    }""", [editor, html])


async def save_draft(page) -> bool:
    return await page.evaluate("""() => {
        const btns = document.querySelectorAll('button');
        for (const btn of btns) {
            if (btn.textContent.trim() === '暂存离开') {
                const r = btn.getBoundingClientRect();
                if (r.x > 0 && r.width > 0) { btn.click(); return true; }
            }
        }
        return false;
    }""")


# ─── Main Publish Flow ─────────────────────────────────────────────
async def publish_to_douyin(
    article_path: str,
    cover_path: str,
    decision: str = "draft",
) -> dict:
    from playwright.async_api import async_playwright

    article = parse_article(article_path)
    print(f"📄 Article parsed: title='{article['title']}' ({article['content_length']} chars, {len(article['tags'])} tags)")
    if article["title_truncated"]:
        print(f"⚠️  Title truncated to {TITLE_MAX} chars")

    cover = Path(cover_path)
    if not cover.exists():
        raise FileNotFoundError(f"Cover not found: {cover_path}")

    result = {
        "status": "ok",
        "title": article["title"],
        "title_truncated": article["title_truncated"],
        "content_length": article["content_length"],
        "tags_planned": article["tags"],
        "draft_saved": False,
    }

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0]

        for pg in ctx.pages[:]:
            if "douyin.com" in pg.url:
                await pg.close()

        n_cookies = await load_cookies(ctx)
        print(f"🍪 Loaded {n_cookies} cookies")

        page = await ctx.new_page()
        page.set_default_timeout(10000)

        try:
            # 1. Navigate
            await page.goto(PUBLISH_URL, timeout=30000)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)

            # Check if redirected to login
            body_text = await page.evaluate("() => document.body.innerText.substring(0, 200)")
            if "扫码登录" in body_text or "验证码登录" in body_text:
                raise RuntimeError("Not logged in to Douyin! Cookie may have expired.")
            if "发布视频" not in body_text and "上传" not in body_text:
                raise RuntimeError(f"Unexpected page state: {body_text[:100]}")
            print("✅ Login verified")

            # 2. Switch to image tab
            await switch_to_image_tab(page)
            await asyncio.sleep(1)
            print("✅ Switched to 发布图文 tab")

            # 3. Check for draft recovery dialog
            draft_dialog = await page.evaluate("""() => {
                const els = document.querySelectorAll('*');
                for (const el of els) {
                    if (el.textContent.includes('继续编辑') && el.textContent.includes('放弃')) {
                        const r = el.getBoundingClientRect();
                        if (r.x > 0 && r.width > 0) return true;
                    }
                }
                return false;
            }""")
            if draft_dialog:
                # Click 放弃 to start fresh
                await page.evaluate("""() => {
                    const els = document.querySelectorAll('*');
                    for (const el of els) {
                        if (el.textContent.trim() === '放弃') {
                            const r = el.getBoundingClientRect();
                            if (r.x > 0 && r.width > 0) { el.click(); return; }
                        }
                    }
                }""")
                await asyncio.sleep(1)
                print("✅ Dismissed draft recovery dialog")

            # 4. Upload image
            image_input = await page.query_selector(SEL_IMAGE_INPUT)
            if not image_input:
                raise RuntimeError("Image input not found")
            await image_input.set_input_files(str(cover))
            print(f"✅ Cover uploaded: {cover.name}")
            await asyncio.sleep(5)

            # 5. Check if we're now on the editor page
            editor_url = page.url
            if "post/image" not in editor_url and "draft" not in editor_url:
                # May need to wait for redirect
                await asyncio.sleep(3)

            # 6. Fill title
            title_input = await page.query_selector(SEL_TITLE)
            if not title_input:
                raise RuntimeError("Title input not found — editor may not have loaded")
            box = await title_input.bounding_box()
            if not box or box["width"] < 10:
                raise RuntimeError("Title input not visible")
            await title_input.click()
            await title_input.fill(article["title"])
            print(f"✅ Title: {article['title']} ({len(article['title'])} chars)")

            # 7. Fill description
            editor = await page.query_selector(SEL_EDITOR)
            if not editor:
                raise RuntimeError("Content editor not found")
            await editor.click()

            # Build description with tags appended
            tag_text = " ".join(f"#{t}" for t in article["tags"][:5])
            full_desc = article["body"]
            if tag_text:
                full_desc += f"\n{tag_text}"
            desc_html = "".join(f"<p>{l}</p>" for l in full_desc.split("\n") if l.strip())

            await fill_contenteditable(page, editor, desc_html)
            print(f"✅ Description: {len(full_desc)} chars (with {len(article['tags'][:5])} tags)")

            result["tags_added"] = article["tags"][:5]

            # 8. Screenshot
            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            ss_path = f"/tmp/douyin_publish_{ts}.png"
            await page.screenshot(path=ss_path)
            result["screenshot_path"] = ss_path
            print(f"✅ Screenshot: {ss_path}")

            # 9. Save draft
            if decision == "draft":
                await asyncio.sleep(1)
                saved = await save_draft(page)
                if saved:
                    await asyncio.sleep(3)
                    print("✅ Draft saved!")
                    result["draft_saved"] = True
                else:
                    raise RuntimeError("Draft button '暂存离开' not found")
            else:
                print("⚠️  Only 'draft' decision is supported. Skipping save.")

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            print(f"❌ Error: {e}")
            try:
                err_ss = f"/tmp/douyin_error_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                await page.screenshot(path=err_ss)
                result["error_screenshot"] = err_ss
            except Exception:
                pass
        finally:
            try:
                await page.close()
            except Exception:
                pass

    return result


# ─── CLI ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Publish article to Douyin drafts")
    parser.add_argument("--article", required=True, help="Path to markdown article")
    parser.add_argument("--cover", required=True, help="Path to cover image")
    parser.add_argument("--decision", default="draft", choices=["draft"], help="Publish decision")
    args = parser.parse_args()

    result = asyncio.run(publish_to_douyin(
        article_path=args.article,
        cover_path=args.cover,
        decision=args.decision,
    ))

    print("\n" + "=" * 50)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
