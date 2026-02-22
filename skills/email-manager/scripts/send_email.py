#!/usr/bin/env python3
"""
Send Email - 发送邮件（需用户确认）
读取已保存的草稿，经用户确认后发送
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from email_client import get_all_clients, EmailClient


def load_draft(draft_id: str) -> Optional[Dict]:
    """加载草稿"""
    drafts_path = Path(__file__).parent.parent / 'cache' / 'drafts.json'
    
    if not drafts_path.exists():
        return None
    
    with open(drafts_path, 'r', encoding='utf-8') as f:
        drafts = json.load(f)
    
    for draft in drafts.get('drafts', []):
        if draft.get('id') == draft_id:
            return draft
    
    return None


def send_draft(draft: Dict, account_email: str = None) -> tuple[bool, str]:
    """发送草稿"""
    clients = get_all_clients()
    
    if not clients:
        return False, "未配置任何邮箱账号"
    
    # 选择发送账号
    client = None
    if account_email:
        for c in clients:
            if c.email_address == account_email:
                client = c
                break
    
    if not client:
        client = clients[0]  # 默认使用第一个账号
    
    # 发送邮件
    success = client.send_email(
        to=draft['to'],
        subject=draft['subject'],
        body=draft['body'],
        is_html=False
    )
    
    if success:
        # 标记草稿为已发送
        mark_draft_sent(draft['id'])
        return True, f"邮件已发送到 {draft['to']}"
    else:
        return False, "发送失败"


def mark_draft_sent(draft_id: str):
    """标记草稿为已发送"""
    drafts_path = Path(__file__).parent.parent / 'cache' / 'drafts.json'
    
    if not drafts_path.exists():
        return
    
    with open(drafts_path, 'r', encoding='utf-8') as f:
        drafts = json.load(f)
    
    for draft in drafts.get('drafts', []):
        if draft.get('id') == draft_id:
            draft['sent'] = True
            draft['sent_at'] = datetime.now().isoformat()
            break
    
    with open(drafts_path, 'w', encoding='utf-8') as f:
        json.dump(drafts, f, ensure_ascii=False, indent=2)


def list_pending_drafts() -> list:
    """列出待发送的草稿"""
    drafts_path = Path(__file__).parent.parent / 'cache' / 'drafts.json'
    
    if not drafts_path.exists():
        return []
    
    with open(drafts_path, 'r', encoding='utf-8') as f:
        drafts = json.load(f)
    
    pending = [
        draft for draft in drafts.get('drafts', [])
        if not draft.get('sent', False)
    ]
    
    return pending


def main():
    """测试代码"""
    print("待发送的草稿:")
    drafts = list_pending_drafts()
    
    if not drafts:
        print("  无待发送草稿")
        return
    
    for draft in drafts:
        print(f"\nID: {draft['id']}")
        print(f"收件人: {draft['to']}")
        print(f"主题: {draft['subject']}")
        print(f"创建时间: {draft['created_at']}")


if __name__ == '__main__':
    main()
