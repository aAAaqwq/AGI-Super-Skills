#!/usr/bin/env python3
"""
小红书自动发布脚本 (Playwright)
用法: python publish.py --title "标题" --content "正文" --tags "标签1,标签2" --image "封面图路径"

前置条件:
- 需要在浏览器中已登录 creator.xiaohongshu.com
- 或使用 --cookie 传入Cookie字符串

工作流模式:
1. --mode preview: 填写内容后截图确认（等待用户指令）
2. --mode draft: 填写内容后直接存草稿
3. --mode publish: 填写内容后直接发布（谨慎使用）
"""

import asyncio
import argparse
import json
import os
import re
from playwright.async_api import async_playwright

# 小红书创作者平台URL
PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"
IMAGE_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?from=menu&target=image"

# 平台限制
TITLE_MAX_LENGTH = 20  # 标题最大字数
CONTENT_MAX_LENGTH = 1000  # 短笔记正文上限
TAGS_MAX = 10  # 标签最大数量
TAGS_RECOMMENDED = 6  # 推荐标签数


async def take_screenshot(page, prefix: str = "preview") -> str:
    """截图并保存到文件"""
    screenshot_dir = "/home/aa/.openclaw/workspace-code/xhs_screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)
    filename = f"{screenshot_dir}/{prefix}_{int(asyncio.get_event_loop().time())}.png"
    await page.screenshot(path=filename, full_page=True)
    print(f"📸 截图已保存: {filename}")
    return filename


async def fill_title_js(page, title: str):
    """使用JavaScript精确填充标题（防止UI错位）"""
    await page.evaluate('''(title) => {
        const titleInput = document.querySelector('input[placeholder*="标题"]');
        if (titleInput) {
            titleInput.value = title;
            titleInput.dispatchEvent(new Event('input', {bubbles: true}));
            titleInput.dispatchEvent(new Event('change', {bubbles: true}));
        }
    }''', title)


async def fill_content_tiptap(page, content: str):
    """使用 Tiptap/ProseMirror API 填写正文内容"""
    # 将 markdown 文本转换为 HTML 段落
    paragraphs = content.strip().split('\n')
    html_parts = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        # 处理 **粗体**
        p = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', p)
        html_parts.append(f'<p>{p}</p>')
    html_content = ''.join(html_parts)
    
    await page.evaluate('''(html) => {
        const editor = document.querySelector('.tiptap.ProseMirror');
        if (!editor) return 'no editor found';
        editor.focus();
        editor.innerHTML = html;
        editor.dispatchEvent(new Event('input', {bubbles: true}));
        return 'done: ' + editor.textContent.length + ' chars';
    }''', html_content)


async def upload_cover_image(page, image_path: str):
    """上传封面图片 - 使用input[type='file']"""
    print(f"📌 上传封面图: {image_path}")
    try:
        # 尝试查找文件上传输入框
        file_input = page.locator("input[type='file']").first
        await file_input.set_input_files(image_path)
        await asyncio.sleep(3)  # 等待图片上传
        print("✅ 封面上传完成")
    except Exception as e:
        print(f"⚠️ 上传失败: {e}")
        raise


