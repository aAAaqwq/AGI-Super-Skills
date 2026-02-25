#!/usr/bin/env python3
"""
Check Email - 检查邮件并生成智能摘要
定时任务调用此脚本
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from email_client import get_all_clients, EmailClient

def format_email_summary(emails: List[Dict], account_name: str) -> str:
    """格式化单个账号的邮件摘要"""
    if not emails:
        return ""
    
    summary = f"\n📧 **{account_name}** ({len(emails)} 封未读):\n"
    
    for i, email in enumerate(emails[:10], 1):  # 最多显示 10 封
        subject = email['subject'][:50]  # 截断主题
        from_ = email['from']
        
        # 检查是否包含重要关键词
        important_keywords = ['urgent', '重要', '紧急', 'deadline', '截止', 'asap', 'immediately']
        is_important = any(kw in subject.lower() or kw in email['body'].lower() 
                          for kw in important_keywords)
        
        prefix = "🔴" if is_important else "  "
        summary += f"{prefix} {i}. {subject} - {from_}\n"
    
    return summary


def generate_ai_summary(all_emails: Dict[str, List[Dict]]) -> str:
    """使用 AI 生成智能摘要（简化版，可后续接入 LLM）"""
    total_count = sum(len(emails) for emails in all_emails.values())
    
    if total_count == 0:
        return "📭 暂无新邮件"
    
    summary = f"📬 **今日邮件摘要** ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n"
    summary += f"共 {total_count} 封未读邮件\n"
    
    # 按账号分组
    for account_name, emails in all_emails.items():
        account_summary = format_email_summary(emails, account_name)
        summary += account_summary
    
    # 检查重要邮件
    important_emails = []
    for account_name, emails in all_emails.items():
        for email in emails:
            important_keywords = ['urgent', '重要', '紧急', 'deadline', '截止']
            if any(kw in email['subject'].lower() or kw in email['body'].lower() 
                   for kw in important_keywords):
                important_emails.append((account_name, email))
    
    if important_emails:
        summary += "\n⚠️ **重要邮件提醒**:\n"
        for account_name, email in important_emails:
            summary += f"  • [{account_name}] {email['subject']}\n"
    
    return summary


def save_email_cache(all_emails: Dict[str, List[Dict]]):
    """保存邮件缓存（用于后续回复等操作）"""
    cache_path = Path(__file__).parent.parent / 'cache' / 'emails.json'
    cache_path.parent.mkdir(exist_ok=True)
    
    cache_data = {
        'timestamp': datetime.now().isoformat(),
        'emails': all_emails
    }
    
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)


def check_all_emails() -> str:
    """检查所有邮箱并返回摘要"""
    clients = get_all_clients()
    
    if not clients:
        return "⚠️ 未配置任何邮箱账号，请先添加账号"
    
    all_emails = {}
    
    for client in clients:
        try:
            # 直接获取未读邮件（跳过 test_connection 节省连接时间）
            emails = client.fetch_unread(limit=10)
            account_name = client.config.get('name', client.email_address)
            all_emails[account_name] = emails
            
        except Exception as e:
            print(f"检查邮箱 {client.email_address} 失败: {e}")
            all_emails[client.config.get('name', client.email_address)] = []
    
    # 保存缓存
    save_email_cache(all_emails)
    
    # 生成摘要
    summary = generate_ai_summary(all_emails)
    
    return summary


def main():
    """主函数"""
    print("开始检查邮件...")
    
    try:
        summary = check_all_emails()
        print(summary)
        
        # 输出到文件（供 cron 任务读取）
        output_path = Path(__file__).parent.parent / 'cache' / 'last_summary.txt'
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(summary)
        
        print(f"\n摘要已保存到: {output_path}")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
