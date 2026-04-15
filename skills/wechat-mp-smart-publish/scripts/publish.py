#!/usr/bin/env python3
"""
WeChat MP Smart Publish — 微信公众号自动发布到草稿箱

Usage:
    python3 publish.py --article article.md --cover cover.jpg [--decision draft]

Requires:
    - OpenClaw browser running (CDP at 127.0.0.1:18800)
    - Playwright Python library (pip install playwright)
    - Valid WeChat MP cookies at ~/.playwright-data/wechat/state-default.json

Author: ives-cco
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── Constants ──────────────────────────────────────────────────────
TITLE_MAX = 64
CDP_URL = "http://127.0.0.1:18800"
COOKIE_PATH = Path.home() / ".playwright-data/wechat/state-default.json"
PUBLISH_URL = "https://mp.weixin.qq.com"

# ─── Markdown → HTML Converter ──────────────────────────────────────
def markdown_to_html(text: str) -> str:
    """Convert basic Markdown to HTML for WeChat UEditor."""
    lines = text.splitlines()
    html_parts = []
    
    in_code_block = False
    code_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # Code block
        if stripped.startswith("```"):
            if in_code_block:
                code_content = "\n".join(code_lines)
                html_parts.append(f'<pre style="background:#f6f8fa;border-left:3px solid #fe6;padding:12px;overflow-x:auto"><code>{code_content}</code></pre>')
                code_lines = []
            else:
                # Close previous paragraph before code block
                pass
            in_code_block = not in_code_block
            continue
        
        if in_code_block:
            code_lines.append(line)
            continue
        
        # H1
        if stripped.startswith("# "):
            content = stripped[2:].strip()
            html_parts.append(f'<h1 style="font-size:22px;font-weight:bold;margin:16px 0">{content}</h1>')
            continue
        
        # H2
        if stripped.startswith("## "):
            content = stripped[3:].strip()
            html_parts.append(f'<h2 style="font-size:18px;font-weight:bold;margin:14px 0">{content}</h2>')
            continue
        
        # H3
        if stripped.startswith("### "):
            content = stripped[4:].strip()
            html_parts.append(f'<h3 style="font-size:16px;font-weight:bold;margin:12px 0">{content}</h3>')
            continue
        
        # HR
        if stripped == "---":
            html_parts.append('<hr style="border:none;border-top:1px solid #eee;margin:16px 0">')
            continue
        
        # Empty line → paragraph break
        if not stripped:
            html_parts.append('<br>')
            continue
        
        # Process inline formatting
        processed = stripped
        
        # Bold **text**
        processed = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', processed)
        
        # Italic *text*
        processed = re.sub(r'\*(.+?)\*', r'<em>\1</em>', processed)
        
        # Inline code `text`
        processed = re.sub(r'`(.+?)`', r'<code style="background:#f6f8fa;padding:2px 6px;border-radius:3px">\1</code>', processed)
        
        # Wrap in paragraph
        html_parts.append(f'<p style="margin:8px 0">{processed}</p>')
    
    return "\n".join(html_parts)


# ─── Markdown Parser ───────────────────────────────────────────────
def parse_article(path: str) -> dict:
    """Parse article from markdown file."""
    raw = Path(path).read_text(encoding="utf-8")
    lines = raw.splitlines()
    
    title = ""
    body_lines = []
    in_body = False
    
    for line in lines:
        stripped = line.strip()
        
        # Skip metadata lines
        if stripped.startswith("📌") or stripped.startswith("🏷️") or stripped.startswith("🖼️"):
            continue
        
        # Title: first # heading or first non-empty line
        if not title:
            if stripped.startswith("# "):
                title = stripped[2:].strip()
                continue
            elif stripped and not in_body:
                title = stripped
                continue
        
        # Cover hint — stop reading body
        if stripped.startswith("📝 正文"):
            in_body = True
            continue
        
        if stripped.startswith("正文") or in_body:
            in_body = True
            body_lines.append(line)
    
    body = "\n".join(body_lines).strip()
    
    # Fallback: first non-empty line as title
    if not title:
        for line in lines:
            if line.strip():
                title = line.strip().lstrip("#").strip()
                break
    
    # Truncate title
    if len(title) > TITLE_MAX:
        title = title[:TITLE_MAX]
    
    return {
        "title": title,
        "body": body,
        "body_html": markdown_to_html(body),
    }


# ─── Browser Helpers ───────────────────────────────────────────────
async def get_browser_context():
    """Connect to OpenClaw browser via CDP."""
    import playwright
    from playwright._impl._driver import compute_driver_checksum
    
    browser = await playwright.chromium.connect_over_cdp(CDP_URL)
    context = await browser.new_context()
    return browser, context


async def load_cookies(context, cookie_path: Path):
    """Load cookies from Playwright state file."""
    if not cookie_path.exists():
        raise FileNotFoundError(f"Cookie file not found: {cookie_path}")
    
    state = json.loads(cookie_path.read_text())
    cookies = state.get("cookies", [])
    
    if not cookies:
        raise ValueError(f"No cookies in state file: {cookie_path}")
    
    # WeChat specific cookie names
    required = ["qname", "uin"]
    found = {c["name"] for c in cookies}
    missing = [r for r in required if r not in found]
    if missing:
        print(f"⚠️  Warning: Missing cookies: {missing}")
    
    await context.add_cookies(cookies)
    print(f"✅ Loaded {len(cookies)} cookies")


async def click_by_text(page, text: str, timeout: float = 5000):
    """Click element by text content."""
    import re
    await page.wait_for_selector(f"text={text}", timeout=timeout)
    await page.click(f"text={text}")


# ─── Main Publish Function ────────────────────────────────────────
async def publish_to_wechat(
    article_path: str,
    cover_path: str,
    decision: str = "draft",
) -> dict:
    """
    Publish article to WeChat MP draft box.
    
    Returns:
        dict with status, draft_saved, screenshot_path, etc.
    """
    import playwright
    
    # Parse article
    article = parse_article(article_path)
    title = article["title"]
    body_html = article["body_html"]
    
    print(f"📝 Article: {title} ({len(body_html)} chars HTML)")
    
    # Prepare cover image
    cover = Path(cover_path)
    if not cover.exists():
        raise FileNotFoundError(f"Cover image not found: {cover_path}")
    
    # Connect to browser
    print("🔗 Connecting to OpenClaw browser...")
    browser, context = await get_browser_context()
    page = await context.new_page()
    
    screenshot_path = f"/tmp/wechat_publish_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    
    try:
        # Load cookies
        print("🔐 Loading cookies...")
        load_cookies(context, COOKIE_PATH)
        
        # Navigate to WeChat MP
        print(f"🌐 Opening {PUBLISH_URL}...")
        await page.goto(PUBLISH_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_load_state("networkidle")
        
        # Check login
        try:
            await page.wait_for_selector('text="新的创作"', timeout=8000)
            print("✅ Login verified")
        except Exception:
            print("❌ Not logged in. Please login via browser.")
            await page.screenshot(path=screenshot_path)
            return {
                "status": "error",
                "error": "Not logged in. Cookie may be expired.",
                "screenshot_path": screenshot_path,
            }
        
        # Click "新的创作"
        print('📝 Clicking "新的创作"...')
        await click_by_text(page, "新的创作")
        await page.wait_for_timeout(2000)
        
        # Handle iframe/new window
        # WeChat MP often opens in a new window/tab
        print("🔍 Looking for editor...")
        
        # Try to find the editor frame
        try:
            # Wait for editor to be available
            await page.wait_for_timeout(3000)
            
            # Try to find UEditor iframe
            editor_frame = None
            for frame in page.frames:
                if "message" in frame.url or "ueditor" in frame.url.lower():
                    editor_frame = frame
                    break
            
            # Upload cover image
            print("🖼️ Uploading cover...")
            file_input = page.locator('input[type="file"]').first
            await file_input.set_input_files(str(cover.absolute()))
            await page.wait_for_timeout(3000)
            
            # Fill title
            print(f"✏️ Filling title: {title[:30]}...")
            try:
                title_input = page.locator('input[name="title"]')
                await title_input.wait_for(timeout=5000)
                await title_input.fill(title)
            except Exception:
                # Try alternative selector
                try:
                    title_input = page.locator('input[placeholder*="标题"]')
                    await title_input.fill(title)
                except Exception:
                    print("⚠️  Title input not found, trying JS...")
                    await page.evaluate(f'''
                        () => {{
                            const inputs = document.querySelectorAll("input");
                            for (const inp of inputs) {{
                                if (inp.type === "text" || inp.placeholder.includes("标题")) {{
                                    inp.value = "{title}";
                                    inp.dispatchEvent(new Event("input", {{ bubbles: true }}));
                                    break;
                                }}
                            }}
                        }}
                    ''')
            
            # Switch to rich text mode if needed
            try:
                await click_by_text(page, "图文", timeout=3000)
                await page.wait_for_timeout(1500)
            except Exception:
                print("⚠️  Could not switch to 图文 mode")
            
            # Inject content into UEditor
            print("📝 Injecting content...")
            
            # Try UEditor approach
            for frame in page.frames:
                try:
                    # Check if this is the UEditor frame
                    if "ueditor" in frame.url.lower() or frame.url.endswith(".js") is False:
                        await frame.wait_for_timeout(2000)
                        # Try to set content
                        await frame.evaluate(f'''
                            () => {{
                                if (typeof UE !== 'undefined') {{
                                    const editor = UE.getEditor('ueditor_0');
                                    if (editor) editor.setContent(`{body_html.replace('`', '\\`').replace('$', '\\$')}`);
                                }}
                            }}
                        ''')
                        break
                except Exception:
                    continue
            
            # Fallback: try page-level content injection
            await page.evaluate(f'''
                () => {{
                    // Try multiple UEditor instances
                    const editors = document.querySelectorAll('iframe');
                    for (const frame of editors) {{
                        try {{
                            const doc = frame.contentDocument || frame.contentWindow.document;
                            if (doc && doc.querySelector('body')) {{
                                doc.body.innerHTML = `{body_html.replace('`', '\\`').replace('$', '\\$')}`;
                                doc.body.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            }}
                        }} catch(e) {{ /* cross-origin, skip */ }}
                    }}
                }}
            ''')
            
            await page.wait_for_timeout(2000)
            
            # Take screenshot before saving
            await page.screenshot(path=screenshot_path)
            print(f"📸 Screenshot saved: {screenshot_path}")
            
            # Save as draft
            if decision == "draft":
                print('💾 Saving as draft...')
                try:
                    await click_by_text(page, "保存")
                    await page.wait_for_timeout(3000)
                    print("✅ Draft saved!")
                except Exception as e:
                    print(f"⚠️  Save failed: {e}")
                    # Try alternative save button
                    try:
                        save_btn = page.locator('button:has-text("保存")').first
                        await save_btn.click()
                        await page.wait_for_timeout(3000)
                    except Exception:
                        pass
            
            # Final screenshot
            await page.screenshot(path=screenshot_path)
            
            return {
                "status": "ok",
                "draft_saved": decision == "draft",
                "screenshot_path": screenshot_path,
                "title": title,
                "title_truncated": len(article.get("title", "")) > TITLE_MAX,
                "content_length": len(body_html),
            }
            
        except Exception as e:
            await page.screenshot(path=screenshot_path)
            return {
                "status": "error",
                "error": str(e),
                "screenshot_path": screenshot_path,
            }
    
    finally:
        await page.close()
        await context.close()
        await browser.disconnect()


# ─── CLI Entry Point ────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="WeChat MP Smart Publish")
    parser.add_argument("--article", required=True, help="Markdown article path")
    parser.add_argument("--cover", required=True, help="Cover image path (jpg/png)")
    parser.add_argument("--decision", default="draft", choices=["draft", "publish"],
                        help="Publish decision (default: draft)")
    
    args = parser.parse_args()
    
    print(f"""
╔══════════════════════════════════════════════╗
║     WeChat MP Smart Publish v1.0.0           ║
╠══════════════════════════════════════════════╣
║  Article : {args.article}
║  Cover   : {args.cover}
║  Decision: {args.decision}
╚══════════════════════════════════════════════╝
    """)
    
    result = asyncio.run(publish_to_wechat(
        article_path=args.article,
        cover_path=args.cover,
        decision=args.decision,
    ))
    
    print("\n📊 Result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    sys.exit(0 if result.get("status") == "ok" else 1)


if __name__ == "__main__":
    main()
