#!/usr/bin/env python3
"""
小红书自动发布脚本 (Playwright)
用法: python publish.py --title "标题" --content "正文" --tags "标签1,标签2" --image "封面图路径"

前置条件:
- 需要在浏览器中已登录 creator.xiaohongshu.com
- 或使用 --cookie 传入Cookie字符串
"""

import asyncio
import argparse
import json
from playwright.async_api import async_playwright

# 小红书创作者平台URL
PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"
IMAGE_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?from=menu&target=image"

# 平台限制
TITLE_MAX_LENGTH = 20  # 标题最大字数
CONTENT_MAX_LENGTH = 1000  # 短笔记正文上限
TAGS_MAX = 10  # 标签最大数量
TAGS_RECOMMENDED = 6  # 推荐标签数


async def publish_note(title: str, content: str, tags: list[str], 
                      image_path: str = None, cookie: str = None,
                      publish: bool = False, headless: bool = True):
    """
    发布小红书笔记到草稿箱或直接发布
    
    Args:
        title: 标题 (≤20字)
        content: 正文内容 (建议300-1000字)
        tags: 标签列表 (建议5-8个)
        image_path: 封面图路径 (可选)
        cookie: Cookie字符串 (可选)
        publish: True=发布, False=存草稿 (默认存草稿)
        headless: 是否无头模式 (默认True)
    """
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
    print(f"🖼️ 封面: {image_path or '无'}")
    print(f"🚀 模式: {'发布' if publish else '草稿'}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        
        if cookie:
            # 解析cookie字符串
            cookies = []
            for item in cookie.split(";"):
                item = item.strip()
                if "=" in item:
                    name, value = item.split("=", 1)
                    cookies.append({"name": name.strip(), "value": value.strip(), 
                                   "domain": ".xiaohongshu.com"})
            await context.add_cookies(cookies)
        
        page = await context.new_page()
        
        try:
            # Step 1: 打开发布页面
            print("📌 正在打开发布页面...")
            await page.goto(PUBLISH_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
            
            # Step 2: 选择上传图文模式
            print("📌 选择上传图文模式...")
            # 点击第二个导航项"上传图文"
            nav_items = page.locator("nav div, [class*='nav'] div")
            count = await nav_items.count()
            for i in range(count):
                text = await nav_items.nth(i).inner_text()
                if "图文" in text and "上传" in text:
                    await nav_items.nth(i).click()
                    break
            await asyncio.sleep(2)
            
            # Step 3: 上传封面图
            if image_path:
                print(f"📌 上传封面图: {image_path}")
                upload_input = page.locator("input[type='file']")
                await upload_input.set_input_files(image_path)
                await asyncio.sleep(3)
            
            # Step 4: 填写标题
            print("📌 填写标题...")
            title_input = page.locator("input[placeholder*='标题'], [class*='title'] input")
            if await title_input.count() > 0:
                await title_input.fill(title)
            else:
                # 尝试contenteditable方式
                title_div = page.locator("[contenteditable='true']").first
                await title_div.fill(title)
            await asyncio.sleep(1)
            
            # Step 5: 填写正文
            print("📌 填写正文...")
            # Quill编辑器
            editor = page.locator(".ql-editor, [contenteditable='true']")
            if await editor.count() > 1:
                # 正文是第二个contenteditable
                await editor.nth(1).fill(content)
            await asyncio.sleep(1)
            
            # Step 6: 添加标签
            print(f"📌 添加标签: {tags_str}")
            for tag in tags:
                tag_input = page.locator("[placeholder*='标签'], [class*='tag'] input")
                if await tag_input.count() > 0:
                    await tag_input.fill(tag)
                    await tag_input.press("Enter")
                    await asyncio.sleep(0.5)
            
            # Step 7: 保存草稿或发布
            if publish:
                print("🚀 正在发布...")
                publish_btn = page.locator("button:has-text('发布'), [class*='publish'] button")
                await publish_btn.click()
            else:
                print("💾 保存草稿...")
                draft_btn = page.locator("button:has-text('草稿'), [class*='draft'] button")
                await draft_btn.click()
            
            await asyncio.sleep(3)
            print("✅ 操作完成!")
            
        except Exception as e:
            print(f"❌ 发布失败: {e}")
            # 保存页面截图用于调试
            await page.screenshot(path="xhs_error.png")
            print("📸 已保存错误截图: xhs_error.png")
        
        finally:
            await browser.close()


def format_content_for_xhs(content: str) -> str:
    """
    将普通文本格式化为小红书风格
    
    规则:
    - 每段之间空一行
    - 每段开头可加emoji
    - 短句为主，避免超长段落
    - 结尾加标签区域
    """
    # 简单格式化：确保段落间有空行
    lines = content.strip().split("\n")
    formatted = []
    for line in lines:
        line = line.strip()
        if line:
            formatted.append(line)
        else:
            formatted.append("")
    
    return "\n\n".join(formatted)


def validate_title(title: str) -> dict:
    """验证标题是否符合小红书规范"""
    result = {"valid": True, "warnings": [], "suggestions": []}
    
    if len(title) > 20:
        result["valid"] = False
        result["warnings"].append(f"标题{len(title)}字，超过20字上限")
    elif len(title) < 5:
        result["warnings"].append("标题不足5字，可能影响点击率")
    
    if not any(c in title for c in "！?。，、"):
        result["suggestions"].append("建议加标点或emoji增加可读性")
    
    if not any(emoji in title for emoji in "🔥💡🌟✨🎉📌❤️👇👆"):
        result["suggestions"].append("加1-2个emoji提升点击率")
    
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="小红书自动发布")
    parser.add_argument("--title", "-t", required=True, help="笔记标题 (≤20字)")
    parser.add_argument("--content", "-c", required=True, help="正文内容")
    parser.add_argument("--tags", help="标签，逗号分隔", default="")
    parser.add_argument("--image", "-i", help="封面图路径")
    parser.add_argument("--cookie", help="Cookie字符串")
    parser.add_argument("--publish", action="store_true", help="直接发布(默认存草稿)")
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器")
    
    args = parser.parse_args()
    
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    
    asyncio.run(publish_note(
        title=args.title,
        content=args.content,
        tags=tags,
        image_path=args.image,
        cookie=args.cookie,
        publish=args.publish,
        headless=not args.no_headless
    ))
