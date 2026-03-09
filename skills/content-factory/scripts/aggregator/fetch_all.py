#!/usr/bin/env python3
"""
统一信息源热点采集器
从 微博/知乎/头条/抖音/B站/GitHub/YouTube/Twitter/Reddit/LinuxDo 等平台采集热门内容
HTTP请求统一用 subprocess+curl 避免 SSL 问题
"""

import json
import re
import subprocess
import sys
import html as htmlmod
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "config.json"
# Portable: output to skill data dir
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "hotpool"

TZ_CST = timezone(timedelta(hours=8))
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def curl_get(url, headers=None, timeout=15):
    """用 subprocess+curl 获取 URL 内容，避免 SSL 问题"""
    cmd = ["curl", "-s", "--max-time", str(timeout), "-L",
           "-H", f"User-Agent: {UA}"]
    if headers:
        for k, v in headers.items():
            cmd += ["-H", f"{k}: {v}"]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}): {r.stderr[:200]}")
    return r.stdout


def curl_get_json(url, headers=None, timeout=15):
    return json.loads(curl_get(url, headers, timeout))


# Legacy compat
http_get = curl_get
http_get_json = curl_get_json


# ── 60s API 通用解析 ──────────────────────────────

def _parse_60s_v2(source_name, api_path, category="热搜"):
    """通用 60s API v2 解析器 (字段: code/data, 每条: title/link/hot_value)"""
    items = []
    try:
        data = curl_get_json(f"https://60s.viki.moe/v2/{api_path}")
        if data.get("code") != 200:
            print(f"  ⚠️ {source_name} 60s API: code={data.get('code')}", file=sys.stderr)
            return items
        for entry in data.get("data", []):
            title = entry.get("title", entry.get("name", entry.get("word", "")))
            url = entry.get("link", entry.get("url", entry.get("mobileUrl", "")))
            if not title:
                continue
            item = {
                "source": source_name,
                "title": title,
                "url": url,
                "summary": entry.get("desc", entry.get("excerpt", ""))[:200] if entry.get("desc") or entry.get("excerpt") else "",
                "category": category,
                "engagement": {},
            }
            hot = entry.get("hot_value", entry.get("hotValue", entry.get("hot", 0)))
            if hot:
                item["engagement"]["hot_value"] = hot
            items.append(item)
    except Exception as e:
        print(f"  ⚠️ {source_name}: {e}", file=sys.stderr)
    return items


# ── 微博热搜 (60s API) ────────────────────────────

def fetch_weibo(config):
    """通过 60s API 获取微博热搜"""
    return _parse_60s_v2("weibo", "weibo", "微博热搜")


# ── 知乎热榜 (60s API) ────────────────────────────

def fetch_zhihu(config):
    """通过 60s API 获取知乎热榜"""
    return _parse_60s_v2("zhihu", "zhihu", "知乎热榜")


# ── 头条热榜 (60s API) ────────────────────────────

def fetch_toutiao(config):
    """通过 60s API 获取今日头条热榜"""
    return _parse_60s_v2("toutiao", "toutiao", "头条热榜")


# ── 抖音热搜 (60s API, 替代原生) ──────────────────

def fetch_douyin(config):
    """通过 60s API 获取抖音热搜"""
    return _parse_60s_v2("douyin", "douyin", "抖音热搜")


# ── Twitter/X ──────────────────────────────────────

