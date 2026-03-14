#!/usr/bin/env python3
"""QQ邮箱操作工具 - 支持读取、搜索、回复、发送邮件"""

import argparse
import imaplib
import smtplib
import email
import ssl
import subprocess
import sys
from email.header import decode_header, make_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, formatdate, make_msgid
from datetime import datetime


def get_auth_code(account: str) -> str:
    """从 pass 获取 QQ 邮箱授权码"""
    # Try multiple pass paths
    paths = [
        f"email/qq/{account}",
        f"email/qq/{account.split('@')[0]}",
        f"email/qq/{account}-auth-code",
    ]
    for path in paths:
        result = subprocess.run(
            ["pass", "show", path], capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")[0]
    print(f"ERROR: Auth code not found. Tried: {paths}", file=sys.stderr)
    sys.exit(1)


def decode_mime_header(header_value: str) -> str:
    """Decode MIME encoded header"""
    if not header_value:
        return ""
    try:
        decoded = decode_header(header_value)
        parts = []
        for part, charset in decoded:
            if isinstance(part, bytes):
                parts.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                parts.append(part)
        return " ".join(parts)
    except Exception:
        return str(header_value)


def get_email_body(msg) -> str:
    """Extract plain text body from email message"""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        # Fallback to HTML
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/html":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                html = payload.decode(charset, errors="replace")
                # Simple HTML to text
                import re
                text = re.sub(r"<br\s*/?>", "\n", html)
                text = re.sub(r"<p[^>]*>", "\n", text)
                text = re.sub(r"</p>", "", text)
                text = re.sub(r"<[^>]+>", "", text)
                text = re.sub(r"&nbsp;", " ", text)
                text = re.sub(r"&amp;", "&", text)
                text = re.sub(r"&lt;", "<", text)
                text = re.sub(r"&gt;", ">", text)
                return text.strip()
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return ""


def connect_imap(account: str):
    """Connect to QQ IMAP"""
    auth_code = get_auth_code(account)
    ctx = ssl.create_default_context()
    mail = imaplib.IMAP4_SSL("imap.qq.com", 993, ssl_context=ctx)
    mail.login(account, auth_code)
    return mail


def cmd_list(args):
    """List recent emails"""
    mail = connect_imap(args.account)
    mail.select("INBOX")
    status, messages = mail.search(None, "ALL")
    ids = messages[0].split()
    total = len(ids)
    limit = args.limit or 10
    show_ids = ids[-limit:]

    print(f"📧 {args.account} 收件箱 (共 {total} 封，显示最近 {len(show_ids)} 封)\n")
    for eid in show_ids:
        status, data = mail.fetch(eid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)] FLAGS)")
        raw = data[0][1]
        msg = email.message_from_bytes(raw)
        from_text = decode_mime_header(msg.get("From", ""))
        subj_text = decode_mime_header(msg.get("Subject", ""))
        date_text = msg.get("Date", "")[:25]
        # Check flags for SEEN
        flags = data[0][0].decode() if data[0][0] else ""
        seen = "📖" if "\\Seen" in flags else "📩"
        print(f"  {seen} ID:{eid.decode():>4} | {date_text:<25} | {from_text[:40]:<40} | {subj_text[:50]}")
    
    mail.logout()


