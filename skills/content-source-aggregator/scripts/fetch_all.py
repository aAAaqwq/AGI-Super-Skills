#!/usr/bin/env python3
"""
统一信息源热点采集器
从 X/Twitter、YouTube、B站、GitHub、Reddit、LinuxDo 免费采集热门内容
"""

import json
import re
import sys
import html as htmlmod
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "config.json"
OUTPUT_DIR = Path.home() / "clawd/workspace/content-pipeline/hotpool"

TZ_CST = timezone(timedelta(hours=8))
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def http_get(url, headers=None, timeout=15):
    hdrs = {"User-Agent": UA}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def http_get_json(url, headers=None, timeout=15):
    return json.loads(http_get(url, headers, timeout))


# ── Twitter/X ──────────────────────────────────────

def fetch_twitter(config):
    """通过 syndication API 免费获取推文"""
    items = []
    accounts = config.get("accounts", [])
    for account in accounts:
        try:
            url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{account}"
            html = http_get(url)
            # 提取推文文本
            texts = re.findall(r'"text":"([^"]{20,500})"', html)
            for i, text in enumerate(texts[:3]):
                clean = htmlmod.unescape(text).replace("\\n", " ").strip()
                if clean.startswith("RT @"):
                    continue  # 跳过转推
                items.append({
                    "source": "twitter",
                    "title": clean[:120],
                    "url": f"https://x.com/{account}",
                    "summary": clean[:300],
                    "category": "Social/Tech",
                    "engagement": {},
                    "author": account,
                })
        except Exception as e:
            print(f"  ⚠️ Twitter @{account}: {e}", file=sys.stderr)
    return items


# ── YouTube ────────────────────────────────────────

def fetch_youtube(config):
    """通过 RSS Feed 免费获取频道最新视频"""
    items = []
    channels = config.get("channels", {})
    for name, channel_id in channels.items():
        try:
            url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            xml = http_get(url)
            entries = re.findall(
                r"<entry>.*?<title>(.+?)</title>.*?<yt:videoId>(.+?)</yt:videoId>.*?<published>(.+?)</published>.*?</entry>",
                xml, re.DOTALL
            )
            for title, vid, published in entries[:3]:
                title = htmlmod.unescape(title)
                items.append({
                    "source": "youtube",
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "summary": f"[{name}] {title}",
                    "category": "Video/Tech",
                    "engagement": {},
                    "author": name,
                    "published": published,
                })
        except Exception as e:
            print(f"  ⚠️ YouTube {name}: {e}", file=sys.stderr)
    return items


# ── B站 ───────────────────────────────────────────

def fetch_bilibili(config):
    """通过公开 API 获取B站热门排行"""
    items = []
    headers = {"Referer": "https://www.bilibili.com"}
    try:
        data = http_get_json(
            "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all",
            headers=headers
        )
        if data.get("code") == 0:
            for v in data["data"]["list"][:15]:
                items.append({
                    "source": "bilibili",
                    "title": v["title"],
                    "url": f"https://www.bilibili.com/video/{v['bvid']}",
                    "summary": v.get("desc", "")[:200],
                    "category": v.get("tname", "综合"),
                    "engagement": {
                        "views": v.get("stat", {}).get("view", 0),
                        "likes": v.get("stat", {}).get("like", 0),
                        "comments": v.get("stat", {}).get("reply", 0),
                    },
                    "author": v.get("owner", {}).get("name", ""),
                })
    except Exception as e:
        print(f"  ⚠️ Bilibili: {e}", file=sys.stderr)

    # 热搜
    try:
        data = http_get_json(
            "https://api.bilibili.com/x/web-interface/wbi/search/square?limit=10",
            headers=headers
        )
        if data.get("code") == 0:
            trending = data.get("data", {}).get("trending", {})
            for t in trending.get("list", [])[:10]:
                items.append({
                    "source": "bilibili",
                    "title": f"[热搜] {t.get('keyword', t.get('show_name', ''))}",
                    "url": f"https://search.bilibili.com/all?keyword={urllib.parse.quote(t.get('keyword', ''))}",
                    "summary": t.get("show_name", ""),
                    "category": "热搜",
                    "engagement": {},
                })
    except Exception as e:
        print(f"  ⚠️ Bilibili 热搜: {e}", file=sys.stderr)

    return items


# ── GitHub ─────────────────────────────────────────

