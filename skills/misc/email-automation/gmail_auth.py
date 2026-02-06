#!/usr/bin/env python3
"""Gmail OAuth 授权脚本"""

import os
import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Gmail API 权限范围
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',      # 读取
    'https://www.googleapis.com/auth/gmail.send',          # 发送
    'https://www.googleapis.com/auth/gmail.compose',       # 撰写
    'https://www.googleapis.com/auth/gmail.modify',        # 修改（标签等）
]

CONFIG_DIR = Path.home() / '.config' / 'gmail'
CREDENTIALS_FILE = CONFIG_DIR / 'credentials.json'
TOKEN_FILE = CONFIG_DIR / 'token.json'

def main():
    """执行 OAuth 授权流程"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    creds = None
    
    # 检查现有 token
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    
    # 如果没有有效凭据，执行授权
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("刷新 token...")
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print(f"错误: 请先将 credentials.json 放到 {CREDENTIALS_FILE}")
                print("\n获取步骤:")
                print("1. 访问 https://console.cloud.google.com/")
                print("2. 创建项目 → APIs & Services → Enable Gmail API")
                print("3. Credentials → Create OAuth 2.0 Client ID (Desktop)")
                print("4. 下载 JSON 并重命名为 credentials.json")
                return
            
            print("启动 OAuth 授权流程...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # 保存 token
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
        print(f"Token 已保存到 {TOKEN_FILE}")
    
    print("✅ Gmail 授权成功!")
    print(f"Token 位置: {TOKEN_FILE}")

if __name__ == '__main__':
    main()
