#!/usr/bin/env python3
"""
抖音自动发布脚本 (Playwright)
用法: python douyin_publish.py --title "标题" --content "正文" --tags "标签1,标签2" --video "视频路径"

前置条件:
- 需要在浏览器中已登录 creator.douyin.com
- 或使用 --cookie 传入Cookie字符串
"""

import asyncio
import argparse
import json
from pathlib import Path
from playwright.async_api import async_playwright

# 抖音创作者平台URL
PUBLISH_URL = "https://creator.douyin.com/creator-micro/content/upload"

# 平台限制
TITLE_MAX_LENGTH = 55  # 标题最大字数
CONTENT_MAX_LENGTH = 500  # 视频描述上限
TAGS_MAX = 5  # 标签最大数量
TAGS_RECOMMENDED = 3  # 推荐标签数
VIDEO_MIN_DURATION = 15  # 视频最短秒数
VIDEO_MAX_DURATION = 600  # 视频最长秒数（10分钟）


async def publish_content(
    title: str,
    content: str,
    tags: list[str] = None,
    video_path: str = None,
    image_paths: list[str] = None,
    cookie: str = None,
    publish: bool = False,
    headless: bool = True,
    use_existing_browser: bool = True,
    content_type: str = "video"
):
    """
    发布抖音内容到草稿箱或直接发布
    
    Args:
        title: 标题/描述 (≤55字)
        content: 正文内容/视频描述 (建议50-200字)
        tags: 标签列表 (建议3-5个)
        video_path: 视频文件路径 (视频模式必填)
        image_paths: 图片路径列表 (图文模式必填)
        cookie: Cookie字符串 (可选)
        publish: True=发布, False=存草稿 (默认存草稿)
        headless: 是否无头模式 (默认True)
        use_existing_browser: 是否连接已存在的openclaw浏览器 (默认True)
        content_type: "video" 或 "image"
    """
    tags = tags or []
    
    # 验证输入
    if len(title) > TITLE_MAX_LENGTH:
        print(f"⚠️ 标题超长! {len(title)}字 > {TITLE_MAX_LENGTH}字上限")
        title = title[:TITLE_MAX_LENGTH]
    
    if len(content) > CONTENT_MAX_LENGTH:
        print(f"⚠️ 正文超长! {len(content)}字 > {CONTENT_MAX_LENGTH}字上限")
        content = content[:CONTENT_MAX_LENGTH]
    
    if len(tags) > TAGS_MAX:
        print(f"⚠️ 标签过多! {len(tags)}个 > {TAGS_MAX}个上限")
        tags = tags[:TAGS_MAX]
    
    tags_str = " ".join(f"#{t}" for t in tags)
    
    print(f"📝 标题: {title} ({len(title)}字)")
    print(f"📄 正文: {len(content)}字")
    print(f"🏷️ 标签: {tags_str}")
    print(f"🎬 类型: {content_type}")
    if content_type == "video":
        print(f"🎥 视频: {video_path or '无'}")
    else:
        print(f"🖼️ 图片: {image_paths or '无'}")
    print(f"🚀 模式: {'发布' if publish else '草稿'}")
    
    async with async_playwright() as p:
        # 优先连接已存在的openclaw浏览器
        browser = None
        if use_existing_browser:
            try:
                # 连接 openclaw 浏览器 (CDP端口18800)
                browser = await p.chromium.connect_over_cdp("http://127.0.0.1:18800")
                print("✅ 已连接 openclaw 浏览器 (CDP)")
            except Exception as e:
                print(f"⚠️ 无法连接openclaw浏览器: {e}")
                print("🔄 尝试启动新浏览器...")
        
        if not browser:
            browser = await p.chromium.launch(headless=headless)
        
        # 获取第一个 context
        contexts = browser.contexts
        if contexts:
            context = contexts[0]
        else:
            context = await browser.new_context()
        
        if cookie:
            # 解析cookie字符串
            cookies = []
            for item in cookie.split(";"):
                item = item.strip()
                if "=" in item:
                    name, value = item.split("=", 1)
                    cookies.append({
                        "name": name.strip(),
                        "value": value.strip(),
                        "domain": ".douyin.com"
                    })
            await context.add_cookies(cookies)
        
        # 获取或创建页面
        pages = context.pages
        if pages:
            page = pages[0]
            print(f"📄 使用已有页面: {page.url}")
        else:
            page = await context.new_page()
        
        try:
            # Step 1: 打开发布页面
            print("📌 正在打开发布页面...")
            await page.goto(PUBLISH_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
            
            # Step 2: 检查登录状态
            # 如果出现登录二维码或登录按钮，需要先登录
            login_selector = "canvas, [class*='qrcode'], button:has-text('登录')"
            if await page.locator(login_selector).count() > 0:
                print("⚠️ 检测到未登录状态，请扫码登录后重试")
                # 等待用户扫码
                await page.wait_for_timeout(30000)  # 等待30秒让用户扫码
                await page.reload()
                await asyncio.sleep(2)
            
            # Step 3: 选择内容类型
            if content_type == "video":
                print("📌 选择视频发布模式...")
                # 查找视频上传选项
                video_tab = page.locator("text=视频, [class*='video']").first
                if await video_tab.count() > 0:
                    await video_tab.click()
                await asyncio.sleep(1)
            else:
                print("📌 选择图文发布模式...")
                # 查找图文中上传选项
                image_tab = page.locator("text=图文, [class*='image']").first
                if await image_tab.count() > 0:
                    await image_tab.click()
                await asyncio.sleep(1)
            
            # Step 4: 上传内容
            if content_type == "video" and video_path:
                print(f"📌 上传视频: {video_path}")
                # 查找文件上传输入框
                file_input = page.locator("input[type='file']").first
                await file_input.set_input_files(video_path)
                print("⏳ 等待视频上传和转码...")
                # 等待上传进度完成
                await page.wait_for_timeout(15000)  # 等待15秒初步上传
            elif content_type == "image" and image_paths:
                print(f"📌 上传图片: {image_paths}")
                file_input = page.locator("input[type='file']").first
                await file_input.set_input_files(image_paths)
                await asyncio.sleep(3)
            
            # Step 5: 填写标题
            print("📌 填写标题...")
            # 尝试多种选择器定位标题输入框
            title_selectors = [
                "input[placeholder*='标题']",
                "textarea[placeholder*='标题']",
                "[class*='title'] input",
                "[class*='title'] textarea"
            ]
            
            title_filled = False
            for selector in title_selectors:
                title_input = page.locator(selector)
                if await title_input.count() > 0:
                    await title_input.fill(title)
                    title_filled = True
                    break
            
            if not title_filled:
                # 尝试使用 contenteditable
                editable = page.locator("[contenteditable='true']").first
                if await editable.count() > 0:
                    await editable.fill(title)
            
            await asyncio.sleep(1)
            
            # Step 6: 填写正文/描述
            print("📌 填写正文/描述...")
            # 尝试多种选择器定位描述输入框
            desc_selectors = [
                "textarea[placeholder*='描述']",
                "textarea[placeholder*='说点什么']",
                "[class*='desc'] textarea",
                "[class*='description']"
            ]
            
            desc_filled = False
            for selector in desc_selectors:
                desc_input = page.locator(selector)
                if await desc_input.count() > 0:
                    await desc_input.fill(content)
                    desc_filled = True
                    break
            
            if not desc_filled:
                # 尝试使用富文本编辑器
                editor = page.locator(".ql-editor, [contenteditable='true']")
                if await editor.count() > 1:
                    await editor.nth(1).fill(content)
                elif await editor.count() > 0:
                    await editor.fill(content)
            
            await asyncio.sleep(1)
            
            # Step 7: 添加话题标签
            if tags:
                print(f"📌 添加话题标签: {tags_str}")
                # 在描述中添加话题
                full_content = f"{content}\n\n{tags_str}"
                
                # 重新填入包含标签的内容
                for selector in desc_selectors:
                    desc_input = page.locator(selector)
                    if await desc_input.count() > 0:
                        await desc_input.fill(full_content)
                        break
            
            # Step 8: 设置封面（视频模式）
            if content_type == "video":
                print("📌 检查封面设置...")
                # 查找封面设置选项
                cover_selectors = [
                    "text=设置封面",
                    "[class*='cover']",
                    "button:has-text('封面')"
                ]
                for selector in cover_selectors:
                    cover_btn = page.locator(selector).first
                    if await cover_btn.count() > 0:
                        print("✅ 找到封面设置按钮")
                        break
            
            # Step 9: 截图预览
            print("📌 生成预览截图...")
            screenshot_path = "douyin_preview.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"📸 预览截图已保存: {screenshot_path}")
            
            # Step 10: 保存草稿或发布
            if publish:
                print("🚀 正在发布...")
                publish_selectors = [
                    "button:has-text('发布')",
                    "[class*='publish'] button",
                    "button:has-text('立即发布')"
                ]
                for selector in publish_selectors:
                    publish_btn = page.locator(selector).first
                    if await publish_btn.count() > 0:
                        await publish_btn.click()
                        break
            else:
                print("💾 保存到草稿箱...")
                draft_selectors = [
                    "button:has-text('草稿')",
                    "button:has-text('存草稿')",
                    "[class*='draft'] button"
                ]
                for selector in draft_selectors:
                    draft_btn = page.locator(selector).first
                    if await draft_btn.count() > 0:
                        await draft_btn.click()
                        break
            
            await asyncio.sleep(3)
            print("✅ 操作完成!")
            
            return {"status": "success", "screenshot": screenshot_path}
            
        except Exception as e:
            print(f"❌ 发布失败: {e}")
            # 保存页面截图用于调试
            error_screenshot = "douyin_error.png"
            await page.screenshot(path=error_screenshot)
            print(f"📸 已保存错误截图: {error_screenshot}")
            return {"status": "error", "message": str(e), "screenshot": error_screenshot}
        
        finally:
            await browser.close()


def format_content_for_douyin(content: str, tags: list[str] = None) -> str:
    """
    将普通文本格式化为抖音风格
    
    规则:
    - 第一行是核心钩子
    - 中间是补充说明
    - 最后是行动指引/互动引导
    - 底部添加话题标签
    """
    lines = content.strip().split("\n")
    formatted_lines = []
    
    for i, line in enumerate(lines):
        line = line.strip()
        if line:
            formatted_lines.append(line)
    
    # 添加话题标签
    if tags:
        formatted_lines.append("")
        formatted_lines.append(" ".join(f"#{t}" for t in tags))
    
    return "\n\n".join(formatted_lines)


def validate_title(title: str) -> dict:
    """验证标题是否符合抖音规范"""
    result = {"valid": True, "warnings": [], "suggestions": []}
    
    if len(title) > 55:
        result["valid"] = False
        result["warnings"].append(f"标题{len(title)}字，超过55字上限")
    elif len(title) < 5:
        result["warnings"].append("标题不足5字，可能影响曝光")
    
    if not any(emoji in title for emoji in "🔥👀❗⚠️💡✨🎉❓🤔"):
        result["suggestions"].append("加1-2个emoji提升点击率")
    
    return result


def validate_video(video_path: str) -> dict:
    """验证视频文件"""
    result = {"valid": True, "errors": [], "warnings": []}
    
    path = Path(video_path)
    if not path.exists():
        result["valid"] = False
        result["errors"].append(f"视频文件不存在: {video_path}")
        return result
    
    # 检查文件扩展名
    valid_extensions = ['.mp4', '.mov', '.avi', '.mkv']
    if path.suffix.lower() not in valid_extensions:
        result["warnings"].append(f"视频格式 {path.suffix} 可能不被支持，建议使用MP4")
    
    # 检查文件大小 (最大500MB)
    max_size = 500 * 1024 * 1024  # 500MB
    if path.stat().st_size > max_size:
        result["warnings"].append(f"视频超过500MB，可能上传困难")
    
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="抖音自动发布")
    parser.add_argument("--title", "-t", required=True, help="内容标题 (≤55字)")
    parser.add_argument("--content", "-c", required=True, help="正文内容/视频描述")
    parser.add_argument("--tags", help="话题标签，逗号分隔", default="")
    parser.add_argument("--video", "-v", help="视频文件路径 (视频模式)")
    parser.add_argument("--images", "-i", help="图片路径，逗号分隔 (图文模式)")
    parser.add_argument("--type", choices=["video", "image"], default="video", 
                       help="发布类型: video=视频, image=图文")
    parser.add_argument("--cookie", help="Cookie字符串")
    parser.add_argument("--publish", action="store_true", help="直接发布(默认存草稿)")
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器")
    parser.add_argument("--no-auto-login", action="store_true", help="不连接openclaw浏览器")
    
    args = parser.parse_args()
    
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    
    # 解析图片列表
    image_paths = None
    if args.images:
        image_paths = [img.strip() for img in args.images.split(",") if img.strip()]
    
    asyncio.run(publish_content(
        title=args.title,
        content=args.content,
        tags=tags,
        video_path=args.video,
        image_paths=image_paths,
        cookie=args.cookie,
        publish=args.publish,
        headless=not args.no_headless,
        use_existing_browser=not args.no_auto_login,
        content_type=args.type
    ))
