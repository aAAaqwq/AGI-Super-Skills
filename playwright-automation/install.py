#!/usr/bin/env python3
"""
Playwright 安装脚本
"""

import subprocess
import sys

def run_command(cmd, description):
    """运行命令并显示进度"""
    print(f"\n🔧 {description}...")
    print(f"命令: {cmd}")
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"✅ {description} 成功")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} 失败")
        if e.stderr:
            print(f"错误: {e.stderr}")
        return False

def main():
    print("=" * 60)
    print("🎭 Playwright 安装脚本")
    print("=" * 60)
    
    steps = [
        ("pip install playwright", "安装 Playwright Python 包"),
        ("playwright install chromium", "安装 Chromium 浏览器"),
    ]
    
    success_count = 0
    for cmd, desc in steps:
        if run_command(cmd, desc):
            success_count += 1
        else:
            print(f"\n⚠️ {desc} 失败，请手动执行: {cmd}")
            print("继续下一步...")
    
    print("\n" + "=" * 60)
    print(f"✅ 安装完成！({success_count}/{len(steps)} 成功)")
    print("=" * 60)
    
    # 验证安装
    print("\n🔍 验证安装...")
    try:
        import playwright
        from playwright.sync_api import sync_playwright
        
        print(f"✅ Playwright 版本: {playwright.__version__}")
        
        # 测试启动
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto('https://example.com')
            title = page.title()
            browser.close()
        
        print(f"✅ 浏览器测试成功！")
        print(f"\n🎉 Playwright 已就绪，可以使用！")
        
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        print("请检查安装是否正确")

if __name__ == "__main__":
    main()
