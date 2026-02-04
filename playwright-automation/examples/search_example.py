#!/usr/bin/env python3
"""
示例：搜索并提取数据
演示如何在天眼查搜索企业并提取信息
"""

from playwright.sync_api import sync_playwright
from urllib.parse import quote
import time
import random

def main():
    company = "迈瑞医疗"
    print(f"🔍 搜索企业: {company}\n")
    
    with sync_playwright() as p:
        print("1. 启动浏览器...")
        browser = p.chromium.launch(
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        print("2. 访问天眼查...")
        page.goto(f'https://www.tianyancha.com/search?key={quote(company)}')
        
        # 随机延迟，模拟人类行为
        delay = random.uniform(2, 5)
        print(f"3. 等待 {delay:.1f} 秒...")
        time.sleep(delay)
        
        print("4. 提取页面信息...")
        # 获取页面标题
        title = page.title()
        print(f"   页面标题: {title}")
        
        # 尝试获取搜索结果
        try:
            results = page.query_selector_all('.search_result_single')
            print(f"   找到 {len(results)} 个结果")
            
            if results:
                first_result = results[0]
                company_name = first_result.text_content()
                print(f"   第一个结果: {company_name}")
        except:
            print("   ⚠️ 无法提取结果（可能需要登录或遇到验证码）")
        
        print("5. 截图保存...")
        page.screenshot(path='/tmp/tianyancha_search.png', full_page=True)
        print(f"   截图: /tmp/tianyancha_search.png")
        
        browser.close()
    
    print("\n✅ 完成！")

if __name__ == "__main__":
    main()
