#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
韭研公社个股产业逻辑/异动解析爬取器
用法: python3 fetch_stock_logic.py "白银有色" [--out out.json] [--max-actions 15] [--article-dir dir]
输出: JSON {stock, actions, articles, pagination}
原理: 站内搜索页 SSR HTML 内嵌 window.__NUXT__ JSON, 无需登录。
tab: 1=全部 2=标题标签 5=异动 8=纪要 product=红宝书 announcement=公告 stock=股票 user=用户
"""
import argparse, json, os, re, subprocess, sys, time, urllib.parse, urllib.request

BASE = "https://www.jiuyangongshe.com"
# 多 UA 轮换（降低指纹识别风险）
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36 Edg/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]
UA_COUNTER = {"i": 0}
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXTRACT_JS = os.path.join(SCRIPT_DIR, "extract_nuxt.js")
# 全局请求间隔（秒），由 --delay 控制
DELAY_SECONDS = 4.0
_last_request_ts = [0.0]


def _rotate_ua():
    """轮换 UA，每次请求取下一个。"""
    UA_COUNTER["i"] += 1
    return USER_AGENTS[UA_COUNTER["i"] % len(USER_AGENTS)]


def _throttle():
    """限速：确保相邻请求间隔 >= DELAY_SECONDS。"""
    elapsed = time.time() - _last_request_ts[0]
    if elapsed < DELAY_SECONDS:
        time.sleep(DELAY_SECONDS - elapsed)
    _last_request_ts[0] = time.time()


def http_get(url, timeout=60, retries=3, delay=2.0):
    """带重试 + UA 轮换 + 限速的 GET，返回响应文本。SSR 慢且间歇 500，必须重试。"""
    last_err = None
    for attempt in range(retries):
        _throttle()
        try:
            ua = _rotate_ua()
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Language": "zh-CN,zh;q=0.9"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries} attempts: {url} :: {last_err}")


def extract_nuxt(html, cache_path=None):
    """从 SSR HTML 提取 window.__NUXT__ 对象。优先用 Node eval（最稳）。"""
    if "window.__NUXT__" not in html:
        return None
    if os.path.exists(EXTRACT_JS):
        tmp_in = cache_path + ".html" if cache_path else "/tmp/_nuxt_in.html"
        tmp_out = cache_path + ".json" if cache_path else "/tmp/_nuxt_out.json"
        with open(tmp_in, "w", encoding="utf-8") as f:
            f.write(html)
        r = subprocess.run(["node", EXTRACT_JS, tmp_in, tmp_out], capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and os.path.exists(tmp_out):
            with open(tmp_out, "r", encoding="utf-8") as f:
                return json.load(f)
        # node 失败则回退正则
    m = re.search(r"window\.__NUXT__=\(function\([^)]*\)\{return (.*?)\}\);?\s*</script>", html, re.S)
    if not m:
        m = re.search(r"window\.__NUXT__\s*=\s*(\{.*?\});?\s*</script>", html, re.S)
    if m:
        try:
            return json.loads(re.sub(r"undefined", "null", m.group(1)))
        except Exception:
            return None
    return None


def search_tab(name, tab, page=1):
    """请求搜索页某 tab，返回 (data dict, raw nuxt)。"""
    q = urllib.parse.quote(name)
    url = f"{BASE}/search/x?k={q}&type={tab}"
    html = http_get(url)
    nuxt = extract_nuxt(html, cache_path=f"/tmp/jyg_{tab}")
    if not nuxt or not nuxt.get("data"):
        return None, None
    return nuxt["data"][0], nuxt


def fetch(name, max_actions=15, article_dir=None):
    name = name.strip()
    result = {"query": name, "stock": None, "actions": [], "articles": [], "pagination": {}, "note": []}

    # 1) stock tab: 股票实体
    data, _ = search_tab(name, "stock")
    if data:
        sl = data.get("list") or []
        if sl and isinstance(sl[0], dict) and sl[0].get("stock_id"):
            result["stock"] = {
                "stock_id": sl[0].get("stock_id"),
                "name": sl[0].get("name"),
                "code": sl[0].get("code"),
                "node": sl[0].get("node"),
            }
        pg = data.get("paginate") or {}
        if pg:
            result["pagination"]["stock"] = {"totalCount": pg.get("totalCount", 0)}
        if not result["stock"] and data.get("checkStock") == -1:
            result["note"].append("该股可能未被韭研公社收录（checkStock=-1）")

    # 2) type=5 异动解析
    data, _ = search_tab(name, "5")
    if data:
        lst = data.get("list") or []
        for item in lst[:max_actions]:
            result["actions"].append({
                "title": item.get("title"),
                "content": item.get("content"),
                "article_id": item.get("article_id"),
                "create_time": item.get("create_time"),
                "sync_time": item.get("sync_time"),
                "integral": item.get("integral"),
                "like_count": item.get("like_count"),
                "author": (item.get("user") or {}).get("nickname"),
                "stock_list": item.get("stock_list"),
            })
        pg = data.get("paginate") or {}
        result["pagination"]["actions"] = {"totalCount": pg.get("totalCount", 0), "pageSize": pg.get("pageSize", 15)}
        if pg.get("totalCount", 0) > len(result["actions"]):
            result["note"].append(f"异动解析共 {pg['totalCount']} 条，SSR 仅公开第一页 {len(result['actions'])} 条（分页需登录）")

    # 3) type=1 全部相关文章
    data, _ = search_tab(name, "1")
    if data:
        lst = data.get("list") or []
        for item in lst[:15]:
            result["articles"].append({
                "title": item.get("title"),
                "article_id": item.get("article_id"),
                "create_time": item.get("create_time"),
                "author": (item.get("user") or {}).get("nickname"),
                "type": item.get("type"),
                "integral": item.get("integral"),
                "stock_list": [s.get("name") for s in (item.get("stock_list") or [])],
            })
        pg = data.get("paginate") or {}
        result["pagination"]["articles"] = {"totalCount": pg.get("totalCount", 0), "pageSize": pg.get("pageSize", 15)}
        if not result["actions"] and not result["articles"] and not result["stock"]:
            result["note"].append("站内无该股任何数据")

    # 4) 可选：抓文章详情
    if article_dir and result["actions"]:
        os.makedirs(article_dir, exist_ok=True)
        for a in result["actions"][:3]:
            try:
                html = http_get(f"{BASE}/a/{a['article_id']}", timeout=90)
                with open(os.path.join(article_dir, f"{a['article_id']}.html"), "w", encoding="utf-8") as f:
                    f.write(html)
            except Exception as e:
                result["note"].append(f"详情页 {a['article_id']} 抓取失败: {e}")

    return result


def main():
    ap = argparse.ArgumentParser(description="韭研公社个股产业逻辑/异动解析爬取")
    ap.add_argument("stock", help="个股名，如 白银有色")
    ap.add_argument("--out", default=None, help="JSON 输出路径（默认 stdout）")
    ap.add_argument("--max-actions", type=int, default=15, help="异动解析最大条数（默认15=SSR第一页）")
    ap.add_argument("--article-dir", default=None, help="可选：抓前3篇详情页 HTML 到该目录")
    ap.add_argument("--delay", type=float, default=4.0, help="请求间隔秒数（默认4，批量时建议>=5）")
    args = ap.parse_args()

    global DELAY_SECONDS
    DELAY_SECONDS = args.delay

    result = fetch(args.stock, max_actions=args.max_actions, article_dir=args.article_dir)
    out = json.dumps(result, ensure_ascii=False, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"saved: {args.out}")
    else:
        print(out)


if __name__ == "__main__":
    main()
