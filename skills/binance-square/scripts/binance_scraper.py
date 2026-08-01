#!/usr/bin/env python3
"""
Binance Square Scraper — CDP extraction only (no LLM)
Saves raw posts to JSON for the agent to classify.

Usage: python3 binance_scraper.py
Output: data/binance_raw_posts.json
"""
import asyncio, json, sys, time, urllib.request, os
import websockets

# ── Config ──────────────────────────────────────
CDP_BASE = "http://127.0.0.1:9222"
BINANCE_SQUARE = "https://www.binance.com/en/square"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(SCRIPT_DIR)
OUTPUT_FILE = os.path.join(WORKSPACE, "data", "binance_raw_posts.json")
DEDUP_FILE = os.path.join(WORKSPACE, "data", "binance_square_last_scan.json")

# ── CDP Helpers ─────────────────────────────────
async def get_binance_tab():
    tabs = json.loads(urllib.request.urlopen(f"{CDP_BASE}/json").read())
    for t in tabs:
        url = t.get("url", "")
        if "binance.com/en/square" in url and not url.startswith("blob:"):
            return t["webSocketDebuggerUrl"], t["id"]
    for t in tabs:
        if "binance.com" in t.get("url", "") and not t.get("url", "").startswith("blob:"):
            return t["webSocketDebuggerUrl"], t["id"]
    raise RuntimeError("No Binance tab found. Open https://www.binance.com/en/square in Chrome.")

async def cdp(ws, method, params=None):
    msg_id = int(time.time() * 1000000) % 1000000
    await ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == msg_id:
            if "error" in resp:
                raise RuntimeError(f"CDP error [{method}]: {resp['error']}")
            return resp.get("result", {})

# ── Scraping ────────────────────────────────────
async def scrape():
    ws_url, tab_id = await get_binance_tab()
    print(f"[CDP] Tab: {tab_id}", file=sys.stderr)

    async with websockets.connect(ws_url, max_size=20*1024*1024) as ws:
        await cdp(ws, "Runtime.enable")
        await cdp(ws, "Page.enable")

        # Navigate
        print("[*] Navigating...", file=sys.stderr)
        await cdp(ws, "Page.navigate", {"url": BINANCE_SQUARE})
        await asyncio.sleep(6)

        # Scroll
        print("[*] Scrolling...", file=sys.stderr)
        scroll_js = """
        (async () => {
            const selectors = ['[class*="feed"]', '[class*="Feed"]', '[class*="content"]', 'main', '#__APP'];
            let target = document.body;
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el && el.scrollHeight > window.innerHeight) { target = el; break; }
            }
            for (let i = 0; i < 10; i++) {
                target.scrollBy(0, 600);
                await new Promise(r => setTimeout(r, 1200));
            }
            return 'done';
        })()
        """
        await cdp(ws, "Runtime.evaluate", {"expression": scroll_js, "awaitPromise": True})
        await asyncio.sleep(3)

        # Extract
        print("[*] Extracting...", file=sys.stderr)
        extract_js = """
        (() => {
            const results = [];
            const seen = new Set();

            function addPost(el) {
                const text = el.textContent.trim();
                if (text.length < 30) return;
                const key = text.substring(0, 100);
                if (seen.has(key)) return;
                seen.add(key);

                const a = el.querySelector('a[href*="/square/post"]') || el.querySelector('a[href*="/post"]');
                const timeEl = el.querySelector('time, [class*="time"], [class*="Time"], [class*="date"], [class*="Date"]');
                const authorEl = el.querySelector('[class*="author"], [class*="Author"], [class*="name"], [class*="Name"], [class*="nickname"]');

                results.push({
                    url: a ? (a.href.startsWith('http') ? a.href : 'https://www.binance.com' + a.getAttribute('href')) : '',
                    text: text.substring(0, 600),
                    time: timeEl ? (timeEl.textContent || timeEl.getAttribute('datetime') || '') : '',
                    author: authorEl ? authorEl.textContent.trim() : ''
                });
            }

            // Strategy 1: post links → parent card
            document.querySelectorAll('a[href*="/square/post"]').forEach(a => {
                const card = a.closest('div[class]') || a.closest('article') || a.closest('section') || a.closest('li');
                if (card) addPost(card);
            });

            // Strategy 2: class-based feed items
            document.querySelectorAll(
                '[class*="FeedItem"], [class*="feed-item"], [class*="PostItem"], [class*="post-item"], ' +
                '[class*="PostCard"], [class*="post-card"], [class*="Article"], [class*="article"]'
            ).forEach(el => addPost(el));

            // Strategy 3: articles
            if (results.length < 10) {
                document.querySelectorAll('article, [role="article"]').forEach(el => addPost(el));
            }

            return {posts: results.slice(0, 40), url: location.href, count: results.length};
        })()
        """
        result = await cdp(ws, "Runtime.evaluate", {"expression": extract_js, "returnByValue": True})
        data = result.get("result", {}).get("value", {})
        posts = data.get("posts", [])

        # Save
        output = {
            "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source_url": data.get("url", BINANCE_SQUARE),
            "count": len(posts),
            "posts": posts
        }
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"[OK] {len(posts)} posts → {OUTPUT_FILE}", file=sys.stderr)
        return posts

async def main():
    print("=" * 50, file=sys.stderr)
    print("[START] Binance Square Scraper", file=sys.stderr)

    try:
        urllib.request.urlopen(f"{CDP_BASE}/json/version", timeout=3)
    except Exception as e:
        print(f"[FAIL] Chrome CDP not available: {e}", file=sys.stderr)
        output = {"error": "Chrome CDP not running on port 9222", "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "count": 0, "posts": []}
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f)
        return False

    try:
        posts = await scrape()
        return True
    except Exception as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        output = {"error": str(e)[:300], "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "count": 0, "posts": []}
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f)
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
