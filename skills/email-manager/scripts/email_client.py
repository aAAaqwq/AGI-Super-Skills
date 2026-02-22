#!/usr/bin/env python3
"""
Email Client - IMAP/SMTP 通用邮件客户端
支持 Gmail、QQ、Outlook 等邮箱
"""

import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

class EmailClient:
    """通用邮件客户端"""
    
    def __init__(self, account_config: Dict, provider_config: Dict):
        self.config = account_config
        self.provider = provider_config
        self.email_address = account_config['email']
        self.provider_name = account_config.get('provider', 'unknown')
        
    def _get_password(self) -> str:
        """从 pass 获取密码/授权码"""
        # 尝试不同的 pass 路径格式
        pass_paths = [
            f"email/{self.provider_name}/{self.email_address}",
            f"email/{self.provider_name}/{self.email_address}-app-pass",
            f"email/{self.provider_name}/{self.email_address}-auth-code",
        ]
        
        for path in pass_paths:
            try:
                result = subprocess.run(
                    ['pass', 'show', path],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return result.stdout.strip().split('\n')[0]
            except Exception:
                continue
        
        raise ValueError(f"未找到邮箱凭据: {self.email_address}")
    
    def connect_imap(self) -> imaplib.IMAP4_SSL:
        """连接 IMAP 服务器"""
        password = self._get_password()
        
        mail = imaplib.IMAP4_SSL(
            self.provider['imap_server'],
            self.provider['imap_port']
        )
        
        mail.login(self.email_address, password)
        return mail
    
    def connect_smtp(self) -> smtplib.SMTP:
        """连接 SMTP 服务器"""
        password = self._get_password()
        
        smtp = smtplib.SMTP(
            self.provider['smtp_server'],
            self.provider['smtp_port']
        )
        
        smtp.starttls()
        smtp.login(self.email_address, password)
        return smtp
    
    def fetch_unread(self, limit: int = 50) -> List[Dict]:
        """获取未读邮件"""
        mail = self.connect_imap()
        mail.select('INBOX')
        
        # 搜索未读邮件
        status, messages = mail.search(None, 'UNSEEN')
        
        if status != 'OK':
            mail.close()
            mail.logout()
            return []
        
        email_ids = messages[0].split()
        email_ids = email_ids[-limit:]  # 限制数量
        
        emails = []
        for email_id in email_ids:
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            if status == 'OK':
                msg = email.message_from_bytes(msg_data[0][1])
                email_data = self._parse_email(msg, email_id.decode())
                emails.append(email_data)
        
        mail.close()
        mail.logout()
        return emails
    
    def fetch_recent(self, hours: int = 24, limit: int = 50) -> List[Dict]:
        """获取最近 N 小时的邮件"""
        mail = self.connect_imap()
        mail.select('INBOX')
        
        # 搜索最近的邮件
        since_date = datetime.now().strftime('%d-%b-%Y')
        status, messages = mail.search(None, f'(SINCE {since_date})')
        
        if status != 'OK':
            mail.close()
            mail.logout()
            return []
        
        email_ids = messages[0].split()
        email_ids = email_ids[-limit:]  # 限制数量
        
        emails = []
        for email_id in reversed(email_ids):  # 最新的在前
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            if status == 'OK':
                msg = email.message_from_bytes(msg_data[0][1])
                email_data = self._parse_email(msg, email_id.decode())
                emails.append(email_data)
        
        mail.close()
        mail.logout()
        return emails
    
    def _parse_email(self, msg: email.message.Message, email_id: str) -> Dict:
        """解析邮件内容"""
        # 解码主题
        subject = ''
        if msg['Subject']:
            decoded_parts = decode_header(msg['Subject'])
            subject_parts = []
            for part, charset in decoded_parts:
                if isinstance(part, bytes):
                    subject_parts.append(part.decode(charset or 'utf-8', errors='ignore'))
                else:
                    subject_parts.append(part)
            subject = ''.join(subject_parts)
        
        # 解码发件人
        from_ = msg['From'] or ''
        if msg['From']:
            decoded_parts = decode_header(msg['From'])
            from_parts = []
            for part, charset in decoded_parts:
                if isinstance(part, bytes):
                    from_parts.append(part.decode(charset or 'utf-8', errors='ignore'))
                else:
                    from_parts.append(part)
            from_ = ''.join(from_parts)
        
        # 提取正文
        body = self._extract_body(msg)
        
        return {
            'id': email_id,
            'subject': subject,
            'from': from_,
            'to': msg['To'] or '',
            'date': msg['Date'] or '',
            'body': body[:1000],  # 限制正文长度
            'has_attachment': self._has_attachment(msg)
        }
    
    def _extract_body(self, msg: email.message.Message) -> str:
        """提取邮件正文"""
        body = ''
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        body = payload.decode(charset, errors='ignore')
                        break
                    except Exception:
                        continue
        else:
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or 'utf-8'
                body = payload.decode(charset, errors='ignore')
            except Exception:
                pass
        
        return body
    
    def _has_attachment(self, msg: email.message.Message) -> bool:
        """检查是否有附件"""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_disposition() == 'attachment':
                    return True
        return False
    
    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        is_html: bool = False,
        cc: List[str] = None,
        reply_to: str = None
    ) -> bool:
        """发送邮件"""
        try:
            smtp = self.connect_smtp()
            
            if is_html:
                msg = MIMEMultipart('alternative')
                msg.attach(MIMEText(body, 'html', 'utf-8'))
            else:
                msg = MIMEText(body, 'plain', 'utf-8')
            
            msg['From'] = self.email_address
            msg['To'] = to
            msg['Subject'] = subject
            
            if cc:
                msg['Cc'] = ', '.join(cc)
            
            if reply_to:
                msg['Reply-To'] = reply_to
            
            recipients = [to]
            if cc:
                recipients.extend(cc)
            
            smtp.sendmail(self.email_address, recipients, msg.as_string())
            smtp.quit()
            
            return True
        except Exception as e:
            print(f"发送邮件失败: {e}")
            return False
    
    def test_connection(self) -> Tuple[bool, str]:
        """测试邮箱连接"""
        try:
            # 测试 IMAP
            mail = self.connect_imap()
            mail.select('INBOX')
            mail.close()
            mail.logout()
            
            # 测试 SMTP
            smtp = self.connect_smtp()
            smtp.quit()
            
            return True, "连接成功"
        except Exception as e:
            return False, str(e)