async def publish_note(title: str, content: str, tags: list[str], 
                      image_path: str = None, cookie: str = None,
                      mode: str = "preview", headless: bool = True,
                      use_existing_browser: bool = True):
    """
    发布小红书笔记到草稿箱或直接发布
    
    Args:
        title: 标题 (≤20字)
        content: 正文内容 (建议300-1000字)
        tags: 标签列表 (建议5-8个)
        image_path: 封面图路径 (可选)
        cookie: Cookie字符串 (可选)
        mode: 运行模式
            - "preview": 填写内容后截图等待确认（默认）
            - "draft": 填写内容后直接存草稿
            - "publish": 填写内容后直接发布（谨慎使用）
        headless: 是否无头模式 (默认True)
        use_existing_browser: 是否连接已存在的openclaw浏览器 (默认True)
    """
    
    # 根据模式决定是否自动发布
    auto_publish = (mode == "publish")
    auto_draft = (mode == "draft")
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
    print(f"🚀 模式: {'发布' if auto_publish else ('草稿' if auto_draft else '预览')}")
    
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
                    cookies.append({"name": name.strip(), "value": value.strip(), 
                                   "domain": ".xiaohongshu.com"})
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
            # 使用图文发布专用URL
            await page.goto(IMAGE_PUBLISH_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
            
            # Step 2: 选择上传图文模式
            print("📌 选择上传图文模式...")
            # 点击"上传图文"按钮
            try:
                # Try different selectors for the upload button
                upload_buttons = page.locator("text=上传图文, button:has-text('上传图文'), [class*='upload']:has-text('图文')")
                count = await upload_buttons.count()
                if count > 0:
                    await upload_buttons.first.click()
                    print("✅ 点击上传图文按钮成功")
                else:
                    # Fallback: click by evaluating JS
                    await page.evaluate('''() => {
                        const buttons = Array.from(document.querySelectorAll('button, div[role=\"button\"], [class*=\"button\"]'));
                        const btn = buttons.find(b => b.textContent.includes('上传图文'));
                        if (btn) btn.click();
                    }''')
            except Exception as e:
                print(f"⚠️ 点击上传图文失败: {e}")
            await asyncio.sleep(2)
            
            # Step 3: 上传封面图 (使用 input[type='file'])
            if image_path:
                await upload_cover_image(page, image_path)
            
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
            
            # Step 5: 填写正文 (使用 Tiptap/ProseMirror API)
            print("📌 填写正文 (Tiptap/ProseMirror)...")
            await fill_content_tiptap(page, content)
            
            # Step 6: 添加标签
            print(f"📌 添加标签: {tags_str}")
            for tag in tags:
                tag_input = page.locator("[placeholder*='标签'], [class*='tag'] input")
                if await tag_input.count() > 0:
                    await tag_input.fill(tag)
                    await tag_input.press("Enter")
                    await asyncio.sleep(0.5)
            
            # ===== 关键步骤：截图确认 =====
            # 在点击发布/保存草稿之前，必须先截图确认
            screenshot_path = await take_screenshot(page, "pre_publish")
            print(f"📸 预览截图已保存: {screenshot_path}")
            
            # 根据模式决定后续操作
            if mode == "preview":
                print("⏳ 已进入预览模式，等待用户确认...")
                print("💡 请在群中回复 '发布' 或 '存草稿' 继续")
                print("📝 当前内容已填写完毕，请确认后回复指令")
                # preview 模式在此停止，等待外部调用决定是否发布
                return {
                    "status": "preview_ready",
                    "screenshot": screenshot_path,
                    "title": title,
                    "content_length": len(content),
                    "tags": tags,
                    "message": "内容已填写完毕，请确认后回复'发布'或'存草稿'"
                }
            elif auto_draft:
                print("💾 直接保存草稿...")
                await save_draft(page)
            elif auto_publish:
                print("🚀 直接发布...")
                await do_publish(page)
            
            await asyncio.sleep(3)
            print("✅ 操作完成!")
            
        except Exception as e:
            print(f"❌ 发布失败: {e}")
            # 保存页面截图用于调试
            await page.screenshot(path="xhs_error.png")
            print("📸 已保存错误截图: xhs_error.png")
        
        finally:
            await browser.close()


async def save_draft(page):
    """保存到草稿箱"""
    try:
        draft_btn = page.locator("button:has-text('暂存离开'), button:has-text('草稿')")
        if await draft_btn.count() > 0:
            await draft_btn.click()
            await asyncio.sleep(2)
            print("✅ 已保存到草稿箱")
        else:
            print("⚠️ 未找到草稿按钮")
    except Exception as e:
        print(f"⚠️ 保存草稿失败: {e}")


async def do_publish(page):
    """执行发布"""
    try:
        publish_btn = page.locator("button:has-text('发布'), [class*='publish'] button")
        if await publish_btn.count() > 0:
            await publish_btn.click()
            await asyncio.sleep(3)
            print("✅ 发布成功!")
        else:
            print("⚠️ 未找到发布按钮")
    except Exception as e:
        print(f"⚠️ 发布失败: {e}")


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
    parser.add_argument("--mode", "-m", 
                       choices=["preview", "draft", "publish"],
                       default="preview",
                       help="运行模式: preview=截图确认后发布, draft=直接存草稿, publish=直接发布(默认preview)")
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器")
    
    args = parser.parse_args()
    
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    
    result = asyncio.run(publish_note(
        title=args.title,
        content=args.content,
        tags=tags,
        image_path=args.image,
        cookie=args.cookie,
        mode=args.mode,
        headless=not args.no_headless
    ))
    
    # 如果是 preview 模式，打印后续操作说明
    if result and result.get("status") == "preview_ready":
        print("\n" + "="*50)
        print("📋 预览模式等待确认...")
        print("请在群中发送以下指令:")
        print("  - '发布' 或 '确认发布' → 执行发布")
        print("  - '存草稿' → 保存到草稿箱")
        print("  - '修改' → 取消本次操作")
        print("="*50)
