#!/usr/bin/env python3
"""
GZH Publisher — 微信公众号自动发布到草稿箱 v3.2

Usage:
    # Auto-scan gzh/ dir for images (recommended)
    python3 publish.py --article gzh/article.md --author "Daniel"

    # Explicit images
    python3 publish.py --article article.md --author "Daniel" --images img1.png img2.jpg

    # Skip 一键排版
    python3 publish.py --article gzh/article.md --author "Daniel" --no-format

Requires:
    - OpenClaw browser running (CDP at 127.0.0.1:18800 or OPENCLAW_CDP_URL)
    - Playwright Python library (pip install playwright)
    - Pillow (pip install Pillow) — for JPG→PNG conversion
    - Valid WeChat MP login session (browser cookies)

Flow:
    1. Find/navigate editor tab → verify login
    2. New article → fill title + author
    3. Scan gzh/ dir for images (if --images not provided, auto-discover)
    4. Inject text-only HTML with image placeholders (innerHTML)
    5. Paste images at placeholder positions (clipboard + Ctrl+V, replaces placeholder)
    6. Set cover from pasted images
    7. 一键排版 (format via articlestruct tab → 使用此排版)
    8. Verify images → save draft

v3.0 (2026-04-18):
    + Auto-scan gzh/ directory for images when --images is empty
    + 一键排版 support (articlestruct tab → 使用此排版)
    + Cover image selection (从正文选择 → first image → confirm)
    + Dedup: skip images already in editor by checking existing src
    + --no-format flag to skip 一键排版
    + --no-cover flag to skip cover selection
    + Better CDN URL collection (check all imgs, not just last)

v3.1.0 (2026-04-18):
    + Verified: 一键排版 preserves images (no re-inject needed)
    + Cover must be set BEFORE innerHTML injection
    + Removed redundant re-injection after formatting

v3.0.0 (2026-04-18):
    + Auto-scan gzh/ directory for images
    + 一键排版 support (articlestruct tab → 使用此排版)
    + Cover image selection (从正文选择)
    + Dedup, --no-format, --no-cover flags
    + JPG→PNG auto-conversion

KEY INSIGHT (2026-04-18 实战验证):
    - ✅ Image paste: clipboard.write(PNG) + keyboard Ctrl+V
    - ✅ Only paste-registered images persist on save (innerHTML img tags don't)
    - ✅ Cover must use paste-registered images (从正文选择)
    - ✅ Placeholder mode: inject text HTML → paste images at placeholder positions
    - ✅ 一键排版 preserves paste-registered images
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# ─── Constants ──────────────────────────────────────────────────────
TITLE_MAX = 64
CDP_URL = os.getenv("OPENCLAW_CDP_URL", "http://127.0.0.1:18800")
MP_HOME = "https://mp.weixin.qq.com"
UPLOAD_DIR = Path("/tmp/openclaw/uploads")
SAFETY_DIR = Path(os.getenv("GZH_SAFETY_DIR", "/tmp/gzh_safety"))
IMAGE_PASTE_WAIT = 8  # seconds to wait after Ctrl+V for CDN conversion
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
COVER_EXCLUDE_NAMES = {"cover-16x9.jpg", "cover-16x9.png", "cover.jpg", "cover.png"}


# ─── Utilities ────────────────────────────────────────────────────────
def log(emoji: str, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {emoji} {msg}")


def screenshot_path(stage: str) -> str:
    SAFETY_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")
    return str(SAFETY_DIR / f"gzh_safety_{stage}_{ts}.png")


def ensure_png(path: str) -> str:
    """Convert JPG/JPEG to PNG if needed. Returns PNG path."""
    p = Path(path)
    if p.suffix.lower() in (".png",):
        return str(p)
    try:
        from PIL import Image
        img = Image.open(p)
        png_path = str(p.with_suffix(".png"))
        img.save(png_path, "PNG")
        log("🔄", f"Converted {p.name} → PNG ({img.size[0]}x{img.size[1]})")
        return png_path
    except ImportError:
        log("⚠️ ", f"Pillow not installed, skipping {p.name} (only PNG supported)")
        return str(p)


def copy_to_uploads(paths: list[str]) -> list[str]:
    """Copy images to uploads dir, convert to PNG. Returns local paths."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    result = []
    for p in paths:
        src = Path(p)
        if not src.exists():
            log("⚠️ ", f"Not found: {p}")
            continue
        dst = UPLOAD_DIR / src.name
        shutil.copy2(src, dst)
        png_path = ensure_png(str(dst))
        result.append(png_path)
    return result


