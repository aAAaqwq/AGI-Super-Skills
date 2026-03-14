---
name: telegram-scraper-run
description: Automatic Telegram scraping
---
# Telegram Scraper Run

> Runs the Telegram Scraper Agent manually for testing or unscheduled scanning.

## When to use

- "run telegram scraper"
- "scan telegram channels"
- "find new channels with AI"
- "check competitors on Telegram"

## Input

Optional:
- `--dry-run` - test run without notifications
- `--category <name>` - scan only one category (competitors/industry/advertising)
- `--no-messages` - skip reading messages (faster)
- `--notify-test` - notification test only

## How to execute

### Full run (production)

```bash
cd $AGENTS_PATH/telegram-scraper
python3 telegram_scraper_agent.py
```

### Dry-run tests

```bash
# Test without notifications
python3 telegram_scraper_agent.py --dry-run

# Single category
python3 telegram_scraper_agent.py --category competitors --dry-run

# Without reading messages (faster)
python3 telegram_scraper_agent.py --no-messages --dry-run
```

### Notification test

```bash
python3 telegram_scraper_agent.py --notify-test
```

### Unit tests

```bash
python3 test_telegram_scraper.py
```

## Output

Agent outputs:
1. Progress to stderr (channel scanning)
2. Summary to stdout (results from Claude)
3. Telegram notification (if high-value channels found)

Data is saved to:
```
$PROJECT_ROOT/data/telegram_scraper/
├── YYYY-MM-DD/           # Dated results
│   ├── competitors_channels.json
│   ├── competitors_ad_contacts.csv
│   ├── industry_channels.json
│   ├── advertising_channels.json
│   └── messages/
└── latest/               # Symlinks to most recent
```

## Checking results

```bash
# Latest results
ls -l $PROJECT_ROOT/data/telegram_scraper/latest/

# Top 5 channels (competitors)
cat $PROJECT_ROOT/data/telegram_scraper/latest/competitors_channels.json | jq '.[0:5]'

# Ad contacts
cat $PROJECT_ROOT/data/telegram_scraper/latest/competitors_ad_contacts.csv

# Agent log
cat $PROJECT_ROOT/data/telegram_scraper/agent_log.json | jq '.[-5:]'
```

## Configuration

Edit config:
```bash
code $PROJECT_ROOT/data/telegram_scraper_config.json
```

Config structure:
```json
{
  "categories": {
    "competitors": {
      "keywords": ["annotation", "data labeling", "cvat"],
      "exclude": ["spam", "crypto"],
      "scan_posts": 10
    }
  },
  "min_subscribers": 100,
  "min_score": 10,
  "notification_threshold": 30
}
```

## Launchd Schedule

Agent runs automatically twice daily (9:00, 18:00).

```bash
# Check status
launchctl list | grep telegram-scraper

# Load schedule
launchctl load ~/Library/LaunchAgents/com.yourcompany.telegram-scraper.plist

# Unload schedule
launchctl unload ~/Library/LaunchAgents/com.yourcompany.telegram-scraper.plist

# View logs
tail -f $GOOGLE_TOOLS_PATH/logs/telegram_scraper.log
tail -f $GOOGLE_TOOLS_PATH/logs/telegram_scraper.err
```

## Troubleshooting

### Session Expired Error

If Telegram session is invalid:
```bash
# Refresh session
cd $TG_TOOLS_PATH
python3 -m tg_utils.auth
```

### No Results

- Check keywords in config (too specific?)
- Verify session: `cd $TG_TOOLS_PATH && python3 -m tg_utils.auth`
- Run with `--dry-run` for debug

### Rate Limited

- Normal: agent waits and retries
- FloodWaitError > 5 min: channel skipped
- Solution: decrease `scan_posts` in config

## Manual Scraping (without the agent)

If the agent is not working:
```bash
cd $TG_TOOLS_PATH/tools

# Find channels with ad contacts
python3 tg_scrape.py ads --keywords "annotation,labeling" --posts 10

# List channels
python3 tg_scrape.py channels --keywords "ai,ml" --output channels.csv

# Read messages
python3 tg_scrape.py messages "Channel Name" --days 7 --limit 50
```

## Next steps

After scraping:

1. **Add contacts to CRM**: use `add-lead` skill
2. **Write outreach**: use `telegram-send` skill
3. **Adjust config**: edit config file and re-run

## Related skills

- `telegram-session` - update Telegram session
- `add-lead` - add found contacts to CRM
- `telegram-send` - message ad contacts
- `daily-briefing` - include findings in morning briefing