def load_accounts() -> Tuple[List[Dict], Dict]:
    """加载账号和供应商配置"""
    base_path = Path(__file__).parent.parent / 'config'
    
    with open(base_path / 'accounts.json', 'r', encoding='utf-8') as f:
        accounts_config = json.load(f)
    
    with open(base_path / 'providers.json', 'r', encoding='utf-8') as f:
        providers = json.load(f)
    
    return accounts_config.get('accounts', []), providers


def get_all_clients() -> List[EmailClient]:
    """获取所有已配置的邮件客户端"""
    accounts, providers = load_accounts()
    
    clients = []
    for account in accounts:
        if not account.get('enabled', True):
            continue
        
        provider_name = account.get('provider')
        if provider_name not in providers:
            print(f"未知的邮件供应商: {provider_name}")
            continue
        
        client = EmailClient(account, providers[provider_name])
        clients.append(client)
    
    return clients


if __name__ == '__main__':
    # 测试代码
    clients = get_all_clients()
    for client in clients:
        print(f"\n测试账号: {client.email_address}")
        success, message = client.test_connection()
        print(f"结果: {message}")
        
        if success:
            emails = client.fetch_unread(limit=5)
            print(f"未读邮件: {len(emails)} 封")
            for e in emails:
                print(f"  - {e['subject']} (from: {e['from']})")
