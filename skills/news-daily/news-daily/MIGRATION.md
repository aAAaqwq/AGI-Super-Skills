# Migration Guide: v1 → v2

## Overview

This guide helps you migrate from the original news-fetcher.sh (v1) to the enhanced news-fetcher-v2.sh with support for multiple content types.

## What's New in v2?

### New Features
- ✅ **YouTube video support** (5 AI/Tech channels)
- ✅ **WeChat articles** (5 official accounts)
- ✅ **虎嗅网** (Huxiu) dedicated fetcher
- ✅ **JSON configuration** alongside legacy conf format
- ✅ **Modular fetchers** for easier maintenance
- ✅ **Flexible CLI options** for content selection

### New Sources
| Type | Sources | Count |
|------|---------|-------|
| Articles | + 虎嗅网 | 6 total |
| Videos | Two Minute Papers, Lex Fridman, AI Addict, Fireship, 3Blue1Brown | 5 |
| WeChat | 量子位, 机器之心, 新智元, InfoQ, 雷锋网 | 5 |

## Quick Start

### Option 1: Gradual Migration (Recommended)

**Step 1: Test v2 with articles only**
```bash
cd /home/aa/clawd/skills/news-daily/news-daily/scripts

# Test without pushing
./news-fetcher-v2.sh --types articles

# Verify output looks good
```

**Step 2: Add videos (if you want them)**
```bash
# First, install yt-dlp
pip install yt-dlp

# Test with videos
./news-fetcher-v2.sh --types articles,videos
```

**Step 3: Add WeChat (optional)**
```bash
# Test with WeChat
./news-fetcher-v2.sh --wechat --types articles,videos
```

**Step 4: Update one cron job at a time**
```bash
# Edit crontab
crontab -e

# Change ONE job to v2
# Example: Morning news
0 8 * * * /path/to/news-fetcher-v2.sh --push telegram --types articles,videos >> /path/to/logs/news-morning.log 2>&1

# Monitor for a few days
tail -f /path/to/logs/news-morning.log

# If good, update other jobs
```

### Option 2: Direct Switch (Advanced)

**For users comfortable with debugging:**

1. **Install dependencies:**
   ```bash
   pip install yt-dlp  # For YouTube
   ```

2. **Test all features:**
   ```bash
   ./news-fetcher-v2.sh --push telegram --wechat --types articles,videos
   ```

3. **Update all cron jobs:**
   ```bash
   0 8 * * * /path/to/news-fetcher-v2.sh --push telegram --types articles,videos >> /path/to/logs/news-morning.log 2>&1
   0 13 * * * /path/to/news-fetcher-v2.sh --push telegram --types articles >> /path/to/logs/news-afternoon.log 2>&1
   0 18 * * * /path/to/news-fetcher-v2.sh --push telegram --wechat >> /path/to/logs/news-evening.log 2>&1
   ```

## Configuration Changes

### Old Format (v1) - Still Supported

**news-sources.conf:**
```bash
# Format: NAME|URL|METHOD|PRIORITY|SELECTOR
机器之心|https://www.jiqizhixin.com/|web_search|10|ai
TechCrunch|https://techcrunch.com/|web_search|8|ai
```

### New Format (v2) - Optional

**news-sources.json:**
```json
{
  "sources": {
    "articles": [
      {
        "id": "jiqizhixin",
        "name": "机器之心",
        "type": "article",
        "fetch_method": "web_search",
        "priority": 10,
        "enabled": true
      }
    ],
    "videos": [...],
    "wechat": [...]
  }
}
```

**Note:** You can use both! v2 reads from both formats.

## CLI Options Comparison

### v1 Options
```bash
./news-fetcher.sh [OPTIONS]
  --push <channel>     Push to telegram or whatsapp
  --sources <list>     Comma-separated source list
  --articles <n>       Number of articles (default: 5)
```

### v2 Options (New)
```bash
./news-fetcher-v2.sh [OPTIONS]
  --push <channel>     Push to telegram or whatsapp
  --types <types>      Content types: articles,videos,wechat
  --articles <n>       Number of articles (default: 5)
  --videos <n>         Number of videos (default: 3)
  --wechat             Include WeChat accounts
```

## Migration Scenarios

### Scenario 1: Keep Current Behavior

**Goal:** Use v2 but get same output as v1

**Solution:**
```bash
# v1 command
./news-fetcher.sh --push telegram

# v2 equivalent (articles only, no videos/WeChat)
./news-fetcher-v2.sh --push telegram --types articles
```

### Scenario 2: Add YouTube Videos

**Goal:** Keep articles + add video recommendations

**Solution:**
```bash
# Install yt-dlp first
pip install yt-dlp

# Use v2 with both types
./news-fetcher-v2.sh --push telegram --types articles,videos
```

### Scenario 3: Add WeChat Sources

**Goal:** Include WeChat official accounts

