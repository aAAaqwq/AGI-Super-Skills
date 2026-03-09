#!/usr/bin/env python3
"""auto_publisher.py — 自动发布模块

支持平台：小红书（xiaohongshu）— MCP优先，Playwright备选
接口：publish(platform, title, content, images, tags) -> {success, url, error}

用法：
  python3 auto_publisher.py --platform xiaohongshu --date 2026-03-02 --topic-id 1
  python3 auto_publisher.py --platform xiaohongshu --title "测试" --content "内容" --dry-run
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from paths import DRAFTS_DIR, DATA_DIR
XHS_MCP_BIN = Path.home() / ".local/bin/xiaohongshu-mcp"
XHS_MCP_ENDPOINT = "http://localhost:18060/mcp"
XHS_COOKIES_DIR = Path.home() / ".playwright-data/xiaohongshu"
XHS_COOKIES_FALLBACK = [
    Path.home() / ".xiaohongshu/cookies.json",
    Path("/tmp/cookies.json"),
]
PUBLISH_LOG = DATA_DIR / "publish-log.json"

PLATFORMS = ["xiaohongshu"]  # Phase 1

# Clear proxy env to avoid socks:// issues with httpx
for _k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
    os.environ.pop(_k, None)


# ---------------------------------------------------------------------------
# MCP transport
# ---------------------------------------------------------------------------

def _mcp_available() -> bool:
    """Check if xiaohongshu-mcp binary exists and service is reachable."""
    if not XHS_MCP_BIN.exists():
        return False
    try:
        import httpx
        r = httpx.get(XHS_MCP_ENDPOINT.replace("/mcp", "/health"), timeout=3)
        return r.status_code < 500
    except Exception:

        return False


def _mcp_call(method: str, params: dict) -> dict:
    """Call xiaohongshu-mcp via stdio JSON-RPC."""
    import httpx

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": method, "arguments": params},
    }
    try:
        r = httpx.post(XHS_MCP_ENDPOINT, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            return {"success": False, "error": str(data["error"])}
        return {"success": True, "result": data.get("result")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def publish_xiaohongshu_mcp(title: str, content: str,
                            images: list = None, tags: list = None) -> dict:
    """Publish via xiaohongshu-mcp (MCP JSON-RPC)."""
    # Step 1: create note
    params = {"title": title, "content": content}
    if images:
        params["images"] = images
    if tags:
        params["tags"] = tags

    result = _mcp_call("create_note", params)
    if not result.get("success"):
        return {"success": False, "url": "", "error": f"MCP create_note failed: {result.get('error')}"}

    note_data = result.get("result", {})
    url = note_data.get("url", note_data.get("note_url", ""))
    return {"success": True, "url": url, "error": ""}


# ---------------------------------------------------------------------------
# Playwright transport (fallback)
# ---------------------------------------------------------------------------

def _find_cookies_storage() -> Optional[Path]:
    """Find a valid storage state / cookies file for Playwright."""
    XHS_COOKIES_DIR.mkdir(parents=True, exist_ok=True)
    state = XHS_COOKIES_DIR / "state.json"
    if state.exists():
        return state
    for p in XHS_COOKIES_FALLBACK:
        if p.exists():
            return p
    return None


def publish_xiaohongshu_playwright(title: str, content: str,
                                   images: list = None, tags: list = None) -> dict:
    """Publish via Playwright automation on creator.xiaohongshu.com."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"success": False, "url": "", "error": "playwright not installed (pip install playwright)"}

    storage = _find_cookies_storage()
    if not storage:
        return {"success": False, "url": "",
                "error": "无小红书 cookies/storage state，请先登录并保存到 ~/.playwright-data/xiaohongshu/state.json"}

    result = {"success": False, "url": "", "error": ""}
    browser = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(storage_state=str(storage))
            page = ctx.new_page()

            # Navigate to creator publish page
            page.goto("https://creator.xiaohongshu.com/publish/publish", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # Check login state
            if "login" in page.url.lower():
                result["error"] = "未登录：cookies 已过期，请重新登录"
                return result

            # --- Fill title ---
            title_sel = 'input[placeholder*="标题"], input[name="title"], #title'
            try:
                page.wait_for_selector(title_sel, timeout=5000)
                page.fill(title_sel, title)
            except Exception:
                # Some versions use contenteditable div
                page.locator('[contenteditable="true"]').first.fill(title)

            # --- Fill content ---
            # XHS editor is usually a contenteditable div or ProseMirror
            editor_sels = [
                '.ql-editor',
                '[contenteditable="true"]:not(input)',
                '.ProseMirror',
                '#content-editable',
            ]
            filled = False
            for sel in editor_sels:
                try:
                    el = page.wait_for_selector(sel, timeout=3000)
                    if el:
                        el.click()
                        page.keyboard.type(content, delay=10)
                        filled = True
                        break
                except Exception:
                    continue
            if not filled:
                result["error"] = "未找到内容编辑器选择器，需要更新 selector"
                return result

            # --- Upload images (if any) ---
            if images:
                file_input = page.locator('input[type="file"]').first
                for img_path in images:
                    if Path(img_path).exists():
                        file_input.set_input_files(img_path)
                        time.sleep(2)  # wait for upload

            # --- Add tags ---
            if tags:
                for tag in tags[:5]:  # XHS limits tags
                    tag_input = page.locator('input[placeholder*="标签"], input[placeholder*="话题"]')
                    if tag_input.count() > 0:
                        tag_input.first.fill(tag)
                        page.keyboard.press("Enter")
                        time.sleep(0.5)

            # --- Click publish ---
            pub_btn_sels = [
                'button:has-text("发布")',
                'button:has-text("Publish")',
                '.publish-btn',
                '[data-testid="publish-btn"]',
            ]
            published = False
            for sel in pub_btn_sels:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible():
                        btn.click()
                        published = True
                        break
                except Exception:
                    continue

            if not published:
                result["error"] = "未找到发布按钮"
                return result

            # Wait for redirect / success indication
            page.wait_for_timeout(3000)
            result["success"] = True
            result["url"] = page.url

            # Save updated storage state
            ctx.storage_state(path=str(storage))

            ctx.close()
            browser.close()
            browser = None

    except Exception as e:
        result["error"] = str(e)
    finally:
        # Force cleanup
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        subprocess.run(["pkill", "-f", "chromium.*--headless"], capture_output=True)

    return result


# ---------------------------------------------------------------------------
# Unified publish interface
# ---------------------------------------------------------------------------

def publish(platform: str, title: str, content: str,
            images: list = None, tags: list = None,
            dry_run: bool = False) -> dict:
    """
    发布内容到指定平台。

    Returns: {"success": bool, "url": str, "error": str, "method": str}
    """
    if platform not in PLATFORMS:
        return {"success": False, "url": "", "error": f"不支持的平台: {platform}", "method": "none"}

    if dry_run:
        print(f"[DRY-RUN] 平台: {platform}")
        print(f"  标题: {title}")
        print(f"  内容: {content[:200]}...")
        print(f"  图片: {images or '无'}")
        print(f"  标签: {tags or '无'}")
        return {"success": True, "url": "dry-run://ok", "error": "", "method": "dry-run"}

    if platform == "xiaohongshu":
        # Try MCP first
        if _mcp_available():
            print("📡 使用 MCP 方式发布...")
            r = publish_xiaohongshu_mcp(title, content, images, tags)
            r["method"] = "mcp"
            if r.get("success"):
                return r
            print(f"⚠️ MCP 失败: {r.get('error')}，回退到 Playwright...")
        else:
            print("⚠️ MCP 不可用，跳过...")

        # Fallback to Playwright
        print("🎭 使用 Playwright 方式...")
        storage = _find_cookies_storage()
        if not storage:
            print("⚠️ 登录态检查: 未找到小红书 cookies")
            print("  请先运行: python3 -m playwright install chromium")
            print("  然后手动登录并保存 storage state 到:")
            print(f"    {XHS_COOKIES_DIR}/state.json")
            return {"success": False, "url": "",
                    "error": "缺少小红书登录态，请先保存 cookies (详见上方提示)",
                    "method": "playwright"}
        print(f"✅ 登录态检查: 找到 cookies → {storage}")
        r = publish_xiaohongshu_playwright(title, content, images, tags)
        r["method"] = "playwright"
        return r

    return {"success": False, "url": "", "error": "unreachable", "method": "none"}


def log_publish(date_str: str, topic_id: str, platform: str, result: dict):
    """Append publish result to log file."""
    PUBLISH_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "date": date_str,
        "topic_id": topic_id,
        "platform": platform,
        **result,
    }
    logs = []
    if PUBLISH_LOG.exists():
        try:
            logs = json.loads(PUBLISH_LOG.read_text())
        except Exception:
            pass
    logs.append(entry)
    PUBLISH_LOG.write_text(json.dumps(logs, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_draft(date_str: str, topic_id: str, platform: str) -> tuple:
    """Read title + content from draft file."""
    path = DRAFTS_DIR / date_str / str(topic_id) / f"{platform}.md"
    if not path.exists():
        raise FileNotFoundError(f"草稿不存在: {path}")
    text = path.read_text()
    # Try to extract title from first line
    lines = text.strip().splitlines()
    title = ""
    content = text
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("【标题】"):
            title = stripped.replace("【标题】", "").strip()
        elif stripped.startswith("[TWEET]") or stripped.startswith("# "):
            title = stripped.lstrip("#[ ").rstrip("]").strip()
            break
    if not title and lines:
        title = lines[0][:60]
    return title, content


def main():
    ap = argparse.ArgumentParser(description="自动发布模块")
    ap.add_argument("--platform", choices=PLATFORMS, default="xiaohongshu")
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--topic-id", type=int, help="从 drafts 读取")
    ap.add_argument("--title", help="直接指定标题")
    ap.add_argument("--content", help="直接指定内容")
    ap.add_argument("--images", nargs="*", help="图片路径")
    ap.add_argument("--tags", nargs="*", help="标签")
    ap.add_argument("--dry-run", action="store_true", help="仅预览不发布")
    args = ap.parse_args()

    if args.title and args.content:
        title, content = args.title, args.content
    elif args.topic_id:
        title, content = parse_draft(args.date, str(args.topic_id), args.platform)
    else:
        print("❌ 需要指定 --topic-id 或 --title + --content", file=sys.stderr)
        return 1

    print(f"{'🏃' if not args.dry_run else '📝'} 发布: {args.platform} | {title[:40]}")
    result = publish(args.platform, title, content, args.images, args.tags, dry_run=args.dry_run)

    if result["success"]:
        print(f"✅ 发布成功 [{result.get('method', '?')}] → {result.get('url', 'N/A')}")
    else:
        print(f"❌ 发布失败 [{result.get('method', '?')}]: {result.get('error', '?')}")

    if not args.dry_run:
        log_publish(args.date, str(args.topic_id or 0), args.platform, result)

    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
