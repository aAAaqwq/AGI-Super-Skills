#!/usr/bin/env python3
"""draft_reviewer.py — 草稿预览推送脚本

功能：
- 读取 drafts/{date}/{topic_id}/{platform}.md
- 支持指定 date/topic/platform；支持 --all 推送当天所有草稿
- 推送到 Daniel (chat_id: YOUR_TELEGRAM_ID)
- --dry-run 仅打印

说明：
- 发送动作使用 OpenClaw message tool 更合适；脚本内默认走 newsbot_send.py 作为降级。
- 当前实现：优先调用 newsbot_send.py（如果其支持 --target/--chat-id），否则 dry-run。
"""

import argparse
import os
from pathlib import Path
from datetime import datetime
import textwrap
import subprocess
import sys

# 清除代理
for _k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
    os.environ.pop(_k, None)

from paths import DRAFTS_DIR, NEWSBOT_SEND
DANIEL_CHAT_ID = "YOUR_TELEGRAM_ID"

PLATFORMS = ["xiaohongshu", "twitter", "wechat"]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def preview(text: str, n: int = 300) -> str:
    t = " ".join(text.split())
    return t[:n] + ("..." if len(t) > n else "")


def iter_drafts(date_str: str, topic_id: str | None, platform: str | None):
    base = DRAFTS_DIR / date_str
    if not base.exists():
        return []

    items = []
    topic_dirs = [base / str(topic_id)] if topic_id else sorted([p for p in base.iterdir() if p.is_dir()], key=lambda p: int(p.name) if p.name.isdigit() else p.name)
    for td in topic_dirs:
        if not td.exists() or not td.is_dir():
            continue
        plats = [platform] if platform else PLATFORMS
        for plat in plats:
            f = td / f"{plat}.md"
            if f.exists():
                items.append((td.name, plat, f))
    return items


def format_message(date_str: str, topic_id: str, platform: str, content: str) -> str:
    head = f"📝 Draft Review\n\nDate: {date_str}\nTopic: #{topic_id}\nPlatform: {platform}\n"
    body = preview(content, 300)
    tail = "\n\n回复：✅ 通过 / ❌ 退回（可附原因）"
    return head + "\n" + body + tail


def send_via_newsbotsend(message: str, dry_run: bool):
    sender = NEWSBOT_SEND
    if dry_run:
        print("--- DRY RUN SEND ---")
        print(message)
        return True
    if not sender.exists():
        raise FileNotFoundError(f"newsbot_send.py 不存在：{NEWSBOT_SEND} (set NEWSBOT_SEND env var)")

    # 尝试把 Daniel chat_id 作为 target 参数传入（兼容不同实现）。
    candidates = [
        [sys.executable, str(sender), "--target", DANIEL_CHAT_ID, "--message", message],
        [sys.executable, str(sender), "--chat-id", DANIEL_CHAT_ID, "--message", message],
        [sys.executable, str(sender), "--to", DANIEL_CHAT_ID, "--message", message],
    ]
    last_err = None
    for cmd in candidates:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if p.returncode == 0:
            return True
        last_err = (p.stderr or p.stdout).strip()

    raise RuntimeError(f"newsbot_send.py 发送失败（可能不支持指定 chat_id 参数）。最后错误: {last_err}")


def main():
    ap = argparse.ArgumentParser(description="推送草稿预览到 Daniel")
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--topic-id", type=int, help="topic id (1-based)")
    ap.add_argument("--platform", choices=PLATFORMS)
    ap.add_argument("--all", action="store_true", help="推送当天所有草稿")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.all:
        topic_id = None
    else:
        topic_id = str(args.topic_id) if args.topic_id else None

    drafts = iter_drafts(args.date, topic_id, args.platform)
    if not drafts:
        print("⚠️ 未找到任何草稿", file=sys.stderr)
        return 1

    for tid, plat, path in drafts:
        content = read_text(path)
        msg = format_message(args.date, tid, plat, content)
        send_via_newsbotsend(msg, args.dry_run)
        print(f"✅ queued: {args.date}/{tid}/{plat}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
