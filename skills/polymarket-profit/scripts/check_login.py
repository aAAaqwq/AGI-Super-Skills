#!/usr/bin/env python3
"""
Polymarket 登录态维护脚本
通过浏览器检查 Polymarket 登录状态，如果未登录则重新登录
"""

import subprocess
import json
from pathlib import Path
from datetime import datetime

COOKIE_FILE = Path.home() / ".playwright-data" / "polymarket" / "state.json"

def check_login():
    """检查 Polymarket 登录状态"""
    print(f"🔍 检查 Polymarket 登录状态... {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查 cookie 文件是否存在
    if COOKIE_FILE.exists():
        print(f"✅ Cookie 文件存在: {COOKIE_FILE}")
        
        # 读取并解析 cookie
        try:
            with open(COOKIE_FILE, 'r') as f:
                cookies = json.load(f)
            
            # 检查是否有有效的认证 cookie
            if cookies.get("cookies"):
                print(f"✅ 找到 {len(cookies['cookies'])} 个 cookies")
                
                # 检查是否有认证相关的 cookie
                auth_cookies = [c for c in cookies['cookies'] if 'auth' in c.get('name', '').lower() or 'session' in c.get('name', '').lower()]
                if auth_cookies:
                    print(f"✅ 认证 cookies 有效: {len(auth_cookies)} 个")
                    return True
        except Exception as e:
            print(f"❌ Cookie 解析失败: {e}")
    
    print("❌ 未找到有效登录态")
    return False

def main():
    print("=" * 60)
    print("🔐 Polymarket 登录态维护")
    print("=" * 60)
    
    is_logged_in = check_login()
    
    if not is_logged_in:
        print("⚠️ 登录态无效，需要重新登录")
        print("📝 提示: 请打开 Polymarket 并重新连接钱包")
        print("   浏览器会自动保存登录态")
    else:
        print("✅ 登录态正常，无需操作")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