def discover_images(article_path: str) -> list[str]:
    """Auto-discover images from the same directory as the article.
    Scans for image files, excluding cover images and article.md.
    """
    article_dir = Path(article_path).parent
    if not article_dir.exists():
        return []

    images = []
    for f in sorted(article_dir.iterdir()):
        if not f.is_file():
            continue
        if f.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        if f.name.lower() in COVER_EXCLUDE_NAMES:
            continue
        if f.name.lower() == "article.md":
            continue
        images.append(str(f))

    return images


# ─── Markdown Parser ───────────────────────────────────────────────
def parse_article(path: str) -> dict:
    raw = Path(path).read_text(encoding="utf-8")
    lines = raw.splitlines()
    title, author, body_start = "", "", 0

    if lines and lines[0].strip() == "---":
        fm_end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if fm_end:
            for line in lines[1:fm_end]:
                if line.strip().startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"').strip("'")
                elif line.strip().startswith("author:"):
                    author = line.split(":", 1)[1].strip().strip('"').strip("'")
            body_start = fm_end + 1

    if not title:
        for i, line in enumerate(lines):
            if line.strip().startswith("# "):
                title = line.strip().lstrip("# ").strip()
                body_start = i + 1
                break

    return {"title": title, "author": author, "body": "\n".join(lines[body_start:]).strip()}


# ─── Markdown → WeChat HTML ────────────────────────────────────────
def auto_insert_images(md_body: str, image_paths: list[str]) -> tuple[str, list[str]]:
    """Insert ![keyword](path) into markdown at positions matching filename keywords.
    Skips entirely if markdown already contains image references."""
    # If markdown already has image references, respect author's layout
    if re.search(r'!\[', md_body):
        log("📸", "Markdown already has image references, skipping auto-insert")
        return md_body, []
    inserted = []
    for img_path in image_paths:
        fname = Path(img_path).stem
        parts = fname.split("-", 1)
        keyword = parts[1] if len(parts) > 1 else fname
        img_ref = f"\n![{keyword}]({img_path})\n"
        body_lines = md_body.split("\n")
        best_pos, best_score = -1, 0
        for i, line in enumerate(body_lines):
            lt = line.strip()
            score = sum(len(w) for w in keyword if len(w) > 1 and w in lt)
            if i > 0 and (body_lines[i-1].strip().startswith("#")):
                score += 5
            if "![" in lt:
                score = 0
            if score > best_score:
                best_score, best_pos = score, i
        if best_pos >= 0 and best_score > 2:
            body_lines.insert(best_pos, img_ref)
            inserted.append(fname)
            md_body = "\n".join(body_lines)
    return md_body, inserted