**Solution:**
```bash
# Use v2 with WeChat enabled
./news-fetcher-v2.sh --push telegram --wechat
```

### Scenario 4: Everything

**Goal:** All sources, all types

**Solution:**
```bash
./news-fetcher-v2.sh --push telegram --wechat --types articles,videos
```

## Cron Job Migration

### Before (v1)
```bash
# Morning news
0 8 * * * /home/aa/clawd/skills/news-daily/news-daily/scripts/news-fetcher.sh --push telegram >> /home/aa/clawd/logs/news-morning.log 2>&1
```

### After (v2) - Articles + Videos
```bash
# Morning news with videos
0 8 * * * /home/aa/clawd/skills/news-daily/news-daily/scripts/news-fetcher-v2.sh --push telegram --types articles,videos >> /home/aa/clawd/logs/news-morning.log 2>&1
```

### After (v2) - All Sources
```bash
# Evening news with WeChat
0 18 * * * /home/aa/clawd/skills/news-daily/news-daily/scripts/news-fetcher-v2.sh --push telegram --wechat --types articles,videos >> /home/aa/clawd/logs/news-evening.log 2>&1
```

## Output Format Changes

### v1 Output
```
📰 每日科技早报 | 2025-01-31
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 Article 1...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Today: 5 articles
```

### v2 Output (with videos)
```
📰 每日科技早报 | 2025-01-31
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 Article 1...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 Article 2...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📹 视频推荐
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎬 Video 1...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎬 Video 2...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Today: 5 articles + 2 videos
```

## Rollback Plan

If something goes wrong:

### Quick Rollback
```bash
# Edit crontab
crontab -e

# Change back to v1
0 8 * * * /path/to/news-fetcher.sh --push telegram >> ...
```

### Partial Rollback
```bash
# Keep using v2 but disable problematic features
./news-fetcher-v2.sh --types articles  # Skip videos/WeChat
```

## Dependencies

### v1 Dependencies
- web_fetch tool (OpenClaw)
- web_search tool (OpenClaw)
- bash

### v2 Additional Dependencies
- **yt-dlp** (for YouTube)
  ```bash
  pip install yt-dlp
  ```
- **curl** (for WeChat RSS)
  - Usually pre-installed
- **jq** (optional, for JSON)
  ```bash
  sudo apt-get install jq  # Debian/Ubuntu
  ```

## Testing Checklist

Before switching cron jobs:

- [ ] Test v2 manually with `--types articles`
- [ ] Verify output format looks correct
- [ ] Test push to your channel (telegram/whatsapp)
- [ ] If using videos: Install yt-dlp and test
- [ ] If using WeChat: Test WeRSS availability
- [ ] Check log files for errors
- [ ] Verify all sources are fetching correctly

## Common Issues

### Issue: "yt-dlp not found"
**Fix:**
```bash
pip install yt-dlp
```

### Issue: "YouTube fetch returns empty"
**Possible causes:**
- Network blocking YouTube
- Channel URL changed
- Rate limiting

**Fix:**
```bash
# Skip videos for now
./news-fetcher-v2.sh --types articles
```

### Issue: "WeChat fetch times out"
**Possible causes:**
- WeRSS service down
- Network issues

**Fix:**
```bash
# Skip WeChat for now
./news-fetcher-v2.sh --types articles,videos
```

### Issue: "JSON parse error"
**Possible causes:**
- news-sources.json has syntax error

**Fix:**
```bash
# Validate JSON
cat scripts/news-sources.json | python3 -m json.tool

# Or delete it and use conf format
rm scripts/news-sources.json
```

## Support

### Getting Help

1. **Check logs:**
   ```bash
   tail -f /home/aa/clawd/logs/news-*.log
   ```

2. **Test fetchers individually:**
   ```bash
   cd scripts/fetchers
   ./huxiu-fetcher.sh
   ./youtube-fetcher.sh
   ./wechat-fetcher.sh
   ```

3. **Fallback to v1:**
   - v1 is still available and works
   - Use it while debugging v2 issues

## Summary

| Feature | v1 | v2 |
|---------|----|----|
| Articles | ✅ 5 sources | ✅ 6 sources (+ 虎嗅) |
| Videos | ❌ | ✅ 5 channels |
| WeChat | ❌ | ✅ 5 accounts |
| Config | .conf only | .conf + .json |
| Fetchers | Monolithic | Modular |
| CLI options | Basic | Enhanced |

**Recommendation:** Start with v2 using `--types articles` (same as v1), then gradually enable videos and WeChat after testing.

## Next Steps

1. ✅ **Review this guide**
2. ✅ **Test v2 manually**
3. ✅ **Decide which features to use**
4. ✅ **Update one cron job**
5. ✅ **Monitor for a few days**
6. ✅ **Roll out to other jobs**

Welcome to News Daily v2! 🎉