def fetch_github(config):
    """通过 Search API 获取近期热门仓库"""
    items = []
    lookback = config.get("lookback_days", 1)
    min_stars = config.get("min_stars", 100)
    date_str = (datetime.now(TZ_CST) - timedelta(days=lookback)).strftime("%Y-%m-%d")
    try:
        url = f"https://api.github.com/search/repositories?q=stars:>{min_stars}+pushed:>{date_str}&sort=stars&per_page=15"
        data = http_get_json(url)
        for r in data.get("items", [])[:15]:
            items.append({
                "source": "github",
                "title": f"{r['full_name']} ⭐{r['stargazers_count']}",
                "url": r["html_url"],
                "summary": (r.get("description") or "")[:200],
                "category": r.get("language", "Unknown"),
                "engagement": {
                    "stars": r["stargazers_count"],
                    "forks": r.get("forks_count", 0),
                },
                "author": r["owner"]["login"],
            })
    except Exception as e:
        print(f"  ⚠️ GitHub: {e}", file=sys.stderr)
    return items


# ── Reddit ─────────────────────────────────────────

def fetch_reddit(config):
    """通过 PullPush API 免费获取热门帖子"""
    items = []
    subreddits = config.get("subreddits", ["technology"])
    for sub in subreddits:
        try:
            url = f"https://api.pullpush.io/reddit/search/submission/?subreddit={sub}&sort=score&sort_type=desc&size=5"
            data = http_get_json(url)
            for p in data.get("data", [])[:5]:
                items.append({
                    "source": "reddit",
                    "title": p.get("title", ""),
                    "url": f"https://reddit.com{p.get('permalink', '')}",
                    "summary": (p.get("selftext") or "")[:200],
                    "category": f"r/{sub}",
                    "engagement": {
                        "upvotes": p.get("score", 0),
                        "comments": p.get("num_comments", 0),
                    },
                    "author": p.get("author", ""),
                })
        except Exception as e:
            print(f"  ⚠️ Reddit r/{sub}: {e}", file=sys.stderr)
    return items


# ── LinuxDo ────────────────────────────────────────

def fetch_linuxdo(config):
    """通过 Discourse JSON API 获取热门帖子
    注意: LinuxDo 有 Cloudflare 防护，直接请求会 403
    方案1: 使用已保存的 cookie/session
    方案2: 通过 web_fetch 工具（OpenClaw 内置，自带浏览器指纹）
    方案3: 通过 Playwright 登录态抓取
    """
    items = []

    # 尝试用 cookie 文件
    cookie_file = Path.home() / ".playwright-data/linuxdo/cookies.txt"
    headers = {
        "Accept": "application/json",
        "Referer": "https://linux.do/",
    }
    if cookie_file.exists():
        with open(cookie_file) as f:
            headers["Cookie"] = f.read().strip()

    try:
        data = http_get_json("https://linux.do/latest.json?order=default", headers=headers)
        topics = data.get("topic_list", {}).get("topics", [])
        for t in topics[:15]:
            items.append({
                "source": "linuxdo",
                "title": t.get("title", ""),
                "url": f"https://linux.do/t/{t.get('slug', '')}/{t.get('id', '')}",
                "summary": "",
                "category": str(t.get("category_id", "")),
                "engagement": {
                    "views": t.get("views", 0),
                    "likes": t.get("like_count", 0),
                    "comments": t.get("posts_count", 0),
                },
            })
    except Exception as e:
        print(f"  ⚠️ LinuxDo: {e} (需要登录态或 Playwright)", file=sys.stderr)
    return items


# ── 抖音 ──────────────────────────────────────────

def fetch_douyin(config):
    """通过抖音热搜 API 免费获取热门话题"""
    items = []
    try:
        data = http_get_json(
            "https://www.douyin.com/aweme/v1/web/hot/search/list/",
            headers={"Referer": "https://www.douyin.com/"}
        )
        for w in data.get("data", {}).get("word_list", [])[:20]:
            word = w.get("word", "")
            items.append({
                "source": "douyin",
                "title": word,
                "url": f"https://www.douyin.com/search/{urllib.parse.quote(word)}",
                "summary": w.get("sentence_tag", ""),
                "category": "热搜",
                "engagement": {
                    "hot_value": w.get("hot_value", 0),
                },
            })
    except Exception as e:
        print(f"  ⚠️ 抖音: {e}", file=sys.stderr)
    return items


# ── 小红书 ────────────────────────────────────────

