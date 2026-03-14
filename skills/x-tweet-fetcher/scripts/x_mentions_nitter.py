#!/usr/bin/env python3
"""
x-mentions-nitter.py - 通过 Nitter 实时抓取 @YuLin807 的 mentions
比 Google/Brave 搜索快得多（分钟级 vs 小时级）

用法：
    python3 scripts/x-mentions-nitter.py
    退出码 0 = 无新内容，1 = 有新内容
"""

import sys
import os
import json
import re
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills/our/x-tweet-fetcher/scripts'))
from camofox_client import camofox_fetch_page

USERNAME = "YuLin807"
CACHE_FILE = "/tmp/x-mentions-nitter-cache.json"
RESULT_FILE = "/tmp/x-mentions-nitter-latest.json"
NITTER_URL = f"https://nitter.net/search?f=tweets&q=%40{USERNAME}"

def parse_mentions(snapshot):
    """从 Nitter 快照中解析 mentions"""
    mentions = []
    lines = snapshot.split('\n')
    
    current = {}
    for line in lines:
        line = line.strip()
        
        # 匹配用户链接 @username
        m = re.search(r'link "@(\w+)"', line)
        if m and m.group(1) != USERNAME:
            current['author'] = m.group(1)
        
        # 匹配时间链接（如 "50m", "1h", "2h", "Feb 26"）
        m = re.search(r'link "(\d+[mhd]|[A-Z][a-z]+ \d+)"', line)
        if m:
            current['time'] = m.group(1)
        
        # 匹配推文链接（/user/status/id#m）
        m = re.search(r'/url: /(\w+)/status/(\d+)#m', line)
        if m:
            current['url'] = f"https://x.com/{m.group(1)}/status/{m.group(2)}"
            current['tweet_id'] = m.group(2)
        
        # 匹配 "Replying to" 后面的文本内容
        if line.startswith('- text: ') and 'Replying to' not in line and current.get('author'):
            text = line[8:].strip()
            # 过滤掉纯数字行（点赞/转发计数）
            if text and not re.match(r'^[\d\s]+$', text) and len(text) > 2:
                current['text'] = text
                if current.get('url'):
                    mentions.append(dict(current))
                current = {}
    
    return mentions


def load_cache():
    """加载已知 tweet IDs"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return set(json.load(f))
    return set()


def save_cache(ids):
    """保存已知 tweet IDs"""
    with open(CACHE_FILE, 'w') as f:
        json.dump(list(ids)[-500:], f)


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔍 Nitter mentions 检查...")
    
    snapshot = camofox_fetch_page(NITTER_URL, "nitter-mentions-check", wait=8)
    if not snapshot:
        print("❌ Nitter 无响应")
        sys.exit(0)
    
    mentions = parse_mentions(snapshot)
    print(f"📊 解析到 {len(mentions)} 条 mentions")
    
    # 对比缓存找新的
    cache = load_cache()
    new_mentions = [m for m in mentions if m.get('tweet_id') not in cache]
    
    # 更新缓存
    all_ids = cache | {m['tweet_id'] for m in mentions if 'tweet_id' in m}
    save_cache(all_ids)
    
    # 输出
    output = {
        "timestamp": datetime.now().isoformat(),
        "total": len(mentions),
        "new_count": len(new_mentions),
        "new": new_mentions[:10],
    }
    
    with open(RESULT_FILE, 'w') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(json.dumps(output, ensure_ascii=False, indent=2))
    
    if new_mentions:
        print(f"\n⚠️ 发现 {len(new_mentions)} 条新 mentions！")
        sys.exit(1)
    else:
        print(f"\n✅ 无新 mentions")
        sys.exit(0)


if __name__ == "__main__":
    main()
