---
name: telegram-scrape
description: Search Telegram channels, read posts, ad contacts
---
# Telegram Scrape

> Search channels, read messages, analyze ad contacts

## When to use

- "find AI channels on telegram"
- "show messages from a channel"
- "find ad contacts of channels"
- "where can I buy ads"
- "scraping telegram channels"

## Tool

`$TG_TOOLS_PATH/tools/tg_scrape.py`

## How to run

### Search channels by keywords

```bash
# Find channels with "ai" or "cursor" in the name
python3 $TG_TOOLS_PATH/tools/tg_scrape.py channels --keywords "ai,cursor"

# Save to CSV
python3 $TG_TOOLS_PATH/tools/tg_scrape.py channels --keywords "ai" --output channels.csv

# Save to JSON (more data: about, links)
python3 $TG_TOOLS_PATH/tools/tg_scrape.py channels --keywords "ai" --output channels.json

# With exclusions
python3 $TG_TOOLS_PATH/tools/tg_scrape.py channels --keywords "ai" --exclude "spam,nsfw"
```

Output: title, username, link, subscribers, ad_contacts, ad_links, about.

### Read channel/group messages

```bash
# Last 20 messages
python3 $TG_TOOLS_PATH/tools/tg_scrape.py messages "Channel Name" --limit 20

# From the last 7 days
python3 $TG_TOOLS_PATH/tools/tg_scrape.py messages "Channel Name" --days 7
```

Channel Name -- search by substring (case-insensitive).

### Search for ad contacts

```bash
python3 $TG_TOOLS_PATH/tools/tg_scrape.py ads --keywords "ai,cursor" --posts 10
```

Analyzes:
- Channel description (looks for @username, t.me/ links, words "ad", "ads", "price")
- Last N posts (keyword mentions)
- Calculates relevance score

Output (JSON stdout): title, username, subscribers, score, ad_contacts, keyword_mentions, sample_posts.

## Parameters

| Command | Parameter | Description |
|---------|-----------|-------------|
| `channels` | `--keywords, -k` | Keywords comma-separated |
| `channels` | `--exclude, -x` | Exclude (comma-separated) |
| `channels` | `--output, -o` | File (.csv or .json) |
| `messages` | `channel` | Channel/group name |
| `messages` | `--limit, -n` | Max messages (default: 20) |
| `messages` | `--days, -d` | Only from last N days |
| `ads` | `--keywords, -k` | Keywords (required) |
| `ads` | `--exclude, -x` | Exclude |
| `ads` | `--posts, -p` | Posts to analyze (default: 10) |

## Limitations

- Searches only among channels you are subscribed to
- GetFullChannelRequest has rate limits
- 0.2-0.3 sec delay between channels (automatic)

## Related skills

- `telegram-groups` -- group operations
- `telegram-send` -- sending messages (e.g. to advertisers)
