#!/usr/bin/env python3
"""
Email Manager CLI - 邮箱管理命令行工具
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from email_client import get_all_clients, EmailClient, load_accounts


def cmd_list_accounts():
    """列出所有已配置的邮箱账号"""
    accounts, providers = load_accounts()
    
    if not accounts:
        print("📭 暂无配置的邮箱账号")
        print("\n添加账号步骤:")
        print("1. 使用 pass 存储邮箱凭据:")
        print("   pass insert email/gmail/your-email@gmail.com")
        print("   pass insert email/gmail/your-email@gmail.com-app-pass")
        print("2. 编辑 config/accounts.json 添加账号配置")
        return
    
    print("📧 已配置的邮箱账号:")
    for i, account in enumerate(accounts, 1):
        status = "✅" if account.get('enabled', True) else "❌"
        print(f"{i}. {status} {account.get('name', account['email'])}")
        print(f"   类型: {account.get('provider', 'unknown')}")
        print(f"   邮箱: {account['email']}")


def cmd_test_connection():
    """测试所有邮箱连接"""
    clients = get_all_clients()
    
    if not clients:
        print("⚠️ 未配置任何邮箱账号")
        return
    
    print("🔌 测试邮箱连接...\n")
    
    all_success = True
    for client in clients:
        print(f"测试: {client.config.get('name', client.email_address)}")
        success, message = client.test_connection()
        
        if success:
            print(f"  ✅ {message}")
        else:
            print(f"  ❌ {message}")
            all_success = False
    
    if all_success:
        print("\n🎉 所有邮箱连接正常")
    else:
        print("\n⚠️ 部分邮箱连接失败，请检查配置")


def cmd_check_emails():
    """检查邮件"""
    from check_email import check_all_emails
    
    print("📬 开始检查邮件...\n")
    summary = check_all_emails()
    print(summary)


def cmd_add_account():
    """添加新邮箱账号（交互式）"""
    print("📧 添加新邮箱账号\n")
    
    # 选择邮箱类型
    print("支持的邮箱类型:")
    print("1. Gmail")
    print("2. QQ邮箱")
    print("3. Outlook")
    print("4. 163邮箱")
    print("5. 126邮箱")
    
    choice = input("\n选择邮箱类型 (1-5): ").strip()
    
    providers_map = {
        '1': 'gmail',
        '2': 'qq',
        '3': 'outlook',
        '4': '163',
        '5': '126'
    }
    
    provider = providers_map.get(choice)
    if not provider:
        print("❌ 无效的选择")
        return
    
    # 获取邮箱地址
    email_address = input("邮箱地址: ").strip()
    if not email_address:
        print("❌ 邮箱地址不能为空")
        return
    
    # 获取账号名称
    account_name = input("账号名称 (可选，直接回车使用邮箱地址): ").strip()
    if not account_name:
        account_name = email_address
    
    print(f"\n📝 配置信息:")
    print(f"  类型: {provider}")
    print(f"  邮箱: {email_address}")
    print(f"  名称: {account_name}")
    
    # 提示存储凭据
    print(f"\n🔐 请先存储邮箱凭据:")
    print(f"   pass insert email/{provider}/{email_address}")
    
    if provider in ['gmail', 'outlook']:
        print(f"   pass insert email/{provider}/{email_address}-app-pass")
    else:
        print(f"   pass insert email/{provider}/{email_address}-auth-code")
    
    confirm = input("\n已完成凭据存储? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ 取消添加")
        return
    
    # 添加到配置文件
    accounts_path = Path(__file__).parent.parent / 'config' / 'accounts.json'
    
    with open(accounts_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 加载供应商配置
    providers_path = Path(__file__).parent.parent / 'config' / 'providers.json'
    with open(providers_path, 'r', encoding='utf-8') as f:
        providers = json.load(f)
    
    provider_config = providers[provider]
    
    new_account = {
        "name": account_name,
        "email": email_address,
        "provider": provider,
        "imap_server": provider_config['imap_server'],
        "imap_port": provider_config['imap_port'],
        "smtp_server": provider_config['smtp_server'],
        "smtp_port": provider_config['smtp_port'],
        "enabled": True
    }
    
    config['accounts'].append(new_account)
    
    with open(accounts_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 账号已添加: {account_name}")
    print("   运行 'python3 manage.py test' 测试连接")


def cmd_show_help():
    """显示帮助"""
    print("Email Manager - 邮箱管理工具\n")
    print("用法: python3 manage.py <command>\n")
    print("命令:")
    print("  list    - 列出所有已配置的邮箱账号")
    print("  test    - 测试所有邮箱连接")
    print("  check   - 检查邮件并生成摘要")
    print("  add     - 添加新邮箱账号（交互式）")
    print("  help    - 显示此帮助")


def main():
    if len(sys.argv) < 2:
        cmd_show_help()
        return
    
    command = sys.argv[1].lower()
    
    commands = {
        'list': cmd_list_accounts,
        'test': cmd_test_connection,
        'check': cmd_check_emails,
        'add': cmd_add_account,
        'help': cmd_show_help,
    }
    
    if command in commands:
        commands[command]()
    else:
        print(f"❌ 未知命令: {command}")
        cmd_show_help()


if __name__ == '__main__':
    main()
