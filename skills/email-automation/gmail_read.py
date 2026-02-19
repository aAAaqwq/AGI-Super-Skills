#!/usr/bin/env python3
"""Gmail 邮件读取和搜索"""

import json
import base64
from pathlib import Path
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

TOKEN_FILE = Path.home() / '.config' / 'gmail' / 'token.json'

def get_service():
    """获取 Gmail API 服务"""
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(f"请先运行 gmail_auth.py 进行授权")
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    return build('gmail', 'v1', credentials=creds)

def list_messages(query='is:unread', max_results=10):
    """列出邮件"""
    service = get_service()
    results = service.users().messages().list(
        userId='me', maxResults=max_results, q=query
    ).execute()
    
    messages = []
    for msg in results.get('messages', []):
        detail = service.users().messages().get(
            userId='me', id=msg['id'], format='metadata',
            metadataHeaders=['From', 'Subject', 'Date']
        ).execute()
        
        headers = {h['name']: h['value'] for h in detail['payload']['headers']}
        messages.append({
            'id': msg['id'],
            'from': headers.get('From', ''),
            'subject': headers.get('Subject', ''),
            'date': headers.get('Date', ''),
            'snippet': detail.get('snippet', ''),
            'labels': detail.get('labelIds', []),
        })
    
    return messages

def get_message(msg_id):
    """获取邮件详情"""
    service = get_service()
    msg = service.users().messages().get(
        userId='me', id=msg_id, format='full'
    ).execute()
    
    headers = {h['name']: h['value'] for h in msg['payload']['headers']}
    
    # 提取正文
    body = ''
    if 'parts' in msg['payload']:
        for part in msg['payload']['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data', '')
                body = base64.urlsafe_b64decode(data).decode('utf-8')
                break
    elif 'body' in msg['payload'] and 'data' in msg['payload']['body']:
        body = base64.urlsafe_b64decode(msg['payload']['body']['data']).decode('utf-8')
    
    return {
        'id': msg_id,
        'from': headers.get('From', ''),
        'to': headers.get('To', ''),
        'subject': headers.get('Subject', ''),
        'date': headers.get('Date', ''),
        'body': body,
        'labels': msg.get('labelIds', []),
    }

def format_summary(messages):
    """格式化邮件摘要"""
    if not messages:
        return "📭 没有符合条件的邮件"
    
    lines = [f"📬 找到 {len(messages)} 封邮件:\n"]
    for i, msg in enumerate(messages, 1):
        lines.append(f"{i}. **{msg['subject'][:50]}**")
        lines.append(f"   来自: {msg['from'][:40]}")
        lines.append(f"   摘要: {msg['snippet'][:60]}...")
        lines.append("")
    
    return '\n'.join(lines)

if __name__ == '__main__':
    import sys
    
    query = sys.argv[1] if len(sys.argv) > 1 else 'is:unread'
    messages = list_messages(query)
    print(format_summary(messages))
