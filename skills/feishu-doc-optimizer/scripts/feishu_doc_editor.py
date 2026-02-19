#!/usr/bin/env python3
"""
飞书文档编辑器
通过 Playwright 浏览器自动化编辑飞书文档
"""

import sys
import asyncio
from playwright.async_api import async_playwright

async def clear_document(page):
    """清空文档内容"""
    print("🗑️ 清空文档内容...")
    
    # 点击内容区域
    try:
        await page.click('[data-block-id]', timeout=5000)
    except:
        pass
    
    await page.wait_for_timeout(300)
    
    # 循环删除直到内容清空
    for i in range(50):
        try:
            await page.click('[data-block-id]', timeout=2000)
        except:
            pass
        
        await page.wait_for_timeout(100)
        await page.keyboard.press("Control+a")
        await page.wait_for_timeout(100)
        await page.keyboard.press("Backspace")
        await page.wait_for_timeout(100)
        
        if i % 10 == 0:
            print(f"  已执行 {i+1} 次删除...")
    
    print("✅ 清空完成")

async def input_content(page, content_lines):
    """输入新内容"""
    print("📝 输入新内容...")
    
    # 点击内容区域
    try:
        await page.click('[data-block-id]', timeout=5000)
    except:
        pass
    
    await page.wait_for_timeout(300)
    
    for i, line in enumerate(content_lines):
        if line.strip():
            await page.keyboard.type(line, delay=3)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(50)
        
        if i % 20 == 0:
            print(f"  已输入 {i+1}/{len(content_lines)} 行...")
    
    print("✅ 输入完成")

async def edit_document(doc_token, content_file):
    """编辑文档"""
    # 读取新内容
    with open(content_file, 'r', encoding='utf-8') as f:
        content = f.read()
    content_lines = content.split('\n')
    
    async with async_playwright() as p:
        # 连接到已有的浏览器
        try:
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:18800")
        except Exception as e:
            print(f"❌ 无法连接浏览器: {e}")
            print("请确保 OpenClaw 浏览器已启动")
            return False
        
        # 查找文档页面
        page = None
        for ctx in browser.contexts:
            for pg in ctx.pages:
                if doc_token in pg.url:
                    page = pg
                    break
        
        if not page:
            # 打开新页面
            print(f"📄 打开文档...")
            ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await ctx.new_page()
            await page.goto(f"https://opencaio.feishu.cn/docx/{doc_token}")
            await page.wait_for_timeout(3000)
        
        print(f"✅ 找到页面: {page.url}")
        
        # 检查是否需要登录
        content = await page.content()
        if '扫码登录' in content or '登录' in content:
            print("❌ 需要登录飞书，请先在浏览器中登录")
            return False
        
        # 进入编辑模式
        try:
            await page.click('text="编辑"', timeout=3000)
            await page.wait_for_timeout(500)
            # 点击编辑选项
            await page.click('text="可编辑文档"', timeout=3000)
            await page.wait_for_timeout(500)
        except:
            print("⚠️ 可能已在编辑模式")
        
        # 清空文档
        await clear_document(page)
        
        # 输入新内容
        await input_content(page, content_lines)
        
        # 等待保存
        await page.wait_for_timeout(2000)
        print("✅ 文档编辑完成！")
        
        return True

def main():
    if len(sys.argv) < 3:
        print("用法: python feishu_doc_editor.py <doc_token> <content_file>")
        print("示例: python feishu_doc_editor.py JM3WdqG2bolLsNxlVnJcTdMjnce optimized.md")
        sys.exit(1)
    
    doc_token = sys.argv[1]
    content_file = sys.argv[2]
    
    success = asyncio.run(edit_document(doc_token, content_file))
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
