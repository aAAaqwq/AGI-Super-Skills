#!/usr/bin/env python3
"""
微信公众号 Playwright 自动发布脚本

使用方法:
1. 首次运行会打开登录页面，需要微信扫码
2. 登录成功后 cookies 会被保存
3. 后续运行自动加载 cookies，无需重复扫码

依赖: pip install playwright beautifulsoup4
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("请先安装 playwright: pip install playwright && playwright install chromium")
    sys.exit(1)


# 配置
WECHAT_MP_URL = "https://mp.weixin.qq.com/"
COOKIES_FILE = os.path.expanduser("~/.openclaw/skills/wechat-mp-smart-publish/cookies.json")
DRAFT_EDITOR_URL = "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77&lang=zh_CN&token={token}"

# 编辑器选择器
SELECTORS = {
    "title": "#js_title",           # 标题输入框
    "author": "#js_author",         # 作者输入框
    "digest": "#js_digest",         # 摘要输入框
    "content": "#js_editor",        # 正文编辑区 (iframe)
    "publish_btn": "#js_send",      # 发布按钮
    "preview_btn": "#js_preview",   # 预览按钮
    "save_btn": "#js_save",         # 保存草稿
    "cover_upload": ".js_cover_upload",  # 封面上传
    "cover_area": ".cover-area",    # 封面区域
}


def save_cookies(cookies, filepath=COOKIES_FILE):
    """保存 cookies 到文件"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"✅ Cookies 已保存到 {filepath}")


def load_cookies(filepath=COOKIES_FILE):
    """从文件加载 cookies"""
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        cookies = json.load(f)
    print(f"✅ 已加载 cookies ({len(cookies)} 个)")
    return cookies


def wait_for_login(page, timeout=120):
    """等待用户扫码登录"""
    print("📱 请用微信扫描二维码登录...")
    print(f"⏰ 等待登录中（最长 {timeout} 秒）...")

    try:
        # 等待页面跳转到管理后台
        page.wait_for_url("**/cgi-bin/home**", timeout=timeout * 1000)
        print("✅ 登录成功！")
        return True
    except PlaywrightTimeout:
        print("❌ 登录超时，请重试")
        return False


def get_token(page):
    """从页面 URL 提取 token"""
    url = page.url
    if "token=" in url:
        return url.split("token=")[1].split("&")[0]
    return None


def upload_cover(page, cover_path):
    """上传封面图"""
    if not cover_path or not os.path.exists(cover_path):
        print("⚠️  未提供封面图路径，跳过上传")
        return

    # 检查封面图尺寸
    try:
        from PIL import Image
        img = Image.open(cover_path)
        w, h = img.size
        print(f"📐 封面图尺寸: {w}×{h}px")
        if w < 900 or h < 500:
            print("⚠️  封面图尺寸不足，建议 900×500px")
    except ImportError:
        print("⚠️  未安装 Pillow，跳过封面图尺寸检查（pip install Pillow）")

    # 点击封面上传区域
    try:
        upload_input = page.query_selector('input[type="file"]')
        if upload_input:
            upload_input.set_input_files(cover_path)
            print("✅ 封面图已上传")
            time.sleep(2)
        else:
            print("⚠️  未找到上传按钮")
    except Exception as e:
        print(f"❌ 封面上传失败: {e}")


def fill_content(page, content_html):
    """填写正文内容（富文本）"""
    try:
        # 微信编辑器使用 iframe
        editor_frame = page.frame_locator("#ueditor_0")
        editor_frame.locator("body").fill("")  # 清空
        # 注入 HTML 内容
        editor_frame.locator("body").evaluate(f"el => el.innerHTML = {json.dumps(content_html)}")
        print("✅ 正文已填写")
    except Exception:
        # 备用方案：直接操作 body
        try:
            frame = page.frame_locator("iframe").first
            frame.locator("body").click()
            page.keyboard.type(content_html, delay=0)  # 不推荐，可能丢失格式
            print("✅ 正文已填写（备用方式）")
        except Exception as e:
            print(f"❌ 正文填写失败: {e}")


