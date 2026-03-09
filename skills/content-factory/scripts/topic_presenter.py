#!/usr/bin/env python3
"""topic_presenter.py

将评分后的选题（topics/YYYY-MM-DD.json）格式化为 Telegram 卡片消息并推送。

需求：
1) 读取 ~/clawd/workspace/content-pipeline/topics/YYYY-MM-DD.json
2) 格式化消息（编号、标题、分数、来源、角度）
3) 调用 ~/clawd/scripts/newsbot_send.py 推送
4) --dry-run 只打印不发送
5) --top N 推送 Top N

用法：
  python topic_presenter.py
  python topic_presenter.py --date 2026-03-02 --top 5 --dry-run

注意：脚本不依赖 topic_scorer.py，可独立运行。
"""

import argparse
import json
import sys
import subprocess
from datetime import datetime
from pathlib import Path

from paths import TOPICS_DIR, NEWSBOT_SEND


def load_topics(date_str: str) -> dict:
    path = TOPICS_DIR / f"{date_str}.json"
    if not path.exists():
        # 回退到最新
        files = sorted(TOPICS_DIR.glob("*.json"), reverse=True)
        if not files:
            raise FileNotFoundError(f"topics 目录为空: {TOPICS_DIR}")
        path = files[0]
        print(f"⚠️ 未找到 {date_str}.json，回退到最新: {path.name}")

    data = json.loads(path.read_text())
    if "top" not in data:
        raise ValueError(f"topics 文件缺少 top 字段: {path}")
    return data


def normalize_source(item: dict) -> str:
    source = item.get("source", "?")
    category = item.get("category", "")
    if category:
        return f"{source}/{category}"
    return str(source)


def format_message(top_items: list, date_str: str, title_prefix: str = "📰 今日选题") -> str:
    nums = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    lines = [
        f"{title_prefix} Top {len(top_items)} ({date_str})",
        "",
    ]

    for i, item in enumerate(top_items):
        num = nums[i] if i < 10 else f"[{i+1}]"
        score = item.get("total_score", item.get("score", "?"))
        title = (item.get("title") or "").strip()
        if len(title) > 80:
            title = title[:77] + "..."

        src = normalize_source(item)
        angle = (item.get("angle") or "").strip()
        if not angle:
            angle = "(未提供)"

        lines.append(f"{num} [{score}分] {title} - {src}")
        lines.append(f"   💡 角度：{angle}")
        lines.append("")

    lines.append("回复编号（如 \"1 3 7\"）选择要创作的主题")
    return "\n".join(lines).rstrip() + "\n"


def send(message: str) -> None:
    sender = NEWSBOT_SEND
    if not sender.exists():
        raise FileNotFoundError(f"newsbot_send.py 不存在：{NEWSBOT_SEND} (set NEWSBOT_SEND env var)")

    proc = subprocess.run(
        [sys.executable, str(sender), "--message", message],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "newsbot_send failed")


def main():
    parser = argparse.ArgumentParser(description="推送今日选题到 Telegram")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="topics 日期")
    parser.add_argument("--top", type=int, default=10, help="推送 Top N")
    parser.add_argument("--dry-run", action="store_true", help="只打印不发送")
    args = parser.parse_args()

    data = load_topics(args.date)
    top_items = data.get("top", [])[: max(args.top, 0)]

    if not top_items:
        print("⚠️ topics.top 为空，退出")
        return 1

    date_str = data.get("date", args.date)
    msg = format_message(top_items, date_str)

    if args.dry_run:
        print(msg)
        return 0

    send(msg)
    print("✅ 已推送")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