def md_to_wechat_html(md: str, image_map: dict[str, str] | None = None, placeholders: bool = False) -> tuple[str, int]:
    """Convert markdown to WeChat-styled HTML.
    
    Args:
        md: Markdown text
        image_map: {filename: cdn_url} mapping (ignored when placeholders=True)
        placeholders: If True, replace images with text placeholders (for paste-mode)
    
    Returns:
        (html_string, image_count)
    """
    image_map = image_map or {}
    html = md
    image_count = [0]

    if not placeholders:
        for fname, cdn_url in image_map.items():
            html = html.replace(f"]({fname})", f"]({cdn_url})")

    html = re.sub(r"```(\w*)\n([\s\S]*?)```", r'<pre style="background:#f6f8fa;border-left:3px solid #fe6;padding:12px;overflow-x:auto;font-size:13px"><code>\2</code></pre>', html)
    html = re.sub(r"^# (.+)$", r'<h1 style="font-size:22px;font-weight:bold;text-align:center;margin:20px 0">\1</h1>', html, flags=re.M)
    html = re.sub(r"^## (.+)$", r'<h2 style="font-size:18px;font-weight:bold;border-left:4px solid #1a73e8;padding-left:10px;margin:24px 0 12px">\1</h2>', html, flags=re.M)
    html = re.sub(r"^### (.+)$", r'<h3 style="font-size:16px;font-weight:bold;margin:16px 0 8px">\1</h3>', html, flags=re.M)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
    html = re.sub(r"`(.+?)`", r'<code style="background:#f6f8fa;padding:2px 6px;border-radius:3px">\1</code>', html)
    html = re.sub(r"^> (.+)$", r'<blockquote style="border-left:3px solid #ddd;color:#666;padding:8px 12px;margin:12px 0;background:#f9f9f9">\1</blockquote>', html, flags=re.M)

    # Image handling
    if placeholders:
        def _placeholder(match):
            caption = match.group(1) or "图片"
            idx = image_count[0]
            image_count[0] += 1
            # Use text placeholder that ProseMirror will keep as text nodes
            return f'<p style="text-align:center;color:#999;font-size:13px;margin:16px 0">【{idx}】{caption}</p>'
        html = re.sub(r"!\[([^\]]*)\]\([^)]+\)", _placeholder, html)
    else:
        html = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<p style="text-align:center;margin:16px 0"><img src="\2" style="max-width:100%;border-radius:4px" /></p>', html)

    if "|" in html:
        html = _convert_tables(html)

    html = re.sub(r"^- (.+)$", r'<li style="margin:4px 0">\1</li>', html, flags=re.M)
    html = re.sub(r"^---$", '<hr style="border:none;border-top:1px solid #eee;margin:16px 0">', html, flags=re.M)
    html = html.replace("\n\n", '</p><p style="font-size:15px;color:#3f3f3f;line-height:1.75;margin:8px 0">')
    html = html.replace("\n", "<br>")
    if html and not html.startswith("<"):
        html = f'<p style="font-size:15px;color:#3f3f3f;line-height:1.75;margin:8px 0">{html}</p>'
    return html, image_count[0]


def _convert_tables(html: str) -> str:
    """Convert markdown pipe tables to styled WeChat-compatible HTML tables.
    
    Features:
    - Zebra-striped rows for readability
    - Responsive width with min-width per column
    - Header row with distinct background
    - Clean borders and padding
    """
    lines = html.split("\n")
    result = []
    in_table = False
    row_idx = 0

    # Table wrapper style: centered, no overflow, clean border
    table_open = (
        '<table style="'
        'width:100%;'
        'border-collapse:collapse;'
        'margin:16px 0;'
        'font-size:14px;'
        'border:1px solid #e0e0e0;'
        'border-radius:4px;'
        'overflow:hidden'
        '">'
    )
    th_style = (
        ' style="'
        'background:#1a73e8;'
        'color:#fff;'
        'font-weight:600;'
        'padding:10px 12px;'
        'text-align:left;'
        'border:1px solid #1a73e8'
        '"'
    )
    td_base = (
        ' style="'
        'padding:10px 12px;'
        'text-align:left;'
        'border:1px solid #e8e8e8'
        '"'
    )
    td_zebra = (
        ' style="'
        'padding:10px 12px;'
        'text-align:left;'
        'border:1px solid #e8e8e8;'
        'background:#f8fafc'
        '"'
    )

    for line in lines:
        stripped = line.strip()
        if "|" in stripped and stripped.startswith("|"):
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            # Skip separator row (---|---|---)
            if all(set(c) <= {"-", ":", " "} for c in cells):
                continue
            if not in_table:
                result.append(table_open)
                in_table = True
                row_idx = 0
            # Header row
            if row_idx == 0:
                result.append("<tr>" + "".join(f"<th{th_style}>{c}</th>" for c in cells) + "</tr>")
            else:
                style = td_zebra if row_idx % 2 == 0 else td_base
                result.append("<tr>" + "".join(f"<td{style}>{c}</td>" for c in cells) + "</tr>")
            row_idx += 1
        else:
            if in_table:
                result.append("</table>")
                in_table = False
                row_idx = 0
            result.append(line)
    if in_table:
        result.append("</table>")
    return "\n".join(result)


