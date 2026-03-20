#!/usr/bin/env python3
"""知识星球长文章发布 - Browser automation via Playwright.

Long articles (100K chars, rich Markdown) can only be published via web UI.
This script automates the browser publishing flow.
"""

import argparse
import os
import sys
import time


def publish_article(group_url, title, text, cover_image=None, headless=True):
    """Publish a long article to 知识星球 using Playwright.

    Args:
        group_url: Group page URL (e.g., https://wx.zsxq.com/group/12345)
        title: Article title
        text: Article content (supports Markdown)
        cover_image: Optional cover image path
        headless: Run browser in headless mode
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Installing playwright...")
        os.system(f"{sys.executable} -m pip install playwright -q")
        os.system("playwright install chromium")
        from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )

        # Inject cookie if available
        token = os.environ.get("ZSXQ_ACCESS_TOKEN", "")
        if token:
            config_path = os.path.expanduser("~/.config/zsxq/config.json")
            if os.path.exists(config_path):
                import json
                with open(config_path) as f:
                    cfg = json.load(f)
                    token = cfg.get("access_token", token)

            if token:
                domain = "zsxq.com"
                context.add_cookies([{
                    "name": "zsxq_access_token",
                    "value": token,
                    "domain": domain,
                    "path": "/",
                }])

        page = context.new_page()

        try:
            # 1. Navigate to group page
            print(f"Opening group: {group_url}")
            page.goto(group_url, wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # Check if logged in
            if "login" in page.url.lower():
                print("❌ Not logged in. Please set ZSXQ_ACCESS_TOKEN.", file=sys.stderr)
                browser.close()
                sys.exit(1)

            # 2. Click "长文章" button
            print("Looking for '长文章' button...")
            article_btn = page.locator("text=长文章").first
            article_btn.click()
            time.sleep(1)

            # 3. Switch to article editor (opens in new tab or iframe)
            # Long articles open in a new window/tab
            pages = context.pages
            editor_page = pages[-1] if len(pages) > 1 else page

            # 4. Fill title
            print(f"Setting title: {title}")
            title_input = editor_page.locator('input[type="text"], [contenteditable="true"]').first
            title_input.fill(title)
            time.sleep(0.5)

            # 5. Fill content
            print(f"Filling content ({len(text)} chars)...")
            editor = editor_page.locator('[contenteditable="true"]').last
            editor.fill(text)
            time.sleep(1)

            # 6. Upload cover image if provided
            if cover_image and os.path.exists(cover_image):
                print(f"Uploading cover: {cover_image}")
                upload_input = editor_page.locator('input[type="file"]').first
                upload_input.set_input_files(cover_image)
                time.sleep(3)

            # 7. Click publish
            print("Publishing...")
            publish_btn = editor_page.locator("text=发布").first
            publish_btn.click()
            time.sleep(3)

            # 8. Verify
            if "发布成功" in editor_page.text_content() or editor_page.url != group_url:
                print("✅ Article published successfully!")
            else:
                print("⚠️ Published (please verify manually)")

        except Exception as e:
            # Screenshot on error for debugging
            screenshot_path = "/tmp/zsxq_publish_error.png"
            page.screenshot(path=screenshot_path)
            print(f"❌ Error: {e}", file=sys.stderr)
            print(f"Screenshot saved: {screenshot_path}", file=sys.stderr)

        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description="知识星球长文章发布")
    parser.add_argument("--group-url", required=True, help="Group URL")
    parser.add_argument("--title", required=True, help="Article title")
    parser.add_argument("--text", help="Article content")
    parser.add_argument("--text-file", help="Read article from markdown file")
    parser.add_argument("--image", help="Cover image path")
    parser.add_argument("--no-headless", action="store_true", help="Show browser")
    args = parser.parse_args()

    text = args.text
    if args.text_file:
        with open(args.text_file, "r", encoding="utf-8") as f:
            text = f.read()

    if not text:
        parser.error("--text or --text-file is required")

    publish_article(
        group_url=args.group_url,
        title=args.title,
        text=text,
        cover_image=args.image,
        headless=not args.no_headless,
    )


if __name__ == "__main__":
    main()
