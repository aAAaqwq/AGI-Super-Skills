#!/usr/bin/env python3
"""
XHS Publisher — 小红书自动发布到草稿箱

Usage:
    python3 publish.py --article article.md --cover cover.jpg [--decision draft]

Requires:
    - OpenClaw browser running (CDP at 127.0.0.1:18800)
    - Playwright Python library (pip install playwright)
    - Valid XHS cookies at ~/.playwright-data/xiaohongshu/state-default.json
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
COOKIE_PATH = Path.home() / ".playwright-data/xiaohongshu/state-default.json"
PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"

# Verified selectors (2026-04-14)
SEL_TAB = "div.creator-tab"
SEL_FILE_INPUT = "input.upload-input[type='file']"
SEL_TITLE = "input.d-text[type='text']"
SEL_EDITOR = "div.tiptap.ProseMirror[contenteditable='true']"
SEL_TOPIC_BTN = "button.contentBtn.topic-btn"
SEL_TAG_INPUT = "input.d-text.--color-text-title"


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
    """Click the visible '上传图文' tab."""
    return await page.evaluate("""() => {
        const tabs = document.querySelectorAll('div.creator-tab');
        for (const tab of tabs) {
            if (tab.textContent.trim() === '上传图文') {
                const r = tab.getBoundingClientRect();
                if (r.x > 0 && r.y > 0) { tab.click(); return true; }
            }
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
    """Click the '暂存离开' button."""
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
) -> dict:
    """Publish article to XHS drafts. Returns result dict."""

    from playwright.async_api import async_playwright

    # Parse article
    article = parse_article(article_path)
    print(f"📄 Article parsed: title='{article['title']}' ({article['content_length']} chars, {len(article['tags'])} tags)")
    if article["title_truncated"]:
        print(f"⚠️  Title truncated to {TITLE_MAX} chars")

    # Validate cover
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

        # Close existing XHS pages
        for pg in ctx.pages[:]:
            if "xiaohongshu" in pg.url:
                await pg.close()

        # Load cookies
        n_cookies = await load_cookies(ctx)
        print(f"🍪 Loaded {n_cookies} cookies")

        page = await ctx.new_page()
        page.set_default_timeout(10000)  # 10s default timeout per action

        try:
            # 1. Navigate
            await page.goto(PUBLISH_URL, timeout=15000)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            # Verify login
            body_text = await page.evaluate("() => document.body.innerText.substring(0, 100)")
            if "创作服务平台" not in body_text:
                raise RuntimeError("Not logged in to XHS! Cookie may have expired.")
            print("✅ Login verified")

            # 2. Switch to image tab
            await switch_to_image_tab(page)
            await asyncio.sleep(1)
            print("✅ Tab switched to 上传图文")

            # 3. Upload cover
            file_input = await page.query_selector(SEL_FILE_INPUT)
            if not file_input:
                raise RuntimeError("File input not found")
            await file_input.set_input_files(str(cover))
            print(f"✅ Cover uploaded: {cover.name}")
            await asyncio.sleep(6)

            # 4. Fill title
            title_input = await page.query_selector(SEL_TITLE)
            if not title_input:
                raise RuntimeError("Title input not found — cover upload may have failed")
            box = await title_input.bounding_box()
            if not box or box["width"] < 10:
                raise RuntimeError("Title input not visible — editor did not load")
            await title_input.click()
            await title_input.fill(article["title"])
            print(f"✅ Title: {article['title']} ({len(article['title'])} chars)")

            # 5. Fill content
            editor = await page.query_selector(SEL_EDITOR)
            if not editor:
                raise RuntimeError("Content editor not found")
            await editor.click()
            await fill_prosemirror(page, editor, article["body_html"])
            print(f"✅ Content: {article['content_length']} chars")

            # 6. Add tags via content (embed hashtags in body text)
            # XHS auto-recognizes #话题 in content — more reliable than topic panel
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

            # 7. Screenshot
            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            ss_path = f"/tmp/xhs_publish_{ts}.png"
            await page.screenshot(path=ss_path)
            result["screenshot_path"] = ss_path
            print(f"✅ Screenshot: {ss_path}")

            # 8. Save draft
            if decision == "draft":
                await asyncio.sleep(1)
                saved = await save_draft(page)
                if saved:
                    await asyncio.sleep(3)
                    draft_info = await get_draft_count(page)
                    result["draft_saved"] = True
                    result["draft_count"] = draft_info
                    print(f"✅ Draft saved → {draft_info}")
                else:
                    raise RuntimeError("Draft button '暂存离开' not found")
            else:
                print("⚠️  Only 'draft' decision is supported. Skipping save.")

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            print(f"❌ Error: {e}")
            # Take error screenshot
            try:
                err_ss = f"/tmp/xhs_error_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                await page.screenshot(path=err_ss)
                result["error_screenshot"] = err_ss
            except Exception:
                pass

        finally:
            # Close XHS page
            try:
                await page.close()
            except Exception:
                pass

    return result


# ─── CLI Entry Point ────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Publish article to XHS drafts")
    parser.add_argument("--article", required=True, help="Path to markdown article")
    parser.add_argument("--cover", required=True, help="Path to cover image")
    parser.add_argument("--decision", default="draft", choices=["draft"], help="Publish decision")
    args = parser.parse_args()

    result = asyncio.run(publish_to_xhs(
        article_path=args.article,
        cover_path=args.cover,
        decision=args.decision,
    ))

    print("\n" + "=" * 50)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