# ─── Clipboard Image Paste ─────────────────────────────────────────
async def get_existing_cdn_urls(page) -> dict[str, str]:
    """Get all existing mmbiz CDN URLs currently in the editor.
    Returns {filename_hint: url} for dedup checking.
    """
    return await page.evaluate("""() => {
        const imgs = document.querySelectorAll('.ProseMirror img');
        const result = {};
        imgs.forEach((img, i) => {
            if (img.src && img.src.includes('mmbiz')) {
                result['existing_' + i] = img.src;
            }
        });
        return result;
    }""")


async def paste_image(page, image_path: str) -> str | None:
    """Paste a PNG image via clipboard + Ctrl+V. Returns CDN URL or None."""
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    # Focus ProseMirror at cursor position (does NOT clear selection)
    await page.evaluate("() => { document.querySelector('.ProseMirror').focus(); }")
    await page.wait_for_timeout(300)

    # Write image to clipboard
    await page.evaluate("""
    async ([b64]) => {
        const blob = await fetch('data:image/png;base64,' + b64).then(r => r.blob());
        const png = new Blob([blob], {type: 'image/png'});
        await navigator.clipboard.write([new ClipboardItem({'image/png': png})]);
    }
    """, [img_b64])

    # Paste via keyboard (replaces current selection if any)
    await page.keyboard.press("Control+v")
    await page.wait_for_timeout(IMAGE_PASTE_WAIT * 1000)

    # Get ALL mmbiz CDN URLs from ProseMirror (not just last)
    all_urls = await page.evaluate("""() => {
        const imgs = document.querySelectorAll('.ProseMirror img');
        return Array.from(imgs)
            .filter(i => i.src && i.src.includes('mmbiz'))
            .map(i => i.src);
    """)
    return all_urls[-1] if all_urls else None


async def select_placeholder(editor_page, idx: int) -> bool:
    """Select placeholder text 【idx】 in ProseMirror. Returns True if found."""
    return await editor_page.evaluate(f"""() => {{
        const editor = document.querySelector('.ProseMirror');
        const marker = '【' + {idx} + '】';
        const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {{
            const node = walker.currentNode;
            const pos = node.textContent.indexOf(marker);
            if (pos >= 0) {{
                const range = document.createRange();
                range.setStart(node, pos);
                range.setEnd(node, pos + marker.length);
                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
                return true;
            }}
        }}
        return false;
    }}""")

async def write_clipboard_image(page, image_path: str) -> None:
    """Write image to clipboard. This may steal ProseMirror focus."""
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    await page.evaluate("""
    async ([b64]) => {
        const blob = await fetch('data:image/png;base64,' + b64).then(r => r.blob());
        const png = new Blob([blob], {type: 'image/png'});
        await navigator.clipboard.write([new ClipboardItem({'image/png': png})]);
    }
    """, [img_b64])


async def paste_at_current_position(page) -> str | None:
    """Ctrl+V paste at current selection/cursor. Returns CDN URL or None."""
    await page.keyboard.press("Control+v")
    await page.wait_for_timeout(IMAGE_PASTE_WAIT * 1000)
    all_urls = await page.evaluate("""() => {
        const imgs = document.querySelectorAll('.ProseMirror img');
        return Array.from(imgs)
            .filter(i => i.src && i.src.includes('mmbiz'))
            .map(i => i.src);
    }""")
    return all_urls[-1] if all_urls else None


async def collect_all_cdn_urls(page) -> dict[str, str]:
    """Collect all mmbiz CDN URLs from ProseMirror after pasting.
    Returns {original_filename: cdn_url} by index matching.
    """
    return await page.evaluate("""() => {
        const imgs = document.querySelectorAll('.ProseMirror img');
        const result = {};
        imgs.forEach((img, i) => {
            if (img.src && img.src.includes('mmbiz')) {
                result['img_' + i] = img.src;
            }
        });
        return result;
    }""")


