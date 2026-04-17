#!/usr/bin/env python3
"""
GZH Publisher — 微信公众号自动发布到草稿箱 v1.0

Usage:
    # Basic: article + cover + author + images
    python3 publish.py \
      --article article.md \
      --cover cover.jpg \
      --author "Daniel" \
      --images img1.png img2.jpg

    # Minimal: article only (no cover, no images)
    python3 publish.py --article article.md --author "Daniel"

Requires:
    - OpenClaw browser running (CDP at 127.0.0.1:18800 or OPENCLAW_CDP_URL)
    - Playwright Python library (pip install playwright)
    - Valid WeChat MP login session (browser cookies)

Flow:
    1. Navigate to mp.weixin.qq.com → verify login
    2. Click "新的创作" → "文章" → new editor tab (appmsg_edit_v2)
    3. Fill title + author
    4. Upload images via CDP DOM.setFileInputFiles → collect CDN URLs
    5. Convert markdown → WeChat HTML → inject via CDP Runtime.evaluate
    6. Click 一键排版 → confirm in articlestruct tab → return
    7. Set cover from first body image (从正文选择)
    8. Save draft

v1.0 (2026-04-17):
    - Initial script based on gzh-publisher-skill SKILL.md v2.4
    - CDP-based image upload (DOM.setFileInputFiles)
    - ProseMirror innerHTML injection (not UEditor iframe)
    - 一键排版 with articlestruct tab handling
    - Cover from body image (3-step: select → 下一步 → 确认)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# ─── Constants ──────────────────────────────────────────────────────
TITLE_MAX = 64
CDP_URL = os.getenv("OPENCLAW_CDP_URL", "http://127.0.0.1:18800")
MP_HOME = "https://mp.weixin.qq.com"
SAFETY_DIR = Path(os.getenv("GZH_SAFETY_DIR", "/tmp/gzh_safety"))
IMAGE_MAX = 20  # reasonable limit for GZH


# ─── Utilities ────────────────────────────────────────────────────────
def log(emoji: str, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {emoji} {msg}")


def screenshot_path(stage: str) -> str:
    SAFETY_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")
    name = f"gzh_safety_{stage}_{ts}.png"
    return str(SAFETY_DIR / name)


# ─── Markdown Parser ───────────────────────────────────────────────
def parse_article(path: str) -> dict:
    """Parse GZH article from markdown.

    Supports frontmatter (--- title/author ---) or plain markdown.
    Body = everything after frontmatter or from first ## heading.
    """
    raw = Path(path).read_text(encoding="utf-8")
    lines = raw.splitlines()

    title = ""
    author = ""
    body_start = 0

    # Try frontmatter
    if lines and lines[0].strip() == "---":
        fm_end = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm_end = i
                break
        if fm_end:
            for line in lines[1:fm_end]:
                if line.strip().startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"').strip("'")
                elif line.strip().startswith("author:"):
                    author = line.split(":", 1)[1].strip().strip('"').strip("'")
            body_start = fm_end + 1

    # Fallback: first # heading as title
    if not title:
        for i, line in enumerate(lines):
            if line.strip().startswith("# "):
                title = line.strip().lstrip("# ").strip()
                body_start = i + 1
                break

    body = "\n".join(lines[body_start:]).strip()
    return {"title": title, "author": author, "body": body}


# ─── Markdown → WeChat HTML ────────────────────────────────────────
def md_to_wechat_html(md: str, image_map: dict[str, str] | None = None) -> str:
    """Convert markdown to WeChat-styled HTML.

    image_map: {filename.png: https://mmbiz.qpic.cn/...}
    """
    image_map = image_map or {}
    html = md

    # Replace image references with CDN URLs
    for fname, cdn_url in image_map.items():
        html = html.replace(f"]({fname})", f"]({cdn_url})")
        html = html.replace(f'src="{fname}"', f'src="{cdn_url}"')

    # Code blocks
    html = re.sub(
        r"```(\w*)\n([\s\S]*?)```",
        r'<pre style="background:#f6f8fa;border-left:3px solid #fe6;padding:12px;overflow-x:auto;font-size:13px"><code>\2</code></pre>',
        html,
    )
    # H1
    html = re.sub(
        r"^# (.+)$",
        r'<h1 style="font-size:22px;font-weight:bold;text-align:center;margin:20px 0">\1</h1>',
        html,
        flags=re.M,
    )
    # H2
    html = re.sub(
        r"^## (.+)$",
        r'<h2 style="font-size:18px;font-weight:bold;border-left:4px solid #1a73e8;padding-left:10px;margin:24px 0 12px">\1</h2>',
        html,
        flags=re.M,
    )
    # H3
    html = re.sub(
        r"^### (.+)$",
        r'<h3 style="font-size:16px;font-weight:bold;margin:16px 0 8px">\1</h3>',
        html,
        flags=re.M,
    )
    # Bold
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    # Italic
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
    # Inline code
    html = re.sub(
        r"`(.+?)`",
        r'<code style="background:#f6f8fa;padding:2px 6px;border-radius:3px">\1</code>',
        html,
    )
    # Blockquote
    html = re.sub(
        r"^> (.+)$",
        r'<blockquote style="border-left:3px solid #ddd;color:#666;padding:8px 12px;margin:12px 0;background:#f9f9f9">\1</blockquote>',
        html,
        flags=re.M,
    )
    # Images (standalone line)
    html = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        r'<p style="text-align:center;margin:16px 0"><img src="\2" style="max-width:100%;border-radius:4px" /></p>',
        html,
    )
    # Tables (basic)
    if "|" in html:
        html = _convert_tables(html)
    # Unordered list
    html = re.sub(r"^- (.+)$", r'<li style="margin:4px 0">\1</li>', html, flags=re.M)
    # Horizontal rule
    html = re.sub(
        r"^---$",
        '<hr style="border:none;border-top:1px solid #eee;margin:16px 0">',
        html,
        flags=re.M,
    )
    # Paragraphs (double newline)
    html = html.replace(
        "\n\n",
        '</p><p style="font-size:15px;color:#3f3f3f;line-height:1.75;margin:8px 0">',
    )
    # Single newline
    html = html.replace("\n", "<br>")
    # Wrap in paragraph
    if not html.startswith("<"):
        html = f'<p style="font-size:15px;color:#3f3f3f;line-height:1.75;margin:8px 0">{html}</p>'
    return html


def _convert_tables(html: str) -> str:
    """Basic markdown table → HTML table."""
    lines = html.split("\n")
    result = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        if "|" in stripped and stripped.startswith("|"):
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if all(set(c) <= {"-", ":", " "} for c in cells):
                continue  # separator row
            if not in_table:
                result.append(
                    '<table style="border-collapse:collapse;width:100%;font-size:14px;margin:10px 0">'
                )
                in_table = True
                tag = "th"
            else:
                tag = "td"
            bg = ' style="background:#f5f5f5;border:1px solid #ddd;padding:8px"' if tag == "th" else ' style="border:1px solid #ddd;padding:8px"'
            row = "<tr>" + "".join(f"<{tag}{bg}>{c}</{tag}>" for c in cells) + "</tr>"
            result.append(row)
        else:
            if in_table:
                result.append("</table>")
                in_table = False
            result.append(line)

    if in_table:
        result.append("</table>")
    return "\n".join(result)


# ─── CDP Helpers ─────────────────────────────────────────────────────
async def cdp_get_ws_url(target_id: str | None = None) -> str:
    """Get WebSocket URL for CDP connection, optionally filtering by target."""
    import httpx

    async with httpx.AsyncClient() as c:
        r = await c.get(f"{CDP_URL}/json/list")
        tabs = r.json()
    if target_id:
        for t in tabs:
            if target_id in t.get("id", "") or target_id in t.get("targetId", ""):
                return t["webSocketDebuggerUrl"]
    # Default: first page tab
    for t in tabs:
        if t.get("type") == "page":
            return t["webSocketDebuggerUrl"]
    raise RuntimeError("No browser tab found")


async def cdp_evaluate(ws, expression: str) -> any:
    """Execute JS via CDP and return result."""
    import websockets

    msg_id = int(time.time() * 1000) % 100000
    await ws.send(json.dumps({
        "id": msg_id,
        "method": "Runtime.evaluate",
        "params": {"expression": expression, "returnByValue": True},
    }))
    resp = json.loads(await ws.recv())
    result = resp.get("result", {}).get("result", {})
    return result.get("value")


async def cdp_upload_file(target_id: str, file_paths: list[str]) -> list[str]:
    """Upload files via CDP DOM.setFileInputFiles. Returns CDN URLs."""
    import httpx
    import websockets

    # Get ws url for the editor tab
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{CDP_URL}/json/list")
        tabs = r.json()

    ws_url = None
    for t in tabs:
        if target_id in t.get("id", "") or target_id in t.get("targetId", "") or "appmsg_edit" in t.get("url", ""):
            ws_url = t["webSocketDebuggerUrl"]
            break
    if not ws_url:
        # Fallback: first page with appmsg
        for t in tabs:
            if "appmsg" in t.get("url", ""):
                ws_url = t["webSocketDebuggerUrl"]
                break
    if not ws_url:
        raise RuntimeError(f"Editor tab not found for target {target_id}")

    async with websockets.connect(ws_url) as ws:
        # Find the file input element
        expr = """document.querySelector('input[type="file"][accept*="image"]')"""
        await ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": expr, "returnByValue": False},
        }))
        resp = json.loads(await ws.recv())
        obj_id = resp["result"]["result"]["objectId"]

        # Set files on the input
        await ws.send(json.dumps({
            "id": 2,
            "method": "DOM.setFileInputFiles",
            "params": {"objectId": obj_id, "files": file_paths},
        }))
        await ws.recv()

    log("⏳", f"Waiting for {len(file_paths)} images to upload...")
    await asyncio.sleep(8)

    # Now collect CDN URLs from ProseMirror
    async with websockets.connect(ws_url) as ws:
        urls = await cdp_evaluate(ws, """(() => {
            const imgs = document.querySelectorAll('.ProseMirror img');
            return Array.from(imgs).map(i => i.src).filter(s => s.includes('mmbiz') || s.includes('op_res'));
        })()""")
    return urls or []


async def cdp_inject_html(target_id: str, html: str) -> str:
    """Inject HTML into ProseMirror editor via CDP."""
    import httpx
    import websockets

    async with httpx.AsyncClient() as c:
        r = await c.get(f"{CDP_URL}/json/list")
        tabs = r.json()

    ws_url = None
    for t in tabs:
        if target_id in t.get("id", "") or target_id in t.get("targetId", "") or "appmsg_edit" in t.get("url", ""):
            ws_url = t["webSocketDebuggerUrl"]
            break
    if not ws_url:
        for t in tabs:
            if "appmsg" in t.get("url", ""):
                ws_url = t["webSocketDebuggerUrl"]
                break
    if not ws_url:
        raise RuntimeError("Editor tab not found")

    # Write HTML to temp file, then read it in the expression to avoid length limits
    tmp_file = "/tmp/gzh_article_body.html"
    Path(tmp_file).write_text(html, encoding="utf-8")

    async with websockets.connect(ws_url) as ws:
        result = await cdp_evaluate(
            ws,
            f"""(() => {{
                const editor = document.querySelector('.ProseMirror');
                if (!editor) return 'ProseMirror not found';
                editor.focus();
                // Read from temp file not possible in browser, use direct injection
                const html = {json.dumps(html)};
                editor.innerHTML = html;
                editor.dispatchEvent(new Event('input', {{bubbles: true}}));
                return 'injected: ' + html.length + ' chars';
            }})()""",
        )
    return result


# ─── Main Publish Flow ─────────────────────────────────────────────
async def publish_to_gzh(
    article_path: str,
    cover_path: str | None,
    author: str,
    image_paths: list[str],
    draft_only: bool = True,
) -> dict:
    """Full publish flow: login → create → fill → upload → inject → format → cover → save."""
    from playwright.async_api import async_playwright

    result = {
        "status": "error",
        "title": "",
        "author": author,
        "draft_saved": False,
        "published": False,
        "screenshot_path": "",
        "images_uploaded": 0,
        "appmsgid": "",
    }

    # Parse article
    article = parse_article(article_path)
    title = article["title"][:TITLE_MAX]
    body_md = article["body"]
    result["title"] = title

    log("📄", f"Article parsed: title='{title}' ({len(body_md)} chars)")

    # ─── Connect to browser ────────────────────────────────────
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # ─── Step 1: Navigate & verify login ───────────────────
        log("🌐", "Navigating to mp.weixin.qq.com...")
        await page.goto(MP_HOME, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        body_text = await page.evaluate("document.body.innerText.substring(0, 200)")
        if "请登录" in body_text or "扫码" in body_text:
            ss = screenshot_path("login_qr")
            await page.screenshot(path=ss)
            result["error"] = "Not logged in. Scan QR code to continue."
            result["screenshot_path"] = ss
            log("❌", "Not logged in! Screenshot saved.")
            return result

        log("✅", "Login verified")

        # ─── Step 2: New article ───────────────────────────────
        log("📝", "Creating new article...")
        # Click "新的创作" heading to expand menu
        await page.evaluate("""() => {
            const h2s = document.querySelectorAll('h2');
            for (const h of h2s) {
                if (h.textContent.trim() === '新的创作') { h.click(); return 'clicked'; }
            }
            return 'not found';
        }""")
        await page.wait_for_timeout(1000)

        # Click "文章" option (it's a div inside the creation area)
        clicked = await page.evaluate("""() => {
            const all = document.querySelectorAll('*');
            for (const el of all) {
                if (el.textContent.trim() === '文章' && el.children.length === 0) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && r.y > 300) {
                        el.click();
                        return 'clicked at ' + r.x + ',' + r.y;
                    }
                }
            }
            return 'not found';
        }""")
        log("📝", f"文章: {clicked}")
        await page.wait_for_timeout(5000)

        # Find the new editor tab
        editor_page = None
        for pg in ctx.pages:
            if "appmsg_edit" in pg.url:
                editor_page = pg
                break

        if not editor_page:
            result["error"] = "Editor tab not opened"
            log("❌", "Editor tab not found after clicking 文章")
            return result

        log("✅", f"Editor tab opened: {editor_page.url[:80]}")
        target_id = editor_page.url  # for CDP targeting

        # ─── Step 3: Fill title ────────────────────────────────
        await editor_page.evaluate(f"""() => {{
            const ta = document.querySelector('textarea');
            if (!ta) return 'no textarea';
            ta.focus();
            ta.value = {json.dumps(title)};
            ta.dispatchEvent(new Event('input', {{bubbles: true}}));
            ta.dispatchEvent(new Event('change', {{bubbles: true}}));
            return 'filled: ' + ta.value;
        }}""")
        log("✅", f"Title: {title} ({len(title)} chars)")

        # ─── Step 4: Fill author ───────────────────────────────
        if author:
            await editor_page.evaluate(f"""() => {{
                const inp = document.querySelector('input[placeholder*="作者"]');
                if (!inp) return 'no author input';
                inp.focus();
                inp.value = {json.dumps(author)};
                inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                return 'author: ' + inp.value;
            }}""")
            log("✅", f"Author: {author}")

        # ─── Step 5a: Upload images & collect CDN URLs ─────────
        cdn_urls: list[str] = []
        if image_paths:
            valid_paths = [p for p in image_paths if Path(p).exists()][:IMAGE_MAX]
            if valid_paths:
                log("🖼️ ", f"Uploading {len(valid_paths)} images...")
                # Copy to uploads dir (required by CDP)
                upload_dir = Path("/tmp/openclaw/uploads")
                upload_dir.mkdir(parents=True, exist_ok=True)
                upload_paths = []
                for img_path in valid_paths:
                    dest = upload_dir / Path(img_path).name
                    import shutil
                    shutil.copy2(img_path, dest)
                    upload_paths.append(str(dest))

                # Get targetId from pages
                editor_target_id = None
                # The page object has internal _impl_obj with target info
                # Use URL matching instead
                cdn_urls = await cdp_upload_file("", upload_paths)
                log("🖼️ ", f"Got {len(cdn_urls)} CDN URLs")
                result["images_uploaded"] = len(cdn_urls)

        # ─── Step 5b: Build HTML & inject ──────────────────────
        image_map = {}
        if image_paths and cdn_urls:
            for i, p in enumerate(image_paths[:len(cdn_urls)]):
                image_map[Path(p).name] = cdn_urls[i]

        html_body = md_to_wechat_html(body_md, image_map)
        log("📝", f"HTML generated: {len(html_body)} chars")

        # Inject via ProseMirror
        inject_result = await cdp_inject_html("", html_body)
        log("✅", f"HTML injected: {inject_result}")
        await editor_page.wait_for_timeout(2000)

        # Verify injection
        editor_text = await editor_page.evaluate(
            "document.querySelector('.ProseMirror')?.innerText?.substring(0, 100) || 'empty'"
        )
        log("📝", f"Editor text preview: {editor_text[:60]}...")

        # ─── Step 6: 一键排版 ──────────────────────────────────
        try:
            log("🎨", "Applying 一键排版...")
            await editor_page.evaluate("""() => {
                const divs = document.querySelectorAll('div');
                for (const d of divs) {
                    if (d.textContent.trim() === '一键排版' && d.offsetParent !== null) {
                        d.click();
                        return 'clicked';
                    }
                }
                return 'not found';
            }""")
            await editor_page.wait_for_timeout(3000)

            # Check for articlestruct tab
            for pg in ctx.pages:
                if "articlestruct" in pg.url:
                    log("🎨", "Found 排版 preview tab, clicking 使用此排版...")
                    await pg.evaluate("""() => {
                        const btns = document.querySelectorAll('button, a, div');
                        for (const b of btns) {
                            if (b.textContent.trim() === '使用此排版' && b.offsetParent !== null) {
                                b.click();
                                return 'clicked';
                            }
                        }
                        return 'not found';
                    }""")
                    await editor_page.wait_for_timeout(3000)
                    break

            log("✅", "一键排版 applied")
        except Exception as e:
            log("⚠️ ", f"一键排版 failed (non-fatal): {e}")

        # ─── Step 7: Cover from body image ─────────────────────
        if cover_path and Path(cover_path).exists():
            try:
                log("🖼️ ", "Setting cover from body image...")
                # Click "从正文选择"
                clicked_cover = await editor_page.evaluate("""() => {
                    const items = document.querySelectorAll('#js_cover_description_area a');
                    for (const el of items) {
                        if (el.textContent.includes('从正文选择') && el.offsetParent !== null) {
                            el.click();
                            return 'clicked';
                        }
                    }
                    return 'not found';
                }""")

                if clicked_cover == "clicked":
                    await editor_page.wait_for_timeout(2000)
                    # Select first image
                    await editor_page.evaluate("""() => {
                        const items = document.querySelectorAll('.appmsg_content_img_item');
                        if (items.length > 0) { items[0].click(); return 'selected'; }
                        return 'no images';
                    }""")
                    await editor_page.wait_for_timeout(1000)

                    # Click 下一步
                    await editor_page.evaluate("""() => {
                        const btns = document.querySelectorAll('.weui-desktop-dialog__ft button');
                        for (const btn of btns) {
                            if (btn.textContent.trim() === '下一步' && btn.offsetParent !== null) {
                                btn.click();
                                return 'clicked 下一步';
                            }
                        }
                        return 'not found';
                    }""")
                    await editor_page.wait_for_timeout(2000)

                    # Click 确认
                    await editor_page.evaluate("""() => {
                        const btns = document.querySelectorAll('.weui-desktop-dialog__ft button');
                        for (const btn of btns) {
                            if (btn.textContent.trim() === '确认' && btn.offsetParent !== null) {
                                btn.click();
                                return 'clicked 确认';
                            }
                        }
                        return 'not found';
                    }""")
                    await editor_page.wait_for_timeout(2000)
                    log("✅", "Cover set from body image")
                else:
                    log("⚠️ ", "从正文选择 not found, skipping cover")
            except Exception as e:
                log("⚠️ ", f"Cover setting failed (non-fatal): {e}")

        # ─── Step 8: Save draft ────────────────────────────────
        log("💾", "Saving draft...")
        await editor_page.evaluate("""() => {
            const btns = document.querySelectorAll('button, div, a, span');
            for (const b of btns) {
                if (b.textContent.trim() === '保存为草稿' && b.offsetParent !== null) {
                    b.click();
                    return 'clicked';
                }
            }
            return 'not found';
        }""")
        await editor_page.wait_for_timeout(5000)

        # Extract appmsgid from URL
        current_url = editor_page.url
        appmsgid_match = re.search(r"appmsgid=(\d+)", current_url)
        if appmsgid_match:
            result["appmsgid"] = appmsgid_match.group(1)

        # Final screenshot
        ss = screenshot_path("draft_saved")
        await editor_page.screenshot(path=ss)
        result["screenshot_path"] = ss

        result["status"] = "ok"
        result["draft_saved"] = True
        result["content_length"] = len(body_md)
        log("✅", "Draft saved!")
        if result["appmsgid"]:
            log("📋", f"appmsgid={result['appmsgid']}")

    except Exception as e:
        result["error"] = str(e)
        log("❌", f"Error: {e}")
    finally:
        await p.stop()

    return result


# ─── CLI ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="GZH Publisher — 微信公众号草稿箱发布")
    parser.add_argument("--article", required=True, help="Markdown article path")
    parser.add_argument("--cover", default=None, help="Cover image path (optional, will try 从正文选择)")
    parser.add_argument("--author", default="", help="Author name")
    parser.add_argument("--images", nargs="*", default=[], help="Additional image paths to upload")
    parser.add_argument("--decision", choices=["draft", "publish"], default="draft", help="draft only (default)")
    args = parser.parse_args()

    if not Path(args.article).exists():
        print(f"❌ Article not found: {args.article}")
        sys.exit(1)

    log("🚀", "GZH Publisher v1.0 starting...")
    log("📄", f"Article: {args.article}")
    log("🖼️ ", f"Cover: {args.cover or 'none'}")
    log("👤", f"Author: {args.author or 'empty'}")
    log("🖼️ ", f"Images: {len(args.images)}")

    result = asyncio.run(publish_to_gzh(
        article_path=args.article,
        cover_path=args.cover,
        author=args.author,
        image_paths=args.images,
        draft_only=(args.decision == "draft"),
    ))

    print("\n" + "=" * 50)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["status"] != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
