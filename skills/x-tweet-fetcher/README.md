# x-tweet-fetcher

Fetch tweets, comments, timelines, and articles from X/Twitter — **without login or API keys**.  
Search WeChat articles, discover tweets by keyword, analyze user profiles.  
One tool for global content intelligence.

An [OpenClaw](https://github.com/openclaw/openclaw) skill. Zero dependencies for basic usage. Python 3.7+.

> **For AI Agents**: All scripts output structured JSON by default. Import as Python modules for direct integration. Exit codes are cron-friendly (0=nothing new, 1=new content found).

## Capabilities

| Feature | Script | Dependencies | Output |
|---------|--------|-------------|--------|
| Fetch single tweet | `fetch_tweet.py` | None | JSON: text, stats, media, quotes |
| Fetch reply comments | `fetch_tweet.py --replies` | Camofox | JSON: threaded comment tree |
| Fetch user timeline | `fetch_tweet.py --user` | Camofox | JSON: tweet list with pagination |
| Fetch X Articles | `fetch_tweet.py --article` | Camofox | JSON: full long-form text |
| Fetch X Lists tweets | `fetch_tweet.py --list` | Camofox | JSON: tweet list with pagination |
| Monitor @mentions | `fetch_tweet.py --monitor` | Camofox | JSON: new mentions since last check |
| **Monitor @mentions via Nitter** | `x_mentions_nitter.py` | Camofox | JSON: new mentions (fast, real-time) |
| **Search WeChat articles** | `sogou_wechat.py` | None | JSON: title, url, author, date |
| **Discover tweets by keyword** | `x_discover.py` | None (DuckDuckGo) or Camofox | JSON: url, title, snippet |
| Search Google | `camofox_client.py` | Camofox | JSON: title, url, snippet |
| Search Google + DuckDuckGo | `camofox_client.py --engine` | Camofox | JSON: title, url, snippet |
| Fetch Chinese platforms | `fetch_china.py` | Weibo/Bilibili/CSDN: Camofox; WeChat: None | JSON: full article content |
| Analyze user profile | `x-profile-analyzer.py` | Camofox + LLM API | Markdown: MBTI, Big Five, topics |
| Check version updates | `version_check.py` | None | Version check thread (silent background) |

## Quick Start

### For Agents (Python import)

```python
# Fetch a tweet
from scripts.fetch_tweet import fetch_tweet
tweet = fetch_tweet("https://x.com/user/status/123456")
# Returns: {"text": "...", "likes": 91, "retweets": 23, "views": 14468, ...}

# Search WeChat articles (no API key needed)
from scripts.sogou_wechat import sogou_wechat_search
articles = sogou_wechat_search("AI Agent", max_results=10)
# Returns: [{"title": "...", "url": "...", "author": "...", "date": "..."}, ...]

# Discover tweets by keyword
from scripts.x_discover import discover_tweets
result = discover_tweets(["AI Agent", "automation"], max_results=5)
# Returns: {"total_new": 3, "finds": [{"url": "...", "title": "...", "snippet": "..."}, ...]}

# Search Google (via Camofox, no API key)
from scripts.camofox_client import camofox_search
results = camofox_search("fetch tweets without API key")
# Also supports: camofox_search("query", engine="duckduckgo")
```

### CLI Usage

```bash
# Fetch tweet (JSON)
python3 scripts/fetch_tweet.py --url "https://x.com/user/status/123456"

# Fetch tweet (human readable)
python3 scripts/fetch_tweet.py --url "https://x.com/user/status/123456" --text-only

# Search WeChat articles
python3 scripts/sogou_wechat.py --keyword "AI Agent" --limit 10 --json

# Discover tweets
python3 scripts/x_discover.py --keywords "AI Agent,LLM tools" --limit 5 --json

# Fetch comments (requires Camofox)
python3 scripts/fetch_tweet.py --url "https://x.com/user/status/123456" --replies

# Monitor mentions (cron-friendly, exit code 1 = new mentions)
python3 scripts/fetch_tweet.py --monitor @username

# Fetch Chinese platforms (auto-detect: Weibo/Bilibili/CSDN/WeChat)
python3 scripts/fetch_china.py --url "https://mp.weixin.qq.com/s/..."

# Google search (no API key)
python3 scripts/camofox_client.py "OpenClaw AI agent"
python3 scripts/camofox_client.py --engine duckduckgo "OpenClaw AI agent"

# User profile analysis (MBTI/Big Five/topics)
python3 scripts/x-profile-analyzer.py --user elonmusk --count 100
```

## Cron Integration

All monitoring scripts use exit codes for automation:
- `0` — No new content
- `1` — New content found
- `2` — Error

```bash
# Check mentions every 30 min
*/30 * * * * python3 fetch_tweet.py --monitor @username --text-only || notify-send "New mentions!"

# Discover new tweets daily
0 9 * * * python3 x_discover.py --keywords "AI Agent" --cache ~/.cache/discover.json --json >> ~/discoveries.jsonl
```

## Camofox Setup (Optional)

Required only for: comments, timelines, mentions monitoring, Google search, non-WeChat Chinese platforms.

```bash
# Option 1: OpenClaw plugin
openclaw plugins install @askjo/camofox-browser

# Option 2: Standalone
git clone https://github.com/jo-inc/camofox-browser
cd camofox-browser && npm install && npm start  # Port 9377
```

[Camofox](https://github.com/jo-inc/camofox-browser) is built on [Camoufox](https://camoufox.com) — a Firefox fork with C++ level fingerprint spoofing. Bypasses Google, Cloudflare, and most anti-bot detection.

## How It Works

- **Basic tweets**: [FxTwitter](https://github.com/FxEmbed/FxEmbed) public API (no auth needed)
- **Comments/Timeline/Mentions**: Camofox browser rendering + parsing
- **WeChat search**: Sogou WeChat search (direct HTTP, no browser needed)
- **Tweet discovery**: DuckDuckGo search with Camofox Google fallback
- **Chinese platforms**: Direct HTTP for WeChat; Camofox for others

## Use Cases

- **Content monitoring**: Track mentions, discover trending topics, monitor competitors
- **Research**: Analyze user profiles, collect tweet datasets, search WeChat articles
- **Automation**: Cron-based monitoring with structured JSON output for downstream processing
- **Multi-language intelligence**: English (X/Twitter) + Chinese (WeChat/Weibo/Bilibili/CSDN) in one tool

## Requirements

- Python 3.7+
- **Camofox** (optional, for advanced features)
- `duckduckgo-search` (optional, for tweet discovery without Camofox)

## License

MIT