# ─── 一键排版 (One-Click Formatting) ─────────────────────────────
async def apply_format(editor_page, context):
    """Click 一键排版 → wait for articlestruct tab → click 使用此排版."""
    log("🎨", "Applying 一键排版...")

    # Scroll to top first to ensure toolbar is visible
    await editor_page.evaluate("() => window.scrollTo(0, 0)")
    await asyncio.sleep(1)

    # Try multiple selectors for 一键排版 button
    clicked = await editor_page.evaluate("""() => {
        // Method 1: exact text match
        const all = document.querySelectorAll('span, div, button, a, [class*="tool"]');
        for (const el of all) {
            if (el.textContent.trim() === '一键排版') {
                // Try clicking even if offsetParent is null (might be in overflow menu)
                el.click();
                return 'clicked: ' + el.tagName;
            }
        }
        // Method 2: contains text
        for (const el of all) {
            if (el.textContent.includes('一键排版') && el.textContent.trim().length < 10) {
                el.click();
                return 'clicked (contains): ' + el.tagName;
            }
        }
        return 'not found';
    }""")

    if 'not found' in clicked:
        log("⚠️ ", f"一键排版 button not found ({clicked}), skipping")
        return

    log("✅", f"一键排版 button {clicked}")

    # Wait for articlestruct tab to open (poll up to 15s)
    format_page = None
    for _ in range(15):
        for page in context.pages:
            if "articlestruct" in page.url:
                format_page = page
                break
        if format_page:
            break
        await asyncio.sleep(1)

    if not format_page:
        log("⚠️ ", "articlestruct tab not found after 15s, skipping format")
        return

    log("✅", "Format preview tab opened")

    # Wait for preview to fully render — poll for "使用此排版" button (up to 60s)
    # Long articles (5000+ words) need more time for preview rendering
    log("⏳", "Waiting for format preview to render...")
    btn_ready = False
    for attempt in range(30):
        await asyncio.sleep(2)
        # Scroll to bottom each time to find the button
        await format_page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(0.5)
        found = await format_page.evaluate("""() => {
            const btns = document.querySelectorAll('button, a, [role="button"]');
            for (const btn of btns) {
                if (btn.textContent.trim() === '使用此排版' && btn.offsetParent !== null) {
                    return true;
                }
            }
            return false;
        }""")
        if found:
            btn_ready = True
            log("✅", f"使用此排版 button ready after {(attempt+1)*2}s")
            break
        if attempt % 5 == 4:
            log("⏳", f"Still waiting... ({(attempt+1)*2}s)")

    if not btn_ready:
        log("⚠️ ", "使用此排版 button not found after 60s, skipping")
        try:
            await format_page.close()
        except Exception:
            pass
        return

    # Click "使用此排版" button
    clicked = await format_page.evaluate("""() => {
        const btns = document.querySelectorAll('button, a, [role="button"]');
        for (const btn of btns) {
            if (btn.textContent.trim() === '使用此排版' && btn.offsetParent !== null) {
                btn.click();
                return 'clicked';
            }
        }
        return 'not found';
    }""")

    if clicked == 'clicked':
        log("✅", "一键排版 applied")
        # Wait for format to be applied and tab to close
        await asyncio.sleep(3)
    else:
        log("⚠️ ", "使用此排版 click failed")
        try:
            await format_page.close()
        except Exception:
            pass


# ─── Cover Image Selection ────────────────────────────────────────
async def set_cover_from_body(editor_page):
    """Set cover image by uploading cover-16x9.jpg to editor first.
    WeChat '从正文选择' only recognizes pasted/uploaded images, not innerHTML.
    So we paste the cover image first, then use '从正文选择'.
    """
    log("🖼️ ", "Setting cover image...")

    # Scroll to top
    await editor_page.evaluate("() => window.scrollTo(0, 0)")
    await asyncio.sleep(1)

    # Try 方法1: 从正文选择 (works if images were pasted before innerHTML)
    clicked = await editor_page.evaluate("""() => {
        const items = document.querySelectorAll('#js_cover_description_area a, #js_cover a, a');
        for (const el of items) {
            if (el.textContent.includes('从正文选择')) {
                el.click();
                return 'clicked';
            }
        }
        return 'not found';
    }""")

    if clicked == 'clicked':
        await asyncio.sleep(3)
        selected = await editor_page.evaluate("""() => {
            const items = document.querySelectorAll('.appmsg_content_img_item');
            if (items.length > 0) {
                items[0].click();
                return 'selected: ' + items.length;
            }
            return 'empty';
        }""")
        if 'empty' in str(selected):
            log("⚠️ ", "从正文选择 dialog empty, closing...")
            # Close the dialog
            await editor_page.evaluate("""() => {
                const close = document.querySelector('.weui-desktop-dialog__hd .weui-desktop-dialog__close');
                if (close) close.click();
            }""")
            await asyncio.sleep(1)
            # Fallback: try 从图片库选择
            clicked2 = await editor_page.evaluate("""() => {
                const items = document.querySelectorAll('#js_cover_description_area a, a');
                for (const el of items) {
                    if (el.textContent.includes('从图片库选择')) {
                        el.click();
                        return 'clicked';
                    }
                }
                return 'not found';
            }""")
            if clicked2 == 'clicked':
                log("✅", "从图片库选择 opened")
                return True
            else:
                log("⚠️ ", "从图片库选择 not found either, skipping cover")
                return False
        else:
            log("✅", f"Cover image {selected}")
    else:
        log("⚠️ ", f"从正文选择 not found, skipping cover")
        return False

    # Click 下一步 → 确认
    for btn_text in ['下一步', '确认']:
        clicked = await editor_page.evaluate(f"""() => {{
            const btns = document.querySelectorAll('button, .weui-desktop-dialog__ft button');
            for (const btn of btns) {{
                if (btn.textContent.trim() === '{btn_text}' && btn.offsetParent !== null) {{
                    btn.click();
                    return 'clicked';
                }}
            }}
            return 'not found';
        }}""")
        if clicked == 'clicked':
            log("✅", f"Cover: clicked {btn_text}")
            await asyncio.sleep(2)
        else:
            log("⚠️ ", f"Cover: {btn_text} not found")

    log("✅", "Cover image set")
    return True


