#!/usr/bin/env python3
"""Push a message to the user's Telegram via the cc-connect bot.

Reads bot token + chat id from ~/.cc-connect/config.toml (no duplicated secrets).
Usage:
    python3 telegram_push.py "message text"
    echo "message" | python3 telegram_push.py
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

CONFIG = os.path.expanduser("~/.cc-connect/config.toml")


def load_telegram_creds():
    with open(CONFIG) as f:
        text = f.read()
    m = re.search(r'^\s*token\s*=\s*"(\d+:[A-Za-z0-9_-]+)"\s*$', text, re.M)
    token = m.group(1) if m else None
    chat = None
    for key in ("allow_from", "admin_from"):
        m = re.search(rf'^\s*{key}\s*=\s*"?(\d+)"?\s*$', text, re.M)
        if m:
            chat = m.group(1).split(",")[0].strip()
            break
    return token, chat


def send(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status
        except Exception as e:
            if attempt == 2:
                return f"ERR {e}"
            time.sleep(2)
    return "ERR"


def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    if not msg.strip():
        return
    token, chat = load_telegram_creds()
    if not token or not chat:
        sys.stderr.write("no token/chat in config\n")
        sys.exit(1)
    print(send(token, chat, msg), flush=True)


if __name__ == "__main__":
    main()
