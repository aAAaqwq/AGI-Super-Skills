#!/usr/bin/env python3
"""
Reply Draft - 生成回复草稿
基于收到的邮件和用户需求，生成礼貌的回复草稿
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from email_client import get_all_clients, EmailClient


def load_email_cache() -> Optional[Dict]:
    """加载邮件缓存"""
    cache_path = Path(__file__).parent.parent / 'cache' / 'emails.json'
    
    if not cache_path.exists():
        return None
    
    with open(cache_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_email_by_index(account_name: str, index: int) -> Optional[Dict]:
    """根据索引获取邮件"""
    cache = load_email_cache()
    
    if not cache:
        return None
    
    emails = cache.get('emails', {}).get(account_name, [])
    
    if 0 < index <= len(emails):
        return emails[index - 1]
    
    return None


def generate_reply_draft(
    original_email: Dict,
    user_request: str,
    sender_name: str = "Daniel"
) -> Dict:
    """生成回复草稿（简化版，可后续接入 LLM）"""
    
    # 提取收件人信息
    to_email = original_email.get('from', '')
    to_name = to_email.split('<')[0].strip() if '<' in to_email else to_email
    
    # 生成主题
    original_subject = original_email.get('subject', '')
    reply_subject = f"Re: {original_subject}" if not original_subject.startswith('Re:') else original_subject
    
    # 基于用户请求生成回复内容
    # 这里是简化版，实际应该调用 LLM
    body = f"""{to_name}，你好！

{user_request}

如有其他问题，随时联系。

祝好，
{sender_name}
"""
    
    return {
        'to': to_email,
        'subject': reply_subject,
        'body': body.strip(),
        'original_email': original_email,
        'created_at': datetime.now().isoformat()
    }


def format_draft_for_review(draft: Dict) -> str:
    """格式化草稿供用户审核"""
    output = "📝 **回复草稿**\n\n"
    output += f"收件人: {draft['to']}\n"
    output += f"主题: {draft['subject']}\n\n"
    output += "内容:\n"
    output += "---\n"
    output += draft['body']
    output += "\n---\n\n"
    output += "确认发送吗？（回复\"确认\"发送，\"修改\"调整，\"取消\"放弃）"
    
    return output


def save_draft(draft: Dict) -> str:
    """保存草稿到文件"""
    drafts_path = Path(__file__).parent.parent / 'cache' / 'drafts.json'
    drafts_path.parent.mkdir(exist_ok=True)
    
    # 加载现有草稿
    if drafts_path.exists():
        with open(drafts_path, 'r', encoding='utf-8') as f:
            drafts = json.load(f)
    else:
        drafts = {'drafts': []}
    
    # 添加新草稿
    draft_id = f"draft_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    draft['id'] = draft_id
    drafts['drafts'].append(draft)
    
    # 保存
    with open(drafts_path, 'w', encoding='utf-8') as f:
        json.dump(drafts, f, ensure_ascii=False, indent=2)
    
    return draft_id


def main():
    """测试代码"""
    # 模拟生成草稿
    test_email = {
        'from': '张三 <zhangsan@example.com>',
        'subject': '项目进度更新',
        'body': '你好，请问项目进度如何？'
    }
    
    draft = generate_reply_draft(
        test_email,
        '项目进度一切正常，按计划推进中。'
    )
    
    print(format_draft_for_review(draft))
    
    # 保存草稿
    draft_id = save_draft(draft)
    print(f"\n草稿已保存，ID: {draft_id}")


if __name__ == '__main__':
    main()