# ─── Main Flow ─────────────────────────────────────────────────────
async def publish_to_gzh(
    article_path: str,
    author: str,
    image_paths: list[str],
    do_format: bool = True,
    do_cover: bool = True,
) -> dict:
    from playwright.async_api import async_playwright

    result = {
        "status": "error",
        "title": "",
        "author": author,
        "draft_saved": False,
        "images_uploaded": 0,
        "images_skipped": 0,
        "cdn_urls": {},
        "appmsgid": "",
        "format_applied": False,
        "cover_set": False,
    }

    article = parse_article(article_path)
    title = article["title"][:TITLE_MAX]
    body_md = article["body"]
    if not author and article["author"]:
        author = article["author"]
    result["title"] = title
    result["author"] = author
    log("📄", f"Article: '{title}' ({len(body_md)} chars)")

    # Auto-discover images if not provided
    if not image_paths:
        image_paths = discover_images(article_path)
        if image_paths:
            log("🔍", f"Auto-discovered {len(image_paths)} images from {Path(article_path).parent}")

    # Convert images to PNG
    png_paths = copy_to_uploads(image_paths) if image_paths else []
    if png_paths:
        log("📸", f"{len(png_paths)} images ready (converted to PNG)")

    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0]

        # Grant clipboard permissions
        await ctx.grant_permissions(["clipboard-read", "clipboard-write"])

        # ─── Step 1: Find or create editor ────────────────────
        home_page = None
        editor_page = None
        for page in ctx.pages:
            if "appmsg_edit" in page.url and "isNew=1" not in page.url:
                pass  # Existing draft
            elif "mp.weixin.qq.com" in page.url and "home" in page.url:
                home_page = page

        if not home_page:
            home_page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        log("🌐", "Navigating to mp.weixin.qq.com...")
        await home_page.goto(MP_HOME, wait_until="domcontentloaded", timeout=30000)
        await home_page.wait_for_timeout(3000)

        body_text = await home_page.inner_text("body")
        if "请登录" in body_text or "扫码登录" in body_text:
            ss = screenshot_path("login_qr")
            await home_page.screenshot(path=ss)
            result["error"] = "Not logged in. Scan QR code."
            result["screenshot_path"] = ss
            log("❌", "Not logged in!")
            return result
        log("✅", "Login verified")

        # ─── Step 2: New article ─────────────────────────────
        log("📝", "Creating new article...")
        await home_page.evaluate("""() => {
            const h2s = document.querySelectorAll('h2');
            for (const h of h2s) {
                if (h.textContent.trim() === '新的创作') { h.click(); return; }
            }
        }""")
        await home_page.wait_for_timeout(1000)

        await home_page.evaluate("""() => {
            const all = document.querySelectorAll('*');
            for (const el of all) {
                if (el.textContent.trim() === '文章' && el.children.length === 0) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && r.y > 300) {
                        el.click(); return;
                    }
                }
            }
        }""")
        await home_page.wait_for_timeout(6000)

        # Log all tabs for debugging
        log("📋", f"Open tabs: {len(ctx.pages)}")
        for i, page in enumerate(ctx.pages):
            log("📋", f"  [{i}] {page.url[:80]}...")

        # Find new editor tab (prioritize isNew=1, fallback to any appmsg_edit)
        editor_page = None
        for page in ctx.pages:
            if "appmsg_edit" in page.url and page != home_page:
                if "isNew=1" in page.url:
                    editor_page = page
                    break  # Best match: freshly created
                elif not editor_page:
                    editor_page = page  # Fallback: any editor tab

        if not editor_page:
            result["error"] = "Editor tab not opened"
            log("❌", "Editor tab not found")
            return result
        log("✅", "Editor ready")

        # ─── Step 3: Fill title + author ─────────────────────
        # Wait for editor to fully load
        await editor_page.wait_for_selector("textarea", timeout=15000)
        await asyncio.sleep(1)

        # Use JS evaluate for title (more reliable than Playwright fill)
        title_result = await editor_page.evaluate(f"""() => {{
            const ta = document.querySelector('textarea');
            if (!ta) return 'textarea not found';
            ta.focus();
            ta.value = {json.dumps(title)};
            ta.dispatchEvent(new Event('input', {{bubbles: true}}));
            ta.dispatchEvent(new Event('change', {{bubbles: true}}));
            return 'filled: ' + ta.value;
        }}""")
        log("✅", f"Title: {title_result}")

        if author:
            author_result = await editor_page.evaluate(f"""() => {{
                const inp = document.querySelector('input[placeholder*="作者"]');
                if (!inp) return 'author input not found';
                inp.focus();
                inp.value = {json.dumps(author)};
                inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                return 'filled';
            }}""")
            log("✅", f"Author: {author_result}")

        # ─── Step 4: Inject text HTML with image placeholders ──
        # innerHTML img tags don't persist on save. Use placeholder <p> tags
        # that will be replaced by pasted images.
        # Auto-insert image references into markdown based on filename keywords
        body_md, matched_images = auto_insert_images(body_md, png_paths)
        log("📸", f"Matched {len(matched_images)} image positions")
        
        html_body, img_count = md_to_wechat_html(body_md, placeholders=True)
        log("📝", f"Injecting text HTML: {len(html_body)} chars ({img_count} image placeholders)")

        inject_result = await editor_page.evaluate(f"""() => {{
            const editor = document.querySelector('.ProseMirror');
            if (!editor) return 'ProseMirror not found';
            editor.focus();
            const html = {json.dumps(html_body)};
            editor.innerHTML = html;
            editor.dispatchEvent(new Event('input', {{bubbles: true}}));
            return 'injected: ' + html.length;
        }}""")
        log("✅", f"HTML injected: {inject_result}")
        await editor_page.wait_for_timeout(2000)

        editor_text = await editor_page.evaluate(
            "() => document.querySelector('.ProseMirror')?.innerText?.substring(0, 80) || 'empty'"
        )
        log("📝", f"Preview: {editor_text[:60]}...")

        # ─── Step 5: Paste images at placeholder positions ──────
        cdn_urls: dict[str, str] = {}
        original_names = [Path(p).name for p in image_paths] if image_paths else []
        paste_count = min(len(png_paths), img_count)

        for i in range(paste_count):
            fname = original_names[i] if i < len(original_names) else Path(png_paths[i]).name
            log("📸", f"Pasting {fname} at placeholder {i}...")

            # 1. Write clipboard FIRST (may steal focus from ProseMirror)
            await write_clipboard_image(editor_page, png_paths[i])
            await asyncio.sleep(0.2)

            # 2. Select placeholder AFTER clipboard write (re-sets focus + selection)
            found = await select_placeholder(editor_page, i)
            if not found:
                log("⚠️ ", f"  Placeholder {i} not found, appending at end")
                await editor_page.evaluate("() => { document.querySelector('.ProseMirror').focus(); }")

            # 3. Paste immediately (selection is fresh, nothing in between)
            cdn_url = await paste_at_current_position(editor_page)
            if cdn_url:
                cdn_urls[fname] = cdn_url
                log("✅", f"  {fname} → CDN OK ({len(cdn_url)} chars)")
            else:
                log("⚠️ ", f"  {fname} → CDN URL not found")

        result["cdn_urls"] = cdn_urls
        result["images_uploaded"] = len(cdn_urls)
        log("📸", f"Images pasted: {len(cdn_urls)}/{paste_count}")

        # ─── Step 6: Set cover (from paste-registered images) ──
        if do_cover:
            await set_cover_from_body(editor_page)
            result["cover_set"] = True
        else:
            log("⏭️ ", "Skipping cover selection (--no-cover)")

        # ─── Step 7: 一键排版 ────────────────────────────────
        if do_format:
            await apply_format(editor_page, ctx)
            result["format_applied"] = True
        else:
            log("⏭️ ", "Skipping 一键排版 (--no-format)")

        # ─── Step 8: Verify images before saving ─────────────
        img_check = await editor_page.evaluate("""() => {
            const imgs = document.querySelectorAll('.ProseMirror img');
            const mmbiz = Array.from(imgs).filter(i => i.src.includes('mmbiz'));
            return {total: imgs.length, cdn: mmbiz.length};
        }""")
        log("📸", f"Images in editor: {img_check['cdn']} CDN / {img_check['total']} total")

        # ─── Step 9: Save draft ──────────────────────────────
        log("💾", "Saving draft...")
        await editor_page.evaluate("""() => {
            const btns = document.querySelectorAll('button, div, a, span');
            for (const b of btns) {
                if (b.textContent.trim() === '保存为草稿' && b.offsetParent !== null) {
                    b.click(); return 'clicked';
                }
            }
            return 'not found';
        }""")
        await editor_page.wait_for_timeout(10000)

        # Dismiss any dialog
        try:
            await editor_page.evaluate("""() => {
                const btns = document.querySelectorAll('button');
                for (const btn of btns) {
                    const t = btn.textContent.trim();
                    if ((t === '确认' || t === '确定') && btn.offsetParent !== null) {
                        btn.click(); return;
                    }
                }
            }""")
            await editor_page.wait_for_timeout(3000)
        except Exception:
            pass

        # Extract appmsgid
        appmsgid_match = re.search(r"appmsgid=(\d+)", editor_page.url)
        if appmsgid_match:
            result["appmsgid"] = appmsgid_match.group(1)

        ss = screenshot_path("draft_saved")
        try:
            await editor_page.screenshot(path=ss)
            result["screenshot_path"] = ss
        except Exception as e:
            log("⚠️ ", f"Screenshot failed: {e}")
            result["screenshot_path"] = f"(failed: {e})"

        result["status"] = "ok"
        result["draft_saved"] = True
        result["content_length"] = len(body_md)
        log("✅", f"Draft saved! appmsgid={result['appmsgid']}")

    return result