def publish_article(config):
    """
    发布公众号文章

    config = {
        "title": "文章标题",          # 必需，≤64字符
        "author": "作者名",           # 可选
        "digest": "文章摘要",         # 可选，≤120字符
        "content_html": "<p>正文HTML</p>",  # 必需
        "cover_path": "/path/to/cover.jpg",  # 可选，900×500px
        "is_draft": True,            # True=保存草稿, False=直接发布
        "publish_time": "2026-03-18 20:00:00",  # 可选，定时发布
        "screenshot_dir": "/path/to/screenshots",  # 可选，截图保存目录
    }
    """
    title = config.get("title", "")
    content_html = config.get("content_html", "")

    # 前置检查
    if not title:
        print("❌ 标题不能为空")
        return False
    if len(title) > 64:
        print(f"⚠️  标题超长（{len(title)}字符），将截断为64字符")
        title = title[:64]

    screenshot_dir = config.get("screenshot_dir")
    if screenshot_dir:
        os.makedirs(screenshot_dir, exist_ok=True)

    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(headless=False)  # 设为 True 可无头运行
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )

        # 加载 cookies
        cookies = load_cookies()
        page = context.new_page()

        if cookies:
            context.add_cookies(cookies)
            page.goto(WECHAT_MP_URL)
            time.sleep(3)

            # 检查是否仍然登录
            if "cgi-bin/home" not in page.url and "token=" not in page.url:
                print("⚠️  Cookies 已过期，需要重新登录")
                if not wait_for_login(page):
                    return False
                cookies = context.cookies()
                save_cookies(cookies)
        else:
            # 首次登录
            page.goto(WECHAT_MP_URL)
            if not wait_for_login(page):
                return False
            cookies = context.cookies()
            save_cookies(cookies)

        # 获取 token
        token = get_token(page)
        if not token:
            print("❌ 无法获取 token")
            return False
        print(f"🔑 Token: {token[:8]}...")

        # 截图：登录后首页
        if screenshot_dir:
            page.screenshot(path=f"{screenshot_dir}/01-home.png")
            print(f"📸 截图已保存: 01-home.png")

        # 进入草稿编辑器
        editor_url = f"https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77&lang=zh_CN&token={token}"
        page.goto(editor_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        if screenshot_dir:
            page.screenshot(path=f"{screenshot_dir}/02-editor.png")
            print(f"📸 截图已保存: 02-editor.png")

        # 填写标题
        try:
            page.fill(SELECTORS["title"], title)
            print(f"✅ 标题已填写: {title}")
        except Exception as e:
            print(f"❌ 标题填写失败: {e}")

        if screenshot_dir:
            page.screenshot(path=f"{screenshot_dir}/03-title-filled.png")
            print(f"📸 截图已保存: 03-title-filled.png")

        # 填写作者
        author = config.get("author", "")
        if author:
            try:
                page.fill(SELECTORS["author"], author)
                print(f"✅ 作者已填写: {author}")
            except Exception:
                print("⚠️  作者填写失败（可能当前账号类型不支持）")

        # 填写摘要
        digest = config.get("digest", "")
        if digest:
            if len(digest) > 120:
                print(f"⚠️  摘要超长（{len(digest)}字符），将截断为120字符")
                digest = digest[:120]
            try:
                page.fill(SELECTORS["digest"], digest)
                print(f"✅ 摘要已填写: {digest[:50]}...")
            except Exception:
                print("⚠️  摘要填写失败")

        # 填写正文
        if content_html:
            fill_content(page, content_html)

        if screenshot_dir:
            page.screenshot(path=f"{screenshot_dir}/04-content-filled.png")
            print(f"📸 截图已保存: 04-content-filled.png")

        # 上传封面
        cover_path = config.get("cover_path")
        if cover_path:
            upload_cover(page, cover_path)

        if screenshot_dir:
            page.screenshot(path=f"{screenshot_dir}/05-before-publish.png")
            print(f"📸 截图已保存: 05-before-publish.png")

        # 保存草稿或发布
        is_draft = config.get("is_draft", True)
        if is_draft:
            try:
                page.click(SELECTORS["save_btn"])
                time.sleep(2)
                print("✅ 文章已保存为草稿")
            except Exception as e:
                print(f"❌ 保存草稿失败: {e}")
                # 尝试发布按钮
                try:
                    page.click(SELECTORS["publish_btn"])
                    time.sleep(2)
                    print("✅ 文章已直接发布")
                except Exception as e2:
                    print(f"❌ 发布也失败: {e2}")
        else:
            try:
                page.click(SELECTORS["publish_btn"])
                time.sleep(2)
                print("✅ 文章已发布！")
            except Exception as e:
                print(f"❌ 发布失败: {e}")

        if screenshot_dir:
            page.screenshot(path=f"{screenshot_dir}/06-result.png")
            print(f"📸 截图已保存: 06-result.png")

        # 关闭浏览器
        time.sleep(3)
        browser.close()
        return True


def main():
    parser = argparse.ArgumentParser(description="微信公众号自动发布")
    parser.add_argument("--title", help="文章标题（≤64字符）")
    parser.add_argument("--content", help="正文 HTML 文件路径")
    parser.add_argument("--cover", help="封面图路径（900×500px）")
    parser.add_argument("--author", help="作者名")
    parser.add_argument("--digest", help="摘要（≤120字符）")
    parser.add_argument("--config", help="JSON 配置文件路径")
    parser.add_argument("--screenshots", help="截图保存目录")
    parser.add_argument("--publish", action="store_true", help="直接发布（默认保存草稿）")

    args = parser.parse_args()

    if args.config:
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)
    else:
        config = {}
        if args.title:
            config["title"] = args.title
        if args.content:
            with open(args.content, 'r', encoding='utf-8') as f:
                config["content_html"] = f.read()
        if args.cover:
            config["cover_path"] = args.cover
        if args.author:
            config["author"] = args.author
        if args.digest:
            config["digest"] = args.digest
        if args.screenshots:
            config["screenshot_dir"] = args.screenshots
        if args.publish:
            config["is_draft"] = False

    if not config.get("title"):
        print("❌ 请提供文章标题（--title 或 --config）")
        sys.exit(1)

    success = publish_article(config)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
