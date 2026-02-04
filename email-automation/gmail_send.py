#!/usr/bin/env python3
"""Gmail 邮件发送（需确认）"""

import base64
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

TOKEN_FILE = Path.home() / '.config' / 'gmail' / 'token.json'

def get_service():
    """获取 Gmail API 服务"""
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(f"请先运行 gmail_auth.py 进行授权")
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    return build('gmail', 'v1', credentials=creds)

def create_message(to, subject, body, reply_to=None):
    """创建邮件消息"""
    message = MIMEText(body, 'plain', 'utf-8')
    message['to'] = to
    message['subject'] = subject
    
    if reply_to:
        message['In-Reply-To'] = reply_to
        message['References'] = reply_to
    
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw}

def create_draft(to, subject, body, reply_to=None):
    """创建草稿（安全操作）"""
    service = get_service()
    message = create_message(to, subject, body, reply_to)
    draft = service.users().drafts().create(
        userId='me', body={'message': message}
    ).execute()
    return draft['id']

def send_email(to, subject, body, reply_to=None):
    """发送邮件（需确认）"""
    service = get_service()
    message = create_message(to, subject, body, reply_to)
    result = service.users().messages().send(
        userId='me', body=message
    ).execute()
    return result['id']

def send_draft(draft_id):
    """发送已有草稿"""
    service = get_service()
    result = service.users().drafts().send(
        userId='me', body={'id': draft_id}
    ).execute()
    return result['id']

def format_confirmation(to, subject, body):
    """生成确认消息"""
    preview = body[:200] + '...' if len(body) > 200 else body
    return f"""⚠️ 需要确认发送邮件：

📧 收件人: {to}
📝 主题: {subject}

内容预览:
---
{preview}
---

回复 "确认" 发送，或 "取消" 放弃"""

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 4:
        print("用法: gmail_send.py <to> <subject> <body>")
        print("示例: gmail_send.py test@example.com 'Hello' 'This is a test'")
        sys.exit(1)
    
    to, subject, body = sys.argv[1], sys.argv[2], sys.argv[3]
    
    # 默认创建草稿而非直接发送
    print("创建草稿...")
    draft_id = create_draft(to, subject, body)
    print(f"✅ 草稿已创建 (ID: {draft_id})")
    print(format_confirmation(to, subject, body))
