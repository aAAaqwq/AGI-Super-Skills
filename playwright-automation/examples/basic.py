#!/usr/bin/env python3
"""
示例：基本浏览器操作
"""

from playwright.sync_api import sync_playwright

def main():
    print("🎭 Playwright 基本操作示例\n")
    
    with sync_playwright() as p:
        print("1. 启动浏览器...")
        browser = p.chromium.launch(headless=True)
        
        print("2. 创建新页面...")
        page = browser.new_page()
        
        print("3. 访问网页...")
        page.goto('https://example.com')
        
        print("4. 获取标题...")
        title = page.title()
        print(f"   标题: {title}")
        
        print("5. 获取 URL...")
        url = page.url
        print(f"   URL: {url}")
        
        print("6. 截图...")
        page.screenshot(path='/tmp/example.png')
        print(f"   截图已保存: /tmp/example.png")
        
        print("7. 关闭浏览器...")
        browser.close()
    
    print("\n✅ 完成！")

if __name__ == "__main__":
    main()