def cmd_search(args):
    """Search emails by from/subject"""
    mail = connect_imap(args.account)
    mail.select("INBOX")
    
    criteria = []
    if args.sender:  # renamed from 'from' to avoid Python keyword
        criteria.append(f'(FROM "{args.sender}")')
    if args.subject:
        criteria.append(f'(SUBJECT "{args.subject}")')
    if not criteria:
        print("ERROR: Specify --from or --subject", file=sys.stderr)
        sys.exit(1)
    
    search_str = " ".join(criteria) if len(criteria) == 1 else f"({' '.join(criteria)})"
    status, messages = mail.search(None, *criteria)
    ids = messages[0].split()
    
    print(f"🔍 搜索结果: {len(ids)} 封\n")
    for eid in ids[-20:]:
        status, data = mail.fetch(eid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        raw = data[0][1]
        msg = email.message_from_bytes(raw)
        from_text = decode_mime_header(msg.get("From", ""))
        subj_text = decode_mime_header(msg.get("Subject", ""))
        date_text = msg.get("Date", "")[:25]
        print(f"  ID:{eid.decode():>4} | {date_text:<25} | {from_text[:40]:<40} | {subj_text[:50]}")
    
    mail.logout()


def cmd_read(args):
    """Read full email content"""
    mail = connect_imap(args.account)
    mail.select("INBOX")
    
    status, data = mail.fetch(str(args.id).encode(), "(BODY.PEEK[])")
    if status != "OK":
        print(f"ERROR: Failed to fetch email {args.id}", file=sys.stderr)
        sys.exit(1)
    
    raw = data[0][1]
    msg = email.message_from_bytes(raw)
    
    from_text = decode_mime_header(msg.get("From", ""))
    to_text = decode_mime_header(msg.get("To", ""))
    subj_text = decode_mime_header(msg.get("Subject", ""))
    date_text = msg.get("Date", "")
    body = get_email_body(msg)
    
    print(f"📧 邮件详情 (ID: {args.id})")
    print(f"{'='*60}")
    print(f"From:    {from_text}")
    print(f"To:      {to_text}")
    print(f"Subject: {subj_text}")
    print(f"Date:    {date_text}")
    print(f"Message-ID: {msg.get('Message-ID', '')}")
    print(f"{'='*60}")
    print(f"\n{body}")
    
    mail.logout()


def cmd_reply(args):
    """Reply to an email"""
    # First fetch the original email to get headers
    mail = connect_imap(args.account)
    mail.select("INBOX")
    
    status, data = mail.fetch(str(args.id).encode(), "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID REFERENCES)])")
    raw = data[0][1]
    orig = email.message_from_bytes(raw)
    mail.logout()
    
    orig_from = orig.get("From", "")
    orig_subject = decode_mime_header(orig.get("Subject", ""))
    orig_msgid = orig.get("Message-ID", "")
    orig_refs = orig.get("References", "")
    
    # Extract reply-to address
    from_parts = decode_header(orig_from)
    reply_to_addr = ""
    for part, enc in from_parts:
        text = part.decode(enc or "utf-8") if isinstance(part, bytes) else part
        if "@" in text:
            # Extract email from "Name <email>" format
            import re
            match = re.search(r"[\w\.-]+@[\w\.-]+", text)
            if match:
                reply_to_addr = match.group()
    
    if not reply_to_addr:
        reply_to_addr = orig_from
    
    # Build reply
    reply_subject = f"Re: {orig_subject}" if not orig_subject.startswith("Re:") else orig_subject
    
    msg = MIMEText(args.body, "plain", "utf-8")
    sender_name = args.sender_name or "Daniel Li"
    msg["From"] = formataddr((sender_name, args.account))
    msg["To"] = reply_to_addr
    msg["Subject"] = reply_subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="qq.com")
    
    # Thread headers
    if orig_msgid:
        msg["In-Reply-To"] = orig_msgid
        refs = f"{orig_refs} {orig_msgid}".strip() if orig_refs else orig_msgid
        msg["References"] = refs
    
    # Preview
    print(f"📤 回复预览:")
    print(f"{'='*60}")
    print(f"From:    {msg['From']}")
    print(f"To:      {msg['To']}")
    print(f"Subject: {msg['Subject']}")
    print(f"{'='*60}")
    print(f"\n{args.body}")
    print(f"\n{'='*60}")
    
    if args.dry_run:
        print("\n🔒 DRY RUN - 未实际发送")
        return
    
    # Send via SMTP
    auth_code = get_auth_code(args.account)
    ctx = ssl.create_default_context()
    
    with smtplib.SMTP_SSL("smtp.qq.com", 465, context=ctx) as smtp:
        smtp.login(args.account, auth_code)
        smtp.send_message(msg)
    
    print(f"\n✅ 回复已发送到 {reply_to_addr}")


def cmd_send(args):
    """Send a new email"""
    msg = MIMEText(args.body, "plain", "utf-8")
    sender_name = args.sender_name or "Daniel Li"
    msg["From"] = formataddr((sender_name, args.account))
    msg["To"] = args.to
    msg["Subject"] = args.subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="qq.com")
    
    print(f"📤 发送预览:")
    print(f"{'='*60}")
    print(f"From:    {msg['From']}")
    print(f"To:      {msg['To']}")
    print(f"Subject: {msg['Subject']}")
    print(f"{'='*60}")
    print(f"\n{args.body}")
    print(f"\n{'='*60}")
    
    if args.dry_run:
        print("\n🔒 DRY RUN - 未实际发送")
        return
    
    auth_code = get_auth_code(args.account)
    ctx = ssl.create_default_context()
    
    with smtplib.SMTP_SSL("smtp.qq.com", 465, context=ctx) as smtp:
        smtp.login(args.account, auth_code)
        smtp.send_message(msg)
    
    print(f"\n✅ 邮件已发送到 {args.to}")


def main():
    parser = argparse.ArgumentParser(description="QQ邮箱操作工具")
    parser.add_argument("--account", "-a", default="REDACTED_EMAIL", help="QQ邮箱地址")
    parser.add_argument("--sender-name", default="Daniel Li", help="发件人显示名")
    parser.add_argument("--dry-run", action="store_true", help="预览不发送")
    
    sub = parser.add_subparsers(dest="command", required=True)
    
    # list
    p_list = sub.add_parser("list", help="列出最近邮件")
    p_list.add_argument("--limit", "-l", type=int, default=10)
    
    # search
    p_search = sub.add_parser("search", help="搜索邮件")
    p_search.add_argument("--from", dest="sender", help="发件人")
    p_search.add_argument("--subject", "-s", help="主题关键词")
    
    # read
    p_read = sub.add_parser("read", help="读取邮件详情")
    p_read.add_argument("--id", type=int, required=True, help="邮件 ID")
    
    # reply
    p_reply = sub.add_parser("reply", help="回复邮件")
    p_reply.add_argument("--id", type=int, required=True, help="原邮件 ID")
    p_reply.add_argument("--body", "-b", required=True, help="回复内容")
    
    # send
    p_send = sub.add_parser("send", help="发送新邮件")
    p_send.add_argument("--to", required=True, help="收件人")
    p_send.add_argument("--subject", "-s", required=True, help="主题")
    p_send.add_argument("--body", "-b", required=True, help="邮件内容")
    
    args = parser.parse_args()
    
    commands = {
        "list": cmd_list,
        "search": cmd_search,
        "read": cmd_read,
        "reply": cmd_reply,
        "send": cmd_send,
    }
    
    commands[args.command](args)


if __name__ == "__main__":
    main()