def fetch_xiaohongshu(config):
    """通过小红书 web 端获取热门内容（需要登录态 cookie）"""
    items = []
    cookie_file = Path.home() / ".playwright-data/xiaohongshu/cookies.txt"
    if not cookie_file.exists():
        print("  ⚠️ 小红书: 需要登录态 cookie (~/.playwright-data/xiaohongshu/cookies.txt)", file=sys.stderr)
        return items

    headers = {
        "Referer": "https://www.xiaohongshu.com/",
        "Origin": "https://www.xiaohongshu.com",
        "Cookie": cookie_file.read_text().strip(),
    }
    try:
        html = http_get("https://www.xiaohongshu.com/explore", headers=headers)
        match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?})\s*</script>', html, re.DOTALL)
        if match:
            raw = match.group(1).replace("undefined", "null")
            state = json.loads(raw)
            feed = state.get("explore", {}).get("feeds", [])
            for note in feed[:15]:
                note_data = note.get("noteCard", note)
                items.append({
                    "source": "xiaohongshu",
                    "title": note_data.get("title", note_data.get("displayTitle", "")),
                    "url": f"https://www.xiaohongshu.com/explore/{note.get('id', '')}",
                    "summary": note_data.get("desc", "")[:200],
                    "category": "小红书",
                    "engagement": {
                        "likes": note_data.get("interactInfo", {}).get("likedCount", 0),
                    },
                    "author": note_data.get("user", {}).get("nickname", ""),
                })
    except Exception as e:
        print(f"  ⚠️ 小红书: {e}", file=sys.stderr)
    return items


# ── 微信公众号 ────────────────────────────────────

def fetch_wechat_mp(config):
    """通过搜狗微信搜索获取热门公众号文章（需要登录态）"""
    items = []
    cookie_file = Path.home() / ".playwright-data/sogou-weixin/cookies.txt"
    headers = {"Referer": "https://weixin.sogou.com/"}
    if cookie_file.exists():
        headers["Cookie"] = cookie_file.read_text().strip()

    keywords = config.get("keywords", ["AI", "科技", "互联网"])
    for kw in keywords[:3]:
        try:
            url = f"https://weixin.sogou.com/weixin?type=2&query={urllib.parse.quote(kw)}&ie=utf8"
            html = http_get(url, headers=headers)
            # 提取文章标题和链接
            articles = re.findall(
                r'<a[^>]*href="([^"]*)"[^>]*target="_blank"[^>]*>(.*?)</a>',
                html, re.DOTALL
            )
            for href, title_html in articles[:5]:
                title = re.sub(r'<[^>]+>', '', title_html).strip()
                if len(title) > 5 and "sogou" not in title.lower():
                    items.append({
                        "source": "wechat_mp",
                        "title": title,
                        "url": href if href.startswith("http") else f"https://weixin.sogou.com{href}",
                        "summary": "",
                        "category": f"公众号/{kw}",
                        "engagement": {},
                    })
        except Exception as e:
            print(f"  ⚠️ 微信公众号 [{kw}]: {e}", file=sys.stderr)
    return items


# ── 微信视频号 ────────────────────────────────────

def fetch_wechat_video(config):
    """微信视频号无公开 API，需要 Playwright 登录态"""
    print("  ⚠️ 微信视频号: 无公开 API，需要 Playwright 登录态抓取", file=sys.stderr)
    return []


# ── 主流程 ─────────────────────────────────────────

FETCHERS = {
    "twitter": fetch_twitter,
    "youtube": fetch_youtube,
    "bilibili": fetch_bilibili,
    "github": fetch_github,
    "reddit": fetch_reddit,
    "linuxdo": fetch_linuxdo,
    "douyin": fetch_douyin,
    "xiaohongshu": fetch_xiaohongshu,
    "wechat_mp": fetch_wechat_mp,
    "wechat_video": fetch_wechat_video,
}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="信息源热点采集")
    parser.add_argument("--source", choices=list(FETCHERS.keys()), help="只采集指定平台")
    parser.add_argument("--dry-run", action="store_true", help="只打印不保存")
    args = parser.parse_args()

    config = load_config()
    now = datetime.now(TZ_CST)
    all_items = []

    sources = [args.source] if args.source else list(FETCHERS.keys())

    for src in sources:
        src_config = config.get(src, {})
        if not src_config.get("enabled", True):
            print(f"⏭️  {src}: disabled")
            continue
        print(f"🔍 采集 {src}...")
        try:
            items = FETCHERS[src](src_config)
            for item in items:
                item["fetched_at"] = now.isoformat()
            all_items.extend(items)
            print(f"  ✅ {len(items)} 条")
        except Exception as e:
            print(f"  ❌ {src}: {e}")

    # 输出
    output = {
        "date": now.strftime("%Y-%m-%d"),
        "fetched_at": now.isoformat(),
        "total": len(all_items),
        "sources": {src: len([i for i in all_items if i["source"] == src]) for src in sources},
        "items": all_items,
    }

    if args.dry_run:
        print(json.dumps(output, indent=2, ensure_ascii=False)[:3000])
        print(f"\n... 共 {len(all_items)} 条")
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        outfile = OUTPUT_DIR / f"{now.strftime('%Y-%m-%d')}.json"
        with open(outfile, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"\n📁 已保存: {outfile}")
        print(f"📊 共 {len(all_items)} 条 ({', '.join(f'{k}:{v}' for k,v in output['sources'].items())})")


if __name__ == "__main__":
    main()