def fetch_twitter(config):
    items = []
    accounts = config.get("accounts", [])
    for account in accounts:
        try:
            url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{account}"
            html = curl_get(url)
            texts = re.findall(r'"text":"([^"]{20,500})"', html)
            for text in texts[:3]:
                clean = htmlmod.unescape(text).replace("\\n", " ").strip()
                if clean.startswith("RT @"):
                    continue
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
    items = []
    channels = config.get("channels", {})
    for name, channel_id in channels.items():
        try:
            url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            xml = curl_get(url)
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
    items = []
    try:
        data = curl_get_json(
            "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all",
            headers={"Referer": "https://www.bilibili.com"}
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
        print(f"  ⚠️ Bilibili 原生API: {e}, 回退60s", file=sys.stderr)
        items.extend(_parse_60s_v2("bilibili", "bili", "B站热门"))

    try:
        data = curl_get_json(
            "https://api.bilibili.com/x/web-interface/wbi/search/square?limit=10",
            headers={"Referer": "https://www.bilibili.com"}
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


# ── GitHub Trending ────────────────────────────────

def fetch_github(config):
    """GitHub Trending daily（替代原来的全历史star排名）"""
    items = []
    try:
        html = curl_get("https://github.com/trending?since=daily")
        repos = re.findall(r'<h2[^>]*>\s*<a[^>]*href="/([^"]+)"[^>]*>', html)
        for repo_path in repos[:15]:
            repo_path = repo_path.strip()
            if not repo_path or repo_path.count('/') != 1:
                continue
            desc_match = re.search(
                rf'href="/{re.escape(repo_path)}".*?<p[^>]*>(.*?)</p>',
                html, re.DOTALL
            )
            desc = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()[:200] if desc_match else ""
            stars_match = re.search(
                rf'{re.escape(repo_path)}.*?(\d[\d,]*)\s*stars today', html, re.DOTALL
            )
            stars_today = int(stars_match.group(1).replace(',', '')) if stars_match else 0
            items.append({
                "source": "github",
                "title": f"{repo_path} 🔥+{stars_today}⭐/today" if stars_today else repo_path,
                "url": f"https://github.com/{repo_path}",
                "summary": desc,
                "category": "GitHub Trending",
                "engagement": {"stars_today": stars_today},
                "author": repo_path.split('/')[0],
            })
    except Exception as e:
        print(f"  ⚠️ GitHub Trending: {e}, 回退Search API", file=sys.stderr)
        lookback = config.get("lookback_days", 1)
        min_stars = config.get("min_stars", 100)
        date_str = (datetime.now(TZ_CST) - timedelta(days=lookback)).strftime("%Y-%m-%d")
        try:
            url = f"https://api.github.com/search/repositories?q=stars:>{min_stars}+pushed:>{date_str}&sort=stars&per_page=15"
            data = curl_get_json(url)
            for r in data.get("items", [])[:15]:
                items.append({
                    "source": "github", "title": f"{r['full_name']} ⭐{r['stargazers_count']}",
                    "url": r["html_url"], "summary": (r.get("description") or "")[:200],
                    "category": r.get("language", "Unknown"),
                    "engagement": {"stars": r["stargazers_count"], "forks": r.get("forks_count", 0)},
                    "author": r["owner"]["login"],
                })
        except Exception as e2:
            print(f"  ⚠️ GitHub Search: {e2}", file=sys.stderr)
    return items


# ── Reddit ─────────────────────────────────────────

def fetch_reddit(config):
    items = []
    subreddits = config.get("subreddits", ["technology"])
    for sub in subreddits:
        try:
            url = f"https://api.pullpush.io/reddit/search/submission/?subreddit={sub}&sort=score&sort_type=desc&size=5"
            data = curl_get_json(url)
            for p in data.get("data", [])[:5]:
                items.append({
                    "source": "reddit", "title": p.get("title", ""),
                    "url": f"https://reddit.com{p.get('permalink', '')}",
                    "summary": (p.get("selftext") or "")[:200],
                    "category": f"r/{sub}",
                    "engagement": {"upvotes": p.get("score", 0), "comments": p.get("num_comments", 0)},
                    "author": p.get("author", ""),
                })
        except Exception as e:
            print(f"  ⚠️ Reddit r/{sub}: {e}", file=sys.stderr)
    return items


# ── LinuxDo ────────────────────────────────────────

def fetch_linuxdo(config):
    items = []
    cookie_file = Path.home() / ".playwright-data/linuxdo/cookies.txt"
    headers = {"Accept": "application/json", "Referer": "https://linux.do/"}
    if cookie_file.exists():
        headers["Cookie"] = cookie_file.read_text().strip()
    try:
        data = curl_get_json("https://linux.do/latest.json?order=default", headers=headers)
        topics = data.get("topic_list", {}).get("topics", [])
        for t in topics[:15]:
            items.append({
                "source": "linuxdo", "title": t.get("title", ""),
                "url": f"https://linux.do/t/{t.get('slug', '')}/{t.get('id', '')}",
                "summary": "", "category": str(t.get("category_id", "")),
                "engagement": {"views": t.get("views", 0), "likes": t.get("like_count", 0), "comments": t.get("posts_count", 0)},
            })
    except Exception as e:
        print(f"  ⚠️ LinuxDo: {e}", file=sys.stderr)
    return items


# ── 小红书 ────────────────────────────────────────

def fetch_xiaohongshu(config):
    items = []
    cookie_file = Path.home() / ".playwright-data/xiaohongshu/cookies.txt"
    if not cookie_file.exists():
        print("  ⚠️ 小红书: 需要登录态 cookie", file=sys.stderr)
        return items
    headers = {"Referer": "https://www.xiaohongshu.com/", "Cookie": cookie_file.read_text().strip()}
    try:
        html = curl_get("https://www.xiaohongshu.com/explore", headers=headers)
        match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?})\s*</script>', html, re.DOTALL)
        if match:
            raw = match.group(1).replace("undefined", "null")
            state = json.loads(raw)
            for note in state.get("explore", {}).get("feeds", [])[:15]:
                nd = note.get("noteCard", note)
                items.append({
                    "source": "xiaohongshu", "title": nd.get("title", nd.get("displayTitle", "")),
                    "url": f"https://www.xiaohongshu.com/explore/{note.get('id', '')}",
                    "summary": nd.get("desc", "")[:200], "category": "小红书",
                    "engagement": {"likes": nd.get("interactInfo", {}).get("likedCount", 0)},
                    "author": nd.get("user", {}).get("nickname", ""),
                })
    except Exception as e:
        print(f"  ⚠️ 小红书: {e}", file=sys.stderr)
    return items