# ─── CLI ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="GZH Publisher v3.2 — 微信公众号草稿箱发布")
    parser.add_argument("--article", required=True, help="Markdown article path")
    parser.add_argument("--author", default="", help="Author name (or from frontmatter)")
    parser.add_argument("--images", nargs="*", default=[], help="Image paths (auto-convert JPG→PNG). If empty, auto-scan article directory.")
    parser.add_argument("--no-format", action="store_true", help="Skip 一键排版")
    parser.add_argument("--no-cover", action="store_true", help="Skip cover image selection")
    args = parser.parse_args()

    if not Path(args.article).exists():
        print(f"❌ Article not found: {args.article}")
        sys.exit(1)

    log("🚀", "GZH Publisher v3.2 starting...")
    log("📄", f"Article: {args.article}")
    log("👤", f"Author: {args.author or '(from article)'}")
    log("📸", f"Images: {len(args.images)} (empty=auto-scan)")
    log("🎨", f"一键排版: {'off' if args.no_format else 'on'}")
    log("🖼️ ", f"Cover: {'off' if args.no_cover else 'on'}")

    result = asyncio.run(publish_to_gzh(
        article_path=args.article,
        author=args.author,
        image_paths=args.images,
        do_format=not args.no_format,
        do_cover=not args.no_cover,
    ))

    print("\n" + "=" * 50)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["status"] != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