# ── 微信公众号 ────────────────────────────────────

def fetch_wechat_mp(config):
    items = []
    cookie_file = Path.home() / ".playwright-data/sogou-weixin/cookies.txt"
    headers = {"Referer": "https://weixin.sogou.com/"}
    if cookie_file.exists():
        headers["Cookie"] = cookie_file.read_text().strip()
    keywords = config.get("keywords", ["AI", "科技", "互联网"])
    for kw in keywords[:3]:
        try:
            url = f"https://weixin.sogou.com/weixin?type=2&query={urllib.parse.quote(kw)}&ie=utf8"
            html = curl_get(url, headers=headers)
            articles = re.findall(r'<a[^>]*href="([^"]*)"[^>]*target="_blank"[^>]*>(.*?)</a>', html, re.DOTALL)
            for href, title_html in articles[:5]:
                title = re.sub(r'<[^>]+>', '', title_html).strip()
                if len(title) > 5 and "sogou" not in title.lower():
                    items.append({
                        "source": "wechat_mp", "title": title,
                        "url": href if href.startswith("http") else f"https://weixin.sogou.com{href}",
                        "summary": "", "category": f"公众号/{kw}", "engagement": {},
                    })
        except Exception as e:
            print(f"  ⚠️ 微信公众号 [{kw}]: {e}", file=sys.stderr)
    return items


def fetch_wechat_video(config):
    print("  ⚠️ 微信视频号: 无公开 API", file=sys.stderr)
    return []


# ── 主流程 ─────────────────────────────────────────

FETCHERS = {
    "weibo": fetch_weibo,
    "zhihu": fetch_zhihu,
    "toutiao": fetch_toutiao,
    "douyin": fetch_douyin,
    "twitter": fetch_twitter,
    "youtube": fetch_youtube,
    "bilibili": fetch_bilibili,
    "github": fetch_github,
    "reddit": fetch_reddit,
    "linuxdo": fetch_linuxdo,
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
